"""133-L dedicated fixed-path Q133-2V; zero wake or mutation authority."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import warnings
from contextlib import (
    ExitStack,
    closing,
    contextmanager,
    redirect_stderr,
    redirect_stdout,
)
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from trading_bot.arch133_acl import read_only, retained_reads
from trading_bot.arch133_verifier import binding, credentials, file_policy, token
from trading_bot.arch133_verifier.activation import (
    ReviewPaperActivation,
    ReviewPaperWakeState,
)
from trading_bot.arch133_verifier.scheduler import build_unattended_scheduler_spec
from trading_bot.arch133_verifier.state import snapshot_unattended_state

SCHEMA = "arch133l-post-publication-verifier/v1"
FAILURE = {
    "schema": SCHEMA,
    "status": "FAILED_CLOSED",
    "reason": "POST_PUBLICATION_VERIFIER_FAILED_CLOSED",
}
SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133l")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133l"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
LAUNCHER = SOURCE_ROOT / "scripts" / "run_arch133_post_publication_verifier.py"
NO_PYCACHE = SOURCE_ROOT / "no-pycache"
BOUND_HEAD = "4677ba442eafdcec56933b992f230a702012d573"
BOUND_TREE = "6ce181b2900df0bf8c88cdd7509eb86a2b36d8dc"
ROOT_IDENTITY = (1855336320, 1407374886183770)
ROOT_SECURITY_SHA256 = (
    "6f37254510de5246c3d8427a49743f013c339f60c205a2464b46e8aa4f8ab5c7"
)
FILE_HASHES = {
    "activation.json": (
        "37873b490c3f2ccced53431c599e40ca54fdc008e09e9bfdb38eb61d10f3cab2"
    ),
    "host-binding.json": (
        "c1106d1937dab615da0f12eb9170c020add2ffdece3d3b88a10d2edf26eb47ab"
    ),
    "paper.sqlite": (
        "384828dd21e9abc82afabec955184eed22cf57839e72bcd43c74d162534663b9"
    ),
    "wake.sqlite": ("210812b956aba6d59dcf3cfbf398ebd628c972cfffbb6dd39bd96ef308a6887f"),
}
ZERO_EFFECTS = {
    name: 0
    for name in (
        "consumed_wake_authority",
        "execution_delegations",
        "oauth_storage_writes",
        "provider_calls",
        "scheduler_reads",
        "scheduler_writes",
        "paper_mutations",
        "state_mutations",
        "acl_mutations",
        "broker_effects",
    )
}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _git(root: Path, *args: str) -> str:
    # Only fixed read-only Git queries. No network/ref updates, helper or fsmonitor.
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
        raise ValueError
    return result.stdout.strip()


def _source(root: Path, branch: str) -> tuple[str, str]:
    head, tree = (_git(root, "rev-parse", name) for name in ("HEAD", "HEAD^{tree}"))
    if (
        any(re.fullmatch(r"[0-9a-f]{40}", value) is None for value in (head, tree))
        or Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
        != root.resolve(strict=True)
        or _git(root, "branch", "--show-current") != branch
        or _git(root, "remote", "get-url", "origin") != ORIGIN
        or _git(root, "status", "--porcelain=v1", "--untracked-files=all")
        or _git(root, "rev-parse", "refs/remotes/origin/" + branch) != head
        or _git(root, "rev-parse", "refs/remotes/origin/" + branch + "^{tree}") != tree
    ):
        raise ValueError
    return head, tree


def _runtime() -> dict:
    if (
        sys.argv[1:]
        or sys.platform != "win32"
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
        raise ValueError
    own = _source(SOURCE_ROOT, SOURCE_BRANCH)
    bound = _source(binding.SOURCE_ROOT, binding.SOURCE_BRANCH)
    if bound != (BOUND_HEAD, BOUND_TREE):
        raise ValueError
    return {
        "verifier_source_head": own[0],
        "verifier_source_tree": own[1],
        "bound_source_head": bound[0],
        "bound_source_tree": bound[1],
        "python_sha256": binding.PRODUCTION_PYTHON_SHA256,
        "python_version": binding.PRODUCTION_PYTHON_VERSION,
        "wake_launcher_sha256": hashlib.sha256(
            binding.LAUNCHER.read_bytes()
        ).hexdigest(),
    }


def _principal() -> None:
    token.require_trading_token(
        binding.TRADING_SID, token.WindowsTradingTokenObserver().observe()
    )


def _paper(activation: ReviewPaperActivation, host: binding.HostBinding) -> str:
    with closing(
        sqlite3.connect(binding.PAPER_PATH.as_uri() + "?mode=ro", uri=True, timeout=0)
    ) as connection:
        connection.execute("BEGIN")
        metadata = [
            list(row)
            for row in connection.execute(
                "SELECT key, value FROM metadata ORDER BY key"
            )
        ]
        cursor = connection.execute(
            "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id"
        )
        columns = [column[0] for column in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
    digest = hashlib.sha256(
        canonical(
            {
                "metadata": metadata,
                "columns": columns,
                "rows": rows,
                "record_count": len(rows),
            }
        ).encode()
    ).hexdigest()
    if (
        metadata
        != [
            ["schema_version", "2"],
            ["starting_cash", dict(metadata).get("starting_cash")],
        ]
        or Decimal(dict(metadata)["starting_cash"]) != activation.starting_cash
        or rows
        or digest != host.paper_predecessor_sha256
    ):
        raise ValueError
    return digest


def _publication(runtime: dict):
    raw_binding = binding.BINDING_PATH.read_bytes()
    raw_activation = binding.ACTIVATION_PATH.read_bytes()
    host = binding.HostBinding.from_json(raw_binding.decode("utf-8"))
    activation = ReviewPaperActivation.from_json(raw_activation.decode("utf-8"))
    expected = binding.HostRuntimeIdentity(
        BOUND_HEAD,
        BOUND_TREE,
        binding.PRODUCTION_PYTHON_SHA256,
        binding.PRODUCTION_PYTHON_VERSION,
        runtime["wake_launcher_sha256"],
    )
    if (
        host.runtime != expected
        or raw_activation != activation.to_json().encode()
        or hashlib.sha256(raw_activation).hexdigest() != host.activation_sha256
        or hashlib.sha256(raw_activation).hexdigest() != FILE_HASHES["activation.json"]
        or hashlib.sha256(raw_binding).hexdigest() != FILE_HASHES["host-binding.json"]
        or (
            activation.source_head,
            activation.source_tree,
            activation.deployment_identity,
        )
        != (BOUND_HEAD, BOUND_TREE, host.runtime.deployment_identity)
        or activation.store_path != str(binding.PAPER_PATH)
        or activation.store_identity != host.store_identity
        or host.oauth_valid_until <= activation.created_at
    ):
        raise ValueError
    state = snapshot_unattended_state(binding.STATE_PATH)
    current = state.current(activation)
    if (
        len(state.activations) != 1
        or len(state.wakes) != 1
        or current.wake.state is not ReviewPaperWakeState.READY
        or current.revision != 0
        or current.wake.updated_at != activation.created_at
    ):
        raise ValueError
    return host, activation, state, current


def _discard_log(_logger: logging.Logger, _record: logging.LogRecord) -> None:
    pass


@contextmanager
def _quiet_edges():
    """Discard credential/native output without retaining a secret-bearing buffer."""
    disabled, handle = logging.root.manager.disable, logging.Logger.handle
    streams = (sys.stdout, sys.stderr)
    for stream in streams:
        stream.flush()
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        redirect_stdout(sink),
        redirect_stderr(sink),
        warnings.catch_warnings(),
        ExitStack() as descriptors,
    ):
        for descriptor in (1, 2):
            saved = os.dup(descriptor)
            descriptors.callback(os.close, saved)
            descriptors.callback(os.dup2, saved, descriptor)
            os.dup2(sink.fileno(), descriptor)
        try:
            logging.disable(sys.maxsize)
            logging.Logger.handle = _discard_log
            warnings.simplefilter("ignore")
            yield
        finally:
            try:
                for stream in streams:
                    stream.flush()
            finally:
                logging.Logger.handle = handle
                logging.disable(disabled)


def verify_post_publication() -> dict:
    """One read-only attempt. No retries, polling, repair or alternate authority."""
    try:
        with _quiet_edges():
            runtime = _runtime()
            _principal()
            with ExitStack() as held:
                parents = []
                for path in ("F:\\", r"F:\AITradingBot"):
                    handle = read_only.open_directory(path)
                    held.callback(read_only.close_handle, handle)
                    parents.append(
                        (
                            handle,
                            path,
                            read_only.inspect_directory_security(handle, path),
                        )
                    )
                root_handle = read_only.open_directory(retained_reads.TARGET_PATH)
                held.callback(read_only.close_handle, root_handle)
                root, security = read_only.inspect_directory_security(
                    root_handle, retained_reads.TARGET_PATH
                )
                if (
                    root.identity != ROOT_IDENTITY
                    or root.filesystem != "NTFS"
                    or root.reparse is not False
                    or root.classification() != "EXACT_INTENDED_ROOT"
                    or security != ROOT_SECURITY_SHA256
                ):
                    raise ValueError
                names = retained_reads.namespace(root_handle)
                if tuple(name for name, _ in names) != retained_reads.FINAL_NAMES:
                    raise ValueError
                files = []
                for name in retained_reads.FINAL_NAMES:
                    handle = retained_reads.open_retained_file(name)
                    held.callback(read_only.close_handle, handle)
                    snapshot = retained_reads.file_snapshot(handle, name)
                    policy = file_policy.observe_file_policy(handle)
                    file_policy.require_file_policy(name, policy)
                    if snapshot != (
                        (ROOT_IDENTITY[0], dict(names)[name]),
                        FILE_HASHES[name],
                    ):
                        raise ValueError
                    files.append((handle, name, snapshot, policy))
                host, activation, state, current = _publication(runtime)
                predecessor = _paper(activation, host)
                scheduler = asdict(build_unattended_scheduler_spec(activation))
                for field in ("start_boundary", "end_boundary"):
                    scheduler[field] = scheduler[field].isoformat(
                        timespec="microseconds"
                    )
                _principal()
                available = credentials.persisted_oauth_availability()
                if (
                    type(available) is not credentials.OAuthAvailability
                    or available.persisted_oauth_available is not True
                    or type(available.oauth_storage_reads) is not int
                    or available.oauth_storage_reads != 2
                ):
                    raise ValueError
                if (
                    _publication(runtime) != (host, activation, state, current)
                    or _paper(activation, host) != predecessor
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
                for handle, path, observation in parents:
                    if (
                        read_only.inspect_directory_security(handle, path)
                        != observation
                    ):
                        raise ValueError
            # Close failures cannot produce PASS. Re-admit executable and token.
            if _runtime() != runtime:
                raise ValueError
            _principal()
            result = {
                "schema": SCHEMA,
                "status": "PASS",
                **runtime,
                "deployment_identity": host.runtime.deployment_identity,
                "trading_sid": binding.TRADING_SID,
                "root_identity": root.identity,
                "root_security_sha256": security,
                "root_policy": root.classification(),
                "filesystem": root.filesystem,
                "reparse": root.reparse,
                "activation_id": str(activation.activation_id),
                "wake_id": str(current.wake.wake_id),
                "wake_state": current.wake.state.value,
                "revision": current.revision,
                "state_fingerprint": state.fingerprint,
                "paper_predecessor_sha256": predecessor,
                "store_identity": str(host.store_identity),
                "persisted_oauth_available": True,
                "oauth_storage_reads": available.oauth_storage_reads,
                "scheduler": scheduler,
                **ZERO_EFFECTS,
            }
            if len(canonical(result)) > 8192:
                raise ValueError
            return result
    except BaseException:
        return dict(FAILURE)


def main(argv: list[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        result = dict(FAILURE) if args else verify_post_publication()
        print(canonical(result))
        return 0 if result["status"] == "PASS" else 3
    except BaseException:
        print(canonical(FAILURE))
        return 3
