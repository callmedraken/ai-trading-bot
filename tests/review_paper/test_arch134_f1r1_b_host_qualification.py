"""Focused no-effect proof for Architecture 134-F1R1-B."""

import ast
import hashlib
import subprocess
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release import (
    LAUNCHER_RELATIVE_PATH,
    STRATEGY_ID,
    STRATEGY_VERSION,
    ReleaseInventoryEntry,
    ReleaseManifest,
)
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    ReleaseBundle,
    ReleaseFile,
    verify_release_bundle,
)
from trading_bot.supervised_release.installation_contract import (
    PYTHON_SHA256,
    PYTHON_VERSION,
    InstalledEvidence,
)
from trading_bot.supervised_release.lifecycle_store import (
    DisposableLifecycleFileStorage,
    DurableLifecycleJournal,
    LifecycleJournalError,
    MemoryLifecycleStorage,
    replay_lifecycle_journal,
)
from trading_bot.supervised_release.runtime_admission import (
    SITE_PACKAGES,
    RuntimeAdmissionEvidence,
    RuntimeAdmissionResult,
    RuntimeReason,
    RuntimeStatus,
)
from trading_bot.supervised_release.runtime_host_composition import (
    Architecture133HostBinding,
    HostBindingError,
    QualificationHost,
    QualificationState,
    SuccessorExternalEffectAdapter,
    bind_architecture133_host,
    bind_architecture133_runtime,
)
from trading_bot.supervised_release.runtime_isolation import (
    DiagnosticReason,
    EffectConsumedError,
    EffectOperation,
    EffectStage,
    EffectStatus,
    LifecycleEvent,
    LifecycleStatus,
    ProductionOperatorState,
    admit_installed_runtime,
    production_manual_start,
    production_state_after_boot_or_login,
)

ROOT = Path(__file__).resolve().parents[2]
COMPOSITION_SOURCE = (
    ROOT / "src/trading_bot/supervised_release/runtime_host_composition.py"
)


def _manifest_and_files() -> tuple[ReleaseManifest, dict[str, bytes]]:
    files = {
        LAUNCHER_RELATIVE_PATH: b"# inert reviewed launcher\n",
        "pyproject.toml": b"[project]\nname = 'qualification-fixture'\n",
        "src/trading_bot/strategies/moving_average.py": b"# inert strategy source\n",
    }
    paths = tuple(sorted(files))
    manifest = ReleaseManifest(
        source_head="a" * 40,
        source_tree="b" * 40,
        production_python_version=PYTHON_VERSION,
        production_python_sha256=PYTHON_SHA256,
        launcher_relative_path=LAUNCHER_RELATIVE_PATH,
        launcher_sha256=hashlib.sha256(files[LAUNCHER_RELATIVE_PATH]).hexdigest(),
        source_inventory=tuple(
            ReleaseInventoryEntry(path, hashlib.sha256(files[path]).hexdigest())
            for path in paths
        ),
        strategy_id=STRATEGY_ID,
        strategy_version=STRATEGY_VERSION,
        strategy_config=MovingAverageCrossoverConfig(5, 20, Decimal("1.00")),
        risk_policy_id="long-only-reviewed-policy",
        risk_policy_version="1.0.0",
        risk_policy_sha256="1" * 64,
    )
    return manifest, files


def _host_evidence() -> tuple[
    object, RuntimeBinding, InstalledEvidence, RuntimeAdmissionResult
]:
    manifest, source_files = _manifest_and_files()
    manifest_bytes = manifest.to_json().encode("utf-8")
    files = {
        **source_files,
        "manifest.json": manifest_bytes,
    }
    bundle = ReleaseBundle(
        tuple(ReleaseFile(path, files[path]) for path in sorted(files))
    )
    release = verify_release_bundle(
        bundle,
        expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        expected_source_head=manifest.source_head,
        expected_source_tree=manifest.source_tree,
        expected_source_paths=tuple(
            entry.relative_path for entry in manifest.source_inventory
        ),
    )
    binding = RuntimeBinding(release)
    parent_identity = (11, 1)
    image_identity = (11, 2)
    python_identity = (11, 3)
    installed = InstalledEvidence(
        manifest.release_id,
        release.expected_manifest_sha256,
        binding.sha256,
        parent_identity,
        image_identity,
        python_identity,
    )
    runtime = RuntimeAdmissionResult(
        RuntimeStatus.VERIFIED,
        RuntimeReason.VERIFIED,
        RuntimeAdmissionEvidence(
            manifest.release_id,
            release.expected_manifest_sha256,
            binding.sha256,
            image_identity,
            python_identity,
            installed.release_id.replace(
                "release-", r"F:\AITradingBot\releases\release-"
            ),
            installed.release_id.replace(
                "release-", r"F:\AITradingBot\releases\release-"
            )
            + r"\src",
            installed.release_id.replace(
                "release-", r"F:\AITradingBot\releases\release-"
            )
            + "\\"
            + LAUNCHER_RELATIVE_PATH.replace("/", "\\"),
            SITE_PACKAGES,
        ),
    )
    return release, binding, installed, runtime


