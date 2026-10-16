"""One acquisition, pure reuse, navigation and closed A16 capability boundary."""

import ast
import json
from hashlib import sha256
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton, QScrollArea
from tests.gui.test_gui_a16_research_candidate_lifecycle_models import (
    CONFIG_FIELDS,
    available_state,
    write_artifacts,
)

from scripts import checkpoint_runner
from trading_bot.gui import (
    EvidenceTimelineFilter,
    EvidenceTimelineSource,
    GuiStartupConfiguration,
    ReadOnlyGuiApplicationService,
    SystemComponentStatus,
    SystemHealthStatus,
    build_evidence_navigation_target,
    build_evidence_source_page_target,
    build_evidence_timeline_state,
    build_supervisor_state,
    build_system_health_state,
    filter_evidence_timeline_entries,
)
from trading_bot.gui.main_window import MainWindow
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecycleDiagnostic as Diagnostic,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageState as State,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageStatus as Status,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    unavailable_research_candidate_lifecycle_state,
)
from trading_bot.gui.supervisor_models import (
    SupervisorConsistency,
    SupervisorPageStatus,
)

ROOT = Path(__file__).resolve().parents[2]
ACQUISITIONS = (
    "get_overview",
    "get_research_state",
    "get_paper_state",
    "get_paper_account_state",
    "get_market_data_state",
    "get_operator_observability_state",
    "get_runtime_state",
    "get_production_strategy_state",
    "get_research_candidate_lifecycle_state",
)
PAGE_IDS = (
    "home",
    "research",
    "research-lifecycle",
    "paper",
    "paper-account",
    "market-data",
    "operations",
    "runtime",
    "supervisor",
    "evidence",
    "system",
)


@pytest.mark.parametrize("size", [(1180, 760), (920, 620)])
def test_exact_nine_acquisitions_five_reads_and_zero_navigation_rereads(
    tmp_path, monkeypatch, size
):
    application = QApplication.instance() or QApplication([])
    paths = write_artifacts(tmp_path)
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(**dict(zip(CONFIG_FIELDS, paths, strict=True)))
    )
    calls, opens = [], []
    for name in ACQUISITIONS:
        original = getattr(service, name)

        def acquired(_name=name, _original=original):
            calls.append(_name)
            return _original()

        monkeypatch.setattr(service, name, acquired)
    original_open = Path.open

    def opened(path, *args, **kwargs):
        opens.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    window = MainWindow(service)
    window.resize(*size)
    window.show()
    application.processEvents()
    assert calls == list(ACQUISITIONS) and opens == list(paths)
    assert window.page_ids == PAGE_IDS
    assert window._navigation.item(2).text() == "Research Lifecycle"
    for page_id in PAGE_IDS:
        window.select_page(page_id)
        application.processEvents()
    window.select_page("research-lifecycle")
    application.processEvents()
    scroll = window._research_lifecycle_page.findChild(QScrollArea)
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.widget().width() <= scroll.viewport().width()
    assert scroll.verticalScrollBar().maximum() > 0
    assert not window._research_lifecycle_page.findChildren(QPushButton)
    supervisor = window._supervisor_page._state
    assert supervisor.research_lifecycle is window._research_lifecycle_page._state
    assert supervisor.status is SupervisorPageStatus.AVAILABLE
    assert supervisor.consistency is SupervisorConsistency.NOT_CHECKED
    text = "\n".join(
        label.text() for label in window._supervisor_page.findChildren(QLabel)
    )
    assert "Research candidate stage: SHADOW" in text
    assert "Production replacement: Disabled" in text
    assert "Production compatibility: Not established" in text
    timeline = window._evidence_timeline_page._state
    assert len(timeline.entries) == 5
    assert all(
        entry.source is EvidenceTimelineSource.RESEARCH_LIFECYCLE
        and entry.occurred_at is None
        for entry in timeline.entries
    )
    system = window._system_health_page._state
    audits = system.audit_entries
    assert len(audits) == 5
    assert system.components[-1].key == "research-lifecycle"
    for audit in audits:
        target = build_evidence_navigation_target(audit)
        assert target.source is EvidenceTimelineSource.RESEARCH_LIFECYCLE
        window._show_evidence_navigation_target(target)
        assert window.current_page_id == "evidence"
        page = window._evidence_timeline_page
        assert page.findChild(QComboBox).currentText() == "Research Lifecycle"
        assert page._count.text() == "Showing 1 of 5 entries."
        button = page.findChild(QPushButton, "evidenceTimelineViewSourceButton")
        button.click()
        assert window.current_page_id == "research-lifecycle"
    assert calls == list(ACQUISITIONS) and opens == list(paths)
    window.close()


