"""Offline OPEN-only desktop campaign using the accepted research engines.

This adapter owns search, chronology, evidence and create-only report output.
It grants no lifecycle or trading authority.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Context, Decimal, localcontext
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import Symbol
from trading_bot.experiments.historical_research_dataset import (
    HistoricalResearchDatasetSnapshot,
    HistoricalResearchPartitionManifest,
)
from trading_bot.experiments.historical_research_desktop import (
    DesktopResearchStorage,
    load_desktop_open_research,
)
from trading_bot.experiments.research_strategy_backtest import (
    ResearchStrategyBacktestEvidence,
    derive_backtest_run_id,
    historical_data_fingerprint,
    run_research_strategy_backtest,
    verify_research_strategy_backtest,
)
from trading_bot.experiments.research_strategy_definition import (
    ResearchStrategyDefinition,
    ResearchStrategyEvaluationPolicy,
)
from trading_bot.experiments.research_strategy_walk_forward import (
    ResearchStrategyWalkForwardEvidence,
    ResearchStrategyWalkForwardFold,
    run_research_strategy_walk_forward,
    verify_research_strategy_walk_forward,
)
from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult
from trading_bot.strategies.moving_average import MovingAverageCrossoverConfig

SCHEMA = "desktop-research-campaign/v1"
NAMESPACE = UUID("3355b98c-3fa0-579a-ab87-0213d1d8883c")
REPORTS_ROOT = Path(r"F:\AI\ai-trading-bot\reports\research\desktop-v1")
MAX_ARTIFACT_BYTES = 10_000_000
SHORT_WINDOWS = tuple(range(5, 61, 5))
LONG_WINDOWS = tuple(range(40, 251, 10))
GRID = tuple(
    (short, long) for short in SHORT_WINDOWS for long in LONG_WINDOWS if short < long
)
SHORTLIST_SIZE = 32
RANKING_POLICY = "development-total-return-desc/drawdown-asc/short-long-asc/v1"
DEVELOPMENT_START = datetime(2016, 1, 1, tzinfo=UTC)
DEVELOPMENT_END = datetime(2020, 1, 1, tzinfo=UTC)
OPEN_END = datetime(2024, 1, 1, tzinfo=UTC)


class DesktopCampaignError(ValueError):
    """Incomplete, conflicting or noncanonical evidence; stop, never retry."""


def _json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise DesktopCampaignError("duplicate field")
        result[key] = value
    return result


def _reject(value: str) -> None:
    raise DesktopCampaignError("nonfinite JSON")


def _parse(body: bytes) -> dict:
    if type(body) is not bytes or len(body) > MAX_ARTIFACT_BYTES:
        raise DesktopCampaignError("artifact size/type rejected")
    try:
        raw = json.loads(body, object_pairs_hook=_pairs, parse_constant=_reject)
        if type(raw) is not dict or _json(raw) != body:
            raise DesktopCampaignError("canonical JSON object required")
        return raw
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise DesktopCampaignError("malformed campaign JSON") from None


def _material(value: object) -> tuple[str, ...]:
    # Typed semantic fields, never artifact bytes, paths, clocks or hashes.
    if type(value) is dict:
        return (
            "object",
            str(len(value)),
            *(x for k in sorted(value) for x in (k, *_material(value[k]))),
        )
    if type(value) in (tuple, list):
        return (
            "sequence",
            str(len(value)),
            *(x for v in value for x in _material(v)),
        )
    if value is None:
        return ("null",)
    if type(value) is bool:
        return ("bool", str(value))
    if type(value) in (str, int):
        return (type(value).__name__, str(value))
    raise DesktopCampaignError("unsupported semantic identity material")


def _identity(kind: str, value: object) -> str:
    material = (SCHEMA, kind, *_material(value))
    return str(uuid5(NAMESPACE, "".join(f"{len(v.encode())}:{v}" for v in material)))


def _source(head: str, tree: str) -> None:
    if any(
        type(v) is not str or not re.fullmatch("[0-9a-f]{40}", v) for v in (head, tree)
    ):
        raise DesktopCampaignError("exact source HEAD/TREE required")


def _decimal(value: Decimal) -> str:
    if type(value) is not Decimal or not value.is_finite():
        raise DesktopCampaignError("finite Decimal required")
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _read_decimal(value: str) -> Decimal:
    if type(value) is not str or len(value) > 100:
        raise DesktopCampaignError("bounded decimal text required")
    try:
        parsed = Decimal(value)
        if _decimal(parsed) != value:
            raise DesktopCampaignError("canonical decimal required")
        return parsed
    except ArithmeticError:
        raise DesktopCampaignError("invalid decimal") from None


def _date(year: int) -> datetime:
    return datetime(year, 1, 1, tzinfo=ZoneInfo("America/New_York")).astimezone(UTC)


@dataclass(frozen=True, slots=True)
class DesktopCampaignDatasetBinding:
    profile: str
    acquisition_source_head: str
    acquisition_source_tree: str
    acquisition_attempt_id: str
    session_authority_identity: str
    session_authority_digest: str
    snapshot_identity: str
    full_historical_fingerprint: str
    open_manifest_identity: str
    open_normalized_sha256: str
    open_row_count: int
    open_first_timestamp: str
    open_last_timestamp: str
    corporate_action_sha256: str
    acquisition_evidence_sha256: str

    def __post_init__(self) -> None:
        _source(self.acquisition_source_head, self.acquisition_source_tree)
        if (
            self.profile != "desktop-v1"
            or type(self.open_row_count) is not int
            or self.open_row_count <= 0
        ):
            raise DesktopCampaignError("invalid dataset binding")
        for name in (
            "acquisition_attempt_id",
            "snapshot_identity",
            "full_historical_fingerprint",
            "open_manifest_identity",
        ):
            value = getattr(self, name)
            if type(value) is not str or str(UUID(value)) != value:
                raise DesktopCampaignError("canonical binding UUID required")
        for name in (
            "session_authority_digest",
            "open_normalized_sha256",
            "corporate_action_sha256",
            "acquisition_evidence_sha256",
        ):
            value = getattr(self, name)
            if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
                raise DesktopCampaignError("binding SHA256 required")
        if (
            type(self.session_authority_identity) is not str
            or not self.session_authority_identity
        ):
            raise DesktopCampaignError("session authority required")
        first, last = (
            datetime.fromisoformat(v)
            for v in (self.open_first_timestamp, self.open_last_timestamp)
        )
        if (
            first.tzinfo is None
            or last.tzinfo is None
            or not DEVELOPMENT_START <= first <= last < OPEN_END
        ):
            raise DesktopCampaignError("OPEN endpoints rejected")


ACCEPTED_DATASET_BINDING = DesktopCampaignDatasetBinding(
    "desktop-v1",
    "108ba9dee6ad593b3f4128ae44750d9f685ffa0d",
    "5652ec3e019766a66a05a9588e79e6cc8c46d70c",
    "a81baba7-7123-45eb-945d-9fb048e24607",
    "nyse-published-regular-sessions-2016-2026-v1",
    "7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1",
    "cf9cb708-89ab-589f-a75c-add17dba25a4",
    "5ebeb399-b97b-5c72-90c4-b1f764fd3109",
    "19ac19ef-aeed-5fcd-a3ee-7e55cec15796",
    "45212bab5eab3c618c6c38d0ae00c8f06fecc4e6b025bc9ff3837920aa545421",
    2012,
    "2016-01-04T05:00:00+00:00",
    "2023-12-29T05:00:00+00:00",
    "9b6a6dbc45f1c5f12e8576b3bf943dec44868ef43e4ec441f37f8ce7fd9a573b",
    "5b90637cd434402962561a42d398cb925bc069420f5d322b55e40ad3cfaeb8f0",
)


def bind_desktop_dataset(
    storage: DesktopResearchStorage,
    *,
    test_binding: DesktopCampaignDatasetBinding | None = None,
) -> DesktopCampaignDatasetBinding:
    """Compare metadata commitments to the P2 freeze, without sealed prices."""
    if type(storage) is not DesktopResearchStorage or (
        test_binding is not None and not storage.test_only
    ):
        raise DesktopCampaignError("dataset test seam rejected")
    expected = ACCEPTED_DATASET_BINDING if test_binding is None else test_binding
    evidence_bytes = storage.read("evidence.json")
    # P2 metadata includes non-price holdout commitments, never OHLCV.
    evidence = json.loads(
        evidence_bytes, object_pairs_hook=_pairs, parse_constant=_reject
    )
    snapshot = HistoricalResearchDatasetSnapshot.from_json(
        storage.read("manifests/snapshot.json").decode()
    )
    opened = HistoricalResearchPartitionManifest.from_json(
        storage.read("manifests/open.json").decode()
    )
    actual = DesktopCampaignDatasetBinding(
        evidence["profile"],
        evidence["source_head"],
        evidence["source_tree"],
        evidence["attempt_id"],
        evidence["calendar_identity"],
        evidence["calendar_sha256"],
        str(snapshot.snapshot_id),
        str(snapshot.full_historical_data_fingerprint),
        str(opened.manifest_id),
        opened.normalized_file_sha256,
        opened.row_count,
        opened.first_bar_timestamp.isoformat(),
        opened.last_bar_timestamp.isoformat(),
        opened.corporate_action_sha256,
        sha256(evidence_bytes).hexdigest(),
    )
    if (
        actual != expected
        or evidence["snapshot"] != json.loads(snapshot.to_json())
        or evidence["open_manifest"] != json.loads(opened.to_json())
    ):
        raise DesktopCampaignError("dataset differs from the exact accepted P2 binding")
    return actual


def evaluation_policy() -> ResearchStrategyEvaluationPolicy:
    """Fixed research economics; trading_enabled is the offline risk flag."""
    return ResearchStrategyEvaluationPolicy(
        starting_cash=Decimal("100000"),
        fixed_commission=Decimal("1"),
        slippage_basis_points=Decimal("5"),
        trading_enabled=True,
        allow_missing_sessions=True,
        max_position_percent=Decimal("1"),
        max_total_exposure_percent=Decimal("1"),
        max_order_notional=None,
        max_new_position_percent=None,
        minimum_cash_reserve_percent=Decimal("0"),
        allow_fractional_shares=False,
        fractional_increment=Decimal("1"),
        allow_buying=True,
        allow_selling=True,
        estimated_commission=Decimal("1"),
    )


def fold_plan() -> tuple[ResearchStrategyWalkForwardFold, ...]:
    """Accepted disjoint chronology; no expanding-window reinterpretation."""
    return (
        ResearchStrategyWalkForwardFold(
            _date(2016), _date(2020), _date(2020), _date(2021)
        ),
        ResearchStrategyWalkForwardFold(
            _date(2021), _date(2022), _date(2022), _date(2024)
        ),
    )


def development_data(data: HistoricalDataResult) -> HistoricalDataResult:
    bars = tuple(
        b for b in data.bars if DEVELOPMENT_START <= b.timestamp < DEVELOPMENT_END
    )
    if not bars:
        raise DesktopCampaignError("empty DEVELOPMENT interval")
    return HistoricalDataResult(
        HistoricalDataRequest(
            data.request.symbol,
            _date(2016),
            _date(2020),
            data.request.timeframe,
            data.request.adjustment,
        ),
        bars,
        data.provider_name,
    )


def campaign_open_projection(data: HistoricalDataResult) -> HistoricalDataResult:
    """Preserve all OPEN bars; express request dates in the engine's NY calendar.

    P2 UTC request bounds remain immutable. This additive research projection
    changes request metadata only, with its own historical fingerprint.
    """
    if any(not DEVELOPMENT_START <= bar.timestamp < OPEN_END for bar in data.bars):
        raise DesktopCampaignError("non-OPEN observation in campaign input")
    return HistoricalDataResult(
        HistoricalDataRequest(
            data.request.symbol,
            _date(2016),
            _date(2024),
            data.request.timeframe,
            data.request.adjustment,
        ),
        data.bars,
        data.provider_name,
    )


def _definition(
    head: str, tree: str, short: int, long: int
) -> ResearchStrategyDefinition:
    return ResearchStrategyDefinition(
        head,
        tree,
        Symbol("SPY"),
        MovingAverageCrossoverConfig(short, long, Decimal("100")),
    )


def _context(binding: DesktopCampaignDatasetBinding, head: str, tree: str) -> dict:
    _source(head, tree)
    grid = {
        "version": "ma-grid/v1",
        "short_windows": SHORT_WINDOWS,
        "long_windows": LONG_WINDOWS,
        "constraint": "short < long",
        "ordering": "short-then-long-ascending",
        "count": len(GRID),
        "desired_quantity": "100",
    }
    return {
        "schema": SCHEMA,
        "dataset_binding": asdict(binding),
        "source_head": head,
        "source_tree": tree,
        "grid": {**grid, "grid_id": _identity("grid", grid)},
        "evaluation_policy": json.loads(evaluation_policy().to_json()),
        "development_interval": [
            "2016-01-01T00:00:00+00:00",
            "2020-01-01T00:00:00+00:00",
        ],
        "request_projection": "nyse-local-year-boundaries/unchanged-open-bars/v1",
        "ranking_policy": RANKING_POLICY,
        "shortlist_size": SHORTLIST_SIZE,
        "fold_plan": [json.loads(f.to_json()) for f in fold_plan()],
        "qualification_policy": None,
        "authority": "RESEARCH_ONLY_NO_LIFECYCLE_OR_TRADING_AUTHORITY",
    }


def campaign_identity(
    binding: DesktopCampaignDatasetBinding, head: str, tree: str
) -> str:
    return _identity("campaign", _context(binding, head, tree))


def candidate_identity(campaign_id: str, short: int, long: int) -> str:
    if (short, long) not in GRID:
        raise DesktopCampaignError("configuration outside frozen grid")
    return _identity("candidate", [campaign_id, short, long])


@dataclass(frozen=True, slots=True)
class DevelopmentResult:
    candidate_id: str
    definition: ResearchStrategyDefinition
    evidence: ResearchStrategyBacktestEvidence
    total_fills: int
    closed_trade_count: int
    turnover: Decimal

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "definition": json.loads(self.definition.to_json()),
            "evidence": json.loads(self.evidence.to_json()),
            "total_fills": self.total_fills,
            "closed_trade_count": self.closed_trade_count,
            "turnover": _decimal(self.turnover),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> DevelopmentResult:
        result = cls(
            raw["candidate_id"],
            ResearchStrategyDefinition.from_json(_json(raw["definition"]).decode()),
            ResearchStrategyBacktestEvidence.from_json(_json(raw["evidence"]).decode()),
            raw["total_fills"],
            raw["closed_trade_count"],
            _read_decimal(raw["turnover"]),
        )
        if result.to_dict() != raw:
            raise DesktopCampaignError("development shape mismatch")
        return result


def rank_development(
    rows: tuple[DevelopmentResult, ...],
) -> tuple[DevelopmentResult, ...]:
    # copy_negate avoids ambient-context rounding during sorting.
    return tuple(
        sorted(
            rows,
            key=lambda r: (
                r.evidence.total_return.copy_negate(),
                r.evidence.maximum_drawdown_percentage,
                r.definition.strategy_config.short_window,
                r.definition.strategy_config.long_window,
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    candidate_id: str
    evidence: ResearchStrategyWalkForwardEvidence
    test_evidence: tuple[ResearchStrategyBacktestEvidence, ...]

    def to_dict(self) -> dict:
        returns = tuple(e.total_return for e in self.test_evidence)
        with localcontext(Context(prec=50)):
            ordered = sorted(returns)
            median = sum(
                ordered[(len(returns) - 1) // 2 : len(returns) // 2 + 1], Decimal("0")
            ) / Decimal(2 if len(returns) % 2 == 0 else 1)
        return {
            "candidate_id": self.candidate_id,
            "evidence": json.loads(self.evidence.to_json()),
            "test_evidence": [json.loads(e.to_json()) for e in self.test_evidence],
            "fold_count": len(returns),
            "test_bar_counts": [e.bar_count for e in self.test_evidence],
            "minimum_fold_return": _decimal(min(returns)),
            "median_fold_return": _decimal(median),
            "maximum_fold_drawdown": _decimal(
                max(e.maximum_drawdown_percentage for e in self.test_evidence)
            ),
            "qualification": None,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> WalkForwardResult:
        result = cls(
            raw["candidate_id"],
            ResearchStrategyWalkForwardEvidence.from_json(
                _json(raw["evidence"]).decode()
            ),
            tuple(
                ResearchStrategyBacktestEvidence.from_json(_json(e).decode())
                for e in raw["test_evidence"]
            ),
        )
        if result.to_dict() != raw:
            raise DesktopCampaignError("walk-forward shape/summary mismatch")
        return result


def parameter_sensitivity(rows: tuple[DevelopmentResult, ...]) -> list[dict]:
    """Adjacent grid evidence; no evaluation or inferred robustness."""
    by_config = {
        (
            r.definition.strategy_config.short_window,
            r.definition.strategy_config.long_window,
        ): r
        for r in rows
    }
    result = []
    for (short, long), row in by_config.items():
        neighbors = []
        for neighbor_short, neighbor_long in (
            (short - 5, long),
            (short + 5, long),
            (short, long - 10),
            (short, long + 10),
        ):
            neighbor = by_config.get((neighbor_short, neighbor_long))
            neighbors.append(
                {
                    "short_window": neighbor_short,
                    "long_window": neighbor_long,
                    "status": "MISSING_GRID_NEIGHBOR"
                    if neighbor is None
                    else "AVAILABLE",
                    "candidate_id": None if neighbor is None else neighbor.candidate_id,
                    "total_return": None
                    if neighbor is None
                    else _decimal(neighbor.evidence.total_return),
                    "maximum_drawdown_percentage": None
                    if neighbor is None
                    else _decimal(neighbor.evidence.maximum_drawdown_percentage),
                }
            )
        result.append({"candidate_id": row.candidate_id, "neighbors": neighbors})
    return result


@dataclass(frozen=True, slots=True)
class _CampaignContext:
    dataset_binding: DesktopCampaignDatasetBinding
    source_head: str
    source_tree: str

    @property
    def campaign_id(self) -> str:
        return campaign_identity(
            self.dataset_binding, self.source_head, self.source_tree
        )

    def validate_development(
        self, row: DevelopmentResult, short: int, long: int
    ) -> None:
        definition = _definition(self.source_head, self.source_tree, short, long)
        evidence = row.evidence
        if (
            row.candidate_id != candidate_identity(self.campaign_id, short, long)
            or row.definition != definition
        ):
            raise DesktopCampaignError("candidate campaign/source/config mismatch")
        _validate_evidence(evidence, definition, self.source_head, self.source_tree)
        if (evidence.data_request_start, evidence.data_request_end) != (
            _date(2016),
            _date(2020),
        ) or not (
            DEVELOPMENT_START
            <= evidence.start_timestamp
            <= evidence.end_timestamp
            < DEVELOPMENT_END
        ):
            raise DesktopCampaignError("development includes out-of-window data")
        if evidence.backtest_run_id != derive_backtest_run_id(
            definition.definition_id,
            evaluation_policy().policy_id,
            evidence.historical_data_fingerprint,
        ):
            raise DesktopCampaignError("development run identity mismatch")
        _decimal(row.turnover)
        if (
            any(
                type(v) is not int or v < 0
                for v in (row.total_fills, row.closed_trade_count)
            )
            or row.turnover < 0
            or row.closed_trade_count > row.total_fills
        ):
            raise DesktopCampaignError("invalid counts/turnover")

    def validate_walk_forward(
        self, walk: WalkForwardResult, row: DevelopmentResult
    ) -> None:
        evidence = walk.evidence
        ResearchStrategyWalkForwardEvidence.from_json(evidence.to_json())
        if (
            walk.candidate_id != row.candidate_id
            or (
                evidence.definition_id,
                evidence.evaluation_policy_id,
                evidence.evaluation_source_head,
                evidence.evaluation_source_tree,
            )
            != (
                row.definition.definition_id,
                evaluation_policy().policy_id,
                self.source_head,
                self.source_tree,
            )
            or len(walk.test_evidence) != len(fold_plan())
            or len(evidence.folds) != len(fold_plan())
        ):
            raise DesktopCampaignError("walk-forward provenance mismatch")
        for fold, fold_evidence, test in zip(
            fold_plan(), evidence.folds, walk.test_evidence, strict=True
        ):
            _validate_evidence(test, row.definition, self.source_head, self.source_tree)
            if (
                fold_evidence.fold_id,
                fold_evidence.training_start,
                fold_evidence.training_end,
                fold_evidence.test_start,
                fold_evidence.test_end,
            ) != (
                fold.fold_id,
                fold.training_start,
                fold.training_end,
                fold.test_start,
                fold.test_end,
            ):
                raise DesktopCampaignError("fold plan mismatch")
            if (test.evidence_id, test.historical_data_fingerprint, test.bar_count) != (
                fold_evidence.test_backtest_evidence_id,
                fold_evidence.test_historical_fingerprint,
                fold_evidence.test_bar_count,
            ) or (test.data_request_start, test.data_request_end) != (
                fold.test_start,
                fold.test_end,
            ):
                raise DesktopCampaignError("fold test evidence mismatch")
            if (
                not fold.test_start
                <= test.start_timestamp
                <= test.end_timestamp
                < fold.test_end
                or test.backtest_run_id
                != derive_backtest_run_id(
                    row.definition.definition_id,
                    evaluation_policy().policy_id,
                    test.historical_data_fingerprint,
                    fold_role="TEST",
                    fold_id=fold.fold_id,
                )
            ):
                raise DesktopCampaignError("test chronology/run mismatch")


@dataclass(frozen=True, slots=True)
class DesktopCampaignBundle(_CampaignContext):
    """Immutable canonical result; parsers verify all derived relationships."""

    development: tuple[DevelopmentResult, ...]
    walk_forward: tuple[WalkForwardResult, ...]

    def __post_init__(self) -> None:
        _source(self.source_head, self.source_tree)
        if type(self.development) is not tuple or type(self.walk_forward) is not tuple:
            raise DesktopCampaignError("immutable result tuples required")
        if len(self.development) != len(GRID):
            raise DesktopCampaignError("complete frozen grid required")
        fingerprint = None
        for row, (short, long) in zip(self.development, GRID, strict=True):
            self.validate_development(row, short, long)
            if (
                fingerprint is not None
                and row.evidence.historical_data_fingerprint != fingerprint
            ):
                raise DesktopCampaignError("development data fingerprint differs")
            fingerprint = row.evidence.historical_data_fingerprint
        shortlist = rank_development(self.development)[:SHORTLIST_SIZE]
        if tuple(w.candidate_id for w in self.walk_forward) != tuple(
            r.candidate_id for r in shortlist
        ):
            raise DesktopCampaignError(
                "walk-forward must exactly match ranked shortlist"
            )
        for walk, row in zip(self.walk_forward, shortlist, strict=True):
            self.validate_walk_forward(walk, row)

    def to_dict(self) -> dict:
        ranked = rank_development(self.development)
        body = {
            **_context(self.dataset_binding, self.source_head, self.source_tree),
            "campaign_id": self.campaign_id,
            "development": [r.to_dict() for r in self.development],
            "development_ranking": [r.candidate_id for r in ranked],
            "shortlist": [r.candidate_id for r in ranked[:SHORTLIST_SIZE]],
            "walk_forward": [w.to_dict() for w in self.walk_forward],
            "parameter_sensitivity": parameter_sensitivity(self.development),
            "recommended_research_only_leader": ranked[0].candidate_id,
        }
        return {**body, "bundle_id": _identity("bundle", body)}

    @property
    def bundle_id(self) -> str:
        return self.to_dict()["bundle_id"]

    def to_bytes(self) -> bytes:
        return _json(self.to_dict())

    @classmethod
    def from_bytes(cls, body: bytes) -> DesktopCampaignBundle:
        try:
            raw = _parse(body)
            if (
                len(raw["development"]) != len(GRID)
                or len(raw["walk_forward"]) != SHORTLIST_SIZE
            ):
                raise DesktopCampaignError("bounded grid/shortlist required")
            result = cls(
                DesktopCampaignDatasetBinding(**raw["dataset_binding"]),
                raw["source_head"],
                raw["source_tree"],
                tuple(DevelopmentResult.from_dict(r) for r in raw["development"]),
                tuple(WalkForwardResult.from_dict(w) for w in raw["walk_forward"]),
            )
            if result.to_bytes() != body:
                raise DesktopCampaignError("bundle identity/derived evidence mismatch")
            return result
        except (
            ValueError,
            TypeError,
            KeyError,
            ArithmeticError,
            RecursionError,
            OverflowError,
            AttributeError,
        ):
            raise DesktopCampaignError("invalid campaign bundle") from None

    def to_csv(self) -> bytes:
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            (
                "candidate_id",
                "development_rank",
                "short_window",
                "long_window",
                "development_return",
                "development_max_drawdown",
                "final_equity",
                "fills",
                "closed_trades",
                "turnover_executed_notional_over_average_equity",
                "shortlisted",
                "research_only_leader",
                "wf_fold_count",
                "wf_min_return",
                "wf_median_return",
                "wf_max_drawdown",
            )
        )
        walks = {w.candidate_id: w.to_dict() for w in self.walk_forward}
        for rank, row in enumerate(rank_development(self.development), 1):
            walk = walks.get(row.candidate_id, {})
            writer.writerow(
                (
                    row.candidate_id,
                    rank,
                    row.definition.strategy_config.short_window,
                    row.definition.strategy_config.long_window,
                    _decimal(row.evidence.total_return),
                    _decimal(row.evidence.maximum_drawdown_percentage),
                    _decimal(row.evidence.final_equity),
                    row.total_fills,
                    row.closed_trade_count,
                    _decimal(row.turnover),
                    row.candidate_id in walks,
                    rank == 1,
                    *(
                        walk.get(k, "")
                        for k in (
                            "fold_count",
                            "minimum_fold_return",
                            "median_fold_return",
                            "maximum_fold_drawdown",
                        )
                    ),
                )
            )
        return output.getvalue().encode()


def _validate_evidence(
    evidence: ResearchStrategyBacktestEvidence,
    definition: ResearchStrategyDefinition,
    head: str,
    tree: str,
) -> None:
    # Public canonical parser validates immutable evidence identities, no replay.
    ResearchStrategyBacktestEvidence.from_json(evidence.to_json())
    if (
        evidence.definition_id,
        evidence.evaluation_policy_id,
        evidence.evaluation_source_head,
        evidence.evaluation_source_tree,
        evidence.data_request_symbol,
    ) != (
        definition.definition_id,
        evaluation_policy().policy_id,
        head,
        tree,
        Symbol("SPY"),
    ):
        raise DesktopCampaignError("backtest evidence provenance mismatch")


def _evaluate_development(
    campaign_id: str,
    definition: ResearchStrategyDefinition,
    data: HistoricalDataResult,
    head: str,
    tree: str,
) -> DevelopmentResult:
    with localcontext(Context(prec=50)):
        completed = run_research_strategy_backtest(
            definition,
            evaluation_policy(),
            data,
            evaluation_source_head=head,
            evaluation_source_tree=tree,
        )
        verify_research_strategy_backtest(
            completed,
            data,
            evaluation_source_head=head,
            evaluation_source_tree=tree,
        )
    config = definition.strategy_config
    return DevelopmentResult(
        candidate_identity(campaign_id, config.short_window, config.long_window),
        definition,
        completed.evidence,
        len(completed.result.fills),
        completed.performance_report.closed_trade_count,
        completed.performance_report.turnover,
    )


def _evaluate_walk_forward(
    row: DevelopmentResult,
    data: HistoricalDataResult,
    head: str,
    tree: str,
) -> WalkForwardResult:
    with localcontext(Context(prec=50)):
        completed = run_research_strategy_walk_forward(
            row.definition,
            evaluation_policy(),
            data,
            fold_plan(),
            evaluation_source_head=head,
            evaluation_source_tree=tree,
        )
        verify_research_strategy_walk_forward(
            completed,
            evaluation_source_head=head,
            evaluation_source_tree=tree,
        )
    # No qualification/promotion policy is inferred from observed results.
    return WalkForwardResult(
        row.candidate_id,
        completed.evidence,
        tuple(f.test.evidence for f in completed.folds),
    )


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise DesktopCampaignError("missing/ambiguous output")
    with path.open("rb") as handle:
        body = handle.read(MAX_ARTIFACT_BYTES + 1)
    if len(body) > MAX_ARTIFACT_BYTES:
        raise DesktopCampaignError("oversized output")
    return body


def read_desktop_campaign_bundle(path: Path) -> DesktopCampaignBundle:
    """Read and strictly validate one bounded desktop campaign bundle."""
    if not isinstance(path, Path):
        raise TypeError("path must be exactly pathlib.Path")
    return DesktopCampaignBundle.from_bytes(_read(path))


def _write_once(path: Path, body: bytes) -> None:
    if path.exists() or path.is_symlink():
        if _read(path) != body:
            raise DesktopCampaignError(
                "conflicting completed output; preserve and stop"
            )
        return
    with path.open("xb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    if _read(path) != body:
        raise DesktopCampaignError("output readback mismatch")


def _journal(campaign_id: str, result: dict) -> bytes:
    return _json(
        {
            "campaign_id": campaign_id,
            "result": result,
            "result_id": _identity("candidate-result", [campaign_id, result]),
        }
    )


def _journal_result(path: Path, campaign_id: str) -> dict:
    body = _read(path)
    raw = _parse(body)
    if (
        set(raw) != {"campaign_id", "result", "result_id"}
        or raw["campaign_id"] != campaign_id
        or _journal(campaign_id, raw["result"]) != body
    ):
        raise DesktopCampaignError("candidate journal context/identity mismatch")
    return raw["result"]


def run_desktop_campaign(
    storage: DesktopResearchStorage,
    *,
    source_head: str,
    source_tree: str,
    output_root: Path = REPORTS_ROOT,
    resume: bool = False,
    test_binding: DesktopCampaignDatasetBinding | None = None,
) -> Path:
    """Run/resume candidate files bound to the exact complete semantic context.

    Verification replays accepted engines; one retained development evaluation
    per configuration. Ranking and sensitivity perform no extra evaluation.
    Partial/corrupt files are never automatically retried or overwritten.
    """
    if type(storage) is not DesktopResearchStorage:
        raise DesktopCampaignError("exact desktop storage required")
    if type(resume) is not bool or (
        not storage.test_only and output_root != REPORTS_ROOT
    ):
        raise DesktopCampaignError("production reports root/resume rejected")
    binding = bind_desktop_dataset(storage, test_binding=test_binding)
    data = load_desktop_open_research(storage)
    if (
        len(data.bars) != binding.open_row_count
        or data.bars[0].timestamp.isoformat() != binding.open_first_timestamp
        or data.bars[-1].timestamp.isoformat() != binding.open_last_timestamp
    ):
        raise DesktopCampaignError("loaded OPEN differs from binding")
    data = campaign_open_projection(data)
    dev = development_data(data)
    dev_fingerprint = historical_data_fingerprint(dev)
    open_fingerprint = historical_data_fingerprint(data)
    context = _CampaignContext(binding, source_head, source_tree)
    campaign_id = context.campaign_id
    destination = output_root / campaign_id
    header = _json(
        {
            **_context(binding, source_head, source_tree),
            "campaign_id": campaign_id,
        }
    )
    if any(
        p.is_symlink() or p.is_junction() for p in (output_root, *output_root.parents)
    ):
        raise DesktopCampaignError("linked reports root rejected")
    if destination.exists():
        if (
            not resume
            or destination.is_symlink()
            or destination.is_junction()
            or _read(destination / "campaign.json") != header
        ):
            raise DesktopCampaignError(
                "existing campaign requires explicit exact resume"
            )
    else:
        if resume:
            raise DesktopCampaignError("resume destination absent")
        destination.mkdir(parents=True, exist_ok=False)
        _write_once(destination / "campaign.json", header)
    for name in ("development", "walk-forward"):
        folder = destination / name
        if folder.is_symlink() or folder.is_junction():
            raise DesktopCampaignError("linked output rejected")
        folder.mkdir(exist_ok=True)
    expected_files = {
        "campaign.json",
        "bundle.json",
        "candidates.csv",
        "development",
        "walk-forward",
    }
    if any(p.name not in expected_files for p in destination.iterdir()):
        raise DesktopCampaignError("unexpected campaign output")
    candidate_ids = {
        candidate_identity(campaign_id, short, long) for short, long in GRID
    }
    for name in ("development", "walk-forward"):
        if any(
            p.suffix != ".json" or p.stem not in candidate_ids or not p.is_file()
            for p in (destination / name).iterdir()
        ):
            raise DesktopCampaignError("unexpected candidate output")
        # Inspect every existing journal before any missing evaluation begins.
        for path in (destination / name).iterdir():
            raw = _journal_result(path, campaign_id)
            if raw.get("candidate_id") != path.stem:
                raise DesktopCampaignError("candidate filename/identity mismatch")
    if (destination / "bundle.json").exists():
        completed = DesktopCampaignBundle.from_bytes(_read(destination / "bundle.json"))
        if (
            completed.campaign_id != campaign_id
            or len(tuple((destination / "development").iterdir())) != len(GRID)
            or len(tuple((destination / "walk-forward").iterdir())) != SHORTLIST_SIZE
            or _read(destination / "candidates.csv") != completed.to_csv()
        ):
            raise DesktopCampaignError(
                "completed campaign files conflict or are missing"
            )
    rows = []
    for short, long in GRID:
        identity = candidate_identity(campaign_id, short, long)
        path = destination / "development" / f"{identity}.json"
        if path.exists() or path.is_symlink():
            row = DevelopmentResult.from_dict(_journal_result(path, campaign_id))
        else:
            row = _evaluate_development(
                campaign_id,
                _definition(source_head, source_tree, short, long),
                dev,
                source_head,
                source_tree,
            )
        context.validate_development(row, short, long)
        if row.evidence.historical_data_fingerprint != dev_fingerprint:
            raise DesktopCampaignError("resumed DEVELOPMENT fingerprint mismatch")
        _write_once(path, _journal(campaign_id, row.to_dict()))
        rows.append(row)
    walks = []
    shortlisted = rank_development(tuple(rows))[:SHORTLIST_SIZE]
    if any(
        p.stem not in {r.candidate_id for r in shortlisted}
        for p in (destination / "walk-forward").iterdir()
    ):
        raise DesktopCampaignError("unexpected non-shortlist walk-forward output")
    for row in shortlisted:
        path = destination / "walk-forward" / f"{row.candidate_id}.json"
        if path.exists() or path.is_symlink():
            walk = WalkForwardResult.from_dict(_journal_result(path, campaign_id))
        else:
            walk = _evaluate_walk_forward(row, data, source_head, source_tree)
        if walk.evidence.source_historical_fingerprint != open_fingerprint:
            raise DesktopCampaignError("resumed OPEN fingerprint mismatch")
        context.validate_walk_forward(walk, row)
        _write_once(path, _journal(campaign_id, walk.to_dict()))
        walks.append(walk)
    bundle = DesktopCampaignBundle(
        binding, source_head, source_tree, tuple(rows), tuple(walks)
    )
    payload = bundle.to_bytes()
    if DesktopCampaignBundle.from_bytes(payload) != bundle:
        raise DesktopCampaignError("bundle readback reconciliation failed")
    _write_once(destination / "candidates.csv", bundle.to_csv())
    _write_once(destination / "bundle.json", payload)
    return destination / "bundle.json"
