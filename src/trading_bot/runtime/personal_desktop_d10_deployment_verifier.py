"""A124-5 second-stage D10 deployment re-verification.

The sealed launch guard is the first trust boundary. This module runs only in
the admitted child and initiates a fresh proof of the fixed D10 objects before
a future controller may consider opening an effect gate.
"""

from __future__ import annotations

import importlib.util
import sys
import weakref
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PureWindowsPath
from types import ModuleType

from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    ACTIVATION_LEASE_SCHEMA,
    D10ActivationLease,
    build_activation_lease_model,
    parse_activation_lease,
    parse_utc_instant,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_PRODUCTION_PYTHON,
    D10_SIGNING_KEY_ID,
    D10_SOURCE_ROOT,
    DEPLOYMENT_ATTESTATION_SCHEMA,
)
from trading_bot.runtime.personal_desktop_d10_python_substrate import (
    VERSION as D10_PYTHON_VERSION,
)
from trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract import (  # noqa: E501
    D10_CACHE_PREFIX,
    D10_LAUNCH_GUARD,
    D10_SCHEDULER_CONTRACT,
    D10_SCHEDULER_CONTRACT_SCHEMA,
    D10_SECOND_STAGE_LAUNCHER,
    is_frozen_one_week_soak_scheduler_contract,
)
from trading_bot.runtime.windows_authority_validation import (
    acquire_validated_production_authority,
    require_validated_production_authority,
)


class DeploymentVerificationBlocked(RuntimeError):
    """The fixed signed D10 deployment cannot be established."""


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class VerifiedD10Deployment:
    """Sanitized same-process evidence; its fields alone grant no authority."""

    deployment_id: str
    attestation_sha256: str
    certified_source_head: str
    certified_source_tree: str
    executable_file_count: int


_ISSUED: weakref.WeakKeyDictionary[VerifiedD10Deployment, tuple[object, ...]] = (
    weakref.WeakKeyDictionary()
)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class VerifiedD10ActivationLease:
    """Sanitized same-process ACTIVE lease proof; its fields alone grant nothing."""

    state: str
    soak_id: str
    accepted_activation_utc: datetime
    end_utc: datetime
    deployment_id: str
    attestation_sha256: str


_ACTIVE_LEASES: weakref.WeakKeyDictionary[
    VerifiedD10ActivationLease, tuple[VerifiedD10Deployment, tuple[object, ...]]
] = weakref.WeakKeyDictionary()


def _fixed_guard() -> ModuleType:
    """Load only the guard admitted by the earlier sealed pre-source boundary."""
    spec = importlib.util.spec_from_file_location(
        "_d10_fixed_launch_guard_for_a4", str(D10_LAUNCH_GUARD)
    )
    if spec is None or spec.loader is None:
        raise DeploymentVerificationBlocked("fixed D10 launch guard is unavailable")
    module = importlib.util.module_from_spec(spec)
    # The standalone guard uses dataclasses, which require its module in sys.modules.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def _require_second_stage_runtime() -> None:
    expected_module = str(
        PureWindowsPath(D10_SOURCE_ROOT)
        / "src"
        / "trading_bot"
        / "runtime"
        / "personal_desktop_d10_deployment_verifier.py"
    )
    if (
        __file__ != expected_module
        or sys.executable != D10_PRODUCTION_PYTHON
        or sys.argv != [str(D10_SECOND_STAGE_LAUNCHER)]
        or not (
            sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
        )
        or sys.pycache_prefix != str(D10_CACHE_PREFIX)
    ):
        raise DeploymentVerificationBlocked("D10 second-stage runtime differs")


