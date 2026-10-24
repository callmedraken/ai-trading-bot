"""D1S4 exact-source direct installation and production-read-only reconciliation.

Inert at import. Mutation is isolated behind a durable, release-derived attempt
and the exact protected interlock. No other deployment operator is reachable.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_acl.read_only import ADMINISTRATORS_SID, SYSTEM_SID
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    MAX_FILE_BYTES,
    VerifiedRelease,
    canonical_json,
    source_namespace,
)
from trading_bot.supervised_release.collector import collect_release_bundle
from trading_bot.supervised_release.installation_contract import (
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstalledEvidence,
    ObjectFacts,
    ReadSession,
)
from trading_bot.supervised_release.model import (
    LAUNCHER_RELATIVE_PATH,
    PRODUCTION_PYTHON,
    RELEASES_BASE,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ReleaseInventoryEntry,
    ReleaseManifest,
    release_root,
)
from trading_bot.supervised_release.native_read import (
    WindowsObserver,
    windows_libraries,
)
from trading_bot.supervised_release.observer import (
    check_object,
    observe_installed_release,
    observe_parent,
    replay_inputs,
)

CHECKPOINT = "arch134-f1r1-d1s4-rename-free-direct-installation"
SCHEMA = CHECKPOINT + "/v1"
BRANCH = (
    "feature/robinhood-production-paper-134f1r1-d1s4-rename-free-direct-install-current"
)
WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-"
    r"d1s4-rename-free-direct-install-current"
)
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
BASE_HEAD = "1e9b6a0638f00ddb009bdb7934039b7a9047e678"
BASE_TREE = "1ef95f954cfce509a6b90639b8bb9599e2e9206f"
REMOTE_HEAD_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_ACCEPTED_HEAD"
SOURCE_TREE_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_ACCEPTED_TREE"
AUTH_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_DIRECT_INSTALL_AUTHORIZATION"
AUTH_VALUE = "ARCH134_F1R1_D1S4_ONE_RENAME_FREE_IMMUTABLE_RELEASE_INSTALL_AUTHORIZED"
ATTEMPT_SCHEMA = "arch134-f1r1-d1s4-rename-free-direct-install-attempt/v1"
ATTEMPT_ROOT = Path(r"F:\AI\temp")
INCIDENT_RELEASE_ID = "release-cb94451fc3295a97afffe9fac5d09ff3"
PRESERVE = "PRESERVE_DIRECT_INSTALLATION_EVIDENCE_NO_RETRY"
ZERO_PROTECTED_EFFECTS = (
    ("SUCCESSOR_ROOT_PROVISIONING", 0),
    ("SCHEDULER_READS", 0),
    ("SCHEDULER_MUTATIONS", 0),
    ("REAL_CREDENTIAL_READS", 0),
    ("PROVIDER_REQUESTS", 0),
    ("PAPER_MUTATIONS", 0),
    ("BROKER_EFFECTS", 0),
    ("D1_OPERATIONAL_EFFECTS", 0),
    ("D2_EFFECTS", 0),
    ("LIVE_EFFECTS", 0),
    ("D1S3_R5_EVIDENCE_MUTATIONS", 0),
)
RISK_MATERIAL = (
    b'{"schema":"arch133-installation-risk-declaration/v1",'
    b'"mode":"paper","instruments":"US-stocks-ETFs","long_only":true,'
    b'"margin":false,"leverage":false,"options":false,"shorts":false,'
    b'"crypto":false,"deterministic_risk_required":true}'
)


class ObservationDrift(ValueError):
    """Repeated exact observations disagree; no effect authority survives."""


@dataclass(frozen=True, slots=True)
class Attempt:
    classification: str
    path: str
    payload_sha256: str | None = None
    identity: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class Namespace:
    parent: ObjectFacts
    python: ObjectFacts
    names: tuple[str, ...]
    final: ObjectFacts | None


def safe_ancestors(path: Path) -> None:
    """Reject links/reparse components before source or latch traversal."""
    for ancestor in reversed(path.parents):
        fact = ancestor.lstat()
        if (
            not stat.S_ISDIR(fact.st_mode)
            or stat.S_ISLNK(fact.st_mode)
            or getattr(fact, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("ANCESTOR_REJECTED")


def read_record(path: Path, limit: int) -> tuple[bytes, tuple[int, int]]:
    """Bounded regular-file observation with stable path and open-handle facts."""
    safe_ancestors(path)
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or getattr(before, "st_file_attributes", 0) & 0x400
        or before.st_nlink != 1
        or not 0 <= before.st_size <= limit
    ):
        raise ValueError("RECORD_OBJECT_REJECTED")
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        data = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    final = path.lstat()
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
    signature = tuple(getattr(before, name) for name in fields)
    if (
        any(
            tuple(getattr(row, name) for name in fields) != signature
            for row in (opened, after, final)
        )
        or opened.st_ctime_ns != after.st_ctime_ns
        or before.st_ctime_ns != final.st_ctime_ns
        or len(data) != before.st_size
    ):
        raise ObservationDrift("RECORD_OBSERVATION_DRIFT")
    return data, (before.st_dev, before.st_ino)


def _git(*args: str) -> bytes:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
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
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(WORKTREE),
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


def admit_source() -> tuple[str, str]:
    """Prove exact local module/worktree and accepted live feature HEAD/tree."""
    head = os.environ.get(REMOTE_HEAD_ENV, "")
    tree = os.environ.get(SOURCE_TREE_ENV, "")
    if any(re.fullmatch("[0-9a-f]{40}", value) is None for value in (head, tree)):
        raise ValueError("SOURCE_INTERLOCK_REJECTED")
    safe_ancestors(WORKTREE / "source")
    expected_module = (
        WORKTREE / "src/trading_bot/supervised_release/successor_direct_installation.py"
    )
    if Path(__file__).resolve() != expected_module.resolve():
        raise ValueError("IMPORT_SOURCE_REJECTED")
    for args, expected in (
        (("rev-parse", "HEAD"), head),
        (("rev-parse", "HEAD^{tree}"), tree),
        (("branch", "--show-current"), BRANCH),
        (("remote", "get-url", "origin"), ORIGIN),
        (("status", "--porcelain=v1", "--untracked-files=all"), ""),
        (("diff", "--cached", "--name-only"), ""),
        (("merge-base", BASE_HEAD, "HEAD"), BASE_HEAD),
        (("rev-parse", BASE_HEAD + "^{tree}"), BASE_TREE),
    ):
        if _git(*args).decode("utf-8").strip() != expected:
            raise ValueError("SOURCE_REJECTED")
    if (
        Path(_git("rev-parse", "--show-toplevel").decode().strip()).resolve()
        != WORKTREE.resolve()
    ):
        raise ValueError("WORKTREE_REJECTED")
    if any(
        row and row[:1] != b"H" for row in _git("ls-files", "-v", "-z").split(b"\0")
    ):
        raise ValueError("HIDDEN_INDEX_FLAGS_REJECTED")
    remote_ref = "refs/heads/" + BRANCH
    rows = _git("ls-remote", "origin", remote_ref).decode().splitlines()
    if len(rows) != 1 or rows[0].split() != [head, remote_ref]:
        raise ValueError("REMOTE_REJECTED")
    return head, tree


def reconstruct_release() -> tuple[VerifiedRelease, RuntimeBinding]:
    """Collect only accepted current checkout bytes, preserving exact CRLF policy."""
    head, tree = admit_source()
    files = []
    for row in _git("ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if not row:
            continue
        metadata, raw_name = row.split(b"\t", 1)
        name = raw_name.decode("utf-8")
        if name in {"pyproject.toml", LAUNCHER_RELATIVE_PATH} or name.startswith(
            "src/trading_bot/"
        ):
            mode, kind, _ = metadata.decode().split()
            if mode not in {"100644", "100755"} or kind != "blob":
                raise ValueError("SOURCE_OBJECT_REJECTED")
            data, _ = read_record(WORKTREE / name, MAX_FILE_BYTES)
            files.append(ReleaseInventoryEntry(name, hashlib.sha256(data).hexdigest()))
    inventory = tuple(sorted(files, key=lambda row: row.relative_path))
    source_namespace(tuple(row.relative_path for row in inventory))
    manifest = ReleaseManifest(
        head,
        tree,
        PYTHON_VERSION,
        PYTHON_SHA256,
        LAUNCHER_RELATIVE_PATH,
        next(
            row.sha256
            for row in inventory
            if row.relative_path == LAUNCHER_RELATIVE_PATH
        ),
        inventory,
        STRATEGY_ID,
        STRATEGY_VERSION,
        MovingAverageCrossoverConfig(5, 20, Decimal("1")),
        "arch133-long-only-review-paper",
        "1.0.0",
        hashlib.sha256(RISK_MATERIAL).hexdigest(),
    )
    release = collect_release_bundle(WORKTREE, declaration=manifest)
    if release.manifest != manifest or admit_source() != (head, tree):
        raise ObservationDrift("SOURCE_COLLECTION_DRIFT")
    binding = RuntimeBinding(release)
    replay_inputs(release, binding)
    if manifest.release_id == INCIDENT_RELEASE_ID:
        raise ValueError("INCIDENT_RELEASE_FORBIDDEN")
    return release, binding


def attempt_path(release: VerifiedRelease) -> Path:
    """No caller-selected attempt name or destination is accepted."""
    paths = replay_inputs(release, RuntimeBinding(release))
    return ATTEMPT_ROOT / (
        "arch134-f1r1-d1s4-direct-install-attempt-" + paths.release_id + ".json"
    )


def attempt_bytes(release: VerifiedRelease) -> bytes:
    return (
        canonical_json(
            {
                "schema": ATTEMPT_SCHEMA,
                "release_id": release.manifest.release_id,
                "source_head": release.expected_source_head,
                "source_tree": release.expected_source_tree,
                "status": "CONSUMED",
                "automatic_retry": "NOT_AUTHORIZED",
            }
        )
        + "\n"
    ).encode("utf-8")


def observe_attempt(release: VerifiedRelease) -> Attempt:
    path = attempt_path(release)
    try:
        safe_ancestors(path)
        try:
            path.lstat()
        except FileNotFoundError:
            return Attempt("AVAILABLE", str(path))
        data, identity = read_record(path, 4096)
        return Attempt(
            "CONSUMED" if data == attempt_bytes(release) else "INDETERMINATE",
            str(path),
            hashlib.sha256(data).hexdigest(),
            identity,
        )
    except (OSError, ValueError):
        return Attempt("INDETERMINATE", str(path))


def consume_attempt(release: VerifiedRelease) -> Attempt:
    """Exclusive create, durable close and exact readback before native import."""
    path = attempt_path(release)
    if observe_attempt(release).classification != "AVAILABLE":
        raise ValueError("ATTEMPT_NOT_AVAILABLE")
    safe_ancestors(path)
    payload = attempt_bytes(release)
    with path.open("xb") as handle:
        created = os.fstat(handle.fileno())
        created_identity = (created.st_dev, created.st_ino)
        if handle.write(payload) != len(payload):
            raise OSError("ATTEMPT_PARTIAL_WRITE")
        handle.flush()
        os.fsync(handle.fileno())
    result = observe_attempt(release)
    if (
        result.classification != "CONSUMED"
        or result.payload_sha256 != hashlib.sha256(payload).hexdigest()
        or result.identity != created_identity
    ):
        raise ValueError("ATTEMPT_READBACK_REJECTED")
    return result


def require_administrator() -> None:
    windows_libraries()
    administrator_sid()


def observe_python(session: ReadSession, volume: int) -> ObjectFacts:
    """Independent binary hash/resource-version observation; never start Python."""
    facts = []
    for path, directory in (
        (r"F:\AITradingBot\runtime", True),
        (PRODUCTION_PYTHON, False),
    ):
        row = check_object(
            session.object(path, directory=directory),
            path,
            directory=directory,
            volume=volume,
            image_policy=False,
        )
        if row.owner not in {ADMINISTRATORS_SID, SYSTEM_SID} or any(
            kind != 0
            or flags & ~0x13
            or (sid not in {ADMINISTRATORS_SID, SYSTEM_SID} and mask & ~0x1200A9)
            for sid, mask, kind, flags in row.aces
        ):
            raise ValueError("PYTHON_SECURITY_REJECTED")
        facts.append(row)
    data = session.read(PRODUCTION_PYTHON, MAX_FILE_BYTES)
    if (
        len(data) != facts[1].size
        or hashlib.sha256(data).hexdigest() != PYTHON_SHA256
        or session.python_version() != PYTHON_VERSION
        or any(
            session.object(row.path, directory=row.kind == "directory") != row
            for row in facts
        )
    ):
        raise ValueError("PYTHON_IDENTITY_REJECTED")
    return facts[1]


def observe_namespace(release: VerifiedRelease, binding: RuntimeBinding) -> Namespace:
    paths = replay_inputs(release, binding)
    with WindowsObserver().read_session(paths) as session:
        parent = observe_parent(session)
        python = observe_python(session, parent.identity[0])
        names = session.names(RELEASES_BASE)
        if (
            type(names) is not tuple
            or len(names) > 20002
            or any(type(name) is not str for name in names)
            or len({name.casefold() for name in names}) != len(names)
        ):
            raise ValueError("NAMESPACE_REJECTED")
        final = session.object(paths.final, directory=True)
        if (paths.release_id in names) != (final is not None) or any(
            name.casefold() == paths.release_id.casefold() and name != paths.release_id
            for name in names
        ):
            raise ObservationDrift("FINAL_NAMESPACE_DRIFT")
        if (
            session.object(paths.final, directory=True) != final
            or session.names(RELEASES_BASE) != names
            or observe_parent(session) != parent
        ):
            raise ObservationDrift("NAMESPACE_OBSERVATION_DRIFT")
        result = Namespace(parent, python, tuple(sorted(names)), final)
    return result


def verify_final(
    release: VerifiedRelease, binding: RuntimeBinding, namespace: Namespace
) -> InstalledEvidence:
    evidence = observe_installed_release(release, binding)
    if (
        type(evidence) is not InstalledEvidence
        or namespace.final is None
        or evidence.release_id != release.manifest.release_id
        or evidence.manifest_sha256 != release.expected_manifest_sha256
        or evidence.binding_sha256 != binding.sha256
        or evidence.parent_identity != namespace.parent.identity
        or evidence.image_identity != namespace.final.identity
        or evidence.python_identity != namespace.python.identity
        or evidence.python_sha256 != release.manifest.production_python_sha256
        or evidence.python_version != PYTHON_VERSION
        or evidence.dependency_closure != "UNPROVEN"
    ):
        raise ValueError("FINAL_EVIDENCE_REJECTED")
    return evidence


def _result(
    status: str,
    reason: str,
    *,
    release=None,
    binding=None,
    attempt=None,
    namespace=None,
    evidence=None,
    stable=False,
    eligible=False,
    final_classification="UNOBSERVED",
    effect="NOT_STARTED",
) -> dict[str, object]:
    return {
        "status": status,
        "effect_disposition": effect,
        "automatic_retry": "NOT_AUTHORIZED",
        "protected_effects": [list(row) for row in ZERO_PROTECTED_EFFECTS],
        "primary": {
            "schema": SCHEMA,
            "status": status,
            "reason": reason,
            "source_head": release.expected_source_head if release else None,
            "source_tree": release.expected_source_tree if release else None,
            "release_id": release.manifest.release_id if release else None,
            "final_path": release_root(release.manifest.release_id)
            if release
            else None,
            "manifest_sha256": release.expected_manifest_sha256 if release else None,
            "source_inventory_sha256": release.manifest.source_inventory_sha256
            if release
            else None,
            "binding_sha256": binding.sha256 if binding else None,
            "attempt": asdict(attempt) if attempt else None,
            "latch_classification": attempt.classification if attempt else "UNOBSERVED",
            "final_classification": final_classification,
            "final_identity": namespace.final.identity
            if namespace and namespace.final
            else None,
            "parent_identity": namespace.parent.identity if namespace else None,
            "python_identity": namespace.python.identity if namespace else None,
            "python_sha256": PYTHON_SHA256 if namespace else None,
            "python_version": PYTHON_VERSION if namespace else None,
            "namespace": asdict(namespace) if namespace else None,
            "image": asdict(evidence) if evidence else None,
            "repeated_observation_stable": stable,
            "execute_eligible": eligible,
            "disposition": PRESERVE
            if status == "INDETERMINATE"
            else "VERIFIED"
            if evidence
            else "NO_INSTALLATION_EFFECT",
            "automatic_retry": "NOT_AUTHORIZED",
            "effect_disposition": effect,
        },
    }


def preflight() -> dict[str, object]:
    """Closed read-only state machine; consumed authority is never renewed."""
    release = binding = attempt = namespace = evidence = None
    classification = "UNOBSERVED"
    stable = False
    try:
        source = admit_source()
        release, binding = reconstruct_release()
        if source != (release.expected_source_head, release.expected_source_tree):
            raise ObservationDrift("SOURCE_REPLAY_DRIFT")
        require_administrator()
        namespace = observe_namespace(release, binding)
        attempt = observe_attempt(release)
        classification = "ABSENT" if namespace.final is None else "PRESENT_UNVERIFIED"
        image_error = False
        if attempt.classification == "CONSUMED" and namespace.final is not None:
            try:
                first = verify_final(release, binding, namespace)
                second = verify_final(release, binding, namespace)
                if first != second:
                    raise ObservationDrift("FINAL_REPLAY_DRIFT")
                evidence = first
                classification = "EXACT_VERIFIED"
            except ObservationDrift:
                raise
            except (Exception, KeyboardInterrupt, SystemExit):
                image_error = True
                classification = "PARTIAL_OR_CONFLICTING"
        if (
            observe_namespace(release, binding) != namespace
            or observe_attempt(release) != attempt
            or admit_source() != source
        ):
            raise ObservationDrift("ADMISSION_OBSERVATION_DRIFT")
        stable = True
        if attempt.classification == "INDETERMINATE":
            status, reason, eligible = "INDETERMINATE", "LATCH_UNPROVEN", False
        elif attempt.classification == "AVAILABLE":
            eligible = namespace.final is None
            status, reason = (
                ("PASS", "READY_FOR_RENAME_FREE_MATERIALIZATION")
                if eligible
                else ("BLOCKED", "UNOWNED_FINAL_PRESENT")
            )
        elif namespace.final is None:
            status, reason, eligible = "BLOCKED", "CONSUMED_ATTEMPT_NO_IMAGE", False
        elif image_error:
            status, reason, eligible = (
                "BLOCKED",
                "PARTIAL_OR_CONFLICTING_DEPLOYMENT",
                False,
            )
        else:
            status, reason, eligible = "PASS", "DIRECT_INSTALL_VERIFIED", False
        return _result(
            status,
            reason,
            release=release,
            binding=binding,
            attempt=attempt,
            namespace=namespace,
            evidence=evidence,
            stable=stable,
            eligible=eligible,
            final_classification=classification,
        )
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        return _result(
            "INDETERMINATE" if isinstance(exc, ObservationDrift) else "BLOCKED",
            "OBSERVATION_DRIFT"
            if isinstance(exc, ObservationDrift)
            else "READ_ONLY_ADMISSION_REJECTED",
            release=release,
            binding=binding,
            attempt=attempt,
            namespace=namespace,
            final_classification=classification,
        )


def execute_once() -> dict[str, object]:
    """Future one-shot execute. Never invoked during source implementation."""
    release = binding = attempt = before = after = evidence = None
    reservation_started = mutation_fence = False
    try:
        if os.environ.get(AUTH_ENV) != AUTH_VALUE:
            return _result("BLOCKED", "AUTHORIZATION_REJECTED")
        source = admit_source()
        release, binding = reconstruct_release()
        if source != (release.expected_source_head, release.expected_source_tree):
            raise ObservationDrift("SOURCE_REPLAY_DRIFT")
        require_administrator()
        before = observe_namespace(release, binding)
        attempt = observe_attempt(release)
        if before.final is not None or attempt.classification != "AVAILABLE":
            return _result(
                "BLOCKED",
                "DIRECT_INSTALL_NOT_ELIGIBLE",
                release=release,
                binding=binding,
                namespace=before,
                attempt=attempt,
            )
        if (
            admit_source() != source
            or observe_namespace(release, binding) != before
            or observe_attempt(release) != attempt
        ):
            raise ObservationDrift("PRE_RESERVATION_DRIFT")
        reservation_started = True
        attempt = consume_attempt(release)
        if attempt != observe_attempt(release) or attempt.classification != "CONSUMED":
            raise ObservationDrift("DURABLE_ATTEMPT_REJECTED")
        from trading_bot.supervised_release.successor_native_direct_write import (
            materialize_release,
        )

        mutation_fence = True
        if (
            materialize_release(release, binding, before.parent, before.python)
            is not True
        ):
            raise ValueError("NATIVE_RESULT_UNCONFIRMED")
        # The native function has closed ALL handles before either independent replay.
        after = observe_namespace(release, binding)
        if (
            after.parent != before.parent
            or after.python != before.python
            or after.final is None
            or after.names
            != tuple(sorted((*before.names, release.manifest.release_id)))
        ):
            raise ObservationDrift("DIRECT_IMAGE_NAMESPACE_DRIFT")
        first = verify_final(release, binding, after)
        second = verify_final(release, binding, after)
        if first != second:
            raise ObservationDrift("DIRECT_IMAGE_REPLAY_DRIFT")
        if (
            observe_namespace(release, binding) != after
            or admit_source() != source
            or observe_attempt(release) != attempt
        ):
            raise ObservationDrift("POST_INSTALL_ADMISSION_DRIFT")
        evidence = first
        return _result(
            "PASS",
            "DIRECT_INSTALL_VERIFIED",
            release=release,
            binding=binding,
            attempt=attempt,
            namespace=after,
            evidence=evidence,
            stable=True,
            final_classification="EXACT_VERIFIED",
            effect="CONFIRMED",
        )
    except (Exception, KeyboardInterrupt, SystemExit):
        if reservation_started and (
            attempt is None or attempt.classification != "CONSUMED"
        ):
            attempt = Attempt("INDETERMINATE", str(attempt_path(release)))
        return _result(
            "INDETERMINATE" if reservation_started else "BLOCKED",
            PRESERVE if reservation_started else "DIRECT_INSTALL_ADMISSION_REJECTED",
            release=release,
            binding=binding,
            attempt=attempt,
            namespace=after or before,
            effect="MAY_HAVE_OCCURRED" if mutation_fence else "NOT_STARTED",
            final_classification="UNPROVEN_AFTER_ATTEMPT"
            if mutation_fence
            else "UNOBSERVED",
        )
