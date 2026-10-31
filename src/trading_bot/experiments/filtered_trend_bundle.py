"""Canonical immutable research evidence and read-only presentation projections."""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

from trading_bot.domain import OrderFill, OrderSide, Symbol
from trading_bot.experiments.filtered_trend_campaign import (
    ALLOCATION,
    BASE_COSTS,
    CONTEXT,
    NY,
    STARTING_CASH,
    STRESS_COSTS,
    AggregateSummary,
    AtrDescription,
    CandidateSummary,
    CellEvidence,
    FillEvidence,
    Metrics,
    candidate_identity,
    config_material,
    decimal_text,
    neighbor_configs,
    regime_plan,
    semantic_identity,
    shortlist,
    summarize,
)
from trading_bot.experiments.filtered_trend_data import UNIVERSE
from trading_bot.experiments.filtered_trend_strategies import (
    StrategyConfig,
    strategy_grid,
)
from trading_bot.ledger import PaperLedger

MAX_BUNDLE_BYTES = 128 * 1024 * 1024


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return decimal_text(value)
    if is_dataclass(value):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def _parse(body: bytes) -> dict:
    if type(body) is not bytes or len(body) > MAX_BUNDLE_BYTES:
        raise ValueError("invalid or oversized bundle")
    raw = json.loads(body, object_pairs_hook=_pairs, parse_constant=_reject)
    if type(raw) is not dict or canonical_json(raw) != body:
        raise ValueError("noncanonical bundle")
    return raw


def _uuid(value: object) -> None:
    if type(value) is not str:
        raise ValueError("invalid UUID5")
    parsed = UUID(value)
    if str(parsed) != value or parsed.version != 5:
        raise ValueError("invalid UUID5")


def _decimal(value: object) -> Decimal:
    if type(value) is not str or "e" in value.lower():
        # Exponent notation is never canonical; reject before expanding it.
        raise ValueError("decimal must be canonical text")
    result = Decimal(value)
    if decimal_text(result) != value:
        raise ValueError("noncanonical decimal")
    return result


def _exact(raw: object, names: set[str]) -> dict:
    if type(raw) is not dict or set(raw) != names:
        raise ValueError("unexpected evidence fields")
    return raw


def _decode(cls: type, raw: object):
    row = _exact(raw, {f.name for f in fields(cls)})
    converted = {}
    for f in fields(cls):
        value = row[f.name]
        if f.type == "Decimal":
            value = _decimal(value)
        elif f.type == "int":
            if type(value) is not int:
                raise ValueError("integer required")
        elif f.type == "str":
            if type(value) is not str:
                raise ValueError("string required")
        elif f.type == "str | None":
            if value is not None and type(value) is not str:
                raise ValueError("optional string required")
        elif f.type == "tuple[FillEvidence, ...]":
            if type(value) is not list:
                raise ValueError("fill list required")
            value = tuple(_decode(FillEvidence, v) for v in value)
        elif f.type in (
            "Metrics",
            "AtrDescription",
            "AggregateSummary",
            "StrategyConfig",
        ):
            value = _decode(
                {
                    "Metrics": Metrics,
                    "AtrDescription": AtrDescription,
                    "AggregateSummary": AggregateSummary,
                    "StrategyConfig": StrategyConfig,
                }[f.type],
                value,
            )
        else:
            raise ValueError("unsupported schema type")
        converted[f.name] = value
    return cls(**converted)


