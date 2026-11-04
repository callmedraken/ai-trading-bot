"""Canonical, effect-free evidence bundle for filtered-trend comparison v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
from typing import Any

from trading_bot.experiments import filtered_trend_comparison_campaign_v2 as _r11
from trading_bot.experiments.filtered_trend_bundle import (
    MAX_BUNDLE_BYTES,
    _decode,
    _exact,
    _parse,
    _plain,
    _uuid,
    _validate_metrics,
    asdict_rows,
    canonical_json,
)
from trading_bot.experiments.filtered_trend_campaign import (
    BASE_COSTS,
    CONTEXT,
    NY,
    STRESS_COSTS,
    AggregateSummary,
    AtrDescription,
    CellEvidence,
    Metrics,
    Regime,
    regime_plan,
    summarize,
)
from trading_bot.experiments.filtered_trend_campaign import (
    semantic_identity as _v1_semantic_identity,
)
from trading_bot.experiments.filtered_trend_comparison_campaign_v2 import (
    ComparisonSummary,
)
from trading_bot.experiments.filtered_trend_comparison_v2 import CANDIDATES, Candidate
from trading_bot.experiments.filtered_trend_data import (
    PRICE_BASIS,
    UNIVERSE,
    ProviderProvenance,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

_BUNDLE_SCHEMA = "filtered-trend-comparison-bundle/v2"
_SUMMARY_FIELDS = {
    "schema",
    "campaign_id",
    "bundle_id",
    "context",
    "cells",
    "summaries",
    "selected_candidate",
    "live_eligible",
}


def _sessions() -> tuple[date, ...]:
    return tuple(
        session
        for session in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= session < date(2024, 1, 1)
    )


def _validate_context(context: dict[str, Any]) -> tuple[str, tuple[date, ...]]:
    required = _r11.frozen_context(
        context.get("source_head"),
        context.get("source_tree"),
        context.get("dataset_id"),
        context.get("price_basis"),
        context.get("dataset_provenance"),
    )
    if canonical_json(context) != canonical_json(required):
        raise ValueError("comparison context differs from frozen policy")

    _uuid(context["dataset_id"])
    if context["price_basis"] != PRICE_BASIS:
        raise ValueError("wrong adjusted-price basis")
    sessions = _sessions()
    provenance = context["dataset_provenance"]
    if type(provenance) is not list or len(provenance) != len(UNIVERSE):
        raise ValueError("missing dataset provenance")
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
            stamp = datetime.fromisoformat(item[key])
            if stamp.tzinfo is None or stamp.astimezone(NY).date() != day:
                raise ValueError("dataset endpoints mismatch")
    campaign_id = _r11.campaign_identity(context)
    _uuid(campaign_id)
    return campaign_id, sessions


def _candidate_ids(campaign_id: str) -> tuple[str, ...]:
    candidate_ids = tuple(
        _r11.candidate_identity(campaign_id, candidate) for candidate in CANDIDATES
    )
    for candidate_id in candidate_ids:
        _uuid(candidate_id)
    return candidate_ids


def _validate_cell(
    cell: CellEvidence,
    expected_candidate_id: str,
    expected_symbol: str,
    regime: Regime,
    sessions: tuple[date, ...],
) -> None:
    if type(cell) is not CellEvidence:
        raise ValueError("typed cell evidence required")
    if (
        type(cell.candidate_id) is not str
        or type(cell.symbol) is not str
        or type(cell.regime) is not str
        or cell.candidate_id != expected_candidate_id
        or cell.symbol != expected_symbol
        or cell.regime != regime.label
    ):
        raise ValueError("candidate/symbol/regime cell identity mismatch")

    expected_sessions = tuple(
        session for session in sessions if regime.start <= session < regime.end
    )
    if (
        type(cell.session_count) is not int
        or cell.session_count != len(expected_sessions)
        or cell.session_count <= 0
        or type(cell.atr) is not AtrDescription
        or type(cell.atr.count) is not int
        or cell.atr.count != cell.session_count
    ):
        raise ValueError("invalid session or ATR count")
    first_expected, last_expected = expected_sessions[0], expected_sessions[-1]
    for stamp, day in (
        (cell.first_session, first_expected),
        (cell.last_session, last_expected),
    ):
        if type(stamp) is not str:
            raise ValueError("session timestamp must be text")
        parsed = datetime.fromisoformat(stamp)
        if (
            parsed.tzinfo is None
            or parsed.isoformat() != stamp
            or parsed.astimezone(NY).date() != day
        ):
            raise ValueError("regime session endpoints mismatch")

    atr_values = (
        cell.atr.minimum,
        cell.atr.median,
        cell.atr.maximum,
        cell.atr.median_close_fraction,
    )
    if any(type(value) is not Decimal or not value.is_finite() for value in atr_values):
        raise ValueError("invalid ATR values")
    if not (
        0 <= cell.atr.minimum <= cell.atr.median <= cell.atr.maximum
        and cell.atr.median_close_fraction >= 0
    ):
        raise ValueError("invalid ATR evidence")

    for metrics, costs, buy_hold in (
        (cell.base, BASE_COSTS, False),
        (cell.stress, STRESS_COSTS, False),
        (cell.buy_and_hold, BASE_COSTS, True),
        (cell.buy_and_hold_stress, STRESS_COSTS, True),
    ):
        if type(metrics) is not Metrics:
            raise ValueError("typed metrics required")
        _validate_metrics(metrics, cell, costs, buy_hold=buy_hold)

    run_id = _v1_semantic_identity(
        "cell", (cell.candidate_id, cell.symbol, cell.regime)
    )
    material = (
        run_id,
        asdict(cell.base),
        asdict(cell.stress),
        asdict(cell.buy_and_hold),
        asdict(cell.buy_and_hold_stress),
        asdict(cell.atr),
        cell.session_count,
        cell.first_session,
        cell.last_session,
    )
    _uuid(cell.result_id)
    if cell.result_id != _v1_semantic_identity("cell-result", material):
        raise ValueError("cell result identity mismatch")


def _decode_summary(raw: object) -> ComparisonSummary:
    row = _exact(raw, {"candidate", "candidate_id", "base", "stress"})
    if type(row["candidate"]) is not str or type(row["candidate_id"]) is not str:
        raise ValueError("invalid comparison summary identity")
    try:
        candidate = Candidate(row["candidate"])
    except ValueError as error:
        raise ValueError("unknown comparison candidate") from error
    return ComparisonSummary(
        candidate,
        row["candidate_id"],
        _decode(AggregateSummary, row["base"]),
        _decode(AggregateSummary, row["stress"]),
    )


@dataclass(frozen=True, slots=True)
class ResearchComparisonBundle:
    """Immutable typed comparison evidence with strict canonical serialization."""

    context_bytes: bytes
    cells: tuple[CellEvidence, ...]
    summaries: tuple[ComparisonSummary, ...]

    def __post_init__(self) -> None:
        if type(self.context_bytes) is not bytes or type(self.cells) is not tuple:
            raise ValueError("immutable comparison evidence required")
        if type(self.summaries) is not tuple:
            raise ValueError("immutable comparison summaries required")
        context = _parse(self.context_bytes)
        campaign_id, sessions = _validate_context(context)
        if any(type(cell) is not CellEvidence for cell in self.cells):
            raise ValueError("typed comparison cells required")
        if any(type(summary) is not ComparisonSummary for summary in self.summaries):
            raise ValueError("typed comparison summaries required")

        candidate_ids = _candidate_ids(campaign_id)
        regimes = regime_plan()
        expected_keys = tuple(
            (candidate_id, symbol, regime)
            for candidate_id in candidate_ids
            for symbol in UNIVERSE
            for regime in regimes
        )
        actual_keys = tuple(
            (cell.candidate_id, cell.symbol, cell.regime) for cell in self.cells
        )
        if len(self.cells) != 144 or actual_keys != tuple(
            (candidate_id, symbol, regime.label)
            for candidate_id, symbol, regime in expected_keys
        ):
            raise ValueError("incomplete, duplicate or misordered comparison cells")

        with localcontext(CONTEXT):
            for cell, (candidate_id, symbol, regime) in zip(
                self.cells, expected_keys, strict=True
            ):
                _validate_cell(cell, candidate_id, symbol, regime, sessions)

            expected_summaries = tuple(
                ComparisonSummary(
                    candidate,
                    candidate_id,
                    summarize(self.cells[index * 48 : (index + 1) * 48]),
                    summarize(self.cells[index * 48 : (index + 1) * 48], stress=True),
                )
                for index, (candidate, candidate_id) in enumerate(
                    zip(CANDIDATES, candidate_ids, strict=True)
                )
            )
            if self.summaries != expected_summaries:
                raise ValueError("comparison aggregate mismatch")

        body = self.to_bytes()
        if type(body) is not bytes or len(body) > MAX_BUNDLE_BYTES:
            raise ValueError("comparison bundle serialization failed")

    @property
    def context(self) -> dict[str, Any]:
        return _parse(self.context_bytes)

    @property
    def campaign_id(self) -> str:
        return _r11.campaign_identity(self.context)

    @property
    def selected_candidate(self) -> str:
        selected = _r11.select_candidate(self.summaries)
        if type(selected) is not str or selected not in {
            *(candidate.value for candidate in CANDIDATES),
            "NONE_QUALIFIES",
        }:
            raise ValueError("invalid research-only candidate selection")
        return selected

    @property
    def identity(self) -> str:
        identity = _r11.semantic_identity(
            "bundle",
            (
                self.context,
                asdict_rows(self.cells),
                asdict_rows(self.summaries),
                self.selected_candidate,
            ),
        )
        _uuid(identity)
        return identity

    @property
    def digest(self) -> str:
        return sha256(self.to_bytes()).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": _BUNDLE_SCHEMA,
            "campaign_id": self.campaign_id,
            "bundle_id": self.identity,
            "context": self.context,
            "cells": _plain(self.cells),
            "summaries": _plain(self.summaries),
            "selected_candidate": self.selected_candidate,
            "live_eligible": False,
        }

    def to_bytes(self) -> bytes:
        return canonical_json(self.to_dict())

    @classmethod
    def from_bytes(cls, body: bytes) -> ResearchComparisonBundle:
        raw = _parse(body)
        _exact(raw, _SUMMARY_FIELDS)
        if (
            raw["schema"] != _BUNDLE_SCHEMA
            or type(raw["cells"]) is not list
            or type(raw["summaries"]) is not list
            or raw["live_eligible"] is not False
            or type(raw["campaign_id"]) is not str
            or type(raw["bundle_id"]) is not str
            or type(raw["selected_candidate"]) is not str
            or type(raw["context"]) is not dict
        ):
            raise ValueError("invalid comparison bundle schema")
        bundle = cls(
            canonical_json(raw["context"]),
            tuple(_decode(CellEvidence, cell) for cell in raw["cells"]),
            tuple(_decode_summary(summary) for summary in raw["summaries"]),
        )
        if (
            bundle.campaign_id != raw["campaign_id"]
            or bundle.identity != raw["bundle_id"]
            or bundle.selected_candidate != raw["selected_candidate"]
            or bundle.to_bytes() != body
        ):
            raise ValueError("derived comparison evidence mismatch")
        return bundle


def build_bundle(
    context: dict[str, Any],
    cells: tuple[CellEvidence, ...],
    summaries: tuple[ComparisonSummary, ...],
) -> ResearchComparisonBundle:
    """Validate and freeze an in-memory R11 result without doing research."""
    return ResearchComparisonBundle(canonical_json(context), cells, summaries)


def _read_comparison_bundle(path: Path) -> ResearchComparisonBundle:
    """Read one explicitly supplied bounded report file; never repairs it."""
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        raise ValueError("an explicit absolute report path is required")
    with path.open("rb") as stream:
        body = stream.read(MAX_BUNDLE_BYTES + 1)
    return ResearchComparisonBundle.from_bytes(body)
