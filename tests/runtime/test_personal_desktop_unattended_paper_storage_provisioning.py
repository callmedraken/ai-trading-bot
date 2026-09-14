"""Focused D1 Administrator-only dual-namespace provisioning tests."""

import copy
import ctypes
import inspect
import pickle
from dataclasses import asdict, replace

import pytest

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution as receipt,
)
from trading_bot.runtime import (
    personal_desktop_supervised_paper_operation_execution as supervised,
)
from trading_bot.runtime import (
    personal_desktop_unattended_market_data_capture as capture,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_decision_publication as publication,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_operation_execution as unattended,
)
from trading_bot.runtime import (
    personal_desktop_unattended_paper_storage_provisioning as provisioning,
)
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)
from trading_bot.runtime.personal_desktop_paper_runtime_output import (
    _PersonalDesktopUnattendedDecisionOutputCapability as DecisionCapability,
)
from trading_bot.runtime.personal_desktop_paper_runtime_output import (
    _PersonalDesktopUnattendedInvocationOutputCapability as InvocationCapability,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
)
from trading_bot.runtime.windows_authority_security import (
    FILE_ALL_ACCESS,
    WRITE_DAC,
    WRITE_OWNER,
    AuthorityObjectKind,
)

from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)
from .test_personal_desktop_paper_account_security import MemoryReadApi

DECISIONS = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS
INVOCATIONS = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
RUNTIME = security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
TRADING_SID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
ADMIN = TradingTokenObservation(
    "S-1-5-21-1-2-3-1005",
    1,
    False,
    True,
    ((security.ADMINISTRATORS_SID, 4),),
)
TARGETS = (provisioning._DECISION_TARGET, provisioning._INVOCATION_TARGET)
ROLES = tuple(target.role for target in TARGETS)
ALL_GATES_CLOSED = (False, False, False, False, False, False, False, False)
Classification = provisioning.PersonalDesktopUnattendedStorageProvisioningClassification
ProvisioningStatus = provisioning.PersonalDesktopUnattendedStorageProvisioningStatus
Diagnostic = provisioning.PersonalDesktopUnattendedStorageProvisioningDiagnostic


@pytest.fixture(autouse=True)
def block_real_native(monkeypatch, prohibit_production_effects):
    assert provisioning._gate_state() == ALL_GATES_CLOSED

    def forbidden(*_args, **_kwargs):
        pytest.fail("D1 source-readiness tests must never load a native DLL")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    yield
    assert provisioning._gate_state() == ALL_GATES_CLOSED


class Observer:
    def __init__(self, *observations):
        self.observations = list(observations) or [ADMIN]
        self.calls = 0

    def observe(self):
        value = self.observations[min(self.calls, len(self.observations) - 1)]
        self.calls += 1
        if isinstance(value, BaseException):
            raise value
        return value


class MemoryProvisioningApi(MemoryReadApi):
    """In-memory exact-name model with source-owned fixed-child operations."""

    def __init__(self, *, with_runtime=True):
        super().__init__()
        if with_runtime:
            self.put(RUNTIME)
        self.create_calls = []
        self.create_hooks = {role: lambda: None for role in ROLES}
        self.presence_hooks = {
            target.role: lambda target=target: target.path in self.nodes
            for target in TARGETS
        }
        self.delete_calls = 0
        self.rename_calls = 0
        self.write_calls = 0
        self.applied_policies = []

    def fixed_child_present(self, target):
        provisioning._require_source_target(target)
        self.calls.append(("fixed_child_present", target.path))
        value = self.presence_hooks[target.role]()
        if type(value) is not bool:
            raise AuthorityObjectError("absence is unproven")
        return value

    def put(self, path, payload=None):
        super().put(path, payload)
        for candidate, node in self.nodes.items():
            spec = security.paper_object_spec(candidate)
            if spec.role in {
                security.PaperObjectRole.VOLUME,
                security.PaperObjectRole.PARENT,
            }:
                continue
            policy = security.paper_security_policy(spec.role, TRADING_SID)
            node.observation = replace(
                node.observation,
                security=replace(
                    node.observation.security,
                    owner_sid=policy.owner_sid,
                    aces=policy.aces,
                ),
            )

    def create_fixed_child(self, target):
        provisioning._require_source_target(target)
        self.calls.append(("create_fixed_child", target.path))
        self.create_calls.append(target.role)
        if self.create_calls.count(target.role) != 1:
            raise AssertionError("fixed create was retried")
        self.create_hooks[target.role]()
        if target.path in self.nodes:
            raise AuthorityObjectError("fixed target already exists")
        self.applied_policies.append(provisioning._fixed_target_policy(target))
        self.put(target.path)


