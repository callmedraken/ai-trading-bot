"""Integrity tests for canonical filtered-trend comparison v2 bundles."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain.market import Bar, Symbol
from trading_bot.experiments.filtered_trend_bundle import canonical_json
from trading_bot.experiments.filtered_trend_campaign import decimal_text
from trading_bot.experiments.filtered_trend_comparison_bundle_v2 import (
    ResearchComparisonBundle,
    build_bundle,
)
from trading_bot.experiments.filtered_trend_comparison_campaign_v2 import (
    CANDIDATES,
    qualifies_candidate,
    run_campaign,
    select_candidate,
)
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    SymbolDataset,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)
from trading_bot.gui.research_comparison_service import (
    read_comparison_report,
    to_research_view,
)
from trading_bot.live_prototype.contracts import ResearchView

_NEW_YORK = ZoneInfo("America/New_York")
_SOURCE_HEAD = "a" * 40
_SOURCE_TREE = "b" * 40


@pytest.fixture(scope="module")
def synthetic_bundle() -> ResearchComparisonBundle:
    sessions = tuple(
        session
        for session in published_historical_session_authority().sessions
        if date(2016, 1, 1) <= session < date(2024, 1, 1)
    )
    datasets = []
    for symbol_index, symbol_text in enumerate(UNIVERSE):
        symbol = Symbol(symbol_text)
        base = Decimal(100 + symbol_index * 10)
        bars = tuple(
            Bar(
                symbol=symbol,
                timestamp=datetime.combine(session, time.min, tzinfo=_NEW_YORK),
                open=base + Decimal(index) / Decimal("100"),
                high=base + Decimal(index) / Decimal("100") + Decimal("0.5"),
                low=base + Decimal(index) / Decimal("100") - Decimal("0.5"),
                close=base + Decimal(index) / Decimal("100"),
                volume=1_000_000,
            )
            for index, session in enumerate(sessions)
        )
        datasets.append(SymbolDataset(symbol_text, bars))

    context, cells, summaries = run_campaign(
        MultiAssetDataset(tuple(datasets)), _SOURCE_HEAD, _SOURCE_TREE
    )
    assert len(cells) == 144
    return build_bundle(context, cells, summaries)


def _raw(bundle: ResearchComparisonBundle) -> dict:
    return json.loads(bundle.to_bytes())


def _mutated_bytes(bundle: ResearchComparisonBundle, mutate) -> bytes:
    raw = _raw(bundle)
    mutate(raw)
    return canonical_json(raw)


def test_round_trip_is_canonical_bounded_and_research_only(
    synthetic_bundle: ResearchComparisonBundle,
) -> None:
    bundle = synthetic_bundle
    body = bundle.to_bytes()

    assert len(bundle.cells) == 144
    assert tuple(summary.candidate for summary in bundle.summaries) == CANDIDATES
    assert body.endswith(b"\n")
    assert ResearchComparisonBundle.from_bytes(body) == bundle
    assert bundle.digest == sha256(body).hexdigest()
    assert UUID(bundle.identity).version == 5
    assert bundle.to_dict()["bundle_id"] == bundle.identity
    assert bundle.selected_candidate == select_candidate(bundle.summaries)
    assert bundle.to_dict()["live_eligible"] is False


def test_rejects_duplicate_unknown_noncanonical_and_live_enabled_fields(
    synthetic_bundle: ResearchComparisonBundle,
) -> None:
    body = synthetic_bundle.to_bytes()
    duplicate = body.replace(b'"schema":', b'"schema":"duplicate","schema":', 1)
    with pytest.raises(ValueError, match="duplicate JSON field"):
        ResearchComparisonBundle.from_bytes(duplicate)

    with pytest.raises(ValueError, match="unexpected evidence fields"):
        ResearchComparisonBundle.from_bytes(
            _mutated_bytes(synthetic_bundle, lambda raw: raw.update(extra="unknown"))
        )

    def add_unknown_cell_field(raw: dict) -> None:
        raw["cells"][0]["extra"] = "unknown"

    with pytest.raises(ValueError, match="unexpected evidence fields"):
        ResearchComparisonBundle.from_bytes(
            _mutated_bytes(synthetic_bundle, add_unknown_cell_field)
        )

    def enable_live(raw: dict) -> None:
        raw["live_eligible"] = True

    with pytest.raises(ValueError, match="invalid comparison bundle schema"):
        ResearchComparisonBundle.from_bytes(
            _mutated_bytes(synthetic_bundle, enable_live)
        )

    def noncanonical_decimal(raw: dict) -> None:
        raw["cells"][0]["base"]["total_return"] = "0.0"

    with pytest.raises(ValueError, match="noncanonical decimal"):
        ResearchComparisonBundle.from_bytes(
            _mutated_bytes(synthetic_bundle, noncanonical_decimal)
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "source",
        "policy",
        "economics",
        "dataset_identity",
        "dataset_coverage",
        "provider_provenance",
        "prior_campaign",
    ],
)
def test_rejects_context_policy_data_and_provenance_tampering(
    synthetic_bundle: ResearchComparisonBundle,
    mutation: str,
) -> None:
    def mutate(raw: dict) -> None:
        context = raw["context"]
        if mutation == "source":
            context["source_head"] = "c" * 40
        elif mutation == "policy":
            context["qualification_policy"] = "permissive"
        elif mutation == "economics":
            context["economics"]["allocation"] = "0.5"
        elif mutation == "dataset_identity":
            context["dataset_id"] = "9a9de371-4d70-5fea-b8d2-5cf5e9c93140"
        elif mutation == "dataset_coverage":
            context["dataset_provenance"][0]["bar_count"] += 1
        elif mutation == "provider_provenance":
            context["dataset_provenance"][0]["provider"]["endpoint"] = (
                "https://unapproved.example"
            )
        elif mutation == "prior_campaign":
            context["prior_campaign_id"] = "9a9de371-4d70-5fea-b8d2-5cf5e9c93140"

    with pytest.raises((ValueError, TypeError)):
        ResearchComparisonBundle.from_bytes(_mutated_bytes(synthetic_bundle, mutate))


@pytest.mark.parametrize("operation", ["remove", "duplicate", "reorder"])
def test_rejects_missing_duplicate_or_reordered_cells(
    synthetic_bundle: ResearchComparisonBundle,
    operation: str,
) -> None:
    def mutate(raw: dict) -> None:
        if operation == "remove":
            raw["cells"].pop()
        elif operation == "duplicate":
            raw["cells"][1] = raw["cells"][0]
        else:
            raw["cells"][0], raw["cells"][1] = raw["cells"][1], raw["cells"][0]

    with pytest.raises(ValueError, match="incomplete, duplicate or misordered"):
        ResearchComparisonBundle.from_bytes(_mutated_bytes(synthetic_bundle, mutate))


def test_recomputes_semantic_ids_summaries_and_fill_accounting(
    synthetic_bundle: ResearchComparisonBundle,
) -> None:
    bundle = synthetic_bundle

    def change_result_id(raw: dict) -> None:
        raw["cells"][0]["result_id"] = "9a9de371-4d70-5fea-b8d2-5cf5e9c93140"

    with pytest.raises(ValueError, match="cell result identity mismatch"):
        ResearchComparisonBundle.from_bytes(_mutated_bytes(bundle, change_result_id))

    def change_summary(raw: dict) -> None:
        raw["summaries"][1]["base"]["median_continuous_return"] = "999"

    with pytest.raises(ValueError, match="comparison aggregate mismatch"):
        ResearchComparisonBundle.from_bytes(_mutated_bytes(bundle, change_summary))

    def change_fill_price(raw: dict) -> None:
        fill = raw["cells"][0]["buy_and_hold"]["fills"][0]
        fill["price"] = "999999"

    with pytest.raises(ValueError, match="unexpected economics/risk evidence"):
        ResearchComparisonBundle.from_bytes(_mutated_bytes(bundle, change_fill_price))

    def introduce_lookahead(raw: dict) -> None:
        strategy_cell = next(cell for cell in raw["cells"] if cell["base"]["fills"])
        fill = strategy_cell["base"]["fills"][0]
        fill["information_through"] = fill["session"]

    with pytest.raises(ValueError, match="lookahead in evidence"):
        ResearchComparisonBundle.from_bytes(_mutated_bytes(bundle, introduce_lookahead))

    def change_selection(raw: dict) -> None:
        raw["selected_candidate"] = "NOT_A_CANDIDATE"

    with pytest.raises(ValueError, match="derived comparison evidence mismatch"):
        ResearchComparisonBundle.from_bytes(_mutated_bytes(bundle, change_selection))


def test_research_projection_is_pure_and_never_live_eligible(
    synthetic_bundle: ResearchComparisonBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbid_file_io(*args, **kwargs):
        raise AssertionError("projection attempted filesystem access")

    monkeypatch.setattr(Path, "open", forbid_file_io)
    view = to_research_view(synthetic_bundle)

    assert type(view) is ResearchView
    assert len(view.candidates) == 3
    assert view.policy == "comparison-v2/qualification-v1"
    assert view.bundle_digest == synthetic_bundle.digest
    assert view.dataset_digest == synthetic_bundle.context["dataset_id"]
    assert view.selected == synthetic_bundle.selected_candidate
    assert view.prior_trials == 30
    assert view.new_trials == 3
    assert view.live_eligible is False
    control = view.candidates[0]
    assert control.candidate == CANDIDATES[0].value
    assert control.reasons == ("CONTROL",)
    for candidate_view, summary in zip(
        view.candidates, synthetic_bundle.summaries, strict=True
    ):
        expected_qualified = summary.candidate is not CANDIDATES[0] and (
            qualifies_candidate(summary, synthetic_bundle.summaries[0])
        )
        assert candidate_view.qualified is expected_qualified
        assert candidate_view.reasons == (
            ()
            if expected_qualified
            else ("CONTROL",)
            if summary.candidate is CANDIDATES[0]
            else ("QUALIFICATION_FAILED",)
        )
        assert candidate_view.base_return == decimal_text(
            summary.base.median_continuous_return
        )
        assert candidate_view.stress_return == decimal_text(
            summary.stress.median_continuous_return
        )
        assert candidate_view.stress_drawdown == decimal_text(
            summary.stress.worst_continuous_drawdown
        )
        assert candidate_view.turnover == decimal_text(summary.stress.median_turnover)


def test_explicit_reader_returns_valid_projection_and_fixed_unavailable_state(
    synthetic_bundle: ResearchComparisonBundle,
    tmp_path: Path,
) -> None:
    report = tmp_path / "comparison.json"
    report.write_bytes(synthetic_bundle.to_bytes())
    view = read_comparison_report(report)
    assert view == to_research_view(synthetic_bundle)

    secret_marker = "RAW_REPORT_ERROR_SHOULD_NOT_LEAK"
    malformed = tmp_path / "malformed.json"
    malformed.write_text(secret_marker, encoding="utf-8")
    unavailable = read_comparison_report(malformed)
    assert unavailable == ResearchView(
        selected="UNAVAILABLE",
        assumptions=("Comparison report unavailable",),
        live_eligible=False,
    )
    assert secret_marker not in repr(unavailable)
    assert str(malformed) not in repr(unavailable)
    assert read_comparison_report("relative-report.json") == unavailable
