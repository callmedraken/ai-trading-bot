"""GUI-A18 lifecycle boundary-map presentation and authority closure."""

import ast
import builtins
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTextEdit,
)

from scripts import checkpoint_runner, run_test_certification
from trading_bot.gui import research_candidate_lifecycle_audit as audit
from trading_bot.gui import research_candidate_lifecycle_boundary_map as boundary_map
from trading_bot.gui.research_candidate_lifecycle_models import (
    LifecycleObservationView,
    LifecycleQualificationStatus,
    LifecycleQualificationView,
    LifecycleSourceView,
    LifecycleZeroEffectsView,
    ResearchCandidateLifecycleDiagnostic,
    ResearchCandidateLifecyclePageState,
    ResearchCandidateLifecyclePageStatus,
    ResearchCandidateLifecycleView,
)
from trading_bot.gui.research_candidate_lifecycle_page import (
    ResearchCandidateLifecyclePage,
)

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = (
    "CREDENTIAL_READS",
    "PROVIDER_CALLS",
    "ROBINHOOD_READS",
    "BROKER_CALLS",
    "PAPER_MUTATIONS",
    "SCHEDULER_CALLS",
    "ACL_MUTATIONS",
    "PRODUCTION_SQLITE_READS",
    "PRODUCTION_SQLITE_WRITES",
)
A16_DIGEST = "887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f"
A17_DIGEST = "dc11d4c1e6099c1eec3346cafb85220e42f495e472d220cf81ac741ccff524c3"
A18_DIGEST = "a82247963625dea0f6842d4dc59a851c6986d9f3d8d0c0f40d452aaea2a35af5"
EXPECTED_ROWS = (
    (
        "Local canonical artifacts",
        "VERIFIED_LOCAL",
        "A16 retained local artifact identities; this is not source acceptance.",
    ),
    (
        "Local SHADOW successor linkage",
        "VERIFIED_LOCAL",
        "The retained immutable linkage is local evidence; no new "
        "lifecycle state is created.",
    ),
    (
        "Retained source provenance",
        "RECORDED",
        "Retained HEAD/TREE values are provenance only; they do not "
        "establish remote acceptance.",
    ),
    (
        "Qualification coverage",
        "RECORDED_SATISFIED",
        "A17 retained B2 coverage facts meeting their minima; coverage is "
        "descriptive only and does not establish profitability, quality, or "
        "readiness.",
    ),
    (
        "Observation effects",
        "RECORDED_ZERO",
        "A17 retained nine zero counters as presentation facts; they grant no "
        "operational authority or observation-origin claim.",
    ),
    (
        "Full historical/external chain",
        "NOT_REVERIFIED",
        "Complete historical and external qualification was not re-run by this GUI.",
    ),
    (
        "Real observation acquisition",
        "NOT_CONNECTED",
        "No real observation or provider acquisition boundary is connected.",
    ),
    (
        "Production compatibility",
        "NOT_ESTABLISHED",
        "Production compatibility and strategy selection are not established.",
    ),
    (
        "PAPER_CANDIDATE",
        "NOT_MATERIALIZED",
        "No later research lifecycle stage is materialized by this page.",
    ),
    (
        "AWAITING_HUMAN_PROMOTION",
        "NOT_MATERIALIZED",
        "No later research lifecycle stage is materialized by this page.",
    ),
    (
        "Automatic promotion",
        "DISABLED",
        "No automatic stage advancement or promotion control exists.",
    ),
    (
        "Promotion authority",
        "NOT_CONNECTED",
        "No promotion authority boundary is connected.",
    ),
    (
        "Trading authority",
        "NONE",
        "No paper, broker, or live trading authority is connected.",
    ),
)


@pytest.fixture
def retained_state():
    instant = datetime(2026, 1, 2, 15, 0, 0, 123456, tzinfo=UTC)
    evidence = ResearchCandidateLifecycleView(
        *(UUID(int=index) for index in range(1, 11)),
        1,
        "Synthetic <read-only> variant",
        2,
        *(
            LifecycleSourceView(head * 40, tree * 40)
            for head, tree in (
                ("a", "b"),
                ("c", "d"),
                ("e", "f"),
                ("1", "2"),
                ("3", "4"),
            )
        ),
        LifecycleObservationView(
            9,
            3,
            date(2026, 1, 2),
            date(2026, 1, 2),
            instant,
            instant,
            LifecycleZeroEffectsView(*(0 for _ in EFFECTS)),
        ),
        LifecycleQualificationView(
            2, 4, 2, 9, 3, 3, LifecycleQualificationStatus.PASSED, ()
        ),
    )
    return ResearchCandidateLifecyclePageState(
        ResearchCandidateLifecyclePageStatus.AVAILABLE,
        ResearchCandidateLifecycleDiagnostic.LOCAL_LINKAGE,
        evidence,
    )


