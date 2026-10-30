"""Architecture 147 interactive acquisition composition; import is inert."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from trading_bot.experiments.historical_research_acquisition import (
    AcquisitionCredentials,
    AcquisitionTransport,
    HistoricalResearchAcquisitionOperator,
    HistoricalResearchRequest,
    HistoricalResearchResponse,
)
from trading_bot.experiments.historical_research_custody import (
    HistoricalSessionAuthority,
    published_historical_session_authority,
    require_accepted_historical_session_authority,
)
from trading_bot.experiments.historical_research_desktop import (
    DESKTOP_RESEARCH_ROOT,
    DesktopResearchStorage,
    inspect_desktop_dataset_integrity,
    load_desktop_open_research,
)
from trading_bot.experiments.historical_research_native import (
    HttpsHistoricalResearchTransport,
    interactive_research_credentials,
)

CANONICAL_PROJECT_ROOT = Path(r"F:\AI\ai-trading-bot")
CANONICAL_ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"


class DesktopAcquisitionError(Exception):
    """A closed stage/classification pair, with no underlying exception text."""

    def __init__(self, stage: str, classification: str) -> None:
        self.stage = stage
        self.classification = classification
        super().__init__(classification)


def _require_identity(head: str, tree: str) -> None:
    if any(
        type(value) is not str or re.fullmatch(r"[0-9a-f]{40}", value) is None
        for value in (head, tree)
    ):
        raise DesktopAcquisitionError("SOURCE", "SOURCE_IDENTITY_MISMATCH")


@dataclass(frozen=True, slots=True)
class DesktopAcquisitionSource:
    head: str
    tree: str


def verify_desktop_acquisition_source(
    repository: Path, *, expected_head: str, expected_tree: str
) -> DesktopAcquisitionSource:
    """Read local Git only. No fetch, host observer, or untracked enumeration."""
    _require_identity(expected_head, expected_tree)
    failed = False
    try:
        if repository.resolve() != CANONICAL_PROJECT_ROOT.resolve():
            raise ValueError

        def git(*args: str) -> str:
            result = subprocess.run(
                ["git", "-C", str(repository), *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout.strip()

        if (
            Path(git("rev-parse", "--show-toplevel")).resolve()
            != CANONICAL_PROJECT_ROOT.resolve()
            or git("branch", "--show-current") != "develop"
            or git("rev-parse", "HEAD") != expected_head
            or git("rev-parse", "HEAD^{tree}") != expected_tree
            or git("status", "--porcelain=v1", "--untracked-files=no")
            or git("remote", "get-url", "origin") != CANONICAL_ORIGIN
            or git("rev-parse", "refs/remotes/origin/develop") != expected_head
        ):
            raise ValueError
    except Exception:
        failed = True
    if failed:
        raise DesktopAcquisitionError("SOURCE", "SOURCE_IDENTITY_MISMATCH")
    return DesktopAcquisitionSource(expected_head, expected_tree)


class DesktopInteractiveResearchCredentialSource:
    """One exact-source/accepted-calendar binding and one hidden terminal read."""

    def __init__(self, *, expected_head: str, expected_tree: str) -> None:
        _require_identity(expected_head, expected_tree)
        self._expected = (expected_head, expected_tree)
        self._bound = False
        self._used = False

    def __repr__(self) -> str:
        return "DesktopInteractiveResearchCredentialSource(<redacted>)"

    def bind_acquisition(
        self,
        *,
        source_head: str,
        source_tree: str,
        session_authority: HistoricalSessionAuthority,
    ) -> None:
        if self._used:
            raise DesktopAcquisitionError("CREDENTIAL_BINDING", "BINDING_REJECTED")
        self._used = True
        if (source_head, source_tree) != self._expected:
            raise DesktopAcquisitionError(
                "CREDENTIAL_BINDING", "SOURCE_IDENTITY_MISMATCH"
            )
        failed = False
        try:
            require_accepted_historical_session_authority(session_authority)
        except Exception:
            failed = True
        if failed:
            raise DesktopAcquisitionError(
                "CREDENTIAL_BINDING", "SESSION_AUTHORITY_REJECTED"
            )
        self._bound = True

    def read(self) -> AcquisitionCredentials:
        if not self._bound:
            raise DesktopAcquisitionError("CREDENTIALS", "CREDENTIAL_INPUT_REJECTED")
        self._bound = False
        result = None
        try:
            result = interactive_research_credentials()
            if type(result) is AcquisitionCredentials:
                result.verify()
        except BaseException:
            result = None
        if type(result) is not AcquisitionCredentials:
            raise DesktopAcquisitionError("CREDENTIALS", "CREDENTIAL_INPUT_REJECTED")
        return result


class _ObservedTransport:
    """Retain only a sanitized failure category while the kernel owns requests."""

    def __init__(self, transport: AcquisitionTransport) -> None:
        self.transport = transport
        self.failure: str | None = None

    def get(
        self, request: HistoricalResearchRequest, credentials: AcquisitionCredentials
    ) -> HistoricalResearchResponse:
        result = None
        try:
            result = self.transport.get(request, credentials)
        except Exception:
            self.failure = "TRANSPORT_FAILURE"
        if result is None:
            raise DesktopAcquisitionError("PROVIDER", "TRANSPORT_FAILURE")
        if type(result) is HistoricalResearchResponse and type(result.status) is int:
            if result.status in (401, 403):
                self.failure = "HTTP_AUTH_OR_ENTITLEMENT"
            elif result.status == 429:
                self.failure = "HTTP_RATE_LIMIT"
            elif 500 <= result.status <= 599:
                self.failure = "HTTP_SERVER"
        return result


class _ObservedPersistence:
    """Delegate persistence unchanged, recording only failed filesystem stages."""

    def __init__(self, storage: DesktopResearchStorage) -> None:
        self.storage = storage
        self.failure: str | None = None

    def __getattr__(self, name: str):
        method = getattr(self.storage, name)
        if name not in {
            "prepare",
            "persist_raw",
            "persist_private",
            "materialize_open",
            "record_terminal",
        }:
            return method

        def call(*args, **kwargs):
            failed = False
            result = None
            try:
                result = method(*args, **kwargs)
            except Exception:
                failed = True
                self.failure = "PERSISTENCE_FAILURE"
            if failed:
                raise DesktopAcquisitionError("STORAGE", "PERSISTENCE_FAILURE")
            return result

        return call


def _require_destination_absent(root: Path) -> None:
    if root.exists() or root.is_symlink():
        raise DesktopAcquisitionError("DESTINATION", "PREEXISTING_DESTINATION")


def acquire_desktop_research(
    source: DesktopAcquisitionSource,
    *,
    attempt_id: str,
    storage: DesktopResearchStorage,
    transport: AcquisitionTransport,
) -> dict[str, object]:
    """Compose the shared kernel; explicit injection supports effect-free tests.

    The production caller must first run verify_desktop_acquisition_source.
    This function never retries and refuses even an empty existing root.
    """
    _require_identity(source.head, source.tree)
    authority = published_historical_session_authority()
    require_accepted_historical_session_authority(authority)
    _require_destination_absent(storage.root)
    # Exclusive ordinary creation also closes the check/create race. The kernel
    # prepares subdirectories before calling the credential source's read().
    failed = False
    try:
        storage.root.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise DesktopAcquisitionError(
            "DESTINATION", "PREEXISTING_DESTINATION"
        ) from None
    except Exception:
        failed = True
    if failed:
        raise DesktopAcquisitionError("STORAGE", "PERSISTENCE_FAILURE")
    credentials = DesktopInteractiveResearchCredentialSource(
        expected_head=source.head, expected_tree=source.tree
    )
    observed = _ObservedTransport(transport)
    persistence = _ObservedPersistence(storage)
    outcome = HistoricalResearchAcquisitionOperator(
        observed, credentials, persistence
    ).run(
        source_head=source.head,
        source_tree=source.tree,
        attempt_id=attempt_id,
        session_authority=authority,
    )
    if outcome.state != "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION":
        stage, _, reason = outcome.stage.partition(":")
        category = persistence.failure or _failure_category(
            stage, reason, observed.failure
        )
        raise DesktopAcquisitionError(stage, category)
    summary = None
    try:
        summary = inspect_desktop_dataset_integrity(storage)
        load_desktop_open_research(storage)
    except Exception:
        failed = True
    if failed:
        raise DesktopAcquisitionError("INTEGRITY", "DATASET_VALIDATION_FAILURE")
    return {
        "status": "SUCCESS",
        "root": str(storage.root),
        **summary.to_dict(),
        "OPEN_LOADER": "PASS",
        "FULL_DATASET_INTEGRITY": "PASS",
    }


def _failure_category(stage: str, reason: str, transport_failure: str | None) -> str:
    if reason in {"HTTP_AUTH_OR_ENTITLEMENT", "HTTP_RATE_LIMIT", "HTTP_SERVER"}:
        return reason
    if transport_failure:
        return transport_failure
    if reason in {
        "PAGE_REPLAY",
        "TOKEN_LOOP",
        "PAGINATION_BOUND",
        "MISSING_TERMINAL_STATE",
    }:
        return "PAGINATION_REPLAY_FAILURE"
    if stage == "CREDENTIALS":
        return "CREDENTIAL_INPUT_REJECTED"
    if stage in {"PREPARE_STORAGE", "DATASET_PERSISTENCE", "OPEN_MATERIALIZATION"} or (
        reason == "TERMINAL_EVIDENCE_PERSISTENCE_AMBIGUITY"
    ):
        return "PERSISTENCE_FAILURE"
    if stage in {"BARS_ACQUISITION", "CORPORATE_ACTION_ACQUISITION"}:
        return "UNEXPECTED_RESPONSE_SHAPE"
    return "DATASET_VALIDATION_FAILURE"


def run_production_acquisition(
    repository: Path, *, expected_head: str, expected_tree: str, attempt_id: str
) -> dict[str, object]:
    """The sole production composition: source -> authority -> absent destination."""
    source = verify_desktop_acquisition_source(
        repository, expected_head=expected_head, expected_tree=expected_tree
    )
    require_accepted_historical_session_authority(
        published_historical_session_authority()
    )
    _require_destination_absent(DESKTOP_RESEARCH_ROOT)
    return acquire_desktop_research(
        source,
        attempt_id=attempt_id,
        storage=DesktopResearchStorage.production(),
        transport=HttpsHistoricalResearchTransport(),
    )
