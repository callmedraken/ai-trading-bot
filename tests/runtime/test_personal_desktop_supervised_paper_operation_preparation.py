"""PD2B3 supervised source-only paper-operation preparation coverage."""

from __future__ import annotations

import ast
import inspect
import weakref
from copy import copy, deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from tests.market_data.daily_snapshot_test_support import CAPTURED_AT, SPY, calendar
from tests.runtime.test_checkpointed_paper_cycle_successor import _edge_artifacts
from tests.runtime.test_checkpointed_verified_snapshot_execution import _target
from tests.runtime.test_manual_paper_strategy_plan import (
    _DEFAULT_CONFIG,
    _NEXT_SESSION,
    _binding,
    _prior,
    _snapshot,
    _verified_seed,
)
from tests.runtime.test_paper_account_lineage_verification import _artifact
from tests.runtime.test_verified_snapshot_preparation import _policies
from tests.runtime.test_windows_authority_capability import _production_validation

from trading_bot.market_data import serialize_daily_snapshot
from trading_bot.portfolio import MetadataEntry
from trading_bot.runtime import (
    CallerAssertedNextSessionOpenReference,
    PaperAccountGenesisRequest,
    PaperAccountLineageArtifact,
    PaperAccountLineageArtifactKind,
    PaperAccountLineageVerificationStatus,
    PaperOperationExecutionInputsError,
    SelectedC3SnapshotAuditEvidence,
    SelectedC3SnapshotPermit,
    SelectedC3SnapshotReadError,
    SelectedC3SnapshotReadResult,
    create_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
    verified_prior_from_full_lineage,
    verified_prior_from_genesis,
    verify_genesis_paper_account_checkpoint,
    verify_paper_account_lineage,
)
from trading_bot.runtime import manual_paper_selected_c3_snapshot as p2
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_preparation as preparation,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexAcquisition,
    PaperAccountMutexState,
    paper_account_mutex_digest,
    paper_account_mutex_name,
)
from trading_bot.runtime.personal_desktop_paper_account_publication_freeze import (
    PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountReadEvidence,
)
from trading_bot.runtime.personal_desktop_paper_account_security import (
    PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
    PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
)
from trading_bot.runtime.windows_authority import WindowsAuthorityError

ACCOUNT_ID = "9415cd7b-bf36-5fba-bd58-a0f99119dc21"
OPERATION_ROOT = r"X:\disposable-paper-v2\runtime"
CALLER_KEY = UUID("cff0bcea-e6d9-548a-8371-a45fb95ce3b4")
SELECTION_ID = UUID("10000000-0000-0000-0000-000000000001")
SESSION_ID = UUID("20000000-0000-0000-0000-000000000002")
ATTEMPT_ID = UUID("25000000-0000-0000-0000-000000000002")
TERMINAL_ID = UUID("30000000-0000-0000-0000-000000000003")
CANONICAL_P2_PATH = r"F:\AITradingBot\capture\selected.json"


def _post_lock_evidence():  # type: ignore[no-untyped-def]
    checkpoint = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            datetime(2025, 1, 1, tzinfo=UTC),
            Decimal("100"),
            (),
            Decimal("0"),
        )
    )
    payload = serialize_paper_account_checkpoint(checkpoint)
    verification = verify_genesis_paper_account_checkpoint(payload)
    prior = verified_prior_from_genesis(verification)
    genesis = PaperAccountLineageArtifact(
        PaperAccountLineageArtifactKind.GENESIS_CHECKPOINT,
        checkpoint.checkpoint_id,
        payload,
        prior.checkpoint_sha256,
        prior.checkpoint_byte_length,
    )
    lineage = verify_paper_account_lineage(
        genesis,
        checkpoint.checkpoint_id,
        (),
        (),
        (),
        calendar(),
    )
    assert lineage.status is PaperAccountLineageVerificationStatus.PASS
    assert lineage.evidence is not None
    return SimpleNamespace(
        anchor=SimpleNamespace(paper_account_id=ACCOUNT_ID),
        prior_checkpoint=prior,
        lineage=lineage.evidence,
        genesis=genesis,
        successors=(),
        reports=(),
        snapshots=(),
    )


