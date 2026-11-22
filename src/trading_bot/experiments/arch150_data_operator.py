"""One-shot Architecture 150 historical-data custody operator boundary.

Import and help are effect-free. The interlocked entry point is reserved for a
separately reviewed real-data execution after this exact source is accepted and
integrated. Tests inject every effectful adapter and never use real secrets or
the network.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns, sleep
from typing import Final, Protocol
from uuid import UUID, uuid4

from trading_bot.experiments.arch150_intraday_data import (
    MAX_PAGES_PER_SYMBOL,
    MAX_PROVIDER_REQUEST_ATTEMPTS,
    Arch150DataError,
    Arch150HistoricalRequest,
    DatasetClassification,
    SymbolPageCollection,
    build_alpaca_request,
    build_custody_evidence,
    collect_symbol_pages,
    qualify_arch150_dataset,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

FEATURE_BRANCH: Final = "feature/research-arch150-intraday-ai-current"
CANONICAL_ORIGIN: Final = "https://github.com/callmedraken/ai-trading-bot.git"
CANONICAL_WORKTREE: Final = Path(
    r"F:\AI\worktrees\ai-trading-bot-arch150-intraday-ai-current"
)
DATA_ROOT: Final = Path(r"F:\AI\research-data\arch150-intraday-data-custody")
ACQUISITION_INTERLOCK: Final = (
    "ACQUIRE ARCH150 SPY QQQ 1MIN 2016-2023 READ ONLY ONCE; NO RETRY"
)
SUCCESS_CLASSIFICATION: Final = "READY_FOR_ARCH150_DATA_CUSTODY_REVIEW"
MIN_PROVIDER_REQUEST_START_INTERVAL_SECONDS: Final = 0.5
_MIN_PROVIDER_REQUEST_START_INTERVAL_NS: Final = int(
    MIN_PROVIDER_REQUEST_START_INTERVAL_SECONDS * 1_000_000_000
)
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_PROTECTED_REPOSITORY = Path(r"F:\AI\ai-trading-bot")
_PROTECTED_WORKTREES = Path(r"F:\AI\worktrees")


class Arch150OperatorError(RuntimeError):
    """Sanitized one-shot stop reason."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ExpectedSource:
    head: str
    tree: str

    def __post_init__(self) -> None:
        if type(self.head) is not str or _SHA1.fullmatch(self.head) is None:
            raise ValueError("expected HEAD must be lowercase SHA-1")
        if type(self.tree) is not str or _SHA1.fullmatch(self.tree) is None:
            raise ValueError("expected tree must be lowercase SHA-1")


@dataclass(frozen=True, slots=True)
class SourceFacts:
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
    passed: bool
    failure_code: str | None
    facts: SourceFacts | None
    feature_authority_passed: bool
    prospective_develop_authority_passed: bool


@dataclass(frozen=True, slots=True)
class AcquisitionOutcome:
    classification: str
    attempt_id: str | None
    attempt_directory: Path | None
    credential_read_attempt_count: int
    provider_request_attempt_count: int
    successful_page_count: int
    dataset_identity: str | None = None
    dataset_sha256: str | None = None
    evidence_sha256: str | None = None
    failure_code: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.classification == SUCCESS_CLASSIFICATION


