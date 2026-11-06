"""Typed, effect-free evidence references for the Q62 readiness boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ProofKind(StrEnum):
    SOURCE = "SOURCE"
    CONFIGURATION = "CONFIGURATION"
    ACCOUNT = "ACCOUNT"
    CAPABILITY = "CAPABILITY"
    OWNERSHIP = "OWNERSHIP"
    BUDGET = "BUDGET"
    SESSION = "SESSION"
    SIGNAL_INPUTS = "SIGNAL_INPUTS"
    RECOVERY = "RECOVERY"


class ProofStatus(StrEnum):
    PROVEN = "PROVEN"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class Q62Status(StrEnum):
    READY_READ_ONLY = "READY_READ_ONLY"
    BLOCKED = "BLOCKED"


class Q62Blocker(StrEnum):
    INVALID_EVALUATION_TIME = "INVALID_EVALUATION_TIME"
    MISSING_PROOF = "MISSING_PROOF"
    DUPLICATE_PROOF = "DUPLICATE_PROOF"
    PROOF_NOT_PROVEN = "PROOF_NOT_PROVEN"
    PROOF_NOT_FRESH = "PROOF_NOT_FRESH"
    PROOF_IDENTITY_MISMATCH = "PROOF_IDENTITY_MISMATCH"
    CAPABILITY_UNPROVEN = "CAPABILITY_UNPROVEN"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    OWNERSHIP_UNPROVEN = "OWNERSHIP_UNPROVEN"
    BUDGET_UNPROVEN = "BUDGET_UNPROVEN"
    SESSION_UNPROVEN = "SESSION_UNPROVEN"
    SIGNAL_INPUTS_UNPROVEN = "SIGNAL_INPUTS_UNPROVEN"
    RECOVERY_UNPROVEN = "RECOVERY_UNPROVEN"


@dataclass(frozen=True, slots=True)
class ReadinessIdentity:
    """Exact source/config/account/session tuple shared by every Q62 proof."""

    source_head: str
    source_tree: str
    config_digest: str
    account_fingerprint: str
    target_session: str

    def __post_init__(self) -> None:
        if (
            type(self.source_head) is not str
            or _SHA1.fullmatch(self.source_head) is None
        ):
            raise ValueError("exact source HEAD required")
        if (
            type(self.source_tree) is not str
            or _SHA1.fullmatch(self.source_tree) is None
        ):
            raise ValueError("exact source tree required")
        for value in (self.config_digest, self.account_fingerprint):
            if type(value) is not str or _SHA256.fullmatch(value) is None:
                raise ValueError("exact configuration and account digests required")
        if type(self.target_session) is not str:
            raise TypeError("target session must be text")
        try:
            parsed = date.fromisoformat(self.target_session)
        except ValueError as error:
            raise ValueError("target session must be an ISO date") from error
        if parsed.isoformat() != self.target_session:
            raise ValueError("target session must use canonical ISO date form")


@dataclass(frozen=True, slots=True)
class FreshProof:
    """A source-owned, expiring evidence reference bound to one exact identity.

    This type validates the reference envelope only. It does not authenticate
    caller-supplied evidence or turn a source publication into effect authority.
    """

    kind: ProofKind
    status: ProofStatus
    evidence_sha256: str | None
    observed_at: datetime
    valid_until: datetime
    identity: ReadinessIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProofKind) or not isinstance(
            self.status, ProofStatus
        ):
            raise TypeError("proof kind and status must be typed")
        if type(self.identity) is not ReadinessIdentity:
            raise TypeError("proof identity must be ReadinessIdentity")
        if self.evidence_sha256 is not None and (
            type(self.evidence_sha256) is not str
            or _SHA256.fullmatch(self.evidence_sha256) is None
        ):
            raise ValueError("proof evidence digest must be lowercase SHA-256")
        if self.status is ProofStatus.PROVEN and self.evidence_sha256 is None:
            raise ValueError("proven evidence requires a digest")
        for value in (self.observed_at, self.valid_until):
            if (
                type(value) is not datetime
                or value.tzinfo is None
                or value.utcoffset() != timedelta(0)
            ):
                raise ValueError("proof timestamps must be timezone-aware UTC")
        if self.valid_until < self.observed_at:
            raise ValueError("proof validity cannot end before observation")


def is_current_utc(value: datetime, *, as_of: datetime) -> bool:
    """Check an explicit UTC observation window without consulting a clock."""

    return (
        type(value) is datetime
        and type(as_of) is datetime
        and value.tzinfo is not None
        and as_of.tzinfo is not None
        and value.utcoffset() == timedelta(0)
        and as_of.utcoffset() == timedelta(0)
        and value <= as_of
    )