def _account_with_one_installed_successor() -> PersonalDesktopPaperAccountReadEvidence:
    genesis_account = _post_lock_evidence()
    genesis_verification = verify_genesis_paper_account_checkpoint(
        genesis_account.genesis.payload
    )
    _, report, report_payload, _, snapshot_payload, successor, successor_payload = (
        _edge_artifacts(
            checkpoint=(genesis_verification, genesis_account.genesis.payload),
            target=_target("0", "0", "100"),
        )
    )
    successor_artifact = _artifact(
        PaperAccountLineageArtifactKind.SUCCESSOR_CHECKPOINT,
        successor.checkpoint_id,
        successor_payload,
    )
    report_artifact = _artifact(
        PaperAccountLineageArtifactKind.CYCLE_REPORT,
        report.report_id,
        report_payload,
    )
    snapshot_artifact = _artifact(
        PaperAccountLineageArtifactKind.DAILY_SNAPSHOT,
        successor.snapshot_reference.snapshot_id,
        snapshot_payload,
    )
    full = verify_paper_account_lineage(
        genesis_account.genesis,
        successor.checkpoint_id,
        (successor_artifact,),
        (report_artifact,),
        (snapshot_artifact,),
        calendar(),
    )
    assert full.status is PaperAccountLineageVerificationStatus.PASS
    assert full.evidence is not None
    return PersonalDesktopPaperAccountReadEvidence(
        genesis_account.anchor,
        b"",
        verified_prior_from_full_lineage(full),
        full.evidence,
        genesis_account.genesis,
        (successor_artifact,),
        (report_artifact,),
        (snapshot_artifact,),
        (),
    )


def test_historical_predecessor_prefix_uses_p_when_current_tip_is_q() -> None:
    account = _account_with_one_installed_successor()
    prefix = verify_paper_account_lineage(
        account.genesis,
        account.genesis.artifact_id,
        (),
        (),
        (),
        calendar(),
    )
    assert prefix.status is PaperAccountLineageVerificationStatus.PASS
    assert prefix.evidence is not None
    prior_p = verified_prior_from_full_lineage(prefix)
    plan = _binding(
        prior=prior_p,
        paper_account_id=ACCOUNT_ID,
        caller_key=str(CALLER_KEY),
    )

    material = preparation.reconstruct_verified_paper_operation_from_predecessor_prefix(
        account, _selected_result(), plan, calendar()
    )

    assert account.lineage.terminal_checkpoint_id == account.successors[0].artifact_id
    assert account.lineage.terminal_checkpoint_id != prior_p.checkpoint_id
    assert material.execution_inputs.verified_prior == prior_p
    assert material.execution_inputs.intent.prior_lineage_evidence == prefix.evidence
    assert (
        material.execution_inputs.intent.prior_lineage_evidence.terminal_checkpoint_id
        == prior_p.checkpoint_id
    )
    assert material.execution_inputs.application_id != account.successors[0].artifact_id


def test_historical_predecessor_prefix_blocks_absent_or_ambiguous_p() -> None:
    account = _account_with_one_installed_successor()
    selected = _selected_result()
    plan = _binding(
        prior=_prior(cash="200"),
        paper_account_id=ACCOUNT_ID,
        caller_key=str(CALLER_KEY),
    )
    with pytest.raises(preparation.SupervisedPaperOperationPreparationError):
        preparation.reconstruct_verified_paper_operation_from_predecessor_prefix(
            account, selected, plan, calendar()
        )
    malformed = replace(account, successors=(account.successors[0],) * 2)
    with pytest.raises(preparation.SupervisedPaperOperationPreparationError):
        preparation.reconstruct_verified_paper_operation_from_predecessor_prefix(
            malformed, selected, plan, calendar()
        )
    valid_plan = _binding(
        prior=_post_lock_evidence().prior_checkpoint,
        paper_account_id=ACCOUNT_ID,
        caller_key=str(CALLER_KEY),
    )
    unrelated = replace(account, snapshots=(*account.snapshots, account.snapshots[0]))
    with pytest.raises(preparation.SupervisedPaperOperationPreparationError):
        preparation.reconstruct_verified_paper_operation_from_predecessor_prefix(
            unrelated, selected, valid_plan, calendar()
        )