def _validate_metrics(
    metrics: Metrics, cell: CellEvidence, costs, *, buy_hold: bool
) -> None:
    if type(metrics.fill_count) is not int or metrics.fill_count != len(metrics.fills):
        raise ValueError("fill count mismatch")
    if type(metrics.closed_trades) is not int or metrics.closed_trades != sum(
        f.side == "SELL" for f in metrics.fills
    ):
        raise ValueError("closed trade count mismatch")
    if not (
        0 <= metrics.maximum_drawdown <= 1
        and 0 <= metrics.time_invested <= 1
        and metrics.turnover >= 0
    ):
        raise ValueError("invalid metric bounds")
    if (
        metrics.final_equity <= 0
        or metrics.total_return != metrics.final_equity / STARTING_CASH - 1
    ):
        raise ValueError("equity/return mismatch")
    _uuid(metrics.equity_trace_identity)
    ledger = PaperLedger(STARTING_CASH)
    previous = None
    for fill in metrics.fills:
        _uuid(fill.identity)
        session = datetime.fromisoformat(fill.session)
        if session.tzinfo is None or session.isoformat() != fill.session:
            raise ValueError("noncanonical session")
        if previous is not None and session <= previous:
            raise ValueError("duplicate/unordered fills")
        previous = session
        regime = next(r for r in regime_plan() if r.label == cell.regime)
        if not regime.start <= session.astimezone(NY).date() < regime.end:
            raise ValueError("fill outside regime")
        if not cell.first_session <= fill.session <= cell.last_session:
            raise ValueError("fill outside result")
        if buy_hold:
            if (
                fill.information_through is not None
                or fill.side != "BUY"
                or len(metrics.fills) != 1
                or fill.session != cell.first_session
            ):
                raise ValueError("invalid buy-and-hold evidence")
        elif (
            fill.information_through is None
            or datetime.fromisoformat(fill.information_through) >= session
        ):
            raise ValueError("lookahead in evidence")
        if (
            fill.side not in ("BUY", "SELL")
            or fill.quantity <= 0
            or fill.quantity != fill.quantity.to_integral_value()
        ):
            raise ValueError("invalid long-only whole-share fill")
        expected = fill.execution_open * (
            1 + costs.slippage_bps / 10000
            if fill.side == "BUY"
            else 1 - costs.slippage_bps / 10000
        )
        if (
            fill.price != expected
            or fill.commission != costs.commission
            or fill.risk_outcome != "APPROVED"
        ):
            raise ValueError("unexpected economics/risk evidence")
        position = ledger.get_position(Symbol(cell.symbol))
        if fill.side == "BUY":
            if (
                position is not None
                or fill.quantity
                != ((ledger.cash * ALLOCATION - costs.commission) / fill.price) // 1
            ):
                raise ValueError("invalid allocation")
        elif position is None or fill.quantity != position.quantity:
            raise ValueError("invalid liquidation")
        ledger.apply_fill(
            OrderFill(
                UUID(fill.identity),
                UUID(semantic_identity("read-order", fill.identity)),
                Symbol(cell.symbol),
                OrderSide(fill.side),
                fill.quantity,
                fill.price,
                fill.commission,
                session,
            )
        )
        if ledger.cash != fill.cash_after:
            raise ValueError("fill cash mismatch")
    if ledger.realized_profit_loss != metrics.realized_profit_loss:
        raise ValueError("realized profit/loss mismatch")
    if not ledger.positions and metrics.final_equity != ledger.cash:
        raise ValueError("cash-only final equity mismatch")
    if not metrics.fills and any(
        (
            metrics.total_return,
            metrics.maximum_drawdown,
            metrics.turnover,
            metrics.time_invested,
            metrics.realized_profit_loss,
        )
    ):
        raise ValueError("no-fill account metrics must be zero")


