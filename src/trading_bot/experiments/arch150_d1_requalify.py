"""Offline sparse custody requalification for the consumed Arch150 D1 attempt.

The public entry point is pinned to the one retained D1 attempt and performs
read-only input validation before creating a fresh output directory. It has no
provider, credential, broker, Robinhood, or strategy execution boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final
from uuid import UUID, uuid5

from trading_bot.experiments import arch150_intraday_data as data
from trading_bot.experiments.arch150_intraday_data import (
    Arch150DataError,
    Arch150HistoricalRequest,
    RawPageCommitment,
    expected_regular_minute_slots,
    parse_alpaca_page,
    published_session_authority,
    session_authority_commitment,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

ATTEMPT_ID: Final = "a8d5975b-a3e9-4917-a8a8-2809e191fa20"
ATTEMPT_DIRECTORY: Final = Path(
    r"F:\AI\research-data\arch150-intraday-data-custody"
    r"\arch150-d1-a8d5975b-a3e9-4917-a8a8-2809e191fa20"
)
FEATURE_BRANCH: Final = "feature/research-arch150-intraday-ai-current"
ORIGINAL_SOURCE_HEAD: Final = "50c5ed6204e909534778b07534fee7217117e47e"
ORIGINAL_SOURCE_TREE: Final = "f53588f74266b3ef054ca49f9ea5c8a29e24d630"
ORIGINAL_LIVE_FEATURE_HEAD: Final = ORIGINAL_SOURCE_HEAD
ORIGINAL_LIVE_DEVELOP_HEAD: Final = ORIGINAL_SOURCE_HEAD
ORIGINAL_DENSE_DATASET_ID: Final = "6085afed-b870-59d7-9c0d-407db940777b"
ORIGINAL_DENSE_DATASET_SHA256: Final = (
    "70bf65d5b5c8726285215ed8337ae06bfaac8371cdb07b5dfd625ed800a96e23"
)
ORIGINAL_CUSTODY_ID: Final = "c0276e43-7533-5af4-9dbe-bb7e9095e693"
ORIGINAL_CUSTODY_SEMANTIC_SHA256: Final = (
    "d10a9eac514fe1c9a2e13f3ea6910e33d770b1397d9e56b29ac71e4c70543893"
)
ORIGINAL_ARTIFACTS: Final = {
    "attempt.json": (
        427,
        "b1e6e3069c36d32a9d828d84526cc555a9dbc22c4f1ae1fac0760274aa48725b",
    ),
    "custody-evidence.json": (
        453326,
        "b83ced21f58cc1aa4731b2e72c1cf8cba4fb7d24378b0f206b303583bc658267",
    ),
    "attempt-result.json": (
        588,
        "b579e1617df02d05d909281b90c746c9d23bcdfd968395d36fb0f4f94b64585b",
    ),
}
ORIGINAL_SYMBOL_FACTS: Final = {
    "SPY": {
        "pages": 158,
        "raw_bars": 1_577_355,
        "observed": 781_876,
        "missing": 104,
        "off_session": 795_479,
    },
    "QQQ": {
        "pages": 148,
        "raw_bars": 1_474_748,
        "observed": 781_865,
        "missing": 115,
        "off_session": 692_883,
    },
}
EXPECTED_CREDENTIAL_READS: Final = 1
EXPECTED_PROVIDER_REQUESTS: Final = 306
EXPECTED_SUCCESSFUL_PAGES: Final = 306
EXPECTED_FAILURE: Final = "MISSING_EXPECTED_SLOT"
EXPECTED_CLASSIFICATION: Final = "BLOCKED"
OUTPUT_CLASSIFICATION: Final = "OFFLINE_SPARSE_CUSTODY_READY_FOR_INDEPENDENT_REVIEW"
DATASET_SCHEMA: Final = "arch150-intraday-sparse-custody-dataset/v1"
CUSTODY_SCHEMA: Final = "arch150-intraday-sparse-custody-evidence/v1"
EVIDENCE_SCHEMA: Final = "arch150-d1-offline-requalification-evidence/v1"
NO_FILL_SEMANTICS: Final = {
    "missing_slot": "ABSENCE_ONLY",
    "forward_fill": False,
    "backfill": False,
    "interpolation": False,
    "synthetic_ohlcv": False,
    "cross_symbol_substitution": False,
}
ZERO_EFFECTS: Final = {
    "credential_reads": 0,
    "network_calls": 0,
    "provider_calls": 0,
    "robinhood_calls": 0,
    "broker_calls": 0,
    "order_mutations": 0,
    "production_state_mutations": 0,
    "strategy_pnl_evaluations": 0,
    "holdout_accesses": 0,
    "extension_accesses": 0,
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_DATASET_NAMESPACE = UUID("cfb39a52-9ab3-5fc4-9f10-493c51e34c71")
_CUSTODY_NAMESPACE = UUID("c44badf6-813d-5de9-a0d5-0a33c7988df2")
_EVIDENCE_NAMESPACE = UUID("f1bd170d-7ef5-5de3-8bd9-9f782eaab57c")
_CSV_HEADER = b"timestamp,symbol,resolution,open,high,low,close,volume\n"


class Arch150D1RequalificationError(ValueError):
    """Sanitized fail-closed reason without retained provider payloads."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RequalificationResult:
    classification: str
    dataset_identity: str
    dataset_sha256: str
    custody_identity: str
    custody_sha256: str
    evidence_identity: str
    evidence_sha256: str
    output_directory: Path


@dataclass(frozen=True, slots=True)
class _ExpectedAttempt:
    attempt_id: str
    attempt_root: Path
    source_head: str
    source_tree: str
    live_feature_head: str
    live_develop_head: str
    dense_dataset_identity: str
    dense_dataset_sha256: str
    custody_identity: str
    custody_semantic_sha256: str
    artifact_facts: tuple[tuple[str, int, str], ...]
    credential_reads: int
    provider_requests: int
    successful_pages: int
    failure_code: str
    classification: str
    symbol_facts: tuple[tuple[str, tuple[tuple[str, object], ...]], ...]


@dataclass(frozen=True, slots=True)
class _SourceIdentity:
    branch: str
    head: str
    tree: str


@dataclass(slots=True)
class _SymbolScan:
    symbol: str
    page_count: int
    raw_bar_count: int
    observed_count: int
    off_session_count: int
    missing_count: int
    missing_hash: object
    missing_bitmap: bytearray
    normalized: bytearray
    discovery_hash: object
    validation_hash: object
    discovery_count: int
    validation_count: int
    first_observed: str | None
    last_observed: str | None