def _selected_result(
    permit: SelectedC3SnapshotPermit | None = None,
) -> SelectedC3SnapshotReadResult:
    verification = _snapshot()
    assert verification.snapshot is not None
    payload = serialize_daily_snapshot(verification.snapshot)
    audit = SelectedC3SnapshotAuditEvidence(
        SELECTION_ID,
        SESSION_ID,
        ATTEMPT_ID,
        TERMINAL_ID,
        verification.snapshot.snapshot_id,
        verification.sha256,
        verification.byte_length,
        "1" * 64,
        "SUCCEEDED",
        "CONFIRMED",
        CANONICAL_P2_PATH,
    )
    return SelectedC3SnapshotReadResult(
        audit,
        permit or object.__new__(SelectedC3SnapshotPermit),
        payload,
        verification,
    )


def _acquisition(
    state: PaperAccountMutexState = PaperAccountMutexState.OWNED,
) -> PaperAccountMutexAcquisition:
    return PaperAccountMutexAcquisition(
        ACCOUNT_ID,
        paper_account_mutex_name(ACCOUNT_ID),
        paper_account_mutex_digest(ACCOUNT_ID),
        state,
    )


class FakeSupervisedCycle:
    def __init__(
        self,
        events: list[object],
        account: object,
        *,
        state: PaperAccountMutexState = PaperAccountMutexState.OWNED,
    ) -> None:
        self.events = events
        self._account = account
        self.acquisition = _acquisition(state)
        self.active = False

    def __enter__(self):  # type: ignore[no-untyped-def]
        self.active = True
        self.events.append("b1-enter")
        return self

    def __exit__(self, exc_type, exc, traceback):  # type: ignore[no-untyped-def]
        self.events.append(("b1-exit", exc_type))
        self.active = False
        return False

    @property
    def evidence(self):  # type: ignore[no-untyped-def]
        assert self.active
        self.events.append("post-lock-evidence")
        return self._account

    @property
    def operation_root(self) -> str:
        assert self.active
        self.events.append("operation-root")
        return OPERATION_ROOT


def _case(
    *,
    account=None,
    state: PaperAccountMutexState = PaperAccountMutexState.OWNED,
    build_plan=preparation.build_manual_paper_strategy_plan,
    verify_plan=preparation.verify_manual_paper_strategy_plan,
):  # type: ignore[no-untyped-def]
    events: list[object] = []
    c1 = object()
    cycle = FakeSupervisedCycle(events, account or _post_lock_evidence(), state=state)

    def supervised_cycle(authority, *, historical_cycle_configuration_payloads=()):  # type: ignore[no-untyped-def]
        events.append(("b1-create", authority, historical_cycle_configuration_payloads))
        return cycle

    def match_selected_snapshot(permit, audit, authority):  # type: ignore[no-untyped-def]
        events.append(("p2-match", permit, audit, authority))

    config = _DEFAULT_CONFIG
    kwargs = dict(
        history_seed=_verified_seed(config, ("10", "10", "9")),
        strategy_config=config,
        caller_idempotency_key=CALLER_KEY,
        open_reference=CallerAssertedNextSessionOpenReference(
            SPY, _NEXT_SESSION, Decimal("12")
        ),
        policies=_policies(),
        planning_at=CAPTURED_AT + timedelta(minutes=1),
        submitted_at=CAPTURED_AT + timedelta(minutes=2),
        filled_at=datetime(2025, 1, 7, 20, tzinfo=UTC),
        metadata=(MetadataEntry("source", "pd2b3-test"),),
        historical_cycle_configuration_payloads=(b"historical-plan",),
        supervised_cycle=supervised_cycle,
        build_plan=build_plan,
        verify_plan=verify_plan,
        match_selected_snapshot=match_selected_snapshot,
        calendar=calendar(),
    )
    scope = preparation._supervised_personal_desktop_paper_operation_preparation(
        c1,  # type: ignore[arg-type]
        _selected_result(),
        **kwargs,
    )
    return scope, cycle, events, kwargs