@dataclass(frozen=True, slots=True)
class ResearchBundle:
    """Immutable typed evidence; context bytes are decoded before semantic identity."""

    context_bytes: bytes
    cells: tuple[CellEvidence, ...]
    summaries: tuple[CandidateSummary, ...]

    def __post_init__(self) -> None:
        context = _parse(self.context_bytes)
        _exact(
            context,
            {
                "schema",
                "source_head",
                "source_tree",
                "dataset_id",
                "price_basis",
                "dataset_provenance",
                "neighbor_policy",
                "universe",
                "grid",
                "regimes",
                "economics",
                "timing",
                "valuation",
                "shortlist_policy",
                "qualification_policy",
                "paper_binding",
                "live_eligible",
            },
        )
        # Rebuild the frozen policy; changes require a new schema version.
        from trading_bot.experiments.filtered_trend_campaign import frozen_context

        expected = frozen_context(
            context["source_head"],
            context["source_tree"],
            context["dataset_id"],
            context["price_basis"],
            context["dataset_provenance"],
        )
        if canonical_json(context) != canonical_json(expected):
            raise ValueError("research policy differs from frozen contract")
        _uuid(context["dataset_id"])
        from trading_bot.experiments.filtered_trend_data import (
            PRICE_BASIS,
            ProviderProvenance,
        )
        from trading_bot.experiments.historical_research_sessions import (
            published_historical_session_authority,
        )

        provenance = context["dataset_provenance"]
        if type(provenance) is not list or len(provenance) != len(UNIVERSE):
            raise ValueError("missing dataset provenance")
        sessions = tuple(
            d
            for d in published_historical_session_authority().sessions
            if 2016 <= d.year < 2024
        )
        for symbol, item in zip(UNIVERSE, provenance, strict=True):
            _exact(item, {"symbol", "provider", "bar_count", "first_bar", "last_bar"})
            if (
                item["symbol"] != symbol
                or type(item["bar_count"]) is not int
                or item["bar_count"] != len(sessions)
            ):
                raise ValueError("dataset coverage provenance mismatch")
            ProviderProvenance.from_dict(item["provider"])
            for key, day in (("first_bar", sessions[0]), ("last_bar", sessions[-1])):
                timestamp = datetime.fromisoformat(item[key])
                if timestamp.tzinfo is None or timestamp.astimezone(NY).date() != day:
                    raise ValueError("dataset endpoints mismatch")

        if context["price_basis"] != PRICE_BASIS:
            raise ValueError("wrong adjusted-price basis")
        if type(self.cells) is not tuple or type(self.summaries) is not tuple:
            raise ValueError("immutable evidence tuples required")
        expected_keys = tuple(
            (candidate_identity(self.campaign_id, c), s, r.label)
            for c in strategy_grid()
            for s in UNIVERSE
            for r in regime_plan()
        )
        if (
            tuple((c.candidate_id, c.symbol, c.regime) for c in self.cells)
            != expected_keys
        ):
            raise ValueError("incomplete, duplicate or misordered cells")
        with localcontext(CONTEXT):
            for cell in self.cells:
                regime = next(r for r in regime_plan() if r.label == cell.regime)
                expected_sessions = tuple(
                    d for d in sessions if regime.start <= d < regime.end
                )
                if type(cell.session_count) is not int or cell.session_count != len(
                    expected_sessions
                ):
                    raise ValueError("regime session coverage mismatch")
                for stamp, day in (
                    (cell.first_session, expected_sessions[0]),
                    (cell.last_session, expected_sessions[-1]),
                ):
                    parsed = datetime.fromisoformat(stamp)
                    if (
                        parsed.tzinfo is None
                        or parsed.isoformat() != stamp
                        or parsed.astimezone(NY).date() != day
                    ):
                        raise ValueError("regime endpoints mismatch")
                if cell.session_count <= 0 or cell.atr.count != cell.session_count:
                    raise ValueError("invalid session/ATR count")
                if (
                    not 0 <= cell.atr.minimum <= cell.atr.median <= cell.atr.maximum
                    or cell.atr.median_close_fraction < 0
                ):
                    raise ValueError("invalid ATR evidence")
                for metrics, costs, bh in (
                    (cell.base, BASE_COSTS, False),
                    (cell.stress, STRESS_COSTS, False),
                    (cell.buy_and_hold, BASE_COSTS, True),
                    (cell.buy_and_hold_stress, STRESS_COSTS, True),
                ):
                    _validate_metrics(metrics, cell, costs, buy_hold=bh)
                run = semantic_identity(
                    "cell", (cell.candidate_id, cell.symbol, cell.regime)
                )
                material = (
                    run,
                    asdict(cell.base),
                    asdict(cell.stress),
                    asdict(cell.buy_and_hold),
                    asdict(cell.buy_and_hold_stress),
                    asdict(cell.atr),
                    cell.session_count,
                    cell.first_session,
                    cell.last_session,
                )
                if cell.result_id != semantic_identity("cell-result", material):
                    raise ValueError("result identity mismatch")
            expected_summaries = tuple(
                CandidateSummary(
                    candidate_identity(self.campaign_id, c),
                    c,
                    summarize(self.cells[i * 48 : (i + 1) * 48]),
                    summarize(self.cells[i * 48 : (i + 1) * 48], stress=True),
                )
                for i, c in enumerate(strategy_grid())
            )
            if self.summaries != expected_summaries:
                raise ValueError("aggregate mismatch")

    @property
    def context(self) -> dict:
        return _parse(self.context_bytes)

    @property
    def campaign_id(self) -> str:
        return semantic_identity("campaign", self.context)

    @property
    def bundle_id(self) -> str:
        return semantic_identity(
            "bundle",
            (self.context, asdict_rows(self.cells), asdict_rows(self.summaries)),
        )

    def to_dict(self) -> dict:
        return {
            "schema": "filtered-trend-bundle/v1",
            "campaign_id": self.campaign_id,
            "bundle_id": self.bundle_id,
            "context": self.context,
            "cells": _plain(self.cells),
            "summaries": _plain(self.summaries),
            "shortlist": [s.candidate_id for s in shortlist(self.summaries)],
            "neighbors": [
                {
                    "candidate_id": s.candidate_id,
                    "neighbors": [
                        candidate_identity(self.campaign_id, c)
                        for c in neighbor_configs(s.config)
                    ],
                }
                for s in shortlist(self.summaries)
            ],
        }

    def to_bytes(self) -> bytes:
        return canonical_json(self.to_dict())

    @classmethod
    def from_bytes(cls, body: bytes) -> ResearchBundle:
        raw = _parse(body)
        _exact(
            raw,
            {
                "schema",
                "campaign_id",
                "bundle_id",
                "context",
                "cells",
                "summaries",
                "shortlist",
                "neighbors",
            },
        )
        if (
            raw["schema"] != "filtered-trend-bundle/v1"
            or type(raw["cells"]) is not list
            or type(raw["summaries"]) is not list
        ):
            raise ValueError("invalid bundle schema")
        bundle = cls(
            canonical_json(raw["context"]),
            tuple(_decode(CellEvidence, c) for c in raw["cells"]),
            tuple(_decode(CandidateSummary, s) for s in raw["summaries"]),
        )
        if bundle.to_bytes() != body:
            raise ValueError("derived evidence mismatch")
        return bundle


