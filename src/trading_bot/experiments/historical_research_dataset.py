"""Pure Architecture-146 v1 data contracts over caller-supplied immutable bytes.

Parsing establishes self-consistency only. Partition verification reconciles all
physical material; full verification additionally reconstructs the logical
fingerprint. OPEN-only verification checks commitments without proving or reading
holdout content. No function reads files, acquires data or admits a holdout.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field, fields
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.research_strategy_backtest import (
    historical_data_fingerprint,
)
from trading_bot.experiments.research_strategy_robustness import (
    ResearchRobustnessPartitionRole,
    ResearchStrategyRobustnessQualificationPolicy,
)
from trading_bot.market_calendar.nyse import NYSEMarketCalendar
from trading_bot.market_data.exceptions import HistoricalDataValidationError
from trading_bot.market_data.models import (
    AdjustmentType,
    HistoricalDataRequest,
    HistoricalDataResult,
    Timeframe,
)

HISTORICAL_RESEARCH_PARTITION_MANIFEST_SCHEMA = (
    "historical-research-partition-manifest/v1"
)
HISTORICAL_RESEARCH_DATASET_SNAPSHOT_SCHEMA = "historical-research-dataset-snapshot/v1"
HISTORICAL_RESEARCH_PARTITION_MANIFEST_NAMESPACE = UUID(
    "8fdd2b9e-be93-5aaf-84b2-b9b7a7381edb"
)
HISTORICAL_RESEARCH_DATASET_SNAPSHOT_NAMESPACE = UUID(
    "61a9b6ef-3fe3-564c-8f73-96478e0857a9"
)
HISTORICAL_RESEARCH_PROVIDER = "Alpaca Market Data historical stock bars"
HISTORICAL_RESEARCH_NORMALIZATION_SCHEMA = "historical-research-normalized-csv/v1"
HISTORICAL_RESEARCH_NORMALIZATION_VERSION = "arch146-v1"
HISTORICAL_RESEARCH_FULL_START = datetime(2016, 1, 1, tzinfo=UTC)
HISTORICAL_RESEARCH_DEVELOPMENT_END = datetime(2020, 1, 1, tzinfo=UTC)
HISTORICAL_RESEARCH_HOLDOUT_START = datetime(2024, 1, 1, tzinfo=UTC)
HISTORICAL_RESEARCH_FULL_END = datetime(2026, 10, 24, tzinfo=UTC)

_HEADERS = ("timestamp", "symbol", "open", "high", "low", "close", "volume")
_NEW_YORK = ZoneInfo("America/New_York")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_VOLUME = re.compile(r"(0|[1-9][0-9]*)")
_COMMON_FIELDS = (
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
)
_FIXED = {
    "symbol": "SPY",
    "calendar": "XNYS",
    "timeframe": "1D",
    "adjustment": "RAW",
    "provider": HISTORICAL_RESEARCH_PROVIDER,
    "feed": "sip",
    "currency": "USD",
    "asof": "-",
    "normalization_schema": HISTORICAL_RESEARCH_NORMALIZATION_SCHEMA,
    "normalization_version": HISTORICAL_RESEARCH_NORMALIZATION_VERSION,
    "price_basis": "PRICE_RETURN",
}
_TIMESTAMP_FIELDS = frozenset(
    {
        "start",
        "end",
        "first_bar_timestamp",
        "last_bar_timestamp",
        "development_start",
        "development_end",
        "walk_forward_start",
        "walk_forward_end",
        "final_holdout_start",
        "final_holdout_end",
    }
)
_UUID_FIELDS = frozenset(
    {
        "historical_data_fingerprint",
        "open_manifest_id",
        "holdout_manifest_id",
        "full_historical_data_fingerprint",
    }
)


class HistoricalResearchDatasetError(ValueError):
    """Malformed, noncanonical or externally unreconciled research material."""


class HistoricalResearchPartitionRole(StrEnum):
    OPEN = "OPEN"
    FINAL_HOLDOUT = "FINAL_HOLDOUT"


class HistoricalResearchSessionCoverageError(HistoricalResearchDatasetError):
    """Explicit missing/unexpected session dates; never a zero-bar substitution."""

    def __init__(self, missing: tuple[date, ...], unexpected: tuple[date, ...]) -> None:
        self.missing_sessions = missing
        self.unexpected_sessions = unexpected
        super().__init__(
            f"XNYS coverage mismatch: missing={missing}, unexpected={unexpected}"
        )


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _timestamp(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalResearchDatasetError("aware datetime required")
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _parse_timestamp(value: object) -> datetime:
    if type(value) is not str:
        raise HistoricalResearchDatasetError("canonical UTC timestamp text required")
    try:
        parsed = datetime.fromisoformat(value)
        if _timestamp(parsed) != value:
            raise ValueError
        return parsed
    except ValueError:
        raise HistoricalResearchDatasetError("noncanonical UTC timestamp") from None


def _uuid(value: object) -> UUID:
    if type(value) is not UUID or value.version != 5:
        raise HistoricalResearchDatasetError("UUID5 required")
    return value


def _parse_uuid(value: object) -> UUID:
    if type(value) is not str:
        raise HistoricalResearchDatasetError("canonical UUID5 text required")
    try:
        parsed = UUID(value)
        if str(_uuid(parsed)) != value:
            raise ValueError
        return parsed
    except ValueError:
        raise HistoricalResearchDatasetError("noncanonical UUID5") from None


def _digest(value: object) -> None:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise HistoricalResearchDatasetError("lowercase SHA256 required")


def _positive_int(value: object) -> None:
    if type(value) is not int or value < 1:
        raise HistoricalResearchDatasetError("positive exact integer required")


def _semantic(value: object) -> dict[str, object]:
    """Explicit typed field projection, excluding derived IDs and artifact bytes."""
    result = {}
    for item in fields(value):
        if item.name in {"manifest_id", "snapshot_id"}:
            continue
        actual = getattr(value, item.name)
        if item.name in _TIMESTAMP_FIELDS:
            actual = _timestamp(actual)
        elif type(actual) is UUID:
            actual = str(actual)
        elif type(actual) is HistoricalResearchPartitionRole:
            actual = actual.value
        elif type(actual) is tuple:
            actual = list(actual)
        result[item.name] = actual
    return result


def _validate_common(value: object) -> None:
    for name, expected in _FIXED.items():
        actual = getattr(value, name)
        if type(actual) is not str or actual != expected:
            raise HistoricalResearchDatasetError(f"v1 {name} must equal {expected}")


def _bounds(role: HistoricalResearchPartitionRole) -> tuple[datetime, datetime]:
    if type(role) is not HistoricalResearchPartitionRole:
        raise HistoricalResearchDatasetError("exact partition role required")
    if role is HistoricalResearchPartitionRole.OPEN:
        return HISTORICAL_RESEARCH_FULL_START, HISTORICAL_RESEARCH_HOLDOUT_START
    return HISTORICAL_RESEARCH_HOLDOUT_START, HISTORICAL_RESEARCH_FULL_END


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise HistoricalResearchDatasetError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise HistoricalResearchDatasetError("nonfinite JSON constant")


def _from_json(cls, value: str, id_name: str):
    if type(value) is not str:
        raise HistoricalResearchDatasetError("canonical JSON text required")
    try:
        raw = json.loads(
            value, object_pairs_hook=_unique, parse_constant=_reject_constant
        )
        if type(raw) is not dict or set(raw) != {item.name for item in fields(cls)}:
            raise HistoricalResearchDatasetError("exact JSON field set required")
        values = dict(raw)
        identity = _parse_uuid(values.pop(id_name))
        schema = values.pop("schema")
        for name in values:
            if name in _TIMESTAMP_FIELDS:
                values[name] = _parse_timestamp(values[name])
            elif name in _UUID_FIELDS:
                values[name] = _parse_uuid(values[name])
            elif name == "role":
                values[name] = HistoricalResearchPartitionRole(values[name])
            elif name == "raw_vendor_page_sha256":
                if type(values[name]) is not list:
                    raise HistoricalResearchDatasetError("page digest array required")
                values[name] = tuple(values[name])
        result = cls(**values)
        if schema != result.schema or identity != getattr(result, id_name):
            raise HistoricalResearchDatasetError("schema or identity mismatch")
        if result.to_json() != value:
            raise HistoricalResearchDatasetError("noncanonical JSON")
        return result
    except (TypeError, ValueError, ArithmeticError, KeyError, UnicodeError) as error:
        raise HistoricalResearchDatasetError(f"invalid {cls.__name__} JSON") from error


def _validated(value, cls):
    if type(value) is not cls:
        raise HistoricalResearchDatasetError(f"exact {cls.__name__} required")
    rebuilt = cls(
        **{item.name: getattr(value, item.name) for item in fields(cls) if item.init}
    )
    if rebuilt != value:
        raise HistoricalResearchDatasetError("inconsistent immutable contract")
    return rebuilt


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoricalResearchPartitionManifest:
    role: HistoricalResearchPartitionRole
    start: datetime
    end: datetime
    normalized_file_sha256: str
    normalized_byte_size: int
    row_count: int
    first_bar_timestamp: datetime
    last_bar_timestamp: datetime
    historical_data_fingerprint: UUID
    raw_vendor_page_sha256: tuple[str, ...]
    corporate_action_sha256: str
    symbol: str = "SPY"
    calendar: str = "XNYS"
    timeframe: str = "1D"
    adjustment: str = "RAW"
    provider: str = HISTORICAL_RESEARCH_PROVIDER
    feed: str = "sip"
    currency: str = "USD"
    asof: str = "-"
    normalization_schema: str = HISTORICAL_RESEARCH_NORMALIZATION_SCHEMA
    normalization_version: str = HISTORICAL_RESEARCH_NORMALIZATION_VERSION
    price_basis: str = "PRICE_RETURN"
    schema: str = field(
        default=HISTORICAL_RESEARCH_PARTITION_MANIFEST_SCHEMA, init=False
    )
    manifest_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate_common(self)
        for name in ("start", "end", "first_bar_timestamp", "last_bar_timestamp"):
            object.__setattr__(
                self, name, _parse_timestamp(_timestamp(getattr(self, name)))
            )
        if (self.start, self.end) != _bounds(self.role):
            raise HistoricalResearchDatasetError(
                "partition must use frozen role bounds"
            )
        if (
            not self.start
            <= self.first_bar_timestamp
            <= self.last_bar_timestamp
            < self.end
        ):
            raise HistoricalResearchDatasetError(
                "bar endpoints outside physical partition"
            )
        _positive_int(self.normalized_byte_size)
        _positive_int(self.row_count)
        if (self.row_count == 1) != (
            self.first_bar_timestamp == self.last_bar_timestamp
        ):
            raise HistoricalResearchDatasetError("row count and bar endpoints disagree")
        for digest in (self.normalized_file_sha256, self.corporate_action_sha256):
            _digest(digest)
        if (
            type(self.raw_vendor_page_sha256) is not tuple
            or not self.raw_vendor_page_sha256
        ):
            raise HistoricalResearchDatasetError("ordered raw page digests required")
        for digest in self.raw_vendor_page_sha256:
            _digest(digest)
        _uuid(self.historical_data_fingerprint)
        object.__setattr__(
            self,
            "manifest_id",
            uuid5(
                HISTORICAL_RESEARCH_PARTITION_MANIFEST_NAMESPACE,
                _json(
                    [
                        "historical-research-partition-manifest-identity/v1",
                        _semantic(self),
                    ]
                ),
            ),
        )

    def to_json(self) -> str:
        _validated(self, HistoricalResearchPartitionManifest)
        return _json({**_semantic(self), "manifest_id": str(self.manifest_id)})

    @classmethod
    def from_json(cls, value: str) -> HistoricalResearchPartitionManifest:
        return _from_json(cls, value, "manifest_id")


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoricalResearchDatasetSnapshot:
    open_manifest_id: UUID
    holdout_manifest_id: UUID
    full_historical_data_fingerprint: UUID
    open_corporate_action_sha256: str
    holdout_corporate_action_sha256: str
    start: datetime = HISTORICAL_RESEARCH_FULL_START
    end: datetime = HISTORICAL_RESEARCH_FULL_END
    development_start: datetime = HISTORICAL_RESEARCH_FULL_START
    development_end: datetime = HISTORICAL_RESEARCH_DEVELOPMENT_END
    walk_forward_start: datetime = HISTORICAL_RESEARCH_DEVELOPMENT_END
    walk_forward_end: datetime = HISTORICAL_RESEARCH_HOLDOUT_START
    final_holdout_start: datetime = HISTORICAL_RESEARCH_HOLDOUT_START
    final_holdout_end: datetime = HISTORICAL_RESEARCH_FULL_END
    symbol: str = "SPY"
    calendar: str = "XNYS"
    timeframe: str = "1D"
    adjustment: str = "RAW"
    provider: str = HISTORICAL_RESEARCH_PROVIDER
    feed: str = "sip"
    currency: str = "USD"
    asof: str = "-"
    normalization_schema: str = HISTORICAL_RESEARCH_NORMALIZATION_SCHEMA
    normalization_version: str = HISTORICAL_RESEARCH_NORMALIZATION_VERSION
    price_basis: str = "PRICE_RETURN"
    schema: str = field(default=HISTORICAL_RESEARCH_DATASET_SNAPSHOT_SCHEMA, init=False)
    snapshot_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        _validate_common(self)
        expected = (
            HISTORICAL_RESEARCH_FULL_START,
            HISTORICAL_RESEARCH_FULL_END,
            HISTORICAL_RESEARCH_FULL_START,
            HISTORICAL_RESEARCH_DEVELOPMENT_END,
            HISTORICAL_RESEARCH_DEVELOPMENT_END,
            HISTORICAL_RESEARCH_HOLDOUT_START,
            HISTORICAL_RESEARCH_HOLDOUT_START,
            HISTORICAL_RESEARCH_FULL_END,
        )
        names = (
            "start",
            "end",
            "development_start",
            "development_end",
            "walk_forward_start",
            "walk_forward_end",
            "final_holdout_start",
            "final_holdout_end",
        )
        for name, bound in zip(names, expected, strict=True):
            canonical = _parse_timestamp(_timestamp(getattr(self, name)))
            if canonical != bound:
                raise HistoricalResearchDatasetError(
                    "snapshot partition calendar is frozen"
                )
            object.__setattr__(self, name, canonical)
        for identity in (
            self.open_manifest_id,
            self.holdout_manifest_id,
            self.full_historical_data_fingerprint,
        ):
            _uuid(identity)
        if self.open_manifest_id == self.holdout_manifest_id:
            raise HistoricalResearchDatasetError("distinct physical manifests required")
        _digest(self.open_corporate_action_sha256)
        _digest(self.holdout_corporate_action_sha256)
        object.__setattr__(
            self,
            "snapshot_id",
            uuid5(
                HISTORICAL_RESEARCH_DATASET_SNAPSHOT_NAMESPACE,
                _json(
                    [
                        "historical-research-dataset-snapshot-identity/v1",
                        _semantic(self),
                    ]
                ),
            ),
        )

    def to_json(self) -> str:
        _validated(self, HistoricalResearchDatasetSnapshot)
        return _json({**_semantic(self), "snapshot_id": str(self.snapshot_id)})

    @classmethod
    def from_json(cls, value: str) -> HistoricalResearchDatasetSnapshot:
        return _from_json(cls, value, "snapshot_id")


@dataclass(frozen=True, slots=True)
class HistoricalResearchPartitionMaterial:
    """Untrusted supplied bytes, not proof; contains no path or acquisition clock."""

    manifest: HistoricalResearchPartitionManifest
    normalized_bytes: bytes
    raw_vendor_pages: tuple[bytes, ...]
    corporate_action_sidecar: bytes


def _bytes(value: object) -> bytes:
    if type(value) is not bytes or not value:
        raise HistoricalResearchDatasetError("nonempty immutable bytes required")
    return value


def _decimal(text: str) -> Decimal:
    try:
        value = Decimal(text)
        if not value.is_finite() or value <= 0:
            raise ValueError
        rendered = format(value, "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        if rendered != text:
            raise ValueError
        return value
    except (ArithmeticError, ValueError):
        raise HistoricalResearchDatasetError(
            "positive canonical Decimal text required"
        ) from None


def parse_historical_research_csv(
    normalized_bytes: bytes,
    role: HistoricalResearchPartitionRole,
) -> HistoricalDataResult:
    """Validate the ENTIRE supplied partition before any downstream slicing.

    v1 normalizes UTC timestamps to fixed microsecond Z text, Decimal values
    to plain minimal text, and volume to unsigned minimal base-10 integer text.
    It uses the existing public Bar/request/result invariants without invoking a
    filesystem provider or sorting away invalid input ordering.
    """
    start, end = _bounds(role)
    try:
        reader = csv.reader(
            io.StringIO(_bytes(normalized_bytes).decode("utf-8"), newline=""),
            strict=True,
        )
        if next(reader, None) != list(_HEADERS):
            raise HistoricalResearchDatasetError(
                "exact normalized CSV headers/order required"
            )
        bars = []
        for row in reader:
            if (
                len(row) != len(_HEADERS)
                or row[1] != "SPY"
                or not _VOLUME.fullmatch(row[6])
            ):
                raise HistoricalResearchDatasetError("invalid CSV row/symbol/volume")
            bars.append(
                Bar(
                    Symbol("SPY"),
                    _parse_timestamp(row[0]),
                    *(_decimal(value) for value in row[2:6]),
                    int(row[6]),
                )
            )
        if not bars:
            raise HistoricalResearchDatasetError("partition must contain bars")
        return HistoricalDataResult(
            HistoricalDataRequest(
                Symbol("SPY"), start, end, Timeframe.DAY_1, AdjustmentType.RAW
            ),
            tuple(bars),
            HISTORICAL_RESEARCH_PROVIDER,
        )
    except (
        ValueError,
        TypeError,
        UnicodeError,
        csv.Error,
        HistoricalDataValidationError,
    ) as error:
        raise HistoricalResearchDatasetError(
            "invalid normalized physical partition"
        ) from error


def validate_historical_research_session_coverage(data: HistoricalDataResult) -> None:
    """Require one daily bar per repository NYSE calendar session.

    Convert frozen UTC boundary dates to exchange-local midnight explicitly:
    calendar.sessions_between itself otherwise converts UTC midnight to the
    previous New York date. Preserve vendor bar instants and compare their
    exchange-local session dates, including across DST.
    """
    if type(data) is not HistoricalDataResult:
        raise HistoricalResearchDatasetError("exact historical result required")
    request = data.request
    calendar = NYSEMarketCalendar()
    start = datetime.combine(request.start.date(), time.min, _NEW_YORK)
    end = datetime.combine(request.end.date(), time.min, _NEW_YORK)
    expected = tuple(
        item.session_date for item in calendar.sessions_between(start, end).sessions
    )
    actual = tuple(bar.timestamp.astimezone(_NEW_YORK).date() for bar in data.bars)
    if len(set(actual)) != len(actual):
        raise HistoricalResearchDatasetError("multiple daily bars for one XNYS session")
    actual_dates, expected_dates = set(actual), set(expected)
    missing = tuple(item for item in expected if item not in actual_dates)
    unexpected = tuple(item for item in actual if item not in expected_dates)
    if missing or unexpected:
        raise HistoricalResearchSessionCoverageError(missing, unexpected)


def verify_historical_research_partition(
    material: HistoricalResearchPartitionMaterial,
    historical_result: HistoricalDataResult | None = None,
) -> HistoricalDataResult:
    """Reconcile supplied normalized/raw/sidecar bytes and optional public result.

    Raw pages and sidecar are opaque integrity provenance here. Provider-page
    parsing, pagination completeness and corporate-action admissibility are
    future acquisition responsibilities; matching digests do not prove them.
    """
    if type(material) is not HistoricalResearchPartitionMaterial:
        raise HistoricalResearchDatasetError(
            "exact supplied partition material required"
        )
    manifest = _validated(material.manifest, HistoricalResearchPartitionManifest)
    normalized = _bytes(material.normalized_bytes)
    if (
        sha256(normalized).hexdigest() != manifest.normalized_file_sha256
        or len(normalized) != manifest.normalized_byte_size
    ):
        raise HistoricalResearchDatasetError("normalized bytes/digest/size mismatch")
    pages = material.raw_vendor_pages
    if (
        type(pages) is not tuple
        or tuple(sha256(_bytes(page)).hexdigest() for page in pages)
        != manifest.raw_vendor_page_sha256
    ):
        raise HistoricalResearchDatasetError("raw page digest/order mismatch")
    if (
        sha256(_bytes(material.corporate_action_sidecar)).hexdigest()
        != manifest.corporate_action_sha256
    ):
        raise HistoricalResearchDatasetError("corporate-action sidecar digest mismatch")
    data = parse_historical_research_csv(normalized, manifest.role)
    if (
        len(data.bars),
        data.bars[0].timestamp,
        data.bars[-1].timestamp,
        historical_data_fingerprint(data),
    ) != (
        manifest.row_count,
        manifest.first_bar_timestamp,
        manifest.last_bar_timestamp,
        manifest.historical_data_fingerprint,
    ):
        raise HistoricalResearchDatasetError("physical historical material mismatch")
    if historical_result is not None:
        if (
            type(historical_result) is not HistoricalDataResult
            or historical_result != data
        ):
            raise HistoricalResearchDatasetError("supplied historical result mismatch")
    validate_historical_research_session_coverage(data)
    return data


def _membership(
    snapshot: HistoricalResearchDatasetSnapshot,
    open_manifest: HistoricalResearchPartitionManifest,
    holdout_manifest: HistoricalResearchPartitionManifest,
) -> None:
    _validated(snapshot, HistoricalResearchDatasetSnapshot)
    for manifest, role, identity, digest in (
        (
            open_manifest,
            HistoricalResearchPartitionRole.OPEN,
            snapshot.open_manifest_id,
            snapshot.open_corporate_action_sha256,
        ),
        (
            holdout_manifest,
            HistoricalResearchPartitionRole.FINAL_HOLDOUT,
            snapshot.holdout_manifest_id,
            snapshot.holdout_corporate_action_sha256,
        ),
    ):
        _validated(manifest, HistoricalResearchPartitionManifest)
        if (
            manifest.role is not role
            or manifest.manifest_id != identity
            or manifest.corporate_action_sha256 != digest
        ):
            raise HistoricalResearchDatasetError(
                "snapshot physical manifest membership mismatch"
            )
        if any(
            getattr(snapshot, name) != getattr(manifest, name)
            for name in _COMMON_FIELDS
        ):
            raise HistoricalResearchDatasetError(
                "snapshot/partition semantics mismatch"
            )


def verify_historical_research_open_commitment(
    snapshot: HistoricalResearchDatasetSnapshot,
    open_material: HistoricalResearchPartitionMaterial,
    holdout_commitment: HistoricalResearchPartitionManifest,
) -> HistoricalDataResult:
    """Verify OPEN bytes and two-manifest membership, NEVER full-fingerprint truth.

    The full UUID remains a stored custodian commitment. This function accepts
    no holdout bars/bytes and cannot produce a full-verification receipt.
    """
    if type(open_material) is not HistoricalResearchPartitionMaterial:
        raise HistoricalResearchDatasetError("exact OPEN material required")
    _membership(snapshot, open_material.manifest, holdout_commitment)
    return verify_historical_research_partition(open_material)


_VERIFICATION_KEY = object()


@dataclass(frozen=True, slots=True, init=False)
class HistoricalResearchDatasetVerification:
    """Process-local, non-price verification receipt; not serializable authority.

    Only complete two-partition verification creates a receipt. Arbitrary Python
    code can bypass Python object privacy; this is not a host custody/security
    boundary or persisted substitute for that future boundary.
    """

    snapshot: HistoricalResearchDatasetSnapshot
    open_manifest: HistoricalResearchPartitionManifest
    holdout_manifest: HistoricalResearchPartitionManifest
    _key: object = field(repr=False, compare=False)
    _snapshot_id: UUID = field(repr=False)

    def __init__(self) -> None:
        raise HistoricalResearchDatasetError("complete external verification required")


def verify_historical_research_dataset(
    snapshot: HistoricalResearchDatasetSnapshot,
    open_material: HistoricalResearchPartitionMaterial,
    holdout_material: HistoricalResearchPartitionMaterial,
) -> HistoricalResearchDatasetVerification:
    """Privileged pure boundary: requires COMPLETE exact OPEN + HOLDOUT material.

    Reverify physical bytes, then concatenate only in role/chronological order.
    No path access, holdout admission or eligibility construction occurs.
    """
    if any(
        type(item) is not HistoricalResearchPartitionMaterial
        for item in (open_material, holdout_material)
    ):
        raise HistoricalResearchDatasetError(
            "both physical partition materials required"
        )
    _membership(snapshot, open_material.manifest, holdout_material.manifest)
    opened = verify_historical_research_partition(open_material)
    holdout = verify_historical_research_partition(holdout_material)
    full = HistoricalDataResult(
        HistoricalDataRequest(Symbol("SPY"), snapshot.start, snapshot.end),
        opened.bars + holdout.bars,
        HISTORICAL_RESEARCH_PROVIDER,
    )
    if historical_data_fingerprint(full) != snapshot.full_historical_data_fingerprint:
        raise HistoricalResearchDatasetError(
            "full logical historical fingerprint mismatch"
        )
    receipt = object.__new__(HistoricalResearchDatasetVerification)
    for name, value in (
        ("snapshot", snapshot),
        ("open_manifest", open_material.manifest),
        ("holdout_manifest", holdout_material.manifest),
        ("_key", _VERIFICATION_KEY),
        ("_snapshot_id", snapshot.snapshot_id),
    ):
        object.__setattr__(receipt, name, value)
    return receipt


def verify_historical_research_policy_binding(
    policy: ResearchStrategyRobustnessQualificationPolicy,
    verification: HistoricalResearchDatasetVerification,
) -> None:
    """Bind a policy to a fully verified non-price snapshot receipt.

    Does not construct/alter a 145 artifact, read holdout content, admit/evaluate
    a holdout, or prove strategy evidence was generated from these bytes.
    """
    if (
        type(verification) is not HistoricalResearchDatasetVerification
        or getattr(verification, "_key", None) is not _VERIFICATION_KEY
    ):
        raise HistoricalResearchDatasetError(
            "external full-snapshot verification required"
        )
    _membership(
        verification.snapshot, verification.open_manifest, verification.holdout_manifest
    )
    if verification._snapshot_id != verification.snapshot.snapshot_id:
        raise HistoricalResearchDatasetError("verification receipt snapshot mismatch")
    if type(policy) is not ResearchStrategyRobustnessQualificationPolicy:
        raise HistoricalResearchDatasetError("exact Architecture-145 policy required")
    # Public roundtrip detects tampering without private imports.
    canonical = policy.to_json()
    if ResearchStrategyRobustnessQualificationPolicy.from_json(canonical) != policy:
        raise HistoricalResearchDatasetError("inconsistent policy")
    snapshot = verification.snapshot
    if (
        str(policy.symbol) != snapshot.symbol
        or policy.historical_data_fingerprint
        != snapshot.full_historical_data_fingerprint
    ):
        raise HistoricalResearchDatasetError(
            "policy full logical fingerprint/symbol mismatch"
        )
    for partition, role, start, end in (
        (
            policy.development_partition,
            ResearchRobustnessPartitionRole.DEVELOPMENT,
            snapshot.development_start,
            snapshot.development_end,
        ),
        (
            policy.walk_forward_partition,
            ResearchRobustnessPartitionRole.WALK_FORWARD,
            snapshot.walk_forward_start,
            snapshot.walk_forward_end,
        ),
        (
            policy.final_holdout_partition,
            ResearchRobustnessPartitionRole.FINAL_HOLDOUT,
            snapshot.final_holdout_start,
            snapshot.final_holdout_end,
        ),
    ):
        if (
            partition.role is not role
            or (partition.start, partition.end) != (start, end)
            or partition.historical_data_fingerprint
            != snapshot.full_historical_data_fingerprint
        ):
            raise HistoricalResearchDatasetError(
                "policy frozen partition bounds/lineage mismatch"
            )


__all__ = [
    "HISTORICAL_RESEARCH_DATASET_SNAPSHOT_NAMESPACE",
    "HISTORICAL_RESEARCH_DATASET_SNAPSHOT_SCHEMA",
    "HISTORICAL_RESEARCH_PARTITION_MANIFEST_NAMESPACE",
    "HISTORICAL_RESEARCH_PARTITION_MANIFEST_SCHEMA",
    "HistoricalResearchDatasetError",
    "HistoricalResearchDatasetSnapshot",
    "HistoricalResearchDatasetVerification",
    "HistoricalResearchPartitionManifest",
    "HistoricalResearchPartitionMaterial",
    "HistoricalResearchPartitionRole",
    "HistoricalResearchSessionCoverageError",
    "parse_historical_research_csv",
    "validate_historical_research_session_coverage",
    "verify_historical_research_dataset",
    "verify_historical_research_open_commitment",
    "verify_historical_research_partition",
    "verify_historical_research_policy_binding",
    "HISTORICAL_RESEARCH_PROVIDER",
    "HISTORICAL_RESEARCH_NORMALIZATION_SCHEMA",
    "HISTORICAL_RESEARCH_NORMALIZATION_VERSION",
    "HISTORICAL_RESEARCH_FULL_START",
    "HISTORICAL_RESEARCH_DEVELOPMENT_END",
    "HISTORICAL_RESEARCH_HOLDOUT_START",
    "HISTORICAL_RESEARCH_FULL_END",
]
