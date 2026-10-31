"""Integrity and read-only boundary tests for filtered trend evidence bundles."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, time
from decimal import Context, Decimal, localcontext
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

import pytest

from trading_bot.domain.market import Bar, Symbol
from trading_bot.experiments.filtered_trend_bundle import (
    ResearchBundle,
    build_bundle,
    canonical_json,
    presentation_rows,
    read_research_bundle,
    write_research_bundle,
)
from trading_bot.experiments.filtered_trend_campaign import (
    candidate_identity,
    run_campaign,
    semantic_identity,
)
from trading_bot.experiments.filtered_trend_data import (
    UNIVERSE,
    MultiAssetDataset,
    SymbolDataset,
)
from trading_bot.experiments.historical_research_sessions import (
    published_historical_session_authority,
)

_NEW_YORK = ZoneInfo("America/New_York")
_SOURCE_HEAD = "a" * 40
_SOURCE_TREE = "b" * 40


@pytest.fixture(scope="module")
def synthetic_evidence() -> tuple[MultiAssetDataset, ResearchBundle]:
    """Build one real 30x8x6 campaign over synthetic published-session bars."""

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

    dataset = MultiAssetDataset(tuple(datasets))
    context, cells, summaries = run_campaign(dataset, _SOURCE_HEAD, _SOURCE_TREE)
    return dataset, build_bundle(context, cells, summaries)


def _body(raw: dict) -> bytes:
    return canonical_json(raw)


def _raw(bundle: ResearchBundle) -> dict:
    return json.loads(bundle.to_bytes())


def test_bundle_roundtrip_is_canonical_and_complete(
    synthetic_evidence: tuple[MultiAssetDataset, ResearchBundle],
) -> None:
    _, bundle = synthetic_evidence
    body = bundle.to_bytes()

    assert body.endswith(b"\n")
    assert ResearchBundle.from_bytes(body) == bundle
    assert len(bundle.cells) == 30 * len(UNIVERSE) * 6
    assert len(bundle.summaries) == 30
    assert bundle.context["qualification_policy"] is None
    assert bundle.context["paper_binding"] is None
    assert bundle.context["live_eligible"] is False


def test_duplicate_unknown_and_tampered_evidence_are_rejected(
    synthetic_evidence: tuple[MultiAssetDataset, ResearchBundle],
) -> None:
    _, bundle = synthetic_evidence
    body = bundle.to_bytes()
    duplicate = body.replace(
        b'{"bundle_id":', b'{"bundle_id":"duplicate","bundle_id":', 1
    )
    with pytest.raises(ValueError, match="duplicate JSON field"):
        ResearchBundle.from_bytes(duplicate)

    unknown = _raw(bundle)
    unknown["unexpected"] = True
    with pytest.raises(ValueError, match="unexpected evidence fields"):
        ResearchBundle.from_bytes(_body(unknown))

    tampered = _raw(bundle)
    tampered["cells"][0]["result_id"] = str(uuid5(NAMESPACE_URL, "tampered"))
    with pytest.raises(ValueError, match="result identity mismatch"):
        ResearchBundle.from_bytes(_body(tampered))


def test_source_policy_and_provider_provenance_are_frozen(
    synthetic_evidence: tuple[MultiAssetDataset, ResearchBundle],
) -> None:
    _, bundle = synthetic_evidence
    changed_policy = _raw(bundle)
    changed_policy["context"]["economics"]["allocation"] = "0.90"
    with pytest.raises(ValueError, match="research policy differs"):
        ResearchBundle.from_bytes(_body(changed_policy))

    changed_provider = _raw(bundle)
    changed_provider["context"]["dataset_provenance"][0]["provider"]["feed"] = (
        "synthetic"
    )
    with pytest.raises(ValueError, match="provenance is frozen"):
        ResearchBundle.from_bytes(_body(changed_provider))


def test_aggregate_and_shortlist_mutations_are_rejected(
    synthetic_evidence: tuple[MultiAssetDataset, ResearchBundle],
) -> None:
    _, bundle = synthetic_evidence
    changed_aggregate = _raw(bundle)
    changed_aggregate["summaries"][0]["base"]["positive_regime_cells"] += 1
    with pytest.raises(ValueError, match="aggregate mismatch"):
        ResearchBundle.from_bytes(_body(changed_aggregate))

    changed_shortlist = _raw(bundle)
    changed_shortlist["shortlist"] = []
    with pytest.raises(ValueError, match="derived evidence mismatch"):
        ResearchBundle.from_bytes(_body(changed_shortlist))


def test_uuid5_identities_are_stable_under_ambient_decimal_context(
    synthetic_evidence: tuple[MultiAssetDataset, ResearchBundle],
) -> None:
    dataset, bundle = synthetic_evidence
    expected_ids = (
        bundle.campaign_id,
        bundle.bundle_id,
        bundle.summaries[0].candidate_id,
        bundle.cells[0].result_id,
    )
    with localcontext(Context(prec=3)):
        rebuilt_dataset = MultiAssetDataset(dataset.datasets)
        campaign_id = semantic_identity("campaign", bundle.context)
        candidate_id = candidate_identity(campaign_id, bundle.summaries[0].config)
        rebuilt_bundle = build_bundle(bundle.context, bundle.cells, bundle.summaries)
        actual_ids = (
            campaign_id,
            rebuilt_bundle.bundle_id,
            candidate_id,
            bundle.cells[0].result_id,
        )

    assert rebuilt_dataset.identity == dataset.identity
    assert actual_ids == expected_ids
    assert all(UUID(identity).version == 5 for identity in actual_ids)


def test_output_is_exclusive_readback_verified_and_presentation_is_detached(
    tmp_path: Path,
    synthetic_evidence: tuple[MultiAssetDataset, ResearchBundle],
) -> None:
    _, bundle = synthetic_evidence
    output = tmp_path / "filtered-trend-bundle.json"
    write_research_bundle(output, bundle)
    original = output.read_bytes()
    assert original == bundle.to_bytes()
    assert read_research_bundle(output) == bundle
    with pytest.raises(FileExistsError):
        write_research_bundle(output, bundle)
    assert output.read_bytes() == original

    rows = presentation_rows(bundle)
    assert rows
    rows[0]["symbol"] = "DETACHED"
    assert presentation_rows(bundle)[0]["symbol"] == bundle.cells[0].symbol
    assert not set(rows[0]).intersection(
        {"selected", "selection", "promotion", "paper_binding", "live_eligible"}
    )


def test_research_imports_do_not_load_provider_or_credential_clients() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_root = repo_root / "src"
    code = f"""
