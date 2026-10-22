"""Architecture 134-F1R1-D1S3 successor installation/readiness operator.

This module is a successor-specific composition.  It does not modify or call
the historical Architecture-133 runner operator directly.  The protected
execute seam is deliberately injectable for source tests and calls the
accepted Architecture-133 installer exactly once after a fresh D1S3 latch has
been durably reserved.
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
from enum import StrEnum
from pathlib import Path

from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_acl.read_only import ADMINISTRATORS_SID
from trading_bot.review_paper.successor_readiness import (
    InstallationObservation,
    InstallationReadiness,
    InstallationReason,
    ReadinessStatus,
    SuccessorReadinessBoundary,
    SuccessorReadinessResult,
    SuccessorReleaseDeclaration,
    SuccessorRootObservation,
    SuccessorRootObserver,
    SuccessorSourcePolicy,
    SuccessorStoreClassification,
    assess_successor_readiness,
    observe_installation_readiness,
)
from trading_bot.review_paper.successor_soak_contract import (
    PARENT_NAME,
    PRODUCTION_ROOT,
    SESSION_NAMES,
    STORE_IDENTITY,
)
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    MAX_FILE_BYTES,
    VerifiedRelease,
    source_namespace,
)
from trading_bot.supervised_release.collector import collect_release_bundle
from trading_bot.supervised_release.installation_contract import (
    IMAGE_ACES,
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstallDisposition,
    InstalledEvidence,
    InstallResult,
    InstallStatus,
    ObserverNative,
    ReleasePaths,
)
from trading_bot.supervised_release.installer import install_release
from trading_bot.supervised_release.model import (
    DURABLE_DATA_ROOT,
    LAUNCHER_RELATIVE_PATH,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ReleaseInventoryEntry,
    ReleaseManifest,
)
from trading_bot.supervised_release.native_read import windows_libraries
from trading_bot.supervised_release.observer import (
    observe_installed_release,
    observe_parent,
    replay_inputs,
)
from trading_bot.supervised_release.runtime_admission import RuntimeObserver

SCHEMA = "arch134-f1r1-d1s3-successor-release-installation-operator/v1"
SOURCE_REMOTE = "https://github.com/callmedraken/ai-trading-bot.git"
SOURCE_REF = (
    "refs/heads/feature/robinhood-production-paper-134f1r1-"
    "successor-installation-operator-current"
)
BRANCH = SOURCE_REF.removeprefix("refs/heads/")
WORKTREE = Path(
    r"F:\AI\worktrees\ai-trading-bot-production-paper-134f1r1-"
    r"successor-installation-operator-current"
)
BASE_HEAD = "2b697b79e6bdbc964d2b0414ced057628e6c2da7"
REMOTE_HEAD_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S3_ACCEPTED_HEAD"
SOURCE_TREE_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S3_ACCEPTED_TREE"
AUTH_ENV = "AI_TRADING_BOT_ARCH134_F1R1_D1S3_INSTALL_AUTHORIZATION"
AUTH_VALUE = "ARCH134_F1R1_D1S3_SUCCESSOR_INSTALLATION_AUTHORIZED"
ATTEMPT_PATH = Path(r"F:\AI\temp\arch134-f1r1-d1s3-installation-attempt\attempt.json")
ATTEMPT_SCHEMA = "arch134-f1r1-d1s3-installation-attempt/v1"
ATTEMPT_BYTES = (
    b'{"automatic_retry":"NOT_AUTHORIZED","schema":"'
    + ATTEMPT_SCHEMA.encode("ascii")
    + b'","status":"CONSUMED"}\n'
)

ZERO_PROTECTED_EFFECTS = (
    ("PRODUCTION_INSTALLATION_EFFECTS", 0),
    ("PRODUCTION_RELEASE_PUBLICATIONS", 0),
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
    ("ORIGINAL_F1_EVIDENCE_MUTATIONS", 0),
    ("C2_EVIDENCE_MUTATIONS", 0),
)

STRATEGY_CONFIG = MovingAverageCrossoverConfig(5, 20, Decimal("1"))
RISK_POLICY_ID = "arch133-long-only-review-paper"
SUCCESSOR_PARENT = DURABLE_DATA_ROOT
RISK_POLICY_VERSION = "1.0.0"
RISK_POLICY_MATERIAL = (
    b'{"schema":"arch133-installation-risk-declaration/v1",'
    b'"mode":"paper","instruments":"US-stocks-ETFs","long_only":true,'
    b'"margin":false,"leverage":false,"options":false,"shorts":false,'
    b'"crypto":false,"deterministic_risk_required":true}'
)


class AttemptState(StrEnum):
    AVAILABLE = "AVAILABLE"
    CONSUMED = "CONSUMED"
    INDETERMINATE = "INDETERMINATE"


class OperatorStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    INDETERMINATE = "INDETERMINATE"


class OperatorReason(StrEnum):
    VERIFIED = "VERIFIED"
    SOURCE_REJECTED = "SOURCE_REJECTED"
    INSTALL_REQUIRED = "INSTALL_REQUIRED"
    ALREADY_INSTALLED_EXACT = "ALREADY_INSTALLED_EXACT"
    INSTALLATION_BLOCKED = "INSTALLATION_BLOCKED"
    INSTALLATION_UNPROVEN = "INSTALLATION_UNPROVEN"
    CONSUMED_ATTEMPT = "CONSUMED_ATTEMPT"
    SUCCESSOR_ROOT_PROVISIONING_REVIEW = "SUCCESSOR_ROOT_PROVISIONING_REVIEW"
    SUCCESSOR_ROOT_BLOCKED = "SUCCESSOR_ROOT_BLOCKED"
    SUCCESSOR_ROOT_UNPROVEN = "SUCCESSOR_ROOT_UNPROVEN"
    AUTHORIZATION_REJECTED = "AUTHORIZATION_REJECTED"
    INSTALLATION_ACK_MISMATCH = "INSTALLATION_ACK_MISMATCH"
    POST_INSTALL_REOBSERVATION_REQUIRED = "POST_INSTALL_REOBSERVATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class AttemptObservation:
    state: AttemptState
    path: str
    payload_sha256: str | None = None

    def __post_init__(self) -> None:
        if type(self.state) is not AttemptState or type(self.path) is not str:
            raise ValueError("closed attempt observation required")
        if (
            self.payload_sha256 is not None
            and re.fullmatch(r"[0-9a-f]{64}", self.payload_sha256) is None
        ):
            raise ValueError("attempt digest required")


@dataclass(frozen=True, slots=True)
class D1S3Boundary:
    """Read-only observations and injected native seams for source tests."""

    declaration: SuccessorReleaseDeclaration
    installation_observer: object
    image_observer: ObserverNative
    runtime_observer: RuntimeObserver
    successor_observer: SuccessorRootObserver

    def readiness_boundary(self) -> SuccessorReadinessBoundary:
        return SuccessorReadinessBoundary(
            self.declaration.source_policy,
            self.declaration.release,
            self.declaration.binding,
            self.installation_observer,
            self.image_observer,
            self.runtime_observer,
            self.successor_observer,
        )


@dataclass(frozen=True, slots=True)
class D1S3PreflightResult:
    status: OperatorStatus
    reason: OperatorReason
    declaration: SuccessorReleaseDeclaration | None
    installation: InstallationObservation | None
    attempt: AttemptObservation
    successor_root: SuccessorRootObservation | None
    execute_eligible: bool
    readiness: SuccessorReadinessResult | None = None
    protected_effects: tuple[tuple[str, int], ...] = ZERO_PROTECTED_EFFECTS

    def __post_init__(self) -> None:
        if (
            type(self.status) is not OperatorStatus
            or type(self.reason) is not OperatorReason
        ):
            raise ValueError("closed D1S3 result required")
        if self.protected_effects != ZERO_PROTECTED_EFFECTS:
            raise ValueError("protected effect counters must remain zero")
        if type(self.attempt) is not AttemptObservation:
            raise ValueError("attempt observation required")
        if type(self.execute_eligible) is not bool:
            raise ValueError("execute eligibility must be boolean")

    def to_dict(self) -> dict[str, object]:
        declaration = self.declaration
        installation = self.installation
        return {
            "schema": SCHEMA,
            "status": self.status.value,
            "reason": self.reason.value,
            "source_head": (
                declaration.source_policy.accepted_head if declaration else None
            ),
            "source_tree": (
                declaration.source_policy.accepted_tree if declaration else None
            ),
            "release_id": declaration.release_id if declaration else None,
            "manifest_sha256": (declaration.manifest_sha256 if declaration else None),
            "source_inventory_sha256": (
                declaration.inventory_sha256 if declaration else None
            ),
            "binding_sha256": (declaration.binding.sha256 if declaration else None),
            "final_path": installation.final_path if installation else None,
            "staging_path": installation.staging_path if installation else None,
            "installation_classification": (
                installation.classification.value if installation else None
            ),
            "attempt_state": self.attempt.state.value,
            "attempt_path": self.attempt.path,
            "successor_root_classification": (
                self.successor_root.classification.value
                if self.successor_root
                else None
            ),
            "readiness_status": (
                self.readiness.status.value if self.readiness else None
            ),
            "protected_effects": [list(item) for item in self.protected_effects],
            "execute_eligible": self.execute_eligible,
        }


class InstallationNativeObserver:
    """Independent read-only FINAL/.installing observer for the fixed paths."""

    def __init__(
        self,
        release: VerifiedRelease,
        binding: RuntimeBinding,
        native: ObserverNative,
    ) -> None:
        self._release = release
        self._binding = binding
        self._native = native

    def observe(self, paths: ReleasePaths) -> InstallationObservation:
        replay_inputs(self._release, self._binding)
        with self._native.read_session(paths) as session:
            parent = observe_parent(session)
            staging = session.object(paths.staging, directory=True)
            if staging is None:
                staging_file = session.object(paths.staging, directory=False)
                if staging_file is not None:
                    return InstallationObservation(
                        InstallationReadiness.BLOCKED,
                        InstallationReason.STAGING_CONFLICT,
                        paths.final,
                        paths.staging,
                        staging_identity=staging_file.identity,
                    )
            else:
                return InstallationObservation(
                    InstallationReadiness.BLOCKED,
                    InstallationReason.STAGING_CONFLICT,
                    paths.final,
                    paths.staging,
                    staging_identity=staging.identity,
                )
            final = session.object(paths.final, directory=True)
            if final is None:
                final_file = session.object(paths.final, directory=False)
                if final_file is not None:
                    return InstallationObservation(
                        InstallationReadiness.BLOCKED,
                        InstallationReason.FINAL_CONFLICT,
                        paths.final,
                        paths.staging,
                        final_identity=final_file.identity,
                    )
        if final is None:
            return InstallationObservation(
                InstallationReadiness.INSTALL_REQUIRED,
                InstallationReason.FINAL_AND_STAGING_ABSENT,
                paths.final,
                paths.staging,
            )
        try:
            installed = observe_installed_release(
                self._release, self._binding, native=self._native
            )
        except (Exception, KeyboardInterrupt):
            return InstallationObservation(
                InstallationReadiness.BLOCKED,
                InstallationReason.FINAL_CONFLICT,
                paths.final,
                paths.staging,
                final_identity=final.identity,
            )
        if installed.parent_identity != parent.identity:
            return InstallationObservation(
                InstallationReadiness.BLOCKED,
                InstallationReason.REPLACED_OBJECT,
                paths.final,
                paths.staging,
                final_identity=final.identity,
            )
        return InstallationObservation(
            InstallationReadiness.ALREADY_INSTALLED_EXACT,
            InstallationReason.EXACT_FINAL,
            paths.final,
            paths.staging,
            final_identity=final.identity,
            installed_evidence=installed,
        )


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object, *, length: int = 40) -> None:
    if type(value) is not str or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError("canonical source digest required")


def _path_safe(path: Path) -> None:
    for ancestor in reversed((path, *path.parents)):
        try:
            facts = ancestor.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(facts.st_mode) or getattr(
            facts, "st_file_attributes", 0
        ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError("source/attempt reparse path rejected")


def _git(repo_root: Path, *arguments: str) -> str:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1")
    completed = subprocess.run(
        (
            "git",
            "--no-replace-objects",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(repo_root),
            *arguments,
        ),
        capture_output=True,
        check=False,
        timeout=30,
        env=environment,
    )
    if completed.returncode != 0:
        raise ValueError("successor source observation rejected")
    return completed.stdout.decode("utf-8").strip()


def _live_remote_head(repo_root: Path) -> str:
    environment = dict(os.environ)
    environment.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    completed = subprocess.run(
        ("git", "ls-remote", "origin", SOURCE_REF),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=environment,
    )
    if completed.returncode != 0:
        raise ValueError("successor live remote observation rejected")
    rows = [line.split() for line in completed.stdout.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != SOURCE_REF:
        raise ValueError("successor live remote row rejected")
    _digest(rows[0][0])
    return rows[0][0]


def _accepted_env(name: str) -> str:
    value = os.environ.get(name, "")
    _digest(value)
    return value


def derive_successor_declaration(
    *,
    repo_root: Path = WORKTREE,
    accepted_head: str | None = None,
    accepted_tree: str | None = None,
) -> SuccessorReleaseDeclaration:
    """Collect a complete release only from the exact accepted live source."""

    if repo_root.resolve() != WORKTREE.resolve():
        raise ValueError("successor source worktree mismatch")
    _path_safe(repo_root)
    accepted_head = (
        _accepted_env(REMOTE_HEAD_ENV) if accepted_head is None else accepted_head
    )
    accepted_tree = (
        _accepted_env(SOURCE_TREE_ENV) if accepted_tree is None else accepted_tree
    )
    _digest(accepted_head)
    _digest(accepted_tree)
    if _live_remote_head(repo_root) != accepted_head:
        raise ValueError("successor live remote HEAD mismatch")
    if (
        _git(repo_root, "rev-parse", "--show-toplevel") != str(WORKTREE.resolve())
        or _git(repo_root, "branch", "--show-current") != BRANCH
        or _git(repo_root, "remote", "get-url", "origin") != SOURCE_REMOTE
        or _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
        or _git(repo_root, "merge-base", BASE_HEAD, "HEAD") != BASE_HEAD
    ):
        raise ValueError("successor source admission rejected")
    head = _git(repo_root, "rev-parse", "HEAD")
    tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
    if (head, tree) != (accepted_head, accepted_tree):
        raise ValueError("successor local HEAD/tree mismatch")
    names = source_namespace(
        tuple(
            sorted(
                name
                for name in _git(
                    repo_root, "ls-tree", "-r", "--name-only", "HEAD"
                ).splitlines()
                if name == "pyproject.toml"
                or name == LAUNCHER_RELATIVE_PATH
                or name.startswith("src/trading_bot/")
            )
        )
    )
    inventory = []
    for name in names:
        path = repo_root / Path(name)
        _path_safe(path)
        facts = path.lstat()
        if not stat.S_ISREG(facts.st_mode) or facts.st_size > MAX_FILE_BYTES:
            raise ValueError("successor source object rejected")
        data = path.read_bytes()
        if len(data) != facts.st_size:
            raise ValueError("successor source bytes rejected")
        inventory.append(ReleaseInventoryEntry(name, hashlib.sha256(data).hexdigest()))
    launcher = next(
        entry for entry in inventory if entry.relative_path == LAUNCHER_RELATIVE_PATH
    )
    declaration = ReleaseManifest(
        head,
        tree,
        PYTHON_VERSION,
        PYTHON_SHA256,
        LAUNCHER_RELATIVE_PATH,
        launcher.sha256,
        tuple(inventory),
        STRATEGY_ID,
        STRATEGY_VERSION,
        # The source-owned strategy projection is intentionally fixed to the
        # Architecture-133 declaration and is not caller-selectable.
        strategy_config=STRATEGY_CONFIG,
        risk_policy_id=RISK_POLICY_ID,
        risk_policy_version=RISK_POLICY_VERSION,
        risk_policy_sha256=hashlib.sha256(RISK_POLICY_MATERIAL).hexdigest(),
    )
    release = collect_release_bundle(repo_root, declaration=declaration)
    if release.manifest != declaration:
        raise ValueError("successor declaration drift")
    binding = RuntimeBinding(release)
    replay_inputs(release, binding)
    if (
        _git(repo_root, "rev-parse", "HEAD") != head
        or _git(repo_root, "rev-parse", "HEAD^{tree}") != tree
        or _live_remote_head(repo_root) != accepted_head
    ):
        raise ValueError("successor source identity drift")
    policy = SuccessorSourcePolicy(
        SOURCE_REMOTE,
        SOURCE_REF,
        head,
        tree,
        tuple(entry.relative_path for entry in inventory),
    )
    return SuccessorReleaseDeclaration(policy, release, binding)


def _attempt_path_text(path: Path) -> str:
    return str(path).replace("/", "\\")


def observe_attempt(path: Path = ATTEMPT_PATH) -> AttemptObservation:
    """Read the fixed latch without creating its parent or file."""

    _path_safe(path)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return AttemptObservation(AttemptState.AVAILABLE, _attempt_path_text(path))
    digest = hashlib.sha256(data).hexdigest()
    if data == ATTEMPT_BYTES:
        return AttemptObservation(
            AttemptState.CONSUMED, _attempt_path_text(path), digest
        )
    return AttemptObservation(
        AttemptState.INDETERMINATE, _attempt_path_text(path), digest
    )


def consume_attempt(path: Path = ATTEMPT_PATH) -> AttemptObservation:
    """Exclusively reserve, flush, fsync and read back one fresh D1S3 latch."""

    state = observe_attempt(path)
    if state.state is not AttemptState.AVAILABLE:
        raise RuntimeError("D1S3 installation attempt is not available")
    _path_safe(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    if observe_attempt(path).state is not AttemptState.AVAILABLE:
        raise RuntimeError("D1S3 installation attempt is not available")
    try:
        with path.open("xb") as handle:
            handle.write(ATTEMPT_BYTES)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise RuntimeError("D1S3 installation attempt is consumed") from exc
    except (Exception, KeyboardInterrupt) as exc:
        raise RuntimeError("D1S3 installation attempt became indeterminate") from exc
    result = observe_attempt(path)
    if (
        result.state is not AttemptState.CONSUMED
        or result.payload_sha256 != hashlib.sha256(ATTEMPT_BYTES).hexdigest()
    ):
        raise RuntimeError("D1S3 installation attempt readback failed")
    return result


def _root_safe(value: SuccessorRootObservation) -> bool:
    fixed = (
        value.path == PRODUCTION_ROOT
        and value.final_path == PRODUCTION_ROOT
        and value.parent == SUCCESSOR_PARENT
        and value.kind == "directory"
        and value.filesystem == "NTFS"
        and value.local is True
        and value.reparse is False
        and value.links == 1
        and value.owner == ADMINISTRATORS_SID
        and value.protected is True
        and value.aces == IMAGE_ACES
        and value.stable is True
    )
    if value.classification is SuccessorStoreClassification.ABSENT_ELIGIBLE:
        return (
            fixed
            and value.identity is None
            and value.names == ()
            and not value.malformed
        )
    if not fixed or value.identity is None or value.parent_identity is None:
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
        value.classification is SuccessorStoreClassification.ALREADY_BOUND_EXACT
        and value.names == (PARENT_NAME, *SESSION_NAMES)
        and value.store_identity == STORE_IDENTITY
        and value.evidence_complete is True
        and value.consumed is False
        and value.malformed is False
    )


def _root_result(
    boundary: D1S3Boundary,
) -> SuccessorRootObservation:
    value = boundary.successor_observer.observe_root()
    if type(value) is not SuccessorRootObservation:
        raise ValueError("successor root observation required")
    if not _root_safe(value):
        raise RuntimeError(value.classification.value)
    return value


def assess_d1s3_preflight(
    boundary: D1S3Boundary,
    *,
    attempt: AttemptObservation | None = None,
) -> D1S3PreflightResult:
    """Perform only source-derived and read-only successor observations."""

    if type(boundary) is not D1S3Boundary:
        raise TypeError("exact D1S3 boundary required")
    attempt = observe_attempt() if attempt is None else attempt
    declaration = boundary.declaration
    try:
        installation = observe_installation_readiness(
            declaration, boundary.installation_observer
        )
    except (Exception, KeyboardInterrupt):
        return D1S3PreflightResult(
            OperatorStatus.INDETERMINATE,
            OperatorReason.INSTALLATION_UNPROVEN,
            declaration,
            None,
            attempt,
            None,
            False,
        )
    if installation.classification is InstallationReadiness.BLOCKED:
        return D1S3PreflightResult(
            OperatorStatus.BLOCKED,
            OperatorReason.INSTALLATION_BLOCKED,
            declaration,
            installation,
            attempt,
            None,
            False,
        )
    if installation.classification is InstallationReadiness.INDETERMINATE:
        return D1S3PreflightResult(
            OperatorStatus.INDETERMINATE,
            OperatorReason.INSTALLATION_UNPROVEN,
            declaration,
            installation,
            attempt,
            None,
            False,
        )
    try:
        root = boundary.successor_observer.observe_root()
        if type(root) is not SuccessorRootObservation:
            raise ValueError("successor root observation required")
        if not _root_safe(root):
            if root.classification is SuccessorStoreClassification.INDETERMINATE:
                return D1S3PreflightResult(
                    OperatorStatus.INDETERMINATE,
                    OperatorReason.SUCCESSOR_ROOT_UNPROVEN,
                    declaration,
                    installation,
                    attempt,
                    root,
                    False,
                )
            return D1S3PreflightResult(
                OperatorStatus.BLOCKED,
                OperatorReason.SUCCESSOR_ROOT_BLOCKED,
                declaration,
                installation,
                attempt,
                root,
                False,
            )
        if installation.classification is InstallationReadiness.INSTALL_REQUIRED:
            if attempt.state is not AttemptState.AVAILABLE:
                return D1S3PreflightResult(
                    OperatorStatus.BLOCKED,
                    OperatorReason.CONSUMED_ATTEMPT,
                    declaration,
                    installation,
                    attempt,
                    root,
                    False,
                )
            return D1S3PreflightResult(
                OperatorStatus.PASS,
                OperatorReason.INSTALL_REQUIRED,
                declaration,
                installation,
                attempt,
                root,
                True,
            )
        if root.classification is SuccessorStoreClassification.ABSENT_ELIGIBLE:
            return D1S3PreflightResult(
                OperatorStatus.PASS,
                OperatorReason.ALREADY_INSTALLED_EXACT,
                declaration,
                installation,
                attempt,
                root,
                False,
            )
        readiness = assess_successor_readiness(boundary.readiness_boundary())
        if (
            readiness.status
            is ReadinessStatus.READY_FOR_D1_SUCCESSOR_INSTALLED_RELEASE_PREFLIGHT
        ):
            return D1S3PreflightResult(
                OperatorStatus.PASS,
                OperatorReason.ALREADY_INSTALLED_EXACT,
                declaration,
                installation,
                attempt,
                root,
                False,
                readiness,
            )
        if readiness.status is ReadinessStatus.INDETERMINATE:
            return D1S3PreflightResult(
                OperatorStatus.INDETERMINATE,
                OperatorReason.SUCCESSOR_ROOT_UNPROVEN,
                declaration,
                installation,
                attempt,
                root,
                False,
                readiness,
            )
        return D1S3PreflightResult(
            OperatorStatus.BLOCKED,
            OperatorReason.SUCCESSOR_ROOT_BLOCKED,
            declaration,
            installation,
            attempt,
            root,
            False,
            readiness,
        )
    except (Exception, KeyboardInterrupt):
        return D1S3PreflightResult(
            OperatorStatus.INDETERMINATE,
            OperatorReason.SUCCESSOR_ROOT_UNPROVEN,
            declaration,
            installation,
            attempt,
            None,
            False,
        )


def _sanitized_install(result: InstallResult) -> dict[str, object]:
    if type(result) is not InstallResult:
        raise ValueError("installation result shape rejected")
    if result.evidence is not None and type(result.evidence) is not InstalledEvidence:
        raise ValueError("installation evidence shape rejected")
    return {
        "status": result.status.value,
        "disposition": result.disposition.value,
        "reason": result.reason.value,
        "evidence": None if result.evidence is None else asdict(result.evidence),
    }


def execute_installation(
    boundary: D1S3Boundary,
    *,
    installer: Callable[[VerifiedRelease, RuntimeBinding], InstallResult] | None = None,
    authorization: str | None = None,
    attempt_path: Path = ATTEMPT_PATH,
) -> dict[str, object]:
    """Execute only the immutable-release installation effect once.

    Source tests pass a fake installer and a disposable attempt path.  The
    default path and installer are reserved for a later separately reviewed
    protected invocation through ``checkpoint_runner``.
    """

    if authorization != AUTH_VALUE and os.environ.get(AUTH_ENV) != AUTH_VALUE:
        return {
            "status": "BLOCKED",
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                "status": "BLOCKED",
                "reason": OperatorReason.AUTHORIZATION_REJECTED.value,
            },
        }
    installer = install_release if installer is None else installer
    preflight = assess_d1s3_preflight(boundary, attempt=observe_attempt(attempt_path))
    if not preflight.execute_eligible:
        return {
            "status": preflight.status.value,
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": preflight.to_dict(),
        }
    entered = False
    try:
        attempt = consume_attempt(attempt_path)
        entered = True
        result = installer(boundary.declaration.release, boundary.declaration.binding)
        sanitized = _sanitized_install(result)
        evidence = result.evidence
        if result.status not in {
            InstallStatus.INSTALLED_VERIFIED,
            InstallStatus.ALREADY_INSTALLED_VERIFIED,
        }:
            return {
                "status": result.status.value,
                "effect_disposition": (
                    "NOT_STARTED"
                    if result.disposition is InstallDisposition.NO_INSTALLATION_EFFECT
                    else "MAY_HAVE_OCCURRED"
                ),
                "automatic_retry": "NOT_AUTHORIZED",
                "primary": sanitized,
                "attempt": asdict(attempt),
            }
        if evidence is None or (
            evidence.release_id != preflight.declaration.release_id
            or evidence.manifest_sha256 != preflight.declaration.manifest_sha256
            or evidence.binding_sha256 != preflight.declaration.binding.sha256
            or evidence.dependency_closure != "UNPROVEN"
        ):
            return {
                "status": "INDETERMINATE",
                "effect_disposition": "MAY_HAVE_OCCURRED",
                "automatic_retry": "NOT_AUTHORIZED",
                "primary": {
                    "status": "INDETERMINATE",
                    "reason": OperatorReason.INSTALLATION_ACK_MISMATCH.value,
                },
                "attempt": asdict(attempt),
            }
        post = observe_installation_readiness(
            preflight.declaration, boundary.installation_observer
        )
        if (
            post.classification is not InstallationReadiness.ALREADY_INSTALLED_EXACT
            or post.installed_evidence is None
            or post.installed_evidence.release_id != evidence.release_id
            or post.installed_evidence.manifest_sha256 != evidence.manifest_sha256
            or post.installed_evidence.binding_sha256 != evidence.binding_sha256
            or post.installed_evidence.image_identity != evidence.image_identity
        ):
            return {
                "status": "INDETERMINATE",
                "effect_disposition": "MAY_HAVE_OCCURRED",
                "automatic_retry": "NOT_AUTHORIZED",
                "primary": {
                    "status": "INDETERMINATE",
                    "reason": OperatorReason.POST_INSTALL_REOBSERVATION_REQUIRED.value,
                },
                "attempt": asdict(attempt),
            }
        root = _root_result(boundary)
        if root.classification is SuccessorStoreClassification.ABSENT_ELIGIBLE:
            return {
                "status": "READY_FOR_D1_SUCCESSOR_ROOT_PROVISIONING_REVIEW",
                "effect_disposition": "CONFIRMED",
                "automatic_retry": "NOT_AUTHORIZED",
                "primary": sanitized,
                "post_install": post.classification.value,
                "successor_root": root.classification.value,
                "attempt": asdict(attempt),
            }
        if not _root_safe(root):
            return {
                "status": "BLOCKED"
                if root.classification is not SuccessorStoreClassification.INDETERMINATE
                else "INDETERMINATE",
                "effect_disposition": "MAY_HAVE_OCCURRED",
                "automatic_retry": "NOT_AUTHORIZED",
                "primary": {
                    "status": "BLOCKED",
                    "reason": OperatorReason.SUCCESSOR_ROOT_BLOCKED.value,
                },
                "attempt": asdict(attempt),
            }
        readiness = assess_successor_readiness(boundary.readiness_boundary())
        return {
            "status": readiness.status.value,
            "effect_disposition": "CONFIRMED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": sanitized,
            "post_install": post.classification.value,
            "successor_root": root.classification.value,
            "readiness": readiness.to_json(),
            "attempt": asdict(attempt),
        }
    except (Exception, KeyboardInterrupt):
        return {
            "status": "INDETERMINATE" if entered else "BLOCKED",
            "effect_disposition": "MAY_HAVE_OCCURRED" if entered else "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                "status": "INDETERMINATE" if entered else "BLOCKED",
                "reason": OperatorReason.INSTALLATION_UNPROVEN.value
                if entered
                else OperatorReason.INSTALLATION_BLOCKED.value,
            },
        }


def _administrator_host() -> None:
    windows_libraries()
    administrator_sid()


def _protected_boundary() -> D1S3Boundary:
    """Host-specific observer composition is a separately reviewed seam."""

    raise RuntimeError("D1S3 host observation composition is not supplied")


def _preflight() -> dict[str, object]:
    try:
        _administrator_host()
        declaration = derive_successor_declaration()
        boundary = _protected_boundary()
        if boundary.declaration != declaration:
            raise ValueError("protected declaration mismatch")
        result = assess_d1s3_preflight(boundary)
        return {
            "status": result.status.value,
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": result.to_dict(),
        }
    except (Exception, KeyboardInterrupt):
        return {
            "status": "BLOCKED",
            "effect_disposition": "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                "status": "BLOCKED",
                "reason": OperatorReason.SOURCE_REJECTED.value,
            },
        }


def _execute() -> dict[str, object]:
    try:
        declaration = derive_successor_declaration()
        boundary = _protected_boundary()
        if boundary.declaration != declaration:
            raise RuntimeError("protected declaration mismatch")
        return execute_installation(boundary, authorization=os.environ.get(AUTH_ENV))
    except (Exception, KeyboardInterrupt):
        attempt = observe_attempt()
        entered = attempt.state is not AttemptState.AVAILABLE
        return {
            "status": "INDETERMINATE" if entered else "BLOCKED",
            "effect_disposition": "MAY_HAVE_OCCURRED" if entered else "NOT_STARTED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                "status": "INDETERMINATE" if entered else "BLOCKED",
                "reason": OperatorReason.INSTALLATION_UNPROVEN.value
                if entered
                else OperatorReason.SOURCE_REJECTED.value,
            },
        }


__all__ = [
    "ATTEMPT_PATH",
    "ATTEMPT_SCHEMA",
    "AUTH_ENV",
    "AUTH_VALUE",
    "BASE_HEAD",
    "BRANCH",
    "D1S3Boundary",
    "D1S3PreflightResult",
    "REMOTE_HEAD_ENV",
    "SOURCE_REF",
    "SOURCE_REMOTE",
    "SOURCE_TREE_ENV",
    "WORKTREE",
    "AttemptObservation",
    "AttemptState",
    "InstallationNativeObserver",
    "OperatorReason",
    "OperatorStatus",
    "ZERO_PROTECTED_EFFECTS",
    "assess_d1s3_preflight",
    "consume_attempt",
    "derive_successor_declaration",
    "execute_installation",
    "observe_attempt",
]
