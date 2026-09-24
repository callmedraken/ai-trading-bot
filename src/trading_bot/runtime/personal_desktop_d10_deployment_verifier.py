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
from pathlib import PureWindowsPath
from types import ModuleType

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
