"""133-O independent credential-free publication/state/paper diagnostic."""

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
    contextmanager,
    redirect_stderr,
    redirect_stdout,
)
from decimal import Decimal
from pathlib import Path

from trading_bot.arch133_acl import read_only, retained_reads
from trading_bot.arch133_verifier import binding, file_policy, token
from trading_bot.arch133_verifier.activation import (
    ReviewPaperActivation,
    ReviewPaperWakeState,
)
from trading_bot.arch133_verifier.state import (
    read_state_connection,
    state_database_path,
)

SCHEMA = "arch133o-publication-state-paper-diagnostic/v1"
SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133o")
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133o"
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
LAUNCHER = SOURCE_ROOT / "scripts" / "run_arch133_publication_state_paper_corrected.py"
NO_PYCACHE = SOURCE_ROOT / "no-pycache"
EXECUTABLE_SOURCE_HEAD = "4677ba442eafdcec56933b992f230a702012d573"
EXECUTABLE_SOURCE_TREE = "6ce181b2900df0bf8c88cdd7509eb86a2b36d8dc"
# Reviewed docs-only runtime closeout; independent frozen executable baseline above.
PUBLISHED_RUNTIME_HEAD = "65f0d40217f8ce129224531a5151f4acea889d89"
PUBLISHED_RUNTIME_TREE = "16cb734cbeaa9e97aaf9e2d521d922fbbc7b7ae2"
BOUND_CHECKOUTS = frozenset(
    {
        (EXECUTABLE_SOURCE_HEAD, EXECUTABLE_SOURCE_TREE),
        (PUBLISHED_RUNTIME_HEAD, PUBLISHED_RUNTIME_TREE),
    }
)
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
        "credential_reads",
        "credential_writes",
        "wake_delegations",
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
        raise ValueError
    return head, tree


def _diagnostic_source() -> tuple[str, str]:
    head, tree = _clean_source(SOURCE_ROOT, SOURCE_BRANCH)
    ref = "refs/remotes/origin/" + SOURCE_BRANCH
    if (
        _git(SOURCE_ROOT, "rev-parse", ref) != head
        or _git(SOURCE_ROOT, "rev-parse", ref + "^{tree}") != tree
    ):
        raise ValueError
    return head, tree