def test_public_boundary_requires_genuine_c1_before_p2_or_b1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        pytest.fail("invalid C1 reached P2 or B1")

    monkeypatch.setattr(
        preparation, "require_selected_c3_snapshot_matches_authority", forbidden
    )
    monkeypatch.setattr(
        preparation, "supervised_personal_desktop_paper_cycle", forbidden
    )
    _, _, _, kwargs = _case()
    public = {
        key: value
        for key, value in kwargs.items()
        if key
        not in {
            "supervised_cycle",
            "build_plan",
            "verify_plan",
            "match_selected_snapshot",
            "calendar",
        }
    }
    with pytest.raises(WindowsAuthorityError):
        preparation.supervised_personal_desktop_paper_operation_preparation(
            object(),  # type: ignore[arg-type]
            _selected_result(),
            **public,
        )


def test_public_boundary_requires_exact_p2_result_before_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c1 = object()
    monkeypatch.setattr(
        preparation, "require_validated_production_authority", lambda value: c1
    )
    monkeypatch.setattr(
        preparation,
        "require_selected_c3_snapshot_matches_authority",
        lambda *args: pytest.fail("non-result reached P2 matching"),
    )
    _, _, _, kwargs = _case()
    public = {
        key: value
        for key, value in kwargs.items()
        if key
        not in {
            "supervised_cycle",
            "build_plan",
            "verify_plan",
            "match_selected_snapshot",
            "calendar",
        }
    }
    with pytest.raises(
        preparation.SupervisedPaperOperationPreparationError,
        match="exact P2 read result",
    ):
        preparation.supervised_personal_desktop_paper_operation_preparation(
            c1,  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            **public,
        )


def test_public_boundary_reconciles_p2_to_the_same_exact_c1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c1 = object()
    selected = _selected_result()
    matched: list[object] = []
    monkeypatch.setattr(
        preparation, "require_validated_production_authority", lambda value: c1
    )

    def match(permit, audit, authority):  # type: ignore[no-untyped-def]
        matched.extend((permit, audit, authority))

    monkeypatch.setattr(
        preparation, "require_selected_c3_snapshot_matches_authority", match
    )
    _, _, _, kwargs = _case()
    public = {
        key: value
        for key, value in kwargs.items()
        if key
        not in {
            "supervised_cycle",
            "build_plan",
            "verify_plan",
            "match_selected_snapshot",
            "calendar",
        }
    }
    scope = preparation.supervised_personal_desktop_paper_operation_preparation(
        c1,  # type: ignore[arg-type]
        selected,
        **public,
    )

    assert matched == [selected.permit, selected.audit, c1]
    assert scope._authority is c1
    assert scope._selected_snapshot is selected


def test_forged_p2_permit_cannot_enter_public_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c1 = _production_validation(monkeypatch)
    _, _, _, kwargs = _case()
    public = {
        key: value
        for key, value in kwargs.items()
        if key
        not in {
            "supervised_cycle",
            "build_plan",
            "verify_plan",
            "match_selected_snapshot",
            "calendar",
        }
    }
    with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
        preparation.supervised_personal_desktop_paper_operation_preparation(
            c1,
            _selected_result(),
            **public,
        )


