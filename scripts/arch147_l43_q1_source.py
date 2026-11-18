"""Source-admitted, read-only dispatch for the Architecture 147 L43-Q1 gate."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import warnings
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

CHECKPOINT: Final = "ARCH147-L43-Q1_QUALIFICATION_PREFLIGHT_SOURCE"
RESULT_SCHEMA: Final = "arch147-l43-qualification-preflight/v1"
FEATURE_BRANCH: Final = "feature/robinhood-live-prototype-current"
REPOSITORY: Final = "callmedraken/ai-trading-bot"
ORIGIN_URLS: Final = frozenset(
    {
        f"https://github.com/{REPOSITORY}",
        f"https://github.com/{REPOSITORY}.git",
    }
)
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_PROVIDER_COUNT_KEYS = frozenset(
    {
        "robinhood_reads",
        "robinhood_pages",
        "alpaca_provider_calls",
        "credential_reads",
    }
)
_EFFECT_COUNT_KEYS = frozenset(
    {
        "review",
        "placement",
        "cancellation",
        "broker_mutation",
        "durable_state_mutation",
        "q62_journal_mutation",
    }
)


@dataclass(frozen=True)
class _SourceSnapshot:
    root_is_canonical: bool
    windows_host: bool
    canonical_origin: bool
    clean: bool | None
    branch: str | None
    local_head: str | None
    local_tree: str | None
    feature_head: str | None
    develop_head: str | None


def run_preflight() -> dict[str, object]:
    """Prove integrated source identity before lazily loading the Q1 owner."""
    before = _capture_source_snapshot()
    before_reasons = _source_failures(before)
    if before_reasons:
        return _report(
            status="BLOCKED",
            source_status="BLOCKED",
            dispatch_status="NOT_STARTED",
            provider_call_counts=_zero_provider_counts(),
            before=before,
            after=None,
            source_reason_codes=before_reasons,
            dispatch_reason_codes=(),
            qualification=None,
        )

    try:
        with _quiet_provider_output():
            owner = _load_q1_owner()
            raw_result = owner._run_protected_preflight()
            result_is_sanitized = owner._is_sanitized_result(raw_result)
    except (Exception, asyncio.CancelledError, KeyboardInterrupt):
        after = _capture_source_snapshot()
        after_reasons = _source_failures(after)
        source_stable = not after_reasons and _same_source(before, after)
        return _report(
            status="BLOCKED",
            source_status="PASS" if source_stable else "BLOCKED",
            dispatch_status="FAILED",
            provider_call_counts=None,
            before=before,
            after=after,
            source_reason_codes=(
                ()
                if source_stable
                else after_reasons or ("SOURCE_IDENTITY_CHANGED_DURING_PREFLIGHT",)
            ),
            dispatch_reason_codes=("QUALIFICATION_DISPATCH_FAILED",),
            qualification=None,
        )

    if (
        result_is_sanitized is not True
        or type(raw_result) is not dict
        or (
            raw_result.get("status") == "PASS"
            and (
                raw_result.get("source_head") != before.local_head
                or raw_result.get("source_tree") != before.local_tree
            )
        )
    ):
        after = _capture_source_snapshot()
        after_reasons = _source_failures(after)
        source_stable = not after_reasons and _same_source(before, after)
        return _report(
            status="BLOCKED",
            source_status="PASS" if source_stable else "BLOCKED",
            dispatch_status="COMPLETED_UNACCEPTED",
            provider_call_counts=None,
            before=before,
            after=after,
            source_reason_codes=(
                ()
                if source_stable
                else after_reasons or ("SOURCE_IDENTITY_CHANGED_DURING_PREFLIGHT",)
            ),
            dispatch_reason_codes=("QUALIFICATION_RESULT_REJECTED",),
            qualification=None,
        )

    after = _capture_source_snapshot()
    after_reasons = _source_failures(after)
    if after_reasons or not _same_source(before, after):
        reasons = after_reasons or ("SOURCE_IDENTITY_CHANGED_DURING_PREFLIGHT",)
        return _report(
            status="BLOCKED",
            source_status="BLOCKED",
            dispatch_status="COMPLETED",
            provider_call_counts=_safe_provider_counts(raw_result),
            before=before,
            after=after,
            source_reason_codes=reasons,
            dispatch_reason_codes=(),
            qualification=_invalidated_qualification(raw_result),
        )
    return _report(
        status=raw_result["status"],
        source_status="PASS",
        dispatch_status="COMPLETED",
        provider_call_counts=_safe_provider_counts(raw_result),
        before=before,
        after=after,
        source_reason_codes=(),
        dispatch_reason_codes=(),
        qualification=raw_result,
    )


def _load_q1_owner() -> object:
    """Import the production owner only after the runner source gate passes."""
    import importlib

    repo_root = Path(__file__).resolve().parents[1]
    source_root = (repo_root / "src").resolve(strict=True)
    module_name = "trading_bot.live_prototype.l43_qualification_preflight"
    for package_name in ("trading_bot", "trading_bot.live_prototype"):
        existing = sys.modules.get(package_name)
        existing_path = getattr(existing, "__file__", None)
        if existing_path is None:
            continue
        try:
            if source_root not in Path(existing_path).resolve(strict=True).parents:
                raise RuntimeError("source package provenance rejected")
        except (OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError("source package provenance rejected") from exc
    source_text = str(source_root)
    original_path = list(sys.path)
    sys.path.insert(0, source_text)
    try:
        owner = importlib.import_module(module_name)
        module_path = Path(owner.__file__).resolve(strict=True)
        if source_root not in module_path.parents:
            raise RuntimeError("Q1 module provenance rejected")
        if (
            getattr(owner, "SCHEMA", None) != RESULT_SCHEMA
            or getattr(owner, "CHECKPOINT", None) != CHECKPOINT
        ):
            raise RuntimeError("Q1 module contract rejected")
        return owner
    finally:
        sys.path[:] = original_path


def _capture_source_snapshot() -> _SourceSnapshot:
    repo_root = Path(__file__).resolve().parents[1]
    root_is_canonical = _root_is_canonical(repo_root)
    origin = _git_text(repo_root, "remote", "get-url", "origin")
    canonical_origin = origin in ORIGIN_URLS
    clean_text = _git_text(
        repo_root, "status", "--porcelain=v1", "--untracked-files=all"
    )
    local_head = _git_text(repo_root, "rev-parse", "HEAD")
    local_tree = _git_text(repo_root, "rev-parse", "HEAD^{tree}")
    branch = _git_text(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    feature_head = None
    develop_head = None
    if canonical_origin:
        feature_head, develop_head = _live_feature_and_develop_heads(repo_root)
    return _SourceSnapshot(
        root_is_canonical=root_is_canonical,
        windows_host=os.name == "nt",
        canonical_origin=canonical_origin,
        clean=None if clean_text is None else not clean_text,
        branch=branch,
        local_head=local_head if _SHA1.fullmatch(local_head or "") else None,
        local_tree=local_tree if _SHA1.fullmatch(local_tree or "") else None,
        feature_head=feature_head,
        develop_head=develop_head,
    )


def _root_is_canonical(repo_root: Path) -> bool:
    try:
        root = repo_root.resolve(strict=True)
        expected = Path(
            r"F:\AI\worktrees\ai-trading-bot-live-prototype-current"
        ).resolve(strict=True)
        return root == expected
    except (OSError, RuntimeError, ValueError):
        return False


def _git_text(repo_root: Path, *arguments: str) -> str | None:
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
        }
    )
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _live_feature_and_develop_heads(repo_root: Path) -> tuple[str | None, str | None]:
    output = _git_text(
        repo_root,
        "ls-remote",
        "origin",
        "refs/heads/develop",
        f"refs/heads/{FEATURE_BRANCH}",
    )
    if output is None:
        return None, None
    expected_refs = {
        f"refs/heads/{FEATURE_BRANCH}",
        "refs/heads/develop",
    }
    rows: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if (
            len(parts) != 2
            or parts[1] not in expected_refs
            or parts[1] in rows
            or _SHA1.fullmatch(parts[0]) is None
        ):
            return None, None
        rows[parts[1]] = parts[0]
    if set(rows) != expected_refs:
        return None, None
    return rows[f"refs/heads/{FEATURE_BRANCH}"], rows["refs/heads/develop"]


def _source_failures(snapshot: _SourceSnapshot) -> tuple[str, ...]:
    failures = []
    if not snapshot.windows_host:
        failures.append("WINDOWS_HOST_REQUIRED")
    if not snapshot.root_is_canonical:
        failures.append("CANONICAL_CHECKOUT_REQUIRED")
    if not snapshot.canonical_origin:
        failures.append("CANONICAL_ORIGIN_REQUIRED")
    if snapshot.clean is not True:
        failures.append("CLEAN_SOURCE_REQUIRED")
    if snapshot.branch != FEATURE_BRANCH:
        failures.append("CANONICAL_FEATURE_BRANCH_REQUIRED")
    if (
        snapshot.local_head is None
        or snapshot.local_tree is None
        or snapshot.feature_head is None
        or snapshot.develop_head is None
    ):
        failures.append("SOURCE_IDENTITY_UNAVAILABLE")
    elif not (snapshot.local_head == snapshot.feature_head == snapshot.develop_head):
        failures.append("FEATURE_DEVELOP_SOURCE_MISMATCH")
    return tuple(dict.fromkeys(failures))


def _same_source(first: _SourceSnapshot, second: _SourceSnapshot) -> bool:
    return first == second


def _invalidated_qualification(value: dict[str, object]) -> dict[str, object]:
    return {
        "status": "BLOCKED",
        "outcome": "BLOCKED",
        "reason_codes": ["SOURCE_IDENTITY_CHANGED_DURING_PREFLIGHT"],
        "result_sha256": _safe_result_digest(value),
        "provider_call_counts": _safe_provider_counts(value),
        "effect_counters": _safe_effect_counts(value),
        "automatic_retry": "NOT_AUTHORIZED",
    }


def _safe_result_digest(value: dict[str, object]) -> str | None:
    try:
        material = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return sha256(material).hexdigest()


def _safe_provider_counts(value: dict[str, object]) -> dict[str, int | None] | None:
    counts = value.get("provider_call_counts")
    if (
        type(counts) is not dict
        or set(counts) != _PROVIDER_COUNT_KEYS
        or any(
            count is not None and (type(count) is not int or count < 0)
            for count in counts.values()
        )
    ):
        return None
    return dict(counts)


def _safe_effect_counts(value: dict[str, object]) -> dict[str, int] | None:
    counts = value.get("effect_counters")
    if (
        type(counts) is not dict
        or set(counts) != _EFFECT_COUNT_KEYS
        or any(type(count) is not int or count != 0 for count in counts.values())
    ):
        return None
    return dict(counts)


def _zero_provider_counts() -> dict[str, int]:
    return {
        "robinhood_reads": 0,
        "robinhood_pages": 0,
        "alpaca_provider_calls": 0,
        "credential_reads": 0,
    }


def _report(
    *,
    status: str,
    source_status: str,
    dispatch_status: str,
    provider_call_counts: dict[str, int | None] | None,
    before: _SourceSnapshot,
    after: _SourceSnapshot | None,
    source_reason_codes: tuple[str, ...],
    dispatch_reason_codes: tuple[str, ...],
    qualification: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "status": status,
        "source_admission": {
            "before": _snapshot_evidence(before),
            "after": None if after is None else _snapshot_evidence(after),
            "status": source_status,
            "reason_codes": list(source_reason_codes),
        },
        "dispatch": {
            "status": dispatch_status,
            "provider_call_counts": provider_call_counts,
            "reason_codes": list(dispatch_reason_codes),
        },
        "qualification": qualification,
    }


def _snapshot_evidence(snapshot: _SourceSnapshot) -> dict[str, object]:
    evidence = asdict(snapshot)
    evidence["branch"] = (
        "FEATURE_BRANCH"
        if snapshot.branch == FEATURE_BRANCH
        else "OTHER"
        if snapshot.branch is not None
        else None
    )
    return evidence


def _discard_log(*args: object, **kwargs: object) -> None:
    del args, kwargs


@contextmanager
def _quiet_provider_output() -> Iterator[None]:
    """Discard provider SDK output, warnings, logs and native stdout/stderr."""
    streams = sys.stdout, sys.stderr
    for stream in streams:
        stream.flush()
    previous_disable = logging.root.manager.disable
    previous_handle = logging.Logger.handle
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
            for stream in streams:
                stream.flush()
            logging.Logger.handle = previous_handle
            logging.disable(previous_disable)