@pytest.fixture
def application():
    app = QApplication.instance() or QApplication([])
    if not QFontDatabase.families():
        assert QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf") >= 0
    original_font = app.font()
    app.setFont(QFont(QFontDatabase.families()[0], 9))
    try:
        yield app
    finally:
        app.setFont(original_font)


def test_exact_immutable_boundary_rows_for_a17_presentation(retained_state):
    presentation = audit.compose_lifecycle_audit(retained_state)
    result = boundary_map.compose_lifecycle_boundary_map(presentation)
    assert [
        (row.boundary, row.recorded_status, row.authority_meaning)
        for row in result.rows
    ] == list(EXPECTED_ROWS)
    assert result == boundary_map.compose_lifecycle_boundary_map(presentation)
    for value in (result, *result.rows):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)
    with pytest.raises(TypeError):
        boundary_map.LifecycleBoundaryRow("x", "y", 1)
    with pytest.raises(TypeError):
        boundary_map.LifecycleBoundaryMapPresentation(list(result.rows))


def test_boundary_composer_has_no_file_service_or_acquisition_access(
    retained_state, monkeypatch
):
    presentation = audit.compose_lifecycle_audit(retained_state)

    def forbidden(*args, **kwargs):
        raise AssertionError("A18 boundary composition attempted an effect")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(audit, "compose_lifecycle_audit", forbidden)
    result = boundary_map.compose_lifecycle_boundary_map(presentation)
    assert len(result.rows) == len(EXPECTED_ROWS)