def requalify_arch150_d1(output_directory: Path) -> RequalificationResult:
    """Requalify the pinned retained attempt without external effects."""

    source = _production_source_identity()
    expected = _production_expectation()
    return _requalify(
        expected=expected,
        output_directory=Path(output_directory),
        source=source,
        authority=published_session_authority(),
        schedule_start=data.DATA_START,
        schedule_end=data.DATA_END_EXCLUSIVE,
        private_test_root=None,
    )


def _requalify_arch150_d1_for_test(
    *,
    attempt_root: Path,
    output_directory: Path,
    expected: _ExpectedAttempt,
    source_head: str,
    source_tree: str,
    authority: object,
    schedule_start: date,
    schedule_end: date,
    test_root: Path,
) -> RequalificationResult:
    """Bounded synthetic fixture seam; never used by the production entry."""

    if expected.attempt_root != Path(attempt_root):
        raise Arch150D1RequalificationError("TEST_FIXTURE_ROOT_MISMATCH")
    return _requalify(
        expected=expected,
        output_directory=Path(output_directory),
        source=_SourceIdentity(FEATURE_BRANCH, source_head, source_tree),
        authority=authority,
        schedule_start=schedule_start,
        schedule_end=schedule_end,
        private_test_root=Path(test_root),
    )


def _production_expectation() -> _ExpectedAttempt:
    return _ExpectedAttempt(
        attempt_id=ATTEMPT_ID,
        attempt_root=ATTEMPT_DIRECTORY,
        source_head=ORIGINAL_SOURCE_HEAD,
        source_tree=ORIGINAL_SOURCE_TREE,
        live_feature_head=ORIGINAL_LIVE_FEATURE_HEAD,
        live_develop_head=ORIGINAL_LIVE_DEVELOP_HEAD,
        dense_dataset_identity=ORIGINAL_DENSE_DATASET_ID,
        dense_dataset_sha256=ORIGINAL_DENSE_DATASET_SHA256,
        custody_identity=ORIGINAL_CUSTODY_ID,
        custody_semantic_sha256=ORIGINAL_CUSTODY_SEMANTIC_SHA256,
        artifact_facts=tuple(
            (name, length, digest)
            for name, (length, digest) in ORIGINAL_ARTIFACTS.items()
        ),
        credential_reads=EXPECTED_CREDENTIAL_READS,
        provider_requests=EXPECTED_PROVIDER_REQUESTS,
        successful_pages=EXPECTED_SUCCESSFUL_PAGES,
        failure_code=EXPECTED_FAILURE,
        classification=EXPECTED_CLASSIFICATION,
        symbol_facts=tuple(
            (
                symbol,
                tuple((key, value) for key, value in facts.items()),
            )
            for symbol, facts in ORIGINAL_SYMBOL_FACTS.items()
        ),
    )


def _requalify(
    *,
    expected: _ExpectedAttempt,
    output_directory: Path,
    source: _SourceIdentity,
    authority: object,
    schedule_start: date,
    schedule_end: date,
    private_test_root: Path | None,
) -> RequalificationResult:
    _validate_source_identity(source)
    original_evidence, commitments = _validate_attempt(expected)
    _validate_output_directory(
        output_directory,
        attempt_root=expected.attempt_root,
        private_test_root=private_test_root,
    )
    try:
        schedule_identity, schedule_digest = session_authority_commitment(authority)
    except Arch150DataError as error:
        raise Arch150D1RequalificationError(error.code) from None
    sessions = _session_facts(authority, schedule_start, schedule_end)
    scans = _scan_raw_pages(
        expected,
        authority,
        schedule_start,
        schedule_end,
        sessions,
        commitments,
        original_evidence,
    )
    sparse = _combined_missing(
        scans,
        slot_stream_factory=lambda: iter(
            expected_regular_minute_slots(schedule_start, schedule_end, authority)
        ),
        sessions=sessions,
    )
    material = _identity_material(
        expected=expected,
        source=source,
        authority=authority,
        schedule_identity=schedule_identity,
        schedule_digest=schedule_digest,
        schedule_start=schedule_start,
        schedule_end=schedule_end,
        scans=scans,
        sparse=sparse,
        original_evidence=original_evidence,
        commitments=commitments,
        scheduled_slot_count=sessions["_scheduled_slot_count"],
    )
    dataset_id, dataset_hash = _versioned_identity(
        DATASET_SCHEMA, material, _DATASET_NAMESPACE
    )
    custody_material = {
        "version": "arch150-intraday-sparse-custody-identity/v1",
        "dataset_identity": dataset_id,
        "dataset_sha256": dataset_hash,
        "attempt_id": expected.attempt_id,
        "original_custody_identity": expected.custody_identity,
        "original_custody_semantic_sha256": expected.custody_semantic_sha256,
        "ordered_raw_page_commitments": material["ordered_raw_page_commitments"],
        "raw_page_sha256_by_symbol": material["raw_page_sha256_by_symbol"],
        "source": material["requalification_source"],
        "effects": dict(ZERO_EFFECTS),
        "automatic_retry": "FORBIDDEN",
    }
    custody_id, custody_hash = _versioned_identity(
        CUSTODY_SCHEMA, custody_material, _CUSTODY_NAMESPACE
    )
    evidence_material = {
        "version": "arch150-d1-offline-requalification-identity/v1",
        "classification": OUTPUT_CLASSIFICATION,
        "dataset_identity": dataset_id,
        "dataset_sha256": dataset_hash,
        "custody_identity": custody_id,
        "custody_sha256": custody_hash,
        "attempt_id": expected.attempt_id,
        "original_dense_dataset": {
            "classification": "BLOCKED",
            "failure_code": expected.failure_code,
            "identity": expected.dense_dataset_identity,
            "sha256": expected.dense_dataset_sha256,
        },
        "original_custody_identity": expected.custody_identity,
        "original_custody_file_sha256": _expected_artifact_hash(
            expected, "custody-evidence.json"
        ),
        "source": material["requalification_source"],
        "effects": dict(ZERO_EFFECTS),
        "automatic_retry": "FORBIDDEN",
    }
    evidence_id, evidence_hash = _versioned_identity(
        EVIDENCE_SCHEMA, evidence_material, _EVIDENCE_NAMESPACE
    )
    outputs = {
        "dataset.json": _artifact(DATASET_SCHEMA, dataset_id, dataset_hash, material),
        "custody-evidence.json": _artifact(
            CUSTODY_SCHEMA, custody_id, custody_hash, custody_material
        ),
        "evidence.json": _artifact(
            EVIDENCE_SCHEMA, evidence_id, evidence_hash, evidence_material
        ),
        "normalized/SPY.csv": bytes(scans["SPY"].normalized),
        "normalized/QQQ.csv": bytes(scans["QQQ"].normalized),
    }
    _write_output_once(output_directory, outputs)
    return RequalificationResult(
        OUTPUT_CLASSIFICATION,
        dataset_id,
        dataset_hash,
        custody_id,
        custody_hash,
        evidence_id,
        evidence_hash,
        output_directory,
    )


