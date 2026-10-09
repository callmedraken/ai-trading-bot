"""Independent 133-S admission preserving every accepted 133-R predicate."""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path

from trading_bot.arch133_acl import read_only, retained_reads
from trading_bot.arch133_acl.administrator import administrator_sid
from trading_bot.arch133_reprovision import generation, predecessor, reads
from trading_bot.arch133_reprovision.material import digest
from trading_bot.arch133_verifier import binding, file_policy
from trading_bot.arch133_verifier.activation import ReviewPaperActivation
from trading_bot.arch133_verifier.state import state_database_path

SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133s")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133s"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
LAUNCHER = SOURCE_ROOT / "scripts" / "run_arch133_parent_security_diagnostic.py"
NO_PYCACHE = SOURCE_ROOT / "no-pycache"


def _git(root: Path, *args: str) -> str:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    result = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(root),
            *args,
        ],
        input="",
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
        env=env,
    )
    if len(result.stdout) > 4096 or result.stderr:
        raise ValueError("git observation rejected")
    return result.stdout.strip()


def _clean_source(root: Path, branch: str) -> tuple[str, str]:
    head, tree = (_git(root, "rev-parse", name) for name in ("HEAD", "HEAD^{tree}"))
    if (
        any(re.fullmatch(r"[0-9a-f]{40}", value) is None for value in (head, tree))
        or Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
        != root.resolve(strict=True)
        or _git(root, "branch", "--show-current") != branch
        or _git(root, "remote", "get-url", "origin") != ORIGIN
        or _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    ):
        raise ValueError("source rejected")
    return head, tree


def observe_runtime() -> dict:
    if (
        sys.platform != "win32"
        or not sys.flags.isolated
        or not sys.dont_write_bytecode
        or sys.pycache_prefix != str(NO_PYCACHE)
        or NO_PYCACHE.exists()
        or Path(__file__).resolve().parents[3] != SOURCE_ROOT.resolve(strict=True)
        or Path(sys.argv[0]).resolve(strict=True) != LAUNCHER.resolve(strict=True)
        or Path(sys.executable).resolve(strict=True)
        != binding.PRODUCTION_PYTHON.resolve(strict=True)
        or ".".join(map(str, sys.version_info[:3])) != binding.PRODUCTION_PYTHON_VERSION
        or hashlib.sha256(binding.PRODUCTION_PYTHON.read_bytes()).hexdigest()
        != binding.PRODUCTION_PYTHON_SHA256
    ):
        raise ValueError("runtime rejected")
    own = _clean_source(SOURCE_ROOT, SOURCE_BRANCH)
    ref = "refs/remotes/origin/" + SOURCE_BRANCH
    if (
        _git(
            SOURCE_ROOT,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        )
        != "origin/" + SOURCE_BRANCH
        or _git(SOURCE_ROOT, "rev-parse", ref) != own[0]
        or _git(SOURCE_ROOT, "rev-parse", ref + "^{tree}") != own[1]
    ):
        raise ValueError("remote source rejected")
    bound = _clean_source(binding.SOURCE_ROOT, binding.SOURCE_BRANCH)
    if bound not in predecessor.BOUND_CHECKOUTS:
        raise ValueError("bound source rejected")
    return {
        "operator_source_head": own[0],
        "operator_source_tree": own[1],
        "bound_source_head": predecessor.EXECUTABLE_SOURCE_HEAD,
        "bound_source_tree": predecessor.EXECUTABLE_SOURCE_TREE,
        "python_sha256": binding.PRODUCTION_PYTHON_SHA256,
        "python_version": binding.PRODUCTION_PYTHON_VERSION,
        "wake_launcher_sha256": hashlib.sha256(
            binding.LAUNCHER.read_bytes()
        ).hexdigest(),
    }


class AdmissionStageError(RuntimeError):
    """Sanitized internal stage marker; never carries native/upstream text."""

    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def _stage(stage: str, function, /, *args):
    try:
        return function(*args)
    except AdmissionStageError:
        raise
    except BaseException:
        raise AdmissionStageError(stage) from None