def _bound_source() -> tuple[str, str]:
    checkout = _clean_source(binding.SOURCE_ROOT, binding.SOURCE_BRANCH)
    if checkout not in BOUND_CHECKOUTS:
        raise ValueError
    return EXECUTABLE_SOURCE_HEAD, EXECUTABLE_SOURCE_TREE


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
    own = _diagnostic_source()
    bound = _bound_source()
    if bound != (EXECUTABLE_SOURCE_HEAD, EXECUTABLE_SOURCE_TREE):
        raise ValueError
    return {
        "diagnostic_source_head": own[0],
        "diagnostic_source_tree": own[1],
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


EMPTY_PAPER_COLUMNS = (
    "paper_trade_id",
    "proposal_id",
    "order_id",
    "symbol",
    "side",
    "desired_quantity",
    "approved_quantity",
    "risk_outcome",
    "risk_reason_codes",
    "proposal_reason",
    "proposal_confidence",
    "order_type",
    "time_in_force",
    "proposed_at",
    "limit_price",
    "reviewed_at",
    "market_data_disclosure",
    "order_checks_json",
    "adjusted_previous_close",
    "ask_price",
    "bid_price",
    "has_traded",
    "last_non_reg_trade_price",
    "last_trade_price",
    "previous_close",
    "previous_close_date",
    "quote_state",
    "venue_ask_time",
    "venue_bid_time",
    "venue_last_non_reg_trade_time",
    "venue_last_trade_time",
    "fill_id",
    "fill_price",
    "commission",
    "slippage_basis_points",
    "filled_at",
)


STAGES = (
    "PUBLICATION_PATH_READ",
    "PUBLICATION_PARSE",
    "PUBLICATION_SEMANTICS",
    "STATE_PATH_RESOLUTION",
    "STATE_SQLITE_OPEN",
    "STATE_SEMANTICS",
    "PAPER_SQLITE_OPEN",
    "PAPER_SEMANTICS",
    "FINAL_REOBSERVATION",
)
RUNTIME_BLOCK = "ARCH133O_RUNTIME_BLOCKED"
MAX_PUBLICATION_BYTES = 1024 * 1024


def publication_fingerprint(metadata: list, columns: list, rows: list) -> str:
    """Frozen qualification fingerprint without importing publication effects."""
    return hashlib.sha256(
        canonical(
            {
                "metadata": metadata,
                "columns": columns,
                "rows": rows,
                "record_count": len(rows),
            }
        ).encode("utf-8")
    ).hexdigest()


def expected_empty_paper_sha256(starting_cash: Decimal) -> str:
    """Reconstruct the accepted predecessor without SQLite or scratch files."""
    return publication_fingerprint(
        [["schema_version", "2"], ["starting_cash", str(starting_cash)]],
        list(EMPTY_PAPER_COLUMNS),
        [],
    )


def _publication_path_read() -> tuple[bytes, bytes]:
    # Same fixed Path reads as 133-M; bound before retaining and after reading.
    raw = []
    for path in (binding.ACTIVATION_PATH, binding.BINDING_PATH):
        if not 0 < path.stat().st_size <= MAX_PUBLICATION_BYTES:
            raise ValueError
        value = path.read_bytes()
        if (
            not 0 < len(value) <= MAX_PUBLICATION_BYTES
            or hashlib.sha256(value).hexdigest() != FILE_HASHES[path.name]
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
        PUBLISHED_RUNTIME_HEAD,
        PUBLISHED_RUNTIME_TREE,
        binding.PRODUCTION_PYTHON_SHA256,
        binding.PRODUCTION_PYTHON_VERSION,
        runtime["wake_launcher_sha256"],
    )
    if (
        host.runtime != expected
        or hashlib.sha256(raw[0]).hexdigest() != host.activation_sha256
        or hashlib.sha256(raw[0]).hexdigest() != FILE_HASHES["activation.json"]
        or hashlib.sha256(raw[1]).hexdigest() != FILE_HASHES["host-binding.json"]
        or (
            activation.source_head,
            activation.source_tree,
            activation.deployment_identity,
        )
        != (
            PUBLISHED_RUNTIME_HEAD,
            PUBLISHED_RUNTIME_TREE,
            expected.deployment_identity,
        )
        or activation.store_path != str(binding.PAPER_PATH)
        or activation.store_identity != host.store_identity
        or host.oauth_valid_until <= activation.created_at
        or host.paper_predecessor_sha256
        != expected_empty_paper_sha256(activation.starting_cash)
    ):
        raise ValueError


def _state_path_resolution(activation: ReviewPaperActivation) -> Path:
    path = state_database_path(binding.STATE_PATH, activation=activation)
    if path != binding.STATE_PATH:
        raise ValueError
    return path


def _state_semantics(connection: sqlite3.Connection, activation: ReviewPaperActivation):
    snapshot = read_state_connection(connection)
    current = snapshot.current(activation)
    if (
        len(snapshot.activations) != 1
        or len(snapshot.wakes) != 1
        or current.wake.state is not ReviewPaperWakeState.READY
        or current.revision != 0
        or current.wake.updated_at != activation.created_at
    ):
        raise ValueError
    return snapshot


def _paper_semantics(
    connection: sqlite3.Connection,
    activation: ReviewPaperActivation,
    host: binding.HostBinding,
) -> str:
    metadata = [
        list(row)
        for row in connection.execute("SELECT key, value FROM metadata ORDER BY key")
    ]
    cursor = connection.execute(
        "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id"
    )
    columns = [column[0] for column in cursor.description]
    rows = [list(row) for row in cursor.fetchall()]
    digest = publication_fingerprint(metadata, columns, rows)
    if (
        metadata
        != [
            ["schema_version", "2"],
            ["starting_cash", dict(metadata).get("starting_cash")],
        ]
        or Decimal(dict(metadata)["starting_cash"]) != activation.starting_cash
        or tuple(columns) != EMPTY_PAPER_COLUMNS
        or len(set(columns)) != len(columns)
        or rows
        or digest != host.paper_predecessor_sha256
    ):
        raise ValueError
    return digest


def _discard_log(_logger: logging.Logger, _record: logging.LogRecord) -> None:
    pass


@contextmanager
def _quiet_edges():
    """Discard native output without retaining a sensitive buffer."""
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


def stage_result(stage: str, *, passed: bool = False) -> dict:
    """Only the frozen nine stages and explicit integer zeros can escape."""
    if stage not in STAGES:
        raise ValueError
    return {
        "schema": SCHEMA,
        "status": "PASS" if passed else "BLOCKED",
        "reason": (
            "PUBLICATION_STATE_PAPER_DIAGNOSTIC_COMPLETE"
            if passed
            else "PUBLICATION_STATE_PAPER_DIAGNOSTIC_BLOCKED"
        ),
        "stage": "PUBLICATION_STATE_PAPER_COMPLETE" if passed else stage,
        **ZERO_EFFECTS,
    }


def diagnose_publication_state_paper() -> dict | None:
    """One observation; None is a pre-publication runtime block, never a stage."""
    stage = None
    close_failed = False

    def close_once(close, *args) -> None:
        nonlocal close_failed
        try:
            close(*args)
        except BaseException:
            close_failed = True

    try:
        with _quiet_edges():
            runtime = _runtime()
            _principal()
            with ExitStack() as held:
                root_handle = read_only.open_directory(retained_reads.TARGET_PATH)
                held.callback(close_once, read_only.close_handle, root_handle)
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
                    held.callback(close_once, read_only.close_handle, handle)
                    snapshot = retained_reads.file_snapshot(handle, name)
                    policy = file_policy.observe_file_policy(handle)
                    file_policy.require_file_policy(name, policy)
                    if snapshot != (
                        (ROOT_IDENTITY[0], dict(names)[name]),
                        FILE_HASHES[name],
                    ):
                        raise ValueError
                    files.append((handle, name, snapshot, policy))

                stage = "PUBLICATION_PATH_READ"
                raw = _publication_path_read()
                stage = "PUBLICATION_PARSE"
                activation, host = _publication_parse(raw)
                stage = "PUBLICATION_SEMANTICS"
                _publication_semantics(runtime, raw, activation, host)
                stage = "STATE_PATH_RESOLUTION"
                state_path = _state_path_resolution(activation)
                stage = "STATE_SQLITE_OPEN"
                state_connection = sqlite3.connect(
                    state_path.as_uri() + "?mode=ro", uri=True, timeout=0
                )
                held.callback(close_once, state_connection.close)
                state_connection.execute("BEGIN")
                stage = "STATE_SEMANTICS"
                state = _state_semantics(state_connection, activation)
                stage = "PAPER_SQLITE_OPEN"
                paper_connection = sqlite3.connect(
                    binding.PAPER_PATH.as_uri() + "?mode=ro", uri=True, timeout=0
                )
                held.callback(close_once, paper_connection.close)
                paper_connection.execute("BEGIN")
                stage = "PAPER_SEMANTICS"
                paper = _paper_semantics(paper_connection, activation, host)
                stage = "FINAL_REOBSERVATION"
                repeated_raw = _publication_path_read()
                repeated = _publication_parse(repeated_raw)
                _publication_semantics(runtime, repeated_raw, *repeated)
                if (
                    repeated_raw != raw
                    or repeated != (activation, host)
                    or _state_path_resolution(activation) != state_path
                    or _state_semantics(state_connection, activation) != state
                    or _paper_semantics(paper_connection, activation, host) != paper
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
            if close_failed or _runtime() != runtime:
                raise ValueError
            _principal()
        return stage_result("FINAL_REOBSERVATION", passed=True)
    except BaseException:
        if close_failed:
            return stage_result("FINAL_REOBSERVATION")
        return None if stage is None else stage_result(stage)


def main(argv: list[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        result = None if args else diagnose_publication_state_paper()
        print(RUNTIME_BLOCK if result is None else canonical(result))
        return 0 if result is not None and result["status"] == "PASS" else 3
    except BaseException:
        print(RUNTIME_BLOCK)
        return 3