def _validate_source_identity(source: _SourceIdentity) -> None:
    if (
        type(source.branch) is not str
        or source.branch != FEATURE_BRANCH
        or type(source.head) is not str
        or _SHA1.fullmatch(source.head) is None
        or type(source.tree) is not str
        or _SHA1.fullmatch(source.tree) is None
    ):
        raise Arch150D1RequalificationError("REQUALIFICATION_SOURCE_INVALID")


def _production_source_identity() -> _SourceIdentity:
    root = Path(__file__).resolve().parents[3]
    canonical = Path(r"F:\AI\worktrees\ai-trading-bot-arch150-intraday-ai-current")
    if not _same_path(root, canonical):
        raise Arch150D1RequalificationError("CANONICAL_WORKTREE_MISMATCH")
    branch = _git(root, "branch", "--show-current")
    head = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    origin = _git(root, "remote", "get-url", "origin")
    status = _git(root, "status", "--porcelain=v1")
    if (
        branch != FEATURE_BRANCH
        or origin.rstrip("/") != "https://github.com/callmedraken/ai-trading-bot.git"
        or status
    ):
        raise Arch150D1RequalificationError("REQUALIFICATION_SOURCE_NOT_ADMITTED")
    return _SourceIdentity(branch, head, tree)


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        raise Arch150D1RequalificationError(
            "REQUALIFICATION_SOURCE_UNAVAILABLE"
        ) from None
    return result.stdout.strip()


def _validate_attempt(
    expected: _ExpectedAttempt,
) -> tuple[dict[str, object], tuple[RawPageCommitment, ...]]:
    root = expected.attempt_root
    if root.name != f"arch150-d1-{expected.attempt_id}":
        raise Arch150D1RequalificationError("ATTEMPT_DIRECTORY_IDENTITY_MISMATCH")
    _require_directory(root, "ATTEMPT_DIRECTORY_INVALID")
    _require_entries(
        root, {"attempt.json", "custody-evidence.json", "attempt-result.json", "raw"}
    )
    expected_artifacts = {
        name: (length, digest) for name, length, digest in expected.artifact_facts
    }
    if set(expected_artifacts) != {
        "attempt.json",
        "custody-evidence.json",
        "attempt-result.json",
    }:
        raise Arch150D1RequalificationError("EXPECTED_ARTIFACT_MANIFEST_INVALID")
    if len(expected_artifacts) != len(expected.artifact_facts):
        raise Arch150D1RequalificationError("EXPECTED_ARTIFACT_MANIFEST_INVALID")
    artifact_bytes: dict[str, bytes] = {}
    artifact_values: dict[str, dict[str, object]] = {}
    for name in ("attempt.json", "custody-evidence.json", "attempt-result.json"):
        body = _read_regular_file(root / name, "ATTEMPT_ARTIFACT_INVALID")
        size, digest = expected_artifacts[name]
        if len(body) != size or _sha256(body) != digest:
            raise Arch150D1RequalificationError("ATTEMPT_ARTIFACT_COMMITMENT_MISMATCH")
        value = _parse_canonical_object(body, "ATTEMPT_ARTIFACT_JSON_INVALID")
        artifact_bytes[name] = body
        artifact_values[name] = value
    raw = root / "raw"
    _require_directory(raw, "RAW_DIRECTORY_INVALID")
    _require_entries(raw, set(data.INITIAL_UNIVERSE))
    attempt = artifact_values["attempt.json"]
    _require_exact_fields(
        attempt,
        {
            "schema",
            "attempt_id",
            "source_branch",
            "source_head",
            "source_tree",
            "live_feature_head",
            "live_develop_head",
            "automatic_retry",
        },
        "ATTEMPT_CLAIM_INVALID",
    )
    if attempt != {
        "schema": "arch150-data-attempt-claim/v1",
        "attempt_id": expected.attempt_id,
        "source_branch": FEATURE_BRANCH,
        "source_head": expected.source_head,
        "source_tree": expected.source_tree,
        "live_feature_head": expected.live_feature_head,
        "live_develop_head": expected.live_develop_head,
        "automatic_retry": "FORBIDDEN",
    }:
        raise Arch150D1RequalificationError("ATTEMPT_CLAIM_MISMATCH")
    evidence = artifact_values["custody-evidence.json"]
    _validate_original_evidence(evidence, expected)
    result = artifact_values["attempt-result.json"]
    _validate_attempt_result(result, expected, artifact_bytes["custody-evidence.json"])
    if (root / "normalized.csv").exists():
        raise Arch150D1RequalificationError("UNEXPECTED_NORMALIZED_ARTIFACT")
    raw_commitments = evidence.get("raw_page_commitments")
    if type(raw_commitments) is not list:
        raise Arch150D1RequalificationError("RAW_PAGE_MANIFEST_INVALID")
    grouped = _parse_commitments(raw_commitments)
    commitments = tuple(
        commitment for symbol in data.INITIAL_UNIVERSE for commitment in grouped[symbol]
    )
    descriptors = evidence.get("request_descriptors")
    if descriptors != [
        json.loads(page.request_descriptor_json) for page in commitments
    ]:
        raise Arch150D1RequalificationError("REQUEST_DESCRIPTOR_LIST_MISMATCH")
    if len(commitments) != expected.successful_pages:
        raise Arch150D1RequalificationError("RAW_PAGE_COUNT_MISMATCH")
    page_hashes = evidence.get("raw_page_sha256_by_symbol")
    if type(page_hashes) is not dict or set(page_hashes) != set(data.INITIAL_UNIVERSE):
        raise Arch150D1RequalificationError("RAW_PAGE_HASH_LIST_INVALID")
    if any(
        page_hashes[symbol] != [page.page_sha256 for page in grouped[symbol]]
        for symbol in data.INITIAL_UNIVERSE
    ):
        raise Arch150D1RequalificationError("RAW_PAGE_HASH_LIST_MISMATCH")
    for symbol in data.INITIAL_UNIVERSE:
        directory = raw / symbol
        _require_directory(directory, "RAW_SYMBOL_DIRECTORY_INVALID")
        expected_names = {
            f"{ordinal:04d}.bin" for ordinal in range(1, len(grouped[symbol]) + 1)
        }
        _require_entries(directory, expected_names)
    return evidence, commitments