def observe_predecessor() -> tuple[object, dict]:
    runtime = _stage("PREDECESSOR_RUNTIME", observe_runtime)
    _stage("PREDECESSOR_ADMINISTRATOR", administrator_sid)
    with ExitStack() as held:
        try:
            root_handle = reads.open_generation_directory(retained_reads.TARGET_PATH)
            held.callback(read_only.close_handle, root_handle)
            root, security = read_only.inspect_directory_security(
                root_handle, retained_reads.TARGET_PATH
            )
            if (
                root.identity != predecessor.ROOT_IDENTITY
                or root.filesystem != "NTFS"
                or root.reparse is not False
                or root.classification() != "EXACT_INTENDED_ROOT"
                or security != predecessor.ROOT_SECURITY_SHA256
            ):
                raise ValueError
        except BaseException:
            raise AdmissionStageError("PREDECESSOR_ROOT") from None

        try:
            names = retained_reads.namespace(root_handle)
            if tuple(name for name, _ in names) != retained_reads.FINAL_NAMES:
                raise ValueError
        except BaseException:
            raise AdmissionStageError("PREDECESSOR_NAMESPACE") from None

        files = []
        try:
            for name in retained_reads.FINAL_NAMES:
                handle = retained_reads.open_retained_file(name)
                held.callback(read_only.close_handle, handle)
                snapshot = retained_reads.file_snapshot(handle, name)
                policy = file_policy.observe_file_policy(handle)
                file_policy.require_file_policy(name, policy)
                if snapshot != (
                    (predecessor.ROOT_IDENTITY[0], dict(names)[name]),
                    predecessor.FILE_HASHES[name],
                ):
                    raise ValueError
                files.append((handle, name, snapshot, policy))
        except BaseException:
            raise AdmissionStageError("PREDECESSOR_FILES") from None

        raw = _stage("PREDECESSOR_PUBLICATION_PATH", _publication_path_read)
        activation, host = _stage(
            "PREDECESSOR_PUBLICATION_PARSE", _publication_parse, raw
        )
        _stage(
            "PREDECESSOR_PUBLICATION_SEMANTICS",
            _publication_semantics,
            runtime,
            raw,
            activation,
            host,
        )
        state_path = _stage(
            "PREDECESSOR_STATE_PATH", _state_path_resolution, activation
        )

        try:
            state_connection = sqlite3.connect(
                state_path.as_uri() + "?mode=ro", uri=True, timeout=0
            )
            held.callback(state_connection.close)
            state_connection.execute("BEGIN")
            state = predecessor.require_ready_state(state_connection, activation)
        except BaseException:
            raise AdmissionStageError("PREDECESSOR_STATE") from None

        try:
            paper_connection = sqlite3.connect(
                binding.PAPER_PATH.as_uri() + "?mode=ro", uri=True, timeout=0
            )
            held.callback(paper_connection.close)
            paper_connection.execute("BEGIN")
            paper = predecessor.require_empty_paper(paper_connection, activation, host)
        except BaseException:
            raise AdmissionStageError("PREDECESSOR_PAPER") from None

        try:
            if (
                _publication_path_read() != raw
                or _state_path_resolution(activation) != state_path
                or predecessor.require_ready_state(state_connection, activation)
                != state
                or predecessor.require_empty_paper(paper_connection, activation, host)
                != paper
                or retained_reads.namespace(root_handle) != names
                or read_only.inspect_directory_security(
                    root_handle, retained_reads.TARGET_PATH
                )
                != (root, security)
            ):
                raise ValueError
            for handle, name, snapshot, policy in files:
                if (
                    retained_reads.file_snapshot(handle, name) != snapshot
                    or file_policy.observe_file_policy(handle) != policy
                ):
                    raise ValueError
        except BaseException:
            raise AdmissionStageError("PREDECESSOR_FINAL_REOBSERVATION") from None

    if _stage("PREDECESSOR_RUNTIME_REOBSERVATION", observe_runtime) != runtime:
        raise AdmissionStageError("PREDECESSOR_RUNTIME_REOBSERVATION")
    _stage("PREDECESSOR_ADMINISTRATOR_REOBSERVATION", administrator_sid)
    return activation, {
        "runtime": runtime,
        "publication_files": predecessor.FILE_HASHES,
        "root_identity": list(predecessor.ROOT_IDENTITY),
        "root_security_sha256": predecessor.ROOT_SECURITY_SHA256,
        "namespace": [list(item) for item in names],
        "store_identity": str(activation.store_identity),
        "paper_predecessor_sha256": paper,
        "state_sha256": state.fingerprint,
        "wake_revision": 0,
        "consumed_wake_authority": 0,
    }


