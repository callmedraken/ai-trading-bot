"""Fake-only tests for the additive tiny-live Q62 evaluator."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.live_prototype import tiny_live_readiness_operator as tiny_readiness
from trading_bot.live_prototype.capability_observer import (
    CapabilityReport,
    Classification,
    FactId,
    FactResult,
    OverallStatus,
)
from trading_bot.live_prototype.capability_rule_binding_l41r6 import (
    L41R6CompositeReport,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.live_contract import IntentKind, OwnershipSnapshot
from trading_bot.live_prototype.readiness_contracts import (
    FreshProof,
    ProofKind,
    ProofStatus,
    Q62Blocker,
    Q62Status,
    ReadinessIdentity,
)
from trading_bot.live_prototype.readiness_operator import (
    Q62EvidenceBundle,
    Q62Report,
    evaluate_q62_readiness,
)
from trading_bot.live_prototype.recovery_operator import (
    RecoveryBlocker,
    RecoveryObservation,
    RecoveryStatus,
    reconcile_read_only,
)
from trading_bot.live_prototype.tiny_live_capability_admission import (
    TinyLivePrototypeCapabilityAdmission,
    TinyLivePrototypeCapabilityStatus,
)

_NOW = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)
_EXPIRY = _NOW + timedelta(minutes=10)
_CAPABILITY_DIGEST = "f" * 64
_OBSERVATION_DIGEST = "1" * 64
_L41_BYTES = b"synthetic accepted L41 artifact bytes"
_L41R5_BYTES = b"synthetic accepted L41R5 artifact bytes"


def _identity() -> ReadinessIdentity:
    return ReadinessIdentity(
        source_head="a" * 40,
        source_tree="b" * 40,
        config_digest="c" * 64,
        account_fingerprint="d" * 64,
        target_session="2026-11-10",
    )


def _capability(
    *,
    status: OverallStatus = OverallStatus.BLOCKED,
    account_fingerprint: str | None = None,
    accepted_l41r6_matrix: bool = True,
) -> CapabilityReport:
    classifications = {
        FactId.QUANTITY_INCREMENT: Classification.BLOCKING_L42,
        FactId.MINIMUM_QUANTITY: Classification.BLOCKING_L42,
        FactId.MAXIMUM_QUANTITY_OR_ABSENCE: Classification.BLOCKING_L42,
        FactId.BELOW_MINIMUM_FULL_CLOSE: Classification.BLOCKING_L42,
        FactId.RESIDUAL_FULL_OWNED_CLOSE: Classification.BLOCKING_L42,
        FactId.INSTANCE_REVIEW_REQUIRES_POSITION: (
            Classification.DEFER_TO_FIRST_OWNED_POSITION
        ),
    }
    if status is OverallStatus.READY_FOR_L42:
        classifications = {
            FactId.INSTANCE_REVIEW_REQUIRES_POSITION: (
                Classification.DEFER_TO_FIRST_OWNED_POSITION
            )
        }
    elif not accepted_l41r6_matrix:
        classifications.pop(FactId.QUANTITY_INCREMENT)
    facts = tuple(
        FactResult(
            fact_id=fact_id,
            classification=classifications.get(fact_id, Classification.PROVEN),
            rationale_code=(
                "TEST_FACT_BLOCKED"
                if fact_id in classifications
                and classifications[fact_id] is Classification.BLOCKING_L42
                else "TEST_FACT_PROVEN"
            ),
            evidence_sha256=_OBSERVATION_DIGEST,
        )
        for fact_id in FactId
    )
    return CapabilityReport(
        status=status,
        facts=facts,
        account_fingerprint=(
            _identity().account_fingerprint
            if account_fingerprint is None
            else account_fingerprint
        ),
        account_type="agentic",
    )


def _composite(report: CapabilityReport) -> L41R6CompositeReport:
    return L41R6CompositeReport(
        capability_report=report,
        consumed_l41=None,  # type: ignore[arg-type]
        consumed_l41r5=None,  # type: ignore[arg-type]
        interface_provenance=(),
        official_claim_bindings=(),
    )


def _ownership(identity: ReadinessIdentity, **overrides: object) -> OwnershipSnapshot:
    values: dict[str, object] = {
        "account_fingerprint": identity.account_fingerprint,
        "source_head": identity.source_head,
        "source_tree": identity.source_tree,
        "config_digest": identity.config_digest,
        "target_session": identity.target_session,
        "lifecycle": Lifecycle.DISARMED,
    }
    values.update(overrides)
    return OwnershipSnapshot(**values)  # type: ignore[arg-type]


def _signal_inputs(
    *,
    basis: str = "ALPACA_ALL_ADJUSTED_PRICE_V1",
    as_of: datetime = _NOW,
) -> CompletedSignalInputs:
    sessions = tuple(date(2026, 1, 1) + timedelta(days=index) for index in range(60))
    return CompletedSignalInputs(
        symbol="SPY",
        selected_sessions=sessions,
        sessions=sessions,
        closes=tuple(Decimal("100.00") for _ in sessions),
        price_basis=basis,
        source_digest="e" * 64,
        as_of=as_of,
        cutoff=min(as_of, _NOW),
    )


def _bundle(
    *,
    identity: ReadinessIdentity | None = None,
    capability: CapabilityReport | None = None,
    capability_digest: str = _CAPABILITY_DIGEST,
    ownership: OwnershipSnapshot | None = None,
    signal_inputs: CompletedSignalInputs | None = None,
    recovery_status: RecoveryStatus = RecoveryStatus.CLEAN,
    working_order_count: int = 0,
    unresolved_effect: bool = False,
) -> Q62EvidenceBundle:
    identity = _identity() if identity is None else identity
    capability = _capability() if capability is None else capability
    ownership = _ownership(identity) if ownership is None else ownership
    signal_inputs = _signal_inputs() if signal_inputs is None else signal_inputs
    observation = RecoveryObservation(
        identity=identity,
        evidence_sha256="2" * 64,
        observed_at=_NOW,
        valid_until=_EXPIRY,
        position_quantity=Decimal("0"),
        working_order_count=working_order_count,
        unresolved_effect=unresolved_effect,
    )
    recovery = reconcile_read_only(identity, ownership, observation, as_of=_NOW)
    if recovery_status is RecoveryStatus.BLOCKED:
        recovery = replace(
            recovery,
            status=RecoveryStatus.BLOCKED,
            blockers=(RecoveryBlocker.WORKING_ORDERS_PRESENT,),
        )
    digests = {
        ProofKind.SOURCE: "3" * 64,
        ProofKind.CONFIGURATION: "4" * 64,
        ProofKind.ACCOUNT: "5" * 64,
        ProofKind.CAPABILITY: capability_digest,
        ProofKind.OWNERSHIP: "6" * 64,
        ProofKind.BUDGET: "7" * 64,
        ProofKind.SESSION: "8" * 64,
        ProofKind.SIGNAL_INPUTS: signal_inputs.digest,
        ProofKind.RECOVERY: observation.evidence_sha256,
    }
    proofs = tuple(
        FreshProof(
            kind=kind,
            status=ProofStatus.PROVEN,
            evidence_sha256=digest,
            observed_at=_NOW,
            valid_until=_EXPIRY,
            identity=identity,
        )
        for kind, digest in digests.items()
    )
    return Q62EvidenceBundle(
        identity=identity,
        proofs=proofs,
        capability=capability,
        ownership=ownership,
        signal_inputs=signal_inputs,
        recovery=recovery,
    )


def _fake_admission(
    report: CapabilityReport,
    *,
    account_fingerprint: str | None = None,
    digest: str = _CAPABILITY_DIGEST,
    status: TinyLivePrototypeCapabilityStatus = (
        TinyLivePrototypeCapabilityStatus.ELIGIBLE_FOR_TINY_LIVE_Q62
    ),
) -> TinyLivePrototypeCapabilityAdmission:
    """Build a synthetic typed return without invoking provider/artifact code."""

    admission = object.__new__(TinyLivePrototypeCapabilityAdmission)
    for name, value in (
        ("status", status),
        ("capability_report", report),
        (
            "account_fingerprint",
            _identity().account_fingerprint
            if account_fingerprint is None
            else account_fingerprint,
        ),
        ("admission_digest", digest),
        ("consumed_l41_sha256", "a" * 64),
        ("consumed_l41r5_sha256", "b" * 64),
        ("official_binding_id", "synthetic-binding"),
        ("official_source_digests", (("synthetic-source", "c" * 64),)),
        ("policy_id", "synthetic-policy"),
        ("policy_sha256", "d" * 64),
    ):
        object.__setattr__(admission, name, value)
    return admission


def _install_admission(
    monkeypatch: pytest.MonkeyPatch,
    composite: L41R6CompositeReport,
    *,
    digest: str = _CAPABILITY_DIGEST,
    status: TinyLivePrototypeCapabilityStatus = (
        TinyLivePrototypeCapabilityStatus.ELIGIBLE_FOR_TINY_LIVE_Q62
    ),
    account_fingerprint: str | None = None,
) -> list[tuple[object, bytes, bytes, str]]:
    calls: list[tuple[object, bytes, bytes, str]] = []
    admission = _fake_admission(
        composite.capability_report,
        account_fingerprint=account_fingerprint,
        digest=digest,
        status=status,
    )

    def admit(
        received_composite: object,
        *,
        consumed_l41_bytes: bytes,
        consumed_l41r5_bytes: bytes,
        account_fingerprint: str,
    ) -> TinyLivePrototypeCapabilityAdmission:
        calls.append(
            (
                received_composite,
                consumed_l41_bytes,
                consumed_l41r5_bytes,
                account_fingerprint,
            )
        )
        return admission

    monkeypatch.setattr(tiny_readiness, "admit_tiny_live_capabilities", admit)
    return calls


def _evaluate(
    bundle: Q62EvidenceBundle,
    composite: L41R6CompositeReport,
) -> tiny_readiness.TinyLiveReadinessReport:
    return tiny_readiness.evaluate_q62_tiny_live_readiness(
        bundle,
        as_of=_NOW,
        composite=composite,
        consumed_l41_bytes=_L41_BYTES,
        consumed_l41r5_bytes=_L41R5_BYTES,
    )


def _replace_proof(
    bundle: Q62EvidenceBundle,
    kind: ProofKind,
    transform,
) -> Q62EvidenceBundle:
    matched = tuple(proof for proof in bundle.proofs if proof.kind is kind)
    assert matched
    target = matched[0]
    return replace(
        bundle,
        proofs=tuple(
            transform(proof) if proof is target else proof for proof in bundle.proofs
        ),
    )


def test_capability_only_historical_blocker_yields_prototype_read_only_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _bundle(capability=report)
    calls = _install_admission(monkeypatch, composite)

    historical = evaluate_q62_readiness(bundle, as_of=_NOW)
    result = _evaluate(bundle, composite)

    assert historical.status is Q62Status.BLOCKED
    assert historical.blockers == (Q62Blocker.CAPABILITY_UNPROVEN,)
    assert (
        result.status
        is tiny_readiness.TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY
    )
    assert result.blockers == ()
    assert result.historical_report is not None
    assert result.historical_report.blockers == (Q62Blocker.CAPABILITY_UNPROVEN,)
    assert result.capability_admission_digest == _CAPABILITY_DIGEST
    assert result.provider_mutation_count == 0
    assert result.live_readiness_granted is False
    assert result.trade_authority_granted is False
    assert calls == [
        (composite, _L41_BYTES, _L41R5_BYTES, bundle.identity.account_fingerprint)
    ]


@pytest.mark.parametrize(
    ("status", "blockers"),
    (
        (Q62Status.READY_READ_ONLY, ()),
        (
            Q62Status.BLOCKED,
            (Q62Blocker.CAPABILITY_UNPROVEN, Q62Blocker.PROOF_NOT_FRESH),
        ),
        (Q62Status.BLOCKED, ()),
    ),
)
def test_unexpected_historical_result_fails_closed_with_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    status: Q62Status,
    blockers: tuple[Q62Blocker, ...],
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _bundle(capability=report)
    _install_admission(monkeypatch, composite)
    unexpected = Q62Report(
        status=status,
        blockers=blockers,
        source_head=bundle.identity.source_head,
        source_tree=bundle.identity.source_tree,
        config_digest=bundle.identity.config_digest,
        account_fingerprint=bundle.identity.account_fingerprint,
        target_session=bundle.identity.target_session,
    )
    monkeypatch.setattr(
        tiny_readiness,
        "evaluate_q62_readiness",
        lambda *args, **kwargs: unexpected,
    )

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert result.historical_report is unexpected
    assert Q62Blocker.CAPABILITY_UNPROVEN in result.blockers
    assert all(blocker in result.blockers for blocker in blockers)


def test_historical_ready_on_ready_lookalike_cannot_replace_blocked_composite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composite_report = _capability()
    composite = _composite(composite_report)
    ready_report = _capability(
        status=OverallStatus.READY_FOR_L42,
        accepted_l41r6_matrix=False,
    )
    bundle = _bundle(
        capability=ready_report,
        capability_digest=_OBSERVATION_DIGEST,
    )
    _install_admission(monkeypatch, composite)

    assert (
        evaluate_q62_readiness(bundle, as_of=_NOW).status is Q62Status.READY_READ_ONLY
    )
    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.CAPABILITY_UNPROVEN in result.blockers


def test_composite_account_mismatch_and_bundle_lookalike_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_report = _capability()
    mismatched_report = _capability(account_fingerprint="9" * 64)
    composite = _composite(mismatched_report)
    bundle = _bundle(capability=bundle_report)
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.ACCOUNT_MISMATCH in result.blockers
    assert Q62Blocker.CAPABILITY_UNPROVEN in result.blockers


def test_admission_account_must_match_the_readiness_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _bundle(capability=report)
    _install_admission(monkeypatch, composite, account_fingerprint="9" * 64)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.ACCOUNT_MISMATCH in result.blockers


def test_malformed_composite_fails_closed_even_with_admission_like_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _capability()
    bundle = _bundle(capability=report)
    admission = _fake_admission(report)
    monkeypatch.setattr(
        tiny_readiness,
        "admit_tiny_live_capabilities",
        lambda *args, **kwargs: admission,
    )

    result = tiny_readiness.evaluate_q62_tiny_live_readiness(
        bundle,
        as_of=_NOW,
        composite=None,  # type: ignore[arg-type]
        consumed_l41_bytes=_L41_BYTES,
        consumed_l41r5_bytes=_L41R5_BYTES,
    )

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.CAPABILITY_UNPROVEN in result.blockers


@pytest.mark.parametrize(
    "transform",
    (
        lambda proof: replace(proof, status=ProofStatus.UNKNOWN),
        lambda proof: replace(proof, evidence_sha256="9" * 64),
        lambda proof: replace(
            proof,
            observed_at=_NOW - timedelta(seconds=2),
            valid_until=_NOW - timedelta(seconds=1),
        ),
        lambda proof: replace(
            proof, identity=replace(_identity(), source_tree="f" * 40)
        ),
    ),
)
def test_capability_proof_must_be_proven_fresh_and_identity_bound(
    monkeypatch: pytest.MonkeyPatch,
    transform,
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _replace_proof(_bundle(capability=report), ProofKind.CAPABILITY, transform)
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.CAPABILITY_UNPROVEN in result.blockers


@pytest.mark.parametrize("duplicate", (False, True))
def test_missing_or_duplicate_capability_proof_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    duplicate: bool,
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _bundle(capability=report)
    cap_proof = next(
        proof for proof in bundle.proofs if proof.kind is ProofKind.CAPABILITY
    )
    proofs = tuple(
        proof for proof in bundle.proofs if proof.kind is not ProofKind.CAPABILITY
    )
    if duplicate:
        proofs += (cap_proof, cap_proof)
    bundle = replace(bundle, proofs=proofs)
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.CAPABILITY_UNPROVEN in result.blockers


def test_admission_rejection_is_sanitized_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _bundle(capability=report)

    def reject(*args: object, **kwargs: object) -> None:
        raise ValueError("secret payload must not escape")

    monkeypatch.setattr(tiny_readiness, "admit_tiny_live_capabilities", reject)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert result.admission_error_code == "TINY_LIVE_CAPABILITY_ADMISSION_REJECTED"
    assert "secret payload" not in repr(result)
    assert Q62Blocker.CAPABILITY_UNPROVEN in result.blockers


@pytest.mark.parametrize(
    ("overrides", "expected_blocker"),
    (
        ({"baseline_quantity": Decimal("1")}, Q62Blocker.OWNERSHIP_UNPROVEN),
        (
            {"effect_disposition": EffectDisposition.CONFIRMED},
            Q62Blocker.OWNERSHIP_UNPROVEN,
        ),
        (
            {"pending_requested_dollars": Decimal("1")},
            Q62Blocker.OWNERSHIP_UNPROVEN,
        ),
        (
            {"pending_requested_quantity": Decimal("0.01")},
            Q62Blocker.OWNERSHIP_UNPROVEN,
        ),
        (
            {"cumulative_entry_filled_dollars": Decimal("0.5")},
            Q62Blocker.BUDGET_UNPROVEN,
        ),
        (
            {"entry_local_intent_id": "prior-entry-intent"},
            Q62Blocker.BUDGET_UNPROVEN,
        ),
        ({"exit_local_intent_id": "prior-exit-intent"}, Q62Blocker.BUDGET_UNPROVEN),
    ),
)
def test_historical_snapshot_omissions_still_block_prototype_readiness(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
    expected_blocker: Q62Blocker,
) -> None:
    identity = _identity()
    report = _capability()
    composite = _composite(report)
    snapshot = _ownership(identity, **overrides)
    bundle = _bundle(identity=identity, capability=report, ownership=snapshot)
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert expected_blocker in result.blockers


def test_historical_budget_drift_blocks_prototype_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity()
    report = _capability()
    composite = _composite(report)
    snapshot = _ownership(identity, entry_reserved_dollars=Decimal("1.00"))
    bundle = _bundle(identity=identity, capability=report, ownership=snapshot)
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.BUDGET_UNPROVEN in result.blockers


@pytest.mark.parametrize(
    ("ownership_overrides", "working_order_count", "unresolved_effect"),
    (
        (
            {
                "pending_intent_id": "pending-entry",
                "pending_kind": IntentKind.ENTRY,
                "pending_requested_dollars": Decimal("10"),
            },
            0,
            False,
        ),
        ({"working_remainder": Decimal("0.01")}, 1, False),
        ({"effect_disposition": EffectDisposition.MAY_HAVE_OCCURRED}, 0, True),
    ),
)
def test_pending_working_or_ambiguous_effect_blocks_prototype_readiness(
    monkeypatch: pytest.MonkeyPatch,
    ownership_overrides: dict[str, object],
    working_order_count: int,
    unresolved_effect: bool,
) -> None:
    identity = _identity()
    report = _capability()
    composite = _composite(report)
    snapshot = _ownership(identity, **ownership_overrides)
    bundle = _bundle(
        identity=identity,
        capability=report,
        ownership=snapshot,
        working_order_count=working_order_count,
        unresolved_effect=unresolved_effect,
    )
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert {
        Q62Blocker.OWNERSHIP_UNPROVEN,
        Q62Blocker.RECOVERY_UNPROVEN,
    } & set(result.blockers)


@pytest.mark.parametrize(
    "changed_signal",
    (
        _signal_inputs(basis="ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1"),
        _signal_inputs(as_of=_NOW + timedelta(seconds=1)),
    ),
)
def test_wrong_or_forward_signal_inputs_block_prototype_readiness(
    monkeypatch: pytest.MonkeyPatch,
    changed_signal: CompletedSignalInputs,
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _bundle(capability=report, signal_inputs=changed_signal)
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.SIGNAL_INPUTS_UNPROVEN in result.blockers


def test_stale_signal_proof_and_nonclean_recovery_remain_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _bundle(capability=report, recovery_status=RecoveryStatus.BLOCKED)
    stale_signal = next(
        proof for proof in bundle.proofs if proof.kind is ProofKind.SIGNAL_INPUTS
    )
    stale_signal = replace(
        stale_signal,
        observed_at=_NOW - timedelta(seconds=2),
        valid_until=_NOW - timedelta(seconds=1),
    )
    bundle = replace(
        bundle,
        proofs=tuple(
            stale_signal if proof.kind is ProofKind.SIGNAL_INPUTS else proof
            for proof in bundle.proofs
        ),
    )
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.PROOF_NOT_FRESH in result.blockers
    assert Q62Blocker.RECOVERY_UNPROVEN in result.blockers


def test_source_and_configuration_identity_mismatch_remain_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _capability()
    composite = _composite(report)
    bundle = _bundle(capability=report)
    source_proof = next(
        proof for proof in bundle.proofs if proof.kind is ProofKind.SOURCE
    )
    configuration_proof = next(
        proof for proof in bundle.proofs if proof.kind is ProofKind.CONFIGURATION
    )
    changed = replace(
        bundle,
        proofs=tuple(
            replace(proof, identity=replace(bundle.identity, source_tree="f" * 40))
            if proof in {source_proof, configuration_proof}
            else proof
            for proof in bundle.proofs
        ),
    )
    _install_admission(monkeypatch, composite)

    result = _evaluate(changed, composite)

    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.PROOF_IDENTITY_MISMATCH in result.blockers


def test_typed_label_alias_in_original_report_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    composite_report = _capability()
    composite = _composite(composite_report)
    lookalike = _capability()
    object.__setattr__(lookalike, "status", str(lookalike.status))
    bundle = _bundle(capability=lookalike)
    _install_admission(monkeypatch, composite)

    result = _evaluate(bundle, composite)

    assert lookalike.status == composite_report.status
    assert type(lookalike.status) is str
    assert result.status is tiny_readiness.TinyLiveReadinessStatus.BLOCKED
    assert Q62Blocker.CAPABILITY_UNPROVEN in result.blockers


def test_new_evaluator_has_no_provider_or_final_holdout_imports() -> None:
    source_path = Path(tiny_readiness.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
            imported.extend(alias.name for alias in node.names)
    assert not any(
        module.startswith(("trading_bot.robinhood_mcp", "mcp"))
        or module
        in {
            "httpx",
            "requests",
            "socket",
            "webbrowser",
            "subprocess",
            "FINAL_HOLDOUT",
        }
        for module in imported
    )
    assert "FINAL_HOLDOUT" not in source_path.read_text(encoding="utf-8")
