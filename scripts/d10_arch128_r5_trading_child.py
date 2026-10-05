"""Architecture-128 R5 actual-Trading read-only deployment qualification.

This source is executed only by the unified runner under the fixed production
Python with the Architecture-124 isolated startup flags. It imports reviewed
qualification source from its exact Git worktree, never deployed governed source.
No scheduler, activation, provider, Paper-v2, broker, or live effect exists here.
"""

from __future__ import annotations

import json
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Final

SCHEMA: Final = "arch128-r5-trading-qualification/v1"

_OPERATOR_FILE = Path(__file__)
if not _OPERATOR_FILE.is_absolute():
    raise RuntimeError("r5_source_path_not_absolute")
_REPO_ROOT = _OPERATOR_FILE.resolve(strict=True).parent.parent
_SRC_ROOT = _REPO_ROOT / "src"
for _root in (str(_REPO_ROOT), str(_SRC_ROOT)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

# ruff: noqa: E402 -- exact source bootstrap precedes reviewed source imports.
from scripts import d10_arch128_r4_replacement as r4
from scripts import run_personal_desktop_d10_launch_guard as guard


def _base() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "production_python_substrate": "SEPARATE_R5_SUBSTRATE_PROFILE_REQUIRED",
        "activation": "NOT_RUN",
        "source_launch": "NOT_RUN",
        "scheduler": "NOT_RUN",
        "provider": "NOT_RUN",
        "Paper-v2": "NOT_RUN",
        "broker": "NOT_RUN",
        "live": "NOT_RUN",
        "second_stage_launch_trap": "NOT_CALLED",
    }


def _require_final_lease_absent(backend: object, guard_module: object) -> None:
    try:
        handle = backend.open(guard_module.D10_ACTIVATION_LEASE, directory=False)
    except guard_module._NativeError as exc:
        if exc.code not in (
            guard_module.ERROR_FILE_NOT_FOUND,
            guard_module.ERROR_PATH_NOT_FOUND,
        ):
            raise
        return
    backend.close(handle)
    raise guard_module.GuardBlocked("R5 final activation lease is present")


def _qualify(
    guard_module: object = guard,
    r4_module: object = r4,
) -> dict[str, object]:
    result = _base()
    try:
        expected = r4_module.NEW_IDENTITY

        calls: list[tuple[object, ...]] = []
        original_run = guard_module.subprocess.run

        def _trap(*args: object, **kwargs: object) -> object:
            calls.append((args, kwargs))
            raise RuntimeError("r5_second_stage_launch_trapped")

        guard_module.subprocess.run = _trap
        saved_argv = sys.argv
        try:
            sys.argv = [guard_module.D10_LAUNCH_GUARD]
            deployment = guard_module._verify_pre_source()
        finally:
            sys.argv = saved_argv
            guard_module.subprocess.run = original_run

        if calls:
            raise RuntimeError("r5_second_stage_launch_was_called")
        if (
            deployment.deployment_id != expected.deployment_id
            or deployment.attestation_sha256 != expected.unsigned_attestation_sha256
            or deployment.certified_source_head != expected.certified_source_head
            or deployment.certified_source_tree != expected.certified_source_tree
            or deployment.executable_file_count != expected.executable_file_count
            or deployment.production_python != guard_module.D10_PRODUCTION_PYTHON
            or deployment.production_python_version
            != guard_module.D10_PRODUCTION_PYTHON_VERSION
        ):
            raise RuntimeError("r5_new_deployment_identity_drift")

        backend = guard_module._Native()
        _require_final_lease_absent(backend, guard_module)
        for path in (
            guard_module.D10_ACTIVATION_LEASE_INSTALLING,
            guard_module.D10_ACTIVATION_LEASE_TEMP,
            guard_module.D10_CACHE_PREFIX,
        ):
            backend.require_absent(path)

        with ExitStack() as stack:
            root_handle = backend.open(guard_module.D10_EVIDENCE_ROOT, directory=True)
            stack.callback(backend.close, root_handle)
            before = backend.inspect(root_handle)
            guard_module._require_facts(
                guard_module.D10_EVIDENCE_ROOT,
                True,
                before,
            )
            names = backend.listdir(guard_module.D10_EVIDENCE_ROOT)
            if names != ():
                raise guard_module.GuardBlocked("R5 evidence root is not empty")
            after = backend.inspect(root_handle)
            guard_module._require_facts(
                guard_module.D10_EVIDENCE_ROOT,
                True,
                after,
            )
            guard_module._stable(before, after)

        result.update(
            {
                "status": "PASS",
                "deployment_id": deployment.deployment_id,
                "attestation_sha256": deployment.attestation_sha256,
                "certified_source_head": deployment.certified_source_head,
                "certified_source_tree": deployment.certified_source_tree,
                "executable_file_count": deployment.executable_file_count,
                "guard_byte_length": expected.guard_byte_length,
                "guard_sha256": expected.guard_sha256,
                "signed_deployment_verification": "PASS",
                "trading_principal_verification": "PASS",
                "sealed_source_verification": "PASS",
                "trust_reread_stability": "PASS",
                "production_runtime_flags": "EXACT",
                "evidence_root": "EXACT_EMPTY_AND_VERIFIED",
                "activation_lease": "FINAL_INSTALLING_TMP_ABSENT_AND_VERIFIED",
                "current_soak_evidence": "ABSENT_AND_VERIFIED",
                "guard_argv_context": "EXACT_INSTALLED_GUARD_PATH_EMULATED",
            }
        )
    except Exception as exc:
        result["reason"] = type(exc).__name__
        result["detail"] = str(exc)
    return result


def main() -> int:
    result = _qualify()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
