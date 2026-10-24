"""D1S3-R5: read-only reconciliation and one fenced preserved-image publication.

No installation or successor-root authority. Native publication is imported only
after exclusive durable recovery-latch readback. Production dispatch is reserved
for a separately reviewed operator boundary; source tests inject observations.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    ReleaseFile,
    VerifiedRelease,
    source_namespace,
)
from trading_bot.supervised_release.collector import collect_release_bundle
from trading_bot.supervised_release.installation_contract import (
    InstalledEvidence,
    ObjectFacts,
    ReleasePaths,
)
from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    RELEASES_BASE,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ReleaseInventoryEntry,
    ReleaseManifest,
)
from trading_bot.supervised_release.native_read import (
    WindowsObserver,
    windows_libraries,
)
from trading_bot.supervised_release.observer import (
    check_object,
    observe_installed_release,
    observe_parent,
    observe_staging_release,
    replay_inputs,
)

CHECKPOINT = "arch134-f1r1-d1s3-r5-successor-release-publication-recovery"
SCHEMA = CHECKPOINT + "/v1"
BRANCH = (
    "feature/robinhood-production-paper-134f1r1-d1s3-r5-publication-recovery-current"
)
WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-"
    r"d1s3-r5-publication-recovery-current"
)
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
REMOTE_HEAD_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S3_R5_ACCEPTED_HEAD"
SOURCE_TREE_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S3_R5_ACCEPTED_TREE"
AUTH_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S3_R5_PUBLICATION_AUTHORIZATION"
AUTH_VALUE = "ARCH134_F1R1_D1S3_R5_ONE_PRESERVED_RELEASE_PUBLICATION_AUTHORIZED"
ATTEMPT_PATH = Path(
    r"F:\AI\temp\arch134-f1r1-d1s3-r5-publication-recovery-attempt\attempt.json"
)
ATTEMPT_BYTES = (
    b'{"automatic_retry":"NOT_AUTHORIZED",'
    b'"schema":"arch134-f1r1-d1s3-r5-publication-recovery-attempt/v1",'
    b'"status":"CONSUMED"}\n'
)
INSTALL_CHECKPOINT = "arch134-f1r1-d1s3-successor-release-installation-operator"
INSTALL_ATTEMPT_PATH = Path(
    r"F:\AI\temp\arch134-f1r1-d1s3-installation-attempt\attempt.json"
)
INSTALL_ATTEMPT_SHA256 = (
    "6677dd0d690fc611d6d4ba643179d78f0f168dfc2183c4310aae26e6d84c5f67"
)
REPORT_ROOT = Path(r"F:\AI\temp\ai-trading-bot-checkpoints") / INSTALL_CHECKPOINT
EXECUTE_REPORT_PATH = REPORT_ROOT / "execute-20261024T061344.551535Z" / "report.json"
EXECUTE_REPORT_SHA256 = (
    "2b62f5718c1d9ed70b9cbf5232129c76734fdb1b77ae690137e6c7a5234fd84d"
)
BLOCKED_REPORT_PATH = REPORT_ROOT / "preflight-20261024T063211.998964Z" / "report.json"
BLOCKED_REPORT_SHA256 = (
    "cd14c43cb9e2c9d500941c0cd026e7e14617d2a9a1c0a377e5d6b06c75debeec"
)
ACCEPTED_HEAD = "ad4c3d3334048054df6d8f046040349619c277f2"
ACCEPTED_TREE = "b4cbf3039171673d3fba44e4999b172e658a4f91"
PREDECESSOR_WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-"
    r"successor-installation-operator-current"
)
PREDECESSOR_BRANCH = (
    "feature/robinhood-production-paper-134f1r1-successor-installation-operator-current"
)
RELEASE_ID = "release-cb94451fc3295a97afffe9fac5d09ff3"
FINAL_PATH = RELEASES_BASE + "\\" + RELEASE_ID
STAGING_PATH = FINAL_PATH + ".installing"
MANIFEST_SHA256 = "e36ca8cdd163a3a93137e50972913acfe468745639ec773ba21e842d8d814875"
BINDING_SHA256 = "5ee1ea4218114b78d24b82ab7369972eafcaf332fa0b8e5ae59e5da08b953329"
INVENTORY_SHA256 = "cd1b9ad5ec963916b6de6d5b81ebbad75d79ebcd5c4fc86fc991bfd0e1225d21"
STAGING_IDENTITY = (1855336320, 281474982917732)
PARENT_IDENTITY = (1855336320, 281474980511321)
PYTHON_IDENTITY = (1855336320, 281474977875353)
PYTHON_VERSION = "3.14.3"
PYTHON_SHA256 = "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
MAX_RECORD_BYTES = 1024 * 1024


class ObservationDrift(ValueError):
    """Repeated observations disagreed; preserve evidence without retry."""


def expected_image() -> InstalledEvidence:
    return InstalledEvidence(
        RELEASE_ID,
        MANIFEST_SHA256,
        BINDING_SHA256,
        PARENT_IDENTITY,
        STAGING_IDENTITY,
        PYTHON_IDENTITY,
        PYTHON_VERSION,
        PYTHON_SHA256,
        "UNPROVEN",
    )


def validate_image(evidence: InstalledEvidence) -> None:
    if type(evidence) is not InstalledEvidence or evidence != expected_image():
        raise ValueError("EXACT_IMAGE_REJECTED")


def _safe_ancestors(path: Path) -> None:
    for ancestor in reversed(path.parents):
        try:
            fact = ancestor.lstat()
        except FileNotFoundError:
            continue
        if (
            not stat.S_ISDIR(fact.st_mode)
            or stat.S_ISLNK(fact.st_mode)
            or getattr(fact, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("EVIDENCE_ANCESTOR_REJECTED")


def read_record(
    path: Path, limit: int = MAX_RECORD_BYTES, *, allow_empty: bool = False
) -> bytes:
    """Bounded no-reparse read with stable object facts and byte length."""
    _safe_ancestors(path)
    fact = path.lstat()
    if (
        not stat.S_ISREG(fact.st_mode)
        or stat.S_ISLNK(fact.st_mode)
        or getattr(fact, "st_file_attributes", 0) & 0x400
        or fact.st_nlink != 1
        or not (0 if allow_empty else 1) <= fact.st_size <= limit
    ):
        raise ValueError("EVIDENCE_OBJECT_REJECTED")
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        if (opened.st_dev, opened.st_ino) != (fact.st_dev, fact.st_ino):
            raise ObservationDrift("EVIDENCE_OPEN_DRIFT")
        data = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    final = path.lstat()
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
    stable = tuple(getattr(fact, field) for field in fields)
    if (
        any(
            tuple(getattr(other, field) for field in fields) != stable
            for other in (opened, after, final)
        )
        or opened.st_ctime_ns != after.st_ctime_ns
        or fact.st_ctime_ns != final.st_ctime_ns
        or len(data) != fact.st_size
    ):
        raise ObservationDrift("EVIDENCE_READ_DRIFT")
    return data


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_EVIDENCE_FIELD")
        result[key] = value
    return result


def _report_semantics(report: dict, *, execute: bool) -> None:
    source = report["source"]
    result = report["result"]
    primary = result["primary"]
    if (
        report["schema"] != "ai-trading-bot-checkpoint-runner/v1"
        or report["checkpoint"] != INSTALL_CHECKPOINT
        or source["identity_stable"] is not True
        or any(
            source[phase][key] != value
            for phase in ("before", "after")
            for key, value in (
                ("head", ACCEPTED_HEAD),
                ("tree", ACCEPTED_TREE),
                ("porcelain", ""),
            )
        )
        or result["automatic_retry"] != "NOT_AUTHORIZED"
    ):
        raise ValueError("INCIDENT_SOURCE_REJECTED")
    if execute:
        attempt = result["attempt"]
        valid = (
            report["protected_execution"] == "ATTEMPTED"
            and report["status"] == "STOPPED"
            and result["status"] == "INDETERMINATE"
            and result["effect_disposition"] == "MAY_HAVE_OCCURRED"
            and primary["status"] == "INDETERMINATE"
            and primary["disposition"] == "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY"
            and primary["reason"] == "PUBLICATION"
            and attempt["state"] == "CONSUMED"
            and attempt["path"] == str(INSTALL_ATTEMPT_PATH)
            and attempt["payload_sha256"] == INSTALL_ATTEMPT_SHA256
        )
    else:
        valid = (
            report["protected_execution"] == "NOT_AUTHORIZED"
            and result["status"] == "BLOCKED"
            and result["effect_disposition"] == "NOT_STARTED"
            and primary["reason"] == "INSTALLATION_BLOCKED"
            and primary["installation_classification"] == "BLOCKED"
            and primary["attempt_state"] == "CONSUMED"
        )
    if not valid:
        raise ValueError("INCIDENT_SEMANTICS_REJECTED")


def admit_incident() -> None:
    """Reprove original consumed authority and both immutable incident reports."""
    for path, digest in (
        (INSTALL_ATTEMPT_PATH, INSTALL_ATTEMPT_SHA256),
        (EXECUTE_REPORT_PATH, EXECUTE_REPORT_SHA256),
        (BLOCKED_REPORT_PATH, BLOCKED_REPORT_SHA256),
    ):
        data = read_record(path)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("INCIDENT_DIGEST_REJECTED")
        if read_record(path) != data:
            raise ObservationDrift("INCIDENT_RECORD_DRIFT")
        record = json.loads(data, object_pairs_hook=_unique)
        if path == INSTALL_ATTEMPT_PATH:
            if record != {
                "schema": "arch134-f1r1-d1s3-installation-attempt/v1",
                "automatic_retry": "NOT_AUTHORIZED",
                "status": "CONSUMED",
            }:
                raise ValueError("ORIGINAL_LATCH_REJECTED")
        else:
            _report_semantics(record, execute=path == EXECUTE_REPORT_PATH)


def _git(*args: str, repo_root: Path = WORKTREE) -> bytes:
    environment = {
        k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")
    }
    environment.update(
        GIT_OPTIONAL_LOCKS="0",
        GIT_NO_LAZY_FETCH="1",
        GIT_TERMINAL_PROMPT="0",
        GCM_INTERACTIVE="Never",
    )
    result = subprocess.run(
        (
            "git",
            "--no-replace-objects",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(repo_root),
            *args,
        ),
        capture_output=True,
        check=False,
        timeout=30,
        env=environment,
    )
    if result.returncode:
        raise ValueError("SOURCE_OBSERVATION_REJECTED")
    return result.stdout


def admit_source() -> None:
    """Exact reviewed R5 HEAD/tree, branch, live remote and clean source admission."""
    head, tree = (
        os.environ.get(REMOTE_HEAD_ENV, ""),
        os.environ.get(SOURCE_TREE_ENV, ""),
    )
    if any(re.fullmatch("[0-9a-f]{40}", value) is None for value in (head, tree)):
        raise ValueError("R5_SOURCE_INTERLOCK_REJECTED")
    _safe_ancestors(WORKTREE / "source")
    if (
        Path(__file__).resolve()
        != (
            WORKTREE
            / "src/trading_bot/supervised_release/successor_publication_recovery.py"
        ).resolve()
    ):
        raise ValueError("R5_IMPORT_SOURCE_REJECTED")
    for args, expected in (
        (("rev-parse", "HEAD"), head),
        (("rev-parse", "HEAD^{tree}"), tree),
        (("branch", "--show-current"), BRANCH),
        (("remote", "get-url", "origin"), ORIGIN),
        (("status", "--porcelain=v1", "--untracked-files=all"), ""),
        (("diff", "--cached", "--name-only"), ""),
        (("merge-base", ACCEPTED_HEAD, "HEAD"), ACCEPTED_HEAD),
        (("rev-parse", ACCEPTED_HEAD + "^{tree}"), ACCEPTED_TREE),
    ):
        if _git(*args).decode().strip() != expected:
            raise ValueError("R5_SOURCE_REJECTED")
    if (
        Path(_git("rev-parse", "--show-toplevel").decode().strip()).resolve()
        != WORKTREE.resolve()
    ):
        raise ValueError("R5_WORKTREE_REJECTED")
    if any(
        entry and entry[:1] != b"H"
        for entry in _git("ls-files", "-v", "-z").split(b"\0")
    ):
        raise ValueError("R5_HIDDEN_INDEX_FLAGS_REJECTED")
    rows = _git("ls-remote", "origin", "refs/heads/" + BRANCH).decode().splitlines()
    if len(rows) != 1 or rows[0].split() != [head, "refs/heads/" + BRANCH]:
        raise ValueError("R5_REMOTE_REJECTED")


def admit_predecessor_source() -> None:
    """Prove accepted D1S3 source separately from current R5 authority."""
    for args, expected in (
        (("rev-parse", "HEAD"), ACCEPTED_HEAD),
        (("rev-parse", "HEAD^{tree}"), ACCEPTED_TREE),
        (("branch", "--show-current"), PREDECESSOR_BRANCH),
        (("remote", "get-url", "origin"), ORIGIN),
        (("status", "--porcelain=v1", "--untracked-files=all"), ""),
    ):
        if _git(*args, repo_root=PREDECESSOR_WORKTREE).decode().strip() != expected:
            raise ValueError("PREDECESSOR_SOURCE_REJECTED")


def reconstruct_release() -> tuple[VerifiedRelease, RuntimeBinding, ReleasePaths]:
    """Collect exact admitted D1S3 checkout bytes, including reviewed CRLFs."""
    admit_predecessor_source()
    rows = (
        _git("ls-tree", "-r", ACCEPTED_HEAD, repo_root=PREDECESSOR_WORKTREE)
        .decode()
        .splitlines()
    )
    files = []
    for row in rows:
        metadata, name = row.split("\t", 1)
        if name in {"pyproject.toml", LAUNCHER_RELATIVE_PATH} or name.startswith(
            "src/trading_bot/"
        ):
            mode, kind, _ = metadata.split()
            if mode not in {"100644", "100755"} or kind != "blob":
                raise ValueError("PREDECESSOR_OBJECT_REJECTED")
            files.append(
                ReleaseFile(
                    name,
                    read_record(
                        PREDECESSOR_WORKTREE / name, 8 * 1024 * 1024, allow_empty=True
                    ),
                )
            )
    source_namespace(tuple(item.relative_path for item in files))
    inventory = tuple(
        ReleaseInventoryEntry(item.relative_path, item.sha256) for item in files
    )
    risk = (
        b'{"schema":"arch133-installation-risk-declaration/v1",'
        b'"mode":"paper","instruments":"US-stocks-ETFs","long_only":true,'
        b'"margin":false,"leverage":false,"options":false,"shorts":false,'
        b'"crypto":false,"deterministic_risk_required":true}'
    )
    manifest = ReleaseManifest(
        ACCEPTED_HEAD,
        ACCEPTED_TREE,
        PYTHON_VERSION,
        PYTHON_SHA256,
        LAUNCHER_RELATIVE_PATH,
        next(f.sha256 for f in files if f.relative_path == LAUNCHER_RELATIVE_PATH),
        inventory,
        STRATEGY_ID,
        STRATEGY_VERSION,
        MovingAverageCrossoverConfig(5, 20, Decimal("1")),
        "arch133-long-only-review-paper",
        "1.0.0",
        hashlib.sha256(risk).hexdigest(),
    )
    data = manifest.to_json().encode()
    if (
        manifest.release_id != RELEASE_ID
        or hashlib.sha256(data).hexdigest() != MANIFEST_SHA256
        or manifest.source_inventory_sha256 != INVENTORY_SHA256
    ):
        raise ValueError("PREDECESSOR_RELEASE_REJECTED")
    release = collect_release_bundle(PREDECESSOR_WORKTREE, declaration=manifest)
    if release.manifest != manifest:
        raise ObservationDrift("PREDECESSOR_COLLECTION_DRIFT")
    binding = RuntimeBinding(release)
    paths = replay_inputs(release, binding)
    if binding.sha256 != BINDING_SHA256 or (paths.final, paths.staging) != (
        FINAL_PATH,
        STAGING_PATH,
    ):
        raise ValueError("PREDECESSOR_BINDING_REJECTED")
    return release, binding, paths


def require_administrator() -> None:
    windows_libraries()
    administrator_sid()


def latch_consumed() -> bool:
    """Any existing R5 latch object consumes authority, even malformed evidence."""
    if ATTEMPT_PATH == INSTALL_ATTEMPT_PATH:
        raise ValueError("ORIGINAL_INSTALLATION_LATCH_FORBIDDEN")
    _safe_ancestors(ATTEMPT_PATH)
    try:
        ATTEMPT_PATH.lstat()
    except FileNotFoundError:
        return False
    return True


def consume_attempt(mark_consumed: Callable[[], None]) -> None:
    """One exclusive reservation; every ambiguous reservation is terminal."""
    if latch_consumed():
        raise FileExistsError("CONSUMED_RECOVERY_ATTEMPT")
    # Only the separate R5 evidence parent may be created by protected execute.
    ATTEMPT_PATH.parent.mkdir(exist_ok=True)
    _safe_ancestors(ATTEMPT_PATH)
    with ATTEMPT_PATH.open("xb") as handle:
        mark_consumed()
        if handle.write(ATTEMPT_BYTES) != len(ATTEMPT_BYTES):
            raise OSError("RECOVERY_LATCH_PARTIAL_WRITE")
        handle.flush()
        os.fsync(handle.fileno())
    if read_record(ATTEMPT_PATH) != ATTEMPT_BYTES:
        raise OSError("RECOVERY_LATCH_READBACK_REJECTED")


@dataclass(frozen=True)
class Namespace:
    parent: ObjectFacts
    names: tuple[str, ...]
    final: ObjectFacts | None
    staging: ObjectFacts | None


def observe_namespace(paths: ReleasePaths) -> Namespace:
    with WindowsObserver().read_session(paths) as session:
        parent = observe_parent(session)
        names = session.names(RELEASES_BASE)
        if (
            parent.identity != PARENT_IDENTITY
            or type(names) is not tuple
            or len(names) > 4096
            or any(type(n) is not str for n in names)
            or len({n.casefold() for n in names}) != len(names)
        ):
            raise ValueError("PARENT_NAMESPACE_REJECTED")
        final = session.object(paths.final, directory=True)
        staging = session.object(paths.staging, directory=True)
        if (RELEASE_ID in names) != (final is not None) or (
            RELEASE_ID + ".installing" in names
        ) != (staging is not None):
            raise ValueError("NAMESPACE_OBJECT_REJECTED")
        for fact, path in ((final, paths.final), (staging, paths.staging)):
            if fact is not None:
                check_object(fact, path, directory=True, volume=PARENT_IDENTITY[0])
                if fact.identity != STAGING_IDENTITY:
                    raise ValueError("PRESERVED_IDENTITY_REJECTED")
        if session.names(RELEASES_BASE) != names or observe_parent(session) != parent:
            raise ObservationDrift("PARENT_NAMESPACE_DRIFT")
        return Namespace(parent, names, final, staging)


def replay_image(
    release: VerifiedRelease, binding: RuntimeBinding, *, final: bool
) -> InstalledEvidence:
    observer = observe_installed_release if final else observe_staging_release
    evidence = observer(release, binding, native=WindowsObserver())
    return evidence


def _admit() -> tuple[
    VerifiedRelease, RuntimeBinding, ReleasePaths, Namespace, InstalledEvidence
]:
    admit_source()
    admit_predecessor_source()
    admit_incident()
    require_administrator()
    release, binding, paths = reconstruct_release()
    before = observe_namespace(paths)
    if before != observe_namespace(paths):
        raise ObservationDrift("PRESERVED_NAMESPACE_DRIFT")
    if before.final is not None and before.staging is not None:
        raise ValueError("NAMESPACE_CONFLICT")
    if before.final is None and before.staging is None:
        raise ValueError("PRESERVED_IMAGE_MISSING")
    final = before.final is not None
    first = replay_image(release, binding, final=final)
    second = replay_image(release, binding, final=final)
    if first != second:
        raise ObservationDrift("IMAGE_REPLAY_DRIFT")
    validate_image(first)
    # Repeat critical source, incident, predecessor and image observations.
    admit_source()
    admit_incident()
    admit_predecessor_source()
    if (
        replay_image(release, binding, final=final) != first
        or observe_namespace(paths) != before
    ):
        raise ObservationDrift("PRESERVED_IMAGE_DRIFT")
    return release, binding, paths, before, first


def _result(
    status: str,
    reason: str,
    *,
    consumed: bool | None = None,
    evidence: InstalledEvidence | None = None,
    namespace: Namespace | None = None,
    eligible: bool = False,
    confirmed: bool = False,
) -> dict[str, object]:
    return {
        "status": status,
        "effect_disposition": "CONFIRMED"
        if confirmed
        else "MAY_HAVE_OCCURRED"
        if status == "INDETERMINATE"
        else "NOT_STARTED",
        "automatic_retry": "NOT_AUTHORIZED",
        "primary": {
            "schema": SCHEMA,
            "status": reason if status == "PASS" else status,
            "reason": reason,
            "execute_eligible": eligible,
            "disposition": "PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY"
            if status == "INDETERMINATE"
            else "VERIFIED"
            if confirmed
            else "NO_PUBLICATION_EFFECT",
            "attempt_state": "UNKNOWN"
            if consumed is None
            else "CONSUMED"
            if consumed
            else "AVAILABLE",
            "attempt_path": str(ATTEMPT_PATH),
            "namespace": None
            if namespace is None
            else {
                "classification": "EXACT_FINAL_ONLY"
                if namespace.final
                else "EXACT_STAGING_ONLY",
                "parent_identity": namespace.parent.identity,
                "names": namespace.names,
                "final_present": namespace.final is not None,
                "staging_present": namespace.staging is not None,
            },
            "image": None if evidence is None else asdict(evidence),
            "incident_execute_sha256": EXECUTE_REPORT_SHA256,
            "incident_blocked_preflight_sha256": BLOCKED_REPORT_SHA256,
            "predecessor_head": ACCEPTED_HEAD,
            "predecessor_tree": ACCEPTED_TREE,
            "source_head": os.environ.get(REMOTE_HEAD_ENV),
            "source_tree": os.environ.get(SOURCE_TREE_ENV),
        },
    }


def preflight() -> dict[str, object]:
    """Read-only reconciliation remains useful after any consumed R5 attempt."""
    consumed = None
    try:
        release, binding, paths, namespace, evidence = _admit()
        consumed = latch_consumed()
        admit_source()
        admit_predecessor_source()
        admit_incident()
        if (
            observe_namespace(paths) != namespace
            or replay_image(release, binding, final=namespace.final is not None)
            != evidence
        ):
            raise ObservationDrift("FINAL_PREFLIGHT_OBSERVATION_DRIFT")
        if consumed != latch_consumed():
            raise ObservationDrift("RECOVERY_LATCH_DRIFT")
        if namespace.final:
            return _result(
                "PASS" if consumed else "BLOCKED",
                "FINAL_PUBLISHED_VERIFIED"
                if consumed
                else "FINAL_PRESENT_BEFORE_RECOVERY",
                consumed=consumed,
                evidence=evidence,
                namespace=namespace,
                confirmed=consumed,
            )
        return _result(
            "BLOCKED" if consumed else "PASS",
            "CONSUMED_RECOVERY_ATTEMPT"
            if consumed
            else "READY_FOR_EXACT_PRESERVED_RELEASE_PUBLICATION",
            consumed=consumed,
            evidence=evidence,
            namespace=namespace,
            eligible=not consumed,
        )
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        return _result(
            "INDETERMINATE" if isinstance(exc, ObservationDrift) else "BLOCKED",
            str(exc) if isinstance(exc, ValueError) else "READ_ONLY_ADMISSION_REJECTED",
            consumed=consumed,
        )


def execute_once() -> dict[str, object]:
    """One publication request; all post-fence ambiguity preserves no-retry evidence."""
    consumed = False
    fence_attempted = False

    def mark() -> None:
        nonlocal consumed
        consumed = True

    try:
        if os.environ.get(AUTH_ENV) != AUTH_VALUE:
            return _result("BLOCKED", "AUTHORIZATION_REJECTED")
        _, _, paths, before, evidence = _admit()
        if before.final or latch_consumed():
            return _result(
                "BLOCKED", "RECOVERY_NOT_ELIGIBLE", consumed=latch_consumed()
            )
        # A second full admission finishes before the exclusive durable fence.
        if _admit()[3:] != (before, evidence):
            raise ObservationDrift("PRE_FENCE_ADMISSION_DRIFT")
        fence_attempted = True
        consume_attempt(mark)
        if (
            not consumed
            or not latch_consumed()
            or read_record(ATTEMPT_PATH) != ATTEMPT_BYTES
        ):
            raise OSError("DURABLE_FENCE_ACKNOWLEDGEMENT_REQUIRED")
        from trading_bot.supervised_release.successor_native_publication import (
            publish_preserved_image,
        )

        if publish_preserved_image(evidence) is not True:
            raise OSError("PUBLICATION_NOT_CONFIRMED")
        _, _, _, after, final_evidence = _admit()
        expected_names = tuple(
            sorted(
                RELEASE_ID if name == RELEASE_ID + ".installing" else name
                for name in before.names
            )
        )
        if (
            after.final is None
            or after.staging is not None
            or after.parent != before.parent
            or tuple(sorted(after.names)) != expected_names
            or final_evidence != evidence
            or after.final.identity != STAGING_IDENTITY
            or not latch_consumed()
            or read_record(ATTEMPT_PATH) != ATTEMPT_BYTES
            or paths != ReleasePaths(RELEASE_ID)
        ):
            raise ObservationDrift("POST_PUBLICATION_DRIFT")
        return _result(
            "PASS",
            "FINAL_PUBLISHED_VERIFIED",
            consumed=True,
            evidence=final_evidence,
            namespace=after,
            confirmed=True,
        )
    except (Exception, KeyboardInterrupt, SystemExit):
        ambiguous = consumed or fence_attempted
        return _result(
            "INDETERMINATE" if ambiguous else "BLOCKED",
            "PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY"
            if ambiguous
            else "PUBLICATION_ADMISSION_REJECTED",
            consumed=True if ambiguous else None,
        )