@pytest.mark.parametrize("status", list(Status))
def test_optional_pure_composition_classifications_audits_and_no_authority(
    tmp_path, monkeypatch, status
):
    lifecycle = {
        Status.UNAVAILABLE: unavailable_research_candidate_lifecycle_state(),
        Status.ATTENTION: State(Status.ATTENTION, Diagnostic.INVALID),
        Status.AVAILABLE: available_state(tmp_path),
    }[status]
    service = ReadOnlyGuiApplicationService(GuiStartupConfiguration())
    overview = service.get_overview()
    research, runtime, strategy = (
        service.get_research_state(),
        service.get_runtime_state(),
        service.get_production_strategy_state(),
    )
    states = (
        research,
        service.get_paper_state(),
        service.get_paper_account_state(),
        service.get_market_data_state(),
        service.get_operator_observability_state(),
        runtime,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Pure composition must never read")

    monkeypatch.setattr(Path, "open", forbidden)
    supervisor = build_supervisor_state(research, runtime, strategy, lifecycle)
    assert supervisor.status.value == status.value
    assert supervisor.automatic_promotion_enabled is False
    assert supervisor.human_promotion_required is True
    assert supervisor.promotion_authority_connected is False
    assert supervisor.can_research_replace_production is False
    system = build_system_health_state(overview, *states, supervisor, lifecycle)
    component = system.components[-1]
    assert (
        component.status
        is {
            Status.UNAVAILABLE: SystemComponentStatus.UNAVAILABLE,
            Status.AVAILABLE: SystemComponentStatus.AVAILABLE,
            Status.ATTENTION: SystemComponentStatus.BLOCKED,
        }[status]
    )
    assert (system.status is SystemHealthStatus.ATTENTION) is (
        status is Status.ATTENTION
    )
    if status is Status.ATTENTION:
        assert (
            "failed canonical parsing or SHADOW successor linkage" in component.detail
        )
        assert "rejected for trading" not in component.detail
    timeline = build_evidence_timeline_state(*states, supervisor, lifecycle)
    if status is Status.AVAILABLE:
        assert len(timeline.entries) == 5
        assert {entry.identifier for entry in timeline.entries} == {
            str(v) for _, v in lifecycle.evidence.artifact_identifiers
        }
        for entry in timeline.entries:
            assert entry.occurred_at is None and entry.sha256 is None
            assert (
                build_evidence_source_page_target(entry).page_id.value
                == "research-lifecycle"
            )
            filtered = filter_evidence_timeline_entries(
                timeline,
                EvidenceTimelineFilter(
                    entry.identifier, EvidenceTimelineSource.RESEARCH_LIFECYCLE
                ),
            )
            assert filtered == (entry,)
        batch = timeline.entries[2]
        assert "5 caller-supplied observations; 2 sessions" in batch.detail
        assert "2026-01-02" in batch.detail and "2026-01-03" in batch.detail
        assert "123456+00:00" in batch.detail
    else:
        assert not timeline.entries and not system.audit_entries
    # Existing callers may omit the optional state entirely.
    assert (
        build_supervisor_state(research, runtime, strategy).research_lifecycle is None
    )
    assert not build_evidence_timeline_state(*states).entries
    assert len(build_system_health_state(overview, *states).components) == 6
    with pytest.raises(TypeError):
        build_supervisor_state(research, runtime, strategy, object())
    with pytest.raises(TypeError):
        build_evidence_timeline_state(*states, research_lifecycle=object())
    with pytest.raises(TypeError):
        build_system_health_state(overview, *states, research_lifecycle=object())


def test_shadow_identity_does_not_change_contract_session_consistency(tmp_path):
    # A16 has no compatibility comparison. Existing exact session comparison is
    # separately covered by A15; absence remains NOT_CHECKED even with SHADOW.
    service = ReadOnlyGuiApplicationService(GuiStartupConfiguration())
    lifecycle = available_state(tmp_path)
    state = build_supervisor_state(
        service.get_research_state(),
        service.get_runtime_state(),
        service.get_production_strategy_state(),
        lifecycle,
    )
    assert state.consistency is SupervisorConsistency.NOT_CHECKED
    assert state.can_research_replace_production is False


def test_a16_static_capability_and_file_io_boundary():
    gui = ROOT / "src/trading_bot/gui"
    new_names = (
        "research_candidate_lifecycle_models.py",
        "research_candidate_lifecycle_service.py",
        "research_candidate_lifecycle_page.py",
    )
    pure_names = (
        "supervisor_models.py",
        "supervisor_adapter.py",
        "supervisor_page.py",
        "system_health_adapter.py",
        "evidence_timeline_adapter.py",
        "evidence_navigation.py",
        "evidence_source_navigation.py",
    )
    forbidden_modules = (
        "requests",
        "httpx",
        "urllib",
        "socket",
        "subprocess",
        "sqlite3",
        "ctypes",
        "win32",
        "keyring",
        "trading_bot.brokers",
        "trading_bot.review_paper",
        "trading_bot.runtime",
        "trading_bot.risk",
        "trading_bot.execution",
        "trading_bot.strategies",
        "trading_bot.simulator",
        "trading_bot.cli",
    )
    forbidden_calls = {
        "__import__",
        "eval",
        "exec",
        "import_module",
        "glob",
        "rglob",
        "walk",
        "iterdir",
        "getenv",
        "listdir",
        "scandir",
        "resolve",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "execute",
        "arm",
        "promote",
        "set_stage",
        "advance",
        "urlopen",
        "connect",
        "submit_order",
        "ProductionStrategyContract",
        "ReviewPaperStore",
        "HistoricalExperimentRunner",
        "HistoricalExperimentWalkForwardRunner",
        "Simulator",
        "qualify_research_candidate_shadow",
        "qualify_research_candidate_walk_forward",
    }
    service_imports = {
        "dataclasses",
        "pathlib",
        "trading_bot.experiments.research_candidate_shadow_binding",
        "trading_bot.experiments.research_candidate_shadow_observation",
        "trading_bot.experiments.research_candidate_shadow_qualification",
        "trading_bot.experiments.research_candidate_walk_forward",
        "trading_bot.gui.research_candidate_lifecycle_models",
    }
    domain_symbols = {
        "ResearchCandidateShadowVariantBinding",
        "ResearchCandidateShadowObservationBatch",
        "ResearchCandidateShadowQualification",
        "ShadowResearchStrategyCandidate",
        "WalkForwardPassedResearchStrategyCandidate",
        "verify_shadow_research_candidate",
    }
    for name in (*new_names, *pure_names):
        tree = ast.parse((gui / name).read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
                assert not (node.module or "").startswith(forbidden_modules)
                if (node.module or "").startswith("trading_bot.experiments"):
                    assert name == "research_candidate_lifecycle_service.py"
                    assert {alias.name for alias in node.names} <= domain_symbols
            elif isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
                assert not any(a.name.startswith(forbidden_modules) for a in node.names)
            elif isinstance(node, ast.Call):
                call = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                assert call not in forbidden_calls
                if name != "research_candidate_lifecycle_service.py":
                    assert call not in {"open", "read", "Path", "from_json"}
                elif call == "open":
                    assert (
                        len(node.args) == 1
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == "rb"
                    )
        if name == "research_candidate_lifecycle_service.py":
            assert imports == service_imports
    # Composition may retain existing unrelated read-only adapters. Freeze the
    # exact added lifecycle service construction/acquisition, with no I/O calls.
    for name in ("startup_composition.py", "main_window.py", "app.py"):
        tree = ast.parse((gui / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(forbidden_modules)
            elif isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(forbidden_modules) for alias in node.names
                )
            elif isinstance(node, ast.Call):
                call = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                if call == "connect":
                    assert name == "main_window.py"
                    assert isinstance(node.func.value, ast.Attribute)
                    assert node.func.value.attr in {
                        "source_navigation_requested",
                        "evidence_navigation_requested",
                        "currentRowChanged",
                    }
                elif call == "exec":
                    assert name == "app.py"
                    assert isinstance(node.func, ast.Attribute)
                    assert isinstance(node.func.value, ast.Name)
                    assert node.func.value.id == "application"
                else:
                    assert call not in forbidden_calls | {"open", "read", "from_json"}
    window = ast.parse((gui / "main_window.py").read_text())
    assert (
        sum(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get_research_candidate_lifecycle_state"
            for n in ast.walk(window)
        )
        == 1
    )


@pytest.mark.parametrize("mutation", ["missing", "extra", "executable", "drift"])
@pytest.mark.parametrize(
    "check",
    [
        checkpoint_runner._arch134_production_paper_runtime_authority_check,
        checkpoint_runner._arch134_authentication_authority_check,
        checkpoint_runner._arch134_d1r5_authority_check,
    ],
)
def test_arch140_successor_override_fails_closed(monkeypatch, mutation, check):
    pins = dict(checkpoint_runner.ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    if mutation == "missing":
        pins.pop("tests/scripts/certification_runner/test_profiles.py")
    elif mutation == "extra":
        pins["tests/gui/test_main_window.py"] = "a" * 40
    elif mutation == "executable":
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    else:
        pins["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    assert check(ROOT)


def test_arch140_exact_seven_successor_blobs():
    predecessor = checkpoint_runner.ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    pins = checkpoint_runner.ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    assert set(predecessor) == set(
        checkpoint_runner.ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    )
    assert set(pins) == set(predecessor)
    for (
        path,
        pin,
    ) in checkpoint_runner.ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.items():
        assert checkpoint_runner._git_blob_sha1(ROOT / path) == (
            checkpoint_runner._arch140a18_current_inventory_test_pin(path, pin)
        )


def test_arch140_frozen_139b2_overlay():
    assert (
        sha256(
            json.dumps(
                checkpoint_runner.ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        == "32ef60967164da03e02c8cfe40928b8839f89a2c4bb90074e967bb08213d6458"
    )


FROZEN_PREDECESSOR_DICTIONARIES = (
    (
        "ARCH134_CURRENT_DECISION_SOURCE_PINS",
        "432cd2b8efeb65f651d332acd499c2efeebe5180e16bb5aa224c19d64152bb12",
    ),
    (
        "ARCH134_MARKET_HISTORY_SOURCE_PINS",
        "e12072bc7da6398eed4c81274b38bffa89a280b7ff9bd4b919a5a5c6e904c9db",
    ),
    (
        "ARCH134_HISTORY_QUALIFICATION_SOURCE_PINS",
        "52b622392c5b32c4c13425aa0a39fca46bae89a915af66edfe6551376ba8d3fa",
    ),
    (
        "ARCH134_ARMED_PAPER_SOURCE_PINS",
        "10188ed4933e8874c145c07bfc7fb47c5ccc78cb74fb4d0ddc671f21c4cd3828",
    ),
    (
        "ARCH134_ARMED_PAPER_IMPORTS",
        "56ec5eb2ae4d0d457e44bfebbe43f23ad609839f90b0695e73d760d8b831ecbf",
    ),
    (
        "ARCH134_ARMED_PAPER_SUCCESSOR_PIN_OVERRIDES",
        "3976d983a2019193eddae89c89ce1fff87cc563e27327e176b67efbadbd9cb3d",
    ),
    (
        "ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES",
        "b397d74fba50bfc157b6a7e6c8fd55c1d713fd0b0fa212dd7cdcc5e607fa59ad",
    ),
    (
        "ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES",
        "0d4fe9f3a0e1ce1af7a01116c26cc8ef64bb9272630f165dcbb5c6863b0ec21b",
    ),
    (
        "ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES",
        "d020b022b3bf3950173b11d5067fee3ad3e04178017ee4e39bf64f5d404980b3",
    ),
    (
        "ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS",
        "8c957aa3d3b5707d644b2d086db08023a01ed35cd3ab3218bb27c19424f03235",
    ),
    (
        "ARCH134_PRODUCTION_PAPER_RUNTIME_IMPORTS",
        "d784128948fb9cc31c6f9794e8347b449e0116d2efd1583ec617c88fa0cc536a",
    ),
    (
        "ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_SOURCE_PINS",
        "403181d4169a5a6537716bd12c1400884fcb959a93867544358ed70889d19de8",
    ),
    (
        "ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_IMPORTS",
        "5a07daffa9aad877de8607b4b147c4dd9c2662eaade00bc3d25cb990e641a42d",
    ),
    (
        "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS",
        "dca04885add2cc74ea2b21383dca60f0c6636fd7d1e12cfc6d8100f8a813d390",
    ),
    (
        "ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS",
        "e6e3a127f70224e978504d57c280de796d3a93c4274c8ff7e62ab0ad3d37f1ba",
    ),
    (
        "ARCH134_AUTH_SOURCE_PINS",
        "92799d3ff0a74258bc12540d55303b509fcae90c6fbed6e18c4cda1e0bfe7903",
    ),
    (
        "ARCH134_AUTH_TEST_PIN_OVERRIDES",
        "a240ad6e800ff29a6720ef416f30f99243f486eeb1b1a7e1f41b097cdd6ce6a6",
    ),
    (
        "ARCH134_AUTH_CORRECTION_TEST_PINS",
        "cc25401816f1fcb59c7ee7bdccd26d390089a19744508cbda64c74ebcdb1dd90",
    ),
    (
        "ARCH134_AUTH_IMPORTS",
        "f4303daae96be4c0d1d62f79e03ee35e3f6b3605e1553550ef8a305a743738eb",
    ),
    (
        "ARCH134_D1R4_SOURCE_PINS",
        "9ed4ef533f4602b76382ce6e6841e790c1304de751684cd9a81cfb41a8f50ab2",
    ),
    (
        "ARCH134_D1R4_IMPORTS",
        "1d88dac76eecb29dbaedd2cc4e117242be1bd1a027824e27a8c122b02de82ec4",
    ),
    (
        "ARCH134_D1R4R_SOURCE_PINS",
        "a6c6af6e231ea41074d2dd8b9fe26e36f9c8e70ef8d764626a22efd7217778c2",
    ),
    (
        "ARCH134_D1R4R_IMPORTS",
        "2fb70bdf88ca899d1ffe27a61a5fe51707b16779161d35bfd11ae3f6f3305456",
    ),
    (
        "ARCH134_HIST2_TEST_PIN_OVERRIDES",
        "1d005a7fa62d7172d58be3a9b61443e548f0c62c92ad8652bc883b8df302d950",
    ),
    (
        "ARCH134_D1R5_TEST_PIN_OVERRIDES",
        "bcdb35cb77572df147ea12a9db54d22da2cbe8933140a6c1a7b448dba8be287b",
    ),
    (
        "ARCH134_D1R5_SOURCE_PINS",
        "3412b689a3c5b5d6ef4495fb62ce3611869e6e512d1055387b50276d188cd230",
    ),
    (
        "ARCH134_D1R5_IMPORTS",
        "7402233d1d0d9ec921399a57cc8d3a3dda4ee82497d7ac608a4b8d88b2c9b38f",
    ),
    (
        "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "8a4021b92a5354cfbdb5394692eb50c14f6a13982b9a50aeb7d259553c7e5988",
    ),
    (
        "ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "9ec72c131a25b962a7d3e49124f99aa712dc2a8e0182d297f4a78507b6e0fb69",
    ),
    (
        "ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "d66e134a5491e1e2966728e27558f05c51946c5e89930707e1471f339324634c",
    ),
    (
        "ARCH134_RUNTIME_ACL_SOURCE_PINS",
        "93760d287a535297a29f1e4acb53c98450613ae6196df064f8697906bfcd00ad",
    ),
    (
        "ARCH134_RUNTIME_ACL_IMPORTS",
        "cf5604482cf46f2e7c0823585526f140e9c2b13f415f726861e735c0f2cda14d",
    ),
    (
        "ARCH134_RUNTIME_ACL_AST_PINS",
        "a8f319cc3f413eacca83e5effab7521394cc3190eafe403e95fb2dd33b7e0acc",
    ),
    (
        "ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "32ef60967164da03e02c8cfe40928b8839f89a2c4bb90074e967bb08213d6458",
    ),
)


@pytest.mark.parametrize("name,digest", FROZEN_PREDECESSOR_DICTIONARIES)
def test_arch140_every_predecessor_dictionary_is_frozen(name, digest):
    assert (
        sha256(
            json.dumps(getattr(checkpoint_runner, name), sort_keys=True).encode()
        ).hexdigest()
        == digest
    )


@pytest.mark.parametrize(
    "name",
    [
        "ARCH134_HIST2_TEST_PIN_OVERRIDES",
        "ARCH134_D1R5_TEST_PIN_OVERRIDES",
        "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
        "ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
    ],
)
def test_arch140_predecessor_drift_cannot_be_masked(monkeypatch, name):
    pins = dict(getattr(checkpoint_runner, name))
    pins[next(iter(pins))] = "0" * 40
    monkeypatch.setattr(checkpoint_runner, name, pins)
    assert checkpoint_runner._arch134_d1r5_authority_check(ROOT)


FROZEN_SOURCE_BLOBS = {
    ".github/workflows/gui-source-gates.yml": (
        "ff019356795e508b3b2e7a065871edd2d6bad5bd"
    ),
    ".github/workflows/checkpoint-source-gates.yml": (
        "fe6aceac62721338eba4fcb40e2e7fde0d976e18"
    ),
    "src/trading_bot/experiments/__init__.py": (
        "a7d3104adb5b1f00448c1559c6efe55ad3a3256c"
    ),
    "src/trading_bot/experiments/research_candidate.py": (
        "5e617d976278a9a97b990284dfd17fd2abc87f18"
    ),
    "src/trading_bot/experiments/research_candidate_walk_forward.py": (
        "b068100e27c290769dc3d8dd4b475edef3d9cfe8"
    ),
    "src/trading_bot/experiments/research_candidate_shadow_binding.py": (
        "ff1f76c5309ab8ed2e2e48d487365600633b1c0d"
    ),
    "src/trading_bot/experiments/research_candidate_shadow_observation.py": (
        "61a4f9bc67ad0c05f961a523c231e64e6fb55732"
    ),
    "src/trading_bot/experiments/research_candidate_shadow_qualification.py": (
        "75cc22d16d65f51ce75921ab66c6dcabfbfa119b"
    ),
}


@pytest.mark.parametrize("path,pin", FROZEN_SOURCE_BLOBS.items())
def test_arch140_preserves_domain_and_workflow_bytes(path, pin):
    assert checkpoint_runner._git_blob_sha1(ROOT / path) == pin
