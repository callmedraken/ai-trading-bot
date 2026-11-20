"""Offline, read-only requalification of the consumed Architecture 148 B2 attempt.

This module deliberately imports only the source-owned parser and sparse
contracts. It has no credential, network, broker, holdout, or baseline path.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from trading_bot.domain import Bar
from trading_bot.experiments.arch148_intraday import (
    ADJUSTMENT,
    ARCH148_INTRADAY_SCHEDULE_DIGEST,
    ARCH148_INTRADAY_SCHEDULE_IDENTITY,
    ASOF,
    CURRENCY,
    FEED,
    INTRADAY_SYMBOLS,
    LIMIT,
    OPEN_END_EXCLUSIVE,
    OPEN_START,
    PRICE_BASIS,
    SORT,
    TIMEFRAME,
    HistoricalIntradayRequest,
    HistoricalIntradaySessionAuthority,
    IntradayPageEvidence,
    IntradaySymbolDataset,
    SparseIntradayCustodyEvidence,
    SparseIntradayDataset,
    build_sparse_intraday_custody_evidence,
    expected_open_slots,
    parse_alpaca_intraday_page,
    verify_sparse_intraday_custody_evidence,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

ORIGINAL_ATTEMPT_ID: Final = "bb1a784b-98d1-41fd-8d95-aa9fa463d5c9"
ORIGINAL_SOURCE_HEAD: Final = "e11840c2ec7054c79183b3e33aee032f427d1a69"
ORIGINAL_SOURCE_TREE: Final = "c5d36dfcac5858f5f7a520cf076e2ed1cd3502c6"
FEATURE_BRANCH: Final = "feature/robinhood-live-prototype-current"
CANONICAL_WORKTREE: Final = Path(
    r"F:\AI\worktrees\ai-trading-bot-live-prototype-current"
)
CANONICAL_ATTEMPT_DIRECTORY: Final = Path(
    rf"F:\AI\temp\arch148-b2-{ORIGINAL_ATTEMPT_ID}"
)
CANONICAL_ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
ORIGINAL_FAILURE_CODE: Final = "QUALIFICATION_BAR_COUNT_MISMATCH"
REQUALIFICATION_SCHEMA: Final = "arch148-b2-offline-requalification-evidence/v1"
REQUALIFICATION_READY: Final = "OFFLINE_REQUALIFICATION_READY_FOR_INDEPENDENT_REVIEW"
EXPECTED_PAGE_COUNTS: Final = {"QQQ": 148, "TQQQ": 141, "SQQQ": 141}
EXPECTED_RAW_BAR_COUNTS: Final = {
    "QQQ": 349_805,
    "TQQQ": 331_112,
    "SQQQ": 328_679,
}
EXPECTED_REGULAR_BAR_COUNTS: Final = {
    "QQQ": 156_379,
    "TQQQ": 156_376,
    "SQQQ": 156_376,
}
EXPECTED_MISSING_COUNTS: Final = {"QQQ": 17, "TQQQ": 20, "SQQQ": 20}
EXPECTED_COMMON_MISSING_COUNT: Final = 17
EXPECTED_UNION_MISSING_COUNT: Final = 23
EXPECTED_TOTAL_PAGES: Final = 430
EXPECTED_TOTAL_PROVIDER_ATTEMPTS: Final = 430
EXPECTED_SLOT_COUNT: Final = 156_396
_REPARSE_POINT: Final = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_HEX = frozenset("0123456789abcdef")


class Arch148B2RequalifierError(RuntimeError):
    """Sanitized failure code for offline evidence requalification."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OfflineRequalificationResult:
    classification: str
    attempt_id: str
    output_directory: Path
    dataset: SparseIntradayDataset
    custody: SparseIntradayCustodyEvidence
    evidence_sha256: str
    evidence_byte_length: int


@dataclass(frozen=True, slots=True)
class _PageManifestEntry:
    sequence: int
    symbol: str
    ordinal: int
    body_sha256: str
    body_size: int
    request_id_sha256: str


@dataclass(frozen=True, slots=True)
class _ValidatedAcquisition:
    dataset: SparseIntradayDataset
    custody: SparseIntradayCustodyEvidence
    pages: tuple[tuple[str, tuple[_PageManifestEntry, ...]], ...]
    raw_bar_counts: tuple[tuple[str, int], ...]
    excluded_bar_counts: tuple[tuple[str, int], ...]


