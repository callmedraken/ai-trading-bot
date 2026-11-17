from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from trading_bot.live_prototype.durable_state import RuntimeIdentity
from trading_bot.live_prototype.l43_production_owner import (
    L43ProductionOwner,
    Q62JournalOrigin,
)
from trading_bot.robinhood_mcp import order_scope_evidence_admission as admission

_ACCOUNT_NUMBER = "rhc3-test-account"
_ACCOUNT_FINGERPRINT = hashlib.sha256(_ACCOUNT_NUMBER.encode("utf-8")).hexdigest()


def _origin(account_fingerprint: str = _ACCOUNT_FINGERPRINT) -> Q62JournalOrigin:
    return Q62JournalOrigin(
        runtime_identity=RuntimeIdentity(
            account_fingerprint=account_fingerprint,
            source_head="1" * 40,
            source_tree="2" * 40,
            config_digest="3" * 64,
            binding_digest="4" * 64,
            lifecycle_id="00000000-0000-0000-0000-000000000147",
        ),
        journal_label="arch147-q62-test-origin",
        journal_sha256="5" * 64,
        initialization_event_sha256="6" * 64,
        consumed_observation_sha256="7" * 64,
    )


def _a2() -> dict[str, object]:
    source_head = "a" * 40
    source_tree = "b" * 40
    return {
        "agent_initiated_schema_sha256": "1" * 64,
        "attempt_counters": {
            "account_reads": 0,
            "browser_launches": 0,
            "cancellation_calls": 0,
            "mcp_session_open_attempts": 1,
            "mcp_tool_invocation_attempts": 0,
            "oauth_scope_entry_attempts": 1,
            "order_reads": 0,
            "other_tool_calls": 0,
            "placement_calls": 0,
            "position_reads": 0,
            "review_calls": 0,
            "tools_list_attempts": 1,
            "tools_list_pages_received": 1,
        },
        "classification": "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW",
        "classifier_output_authenticated": False,
        "contract_version": "AGENT_INITIATED_RUNTIME_PARTITION_PROOF_ELIGIBLE/v1",
        "description_sha256": "2" * 64,
        "exhaustive_pagination": True,
        "input_schema_sha256": "3" * 64,
        "metadata_source_authenticated": True,
        "metadata_validation_boundary": (
            "SDK_PARSED_MODELS; VISIBLE_ALIAS_AND_TOOL_NAME_DUPLICATES_REJECTED; "
            "RAW_JSON_DUPLICATE_KEYS_UNOBSERVABLE"
        ),
        "observation": admission._A2_OBSERVATION,
        "output_schema_sha256": "4" * 64,
        "partition_equality_proof": "NOT_PROVEN",
        "production_order_scope_authority": "NOT_GRANTED",
        "qualifier_evidence_sha256": "5" * 64,
        "reason": "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW_ONLY",
        "remote_develop": {"head": source_head, "tree": source_tree},
        "remote_feature": {"head": source_head, "tree": source_tree},
        "runtime_proof_eligibility": "ELIGIBLE",
        "schema": admission._A2_SCHEMA,
        "source_authority": {
            "feature": "PASS",
            "prospective_develop": "PASS",
            "status": "PASS",
        },
        "source_head": source_head,
        "source_tree": source_tree,
        "status": "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW",
        "tools_list_pages": 1,
    }