class HistoricalBarsTransport(Protocol):
    def execute(
        self,
        request: object,
        *,
        api_key_id: str,
        api_secret_key: str,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class OperatorAdapters:
    """Injectable boundaries; production defaults are created lazily."""

    source_probe: Callable[[], SourceFacts]
    authority_evaluator: Callable[[Path, str], object]
    credential_reader: Callable[[], object]
    credential_scope_validator: Callable[[object], bool]
    transport_factory: Callable[[], HistoricalBarsTransport]
    monotonic_clock: Callable[[], int]
    sleep_fn: Callable[[float], None]
    attempt_id_factory: Callable[[], str]


def operator_help() -> str:
    """Return effect-free operator guidance."""

    return (
        "Architecture 150 D1 source boundary. Import and help are effect-free. "
        "Real acquisition requires the exact accepted/integrated source, the "
        "one-shot interlock, and a separate review. A failed attempt is never retried."
    )


def main(argv: list[str] | None = None) -> int:
    """Expose effect-free source preflight and the separately interlocked entry."""

    parser = argparse.ArgumentParser(description=operator_help())
    actions = parser.add_subparsers(dest="action")
    for action, help_text in (
        ("preflight", "read-only exact-source admission"),
        ("acquire", "one separately reviewed historical-data acquisition"),
    ):
        command = actions.add_parser(action, help=help_text)
        command.add_argument("--expected-head", required=True)
        command.add_argument("--expected-tree", required=True)
    actions.choices["acquire"].add_argument("--interlock", required=True)
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
        if result.failure_code is not None:
            print("FAILURE_CODE=" + result.failure_code)
        return 0 if result.passed else 1
    outcome = acquire_arch150_intraday_data(
        interlock=arguments.interlock,
        expected_head=arguments.expected_head,
        expected_tree=arguments.expected_tree,
    )
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
    return 0 if outcome.succeeded else 1


def preflight_source(
    expected: ExpectedSource, *, adapters: OperatorAdapters | None = None
) -> SourceAdmission:
    """Prove exact local/live source plus FEATURE and prospective authority."""

    selected = _default_adapters() if adapters is None else adapters
    return _source_admission(expected, selected)


def acquire_arch150_intraday_data(
    *,
    interlock: str,
    expected_head: str,
    expected_tree: str,
    adapters: OperatorAdapters | None = None,
) -> AcquisitionOutcome:
    """Run the one-shot effect boundary; real callers use the fixed F: data root."""

    if type(interlock) is not str or interlock != ACQUISITION_INTERLOCK:
        return _blocked("INTERLOCK_REQUIRED")
    try:
        expected = ExpectedSource(expected_head, expected_tree)
    except (TypeError, ValueError):
        return _blocked("EXPECTED_SOURCE_INVALID")
    selected = _default_adapters() if adapters is None else adapters
    return _run_one_shot(expected, selected, output_root=DATA_ROOT)


def _run_one_shot(
    expected: ExpectedSource,
    adapters: OperatorAdapters,
    *,
    output_root: Path,
    _test_output_root_validator: Callable[[Path], None] | None = None,
) -> AcquisitionOutcome:
    """Run an injected one-shot attempt; production omits the test validator."""

    initial = _source_admission(expected, adapters)
    if not initial.passed:
        return _blocked(initial.failure_code or "SOURCE_ADMISSION_FAILED")
    try:
        attempt_id = adapters.attempt_id_factory()
        attempt_path = _create_attempt_directory(
            attempt_id,
            expected,
            initial.facts,
            output_root=output_root,
            output_root_validator=_test_output_root_validator,
        )
    except Arch150OperatorError as error:
        return _blocked(error.code)
    except Exception:
        return _blocked("ATTEMPT_CREATE_FAILED")

    credential_attempts = 0
    provider_attempts = 0
    successful_pages = 0
    failure_code: str | None = None
    collections: list[SymbolPageCollection] = []

    before_credentials = _source_admission(expected, adapters)
    if not before_credentials.passed:
        failure_code = before_credentials.failure_code or "SOURCE_DRIFT"
    scope: object | None = None
    if failure_code is None:
        credential_attempts = 1
        try:
            scope = adapters.credential_reader()
        except Exception:
            failure_code = "CREDENTIAL_READ_FAILED"
        if failure_code is None:
            try:
                scope_valid = adapters.credential_scope_validator(scope)
            except Exception:
                scope_valid = False
            if not scope_valid:
                _close_scope(scope)
                scope = None
                failure_code = "CREDENTIAL_SCOPE_INVALID"

    if failure_code is None and scope is not None:
        try:
            with scope:  # type: ignore[attr-defined]
                transport = adapters.transport_factory()

                def use_secrets(key: str, secret: str) -> None:
                    nonlocal provider_attempts, successful_pages, failure_code
                    previous_start_ns: int | None = None
                    for symbol in ("SPY", "QQQ"):
                        if failure_code is not None:
                            break

                        def fetch(request: Arch150HistoricalRequest) -> bytes:
                            nonlocal provider_attempts, successful_pages
                            nonlocal previous_start_ns
                            if provider_attempts >= MAX_PROVIDER_REQUEST_ATTEMPTS:
                                raise Arch150DataError("GLOBAL_REQUEST_LIMIT_REACHED")
                            drift = _current_source_failure(
                                expected, adapters.source_probe
                            )
                            if drift is not None:
                                raise Arch150DataError(drift)
                            now = adapters.monotonic_clock()
                            if previous_start_ns is not None:
                                elapsed = now - previous_start_ns
                                if elapsed < 0:
                                    raise Arch150DataError("PACING_CLOCK_INVALID")
                                remaining = (
                                    _MIN_PROVIDER_REQUEST_START_INTERVAL_NS - elapsed
                                )
                                if remaining > 0:
                                    adapters.sleep_fn(remaining / 1_000_000_000)
                                    now = adapters.monotonic_clock()
                                    if now - previous_start_ns < (
                                        _MIN_PROVIDER_REQUEST_START_INTERVAL_NS
                                    ):
                                        raise Arch150DataError("PACING_INTERVAL_FAILED")
                            previous_start_ns = now
                            provider_attempts += 1
                            try:
                                response = transport.execute(
                                    build_alpaca_request(request),
                                    api_key_id=key,
                                    api_secret_key=secret,
                                )
                            except Exception:
                                raise Arch150DataError(
                                    "PROVIDER_REQUEST_FAILED"
                                ) from None
                            body = getattr(response, "body", None)
                            body_hash = getattr(response, "body_sha256", None)
                            body_length = getattr(response, "body_byte_length", None)
                            if (
                                getattr(response, "status", None) != 200
                                or getattr(response, "media_type", None)
                                != "application/json"
                                or type(body) is not bytes
                                or type(body_hash) is not str
                                or hashlib.sha256(body).hexdigest() != body_hash
                                or type(body_length) is not int
                                or body_length != len(body)
                            ):
                                raise Arch150DataError("PROVIDER_RESPONSE_INVALID")
                            successful_pages += 1
                            return body

                        def persist(
                            symbol_name: str, ordinal: int, body: bytes
                        ) -> None:
                            try:
                                _write_once(
                                    attempt_path
                                    / "raw"
                                    / symbol_name
                                    / f"{ordinal:04d}.bin",
                                    body,
                                    attempt_path=attempt_path,
                                )
                            except Arch150OperatorError as error:
                                raise Arch150DataError(error.code) from None

                        collection = collect_symbol_pages(
                            symbol,
                            fetch,
                            persist,
                            max_pages=MAX_PAGES_PER_SYMBOL,
                        )
                        collections.append(collection)
                        if collection.failure_code is not None:
                            failure_code = collection.failure_code
                    for symbol in ("SPY", "QQQ")[len(collections) :]:
                        collections.append(_not_attempted_collection(symbol))

                scope.use(use_secrets)  # type: ignore[attr-defined]
        except Exception:
            if failure_code is None:
                failure_code = "CREDENTIAL_SCOPE_FAILED"
        finally:
            _close_scope(scope)

    if len(collections) < 2:
        collections.extend(
            _not_attempted_collection(symbol)
            for symbol in ("SPY", "QQQ")[len(collections) :]
        )
    try:
        dataset = qualify_arch150_dataset(tuple(collections))
    except Exception:
        dataset = None
        failure_code = failure_code or "DATASET_QUALIFICATION_FAILED"

    evidence_bytes: bytes | None = None
    if dataset is not None:
        try:
            evidence = build_custody_evidence(
                dataset,
                source_head=expected.head,
                source_tree=expected.tree,
                credential_read_attempt_count=credential_attempts,
                provider_request_attempt_count=provider_attempts,
            )
            evidence_bytes = evidence.to_bytes()
            _write_once(
                attempt_path / "custody-evidence.json",
                evidence_bytes,
                attempt_path=attempt_path,
            )
            if dataset.classification is DatasetClassification.READY:
                _write_once(
                    attempt_path / "normalized.csv",
                    dataset.normalized_bytes,
                    attempt_path=attempt_path,
                )
            final_source_failure = _current_source_failure(
                expected, adapters.source_probe
            )
            if final_source_failure is not None:
                failure_code = final_source_failure
            manifest = {
                "schema": "arch150-data-operator-attempt-result/v1",
                "classification": (
                    SUCCESS_CLASSIFICATION
                    if failure_code is None
                    and dataset.classification is DatasetClassification.READY
                    else "BLOCKED"
                ),
                "failure_code": failure_code
                or (dataset.failure_codes[0] if dataset.failure_codes else None),
                "source_head": expected.head,
                "source_tree": expected.tree,
                "dataset_identity": str(dataset.identity),
                "dataset_sha256": dataset.sha256,
                "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
                "credential_read_attempt_count": credential_attempts,
                "provider_request_attempt_count": provider_attempts,
                "successful_page_count": successful_pages,
                "automatic_retry": "FORBIDDEN",
            }
            _write_once(
                attempt_path / "attempt-result.json",
                canonical_json_bytes(manifest),
                attempt_path=attempt_path,
            )
        except Arch150OperatorError as error:
            failure_code = failure_code or error.code
    if dataset is None:
        return AcquisitionOutcome(
            "BLOCKED",
            attempt_id,
            attempt_path,
            credential_attempts,
            provider_attempts,
            successful_pages,
            failure_code=failure_code,
        )
    success = (
        failure_code is None and dataset.classification is DatasetClassification.READY
    )
    return AcquisitionOutcome(
        SUCCESS_CLASSIFICATION if success else "BLOCKED",
        attempt_id,
        attempt_path,
        credential_attempts,
        provider_attempts,
        successful_pages,
        str(dataset.identity),
        dataset.sha256,
        hashlib.sha256(evidence_bytes).hexdigest() if evidence_bytes else None,
        failure_code
        or (
            None
            if success
            else dataset.failure_codes[0]
            if dataset.failure_codes
            else "DATASET_BLOCKED"
        ),
    )


def _not_attempted_collection(symbol: str) -> SymbolPageCollection:
    return SymbolPageCollection(
        symbol=symbol,
        pages=(),
        bars=(),
        terminal_state="NOT_ATTEMPTED",
        failure_code="NOT_ATTEMPTED_AFTER_STOP",
        parsed_page_count=0,
        raw_bar_count=None,
    )


def _blocked(code: str) -> AcquisitionOutcome:
    return AcquisitionOutcome("BLOCKED", None, None, 0, 0, 0, failure_code=code)


def _close_scope(scope: object | None) -> None:
    close = getattr(scope, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def _default_adapters() -> OperatorAdapters:
    def evaluate(root: Path, context: str) -> object:
        from scripts.current_source_authority import (
            PublicationContext,
            evaluate_source_authority,
        )

        return evaluate_source_authority(
            root,
            publication_context=PublicationContext(context),
        )

    def credential_scope_valid(scope: object) -> bool:
        from trading_bot.review_paper.alpaca_windows_credentials import (
            ScopedAlpacaSecrets,
        )

        return type(scope) is ScopedAlpacaSecrets

    def read_credentials() -> object:
        from trading_bot.review_paper.alpaca_windows_credentials import (
            read_current_product_alpaca_secrets,
        )

        return read_current_product_alpaca_secrets()

    def transport() -> HistoricalBarsTransport:
        from trading_bot.market_data.alpaca_http import (
            StdlibAlpacaHistoricalBarsTransport,
        )

        return StdlibAlpacaHistoricalBarsTransport()

    return OperatorAdapters(
        source_probe=_read_source_facts,
        authority_evaluator=evaluate,
        credential_reader=read_credentials,
        credential_scope_validator=credential_scope_valid,
        transport_factory=transport,
        monotonic_clock=monotonic_ns,
        sleep_fn=sleep,
        attempt_id_factory=lambda: str(uuid4()),
    )


def _source_admission(
    expected: ExpectedSource, adapters: OperatorAdapters
) -> SourceAdmission:
    if type(expected) is not ExpectedSource:
        return SourceAdmission(False, "EXPECTED_SOURCE_INVALID", None, False, False)
    try:
        facts = adapters.source_probe()
    except Exception:
        return SourceAdmission(False, "SOURCE_PROBE_FAILED", None, False, False)
    failure = _source_facts_failure(expected, facts)
    feature_passed = False
    prospective_passed = False
    if failure is None:
        try:
            feature = adapters.authority_evaluator(CANONICAL_WORKTREE, "FEATURE")
            prospective = adapters.authority_evaluator(
                CANONICAL_WORKTREE, "PROSPECTIVE_DEVELOP"
            )
            feature_passed = bool(
                getattr(feature, "passed", False)
                and getattr(feature, "head", None) == expected.head
                and getattr(feature, "tree", None) == expected.tree
            )
            prospective_passed = bool(
                getattr(prospective, "passed", False)
                and getattr(prospective, "head", None) == expected.head
                and getattr(prospective, "tree", None) == expected.tree
            )
            if not feature_passed or not prospective_passed:
                failure = "SOURCE_AUTHORITY_FAILED"
            latest = adapters.source_probe()
            latest_failure = _source_facts_failure(expected, latest)
            if latest_failure is not None:
                failure = latest_failure
                facts = latest
        except Exception:
            failure = "SOURCE_AUTHORITY_UNAVAILABLE"
    return SourceAdmission(
        failure is None,
        failure,
        facts,
        feature_passed,
        prospective_passed,
    )


def _current_source_failure(
    expected: ExpectedSource, probe: Callable[[], SourceFacts]
) -> str | None:
    try:
        return _source_facts_failure(expected, probe())
    except Exception:
        return "SOURCE_PROBE_FAILED"


def _source_facts_failure(expected: ExpectedSource, facts: SourceFacts) -> str | None:
    if type(facts) is not SourceFacts:
        return "SOURCE_FACTS_INVALID"
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


def _git_text(*arguments: str) -> str:
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=CANONICAL_WORKTREE,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env={
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GCM_INTERACTIVE": "Never",
                "GIT_OPTIONAL_LOCKS": "0",
            },
        )
    except Exception:
        raise Arch150OperatorError("SOURCE_PROBE_FAILED") from None
    if result.returncode != 0:
        raise Arch150OperatorError("SOURCE_PROBE_FAILED")
    return result.stdout.strip()


def _read_source_facts() -> SourceFacts:
    try:
        resolved_root = CANONICAL_WORKTREE.resolve(strict=True)
        if not _same_path(resolved_root, CANONICAL_WORKTREE):
            raise Arch150OperatorError("CANONICAL_WORKTREE_MISMATCH")
        top = Path(_git_text("rev-parse", "--show-toplevel")).resolve(strict=True)
        live = _git_text(
            "ls-remote",
            "--heads",
            "origin",
            f"refs/heads/{FEATURE_BRANCH}",
            "refs/heads/develop",
        )
        refs = {
            fields[1]: fields[0]
            for line in live.splitlines()
            if len(fields := line.split("\t")) == 2
        }
        return SourceFacts(
            str(top),
            _git_text("branch", "--show-current"),
            _git_text("rev-parse", "HEAD"),
            _git_text("rev-parse", "HEAD^{tree}"),
            _git_text("remote", "get-url", "origin"),
            _git_text("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"),
            _git_text("status", "--porcelain=v1", "--untracked-files=all"),
            refs.get(f"refs/heads/{FEATURE_BRANCH}", ""),
            refs.get("refs/heads/develop", ""),
        )
    except Arch150OperatorError:
        raise
    except Exception:
        raise Arch150OperatorError("SOURCE_PROBE_FAILED") from None


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
        os.path.abspath(str(right))
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(str(path))).relative_to(Path(os.path.abspath(str(parent))))
        return True
    except ValueError:
        return False


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
            raise Arch150OperatorError("OUTPUT_PATH_ALIAS")