def requalify_arch148_b2(
    attempt_directory: Path,
    output_directory: Path,
    *,
    candidate_source_head: str,
    candidate_source_tree: str,
) -> OfflineRequalificationResult:
    """Validate the fixed consumed attempt and write fresh sparse evidence.

    The original attempt is opened read-only. All output is create-once and
    must resolve outside the consumed attempt. The caller must bind the
    requalification result to the exact candidate source identity.
    """

    _validate_git_identity(candidate_source_head, "candidate HEAD")
    _validate_git_identity(candidate_source_tree, "candidate tree")
    try:
        attempt_path = _validate_attempt_path(attempt_directory)
        output_path = _validate_output_path(attempt_path, output_directory)
        claim, failure = _validate_incident_records(attempt_path)
        validated = _validate_pages_and_build_dataset(attempt_path)

        # Creating the output is the first write and happens only after every
        # original source, incident, page, token, parser, and sparse-dataset check.
        _create_output_directory(output_path)
        output_path.joinpath("normalized").mkdir()
        artifact_facts = _write_sparse_artifacts(output_path, validated)
        evidence = _requalification_evidence(
            claim,
            failure,
            validated,
            artifact_facts,
            candidate_source_head,
            candidate_source_tree,
        )
        evidence_bytes = canonical_json_bytes(evidence)
        _write_once(output_path / "evidence.json", evidence_bytes)
        _verify_file(output_path / "evidence.json", evidence_bytes)
    except Arch148B2RequalifierError:
        raise
    except OSError:
        raise Arch148B2RequalifierError("OFFLINE_REQUALIFICATION_IO_FAILED") from None
    except Exception:
        raise Arch148B2RequalifierError("OFFLINE_REQUALIFICATION_FAILED") from None
    return OfflineRequalificationResult(
        REQUALIFICATION_READY,
        ORIGINAL_ATTEMPT_ID,
        output_path,
        validated.dataset,
        validated.custody,
        hashlib.sha256(evidence_bytes).hexdigest(),
        len(evidence_bytes),
    )


def requalify_preserved_bb1a(
    output_directory: Path,
) -> OfflineRequalificationResult:
    """Run the fixed offline transformation after proving the local candidate.

    This entry point pins the canonical F: worktree and consumed attempt. It
    performs read-only local Git inspection, with no fetch or other network use.
    """

    head, tree = _candidate_source_identity()
    return requalify_arch148_b2(
        CANONICAL_ATTEMPT_DIRECTORY,
        output_directory,
        candidate_source_head=head,
        candidate_source_tree=tree,
    )


def _candidate_source_identity() -> tuple[str, str]:
    worktree = CANONICAL_WORKTREE
    try:
        resolved = worktree.resolve(strict=True)
        source_root = Path(__file__).resolve().parents[3]
    except OSError:
        raise Arch148B2RequalifierError("CANDIDATE_WORKTREE_INVALID") from None
    if not _same_path(resolved, worktree) or not _same_path(source_root, worktree):
        raise Arch148B2RequalifierError("CANDIDATE_WORKTREE_MISMATCH")
    try:
        branch = _git_output(worktree, "branch", "--show-current")
        origin = _git_output(worktree, "remote", "get-url", "origin")
        head = _git_output(worktree, "rev-parse", "HEAD")
        tree = _git_output(worktree, "rev-parse", "HEAD^{tree}")
        status = _git_output(
            worktree, "status", "--porcelain=v1", "--untracked-files=all"
        )
    except (OSError, subprocess.SubprocessError):
        raise Arch148B2RequalifierError("CANDIDATE_GIT_FACTS_UNAVAILABLE") from None
    if branch != FEATURE_BRANCH or origin != CANONICAL_ORIGIN or status:
        raise Arch148B2RequalifierError("CANDIDATE_SOURCE_NOT_CLEAN_CANONICAL")
    _validate_git_identity(head, "candidate HEAD")
    _validate_git_identity(tree, "candidate tree")
    return head, tree


def _git_output(worktree: Path, *args: str) -> str:
    completed = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(worktree),
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _validate_attempt_path(path: Path) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        raise Arch148B2RequalifierError("ATTEMPT_PATH_INVALID")
    _check_path_chain(path)
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise Arch148B2RequalifierError("ATTEMPT_PATH_INVALID") from None
    if not _same_path(path, resolved) or not resolved.is_dir():
        raise Arch148B2RequalifierError("ATTEMPT_PATH_ALIAS")
    if path.name != f"arch148-b2-{ORIGINAL_ATTEMPT_ID}":
        raise Arch148B2RequalifierError("ATTEMPT_ID_MISMATCH")
    return resolved