def _observer() -> dict[str, object]:
    reads = [
        {
            "agent_initiated": filter_value,
            "exhaustive": True,
            "label": label,
            "page_count": 1,
            "query_sha256": _b2_query_sha256(_ACCOUNT_FINGERPRINT, filter_value),
            "row_count": 0,
        }
        for label, filter_value in admission._EXPECTED_READS
    ]
    proof_digests = {
        "canonical_order_material_digest": "8" * 64,
        "false_partition_digest": "9" * 64,
        "stable_all_universe_digest": "a" * 64,
        "true_partition_digest": "b" * 64,
    }
    observer = {
        "account_fingerprint": _ACCOUNT_FINGERPRINT,
        "attempt_counters": {
            "account_read_attempts": 1,
            "browser_launch_attempts": 0,
            "cancellation_attempts": 0,
            "mcp_session_open_attempts": 1,
            "mcp_tool_invocation_attempts": 5,
            "oauth_scope_entry_attempts": 1,
            "order_read_attempts": 4,
            "other_tool_attempts": 0,
            "placement_attempts": 0,
            "review_attempts": 0,
            "tools_list_attempts": 1,
            "tools_list_pages_received": 1,
        },
        "b2_evidence_sha256": "0" * 64,
        "b2_proof_contract_version": admission._RHC2_CONTRACT,
        "b2_result": {
            "account_fingerprint": _ACCOUNT_FINGERPRINT,
            **proof_digests,
            "contract_version": admission._RHC2_CONTRACT,
            "evidence_sha256": "0" * 64,
            "false_partition_digest": proof_digests["false_partition_digest"],
            "logical_reads": reads,
            "partition_equality_proof": "PROVEN",
            "reason": "PARTITION_EQUALITY_PROVEN",
            "status": "PROVEN",
        },
        "b2_result_reason": "PARTITION_EQUALITY_PROVEN",
        "b2_result_status": "PROVEN",
        **proof_digests,
        "logical_reads": reads,
        "observation": "ARCH147_L43_AGENT_INITIATED_RUNTIME_PARTITION_OBSERVER",
        "partition_equality_proof": "PROVEN",
        "production_order_scope_authority": "NOT_GRANTED",
        "reason": "PARTITION_EQUALITY_PROVEN",
        "schema": admission._RHC2_SCHEMA,
        "source_authority": {
            "feature": "PASS",
            "prospective_develop": "PASS",
            "status": "PASS",
        },
        "source_branch": admission._RHC2_BRANCH,
        "source_head": admission._RHC2_SOURCE_HEAD,
        "source_recheck_status": "PASS",
        "source_tree": admission._RHC2_SOURCE_TREE,
        "status": "PROVEN",
    }
    b2_sha256 = _inner_b2_sha256(observer)
    observer["b2_evidence_sha256"] = b2_sha256
    observer["b2_result"]["evidence_sha256"] = b2_sha256
    return observer


def _b2_query_sha256(account_fingerprint: str, filter_value: bool | None) -> str:
    material = (
        "ARCH147_L43_B2_ORDER_QUERY_V1",
        account_fingerprint,
        "SPY",
        filter_value,
    )
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _inner_b2_sha256(observer: dict[str, object]) -> str:
    b2 = observer["b2_result"]
    payload = {
        "contract_version": b2["contract_version"],
        "status": b2["status"],
        "reason": b2["reason"],
        "source_head": observer["source_head"],
        "source_tree": observer["source_tree"],
        "account_fingerprint": b2["account_fingerprint"],
        "symbol": "SPY",
        "logical_reads": b2["logical_reads"],
        "stable_all_universe_digest": b2["stable_all_universe_digest"],
        "true_partition_digest": b2["true_partition_digest"],
        "false_partition_digest": b2["false_partition_digest"],
        "canonical_order_material_digest": b2["canonical_order_material_digest"],
        "partition_equality_proof": b2["partition_equality_proof"],
        "production_order_scope_authority": "NOT_GRANTED",
    }
    return hashlib.sha256(_encode(payload)).hexdigest()


def _report(observer_sha256: str) -> dict[str, object]:
    source_phase = {
        "branch": admission._RHC2_BRANCH,
        "head": admission._RHC2_SOURCE_HEAD,
        "porcelain": "",
        "tree": admission._RHC2_SOURCE_TREE,
    }
    return {
        "checkpoint": admission._RHC2_CHECKPOINT,
        "description": (
            "RHC2 review-only B2 successor observation; explicit read-only "
            "preflight only"
        ),
        "kind": "read_only_preflight",
        "production_effects": "NOT_RUN",
        "protected_execution": "NOT_AUTHORIZED",
        "result": {
            "attempt_counters": {
                "account_read_attempts": 1,
                "browser_launch_attempts": 0,
                "cancellation_attempts": 0,
                "mcp_session_open_attempts": 1,
                "mcp_tool_invocation_attempts": 5,
                "oauth_scope_entry_attempts": 1,
                "order_read_attempts": 4,
                "other_tool_attempts": 0,
                "placement_attempts": 0,
                "review_attempts": 0,
                "tools_list_attempts": 1,
                "tools_list_pages_received": 1,
            },
            "disposition": "REVIEW_ONLY",
            "observer_evidence_path": admission._RHC2_OBSERVER_PATH,
            "observer_evidence_sha256": observer_sha256,
            "observer_status": "PROVEN",
            "production_order_scope_authority": "NOT_GRANTED",
            "provider_dispatch_started": True,
            "reason": "PARTITION_EQUALITY_PROVEN",
            "source_head": admission._RHC2_SOURCE_HEAD,
            "source_recheck_status": "PASS",
            "source_tree": admission._RHC2_SOURCE_TREE,
            "status": "PASS",
        },
        "schema": admission._RHC2_REPORT_SCHEMA,
        "source": {
            "after": source_phase,
            "before": dict(source_phase),
            "identity_stable": True,
            "remote_branch": admission._RHC2_BRANCH,
            "remote_head": admission._RHC2_SOURCE_HEAD,
            "remote_head_source": "LIVE_REMOTE_LOOKUP",
        },
        "status": "PASS",
    }


