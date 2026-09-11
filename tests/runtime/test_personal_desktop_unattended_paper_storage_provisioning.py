"""Focused PD4-B3 Administrator-only fixed-container provisioning tests."""

import ctypes
import inspect
from dataclasses import asdict, replace

import pytest

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_paper_receipt_recovery_execution,
    personal_desktop_supervised_paper_operation_execution,
    personal_desktop_unattended_paper_operation_execution,
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
    _PersonalDesktopUnattendedInvocationOutputCapability as UnattendedOutputCapability,
)
from trading_bot.runtime.windows_authority import AuthorityObjectError
from trading_bot.runtime.windows_authority_security import (
    FILE_ALL_ACCESS,
    WRITE_DAC,
    WRITE_OWNER,
    AuthorityObjectKind,
)

from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)
from .test_personal_desktop_paper_account_security import (
    SID,
    MemoryReadApi,
)

TARGET = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
RUNTIME = security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME
TRADING_SID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
ADMIN = TradingTokenObservation(
    "S-1-5-21-1-2-3-1005",
    1,
    False,
    True,
    ((security.ADMINISTRATORS_SID, 4),),
)


@pytest.fixture(autouse=True)
def block_real_native(monkeypatch, prohibit_production_effects):
    assert provisioning._gate_state() == (False, False, False, False, False, False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("PD4-B3 tests must never load a native DLL")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    yield
    assert provisioning._gate_state() == (False, False, False, False, False, False)


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
    """In-memory exact-name model with one fixed create operation."""

    def __init__(self, *, with_runtime=True):
        super().__init__()
        if with_runtime:
            self.put(RUNTIME)
        self.create_calls = 0
        self.create_hook = lambda: None
        self.presence_hook = lambda: TARGET in self.nodes
        self.delete_calls = 0
        self.rename_calls = 0
        self.write_calls = 0
        self.applied_policies = []

    def fixed_child_present(self):
        self.calls.append(("fixed_child_present", TARGET))
        value = self.presence_hook()
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

    def create_fixed_unattended_invocations(self):
        self.calls.append(("create_fixed_unattended_invocations", TARGET))
        self.create_calls += 1
        if self.create_calls != 1:
            raise AssertionError("fixed create was retried")
        self.create_hook()
        if TARGET in self.nodes:
            raise AuthorityObjectError("fixed target already exists")
        self.applied_policies.append(provisioning._fixed_target_policy())
        self.put(TARGET)


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


def test_six_committed_effect_gates_are_distinct_and_false():
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is False
    assert (
        personal_desktop_supervised_paper_operation_execution.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        personal_desktop_paper_receipt_recovery_execution.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED
        is False
    )
    assert (
        personal_desktop_unattended_paper_operation_execution.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED
        is False
    )
    assert (
        provisioning.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED
        is False
    )


def test_fixed_target_role_and_exact_b1_policy_are_reused():
    assert TARGET == r"F:\AITradingBot\Paper-v2\runtime\unattended-invocations"
    spec = security.paper_object_spec(TARGET)
    assert spec.role is security.PaperObjectRole.UNATTENDED_INVOCATIONS
    assert spec.kind is AuthorityObjectKind.DIRECTORY
    assert provisioning._fixed_target_policy() == security.paper_security_policy(
        spec.role,
        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid,
    )
    policy = provisioning._fixed_target_policy()
    assert policy.owner_sid == security.ADMINISTRATORS_SID
    rights = {ace.principal_sid: ace.access_mask for ace in policy.aces}
    assert rights[security.ADMINISTRATORS_SID] == FILE_ALL_ACCESS
    assert rights[security.SYSTEM_SID] == FILE_ALL_ACCESS
    trading = rights[
        PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid
    ]
    assert trading == security.TRADING_CONTAINER_DATA
    assert not trading & (0x10000 | WRITE_DAC | WRITE_OWNER)


def test_production_boundaries_accept_no_path_sid_api_policy_or_gate_override():
    assert (
        inspect.signature(
            provisioning.qualify_personal_desktop_unattended_storage_provisioning
        ).parameters
        == {}
    )
    assert (
        inspect.signature(
            provisioning.provision_personal_desktop_unattended_storage
        ).parameters
        == {}
    )
    assert (
        inspect.signature(provisioning._WindowsProvisioningMutationNativeApi).parameters
        == {}
    )
    for name in ("path", "root", "sid", "api", "policy", "enabled", "target"):
        with pytest.raises(TypeError):
            provisioning.provision_personal_desktop_unattended_storage(
                **{name: object()}
            )


@pytest.mark.parametrize(
    "token",
    (
        replace(ADMIN, elevated=False),
        replace(ADMIN, groups=()),
        replace(ADMIN, groups=((security.ADMINISTRATORS_SID, 0),)),
        replace(ADMIN, groups=((security.ADMINISTRATORS_SID, 0x14),)),
        replace(ADMIN, token_type=2),
        replace(ADMIN, thread_token_present=True),
    ),
)
def test_invalid_administrator_blocks_before_native_construction(monkeypatch, token):
    calls = []

    def forbidden():
        calls.append("native")
        raise AssertionError("invalid administrator reached native construction")

    monkeypatch.setattr(
        provisioning, "WindowsTradingTokenObserver", lambda: Observer(token)
    )
    monkeypatch.setattr(provisioning, "_WindowsProvisioningReadNativeApi", forbidden)

    result = provisioning.provision_personal_desktop_unattended_storage()

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.create_attempted is False
    assert calls == []


def test_missing_root_or_runtime_blocks_before_presence_or_create():
    for existing in (None, security.PERSONAL_DESKTOP_PAPER_V2_ROOT):
        api = MemoryProvisioningApi(with_runtime=False)
        if existing is not None:
            api.put(existing)

        result = _qualify(api)

        assert result.classification is (
            provisioning.PersonalDesktopUnattendedStorageProvisioningClassification.BLOCKED
        )
        assert not any(call[0] == "fixed_child_present" for call in api.calls)
        assert api.create_calls == 0


def test_exact_absent_target_is_missing_in_disposable_qualification():
    api = MemoryProvisioningApi()

    result = _qualify(api)

    assert result.classification is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningClassification.MISSING
    )
    assert result.diagnostic is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningDiagnostic.VERIFIED_MISSING
    )
    assert result.child_present is False
    assert api.create_calls == 0


