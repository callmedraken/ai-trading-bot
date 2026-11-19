"""Architecture 148-B2 one-shot OPEN acquisition and evidence boundary.

Import, construction, help and source preflight are effect-free.  The explicit
acquisition entry point is reserved for a later, separately reviewed B2-B run.
It reuses the accepted B1 parser, dataset and custody contracts and never retries
an ambiguous provider request.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from trading_bot.domain import Bar
from trading_bot.experiments.arch148_intraday import (
    ARCH148_INTRADAY_DATASET_SCHEMA,
    ARCH148_INTRADAY_EVIDENCE_SCHEMA,
    ARCH148_INTRADAY_SCHEDULE_DIGEST,
    ARCH148_INTRADAY_SCHEDULE_IDENTITY,
    EARLY_CLOSE_DATES,
    INTRADAY_SYMBOLS,
    OPEN_END_EXCLUSIVE,
    OPEN_START,
    PRICE_BASIS,
    TIMEFRAME,
    CollectedIntradayPages,
    HistoricalIntradayRequest,
    HistoricalIntradaySessionAuthority,
    IntradayCustodyEvidence,
    IntradayDataset,
    IntradaySymbolDataset,
    build_alpaca_intraday_request,
    build_intraday_custody_evidence,
    expected_open_slots,
    parse_alpaca_intraday_page,
    verify_intraday_custody_evidence,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes
from trading_bot.market_data.alpaca_http import (
    AlpacaHttpResponse,
    StdlibAlpacaHistoricalBarsTransport,
)
from trading_bot.market_data.exceptions import (
    AlpacaHttpStatusError,
    AlpacaTransportError,
)
from trading_bot.review_paper.alpaca_windows_credentials import (
    ScopedAlpacaSecrets,
    read_current_product_alpaca_secrets,
)

EVIDENCE_SCHEMA: Final = "arch148-b2-readonly-acquisition-evidence/v1"
SUCCESS_CLASSIFICATION: Final = "READY_FOR_INDEPENDENT_B2_EVIDENCE_REVIEW"
ACQUISITION_INTERLOCK: Final = "ACQUIRE ARCH148 B2 OPEN DATA ONCE; READ-ONLY; NO RETRY"
FEATURE_BRANCH: Final = "feature/robinhood-live-prototype-current"
CANONICAL_ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
CANONICAL_WORKTREE: Final = Path(
    r"F:\AI\worktrees\ai-trading-bot-live-prototype-current"
)
EVIDENCE_ROOT: Final = Path(r"F:\AI\temp")
MAX_PAGES_PER_SYMBOL: Final = 64
MAX_PROVIDER_REQUEST_ATTEMPTS: Final = 192
EXPECTED_OPEN_SESSIONS: Final = 2012
EXPECTED_EARLY_CLOSE_SESSIONS: Final = 15
EXPECTED_SLOTS_PER_SYMBOL: Final = 156_396
EXPECTED_TOTAL_BARS: Final = 469_188

_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class Arch148B2OperatorError(RuntimeError):
    """A bounded, sanitized stop reason for one B2 attempt."""

    def __init__(self, code: str, *, attempt_path: Path | None = None) -> None:
        self.code = code
        self.attempt_path = attempt_path
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ExpectedSource:
    """Exact accepted feature source identity supplied by the reviewed caller."""

    head: str
    tree: str

    def __post_init__(self) -> None:
        if type(self.head) is not str or _SHA1.fullmatch(self.head) is None:
            raise ValueError("expected HEAD must be a lowercase Git SHA-1")
        if type(self.tree) is not str or _SHA1.fullmatch(self.tree) is None:
            raise ValueError("expected tree must be a lowercase Git SHA-1")


@dataclass(frozen=True, slots=True)
class SourceFacts:
    """Nonsecret local and live Git facts used by source admission."""

    canonical_root: str
    branch: str
    head: str
    tree: str
    origin: str
    upstream: str
    porcelain: str
    live_feature_head: str
    live_develop_head: str


@dataclass(frozen=True, slots=True)
class SourceAdmission:
    """Result of the effect-free exact-source admission check."""

    passed: bool
    failure_code: str | None
    facts: SourceFacts | None
    feature_authority_passed: bool
    prospective_develop_authority_passed: bool


@dataclass(frozen=True, slots=True)
class AcquisitionOutcome:
    """Sanitized terminal result; never contains provider or credential text."""

    classification: str
    attempt_id: str | None
    attempt_directory: Path | None
    credential_read_attempt_count: int
    provider_request_attempt_count: int
    successful_page_count: int
    failure_code: str | None = None
    evidence_sha256: str | None = None
    evidence_byte_length: int | None = None

    @property
    def succeeded(self) -> bool:
        return self.classification == SUCCESS_CLASSIFICATION


@dataclass(frozen=True, slots=True)
class _PageAccounting:
    symbol: str
    raw_page_sha256: tuple[str, ...]
    raw_page_byte_size: tuple[int, ...]
    request_id_sha256: tuple[str, ...]
    bars: tuple[Bar, ...]


def operator_help() -> str:
    """Return effect-free usage text for the later reviewed B2-B invocation."""

    return (
        "Architecture 148-B2-A source-only boundary. Import, help and source "
        "preflight perform zero credential reads and zero provider requests. "
        "The one-shot acquisition entry point requires the exact interlock and "
        "accepted feature HEAD/tree; it never retries and is not authorized by "
        "B2-A publication."
    )


def main(argv: list[str] | None = None) -> int:
    """Expose effect-free help/preflight and the explicit interlocked entry."""

    parser = argparse.ArgumentParser(description=operator_help())
    actions = parser.add_subparsers(dest="action")
    preflight = actions.add_parser("preflight", help="read-only exact-source admission")
    acquire = actions.add_parser(
        "acquire", help="one separately reviewed READ_ONLY acquisition"
    )
    for command in (preflight, acquire):
        command.add_argument("--expected-head", required=True)
        command.add_argument("--expected-tree", required=True)
    acquire.add_argument("--interlock", required=True)
    arguments = parser.parse_args(argv)
    if arguments.action is None:
        parser.print_help()
        return 0
    try:
        expected = ExpectedSource(arguments.expected_head, arguments.expected_tree)
    except (TypeError, ValueError):
        print("BLOCKED EXPECTED_SOURCE_INVALID")
        return 2
    if arguments.action == "preflight":
        result = preflight_source(expected)
        print(
            "SOURCE_ADMISSION="
            + ("PASS" if result.passed else "BLOCKED")
            + " FEATURE="
            + ("PASS" if result.feature_authority_passed else "FAIL")
            + " PROSPECTIVE_DEVELOP="
            + ("PASS" if result.prospective_develop_authority_passed else "FAIL")
        )
        if result.passed:
            return 0
        print("FAILURE_CODE=" + (result.failure_code or "SOURCE_ADMISSION_FAILED"))
        return 1
    try:
        outcome = acquire_arch148_b2(
            interlock=arguments.interlock,
            expected_head=arguments.expected_head,
            expected_tree=arguments.expected_tree,
        )
    except Arch148B2OperatorError as error:
        print("BLOCKED " + error.code)
        return 1
    print(
        "CLASSIFICATION="
        + outcome.classification
        + f" CREDENTIAL_READ_ATTEMPTS={outcome.credential_read_attempt_count}"
        + f" PROVIDER_REQUEST_ATTEMPTS={outcome.provider_request_attempt_count}"
    )
    if outcome.attempt_id is not None:
        print("ATTEMPT_ID=" + outcome.attempt_id)
    if outcome.attempt_directory is not None:
        print("ATTEMPT_DIRECTORY=" + str(outcome.attempt_directory))
    if outcome.failure_code is not None:
        print("FAILURE_CODE=" + outcome.failure_code)
        return 1
    return 0 if outcome.succeeded else 1


def preflight_source(expected: ExpectedSource) -> SourceAdmission:
    """Prove local/live source and FEATURE plus PROSPECTIVE_DEVELOP authority."""

    return _source_admission(expected, run_authority=True)


def acquire_arch148_b2(
    *,
    interlock: str,
    expected_head: str,
    expected_tree: str,
) -> AcquisitionOutcome:
    """Run one separately reviewed, bounded, read-only B2-B acquisition.

    B2-A implementation and tests must never call this with real credentials or
    the real transport.  A wrong/missing interlock fails before source, output,
    credential or provider effects.
    """

    if type(interlock) is not str or interlock != ACQUISITION_INTERLOCK:
        raise Arch148B2OperatorError("INTERLOCK_REQUIRED")
    try:
        expected = ExpectedSource(expected_head, expected_tree)
    except (TypeError, ValueError):
        raise Arch148B2OperatorError("EXPECTED_SOURCE_INVALID") from None

    initial = preflight_source(expected)
    if not initial.passed:
        return _blocked(
            None, None, 0, 0, 0, initial.failure_code or "SOURCE_ADMISSION_FAILED"
        )
    contract_code = _b1_contract_failure_code()
    if contract_code is not None:
        return _blocked(None, None, 0, 0, 0, contract_code)

    attempt_id = str(uuid4())
    try:
        attempt_path = _create_attempt_directory(attempt_id, expected, initial.facts)
    except Arch148B2OperatorError as error:
        return _blocked(attempt_id, error.attempt_path, 0, 0, 0, error.code)

    credential_attempts = 0
    provider_attempts = 0
    successful_pages = 0
    failure_code: str | None = None
    collected: tuple[_PageAccounting, ...] = ()
    source_before_credentials = preflight_source(expected)
    if not source_before_credentials.passed:
        failure_code = source_before_credentials.failure_code or "SOURCE_DRIFT"
    else:
        try:
            credential_attempts = 1
            scope = read_current_product_alpaca_secrets()
        except Exception:
            scope = None
            failure_code = "CREDENTIAL_READ_FAILED"
        if failure_code is None:
            if type(scope) is not ScopedAlpacaSecrets:
                close = getattr(scope, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
                failure_code = "CREDENTIAL_SCOPE_INVALID"
            else:
                try:
                    with scope:
                        transport = StdlibAlpacaHistoricalBarsTransport()

                        def run_with_secrets(
                            key: str, secret: str
                        ) -> tuple[tuple[_PageAccounting, ...], int, int, str | None]:
                            return _fetch_all_symbols(
                                attempt_path,
                                attempt_id,
                                expected,
                                transport,
                                key,
                                secret,
                            )

                        collected, provider_attempts, successful_pages, failure_code = (
                            scope.use(run_with_secrets)
                        )
                except Exception:
                    if failure_code is None:
                        failure_code = "CREDENTIAL_SCOPE_FAILED"
                finally:
                    try:
                        scope.close()
                    except Exception:
                        failure_code = "CREDENTIAL_SCOPE_CLOSE_FAILED"

    post_provider = preflight_source(expected)
    if not post_provider.passed:
        failure_code = post_provider.failure_code or "SOURCE_DRIFT"

    if failure_code is None:
        try:
            dataset, custody = _qualify_dataset(collected)
            normalized_metadata, dataset_bytes, custody_bytes = _write_data_artifacts(
                attempt_path, dataset, custody
            )
            _verify_persisted_artifacts(
                attempt_path,
                collected,
                normalized_metadata,
                dataset_bytes,
                custody_bytes,
            )
            failure_code = _terminal_source_check(expected)
            if failure_code is None:
                evidence = _terminal_evidence(
                    expected,
                    post_provider.facts,
                    attempt_id,
                    credential_attempts,
                    provider_attempts,
                    successful_pages,
                    collected,
                    dataset,
                    custody,
                    dataset_bytes,
                    custody_bytes,
                    normalized_metadata,
                )
                evidence_bytes = canonical_json_bytes(evidence)
                evidence_path = attempt_path / "evidence.json"
                _write_once(evidence_path, evidence_bytes)
                _verify_file(evidence_path, evidence_bytes)
                print(evidence_bytes.decode("utf-8"))
                print(
                    "EVIDENCE_SHA256="
                    + hashlib.sha256(evidence_bytes).hexdigest()
                    + f" BYTE_LENGTH={len(evidence_bytes)}"
                )
                return AcquisitionOutcome(
                    SUCCESS_CLASSIFICATION,
                    attempt_id,
                    attempt_path,
                    credential_attempts,
                    provider_attempts,
                    successful_pages,
                    evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
                    evidence_byte_length=len(evidence_bytes),
                )
        except Arch148B2OperatorError as error:
            failure_code = error.code
        except Exception:
            failure_code = "QUALIFICATION_OR_OUTPUT_FAILED"

    _write_failure_record(
        attempt_path,
        attempt_id,
        failure_code or "ACQUISITION_BLOCKED",
        credential_attempts,
        provider_attempts,
        successful_pages,
    )
    return _blocked(
        attempt_id,
        attempt_path,
        credential_attempts,
        provider_attempts,
        successful_pages,
        failure_code or "ACQUISITION_BLOCKED",
    )


def _blocked(
    attempt_id: str | None,
    attempt_path: Path | None,
    credential_attempts: int,
    provider_attempts: int,
    successful_pages: int,
    failure_code: str,
) -> AcquisitionOutcome:
    return AcquisitionOutcome(
        "BLOCKED",
        attempt_id,
        attempt_path,
        credential_attempts,
        provider_attempts,
        successful_pages,
        failure_code=failure_code,
    )


def _git_text(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise Arch148B2OperatorError("SOURCE_PROBE_FAILED")
    return completed.stdout.strip()


def _read_source_facts() -> SourceFacts:
    root = CANONICAL_WORKTREE
    try:
        resolved = root.resolve(strict=True)
        if not _same_path(resolved, root):
            raise Arch148B2OperatorError("CANONICAL_WORKTREE_MISMATCH")
        top = Path(_git_text(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
        live_refs = _git_text(
            root,
            "ls-remote",
            "--heads",
            "origin",
            f"refs/heads/{FEATURE_BRANCH}",
            "refs/heads/develop",
        )
        refs: dict[str, str] = {}
        for line in live_refs.splitlines():
            fields = line.split("\t")
            if len(fields) == 2:
                refs[fields[1]] = fields[0]
        feature = refs.get(f"refs/heads/{FEATURE_BRANCH}", "")
        develop = refs.get("refs/heads/develop", "")
        return SourceFacts(
            canonical_root=str(top),
            branch=_git_text(root, "branch", "--show-current"),
            head=_git_text(root, "rev-parse", "HEAD"),
            tree=_git_text(root, "rev-parse", "HEAD^{tree}"),
            origin=_git_text(root, "remote", "get-url", "origin"),
            upstream=_git_text(
                root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
            ),
            porcelain=_git_text(
                root, "status", "--porcelain=v1", "--untracked-files=all"
            ),
            live_feature_head=feature,
            live_develop_head=develop,
        )
    except Arch148B2OperatorError:
        raise
    except Exception:
        raise Arch148B2OperatorError("SOURCE_PROBE_FAILED") from None


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
        os.path.abspath(str(right))
    )


def _source_admission(
    expected: ExpectedSource,
    *,
    run_authority: bool,
) -> SourceAdmission:
    if type(expected) is not ExpectedSource:
        return SourceAdmission(False, "EXPECTED_SOURCE_INVALID", None, False, False)
    try:
        facts = _read_source_facts()
    except Arch148B2OperatorError as error:
        return SourceAdmission(False, error.code, None, False, False)

    failure_code = _source_facts_failure(expected, facts)
    feature_passed = False
    prospective_passed = False
    if failure_code is None and run_authority:
        try:
            from scripts.current_source_authority import (
                PublicationContext,
                evaluate_source_authority,
            )

            feature = evaluate_source_authority(
                CANONICAL_WORKTREE,
                publication_context=PublicationContext.FEATURE,
            )
            prospective = evaluate_source_authority(
                CANONICAL_WORKTREE,
                publication_context=PublicationContext.PROSPECTIVE_DEVELOP,
            )
            feature_passed = bool(
                feature.passed
                and feature.head == expected.head
                and feature.tree == expected.tree
            )
            prospective_passed = bool(
                prospective.passed
                and prospective.head == expected.head
                and prospective.tree == expected.tree
            )
            if not feature_passed or not prospective_passed:
                failure_code = "SOURCE_AUTHORITY_FAILED"
            latest = _read_source_facts()
            latest_failure = _source_facts_failure(expected, latest)
            if latest_failure is not None:
                failure_code = latest_failure
                facts = latest
        except Exception:
            failure_code = "SOURCE_AUTHORITY_UNAVAILABLE"
    return SourceAdmission(
        failure_code is None,
        failure_code,
        facts,
        feature_passed,
        prospective_passed,
    )


def _source_facts_failure(expected: ExpectedSource, facts: SourceFacts) -> str | None:
    if not _same_path(Path(facts.canonical_root), CANONICAL_WORKTREE):
        return "CANONICAL_WORKTREE_MISMATCH"
    if facts.branch != FEATURE_BRANCH:
        return "SOURCE_BRANCH_MISMATCH"
    if facts.head != expected.head or facts.tree != expected.tree:
        return "SOURCE_IDENTITY_MISMATCH"
    if facts.origin != CANONICAL_ORIGIN or facts.upstream != f"origin/{FEATURE_BRANCH}":
        return "SOURCE_REMOTE_MISMATCH"
    if facts.porcelain:
        return "SOURCE_NOT_CLEAN"
    if (
        facts.live_feature_head != expected.head
        or facts.live_develop_head != expected.head
    ):
        return "LIVE_REF_MISMATCH"
    return None


def _local_live_source_check(expected: ExpectedSource) -> str | None:
    try:
        return _source_facts_failure(expected, _read_source_facts())
    except Arch148B2OperatorError as error:
        return error.code


def _terminal_source_check(expected: ExpectedSource) -> str | None:
    admission = preflight_source(expected)
    if admission.passed:
        return None
    return admission.failure_code or "SOURCE_ADMISSION_FAILED"


def _b1_contract_failure_code() -> str | None:
    try:
        authority = HistoricalIntradaySessionAuthority()
        start_date = OPEN_START.date()
        end_date = OPEN_END_EXCLUSIVE.date()
        sessions = tuple(
            session
            for session in authority.published.sessions
            if start_date <= session < end_date
        )
        slots = expected_open_slots(OPEN_START, OPEN_END_EXCLUSIVE, authority)
        if (
            len(sessions) != EXPECTED_OPEN_SESSIONS
            or len(EARLY_CLOSE_DATES) != EXPECTED_EARLY_CLOSE_SESSIONS
            or len(slots) != EXPECTED_SLOTS_PER_SYMBOL
            or EXPECTED_SLOTS_PER_SYMBOL * len(INTRADAY_SYMBOLS) != EXPECTED_TOTAL_BARS
        ):
            return "B1_SCHEDULE_CONTRACT_MISMATCH"
        if (
            ARCH148_INTRADAY_SCHEDULE_IDENTITY != "4fe981d0-34ef-57be-a7d1-ffd017460bf5"
            or ARCH148_INTRADAY_SCHEDULE_DIGEST
            != "a33be70499cdafbfa21f45a04c854ab834425807b6c0314814b7442749aa2bad"
            or PRICE_BASIS != "ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1"
            or TIMEFRAME != "5Min"
        ):
            return "B1_CONTRACT_IDENTITY_MISMATCH"
    except Exception:
        return "B1_CONTRACT_UNAVAILABLE"
    return None


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _check_non_reparse_ancestors(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if _is_reparse_point(ancestor):
            raise Arch148B2OperatorError("ATTEMPT_PATH_ALIAS")


def _validate_attempt_location(
    path: Path, *, evidence_root: Path | None = None
) -> None:
    evidence_root = EVIDENCE_ROOT if evidence_root is None else evidence_root
    try:
        resolved_root = evidence_root.resolve(strict=True)
    except Exception:
        raise Arch148B2OperatorError("EVIDENCE_PARENT_INVALID") from None
    if not resolved_root.is_dir() or not _same_path(resolved_root, evidence_root):
        raise Arch148B2OperatorError("EVIDENCE_PARENT_INVALID")
    _check_non_reparse_ancestors(resolved_root)
    if not path.is_absolute() or not _same_path(path.parent, resolved_root):
        raise Arch148B2OperatorError("ATTEMPT_PARENT_MISMATCH")
    if path.name != path.name.lower() or not path.name.startswith("arch148-b2-"):
        raise Arch148B2OperatorError("ATTEMPT_NAME_INVALID")
    suffix = path.name.removeprefix("arch148-b2-")
    try:
        parsed = UUID(suffix)
    except (TypeError, ValueError, AttributeError):
        raise Arch148B2OperatorError("ATTEMPT_UUID_INVALID") from None
    if str(parsed) != suffix or _same_path(path, path.resolve(strict=False)) is False:
        raise Arch148B2OperatorError("ATTEMPT_PATH_ALIAS")
    if path.exists() or path.is_symlink():
        raise Arch148B2OperatorError("ATTEMPT_ALREADY_EXISTS")


def _create_attempt_directory(
    attempt_id: str,
    expected: ExpectedSource,
    facts: SourceFacts | None,
) -> Path:
    try:
        parsed_id = UUID(attempt_id)
    except (TypeError, ValueError, AttributeError):
        raise Arch148B2OperatorError("ATTEMPT_UUID_INVALID") from None
    if str(parsed_id) != attempt_id:
        raise Arch148B2OperatorError("ATTEMPT_UUID_INVALID")
    attempt_path = EVIDENCE_ROOT / f"arch148-b2-{attempt_id}"
    _validate_attempt_location(attempt_path)
    try:
        attempt_path.mkdir()
    except FileExistsError:
        raise Arch148B2OperatorError("ATTEMPT_ALREADY_EXISTS") from None
    except OSError:
        raise Arch148B2OperatorError("ATTEMPT_CREATE_FAILED") from None
    if _is_reparse_point(attempt_path) or not _same_path(
        attempt_path, attempt_path.resolve(strict=True)
    ):
        raise Arch148B2OperatorError("ATTEMPT_PATH_ALIAS")
    claim = {
        "schema": "arch148-b2-attempt-claim/v1",
        "attempt_id": attempt_id,
        "source_branch": FEATURE_BRANCH,
        "source_head": expected.head,
        "source_tree": expected.tree,
        "live_origin_feature_head": (
            facts.live_feature_head if facts is not None else None
        ),
        "live_origin_develop_head": (
            facts.live_develop_head if facts is not None else None
        ),
        "automatic_retry": "FORBIDDEN",
    }
    try:
        claim_bytes = canonical_json_bytes(claim)
        _write_once(attempt_path / "attempt.json", claim_bytes)
        _verify_file(attempt_path / "attempt.json", claim_bytes)
    except Arch148B2OperatorError as error:
        raise Arch148B2OperatorError(error.code, attempt_path=attempt_path) from None
    return attempt_path


def _write_once(path: Path, body: bytes) -> None:
    if type(body) is not bytes:
        raise Arch148B2OperatorError("OUTPUT_BYTES_INVALID")
    _ensure_output_parent(path.parent)
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except FileExistsError:
        raise Arch148B2OperatorError("OUTPUT_COLLISION") from None
    except OSError:
        raise Arch148B2OperatorError("OUTPUT_CREATE_FAILED") from None
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            written = stream.write(body)
            if written != len(body):
                raise Arch148B2OperatorError("OUTPUT_WRITE_FAILED")
            stream.flush()
            os.fsync(stream.fileno())
    except Arch148B2OperatorError:
        raise
    except OSError:
        raise Arch148B2OperatorError("OUTPUT_WRITE_FAILED") from None


def _ensure_output_parent(parent: Path) -> None:
    try:
        attempt_root = next(
            part
            for part in (parent, *parent.parents)
            if part.name.startswith("arch148-b2-")
        )
    except StopIteration:
        raise Arch148B2OperatorError("OUTPUT_PARENT_INVALID") from None
    if not _same_path(attempt_root.parent, EVIDENCE_ROOT):
        raise Arch148B2OperatorError("OUTPUT_PARENT_INVALID")
    _check_non_reparse_ancestors(attempt_root)
    current = attempt_root
    relative_parts = parent.relative_to(attempt_root).parts
    for component in relative_parts:
        current = current / component
        try:
            current.mkdir()
        except FileExistsError:
            if not current.is_dir():
                raise Arch148B2OperatorError("OUTPUT_PARENT_INVALID") from None
        except OSError:
            raise Arch148B2OperatorError("OUTPUT_PARENT_CREATE_FAILED") from None
        if _is_reparse_point(current):
            raise Arch148B2OperatorError("ATTEMPT_PATH_ALIAS")


def _verify_file(path: Path, expected: bytes) -> None:
    try:
        observed = path.read_bytes()
    except OSError:
        raise Arch148B2OperatorError("ARTIFACT_READBACK_FAILED") from None
    if (
        len(observed) != len(expected)
        or hashlib.sha256(observed).digest() != hashlib.sha256(expected).digest()
    ):
        raise Arch148B2OperatorError("ARTIFACT_READBACK_MISMATCH")


def _write_json_once(path: Path, value: object) -> bytes:
    body = canonical_json_bytes(value)
    _write_once(path, body)
    _verify_file(path, body)
    return body


def _fetch_all_symbols(
    attempt_path: Path,
    attempt_id: str,
    expected: ExpectedSource,
    transport: StdlibAlpacaHistoricalBarsTransport,
    api_key_id: str,
    api_secret_key: str,
) -> tuple[tuple[_PageAccounting, ...], int, int, str | None]:
    all_collected: list[_PageAccounting] = []
    provider_attempts = 0
    successful_pages = 0
    for symbol in INTRADAY_SYMBOLS:
        token: str | None = None
        seen_tokens: set[str | None] = set()
        symbol_attempts = 0
        bars: list[object] = []
        page_hashes: list[str] = []
        page_sizes: list[int] = []
        request_id_hashes: list[str] = []
        previous_timestamp: datetime | None = None
        while True:
            if symbol_attempts >= MAX_PAGES_PER_SYMBOL:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    "PAGE_LIMIT_REACHED",
                )
            if provider_attempts >= MAX_PROVIDER_REQUEST_ATTEMPTS:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    "GLOBAL_REQUEST_LIMIT_REACHED",
                )
            if token in seen_tokens:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    "PAGINATION_TOKEN_LOOP",
                )
            source_failure = _local_live_source_check(expected)
            if source_failure is not None:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    source_failure,
                )
            seen_tokens.add(token)
            ordinal = symbol_attempts + 1
            request = HistoricalIntradayRequest(symbol=symbol, page_token=token)
            sequence = provider_attempts + 1
            intent = {
                "schema": "arch148-b2-request-intent/v1",
                "attempt_id": attempt_id,
                "provider_sequence": sequence,
                "symbol": symbol,
                "symbol_page_ordinal": ordinal,
                "request_descriptor_sha256": request.digest,
                "page_token_sha256": (
                    hashlib.sha256(token.encode("utf-8")).hexdigest()
                    if token is not None
                    else None
                ),
                "automatic_retry": "FORBIDDEN",
            }
            intent_path = attempt_path / "journal" / "intents" / f"{sequence:04d}.json"
            try:
                _write_json_once(intent_path, intent)
            except Arch148B2OperatorError as error:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    error.code,
                )

            # An intent with no result is conservatively MAY_HAVE_OCCURRED.
            symbol_attempts += 1
            provider_attempts += 1
            try:
                response = transport.execute(
                    build_alpaca_intraday_request(request),
                    api_key_id=api_key_id,
                    api_secret_key=api_secret_key,
                )
            except AlpacaHttpStatusError as error:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    _http_failure_code(error),
                )
            except AlpacaTransportError as error:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    _transport_failure_code(error),
                )
            except Exception:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    "TRANSPORT_AMBIGUOUS",
                )

            if type(response) is not AlpacaHttpResponse:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    "RESPONSE_INVALID",
                )
            body_sha256 = hashlib.sha256(response.body).hexdigest()
            body_size = len(response.body)
            if (
                response.status != 200
                or response.body_sha256 != body_sha256
                or response.body_byte_length != body_size
            ):
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    "RESPONSE_INVALID",
                )
            result = {
                "schema": "arch148-b2-request-result/v1",
                "attempt_id": attempt_id,
                "provider_sequence": sequence,
                "symbol": symbol,
                "symbol_page_ordinal": ordinal,
                "response_body_sha256": body_sha256,
                "response_body_byte_length": body_size,
                "request_id_sha256": hashlib.sha256(
                    response.request_id.encode("utf-8")
                ).hexdigest(),
                "http_classification": "SUCCESS_200",
            }
            result_path = attempt_path / "journal" / "results" / f"{sequence:04d}.json"
            try:
                _write_json_once(result_path, result)
                raw_path = attempt_path / "raw" / symbol / f"{ordinal:04d}.json"
                _write_once(raw_path, response.body)
                _verify_file(raw_path, response.body)
            except Arch148B2OperatorError as error:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    error.code,
                )

            # B1 parsing is deliberately after the create-once raw page write.
            try:
                page = parse_alpaca_intraday_page(response.body, request)
            except Exception:
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    "MALFORMED_PROVIDER_PAGE",
                )
            if (
                page.raw_page_sha256 != body_sha256
                or page.raw_page_byte_size != body_size
                or len(page.bars) > request.limit
            ):
                return (
                    tuple(all_collected),
                    provider_attempts,
                    successful_pages,
                    "PAGE_CUSTODY_MISMATCH",
                )
            for bar in page.bars:
                if bar.symbol.value != symbol:
                    return (
                        tuple(all_collected),
                        provider_attempts,
                        successful_pages,
                        "UNEXPECTED_SYMBOL",
                    )
                if (
                    previous_timestamp is not None
                    and bar.timestamp <= previous_timestamp
                ):
                    return (
                        tuple(all_collected),
                        provider_attempts,
                        successful_pages,
                        "PROVIDER_ORDER_INVALID",
                    )
                previous_timestamp = bar.timestamp
                bars.append(bar)
            page_hashes.append(body_sha256)
            page_sizes.append(body_size)
            request_id_hashes.append(result["request_id_sha256"])
            successful_pages += 1
            token = page.next_page_token
            if token is None:
                all_collected.append(
                    _PageAccounting(
                        symbol,
                        tuple(page_hashes),
                        tuple(page_sizes),
                        tuple(request_id_hashes),
                        tuple(bars),
                    )
                )
                break
    return tuple(all_collected), provider_attempts, successful_pages, None


def _http_failure_code(error: AlpacaHttpStatusError) -> str:
    status = error.status if type(error) is AlpacaHttpStatusError else None
    if status in (401, 403):
        return "AUTHENTICATION_OR_ENTITLEMENT"
    if status == 429:
        return "RATE_LIMIT"
    if type(status) is int and 500 <= status <= 599:
        return "PROVIDER_SERVER"
    return "HTTP_FAILURE"


def _transport_failure_code(error: AlpacaTransportError) -> str:
    stage = getattr(error, "stage", None)
    if type(stage) is str:
        stage = stage.upper()
    elif hasattr(stage, "value"):
        stage = stage.value
    if stage in {"REQUEST", "RESPONSE_START", "RESPONSE_METADATA", "RESPONSE_BODY"}:
        return f"TRANSPORT_{stage}"
    return "TRANSPORT_AMBIGUOUS"


def _qualify_dataset(
    collected: tuple[_PageAccounting, ...],
) -> tuple[IntradayDataset, IntradayCustodyEvidence]:
    if (
        type(collected) is not tuple
        or tuple(item.symbol for item in collected) != INTRADAY_SYMBOLS
    ):
        raise Arch148B2OperatorError("SYMBOL_STREAMS_INCOMPLETE_OR_REORDERED")
    if any(len(item.bars) != EXPECTED_SLOTS_PER_SYMBOL for item in collected):
        raise Arch148B2OperatorError("QUALIFICATION_BAR_COUNT_MISMATCH")
    if sum(len(item.bars) for item in collected) != EXPECTED_TOTAL_BARS:
        raise Arch148B2OperatorError("QUALIFICATION_TOTAL_BAR_COUNT_MISMATCH")
    datasets = tuple(
        IntradaySymbolDataset(item.symbol, item.bars) for item in collected
    )
    dataset = IntradayDataset(OPEN_START, OPEN_END_EXCLUSIVE, datasets)
    b1_pages = tuple(
        CollectedIntradayPages(
            item.symbol,
            item.bars,
            item.raw_page_sha256,
            item.raw_page_byte_size,
        )
        for item in collected
    )
    custody = build_intraday_custody_evidence(dataset, b1_pages)
    verify_intraday_custody_evidence(dataset, custody)
    return dataset, custody


def _write_data_artifacts(
    attempt_path: Path,
    dataset: IntradayDataset,
    custody: IntradayCustodyEvidence,
) -> tuple[dict[str, dict[str, object]], bytes, bytes]:
    normalized: dict[str, dict[str, object]] = {}
    for item in dataset.datasets:
        path = attempt_path / "normalized" / f"{item.symbol}.csv"
        body = item.normalized_bytes
        _write_once(path, body)
        _verify_file(path, body)
        normalized[item.symbol] = {
            "sha256": hashlib.sha256(body).hexdigest(),
            "byte_length": len(body),
            "bar_count": len(item.bars),
        }
    dataset_bytes = dataset.to_json().encode("utf-8")
    _write_once(attempt_path / "dataset.json", dataset_bytes)
    _verify_file(attempt_path / "dataset.json", dataset_bytes)
    custody_bytes = custody.to_json().encode("utf-8")
    _write_once(attempt_path / "custody-evidence.json", custody_bytes)
    _verify_file(attempt_path / "custody-evidence.json", custody_bytes)
    return normalized, dataset_bytes, custody_bytes


def _verify_persisted_artifacts(
    attempt_path: Path,
    collected: tuple[_PageAccounting, ...],
    normalized: dict[str, dict[str, object]],
    dataset_bytes: bytes,
    custody_bytes: bytes,
) -> None:
    """Recheck every success artifact immediately before returning SUCCESS."""

    for item in collected:
        for ordinal, (digest, size) in enumerate(
            zip(item.raw_page_sha256, item.raw_page_byte_size, strict=True), start=1
        ):
            path = attempt_path / "raw" / item.symbol / f"{ordinal:04d}.json"
            try:
                body = path.read_bytes()
            except OSError:
                raise Arch148B2OperatorError("RAW_PAGE_READBACK_FAILED") from None
            if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
                raise Arch148B2OperatorError("RAW_PAGE_READBACK_MISMATCH")
    for symbol in INTRADAY_SYMBOLS:
        path = attempt_path / "normalized" / f"{symbol}.csv"
        try:
            body = path.read_bytes()
        except OSError:
            raise Arch148B2OperatorError("NORMALIZED_READBACK_FAILED") from None
        expected = normalized[symbol]
        if (
            len(body) != expected["byte_length"]
            or hashlib.sha256(body).hexdigest() != expected["sha256"]
        ):
            raise Arch148B2OperatorError("NORMALIZED_READBACK_MISMATCH")
    _verify_file(attempt_path / "dataset.json", dataset_bytes)
    _verify_file(attempt_path / "custody-evidence.json", custody_bytes)


def _terminal_evidence(
    expected: ExpectedSource,
    facts: SourceFacts | None,
    attempt_id: str,
    credential_attempts: int,
    provider_attempts: int,
    successful_pages: int,
    collected: tuple[_PageAccounting, ...],
    dataset: IntradayDataset,
    custody: IntradayCustodyEvidence,
    dataset_bytes: bytes,
    custody_bytes: bytes,
    normalized: dict[str, dict[str, object]],
) -> dict[str, object]:
    if facts is None:
        raise Arch148B2OperatorError("SOURCE_FACTS_UNAVAILABLE")
    if credential_attempts != 1:
        raise Arch148B2OperatorError("CREDENTIAL_READ_LIMIT_EXCEEDED")
    if provider_attempts > MAX_PROVIDER_REQUEST_ATTEMPTS:
        raise Arch148B2OperatorError("GLOBAL_REQUEST_LIMIT_REACHED")
    if tuple(normalized) != INTRADAY_SYMBOLS:
        raise Arch148B2OperatorError("NORMALIZED_ARTIFACTS_INCOMPLETE")
    evidence_streams: list[dict[str, object]] = []
    for item in collected:
        if not item.raw_page_sha256 or not (
            len(item.raw_page_sha256)
            == len(item.raw_page_byte_size)
            == len(item.request_id_sha256)
        ):
            raise Arch148B2OperatorError("PAGE_EVIDENCE_INCOMPLETE")
        evidence_streams.append(
            {
                "symbol": item.symbol,
                "raw_page_sha256": list(item.raw_page_sha256),
                "raw_page_byte_size": list(item.raw_page_byte_size),
                "request_id_sha256": list(item.request_id_sha256),
                "page_count": len(item.raw_page_sha256),
                "pagination_exhausted": True,
            }
        )
    return {
        "schema": EVIDENCE_SCHEMA,
        "classification": SUCCESS_CLASSIFICATION,
        "source": {
            "branch": FEATURE_BRANCH,
            "head": expected.head,
            "tree": expected.tree,
            "live_origin_feature_head": facts.live_feature_head,
            "live_origin_develop_head": facts.live_develop_head,
        },
        "attempt_id": attempt_id,
        "dataset": {
            "schema": ARCH148_INTRADAY_DATASET_SCHEMA,
            "identity": dataset.identity,
            "sha256": hashlib.sha256(dataset_bytes).hexdigest(),
            "byte_length": len(dataset_bytes),
        },
        "custody": {
            "schema": ARCH148_INTRADAY_EVIDENCE_SCHEMA,
            "evidence_id": custody.evidence_id,
            "sha256": hashlib.sha256(custody_bytes).hexdigest(),
            "byte_length": len(custody_bytes),
        },
        "schedule": {
            "identity": ARCH148_INTRADAY_SCHEDULE_IDENTITY,
            "sha256": ARCH148_INTRADAY_SCHEDULE_DIGEST,
        },
        "request_descriptor_sha256": dataset.request_digest,
        "price_basis": PRICE_BASIS,
        "open_start": "2016-01-01T00:00:00.000000Z",
        "open_end_exclusive": "2024-01-01T00:00:00.000000Z",
        "ordered_symbols": list(INTRADAY_SYMBOLS),
        "expected_open_sessions": EXPECTED_OPEN_SESSIONS,
        "expected_early_close_sessions": EXPECTED_EARLY_CLOSE_SESSIONS,
        "expected_slots_per_symbol": EXPECTED_SLOTS_PER_SYMBOL,
        "expected_total_bars": EXPECTED_TOTAL_BARS,
        "credential_read_attempt_count": credential_attempts,
        "provider_attempt_ceiling": {
            "pages_per_symbol": MAX_PAGES_PER_SYMBOL,
            "total_provider_request_attempts": MAX_PROVIDER_REQUEST_ATTEMPTS,
        },
        "provider_request_attempt_count": provider_attempts,
        "successful_page_count": successful_pages,
        "streams": evidence_streams,
        "normalized": [
            {"symbol": symbol, **normalized[symbol]} for symbol in INTRADAY_SYMBOLS
        ],
        "automatic_retry": "FORBIDDEN",
        "robinhood_calls": 0,
        "broker_calls": 0,
        "order_mutations": 0,
        "production_state_mutations": 0,
        "final_holdout_accesses": 0,
        "baseline_backtests": 0,
    }


def _write_failure_record(
    attempt_path: Path,
    attempt_id: str,
    failure_code: str,
    credential_attempts: int,
    provider_attempts: int,
    successful_pages: int,
) -> None:
    unresolved_intent = False
    try:
        intent_paths = tuple((attempt_path / "journal" / "intents").glob("*.json"))
        result_root = attempt_path / "journal" / "results"
        unresolved_intent = any(
            not (result_root / intent.name).is_file() for intent in intent_paths
        )
    except OSError:
        unresolved_intent = provider_attempts > successful_pages
    failure = {
        "schema": "arch148-b2-blocked-attempt/v1",
        "classification": "BLOCKED",
        "failure_code": failure_code,
        "attempt_id": attempt_id,
        "credential_read_attempt_count": credential_attempts,
        "provider_request_attempt_count": provider_attempts,
        "successful_page_count": successful_pages,
        "unresolved_intent_status": (
            "MAY_HAVE_OCCURRED" if unresolved_intent else "NONE"
        ),
        "automatic_retry": "FORBIDDEN",
        "robinhood_calls": 0,
        "broker_calls": 0,
        "order_mutations": 0,
        "production_state_mutations": 0,
        "final_holdout_accesses": 0,
        "baseline_backtests": 0,
    }
    try:
        _write_json_once(attempt_path / "failure.json", failure)
    except Arch148B2OperatorError:
        # Failure evidence is best effort; the outcome remains closed and safe.
        return


__all__ = [
    "ACQUISITION_INTERLOCK",
    "AcquisitionOutcome",
    "Arch148B2OperatorError",
    "EVIDENCE_SCHEMA",
    "ExpectedSource",
    "SourceAdmission",
    "SourceFacts",
    "SUCCESS_CLASSIFICATION",
    "acquire_arch148_b2",
    "main",
    "operator_help",
    "preflight_source",
]


if __name__ == "__main__":
    raise SystemExit(main())