def test_disposable_p2_provenance_cannot_enter_public_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c1 = _production_validation(monkeypatch)
    provisional = _selected_result()
    core = object.__new__(p2._SelectedC3SnapshotReadCore)
    core._authority = None
    core._production = False
    reader = object.__new__(p2.DisposableSelectedC3SnapshotReadAuthorityForTest)
    reader._core = core
    registration = p2._ReadCoreRegistration(
        weakref.ref(reader), None, p2._DISPOSABLE_CORE_PROVENANCE
    )
    permit = object.__new__(SelectedC3SnapshotPermit)
    binding = p2._PermitBinding(
        weakref.ref(provisional.audit),
        weakref.ref(core),
        weakref.ref(reader),
        registration,
        (
            c1.machine_authority_id,
            c1.approved_account_sid,
            c1.authority_epoch_id,
        ),
    )
    with p2._PERMIT_REGISTRY_LOCK:
        p2._CORE_REGISTRY[core] = registration
        p2._PERMIT_REGISTRY[permit] = binding
    result = _selected_result(permit)
    # Preserve the exact audit identity to which the disposable permit is bound.
    result = replace(result, audit=provisional.audit)
    _, _, _, kwargs = _case()
    public = {
        key: value
        for key, value in kwargs.items()
        if key
        not in {
            "supervised_cycle",
            "build_plan",
            "verify_plan",
            "match_selected_snapshot",
            "calendar",
        }
    }
    try:
        with pytest.raises(SelectedC3SnapshotReadError, match="provenance"):
            preparation.supervised_personal_desktop_paper_operation_preparation(
                c1,
                result,
                **public,
            )
    finally:
        with p2._PERMIT_REGISTRY_LOCK:
            p2._PERMIT_REGISTRY.pop(permit, None)
            p2._CORE_REGISTRY.pop(core, None)


def test_b1_precedes_post_lock_consumption_and_exact_p1_is_replay_verified() -> None:
    calls: list[object] = []

    def build(request, identified_calendar):  # type: ignore[no-untyped-def]
        calls.append(("build", request))
        return preparation.build_manual_paper_strategy_plan(
            request, identified_calendar
        )

    def verify(payload, identified_calendar, **expected):  # type: ignore[no-untyped-def]
        calls.append(("verify", payload, expected))
        return preparation.verify_manual_paper_strategy_plan(
            payload, identified_calendar, **expected
        )

    scope, cycle, events, _ = _case(build_plan=build, verify_plan=verify)
    with scope as active:
        assert events[:4] == [
            (
                "p2-match",
                scope._selected_snapshot.permit,
                scope._selected_snapshot.audit,
                scope._authority,
            ),
            ("b1-create", scope._authority, (b"historical-plan",)),
            "b1-enter",
            "post-lock-evidence",
        ]
        assert [call[0] for call in calls] == ["build", "verify"]
        built = calls[0][1]
        replay_payload = calls[1][1]
        replay_expected = calls[1][2]
        assert built.paper_account_id == ACCOUNT_ID
        assert built.prior_checkpoint == cycle._account.prior_checkpoint
        assert built.selected_c3_assertion.selection_id == SELECTION_ID
        assert built.selected_c3_assertion.terminal_id == TERMINAL_ID
        assert built.selected_c3_assertion.snapshot_id == active.selected_snapshot_id
        assert built.caller_idempotency_key == str(CALLER_KEY)
        assert replay_payload is not None
        assert replay_expected == {
            "expected_sha256": active.plan_artifact_sha256,
            "expected_byte_length": active.plan_artifact_byte_length,
            "expected_checkpointed_request": (
                preparation._require_active_prepared_paper_operation_binding(
                    active
                ).execution_inputs.request
            ),
        }