def _validate_output_root(path: Path) -> None:
    if not path.is_absolute() or path.drive.upper() != "F:":
        raise Arch150OperatorError("OUTPUT_ROOT_MUST_BE_ON_F")
    if (
        _is_within(path, _PROTECTED_REPOSITORY)
        or _is_within(_PROTECTED_REPOSITORY, path)
        or _is_within(path, _PROTECTED_WORKTREES)
        or _is_within(_PROTECTED_WORKTREES, path)
    ):
        raise Arch150OperatorError("OUTPUT_ROOT_INSIDE_REPOSITORY_OR_WORKTREE")
    _check_non_reparse_ancestors(path)
    existing = next((item for item in (path, *path.parents) if item.exists()), None)
    if existing is None or not existing.is_dir():
        raise Arch150OperatorError("OUTPUT_ROOT_PARENT_INVALID")
    try:
        if not _same_path(existing.resolve(strict=True), existing):
            raise Arch150OperatorError("OUTPUT_PATH_ALIAS")
    except Arch150OperatorError:
        raise
    except Exception:
        raise Arch150OperatorError("OUTPUT_ROOT_PARENT_INVALID") from None


def _create_attempt_directory(
    attempt_id: str,
    expected: ExpectedSource,
    facts: SourceFacts | None,
    *,
    output_root: Path,
    output_root_validator: Callable[[Path], None] | None = None,
) -> Path:
    try:
        parsed = UUID(attempt_id)
    except (TypeError, ValueError, AttributeError):
        raise Arch150OperatorError("ATTEMPT_UUID_INVALID") from None
    if str(parsed) != attempt_id:
        raise Arch150OperatorError("ATTEMPT_UUID_INVALID")
    validator = (
        _validate_output_root
        if output_root_validator is None
        else output_root_validator
    )
    validator(output_root)
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        _check_non_reparse_ancestors(output_root)
        if not _same_path(output_root.resolve(strict=True), output_root):
            raise Arch150OperatorError("OUTPUT_PATH_ALIAS")
        attempt = output_root / f"arch150-d1-{attempt_id}"
        attempt.mkdir()
    except FileExistsError:
        raise Arch150OperatorError("ATTEMPT_ALREADY_EXISTS") from None
    except Arch150OperatorError:
        raise
    except OSError:
        raise Arch150OperatorError("ATTEMPT_CREATE_FAILED") from None
    if _is_reparse_point(attempt) or not _same_path(
        attempt.resolve(strict=True), attempt
    ):
        raise Arch150OperatorError("OUTPUT_PATH_ALIAS")
    claim = {
        "schema": "arch150-data-attempt-claim/v1",
        "attempt_id": attempt_id,
        "source_branch": FEATURE_BRANCH,
        "source_head": expected.head,
        "source_tree": expected.tree,
        "live_feature_head": facts.live_feature_head if facts else None,
        "live_develop_head": facts.live_develop_head if facts else None,
        "automatic_retry": "FORBIDDEN",
    }
    _write_once(
        attempt / "attempt.json",
        canonical_json_bytes(claim),
        attempt_path=attempt,
    )
    return attempt


