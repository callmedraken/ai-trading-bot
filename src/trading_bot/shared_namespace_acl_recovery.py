"""D1S4-R1 closed two-object ACL recovery; inert until registered invocation.

No release installation or runtime admission is conferred by this operator.
All paths, policies, identities and incident objects are source-owned.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_acl.read_only import (
    ADMIN_ACES,
    ADMINISTRATORS_SID,
    SYSTEM_SID,
    TRADING_SID,
)

CHECKPOINT = "arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery"
SCHEMA = CHECKPOINT + "/v1"
PLAN_SCHEMA = CHECKPOINT + "-plan/v1"
ATTEMPT_SCHEMA = CHECKPOINT + "-attempt/v1"
BRANCH = (
    "feature/robinhood-production-paper-134f1r1-"
    "d1s4-r1-shared-namespace-acl-recovery-current"
)
WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-d1s4-r1-shared-namespace-acl-recovery-current"
)
BASE_HEAD = "30a410d9023324ebe5c23e6a8ff128353b9ebf1f"
BASE_TREE = "cf50b0b7b84428d9e502ed5bd85307001bc866ed"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
HEAD_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_R1_ACCEPTED_HEAD"
TREE_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_R1_ACCEPTED_TREE"
PLAN_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_R1_REVIEWED_PLAN_SHA256"
AUTH_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S4_R1_ACL_RECOVERY_AUTHORIZATION"
AUTH_VALUE = "ARCH134_F1R1_D1S4_R1_ONE_SHARED_NAMESPACE_ACL_RECOVERY_AUTHORIZED"
ATTEMPT_PATH = Path(
    r"F:\AI\temp\arch134-f1r1-d1s4-r1-shared-namespace-acl-recovery-attempt.json"
)
DRIFT_SID = "S-1-5-21-1397534616-3988210162-180023805-1005"
DRIFT_ACE = (DRIFT_SID, 0x1F01FF, 0, 3)
TARGET_PATHS = (r"F:\AITradingBot", r"F:\AITradingBot\releases")
TARGET_IDENTITIES = ((1855336320, 1125899907973390), (1855336320, 281474980511321))
PRE_HASHES = (
    "292a285f86a102698ab1b212a998d18178ba4c7e8cbe0c25ac195a747fb944d9",
    "7113305203979cd4dd63a92a5239e9de9e2d4de0212610c149ef834babbee6de",
)
IMAGE_ACES = ADMIN_ACES + ((TRADING_SID, 0x1200A9, 0, 0),)
POST_ACES = (ADMIN_ACES, IMAGE_ACES)
PRE_ACES = tuple(policy + (DRIFT_ACE,) for policy in POST_ACES)
INCIDENT_RELEASE_IDS = (
    "release-18d5d329c1d458558e98d7effe523c3b",
    "release-cb94451fc3295a97afffe9fac5d09ff3",
    "release-03c42597246752319956ab96e01ed61c",
)
PRESERVED_PATHS = (
    TARGET_PATHS[1] + "\\" + INCIDENT_RELEASE_IDS[0],
    *(
        TARGET_PATHS[1] + "\\" + item + ".installing"
        for item in INCIDENT_RELEASE_IDS[1:]
    ),
)
RUNTIME_PATHS = (r"F:\AITradingBot\runtime", r"F:\AITradingBot\runtime\python.exe")
VOLUME_PATH = "F:\\"
OBSERVED_PATHS = (VOLUME_PATH, *TARGET_PATHS, *RUNTIME_PATHS, *PRESERVED_PATHS)
# The first target is the outer boundary; stop without touching the second on failure.
MUTATION_ORDER = TARGET_PATHS
PRESERVE = "PRESERVE_SHARED_NAMESPACE_ACL_RECOVERY_EVIDENCE_NO_RETRY"
ZERO_EFFECTS = (
    ("PROVIDER_REQUESTS", 0),
    ("REAL_CREDENTIAL_READS", 0),
    ("SCHEDULER_READS", 0),
    ("SCHEDULER_MUTATIONS", 0),
    ("RUNTIME_STARTS", 0),
    ("PAPER_MUTATIONS", 0),
    ("BROKER_EFFECTS", 0),
    ("D1_EFFECTS", 0),
    ("D2_EFFECTS", 0),
    ("LIVE_EFFECTS", 0),
    ("PRESERVED_RELEASE_MUTATIONS", 0),
)
_lock = Lock()
_spent = False


class RecoveryRejected(ValueError):
    """Closed diagnostics only."""


@dataclass(frozen=True, slots=True)
class ObjectFacts:
    """Fixed security observation; independent of release/strategy/provider models."""

    path: str
    kind: str
    identity: tuple[int, int]
    owner: str
    protected: bool
    aces: tuple[tuple[str, int, int, int], ...]
    filesystem: str = "NTFS"
    local: bool = True
    persistent_acls: bool = True
    reparse: bool = False
    links: int = 1
    size: int = 0


@dataclass(frozen=True, slots=True)
class SecurityEvidence:
    facts: ObjectFacts
    descriptor_sha256: str


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(WORKTREE), *args],
        check=True,
        capture_output=True,
        timeout=30,
    )
    if len(result.stdout) > 2_000_000:
        raise RecoveryRejected("SOURCE_BUDGET_REJECTED")
    return result.stdout.decode("utf-8").strip()


def admit_source() -> tuple[str, str]:
    """Exact installed source, clean index, base ancestry and live remote equality."""
    head, tree = _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")
    if any(re.fullmatch(r"[0-9a-f]{40}", item) is None for item in (head, tree)):
        raise RecoveryRejected("SOURCE_IDENTITY_REJECTED")
    if (head, tree) != (os.environ.get(HEAD_ENV), os.environ.get(TREE_ENV)):
        raise RecoveryRejected("SOURCE_INTERLOCK_REJECTED")
    if Path(__file__).resolve().parents[2] != WORKTREE.resolve(strict=True):
        raise RecoveryRejected("SOURCE_LOCATION_REJECTED")
    for args, expected in (
        (("branch", "--show-current"), BRANCH),
        (("remote", "get-url", "origin"), ORIGIN),
        (("status", "--porcelain=v1", "--untracked-files=all"), ""),
        (("diff", "--cached", "--name-only"), ""),
        (("merge-base", BASE_HEAD, "HEAD"), BASE_HEAD),
        (("rev-parse", BASE_HEAD + "^{tree}"), BASE_TREE),
    ):
        if _git(*args) != expected:
            raise RecoveryRejected("SOURCE_ADMISSION_REJECTED")
    if Path(_git("rev-parse", "--show-toplevel")).resolve() != WORKTREE.resolve():
        raise RecoveryRejected("SOURCE_LOCATION_REJECTED")
    if any(row and row[:1] != "H" for row in _git("ls-files", "-v").splitlines()):
        raise RecoveryRejected("SOURCE_INDEX_FLAGS_REJECTED")
    remote = "refs/heads/" + BRANCH
    if _git("ls-remote", "origin", remote).split() != [head, remote]:
        raise RecoveryRejected("SOURCE_REMOTE_REJECTED")
    return head, tree


def require_administrator() -> None:
    administrator_sid()


def _safe_ancestors(path: Path) -> None:
    for parent in reversed(path.parents):
        fact = parent.lstat()
        if (
            not stat.S_ISDIR(fact.st_mode)
            or stat.S_ISLNK(fact.st_mode)
            or fact.st_file_attributes & 0x400
        ):
            raise RecoveryRejected("LATCH_ANCESTOR_REJECTED")


def _read_latch() -> bytes | None:
    _safe_ancestors(ATTEMPT_PATH)
    try:
        before = ATTEMPT_PATH.lstat()
    except FileNotFoundError:
        return None
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_file_attributes & 0x400
        or before.st_size > 16384
    ):
        raise RecoveryRejected("LATCH_OBJECT_REJECTED")
    with ATTEMPT_PATH.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        data = handle.read(16385)
        after = os.fstat(handle.fileno())
    named = ATTEMPT_PATH.lstat()

    def key(value):
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)

    if (
        not key(before) == key(opened) == key(after) == key(named)
        or len(data) != before.st_size
    ):
        raise RecoveryRejected("LATCH_OBSERVATION_DRIFT")
    return data


def _latch_payload(plan: dict[str, object]) -> bytes:
    return (
        canonical(
            {
                "schema": ATTEMPT_SCHEMA,
                "source_head": plan["source_head"],
                "source_tree": plan["source_tree"],
                "plan_sha256": hashlib.sha256(canonical(plan)).hexdigest(),
                "target_identities": TARGET_IDENTITIES,
                "pre_descriptor_sha256": PRE_HASHES,
                "status": "CONSUMED",
                "automatic_retry": "NOT_AUTHORIZED",
            }
        )
        + b"\n"
    )


def observe_attempt(plan: dict[str, object]) -> str:
    try:
        data = _read_latch()
        if data is None:
            return "INDETERMINATE" if _spent else "AVAILABLE"
        return "CONSUMED" if data == _latch_payload(plan) else "INDETERMINATE"
    except (Exception, KeyboardInterrupt, SystemExit):
        return "INDETERMINATE"


def _consume_attempt(plan: dict[str, object]) -> None:
    global _spent
    if observe_attempt(plan) != "AVAILABLE":
        raise RecoveryRejected("ATTEMPT_UNAVAILABLE")
    _safe_ancestors(ATTEMPT_PATH)
    payload = _latch_payload(plan)
    handle = ATTEMPT_PATH.open("xb")
    # Exclusive creation is the durable reservation boundary. Preserve the named
    # object on every later failure, including context entry, metadata and close.
    _spent = True
    with handle:
        created = os.fstat(handle.fileno())
        if handle.write(payload) != len(payload):
            raise RecoveryRejected("LATCH_SHORT_WRITE")
        handle.flush()
        os.fsync(handle.fileno())
    if _read_latch() != payload:
        raise RecoveryRejected("LATCH_READBACK_REJECTED")
    named = ATTEMPT_PATH.lstat()
    if (created.st_dev, created.st_ino) != (named.st_dev, named.st_ino):
        raise RecoveryRejected("LATCH_IDENTITY_DRIFT")


def observe_fixed_scope() -> tuple[SecurityEvidence, ...]:
    from trading_bot.shared_namespace_acl_native import _observe

    return _observe()


def validate_scope(snapshot: tuple[SecurityEvidence, ...]) -> None:
    if type(snapshot) is not tuple or len(snapshot) != len(OBSERVED_PATHS):
        raise RecoveryRejected("FIXED_SCOPE_REJECTED")
    identities = set()
    for path, row in zip(OBSERVED_PATHS, snapshot, strict=True):
        if type(row) is not SecurityEvidence or type(row.facts) is not ObjectFacts:
            raise RecoveryRejected("OBSERVATION_TYPE_REJECTED")
        fact = row.facts
        if (
            fact.path != path
            or fact.kind != ("file" if path == RUNTIME_PATHS[1] else "directory")
            or fact.filesystem != "NTFS"
            or fact.reparse is not False
            or fact.local is not True
            or fact.persistent_acls is not True
            or fact.links != 1
            or type(fact.identity) is not tuple
            or len(fact.identity) != 2
            or any(type(value) is not int or value <= 0 for value in fact.identity)
            or fact.identity[0] != TARGET_IDENTITIES[0][0]
            or fact.identity in identities
            or re.fullmatch(r"[0-9a-f]{64}", row.descriptor_sha256) is None
        ):
            raise RecoveryRejected("OBJECT_SECURITY_REJECTED")
        identities.add(fact.identity)
    volume = snapshot[0].facts
    if volume.owner not in {ADMINISTRATORS_SID, SYSTEM_SID}:
        raise RecoveryRejected("VOLUME_OWNER_REJECTED")
    for sid, mask, kind, flags in volume.aces:
        if (
            kind not in {0, 1}
            or flags & ~0x1F
            or (
                kind == 0
                and not flags & 8
                and sid not in {ADMINISTRATORS_SID, SYSTEM_SID}
                and mask & (0xC0040 | 0x10000000)
            )
        ):
            raise RecoveryRejected("VOLUME_AUTHORITY_REJECTED")
    for index in (1, 2):
        row = snapshot[index].facts
        if (
            row.identity != TARGET_IDENTITIES[index - 1]
            or row.owner != ADMINISTRATORS_SID
            or row.protected is not True
        ):
            raise RecoveryRejected("TARGET_IDENTITY_REJECTED")
    for row in snapshot[3:5]:
        fact = row.facts
        if fact.owner not in {ADMINISTRATORS_SID, SYSTEM_SID} or any(
            sid == DRIFT_SID
            or kind != 0
            or flags & ~0x13
            or (sid not in {ADMINISTRATORS_SID, SYSTEM_SID} and mask & ~0x1200A9)
            for sid, mask, kind, flags in fact.aces
        ):
            raise RecoveryRejected("RUNTIME_DRIFT_SCOPE_REJECTED")
    for row, drift in zip(snapshot[5:], (True, True, False), strict=True):
        # Each preserved root must be an inheritance barrier. Never touch it.
        if row.facts.protected is not True or (
            any(sid == DRIFT_SID for sid, *_ in row.facts.aces) is not drift
        ):
            raise RecoveryRejected("PRESERVED_SCOPE_REJECTED")


def classify_baseline(snapshot: tuple[SecurityEvidence, ...]) -> str:
    validate_scope(snapshot)
    before = all(
        row.facts.aces == PRE_ACES[index] and row.descriptor_sha256 == PRE_HASHES[index]
        for index, row in enumerate(snapshot[1:3])
    )
    after = all(
        row.facts.aces == POST_ACES[index]
        and all(sid != DRIFT_SID for sid, *_ in row.facts.aces)
        for index, row in enumerate(snapshot[1:3])
    )
    return "FROZEN_DRIFT" if before else "RECOVERED" if after else "CONFLICTING"


def recovery_plan(
    source: tuple[str, str], snapshot: tuple[SecurityEvidence, ...]
) -> dict[str, object]:
    validate_scope(snapshot)
    return {
        "schema": PLAN_SCHEMA,
        "source_head": source[0],
        "source_tree": source[1],
        "targets": [
            {
                "path": path,
                "identity": TARGET_IDENTITIES[index],
                "pre_descriptor_sha256": PRE_HASHES[index],
                "pre_aces": PRE_ACES[index],
                "target_aces": POST_ACES[index],
                "owner": ADMINISTRATORS_SID,
                "protected": True,
                "filesystem": "NTFS",
                "reparse": False,
            }
            for index, path in enumerate(TARGET_PATHS)
        ],
        "drift_sid": DRIFT_SID,
        "mutation_order": MUTATION_ORDER,
        "non_targets": [asdict(row) for row in (snapshot[0], *snapshot[3:])],
        "preserved_incident_release_ids": INCIDENT_RELEASE_IDS,
        "preserved_incident_paths": PRESERVED_PATHS,
        "runtime_binding_eligible": False,
        "successor_soak_eligible": False,
        "automatic_retry": "NOT_AUTHORIZED",
    }


def _result(
    status: str,
    reason: str,
    *,
    source=None,
    snapshot=None,
    plan=None,
    latch="UNOBSERVED",
    eligible=False,
    stable=False,
    effect="NOT_STARTED",
    native_results=(),
    readbacks=(),
) -> dict[str, object]:
    return {
        "status": status,
        "effect_disposition": effect,
        "automatic_retry": "NOT_AUTHORIZED",
        "protected_effects": ZERO_EFFECTS,
        "primary": {
            "schema": SCHEMA,
            "status": status,
            "reason": reason,
            "source_head": source[0] if source else None,
            "source_tree": source[1] if source else None,
            "plan": plan,
            "plan_sha256": hashlib.sha256(canonical(plan)).hexdigest()
            if plan
            else None,
            "latch_classification": latch,
            "execute_eligible": eligible,
            "repeated_observation_stable": stable,
            "observations": [asdict(row) for row in snapshot] if snapshot else None,
            "native_results": native_results,
            "readbacks": readbacks,
            "automatic_retry": "NOT_AUTHORIZED",
            "effect_disposition": effect,
            "preserved_incident_paths": PRESERVED_PATHS,
            "runtime_binding_eligible": False,
            "successor_soak_eligible": False,
        },
    }


def preflight() -> dict[str, object]:
    """Read-only admission/reconciliation. No state can renew a consumed attempt."""
    source = snapshot = plan = None
    latch = "UNOBSERVED"
    try:
        source = admit_source()
        require_administrator()
        snapshot = observe_fixed_scope()
        baseline = classify_baseline(snapshot)
        plan = recovery_plan(source, snapshot)
        latch = observe_attempt(plan)
        if (
            observe_fixed_scope() != snapshot
            or admit_source() != source
            or observe_attempt(plan) != latch
        ):
            raise RecoveryRejected("REPEAT_ADMISSION_REJECTED")
        reviewed = os.environ.get(PLAN_ENV)
        if (
            latch == "AVAILABLE"
            and reviewed is not None
            and (
                re.fullmatch(r"[0-9a-f]{64}", reviewed) is None
                or hashlib.sha256(canonical(plan)).hexdigest() != reviewed
            )
        ):
            baseline = "CONFLICTING"
        if latch == "AVAILABLE":
            status, reason, eligible = (
                ("PASS", "READY_FOR_SHARED_NAMESPACE_ACL_RECOVERY", True)
                if baseline == "FROZEN_DRIFT"
                else ("BLOCKED", "PRE_RECOVERY_BASELINE_DRIFT", False)
            )
        elif latch == "CONSUMED" and baseline == "RECOVERED":
            status, reason, eligible = (
                "PASS",
                "SHARED_NAMESPACE_ACL_RECOVERY_VERIFIED",
                False,
            )
        elif latch == "CONSUMED" and baseline == "FROZEN_DRIFT":
            status, reason, eligible = (
                "BLOCKED",
                "CONSUMED_ATTEMPT_NO_CONFIRMED_RECOVERY",
                False,
            )
        else:
            status, reason, eligible = (
                "INDETERMINATE",
                "PARTIAL_OR_CONFLICTING_ACL_RECOVERY",
                False,
            )
        return _result(
            status,
            reason,
            source=source,
            snapshot=snapshot,
            plan=plan,
            latch=latch,
            eligible=eligible,
            stable=True,
        )
    except (Exception, KeyboardInterrupt, SystemExit):
        try:
            consumed = _read_latch() is not None or _spent
        except (Exception, KeyboardInterrupt, SystemExit):
            consumed = True
        return _result(
            "INDETERMINATE" if consumed else "BLOCKED",
            "PARTIAL_OR_CONFLICTING_ACL_RECOVERY"
            if consumed
            else "PRE_RECOVERY_BASELINE_DRIFT",
            source=source,
            snapshot=snapshot,
            plan=plan,
            latch="INDETERMINATE" if consumed else "AVAILABLE",
        )


def execute_once() -> dict[str, object]:
    """Separate protected surface; one durable latch, at most two fixed calls."""
    if not _lock.acquire(blocking=False):
        return _result("BLOCKED", "ATTEMPT_UNAVAILABLE")
    try:
        return _execute_locked()
    finally:
        _lock.release()


def _execute_locked() -> dict[str, object]:
    source = before = plan = None
    latch = "UNOBSERVED"
    reservation = fence = False
    results, readbacks = [], []
    failed = False
    try:
        reviewed = os.environ.get(PLAN_ENV, "")
        if (
            os.environ.get(AUTH_ENV) != AUTH_VALUE
            or re.fullmatch(r"[0-9a-f]{64}", reviewed) is None
        ):
            return _result("BLOCKED", "AUTHORIZATION_REJECTED")
        source = admit_source()
        require_administrator()
        before = observe_fixed_scope()
        plan = recovery_plan(source, before)
        if (
            classify_baseline(before) != "FROZEN_DRIFT"
            or hashlib.sha256(canonical(plan)).hexdigest() != reviewed
        ):
            return _result("BLOCKED", "REVIEWED_PLAN_REJECTED")
        latch = observe_attempt(plan)
        if latch != "AVAILABLE":
            return _result("BLOCKED", "ATTEMPT_UNAVAILABLE", plan=plan, latch=latch)
        from trading_bot.shared_namespace_acl_native import (
            _PinnedTargets,
        )

        try:
            # Pin both targets and reobserve before reserving the attempt.
            with _PinnedTargets() as pinned:
                if (
                    pinned.snapshot() != before
                    or admit_source() != source
                    or observe_attempt(plan) != "AVAILABLE"
                ):
                    raise RecoveryRejected("PINNED_PLAN_DRIFT")
                try:
                    _consume_attempt(plan)
                finally:
                    reservation = _spent
                latch = observe_attempt(plan)
                if (
                    latch != "CONSUMED"
                    or pinned.snapshot() != before
                    or admit_source() != source
                ):
                    raise RecoveryRejected("MUTATION_FENCE_REJECTED")
                fence = True
                for index in range(2):
                    # Fence precedes invocation, even if the native call never returns.
                    code = None
                    try:
                        code = pinned.apply_next()
                    except (Exception, KeyboardInterrupt, SystemExit):
                        code = pinned.last_status
                        failed = True
                    results.append({"path": TARGET_PATHS[index], "raw_dword": code})
                    # Read back even after false, nonzero or lost native results.
                    try:
                        observed = pinned.snapshot()
                        readbacks.append([asdict(row) for row in observed])
                        validate_scope(observed)
                        if observed[0] != before[0] or observed[3:] != before[3:]:
                            failed = True
                        for offset, row in enumerate(observed[1:3]):
                            expected = (
                                POST_ACES[offset]
                                if offset <= index
                                else PRE_ACES[offset]
                            )
                            if row.facts.aces != expected:
                                failed = True
                        if index == 0 and observed[2] != before[2]:
                            failed = True
                    except (Exception, KeyboardInterrupt, SystemExit):
                        failed = True
                    if type(code) is not int or code != 0 or failed:
                        failed = True
                        break
        except (Exception, KeyboardInterrupt, SystemExit):
            if not fence:
                raise
            failed = True
        # Reopen twice after all handles close, including after native failure.
        after = []
        for _ in range(2):
            try:
                row = observe_fixed_scope()
                after.append(row)
                readbacks.append([asdict(item) for item in row])
            except (Exception, KeyboardInterrupt, SystemExit):
                failed = True
        if len(after) != 2 or after[0] != after[1]:
            failed = True
        for row in after:
            if (
                classify_baseline(row) != "RECOVERED"
                or row[0] != before[0]
                or row[3:] != before[3:]
            ):
                failed = True
        if admit_source() != source or observe_attempt(plan) != "CONSUMED":
            failed = True
        if failed or len(results) != 2:
            raise RecoveryRejected("POST_EFFECT_UNCONFIRMED")
        return _result(
            "PASS",
            "SHARED_NAMESPACE_ACL_RECOVERY_VERIFIED",
            source=source,
            snapshot=after[0],
            plan=plan,
            latch=latch,
            stable=True,
            effect="CONFIRMED",
            native_results=results,
            readbacks=readbacks,
        )
    except (Exception, KeyboardInterrupt, SystemExit):
        if not reservation and plan is not None:
            # A failed create is not a reservation. Prove absence read-only;
            # an existing or unprovable object still closes execute authority.
            latch = observe_attempt(plan)
        ambiguous = reservation or latch in {"CONSUMED", "INDETERMINATE"}
        return _result(
            "INDETERMINATE" if ambiguous else "BLOCKED",
            PRESERVE
            if reservation
            else "PARTIAL_OR_CONFLICTING_ACL_RECOVERY"
            if ambiguous
            else "RECOVERY_ADMISSION_REJECTED",
            source=source,
            snapshot=before,
            plan=plan,
            latch="INDETERMINATE" if reservation and latch != "CONSUMED" else latch,
            effect="MAY_HAVE_OCCURRED" if fence else "NOT_STARTED",
            native_results=results,
            readbacks=readbacks,
        )