def verify_d10_deployment() -> VerifiedD10Deployment:
    """Reopen and reverify every fixed trust/source object with no caller facts."""
    try:
        _require_second_stage_runtime()
        c1 = acquire_validated_production_authority()
        guard = _fixed_guard()
        facts = guard.verify_fixed_deployment_for_second_stage()
        expected_facts = (
            DEPLOYMENT_ATTESTATION_SCHEMA,
            D10_SIGNING_KEY_ID,
            D10_SOURCE_ROOT,
            str(D10_LAUNCH_GUARD),
            str(D10_SECOND_STAGE_LAUNCHER),
            D10_SCHEDULER_CONTRACT_SCHEMA,
            D10_SCHEDULER_CONTRACT.principal_sid,
            D10_PRODUCTION_PYTHON,
            D10_PYTHON_VERSION,
        )
        observed_facts = (
            facts.schema,
            facts.signing_key_id,
            facts.source_root,
            facts.launch_guard,
            facts.launcher,
            facts.scheduler_contract_schema,
            facts.approved_trading_sid,
            facts.production_python,
            facts.production_python_version,
        )
        if (
            not is_frozen_one_week_soak_scheduler_contract(D10_SCHEDULER_CONTRACT)
            or type(facts) is not guard.VerifiedDeploymentFacts
            or observed_facts != expected_facts
            or D10_PYTHON_VERSION
            != ".".join(str(part) for part in sys.version_info[:3])
        ):
            raise DeploymentVerificationBlocked("D10 source-owned identity differs")
        require_validated_production_authority(c1)
        if acquire_validated_production_authority() != c1:
            raise DeploymentVerificationBlocked("D10 current C1 authority drifted")
        result = VerifiedD10Deployment(
            deployment_id=facts.deployment_id,
            attestation_sha256=facts.attestation_sha256,
            certified_source_head=facts.certified_source_head,
            certified_source_tree=facts.certified_source_tree,
            executable_file_count=facts.executable_file_count,
        )
        _ISSUED[result] = (
            result.deployment_id,
            result.attestation_sha256,
            result.certified_source_head,
            result.certified_source_tree,
            result.executable_file_count,
        )
        return result
    except Exception as exc:
        raise DeploymentVerificationBlocked(
            "D10 deployment re-verification failed"
        ) from exc


def require_verified_d10_deployment(
    evidence: VerifiedD10Deployment,
) -> VerifiedD10Deployment:
    """Reject copied or reconstructed A4 evidence at a later effect boundary."""
    if type(evidence) is not VerifiedD10Deployment or _ISSUED.get(evidence) != (
        evidence.deployment_id,
        evidence.attestation_sha256,
        evidence.certified_source_head,
        evidence.certified_source_tree,
        evidence.executable_file_count,
    ):
        raise DeploymentVerificationBlocked("D10 deployment provenance is not current")
    return evidence


class ActivationLeaseVerificationBlocked(RuntimeError):
    """The fixed ACTIVE D10 activation lease cannot be established."""


def build_d10_activation_lease(
    deployment: VerifiedD10Deployment, accepted_activation_utc: datetime
) -> D10ActivationLease:
    """Build later P124-5 bytes from genuine A4 deployment provenance."""
    require_verified_d10_deployment(deployment)
    return build_activation_lease_model(
        deployment_id=deployment.deployment_id,
        attestation_sha256=deployment.attestation_sha256,
        accepted_activation_utc=accepted_activation_utc,
        certified_source_head=deployment.certified_source_head,
        certified_source_tree=deployment.certified_source_tree,
    )


def build_d10_activation_lease_bytes(
    deployment: VerifiedD10Deployment, accepted_activation_utc: datetime
) -> bytes:
    """Return canonical create-only publication material, without writing it."""
    return build_d10_activation_lease(
        deployment, accepted_activation_utc
    ).canonical_bytes()


def _trusted_runtime_utc_now() -> datetime:
    """Internal clock seam; runtime callers cannot supply an observation time."""
    instant = datetime.now(UTC)
    if type(instant) is not datetime or instant.tzinfo is not UTC:
        raise ActivationLeaseVerificationBlocked(
            "D10 trusted runtime UTC clock is unavailable"
        )
    return instant