def _validate_original_evidence(
    evidence: dict[str, object], expected: _ExpectedAttempt
) -> None:
    if evidence.get("schema") != data.ARCH150_CUSTODY_SCHEMA:
        raise Arch150D1RequalificationError("ORIGINAL_CUSTODY_SCHEMA_MISMATCH")
    if evidence.get("classification") != expected.classification:
        raise Arch150D1RequalificationError("ORIGINAL_CLASSIFICATION_MISMATCH")
    if evidence.get("failure_codes") != [expected.failure_code]:
        raise Arch150D1RequalificationError("ORIGINAL_FAILURE_MISMATCH")
    if evidence.get("identity") != expected.custody_identity:
        raise Arch150D1RequalificationError("ORIGINAL_CUSTODY_IDENTITY_MISMATCH")
    if evidence.get("sha256") != expected.custody_semantic_sha256:
        raise Arch150D1RequalificationError("ORIGINAL_CUSTODY_HASH_MISMATCH")
    if evidence.get("source") != {
        "head": expected.source_head,
        "tree": expected.source_tree,
    }:
        raise Arch150D1RequalificationError("ORIGINAL_SOURCE_MISMATCH")
    if evidence.get("dataset") != {
        "identity": expected.dense_dataset_identity,
        "sha256": expected.dense_dataset_sha256,
    }:
        raise Arch150D1RequalificationError("ORIGINAL_DENSE_DATASET_MISMATCH")
    if evidence.get("automatic_retry") != "FORBIDDEN":
        raise Arch150D1RequalificationError("ORIGINAL_RETRY_POLICY_MISMATCH")
    effects = evidence.get("effects")
    if type(effects) is not dict:
        raise Arch150D1RequalificationError("ORIGINAL_EFFECTS_INVALID")
    expected_effects = {
        "credential_read_attempt_count": expected.credential_reads,
        "provider_request_attempt_count": expected.provider_requests,
        "robinhood_calls": 0,
        "broker_calls": 0,
        "order_mutations": 0,
        "production_state_mutations": 0,
        "strategy_pnl_evaluations": 0,
        "holdout_accesses": 0,
        "extension_accesses": 0,
    }
    if effects != expected_effects:
        raise Arch150D1RequalificationError("ORIGINAL_EFFECTS_MISMATCH")
    _validate_evidence_diagnostics(evidence, expected)


def _validate_evidence_diagnostics(
    evidence: dict[str, object], expected: _ExpectedAttempt
) -> None:
    diagnostics = evidence.get("diagnostics_by_symbol")
    if (
        type(diagnostics) is not list
        or tuple(item.get("symbol") for item in diagnostics if type(item) is dict)
        != data.INITIAL_UNIVERSE
    ):
        raise Arch150D1RequalificationError("ORIGINAL_DIAGNOSTICS_INVALID")
    facts = {symbol: dict(values) for symbol, values in expected.symbol_facts}
    for item in diagnostics:
        if type(item) is not dict:
            raise Arch150D1RequalificationError("ORIGINAL_DIAGNOSTICS_INVALID")
        symbol = item.get("symbol")
        expected_values = facts[symbol]
        checks = {
            "raw_page_count": expected_values["pages"],
            "raw_bar_count": expected_values["raw_bars"],
            "raw_bar_count_known": True,
            "parsed_page_count": expected_values["pages"],
            "observed_regular_slot_bar_count": expected_values["observed"],
            "normalized_regular_bar_count": 0,
            "missing_expected_slot_count": expected_values["missing"],
            "off_session_excluded_count": expected_values["off_session"],
            "duplicate_expected_slot_count": 0,
            "duplicate_expected_slot_sha256": _sha256(b""),
            "malformed_bar_count": 0,
            "pagination_terminal_state": "NULL_TOKEN_EXHAUSTED",
            "failure_code": None,
        }
        if any(item.get(key) != value for key, value in checks.items()):
            raise Arch150D1RequalificationError("ORIGINAL_DIAGNOSTICS_MISMATCH")
        if not _is_sha256(item.get("missing_expected_slot_sha256")):
            raise Arch150D1RequalificationError("ORIGINAL_MISSING_COMMITMENT_INVALID")


def _validate_attempt_result(
    result: dict[str, object], expected: _ExpectedAttempt, evidence_body: bytes
) -> None:
    fields = {
        "schema": "arch150-data-operator-attempt-result/v1",
        "classification": expected.classification,
        "failure_code": expected.failure_code,
        "source_head": expected.source_head,
        "source_tree": expected.source_tree,
        "dataset_identity": expected.dense_dataset_identity,
        "dataset_sha256": expected.dense_dataset_sha256,
        "evidence_sha256": _sha256(evidence_body),
        "credential_read_attempt_count": expected.credential_reads,
        "provider_request_attempt_count": expected.provider_requests,
        "successful_page_count": expected.successful_pages,
        "automatic_retry": "FORBIDDEN",
    }
    if result != fields:
        raise Arch150D1RequalificationError("ATTEMPT_RESULT_MISMATCH")