def _validate_output_path(attempt_path: Path, path: Path) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        raise Arch148B2RequalifierError("OUTPUT_PATH_INVALID")
    _check_path_chain(path.parent)
    try:
        resolved_parent = path.parent.resolve(strict=True)
        resolved_candidate = resolved_parent / path.name
    except OSError:
        raise Arch148B2RequalifierError("OUTPUT_PARENT_INVALID") from None
    if (
        not resolved_parent.is_dir()
        or not _same_path(path.parent, resolved_parent)
        or not path.name
        or path.name in {".", ".."}
        or not _same_path(path, resolved_candidate)
    ):
        raise Arch148B2RequalifierError("OUTPUT_PATH_ALIAS")
    if _is_within(attempt_path, resolved_candidate) or _is_within(
        resolved_candidate, attempt_path
    ):
        raise Arch148B2RequalifierError("OUTPUT_OVERLAPS_CONSUMED_ATTEMPT")
    if path.exists() or path.is_symlink():
        raise Arch148B2RequalifierError("OUTPUT_ALREADY_EXISTS")
    return resolved_candidate


def _validate_incident_records(
    attempt_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    _require_directory_entries(
        attempt_path, {"attempt.json", "failure.json", "journal", "raw"}
    )
    claim = _read_canonical_object(
        attempt_path / "attempt.json", "ATTEMPT_CLAIM_INVALID"
    )
    expected_claim_fields = {
        "schema",
        "attempt_id",
        "source_branch",
        "source_head",
        "source_tree",
        "live_origin_feature_head",
        "live_origin_develop_head",
        "automatic_retry",
    }
    if (
        set(claim) != expected_claim_fields
        or claim["schema"] != "arch148-b2-attempt-claim/v1"
        or claim["attempt_id"] != ORIGINAL_ATTEMPT_ID
        or claim["source_branch"] != FEATURE_BRANCH
        or claim["source_head"] != ORIGINAL_SOURCE_HEAD
        or claim["source_tree"] != ORIGINAL_SOURCE_TREE
        or claim["live_origin_feature_head"] != ORIGINAL_SOURCE_HEAD
        or claim["live_origin_develop_head"] != ORIGINAL_SOURCE_HEAD
        or claim["automatic_retry"] != "FORBIDDEN"
    ):
        raise Arch148B2RequalifierError("ORIGINAL_SOURCE_CLAIM_MISMATCH")

    failure = _read_canonical_object(
        attempt_path / "failure.json", "ATTEMPT_FAILURE_RECORD_INVALID"
    )
    expected_failure_fields = {
        "schema",
        "classification",
        "failure_code",
        "attempt_id",
        "credential_read_attempt_count",
        "provider_request_attempt_count",
        "successful_page_count",
        "unresolved_intent_status",
        "automatic_retry",
        "robinhood_calls",
        "broker_calls",
        "order_mutations",
        "production_state_mutations",
        "final_holdout_accesses",
        "baseline_backtests",
    }
    if (
        set(failure) != expected_failure_fields
        or failure["schema"] != "arch148-b2-blocked-attempt/v1"
        or failure["classification"] != "BLOCKED"
        or failure["failure_code"] != ORIGINAL_FAILURE_CODE
        or failure["attempt_id"] != ORIGINAL_ATTEMPT_ID
        or type(failure["credential_read_attempt_count"]) is not int
        or failure["credential_read_attempt_count"] != 1
        or type(failure["provider_request_attempt_count"]) is not int
        or failure["provider_request_attempt_count"] != EXPECTED_TOTAL_PROVIDER_ATTEMPTS
        or type(failure["successful_page_count"]) is not int
        or failure["successful_page_count"] != EXPECTED_TOTAL_PAGES
        or failure["unresolved_intent_status"] != "NONE"
        or failure["automatic_retry"] != "FORBIDDEN"
        or any(
            type(failure[field]) is not int or failure[field] != 0
            for field in (
                "robinhood_calls",
                "broker_calls",
                "order_mutations",
                "production_state_mutations",
                "final_holdout_accesses",
                "baseline_backtests",
            )
        )
    ):
        raise Arch148B2RequalifierError("ORIGINAL_CONSUMED_CLASSIFICATION_MISMATCH")
    return claim, failure


def _validate_pages_and_build_dataset(attempt_path: Path) -> _ValidatedAcquisition:
    journal = attempt_path / "journal"
    intent_dir = journal / "intents"
    result_dir = journal / "results"
    raw_root = attempt_path / "raw"
    _require_directory_entries(journal, {"intents", "results"})
    expected_names = {
        f"{sequence:04d}.json" for sequence in range(1, EXPECTED_TOTAL_PAGES + 1)
    }
    _require_directory_entries(intent_dir, expected_names)
    _require_directory_entries(result_dir, expected_names)
    _require_directory_entries(raw_root, set(INTRADAY_SYMBOLS))
    for symbol in INTRADAY_SYMBOLS:
        _require_directory_entries(
            raw_root / symbol,
            {
                f"{ordinal:04d}.json"
                for ordinal in range(1, EXPECTED_PAGE_COUNTS[symbol] + 1)
            },
        )

    slots = expected_open_slots(OPEN_START, OPEN_END_EXCLUSIVE)
    if len(slots) != EXPECTED_SLOT_COUNT:
        raise Arch148B2RequalifierError("SCHEDULE_SLOT_COUNT_MISMATCH")
    expected_slot_set = set(slots)
    authority = HistoricalIntradaySessionAuthority()
    session_bounds: dict[date, tuple[datetime, datetime]] = {}
    for session_date in sorted({slot.date() for slot in slots}):
        schedule = authority.schedule_for(session_date)
        if schedule is None:
            raise Arch148B2RequalifierError("SCHEDULE_SESSION_UNAVAILABLE")
        session_bounds[session_date] = (
            schedule.opens_at.astimezone(UTC),
            schedule.closes_at.astimezone(UTC),
        )
    bars_by_symbol: dict[str, list[Bar]] = {symbol: [] for symbol in INTRADAY_SYMBOLS}
    page_entries: dict[str, list[_PageManifestEntry]] = {
        symbol: [] for symbol in INTRADAY_SYMBOLS
    }
    raw_bar_counts = {symbol: 0 for symbol in INTRADAY_SYMBOLS}
    regular_bar_counts = {symbol: 0 for symbol in INTRADAY_SYMBOLS}
    previous_timestamp = {symbol: None for symbol in INTRADAY_SYMBOLS}
    request_tokens: dict[str, set[str | None]] = {
        symbol: set() for symbol in INTRADAY_SYMBOLS
    }
    next_tokens: dict[str, str | None] = {symbol: None for symbol in INTRADAY_SYMBOLS}
    expected_stream = tuple(
        (symbol, ordinal)
        for symbol in INTRADAY_SYMBOLS
        for ordinal in range(1, EXPECTED_PAGE_COUNTS[symbol] + 1)
    )
    all_page_hashes: dict[str, list[str]] = {symbol: [] for symbol in INTRADAY_SYMBOLS}
    all_page_sizes: dict[str, list[int]] = {symbol: [] for symbol in INTRADAY_SYMBOLS}

    for sequence, (symbol, ordinal) in enumerate(expected_stream, start=1):
        intent_path = intent_dir / f"{sequence:04d}.json"
        result_path = result_dir / f"{sequence:04d}.json"
        intent = _read_canonical_object(intent_path, "REQUEST_INTENT_INVALID")
        result = _read_canonical_object(result_path, "REQUEST_RESULT_INVALID")
        if (
            set(intent)
            != {
                "schema",
                "attempt_id",
                "provider_sequence",
                "symbol",
                "symbol_page_ordinal",
                "request_descriptor_sha256",
                "page_token_sha256",
                "automatic_retry",
            }
            or intent["schema"] != "arch148-b2-request-intent/v1"
            or intent["attempt_id"] != ORIGINAL_ATTEMPT_ID
            or type(intent["provider_sequence"]) is not int
            or intent["provider_sequence"] != sequence
            or intent["symbol"] != symbol
            or type(intent["symbol_page_ordinal"]) is not int
            or intent["symbol_page_ordinal"] != ordinal
            or intent["automatic_retry"] != "FORBIDDEN"
        ):
            raise Arch148B2RequalifierError("REQUEST_INTENT_SEQUENCE_MISMATCH")
        if (
            set(result)
            != {
                "schema",
                "attempt_id",
                "provider_sequence",
                "symbol",
                "symbol_page_ordinal",
                "response_body_sha256",
                "response_body_byte_length",
                "request_id_sha256",
                "http_classification",
            }
            or result["schema"] != "arch148-b2-request-result/v1"
            or result["attempt_id"] != ORIGINAL_ATTEMPT_ID
            or type(result["provider_sequence"]) is not int
            or result["provider_sequence"] != sequence
            or result["symbol"] != symbol
            or type(result["symbol_page_ordinal"]) is not int
            or result["symbol_page_ordinal"] != ordinal
            or result["http_classification"] != "SUCCESS_200"
        ):
            raise Arch148B2RequalifierError("REQUEST_RESULT_SEQUENCE_MISMATCH")

        request = HistoricalIntradayRequest(symbol, page_token=next_tokens[symbol])
        expected_request_digest = request.digest
        expected_token_digest = (
            None
            if request.page_token is None
            else hashlib.sha256(request.page_token.encode("utf-8")).hexdigest()
        )
        if (
            intent["request_descriptor_sha256"] != expected_request_digest
            or intent["page_token_sha256"] != expected_token_digest
        ):
            raise Arch148B2RequalifierError("REQUEST_TOKEN_CHAIN_MISMATCH")
        if request.page_token in request_tokens[symbol]:
            raise Arch148B2RequalifierError("REQUEST_TOKEN_REPEATED")
        request_tokens[symbol].add(request.page_token)

        body_sha256 = result["response_body_sha256"]
        request_id_sha256 = result["request_id_sha256"]
        body_size = result["response_body_byte_length"]
        _require_digest(body_sha256, "RAW_PAGE_DIGEST_INVALID")
        _require_digest(request_id_sha256, "REQUEST_ID_DIGEST_INVALID")
        if type(body_size) is not int or body_size <= 0:
            raise Arch148B2RequalifierError("RAW_PAGE_SIZE_INVALID")
        raw_path = raw_root / symbol / f"{ordinal:04d}.json"
        body = _read_bytes(raw_path, "RAW_PAGE_READ_FAILED")
        actual_sha256 = hashlib.sha256(body).hexdigest()
        if len(body) != body_size or actual_sha256 != body_sha256:
            raise Arch148B2RequalifierError("RAW_PAGE_CUSTODY_MISMATCH")
        try:
            page = parse_alpaca_intraday_page(body, request)
        except Exception:
            raise Arch148B2RequalifierError("RAW_PAGE_PARSER_REJECTED") from None
        if page.raw_page_sha256 != body_sha256 or page.raw_page_byte_size != body_size:
            raise Arch148B2RequalifierError("RAW_PAGE_CUSTODY_MISMATCH")
        for bar in page.bars:
            if bar.symbol.value != symbol:
                raise Arch148B2RequalifierError("RAW_PAGE_SYMBOL_MISMATCH")
            prior = previous_timestamp[symbol]
            if prior is not None and bar.timestamp <= prior:
                raise Arch148B2RequalifierError("RAW_STREAM_ORDER_OR_DUPLICATE")
            previous_timestamp[symbol] = bar.timestamp
            raw_bar_counts[symbol] += 1
            if bar.timestamp in expected_slot_set:
                bars_by_symbol[symbol].append(bar)
                regular_bar_counts[symbol] += 1
            else:
                bounds = session_bounds.get(bar.timestamp.date())
                if bounds is not None and bounds[0] <= bar.timestamp < bounds[1]:
                    raise Arch148B2RequalifierError("OFF_GRID_REGULAR_SESSION_BAR")

        next_token = page.next_page_token
        if next_token is not None and next_token in request_tokens[symbol]:
            raise Arch148B2RequalifierError("RESPONSE_TOKEN_REPEATED")
        next_tokens[symbol] = next_token
        page_entries[symbol].append(
            _PageManifestEntry(
                sequence,
                symbol,
                ordinal,
                body_sha256,
                body_size,
                request_id_sha256,
            )
        )
        all_page_hashes[symbol].append(body_sha256)
        all_page_sizes[symbol].append(body_size)

    if any(next_tokens[symbol] is not None for symbol in INTRADAY_SYMBOLS):
        raise Arch148B2RequalifierError("FINAL_PAGE_TOKEN_NOT_EXHAUSTED")
    if tuple(len(page_entries[symbol]) for symbol in INTRADAY_SYMBOLS) != tuple(
        EXPECTED_PAGE_COUNTS[symbol] for symbol in INTRADAY_SYMBOLS
    ):
        raise Arch148B2RequalifierError("PAGE_COUNT_MISMATCH")
    if raw_bar_counts != EXPECTED_RAW_BAR_COUNTS:
        raise Arch148B2RequalifierError("RAW_BAR_COUNT_MISMATCH")
    if regular_bar_counts != EXPECTED_REGULAR_BAR_COUNTS:
        raise Arch148B2RequalifierError("REGULAR_BAR_COUNT_MISMATCH")
    missing_counts = {
        symbol: EXPECTED_SLOT_COUNT - regular_bar_counts[symbol]
        for symbol in INTRADAY_SYMBOLS
    }
    if missing_counts != EXPECTED_MISSING_COUNTS:
        raise Arch148B2RequalifierError("SPARSE_MISSING_COUNT_MISMATCH")

    datasets = tuple(
        IntradaySymbolDataset(symbol, tuple(bars_by_symbol[symbol]))
        for symbol in INTRADAY_SYMBOLS
    )
    try:
        dataset = SparseIntradayDataset(OPEN_START, OPEN_END_EXCLUSIVE, datasets)
    except Exception as error:
        if getattr(error, "missing_session_count", None) is not None:
            raise Arch148B2RequalifierError("FULLY_MISSING_EXPECTED_SESSION") from None
        raise Arch148B2RequalifierError("SPARSE_DATASET_QUALIFICATION_FAILED") from None
    if (
        tuple(item.scheduled_slot_count for item in dataset.sparse_evidence)
        != (EXPECTED_SLOT_COUNT, EXPECTED_SLOT_COUNT, EXPECTED_SLOT_COUNT)
        or tuple(
            item.observed_regular_session_count for item in dataset.sparse_evidence
        )
        != tuple(EXPECTED_REGULAR_BAR_COUNTS[symbol] for symbol in INTRADAY_SYMBOLS)
        or tuple(item.missing_count for item in dataset.sparse_evidence)
        != tuple(EXPECTED_MISSING_COUNTS[symbol] for symbol in INTRADAY_SYMBOLS)
        or dataset.common_missing_slot_count != EXPECTED_COMMON_MISSING_COUNT
        or dataset.union_missing_slot_count != EXPECTED_UNION_MISSING_COUNT
    ):
        raise Arch148B2RequalifierError("SPARSE_EVIDENCE_MISMATCH")

    pages = tuple(
        IntradayPageEvidence(
            symbol, tuple(all_page_hashes[symbol]), tuple(all_page_sizes[symbol])
        )
        for symbol in INTRADAY_SYMBOLS
    )
    custody = build_sparse_intraday_custody_evidence(dataset, pages)
    try:
        verify_sparse_intraday_custody_evidence(dataset, custody)
    except Exception:
        raise Arch148B2RequalifierError("SPARSE_CUSTODY_VALIDATION_FAILED") from None
    return _ValidatedAcquisition(
        dataset,
        custody,
        tuple((symbol, tuple(page_entries[symbol])) for symbol in INTRADAY_SYMBOLS),
        tuple((symbol, raw_bar_counts[symbol]) for symbol in INTRADAY_SYMBOLS),
        tuple(
            (symbol, raw_bar_counts[symbol] - regular_bar_counts[symbol])
            for symbol in INTRADAY_SYMBOLS
        ),
    )


def _write_sparse_artifacts(
    output_path: Path, validated: _ValidatedAcquisition
) -> dict[str, object]:
    dataset_bytes = validated.dataset.to_json().encode("utf-8")
    custody_bytes = validated.custody.to_json().encode("utf-8")
    normalized: list[dict[str, object]] = []
    for item in validated.dataset.datasets:
        body = item.normalized_bytes
        path = output_path / "normalized" / f"{item.symbol}.csv"
        _write_once(path, body)
        _verify_file(path, body)
        normalized.append(
            {
                "symbol": item.symbol,
                "sha256": hashlib.sha256(body).hexdigest(),
                "byte_length": len(body),
                "bar_count": len(item.bars),
            }
        )
    _write_once(output_path / "dataset.json", dataset_bytes)
    _verify_file(output_path / "dataset.json", dataset_bytes)
    _write_once(output_path / "custody-evidence.json", custody_bytes)
    _verify_file(output_path / "custody-evidence.json", custody_bytes)
    return {
        "dataset": {
            "schema": "arch148-intraday-dataset/v3",
            "identity": validated.dataset.identity,
            "sha256": hashlib.sha256(dataset_bytes).hexdigest(),
            "byte_length": len(dataset_bytes),
        },
        "custody": {
            "schema": "arch148-intraday-custody-evidence/v3",
            "evidence_id": validated.custody.evidence_id,
            "sha256": hashlib.sha256(custody_bytes).hexdigest(),
            "byte_length": len(custody_bytes),
        },
        "normalized": normalized,
    }


def _requalification_evidence(
    claim: dict[str, object],
    failure: dict[str, object],
    validated: _ValidatedAcquisition,
    artifacts: dict[str, object],
    candidate_source_head: str,
    candidate_source_tree: str,
) -> dict[str, object]:
    streams = []
    for symbol, entries in validated.pages:
        raw_bar_count = dict(validated.raw_bar_counts)[symbol]
        excluded_count = dict(validated.excluded_bar_counts)[symbol]
        sparse = validated.dataset.sparse_evidence_by_symbol[symbol]
        streams.append(
            {
                "symbol": symbol,
                "page_count": len(entries),
                "pagination_exhausted": True,
                "raw_bar_count": raw_bar_count,
                "qualified_regular_session_bar_count": (
                    sparse.observed_regular_session_count
                ),
                "excluded_non_regular_bar_count": excluded_count,
                "raw_page_sha256": [entry.body_sha256 for entry in entries],
                "raw_page_byte_size": [entry.body_size for entry in entries],
                "request_id_sha256": [entry.request_id_sha256 for entry in entries],
                "sparse": sparse.to_dict(),
            }
        )
    return {
        "schema": REQUALIFICATION_SCHEMA,
        "classification": REQUALIFICATION_READY,
        "original_attempt": {
            "attempt_id": ORIGINAL_ATTEMPT_ID,
            "classification": (
                "CONSUMED / BLOCKED / QUALIFICATION_BAR_COUNT_MISMATCH / NO RETRY"
            ),
            "failure_code": failure["failure_code"],
            "source_branch": claim["source_branch"],
            "source_head": claim["source_head"],
            "source_tree": claim["source_tree"],
            "credential_read_attempt_count": failure["credential_read_attempt_count"],
            "provider_request_attempt_count": failure["provider_request_attempt_count"],
            "successful_page_count": failure["successful_page_count"],
            "unresolved_intent_status": failure["unresolved_intent_status"],
            "automatic_retry": "FORBIDDEN",
        },
        "requalification_source": {
            "candidate_head": candidate_source_head,
            "candidate_tree": candidate_source_tree,
        },
        "dataset": artifacts["dataset"],
        "custody": artifacts["custody"],
        "schedule": {
            "identity": ARCH148_INTRADAY_SCHEDULE_IDENTITY,
            "sha256": ARCH148_INTRADAY_SCHEDULE_DIGEST,
        },
        "price_basis": PRICE_BASIS,
        "open_start": "2016-01-01T00:00:00.000000Z",
        "open_end_exclusive": "2024-01-01T00:00:00.000000Z",
        "timeframe": TIMEFRAME,
        "adjustment": ADJUSTMENT,
        "feed": FEED,
        "currency": CURRENCY,
        "asof": ASOF,
        "sort": SORT,
        "limit": LIMIT,
        "ordered_symbols": list(INTRADAY_SYMBOLS),
        "expected_slots_per_symbol": EXPECTED_SLOT_COUNT,
        "expected_total_provider_pages": EXPECTED_TOTAL_PAGES,
        "streams": streams,
        "sparse_universe": {
            "common_missing_slot_count": validated.dataset.common_missing_slot_count,
            "common_missing_slot_sha256": validated.dataset.common_missing_slot_sha256,
            "union_missing_slot_count": validated.dataset.union_missing_slot_count,
            "union_missing_slot_sha256": validated.dataset.union_missing_slot_sha256,
        },
        "normalized": artifacts["normalized"],
        "requalifier_effects": {
            "credential_reads": 0,
            "network_calls": 0,
            "provider_calls": 0,
            "robinhood_calls": 0,
            "broker_calls": 0,
            "order_mutations": 0,
            "production_state_mutations": 0,
            "final_holdout_accesses": 0,
            "baseline_backtests": 0,
        },
        "automatic_retry": "FORBIDDEN",
    }


def _create_output_directory(path: Path) -> None:
    try:
        path.mkdir()
    except FileExistsError:
        raise Arch148B2RequalifierError("OUTPUT_ALREADY_EXISTS") from None
    except OSError:
        raise Arch148B2RequalifierError("OUTPUT_CREATE_FAILED") from None
    if _is_reparse_point(path) or not _same_path(path, path.resolve(strict=True)):
        raise Arch148B2RequalifierError("OUTPUT_PATH_ALIAS")


def _write_once(path: Path, body: bytes) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except FileExistsError:
        raise Arch148B2RequalifierError("OUTPUT_ARTIFACT_COLLISION") from None
    except OSError:
        raise Arch148B2RequalifierError("OUTPUT_ARTIFACT_CREATE_FAILED") from None
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            if stream.write(body) != len(body):
                raise Arch148B2RequalifierError("OUTPUT_ARTIFACT_WRITE_FAILED")
            stream.flush()
            os.fsync(stream.fileno())
    except Arch148B2RequalifierError:
        raise
    except OSError:
        raise Arch148B2RequalifierError("OUTPUT_ARTIFACT_WRITE_FAILED") from None


def _verify_file(path: Path, expected: bytes) -> None:
    actual = _read_bytes(path, "OUTPUT_READBACK_FAILED")
    if (
        len(actual) != len(expected)
        or hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest()
    ):
        raise Arch148B2RequalifierError("OUTPUT_READBACK_MISMATCH")


def _read_canonical_object(path: Path, code: str) -> dict[str, object]:
    body = _read_bytes(path, code)
    try:
        value = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except Exception:
        raise Arch148B2RequalifierError(code) from None
    if type(value) is not dict or canonical_json_bytes(value) != body:
        raise Arch148B2RequalifierError(code)
    return value


def _read_bytes(path: Path, code: str) -> bytes:
    try:
        if _is_reparse_point(path) or not path.is_file():
            raise Arch148B2RequalifierError(code)
        resolved = path.resolve(strict=True)
        if not _same_path(path, resolved):
            raise Arch148B2RequalifierError(code)
        return path.read_bytes()
    except Arch148B2RequalifierError:
        raise
    except OSError:
        raise Arch148B2RequalifierError(code) from None


def _require_directory_entries(path: Path, expected: set[str]) -> None:
    if _is_reparse_point(path) or not path.is_dir():
        raise Arch148B2RequalifierError("EVIDENCE_TREE_INVALID")
    try:
        entries = {item.name for item in path.iterdir()}
    except OSError:
        raise Arch148B2RequalifierError("EVIDENCE_TREE_INVALID") from None
    if entries != expected:
        raise Arch148B2RequalifierError("EVIDENCE_MANIFEST_MISMATCH")
    for item in path.iterdir():
        if _is_reparse_point(item):
            raise Arch148B2RequalifierError("EVIDENCE_PATH_ALIAS")


def _check_path_chain(path: Path) -> None:
    for item in (path, *path.parents):
        if _is_reparse_point(item):
            raise Arch148B2RequalifierError("EVIDENCE_PATH_ALIAS")


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise Arch148B2RequalifierError("EVIDENCE_PATH_INSPECTION_FAILED") from None
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_git_identity(value: str, label: str) -> None:
    if type(value) is not str or len(value) != 40 or not set(value) <= _HEX:
        raise Arch148B2RequalifierError(f"{label.upper().replace(' ', '_')}_INVALID")


def _require_digest(value: object, code: str) -> None:
    if type(value) is not str or len(value) != 64 or not set(value) <= _HEX:
        raise Arch148B2RequalifierError(code)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object field")
        value[key] = item
    return value


def _reject_constant(_: str) -> None:
    raise ValueError("nonfinite JSON value")


__all__ = [
    "Arch148B2RequalifierError",
    "CANONICAL_ATTEMPT_DIRECTORY",
    "CANONICAL_WORKTREE",
    "OfflineRequalificationResult",
    "ORIGINAL_ATTEMPT_ID",
    "ORIGINAL_FAILURE_CODE",
    "ORIGINAL_SOURCE_HEAD",
    "ORIGINAL_SOURCE_TREE",
    "REQUALIFICATION_READY",
    "requalify_arch148_b2",
    "requalify_preserved_bb1a",
]
