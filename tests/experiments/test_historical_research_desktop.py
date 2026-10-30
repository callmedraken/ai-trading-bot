"""Current Architecture 147 desktop research profile coverage."""

import ast
import json
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import pytest

import trading_bot.experiments.historical_research_acquisition as acquisition
import trading_bot.experiments.historical_research_custody as custody
import trading_bot.experiments.historical_research_dataset as dataset
import trading_bot.experiments.historical_research_desktop as desktop
from trading_bot.domain import Symbol
from trading_bot.experiments.research_strategy_robustness import (
    ResearchExecutionStressKind,
    ResearchExecutionStressScenario,
    ResearchRobustnessPartitionRole,
    ResearchStrategyRobustnessPartition,
    ResearchStrategyRobustnessQualificationPolicy,
    admit_research_strategy_final_holdout,
)
from trading_bot.strategies import MovingAverageCrossoverConfig

NY = ZoneInfo("America/New_York")
HEAD = "a" * 40
TREE = "b" * 40
ATTEMPT = "930cba37-a96e-4d59-b722-116e232e17cc"


def _wire(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


@pytest.fixture(scope="module")
def vendor():
    authority = custody.ACCEPTED_HISTORICAL_SESSION_AUTHORITIES[0]
    rows = []
    for item in authority.sessions:
        stamp = datetime.combine(item, time.min, NY).astimezone(UTC)
        price = (
            9876.54321 if stamp >= dataset.HISTORICAL_RESEARCH_HOLDOUT_START else 100.25
        )
        rows.append(
            {
                "t": stamp.isoformat().replace("+00:00", "Z"),
                "o": price,
                "h": price + 1,
                "l": price - 1,
                "c": price,
                "v": 42,
            }
        )
    split = len(rows) - 100
    bars = (
        _wire({"symbol": "SPY", "bars": rows[:split], "next_page_token": "second"}),
        _wire({"symbol": "SPY", "bars": rows[split:], "next_page_token": None}),
    )
    actions = (
        _wire(
            {
                "corporate_actions": {
                    "cash_dividends": [
                        {
                            "id": "synthetic-dividend",
                            "symbol": "SPY",
                            "process_date": "2025-01-02",
                            "rate": 1.5,
                        }
                    ]
                },
                "next_page_token": None,
            }
        ),
    )
    return bars, actions, authority


class FakeCredentials:
    def __init__(self) -> None:
        self.reads = 0

    def read(self) -> acquisition.AcquisitionCredentials:
        self.reads += 1
        return acquisition.AcquisitionCredentials("SYNTHETIC_KEY", "SYNTHETIC_SECRET")


class FakeTransport:
    def __init__(self, vendor) -> None:
        self.bars, self.actions = vendor[:2]
        self.calls = []

    def get(self, request, credentials):
        del credentials
        self.calls.append(request)
        pages = (
            self.bars
            if request.stream is acquisition.AcquisitionStream.BARS
            else self.actions
        )
        index = sum(item.stream is request.stream for item in self.calls) - 1
        return acquisition.HistoricalResearchResponse(request, 200, pages[index])


def _acquire(root: Path, vendor):
    storage = desktop.DesktopResearchStorage.for_test(root)
    transport = FakeTransport(vendor)
    credentials = FakeCredentials()
    result = acquisition.HistoricalResearchAcquisitionOperator(
        transport, credentials, storage
    ).run(
        source_head=HEAD,
        source_tree=TREE,
        attempt_id=ATTEMPT,
        session_authority=vendor[2],
    )
    assert result.state == "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION", result.stage
    assert result.evidence_bytes is not None
    return storage, result, transport, credentials


@pytest.fixture
def completed(tmp_path, vendor):
    return _acquire(tmp_path / "desktop-v1", vendor)


def test_fixed_root_and_explicit_test_seam(tmp_path):
    production = desktop.DesktopResearchStorage.production()
    assert production.root == desktop.DESKTOP_RESEARCH_ROOT
    assert production.test_only is False
    assert not production.root.exists()
    with pytest.raises(desktop.DesktopResearchError, match="explicit test seam"):
        desktop.DesktopResearchStorage(tmp_path / "arbitrary")
    with pytest.raises(desktop.DesktopResearchError, match="nonproduction"):
        desktop.DesktopResearchStorage.for_test(desktop.DESKTOP_RESEARCH_ROOT)


def test_ordinary_filesystem_has_no_security_or_provenance_dependency():
    tree = ast.parse(Path(desktop.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any(
        name.startswith(("ctypes", "win32", "winreg", "subprocess", "socket"))
        for name in imported
    )
    source = Path(desktop.__file__).read_text(encoding="utf-8").lower()
    assert "accepted_custody_admissions" not in source
    assert "rename" not in source
    assert "set-acl" not in source


def test_storage_is_create_only_readback_verified_and_does_not_clean(tmp_path):
    storage = desktop.DesktopResearchStorage.for_test(tmp_path / "desktop-v1")
    storage.prepare()
    receipt = storage.persist_private("manifests/example.json", b"{}")
    assert receipt.durable_readback_verified is True
    receipt.verify("manifests/example.json", b"{}")
    with pytest.raises(desktop.DesktopResearchError, match="already exists"):
        storage.persist_private("manifests/example.json", b"changed")
    assert storage.read("manifests/example.json") == b"{}"
    assert (storage.root / "manifests/example.json").exists()


def test_incomplete_dataset_blocks(completed):
    storage, _, _, _ = completed
    (storage.root / "acquisition.json").unlink()
    with pytest.raises(desktop.DesktopResearchError):
        desktop.load_desktop_open_research(storage)


def test_open_loader_reads_open_and_nonprice_metadata_only(completed, monkeypatch):
    storage, _, _, _ = completed
    original = storage.read
    reads = []

    def read(relative):
        reads.append(relative)
        return original(relative)

    monkeypatch.setattr(storage, "read", read)
    result = desktop.load_desktop_open_research(storage)
    assert result.request.symbol == Symbol("SPY")
    assert result.bars[-1].timestamp < dataset.HISTORICAL_RESEARCH_HOLDOUT_START
    assert "normalized/holdout/SPY.csv" not in reads
    assert not any(path.startswith("raw/") for path in reads)
    assert "ACCEPTED_CUSTODY_ADMISSIONS" not in Path(desktop.__file__).read_text()


@pytest.mark.parametrize("relative", ["normalized/open/SPY.csv", "manifests/open.json"])
def test_open_integrity_and_manifest_mismatch_block(completed, relative):
    storage, _, _, _ = completed
    path = storage.root / relative
    original = path.read_bytes()
    path.write_bytes(original + b"\n")
    with pytest.raises(
        (desktop.DesktopResearchError, dataset.HistoricalResearchDatasetError)
    ):
        desktop.load_desktop_open_research(storage)


def test_desktop_acquisition_preserves_full_partition_lineage(completed):
    storage, outcome, transport, credentials = completed
    assert transport.calls and credentials.reads == 1
    assert (storage.root / "raw/bars/0000.json").is_file()
    open_manifest = dataset.HistoricalResearchPartitionManifest.from_json(
        (storage.root / "manifests/open.json").read_text()
    )
    holdout_manifest = dataset.HistoricalResearchPartitionManifest.from_json(
        (storage.root / "manifests/holdout.json").read_text()
    )
    snapshot = dataset.HistoricalResearchDatasetSnapshot.from_json(
        (storage.root / "manifests/snapshot.json").read_text()
    )
    assert (
        open_manifest.raw_vendor_page_sha256 == holdout_manifest.raw_vendor_page_sha256
    )
    assert (
        open_manifest.corporate_action_sha256
        == holdout_manifest.corporate_action_sha256
    )
    assert snapshot.open_manifest_id == open_manifest.manifest_id
    assert snapshot.holdout_manifest_id == holdout_manifest.manifest_id
    assert outcome.evidence_bytes is not None


def _admission(snapshot):
    full = snapshot.full_historical_data_fingerprint
    namespace = UUID("3f8d2d2d-8d6a-5a10-bc23-9c3de5a59f8a")
    partitions = (
        ResearchStrategyRobustnessPartition(
            ResearchRobustnessPartitionRole.DEVELOPMENT,
            snapshot.development_start,
            snapshot.development_end,
            full,
            uuid5(namespace, "development"),
        ),
        ResearchStrategyRobustnessPartition(
            ResearchRobustnessPartitionRole.WALK_FORWARD,
            snapshot.walk_forward_start,
            snapshot.walk_forward_end,
            full,
            uuid5(namespace, "walk-forward"),
        ),
        ResearchStrategyRobustnessPartition(
            ResearchRobustnessPartitionRole.FINAL_HOLDOUT,
            snapshot.final_holdout_start,
            snapshot.final_holdout_end,
            full,
            uuid5(namespace, "holdout"),
        ),
    )
    kinds = (
        ResearchExecutionStressKind.HIGHER_COST,
        ResearchExecutionStressKind.DELAYED_FILL,
        ResearchExecutionStressKind.MISSED_FILL,
        ResearchExecutionStressKind.REJECTED_FILL,
        ResearchExecutionStressKind.PARTIAL_FILL,
    )
    scenarios = tuple(
        ResearchExecutionStressScenario(
            kind.value,
            kind,
            (
                Decimal("10")
                if kind is ResearchExecutionStressKind.HIGHER_COST
                else Decimal("0")
            ),
            Decimal("0"),
            1 if kind is ResearchExecutionStressKind.DELAYED_FILL else 0,
            (
                Decimal("0.5")
                if kind is ResearchExecutionStressKind.PARTIAL_FILL
                else None
            ),
        )
        for kind in kinds
    )
    policy = ResearchStrategyRobustnessQualificationPolicy(
        uuid5(namespace, "candidate"),
        uuid5(namespace, "strategy"),
        HEAD,
        TREE,
        "moving_average_crossover",
        "v1",
        Symbol("SPY"),
        MovingAverageCrossoverConfig(3, 5, Decimal("10")),
        full,
        *partitions,
        1,
        Decimal("100"),
        Decimal("-1"),
        1,
        Decimal("0"),
        Decimal("0"),
        Decimal("100"),
        Decimal("100"),
        1,
        0,
        Decimal("100"),
        scenarios,
        None,
        HEAD,
        TREE,
    )
    return admit_research_strategy_final_holdout(
        policy, admission_source_head=HEAD, admission_source_tree=TREE
    )


def test_final_loader_requires_exact_admission_and_validates_holdout(completed):
    storage, _, _, _ = completed
    with pytest.raises(desktop.DesktopResearchError, match="admission"):
        desktop.load_desktop_final_holdout(storage, None)
    snapshot = dataset.HistoricalResearchDatasetSnapshot.from_json(
        (storage.root / "manifests/snapshot.json").read_text()
    )
    result = desktop.load_desktop_final_holdout(storage, _admission(snapshot))
    assert result.request.start == dataset.HISTORICAL_RESEARCH_HOLDOUT_START
    assert result.bars[0].timestamp >= dataset.HISTORICAL_RESEARCH_HOLDOUT_START


def test_optimizer_and_walk_forward_do_not_import_holdout_loader():
    for relative in (
        "src/trading_bot/portfolio/optimizer.py",
        "src/trading_bot/experiments/research_candidate.py",
        "src/trading_bot/experiments/research_candidate_walk_forward.py",
        "src/trading_bot/experiments/research_strategy_walk_forward.py",
    ):
        source = Path(relative).read_text(encoding="utf-8")
        assert "historical_research_desktop" not in source
        assert "load_desktop_final_holdout" not in source


def test_desktop_readiness_is_source_only_and_no_production_root_is_created():
    assert desktop.desktop_research_readiness() == (
        "READY_FOR_DESKTOP_RESEARCH_ACQUISITION_REVIEW"
    )
    assert not desktop.DESKTOP_RESEARCH_ROOT.exists()
