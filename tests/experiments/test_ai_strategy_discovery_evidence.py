from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

from trading_bot.experiments import ai_strategy_discovery_evidence as evidence
from trading_bot.experiments.ai_strategy_discovery import DiscoveryError, TrialLedger
from trading_bot.experiments.filtered_trend_bundle import canonical_json
from trading_bot.experiments.filtered_trend_campaign import frozen_context
from trading_bot.experiments.filtered_trend_data import ProviderProvenance

_HEAD = "a" * 40
_TREE = "b" * 40


def _by_id(
    inventory: evidence.Generation0Inventory,
) -> dict[str, evidence.EvidenceReference]:
    return {item.reference_id: item for item in inventory.references}


def _reidentify(value: dict[str, object], version: str) -> dict[str, object]:
    payload = dict(value)
    payload.pop("identity", None)
    value["identity"] = evidence._identity(version, payload)
    return value


def test_default_inventory_distinguishes_evidence_states_without_scanning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("default inventory must not inspect the filesystem")

    monkeypatch.setattr(evidence.os, "lstat", fail)
    inventory = evidence.build_generation0_inventory()
    refs = _by_id(inventory)

    assert (
        refs["arch147-filtered-trend-multi-asset"].status
        is evidence.EvidenceStatus.UNAVAILABLE
    )
    assert refs["arch148-churn-research"].status is evidence.EvidenceStatus.UNAVAILABLE
    assert (
        refs["arch148-bullish-band-session-reference"].status
        is evidence.EvidenceStatus.NONCANONICAL_SESSION_EVIDENCE
    )
    assert (
        refs["arch148-late-session-momentum-design"].status
        is evidence.EvidenceStatus.QUEUED_UNEVALUATED
    )
    assert (
        refs["prior-canonical-research"].status is evidence.EvidenceStatus.UNAVAILABLE
    )
    assert refs["arch147-filtered-trend-multi-asset"].synthesis.timeframe == "1Day"
    assert refs["arch148-churn-research"].synthesis.metrics
    assert refs["arch148-late-session-momentum-design"].synthesis.metrics == ()
    assert (
        "FINAL_HOLDOUT"
        in refs["arch148-churn-research"].synthesis.unanswered_questions[-1]
    )
    assert refs["arch148-bullish-band-session-reference"].artifact_identity is None


def test_a147_requires_exact_reviewed_binding_and_uses_public_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b"synthetic filtered-trend bundle fixture"
    path = tmp_path / "bundle.json"
    path.write_bytes(body)
    symbols = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "PDBC")
    dataset_provenance = [
        {
            "symbol": symbol,
            "provider": ProviderProvenance().to_dict(),
            "bar_count": 1,
            "first_bar": "2016-01-04T00:00:00-05:00",
            "last_bar": "2023-12-29T00:00:00-05:00",
        }
        for symbol in symbols
    ]
    context = frozen_context(
        _HEAD,
        _TREE,
        "synthetic-dataset",
        "ALPACA_ALL_ADJUSTED_PRICE_V1",
        dataset_provenance,
    )
    fake_bundle = object.__new__(evidence.ResearchBundle)
    object.__setattr__(fake_bundle, "context_bytes", canonical_json(context))
    object.__setattr__(fake_bundle, "summaries", ())
    object.__setattr__(fake_bundle, "cells", ())
    bundle_identity = fake_bundle.bundle_id
    calls: list[bytes] = []

    def parse_fixture(cls: type, payload: bytes) -> object:
        assert cls is evidence.ResearchBundle
        calls.append(payload)
        return fake_bundle

    monkeypatch.setattr(
        evidence.ResearchBundle,
        "from_bytes",
        classmethod(parse_fixture),
    )
    binding = evidence.ReviewedA147Binding(
        bundle_identity=bundle_identity,
        sha256=hashlib.sha256(body).hexdigest(),
        source_head=_HEAD,
        source_tree=_TREE,
        review_reference="synthetic-reviewed-A147-acceptance-tuple",
    )

    inventory = evidence.build_generation0_inventory(
        a147_path=path,
        a147_binding=binding,
    )
    ref = _by_id(inventory)["arch147-filtered-trend-multi-asset"]

    assert ref.status is evidence.EvidenceStatus.CANONICAL_ACCEPTED
    assert ref.verification == "VERIFIED_EXACT_BINDING"
    assert ref.review_reference == binding.review_reference
    assert ref.artifact_sha256 == binding.sha256
    assert json.loads(ref.synthesis.canonical_summary_json)["symbol_regime_cells"] == []
    assert calls == [body]
    assert str(path) not in inventory.to_bytes().decode("utf-8")
    wrong_source = evidence.ReviewedA147Binding(
        bundle_identity=bundle_identity,
        sha256=binding.sha256,
        source_head=_HEAD,
        source_tree="c" * 40,
        review_reference="synthetic-reviewed-A147-acceptance-tuple",
    )
    with pytest.raises(DiscoveryError, match="A147_ACCEPTANCE_BINDING_MISMATCH"):
        evidence.build_generation0_inventory(a147_path=path, a147_binding=wrong_source)


