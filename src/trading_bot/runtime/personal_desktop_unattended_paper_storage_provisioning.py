"""Administrator-only provisioning for the fixed PD4 invocation container.

The production mutation is separately gated and has exactly one destination.
Qualification is read-only.  Existing unsafe objects are never repaired, and a
failed or uncertain create is never retried or cleaned up.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Self

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_first_paper_operation import (
    PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE,
)
from trading_bot.runtime.personal_desktop_paper_account_publication import (
    require_paper_publication_administrator,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
    TradingTokenObserver,
    WindowsTradingTokenObserver,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
)
from trading_bot.runtime.windows_authority_security import (
    AuthorityObjectKind,
    SecurityPolicy,
    build_security_attributes,
)

PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED = False

_TARGET = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
_TRADING_SID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid


class PersonalDesktopUnattendedStorageProvisioningClassification(StrEnum):
    """Stable read-only classification of the single fixed target."""

    MISSING = "MISSING"
    ALREADY_PROVISIONED = "ALREADY_PROVISIONED"
    BLOCKED = "BLOCKED"


class PersonalDesktopUnattendedStorageProvisioningStatus(StrEnum):
    """Stable outcome of the tightly composed provisioning boundary."""

    PROVISIONED = "PROVISIONED"
    ALREADY_PROVISIONED = "ALREADY_PROVISIONED"
    BLOCKED = "BLOCKED"


class PersonalDesktopUnattendedStorageProvisioningDiagnostic(StrEnum):
    """Sanitized diagnostics with no path, SID, handle, or native evidence."""

    VERIFIED_MISSING = "VERIFIED_MISSING"
    VERIFIED_ALREADY_PROVISIONED = "VERIFIED_ALREADY_PROVISIONED"
    QUALIFICATION_BLOCKED = "QUALIFICATION_BLOCKED"
    EFFECT_STATE_BLOCKED = "EFFECT_STATE_BLOCKED"
    CREATE_FAILED_OR_UNCERTAIN = "CREATE_FAILED_OR_UNCERTAIN"
    POST_CREATE_VERIFICATION_BLOCKED = "POST_CREATE_VERIFICATION_BLOCKED"
    PROVISIONED_AND_VERIFIED = "PROVISIONED_AND_VERIFIED"


class PersonalDesktopUnattendedStorageProvisioningError(AuthorityObjectError):
    """The fixed provisioning authority failed closed."""


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedStorageProvisioningQualification:
    """Immutable read-only evidence; never a reusable creation capability."""

    classification: PersonalDesktopUnattendedStorageProvisioningClassification
    diagnostic: PersonalDesktopUnattendedStorageProvisioningDiagnostic
    target_role: security.PaperObjectRole
    child_present: bool

    def __post_init__(self) -> None:
        classifications = PersonalDesktopUnattendedStorageProvisioningClassification
        expected = {
            classifications.MISSING: (
                PersonalDesktopUnattendedStorageProvisioningDiagnostic.VERIFIED_MISSING,
                False,
            ),
            classifications.ALREADY_PROVISIONED: (
                PersonalDesktopUnattendedStorageProvisioningDiagnostic.VERIFIED_ALREADY_PROVISIONED,
                True,
            ),
            classifications.BLOCKED: (
                PersonalDesktopUnattendedStorageProvisioningDiagnostic.QUALIFICATION_BLOCKED,
                False,
            ),
        }.get(self.classification)
        if (
            type(self.classification)
            is not PersonalDesktopUnattendedStorageProvisioningClassification
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedStorageProvisioningDiagnostic
            or type(self.target_role) is not security.PaperObjectRole
            or self.target_role is not security.PaperObjectRole.UNATTENDED_INVOCATIONS
            or type(self.child_present) is not bool
            or expected != (self.diagnostic, self.child_present)
        ):
            raise ValueError("unattended storage qualification is invalid")


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedStorageProvisioningResult:
    """Immutable non-authorizing evidence for one bounded operation."""

    status: PersonalDesktopUnattendedStorageProvisioningStatus
    diagnostic: PersonalDesktopUnattendedStorageProvisioningDiagnostic
    target_role: security.PaperObjectRole
    create_attempted: bool
    created: bool
    verified: bool

    def __post_init__(self) -> None:
        statuses = PersonalDesktopUnattendedStorageProvisioningStatus
        diagnostics = PersonalDesktopUnattendedStorageProvisioningDiagnostic
        valid = {
            statuses.PROVISIONED: (
                diagnostics.PROVISIONED_AND_VERIFIED,
                True,
                True,
                True,
            ),
            statuses.ALREADY_PROVISIONED: (
                diagnostics.VERIFIED_ALREADY_PROVISIONED,
                False,
                False,
                True,
            ),
        }
        if self.status is statuses.BLOCKED:
            valid_outcome = (
                self.diagnostic
                in {
                    diagnostics.QUALIFICATION_BLOCKED,
                    diagnostics.EFFECT_STATE_BLOCKED,
                    diagnostics.CREATE_FAILED_OR_UNCERTAIN,
                    diagnostics.POST_CREATE_VERIFICATION_BLOCKED,
                }
                and self.verified is False
                and (not self.created or self.create_attempted)
            )
        else:
            valid_outcome = valid.get(self.status) == (
                self.diagnostic,
                self.create_attempted,
                self.created,
                self.verified,
            )
        if (
            type(self.status) is not PersonalDesktopUnattendedStorageProvisioningStatus
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedStorageProvisioningDiagnostic
            or type(self.target_role) is not security.PaperObjectRole
            or self.target_role is not security.PaperObjectRole.UNATTENDED_INVOCATIONS
            or any(
                type(value) is not bool
                for value in (self.create_attempted, self.created, self.verified)
            )
            or not valid_outcome
        ):
            raise ValueError("unattended storage provisioning result is invalid")


class _ProvisioningReadNativeApi(security.PaperReadNativeApi, Protocol):
    def fixed_child_present(self) -> bool: ...


class _ProvisioningMutationNativeApi(_ProvisioningReadNativeApi, Protocol):
    def create_fixed_unattended_invocations(self) -> None: ...


@dataclass(frozen=True, slots=True)
class _PinnedParent:
    handle: object
    spec: security.PaperObjectSpec
    observation: security.PaperObjectObservation


class _PinnedProvisioningParent:
    """Hold and revalidate the complete fixed chain needed for one child."""

    _PATHS = (
        "F:\\",
        security.PERSONAL_DESKTOP_PAPER_PARENT,
        security.PERSONAL_DESKTOP_PAPER_V2_ROOT,
        security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME,
    )

    def __init__(self, api: _ProvisioningReadNativeApi) -> None:
        self._api = api
        self._handles = ExitStack()
        self._objects: dict[str, _PinnedParent] = {}
        self._closed = False

    def __enter__(self) -> Self:
        if self._closed or self._objects:
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "provisioning parent guard cannot be reused"
            )
        try:
            for path in self._PATHS:
                spec = security.paper_object_spec(path)
                handle = self._api.open(path, spec.kind)
                self._handles.callback(self._api.close, handle)
                observation = self._api.inspect(handle, path, spec.kind)
                self._check(path, spec, observation)
                self._objects[path] = _PinnedParent(handle, spec, observation)
            self.finish()
        except BaseException:
            self._closed = True
            self._handles.close()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            self.finish()
        finally:
            self._closed = True
            self._handles.close()

    @staticmethod
    def _check(
        path: str,
        spec: security.PaperObjectSpec,
        observation: security.PaperObjectObservation,
    ) -> None:
        expected_roles = {
            "F:\\": security.PaperObjectRole.VOLUME,
            security.PERSONAL_DESKTOP_PAPER_PARENT: security.PaperObjectRole.PARENT,
            security.PERSONAL_DESKTOP_PAPER_V2_ROOT: security.PaperObjectRole.ROOT,
            security.PERSONAL_DESKTOP_PAPER_V2_RUNTIME: (
                security.PaperObjectRole.RUNTIME
            ),
        }
        if expected_roles.get(path) is not spec.role:
            raise AuthorityPathError("provisioning parent role is not exact")
        security.require_paper_object_security(
            path, spec, observation.security, _TRADING_SID
        )
        if (
            type(observation.identity) is not tuple
            or len(observation.identity) != 2
            or any(
                type(value) is not int or value < 0 for value in observation.identity
            )
            or observation.identity[1] == 0
        ):
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "provisioning parent identity is unsafe"
            )

    def finish(self) -> None:
        """Require held and independently reopened identity/security equality."""

        if self._closed or tuple(self._objects) != self._PATHS:
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "provisioning parent guard is not active"
            )
        for path, pinned in self._objects.items():
            current = self._api.inspect(pinned.handle, path, pinned.spec.kind)
            self._check(path, pinned.spec, current)
            if (
                current.identity != pinned.observation.identity
                or current.security != pinned.observation.security
                or (path == "F:\\" and current != pinned.observation)
            ):
                raise PersonalDesktopUnattendedStorageProvisioningError(
                    "provisioning parent identity/security drift"
                )
            reopened = self._api.open(path, pinned.spec.kind)
            try:
                observed = self._api.inspect(reopened, path, pinned.spec.kind)
                self._check(path, pinned.spec, observed)
                if (
                    observed.identity != pinned.observation.identity
                    or observed.security != pinned.observation.security
                    or (path == "F:\\" and observed != pinned.observation)
                ):
                    raise PersonalDesktopUnattendedStorageProvisioningError(
                        "provisioning parent named object was replaced"
                    )
            finally:
                self._api.close(reopened)


def _validate_target_observation(
    observation: security.PaperObjectObservation,
) -> None:
    spec = security.paper_object_spec(_TARGET)
    if (
        spec.role is not security.PaperObjectRole.UNATTENDED_INVOCATIONS
        or spec.kind is not AuthorityObjectKind.DIRECTORY
    ):
        raise AuthorityPathError("unattended provisioning target role is not exact")
    security.require_paper_object_security(
        _TARGET, spec, observation.security, _TRADING_SID
    )
    if (
        type(observation.identity) is not tuple
        or len(observation.identity) != 2
        or any(type(value) is not int or value < 0 for value in observation.identity)
        or observation.identity[1] == 0
    ):
        raise PersonalDesktopUnattendedStorageProvisioningError(
            "unattended provisioning target identity is unsafe"
        )


def _fixed_target_policy() -> SecurityPolicy:
    """Return the already-frozen B1 policy for the one fixed container role."""

    spec = security.paper_object_spec(_TARGET)
    if (
        spec.role is not security.PaperObjectRole.UNATTENDED_INVOCATIONS
        or spec.kind is not AuthorityObjectKind.DIRECTORY
    ):
        raise AuthorityPathError("unattended provisioning target role is not exact")
    return security.paper_security_policy(spec.role, _TRADING_SID)


def _verify_empty_target(api: _ProvisioningReadNativeApi) -> None:
    """Pin, inspect, inventory, and independently reopen the fixed child."""

    spec = security.paper_object_spec(_TARGET)
    handle = api.open(_TARGET, spec.kind)
    try:
        observation = api.inspect(handle, _TARGET, spec.kind)
        _validate_target_observation(observation)
        if api.names(handle, _TARGET, 1) != ():
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "unattended provisioning target is not empty"
            )
        current = api.inspect(handle, _TARGET, spec.kind)
        _validate_target_observation(current)
        if (
            current.identity != observation.identity
            or current.security != observation.security
        ):
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "unattended provisioning target identity/security drift"
            )
        reopened = api.open(_TARGET, spec.kind)
        try:
            independent = api.inspect(reopened, _TARGET, spec.kind)
            _validate_target_observation(independent)
            if (
                independent.identity != observation.identity
                or independent.security != observation.security
                or api.names(reopened, _TARGET, 1) != ()
            ):
                raise PersonalDesktopUnattendedStorageProvisioningError(
                    "unattended provisioning target named object changed"
                )
        finally:
            api.close(reopened)
        if api.names(handle, _TARGET, 1) != ():
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "unattended provisioning target inventory drift"
            )
    finally:
        api.close(handle)


def _classify_target(
    api: _ProvisioningReadNativeApi,
) -> PersonalDesktopUnattendedStorageProvisioningClassification:
    if api.fixed_child_present() is False:
        return PersonalDesktopUnattendedStorageProvisioningClassification.MISSING
    _verify_empty_target(api)
    return (
        PersonalDesktopUnattendedStorageProvisioningClassification.ALREADY_PROVISIONED
    )


def _observe_administrator(
    observer: TradingTokenObserver,
) -> TradingTokenObservation:
    observation = observer.observe()
    require_paper_publication_administrator(observation)
    return observation


def _require_unchanged_administrator(
    observer: TradingTokenObserver, initial: TradingTokenObservation
) -> None:
    final = _observe_administrator(observer)
    if final != initial:
        raise PersonalDesktopUnattendedStorageProvisioningError(
            "administrator token changed during provisioning"
        )


def _qualification_result(
    classification: PersonalDesktopUnattendedStorageProvisioningClassification,
) -> PersonalDesktopUnattendedStorageProvisioningQualification:
    classifications = PersonalDesktopUnattendedStorageProvisioningClassification
    diagnostics = PersonalDesktopUnattendedStorageProvisioningDiagnostic
    return PersonalDesktopUnattendedStorageProvisioningQualification(
        classification=classification,
        diagnostic={
            classifications.MISSING: diagnostics.VERIFIED_MISSING,
            classifications.ALREADY_PROVISIONED: (
                diagnostics.VERIFIED_ALREADY_PROVISIONED
            ),
        }[classification],
        target_role=security.PaperObjectRole.UNATTENDED_INVOCATIONS,
        child_present=classification is classifications.ALREADY_PROVISIONED,
    )


def _blocked_qualification() -> (
    PersonalDesktopUnattendedStorageProvisioningQualification
):
    return PersonalDesktopUnattendedStorageProvisioningQualification(
        classification=(
            PersonalDesktopUnattendedStorageProvisioningClassification.BLOCKED
        ),
        diagnostic=(
            PersonalDesktopUnattendedStorageProvisioningDiagnostic.QUALIFICATION_BLOCKED
        ),
        target_role=security.PaperObjectRole.UNATTENDED_INVOCATIONS,
        child_present=False,
    )


def _qualify(
    observer: TradingTokenObserver,
    api_factory: Callable[[], _ProvisioningReadNativeApi],
) -> PersonalDesktopUnattendedStorageProvisioningQualification:
    try:
        initial = _observe_administrator(observer)
        api = api_factory()
        with _PinnedProvisioningParent(api) as parent:
            classification = _classify_target(api)
            parent.finish()
        _require_unchanged_administrator(observer, initial)
        return _qualification_result(classification)
    except Exception:
        return _blocked_qualification()


def qualify_personal_desktop_unattended_storage_provisioning() -> (
    PersonalDesktopUnattendedStorageProvisioningQualification
):
    """Administrator-only read of the one fixed production target."""

    return _qualify(WindowsTradingTokenObserver(), _WindowsProvisioningReadNativeApi)


def _gate_state() -> tuple[bool, bool, bool, bool, bool, bool]:
    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_paper_receipt_recovery_execution as receipt,
    )
    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_supervised_paper_operation_execution as supervised,
    )
    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_unattended_paper_operation_execution as unattended,
    )

    return (
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        receipt.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        unattended.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )


def _require_closed_committed_gate_state() -> None:
    if _gate_state() != (False, False, False, False, False, False):
        raise PersonalDesktopUnattendedStorageProvisioningError(
            "committed Paper-v2 effect-gate state is invalid"
        )


class _ProductionProvisioningEffectAuthority:
    def begin(self) -> None:
        if _gate_state() != (False, False, False, False, False, True):
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "unattended storage provisioning effect-gate state is invalid"
            )

    def require_active(self) -> None:
        self.begin()


_DISPOSABLE_EFFECT_ISSUER = object()


class _DisposableProvisioningEffectAuthorityForTest:
    """One-shot model of the future gate without changing production source."""

    __slots__ = ("_active", "_issuer", "_lock", "_used")

    def __init__(self, *, _issuer: object) -> None:
        if _issuer is not _DISPOSABLE_EFFECT_ISSUER:
            raise TypeError("disposable provisioning effect issuer is invalid")
        self._issuer = _issuer
        self._lock = threading.Lock()
        self._used = False
        self._active = False

    def begin(self) -> None:
        with self._lock:
            _require_closed_committed_gate_state()
            if self._issuer is not _DISPOSABLE_EFFECT_ISSUER or self._used:
                raise TypeError(
                    "disposable provisioning effect authority is invalid or consumed"
                )
            self._used = True
            self._active = True

    def require_active(self) -> None:
        with self._lock:
            _require_closed_committed_gate_state()
            if not self._active:
                raise TypeError("disposable provisioning effect authority is inactive")

    def __copy__(self) -> object:
        raise TypeError("disposable provisioning effect authority cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(
            "disposable provisioning effect authority cannot be deep-copied"
        )

    def __reduce__(self) -> object:
        raise TypeError("disposable provisioning effect authority cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("disposable provisioning effect authority cannot be pickled")


def _open_disposable_provisioning_effect_authority_for_test() -> (
    _DisposableProvisioningEffectAuthorityForTest
):
    _require_closed_committed_gate_state()
    return _DisposableProvisioningEffectAuthorityForTest(
        _issuer=_DISPOSABLE_EFFECT_ISSUER
    )


def _result(
    status: PersonalDesktopUnattendedStorageProvisioningStatus,
    diagnostic: PersonalDesktopUnattendedStorageProvisioningDiagnostic,
    *,
    create_attempted: bool,
    created: bool,
    verified: bool,
) -> PersonalDesktopUnattendedStorageProvisioningResult:
    return PersonalDesktopUnattendedStorageProvisioningResult(
        status=status,
        diagnostic=diagnostic,
        target_role=security.PaperObjectRole.UNATTENDED_INVOCATIONS,
        create_attempted=create_attempted,
        created=created,
        verified=verified,
    )


def _run_provisioning(
    *,
    observer: TradingTokenObserver,
    read_api_factory: Callable[[], _ProvisioningReadNativeApi],
    mutation_api_factory: Callable[[], _ProvisioningMutationNativeApi],
    effect_authority: object,
) -> PersonalDesktopUnattendedStorageProvisioningResult:
    statuses = PersonalDesktopUnattendedStorageProvisioningStatus
    diagnostics = PersonalDesktopUnattendedStorageProvisioningDiagnostic
    classifications = PersonalDesktopUnattendedStorageProvisioningClassification
    phase = "qualification"
    attempted = False
    created = False
    try:
        initial = _observe_administrator(observer)
        read_api = read_api_factory()
        with _PinnedProvisioningParent(read_api) as parent:
            classification = _classify_target(read_api)
            parent.finish()
            if classification is classifications.MISSING:
                phase = "effect"
                effect_authority.begin()
                _require_unchanged_administrator(observer, initial)
                parent.finish()

                mutation_api = mutation_api_factory()
                effect_authority.require_active()
                phase = "create"
                attempted = True
                mutation_api.create_fixed_unattended_invocations()
                created = True

                phase = "verify"
                _verify_empty_target(mutation_api)
                parent.finish()
                effect_authority.require_active()
        _require_unchanged_administrator(observer, initial)
        if classification is classifications.ALREADY_PROVISIONED:
            return _result(
                statuses.ALREADY_PROVISIONED,
                diagnostics.VERIFIED_ALREADY_PROVISIONED,
                create_attempted=False,
                created=False,
                verified=True,
            )
        effect_authority.require_active()
        return _result(
            statuses.PROVISIONED,
            diagnostics.PROVISIONED_AND_VERIFIED,
            create_attempted=True,
            created=True,
            verified=True,
        )
    except Exception:
        diagnostic = {
            "qualification": diagnostics.QUALIFICATION_BLOCKED,
            "effect": diagnostics.EFFECT_STATE_BLOCKED,
            "create": diagnostics.CREATE_FAILED_OR_UNCERTAIN,
            "verify": diagnostics.POST_CREATE_VERIFICATION_BLOCKED,
        }[phase]
        return _result(
            statuses.BLOCKED,
            diagnostic,
            create_attempted=attempted,
            created=created,
            verified=False,
        )


def provision_personal_desktop_unattended_storage() -> (
    PersonalDesktopUnattendedStorageProvisioningResult
):
    """Provision only the fixed target; accepts no caller authority overrides."""

    return _run_provisioning(
        observer=WindowsTradingTokenObserver(),
        read_api_factory=_WindowsProvisioningReadNativeApi,
        mutation_api_factory=_WindowsProvisioningMutationNativeApi,
        effect_authority=_ProductionProvisioningEffectAuthority(),
    )


def _provision_personal_desktop_unattended_storage_for_test(
    *,
    api: _ProvisioningMutationNativeApi,
    observer: TradingTokenObserver,
    authority: _DisposableProvisioningEffectAuthorityForTest,
) -> PersonalDesktopUnattendedStorageProvisioningResult:
    """Exercise the same algorithm with a fake native implementation only."""

    if type(authority) is not _DisposableProvisioningEffectAuthorityForTest:
        raise TypeError("disposable provisioning effect authority is invalid")
    if isinstance(api, _WindowsProvisioningMutationNativeApi):
        raise TypeError(
            "the disposable provisioning seam rejects the genuine Windows native "
            "implementation"
        )
    return _run_provisioning(
        observer=observer,
        read_api_factory=lambda: api,
        mutation_api_factory=lambda: api,
        effect_authority=authority,
    )


def _bind(library: object, name: str, arguments: list, result: object):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


class _WindowsProvisioningReadNativeApi(security.WindowsPaperReadNativeApi):
    """No-follow presence probe for only the fixed provisioning child."""

    def fixed_child_present(self) -> bool:
        create = _bind(
            self._kernel,
            "CreateFileW",
            [
                ctypes.c_wchar_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.c_void_p,
            ],
            ctypes.c_void_p,
        )
        close = _bind(self._kernel, "CloseHandle", [ctypes.c_void_p], ctypes.c_int32)
        handle = create(
            _TARGET,
            0,
            7,
            None,
            3,
            0x02200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
            None,
        )
        if handle in (-1, ctypes.c_void_p(-1).value):
            if ctypes.get_last_error() in (2, 3):
                return False
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "fixed unattended target absence is unproven"
            )
        if handle in (None, 0):
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "fixed unattended target probe returned an invalid handle"
            )
        if not close(handle):
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "fixed unattended target probe close failed"
            )
        return True


class _WindowsProvisioningMutationNativeApi(_WindowsProvisioningReadNativeApi):
    """One create-new operation with the final frozen B1 container policy."""

    def __init__(self) -> None:
        _ProductionProvisioningEffectAuthority().require_active()
        super().__init__()
        self._attempted = False

    def create_fixed_unattended_invocations(self) -> None:
        _ProductionProvisioningEffectAuthority().require_active()
        if self._attempted:
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "fixed unattended target creation was already attempted"
            )
        self._attempted = True
        spec = security.paper_object_spec(_TARGET)
        if (
            spec.role is not security.PaperObjectRole.UNATTENDED_INVOCATIONS
            or spec.kind is not AuthorityObjectKind.DIRECTORY
        ):
            raise AuthorityPathError("native provisioning target role is not exact")
        policy = _fixed_target_policy()
        create = _bind(
            self._kernel,
            "CreateDirectoryW",
            [ctypes.c_wchar_p, ctypes.c_void_p],
            ctypes.c_int32,
        )
        with build_security_attributes(policy) as attributes:
            if not create(_TARGET, ctypes.byref(attributes.attributes)):
                raise PersonalDesktopUnattendedStorageProvisioningError(
                    "fixed unattended target create-new failed or was uncertain"
                )