def require_retained(old: object) -> None:
    retained = generation.predecessor_material()
    if (
        retained.activation != old
        or digest(retained.host.to_json().encode())
        != predecessor.FILE_HASHES["host-binding.json"]
    ):
        raise ValueError("retained predecessor changed")


def _publication_path_read() -> tuple[bytes, bytes]:
    # Same fixed Path reads as 133-M; bound before retaining and after reading.
    raw = []
    for path in (binding.ACTIVATION_PATH, binding.BINDING_PATH):
        if not 0 < path.stat().st_size <= predecessor.MAX_PUBLICATION_BYTES:
            raise ValueError
        value = path.read_bytes()
        if (
            not 0 < len(value) <= predecessor.MAX_PUBLICATION_BYTES
            or hashlib.sha256(value).hexdigest() != predecessor.FILE_HASHES[path.name]
        ):
            raise ValueError
        raw.append(value)
    return raw[0], raw[1]


def _publication_parse(
    raw: tuple[bytes, bytes],
) -> tuple[ReviewPaperActivation, binding.HostBinding]:
    activation = ReviewPaperActivation.from_json(raw[0].decode("utf-8"))
    host = binding.HostBinding.from_json(raw[1].decode("utf-8"))
    if raw != (activation.to_json().encode("utf-8"), host.to_json().encode("utf-8")):
        raise ValueError
    return activation, host


def _publication_semantics(
    runtime: dict,
    raw: tuple[bytes, bytes],
    activation: ReviewPaperActivation,
    host: binding.HostBinding,
) -> None:
    expected = binding.HostRuntimeIdentity(
        predecessor.PUBLISHED_RUNTIME_HEAD,
        predecessor.PUBLISHED_RUNTIME_TREE,
        binding.PRODUCTION_PYTHON_SHA256,
        binding.PRODUCTION_PYTHON_VERSION,
        runtime["wake_launcher_sha256"],
    )
    if (
        host.runtime != expected
        or hashlib.sha256(raw[0]).hexdigest() != host.activation_sha256
        or hashlib.sha256(raw[0]).hexdigest()
        != predecessor.FILE_HASHES["activation.json"]
        or hashlib.sha256(raw[1]).hexdigest()
        != predecessor.FILE_HASHES["host-binding.json"]
        or (
            activation.source_head,
            activation.source_tree,
            activation.deployment_identity,
        )
        != (
            predecessor.PUBLISHED_RUNTIME_HEAD,
            predecessor.PUBLISHED_RUNTIME_TREE,
            expected.deployment_identity,
        )
        or activation.store_path != str(binding.PAPER_PATH)
        or activation.store_identity != host.store_identity
        or host.oauth_valid_until <= activation.created_at
        or host.paper_predecessor_sha256
        != predecessor.expected_empty_paper_sha256(activation.starting_cash)
    ):
        raise ValueError


def _state_path_resolution(activation: ReviewPaperActivation) -> Path:
    path = state_database_path(binding.STATE_PATH, activation=activation)
    if path != binding.STATE_PATH:
        raise ValueError
    return path
