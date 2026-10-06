"""133-E fixed-location zero-argument host and provider-free Q133-1 preflight.

No authority comes from scheduler state, CLI, cwd, or environment. Publication
is read-only here. The accepted 133-D/C/B path owns all state/effect ordering.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
import warnings
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from trading_bot.review_paper import unattended_host_identity as identity
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import (
    ReviewPaperActivation,
    ReviewPaperWakeState,
)
from trading_bot.review_paper.unattended_execution import (
    UnattendedExecutionBinding,
    UnattendedExecutionResult,
    execute_one_unattended_review_paper_wake,
)
from trading_bot.review_paper.unattended_one_wake import (
    OneWakeClassification,
    OneWakeInstants,
    OneWakeResult,
)
from trading_bot.review_paper.unattended_scheduler import (
    UnattendedSchedulerSpec,
    build_unattended_scheduler_spec,
)
from trading_bot.review_paper.unattended_state_schema import PersistedReviewPaperWake
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.review_paper.unattended_state_verifier import snapshot_unattended_state
from trading_bot.robinhood_execute_qualification_verifier import (
    qualification_fingerprint,
    read_qualification_store,
)
from trading_bot.robinhood_mcp.windows_oauth import WindowsOAuthStorage


@dataclass(frozen=True, slots=True)
class UnattendedHostEvidence:
    status: str
    activation_id: UUID
    wake_id: UUID
    state: ReviewPaperWakeState
    revision: int
    execution_delegations: int


@dataclass(frozen=True, slots=True)
class UnattendedHostPreflight:
    source_head: str
    source_tree: str
    deployment_identity: str
    activation_id: UUID
    wake_id: UUID
    state_fingerprint: str
    paper_predecessor_sha256: str
    persisted_oauth_available: bool
    scheduler: UnattendedSchedulerSpec
    consumed_wake_authority: int = 0
    execution_delegations: int = 0


def _admit() -> tuple[
    identity.HostBinding, ReviewPaperActivation, PersistedReviewPaperWake
]:
    binding = identity.read_host_binding()
    identity.admit_host_runtime(binding)
    raw = identity.ACTIVATION_PATH.read_bytes()
    activation = ReviewPaperActivation.from_json(raw.decode("utf-8"))
    snapshot = snapshot_unattended_state(identity.STATE_PATH)
    current = snapshot.current(activation)
    if (
        raw != activation.to_json().encode("utf-8")
        or hashlib.sha256(raw).hexdigest() != binding.activation_sha256
        or (
            activation.source_head,
            activation.source_tree,
            activation.deployment_identity,
        )
        != (
            binding.runtime.source_head,
            binding.runtime.source_tree,
            binding.runtime.deployment_identity,
        )
        or activation.store_path != str(identity.PAPER_PATH)
        or activation.store_identity != binding.store_identity
        or len(snapshot.activations) != 1
        or binding.oauth_valid_until <= activation.created_at
        or (current.wake.state is ReviewPaperWakeState.READY and current.revision != 0)
    ):
        raise identity.UnattendedHostError("host activation/state binding failed")
    return binding, activation, current


def _paper_predecessor(
    binding: identity.HostBinding, activation: ReviewPaperActivation
) -> str:
    metadata, columns, rows = read_qualification_store(identity.PAPER_PATH)
    values = dict(metadata)
    digest = qualification_fingerprint(metadata, columns, rows)["sha256"]
    if (
        len(metadata) != 2
        or set(values) != {"schema_version", "starting_cash"}
        or values["schema_version"] != "2"
        or Decimal(values["starting_cash"]) != activation.starting_cash
        or digest != binding.paper_predecessor_sha256
    ):
        raise identity.UnattendedHostError("host paper predecessor failed")
    return digest


def _current_utc() -> datetime:
    return datetime.now(UTC)


def _persisted_oauth_available() -> bool:
    # Summarize only accepted persisted-storage availability. No OAuth provider,
    # refresh, browser or registration object is constructed. Raw tokens stay
    # inside this boundary and are never evidence or execution authority.
    tokens = asyncio.run(WindowsOAuthStorage().get_tokens())
    return bool(
        tokens is not None
        and tokens.token_type.lower() == "bearer"
        and tokens.access_token
        and (tokens.expires_in is None or tokens.expires_in > 0)
    )


def _discard_log(_logger: logging.Logger, _record: logging.LogRecord) -> None:
    pass


@contextmanager
def _quiet_edges() -> Iterator[None]:
    """Discard credential/provider output; retain no secret-bearing buffer."""
    disabled = logging.root.manager.disable
    handle = logging.Logger.handle
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


def preflight_unattended_host() -> UnattendedHostPreflight:
    """Q133-1 read-only; never construct stores/writers or invoke 133-D.

    This surface requires already-published exact material. Publication itself
    remains separately authorized; source tests use deterministic publications.
    """
    try:
        with _quiet_edges():
            binding, activation, current = _admit()
            if (
                current.wake.state is not ReviewPaperWakeState.READY
                or current.revision != 0
            ):
                raise ValueError
            scheduler = build_unattended_scheduler_spec(activation)
            digest = _paper_predecessor(binding, activation)
            available = _persisted_oauth_available()
            after = snapshot_unattended_state(identity.STATE_PATH)
            if (
                available is not True
                or len(after.activations) != 1
                or after.current(activation) != current
                or _paper_predecessor(binding, activation) != digest
            ):
                raise ValueError
            return UnattendedHostPreflight(
                activation.source_head,
                activation.source_tree,
                activation.deployment_identity,
                activation.activation_id,
                current.wake.wake_id,
                after.fingerprint,
                digest,
                available,
                scheduler,
            )
    except BaseException:
        raise identity.UnattendedHostError("host preflight failed closed") from None


def run_unattended_host() -> UnattendedHostEvidence:
    """Inspect one published wake and delegate at most once, without retry."""
    try:
        with _quiet_edges():
            binding, activation, current = _admit()
            if current.wake.state is not ReviewPaperWakeState.READY:
                # Accepted durable state is authoritative even for a manual launch.
                return UnattendedHostEvidence(
                    "READ_ONLY_REPLAY",
                    activation.activation_id,
                    current.wake.wake_id,
                    current.wake.state,
                    current.revision,
                    0,
                )
            build_unattended_scheduler_spec(activation)
            _paper_predecessor(binding, activation)
            at = _current_utc()  # Sole current-time capture, after exact admission.
            if type(at) is not datetime or at.tzinfo is None or at.utcoffset() is None:
                raise ValueError
            at = at.astimezone(UTC)
            if at < activation.created_at:
                raise ValueError
            # An expired OAuth bound is a no-provider STOP through the accepted
            # 133-D quote edge; the host never substitutes fresh OAuth authority.
            result = execute_one_unattended_review_paper_wake(
                activation=activation,
                expected=current,
                state_store=UnattendedStateStore(identity.STATE_PATH),
                paper_store=ReviewPaperStore(
                    identity.PAPER_PATH, starting_cash=activation.starting_cash
                ),
                instants=OneWakeInstants(at, at, at),
                binding=UnattendedExecutionBinding(
                    identity.SOURCE_BRANCH,
                    activation.source_head,
                    activation.source_tree,
                    activation.deployment_identity,
                    identity.EVIDENCE_PATH,
                    identity.REDIRECT_URI,
                    binding.oauth_valid_until,
                    at,
                ),
                oauth_storage=WindowsOAuthStorage(),
            )
            if (
                type(result) is not UnattendedExecutionResult
                or type(result.wake) is not OneWakeResult
                or type(result.wake.classification) is not OneWakeClassification
            ):
                raise ValueError
            final = snapshot_unattended_state(identity.STATE_PATH).current(activation)
            if (
                result.wake.activation_id != activation.activation_id
                or result.wake.wake_id != current.wake.wake_id
                or result.wake.final_state is not final.wake.state
                or result.wake.revisions[-1] != final.revision
                or type(result.wake.classification.value) is not str
            ):
                raise ValueError
            return UnattendedHostEvidence(
                result.wake.classification.value,
                activation.activation_id,
                final.wake.wake_id,
                final.wake.state,
                final.revision,
                1,
            )
    except BaseException:
        # Never compensate/retry after a delegation exception. Reopen is read-only
        # if accepted durability has consumed/ambiguously crossed an effect fence.
        raise identity.UnattendedHostError("host wake failed closed") from None


def main(argv: list[str] | None = None) -> int:
    """Zero semantic arguments; even invalid/secret input is never echoed."""
    if sys.argv[1:] if argv is None else argv:
        print(
            '{"reason":"INVALID_ARGUMENTS","schema":"arch133-host/v1"}', file=sys.stderr
        )
        return 2
    try:
        result = run_unattended_host()
        payload = asdict(result)
        payload["activation_id"] = str(result.activation_id)
        payload["wake_id"] = str(result.wake_id)
        payload["schema"] = "arch133-host/v1"
    except BaseException:
        print(
            '{"reason":"HOST_FAILED_CLOSED","schema":"arch133-host/v1"}',
            file=sys.stderr,
        )
        return 3
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0
