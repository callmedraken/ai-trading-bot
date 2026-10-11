"""133-AJ: one preserved-image publication; no installation or retry authority."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Final

from trading_bot.supervised_release import installation_reconciliation as incident
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import VerifiedRelease
from trading_bot.supervised_release.installation_contract import (
    InstalledEvidence,
    ReleasePaths,
)
from trading_bot.supervised_release.model import RELEASES_BASE
from trading_bot.supervised_release.native_read import WindowsObserver
from trading_bot.supervised_release.observer import (
    observe_installed_release,
    observe_parent,
    observe_staging_release,
)

WORKTREE: Final = Path(
    r"F:\AI\worktrees\ai-trading-bot-supervised-release-publication-recovery"
)
BRANCH: Final = "feature/robinhood-supervised-release-publication-recovery"
BASE_HEAD: Final = "6456e2921643ed6427f118cbf6e9a7d57e0186ce"
ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
AUTH_ENV: Final = "AI_TRADING_BOT_ARCH133_AJ_PUBLICATION_AUTHORIZATION"
AUTH_VALUE: Final = "ARCH133_AJ_ONE_PRESERVED_RELEASE_PUBLICATION_AUTHORIZED"
ATTEMPT_PATH: Final = Path(r"F:\AI\temp\arch133-aj-publication-recovery-attempt.json")
ATTEMPT_BYTES: Final = (
    b'{"schema":"arch133-aj-publication-recovery-attempt/v1","status":"CONSUMED",'
    b'"automatic_retry":"NOT_AUTHORIZED"}\n'
)
AI_REPORT_PATH: Final = Path(
    r"F:\AI\temp\arch133ai-reconciliation-corrected-6a5d4f6a8ee641a1a4c44a41bbd152f0"
    r"\arch133-robinhood-supervised-release-installation-reconciliation"
    r"\preflight-20261011T043729.349823Z\report.json"
)
AI_REPORT_SHA256: Final = (
    "f620f13a9d9cac6caeda36205b47b68f849fe1c4ac7c337df18fc795d56d6e45"
)
AG_REPORT_SHA256: Final = (
    "ac1c51bc7dc30dde655efe64570f1ed301586e742dfe0bd0e47f2bc12c1d8560"
)
STAGING_IDENTITY: Final = (1855336320, 281474980566367)


def expected_image() -> InstalledEvidence:
    """Exact immutable image accepted by the fixed AI reconciliation evidence."""
    return InstalledEvidence(
        incident.EXPECTED_RELEASE_ID,
        incident.EXPECTED_MANIFEST_SHA256,
        incident.EXPECTED_BINDING_SHA256,
        incident.EXPECTED_PARENT_IDENTITY,
        STAGING_IDENTITY,
        incident.EXPECTED_PYTHON_IDENTITY,
    )


def _records() -> None:
    incident.admit_failed_installation()
    for path, digest in (
        (incident.REPORT_PATH, AG_REPORT_SHA256),
        (AI_REPORT_PATH, AI_REPORT_SHA256),
    ):
        first = incident.read_incident_record(path, incident.MAX_RECORD_BYTES)
        if (
            hashlib.sha256(first).hexdigest() != digest
            or incident.read_incident_record(path, incident.MAX_RECORD_BYTES) != first
        ):
            raise ValueError("fixed publication incident evidence rejected")
        if path == AI_REPORT_PATH:
            report = json.loads(first)
            expected_primary = {
                "status": "STAGING_VERIFIED_PRESERVED",
                "disposition": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
                "reason": "EXACT_STAGING_ONLY",
                **json.loads(json.dumps(asdict(expected_image()))),
            }
            if report["result"]["primary"] != expected_primary:
                raise ValueError("accepted AI image rejected")


def latch_consumed() -> bool:
    """Any existing AJ object consumes authority; no reset/repair is provided."""
    for path in reversed(ATTEMPT_PATH.parents):
        facts = path.lstat()
        if (
            not stat.S_ISDIR(facts.st_mode)
            or stat.S_ISLNK(facts.st_mode)
            or getattr(facts, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("AJ latch ancestor rejected")
    try:
        ATTEMPT_PATH.lstat()
    except FileNotFoundError:
        return False
    return True


def _consume(mark_consumed: Callable[[], None]) -> None:
    if latch_consumed():
        raise FileExistsError("AJ attempt already consumed")
    # Exclusive creation consumes authority before write/flush/close. Any of those
    # failures must preserve the latch and be classified after the fence.
    with ATTEMPT_PATH.open("xb") as handle:
        mark_consumed()
        if handle.write(ATTEMPT_BYTES) != len(ATTEMPT_BYTES):
            raise OSError("AJ latch partial write")
        handle.flush()
        os.fsync(handle.fileno())


def _namespace(paths: ReleasePaths):
    with WindowsObserver().read_session(paths) as session:
        parent = observe_parent(session)
        names = session.names(RELEASES_BASE)
        if (
            type(names) is not tuple
            or len(names) > 4096
            or any(type(name) is not str for name in names)
            or len({name.casefold() for name in names}) != len(names)
        ):
            raise ValueError("publication namespace rejected")
        for name in names:
            if name != paths.release_id + ".installing":
                ReleasePaths(name)
        final = session.object(paths.final, directory=True)
        staging = session.object(paths.staging, directory=True)
        if (
            parent.identity != incident.EXPECTED_PARENT_IDENTITY
            or (paths.release_id in names) != (final is not None)
            or (paths.release_id + ".installing" in names) != (staging is not None)
            or session.names(RELEASES_BASE) != names
            or observe_parent(session) != parent
        ):
            raise ValueError("publication namespace drift")
    return parent, names, final, staging


def _image(
    release: VerifiedRelease,
    binding: RuntimeBinding,
    paths: ReleasePaths,
    *,
    final: bool,
) -> InstalledEvidence:
    first = _namespace(paths)
    if first != _namespace(paths):
        raise ValueError("publication namespace drift")
    _, _, installed, staging = first
    if (final and (installed is None or staging is not None)) or (
        not final and (installed is not None or staging is None)
    ):
        raise ValueError("publication requires exact sole namespace")
    fact = installed if final else staging
    if fact.identity != STAGING_IDENTITY:
        raise ValueError("preserved image identity drift")
    observer = observe_installed_release if final else observe_staging_release
    evidence = observer(release, binding, native=WindowsObserver())
    if evidence != observer(release, binding, native=WindowsObserver()):
        raise ValueError("publication image observation drift")
    incident.validate_incident_image(evidence, image_identity=STAGING_IDENTITY)
    if evidence != expected_image() or _namespace(paths) != first:
        raise ValueError("publication image drift")
    return evidence


def _ready(admit_source: Callable[[], None]):
    admit_source()
    _records()
    incident.require_administrator_host()
    release, binding, paths = incident.reconstruct_failed_release()
    if (
        release.expected_source_head != incident.FAILED_AG_HEAD
        or release.expected_source_tree != incident.FAILED_AG_TREE
        or paths != ReleasePaths(incident.EXPECTED_RELEASE_ID)
    ):
        raise ValueError("publication source image rejected")
    evidence = _image(release, binding, paths, final=False)
    if incident.reconstruct_failed_release() != (release, binding, paths):
        raise ValueError("failed AG source drift")
    _records()
    admit_source()
    return release, binding, paths, evidence


def _result(
    status: str, reason: str, evidence: InstalledEvidence | None = None
) -> dict[str, object]:
    success = status == "PASS"
    ambiguous = status == "INDETERMINATE"
    return {
        "status": status,
        "effect_disposition": "CONFIRMED"
        if success
        else "MAY_HAVE_OCCURRED"
        if ambiguous
        else "NOT_STARTED",
        "automatic_retry": "NOT_AUTHORIZED",
        "primary": {
            "status": "FINAL_PUBLISHED_VERIFIED" if success else status,
            "reason": reason,
            "disposition": "VERIFIED"
            if success
            else "PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY"
            if ambiguous
            else "NO_PUBLICATION_EFFECT",
            **(asdict(evidence) if evidence is not None else {}),
        },
    }


def preflight(admit_source: Callable[[], None]) -> dict[str, object]:
    """Read-only incident, source, host and preserved STAGING reproof."""
    try:
        if latch_consumed():
            return _result("INDETERMINATE", "CONSUMED_AJ_ATTEMPT")
        _, _, _, evidence = _ready(admit_source)
        if latch_consumed():
            return _result("INDETERMINATE", "CONSUMED_AJ_ATTEMPT")
        result = _result("BLOCKED", "EXACT_STAGING_ONLY", evidence)
        result["status"] = "PASS"
        result["primary"]["status"] = "READY"
        return result
    except (Exception, KeyboardInterrupt):
        return _result("BLOCKED", "PUBLICATION_ADMISSION_REJECTED")


def execute_once(admit_source: Callable[[], None]) -> dict[str, object]:
    """Runner-only transport; new authorization never refreshes consumed authority."""
    consumed = False
    fence_attempted = False

    def fence() -> None:
        nonlocal consumed
        consumed = True

    try:
        if os.environ.get(AUTH_ENV) != AUTH_VALUE:
            raise ValueError("AJ authorization interlock rejected")
        if latch_consumed():
            return _result("INDETERMINATE", "CONSUMED_AJ_ATTEMPT")
        release, binding, paths, evidence = _ready(admit_source)
        # Source/incident checks finish before consuming the durable one-shot.
        before = _namespace(paths)
        if (
            before[2] is not None
            or before[3] is None
            or before[3].identity != STAGING_IDENTITY
        ):
            raise ValueError("publication namespace changed before fence")
        _records()
        admit_source()
        fence_attempted = True
        _consume(fence)
        if not consumed:
            raise ValueError("AJ durable fence acknowledgement rejected")
        if incident.read_incident_record(ATTEMPT_PATH, 4096) != ATTEMPT_BYTES:
            raise ValueError("AJ durable latch readback rejected")
        from trading_bot.supervised_release.native_publication import (
            publish_preserved_image,
        )

        if publish_preserved_image(evidence) is not True:
            raise ValueError("publication return ambiguous")
        final = _image(release, binding, paths, final=True)
        after = _namespace(paths)
        expected_names = set(before[1]) - {paths.release_id + ".installing"} | {
            paths.release_id
        }
        if (
            after[0] != before[0]
            or set(after[1]) != expected_names
            or after[3] is not None
        ):
            raise ValueError("publication parent namespace drift")
        _records()
        if incident.reconstruct_failed_release() != (release, binding, paths):
            raise ValueError("post-publication AG source drift")
        admit_source()
        if _namespace(paths) != after:
            raise ValueError("late publication namespace drift")
        return _result("PASS", "EXACT_FINAL_ONLY", final)
    except BaseException:
        if fence_attempted and not consumed:
            try:
                consumed = latch_consumed()
            except BaseException:
                consumed = True
        return _result(
            "INDETERMINATE" if consumed else "BLOCKED",
            "PUBLICATION_AMBIGUITY" if consumed else "PUBLICATION_ADMISSION_REJECTED",
        )
