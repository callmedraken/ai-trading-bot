"""Additive 146-B custody evidence and OPEN admission; no filesystem effects.

The custody-admission registry is intentionally empty. Published sessions are
independently accepted source-owned non-price authority. Parsing a report/admission
establishes consistency only. Independent review must add exact accepted entries
before any real acquired OPEN package can be admitted.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from datetime import date
from hashlib import sha256
from uuid import UUID
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar
from trading_bot.experiments.historical_research_dataset import (
    HISTORICAL_RESEARCH_FULL_END,
    HISTORICAL_RESEARCH_FULL_START,
    HistoricalResearchDatasetError,
    HistoricalResearchDatasetSnapshot,
    HistoricalResearchDatasetVerification,
    HistoricalResearchPartitionManifest,
    HistoricalResearchPartitionMaterial,
    HistoricalResearchPartitionRole,
    _complete_historical_research_dataset_verification,
    _membership,
    _verify_historical_research_partition_physical,
    parse_historical_research_csv,
)
from trading_bot.experiments.research_strategy_backtest import (
    historical_data_fingerprint,
)
from trading_bot.market_data.models import HistoricalDataResult

CUSTODY_EVIDENCE_SCHEMA = "historical-research-custody-evidence/v1"
CUSTODY_ADMISSION_SCHEMA = "historical-research-custody-admission/v1"
ACQUISITION_CHECKPOINT = "arch146-b2-historical-research-acquisition-custody"
OPEN_ROOT = r"F:\AI\ai-trading-bot\data\research\arch146-v1"
CUSTODY_ROOT = r"F:\AI\research-holdout\arch146-v1"
CUSTODY_SDDL = "O:BAG:BAD:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)"
_DIGEST = re.compile(r"[0-9a-f]{64}")
_GIT = re.compile(r"[0-9a-f]{40}")


class HistoricalResearchCustodyError(HistoricalResearchDatasetError):
    """Closed non-price custody failure; vendor bodies are never diagnostics."""


def frozen_request_descriptors() -> list[dict]:
    """Public immutable semantics of both full-range request families."""
    from trading_bot.experiments.historical_research_acquisition import (
        AcquisitionStream,
        HistoricalResearchRequest,
    )

    return [
        HistoricalResearchRequest(stream).descriptor for stream in AcquisitionStream
    ]


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise HistoricalResearchCustodyError("duplicate JSON field")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise HistoricalResearchCustodyError("nonfinite JSON constant")


def parse_custody_json(value: bytes) -> dict:
    """Strict bounded object parsing, with no raw-body exception chaining."""
    try:
        if type(value) is not bytes or not 0 < len(value) <= 4 * 1024 * 1024:
            raise ValueError
        result = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
        if type(result) is not dict:
            raise ValueError
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise HistoricalResearchCustodyError("invalid JSON object") from None


def _digest(value: str) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise HistoricalResearchCustodyError("SHA256 required")


def _git(value: str) -> None:
    if type(value) is not str or _GIT.fullmatch(value) is None:
        raise HistoricalResearchCustodyError("exact Git identity required")


def _uuid(value: str) -> None:
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError):
        raise HistoricalResearchCustodyError("canonical UUID required") from None


def _text(value: str) -> None:
    if (
        type(value) is not str
        or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}", value) is None
    ):
        raise HistoricalResearchCustodyError("bounded identity text required")


def historical_research_normalized_csv(bars: tuple[Bar, ...]) -> bytes:
    """Canonical CSV rendering without ambient Decimal arithmetic or rounding."""
    rows = ["timestamp,symbol,open,high,low,close,volume\n"]
    for bar in bars:
        prices = []
        for value in (bar.open, bar.high, bar.low, bar.close):
            if not value.is_finite() or value <= 0:
                raise HistoricalResearchCustodyError("invalid price")
            rendered = format(value, "f")
            prices.append(
                rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
            )
        stamp = bar.timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")
        rows.append(
            ",".join((stamp, bar.symbol.value, *prices, str(bar.volume))) + "\n"
        )
    return "".join(rows).encode("utf-8")


@dataclass(frozen=True, slots=True)
class HistoricalSessionAuthority:
    """Supplied session dates; external authority exists only by source admission."""

    identity: str
    sessions: tuple[date, ...]
    source_sha256: str

    def __post_init__(self) -> None:
        _text(self.identity)
        _digest(self.source_sha256)
        if (
            type(self.sessions) is not tuple
            or not self.sessions
            or any(type(item) is not date for item in self.sessions)
            or tuple(sorted(set(self.sessions))) != self.sessions
            or any(
                not HISTORICAL_RESEARCH_FULL_START.date()
                <= item
                < HISTORICAL_RESEARCH_FULL_END.date()
                for item in self.sessions
            )
        ):
            raise HistoricalResearchCustodyError("invalid historical session authority")

    @property
    def digest(self) -> str:
        return sha256(
            canonical_json_bytes(
                {
                    "schema": "historical-research-session-authority/v1",
                    "identity": self.identity,
                    "source_sha256": self.source_sha256,
                    "calendar": "XNYS",
                    "timezone": "America/New_York",
                    "start": "2016-01-01",
                    "end": "2026-10-24",
                    "sessions": [item.isoformat() for item in self.sessions],
                }
            )
        ).hexdigest()

    def verify(self, data: HistoricalDataResult) -> None:
        actual = tuple(
            bar.timestamp.astimezone(ZoneInfo("America/New_York")).date()
            for bar in data.bars
        )
        expected = tuple(
            item
            for item in self.sessions
            if data.request.start.date() <= item < data.request.end.date()
        )
        if actual != expected:
            raise HistoricalResearchCustodyError(
                "historical session authority disagreement"
            )


@dataclass(frozen=True, slots=True)
class HistoricalResearchCustodyEvidence:
    source_head: str
    source_tree: str
    attempt_id: str
    calendar_identity: str
    calendar_sha256: str
    bars_page_sha256: tuple[str, ...]
    corporate_page_sha256: tuple[str, ...]
    snapshot: HistoricalResearchDatasetSnapshot
    open_manifest: HistoricalResearchPartitionManifest
    holdout_manifest: HistoricalResearchPartitionManifest
    checkpoint: str = ACQUISITION_CHECKPOINT

    def __post_init__(self) -> None:
        _git(self.source_head)
        _git(self.source_tree)
        _uuid(self.attempt_id)
        _text(self.calendar_identity)
        _digest(self.calendar_sha256)
        if self.checkpoint != ACQUISITION_CHECKPOINT:
            raise HistoricalResearchCustodyError("wrong acquisition checkpoint")
        for pages in (self.bars_page_sha256, self.corporate_page_sha256):
            if type(pages) is not tuple or not 0 < len(pages) <= 1000:
                raise HistoricalResearchCustodyError(
                    "bounded ordered page vector required"
                )
            for digest in pages:
                _digest(digest)
            if len(set(pages)) != len(pages):
                raise HistoricalResearchCustodyError("duplicate page digest")
        # Public constructors/parsers revalidate all frozen 146-A semantics.
        snapshot = HistoricalResearchDatasetSnapshot.from_json(self.snapshot.to_json())
        opened = HistoricalResearchPartitionManifest.from_json(
            self.open_manifest.to_json()
        )
        held = HistoricalResearchPartitionManifest.from_json(
            self.holdout_manifest.to_json()
        )
        if (
            opened.role is not HistoricalResearchPartitionRole.OPEN
            or held.role is not HistoricalResearchPartitionRole.FINAL_HOLDOUT
            or (opened.manifest_id, held.manifest_id)
            != (snapshot.open_manifest_id, snapshot.holdout_manifest_id)
            or opened.raw_vendor_page_sha256 != self.bars_page_sha256
            or held.raw_vendor_page_sha256 != self.bars_page_sha256
            or opened.corporate_action_sha256 != held.corporate_action_sha256
            or (
                snapshot.open_corporate_action_sha256,
                snapshot.holdout_corporate_action_sha256,
            )
            != (opened.corporate_action_sha256, held.corporate_action_sha256)
        ):
            raise HistoricalResearchCustodyError(
                "custody manifest/snapshot membership mismatch"
            )
        for name in (
            "symbol",
            "calendar",
            "timeframe",
            "adjustment",
            "provider",
            "feed",
            "currency",
            "asof",
            "normalization_schema",
            "normalization_version",
            "price_basis",
        ):
            if (
                not getattr(snapshot, name)
                == getattr(opened, name)
                == getattr(held, name)
            ):
                raise HistoricalResearchCustodyError("custody semantics mismatch")

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(
            {
                "schema": CUSTODY_EVIDENCE_SCHEMA,
                "source_head": self.source_head,
                "source_tree": self.source_tree,
                "attempt_id": self.attempt_id,
                "checkpoint": self.checkpoint,
                "calendar_identity": self.calendar_identity,
                "calendar_sha256": self.calendar_sha256,
                "requests": frozen_request_descriptors(),
                "bars_page_count": len(self.bars_page_sha256),
                "corporate_page_count": len(self.corporate_page_sha256),
                "bars_page_sha256": self.bars_page_sha256,
                "corporate_page_sha256": self.corporate_page_sha256,
                "snapshot": json.loads(self.snapshot.to_json()),
                "open_manifest": json.loads(self.open_manifest.to_json()),
                "holdout_manifest": json.loads(self.holdout_manifest.to_json()),
                "custody_root": CUSTODY_ROOT,
                "open_root": OPEN_ROOT,
                "acl": CUSTODY_SDDL,
                "state": "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION",
                "repository_calendar": "PASS",
                "historical_calendar": "PASS",
                "production_effects": 0,
                "paper_effects": 0,
                "broker_effects": 0,
                "live_effects": 0,
            }
        )

    @classmethod
    def from_bytes(cls, value: bytes) -> HistoricalResearchCustodyEvidence:
        try:
            raw = parse_custody_json(value)
            result = cls(
                source_head=raw["source_head"],
                source_tree=raw["source_tree"],
                attempt_id=raw["attempt_id"],
                checkpoint=raw["checkpoint"],
                calendar_identity=raw["calendar_identity"],
                calendar_sha256=raw["calendar_sha256"],
                bars_page_sha256=tuple(raw["bars_page_sha256"]),
                corporate_page_sha256=tuple(raw["corporate_page_sha256"]),
                snapshot=HistoricalResearchDatasetSnapshot.from_json(
                    canonical_json_bytes(raw["snapshot"]).decode()
                ),
                open_manifest=HistoricalResearchPartitionManifest.from_json(
                    canonical_json_bytes(raw["open_manifest"]).decode()
                ),
                holdout_manifest=HistoricalResearchPartitionManifest.from_json(
                    canonical_json_bytes(raw["holdout_manifest"]).decode()
                ),
            )
            if result.to_bytes() != value:
                raise ValueError
            return result
        except (ValueError, TypeError, KeyError, AttributeError):
            raise HistoricalResearchCustodyError(
                "invalid canonical custody evidence"
            ) from None


@dataclass(frozen=True, slots=True)
class HistoricalResearchCustodyAdmission:
    evidence_sha256: str
    source_head: str
    source_tree: str
    checkpoint: str
    attempt_id: str
    snapshot_id: str
    calendar_identity: str
    calendar_sha256: str

    def __post_init__(self) -> None:
        _digest(self.evidence_sha256)
        _git(self.source_head)
        _git(self.source_tree)
        _uuid(self.attempt_id)
        _uuid(self.snapshot_id)
        _text(self.calendar_identity)
        _digest(self.calendar_sha256)
        if self.checkpoint != ACQUISITION_CHECKPOINT:
            raise HistoricalResearchCustodyError("wrong custody admission checkpoint")

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(
            {
                "schema": CUSTODY_ADMISSION_SCHEMA,
                **{
                    name: getattr(self, name)
                    for name in (item.name for item in fields(self))
                },
            }
        )

    @classmethod
    def from_bytes(cls, value: bytes) -> HistoricalResearchCustodyAdmission:
        try:
            raw = parse_custody_json(value)
            if raw.pop("schema") != CUSTODY_ADMISSION_SCHEMA:
                raise ValueError
            result = cls(**raw)
            if result.to_bytes() != value:
                raise ValueError
            return result
        except (ValueError, TypeError, KeyError):
            raise HistoricalResearchCustodyError(
                "invalid canonical custody admission"
            ) from None


# Only independently reviewed source changes may populate these registries.
# Tests replace them with synthetic fixtures; no runtime registration API exists.
ACCEPTED_CUSTODY_ADMISSIONS: tuple[HistoricalResearchCustodyAdmission, ...] = ()
from trading_bot.experiments.historical_research_sessions import (  # noqa: E402
    published_historical_session_authority,
)

ACCEPTED_HISTORICAL_SESSION_AUTHORITIES: tuple[HistoricalSessionAuthority, ...] = (
    published_historical_session_authority(),
)


def require_accepted_historical_session_authority(
    authority: HistoricalSessionAuthority,
) -> None:
    """Equality and recomputed commitment are required; parsing never registers."""
    if (
        type(authority) is not HistoricalSessionAuthority
        or sum(item == authority for item in ACCEPTED_HISTORICAL_SESSION_AUTHORITIES)
        != 1
        or authority.digest != published_historical_session_authority().digest
    ):
        raise HistoricalResearchCustodyError(
            "historical session authority not accepted"
        )


def verify_historical_research_published_partition(
    material: HistoricalResearchPartitionMaterial,
    authority: HistoricalSessionAuthority,
) -> HistoricalDataResult:
    """146-B physical verification with exactly the independently accepted authority."""
    require_accepted_historical_session_authority(authority)
    data = _verify_historical_research_partition_physical(material)
    authority.verify(data)
    return data


def verify_historical_research_custodian_dataset(
    snapshot: HistoricalResearchDatasetSnapshot,
    open_material: HistoricalResearchPartitionMaterial,
    holdout_material: HistoricalResearchPartitionMaterial,
    authority: HistoricalSessionAuthority,
) -> HistoricalResearchDatasetVerification:
    """Complete OPEN/HOLDOUT bytes plus published coverage and full fingerprint."""
    require_accepted_historical_session_authority(authority)
    if any(
        type(item) is not HistoricalResearchPartitionMaterial
        for item in (open_material, holdout_material)
    ):
        raise HistoricalResearchCustodyError(
            "both physical partition materials required"
        )
    _membership(snapshot, open_material.manifest, holdout_material.manifest)
    opened = verify_historical_research_published_partition(open_material, authority)
    held = verify_historical_research_published_partition(holdout_material, authority)
    return _complete_historical_research_dataset_verification(
        snapshot, open_material, holdout_material, opened, held
    )


def real_acquisition_readiness(authority: HistoricalSessionAuthority) -> str:
    """Pure prerequisite classification, never dispatch or protected authority."""
    if (
        type(authority) is not HistoricalSessionAuthority
        or authority not in ACCEPTED_HISTORICAL_SESSION_AUTHORITIES
    ):
        return "BLOCKED_HISTORICAL_SESSION_AUTHORITY"
    return "HISTORICAL_AUTHORITY_ACCEPTED_OTHER_B2_PREREQUISITES_NOT_EVALUATED"


def verify_historical_research_open_publication(
    normalized_open_bytes: bytes,
    snapshot: HistoricalResearchDatasetSnapshot,
    open_manifest: HistoricalResearchPartitionManifest,
    holdout_commitment: HistoricalResearchPartitionManifest,
    custody_evidence_bytes: bytes,
    custody_admission_bytes: bytes,
) -> HistoricalDataResult:
    """Admit only OPEN CSV plus independently source-pinned non-price evidence.

    No raw pages, sidecar bytes, report paths or caller-selected expected hash
    are accepted. The full logical fingerprint remains a custodian assertion
    whose provenance is established by independent evidence acceptance.
    """
    if (
        type(snapshot) is not HistoricalResearchDatasetSnapshot
        or type(open_manifest) is not HistoricalResearchPartitionManifest
        or type(holdout_commitment) is not HistoricalResearchPartitionManifest
    ):
        raise HistoricalResearchCustodyError("exact public contract types required")
    evidence = HistoricalResearchCustodyEvidence.from_bytes(custody_evidence_bytes)
    admission = HistoricalResearchCustodyAdmission.from_bytes(custody_admission_bytes)
    if admission not in ACCEPTED_CUSTODY_ADMISSIONS:
        raise HistoricalResearchCustodyError(
            "custody admission has not been independently accepted"
        )
    expected = HistoricalResearchCustodyAdmission(
        sha256(custody_evidence_bytes).hexdigest(),
        evidence.source_head,
        evidence.source_tree,
        evidence.checkpoint,
        evidence.attempt_id,
        str(evidence.snapshot.snapshot_id),
        evidence.calendar_identity,
        evidence.calendar_sha256,
    )
    if admission != expected:
        raise HistoricalResearchCustodyError(
            "accepted custody evidence binding mismatch"
        )
    authorities = tuple(
        item
        for item in ACCEPTED_HISTORICAL_SESSION_AUTHORITIES
        if (item.identity, item.digest)
        == (admission.calendar_identity, admission.calendar_sha256)
    )
    if len(authorities) != 1:
        raise HistoricalResearchCustodyError(
            "historical session authority not independently accepted"
        )
    if (snapshot, open_manifest, holdout_commitment) != (
        evidence.snapshot,
        evidence.open_manifest,
        evidence.holdout_manifest,
    ):
        raise HistoricalResearchCustodyError("public package membership mismatch")
    if (
        type(normalized_open_bytes) is not bytes
        or sha256(normalized_open_bytes).hexdigest()
        != open_manifest.normalized_file_sha256
        or len(normalized_open_bytes) != open_manifest.normalized_byte_size
    ):
        raise HistoricalResearchCustodyError("OPEN bytes/digest/size mismatch")
    data = parse_historical_research_csv(
        normalized_open_bytes, HistoricalResearchPartitionRole.OPEN
    )
    if historical_research_normalized_csv(data.bars) != normalized_open_bytes:
        raise HistoricalResearchCustodyError("noncanonical OPEN CSV bytes")
    if (
        len(data.bars),
        data.bars[0].timestamp,
        data.bars[-1].timestamp,
        historical_data_fingerprint(data),
    ) != (
        open_manifest.row_count,
        open_manifest.first_bar_timestamp,
        open_manifest.last_bar_timestamp,
        open_manifest.historical_data_fingerprint,
    ):
        raise HistoricalResearchCustodyError("OPEN physical metadata mismatch")
    require_accepted_historical_session_authority(authorities[0])
    authorities[0].verify(data)
    return data
