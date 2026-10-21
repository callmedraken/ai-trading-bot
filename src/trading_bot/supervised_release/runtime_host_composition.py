"""Architecture 134-F1R1-B host composition and no-effect qualification.

This module accepts only replayable Architecture-133 evidence and immutable
F1R1-A material.  Its qualification host can admit, wait, record lifecycle
evidence, and stop.  It has no installation, scheduler, credential, network,
paper, broker, or trading capability.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from trading_bot.supervised_release.binding import DEPENDENCY_CLOSURE, RuntimeBinding
from trading_bot.supervised_release.bundle import VerifiedRelease, verify_release_bundle
from trading_bot.supervised_release.installation_contract import (
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstalledEvidence,
)
from trading_bot.supervised_release.lifecycle_store import DurableLifecycleJournal
from trading_bot.supervised_release.model import PRODUCTION_PYTHON, release_root
from trading_bot.supervised_release.runtime_admission import (
    SITE_PACKAGES,
)
from trading_bot.supervised_release.runtime_admission import (
    RuntimeAdmissionEvidence as Architecture133RuntimeAdmissionEvidence,
)
from trading_bot.supervised_release.runtime_admission import (
    RuntimeAdmissionResult as Architecture133RuntimeAdmissionResult,
)
from trading_bot.supervised_release.runtime_admission import (
    RuntimeReason as Architecture133RuntimeReason,
)
from trading_bot.supervised_release.runtime_admission import (
    RuntimeStatus as Architecture133RuntimeStatus,
)
from trading_bot.supervised_release.runtime_isolation import (
    DurableEffectJournal,
    DurableStoreIdentity,
    EffectOperation,
    EffectResult,
    InstalledRuntimeMaterial,
    LifecycleEvent,
    LifecycleEvidence,
    LifecycleStatus,
    RuntimeAdmissionStatus,
    admit_installed_runtime,
    run_durable_effect,
)

HOST_COMPOSITION_SCHEMA = "arch134-f1r1-b-host-composition/v1"
QUALIFICATION_SCHEMA = "arch134-f1r1-b-qualification/v1"
MAX_QUALIFICATION_BYTES = 8192


class HostBindingError(ValueError):
    """Independently supplied host evidence failed closed."""


@dataclass(frozen=True, slots=True)
class Architecture133HostBinding:
    """The exact evidence joined at the F1R1-A material boundary."""

    material: InstalledRuntimeMaterial
    verified_release: VerifiedRelease
    runtime_binding: RuntimeBinding
    installed_evidence: InstalledEvidence
    runtime_admission: Architecture133RuntimeAdmissionResult

    @property
    def runtime_id(self) -> str:
        return self.material.runtime_id

    @property
    def source_paths(self) -> tuple[str, ...]:
        return tuple(
            entry.relative_path
            for entry in self.verified_release.manifest.source_inventory
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": HOST_COMPOSITION_SCHEMA,
                "runtime_id": self.runtime_id,
                "release_id": self.verified_release.manifest.release_id,
                "manifest_sha256": self.material.manifest_sha256,
                "binding_sha256": self.runtime_binding.sha256,
                "source_paths": list(self.source_paths),
                "launcher": self.runtime_admission.evidence.launcher
                if self.runtime_admission.evidence is not None
                else None,
                "python_executable": PRODUCTION_PYTHON,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def _identity(value: object) -> bool:
    return (
        type(value) is tuple
        and len(value) == 2
        and all(type(part) is int and part > 0 for part in value)
    )


def _manifest_sha(release: VerifiedRelease) -> str:
    return hashlib.sha256(release.manifest.to_json().encode("utf-8")).hexdigest()


def _require_exact_host_evidence(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    installed: InstalledEvidence,
    runtime_admission: Architecture133RuntimeAdmissionResult,
) -> None:
    if (
        type(release) is not VerifiedRelease
        or type(binding) is not RuntimeBinding
        or type(installed) is not InstalledEvidence
        or type(runtime_admission) is not Architecture133RuntimeAdmissionResult
        or runtime_admission.status is not Architecture133RuntimeStatus.VERIFIED
        or runtime_admission.reason is not Architecture133RuntimeReason.VERIFIED
        or type(runtime_admission.evidence)
        is not Architecture133RuntimeAdmissionEvidence
    ):
        raise HostBindingError("verified Architecture-133 admission required")

    replayed = verify_release_bundle(
        release.bundle,
        expected_manifest_sha256=release.expected_manifest_sha256,
        expected_source_head=release.expected_source_head,
        expected_source_tree=release.expected_source_tree,
        expected_source_paths=release.expected_source_paths,
    )
    if replayed != release or binding.verified_release != replayed:
        raise HostBindingError("release replay or binding mismatch")
    RuntimeBinding.from_json(binding.to_json(), verified_release=replayed)

    manifest = replayed.manifest
    manifest_sha = _manifest_sha(replayed)
    if release.expected_manifest_sha256 != manifest_sha:
        raise HostBindingError("manifest identity mismatch")
    expected_paths = tuple(entry.relative_path for entry in manifest.source_inventory)
    if expected_paths != release.expected_source_paths:
        raise HostBindingError("immutable source inventory mismatch")

    evidence = runtime_admission.evidence
    root = release_root(manifest.release_id)
    source_root = root + r"\src"
    launcher = root + "\\" + manifest.launcher_relative_path.replace("/", "\\")
    checks = (
        installed.release_id == manifest.release_id,
        installed.manifest_sha256 == manifest_sha,
        installed.binding_sha256 == binding.sha256,
        installed.python_version == PYTHON_VERSION,
        installed.python_sha256 == PYTHON_SHA256,
        installed.dependency_closure == DEPENDENCY_CLOSURE,
        _identity(installed.parent_identity),
        _identity(installed.image_identity),
        _identity(installed.python_identity),
        evidence.release_id == manifest.release_id,
        evidence.manifest_sha256 == manifest_sha,
        evidence.binding_sha256 == binding.sha256,
        evidence.image_identity == installed.image_identity,
        evidence.python_identity == installed.python_identity,
        evidence.release_root == root,
        evidence.source_root == source_root,
        evidence.launcher == launcher,
        evidence.site_packages == SITE_PACKAGES,
        evidence.dependency_closure == DEPENDENCY_CLOSURE,
    )
    if not all(checks):
        raise HostBindingError("Architecture-133 evidence identity mismatch")


def bind_architecture133_host(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    installed: InstalledEvidence,
    runtime_admission: Architecture133RuntimeAdmissionResult,
    *,
    durable_store_identities: tuple[DurableStoreIdentity, ...] = (),
) -> Architecture133HostBinding:
    """Join independently verified 133 evidence into immutable F1R1 material."""

    try:
        _require_exact_host_evidence(release, binding, installed, runtime_admission)
        material = InstalledRuntimeMaterial.from_manifest(
            release.manifest,
            binding_sha256=binding.sha256,
            durable_store_identities=durable_store_identities,
        )
        admitted = admit_installed_runtime(
            material,
            expected_runtime_id=material.runtime_id,
            expected_state_identities=material.durable_store_identities,
        )
        if admitted.status is not RuntimeAdmissionStatus.ADMITTED:
            raise HostBindingError("immutable runtime material rejected")
        return Architecture133HostBinding(
            material, release, binding, installed, runtime_admission
        )
    except HostBindingError:
        raise
    except (TypeError, ValueError, KeyError, ArithmeticError) as exc:
        raise HostBindingError("Architecture-133 host binding rejected") from exc


def bind_architecture133_runtime(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    installed: InstalledEvidence,
    runtime_admission: Architecture133RuntimeAdmissionResult,
    *,
    durable_store_identities: tuple[DurableStoreIdentity, ...] = (),
) -> InstalledRuntimeMaterial:
    """Return only the immutable material used by all later admissions."""

    return bind_architecture133_host(
        release,
        binding,
        installed,
        runtime_admission,
        durable_store_identities=durable_store_identities,
    ).material


class SuccessorExternalEffectAdapter:
    """Inert composition for a future quote/paper seam."""

    def __init__(self, journal: DurableEffectJournal, operation: EffectOperation):
        if not all(
            callable(getattr(journal, name, None)) for name in ("records", "append")
        ):
            raise ValueError("injected effect journal required")
        if type(operation) is not EffectOperation:
            raise ValueError("closed effect operation required")
        self._journal = journal
        self._operation = operation

    def execute(
        self,
        *,
        pre_entry_guard: Callable[[], bool],
        external_seam: Callable[[], None],
    ) -> EffectResult:
        return run_durable_effect(
            journal=self._journal,
            operation=self._operation,
            pre_entry_guard=pre_entry_guard,
            external_operation=external_seam,
        )


class QualificationState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SAFE_WAITING = "SAFE_WAITING"
    STOPPED = "STOPPED"
    CAUGHT_INTERNAL_FAILURE = "CAUGHT_INTERNAL_FAILURE"


class StopSignal(Protocol):
    def __call__(self) -> bool: ...


class WaitOnce(Protocol):
    def __call__(self) -> None: ...


@dataclass(frozen=True, slots=True)
class QualificationEvidence:
    runtime_id: str
    state: QualificationState
    lifecycle: LifecycleEvidence

    def __post_init__(self) -> None:
        if self.lifecycle.runtime_id != self.runtime_id:
            raise ValueError("qualification runtime identity mismatch")
        if type(self.state) is not QualificationState:
            raise ValueError("closed qualification state required")

    @property
    def status(self) -> LifecycleStatus:
        return self.lifecycle.status

    def to_json(self) -> str:
        text = json.dumps(
            {
                "schema": QUALIFICATION_SCHEMA,
                "runtime_id": self.runtime_id,
                "state": self.state.value,
                "lifecycle": json.loads(self.lifecycle.to_json()),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(text.encode("utf-8")) > MAX_QUALIFICATION_BYTES:
            raise ValueError("qualification evidence exceeds bounded size")
        return text


class QualificationHost:
    """Cooperative safe-idle host with injected stop and wait seams."""

    def __init__(
        self, material: InstalledRuntimeMaterial, journal: DurableLifecycleJournal
    ):
        if type(material) is not InstalledRuntimeMaterial:
            raise ValueError("immutable runtime material required")
        if not isinstance(journal, DurableLifecycleJournal):
            raise ValueError("durable lifecycle journal required")
        if journal.runtime_id != material.runtime_id:
            raise ValueError("lifecycle journal runtime identity mismatch")
        self._material = material
        self._journal = journal
        self._state = QualificationState.NOT_STARTED

    @property
    def runtime_id(self) -> str:
        return self._material.runtime_id

    def evidence(self) -> QualificationEvidence:
        return QualificationEvidence(
            self.runtime_id,
            self._state,
            self._journal.snapshot(),
        )

    def run(self, *, stop: StopSignal, wait_once: WaitOnce) -> QualificationEvidence:
        if self._state is not QualificationState.NOT_STARTED:
            raise ValueError("qualification host is single-use")
        if self._journal.records():
            raise ValueError("qualification lifecycle is already consumed")
        admitted = admit_installed_runtime(
            self._material,
            expected_runtime_id=self.runtime_id,
            expected_state_identities=self._material.durable_store_identities,
        )
        if admitted.status is not RuntimeAdmissionStatus.ADMITTED:
            raise ValueError("fresh immutable runtime admission required")
        self._journal.append(LifecycleEvent.HOST_ENTERED)
        self._journal.append(LifecycleEvent.SUPERVISOR_LOCK_ACQUIRED)
        self._journal.append(LifecycleEvent.SUPERVISOR_LOOP_ENTERED)
        self._journal.append(LifecycleEvent.SAFE_WAITING)
        self._state = QualificationState.SAFE_WAITING
        try:
            while stop() is not True:
                wait_once()
            self._journal.append(LifecycleEvent.NORMAL_RETURN)
            self._state = QualificationState.STOPPED
        except Exception:
            self._journal.append(LifecycleEvent.CAUGHT_INTERNAL_FAILURE)
            self._state = QualificationState.CAUGHT_INTERNAL_FAILURE
        return self.evidence()


__all__ = [
    "Architecture133HostBinding",
    "HostBindingError",
    "QualificationEvidence",
    "QualificationHost",
    "QualificationState",
    "StopSignal",
    "SuccessorExternalEffectAdapter",
    "WaitOnce",
    "bind_architecture133_host",
    "bind_architecture133_runtime",
]
