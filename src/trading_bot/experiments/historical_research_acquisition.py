"""146-B1 dependency-injected acquisition kernel; no real host dispatcher.

Every effect is a required explicit port. This module provides no credential
store, HTTP client, filesystem or Windows ACL implementation. B2 must separately
admit source, native adapter bindings and historical authority before wiring it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from urllib.parse import urlencode
from uuid import UUID

from trading_bot.domain import Bar, Symbol
from trading_bot.experiments.historical_research_custody import (
    CUSTODY_ROOT,
    CUSTODY_SDDL,
    OPEN_ROOT,
    HistoricalResearchCustodyError,
    HistoricalResearchCustodyEvidence,
    HistoricalSessionAuthority,
    historical_research_normalized_csv,
    parse_custody_json,
    require_accepted_historical_session_authority,
    verify_historical_research_custodian_dataset,
)
from trading_bot.experiments.historical_research_dataset import (
    HISTORICAL_RESEARCH_FULL_END,
    HISTORICAL_RESEARCH_FULL_START,
    HISTORICAL_RESEARCH_HOLDOUT_START,
    HISTORICAL_RESEARCH_PROVIDER,
    HistoricalResearchDatasetSnapshot,
    HistoricalResearchPartitionManifest,
    HistoricalResearchPartitionMaterial,
    HistoricalResearchPartitionRole,
    parse_historical_research_csv,
)
from trading_bot.experiments.research_strategy_backtest import (
    historical_data_fingerprint,
)
from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult

MAX_PAGES = 1000
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_STREAM_BYTES = 64 * 1024 * 1024


class AcquisitionStream(StrEnum):
    BARS = "bars"
    CORPORATE_ACTIONS = "corporate-actions"


@dataclass(frozen=True, slots=True)
class HistoricalResearchRequest:
    stream: AcquisitionStream
    page_token: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if type(self.stream) is not AcquisitionStream:
            raise HistoricalResearchCustodyError("unsupported acquisition stream")
        if self.page_token is not None and (
            type(self.page_token) is not str
            or re.fullmatch(r"[!-~]{1,1024}", self.page_token) is None
        ):
            raise HistoricalResearchCustodyError("invalid pagination token")

    @property
    def method(self) -> str:
        return "GET"

    @property
    def host(self) -> str:
        return "data.alpaca.markets"

    @property
    def descriptor(self) -> dict:
        """Frozen nonsecret request semantics; tokens are never evidence."""
        if self.stream is AcquisitionStream.BARS:
            path = "/v2/stocks/SPY/bars"
            parameters = {
                "timeframe": "1Day",
                "start": "2016-01-01T00:00:00Z",
                "end": "2026-10-24T00:00:00Z",
                "adjustment": "raw",
                "feed": "sip",
                "currency": "USD",
                "sort": "asc",
                "limit": "10000",
            }
        else:
            path = "/v1/corporate-actions"
            parameters = {
                "symbols": "SPY",
                "region": "us",
                "start": "2016-01-01",
                "end": "2026-10-24",
                "data_quality": "complete",
                "sort": "asc",
                "limit": "1000",
            }
        return {
            "method": self.method,
            "host": self.host,
            "path": path,
            "parameters": parameters,
        }

    @property
    def target(self) -> str:
        descriptor = self.descriptor
        parameters = descriptor["parameters"]
        if self.page_token is not None:
            parameters["page_token"] = self.page_token
        return descriptor["path"] + "?" + urlencode(parameters)


@dataclass(frozen=True, slots=True, repr=False)
class AcquisitionCredentials:
    api_key_id: str
    api_secret_key: str

    def __post_init__(self) -> None:
        if any(
            type(item) is not str or re.fullmatch(r"[!-~]{1,256}", item) is None
            for item in (self.api_key_id, self.api_secret_key)
        ):
            raise HistoricalResearchCustodyError("invalid injected credentials")

    def __repr__(self) -> str:
        return "AcquisitionCredentials(<redacted>)"


@dataclass(frozen=True, slots=True)
class HistoricalResearchResponse:
    request: HistoricalResearchRequest
    status: int
    body: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class CustodyPersistencePlan:
    """Fixed paths; callers cannot substitute a repository/temp/production root."""

    custody_root: str = field(default=CUSTODY_ROOT, init=False)
    open_root: str = field(default=OPEN_ROOT, init=False)
    sddl: str = field(default=CUSTODY_SDDL, init=False)


@dataclass(frozen=True, slots=True)
class CustodyInspection:
    custody_root: str
    open_root: str
    owner_sid: str
    sddl: str
    local_ntfs: bool
    reparse_free: bool
    exclusive_destinations: bool

    def verify(self) -> None:
        if (self.custody_root, self.open_root, self.owner_sid, self.sddl) != (
            CUSTODY_ROOT,
            OPEN_ROOT,
            "S-1-5-32-544",
            CUSTODY_SDDL,
        ) or any(
            item is not True
            for item in (
                self.local_ntfs,
                self.reparse_free,
                self.exclusive_destinations,
            )
        ):
            raise HistoricalResearchCustodyError(
                "custody path/ACL/owner/volume rejection"
            )


@dataclass(frozen=True, slots=True)
class PersistenceReceipt:
    relative_path: str
    digest: str
    byte_size: int
    durable_readback_verified: bool

    def verify(self, relative_path: str, body: bytes) -> None:
        if (
            (self.relative_path, self.digest, self.byte_size)
            != (relative_path, sha256(body).hexdigest(), len(body))
            or type(self.byte_size) is not int
            or self.durable_readback_verified is not True
        ):
            raise HistoricalResearchCustodyError("persistence/readback ambiguity")


class AcquisitionTransport(Protocol):
    def get(
        self, request: HistoricalResearchRequest, credentials: AcquisitionCredentials
    ) -> HistoricalResearchResponse: ...


class CredentialSource(Protocol):
    def read(self) -> AcquisitionCredentials: ...


class AcquisitionCustody(Protocol):
    """Trusted effect boundary; native implementations need separate B2 review.

    claim_attempt durably consumes the attempt BEFORE any other write/network
    effect. It rejects all existing/ambiguous attempts and destination state.
    All protected writes are create-only, fsynced and read-back verified. OPEN
    writes are also create-only and never cause directory namespace promotion.
    """

    def claim_attempt(self, attempt_id: str, plan: CustodyPersistencePlan) -> bool: ...
    def prepare_protected(self, plan: CustodyPersistencePlan) -> None: ...
    def inspect(self) -> CustodyInspection: ...
    def persist_protected(
        self, relative_path: str, body: bytes
    ) -> PersistenceReceipt: ...
    def materialize_open(
        self, files: tuple[tuple[str, bytes], ...]
    ) -> tuple[PersistenceReceipt, ...]: ...
    def record_terminal(self, state: str, stage: str) -> None: ...


@dataclass(frozen=True, slots=True)
class AcquisitionOutcome:
    state: str
    stage: str
    evidence_bytes: bytes | None = field(default=None, repr=False)


class _Stop(Exception):
    pass


_STOP_REASONS = frozenset(
    {
        "RESPONSE_BINDING",
        "RESPONSE_SIZE",
        "STREAM_SIZE_BOUND",
        "HTTP_AUTH_OR_ENTITLEMENT",
        "HTTP_RATE_LIMIT",
        "HTTP_SERVER",
        "HTTP_STATUS",
        "PAGE_REPLAY",
        "MISSING_TERMINAL_STATE",
        "TOKEN_LOOP",
        "PAGINATION_BOUND",
        "CONTINUITY_ACTION_REVIEW_REQUIRED",
        "INVALID_SOURCE_ATTEMPT_OR_CALENDAR",
        "ATTEMPT_OR_DESTINATION_NOT_FRESH",
        "INVALID_CREDENTIAL_ADAPTER",
        "OPEN_PERSISTENCE_AMBIGUITY",
    }
)


def _page(body: bytes) -> dict:
    # Decimal lexical preservation; the public JSON parser checks duplicates,
    # shape/size/nonfinite constants first without exposing raw bodies.
    parse_custody_json(body)
    return json.loads(body, parse_float=Decimal)


def _collect(
    stream: AcquisitionStream,
    transport: AcquisitionTransport,
    credentials: AcquisitionCredentials,
    custody: AcquisitionCustody,
) -> tuple[bytes, ...]:
    pages = []
    digests = set()
    tokens = set()
    token = None
    total_bytes = 0
    for index in range(MAX_PAGES):
        request = HistoricalResearchRequest(stream, token)
        response = transport.get(request, credentials)
        if (
            type(response) is not HistoricalResearchResponse
            or response.request != request
            or type(response.status) is not int
        ):
            raise _Stop("RESPONSE_BINDING")
        if (
            type(response.body) is not bytes
            or not 0 < len(response.body) <= MAX_RESPONSE_BYTES
        ):
            raise _Stop("RESPONSE_SIZE")
        total_bytes += len(response.body)
        if total_bytes > MAX_STREAM_BYTES:
            raise _Stop("STREAM_SIZE_BOUND")
        custody.inspect().verify()
        relative = f"vendor-raw/{stream.value}/{index:04d}.json"
        custody.persist_protected(relative, response.body).verify(
            relative, response.body
        )
        custody.inspect().verify()
        if response.status != 200:
            if response.status in (401, 403):
                raise _Stop("HTTP_AUTH_OR_ENTITLEMENT")
            if response.status == 429:
                raise _Stop("HTTP_RATE_LIMIT")
            raise _Stop("HTTP_SERVER" if response.status >= 500 else "HTTP_STATUS")
        digest = sha256(response.body).hexdigest()
        if digest in digests:
            raise _Stop("PAGE_REPLAY")
        digests.add(digest)
        raw = _page(response.body)
        if "next_page_token" not in raw:
            raise _Stop("MISSING_TERMINAL_STATE")
        pages.append(response.body)
        token = raw["next_page_token"]
        if token is None:
            return tuple(pages)
        HistoricalResearchRequest(stream, token)
        if token in tokens:
            raise _Stop("TOKEN_LOOP")
        tokens.add(token)
    raise _Stop("PAGINATION_BOUND")


def _number(value: object) -> Decimal:
    if type(value) not in (int, Decimal):
        raise HistoricalResearchCustodyError("invalid OHLC numeric type")
    result = Decimal(value)
    if (
        not result.is_finite()
        or result <= 0
        or len(result.as_tuple().digits) > 64
        or abs(result.as_tuple().exponent) > 64
    ):
        raise HistoricalResearchCustodyError("invalid OHLC number")
    return result


def normalize_historical_research_bars(pages: tuple[bytes, ...]) -> tuple[Bar, ...]:
    """Reconcile original single-symbol responses without sorting/filtering."""
    bars = []
    for page in pages:
        raw = _page(page)
        if not {"symbol", "bars", "next_page_token"} <= set(raw) or set(raw) - {
            "symbol",
            "bars",
            "next_page_token",
            "feed",
            "adjustment",
            "currency",
        }:
            raise HistoricalResearchCustodyError("unexpected bars response shape")
        if raw["symbol"] != "SPY" or type(raw["bars"]) is not list:
            raise HistoricalResearchCustodyError("bars symbol/shape mismatch")
        for name, expected in (
            ("feed", "sip"),
            ("adjustment", "raw"),
            ("currency", "USD"),
        ):
            if name in raw and raw[name] != expected:
                raise HistoricalResearchCustodyError("bars response semantics mismatch")
        for row in raw["bars"]:
            if (
                type(row) is not dict
                or not {"t", "o", "h", "l", "c", "v"} <= set(row)
                or set(row) - {"t", "o", "h", "l", "c", "v", "n", "vw"}
            ):
                raise HistoricalResearchCustodyError("invalid bars row shape")
            if type(row["t"]) is not str or type(row["v"]) is not int or row["v"] < 0:
                raise HistoricalResearchCustodyError("invalid timestamp/volume type")
            if (
                re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})",
                    row["t"],
                )
                is None
                or row["v"] > 2**63 - 1
            ):
                raise HistoricalResearchCustodyError(
                    "unsupported timestamp precision/volume"
                )
            stamp = datetime.fromisoformat(row["t"])
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise HistoricalResearchCustodyError("aware vendor timestamp required")
            stamp = stamp.astimezone(UTC)
            if (
                not HISTORICAL_RESEARCH_FULL_START
                <= stamp
                < HISTORICAL_RESEARCH_FULL_END
                or (bars and stamp <= bars[-1].timestamp)
            ):
                raise HistoricalResearchCustodyError(
                    "bar bounds/order/duplicate rejection"
                )
            bars.append(
                Bar(
                    Symbol("SPY"),
                    stamp,
                    *(_number(row[key]) for key in ("o", "h", "l", "c")),
                    row["v"],
                )
            )
    if not bars:
        raise HistoricalResearchCustodyError("empty bars dataset")
    return tuple(bars)


def corporate_action_sidecar(pages: tuple[bytes, ...]) -> bytes:
    """Preserve all original pages; non-cash/unknown actions block admissibility."""
    seen = set()
    previous = None
    for page in pages:
        raw = _page(page)
        if (
            set(raw) != {"corporate_actions", "next_page_token"}
            or type(raw["corporate_actions"]) is not dict
        ):
            raise HistoricalResearchCustodyError(
                "invalid corporate-action response shape"
            )
        for group, actions in raw["corporate_actions"].items():
            if type(actions) is not list:
                raise HistoricalResearchCustodyError("invalid corporate-action group")
            if actions and group != "cash_dividends":
                raise _Stop("CONTINUITY_ACTION_REVIEW_REQUIRED")
            for action in actions:
                if (
                    type(action) is not dict
                    or action.get("symbol") != "SPY"
                    or type(action.get("id")) is not str
                    or action["id"] in seen
                ):
                    raise HistoricalResearchCustodyError(
                        "corporate-action identity/symbol mismatch"
                    )
                process_date = action.get("process_date")
                if (
                    type(process_date) is not str
                    or re.fullmatch(r"\d{4}-\d{2}-\d{2}", process_date) is None
                ):
                    raise HistoricalResearchCustodyError(
                        "invalid corporate-action process date"
                    )
                day = datetime.strptime(process_date, "%Y-%m-%d").date()
                if (
                    not HISTORICAL_RESEARCH_FULL_START.date()
                    <= day
                    <= HISTORICAL_RESEARCH_FULL_END.date()
                    or (previous is not None and day < previous)
                ):
                    raise HistoricalResearchCustodyError(
                        "corporate-action bounds/order mismatch"
                    )
                if "rate" not in action or _number(action["rate"]) <= 0:
                    raise HistoricalResearchCustodyError("invalid cash dividend")
                previous = day
                seen.add(action["id"])
    return b'{"pages":[' + b",".join(pages) + b"]}"


def _partition(
    role: HistoricalResearchPartitionRole,
    bars: tuple[Bar, ...],
    pages: tuple[bytes, ...],
    sidecar: bytes,
) -> HistoricalResearchPartitionMaterial:
    normalized = historical_research_normalized_csv(bars)
    data = parse_historical_research_csv(normalized, role)
    manifest = HistoricalResearchPartitionManifest(
        role=role,
        start=data.request.start,
        end=data.request.end,
        normalized_file_sha256=sha256(normalized).hexdigest(),
        normalized_byte_size=len(normalized),
        row_count=len(bars),
        first_bar_timestamp=bars[0].timestamp,
        last_bar_timestamp=bars[-1].timestamp,
        historical_data_fingerprint=historical_data_fingerprint(data),
        raw_vendor_page_sha256=tuple(sha256(page).hexdigest() for page in pages),
        corporate_action_sha256=sha256(sidecar).hexdigest(),
    )
    return HistoricalResearchPartitionMaterial(manifest, normalized, pages, sidecar)


class HistoricalResearchAcquisitionOperator:
    """One-use injected kernel; success materializes but NEVER admits research."""

    def __init__(
        self,
        transport: AcquisitionTransport,
        credentials: CredentialSource,
        custody: AcquisitionCustody,
    ) -> None:
        self._transport = transport
        self._credentials = credentials
        self._custody = custody
        self._used = False

    def run(
        self,
        *,
        source_head: str,
        source_tree: str,
        attempt_id: str,
        session_authority: HistoricalSessionAuthority,
    ) -> AcquisitionOutcome:
        if self._used:
            return AcquisitionOutcome("STOP_NO_RETRY", "OPERATOR_CONSUMED")
        self._used = True
        stage = "SOURCE_AND_ATTEMPT"
        claimed = False
        try:
            if (
                any(
                    type(item) is not str or re.fullmatch(r"[0-9a-f]{40}", item) is None
                    for item in (source_head, source_tree)
                )
                or type(attempt_id) is not str
                or str(UUID(attempt_id)) != attempt_id
                or type(session_authority) is not HistoricalSessionAuthority
            ):
                raise _Stop("INVALID_SOURCE_ATTEMPT_OR_CALENDAR")
            require_accepted_historical_session_authority(session_authority)
            from trading_bot.experiments.historical_research_sessions import (
                reconcile_historical_session_model,
            )

            reconcile_historical_session_model(session_authority)
            stage = "DURABLE_CLAIM"
            if (
                self._custody.claim_attempt(attempt_id, CustodyPersistencePlan())
                is not True
            ):
                raise _Stop("ATTEMPT_OR_DESTINATION_NOT_FRESH")
            claimed = True
            stage = "PREPARE_PROTECTED"
            self._custody.prepare_protected(CustodyPersistencePlan())
            self._custody.inspect().verify()
            stage = "CREDENTIALS"
            credentials = self._credentials.read()
            if type(credentials) is not AcquisitionCredentials:
                raise _Stop("INVALID_CREDENTIAL_ADAPTER")
            stage = "BARS_ACQUISITION"
            pages = _collect(
                AcquisitionStream.BARS, self._transport, credentials, self._custody
            )
            stage = "CORPORATE_ACTION_ACQUISITION"
            actions = _collect(
                AcquisitionStream.CORPORATE_ACTIONS,
                self._transport,
                credentials,
                self._custody,
            )
            stage = "NORMALIZATION_AND_CUSTODIAN_VERIFICATION"
            bars = normalize_historical_research_bars(pages)
            sidecar = corporate_action_sidecar(actions)
            opened = _partition(
                HistoricalResearchPartitionRole.OPEN,
                tuple(
                    bar
                    for bar in bars
                    if bar.timestamp < HISTORICAL_RESEARCH_HOLDOUT_START
                ),
                pages,
                sidecar,
            )
            held = _partition(
                HistoricalResearchPartitionRole.FINAL_HOLDOUT,
                tuple(
                    bar
                    for bar in bars
                    if bar.timestamp >= HISTORICAL_RESEARCH_HOLDOUT_START
                ),
                pages,
                sidecar,
            )
            full = HistoricalDataResult(
                HistoricalDataRequest(
                    Symbol("SPY"),
                    HISTORICAL_RESEARCH_FULL_START,
                    HISTORICAL_RESEARCH_FULL_END,
                ),
                bars,
                HISTORICAL_RESEARCH_PROVIDER,
            )
            snapshot = HistoricalResearchDatasetSnapshot(
                open_manifest_id=opened.manifest.manifest_id,
                holdout_manifest_id=held.manifest.manifest_id,
                full_historical_data_fingerprint=historical_data_fingerprint(full),
                open_corporate_action_sha256=sha256(sidecar).hexdigest(),
                holdout_corporate_action_sha256=sha256(sidecar).hexdigest(),
            )
            verify_historical_research_custodian_dataset(
                snapshot, opened, held, session_authority
            )
            stage = "PROTECTED_PERSISTENCE"
            for relative, body in (
                ("normalized/holdout/SPY.csv", held.normalized_bytes),
                ("corporate-actions/sidecar.json", sidecar),
                ("manifests/open.json", opened.manifest.to_json().encode()),
                ("manifests/holdout.json", held.manifest.to_json().encode()),
                ("manifests/snapshot.json", snapshot.to_json().encode()),
            ):
                self._custody.inspect().verify()
                self._custody.persist_protected(relative, body).verify(relative, body)
                self._custody.inspect().verify()
            evidence = HistoricalResearchCustodyEvidence(
                source_head,
                source_tree,
                attempt_id,
                session_authority.identity,
                session_authority.digest,
                tuple(sha256(page).hexdigest() for page in pages),
                tuple(sha256(page).hexdigest() for page in actions),
                snapshot,
                opened.manifest,
                held.manifest,
            )
            evidence_bytes = evidence.to_bytes()
            stage = "OPEN_MATERIALIZATION"
            files = (
                ("normalized/open/SPY.csv", opened.normalized_bytes),
                ("manifests/open-partition.json", opened.manifest.to_json().encode()),
                ("manifests/holdout-commitment.json", held.manifest.to_json().encode()),
                ("manifests/dataset-commitment.json", snapshot.to_json().encode()),
                ("manifests/custody-evidence.json", evidence_bytes),
            )
            self._custody.inspect().verify()
            receipts = self._custody.materialize_open(files)
            if type(receipts) is not tuple or len(receipts) != len(files):
                raise _Stop("OPEN_PERSISTENCE_AMBIGUITY")
            for receipt, (relative, body) in zip(receipts, files, strict=True):
                receipt.verify(relative, body)
            self._custody.inspect().verify()
            stage = "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION"
            self._custody.record_terminal(stage, stage)
            return AcquisitionOutcome(stage, stage, evidence_bytes)
        except Exception as exc:
            reason = "DEPENDENCY_OR_VALIDATION_FAILURE"
            if type(exc) is _Stop and str(exc) in _STOP_REASONS:
                reason = str(exc)
            if claimed:
                try:
                    self._custody.record_terminal("STOP_RECONCILIATION_REQUIRED", stage)
                except Exception:
                    reason = "TERMINAL_EVIDENCE_PERSISTENCE_AMBIGUITY"
            return AcquisitionOutcome(
                "STOP_RECONCILIATION_REQUIRED", stage + ":" + reason
            )