def _parse_commitments(raw: list[object]) -> dict[str, list[RawPageCommitment]]:
    grouped = {symbol: [] for symbol in data.INITIAL_UNIVERSE}
    seen_symbol_transition: list[str] = []
    for item in raw:
        if type(item) is not dict:
            raise Arch150D1RequalificationError("RAW_PAGE_MANIFEST_INVALID")
        try:
            descriptor = item["request_descriptor"]
            if type(descriptor) is not dict or set(item) != {
                "schema",
                "ordinal",
                "symbol",
                "request_digest",
                "request_descriptor",
                "input_token_sha256",
                "page_sha256",
                "byte_length",
                "next_token_sha256",
                "terminal_state",
            }:
                raise ValueError
            if item["schema"] != data.ARCH150_RAW_PAGE_SCHEMA:
                raise ValueError
            commitment = RawPageCommitment(
                ordinal=item["ordinal"],
                symbol=item["symbol"],
                request_digest=item["request_digest"],
                request_descriptor_json=canonical_json_bytes(descriptor).decode(
                    "utf-8"
                ),
                input_token_sha256=item["input_token_sha256"],
                page_sha256=item["page_sha256"],
                byte_length=item["byte_length"],
                next_token_sha256=item["next_token_sha256"],
                terminal_state=item["terminal_state"],
            )
        except (KeyError, TypeError, ValueError, Arch150DataError):
            raise Arch150D1RequalificationError("RAW_PAGE_MANIFEST_INVALID") from None
        if (
            not seen_symbol_transition
            or seen_symbol_transition[-1] != commitment.symbol
        ):
            seen_symbol_transition.append(commitment.symbol)
        if seen_symbol_transition not in (["SPY"], ["SPY", "QQQ"]):
            raise Arch150D1RequalificationError("RAW_PAGE_SYMBOL_ORDER_INVALID")
        grouped[commitment.symbol].append(commitment)
    if tuple(seen_symbol_transition) != data.INITIAL_UNIVERSE:
        raise Arch150D1RequalificationError("RAW_PAGE_SYMBOL_ORDER_INVALID")
    for symbol in data.INITIAL_UNIVERSE:
        pages = grouped[symbol]
        if not pages or [page.ordinal for page in pages] != list(
            range(1, len(pages) + 1)
        ):
            raise Arch150D1RequalificationError("RAW_PAGE_ORDINAL_INVALID")
        if pages[-1].terminal_state != "NULL_TOKEN_EXHAUSTED" or any(
            page.terminal_state != "CONTINUE" for page in pages[:-1]
        ):
            raise Arch150D1RequalificationError("RAW_PAGE_TERMINAL_INVALID")
    return grouped


