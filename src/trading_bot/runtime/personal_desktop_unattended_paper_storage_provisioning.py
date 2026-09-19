"""Administrator-only provisioning for the two fixed PD4 storage namespaces.

Qualification covers both source-owned destinations before any mutation.
Existing unsafe objects are never repaired, and a failed or uncertain create is
never retried or cleaned up.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, replace
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

_TRADING_SID = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE.approved_trading_sid


@dataclass(frozen=True, slots=True)
class _ProvisioningTarget:
    path: str
    role: security.PaperObjectRole


_DECISION_TARGET = _ProvisioningTarget(
    security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_DECISIONS,
    security.PaperObjectRole.UNATTENDED_DECISIONS,
)
_INVOCATION_TARGET = _ProvisioningTarget(
    security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS,
    security.PaperObjectRole.UNATTENDED_INVOCATIONS,
)
_TARGETS = (_DECISION_TARGET, _INVOCATION_TARGET)


class PersonalDesktopUnattendedStorageProvisioningClassification(StrEnum):
    """Stable read-only classification of a fixed target or both targets."""

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
    PRE_CREATE_REVALIDATION_BLOCKED = "PRE_CREATE_REVALIDATION_BLOCKED"
    CREATE_FAILED_OR_UNCERTAIN = "CREATE_FAILED_OR_UNCERTAIN"
    POST_CREATE_VERIFICATION_BLOCKED = "POST_CREATE_VERIFICATION_BLOCKED"
    FINAL_REVERIFICATION_BLOCKED = "FINAL_REVERIFICATION_BLOCKED"
    PROVISIONED_AND_VERIFIED = "PROVISIONED_AND_VERIFIED"


class PersonalDesktopUnattendedStorageProvisioningError(AuthorityObjectError):
    """The fixed provisioning authority failed closed."""


_TARGET_ROLES = {
    security.PaperObjectRole.UNATTENDED_DECISIONS,
    security.PaperObjectRole.UNATTENDED_INVOCATIONS,
}


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedStorageTargetQualification:
    """Immutable read-only evidence for one exact fixed target."""

    classification: PersonalDesktopUnattendedStorageProvisioningClassification
    diagnostic: PersonalDesktopUnattendedStorageProvisioningDiagnostic
    target_role: security.PaperObjectRole
    child_present: bool

    def __post_init__(self) -> None:
        classifications = PersonalDesktopUnattendedStorageProvisioningClassification
        diagnostics = PersonalDesktopUnattendedStorageProvisioningDiagnostic
        expected = {
            classifications.MISSING: (diagnostics.VERIFIED_MISSING, False),
            classifications.ALREADY_PROVISIONED: (
                diagnostics.VERIFIED_ALREADY_PROVISIONED,
                True,
            ),
            classifications.BLOCKED: (diagnostics.QUALIFICATION_BLOCKED, False),
        }.get(self.classification)
        if (
            type(self.classification)
            is not PersonalDesktopUnattendedStorageProvisioningClassification
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedStorageProvisioningDiagnostic
            or type(self.target_role) is not security.PaperObjectRole
            or self.target_role not in _TARGET_ROLES
            or type(self.child_present) is not bool
            or expected != (self.diagnostic, self.child_present)
        ):
            raise ValueError("unattended storage target qualification is invalid")


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedStorageProvisioningQualification:
    """Aggregate read-only evidence for both fixed targets."""

    classification: PersonalDesktopUnattendedStorageProvisioningClassification
    diagnostic: PersonalDesktopUnattendedStorageProvisioningDiagnostic
    decision_target: PersonalDesktopUnattendedStorageTargetQualification
    invocation_target: PersonalDesktopUnattendedStorageTargetQualification

    def __post_init__(self) -> None:
        classifications = PersonalDesktopUnattendedStorageProvisioningClassification
        diagnostics = PersonalDesktopUnattendedStorageProvisioningDiagnostic
        target_states = (
            self.decision_target.classification,
            self.invocation_target.classification,
        )
        if classifications.BLOCKED in target_states:
            expected = (classifications.BLOCKED, diagnostics.QUALIFICATION_BLOCKED)
        elif target_states == (
            classifications.ALREADY_PROVISIONED,
            classifications.ALREADY_PROVISIONED,
        ):
            expected = (
                classifications.ALREADY_PROVISIONED,
                diagnostics.VERIFIED_ALREADY_PROVISIONED,
            )
        else:
            expected = (classifications.MISSING, diagnostics.VERIFIED_MISSING)
        if (
            type(self.classification)
            is not PersonalDesktopUnattendedStorageProvisioningClassification
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedStorageProvisioningDiagnostic
            or type(self.decision_target)
            is not PersonalDesktopUnattendedStorageTargetQualification
            or type(self.invocation_target)
            is not PersonalDesktopUnattendedStorageTargetQualification
            or self.decision_target.target_role
            is not security.PaperObjectRole.UNATTENDED_DECISIONS
            or self.invocation_target.target_role
            is not security.PaperObjectRole.UNATTENDED_INVOCATIONS
            or expected != (self.classification, self.diagnostic)
        ):
            raise ValueError("unattended storage qualification is invalid")


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedStorageTargetResult:
    """Immutable non-authorizing evidence for one fixed target."""

    qualification: PersonalDesktopUnattendedStorageProvisioningClassification
    target_role: security.PaperObjectRole
    create_attempted: bool
    created: bool
    verified: bool

    def __post_init__(self) -> None:
        classifications = PersonalDesktopUnattendedStorageProvisioningClassification
        valid = (
            type(self.qualification)
            is PersonalDesktopUnattendedStorageProvisioningClassification
            and type(self.target_role) is security.PaperObjectRole
            and self.target_role in _TARGET_ROLES
            and all(
                type(value) is bool
                for value in (self.create_attempted, self.created, self.verified)
            )
            and (not self.created or self.create_attempted)
            and (
                self.qualification is not classifications.BLOCKED
                or (
                    not self.create_attempted and not self.created and not self.verified
                )
            )
            and (
                self.qualification is not classifications.ALREADY_PROVISIONED
                or (not self.create_attempted and not self.created)
            )
        )
        if not valid:
            raise ValueError("unattended storage target result is invalid")


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedStorageProvisioningResult:
    """Aggregate immutable non-authorizing evidence for one bounded operation."""

    status: PersonalDesktopUnattendedStorageProvisioningStatus
    diagnostic: PersonalDesktopUnattendedStorageProvisioningDiagnostic
    decision_target: PersonalDesktopUnattendedStorageTargetResult
    invocation_target: PersonalDesktopUnattendedStorageTargetResult
    failed_target_role: security.PaperObjectRole | None

    def __post_init__(self) -> None:
        statuses = PersonalDesktopUnattendedStorageProvisioningStatus
        diagnostics = PersonalDesktopUnattendedStorageProvisioningDiagnostic
        targets = (self.decision_target, self.invocation_target)
        if self.status is statuses.PROVISIONED:
            valid_outcome = (
                self.diagnostic is diagnostics.PROVISIONED_AND_VERIFIED
                and self.failed_target_role is None
                and all(target.verified for target in targets)
                and any(target.created for target in targets)
            )
        elif self.status is statuses.ALREADY_PROVISIONED:
            valid_outcome = (
                self.diagnostic is diagnostics.VERIFIED_ALREADY_PROVISIONED
                and self.failed_target_role is None
                and all(target.verified for target in targets)
                and not any(target.create_attempted for target in targets)
            )
        else:
            valid_outcome = self.status is statuses.BLOCKED and self.diagnostic in {
                diagnostics.QUALIFICATION_BLOCKED,
                diagnostics.EFFECT_STATE_BLOCKED,
                diagnostics.PRE_CREATE_REVALIDATION_BLOCKED,
                diagnostics.CREATE_FAILED_OR_UNCERTAIN,
                diagnostics.POST_CREATE_VERIFICATION_BLOCKED,
                diagnostics.FINAL_REVERIFICATION_BLOCKED,
            }
        if (
            type(self.status) is not PersonalDesktopUnattendedStorageProvisioningStatus
            or type(self.diagnostic)
            is not PersonalDesktopUnattendedStorageProvisioningDiagnostic
            or type(self.decision_target)
            is not PersonalDesktopUnattendedStorageTargetResult
            or type(self.invocation_target)
            is not PersonalDesktopUnattendedStorageTargetResult
            or self.decision_target.target_role
            is not security.PaperObjectRole.UNATTENDED_DECISIONS
            or self.invocation_target.target_role
            is not security.PaperObjectRole.UNATTENDED_INVOCATIONS
            or self.failed_target_role not in ({None} | _TARGET_ROLES)
            or (
                self.failed_target_role is not None
                and type(self.failed_target_role) is not security.PaperObjectRole
            )
            or not valid_outcome
        ):
            raise ValueError("unattended storage provisioning result is invalid")


class _ProvisioningReadNativeApi(security.PaperReadNativeApi, Protocol):
    def fixed_child_present(self, target: _ProvisioningTarget) -> bool: ...


class _ProvisioningMutationNativeApi(_ProvisioningReadNativeApi, Protocol):
    def create_fixed_child(self, target: _ProvisioningTarget) -> None: ...


@dataclass(frozen=True, slots=True)
class _PinnedParent:
    handle: object
    spec: security.PaperObjectSpec
    observation: security.PaperObjectObservation


class _PinnedProvisioningParent:
    """Hold and revalidate the complete fixed chain needed for both children."""

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


def _require_source_target(target: _ProvisioningTarget) -> None:
    if not any(target is candidate for candidate in _TARGETS):
        raise AuthorityPathError("unattended provisioning target is not source-owned")
    spec = security.paper_object_spec(target.path)
    if spec.role is not target.role or spec.kind is not AuthorityObjectKind.DIRECTORY:
        raise AuthorityPathError("unattended provisioning target role is not exact")


def _validate_target_observation(
    target: _ProvisioningTarget,
    observation: security.PaperObjectObservation,
) -> None:
    _require_source_target(target)
    spec = security.paper_object_spec(target.path)
    security.require_paper_object_security(
        target.path, spec, observation.security, _TRADING_SID
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


def _fixed_target_policy(target: _ProvisioningTarget) -> SecurityPolicy:
    """Return the frozen role-specific policy for one source-owned container."""

    _require_source_target(target)
    return security.paper_security_policy(target.role, _TRADING_SID)


def _verify_empty_target(
    api: _ProvisioningReadNativeApi, target: _ProvisioningTarget
) -> None:
    """Pin, inspect, inventory, and independently reopen one fixed child."""

    _require_source_target(target)
    spec = security.paper_object_spec(target.path)
    handle = api.open(target.path, spec.kind)
    try:
        observation = api.inspect(handle, target.path, spec.kind)
        _validate_target_observation(target, observation)
        if api.names(handle, target.path, 1) != ():
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "unattended provisioning target is not empty"
            )
        current = api.inspect(handle, target.path, spec.kind)
        _validate_target_observation(target, current)
        if (
            current.identity != observation.identity
            or current.security != observation.security
        ):
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "unattended provisioning target identity/security drift"
            )
        reopened = api.open(target.path, spec.kind)
        try:
            independent = api.inspect(reopened, target.path, spec.kind)
            _validate_target_observation(target, independent)
            if (
                independent.identity != observation.identity
                or independent.security != observation.security
                or api.names(reopened, target.path, 1) != ()
            ):
                raise PersonalDesktopUnattendedStorageProvisioningError(
                    "unattended provisioning target named object changed"
                )
        finally:
            api.close(reopened)
        if api.names(handle, target.path, 1) != ():
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "unattended provisioning target inventory drift"
            )
    finally:
        api.close(handle)


def _classify_target(
    api: _ProvisioningReadNativeApi, target: _ProvisioningTarget
) -> PersonalDesktopUnattendedStorageProvisioningClassification:
    _require_source_target(target)
    if api.fixed_child_present(target) is False:
        return PersonalDesktopUnattendedStorageProvisioningClassification.MISSING
    _verify_empty_target(api, target)
    return (
        PersonalDesktopUnattendedStorageProvisioningClassification.ALREADY_PROVISIONED
    )


def _target_qualification(
    target: _ProvisioningTarget,
    classification: PersonalDesktopUnattendedStorageProvisioningClassification,
) -> PersonalDesktopUnattendedStorageTargetQualification:
    classifications = PersonalDesktopUnattendedStorageProvisioningClassification
    diagnostics = PersonalDesktopUnattendedStorageProvisioningDiagnostic
    return PersonalDesktopUnattendedStorageTargetQualification(
        classification=classification,
        diagnostic={
            classifications.MISSING: diagnostics.VERIFIED_MISSING,
            classifications.ALREADY_PROVISIONED: (
                diagnostics.VERIFIED_ALREADY_PROVISIONED
            ),
            classifications.BLOCKED: diagnostics.QUALIFICATION_BLOCKED,
        }[classification],
        target_role=target.role,
        child_present=classification is classifications.ALREADY_PROVISIONED,
    )


def _classify_both_targets(
    api: _ProvisioningReadNativeApi,
) -> tuple[
    PersonalDesktopUnattendedStorageTargetQualification,
    PersonalDesktopUnattendedStorageTargetQualification,
]:
    evidence: list[PersonalDesktopUnattendedStorageTargetQualification] = []
    for target in _TARGETS:
        try:
            classification = _classify_target(api, target)
        except Exception:
            classification = (
                PersonalDesktopUnattendedStorageProvisioningClassification.BLOCKED
            )
        evidence.append(_target_qualification(target, classification))
    return evidence[0], evidence[1]


def _qualification_result(
    decision_target: PersonalDesktopUnattendedStorageTargetQualification,
    invocation_target: PersonalDesktopUnattendedStorageTargetQualification,
) -> PersonalDesktopUnattendedStorageProvisioningQualification:
    classifications = PersonalDesktopUnattendedStorageProvisioningClassification
    diagnostics = PersonalDesktopUnattendedStorageProvisioningDiagnostic
    target_states = (
        decision_target.classification,
        invocation_target.classification,
    )
    if classifications.BLOCKED in target_states:
        classification = classifications.BLOCKED
        diagnostic = diagnostics.QUALIFICATION_BLOCKED
    elif target_states == (
        classifications.ALREADY_PROVISIONED,
        classifications.ALREADY_PROVISIONED,
    ):
        classification = classifications.ALREADY_PROVISIONED
        diagnostic = diagnostics.VERIFIED_ALREADY_PROVISIONED
    else:
        classification = classifications.MISSING
        diagnostic = diagnostics.VERIFIED_MISSING
    return PersonalDesktopUnattendedStorageProvisioningQualification(
        classification=classification,
        diagnostic=diagnostic,
        decision_target=decision_target,
        invocation_target=invocation_target,
    )


def _blocked_qualification() -> (
    PersonalDesktopUnattendedStorageProvisioningQualification
):
    blocked = PersonalDesktopUnattendedStorageProvisioningClassification.BLOCKED
    return _qualification_result(
        _target_qualification(_DECISION_TARGET, blocked),
        _target_qualification(_INVOCATION_TARGET, blocked),
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


def _qualify(
    observer: TradingTokenObserver,
    api_factory: Callable[[], _ProvisioningReadNativeApi],
) -> PersonalDesktopUnattendedStorageProvisioningQualification:
    try:
        initial = _observe_administrator(observer)
        api = api_factory()
        with _PinnedProvisioningParent(api) as parent:
            targets = _classify_both_targets(api)
            parent.finish()
        _require_unchanged_administrator(observer, initial)
        return _qualification_result(*targets)
    except Exception:
        return _blocked_qualification()


def qualify_personal_desktop_unattended_storage_provisioning() -> (
    PersonalDesktopUnattendedStorageProvisioningQualification
):
    """Administrator-only read of both fixed production targets."""

    return _qualify(WindowsTradingTokenObserver(), _WindowsProvisioningReadNativeApi)


def _gate_state() -> tuple[bool, bool, bool, bool, bool, bool, bool, bool]:
    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_paper_receipt_recovery_execution as receipt,
    )
    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_supervised_paper_operation_execution as supervised,
    )
    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_unattended_market_data_capture as capture,
    )
    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_unattended_paper_decision_publication as publication,
    )
    from trading_bot.runtime import (  # noqa: PLC0415
        personal_desktop_unattended_paper_operation_execution as unattended,
    )

    return (
        capture.PERSONAL_DESKTOP_UNATTENDED_MARKET_DATA_CAPTURE_EFFECTS_ENABLED,
        publication.PERSONAL_DESKTOP_UNATTENDED_DECISION_PUBLICATION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED,
        security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED,
        supervised.PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED,
        receipt.PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED,
        unattended.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED,
        PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_STORAGE_PROVISIONING_EFFECTS_ENABLED,
    )


def _require_closed_committed_gate_state() -> None:
    if not _gate_state_is((False, False, False, False, False, False, False, False)):
        raise PersonalDesktopUnattendedStorageProvisioningError(
            "committed unattended Paper-v2 effect-gate state is invalid"
        )


def _gate_state_is(
    required: tuple[bool, bool, bool, bool, bool, bool, bool, bool],
) -> bool:
    return all(
        observed is expected
        for observed, expected in zip(_gate_state(), required, strict=True)
    )


class _ProductionProvisioningEffectAuthority:
    def begin(self) -> None:
        if not _gate_state_is((False, False, False, False, False, False, False, True)):
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


def _initial_target_result(
    evidence: PersonalDesktopUnattendedStorageTargetQualification,
) -> PersonalDesktopUnattendedStorageTargetResult:
    classifications = PersonalDesktopUnattendedStorageProvisioningClassification
    return PersonalDesktopUnattendedStorageTargetResult(
        qualification=evidence.classification,
        target_role=evidence.target_role,
        create_attempted=False,
        created=False,
        verified=evidence.classification is classifications.ALREADY_PROVISIONED,
    )


def _result(
    status: PersonalDesktopUnattendedStorageProvisioningStatus,
    diagnostic: PersonalDesktopUnattendedStorageProvisioningDiagnostic,
    target_results: dict[
        security.PaperObjectRole, PersonalDesktopUnattendedStorageTargetResult
    ],
    *,
    failed_target_role: security.PaperObjectRole | None = None,
) -> PersonalDesktopUnattendedStorageProvisioningResult:
    return PersonalDesktopUnattendedStorageProvisioningResult(
        status=status,
        diagnostic=diagnostic,
        decision_target=target_results[security.PaperObjectRole.UNATTENDED_DECISIONS],
        invocation_target=target_results[
            security.PaperObjectRole.UNATTENDED_INVOCATIONS
        ],
        failed_target_role=failed_target_role,
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
    current_target: _ProvisioningTarget | None = None
    target_results = {
        target.role: PersonalDesktopUnattendedStorageTargetResult(
            classifications.BLOCKED, target.role, False, False, False
        )
        for target in _TARGETS
    }
    try:
        initial = _observe_administrator(observer)
        read_api = read_api_factory()
        with _PinnedProvisioningParent(read_api) as parent:
            qualification = _qualification_result(*_classify_both_targets(read_api))
            target_evidence = (
                qualification.decision_target,
                qualification.invocation_target,
            )
            target_results = {
                evidence.target_role: _initial_target_result(evidence)
                for evidence in target_evidence
            }
            parent.finish()
            if qualification.classification is classifications.BLOCKED:
                current_target = next(
                    target
                    for target, evidence in zip(_TARGETS, target_evidence, strict=True)
                    if evidence.classification is classifications.BLOCKED
                )
                raise PersonalDesktopUnattendedStorageProvisioningError(
                    "fixed target qualification blocked"
                )
            missing = tuple(
                target
                for target, evidence in zip(_TARGETS, target_evidence, strict=True)
                if evidence.classification is classifications.MISSING
            )
            if not missing:
                _require_unchanged_administrator(observer, initial)
                return _result(
                    statuses.ALREADY_PROVISIONED,
                    diagnostics.VERIFIED_ALREADY_PROVISIONED,
                    target_results,
                )

            phase = "effect"
            effect_authority.begin()
            mutation_api: _ProvisioningMutationNativeApi | None = None
            for target in missing:
                current_target = target
                phase = "pre_create"
                _require_unchanged_administrator(observer, initial)
                parent.finish()

                if mutation_api is None:
                    mutation_api = mutation_api_factory()
                effect_authority.require_active()
                phase = "create"
                target_results[target.role] = replace(
                    target_results[target.role], create_attempted=True
                )
                mutation_api.create_fixed_child(target)
                target_results[target.role] = replace(
                    target_results[target.role], created=True
                )

                phase = "verify"
                _verify_empty_target(mutation_api, target)
                parent.finish()
                effect_authority.require_active()
                target_results[target.role] = replace(
                    target_results[target.role], verified=True
                )

            phase = "reverify"
            for target in _TARGETS:
                current_target = target
                target_results[target.role] = replace(
                    target_results[target.role], verified=False
                )
                _verify_empty_target(read_api, target)
                target_results[target.role] = replace(
                    target_results[target.role], verified=True
                )
            current_target = None
            parent.finish()
            effect_authority.require_active()
        current_target = None
        _require_unchanged_administrator(observer, initial)
        effect_authority.require_active()
        return _result(
            statuses.PROVISIONED,
            diagnostics.PROVISIONED_AND_VERIFIED,
            target_results,
        )
    except Exception:
        diagnostic = {
            "qualification": diagnostics.QUALIFICATION_BLOCKED,
            "effect": diagnostics.EFFECT_STATE_BLOCKED,
            "pre_create": diagnostics.PRE_CREATE_REVALIDATION_BLOCKED,
            "create": diagnostics.CREATE_FAILED_OR_UNCERTAIN,
            "verify": diagnostics.POST_CREATE_VERIFICATION_BLOCKED,
            "reverify": diagnostics.FINAL_REVERIFICATION_BLOCKED,
        }[phase]
        return _result(
            statuses.BLOCKED,
            diagnostic,
            target_results,
            failed_target_role=None if current_target is None else current_target.role,
        )


def provision_personal_desktop_unattended_storage() -> (
    PersonalDesktopUnattendedStorageProvisioningResult
):
    """Provision only the two fixed targets; accepts no caller authority overrides."""

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
    """No-follow presence probes for only the two fixed provisioning children."""

    def fixed_child_present(self, target: _ProvisioningTarget) -> bool:
        _require_source_target(target)
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
            target.path,
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
    """One create-new attempt per fixed child with its frozen container policy."""

    def __init__(self) -> None:
        _ProductionProvisioningEffectAuthority().require_active()
        super().__init__()
        self._attempted: set[security.PaperObjectRole] = set()

    def create_fixed_child(self, target: _ProvisioningTarget) -> None:
        _ProductionProvisioningEffectAuthority().require_active()
        _require_source_target(target)
        if target.role in self._attempted:
            raise PersonalDesktopUnattendedStorageProvisioningError(
                "fixed unattended target creation was already attempted"
            )
        self._attempted.add(target.role)
        create = _bind(
            self._kernel,
            "CreateDirectoryW",
            [ctypes.c_wchar_p, ctypes.c_void_p],
            ctypes.c_int32,
        )
        with build_security_attributes(_fixed_target_policy(target)) as attributes:
            if not create(target.path, ctypes.byref(attributes.attributes)):
                raise PersonalDesktopUnattendedStorageProvisioningError(
                    "fixed unattended target create-new failed or was uncertain"
                )