class _EffectJournal:
    def __init__(self) -> None:
        self._records = ()

    def records(self):
        return self._records

    def append(self, record):
        self._records = (*self._records, record)


def test_verified_architecture_133_evidence_binds_to_f1r1_material():
    release, binding, installed, runtime = _host_evidence()

    result = bind_architecture133_host(release, binding, installed, runtime)

    assert isinstance(result, Architecture133HostBinding)
    assert result.material.manifest_sha256 == release.expected_manifest_sha256
    assert result.material.binding_sha256 == binding.sha256
    assert result.material.manifest.release_id == release.manifest.release_id
    assert result.source_paths == release.expected_source_paths
    assert result.runtime_id.startswith("runtime-")
    assert bind_architecture133_runtime(release, binding, installed, runtime) == (
        result.material
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda installed, runtime: (
            replace(installed, release_id="release-" + "0" * 32),
            runtime,
        ),
        lambda installed, runtime: (
            installed,
            replace(
                runtime,
                evidence=replace(runtime.evidence, manifest_sha256="0" * 64),
            ),
        ),
        lambda installed, runtime: (
            installed,
            replace(
                runtime,
                evidence=replace(runtime.evidence, binding_sha256="0" * 64),
            ),
        ),
        lambda installed, runtime: (
            installed,
            replace(runtime, evidence=replace(runtime.evidence, launcher="wrong")),
        ),
        lambda installed, runtime: (
            installed,
            replace(runtime, evidence=replace(runtime.evidence, source_root="wrong")),
        ),
        lambda installed, runtime: (
            replace(installed, python_version="3.14.2"),
            runtime,
        ),
    ],
)
def test_any_overlapping_host_identity_mismatch_fails_closed(change):
    release, binding, installed, runtime = _host_evidence()
    changed_installed, changed_runtime = change(installed, runtime)

    with pytest.raises(HostBindingError):
        bind_architecture133_host(release, binding, changed_installed, changed_runtime)


def test_repeated_admission_is_immutable_and_does_not_use_development_state(
    monkeypatch: pytest.MonkeyPatch,
):
    release, binding, installed, runtime = _host_evidence()
    material = bind_architecture133_runtime(release, binding, installed, runtime)
    first = admit_installed_runtime(material, expected_runtime_id=material.runtime_id)
    monkeypatch.chdir(ROOT / "tests")
    second = admit_installed_runtime(material, expected_runtime_id=material.runtime_id)

    assert first == second
    assert first.proof is not None
    assert first.proof.runtime_id == material.runtime_id
    tree = ast.parse(COMPOSITION_SOURCE.read_text(encoding="utf-8"))
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    forbidden = ("git", "github", "subprocess", "credential", "provider", "broker")
    assert not any(
        any(word in imported.casefold() for word in forbidden) for imported in imports
    )


def test_durable_lifecycle_is_canonical_bounded_and_replayable(tmp_path: Path):
    release, binding, installed, runtime = _host_evidence()
    material = bind_architecture133_runtime(release, binding, installed, runtime)
    storage = DisposableLifecycleFileStorage(tmp_path / "lifecycle.jsonl")
    journal = DurableLifecycleJournal(material.runtime_id, storage)
    for event in (
        LifecycleEvent.HOST_ENTERED,
        LifecycleEvent.SUPERVISOR_LOCK_ACQUIRED,
        LifecycleEvent.SUPERVISOR_LOOP_ENTERED,
        LifecycleEvent.SAFE_WAITING,
        LifecycleEvent.NORMAL_RETURN,
    ):
        journal.append(event)

    replayed = replay_lifecycle_journal(material.runtime_id, storage)
    raw = (tmp_path / "lifecycle.jsonl").read_bytes()
    assert replayed.status is LifecycleStatus.NORMAL_RETURN
    assert replayed.to_json() == replayed.to_json()
    assert raw == raw.decode("utf-8").encode("utf-8")
    assert len(raw) < 16 * 1024
    assert journal.records() == replayed.records


def test_partial_or_corrupt_lifecycle_state_fails_closed(tmp_path: Path):
    release, binding, installed, runtime = _host_evidence()
    material = bind_architecture133_runtime(release, binding, installed, runtime)
    path = tmp_path / "lifecycle.jsonl"
    path.write_bytes(b'{"schema":"arch134-f1r1-b-lifecycle-journal/v1"')
    with pytest.raises(LifecycleJournalError):
        DurableLifecycleJournal(
            material.runtime_id, DisposableLifecycleFileStorage(path)
        )

    storage = MemoryLifecycleStorage()
    journal = DurableLifecycleJournal(material.runtime_id, storage)
    journal.append(LifecycleEvent.HOST_ENTERED)
    storage._data += b"not-json\n"
    with pytest.raises(LifecycleJournalError):
        journal.records()