def test_exact_safe_empty_existing_target_is_already_provisioned():
    api = MemoryProvisioningApi()
    api.put(TARGET)

    qualification = _qualify(api)
    result = _provision(api)

    assert qualification.classification is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningClassification.ALREADY_PROVISIONED
    )
    assert result.status is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.ALREADY_PROVISIONED
    )
    assert result.created is False
    assert result.verified is True
    assert api.create_calls == 0


def test_existing_nonempty_target_is_blocked():
    api = MemoryProvisioningApi()
    api.put(TARGET)
    api.overrides[TARGET] = ("unexpected",)

    result = _qualify(api)

    assert result.classification is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningClassification.BLOCKED
    )


@pytest.mark.parametrize("change", ("file", "reparse", "owner", "acl", "path"))
def test_existing_wrong_kind_reparse_owner_acl_or_path_is_blocked(change):
    api = MemoryProvisioningApi()
    api.put(TARGET)
    node = api.nodes[TARGET]
    facts = node.observation.security
    if change == "file":
        facts = replace(facts, kind=AuthorityObjectKind.FILE)
    elif change == "reparse":
        facts = replace(facts, is_reparse_point=True)
    elif change == "owner":
        facts = replace(facts, owner_sid=SID)
    elif change == "acl":
        facts = replace(facts, aces=facts.aces[:-1])
    else:
        facts = replace(facts, final_path=TARGET.lower())
    node.observation = replace(node.observation, security=facts)

    assert _qualify(api).classification is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningClassification.BLOCKED
    )


def test_unknown_occupancy_error_is_blocked_never_missing():
    api = MemoryProvisioningApi()
    api.presence_hook = lambda: (_ for _ in ()).throw(
        AuthorityObjectError("access denied is not absence")
    )

    assert _qualify(api).classification is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningClassification.BLOCKED
    )