def _encode(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _install_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    edit_a2: Callable[[dict[str, object]], None] | None = None,
    edit_report: Callable[[dict[str, object]], None] | None = None,
    edit_observer: Callable[[dict[str, object]], None] | None = None,
    a2_bytes: bytes | None = None,
    report_bytes: bytes | None = None,
    observer_bytes: bytes | None = None,
    wrong_pin_index: int | None = None,
) -> tuple[tuple[admission._PinnedEvidenceFile, ...], dict[str, Path]]:
    monkeypatch.setattr(admission, "_RHC2_ACCOUNT_FINGERPRINT", _ACCOUNT_FINGERPRINT)
    a2_doc = _a2()
    observer_doc = _observer()
    monkeypatch.setattr(
        admission,
        "_RHC2_INNER_B2_SHA256",
        observer_doc["b2_evidence_sha256"],
    )
    if edit_a2 is not None:
        edit_a2(a2_doc)
    if edit_observer is not None:
        edit_observer(observer_doc)
    observer_bytes = _encode(observer_doc) if observer_bytes is None else observer_bytes
    report_doc = _report(hashlib.sha256(observer_bytes).hexdigest())
    if edit_report is not None:
        report_doc = _report(hashlib.sha256(observer_bytes).hexdigest())
        edit_report(report_doc)
    a2_bytes = _encode(a2_doc) if a2_bytes is None else a2_bytes
    report_bytes = _encode(report_doc) if report_bytes is None else report_bytes
    paths = {
        "a2": tmp_path / "a2.json",
        "report": tmp_path / "report.json",
        "observer": tmp_path / "observer.json",
    }
    contents = {"a2": a2_bytes, "report": report_bytes, "observer": observer_bytes}
    for name, path in paths.items():
        path.write_bytes(contents[name])
    pins = [
        admission._PinnedEvidenceFile(path, hashlib.sha256(contents[name]).hexdigest())
        for name, path in paths.items()
    ]
    if wrong_pin_index is not None:
        pin = pins[wrong_pin_index]
        pins[wrong_pin_index] = admission._PinnedEvidenceFile(pin.path, "0" * 64)
    pinned = tuple(pins)
    monkeypatch.setattr(admission, "_PINNED_EVIDENCE", pinned)
    return pinned, paths


def _accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _install_chain(tmp_path, monkeypatch)
    return admission.load_order_scope_evidence_authority(_origin())


