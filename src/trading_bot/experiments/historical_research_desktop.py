"""Current single-user desktop research storage and explicit data boundaries.

This module is intentionally an ordinary filesystem profile.  It contains no
Windows security, identity, elevation, provider, credential or brokerage
operation.  The profile supplies the persistence seam consumed by the shared
146-B acquisition kernel; it does not change the deterministic 146-A dataset
contracts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from trading_bot.experiments.desktop_research_dataset import (
    verify_desktop_open_bytes,
    verify_desktop_published_dataset,
)
from trading_bot.experiments.historical_research_acquisition import (
    AcquisitionPersistence,
    PersistenceReceipt,
)
from trading_bot.experiments.historical_research_custody import (
    HistoricalSessionAuthority,
    canonical_json_bytes,
    published_historical_session_authority,
    require_accepted_historical_session_authority,
)
from trading_bot.experiments.historical_research_dataset import (
    HistoricalResearchDatasetError,
    HistoricalResearchDatasetSnapshot,
    HistoricalResearchPartitionManifest,
    HistoricalResearchPartitionMaterial,
    HistoricalResearchPartitionRole,
    parse_historical_research_csv,
    verify_historical_research_policy_binding,
)
from trading_bot.experiments.research_strategy_robustness import (
    ResearchStrategyFinalHoldoutAdmission,
)
from trading_bot.market_data.models import HistoricalDataResult

DESKTOP_RESEARCH_PROFILE = "desktop-v1"
DESKTOP_RESEARCH_ROOT = Path(r"F:\AI\ai-trading-bot\data\research\desktop-v1")
DESKTOP_RESEARCH_EVIDENCE_SCHEMA = "historical-research-desktop-evidence/v1"
DESKTOP_RESEARCH_ACQUISITION_SCHEMA = "historical-research-desktop-acquisition/v1"
_TEST_SEAM = object()


class DesktopResearchError(HistoricalResearchDatasetError):
    """Malformed, incomplete or inconsistent desktop research material."""


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DesktopResearchError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise DesktopResearchError("nonfinite JSON constant")


def _json_object(body: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, TypeError, ValueError, RecursionError):
        raise DesktopResearchError("invalid desktop JSON") from None
    if type(value) is not dict:
        raise DesktopResearchError("desktop JSON object required")
    return value


def _digest(value: object) -> None:
    if type(value) is not str or len(value) != 64:
        raise DesktopResearchError("desktop SHA256 required")
    try:
        int(value, 16)
    except ValueError:
        raise DesktopResearchError("desktop SHA256 required") from None


def _git(value: object) -> None:
    if type(value) is not str or len(value) != 40:
        raise DesktopResearchError("desktop Git identity required")
    try:
        int(value, 16)
    except ValueError:
        raise DesktopResearchError("desktop Git identity required") from None


def _uuid(value: object) -> None:
    if type(value) is not str:
        raise DesktopResearchError("desktop UUID required")
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (TypeError, ValueError):
        raise DesktopResearchError("desktop UUID required") from None


def _page_digests(value: object) -> tuple[str, ...]:
    if type(value) is not list or not value:
        raise DesktopResearchError("desktop page digest vector required")
    result = tuple(value)
    for digest in result:
        _digest(digest)
    if len(set(result)) != len(result):
        raise DesktopResearchError("desktop page digest vector must be unique")
    return result


@dataclass(frozen=True, slots=True)
class DesktopResearchInspection:
    """Profile-local inspection with ordinary filesystem invariants only."""

    root: Path
    test_only: bool
    ordinary_filesystem: bool = True

    def verify(self) -> None:
        if (
            not isinstance(self.root, Path)
            or type(self.test_only) is not bool
            or self.test_only is False
            and self.root != DESKTOP_RESEARCH_ROOT
            or self.test_only is True
            and (not self.root.is_absolute() or self.root == DESKTOP_RESEARCH_ROOT)
            or self.ordinary_filesystem is not True
        ):
            raise DesktopResearchError("desktop storage profile rejected")


@dataclass(frozen=True, slots=True)
class HistoricalResearchDesktopAcquisitionEvidence:
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
    profile: str = DESKTOP_RESEARCH_PROFILE
    schema: str = DESKTOP_RESEARCH_EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        _git(self.source_head)
        _git(self.source_tree)
        _uuid(self.attempt_id)
        _digest(self.calendar_sha256)
        if type(self.calendar_identity) is not str or not self.calendar_identity:
            raise DesktopResearchError("desktop calendar identity required")
        if self.profile != DESKTOP_RESEARCH_PROFILE:
            raise DesktopResearchError("desktop profile is fixed")
        if self.schema != DESKTOP_RESEARCH_EVIDENCE_SCHEMA:
            raise DesktopResearchError("desktop evidence schema is fixed")
        for pages in (self.bars_page_sha256, self.corporate_page_sha256):
            _page_digests(list(pages))
        if (
            type(self.snapshot) is not HistoricalResearchDatasetSnapshot
            or type(self.open_manifest) is not HistoricalResearchPartitionManifest
            or type(self.holdout_manifest) is not HistoricalResearchPartitionManifest
            or self.open_manifest.role is not HistoricalResearchPartitionRole.OPEN
            or self.holdout_manifest.role
            is not HistoricalResearchPartitionRole.FINAL_HOLDOUT
            or (
                self.snapshot.open_manifest_id,
                self.snapshot.holdout_manifest_id,
            )
            != (self.open_manifest.manifest_id, self.holdout_manifest.manifest_id)
            or self.open_manifest.raw_vendor_page_sha256 != self.bars_page_sha256
            or self.holdout_manifest.raw_vendor_page_sha256 != self.bars_page_sha256
            or self.open_manifest.corporate_action_sha256
            != self.holdout_manifest.corporate_action_sha256
        ):
            raise DesktopResearchError("desktop evidence membership mismatch")

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(
            {
                "schema": self.schema,
                "profile": self.profile,
                "source_head": self.source_head,
                "source_tree": self.source_tree,
                "attempt_id": self.attempt_id,
                "calendar_identity": self.calendar_identity,
                "calendar_sha256": self.calendar_sha256,
                "bars_page_sha256": self.bars_page_sha256,
                "corporate_page_sha256": self.corporate_page_sha256,
                "snapshot": json.loads(self.snapshot.to_json()),
                "open_manifest": json.loads(self.open_manifest.to_json()),
                "holdout_manifest": json.loads(self.holdout_manifest.to_json()),
            }
        )


class DesktopResearchStorage(AcquisitionPersistence):
    """Create-only ordinary storage for the current desktop research profile."""

    def __init__(self, root: Path, *, _seam: object | None = None) -> None:
        if not isinstance(root, Path):
            raise TypeError("desktop storage root must be a Path")
        if root != DESKTOP_RESEARCH_ROOT and _seam is not _TEST_SEAM:
            raise DesktopResearchError(
                "arbitrary production roots require the explicit test seam"
            )
        if _seam is _TEST_SEAM and (
            not root.is_absolute() or root == DESKTOP_RESEARCH_ROOT
        ):
            raise DesktopResearchError("test storage root must be a nonproduction path")
        self._root = root
        self._test_only = _seam is _TEST_SEAM
        self._used = False

    @classmethod
    def production(cls) -> DesktopResearchStorage:
        return cls(DESKTOP_RESEARCH_ROOT)

    @classmethod
    def for_test(cls, root: Path) -> DesktopResearchStorage:
        return cls(root, _seam=_TEST_SEAM)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def test_only(self) -> bool:
        return self._test_only

    def inspect(self) -> DesktopResearchInspection:
        return DesktopResearchInspection(self._root, self._test_only)

    def prepare(self) -> None:
        self.inspect().verify()
        if self._root.exists() and self._root.is_symlink():
            raise DesktopResearchError("desktop root must not be a link")
        for relative in (
            "raw/bars",
            "raw/corporate-actions",
            "normalized/open",
            "normalized/holdout",
            "corporate-actions",
            "manifests",
        ):
            path = self._root.joinpath(*relative.split("/"))
            if path.exists() and path.is_symlink():
                raise DesktopResearchError("desktop path must not be a link")
            path.mkdir(parents=True, exist_ok=True)

    def claim_attempt(self, attempt_id: str) -> bool:
        if self._used or type(attempt_id) is not str:
            return False
        try:
            if str(UUID(attempt_id)) != attempt_id:
                return False
        except ValueError:
            return False
        if self._root.exists():
            if self._root.is_symlink():
                return False
            if any(
                path.is_file() or path.is_symlink() for path in self._root.rglob("*")
            ):
                return False
        self._used = True
        return True

    @staticmethod
    def _relative(relative: str) -> tuple[str, ...]:
        if (
            type(relative) is not str
            or not relative
            or relative.startswith(("/", "\\"))
            or ":" in relative
        ):
            raise DesktopResearchError("relative desktop path required")
        parts = tuple(relative.split("/"))
        if any(not part or part in {".", ".."} or "\\" in part for part in parts):
            raise DesktopResearchError("unsafe desktop relative path")
        return parts

    def _path(self, relative: str) -> Path:
        parts = self._relative(relative)
        path = self._root.joinpath(*parts)
        current = self._root
        for part in parts[:-1]:
            current = current / part
            if current.exists() and current.is_symlink():
                raise DesktopResearchError("desktop path must not be a link")
        return path

    def _create(self, relative: str, body: bytes) -> PersistenceReceipt:
        if type(body) is not bytes or not body:
            raise DesktopResearchError("nonempty desktop bytes required")
        path = self._path(relative)
        if path.exists() or path.is_symlink():
            raise DesktopResearchError("desktop dataset file already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise DesktopResearchError("desktop file persistence failed") from error
        try:
            readback = path.read_bytes()
        except OSError as error:
            raise DesktopResearchError("desktop readback failed") from error
        if readback != body:
            raise DesktopResearchError("desktop readback mismatch")
        return PersistenceReceipt(relative, sha256(body).hexdigest(), len(body), True)

    def read(self, relative: str) -> bytes:
        path = self._path(relative)
        if not path.is_file() or path.is_symlink():
            raise DesktopResearchError("required desktop dataset file is missing")
        try:
            body = path.read_bytes()
        except OSError as error:
            raise DesktopResearchError("desktop file read failed") from error
        if not body:
            raise DesktopResearchError("desktop dataset file is empty")
        return body

    def persist_raw(self, relative_path: str, body: bytes) -> PersistenceReceipt:
        if not relative_path.startswith("vendor-raw/"):
            raise DesktopResearchError("acquisition raw path is not recognized")
        relative = "raw/" + relative_path.removeprefix("vendor-raw/")
        receipt = self._create(relative, body)
        return PersistenceReceipt(
            relative_path,
            receipt.digest,
            receipt.byte_size,
            receipt.durable_readback_verified,
        )

    def persist_private(self, relative_path: str, body: bytes) -> PersistenceReceipt:
        return self._create(relative_path, body)

    def build_evidence(
        self,
        *,
        source_head: str,
        source_tree: str,
        attempt_id: str,
        session_authority: HistoricalSessionAuthority,
        bars_pages: tuple[bytes, ...],
        corporate_action_pages: tuple[bytes, ...],
        snapshot: HistoricalResearchDatasetSnapshot,
        open_manifest: HistoricalResearchPartitionManifest,
        holdout_manifest: HistoricalResearchPartitionManifest,
    ) -> bytes:
        return HistoricalResearchDesktopAcquisitionEvidence(
            source_head,
            source_tree,
            attempt_id,
            session_authority.identity,
            session_authority.digest,
            tuple(sha256(page).hexdigest() for page in bars_pages),
            tuple(sha256(page).hexdigest() for page in corporate_action_pages),
            snapshot,
            open_manifest,
            holdout_manifest,
        ).to_bytes()

    def verify_dataset(
        self,
        snapshot: HistoricalResearchDatasetSnapshot,
        open_material: HistoricalResearchPartitionMaterial,
        holdout_material: HistoricalResearchPartitionMaterial,
        session_authority: HistoricalSessionAuthority,
    ) -> None:
        require_accepted_historical_session_authority(session_authority)
        verify_desktop_published_dataset(
            snapshot, open_material, holdout_material, session_authority
        )

    @staticmethod
    def open_files(
        opened: HistoricalResearchPartitionMaterial,
        holdout: HistoricalResearchPartitionMaterial,
        snapshot: HistoricalResearchDatasetSnapshot,
        evidence_bytes: bytes,
    ) -> tuple[tuple[str, bytes], ...]:
        del holdout, snapshot, evidence_bytes
        return (("normalized/open/SPY.csv", opened.normalized_bytes),)

    def materialize_open(
        self, files: tuple[tuple[str, bytes], ...]
    ) -> tuple[PersistenceReceipt, ...]:
        if tuple(path for path, _ in files) != ("normalized/open/SPY.csv",):
            raise DesktopResearchError("desktop OPEN materialization shape mismatch")
        return tuple(self._create(path, body) for path, body in files)

    def record_terminal(self, state: str, stage: str) -> None:
        if type(state) is not str or type(stage) is not str or not state or not stage:
            raise DesktopResearchError("desktop terminal state required")
        terminal = (
            "COMPLETE"
            if state == "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION"
            else "STOPPED"
        )
        self._create(
            "acquisition.json",
            canonical_json_bytes(
                {
                    "schema": DESKTOP_RESEARCH_ACQUISITION_SCHEMA,
                    "profile": DESKTOP_RESEARCH_PROFILE,
                    "state": terminal,
                    "stage": stage,
                }
            ),
        )


def _complete_record(storage: DesktopResearchStorage) -> None:
    raw = _json_object(storage.read("acquisition.json"))
    if (
        raw
        != {
            "schema": DESKTOP_RESEARCH_ACQUISITION_SCHEMA,
            "profile": DESKTOP_RESEARCH_PROFILE,
            "state": "COMPLETE",
            "stage": raw.get("stage"),
        }
        or type(raw["stage"]) is not str
        or not raw["stage"]
    ):
        raise DesktopResearchError("desktop acquisition is incomplete")


def _bundle(
    storage: DesktopResearchStorage,
) -> tuple[
    HistoricalResearchDatasetSnapshot,
    HistoricalResearchPartitionManifest,
    HistoricalResearchPartitionManifest,
]:
    snapshot = HistoricalResearchDatasetSnapshot.from_json(
        storage.read("manifests/snapshot.json").decode("utf-8")
    )
    opened = HistoricalResearchPartitionManifest.from_json(
        storage.read("manifests/open.json").decode("utf-8")
    )
    holdout = HistoricalResearchPartitionManifest.from_json(
        storage.read("manifests/holdout.json").decode("utf-8")
    )
    return snapshot, opened, holdout


def _sidecar(storage: DesktopResearchStorage, *manifests) -> bytes:
    body = storage.read("corporate-actions/sidecar.json")
    digest = sha256(body).hexdigest()
    if any(manifest.corporate_action_sha256 != digest for manifest in manifests):
        raise DesktopResearchError("desktop corporate-action digest mismatch")
    return body


def load_desktop_open_research(
    storage: DesktopResearchStorage,
) -> HistoricalDataResult:
    """Load only the ordinary OPEN research projection."""
    if type(storage) is not DesktopResearchStorage:
        raise DesktopResearchError("exact desktop storage required")
    _complete_record(storage)
    snapshot, opened, holdout = _bundle(storage)
    _sidecar(storage, opened, holdout)
    authority = published_historical_session_authority()
    require_accepted_historical_session_authority(authority)
    data = verify_desktop_open_bytes(
        storage.read("normalized/open/SPY.csv"),
        snapshot,
        opened,
        holdout,
    )
    authority.verify(data)
    return data


def _raw_pages(storage: DesktopResearchStorage, manifest) -> tuple[bytes, ...]:
    return tuple(
        storage.read(f"raw/bars/{index:04d}.json")
        for index in range(len(manifest.raw_vendor_page_sha256))
    )


def load_desktop_final_holdout(
    storage: DesktopResearchStorage,
    admission: ResearchStrategyFinalHoldoutAdmission,
) -> HistoricalDataResult:
    """Load FINAL_HOLDOUT only through the existing Architecture-145 admission."""
    if type(storage) is not DesktopResearchStorage:
        raise DesktopResearchError("exact desktop storage required")
    if type(admission) is not ResearchStrategyFinalHoldoutAdmission:
        raise DesktopResearchError("exact Architecture-145 admission required")
    _complete_record(storage)
    snapshot, opened, holdout = _bundle(storage)
    sidecar = _sidecar(storage, opened, holdout)
    bars_pages = _raw_pages(storage, opened)
    open_material = HistoricalResearchPartitionMaterial(
        opened,
        storage.read("normalized/open/SPY.csv"),
        bars_pages,
        sidecar,
    )
    holdout_material = HistoricalResearchPartitionMaterial(
        holdout,
        storage.read("normalized/holdout/SPY.csv"),
        bars_pages,
        sidecar,
    )
    authority = published_historical_session_authority()
    require_accepted_historical_session_authority(authority)
    verification = verify_desktop_published_dataset(
        snapshot, open_material, holdout_material, authority
    )
    verify_historical_research_policy_binding(admission.policy, verification)
    return parse_historical_research_csv(
        holdout_material.normalized_bytes,
        HistoricalResearchPartitionRole.FINAL_HOLDOUT,
    )


def desktop_research_readiness() -> str:
    """Pure current readiness label; never creates a root or grants effects."""
    return "READY_FOR_DESKTOP_RESEARCH_ACQUISITION_REVIEW"


__all__ = [
    "DESKTOP_RESEARCH_ACQUISITION_SCHEMA",
    "DESKTOP_RESEARCH_EVIDENCE_SCHEMA",
    "DESKTOP_RESEARCH_PROFILE",
    "DESKTOP_RESEARCH_ROOT",
    "DesktopResearchError",
    "DesktopResearchInspection",
    "DesktopResearchStorage",
    "HistoricalResearchDesktopAcquisitionEvidence",
    "desktop_research_readiness",
    "load_desktop_final_holdout",
    "load_desktop_open_research",
]