def _active_lease_values(
    evidence: VerifiedD10ActivationLease,
) -> tuple[object, ...]:
    return (
        evidence.state,
        evidence.soak_id,
        evidence.accepted_activation_utc,
        evidence.end_utc,
        evidence.deployment_id,
        evidence.attestation_sha256,
    )


def verify_d10_activation_lease(
    deployment: VerifiedD10Deployment,
) -> VerifiedD10ActivationLease:
    """Independently reread the fixed lease and bind ACTIVE proof to genuine A4."""
    try:
        require_verified_d10_deployment(deployment)
        c1 = acquire_validated_production_authority()
        require_validated_production_authority(c1)
        guard = _fixed_guard()
        facts = guard.verify_fixed_activation_lease_for_second_stage()
        if type(facts) is not guard.VerifiedActivationLeaseFacts:
            raise ActivationLeaseVerificationBlocked(
                "D10 activation lease boundary returned an unknown result"
            )
        lease = D10ActivationLease(
            schema=ACTIVATION_LEASE_SCHEMA,
            deployment_id=facts.deployment_id,
            attestation_sha256=facts.attestation_sha256,
            accepted_activation_utc=parse_utc_instant(facts.accepted_activation_utc),
            end_utc=parse_utc_instant(facts.end_utc),
            certified_source_head=facts.certified_source_head,
            certified_source_tree=facts.certified_source_tree,
            scheduler_contract_schema=facts.scheduler_contract_schema,
            scheduler_contract_id=facts.scheduler_contract_id,
            trading_sid=facts.trading_sid,
            production_python=facts.production_python,
            production_python_version=facts.production_python_version,
            soak_id=facts.soak_id,
        )
        parsed = parse_activation_lease(lease.canonical_bytes())
        if (
            facts.state != "ACTIVE"
            or parsed != lease
            or lease.deployment_id != deployment.deployment_id
            or lease.attestation_sha256 != deployment.attestation_sha256
            or lease.certified_source_head != deployment.certified_source_head
            or lease.certified_source_tree != deployment.certified_source_tree
            or not lease.accepted_activation_utc
            <= _trusted_runtime_utc_now()
            < lease.end_utc
        ):
            raise ActivationLeaseVerificationBlocked(
                "D10 activation lease differs from current deployment or time"
            )
        require_verified_d10_deployment(deployment)
        if acquire_validated_production_authority() != c1:
            raise ActivationLeaseVerificationBlocked("D10 current C1 authority drifted")
        result = VerifiedD10ActivationLease(
            state="ACTIVE",
            soak_id=lease.soak_id,
            accepted_activation_utc=lease.accepted_activation_utc,
            end_utc=lease.end_utc,
            deployment_id=lease.deployment_id,
            attestation_sha256=lease.attestation_sha256,
        )
        _ACTIVE_LEASES[result] = (deployment, _active_lease_values(result))
        return result
    except Exception as exc:
        raise ActivationLeaseVerificationBlocked(
            "D10 activation lease verification failed"
        ) from exc


def require_verified_d10_activation_lease(
    evidence: VerifiedD10ActivationLease, deployment: VerifiedD10Deployment
) -> VerifiedD10ActivationLease:
    """Reject copied lease results and expired or differently-bound evidence."""
    require_verified_d10_deployment(deployment)
    if type(evidence) is not VerifiedD10ActivationLease:
        raise ActivationLeaseVerificationBlocked(
            "D10 activation lease provenance is not current"
        )
    issued = _ACTIVE_LEASES.get(evidence)
    if (
        issued is None
        or issued[0] is not deployment
        or issued[1] != _active_lease_values(evidence)
        or evidence.state != "ACTIVE"
        or evidence.deployment_id != deployment.deployment_id
        or evidence.attestation_sha256 != deployment.attestation_sha256
        or not evidence.accepted_activation_utc
        <= _trusted_runtime_utc_now()
        < evidence.end_utc
    ):
        raise ActivationLeaseVerificationBlocked(
            "D10 activation lease provenance is not current"
        )
    return evidence