def _ensure_output_parent(parent: Path, *, attempt_path: Path) -> None:
    try:
        parent.relative_to(attempt_path)
    except ValueError:
        raise Arch150OperatorError("OUTPUT_PARENT_INVALID") from None
    _check_non_reparse_ancestors(attempt_path)
    current = attempt_path
    for component in parent.relative_to(attempt_path).parts:
        current = current / component
        try:
            current.mkdir()
        except FileExistsError:
            if not current.is_dir():
                raise Arch150OperatorError("OUTPUT_PARENT_INVALID") from None
        except OSError:
            raise Arch150OperatorError("OUTPUT_PARENT_CREATE_FAILED") from None
        if _is_reparse_point(current):
            raise Arch150OperatorError("OUTPUT_PATH_ALIAS")


def _write_once(path: Path, body: bytes, *, attempt_path: Path) -> None:
    if type(body) is not bytes:
        raise Arch150OperatorError("OUTPUT_BYTES_INVALID")
    _ensure_output_parent(path.parent, attempt_path=attempt_path)
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except FileExistsError:
        raise Arch150OperatorError("OUTPUT_COLLISION") from None
    except OSError:
        raise Arch150OperatorError("OUTPUT_CREATE_FAILED") from None
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            if stream.write(body) != len(body):
                raise Arch150OperatorError("OUTPUT_WRITE_FAILED")
            stream.flush()
            os.fsync(stream.fileno())
    except Arch150OperatorError:
        raise
    except OSError:
        raise Arch150OperatorError("OUTPUT_WRITE_FAILED") from None
    try:
        stored = path.read_bytes()
    except OSError:
        raise Arch150OperatorError("ARTIFACT_READBACK_FAILED") from None
    if (
        len(stored) != len(body)
        or hashlib.sha256(stored).digest() != hashlib.sha256(body).digest()
    ):
        raise Arch150OperatorError("ARTIFACT_READBACK_MISMATCH")


__all__ = [
    "ACQUISITION_INTERLOCK",
    "AcquisitionOutcome",
    "Arch150OperatorError",
    "DATA_ROOT",
    "ExpectedSource",
    "OperatorAdapters",
    "SourceAdmission",
    "SourceFacts",
    "SUCCESS_CLASSIFICATION",
    "acquire_arch150_intraday_data",
    "main",
    "operator_help",
    "preflight_source",
]


if __name__ == "__main__":
    raise SystemExit(main())
