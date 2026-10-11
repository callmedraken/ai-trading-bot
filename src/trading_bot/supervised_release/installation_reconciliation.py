"""Read-only reconciliation for the consumed Architecture 133-AG installation.

This checkpoint owns no mutation authority. It reconstructs the exact failed AG
release from the still-frozen AG worktree and independently classifies preserved
FINAL/STAGING state after the one-shot publication ambiguity.
"""

from __future__ import annotations

import json
import stat
from dataclasses import asdict
from pathlib import Path
from typing import Final

import trading_bot.supervised_release.installation_operator as ag
from trading_bot.supervised_release.installation_contract import InstalledEvidence
from trading_bot.supervised_release.native_read import WindowsObserver
from trading_bot.supervised_release.observer import (
    observe_installed_release,
    observe_staging_release,
    replay_inputs,
)

WORKTREE: Final = Path(
    r"F:\AI\worktrees\ai-trading-bot-supervised-release-installation-reconciliation"
)
BRANCH: Final = "feature/robinhood-supervised-release-installation-reconciliation"
ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"

FAILED_AG_HEAD: Final = "513b60029f459ad6ecb4938f8fea2d54209a29d1"
FAILED_AG_TREE: Final = "14e8d161ac95e57982c576ebd19681bb204b22fd"
FAILED_AG_BRANCH: Final = "feature/robinhood-supervised-release-installation-operator"
EXPECTED_RELEASE_ID: Final = "release-03c42597246752319956ab96e01ed61c"
EXPECTED_MANIFEST_SHA256: Final = (
    "217d9a1d65fc6f3cc457a97ca227481c0507738fcd2d4128830960271220f4ed"
)
EXPECTED_BINDING_SHA256: Final = (
    "aa4992894106d69b8f251e880ef9bae1b9f5c687d69617c4a297107c25011f03"
)
EXPECTED_PARENT_IDENTITY: Final = (1855336320, 281474980511321)
EXPECTED_PYTHON_IDENTITY: Final = (1855336320, 281474977875353)
EXPECTED_FINAL: Final = (
    r"F:\AITradingBot\releases\release-03c42597246752319956ab96e01ed61c"
)
EXPECTED_STAGING: Final = (
    r"F:\AITradingBot\releases\release-03c42597246752319956ab96e01ed61c.installing"
)

ATTEMPT_PATH: Final = Path(r"F:\AI\temp\arch133-ag-installation-attempt\attempt.json")
ATTEMPT_BYTES: Final = (
    b'{"schema":"arch133-ag-installation-attempt/v1","status":"CONSUMED",'
    b'"automatic_retry":"NOT_AUTHORIZED"}\n'
)
REPORT_PATH: Final = Path(
    r"F:\AI\temp\arch133ag-protected-execute"
    r"\arch133-robinhood-supervised-release-installation-operator"
    r"\execute-20261011T034428.605950Z\report.json"
)
MAX_RECORD_BYTES: Final = 65536


def _read_record(path: Path, limit: int) -> bytes:
    facts = path.lstat()
    attributes = getattr(facts, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        not stat.S_ISREG(facts.st_mode)
        or stat.S_ISLNK(facts.st_mode)
        or bool(attributes & reparse_flag)
        or facts.st_size <= 0
        or facts.st_size > limit
    ):
        raise ValueError("reconciliation evidence object rejected")
    data = path.read_bytes()
    if len(data) != facts.st_size or len(data) > limit:
        raise ValueError("reconciliation evidence bytes rejected")
    return data


def _attempt_context() -> None:
    attempt = _read_record(ATTEMPT_PATH, 4096)
    if attempt != ATTEMPT_BYTES or _read_record(ATTEMPT_PATH, 4096) != attempt:
        raise ValueError("installation attempt latch rejected")

    report_bytes = _read_record(REPORT_PATH, MAX_RECORD_BYTES)
    if _read_record(REPORT_PATH, MAX_RECORD_BYTES) != report_bytes:
        raise ValueError("installation attempt report drift")
    report = json.loads(report_bytes.decode("utf-8"))
    if type(report) is not dict:
        raise ValueError("installation attempt report rejected")

    expected_state = {
        "head": FAILED_AG_HEAD,
        "tree": FAILED_AG_TREE,
        "branch": FAILED_AG_BRANCH,
        "porcelain": "",
    }
    source = report.get("source")
    result = report.get("result")
    primary = result.get("primary") if type(result) is dict else None

    if (
        report.get("schema") != "ai-trading-bot-checkpoint-runner/v1"
        or report.get("kind") != "protected_execution"
        or report.get("checkpoint")
        != "arch133-robinhood-supervised-release-installation-operator"
        or report.get("status") != "STOPPED"
        or report.get("effect_disposition") != "MAY_HAVE_OCCURRED"
        or report.get("protected_execution") != "ATTEMPTED"
        or report.get("automatic_retry") != "NOT_AUTHORIZED"
        or type(source) is not dict
        or source.get("before") != expected_state
        or source.get("after") != expected_state
        or source.get("remote_branch") != FAILED_AG_BRANCH
        or source.get("remote_head") != FAILED_AG_HEAD
        or source.get("identity_stable") is not True
        or type(result) is not dict
        or result.get("status") != "INDETERMINATE"
        or result.get("effect_disposition") != "MAY_HAVE_OCCURRED"
        or result.get("automatic_retry") != "NOT_AUTHORIZED"
        or type(primary) is not dict
        or primary.get("status") != "INDETERMINATE"
        or primary.get("disposition") != "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY"
        or primary.get("reason") != "PUBLICATION"
    ):
        raise ValueError("installation attempt report semantics rejected")