def _scan_raw_pages(
    expected: _ExpectedAttempt,
    authority: object,
    schedule_start: date,
    schedule_end: date,
    sessions: dict[date | str, object],
    commitments: tuple[RawPageCommitment, ...],
    evidence: dict[str, object],
) -> dict[str, _SymbolScan]:
    by_symbol: dict[str, list[RawPageCommitment]] = {
        symbol: [] for symbol in data.INITIAL_UNIVERSE
    }
    for page in commitments:
        by_symbol[page.symbol].append(page)
    scans: dict[str, _SymbolScan] = {}
    for symbol in data.INITIAL_UNIVERSE:
        pages = by_symbol[symbol]
        slot_iter = iter(
            expected_regular_minute_slots(
                schedule_start,
                schedule_end,
                authority,
            )
        )
        next_slot = next(slot_iter, None)
        scan = _SymbolScan(
            symbol=symbol,
            page_count=len(pages),
            raw_bar_count=0,
            observed_count=0,
            off_session_count=0,
            missing_count=0,
            missing_hash=hashlib.sha256(),
            missing_bitmap=bytearray((sessions["_scheduled_slot_count"] + 7) // 8),
            normalized=bytearray(_CSV_HEADER),
            discovery_hash=hashlib.sha256(_CSV_HEADER),
            validation_hash=hashlib.sha256(_CSV_HEADER),
            discovery_count=0,
            validation_count=0,
            first_observed=None,
            last_observed=None,
        )
        slot_index = 0
        previous_stamp: datetime | None = None
        token: str | None = None
        seen_tokens: set[str] = set()
        observed_page_hashes: list[str] = []
        for ordinal, commitment in enumerate(pages, start=1):
            request = Arch150HistoricalRequest(symbol, token)
            expected_descriptor = request.descriptor
            if (
                commitment.ordinal != ordinal
                or json.loads(commitment.request_descriptor_json) != expected_descriptor
                or commitment.request_digest != request.digest
                or commitment.input_token_sha256
                != expected_descriptor["page_token_sha256"]
            ):
                raise Arch150D1RequalificationError("REQUEST_COMMITMENT_MISMATCH")
            raw_path = expected.attempt_root / "raw" / symbol / f"{ordinal:04d}.bin"
            payload = _read_regular_file(raw_path, "RAW_PAGE_READ_FAILED")
            if (
                len(payload) != commitment.byte_length
                or _sha256(payload) != commitment.page_sha256
            ):
                raise Arch150D1RequalificationError("RAW_PAGE_HASH_MISMATCH")
            try:
                page = parse_alpaca_page(payload, request)
            except Arch150DataError as error:
                raise Arch150D1RequalificationError(error.code) from None
            observed_page_hashes.append(page.raw_page_sha256)
            next_digest = (
                _sha256(page.next_page_token.encode("utf-8"))
                if page.next_page_token is not None
                else None
            )
            if next_digest != commitment.next_token_sha256:
                raise Arch150D1RequalificationError("PAGE_TOKEN_CHAIN_MISMATCH")
            expected_terminal = (
                "CONTINUE"
                if page.next_page_token is not None
                else "NULL_TOKEN_EXHAUSTED"
            )
            if commitment.terminal_state != expected_terminal:
                raise Arch150D1RequalificationError("PAGE_TERMINAL_MISMATCH")
            if page.next_page_token is not None:
                if page.next_page_token in seen_tokens or page.next_page_token == token:
                    raise Arch150D1RequalificationError("PAGE_TOKEN_REPEATED")
                if token is not None:
                    seen_tokens.add(token)
                token = page.next_page_token
            elif ordinal != len(pages):
                raise Arch150D1RequalificationError("PAGE_TOKEN_CHAIN_MISMATCH")
            for bar in page.bars:
                stamp = bar.timestamp
                if previous_stamp is not None and stamp <= previous_stamp:
                    code = (
                        "RAW_STREAM_DUPLICATE"
                        if stamp == previous_stamp
                        else "RAW_STREAM_ORDER_INVALID"
                    )
                    raise Arch150D1RequalificationError(code)
                previous_stamp = stamp
                scan.raw_bar_count += 1
                local_day = stamp.astimezone(data._NEW_YORK).date()
                schedule = authority.schedule_for(local_day)
                if (
                    schedule is None
                    or not schedule.opens_at <= stamp < schedule.closes_at
                ):
                    scan.off_session_count += 1
                    continue
                if stamp.second != 0 or stamp.microsecond != 0:
                    raise Arch150D1RequalificationError("OFF_GRID_REGULAR_BAR")
                while next_slot is not None and next_slot < stamp:
                    _record_missing(scan, next_slot, slot_index, sessions)
                    slot_index += 1
                    next_slot = next(slot_iter, None)
                if next_slot != stamp:
                    raise Arch150D1RequalificationError(
                        "REGULAR_BAR_NOT_ON_PUBLISHED_SLOT"
                    )
                _record_observed(scan, bar)
                scan.observed_count += 1
                scan.first_observed = scan.first_observed or _timestamp_text(stamp)
                scan.last_observed = _timestamp_text(stamp)
                slot_index += 1
                next_slot = next(slot_iter, None)
        if pages[-1].next_token_sha256 is not None:
            raise Arch150D1RequalificationError("PAGE_TOKEN_CHAIN_NOT_EXHAUSTED")
        while next_slot is not None:
            _record_missing(scan, next_slot, slot_index, sessions)
            slot_index += 1
            next_slot = next(slot_iter, None)
        if slot_index != sessions["_scheduled_slot_count"]:
            raise Arch150D1RequalificationError("SCHEDULE_SLOT_ACCOUNTING_MISMATCH")
        _validate_original_symbol_scan(scan, evidence, expected)
        expected_hashes = evidence.get("raw_page_sha256_by_symbol")
        if (
            type(expected_hashes) is not dict
            or expected_hashes.get(symbol) != observed_page_hashes
        ):
            raise Arch150D1RequalificationError("RAW_PAGE_HASH_LIST_MISMATCH")
        scans[symbol] = scan
    return scans


def _record_missing(
    scan: _SymbolScan,
    stamp: datetime,
    slot_index: int,
    sessions: dict[date, dict[str, object]],
) -> None:
    scan.missing_hash.update(_timestamp_text(stamp).encode("ascii") + b"\n")
    scan.missing_count += 1
    scan.missing_bitmap[slot_index // 8] |= 1 << (slot_index % 8)
    session = sessions.get(stamp.astimezone(data._NEW_YORK).date())
    if session is None:
        raise Arch150D1RequalificationError("SESSION_SLOT_NOT_PUBLISHED")
    symbol_index = 0 if scan.symbol == "SPY" else 1
    session["missing_counts"][symbol_index] += 1
    session["missing_hashes"][symbol_index].update(
        _timestamp_text(stamp).encode("ascii") + b"\n"
    )


def _record_observed(scan: _SymbolScan, bar: object) -> None:
    row = _bar_row(bar)
    scan.normalized.extend(row)
    if data.DISCOVERY_START <= bar.session_date < data.DISCOVERY_END:
        scan.discovery_hash.update(row)
        scan.discovery_count += 1
    elif data.VALIDATION_START <= bar.session_date < data.VALIDATION_END:
        scan.validation_hash.update(row)
        scan.validation_count += 1


def _validate_original_symbol_scan(
    scan: _SymbolScan, evidence: dict[str, object], expected: _ExpectedAttempt
) -> None:
    facts = {item.get("symbol"): item for item in evidence["diagnostics_by_symbol"]}
    item = facts.get(scan.symbol)
    expected_values = dict(dict(expected.symbol_facts)[scan.symbol])
    actual = {
        "raw_page_count": scan.page_count,
        "raw_bar_count": scan.raw_bar_count,
        "observed_regular_slot_bar_count": scan.observed_count,
        "missing_expected_slot_count": scan.missing_count,
        "missing_expected_slot_sha256": scan.missing_hash.hexdigest(),
        "off_session_excluded_count": scan.off_session_count,
    }
    if item is None:
        raise Arch150D1RequalificationError("ORIGINAL_DIAGNOSTICS_INVALID")
    for key, value in actual.items():
        if key == "missing_expected_slot_sha256":
            expected_value = item.get(key)
        else:
            expected_value = expected_values.get(
                key.removesuffix("_expected_slot_count"), expected_values.get(key)
            )
            if key == "raw_page_count":
                expected_value = expected_values.get("pages")
            elif key == "raw_bar_count":
                expected_value = expected_values.get("raw_bars")
            elif key == "observed_regular_slot_bar_count":
                expected_value = expected_values.get("observed")
            elif key == "missing_expected_slot_count":
                expected_value = expected_values.get("missing")
            elif key == "off_session_excluded_count":
                expected_value = expected_values.get("off_session")
        if expected_value is not None and value != expected_value:
            raise Arch150D1RequalificationError("REQUALIFIED_DIAGNOSTICS_MISMATCH")
    if actual["missing_expected_slot_sha256"] != item.get(
        "missing_expected_slot_sha256"
    ):
        raise Arch150D1RequalificationError("REQUALIFIED_DIAGNOSTICS_MISMATCH")


def _session_facts(
    authority: object, start: date, end: date
) -> dict[date | str, object]:
    rows: dict[date | str, object] = {}
    slot_count = 0
    for day in authority.published.sessions:
        if not start <= day < end:
            continue
        schedule = authority.schedule_for(day)
        if schedule is None:
            raise Arch150D1RequalificationError("PUBLISHED_SESSION_SCHEDULE_MISSING")
        count = int((schedule.closes_at - schedule.opens_at) / timedelta(minutes=1))
        rows[day] = {
            "scheduled_slot_count": count,
            "missing_counts": [0, 0],
            "missing_hashes": [hashlib.sha256(), hashlib.sha256()],
        }
        slot_count += count
    if not rows:
        raise Arch150D1RequalificationError("PUBLISHED_SESSION_RANGE_EMPTY")
    rows["_scheduled_slot_count"] = slot_count
    return rows


def _combined_missing(
    scans: dict[str, _SymbolScan],
    *,
    slot_stream_factory: object,
    sessions: dict[date | str, object],
) -> dict[str, object]:
    spy = scans["SPY"].missing_bitmap
    qqq = scans["QQQ"].missing_bitmap
    common_hash = hashlib.sha256()
    union_hash = hashlib.sha256()
    common_count = union_count = slot_index = 0
    for stamp in slot_stream_factory():
        spy_missing = bool(spy[slot_index // 8] & (1 << (slot_index % 8)))
        qqq_missing = bool(qqq[slot_index // 8] & (1 << (slot_index % 8)))
        encoded = _timestamp_text(stamp).encode("ascii") + b"\n"
        if spy_missing and qqq_missing:
            common_hash.update(encoded)
            common_count += 1
        if spy_missing or qqq_missing:
            union_hash.update(encoded)
            union_count += 1
        slot_index += 1
    session_rows = []
    affected = fully_spy = fully_qqq = both = 0
    for day in sorted(key for key in sessions if isinstance(key, date)):
        facts = sessions[day]
        counts = facts["missing_counts"]
        total = facts["scheduled_slot_count"]
        if counts[0] or counts[1]:
            affected += 1
        if counts[0] == total:
            fully_spy += 1
        if counts[1] == total:
            fully_qqq += 1
        if counts[0] and counts[1]:
            both += 1
        session_rows.append(
            {
                "session_date": day.isoformat(),
                "scheduled_slot_count": total,
                "SPY_missing_count": counts[0],
                "SPY_missing_sha256": facts["missing_hashes"][0].hexdigest(),
                "QQQ_missing_count": counts[1],
                "QQQ_missing_sha256": facts["missing_hashes"][1].hexdigest(),
            }
        )
    return {
        "common_missing_count": common_count,
        "common_missing_sha256": common_hash.hexdigest(),
        "union_missing_count": union_count,
        "union_missing_sha256": union_hash.hexdigest(),
        "affected_session_count": affected,
        "fully_missing_session_count_by_symbol": {"SPY": fully_spy, "QQQ": fully_qqq},
        "sessions_affected_in_both_symbols": both,
        "per_session_missing_commitments": session_rows,
    }


def _identity_material(
    *,
    expected: _ExpectedAttempt,
    source: _SourceIdentity,
    authority: object,
    schedule_identity: str,
    schedule_digest: str,
    schedule_start: date,
    schedule_end: date,
    scans: dict[str, _SymbolScan],
    sparse: dict[str, object],
    original_evidence: dict[str, object],
    commitments: tuple[RawPageCommitment, ...],
    scheduled_slot_count: int,
) -> dict[str, object]:
    evidence = original_evidence
    artifact_hashes = {name: digest for name, _, digest in expected.artifact_facts}
    diagnostics = []
    normalized = {}
    for symbol in data.INITIAL_UNIVERSE:
        scan = scans[symbol]
        normalized[symbol] = {
            "bar_count": scan.observed_count,
            "sha256": _sha256(bytes(scan.normalized)),
            "first_timestamp": scan.first_observed,
            "last_timestamp": scan.last_observed,
            "discovery": {
                "bar_count": scan.discovery_count,
                "sha256": scan.discovery_hash.hexdigest(),
            },
            "validation": {
                "bar_count": scan.validation_count,
                "sha256": scan.validation_hash.hexdigest(),
            },
        }
        diagnostics.append(
            {
                "symbol": symbol,
                "scheduled_slot_count": scheduled_slot_count,
                "observed_regular_session_count": scan.observed_count,
                "missing_slot_count": scan.missing_count,
                "missing_timestamp_sha256": scan.missing_hash.hexdigest(),
                "first_observed_timestamp": scan.first_observed,
                "last_observed_timestamp": scan.last_observed,
                "raw_bar_count": scan.raw_bar_count,
                "raw_page_count": scan.page_count,
                "off_session_excluded_count": scan.off_session_count,
                "duplicate_count": 0,
                "malformed_count": 0,
                "pagination_terminal_state": "NULL_TOKEN_EXHAUSTED",
            }
        )
    raw_hashes = evidence.get("raw_page_sha256_by_symbol")
    return {
        "version": "arch150-intraday-sparse-custody-dataset-identity/v1",
        "schema": DATASET_SCHEMA,
        "classification": OUTPUT_CLASSIFICATION,
        "original_dense_dataset": {
            "classification": "BLOCKED",
            "failure_code": expected.failure_code,
            "identity": expected.dense_dataset_identity,
            "sha256": expected.dense_dataset_sha256,
        },
        "attempt": {
            "identity": expected.attempt_id,
            "artifact_sha256": artifact_hashes,
            "original_source": {
                "branch": FEATURE_BRANCH,
                "head": expected.source_head,
                "tree": expected.source_tree,
                "live_feature_head": expected.live_feature_head,
                "live_develop_head": expected.live_develop_head,
            },
            "original_custody_identity": expected.custody_identity,
            "original_custody_semantic_sha256": expected.custody_semantic_sha256,
        },
        "ordered_raw_page_commitments": [page.to_dict() for page in commitments],
        "raw_page_sha256_by_symbol": raw_hashes,
        "request_semantics": {
            "provider": data.PROVIDER_NAME,
            "endpoint": data.PROVIDER_ENDPOINT,
            "timeframe": data.TIMEFRAME,
            "adjustment": data.ADJUSTMENT,
            "feed": data.FEED,
            "currency": data.CURRENCY,
            "sort": data.SORT,
            "limit": data.LIMIT,
            "start": data.REQUEST_START.isoformat(),
            "end_inclusive": data.REQUEST_END_INCLUSIVE.isoformat(),
            "pagination": "next_page_token_until_null",
        },
        "xnys_authority": {
            "identity": authority.published.identity,
            "digest": authority.published.digest,
            "schedule_identity": schedule_identity,
            "schedule_digest": schedule_digest,
            "timezone": data.SCHEDULE_TIMEZONE,
        },
        "schedule_range": {
            "start": schedule_start.isoformat(),
            "end_exclusive": schedule_end.isoformat(),
        },
        "discovery_boundary": {
            "start": data.DISCOVERY_START.isoformat(),
            "end_exclusive": data.DISCOVERY_END.isoformat(),
        },
        "validation_boundary": {
            "start": data.VALIDATION_START.isoformat(),
            "end_exclusive": data.VALIDATION_END.isoformat(),
        },
        "symbol_diagnostics": diagnostics,
        "sparse_universe": sparse,
        "normalized_sparse_regular_bars": normalized,
        "missing_slot_semantics": dict(NO_FILL_SEMANTICS),
        "requalification_source": {
            "branch": source.branch,
            "head": source.head,
            "tree": source.tree,
        },
        "requalifier_effects": dict(ZERO_EFFECTS),
    }


def _versioned_identity(
    schema: str, material: dict[str, object], namespace: UUID
) -> tuple[str, str]:
    body = canonical_json_bytes(material)
    identity = uuid5(
        namespace,
        canonical_json_bytes({"schema": schema, "material": material}).decode("utf-8"),
    )
    return str(identity), _sha256(body)


def _artifact(
    schema: str, identity: str, digest: str, material: dict[str, object]
) -> bytes:
    return canonical_json_bytes(
        {"schema": schema, "identity": identity, "sha256": digest, "material": material}
    )


def _write_output_once(root: Path, artifacts: dict[str, bytes]) -> None:
    try:
        root.mkdir()
    except FileExistsError:
        raise Arch150D1RequalificationError("OUTPUT_ALREADY_EXISTS") from None
    except OSError:
        raise Arch150D1RequalificationError("OUTPUT_CREATE_FAILED") from None
    _require_directory(root, "OUTPUT_PATH_ALIAS")
    for relative, body in artifacts.items():
        path = root.joinpath(*relative.split("/"))
        parent = path.parent
        if not parent.exists():
            try:
                parent.mkdir()
            except OSError:
                raise Arch150D1RequalificationError(
                    "OUTPUT_PARENT_CREATE_FAILED"
                ) from None
        _require_directory(parent, "OUTPUT_PATH_ALIAS")
        try:
            descriptor = os.open(
                path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
                0o600,
            )
        except FileExistsError:
            raise Arch150D1RequalificationError("OUTPUT_ARTIFACT_COLLISION") from None
        except OSError:
            raise Arch150D1RequalificationError(
                "OUTPUT_ARTIFACT_CREATE_FAILED"
            ) from None
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                if stream.write(body) != len(body):
                    raise Arch150D1RequalificationError("OUTPUT_ARTIFACT_WRITE_FAILED")
                stream.flush()
                os.fsync(stream.fileno())
        except Arch150D1RequalificationError:
            raise
        except OSError:
            raise Arch150D1RequalificationError(
                "OUTPUT_ARTIFACT_WRITE_FAILED"
            ) from None
        actual = _read_regular_file(path, "OUTPUT_READBACK_FAILED")
        if len(actual) != len(body) or _sha256(actual) != _sha256(body):
            raise Arch150D1RequalificationError("OUTPUT_READBACK_MISMATCH")


def _validate_output_directory(
    root: Path, *, attempt_root: Path, private_test_root: Path | None
) -> None:
    absolute = Path(os.path.abspath(root))
    protected = (
        attempt_root,
        Path(r"F:\AI\ai-trading-bot"),
        Path(r"F:\AI\worktrees"),
    )
    for protected_path in protected:
        if _is_within(absolute, protected_path) or _is_within(protected_path, absolute):
            raise Arch150D1RequalificationError("OUTPUT_OVERLAPS_PROTECTED_PATH")
    if private_test_root is None:
        if absolute.drive.upper() != "F:":
            raise Arch150D1RequalificationError("OUTPUT_MUST_BE_ON_F")
    else:
        test_root = Path(os.path.abspath(private_test_root))
        if not _same_path(test_root, private_test_root) or not _is_within(
            absolute, test_root
        ):
            raise Arch150D1RequalificationError("TEST_OUTPUT_OUTSIDE_FIXTURE_ROOT")
        if _is_within(attempt_root, absolute) or _is_within(absolute, attempt_root):
            raise Arch150D1RequalificationError("OUTPUT_OVERLAPS_ATTEMPT")
    if absolute.exists():
        raise Arch150D1RequalificationError("OUTPUT_ALREADY_EXISTS")
    parent = absolute.parent
    if not parent.is_dir():
        raise Arch150D1RequalificationError("OUTPUT_PARENT_INVALID")
    _check_no_reparse_chain(parent)


def _require_directory(path: Path, code: str) -> None:
    if _is_reparse(path) or not path.is_dir():
        raise Arch150D1RequalificationError(code)
    try:
        if not _same_path(path, path.resolve(strict=True)):
            raise Arch150D1RequalificationError("PATH_ALIAS")
    except OSError:
        raise Arch150D1RequalificationError(code) from None
    _check_no_reparse_chain(path)


def _require_entries(path: Path, expected: set[str]) -> None:
    _require_directory(path, "INPUT_DIRECTORY_INVALID")
    try:
        entries = {item.name for item in path.iterdir()}
    except OSError:
        raise Arch150D1RequalificationError("INPUT_DIRECTORY_UNREADABLE") from None
    if entries != expected:
        raise Arch150D1RequalificationError("INPUT_MANIFEST_MISMATCH")
    for item in path.iterdir():
        if _is_reparse(item):
            raise Arch150D1RequalificationError("INPUT_PATH_ALIAS")


def _read_regular_file(path: Path, code: str) -> bytes:
    try:
        if (
            _is_reparse(path)
            or not path.is_file()
            or not _same_path(path, path.resolve(strict=True))
        ):
            raise Arch150D1RequalificationError(code)
        return path.read_bytes()
    except Arch150D1RequalificationError:
        raise
    except OSError:
        raise Arch150D1RequalificationError(code) from None


def _parse_canonical_object(body: bytes, code: str) -> dict[str, object]:
    try:
        value = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Arch150D1RequalificationError(code) from None
    if type(value) is not dict or canonical_json_bytes(value) != body:
        raise Arch150D1RequalificationError(code)
    return value


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError


def _check_no_reparse_chain(path: Path) -> None:
    for component in (path, *path.parents):
        if _is_reparse(component):
            raise Arch150D1RequalificationError("PATH_ALIAS")


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise Arch150D1RequalificationError("PATH_INSPECTION_FAILED") from None
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(parent)))
        return True
    except ValueError:
        return False


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _expected_artifact_hash(expected: _ExpectedAttempt, name: str) -> str:
    return next(
        digest for artifact, _, digest in expected.artifact_facts if artifact == name
    )


def _require_exact_fields(
    value: dict[str, object], fields: set[str], code: str
) -> None:
    if set(value) != fields:
        raise Arch150D1RequalificationError(code)


def _timestamp_text(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _decimal_text(value: object) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _bar_row(bar: object) -> bytes:
    return (
        ",".join(
            (
                _timestamp_text(bar.timestamp),
                bar.symbol,
                data.TIMEFRAME,
                _decimal_text(bar.open),
                _decimal_text(bar.high),
                _decimal_text(bar.low),
                _decimal_text(bar.close),
                str(bar.volume),
            )
        ).encode("utf-8")
        + b"\n"
    )


__all__ = [
    "ATTEMPT_ID",
    "ATTEMPT_DIRECTORY",
    "Arch150D1RequalificationError",
    "EVIDENCE_SCHEMA",
    "OUTPUT_CLASSIFICATION",
    "RequalificationResult",
    "requalify_arch150_d1",
]