def test_boundary_module_has_no_parser_or_verifier_dependency():
    path = ROOT / "src/trading_bot/gui/research_candidate_lifecycle_boundary_map.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {}
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.Import, ast.AsyncFunctionDef, ast.Global))
        if isinstance(node, ast.ImportFrom):
            imports[node.module] = {alias.name for alias in node.names}
    assert imports == {
        "dataclasses": {"dataclass"},
        "trading_bot.gui.research_candidate_lifecycle_audit": {
            "LifecycleAuditPresentation"
        },
    }
    assert "from_json" not in source
    assert "verify_" not in source
    assert "ResearchCandidateLifecycleInspectionService" not in source
    allowed_calls = {
        "dataclass",
        "any",
        "type",
        "str",
        "TypeError",
        "LifecycleBoundaryRow",
        "LifecycleBoundaryMapPresentation",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            assert name in allowed_calls


def test_coverage_and_zero_effects_remain_presentation_only(retained_state):
    presentation = audit.compose_lifecycle_audit(retained_state)
    changed = replace(
        presentation,
        coverage=tuple(
            replace(row, recorded=row.recorded + 100) for row in presentation.coverage
        ),
        effects=tuple(replace(row, value="999") for row in presentation.effects),
    )
    assert boundary_map.compose_lifecycle_boundary_map(changed) == (
        boundary_map.compose_lifecycle_boundary_map(presentation)
    )


def test_boundary_statuses_never_infer_profitability_quality_or_readiness(
    retained_state,
):
    result = boundary_map.compose_lifecycle_boundary_map(
        audit.compose_lifecycle_audit(retained_state)
    )
    assert [row.recorded_status for row in result.rows] == [
        row[1] for row in EXPECTED_ROWS
    ]
    assert (
        "does not establish profitability, quality, or readiness"
        in result.rows[3].authority_meaning
    )
    assert not any(
        status in {"PROFITABLE", "ALPHA", "QUALITY_CONFIRMED", "READY", "ELIGIBLE"}
        for status in (row.recorded_status for row in result.rows)
    )


@pytest.mark.parametrize(
    "state",
    [
        ResearchCandidateLifecyclePageState(
            ResearchCandidateLifecyclePageStatus.UNAVAILABLE,
            ResearchCandidateLifecycleDiagnostic.NOT_CONFIGURED,
        ),
        ResearchCandidateLifecyclePageState(
            ResearchCandidateLifecyclePageStatus.ATTENTION,
            ResearchCandidateLifecycleDiagnostic.INVALID,
        ),
    ],
)
def test_unavailable_attention_do_not_fabricate_boundary_rows(state, application):
    result = boundary_map.compose_lifecycle_boundary_map(
        audit.LifecycleAuditPresentation()
    )
    assert result == boundary_map.LifecycleBoundaryMapPresentation()
    page = ResearchCandidateLifecyclePage(state)
    text = "\n".join(label.text() for label in page.findChildren(QLabel))
    assert "Lifecycle boundary map" not in text
    page.close()


@pytest.mark.parametrize("size", [(920, 620), (1180, 760)])
def test_exact_qt_boundary_grid_is_selectable_scrollable_and_read_only(
    retained_state, size, application
):
    page = ResearchCandidateLifecyclePage(retained_state)
    page.resize(size[0] - 210, size[1])
    page.show()
    application.processEvents()
    labels = page.findChildren(QLabel)
    text = "\n".join(label.text() for label in labels)
    assert "Lifecycle boundary map" in text
    assert len(page.findChildren(QLabel, "researchLifecycleBoundaryHeading")) == 3
    assert len(page.findChildren(QLabel, "researchLifecycleBoundaryValue")) == 39
    for boundary, status, meaning in EXPECTED_ROWS:
        assert boundary in text and status in text and meaning in text
    assert not page.findChildren(QAbstractButton)
    assert not page.findChildren(QLineEdit)
    assert not page.findChildren(QTextEdit)
    for label in labels:
        assert label.textFormat() == Qt.TextFormat.PlainText
        assert (
            label.textInteractionFlags() == Qt.TextInteractionFlag.TextSelectableByMouse
        )
        assert label.heightForWidth(label.width()) <= label.height(), label.text()
    scroll = page.findChild(QScrollArea, "researchLifecycleScroll")
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().maximum() > 0
    page.close()


def test_repeated_boundary_composition_and_rendering_are_pure(
    retained_state, application, monkeypatch
):
    presentation = audit.compose_lifecycle_audit(retained_state)

    def forbidden(*args, **kwargs):
        raise AssertionError("A18 repeated rendering attempted acquisition")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    for _ in range(3):
        assert boundary_map.compose_lifecycle_boundary_map(presentation).rows
        page = ResearchCandidateLifecyclePage(retained_state)
        page.show()
        application.processEvents()
        page.close()


def test_a16_a17_frozen_digests_and_source_blobs_remain_exact():
    assert (
        sha256(
            json.dumps(
                checkpoint_runner.ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        == A16_DIGEST
    )
    assert (
        sha256(
            json.dumps(
                checkpoint_runner.ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        == A17_DIGEST
    )
    assert (
        sha256(
            json.dumps(
                checkpoint_runner.ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        == A18_DIGEST
    )
    frozen = {
        "src/trading_bot/gui/research_candidate_lifecycle_models.py": (
            "19ca4f9e4e75b4a061e0d8ec8d6515cf35a53352"
        ),
        "src/trading_bot/gui/research_candidate_lifecycle_service.py": (
            "62da586b13a399b5c806cf159b33e47b21ffc56b"
        ),
        "src/trading_bot/gui/research_candidate_lifecycle_audit.py": (
            "7ce5a7fcedfa77145b3e68c525dbda0331c61887"
        ),
        ".github/workflows/gui-source-gates.yml": (
            "ff019356795e508b3b2e7a065871edd2d6bad5bd"
        ),
        ".github/workflows/checkpoint-source-gates.yml": (
            "fe6aceac62721338eba4fcb40e2e7fde0d976e18"
        ),
    }
    for path, pin in frozen.items():
        assert checkpoint_runner._git_blob_sha1(ROOT / path) == pin


def test_a18_overlay_rejects_a17_predecessor_drift(monkeypatch):
    pins = dict(checkpoint_runner.ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    pins["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    with pytest.raises(ValueError, match="140-A18 frozen A17 predecessor drift"):
        checkpoint_runner._arch140a18_current_inventory_test_pin(
            "tests/scripts/certification_runner/test_profiles.py",
            checkpoint_runner.ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[
                "tests/scripts/certification_runner/test_profiles.py"
            ],
        )


@pytest.mark.parametrize("mutation", ["missing", "extra", "wrong"])
def test_a18_inventory_overlay_fails_closed_on_drift(monkeypatch, mutation):
    pins = dict(checkpoint_runner.ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    if mutation == "missing":
        pins.clear()
    elif mutation == "extra":
        pins["tests/gui/test_main_window.py"] = "a" * 40
    else:
        pins["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    result = checkpoint_runner._arch134_d1r5_authority_check(ROOT)
    assert result


def test_a18_inventory_counts_and_legacy_ownership_are_exact():
    inventory = run_test_certification.discover_inventory(ROOT)
    assert {
        name: len(run_test_certification.select_inventory(inventory, name))
        for name in ("full", "robinhood", "legacy", "exhaustive")
    } == {"full": 185, "robinhood": 101, "legacy": 222, "exhaustive": 407}
    assert len(checkpoint_runner.ACTIVE_CI_CHECKPOINTS) == 67
    gui_paths = [path for path in inventory if path.startswith("tests/gui/")]
    assert len(gui_paths) == 51
    relative = Path(__file__).relative_to(ROOT).as_posix()
    assert relative in run_test_certification.select_inventory(inventory, "legacy")
    assert relative not in run_test_certification.select_inventory(inventory, "full")
    profile_path = "tests/scripts/certification_runner/test_profiles.py"
    expected = checkpoint_runner._arch134_d1r7_test_pin(
        profile_path,
        checkpoint_runner._canonical_current_inventory_test_pin(
            profile_path,
            checkpoint_runner.ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[
                profile_path
            ],
        ),
    )
    expected = checkpoint_runner._arch142_current_inventory_test_pin(
        profile_path, expected
    )
    expected = checkpoint_runner._arch142b_current_inventory_test_pin(
        profile_path, expected
    )
    assert checkpoint_runner._git_blob_sha1(ROOT / profile_path) == expected