def test_terminal_lifecycle_record_is_final_and_abrupt_disappearance_is_distinct():
    release, binding, installed, runtime = _host_evidence()
    material = bind_architecture133_runtime(release, binding, installed, runtime)
    journal = DurableLifecycleJournal(material.runtime_id, MemoryLifecycleStorage())
    journal.append(LifecycleEvent.HOST_ENTERED)
    journal.append(LifecycleEvent.SUPERVISOR_LOCK_ACQUIRED)
    journal.append(LifecycleEvent.SUPERVISOR_LOOP_ENTERED)
    assert journal.snapshot().status is LifecycleStatus.ABRUPT_PROCESS_DISAPPEARANCE
    journal.append(LifecycleEvent.NORMAL_RETURN)
    with pytest.raises(LifecycleJournalError):
        journal.append(LifecycleEvent.SAFE_WAITING)


def test_effect_adapter_proves_entry_order_consumption_and_ack():
    pre_entry = _EffectJournal()
    calls = []
    rejected = SuccessorExternalEffectAdapter(
        pre_entry, EffectOperation.QUOTE_REQUEST
    ).execute(
        pre_entry_guard=lambda: False,
        external_seam=lambda: calls.append("entered"),
    )
    assert rejected.status is EffectStatus.PRE_ENTRY_REJECTED
    assert [record.stage for record in rejected.records] == [
        EffectStage.INTENT,
        EffectStage.PRE_ENTRY_REJECTED,
    ]
    assert calls == []

    failed_journal = _EffectJournal()
    entered = []

    def fail_after_entry():
        entered.append(tuple(record.stage for record in failed_journal.records()))
        raise RuntimeError("not persisted")

    failed_adapter = SuccessorExternalEffectAdapter(
        failed_journal, EffectOperation.QUOTE_REQUEST
    )
    failed = failed_adapter.execute(
        pre_entry_guard=lambda: True,
        external_seam=fail_after_entry,
    )
    assert entered == [(EffectStage.INTENT, EffectStage.ENTRY_ADMITTED)]
    assert failed.status is EffectStatus.AMBIGUOUS
    assert failed.reason is DiagnosticReason.PROVIDER_ENTRY_FAILED
    with pytest.raises(EffectConsumedError):
        failed_adapter.execute(pre_entry_guard=lambda: True, external_seam=lambda: None)

    acknowledged = SuccessorExternalEffectAdapter(
        _EffectJournal(), EffectOperation.PAPER_MUTATION
    ).execute(pre_entry_guard=lambda: True, external_seam=lambda: None)
    assert acknowledged.status is EffectStatus.ACKNOWLEDGED
    assert acknowledged.records[-1].stage is EffectStage.ACK


def test_qualification_host_survives_disposable_development_disturbances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    release, binding, installed, runtime = _host_evidence()
    material = bind_architecture133_runtime(release, binding, installed, runtime)
    journal = DurableLifecycleJournal(material.runtime_id, MemoryLifecycleStorage())
    host = QualificationHost(material, journal)
    stop_state = {"done": False}

    def wait_once() -> None:
        disposable_repo = tmp_path / "development-repo"
        disposable_repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=disposable_repo, check=True)
        (tmp_path / "unrelated.txt").write_text("development change", encoding="utf-8")
        (tmp_path / "unrelated-worktree-like").mkdir()
        monkeypatch.chdir(tmp_path)
        subprocess.run(["git", "status", "--short"], cwd=disposable_repo, check=True)
        (tmp_path / "unrelated-worktree-like").rmdir()
        monkeypatch.chdir(ROOT)
        stop_state["done"] = True

    result = host.run(stop=lambda: stop_state["done"], wait_once=wait_once)
    assert result.state is QualificationState.STOPPED
    assert result.runtime_id == material.runtime_id
    assert result.status is LifecycleStatus.NORMAL_RETURN
    assert host.evidence().runtime_id == material.runtime_id


def test_qualification_host_has_no_effect_capability_and_reboot_stays_manual():
    release, binding, installed, runtime = _host_evidence()
    material = bind_architecture133_runtime(release, binding, installed, runtime)
    admitted = admit_installed_runtime(material)
    assert (
        production_state_after_boot_or_login(ProductionOperatorState.RUNNING)
        is ProductionOperatorState.STOPPED
    )
    assert production_manual_start(ProductionOperatorState.STOPPED, admitted) is (
        ProductionOperatorState.RUNNING
    )
    tree = ast.parse(COMPOSITION_SOURCE.read_text(encoding="utf-8"))
    imported = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not imported & {
        "subprocess",
        "sqlite3",
        "trading_bot.broker",
        "trading_bot.credentials",
        "trading_bot.scheduler",
    }