def test_a147_path_without_review_binding_is_never_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("unbound evidence path must not be inspected")

    monkeypatch.setattr(evidence.os, "lstat", fail)
    inventory = evidence.build_generation0_inventory(a147_path=tmp_path / "bundle.json")
    ref = _by_id(inventory)["arch147-filtered-trend-multi-asset"]
    assert ref.status is evidence.EvidenceStatus.UNAVAILABLE
    assert ref.verification == "NO_REVIEWED_ACCEPTANCE_BINDING; PATH_NOT_OPENED"


def test_a147_digest_mismatch_fails_before_public_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "bundle.json"
    body = b"tampered synthetic bundle"
    path.write_bytes(body)

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("digest mismatch must be checked before parsing")

    monkeypatch.setattr(evidence.ResearchBundle, "from_bytes", fail)
    binding = evidence.ReviewedA147Binding(
        bundle_identity=str(uuid5(NAMESPACE_URL, "synthetic expected bundle")),
        sha256="0" * 64,
        source_head=_HEAD,
        source_tree=_TREE,
        review_reference="synthetic-reviewed-A147-acceptance-tuple",
    )
    with pytest.raises(DiscoveryError, match="A147_ACCEPTANCE_BINDING_MISMATCH"):
        evidence.build_generation0_inventory(a147_path=path, a147_binding=binding)


def test_a148_churn_uses_pinned_bytes_and_public_report_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "research.json"
    body = b"synthetic churn report fixture"
    path.write_bytes(body)

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("unmatched evidence digest must not invoke the reader")

    monkeypatch.setattr(evidence.ChurnResearchReport, "from_json", fail)
    with pytest.raises(DiscoveryError, match="A148_CHURN_ACCEPTANCE_BINDING_MISMATCH"):
        evidence.build_generation0_inventory(a148_churn_path=path)