def asdict_rows(rows: tuple) -> tuple[dict, ...]:
    return tuple(asdict(row) for row in rows)


def build_bundle(
    context: dict,
    cells: tuple[CellEvidence, ...],
    summaries: tuple[CandidateSummary, ...],
) -> ResearchBundle:
    return ResearchBundle(canonical_json(context), cells, summaries)


def read_research_bundle(path: Path) -> ResearchBundle:
    if path.is_symlink() or path.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError("linked/oversized bundle")
    with path.open("rb") as stream:
        return ResearchBundle.from_bytes(stream.read(MAX_BUNDLE_BYTES + 1))


def write_research_bundle(path: Path, bundle: ResearchBundle) -> None:
    """Exclusive create, fsync and strict readback; never repair partial output."""
    body = bundle.to_bytes()
    ResearchBundle.from_bytes(body)
    with path.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    if read_research_bundle(path).to_bytes() != body:
        raise ValueError("bundle readback mismatch")


def presentation_rows(bundle: ResearchBundle) -> tuple[dict, ...]:
    """Detached read-only projection, with no campaign or binding controls."""
    configs = {s.candidate_id: s.config for s in bundle.summaries}
    return tuple(
        {
            "symbol": c.symbol,
            **config_material(configs[c.candidate_id]),
            "regime": c.regime,
            "return": decimal_text(c.base.total_return),
            "drawdown": decimal_text(c.base.maximum_drawdown),
            "buy_hold_return": decimal_text(c.buy_and_hold.total_return),
            "buy_hold_drawdown": decimal_text(c.buy_and_hold.maximum_drawdown),
            "cost_stress_return": decimal_text(c.stress.total_return),
            "cost_stress_drawdown": decimal_text(c.stress.maximum_drawdown),
            "candidate_id": c.candidate_id,
            "result_id": c.result_id,
        }
        for c in bundle.cells
    )


def report_csv(bundle: ResearchBundle) -> bytes:
    rows = presentation_rows(bundle)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")