def test_parent_security_and_identity_drift_block():
    for change in ("security", "identity"):
        api = MemoryProvisioningApi()

        def drift(change=change, api=api):
            node = api.nodes[RUNTIME]
            if change == "security":
                node.observation = replace(
                    node.observation,
                    security=replace(
                        node.observation.security,
                        dacl_protected=False,
                    ),
                )
            else:
                node.observation = replace(node.observation, identity=(7, 9999))
            return False

        api.presence_hook = drift

        assert _qualify(api).classification is (
            provisioning.PersonalDesktopUnattendedStorageProvisioningClassification.BLOCKED
        )


def test_token_drift_blocks_before_create():
    api = MemoryProvisioningApi()
    drifted = replace(ADMIN, user_sid="S-1-5-21-1-2-3-1006")

    result = _provision(api, observer=Observer(ADMIN, drifted))

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.create_attempted is False
    assert api.create_calls == 0


def test_disabled_production_gate_blocks_before_mutation_native_construction(
    monkeypatch,
):
    api = MemoryProvisioningApi()
    constructed = []

    def forbidden_mutation():
        constructed.append(True)
        raise AssertionError("disabled gate reached mutation construction")

    monkeypatch.setattr(provisioning, "WindowsTradingTokenObserver", lambda: Observer())
    monkeypatch.setattr(provisioning, "_WindowsProvisioningReadNativeApi", lambda: api)
    monkeypatch.setattr(
        provisioning, "_WindowsProvisioningMutationNativeApi", forbidden_mutation
    )

    result = provisioning.provision_personal_desktop_unattended_storage()

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.diagnostic is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningDiagnostic.EFFECT_STATE_BLOCKED
    )
    assert result.create_attempted is False
    assert constructed == []


def test_constructed_missing_evidence_is_not_a_production_creation_permit():
    qualification_type = (
        provisioning.PersonalDesktopUnattendedStorageProvisioningQualification
    )
    constructed = qualification_type(
        classification=(
            provisioning.PersonalDesktopUnattendedStorageProvisioningClassification.MISSING
        ),
        diagnostic=(
            provisioning.PersonalDesktopUnattendedStorageProvisioningDiagnostic.VERIFIED_MISSING
        ),
        target_role=security.PaperObjectRole.UNATTENDED_INVOCATIONS,
        child_present=False,
    )
    assert constructed.classification.name == "MISSING"
    assert (
        "qualification"
        not in inspect.signature(
            provisioning.provision_personal_desktop_unattended_storage
        ).parameters
    )


def test_disposable_future_enabled_path_creates_fixed_child_once_with_b1_policy():
    api = MemoryProvisioningApi()

    result = _provision(api)

    assert result == provisioning.PersonalDesktopUnattendedStorageProvisioningResult(
        status=provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.PROVISIONED,
        diagnostic=provisioning.PersonalDesktopUnattendedStorageProvisioningDiagnostic.PROVISIONED_AND_VERIFIED,
        target_role=security.PaperObjectRole.UNATTENDED_INVOCATIONS,
        create_attempted=True,
        created=True,
        verified=True,
    )
    assert api.create_calls == 1
    assert api.applied_policies == [provisioning._fixed_target_policy()]
    assert TARGET in api.nodes


def test_post_create_exact_identity_security_inventory_and_independent_reopen():
    api = MemoryProvisioningApi()

    result = _provision(api)

    target_opens = [
        call for call in api.calls if call[0] == "open" and call[1] == TARGET
    ]
    target_names = [
        call for call in api.calls if call[0] == "names" and call[1] == TARGET
    ]
    assert result.verified is True
    assert len(target_opens) == 2
    assert len(target_names) == 3
    assert api.inspections[TARGET] == 3


def test_post_create_nonempty_inventory_blocks_without_cleanup_or_repair():
    api = MemoryProvisioningApi()
    original = api.create_fixed_unattended_invocations

    def create_nonempty():
        original()
        api.overrides[TARGET] = ("unexpected",)

    api.create_fixed_unattended_invocations = create_nonempty

    result = _provision(api)

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.created is True
    assert result.diagnostic is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningDiagnostic.POST_CREATE_VERIFICATION_BLOCKED
    )
    assert TARGET in api.nodes
    assert api.delete_calls == api.rename_calls == api.write_calls == 0