def test_a148_exact_binding_projects_a_bounded_canonical_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "accepted-research.json"
    body = b"synthetic reader fixture; expected digest supplied by the parser test"
    path.write_bytes(body)
    fields = {
        "source": {
            "candidate_head": evidence._A148_CHURN_SOURCE_HEAD,
            "candidate_tree": evidence._A148_CHURN_SOURCE_TREE,
        },
        "input": {"dataset_identity": "synthetic-accepted-dataset"},
        "scope": {"name": "OPEN", "final_holdout_accesses": 0},
        "accepted_baseline": {"runs": {}},
        "variant_definitions": [],
        "cost_models": [],
        "partitions": [],
        "equity_mark_timestamp_semantics": "synthetic",
        "runs": [],
        "descriptive_ranking": [],
        "selection": {"selected_variant": None},
        "effects": {"final_holdout_accesses": 0},
    }
    fake_report = SimpleNamespace(
        identity=evidence._A148_CHURN_IDENTITY,
        to_dict=lambda: fields,
    )
    original_sha256 = hashlib.sha256

    def pinned_sha256(value: bytes = b"") -> object:
        if value == body:
            return SimpleNamespace(hexdigest=lambda: evidence._A148_CHURN_SHA256)
        return original_sha256(value)

    calls: list[bytes] = []

    def parse_fixture(cls: type, value: bytes) -> object:
        assert cls is evidence.ChurnResearchReport
        calls.append(value)
        return fake_report

    monkeypatch.setattr(evidence.hashlib, "sha256", pinned_sha256)
    monkeypatch.setattr(
        evidence.ChurnResearchReport,
        "from_json",
        classmethod(parse_fixture),
    )
    inventory = evidence.build_generation0_inventory(a148_churn_path=path)
    ref = _by_id(inventory)["arch148-churn-research"]

    assert ref.status is evidence.EvidenceStatus.CANONICAL_REJECTED
    assert ref.artifact_identity == evidence._A148_CHURN_IDENTITY
    assert ref.source_head == evidence._A148_CHURN_SOURCE_HEAD
    assert ref.source_tree == evidence._A148_CHURN_SOURCE_TREE
    assert ref.synthesis.canonical_summary_json is not None
    assert json.loads(ref.synthesis.canonical_summary_json)["runs"] == []
    assert calls == [body]
    fields["source"]["candidate_tree"] = "c" * 40
    with pytest.raises(DiscoveryError, match="A148_CHURN_ACCEPTANCE_BINDING_MISMATCH"):
        evidence.build_generation0_inventory(a148_churn_path=path)


def test_missing_explicit_evidence_file_remains_unavailable(tmp_path: Path) -> None:
    missing = tmp_path / "not-present.json"
    binding = evidence.ReviewedA147Binding(
        bundle_identity=str(uuid5(NAMESPACE_URL, "synthetic missing bundle")),
        sha256="1" * 64,
        source_head=_HEAD,
        source_tree=_TREE,
        review_reference="synthetic-reviewed-A147-acceptance-tuple",
    )
    inventory = evidence.build_generation0_inventory(
        a147_path=missing,
        a147_binding=binding,
        a148_churn_path=missing,
    )
    refs = _by_id(inventory)
    assert (
        refs["arch147-filtered-trend-multi-asset"].status
        is evidence.EvidenceStatus.UNAVAILABLE
    )
    assert refs["arch148-churn-research"].status is evidence.EvidenceStatus.UNAVAILABLE
    assert (
        refs["arch147-filtered-trend-multi-asset"].artifact_identity
        == binding.bundle_identity
    )


def test_path_guards_reject_holdout_traversal_links_and_nonregular_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("FINAL_HOLDOUT path must fail before filesystem access")

    monkeypatch.setattr(evidence.os, "lstat", fail)
    monkeypatch.setattr(evidence.os, "open", fail)
    holdout_path = tmp_path / "FINAL_HOLDOUT-evidence.json"
    with pytest.raises(DiscoveryError, match="FINAL_HOLDOUT_PATH_FORBIDDEN"):
        evidence.build_generation0_inventory(a148_churn_path=holdout_path)

    with pytest.raises(DiscoveryError, match="EVIDENCE_PATH_INVALID"):
        evidence._read_explicit_file(tmp_path / ".." / "escaped.json", 64)


def test_path_guard_rejects_symlinks_reparse_points_and_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_lstat = os.lstat
    link = tmp_path / "linked.json"
    symlink_stat = os.stat_result((stat.S_IFLNK | 0o777, 1, 0, 0, 0, 0, 0, 0, 0, 0))

    def with_synthetic_symlink(path: Path) -> os.stat_result:
        if Path(path) == link:
            return symlink_stat
        return original_lstat(path)

    monkeypatch.setattr(evidence.os, "lstat", with_synthetic_symlink)
    with pytest.raises(DiscoveryError, match="EVIDENCE_PATH_LINKED"):
        evidence._read_explicit_file(link, 128)

    junction = tmp_path / "reparse-directory"
    reparse_path = junction / "evidence.json"

    def with_synthetic_reparse(path: Path) -> os.stat_result | SimpleNamespace:
        if Path(path) == junction:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0x400
            )
        if Path(path) == reparse_path:
            return SimpleNamespace(
                st_mode=stat.S_IFREG | 0o644,
                st_file_attributes=0,
                st_size=0,
            )
        return original_lstat(path)

    monkeypatch.setattr(evidence.os, "lstat", with_synthetic_reparse)
    with pytest.raises(DiscoveryError, match="EVIDENCE_PATH_LINKED"):
        evidence._read_explicit_file(reparse_path, 128)

    monkeypatch.setattr(evidence.os, "lstat", original_lstat)
    with pytest.raises(DiscoveryError, match="EVIDENCE_FILE_INVALID_OR_OVERSIZED"):
        evidence._read_explicit_file(tmp_path, 128)