class _AuthorityVerifier:
    def verify(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("source authority is deferred")


class _JournalReader:
    def replay(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("journal replay is deferred")


def _production_verifier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from trading_bot.robinhood_mcp import l43_production_composition as composition

    origin = _origin()
    owner = L43ProductionOwner(
        authority_verifier=_AuthorityVerifier(), journal_reader=_JournalReader()
    )
    monkeypatch.setattr(composition, "read_canonical_q62_origin", lambda: origin)
    monkeypatch.setattr(
        composition.L43ProductionOwner,
        "for_production",
        classmethod(lambda cls, *, repo_root: owner),
    )
    built = composition.L43ProductionPreEffectComposition.for_production(
        repo_root=tmp_path,
    )
    return built.dependencies.order_scope_verifier


def _query_sha256() -> str:
    from trading_bot.live_prototype.l43_pre_effect_observation import (
        _account_wide_spy_order_query_digest,
    )

    return _account_wide_spy_order_query_digest(
        _ACCOUNT_FINGERPRINT,
        {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
    )


def test_fixed_a2_and_rhc2_evidence_chain_authenticates_with_q62_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    authority = _accepted(tmp_path, monkeypatch)

    assert type(authority) is admission.OrderScopeEvidenceAuthority
    assert authority.account_fingerprint == _ACCOUNT_FINGERPRINT
    assert authority.a2_evidence_sha256 == admission._PINNED_EVIDENCE[0].sha256
    assert authority.rhc2_report_sha256 == admission._PINNED_EVIDENCE[1].sha256
    assert (
        authority.rhc2_observer_evidence_sha256 == admission._PINNED_EVIDENCE[2].sha256
    )
    assert authority.inner_b2_evidence_sha256 == admission._RHC2_INNER_B2_SHA256


@pytest.mark.parametrize("row_count", [0, 13])
def test_production_verifier_admits_authenticated_current_spy_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    row_count: int,
):
    pins, _ = _install_chain(tmp_path, monkeypatch)
    verifier = _production_verifier(monkeypatch, tmp_path)

    proof = verifier.verify_account_wide_spy_orders(
        account_fingerprint=_ACCOUNT_FINGERPRINT,
        query_sha256=_query_sha256(),
        order_arguments={"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
        pages_read=2,
        row_count=row_count,
        exhausted=True,
    )

    assert proof is not None
    assert proof.scope.value == "ACCOUNT_WIDE_ALL_AGENTS"
    assert proof.query_sha256 == _query_sha256()
    assert proof.pages_read == 2
    assert proof.row_count == row_count
    assert proof.exhausted is True
    expected_material = (
        "ARCH147_RHC3_PRODUCTION_ORDER_SCOPE_EVIDENCE_V1",
        pins[0].sha256,
        pins[1].sha256,
        pins[2].sha256,
        admission._RHC2_INNER_B2_SHA256,
        _ACCOUNT_FINGERPRINT,
        _query_sha256(),
        2,
        row_count,
        True,
    )
    expected_sha256 = hashlib.sha256(
        json.dumps(
            expected_material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    assert proof.evidence_sha256 == expected_sha256


@pytest.mark.parametrize(
    ("account_fingerprint", "query_sha256", "arguments", "pages", "rows", "exhausted"),
    [
        (
            _ACCOUNT_FINGERPRINT,
            "0" * 64,
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            1,
            0,
            True,
        ),
        (
            _ACCOUNT_FINGERPRINT,
            _query_sha256(),
            {"account_number": "other-account", "symbol": "SPY"},
            1,
            0,
            True,
        ),
        (
            _ACCOUNT_FINGERPRINT,
            _query_sha256(),
            {"account_number": _ACCOUNT_NUMBER, "symbol": "QQQ"},
            1,
            0,
            True,
        ),
        (
            _ACCOUNT_FINGERPRINT,
            _query_sha256(),
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY", "cursor": "x"},
            1,
            0,
            True,
        ),
        (
            _ACCOUNT_FINGERPRINT,
            _query_sha256(),
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            0,
            0,
            True,
        ),
        (
            _ACCOUNT_FINGERPRINT,
            _query_sha256(),
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            True,
            0,
            True,
        ),
        (
            _ACCOUNT_FINGERPRINT,
            _query_sha256(),
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            1,
            -1,
            True,
        ),
        (
            _ACCOUNT_FINGERPRINT,
            _query_sha256(),
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            1,
            True,
            True,
        ),
        (
            _ACCOUNT_FINGERPRINT,
            _query_sha256(),
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            1,
            0,
            False,
        ),
        (
            "not-a-fingerprint",
            _query_sha256(),
            {"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            1,
            0,
            True,
        ),
    ],
)
def test_current_query_or_counts_cannot_be_asserted_by_caller(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    account_fingerprint: str,
    query_sha256: str,
    arguments: dict[str, object],
    pages: int,
    rows: int,
    exhausted: bool,
):
    _install_chain(tmp_path, monkeypatch)
    verifier = _production_verifier(monkeypatch, tmp_path)

    assert (
        verifier.verify_account_wide_spy_orders(
            account_fingerprint=account_fingerprint,
            query_sha256=query_sha256,
            order_arguments=arguments,
            pages_read=pages,
            row_count=rows,
            exhausted=exhausted,
        )
        is None
    )


def test_evidence_tampering_after_composition_construction_stays_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _, paths = _install_chain(tmp_path, monkeypatch)
    verifier = _production_verifier(monkeypatch, tmp_path)
    paths["observer"].write_bytes(paths["observer"].read_bytes() + b" ")

    assert (
        verifier.verify_account_wide_spy_orders(
            account_fingerprint=_ACCOUNT_FINGERPRINT,
            query_sha256=_query_sha256(),
            order_arguments={"account_number": _ACCOUNT_NUMBER, "symbol": "SPY"},
            pages_read=1,
            row_count=0,
            exhausted=True,
        )
        is None
    )


@pytest.mark.parametrize("missing_index", [0, 1, 2])
def test_missing_fixed_evidence_file_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_index: int
):
    pins, _ = _install_chain(tmp_path, monkeypatch)
    missing = tmp_path / f"missing-{missing_index}.json"
    monkeypatch.setattr(
        admission,
        "_PINNED_EVIDENCE",
        tuple(
            admission._PinnedEvidenceFile(missing, pin.sha256)
            if index == missing_index
            else pin
            for index, pin in enumerate(pins)
        ),
    )

    assert admission.load_order_scope_evidence_authority(_origin()) is None


@pytest.mark.parametrize("wrong_pin_index", [0, 1, 2])
def test_wrong_fixed_evidence_hash_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong_pin_index: int
):
    _install_chain(tmp_path, monkeypatch, wrong_pin_index=wrong_pin_index)

    assert admission.load_order_scope_evidence_authority(_origin()) is None


@pytest.mark.parametrize(
    "edit_a2",
    [
        lambda doc: doc.update(schema="arch147-order-scope-schema-observation/v1"),
        lambda doc: doc.update(reason="UNPROVEN_PROVIDER_SEMANTICS"),
        lambda doc: doc.update(runtime_proof_eligibility="NOT_ELIGIBLE"),
        lambda doc: doc.update(metadata_source_authenticated=False),
        lambda doc: doc.update(exhaustive_pagination=False),
        lambda doc: doc.update(partition_equality_proof="PROVEN"),
    ],
    ids=(
        "old-schema-artifact",
        "wrong-reason",
        "not-eligible",
        "unauthenticated",
        "not-exhaustive",
        "claims-equality",
    ),
)
def test_a2_wrong_or_old_semantics_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    edit_a2: Callable[[dict[str, object]], None],
):
    _install_chain(tmp_path, monkeypatch, edit_a2=edit_a2)

    assert admission.load_order_scope_evidence_authority(_origin()) is None


@pytest.mark.parametrize(
    ("edit_report", "edit_observer"),
    [
        (lambda doc: doc.update(status="FAIL"), None),
        (None, lambda doc: doc.update(status="BLOCKED")),
        (
            lambda doc: doc.update(
                checkpoint="arch147-b2o-runtime-partition-observation"
            ),
            None,
        ),
        (lambda doc: doc["source"].update(identity_stable=False), None),
        (
            lambda doc: doc["result"].update(
                observer_evidence_path="F:\\other\\evidence.json"
            ),
            None,
        ),
        (lambda doc: doc["result"].update(observer_evidence_sha256="0" * 64), None),
        (None, lambda doc: doc.update(b2_proof_contract_version="ARCH147_L43_B2/v1")),
        (None, lambda doc: doc.update(source_recheck_status="FAIL")),
        (None, lambda doc: doc.update(source_tree="0" * 40)),
        (None, lambda doc: doc.update(production_order_scope_authority="GRANTED")),
    ],
    ids=(
        "report-not-pass",
        "observer-not-proven",
        "wrong-checkpoint",
        "identity-unstable",
        "wrong-evidence-path",
        "wrong-evidence-hash",
        "b2-contract-mismatch",
        "source-recheck-mismatch",
        "source-tree-mismatch",
        "production-authority-claim",
    ),
)
def test_rhc2_report_and_observer_identity_mismatches_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    edit_report: Callable[[dict[str, object]], None] | None,
    edit_observer: Callable[[dict[str, object]], None] | None,
):
    _install_chain(
        tmp_path,
        monkeypatch,
        edit_report=edit_report,
        edit_observer=edit_observer,
    )

    assert admission.load_order_scope_evidence_authority(_origin()) is None


@pytest.mark.parametrize(
    "edit_observer",
    [
        lambda doc: doc.update(account_fingerprint="0" * 64),
        lambda doc: doc["logical_reads"][0].update(label="TRUE"),
        lambda doc: doc["logical_reads"][1].update(agent_initiated=None),
        lambda doc: doc["logical_reads"][2].update(agent_initiated=True),
        lambda doc: doc["logical_reads"][3].update(label="ALL_BEFORE"),
        lambda doc: doc["logical_reads"][1].update(exhaustive=False),
        lambda doc: doc["logical_reads"][3].update(query_sha256="d" * 64),
        lambda doc: doc.update(status="FAILED"),
        lambda doc: doc.update(reason="OTHER_REASON"),
        lambda doc: doc.update(partition_equality_proof="NOT_PROVEN"),
        lambda doc: doc["b2_result"].update(true_partition_digest="0" * 64),
    ],
    ids=(
        "wrong-account",
        "wrong-first-label",
        "wrong-true-filter",
        "wrong-false-filter",
        "wrong-last-label",
        "non-exhaustive-read",
        "all-read-disagreement",
        "wrong-proof-status",
        "wrong-proof-reason",
        "wrong-equality-status",
        "nested-b2-digest-disagreement",
    ),
)
def test_rhc2_partition_semantic_mismatches_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    edit_observer: Callable[[dict[str, object]], None],
):
    _install_chain(tmp_path, monkeypatch, edit_observer=edit_observer)

    assert admission.load_order_scope_evidence_authority(_origin()) is None


@pytest.mark.parametrize(
    ("target", "counter"),
    [
        ("report", "review_attempts"),
        ("report", "placement_attempts"),
        ("report", "cancellation_attempts"),
        ("report", "other_tool_attempts"),
        ("observer", "review_attempts"),
        ("observer", "placement_attempts"),
        ("observer", "cancellation_attempts"),
        ("observer", "other_tool_attempts"),
    ],
)
def test_any_rhc2_write_or_other_tool_attempt_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    counter: str,
):
    def edit(document: dict[str, object]) -> None:
        document["result"]["attempt_counters"][counter] = 1

    def edit_observer(document: dict[str, object]) -> None:
        document["attempt_counters"][counter] = 1

    _install_chain(
        tmp_path,
        monkeypatch,
        edit_report=edit if target == "report" else None,
        edit_observer=edit_observer if target == "observer" else None,
    )

    assert admission.load_order_scope_evidence_authority(_origin()) is None