def _frozen_inputs():
    if (
        ag._git("rev-parse", "HEAD") != FAILED_AG_HEAD
        or ag._git("rev-parse", "HEAD^{tree}") != FAILED_AG_TREE
        or ag._git("branch", "--show-current") != FAILED_AG_BRANCH
    ):
        raise ValueError("failed AG source identity rejected")

    release, binding = ag._derive_release()
    paths = replay_inputs(release, binding)

    if (
        release.manifest.release_id != EXPECTED_RELEASE_ID
        or release.expected_manifest_sha256 != EXPECTED_MANIFEST_SHA256
        or binding.sha256 != EXPECTED_BINDING_SHA256
        or paths.final != EXPECTED_FINAL
        or paths.staging != EXPECTED_STAGING
    ):
        raise ValueError("failed AG release identity rejected")
    return release, binding, paths


def _presence(paths):
    native = WindowsObserver()
    with native.read_session(paths) as session:
        final = session.object(paths.final, directory=True)
        staging = session.object(paths.staging, directory=True)
    return final, staging


def _validate_evidence(
    evidence: InstalledEvidence,
    *,
    image_identity: tuple[int, int],
) -> None:
    if (
        type(evidence) is not InstalledEvidence
        or evidence.release_id != EXPECTED_RELEASE_ID
        or evidence.manifest_sha256 != EXPECTED_MANIFEST_SHA256
        or evidence.binding_sha256 != EXPECTED_BINDING_SHA256
        or evidence.parent_identity != EXPECTED_PARENT_IDENTITY
        or evidence.image_identity != image_identity
        or evidence.python_identity != EXPECTED_PYTHON_IDENTITY
        or evidence.python_version != "3.14.3"
        or evidence.python_sha256
        != "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
        or evidence.dependency_closure != "UNPROVEN"
    ):
        raise ValueError("reconciled image evidence rejected")


def _blocked(reason: str) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "effect_disposition": "MAY_HAVE_OCCURRED",
        "automatic_retry": "NOT_AUTHORIZED",
        "primary": {
            "status": "RECONCILIATION_UNRESOLVED",
            "disposition": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
            "reason": reason,
        },
    }


def _preflight() -> dict[str, object]:
    try:
        _attempt_context()
        ag._administrator_host()
        release, binding, paths = _frozen_inputs()

        first = _presence(paths)
        second = _presence(paths)
        if first != second:
            return _blocked("PRESERVED_NAMESPACE_DRIFT")

        final, staging = first
        if final is not None and staging is None:
            first_evidence = observe_installed_release(
                release, binding, native=WindowsObserver()
            )
            second_evidence = observe_installed_release(
                release, binding, native=WindowsObserver()
            )
            if first_evidence != second_evidence:
                return _blocked("FINAL_OBSERVATION_DRIFT")
            _validate_evidence(first_evidence, image_identity=final.identity)
            if _presence(paths) != first:
                return _blocked("PRESERVED_NAMESPACE_DRIFT")
            return {
                "status": "PASS",
                "effect_disposition": "CONFIRMED",
                "automatic_retry": "NOT_AUTHORIZED",
                "primary": {
                    "status": "FINAL_INSTALLED_VERIFIED",
                    "disposition": "RECONCILED_INSTALLED",
                    "reason": "EXACT_FINAL_ONLY",
                    **asdict(first_evidence),
                },
            }

        if final is None and staging is not None:
            first_evidence = observe_staging_release(
                release, binding, native=WindowsObserver()
            )
            second_evidence = observe_staging_release(
                release, binding, native=WindowsObserver()
            )
            if first_evidence != second_evidence:
                return _blocked("STAGING_OBSERVATION_DRIFT")
            _validate_evidence(first_evidence, image_identity=staging.identity)
            if _presence(paths) != first:
                return _blocked("PRESERVED_NAMESPACE_DRIFT")
            return {
                "status": "PASS",
                "effect_disposition": "MAY_HAVE_OCCURRED",
                "automatic_retry": "NOT_AUTHORIZED",
                "primary": {
                    "status": "STAGING_VERIFIED_PRESERVED",
                    "disposition": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
                    "reason": "EXACT_STAGING_ONLY",
                    **asdict(first_evidence),
                },
            }

        if final is not None and staging is not None:
            return _blocked("FINAL_AND_STAGING_BOTH_PRESENT")
        return _blocked("FINAL_AND_STAGING_BOTH_ABSENT")
    except (Exception, KeyboardInterrupt):
        return _blocked("RECONCILIATION_OBSERVATION_REJECTED")