def test_reference_status_cannot_claim_unbound_canonical_evidence() -> None:
    reference = evidence._a147_unavailable()
    raw = reference.to_dict()
    raw["status"] = evidence.EvidenceStatus.CANONICAL_ACCEPTED.value
    raw["verification"] = "VERIFIED_EXACT_BINDING"
    with pytest.raises(DiscoveryError, match="GENERATION0_CANONICAL_BINDING_REQUIRED"):
        evidence.EvidenceReference.from_dict(raw)


def test_parsers_reject_duplicate_unknown_missing_fields() -> None:
    inventory = evidence.build_generation0_inventory()
    duplicate_field = b'{"identity":"x","identity":"y"}'
    with pytest.raises(DiscoveryError, match="DUPLICATE_JSON_FIELD"):
        evidence.Generation0Inventory.from_bytes(duplicate_field)

    extra = inventory.to_dict()
    extra["unknown"] = True
    with pytest.raises(DiscoveryError, match="UNKNOWN_OR_MISSING_FIELD"):
        evidence.Generation0Inventory.from_bytes(evidence.canonical_json_bytes(extra))

    missing = inventory.to_dict()
    del missing["references"]
    with pytest.raises(DiscoveryError, match="UNKNOWN_OR_MISSING_FIELD"):
        evidence.Generation0Inventory.from_bytes(evidence.canonical_json_bytes(missing))


def test_campaign_parser_is_strict_bounded_and_path_read_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inventory = evidence.build_generation0_inventory()
    artifact = evidence.create_campaign_foundation(
        source_head=_HEAD,
        source_tree=_TREE,
        generation0=inventory,
        trial_ledger=TrialLedger(records=()),
    )
    body = artifact.to_bytes()
    expected = {
        "expected_source_head": _HEAD,
        "expected_source_tree": _TREE,
        "expected_generation0": inventory,
    }

    with pytest.raises(DiscoveryError, match="DUPLICATE_JSON_FIELD"):
        evidence.verify_campaign_foundation(
            b'{"identity":"x","identity":"y"}', **expected
        )

    extra = artifact.to_dict()
    extra["unknown"] = True
    with pytest.raises(DiscoveryError, match="UNKNOWN_OR_MISSING_FIELD"):
        evidence.verify_campaign_foundation(
            evidence.canonical_json_bytes(extra), **expected
        )

    missing = artifact.to_dict()
    del missing["authority"]
    with pytest.raises(DiscoveryError, match="UNKNOWN_OR_MISSING_FIELD"):
        evidence.verify_campaign_foundation(
            evidence.canonical_json_bytes(missing), **expected
        )

    path = tmp_path / "foundation.json"
    path.write_bytes(body)
    assert evidence.read_campaign_foundation(path, **expected) == artifact

    monkeypatch.setattr(evidence, "MAX_FOUNDATION_BYTES", len(body) - 1)
    with pytest.raises(DiscoveryError, match="CAMPAIGN_FOUNDATION_JSON_INVALID"):
        evidence.verify_campaign_foundation(body, **expected)