def test_independent_reopen_mismatch_blocks_and_leaves_child_present():
    api = MemoryProvisioningApi()

    def replace_on_reopen(path, count, node):
        if path == TARGET and count == 3:
            node.observation = replace(node.observation, identity=(7, 99999))

    api.on_inspect = replace_on_reopen

    result = _provision(api)

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.created is True
    assert TARGET in api.nodes


def test_runtime_parent_revalidation_is_mandatory_after_create():
    api = MemoryProvisioningApi()
    original = api.create_fixed_unattended_invocations

    def create_and_drift_parent():
        original()
        node = api.nodes[RUNTIME]
        node.observation = replace(node.observation, identity=(7, 77777))

    api.create_fixed_unattended_invocations = create_and_drift_parent

    result = _provision(api)

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.created is True
    assert TARGET in api.nodes


def test_create_uncertainty_is_attempted_once_without_retry_or_cleanup():
    api = MemoryProvisioningApi()

    def uncertain():
        raise AuthorityObjectError("native response was lost")

    api.create_hook = uncertain

    result = _provision(api)

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.diagnostic is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningDiagnostic.CREATE_FAILED_OR_UNCERTAIN
    )
    assert result.create_attempted is True
    assert result.created is False
    assert api.create_calls == 1
    assert api.delete_calls == api.rename_calls == api.write_calls == 0


def test_post_create_token_drift_blocks_without_cleanup():
    api = MemoryProvisioningApi()
    drifted = replace(ADMIN, groups=((security.ADMINISTRATORS_SID, 0),))

    result = _provision(api, observer=Observer(ADMIN, ADMIN, drifted))

    assert (
        result.status
        is provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.BLOCKED
    )
    assert result.created is True
    assert TARGET in api.nodes
    assert api.delete_calls == 0


def test_already_provisioned_performs_zero_mutation_construction(monkeypatch):
    api = MemoryProvisioningApi()
    api.put(TARGET)
    constructed = []

    def forbidden():
        constructed.append(True)
        raise AssertionError("idempotent state constructed mutation native")

    result = provisioning._run_provisioning(
        observer=Observer(),
        read_api_factory=lambda: api,
        mutation_api_factory=forbidden,
        effect_authority=object(),
    )

    assert result.status is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.ALREADY_PROVISIONED
    )
    assert constructed == []
    assert api.create_calls == 0


def test_disposable_seam_rejects_genuine_windows_native_implementation():
    native = object.__new__(provisioning._WindowsProvisioningMutationNativeApi)
    authority = provisioning._open_disposable_provisioning_effect_authority_for_test()

    with pytest.raises(TypeError, match="rejects the genuine Windows"):
        provisioning._provision_personal_desktop_unattended_storage_for_test(
            api=native,
            observer=Observer(),
            authority=authority,
        )


def test_result_and_qualification_expose_no_path_sid_handle_or_native_authority():
    api = MemoryProvisioningApi()
    qualification = _qualify(api)
    result = _provision(api)
    forbidden = ("path", "sid", "handle", "api", "native", "policy", "authority")

    for evidence in (qualification, result):
        assert not any(
            fragment in name for name in asdict(evidence) for fragment in forbidden
        )
        assert "F:\\" not in repr(evidence)
        assert "S-1-" not in repr(evidence)


def test_b1_trading_read_accepts_safely_provisioned_empty_fake_container():
    api = MemoryProvisioningApi()
    assert _provision(api).status is (
        provisioning.PersonalDesktopUnattendedStorageProvisioningStatus.PROVISIONED
    )
    api.trading_runtime = True

    with security.PinnedTradingPaperReadSession(api, TRADING_SID) as session:
        assert session.names(TARGET) == ()


def test_b2_cannot_create_the_fixed_parent_and_effect_subsystems_are_absent():
    assert (
        "create_fixed_unattended_invocations" not in UnattendedOutputCapability.__dict__
    )
    assert "provision" not in UnattendedOutputCapability.__dict__
    public_callables = {
        name
        for name, value in provisioning.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    forbidden = (
        "publish",
        "invocation",
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