def test_prepared_binding_is_exact_path_independent_a67_material() -> None:
    scope, cycle, _, _ = _case()
    selected = scope._selected_snapshot
    with scope as active:
        binding = preparation._require_active_prepared_paper_operation_binding(active)
        inputs = binding.execution_inputs
        assert binding.operation_root == OPERATION_ROOT
        assert inputs.verified_prior == cycle._account.prior_checkpoint
        assert inputs.intent.prior_lineage_evidence == cycle._account.lineage
        assert inputs.terminal_checkpoint_payload == cycle._account.genesis.payload
        assert inputs.completed_snapshot_payload == selected.snapshot_bytes
        assert inputs.snapshot_verification == selected.verification
        assert inputs.cycle_configuration_payload != b"historical-plan"
        verified_plan = preparation.verify_manual_paper_strategy_plan(
            inputs.cycle_configuration_payload,
            inputs.calendar,
            expected_sha256=active.plan_artifact_sha256,
            expected_byte_length=active.plan_artifact_byte_length,
            expected_checkpointed_request=inputs.request,
        )
        assert inputs.cycle_configuration_payload == verified_plan.artifact_bytes
        assert verified_plan.plan.plan_id == active.plan_id
        assert verified_plan.plan.selected_c3_assertion.artifact_sha256 == (
            selected.audit.artifact_sha256
        )
        assert verified_plan.plan.selected_c3_assertion.artifact_byte_length == (
            selected.audit.artifact_byte_length
        )
        assert inputs.request == inputs.intent.request
        assert inputs.intent.caller_idempotency_key == CALLER_KEY
        assert inputs.intent.operation_id == active.operation_id
        assert inputs.application_id == active.application_id
        assert active.mutex_acquisition_state is PaperAccountMutexState.OWNED
        assert inputs.intent.cycle_configuration_artifact.sha256 == (
            active.plan_artifact_sha256
        )
        assert inputs.intent.cycle_configuration_artifact.byte_length == (
            active.plan_artifact_byte_length
        )
        assert inputs.intent.completed_snapshot_artifact.artifact_id == (
            selected.audit.snapshot_id
        )
        assert inputs.intent.completed_snapshot_artifact.sha256 == (
            selected.audit.artifact_sha256
        )
        assert CANONICAL_P2_PATH not in repr(inputs)
        assert not hasattr(active, "operation_root")
        assert not hasattr(active, "execution_inputs")
        assert not hasattr(active, "execute")
        assert not hasattr(active, "execute_paper_operation_once")


def test_changed_pre_lock_tip_cannot_replace_post_lock_prior() -> None:
    scope, cycle, _, _ = _case()
    pre_lock_prior = deepcopy(cycle._account.prior_checkpoint)
    object.__setattr__(pre_lock_prior, "checkpoint_sha256", "0" * 64)
    assert not hasattr(scope, "_pre_lock_prior")
    with scope as active:
        inputs = preparation._require_active_prepared_paper_operation_binding(
            active
        ).execution_inputs
        assert inputs.verified_prior == cycle._account.prior_checkpoint
        assert inputs.verified_prior != pre_lock_prior


def test_abandoned_owner_blocks_before_p1_or_a67_and_releases() -> None:
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        pytest.fail("abandoned ownership reached P1")

    scope, _, events, _ = _case(
        state=PaperAccountMutexState.ABANDONED_OWNER,
        build_plan=forbidden,
        verify_plan=forbidden,
    )
    with pytest.raises(
        preparation.PaperOperationPreparationReconciliationRequiredError,
        match="requires reconciliation",
    ):
        with scope:
            pytest.fail("abandoned ownership exposed a prepared context")
    assert "post-lock-evidence" not in events
    assert events[-1] == ("b1-exit", None)


def test_private_binding_expires_and_normal_or_body_exit_releases() -> None:
    scope, _, events, _ = _case()
    with scope as active:
        preparation._require_active_prepared_paper_operation_binding(active)
    assert events[-1] == ("b1-exit", None)
    with pytest.raises(
        preparation.SupervisedPaperOperationPreparationError,
        match="not active",
    ):
        preparation._require_active_prepared_paper_operation_binding(scope)

    exceptional, _, exceptional_events, _ = _case()
    with pytest.raises(LookupError, match="body"):
        with exceptional:
            raise LookupError("body")
    assert exceptional_events[-1] == ("b1-exit", LookupError)