def test_campaign_artifact_binds_ledger_inventory_source_budgets_and_zero_effects() -> (
    None
):
    inventory = evidence.build_generation0_inventory()
    ledger = TrialLedger(records=())
    artifact = evidence.create_campaign_foundation(
        source_head=_HEAD,
        source_tree=_TREE,
        generation0=inventory,
        trial_ledger=ledger,
    )
    body = artifact.to_bytes()
    verified = evidence.verify_campaign_foundation(
        body,
        expected_source_head=_HEAD,
        expected_source_tree=_TREE,
        expected_generation0=inventory,
    )
    document = verified.to_dict()

    assert verified.evaluated_trial_count == 0
    assert document["trial_ledger"] == ledger.to_dict()
    assert document["budgets"] == {
        "generation_1_max_evaluated": 32,
        "generation_2_max_evaluated": 16,
    }
    assert document["final_holdout_sealed"] is True
    assert set(document["effects"].values()) == {0}
    assert document["authority"] == evidence.AUTHORITY

    with pytest.raises(DiscoveryError, match="CAMPAIGN_FOUNDATION_SOURCE_MISMATCH"):
        evidence.verify_campaign_foundation(
            body,
            expected_source_head="c" * 40,
            expected_source_tree=_TREE,
            expected_generation0=inventory,
        )


def test_foundation_requires_independent_inventory_and_rejects_effect_tampering() -> (
    None
):
    inventory = evidence.build_generation0_inventory()
    artifact = evidence.create_campaign_foundation(
        source_head=_HEAD,
        source_tree=_TREE,
        generation0=inventory,
        trial_ledger=TrialLedger(records=()),
    )
    body = artifact.to_bytes()

    tampered_inventory = inventory.to_dict()
    tampered_inventory["references"][0]["synthesis"]["failure_mode"] = "counterfeit"
    tampered_inventory = _reidentify(
        tampered_inventory, evidence._INVENTORY_IDENTITY_VERSION
    )
    untrusted_inventory = evidence.Generation0Inventory.from_bytes(
        evidence.canonical_json_bytes(tampered_inventory)
    )
    untrusted_artifact = evidence.create_campaign_foundation(
        source_head=_HEAD,
        source_tree=_TREE,
        generation0=untrusted_inventory,
        trial_ledger=TrialLedger(records=()),
    )
    with pytest.raises(DiscoveryError, match="CAMPAIGN_FOUNDATION_INVENTORY_MISMATCH"):
        evidence.verify_campaign_foundation(
            untrusted_artifact.to_bytes(),
            expected_source_head=_HEAD,
            expected_source_tree=_TREE,
            expected_generation0=inventory,
        )

    raw = json.loads(body)
    raw["effects"]["PROVIDER_CALLS"] = 1
    raw = _reidentify(raw, evidence._FOUNDATION_IDENTITY_VERSION)
    with pytest.raises(DiscoveryError, match="CAMPAIGN_FOUNDATION_EFFECTS_INVALID"):
        evidence.verify_campaign_foundation(
            evidence.canonical_json_bytes(raw),
            expected_source_head=_HEAD,
            expected_source_tree=_TREE,
            expected_generation0=inventory,
        )


def test_campaign_rejects_misleading_identity_and_holdout_mutation() -> None:
    inventory = evidence.build_generation0_inventory()
    artifact = evidence.create_campaign_foundation(
        source_head=_HEAD,
        source_tree=_TREE,
        generation0=inventory,
        trial_ledger=TrialLedger(records=()),
    )
    raw = artifact.to_dict()
    raw["final_holdout_sealed"] = False
    raw = _reidentify(raw, evidence._FOUNDATION_IDENTITY_VERSION)
    with pytest.raises(DiscoveryError, match="CAMPAIGN_FOUNDATION_AUTHORITY_INVALID"):
        evidence.verify_campaign_foundation(
            evidence.canonical_json_bytes(raw),
            expected_source_head=_HEAD,
            expected_source_tree=_TREE,
            expected_generation0=inventory,
        )


def test_module_help_is_effect_free_and_has_no_campaign_action() -> None:
    root = Path(__file__).parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "trading_bot.experiments.ai_strategy_discovery_evidence",
            "--help",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "no campaign, replay, provider, AI, or trading action" in result.stdout
    assert "--run" not in result.stdout
