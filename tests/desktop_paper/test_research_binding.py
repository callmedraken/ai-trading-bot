"""Focused external-bundle binding and fail-closed composition coverage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.desktop_paper.research_binding import (
    ACCEPTED_FILTERED_TREND_BUNDLE_PATH,
    FILTERED_TREND_BUNDLE_ID,
    FILTERED_TREND_CAMPAIGN_ID,
    FILTERED_TREND_CANDIDATE_ID,
    FILTERED_TREND_DATASET_ID,
    FILTERED_TREND_PRICE_BASIS,
    FILTERED_TREND_SOURCE_HEAD,
    FILTERED_TREND_SOURCE_TREE,
    PaperEvaluationBindingRejected,
    load_accepted_paper_binding,
)
from trading_bot.experiments.filtered_trend_bundle import ResearchBundle


def _context() -> dict[str, object]:
    return {
        "schema": "filtered-trend-campaign/v1",
        "source_head": FILTERED_TREND_SOURCE_HEAD,
        "source_tree": FILTERED_TREND_SOURCE_TREE,
        "dataset_id": FILTERED_TREND_DATASET_ID,
        "price_basis": FILTERED_TREND_PRICE_BASIS,
        "qualification_policy": None,
        "paper_binding": None,
        "live_eligible": False,
        "universe": ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "PDBC"],
    }


def _fake_bundle(
    *,
    context: dict[str, object] | None = None,
    shortlist: list[str] | None = None,
    campaign_id: str = FILTERED_TREND_CAMPAIGN_ID,
    bundle_id: str = FILTERED_TREND_BUNDLE_ID,
    candidate_id: str = FILTERED_TREND_CANDIDATE_ID,
    family: str = "BASE_MA",
    fast: int = 35,
    slow: int = 50,
    parameter: str = "none",
) -> SimpleNamespace:
    candidate = SimpleNamespace(
        candidate_id=candidate_id,
        config=SimpleNamespace(
            family=family, fast=fast, slow=slow, parameter=parameter
        ),
        base=SimpleNamespace(median_continuous_return="changed"),
    )
    return SimpleNamespace(
        context=context or _context(),
        campaign_id=campaign_id,
        bundle_id=bundle_id,
        summaries=(candidate,),
        to_dict=lambda: {
            "shortlist": shortlist
            or [candidate_id] + [f"candidate-{i}" for i in range(9)]
        },
    )


def _patch_bundle(monkeypatch, fake_bundle: SimpleNamespace, path: Path) -> bytes:
    body = json.dumps({"schema": "filtered-trend-bundle/v1"}).encode("ascii")
    path.write_bytes(body)
    monkeypatch.setattr(
        ResearchBundle,
        "from_bytes",
        classmethod(lambda cls, value: fake_bundle),
    )
    return body


@pytest.mark.skipif(
    not ACCEPTED_FILTERED_TREND_BUNDLE_PATH.exists(),
    reason="accepted real research artifact is external to the repository",
)
def test_real_bundle_derives_exact_rank_one_spy_binding() -> None:
    binding = load_accepted_paper_binding(ACCEPTED_FILTERED_TREND_BUNDLE_PATH)

    assert binding.strategy_family == "FILTERED_TREND_BASE_MA"
    assert binding.strategy_version == "filtered-trend-base-ma/v1"
    assert binding.symbol.value == "SPY"
    assert binding.parameter_set == (("fast", 35), ("slow", 50))
    assert binding.research_campaign_id == UUID(FILTERED_TREND_CAMPAIGN_ID)
    assert binding.research_bundle_id == UUID(FILTERED_TREND_BUNDLE_ID)
    assert binding.research_candidate_id == UUID(FILTERED_TREND_CANDIDATE_ID)
    assert (
        binding.provenance_digest
        == hashlib.sha256(ACCEPTED_FILTERED_TREND_BUNDLE_PATH.read_bytes()).hexdigest()
    )
    assert binding.purpose == "PAPER_EVALUATION"
    assert binding.qualification_policy is None
    assert binding.live_eligible is False


@pytest.mark.parametrize(
    "change",
    [
        {"campaign_id": "wrong"},
        {"bundle_id": "wrong"},
        {"context": {**_context(), "dataset_id": "wrong"}},
        {"context": {**_context(), "source_head": "f" * 40}},
        {"context": {**_context(), "source_tree": "e" * 40}},
        {"context": {**_context(), "price_basis": "OTHER"}},
        {"context": {**_context(), "qualification_policy": "qualified"}},
        {"context": {**_context(), "live_eligible": True}},
        {"shortlist": ["wrong"] + [f"candidate-{i}" for i in range(9)]},
        {"candidate_id": "wrong"},
        {"family": "MA_ADX"},
        {"fast": 55},
        {"slow": 100},
        {"parameter": "20"},
        {"context": {**_context(), "universe": ["QQQ", "SPY"]}},
    ],
)
def test_synthetic_bundle_mismatch_fails_closed(
    tmp_path: Path, monkeypatch, change: dict[str, object]
) -> None:
    kwargs = {
        "context": _context(),
        "shortlist": None,
        "family": "BASE_MA",
        "fast": 35,
        "slow": 50,
        "parameter": "none",
    }
    kwargs.update(change)
    fake = _fake_bundle(**kwargs)
    _patch_bundle(monkeypatch, fake, tmp_path / "bundle.json")

    with pytest.raises(PaperEvaluationBindingRejected):
        load_accepted_paper_binding(tmp_path / "bundle.json")


def test_historical_performance_change_never_substitutes_frozen_symbol(
    tmp_path: Path, monkeypatch
) -> None:
    fake = _fake_bundle()
    fake.summaries[0].base.median_continuous_return = "-999999"
    body = _patch_bundle(monkeypatch, fake, tmp_path / "bundle.json")

    binding = load_accepted_paper_binding(tmp_path / "bundle.json")

    assert binding.symbol.value == "SPY"
    assert binding.provenance_digest == hashlib.sha256(body).hexdigest()


def test_missing_or_malformed_bundle_fails_before_runtime_state(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(PaperEvaluationBindingRejected, match="SELECTION_REQUIRED"):
        load_accepted_paper_binding(missing)

    malformed = tmp_path / "malformed.json"
    malformed.write_bytes(b"not-json")
    with pytest.raises(PaperEvaluationBindingRejected):
        load_accepted_paper_binding(malformed)

    assert not list(tmp_path.glob("*.sqlite"))
    assert not list(tmp_path.glob("*.jsonl"))