def test_context_is_one_shot_noncopyable_and_private_binding_type_is_exact() -> None:
    scope, _, _, _ = _case()
    for operation in (copy, deepcopy):
        with pytest.raises(TypeError):
            operation(scope)
    with pytest.raises(
        preparation.SupervisedPaperOperationPreparationError,
        match="context type",
    ):
        preparation._require_active_prepared_paper_operation_binding(object())  # type: ignore[arg-type]
    with scope:
        pass
    with pytest.raises(
        preparation.SupervisedPaperOperationPreparationError,
        match="one-shot",
    ):
        with scope:
            pass


def test_public_signature_accepts_only_c1_p2_and_pure_planning_inputs() -> None:
    parameters = inspect.signature(
        preparation.supervised_personal_desktop_paper_operation_preparation
    ).parameters
    assert tuple(parameters) == (
        "authority",
        "selected_snapshot",
        "history_seed",
        "strategy_config",
        "caller_idempotency_key",
        "open_reference",
        "policies",
        "planning_at",
        "submitted_at",
        "filled_at",
        "metadata",
        "historical_cycle_configuration_payloads",
    )
    prohibited = {
        "paper_account_id",
        "prior_checkpoint",
        "lineage_tip",
        "lineage_evidence",
        "operation_root",
        "path",
        "execution_inputs",
        "intent",
        "request",
        "application_id",
        "operation_id",
        "mutex_name",
        "sid",
        "native_handle",
        "timeout",
        "cycle_configuration_payload",
        "strategy_plan",
    }
    assert prohibited.isdisjoint(parameters)


def test_pd2b3_has_no_a67_writer_or_external_effect_surface() -> None:
    import trading_bot.runtime as runtime_public

    source = Path(preparation.__file__).read_text(encoding="utf-8")
    imported_modules = {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    for prohibited in (
        "execute_paper_operation_once",
        "inspect_paper_operation_root",
        "commit_paper_operation_receipt",
        "transition staging",
        "transition finalization",
    ):
        assert prohibited not in source
    assert not any(
        boundary in module
        for module in imported_modules
        for boundary in ("provider", "broker", "live")
    )
    assert "open(" not in source
    assert not hasattr(
        runtime_public, "_require_active_prepared_paper_operation_binding"
    )
    assert PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE is not None
    assert PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE.paper_account_id == ACCOUNT_ID


def test_execution_input_reconciliation_is_not_bypassed() -> None:
    scope, _, _, _ = _case()
    original = preparation.VerifiedPaperOperationExecutionInputs

    def rejecting(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise PaperOperationExecutionInputsError("reconciliation was called")

    preparation.VerifiedPaperOperationExecutionInputs = rejecting  # type: ignore[misc]
    try:
        with pytest.raises(PaperOperationExecutionInputsError, match="was called"):
            with scope:
                pass
    finally:
        preparation.VerifiedPaperOperationExecutionInputs = original  # type: ignore[misc]


def test_public_scope_never_accepts_a_prebuilt_supervised_cycle() -> None:
    assert not hasattr(preparation, "SupervisedPaperOperationPreparation")
    with pytest.raises(PersonalDesktopPaperAccountError):
        preparation._SupervisedPaperOperationPreparation(  # type: ignore[call-arg]
            object(),
            _selected_result(),
            history_seed=object(),
            strategy_config=_DEFAULT_CONFIG,
            caller_idempotency_key=CALLER_KEY,
            open_reference=object(),
            policies=object(),
            planning_at=CAPTURED_AT,
            submitted_at=CAPTURED_AT,
            filled_at=CAPTURED_AT,
            metadata=(),
            historical_cycle_configuration_payloads=(),
            supervised_cycle=lambda authority: object(),
            build_plan=lambda request, identified_calendar: object(),
            verify_plan=lambda payload, identified_calendar: object(),
            match_selected_snapshot=lambda permit, audit, authority: None,
            calendar=calendar(),
            _key=object(),
        )
