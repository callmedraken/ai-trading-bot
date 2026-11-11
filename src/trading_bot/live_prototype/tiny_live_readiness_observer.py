"""Source-owned, read-only Q62 observation and create-once local preparation.

Importing this module constructs no credential, provider, broker transport, or
filesystem state. The observer uses fixed source-owned identities and paths;
its only broker operations are the three bounded Robinhood reads and one
cached Alpaca signal refresh needed to build the existing nine Q62 proofs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final, Protocol

from scripts.current_source_authority import (
    PublicationContext,
    evaluate_source_authority,
)

from trading_bot.desktop_paper.robinhood_read import (
    AgenticAccountIdentity,
    data,
    parse_order,
    parse_position,
    resolve_account,
)
from trading_bot.live_prototype.alpaca_runtime_signal_provider import (
    AlpacaRuntimeSignalProvider,
    RuntimeSignalSnapshot,
)
from trading_bot.live_prototype.capability_observer import CapabilityReport
from trading_bot.live_prototype.capability_operator import (
    _create_windows_oauth_factory,
)
from trading_bot.live_prototype.capability_rule_binding_l41r6 import (
    L41R6CompositeReport,
    classify_l41r6_composite,
)
from trading_bot.live_prototype.configuration import CompletedSignalInputs
from trading_bot.live_prototype.consumed_l41_evidence import (
    CONSUMED_L41_EVIDENCE_BYTES,
    CONSUMED_L41_EVIDENCE_SHA256,
)
from trading_bot.live_prototype.consumed_l41r5_evidence import (
    CONSUMED_L41R5_EVIDENCE_BYTES,
    CONSUMED_L41R5_EVIDENCE_SHA256,
)
from trading_bot.live_prototype.contracts import EffectDisposition, Lifecycle
from trading_bot.live_prototype.durable_state import (
    DurableState,
    DurableStateStore,
    IntentStatus,
    RuntimeIdentity,
)
from trading_bot.live_prototype.live_contract import (
    IntentKind as OwnershipIntentKind,
)
from trading_bot.live_prototype.live_contract import (
    OwnershipSnapshot,
)
from trading_bot.live_prototype.readiness_contracts import (
    FreshProof,
    ProofKind,
    ProofStatus,
    Q62Blocker,
    ReadinessIdentity,
)
from trading_bot.live_prototype.readiness_operator import (
    Q62EvidenceBundle,
    Q62Status,
    evaluate_q62_readiness,
)
from trading_bot.live_prototype.recovery_operator import (
    RecoveryObservation,
    RecoveryReport,
    reconcile_read_only,
)
from trading_bot.live_prototype.tiny_live_capability_admission import (
    TinyLivePrototypeCapabilityAdmission,
    admit_tiny_live_capabilities,
)
from trading_bot.live_prototype.tiny_live_policy import TINY_LIVE_POLICY
from trading_bot.live_prototype.tiny_live_readiness_operator import (
    TinyLiveReadinessReport,
    TinyLiveReadinessStatus,
    evaluate_q62_tiny_live_readiness,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.robinhood_mcp.current_read_transport import (
    RobinhoodCurrentReadTransport,
)

OBSERVATION_SCHEMA: Final = "arch147-q62-tiny-live-readiness-observation/v1"
FEATURE_BRANCH: Final = "feature/robinhood-live-prototype-current"
CHECKPOINT_NAME: Final = "arch147-live-prototype"
CANONICAL_ROOT: Final = Path(r"F:\AI\worktrees\ai-trading-bot-live-prototype-current")
EVIDENCE_ROOT: Final = Path(r"F:\AI\temp")
LIVE_STATE_ROOT: Final = Path(r"F:\AI\arch147-q62-live-state-v1")
STATE_FILENAME: Final = "durable-state.jsonl"
_EXPECTED_ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
_CONSUMED_L41_PATH: Final = Path(
    r"F:\AI\temp\arch147-l41-capability-observation-c0f29dfb1fb544d8b330910ad41af1f6\evidence.json"
)
_CONSUMED_L41R5_PATH: Final = Path(
    r"F:\AI\temp\arch147-l41r5-schema-observation-6fcfcdf0cfd641fc95c7b5855292e8b4\evidence.json"
)
_ACCOUNT_TTL = timedelta(minutes=10)
_MAX_POSITION_PAGES = 3
_MAX_POSITIONS = 1000
_MAX_ORDER_PAGES = 3
_MAX_ORDERS = 300
_MAX_ACCOUNTS = 100
_TERMINAL_ORDER_STATES: Final = frozenset(
    {"filled", "canceled", "rejected", "failed", "voided", "expired"}
)
_ZERO = Decimal("0")

_BINDING_MATERIAL: Final = (
    ("schema", "arch147-tiny-live-runtime-binding/v1"),
    ("purpose", "RETAINED_CONTROL_RESEARCH_PROVENANCE"),
    ("campaign_id", "9b2a000e-3adc-50f4-ab47-2aa90665e3c9"),
    ("bundle_id", "f01a39a7-0a65-55bb-9d38-608b1ce0bd21"),
    (
        "bundle_sha256",
        "94870e0e0e10de16f7e98e7cfea2e2c84458a15e6f1d2665cd8a5dc7e404fc11",
    ),
    ("candidate", "BASE_MA35_50_V1"),
    ("candidate_id", "21158358-75be-5597-b940-5bccdda1429c"),
    ("live_eligible", False),
    ("challenger_promotion", False),
)
_CONFIGURATION_MATERIAL: Final = (
    ("schema", "arch147-q62-tiny-live-readiness-configuration/v1"),
    ("product_scope", "PRIVATE_SINGLE_USER_WINDOWS_DESKTOP"),
    ("symbol", "SPY"),
    ("strategy", "BASE_MA35_50_V1"),
    ("price_basis", "ALPACA_ALL_ADJUSTED_PRICE_V1"),
    ("position_model", "CASH_LONG_ONLY"),
    ("session", "REGULAR_HOURS"),
    ("time_in_force", "DAY"),
    ("entry_order_type", "MARKET"),
    ("exit_order_type", "MARKET"),
    ("max_entry_usd_cents", 1000),
    ("max_entry_intents", 1),
    ("budget_replenishes", False),
    ("policy_id", "ARCH147_TINY_LIVE_SPY_SINGLE_ENTRY_V1"),
    ("policy_sha256", TINY_LIVE_POLICY.canonical_sha256()),
    (
        "binding_sha256",
        hashlib.sha256(
            json.dumps(
                dict(_BINDING_MATERIAL),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest(),
    ),
    ("provider_fallback", False),
    ("holdout_policy", "SEALED_NO_ACCESS"),
)
BINDING_SHA256: Final = hashlib.sha256(
    json.dumps(
        dict(_BINDING_MATERIAL),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
).hexdigest()
CONFIGURATION_SHA256: Final = hashlib.sha256(
    json.dumps(
        dict(_CONFIGURATION_MATERIAL),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
).hexdigest()


class _ObserverBlocked(RuntimeError):
    """Closed, sanitized failure code for an incomplete observation."""

    def __init__(self, code: str) -> None:
        if not code.startswith("Q62_") or not code.replace("_", "").isalnum():
            code = "Q62_OBSERVATION_BLOCKED"
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _SourceAdmission:
    branch: str
    head: str
    tree: str
    origin_feature_head: str
    origin_feature_tree: str
    origin_develop_head: str
    origin_develop_tree: str
    feature_authority: str
    prospective_develop_authority: str

    def material(self) -> dict[str, str]:
        return {
            "branch": self.branch,
            "head": self.head,
            "tree": self.tree,
            "origin_feature_head": self.origin_feature_head,
            "origin_feature_tree": self.origin_feature_tree,
            "origin_develop_head": self.origin_develop_head,
            "origin_develop_tree": self.origin_develop_tree,
            "feature_authority": self.feature_authority,
            "prospective_develop_authority": self.prospective_develop_authority,
        }


@dataclass(slots=True)
class _AttemptLedger:
    robinhood_oauth_factory_build_attempts: int = 0
    robinhood_oauth_scope_entry_attempts: int = 0
    robinhood_mcp_session_open_attempts: int = 0
    robinhood_tools_list_page_attempts: int = 0
    robinhood_get_accounts_attempts: int = 0
    robinhood_position_page_attempts: int = 0
    robinhood_order_page_attempts: int = 0
    robinhood_tool_dispatch_attempts: dict[str, int] = field(
        default_factory=lambda: {
            "get_accounts": 0,
            "get_equity_positions": 0,
            "get_equity_orders": 0,
            "get_portfolio": 0,
            "get_equity_quotes": 0,
            "review_equity_order": 0,
            "place_equity_order": 0,
            "cancel_equity_order": 0,
            "other": 0,
        }
    )
    robinhood_native_credential_read_count: None = None
    robinhood_credential_store_accounting: str = (
        "SDK_MANAGED_NATIVE_READS_NOT_INDIVIDUALLY_COUNTED"
    )
    alpaca_credential_scope_attempts: int | None = 0
    alpaca_native_credential_read_count: None = None
    alpaca_snapshot_attempts: int = 0
    alpaca_provider_call_attempts: int | None = 0
    alpaca_provider_construction_attempts: int = 0
    alpaca_transport_factory_attempts: int | None = 0
    evidence_write_attempts: int = 0
    review_attempts: int = 0
    placement_attempts: int = 0
    cancellation_attempts: int = 0
    broker_mutation_attempts: int = 0
    live_mutation_attempts: int = 0
    paper_mutation_attempts: int = 0
    holdout_access_attempts: int = 0

    def material(self) -> dict[str, object]:
        return {
            "robinhood_oauth_factory_build_attempts": (
                self.robinhood_oauth_factory_build_attempts
            ),
            "robinhood_oauth_scope_entry_attempts": (
                self.robinhood_oauth_scope_entry_attempts
            ),
            "robinhood_mcp_session_open_attempts": (
                self.robinhood_mcp_session_open_attempts
            ),
            "robinhood_tools_list_page_attempts": (
                self.robinhood_tools_list_page_attempts
            ),
            "robinhood_get_accounts_attempts": (self.robinhood_get_accounts_attempts),
            "robinhood_position_page_attempts": (self.robinhood_position_page_attempts),
            "robinhood_order_page_attempts": self.robinhood_order_page_attempts,
            "robinhood_tool_dispatch_attempts": dict(
                self.robinhood_tool_dispatch_attempts
            ),
            "robinhood_native_credential_read_count": None,
            "robinhood_credential_store_accounting": (
                self.robinhood_credential_store_accounting
            ),
            "alpaca_credential_scope_attempts": self.alpaca_credential_scope_attempts,
            "alpaca_native_credential_read_count": None,
            "alpaca_snapshot_attempts": self.alpaca_snapshot_attempts,
            "alpaca_provider_call_attempts": self.alpaca_provider_call_attempts,
            "alpaca_provider_construction_attempts": (
                self.alpaca_provider_construction_attempts
            ),
            "alpaca_transport_factory_attempts": (
                self.alpaca_transport_factory_attempts
            ),
            "evidence_write_attempts": self.evidence_write_attempts,
            "review_attempts": 0,
            "placement_attempts": 0,
            "cancellation_attempts": 0,
            "broker_mutation_attempts": 0,
            "live_mutation_attempts": 0,
            "paper_mutation_attempts": 0,
            "holdout_access_attempts": 0,
        }


class _ReadBoundary(Protocol):
    def get_accounts(self) -> Mapping[str, object]: ...

    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]: ...


class _ObservedRobinhoodTransport(RobinhoodCurrentReadTransport):
    """Count sessions, discovery pages, and dispatch attempts before calls."""

    def __init__(self, oauth_factory: Callable[[], object], ledger: _AttemptLedger):
        super().__init__(oauth_factory)
        self._ledger = ledger

    async def _request(
        self, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        self._ledger.robinhood_mcp_session_open_attempts += 1
        return await super()._request(name, arguments)

    async def _read(
        self, client: object, name: str, arguments: dict[str, object]
    ) -> Mapping[str, object]:
        return await super()._read(
            _CountingMcpClient(client, self._ledger), name, arguments
        )


class _CountingMcpClient:
    __slots__ = ("_client", "_ledger")

    def __init__(self, client: object, ledger: _AttemptLedger) -> None:
        self._client = client
        self._ledger = ledger

    async def list_tools(self, *, cursor: str | None) -> object:
        self._ledger.robinhood_tools_list_page_attempts += 1
        method = self._client.list_tools
        return await method(cursor=cursor)

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        if name in self._ledger.robinhood_tool_dispatch_attempts:
            self._ledger.robinhood_tool_dispatch_attempts[name] += 1
        else:
            self._ledger.robinhood_tool_dispatch_attempts["other"] += 1
        method = self._client.call_tool
        return await method(name, arguments)


class _TrackedReadBoundary:
    __slots__ = ("_read", "_ledger")

    def __init__(self, read: _ReadBoundary, ledger: _AttemptLedger) -> None:
        self._read = read
        self._ledger = ledger

    def get_accounts(self) -> Mapping[str, object]:
        self._ledger.robinhood_get_accounts_attempts += 1
        return self._read.get_accounts()

    def get_equity_positions(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._read.get_equity_positions(arguments)

    def get_equity_orders(
        self, arguments: Mapping[str, object]
    ) -> Mapping[str, object]:
        return self._read.get_equity_orders(arguments)


@dataclass(frozen=True, slots=True)
class _Dependencies:
    source_admitter: Callable[[], _SourceAdmission]
    evidence_destination: Callable[[], Path]
    state_root: Path
    artifact_loader: Callable[[], tuple[bytes, bytes, L41R6CompositeReport]]
    robinhood_builder: Callable[[_AttemptLedger], _ReadBoundary]
    signal_provider_builder: Callable[[_AttemptLedger], object]
    clock: Callable[[], datetime]
    session_authority: object


@dataclass(frozen=True, slots=True)
class _CompletedObservation:
    status: str
    reason: str
    evidence: dict[str, object]
    evidence_path: Path | None
    historical_report: object | None
    prototype_report: TinyLiveReadinessReport | None


def _canonical_digest(material: object) -> str:
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _source_admission(repo_root: Path | None = None) -> _SourceAdmission:
    root = (
        CANONICAL_ROOT.resolve(strict=True)
        if repo_root is None
        else repo_root.resolve(strict=True)
    )
    if str(root).casefold() != str(CANONICAL_ROOT.resolve(strict=True)).casefold():
        raise _ObserverBlocked("Q62_SOURCE_ROOT_INVALID")
    before = _local_git_identity(root, require_live_refs=True)
    if before["branch"] != FEATURE_BRANCH:
        raise _ObserverBlocked("Q62_SOURCE_BRANCH_INVALID")
    feature = evaluate_source_authority(
        root, publication_context=PublicationContext.FEATURE
    )
    prospective = evaluate_source_authority(
        root, publication_context=PublicationContext.PROSPECTIVE_DEVELOP
    )
    after = _local_git_identity(root, require_live_refs=True)
    if before != after:
        raise _ObserverBlocked("Q62_SOURCE_IDENTITY_UNSTABLE")
    head, tree = before["head"], before["tree"]
    for result in (feature, prospective):
        if (
            not result.passed
            or result.head != head
            or result.tree != tree
            or CHECKPOINT_NAME not in result.checkpoints
        ):
            raise _ObserverBlocked("Q62_SOURCE_AUTHORITY_BLOCKED")
    return _SourceAdmission(
        branch=FEATURE_BRANCH,
        head=head,
        tree=tree,
        origin_feature_head=head,
        origin_feature_tree=tree,
        origin_develop_head=head,
        origin_develop_tree=tree,
        feature_authority="PASS",
        prospective_develop_authority="PASS",
    )


def _local_git_identity(root: Path, *, require_live_refs: bool) -> dict[str, str]:
    def git(*arguments: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *arguments],
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        except Exception:
            raise _ObserverBlocked("Q62_SOURCE_GIT_UNAVAILABLE") from None
        if result.returncode:
            raise _ObserverBlocked("Q62_SOURCE_GIT_UNAVAILABLE")
        return result.stdout.strip()

    branch = git("branch", "--show-current")
    if git("status", "--porcelain=v1", "--untracked-files=all"):
        raise _ObserverBlocked("Q62_SOURCE_DIRTY")
    head = git("rev-parse", "--verify", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    if git("remote", "get-url", "origin") != _EXPECTED_ORIGIN:
        raise _ObserverBlocked("Q62_SOURCE_ORIGIN_INVALID")
    if len(head) != 40 or len(tree) != 40:
        raise _ObserverBlocked("Q62_SOURCE_IDENTITY_INVALID")
    identity = {"branch": branch, "head": head, "tree": tree}
    if require_live_refs:
        refs = {}
        for name in (FEATURE_BRANCH, "develop"):
            output = git(
                "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{name}"
            )
            rows = output.splitlines()
            if len(rows) != 1:
                raise _ObserverBlocked("Q62_SOURCE_REMOTE_INVALID")
            pieces = rows[0].split("\t")
            if len(pieces) != 2 or pieces[1] != f"refs/heads/{name}":
                raise _ObserverBlocked("Q62_SOURCE_REMOTE_INVALID")
            refs[name] = pieces[0]
        if refs[FEATURE_BRANCH] != head or refs["develop"] != head:
            raise _ObserverBlocked("Q62_SOURCE_REMOTE_MISMATCH")
        identity["origin_feature_head"] = refs[FEATURE_BRANCH]
        identity["origin_feature_tree"] = tree
        identity["origin_develop_head"] = refs["develop"]
        identity["origin_develop_tree"] = tree
    else:
        for name in (FEATURE_BRANCH, "develop"):
            reference = f"refs/remotes/origin/{name}"
            try:
                remote_head = git("rev-parse", "--verify", reference)
            except _ObserverBlocked:
                raise _ObserverBlocked("Q62_LOCAL_SOURCE_REF_UNAVAILABLE") from None
            if remote_head != head:
                raise _ObserverBlocked("Q62_LOCAL_SOURCE_REF_MISMATCH")
    return identity


def _local_preparation_source() -> _SourceAdmission:
    root = CANONICAL_ROOT.resolve(strict=True)
    before = _local_git_identity(root, require_live_refs=False)
    if before["branch"] != FEATURE_BRANCH:
        raise _ObserverBlocked("Q62_SOURCE_BRANCH_INVALID")
    feature = evaluate_source_authority(
        root, publication_context=PublicationContext.FEATURE
    )
    prospective = evaluate_source_authority(
        root, publication_context=PublicationContext.PROSPECTIVE_DEVELOP
    )
    after = _local_git_identity(root, require_live_refs=False)
    if before != after:
        raise _ObserverBlocked("Q62_SOURCE_IDENTITY_UNSTABLE")
    for result in (feature, prospective):
        if (
            not result.passed
            or result.head != before["head"]
            or result.tree != before["tree"]
            or CHECKPOINT_NAME not in result.checkpoints
        ):
            raise _ObserverBlocked("Q62_SOURCE_AUTHORITY_BLOCKED")
    return _SourceAdmission(
        FEATURE_BRANCH,
        before["head"],
        before["tree"],
        before["head"],
        before["tree"],
        before["head"],
        before["tree"],
        "PASS",
        "PASS",
    )


def _load_consumed_artifacts() -> tuple[bytes, bytes, L41R6CompositeReport]:
    first = _read_exact_artifact(
        _CONSUMED_L41_PATH,
        expected_length=CONSUMED_L41_EVIDENCE_BYTES,
        expected_sha256=CONSUMED_L41_EVIDENCE_SHA256,
    )
    second = _read_exact_artifact(
        _CONSUMED_L41R5_PATH,
        expected_length=CONSUMED_L41R5_EVIDENCE_BYTES,
        expected_sha256=CONSUMED_L41R5_EVIDENCE_SHA256,
    )
    try:
        composite = classify_l41r6_composite(first, second)
    except Exception:
        raise _ObserverBlocked("Q62_CONSUMED_CAPABILITY_INVALID") from None
    if type(composite) is not L41R6CompositeReport:
        raise _ObserverBlocked("Q62_CONSUMED_CAPABILITY_INVALID")
    return first, second, composite


def _read_exact_artifact(
    path: Path, *, expected_length: int, expected_sha256: str
) -> bytes:
    try:
        root = EVIDENCE_ROOT.resolve(strict=True)
        resolved_parent = path.parent.resolve(strict=True)
        if not resolved_parent.is_relative_to(root) or path.parent != resolved_parent:
            raise _ObserverBlocked("Q62_CONSUMED_ARTIFACT_PATH_INVALID")
        _reject_reparse_ancestors(path, stop=root)
        if path.is_symlink() or not path.is_file():
            raise _ObserverBlocked("Q62_CONSUMED_ARTIFACT_UNAVAILABLE")
        raw = path.read_bytes()
    except _ObserverBlocked:
        raise
    except Exception:
        raise _ObserverBlocked("Q62_CONSUMED_ARTIFACT_UNAVAILABLE") from None
    if (
        len(raw) != expected_length
        or hashlib.sha256(raw).hexdigest() != expected_sha256
    ):
        raise _ObserverBlocked("Q62_CONSUMED_ARTIFACT_IDENTITY_MISMATCH")
    return raw


def _reject_reparse_ancestors(path: Path, *, stop: Path) -> None:
    current = path if path.exists() else path.parent
    while True:
        if current.is_symlink() or _is_reparse_point(current):
            raise _ObserverBlocked("Q62_PATH_REPARSE_POINT_REJECTED")
        if current == stop:
            return
        if current.parent == current or not current.is_relative_to(stop):
            raise _ObserverBlocked("Q62_PATH_OUTSIDE_FIXED_ROOT")
        current = current.parent


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(path.stat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _new_evidence_destination() -> Path:
    root = EVIDENCE_ROOT.resolve(strict=True)
    if root != EVIDENCE_ROOT or root.drive.upper() != "F:" or _is_reparse_point(root):
        raise _ObserverBlocked("Q62_EVIDENCE_ROOT_INVALID")
    candidate = root / f"arch147-q62-tiny-live-readiness-{uuid.uuid4().hex}"
    _validate_evidence_destination(candidate, root=root, create=True)
    return candidate


def _validate_evidence_destination(
    candidate: Path, *, root: Path = EVIDENCE_ROOT, create: bool = False
) -> Path:
    root = root.resolve(strict=True)
    if (
        candidate.drive.upper() != "F:"
        or candidate.parent != root
        or candidate.exists()
        or candidate.is_symlink()
        or _is_reparse_point(root)
    ):
        raise _ObserverBlocked("Q62_EVIDENCE_PATH_INVALID")
    try:
        _reject_reparse_ancestors(root, stop=root)
        if create:
            candidate.mkdir()
    except _ObserverBlocked:
        raise
    except Exception:
        raise _ObserverBlocked("Q62_EVIDENCE_PATH_INVALID") from None
    return candidate


def _validate_state_root(state_root: Path, *, require_absent: bool) -> Path:
    if state_root != LIVE_STATE_ROOT or state_root.drive.upper() != "F:":
        raise _ObserverBlocked("Q62_STATE_ROOT_INVALID")
    try:
        parent = state_root.parent.resolve(strict=True)
        if parent != state_root.parent or parent != Path(r"F:\AI"):
            raise _ObserverBlocked("Q62_STATE_ROOT_INVALID")
        _reject_reparse_ancestors(parent, stop=Path("F:/"))
    except _ObserverBlocked:
        raise
    except Exception:
        raise _ObserverBlocked("Q62_STATE_ROOT_INVALID") from None
    if state_root.exists() or state_root.is_symlink() or _is_reparse_point(state_root):
        if require_absent:
            raise _ObserverBlocked("Q62_STATE_ROOT_ALREADY_EXISTS")
        if (
            state_root.is_symlink()
            or _is_reparse_point(state_root)
            or not state_root.is_dir()
        ):
            raise _ObserverBlocked("Q62_STATE_ROOT_INVALID")
    elif not require_absent:
        raise _ObserverBlocked("Q62_STATE_MISSING")
    return state_root / STATE_FILENAME


def _runtime_identity(
    *, account_fingerprint: str, source: _SourceAdmission
) -> RuntimeIdentity:
    material = {
        "schema": "arch147-q62-lifecycle-identity/v1",
        "account_fingerprint": account_fingerprint,
        "source_head": source.head,
        "source_tree": source.tree,
        "config_sha256": CONFIGURATION_SHA256,
        "binding_sha256": BINDING_SHA256,
    }
    lifecycle_id = str(uuid.uuid5(uuid.NAMESPACE_URL, _canonical_json_text(material)))
    return RuntimeIdentity(
        account_fingerprint=account_fingerprint,
        source_head=source.head,
        source_tree=source.tree,
        config_digest=CONFIGURATION_SHA256,
        binding_digest=BINDING_SHA256,
        lifecycle_id=lifecycle_id,
    )


def _canonical_json_text(material: object) -> str:
    return json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def prepare_state() -> _CompletedObservation:
    """Create the one fixed initial journal without credentials or network."""
    ledger = _AttemptLedger()
    evidence_path: Path | None = None
    try:
        source = _local_preparation_source()
        state_file = _validate_state_root(LIVE_STATE_ROOT, require_absent=True)
        _read_exact_configuration()
        _, _, composite = _load_consumed_artifacts()
        report = composite.capability_report
        if type(report) is not CapabilityReport or not report.account_fingerprint:
            raise _ObserverBlocked("Q62_CONSUMED_ACCOUNT_INVALID")
        runtime_identity = _runtime_identity(
            account_fingerprint=report.account_fingerprint, source=source
        )
        # mkdir and exclusive journal creation are the only operation effects.
        LIVE_STATE_ROOT.mkdir()
        try:
            DurableStateStore.create(
                state_file, runtime_identity, initial_position=_ZERO
            )
        except Exception:
            # Preserve any partial state; never remove or reinitialize it.
            raise _ObserverBlocked("Q62_STATE_CREATE_FAILED") from None
        return _CompletedObservation(
            "PREPARED",
            "Q62_LOCAL_STATE_PREPARED_CREATE_ONCE",
            {
                "schema": "arch147-q62-local-state-preparation/v1",
                "status": "PREPARED",
                "reason": "Q62_LOCAL_STATE_PREPARED_CREATE_ONCE",
                "source": source.material(),
                "configuration_sha256": CONFIGURATION_SHA256,
                "binding_sha256": BINDING_SHA256,
                "policy_sha256": TINY_LIVE_POLICY.canonical_sha256(),
                "account_fingerprint": report.account_fingerprint,
                "baseline_quantity": "0",
                "entries_used": 0,
                "exits_used": 0,
                "credentials_or_provider_constructed": False,
                "network_attempts": 0,
                "automatic_reinitialization": False,
                "effects": ledger.material(),
            },
            evidence_path,
            None,
            None,
        )
    except _ObserverBlocked as error:
        return _blocked_result(error.code, ledger, evidence_path=evidence_path)
    except Exception:
        return _blocked_result(
            "Q62_PREPARATION_BLOCKED", ledger, evidence_path=evidence_path
        )


def _read_exact_configuration() -> None:
    if (
        TINY_LIVE_POLICY.canonical_sha256()
        != "485c6d93bd6413c5754c76437587f2cbda11db9bbf6394863ebe9f0991fdb287"
        or len(CONFIGURATION_SHA256) != 64
        or len(BINDING_SHA256) != 64
    ):
        raise _ObserverBlocked("Q62_CONFIGURATION_INVALID")


def observe_q62() -> _CompletedObservation:
    """Run one explicit source-admitted read-only Q62 attempt."""
    dependencies = _Dependencies(
        source_admitter=_source_admission,
        evidence_destination=_new_evidence_destination,
        state_root=LIVE_STATE_ROOT,
        artifact_loader=_load_consumed_artifacts,
        robinhood_builder=_build_robinhood_transport,
        signal_provider_builder=_build_signal_provider,
        clock=lambda: datetime.now(UTC),
        session_authority=NYSEPublishedRegularSessionAuthority(),
    )
    return _observe_once(dependencies)


def _build_robinhood_transport(ledger: _AttemptLedger) -> _ReadBoundary:
    ledger.robinhood_oauth_factory_build_attempts += 1
    try:
        oauth_factory = _create_windows_oauth_factory()
    except Exception:
        raise _ObserverBlocked("Q62_ROBINHOOD_CREDENTIAL_FACTORY_BLOCKED") from None

    def counted_oauth_scope() -> object:
        ledger.robinhood_oauth_scope_entry_attempts += 1
        return oauth_factory()

    return _ObservedRobinhoodTransport(counted_oauth_scope, ledger)


def _build_signal_provider(ledger: _AttemptLedger) -> object:
    del ledger
    return AlpacaRuntimeSignalProvider()


def _observe_once(dependencies: _Dependencies) -> _CompletedObservation:
    ledger = _AttemptLedger()
    evidence_path: Path | None = None
    source: _SourceAdmission | None = None
    try:
        source = dependencies.source_admitter()
        if type(source) is not _SourceAdmission or source.branch != FEATURE_BRANCH:
            raise _ObserverBlocked("Q62_SOURCE_ADMISSION_INVALID")
        evidence_path = dependencies.evidence_destination()
        if evidence_path.parent != EVIDENCE_ROOT:
            raise _ObserverBlocked("Q62_EVIDENCE_PATH_INVALID")
        _read_exact_configuration()
        state_file = _validate_state_root(dependencies.state_root, require_absent=False)
        if (
            state_file.is_symlink()
            or _is_reparse_point(state_file)
            or not state_file.is_file()
        ):
            raise _ObserverBlocked("Q62_STATE_FILE_INVALID")
        l41_bytes, l41r5_bytes, composite = dependencies.artifact_loader()
        if (
            len(l41_bytes) != CONSUMED_L41_EVIDENCE_BYTES
            or hashlib.sha256(l41_bytes).hexdigest() != CONSUMED_L41_EVIDENCE_SHA256
            or len(l41r5_bytes) != CONSUMED_L41R5_EVIDENCE_BYTES
            or hashlib.sha256(l41r5_bytes).hexdigest() != CONSUMED_L41R5_EVIDENCE_SHA256
        ):
            raise _ObserverBlocked("Q62_CONSUMED_CAPABILITY_INVALID")
        retained_capability = composite.capability_report
        if (
            type(retained_capability) is not CapabilityReport
            or not retained_capability.account_fingerprint
        ):
            raise _ObserverBlocked("Q62_CONSUMED_ACCOUNT_INVALID")
        expected_runtime_identity = _runtime_identity(
            account_fingerprint=retained_capability.account_fingerprint,
            source=source,
        )
        try:
            state_store = DurableStateStore.open(state_file, expected_runtime_identity)
        except Exception:
            raise _ObserverBlocked("Q62_STATE_IDENTITY_OR_JOURNAL_INVALID") from None
        durable_state = state_store.state
        if not _is_pristine_initial_state(durable_state):
            raise _ObserverBlocked("Q62_INITIAL_STATE_NOT_PRISTINE")

        # Credential/provider construction follows both source and evidence admission.
        boundary = _TrackedReadBoundary(dependencies.robinhood_builder(ledger), ledger)
        account_payload = boundary.get_accounts()
        account = resolve_account(account_payload)
        if type(account) is not AgenticAccountIdentity:
            raise _ObserverBlocked("Q62_ACCOUNT_INVALID")
        account_observed_at = _utc_clock(dependencies.clock)
        account_fingerprint = account.fingerprint
        if account_fingerprint != retained_capability.account_fingerprint:
            raise _ObserverBlocked("Q62_ACCOUNT_IDENTITY_MISMATCH")
        try:
            admission = admit_tiny_live_capabilities(
                composite,
                consumed_l41_bytes=l41_bytes,
                consumed_l41r5_bytes=l41r5_bytes,
                account_fingerprint=account_fingerprint,
            )
        except Exception:
            raise _ObserverBlocked("Q62_CAPABILITY_ADMISSION_BLOCKED") from None
        if type(admission) is not TinyLivePrototypeCapabilityAdmission:
            raise _ObserverBlocked("Q62_CAPABILITY_ADMISSION_INVALID")
        capability_observed_at = _utc_clock(dependencies.clock)

        ownership = _ownership_from_durable_state(durable_state, target_session=None)
        state_observed_at = _utc_clock(dependencies.clock)

        position_rows = _read_pages(
            boundary.get_equity_positions,
            {"account_number": account.account_number},
            "positions",
            max_pages=_MAX_POSITION_PAGES,
            max_rows=_MAX_POSITIONS,
            page_counter="robinhood_position_page_attempts",
            ledger=ledger,
        )
        try:
            positions = tuple(parse_position(row) for row in position_rows)
        except Exception:
            raise _ObserverBlocked("Q62_ROBINHOOD_RESPONSE_INVALID") from None
        order_rows = _read_pages(
            boundary.get_equity_orders,
            {
                "account_number": account.account_number,
                "placed_agent": "agentic",
                "symbol": "SPY",
            },
            "orders",
            max_pages=_MAX_ORDER_PAGES,
            max_rows=_MAX_ORDERS,
            page_counter="robinhood_order_page_attempts",
            ledger=ledger,
        )
        try:
            orders = tuple(parse_order(row) for row in order_rows)
        except Exception:
            raise _ObserverBlocked("Q62_ROBINHOOD_RESPONSE_INVALID") from None
        spy_positions = tuple(item for item in positions if item.symbol == "SPY")
        if len(spy_positions) > 1:
            raise _ObserverBlocked("Q62_POSITION_DUPLICATE")
        spy_position = spy_positions[0] if spy_positions else None
        observed_quantity = _ZERO if spy_position is None else spy_position.quantity
        sellable_quantity = (
            _ZERO if spy_position is None else spy_position.shares_available_for_sells
        )
        spy_orders = tuple(item for item in orders if item.symbol == "SPY")
        unresolved_orders = tuple(
            item
            for item in spy_orders
            if item.state.casefold() not in _TERMINAL_ORDER_STATES
        )
        broker_material = {
            "account_fingerprint": account_fingerprint,
            "observed_account_count": account.observed_account_count,
            "eligible_account_count": account.eligible_account_count,
            "position_count": len(positions),
            "position_sha256": _canonical_digest(
                [
                    [
                        item.symbol,
                        str(item.quantity),
                        str(item.shares_available_for_sells),
                        item.position_type,
                    ]
                    for item in positions
                ]
            ),
            "spy_position_quantity": str(observed_quantity),
            "spy_sellable_quantity": str(sellable_quantity),
            "agentic_order_count": len(orders),
            "spy_order_count": len(spy_orders),
            "unresolved_spy_order_count": len(unresolved_orders),
            "order_sha256": _canonical_digest(
                [
                    [
                        item.order_id,
                        item.symbol,
                        item.side,
                        item.state,
                        None if item.quantity is None else str(item.quantity),
                        str(item.cumulative_quantity),
                        item.created_at.isoformat(),
                    ]
                    for item in orders
                ]
            ),
        }
        broker_completed_at = _utc_clock(dependencies.clock)
        schedule = _target_session(dependencies.session_authority, broker_completed_at)
        identity = ReadinessIdentity(
            source_head=source.head,
            source_tree=source.tree,
            config_digest=CONFIGURATION_SHA256,
            account_fingerprint=account_fingerprint,
            target_session=schedule.session_date.isoformat(),
        )
        ownership = _ownership_from_durable_state(
            durable_state, target_session=identity.target_session
        )
        recovery_material = {
            "schema": "arch147-q62-recovery-evidence/v1",
            "identity": _identity_material(identity),
            "durable_journal_sha256": durable_state.journal_hash,
            "ownership_sha256": _ownership_digest(ownership),
            "broker_material_sha256": _canonical_digest(broker_material),
            "observed_position": str(observed_quantity),
            "working_order_count": len(unresolved_orders),
            "unresolved_effect": bool(unresolved_orders),
        }
        recovery_digest = _canonical_digest(recovery_material)
        recovery_observation = RecoveryObservation(
            identity=identity,
            evidence_sha256=recovery_digest,
            observed_at=broker_completed_at,
            valid_until=broker_completed_at + _ACCOUNT_TTL,
            position_quantity=observed_quantity,
            working_order_count=len(unresolved_orders),
            unresolved_effect=bool(unresolved_orders),
        )

        ledger.alpaca_provider_construction_attempts += 1
        provider = dependencies.signal_provider_builder(ledger)
        snapshot_method = getattr(provider, "snapshot", None)
        if not callable(snapshot_method):
            raise _ObserverBlocked("Q62_ALPACA_PROVIDER_INVALID")
        ledger.alpaca_snapshot_attempts += 1
        ledger.alpaca_credential_scope_attempts = None
        ledger.alpaca_provider_call_attempts = None
        ledger.alpaca_transport_factory_attempts = None
        try:
            signal_snapshot = snapshot_method(broker_completed_at)
        except Exception:
            raise _ObserverBlocked("Q62_ALPACA_OBSERVATION_BLOCKED") from None
        if type(signal_snapshot) is not RuntimeSignalSnapshot:
            raise _ObserverBlocked("Q62_ALPACA_OBSERVATION_INVALID")
        ledger.alpaca_credential_scope_attempts = signal_snapshot.credential_read_count
        ledger.alpaca_provider_call_attempts = signal_snapshot.provider_call_count
        ledger.alpaca_transport_factory_attempts = signal_snapshot.provider_call_count
        inputs = signal_snapshot.inputs_for_trading
        if (
            signal_snapshot.status != "READY"
            or signal_snapshot.stale
            or type(inputs) is not CompletedSignalInputs
        ):
            raise _ObserverBlocked("Q62_ALPACA_SIGNAL_NOT_FRESH")
        if (
            inputs.symbol != "SPY"
            or inputs.price_basis != "ALPACA_ALL_ADJUSTED_PRICE_V1"
            or inputs.selected_sessions != signal_snapshot.selected_sessions
            or len(inputs.sessions) != 60
            or len(inputs.closes) != 60
        ):
            raise _ObserverBlocked("Q62_ALPACA_SIGNAL_IDENTITY_INVALID")
        final_source = dependencies.source_admitter()
        if final_source != source:
            raise _ObserverBlocked("Q62_SOURCE_IDENTITY_UNSTABLE")
        evaluation_as_of = _utc_clock(dependencies.clock)
        if evaluation_as_of > schedule.closes_at:
            raise _ObserverBlocked("Q62_SESSION_EXPIRED_DURING_OBSERVATION")

        capability_admission = admission
        capability = capability_admission.capability_report
        proofs = _derive_proofs(
            identity=identity,
            source=source,
            account=account,
            capability_admission=capability_admission,
            ownership=ownership,
            durable_state=durable_state,
            schedule=schedule,
            inputs=inputs,
            recovery_observation=recovery_observation,
            source_observed_at=evaluation_as_of,
            account_observed_at=account_observed_at,
            capability_observed_at=capability_observed_at,
            state_observed_at=state_observed_at,
            signal_observed_at=inputs.as_of,
        )
        recovery = reconcile_read_only(
            identity,
            ownership,
            recovery_observation,
            as_of=evaluation_as_of,
        )
        bundle = Q62EvidenceBundle(
            identity=identity,
            proofs=proofs,
            capability=capability,
            ownership=ownership,
            signal_inputs=inputs,
            recovery=recovery,
        )
        historical = evaluate_q62_readiness(bundle, as_of=evaluation_as_of)
        prototype = evaluate_q62_tiny_live_readiness(
            bundle,
            as_of=evaluation_as_of,
            composite=composite,
            consumed_l41_bytes=l41_bytes,
            consumed_l41r5_bytes=l41r5_bytes,
        )
        if (
            prototype.status
            is TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY
            and (
                historical.status is not Q62Status.BLOCKED
                or historical.blockers != (Q62Blocker.CAPABILITY_UNPROVEN,)
            )
        ):
            raise _ObserverBlocked("Q62_HISTORICAL_EVALUATOR_DRIFT")
        status = prototype.status.value
        reason = (
            "Q62_READ_ONLY_PREREQUISITES_PROVEN"
            if prototype.status
            is TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY
            else "Q62_READ_ONLY_PREREQUISITES_BLOCKED"
        )
        ledger.evidence_write_attempts += 1
        evidence = _evidence_material(
            attempt_id=evidence_path.name.removeprefix(
                "arch147-q62-tiny-live-readiness-"
            ),
            status=status,
            reason=reason,
            source=source,
            identity=identity,
            account=account,
            admission=capability_admission,
            ownership=ownership,
            durable_state=durable_state,
            schedule=schedule,
            inputs=inputs,
            signal_snapshot=signal_snapshot,
            broker_material=broker_material,
            recovery=recovery,
            historical=historical,
            prototype=prototype,
            proofs=proofs,
            ledger=ledger,
            evaluation_as_of=evaluation_as_of,
        )
        try:
            _write_evidence_once(evidence_path, evidence)
        except _ObserverBlocked:
            return _blocked_result(
                "Q62_EVIDENCE_WRITE_FAILED", ledger, evidence_path=evidence_path
            )
        return _CompletedObservation(
            status, reason, evidence, evidence_path, historical, prototype
        )
    except _ObserverBlocked as error:
        result = _blocked_result(error.code, ledger, evidence_path=evidence_path)
    except Exception:
        result = _blocked_result(
            "Q62_OBSERVATION_INDETERMINATE", ledger, evidence_path=evidence_path
        )
    if evidence_path is not None:
        try:
            ledger.evidence_write_attempts += 1
            _write_evidence_once(
                evidence_path,
                {**result.evidence, "attempts": ledger.material()},
            )
            result = _CompletedObservation(
                result.status,
                result.reason,
                {**result.evidence, "attempts": ledger.material()},
                evidence_path,
                result.historical_report,
                result.prototype_report,
            )
        except Exception:
            return _blocked_result(
                "Q62_EVIDENCE_WRITE_FAILED", ledger, evidence_path=evidence_path
            )
    return result


def _utc_clock(clock: Callable[[], datetime]) -> datetime:
    try:
        value = clock()
    except Exception:
        raise _ObserverBlocked("Q62_CLOCK_UNAVAILABLE") from None
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise _ObserverBlocked("Q62_CLOCK_INVALID")
    return value.astimezone(UTC)


def _target_session(authority: object, as_of: datetime) -> object:
    schedule_for = getattr(authority, "schedule_for", None)
    if not callable(schedule_for):
        raise _ObserverBlocked("Q62_SESSION_AUTHORITY_INVALID")
    start = as_of.astimezone(UTC).date()
    for offset in range(0, 370):
        candidate = start + timedelta(days=offset)
        try:
            schedule = schedule_for(candidate)
        except Exception:
            raise _ObserverBlocked("Q62_SESSION_AUTHORITY_UNAVAILABLE") from None
        if schedule is not None and schedule.closes_at > as_of:
            if (
                type(schedule.session_date) is not date
                or schedule.opens_at.tzinfo is None
                or schedule.closes_at.tzinfo is None
                or schedule.opens_at >= schedule.closes_at
            ):
                raise _ObserverBlocked("Q62_SESSION_SCHEDULE_INVALID")
            return schedule
    raise _ObserverBlocked("Q62_SESSION_UNAVAILABLE")


def _read_pages(
    read: Callable[[Mapping[str, object]], Mapping[str, object]],
    arguments: dict[str, object],
    key: str,
    *,
    max_pages: int,
    max_rows: int,
    page_counter: str,
    ledger: _AttemptLedger,
) -> tuple[object, ...]:
    rows: list[object] = []
    seen: set[str] = set()
    request = dict(arguments)
    for _ in range(max_pages):
        setattr(ledger, page_counter, getattr(ledger, page_counter) + 1)
        try:
            payload = data(read(request))
        except Exception:
            raise _ObserverBlocked("Q62_ROBINHOOD_READ_FAILED") from None
        items = payload.get(key)
        if not isinstance(items, list) or len(rows) + len(items) > max_rows:
            raise _ObserverBlocked("Q62_ROBINHOOD_COLLECTION_INVALID")
        rows.extend(items)
        cursor = payload.get("next")
        if cursor is None or cursor == "":
            return tuple(rows)
        if (
            type(cursor) is not str
            or not cursor
            or len(cursor) > 4096
            or cursor in seen
        ):
            raise _ObserverBlocked("Q62_ROBINHOOD_CURSOR_INVALID")
        seen.add(cursor)
        request = {**arguments, "cursor": cursor}
    raise _ObserverBlocked("Q62_ROBINHOOD_PAGE_BOUND_EXCEEDED")


def _ownership_from_durable_state(
    state: DurableState, *, target_session: str | None
) -> OwnershipSnapshot:
    if type(state) is not DurableState:
        raise _ObserverBlocked("Q62_STATE_INVALID")
    entry, exit_order = state.entry, state.exit
    pristine = (
        state.last_sequence == 0
        and state.baseline_quantity == _ZERO
        and entry is None
        and exit_order is None
        and state.blocked_reason is None
        and not state.reconciled
    )
    uncertain = any(
        order is not None
        and order.status in {IntentStatus.MAY_HAVE_OCCURRED, IntentStatus.UNKNOWN}
        for order in (entry, exit_order)
    )
    active = tuple(
        order
        for order in (entry, exit_order)
        if order is not None
        and order.status
        in {
            IntentStatus.RESERVED,
            IntentStatus.MAY_HAVE_OCCURRED,
            IntentStatus.UNKNOWN,
            IntentStatus.WORKING,
            IntentStatus.PARTIAL,
        }
    )
    pending = active[0] if len(active) == 1 else None
    disposition = (
        EffectDisposition.NO_EFFECT
        if entry is None and exit_order is None
        else EffectDisposition.MAY_HAVE_OCCURRED
        if uncertain
        else EffectDisposition.CONFIRMED
    )
    return OwnershipSnapshot(
        account_fingerprint=state.identity.account_fingerprint,
        symbol=state.identity.symbol,
        strategy=state.identity.strategy,
        source_head=state.identity.source_head,
        source_tree=state.identity.source_tree,
        config_digest=state.identity.config_digest,
        binding_digest=state.identity.binding_digest,
        lifecycle_id=state.identity.lifecycle_id,
        target_session=target_session,
        lifecycle=Lifecycle.DISARMED if pristine else Lifecycle.UNKNOWN,
        effect_disposition=disposition,
        baseline_quantity=state.baseline_quantity,
        cumulative_bought=_ZERO if entry is None else entry.cumulative_quantity,
        cumulative_sold=_ZERO if exit_order is None else exit_order.cumulative_quantity,
        cumulative_entry_filled_dollars=_ZERO
        if entry is None
        else entry.cumulative_notional,
        entry_reserved_dollars=state.entry_reserved_dollars,
        working_remainder=(_ZERO if pending is None else pending.working_remainder),
        entries_used=state.entries_used,
        exits_used=state.exits_used,
        entry_local_intent_id=None if entry is None else entry.intent_id,
        entry_provider_order_id=None if entry is None else entry.provider_order_id,
        exit_local_intent_id=None if exit_order is None else exit_order.intent_id,
        exit_provider_order_id=None
        if exit_order is None
        else exit_order.provider_order_id,
        pending_intent_id=None if pending is None else pending.intent_id,
        pending_kind=(
            None if pending is None else OwnershipIntentKind(pending.kind.value)
        ),
        pending_requested_dollars=(
            _ZERO
            if pending is None or pending.requested_dollars is None
            else pending.requested_dollars
        ),
        pending_requested_quantity=(
            _ZERO
            if pending is None or pending.requested_quantity is None
            else pending.requested_quantity
        ),
    )


def _is_pristine_initial_state(state: DurableState) -> bool:
    return (
        type(state) is DurableState
        and state.last_sequence == 0
        and state.baseline_quantity == _ZERO
        and state.entry is None
        and state.exit is None
        and state.blocked_reason is None
        and not state.reconciled
    )


def _identity_material(identity: ReadinessIdentity) -> dict[str, str]:
    return {
        "source_head": identity.source_head,
        "source_tree": identity.source_tree,
        "config_digest": identity.config_digest,
        "account_fingerprint": identity.account_fingerprint,
        "target_session": identity.target_session,
    }


def _ownership_digest(snapshot: OwnershipSnapshot) -> str:
    return _canonical_digest(
        {
            "account_fingerprint": snapshot.account_fingerprint,
            "source_head": snapshot.source_head,
            "source_tree": snapshot.source_tree,
            "config_digest": snapshot.config_digest,
            "binding_digest": snapshot.binding_digest,
            "lifecycle_id": snapshot.lifecycle_id,
            "target_session": snapshot.target_session,
            "lifecycle": snapshot.lifecycle.value,
            "effect_disposition": snapshot.effect_disposition.value,
            "baseline_quantity": str(snapshot.baseline_quantity),
            "cumulative_bought": str(snapshot.cumulative_bought),
            "cumulative_sold": str(snapshot.cumulative_sold),
            "entry_reserved_dollars": str(snapshot.entry_reserved_dollars),
            "working_remainder": str(snapshot.working_remainder),
            "entries_used": snapshot.entries_used,
            "exits_used": snapshot.exits_used,
            "pending_intent_id": snapshot.pending_intent_id,
            "pending_kind": None
            if snapshot.pending_kind is None
            else snapshot.pending_kind.value,
        }
    )


def _derive_proofs(
    *,
    identity: ReadinessIdentity,
    source: _SourceAdmission,
    account: AgenticAccountIdentity,
    capability_admission: TinyLivePrototypeCapabilityAdmission,
    ownership: OwnershipSnapshot,
    durable_state: DurableState,
    schedule: object,
    inputs: object,
    recovery_observation: RecoveryObservation,
    source_observed_at: datetime,
    account_observed_at: datetime,
    capability_observed_at: datetime,
    state_observed_at: datetime,
    signal_observed_at: datetime,
) -> tuple[FreshProof, ...]:
    session_material = {
        "session_date": schedule.session_date.isoformat(),
        "opens_at": schedule.opens_at.isoformat(),
        "closes_at": schedule.closes_at.isoformat(),
        "authority": "NYSE_PUBLISHED_REGULAR_SESSION_MANIFEST",
    }
    proofs = (
        FreshProof(
            ProofKind.SOURCE,
            ProofStatus.PROVEN,
            _canonical_digest(source.material()),
            source_observed_at,
            schedule.closes_at,
            identity,
        ),
        FreshProof(
            ProofKind.CONFIGURATION,
            ProofStatus.PROVEN,
            _canonical_digest(
                {
                    "configuration_sha256": CONFIGURATION_SHA256,
                    "binding_sha256": BINDING_SHA256,
                    "policy_sha256": TINY_LIVE_POLICY.canonical_sha256(),
                    "configuration_material": dict(_CONFIGURATION_MATERIAL),
                    "binding_material": dict(_BINDING_MATERIAL),
                }
            ),
            source_observed_at,
            schedule.closes_at,
            identity,
        ),
        FreshProof(
            ProofKind.ACCOUNT,
            ProofStatus.PROVEN,
            _canonical_digest(
                {
                    "account_fingerprint": account.fingerprint,
                    "observed_account_count": account.observed_account_count,
                    "eligible_account_count": account.eligible_account_count,
                }
            ),
            account_observed_at,
            account_observed_at + _ACCOUNT_TTL,
            identity,
        ),
        FreshProof(
            ProofKind.CAPABILITY,
            ProofStatus.PROVEN,
            capability_admission.admission_digest,
            capability_observed_at,
            schedule.closes_at,
            identity,
        ),
        FreshProof(
            ProofKind.OWNERSHIP,
            ProofStatus.PROVEN,
            _canonical_digest(
                {
                    "durable_journal_sha256": durable_state.journal_hash,
                    "durable_sequence": durable_state.last_sequence,
                    "ownership_sha256": _ownership_digest(ownership),
                }
            ),
            state_observed_at,
            state_observed_at + _ACCOUNT_TTL,
            identity,
        ),
        FreshProof(
            ProofKind.BUDGET,
            ProofStatus.PROVEN,
            _canonical_digest(
                {
                    "entry_budget": "10.00",
                    "budget_remaining": str(ownership.budget_remaining),
                    "entry_reserved_dollars": str(ownership.entry_reserved_dollars),
                    "entries_used": ownership.entries_used,
                    "exits_used": ownership.exits_used,
                    "cumulative_bought": str(ownership.cumulative_bought),
                    "cumulative_sold": str(ownership.cumulative_sold),
                }
            ),
            state_observed_at,
            state_observed_at + _ACCOUNT_TTL,
            identity,
        ),
        FreshProof(
            ProofKind.SESSION,
            ProofStatus.PROVEN,
            _canonical_digest(session_material),
            source_observed_at,
            schedule.closes_at,
            identity,
        ),
        FreshProof(
            ProofKind.SIGNAL_INPUTS,
            ProofStatus.PROVEN,
            inputs.digest,
            signal_observed_at,
            schedule.closes_at,
            identity,
        ),
        FreshProof(
            ProofKind.RECOVERY,
            ProofStatus.PROVEN,
            recovery_observation.evidence_sha256,
            recovery_observation.observed_at,
            recovery_observation.valid_until,
            identity,
        ),
    )
    if tuple(item.kind for item in proofs) != tuple(ProofKind):
        raise _ObserverBlocked("Q62_PROOF_INVENTORY_INVALID")
    return proofs


def _evidence_material(
    *,
    attempt_id: str,
    status: str,
    reason: str,
    source: _SourceAdmission,
    identity: ReadinessIdentity,
    account: AgenticAccountIdentity,
    admission: TinyLivePrototypeCapabilityAdmission,
    ownership: OwnershipSnapshot,
    durable_state: DurableState,
    schedule: object,
    inputs: object,
    signal_snapshot: RuntimeSignalSnapshot,
    broker_material: dict[str, object],
    recovery: RecoveryReport,
    historical: object,
    prototype: TinyLiveReadinessReport,
    proofs: tuple[FreshProof, ...],
    ledger: _AttemptLedger,
    evaluation_as_of: datetime,
) -> dict[str, object]:
    del account
    return {
        "schema": OBSERVATION_SCHEMA,
        "attempt_id": attempt_id,
        "status": status,
        "reason": reason,
        "source": source.material(),
        "identity": _identity_material(identity),
        "configuration_sha256": CONFIGURATION_SHA256,
        "binding_sha256": BINDING_SHA256,
        "policy_sha256": TINY_LIVE_POLICY.canonical_sha256(),
        "configuration": dict(_CONFIGURATION_MATERIAL),
        "binding": dict(_BINDING_MATERIAL),
        "account_fingerprint": identity.account_fingerprint,
        "target_session": {
            "date": schedule.session_date.isoformat(),
            "opens_at": schedule.opens_at.isoformat(),
            "closes_at": schedule.closes_at.isoformat(),
            "authority": "NYSE_PUBLISHED_REGULAR_SESSION_MANIFEST",
        },
        "capability": {
            "admission_sha256": admission.admission_digest,
            "historical_capability_status": admission.capability_report.status.value,
            "consumed_l41_sha256": admission.consumed_l41_sha256,
            "consumed_l41r5_sha256": admission.consumed_l41r5_sha256,
        },
        "proofs": [
            {
                "kind": proof.kind.value,
                "status": proof.status.value,
                "evidence_sha256": proof.evidence_sha256,
                "observed_at": proof.observed_at.isoformat(),
                "valid_until": proof.valid_until.isoformat(),
                "identity": _identity_material(proof.identity),
            }
            for proof in proofs
        ],
        "ownership": {
            "journal_sha256": durable_state.journal_hash,
            "sequence": durable_state.last_sequence,
            "lifecycle": ownership.lifecycle.value,
            "effect_disposition": ownership.effect_disposition.value,
            "baseline_quantity": str(ownership.baseline_quantity),
            "owned_quantity": str(ownership.owned_quantity),
            "entry_reserved_dollars": str(ownership.entry_reserved_dollars),
            "budget_remaining": str(ownership.budget_remaining),
            "entries_used": ownership.entries_used,
            "exits_used": ownership.exits_used,
            "cumulative_bought": str(ownership.cumulative_bought),
            "cumulative_sold": str(ownership.cumulative_sold),
            "entry_provider_order_id_present": ownership.entry_provider_order_id
            is not None,
            "exit_provider_order_id_present": ownership.exit_provider_order_id
            is not None,
            "pending_intent_present": ownership.pending_intent_id is not None,
            "working_remainder": str(ownership.working_remainder),
        },
        "signal": {
            "status": signal_snapshot.status,
            "reason": signal_snapshot.reason.value,
            "stale": signal_snapshot.stale,
            "refreshed": signal_snapshot.refreshed,
            "symbol": inputs.symbol,
            "price_basis": inputs.price_basis,
            "timeframe": "1Day",
            "adjustment": "all",
            "feed": "sip",
            "currency": "USD",
            "fallback": False,
            "session_count": len(inputs.sessions),
            "first_session": inputs.sessions[0].isoformat(),
            "last_session": inputs.sessions[-1].isoformat(),
            "input_sha256": inputs.digest,
            "source_body_sha256": inputs.source_digest,
            "as_of": inputs.as_of.isoformat(),
            "cutoff": inputs.cutoff.isoformat(),
            "credential_read_count": signal_snapshot.credential_read_count,
            "provider_call_count": signal_snapshot.provider_call_count,
        },
        "broker": broker_material,
        "recovery": {
            "status": recovery.status.value,
            "blockers": [item.value for item in recovery.blockers],
            "evidence_sha256": recovery.evidence_sha256,
            "observed_position": None
            if recovery.observed_position is None
            else str(recovery.observed_position),
            "working_order_count": recovery.working_order_count,
            "observed_at": None
            if recovery.observed_at is None
            else recovery.observed_at.isoformat(),
            "valid_until": None
            if recovery.valid_until is None
            else recovery.valid_until.isoformat(),
        },
        "historical_q62": {
            "status": historical.status.value,
            "blockers": [item.value for item in historical.blockers],
        },
        "prototype_q62": {
            "status": prototype.status.value,
            "blockers": [item.value for item in prototype.blockers],
            "provider_mutation_count": prototype.provider_mutation_count,
            "live_readiness_granted": False,
            "trade_authority_granted": False,
        },
        "evaluation_as_of": evaluation_as_of.isoformat(),
        "attempts": ledger.material(),
        "read_bounds": {
            "robinhood_accounts_calls": 1,
            "robinhood_accounts_max_rows": _MAX_ACCOUNTS,
            "robinhood_position_pages": _MAX_POSITION_PAGES,
            "robinhood_position_max_rows": _MAX_POSITIONS,
            "robinhood_order_pages": _MAX_ORDER_PAGES,
            "robinhood_order_max_rows": _MAX_ORDERS,
            "robinhood_sessions": 1 + _MAX_POSITION_PAGES + _MAX_ORDER_PAGES,
            "robinhood_tools_list_pages_per_session": 20,
            "robinhood_tools_list_pages_total": 20
            * (1 + _MAX_POSITION_PAGES + _MAX_ORDER_PAGES),
            "alpaca_snapshot_attempts": 1,
            "alpaca_credential_scopes": 1,
            "alpaca_provider_calls": 1,
            "alpaca_transport_factories": 1,
        },
        "provider_mutation_count": 0,
        "live_readiness_granted": False,
        "trade_authority_granted": False,
    }


def _blocked_result(
    reason: str, ledger: _AttemptLedger, *, evidence_path: Path | None
) -> _CompletedObservation:
    return _CompletedObservation(
        "BLOCKED",
        reason,
        {
            "schema": OBSERVATION_SCHEMA,
            "status": "BLOCKED",
            "reason": reason,
            "proofs": [],
            "attempts": ledger.material(),
            "provider_mutation_count": 0,
            "live_readiness_granted": False,
            "trade_authority_granted": False,
        },
        evidence_path,
        None,
        None,
    )


def _write_evidence_once(destination: Path, material: dict[str, object]) -> None:
    try:
        if (
            destination.parent != EVIDENCE_ROOT
            or not destination.is_dir()
            or destination.is_symlink()
            or _is_reparse_point(destination)
            or destination.joinpath("evidence.json").exists()
        ):
            raise _ObserverBlocked("Q62_EVIDENCE_PATH_INVALID")
        _reject_reparse_ancestors(destination, stop=EVIDENCE_ROOT)
        text = _canonical_json_text(material) + "\n"
        with destination.joinpath("evidence.json").open(
            "x", encoding="ascii", newline="\n"
        ) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
    except _ObserverBlocked:
        raise
    except Exception:
        raise _ObserverBlocked("Q62_EVIDENCE_WRITE_FAILED") from None


def _dependencies_for_test(
    *,
    source_admitter: Callable[[], _SourceAdmission],
    evidence_destination: Callable[[], Path],
    state_root: Path,
    artifact_loader: Callable[[], tuple[bytes, bytes, L41R6CompositeReport]],
    robinhood_builder: Callable[[_AttemptLedger], _ReadBoundary],
    signal_provider_builder: Callable[[_AttemptLedger], object],
    clock: Callable[[], datetime],
    session_authority: object,
) -> _Dependencies:
    """Private fake-only seam; the command line exposes none of these values."""
    return _Dependencies(
        source_admitter,
        evidence_destination,
        state_root,
        artifact_loader,
        robinhood_builder,
        signal_provider_builder,
        clock,
        session_authority,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m trading_bot.live_prototype.tiny_live_readiness_observer",
        allow_abbrev=False,
        description=(
            "Run one source-admitted read-only Q62 observation or prepare its "
            "fixed local state."
        ),
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("observe", help="perform one bounded read-only Q62 attempt")
    commands.add_parser(
        "prepare-state", help="create the fixed initial durable journal once"
    )
    arguments = parser.parse_args(argv)
    if arguments.command is None:
        parser.error("choose observe or prepare-state")
    result = observe_q62() if arguments.command == "observe" else prepare_state()
    print(f"status={result.status} reason={result.reason}")
    if result.evidence_path is not None:
        print(f"evidence_directory={result.evidence_path}")
    return (
        0
        if result.status
        in {"PREPARED", TinyLiveReadinessStatus.READY_FOR_L43_PROTOTYPE_READ_ONLY.value}
        else 2
    )


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "BINDING_SHA256",
    "CONFIGURATION_SHA256",
    "EVIDENCE_ROOT",
    "LIVE_STATE_ROOT",
    "OBSERVATION_SCHEMA",
    "main",
    "observe_q62",
    "prepare_state",
]
