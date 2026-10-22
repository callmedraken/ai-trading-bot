"""D1S2 installed-release and manual-start readiness composition.

This module is a pure, read-only bridge.  It binds an explicitly supplied
accepted source policy to the existing Architecture-133 release primitives,
then composes the existing Architecture-133 -> F1R1-A -> F1R1-B -> D1
admission order through injected observers.  It has no installation,
provisioning, scheduler, credential, provider, paper, broker, or live
capability.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Protocol

from trading_bot.arch133_acl.read_only import ADMINISTRATORS_SID
from trading_bot.review_paper.successor_soak_admission import (
    ManualAdmission,
    ManualProcessObservation,
    ManualStartBoundary,
    StoreObservation,
)
from trading_bot.review_paper.successor_soak_contract import (
    PRODUCTION_ROOT,
    SESSION_NAMES,
    SESSIONS,
    STORE_IDENTITY,
    SuccessorLineage,
)
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    VerifiedRelease,
    source_namespace,
    verify_release_bundle,
)
from trading_bot.supervised_release.installation_contract import (
    IMAGE_ACES,
    InstalledEvidence,
    ObserverNative,
    ReleasePaths,
)
from trading_bot.supervised_release.model import (
    DURABLE_DATA_ROOT,
    LAUNCHER_RELATIVE_PATH,
    PRODUCTION_PYTHON,
)
from trading_bot.supervised_release.observer import replay_inputs
from trading_bot.supervised_release.runtime_admission import RuntimeObserver
from trading_bot.supervised_release.runtime_host_composition import (
    Architecture133HostBinding,
    HostQualificationReadiness,
    assess_host_qualification_readiness,
)
from trading_bot.supervised_release.runtime_isolation import (
    ProductionOperatorState,
    RuntimeAdmissionStatus,
    admit_installed_runtime,
    production_manual_start,
    production_state_after_boot_or_login,
)
from trading_bot.supervised_release.runtime_isolation import (
    RuntimeAdmissionResult as F1R1ARuntimeAdmissionResult,
)

READINESS_SCHEMA = "arch134-f1r1-d1s2-successor-installed-readiness/v1"
SOURCE_POLICY_SCHEMA = "arch134-f1r1-d1s2-successor-source-policy/v1"
SOURCE_REMOTE = "https://github.com/callmedraken/ai-trading-bot.git"
SUCCESSOR_PARENT = DURABLE_DATA_ROOT
LAUNCHER_RUNTIME_STATUS = "INERT_FAIL_CLOSED"
LAUNCHER_EFFECT_STATUS = "NO_PROVIDER_OR_PAPER_WIRING"

# These are policy names, not mutable counters.  A readiness result carries
# them as closed zero evidence and never exposes a way to increment them.
ZERO_PROTECTED_EFFECTS = (
    ("PRODUCTION_INSTALLATION_EFFECTS", 0),
    ("PRODUCTION_RELEASE_PUBLICATIONS", 0),
    ("SUCCESSOR_STORE_PROVISIONING", 0),
    ("SCHEDULER_READS", 0),
    ("SCHEDULER_MUTATIONS", 0),
    ("REAL_CREDENTIAL_READS", 0),
    ("PROVIDER_REQUESTS", 0),
    ("PAPER_MUTATIONS", 0),
    ("BROKER_EFFECTS", 0),
    ("D1_OPERATIONAL_EFFECTS", 0),
    ("D2_EFFECTS", 0),
    ("LIVE_EFFECTS", 0),
)


def _digest(value: object, *, length: int = 64) -> None:
    if (
        type(value) is not str
        or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None
        or (length == 40 and set(value) == {"0"})
    ):
        raise ValueError("canonical nonzero digest required")


def _identity(value: object, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if (
        type(value) is not tuple
        or len(value) != 2
        or any(type(part) is not int or part <= 0 for part in value)
    ):
        raise ValueError("positive object identity required")


def _canonical_path(value: object) -> bool:
    if type(value) is not str or not value or value.startswith("\\\\"):
        return False
    path = PureWindowsPath(value)
    return str(path) == value and ".." not in path.parts


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class SuccessorSourcePolicy:
    """Explicit accepted-source declaration supplied after source review.

    No future HEAD or tree is guessed here.  A protected operator must supply
    the exact accepted source identities and prove the same remote/ref before
    constructing a release bundle.
    """

    source_remote: str
    source_ref: str
    accepted_head: str
    accepted_tree: str
    source_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.source_remote != SOURCE_REMOTE:
            raise ValueError("accepted repository remote mismatch")
        if (
            type(self.source_ref) is not str
            or re.fullmatch(r"refs/(?:heads|tags)/[A-Za-z0-9._/-]+", self.source_ref)
            is None
            or ".." in self.source_ref.split("/")
        ):
            raise ValueError("canonical accepted source ref required")
        _digest(self.accepted_head, length=40)
        _digest(self.accepted_tree, length=40)
        source_namespace(self.source_paths)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SOURCE_POLICY_SCHEMA,
            "source_remote": self.source_remote,
            "source_ref": self.source_ref,
            "accepted_head": self.accepted_head,
            "accepted_tree": self.accepted_tree,
            "source_paths": list(self.source_paths),
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())


@dataclass(frozen=True, slots=True)
class SuccessorReleaseDeclaration:
    """A complete bundle/binding joined to the explicit accepted-source policy."""

    source_policy: SuccessorSourcePolicy
    release: VerifiedRelease
    binding: RuntimeBinding

    def __post_init__(self) -> None:
        if (
            type(self.source_policy) is not SuccessorSourcePolicy
            or type(self.release) is not VerifiedRelease
            or type(self.binding) is not RuntimeBinding
        ):
            raise ValueError("exact successor declaration inputs required")
        replay = verify_release_bundle(
            self.release.bundle,
            expected_manifest_sha256=self.release.expected_manifest_sha256,
            expected_source_head=self.release.expected_source_head,
            expected_source_tree=self.release.expected_source_tree,
            expected_source_paths=self.release.expected_source_paths,
        )
        if replay != self.release or self.binding.verified_release != replay:
            raise ValueError("successor release replay mismatch")
        RuntimeBinding.from_json(self.binding.to_json(), verified_release=replay)
        if (
            self.release.expected_source_head != self.source_policy.accepted_head
            or self.release.expected_source_tree != self.source_policy.accepted_tree
            or self.release.expected_source_paths != self.source_policy.source_paths
            or tuple(
                entry.relative_path for entry in self.release.manifest.source_inventory
            )
            != self.source_policy.source_paths
        ):
            raise ValueError("release is not bound to accepted successor source")

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(
            self.release.manifest.to_json().encode("utf-8")
        ).hexdigest()

    @property
    def release_id(self) -> str:
        return self.release.manifest.release_id

    @property
    def inventory_sha256(self) -> str:
        return self.release.manifest.source_inventory_sha256

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": READINESS_SCHEMA,
            "source_policy": self.source_policy.to_dict(),
            "source_head": self.source_policy.accepted_head,
            "source_tree": self.source_policy.accepted_tree,
            "source_paths": list(self.source_policy.source_paths),
            "release_id": self.release_id,
            "manifest_sha256": self.manifest_sha256,
            "inventory_sha256": self.inventory_sha256,
            "binding_sha256": self.binding.sha256,
            "launcher_relative_path": LAUNCHER_RELATIVE_PATH,
            "production_python": PRODUCTION_PYTHON,
        }


class InstallationReadiness(StrEnum):
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    ALREADY_INSTALLED_EXACT = "ALREADY_INSTALLED_EXACT"
    BLOCKED = "BLOCKED"
    INDETERMINATE = "INDETERMINATE"


class InstallationReason(StrEnum):
    FINAL_AND_STAGING_ABSENT = "FINAL_AND_STAGING_ABSENT"
    EXACT_FINAL = "EXACT_FINAL"
    FINAL_CONFLICT = "FINAL_CONFLICT"
    STAGING_CONFLICT = "STAGING_CONFLICT"
    REPLACED_OBJECT = "REPLACED_OBJECT"
    CONSUMED_EVIDENCE = "CONSUMED_EVIDENCE"
    MALFORMED_EVIDENCE = "MALFORMED_EVIDENCE"
    OBSERVATION_UNPROVEN = "OBSERVATION_UNPROVEN"


@dataclass(frozen=True, slots=True)
class InstallationObservation:
    """Read-only final/staging classification from an injected observer."""

    classification: InstallationReadiness
    reason: InstallationReason
    final_path: str
    staging_path: str
    final_identity: tuple[int, int] | None = None
    staging_identity: tuple[int, int] | None = None
    installed_evidence: InstalledEvidence | None = None

    def __post_init__(self) -> None:
        if (
            type(self.classification) is not InstallationReadiness
            or type(self.reason) is not InstallationReason
            or type(self.final_path) is not str
            or type(self.staging_path) is not str
        ):
            raise ValueError("closed installation observation required")
        _identity(self.final_identity, optional=True)
        _identity(self.staging_identity, optional=True)
        if (
            self.installed_evidence is not None
            and type(self.installed_evidence) is not InstalledEvidence
        ):
            raise ValueError("exact installed evidence required")


class SuccessorInstallationObserver(Protocol):
    """Injected read-only adapter; it cannot create, publish, or repair."""

    def observe(self, paths: ReleasePaths) -> InstallationObservation: ...


def observe_installation_readiness(
    declaration: SuccessorReleaseDeclaration,
    observer: SuccessorInstallationObserver,
) -> InstallationObservation:
    """Classify only the exact derived FINAL and .installing paths."""

    if not callable(getattr(observer, "observe", None)):
        raise TypeError("read-only installation observer required")
    paths = replay_inputs(declaration.release, declaration.binding)
    value = observer.observe(paths)
    if type(value) is not InstallationObservation:
        raise ValueError("exact installation observation required")
    if value.final_path != paths.final or value.staging_path != paths.staging:
        raise ValueError("installation paths are not the exact derived paths")
    if value.classification is InstallationReadiness.INSTALL_REQUIRED:
        if (
            value.reason is not InstallationReason.FINAL_AND_STAGING_ABSENT
            or value.final_identity is not None
            or value.staging_identity is not None
            or value.installed_evidence is not None
        ):
            raise ValueError("install-required observation is not exact")
    elif value.classification is InstallationReadiness.ALREADY_INSTALLED_EXACT:
        installed = value.installed_evidence
        if (
            value.reason is not InstallationReason.EXACT_FINAL
            or value.final_identity is None
            or value.staging_identity is not None
            or installed is None
            or installed.release_id != declaration.release_id
        ):
            # The explicit checks below avoid accepting evidence that merely
            # carries the right release ID; all overlapping identities matter.
            raise ValueError("exact installed observation is incomplete")
        if (
            installed.manifest_sha256 != declaration.manifest_sha256
            or installed.binding_sha256 != declaration.binding.sha256
            or installed.image_identity != value.final_identity
            or installed.dependency_closure != "UNPROVEN"
        ):
            raise ValueError("installed evidence identity mismatch")
    elif value.classification is InstallationReadiness.BLOCKED:
        if value.installed_evidence is not None:
            raise ValueError("blocked installation cannot carry positive evidence")
    elif value.classification is InstallationReadiness.INDETERMINATE:
        if value.installed_evidence is not None:
            raise ValueError(
                "indeterminate installation cannot carry positive evidence"
            )
    return value


class SuccessorStoreClassification(StrEnum):
    ABSENT_ELIGIBLE = "ABSENT_ELIGIBLE"
    EMPTY_FRESH_ADMITTED = "EMPTY_FRESH_ADMITTED"
    ALREADY_BOUND_EXACT = "ALREADY_BOUND_EXACT"
    CONFLICTING_FOREIGN = "CONFLICTING_FOREIGN"
    ALIAS_OR_REPARSE = "ALIAS_OR_REPARSE"
    WRONG_PARENT_OR_POLICY = "WRONG_PARENT_OR_POLICY"
    REPLACED_OBJECT = "REPLACED_OBJECT"
    CONSUMED = "CONSUMED"
    MALFORMED = "MALFORMED"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True, slots=True)
class SuccessorRootObservation:
    """Closed facts for the exact future durable successor namespace."""

    classification: SuccessorStoreClassification
    path: str = PRODUCTION_ROOT
    final_path: str = PRODUCTION_ROOT
    parent: str = SUCCESSOR_PARENT
    kind: str = "directory"
    identity: tuple[int, int] | None = None
    parent_identity: tuple[int, int] | None = None
    filesystem: str = "NTFS"
    local: bool = True
    reparse: bool = False
    links: int = 1
    owner: str = ADMINISTRATORS_SID
    protected: bool = True
    aces: tuple[tuple[str, int, int, int], ...] = IMAGE_ACES
    names: tuple[str, ...] = ()
    store_identity: object | None = None
    evidence_complete: bool = False
    consumed: bool = False
    malformed: bool = False
    stable: bool = True

    def __post_init__(self) -> None:
        if type(self.classification) is not SuccessorStoreClassification:
            raise ValueError("closed successor store classification required")
        _identity(self.identity, optional=True)
        _identity(self.parent_identity, optional=True)
        if self.store_identity is not None and type(self.store_identity) is not type(
            STORE_IDENTITY
        ):
            raise ValueError("exact durable store identity required")
        if type(self.names) is not tuple or any(
            type(name) is not str for name in self.names
        ):
            raise ValueError("closed successor namespace required")


class SuccessorRootObserver(Protocol):
    """Injected native/read-only successor-root and process observer."""

    def observe_root(self) -> SuccessorRootObservation: ...

    def observe_manual_process(self) -> ManualProcessObservation: ...


def _exact_successor_root(value: SuccessorRootObservation) -> bool:
    if (
        value.classification
        not in {
            SuccessorStoreClassification.EMPTY_FRESH_ADMITTED,
            SuccessorStoreClassification.ALREADY_BOUND_EXACT,
        }
        or value.path != PRODUCTION_ROOT
        or value.final_path != PRODUCTION_ROOT
        or value.parent != SUCCESSOR_PARENT
        or value.kind != "directory"
        or value.filesystem != "NTFS"
        or value.local is not True
        or value.reparse is not False
        or value.links != 1
        or value.owner != ADMINISTRATORS_SID
        or value.protected is not True
        or value.aces != IMAGE_ACES
        or value.stable is not True
        or value.identity is None
        or value.parent_identity is None
    ):
        return False
    if value.classification is SuccessorStoreClassification.EMPTY_FRESH_ADMITTED:
        return (
            value.names == ()
            and value.store_identity is None
            and value.evidence_complete is False
            and value.consumed is False
            and value.malformed is False
        )
    return (
        value.names == ("successor-parent-v1.jsonl", *SESSION_NAMES)
        and value.store_identity == STORE_IDENTITY
        and value.evidence_complete is True
        and value.consumed is False
        and value.malformed is False
    )


class StoreObservationError(ValueError):
    """A successor-root observation cannot satisfy the exact D1 namespace."""

    def __init__(
        self, classification: SuccessorStoreClassification, *, drift: bool = False
    ):
        super().__init__(classification.value)
        self.classification = classification
        self.drift = drift


class _BridgeSuccessorObserver:
    def __init__(self, observer: SuccessorRootObserver):
        self._observer = observer
        self.last_root: SuccessorRootObservation | None = None
        self.last_process: ManualProcessObservation | None = None
        self._last_store: StoreObservation | None = None

    def observe_store(self) -> StoreObservation:
        root = self._observer.observe_root()
        if type(root) is not SuccessorRootObservation:
            raise StoreObservationError(SuccessorStoreClassification.INDETERMINATE)
        self.last_root = root
        if not _exact_successor_root(root):
            raise StoreObservationError(root.classification)
        store = StoreObservation(
            root.path,
            root.final_path,
            root.parent,
            True,
            True,
            True,
            True,
            root.identity,
        )
        if self._last_store is not None and store != self._last_store:
            raise StoreObservationError(
                SuccessorStoreClassification.REPLACED_OBJECT, drift=True
            )
        self._last_store = store
        return store

    def observe_manual_process(self) -> ManualProcessObservation:
        process = self._observer.observe_manual_process()
        if type(process) is not ManualProcessObservation:
            raise ValueError("exact manual process observation required")
        if process.observed_date not in SESSIONS:
            raise ValueError("manual process date is outside the fixed D1 tuple")
        self.last_process = process
        return process


@dataclass(frozen=True, slots=True)
class SuccessorReadinessBoundary:
    """Pure inputs for a source-only installed-release readiness observation."""

    source_policy: SuccessorSourcePolicy
    release: VerifiedRelease
    binding: RuntimeBinding
    installation_observer: SuccessorInstallationObserver
    image_observer: ObserverNative
    runtime_observer: RuntimeObserver
    successor_observer: SuccessorRootObserver


class ReadinessStatus(StrEnum):
    READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT = (
        "READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT"
    )
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    BLOCKED = "BLOCKED"
    INDETERMINATE = "INDETERMINATE"


class ReadinessReason(StrEnum):
    VERIFIED = "VERIFIED"
    SOURCE_POLICY_REJECTED = "SOURCE_POLICY_REJECTED"
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    INSTALLATION_BLOCKED = "INSTALLATION_BLOCKED"
    INSTALLATION_UNPROVEN = "INSTALLATION_UNPROVEN"
    SUCCESSOR_STORE_NOT_READY = "SUCCESSOR_STORE_NOT_READY"
    SUCCESSOR_STORE_UNPROVEN = "SUCCESSOR_STORE_UNPROVEN"
    SUCCESSOR_STORE_DRIFT = "SUCCESSOR_STORE_DRIFT"
    HOST_ADMISSION_REJECTED = "HOST_ADMISSION_REJECTED"
    MANUAL_PROCESS_REJECTED = "MANUAL_PROCESS_REJECTED"


@dataclass(frozen=True, slots=True)
class SuccessorReadinessResult:
    status: ReadinessStatus
    reason: ReadinessReason
    declaration: SuccessorReleaseDeclaration | None = None
    installation: InstallationObservation | None = None
    host: Architecture133HostBinding | None = None
    f1r1_a: F1R1ARuntimeAdmissionResult | None = None
    f1r1_b: HostQualificationReadiness | None = None
    lineage: SuccessorLineage | None = None
    store: SuccessorRootObservation | None = None
    process: ManualProcessObservation | None = None
    manual_start_state: tuple[str, str, str] | None = None
    launcher_runtime_status: str = LAUNCHER_RUNTIME_STATUS
    launcher_effect_status: str = LAUNCHER_EFFECT_STATUS
    protected_effects: tuple[tuple[str, int], ...] = ZERO_PROTECTED_EFFECTS

    def __post_init__(self) -> None:
        if (
            type(self.status) is not ReadinessStatus
            or type(self.reason) is not ReadinessReason
        ):
            raise ValueError("closed readiness result required")
        if (
            self.launcher_runtime_status != LAUNCHER_RUNTIME_STATUS
            or self.launcher_effect_status != LAUNCHER_EFFECT_STATUS
        ):
            raise ValueError("launcher capability classification drift")
        if self.protected_effects != ZERO_PROTECTED_EFFECTS:
            raise ValueError("protected effects must remain zero")
        if (
            self.status
            is ReadinessStatus.READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT
        ):
            if (
                self.reason is not ReadinessReason.VERIFIED
                or self.declaration is None
                or self.installation is None
                or self.installation.classification
                is not InstallationReadiness.ALREADY_INSTALLED_EXACT
                or self.installation.installed_evidence is None
                or self.installation.final_identity is None
                or self.installation.staging_identity is not None
                or type(self.host) is not Architecture133HostBinding
                or self.f1r1_a is None
                or self.f1r1_a.status is not RuntimeAdmissionStatus.ADMITTED
                or self.f1r1_b
                is not HostQualificationReadiness.READY_FOR_F1R1_HOST_QUALIFICATION
                or type(self.lineage) is not SuccessorLineage
                or self.store is None
                or not _exact_successor_root(self.store)
                or type(self.process) is not ManualProcessObservation
                or self.process.observed_date not in SESSIONS
                or self.lineage.material.durable_store_identities != (STORE_IDENTITY,)
                or self.manual_start_state != ("RUNNING", "STOPPED", "RUNNING")
            ):
                raise ValueError("positive readiness proof is incomplete")
            paths = replay_inputs(self.declaration.release, self.declaration.binding)
            evidence = self.installation.installed_evidence
            if (
                self.installation.final_path != paths.final
                or self.installation.staging_path != paths.staging
                or evidence.release_id != self.declaration.release_id
                or evidence.manifest_sha256 != self.declaration.manifest_sha256
                or evidence.binding_sha256 != self.declaration.binding.sha256
                or evidence.image_identity != self.installation.final_identity
                or evidence.dependency_closure != "UNPROVEN"
            ):
                raise ValueError("positive installed-release proof is incomplete")

    @property
    def ready(self) -> bool:
        return (
            self.status
            is ReadinessStatus.READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT
        )

    def to_json(self) -> str:
        return _canonical_json(
            {
                "schema": READINESS_SCHEMA,
                "status": self.status.value,
                "reason": self.reason.value,
                "source_head": (
                    self.declaration.source_policy.accepted_head
                    if self.declaration
                    else None
                ),
                "source_tree": (
                    self.declaration.source_policy.accepted_tree
                    if self.declaration
                    else None
                ),
                "release_id": self.declaration.release_id if self.declaration else None,
                "manifest_sha256": self.declaration.manifest_sha256
                if self.declaration
                else None,
                "installation": self.installation.classification.value
                if self.installation
                else None,
                "store": self.store.classification.value if self.store else None,
                "runtime_id": self.host.runtime_id if self.host else None,
                "process_date": self.process.observed_date if self.process else None,
                "launcher_runtime_status": self.launcher_runtime_status,
                "launcher_effect_status": self.launcher_effect_status,
                "protected_effects": [list(item) for item in self.protected_effects],
            }
        )


def _result(
    status: ReadinessStatus,
    reason: ReadinessReason,
    *,
    declaration: SuccessorReleaseDeclaration | None = None,
    installation: InstallationObservation | None = None,
    store: SuccessorRootObservation | None = None,
    process: ManualProcessObservation | None = None,
) -> SuccessorReadinessResult:
    return SuccessorReadinessResult(
        status,
        reason,
        declaration=declaration,
        installation=installation,
        store=store,
        process=process,
    )


def assess_successor_readiness(
    boundary: SuccessorReadinessBoundary,
) -> SuccessorReadinessResult:
    """Return a closed read-only D1S2 result; never install or start anything."""

    try:
        declaration = SuccessorReleaseDeclaration(
            boundary.source_policy, boundary.release, boundary.binding
        )
    except (TypeError, ValueError, KeyError, ArithmeticError):
        return _result(ReadinessStatus.BLOCKED, ReadinessReason.SOURCE_POLICY_REJECTED)

    try:
        installation = observe_installation_readiness(
            declaration, boundary.installation_observer
        )
    except (TypeError, ValueError, KeyError, ArithmeticError):
        return _result(
            ReadinessStatus.BLOCKED,
            ReadinessReason.INSTALLATION_BLOCKED,
            declaration=declaration,
        )
    except Exception:
        return _result(
            ReadinessStatus.INDETERMINATE,
            ReadinessReason.INSTALLATION_UNPROVEN,
            declaration=declaration,
        )

    if installation.classification is InstallationReadiness.INSTALL_REQUIRED:
        return _result(
            ReadinessStatus.INSTALL_REQUIRED,
            ReadinessReason.INSTALL_REQUIRED,
            declaration=declaration,
            installation=installation,
        )
    if installation.classification is InstallationReadiness.BLOCKED:
        return _result(
            ReadinessStatus.BLOCKED,
            ReadinessReason.INSTALLATION_BLOCKED,
            declaration=declaration,
            installation=installation,
        )
    if installation.classification is InstallationReadiness.INDETERMINATE:
        return _result(
            ReadinessStatus.INDETERMINATE,
            ReadinessReason.INSTALLATION_UNPROVEN,
            declaration=declaration,
            installation=installation,
        )

    bridge = _BridgeSuccessorObserver(boundary.successor_observer)
    try:
        manual: ManualAdmission = ManualStartBoundary(
            declaration.release,
            declaration.binding,
            installation.installed_evidence,
            boundary.image_observer,
            boundary.runtime_observer,
            bridge,
        ).admit()
        root = bridge.last_root
        process = bridge.last_process
        if root is None or process is None:
            raise ValueError("successor observations incomplete")
        a_result = admit_installed_runtime(
            manual.host.material,
            expected_runtime_id=manual.host.runtime_id,
            expected_state_identities=(STORE_IDENTITY,),
        )
        if a_result.status is not RuntimeAdmissionStatus.ADMITTED:
            raise ValueError("fresh F1R1-A admission required")
        b_result = assess_host_qualification_readiness(manual.host)
        if b_result is not HostQualificationReadiness.READY_FOR_F1R1_HOST_QUALIFICATION:
            raise ValueError("fresh F1R1-B readiness required")
        stopped = production_state_after_boot_or_login(ProductionOperatorState.RUNNING)
        running = production_manual_start(stopped, a_result)
        if running is not ProductionOperatorState.RUNNING:
            raise ValueError("manual-start readiness transition rejected")
        return SuccessorReadinessResult(
            ReadinessStatus.READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT,
            ReadinessReason.VERIFIED,
            declaration=declaration,
            installation=installation,
            host=manual.host,
            f1r1_a=a_result,
            f1r1_b=b_result,
            lineage=manual.lineage,
            store=root,
            process=process,
            manual_start_state=("RUNNING", "STOPPED", "RUNNING"),
        )
    except StoreObservationError as exc:
        if exc.classification is SuccessorStoreClassification.INDETERMINATE:
            status, reason = (
                ReadinessStatus.INDETERMINATE,
                ReadinessReason.SUCCESSOR_STORE_UNPROVEN,
            )
        elif exc.drift:
            status, reason = (
                ReadinessStatus.BLOCKED,
                ReadinessReason.SUCCESSOR_STORE_DRIFT,
            )
        else:
            status, reason = (
                ReadinessStatus.BLOCKED,
                ReadinessReason.SUCCESSOR_STORE_NOT_READY,
            )
        return _result(
            status,
            reason,
            declaration=declaration,
            installation=installation,
            store=bridge.last_root,
            process=bridge.last_process,
        )
    except (TypeError, ValueError, KeyError, ArithmeticError):
        return _result(
            ReadinessStatus.BLOCKED,
            ReadinessReason.HOST_ADMISSION_REJECTED,
            declaration=declaration,
            installation=installation,
            store=bridge.last_root,
            process=bridge.last_process,
        )
    except Exception:
        return _result(
            ReadinessStatus.INDETERMINATE,
            ReadinessReason.SUCCESSOR_STORE_UNPROVEN,
            declaration=declaration,
            installation=installation,
            store=bridge.last_root,
            process=bridge.last_process,
        )


__all__ = [
    "InstallationObservation",
    "InstallationReadiness",
    "InstallationReason",
    "LAUNCHER_EFFECT_STATUS",
    "LAUNCHER_RUNTIME_STATUS",
    "ReadinessReason",
    "ReadinessStatus",
    "SOURCE_POLICY_SCHEMA",
    "SOURCE_REMOTE",
    "SuccessorInstallationObserver",
    "SuccessorReadinessBoundary",
    "SuccessorReadinessResult",
    "SuccessorReleaseDeclaration",
    "SuccessorRootObservation",
    "SuccessorRootObserver",
    "SuccessorSourcePolicy",
    "SuccessorStoreClassification",
    "ZERO_PROTECTED_EFFECTS",
    "assess_successor_readiness",
    "observe_installation_readiness",
]