def _qualify(api, *, observer=None):
    return provisioning._qualify(observer or Observer(), lambda: api)


def _provision(api, *, observer=None, authority=None):
    return provisioning._provision_personal_desktop_unattended_storage_for_test(
        api=api,
        observer=observer or Observer(),
        authority=(
            authority
            or provisioning._open_disposable_provisioning_effect_authority_for_test()
        ),
    )


def _put(api, *roles):
    for target in TARGETS:
        if target.role in roles:
            api.put(target.path)


def _target_result(result, role):
    if role is security.PaperObjectRole.UNATTENDED_DECISIONS:
        return result.decision_target
    return result.invocation_target


def _patch_gate(monkeypatch, index, value):
    module_attribute = (
        (capture, "PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED"),
        (
            publication,
            "PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED",
        ),
        (security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED"),
        (security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED"),
        (
            supervised,
            "PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED",
        ),
        (receipt, "PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED"),
        (unattended, "PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED"),
        (
            provisioning,
            "PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED",
        ),
    )[index]
    monkeypatch.setattr(*module_attribute, value)


def test_eight_committed_effect_gates_are_distinct_and_false():
    assert provisioning._gate_state() == ALL_GATES_CLOSED
    assert all(value is False for value in provisioning._gate_state())


def test_fixed_targets_roles_order_and_exact_policies_are_source_owned():
    assert tuple(target.path for target in TARGETS) == (
        r"F:\AITradingBot\Paper-v2\runtime\unattended-decisions",
        r"F:\AITradingBot\Paper-v2\runtime\unattended-invocations",
    )
    assert ROLES == (
        security.PaperObjectRole.UNATTENDED_DECISIONS,
        security.PaperObjectRole.UNATTENDED_INVOCATIONS,
    )
    for target in TARGETS:
        spec = security.paper_object_spec(target.path)
        assert spec.role is target.role
        assert spec.kind is AuthorityObjectKind.DIRECTORY
        policy = provisioning._fixed_target_policy(target)
        assert policy == security.paper_security_policy(target.role, TRADING_SID)
        assert policy.owner_sid == security.ADMINISTRATORS_SID
        rights = {ace.principal_sid: ace.access_mask for ace in policy.aces}
        assert rights[security.ADMINISTRATORS_SID] == FILE_ALL_ACCESS
        assert rights[security.SYSTEM_SID] == FILE_ALL_ACCESS
        assert rights[TRADING_SID] == security.TRADING_CONTAINER_DATA
        assert not rights[TRADING_SID] & (0x10000 | WRITE_DAC | WRITE_OWNER)


def test_production_boundaries_accept_no_caller_authority_overrides():
    assert not inspect.signature(
        provisioning.qualify_personal_desktop_unattended_storage_provisioning
    ).parameters
    assert not inspect.signature(
        provisioning.provision_personal_desktop_unattended_storage
    ).parameters
    assert not inspect.signature(
        provisioning._WindowsProvisioningMutationNativeApi
    ).parameters
    for name in ("path", "role", "root", "sid", "api", "policy", "target"):
        with pytest.raises(TypeError):
            provisioning.provision_personal_desktop_unattended_storage(
                **{name: object()}
            )
    with pytest.raises(AuthorityPathError):
        provisioning._require_source_target(
            provisioning._ProvisioningTarget(INVOCATIONS, ROLES[1])
        )


@pytest.mark.parametrize(
    "token",
    (
        replace(ADMIN, elevated=False),
        replace(ADMIN, groups=()),
        replace(ADMIN, groups=((security.ADMINISTRATORS_SID, 0),)),
        replace(ADMIN, token_type=2),
        replace(ADMIN, thread_token_present=True),
    ),
)
def test_invalid_administrator_blocks_before_native_construction(monkeypatch, token):
    calls = []
    monkeypatch.setattr(
        provisioning, "WindowsTradingTokenObserver", lambda: Observer(token)
    )
    monkeypatch.setattr(
        provisioning,
        "_WindowsProvisioningReadNativeApi",
        lambda: calls.append("native"),
    )

    result = provisioning.provision_personal_desktop_unattended_storage()

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert not any(
        target.create_attempted
        for target in (result.decision_target, result.invocation_target)
    )
    assert calls == []


def test_missing_root_or_runtime_blocks_before_both_presence_probes():
    for existing in (None, security.PERSONAL_DESKTOP_PAPER_V2_ROOT):
        api = MemoryProvisioningApi(with_runtime=False)
        if existing is not None:
            api.put(existing)
        result = _qualify(api)
        assert result.classification is Classification.BLOCKED
        assert not any(call[0] == "fixed_child_present" for call in api.calls)


@pytest.mark.parametrize(
    ("present", "expected"),
    (
        ((), ("MISSING", "MISSING")),
        ((ROLES[0],), ("ALREADY_PROVISIONED", "MISSING")),
        ((ROLES[1],), ("MISSING", "ALREADY_PROVISIONED")),
        (ROLES, ("ALREADY_PROVISIONED", "ALREADY_PROVISIONED")),
    ),
)
def test_qualification_reports_each_fixed_target(present, expected):
    api = MemoryProvisioningApi()
    _put(api, *present)

    result = _qualify(api)

    assert (
        result.decision_target.classification.name,
        result.invocation_target.classification.name,
    ) == expected
    assert [call[1] for call in api.calls if call[0] == "fixed_child_present"] == [
        DECISIONS,
        INVOCATIONS,
    ]


@pytest.mark.parametrize("unsafe_role", ROLES)
@pytest.mark.parametrize("change", ("reparse", "identity", "acl"))
def test_either_existing_unsafe_target_blocks_after_inspecting_both_before_creation(
    unsafe_role, change
):
    api = MemoryProvisioningApi()
    _put(api, unsafe_role)
    target = next(target for target in TARGETS if target.role is unsafe_role)
    node = api.nodes[target.path]
    if change == "identity":
        node.observation = replace(node.observation, identity=(7, 0))
    elif change == "reparse":
        node.observation = replace(
            node.observation,
            security=replace(node.observation.security, is_reparse_point=True),
        )
    else:
        node.observation = replace(
            node.observation,
            security=replace(
                node.observation.security, aces=node.observation.security.aces[:-1]
            ),
        )

    result = _provision(api)

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.diagnostic is Diagnostic.QUALIFICATION_BLOCKED
    assert result.failed_target_role is unsafe_role
    assert [call[1] for call in api.calls if call[0] == "fixed_child_present"] == [
        DECISIONS,
        INVOCATIONS,
    ]
    assert api.create_calls == []


@pytest.mark.parametrize("unsafe_role", ROLES)
def test_nonempty_preexisting_target_blocks_before_any_creation(unsafe_role):
    api = MemoryProvisioningApi()
    _put(api, unsafe_role)
    target = next(target for target in TARGETS if target.role is unsafe_role)
    api.overrides[target.path] = ("unexpected",)
    assert (
        _provision(api).status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert api.create_calls == []


def test_both_missing_are_created_once_in_fixed_order_and_fully_verified():
    api = MemoryProvisioningApi()

    result = _provision(api)

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.PROVISIONED
    )
    assert api.create_calls == list(ROLES)
    relevant_calls = [
        call[0]
        for call in api.calls
        if call[0] in {"fixed_child_present", "create_fixed_child"}
    ]
    assert relevant_calls[:3] == [
        "fixed_child_present",
        "fixed_child_present",
        "create_fixed_child",
    ]
    assert all(target.path in api.nodes for target in TARGETS)
    assert (
        result.decision_target.create_attempted
        is result.decision_target.created
        is result.decision_target.verified
        is True
    )
    assert (
        result.invocation_target.create_attempted
        is result.invocation_target.created
        is result.invocation_target.verified
        is True
    )
    assert api.applied_policies == [
        provisioning._fixed_target_policy(target) for target in TARGETS
    ]


def test_both_already_safe_are_read_only_with_no_mutation_construction():
    api = MemoryProvisioningApi()
    _put(api, *ROLES)
    constructed = []

    result = provisioning._run_provisioning(
        observer=Observer(),
        read_api_factory=lambda: api,
        mutation_api_factory=lambda: constructed.append(True),
        effect_authority=object(),
    )

    assert result.status is ProvisioningStatus.ALREADY_PROVISIONED
    assert all(
        target.verified for target in (result.decision_target, result.invocation_target)
    )
    assert constructed == []
    assert api.create_calls == []


@pytest.mark.parametrize(
    ("present_role", "created_role"),
    ((ROLES[0], ROLES[1]), (ROLES[1], ROLES[0])),
)
def test_only_missing_target_is_created(present_role, created_role):
    api = MemoryProvisioningApi()
    _put(api, present_role)

    result = _provision(api)

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.PROVISIONED
    )
    assert api.create_calls == [created_role]
    assert _target_result(result, present_role).create_attempted is False
    assert _target_result(result, created_role).created is True


def test_first_create_failure_stops_without_second_create_cleanup_or_retry():
    api = MemoryProvisioningApi()
    api.create_hooks[ROLES[0]] = lambda: (_ for _ in ()).throw(
        AuthorityObjectError("uncertain")
    )

    result = _provision(api)

    assert result.diagnostic is Diagnostic.CREATE_FAILED_OR_UNCERTAIN
    assert result.failed_target_role is ROLES[0]
    assert api.create_calls == [ROLES[0]]
    assert api.delete_calls == api.rename_calls == api.write_calls == 0


def test_second_create_failure_leaves_first_and_never_cleans_or_retries():
    api = MemoryProvisioningApi()
    api.create_hooks[ROLES[1]] = lambda: (_ for _ in ()).throw(
        AuthorityObjectError("uncertain")
    )

    result = _provision(api)

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.failed_target_role is ROLES[1]
    assert api.create_calls == list(ROLES)
    assert DECISIONS in api.nodes and INVOCATIONS not in api.nodes
    assert result.decision_target.created is result.decision_target.verified is True
    assert result.invocation_target.create_attempted is True
    assert result.invocation_target.created is False
    assert api.delete_calls == api.rename_calls == api.write_calls == 0


def test_immediate_post_create_verification_failure_blocks_without_retry():
    api = MemoryProvisioningApi()
    original = api.create_fixed_child

    def create_nonempty(target):
        original(target)
        api.overrides[target.path] = ("unexpected",)

    api.create_fixed_child = create_nonempty

    result = _provision(api)

    assert result.diagnostic is Diagnostic.POST_CREATE_VERIFICATION_BLOCKED
    assert result.failed_target_role is ROLES[0]
    assert api.create_calls == [ROLES[0]]
    assert DECISIONS in api.nodes and INVOCATIONS not in api.nodes


def test_parent_drift_between_qualification_and_first_create_blocks_mutation():
    api = MemoryProvisioningApi()

    class DriftAuthority:
        def begin(self):
            node = api.nodes[RUNTIME]
            node.observation = replace(node.observation, identity=(7, 99999))

        def require_active(self):
            pass

    result = provisioning._run_provisioning(
        observer=Observer(),
        read_api_factory=lambda: api,
        mutation_api_factory=lambda: api,
        effect_authority=DriftAuthority(),
    )

    assert result.diagnostic is Diagnostic.PRE_CREATE_REVALIDATION_BLOCKED
    assert result.failed_target_role is ROLES[0]
    assert api.create_calls == []


def test_token_drift_before_create_blocks_without_mutation():
    api = MemoryProvisioningApi()
    drifted = replace(ADMIN, user_sid="S-1-5-21-1-2-3-1006")

    result = _provision(api, observer=Observer(ADMIN, drifted))

    assert result.diagnostic is Diagnostic.PRE_CREATE_REVALIDATION_BLOCKED
    assert result.failed_target_role is ROLES[0]
    assert api.create_calls == []


def test_independent_reopen_mismatch_blocks_before_creation():
    api = MemoryProvisioningApi()
    _put(api, ROLES[0])

    def replace_on_reopen(path, count, node):
        if path == DECISIONS and count == 3:
            node.observation = replace(node.observation, identity=(7, 99999))

    api.on_inspect = replace_on_reopen

    result = _provision(api)

    assert result.diagnostic is Diagnostic.QUALIFICATION_BLOCKED
    assert result.failed_target_role is ROLES[0]
    assert api.create_calls == []


def test_disabled_committed_gate_blocks_native_mutation_construction():
    api = MemoryProvisioningApi()
    constructed = []

    result = provisioning._run_provisioning(
        observer=Observer(),
        read_api_factory=lambda: api,
        mutation_api_factory=lambda: constructed.append(True),
        effect_authority=provisioning._ProductionProvisioningEffectAuthority(),
    )

    assert result.diagnostic is Diagnostic.EFFECT_STATE_BLOCKED
    assert constructed == []


def test_final_dual_target_reverification_failure_is_sanitized_and_not_retried():
    api = MemoryProvisioningApi()
    original_names = api.names
    counts = {target.path: 0 for target in TARGETS}

    def drift_names(handle, path, maximum):
        if path in counts:
            counts[path] += 1
            if path == DECISIONS and counts[path] == 4:
                return ("unexpected",)
        return original_names(handle, path, maximum)

    api.names = drift_names

    result = _provision(api)

    assert result.diagnostic is Diagnostic.FINAL_REVERIFICATION_BLOCKED
    assert result.failed_target_role is ROLES[0]
    assert result.decision_target.verified is False
    assert api.create_calls == list(ROLES)


def test_final_token_drift_preserves_target_evidence_but_blocks_aggregate():
    api = MemoryProvisioningApi()
    drifted = replace(ADMIN, groups=())

    result = _provision(api, observer=Observer(ADMIN, ADMIN, ADMIN, drifted))

    assert result.status is ProvisioningStatus.BLOCKED
    assert result.diagnostic is Diagnostic.FINAL_REVERIFICATION_BLOCKED
    assert result.failed_target_role is None
    assert result.decision_target.verified is True
    assert result.invocation_target.verified is True


def test_all_companion_gate_combinations_block_before_mutation_construction(
    monkeypatch,
):
    api = MemoryProvisioningApi()
    constructed = []
    for mask in range(1, 1 << 7):
        with monkeypatch.context() as context:
            for index in range(7):
                _patch_gate(context, index, bool(mask & (1 << index)))
            _patch_gate(context, 7, True)
            result = provisioning._run_provisioning(
                observer=Observer(),
                read_api_factory=lambda: api,
                mutation_api_factory=lambda mask=mask: constructed.append(mask),
                effect_authority=provisioning._ProductionProvisioningEffectAuthority(),
            )
            assert result.diagnostic is Diagnostic.EFFECT_STATE_BLOCKED
    assert constructed == []


def test_exact_genuine_provisioning_gate_combination_is_required(monkeypatch):
    authority = provisioning._ProductionProvisioningEffectAuthority()
    with monkeypatch.context() as context:
        _patch_gate(context, 7, True)
        authority.begin()
    with monkeypatch.context() as context:
        _patch_gate(context, 7, 1)
        with pytest.raises(
            provisioning.PersonalDesktopUnattendedStorageProvisioningError
        ):
            authority.begin()


def test_all_gate_checks_require_exact_bool_identity(monkeypatch):
    for index in range(8):
        with monkeypatch.context() as context:
            _patch_gate(context, index, 0)
            with pytest.raises(
                provisioning.PersonalDesktopUnattendedStorageProvisioningError
            ):
                provisioning._require_closed_committed_gate_state()
    for index in range(7):
        with monkeypatch.context() as context:
            _patch_gate(context, index, 0)
            _patch_gate(context, 7, True)
            with pytest.raises(
                provisioning.PersonalDesktopUnattendedStorageProvisioningError
            ):
                provisioning._ProductionProvisioningEffectAuthority().begin()


def test_disposable_effect_authority_is_one_shot_noncopyable_nonserializable():
    authority = provisioning._open_disposable_provisioning_effect_authority_for_test()
    authority.begin()
    authority.require_active()
    with pytest.raises(TypeError):
        authority.begin()
    with pytest.raises(TypeError):
        copy.copy(authority)
    with pytest.raises(TypeError):
        copy.deepcopy(authority)
    with pytest.raises(TypeError):
        pickle.dumps(authority)


def test_disposable_seam_rejects_genuine_windows_native_implementation():
    native = object.__new__(provisioning._WindowsProvisioningMutationNativeApi)
    authority = provisioning._open_disposable_provisioning_effect_authority_for_test()
    with pytest.raises(TypeError, match="rejects the genuine Windows"):
        provisioning._provision_personal_desktop_unattended_storage_for_test(
            api=native,
            observer=Observer(),
            authority=authority,
        )


def test_result_and_qualification_expose_no_path_sid_handle_or_authority():
    api = MemoryProvisioningApi()
    for evidence in (_qualify(api), _provision(api)):
        fields = asdict(evidence)
        forbidden = ("path", "sid", "handle", "api", "native", "policy", "authority")
        assert not any(fragment in name for name in fields for fragment in forbidden)
        assert "F:\\" not in repr(evidence)
        assert "S-1-" not in repr(evidence)


def test_safely_provisioned_fake_namespaces_remain_readable_by_output_contracts():
    api = MemoryProvisioningApi()
    assert (
        _provision(api).status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.PROVISIONED
    )
    api.trading_runtime = True
    with security.PinnedTradingPaperReadSession(api, TRADING_SID) as session:
        assert session.names(DECISIONS) == ()
        assert session.names(INVOCATIONS) == ()


def test_existing_output_capability_cannot_provision_either_fixed_namespace():
    for capability in (DecisionCapability, InvocationCapability):
        assert "create_fixed_child" not in capability.__dict__
        assert "provision" not in capability.__dict__
    public_callables = {
        name
        for name, value in provisioning.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    forbidden = (
        "publish",
        "recover",
        "execute",
        "broker",
        "schedule",
        "delete",
        "rename",
        "write",
    )
    assert not any(
        fragment in name for name in public_callables for fragment in forbidden
    )