def test_q62_account_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _install_chain(tmp_path, monkeypatch)

    assert admission.load_order_scope_evidence_authority(_origin("e" * 64)) is None


@pytest.mark.parametrize("extra_field", ["unexpected", "metadata"])
def test_unexpected_structure_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra_field: str
):
    _install_chain(
        tmp_path,
        monkeypatch,
        edit_observer=lambda doc: doc.update({extra_field: "value"}),
    )

    assert admission.load_order_scope_evidence_authority(_origin()) is None


def test_duplicate_json_key_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, paths = _install_chain(tmp_path, monkeypatch)
    observer = json.loads(paths["observer"].read_text(encoding="utf-8"))
    raw = _encode(observer).decode("utf-8")
    raw = raw[:-1] + ',"status":"PROVEN"}'
    paths["observer"].write_text(raw, encoding="utf-8")
    current = admission._PINNED_EVIDENCE
    monkeypatch.setattr(
        admission,
        "_PINNED_EVIDENCE",
        tuple(
            admission._PinnedEvidenceFile(
                pin.path,
                hashlib.sha256(raw.encode("utf-8")).hexdigest()
                if index == 2
                else pin.sha256,
            )
            for index, pin in enumerate(current)
        ),
    )

    assert admission.load_order_scope_evidence_authority(_origin()) is None


def test_malformed_json_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _, paths = _install_chain(tmp_path, monkeypatch)
    raw = b'{"status":'
    paths["a2"].write_bytes(raw)
    current = admission._PINNED_EVIDENCE
    monkeypatch.setattr(
        admission,
        "_PINNED_EVIDENCE",
        (
            admission._PinnedEvidenceFile(paths["a2"], hashlib.sha256(raw).hexdigest()),
            current[1],
            current[2],
        ),
    )

    assert admission.load_order_scope_evidence_authority(_origin()) is None


def test_non_file_reparse_target_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source.json"
    source.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this host")
    pin = admission._PinnedEvidenceFile(
        link, hashlib.sha256(source.read_bytes()).hexdigest()
    )

    with pytest.raises(ValueError):
        admission._read_pinned_file(pin)