import importlib.abc
import socket
import sys
sys.path.insert(0, {str(source_root)!r})
forbidden = {{"alpaca", "robinhood", "httpx", "httpx2", "requests", "keyring"}}
class RejectForbiddenImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in forbidden:
            raise AssertionError("forbidden import: " + fullname)
        return None
def reject_network(*args, **kwargs):
    raise AssertionError("network connection attempted during import")
socket.create_connection = reject_network
socket.socket.connect = reject_network
sys.meta_path.insert(0, RejectForbiddenImports())
import trading_bot.experiments.filtered_trend_data
import trading_bot.experiments.filtered_trend_strategies
import trading_bot.experiments.filtered_trend_campaign
import trading_bot.experiments.filtered_trend_bundle
assert not forbidden.intersection(sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "field,value",
    [
        ("final_equity", Decimal(200000)),
        ("maximum_drawdown", Decimal(".2")),
        ("turnover", Decimal(1)),
        ("time_invested", Decimal(1)),
    ],
)
def test_cash_only_accounts_cannot_claim_unsupported_metrics(
    synthetic_evidence, field, value
):
    from dataclasses import replace

    _, bundle = synthetic_evidence
    cell = next(c for c in bundle.cells if not c.base.fills)
    changes = {field: value}
    if field == "final_equity":
        changes["total_return"] = Decimal(1)
    altered = replace(cell, base=replace(cell.base, **changes))
    cells = tuple(altered if c is cell else c for c in bundle.cells)
    with pytest.raises(
        ValueError, match="cash-only final equity|no-fill account metrics"
    ):
        build_bundle(bundle.context, cells, bundle.summaries)


def test_liquidated_account_terminal_equity_must_match_cash(synthetic_evidence):
    from dataclasses import replace
    from datetime import UTC, timedelta

    from trading_bot.experiments.filtered_trend_campaign import (
        CONTEXT,
        evaluate_cell,
        regime_plan,
        strategy_grid,
    )

    stamps = tuple(
        datetime(2017, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(300)
    ) + tuple(
        datetime(2019, 1, 2, 5, tzinfo=UTC) + timedelta(days=i) for i in range(100)
    )
    prices = tuple(
        Decimal(100) + Decimal(i) / 10 if i < 340 else Decimal(134) - Decimal(i - 340)
        for i in range(400)
    )
    bars = tuple(
        Bar(Symbol("SPY"), t, p, p + 1, p - 1, p, 1000)
        for t, p in zip(stamps, prices, strict=True)
    )
    cell = evaluate_cell(
        bars,
        strategy_grid()[0],
        regime_plan()[0],
        semantic_identity("candidate", "cash-regression"),
    )
    assert cell.base.fills[-1].side == "SELL"
    with localcontext(CONTEXT):
        claimed = replace(
            cell.base,
            final_equity=cell.base.final_equity + 100,
            total_return=(cell.base.final_equity + 100) / 100000 - 1,
        )
        _, bundle = synthetic_evidence
        target = bundle.cells[0]
        altered = replace(target, base=claimed)
        cells = (altered,) + bundle.cells[1:]
        with pytest.raises(ValueError, match="cash-only final equity"):
            build_bundle(bundle.context, cells, bundle.summaries)


@pytest.mark.parametrize("price", ["1e1000000000", "1e-1000000000"])
def test_noncanonical_exponent_metric_is_rejected_before_expansion(
    synthetic_evidence, price
):
    _, bundle = synthetic_evidence
    raw = _raw(bundle)
    raw["cells"][0]["base"]["final_equity"] = price
    with pytest.raises(ValueError, match="decimal must be canonical text"):
        ResearchBundle.from_bytes(_body(raw))
