"""Pure retained-state audit, real Qt layout, and closed successor authority."""

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
from tests.gui.test_gui_a16_research_candidate_lifecycle_composition import (
    FROZEN_PREDECESSOR_DICTIONARIES,
)

from scripts import checkpoint_runner, run_test_certification
from trading_bot.gui import research_candidate_lifecycle_audit as audit
from trading_bot.gui.research_candidate_lifecycle_models import (
    LOCAL_VERIFICATION_SCOPE,
    RANK_NOTICE,
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
GUI = ROOT / "src/trading_bot/gui"
A16_DIGEST = "887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f"
A17_DIGEST = "dc11d4c1e6099c1eec3346cafb85220e42f495e472d220cf81ac741ccff524c3"
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
GOVERNANCE = (
    ("Stage", "SHADOW"),
    ("Local canonical artifacts", "Verified"),
    ("Local SHADOW linkage", "Verified"),
    ("Full historical chain", "Not re-run by this GUI"),
    ("Real observation acquisition", "Not connected"),
    ("Automatic promotion", "Disabled"),
    ("Promotion authority", "Not connected"),
    ("Production compatibility", "Not established"),
    ("PAPER_CANDIDATE", "Not materialized"),
    ("AWAITING_HUMAN_PROMOTION", "Not materialized"),
    ("Trading authority", "None"),
)


@pytest.fixture
def retained_state():
    """Already acquired A16 facts; no artifacts, parsers, or services."""
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
    # Windows offscreen has no system fonts. Load an explicit test-only font
    # before installing file-read sentinels so geometry uses actual glyphs.
    if not QFontDatabase.families():
        assert QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf") >= 0
    original_font = app.font()
    app.setFont(QFont(QFontDatabase.families()[0], 9))
    try:
        yield app
    finally:
        app.setFont(original_font)


def test_exact_deterministic_retained_artifacts_sources_coverage_and_effects(
    retained_state,
):
    view = audit.compose_lifecycle_audit(retained_state)
    assert view == audit.compose_lifecycle_audit(retained_state)
    e = retained_state.evidence
    assert [(r.label, r.value) for r in view.artifacts] == [
        ("WALK_FORWARD_PASSED candidate", str(e.walk_forward_passed_candidate_id)),
        ("139-A binding", str(e.binding_id)),
        ("B1 observation batch", str(e.observation_batch_id)),
        ("B2 qualification", str(e.qualification_id)),
        ("SHADOW candidate", str(e.shadow_candidate_id)),
    ]
    assert [(r.label, r.head, r.tree) for r in view.provenance] == [
        (label, head * 40, tree * 40)
        for label, head, tree in (
            ("Candidate", "a", "b"),
            ("Walk-forward qualification", "c", "d"),
            ("139-A binding", "e", "f"),
            ("B1 observation", "1", "2"),
            ("B2 qualification", "3", "4"),
        )
    ]
    assert [(r.metric, r.required, r.recorded, r.margin) for r in view.coverage] == [
        ("Sessions", 2, 3, 1),
        ("Total observations", 4, 9, 5),
        ("Minimum per session", 2, 3, 1),
    ]
    assert [(r.label, r.value) for r in view.effects] == [
        (name, "0") for name in EFFECTS
    ]
    assert [(r.label, r.value) for r in view.governance] == list(GOVERNANCE)
    assert view.supporting[-1] == audit.LifecycleAuditRow("Original rank", "2")
    assert audit.COVERAGE_NOTICE == (
        "Margins are coverage headroom only; they do not represent profitability, "
        "alpha, strategy quality, trading quality, confidence, or production readiness."
    )
    assert "external observation-origin claim" in audit.ZERO_EFFECT_NOTICE


def test_frozen_slotted_exact_audit_objects(retained_state):
    view = audit.compose_lifecycle_audit(retained_state)
    for value in (
        view,
        *view.artifacts,
        *view.supporting,
        *view.provenance,
        *view.coverage,
        *view.effects,
        *view.governance,
    ):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)
    with pytest.raises(TypeError):
        replace(view, artifacts=list(view.artifacts))
    with pytest.raises(TypeError):
        replace(view, provenance=view.artifacts)

    class RowSubclass(audit.LifecycleAuditRow):
        pass

    with pytest.raises(TypeError):
        replace(view, artifacts=(RowSubclass("x", "y"),))
    with pytest.raises(TypeError):
        audit.LifecycleAuditRow("x", 1)
    with pytest.raises(TypeError):
        audit.LifecycleProvenanceRow("x", True, "b" * 40)


@pytest.mark.parametrize("field", ["required", "recorded"])
@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, "1", None])
def test_coverage_exact_integer_excluding_bool(field, value):
    with pytest.raises(ValueError):
        replace(audit.LifecycleCoverageRow("Sessions", 1, 2), **{field: value})


def test_margin_zero_negative_and_extreme_exact_integer():
    assert audit.LifecycleCoverageRow("Sessions", 2, 2).margin == 0
    assert audit.LifecycleCoverageRow("Sessions", 1, 100_000).margin == 99_999
    with pytest.raises(ValueError):
        audit.LifecycleCoverageRow("Sessions", 3, 2)
    with pytest.raises(TypeError):
        audit.LifecycleCoverageRow(True, 1, 2)


@pytest.mark.parametrize("value", [None, object(), {}, "AVAILABLE"])
def test_composer_requires_exact_state(value):
    with pytest.raises(TypeError):
        audit.compose_lifecycle_audit(value)


def test_subclass_state_rejected(retained_state):
    class StateSubclass(ResearchCandidateLifecyclePageState):
        pass

    with pytest.raises(TypeError):
        audit.compose_lifecycle_audit(
            StateSubclass(
                retained_state.status,
                retained_state.diagnostic,
                retained_state.evidence,
            )
        )


@pytest.mark.parametrize(
    "status,diagnostic",
    [
        (
            ResearchCandidateLifecyclePageStatus.UNAVAILABLE,
            ResearchCandidateLifecycleDiagnostic.NOT_CONFIGURED,
        ),
        (
            ResearchCandidateLifecyclePageStatus.ATTENTION,
            ResearchCandidateLifecycleDiagnostic.INVALID,
        ),
    ],
)
def test_unavailable_attention_have_no_fabricated_audit(status, diagnostic):
    state = ResearchCandidateLifecyclePageState(status, diagnostic)
    view = audit.compose_lifecycle_audit(state)
    assert view == audit.LifecycleAuditPresentation()
    application = QApplication.instance() or QApplication([])
    page = ResearchCandidateLifecyclePage(state)
    text = "\n".join(label.text() for label in page.findChildren(QLabel))
    assert state.message in text and state.status.value in text
    for absent in (
        "Verified",
        "coverage headroom",
        "all nine counters",
        "HEAD:",
        "TREE:",
        "Stage: SHADOW",
        "Coverage comparison",
    ):
        assert absent not in text
    page.close()
    application.processEvents()


@pytest.mark.parametrize("rank", [None, 1, 1_000_000])
def test_rank_evidence_only(retained_state, rank):
    state = replace(
        retained_state, evidence=replace(retained_state.evidence, rank=rank)
    )
    result = audit.compose_lifecycle_audit(state)
    assert result.supporting[-1].value == ("Unranked" if rank is None else str(rank))
    assert result.governance == audit.compose_lifecycle_audit(retained_state).governance
    assert (
        RANK_NOTICE
        == "Original rank is retained as evidence only; rank grants no authority."
    )


@pytest.mark.parametrize("size", [(920, 620), (1180, 760)])
def test_real_qt_read_only_full_selectable_text_scroll_and_zero_reacquisition(
    retained_state,
    size,
    monkeypatch,
    application,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("A17 attempted acquisition or file I/O")

    from trading_bot.gui.research_candidate_lifecycle_service import (
        ResearchCandidateLifecycleInspectionService,
    )
    from trading_bot.gui.services import GuiApplicationService

    monkeypatch.setattr(builtins, "open", forbidden)
    for name in ("open", "read_text", "read_bytes", "glob", "rglob", "iterdir"):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(
        ResearchCandidateLifecycleInspectionService,
        "get_research_candidate_lifecycle_state",
        forbidden,
    )
    for name in vars(GuiApplicationService):
        if name.startswith("get_"):
            monkeypatch.setattr(GuiApplicationService, name, forbidden)
    for _ in range(3):
        page = ResearchCandidateLifecyclePage(retained_state)
        page.resize(size[0] - 210, size[1])
        page.show()
        application.processEvents()
        labels = page.findChildren(QLabel)
        text = "\n".join(label.text() for label in labels)
        assert LOCAL_VERIFICATION_SCOPE in text and RANK_NOTICE in text
        assert audit.COVERAGE_NOTICE in text and audit.ZERO_EFFECT_NOTICE in text
        assert all(f"{label}: {value}" in text for label, value in GOVERNANCE)
        assert not page.findChildren(QAbstractButton)
        assert not page.findChildren(QLineEdit)
        assert not page.findChildren(QTextEdit)
        for label in labels:
            assert label.textFormat() == Qt.TextFormat.PlainText
            assert (
                label.textInteractionFlags()
                == Qt.TextInteractionFlag.TextSelectableByMouse
            )
            assert not label.openExternalLinks()
            # Check wrapping height and geometry: no clipped UUID/hash suffixes.
            assert label.heightForWidth(label.width()) <= label.height(), label.text()
        for row in audit.compose_lifecycle_audit(retained_state).artifacts:
            assert row.value in text
        for row in audit.compose_lifecycle_audit(retained_state).provenance:
            assert row.head in text and row.tree in text
        # Each unbroken identifier fits within its actual selectable label.
        for label in labels:
            for token in label.text().split():
                if len(token) in (36, 40):
                    assert (
                        label.fontMetrics().horizontalAdvance(token)
                        <= label.contentsRect().width()
                    )
        assert len(page.findChildren(QLabel, "researchLifecycleArtifact")) == 5
        assert len(page.findChildren(QLabel, "researchLifecycleCoverageValue")) == 12
        for label in page.findChildren(
            QLabel, "researchLifecycleCoverageHeading"
        ) + page.findChildren(QLabel, "researchLifecycleCoverageValue"):
            assert label.isVisible()
            assert label.fontMetrics().horizontalAdvance(label.text()) <= label.width()
        scroll = page.findChild(QScrollArea, "researchLifecycleScroll")
        assert scroll.horizontalScrollBar().maximum() == 0
        assert scroll.widget().width() <= scroll.viewport().width()
        assert scroll.verticalScrollBar().maximum() > 0
        for value in (0, scroll.verticalScrollBar().maximum(), 0):
            scroll.verticalScrollBar().setValue(value)
            application.processEvents()
        page.close()


def test_audit_ast_exact_capability_closure():
    tree = ast.parse(
        (GUI / "research_candidate_lifecycle_audit.py").read_text(encoding="utf-8")
    )
    imports = {}
    for node in ast.walk(tree):
        assert not isinstance(
            node, (ast.Import, ast.AsyncFunctionDef, ast.Global, ast.Nonlocal)
        )
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert all(alias.asname is None for alias in node.names)
            imports[node.module] = {alias.name for alias in node.names}
    assert imports == {
        "dataclasses": {"dataclass", "fields"},
        "trading_bot.gui.research_candidate_lifecycle_models": {
            "ResearchCandidateLifecyclePageState"
        },
    }
    allowed_calls = {
        "dataclass",
        "fields",
        "type",
        "str",
        "getattr",
        "any",
        "tuple",
        "TypeError",
        "ValueError",
        "LifecycleAuditRow",
        "LifecycleProvenanceRow",
        "LifecycleCoverageRow",
        "LifecycleAuditPresentation",
        "upper",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert isinstance(node.func, (ast.Name, ast.Attribute))
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            assert name in allowed_calls
        if isinstance(node, ast.Attribute):
            assert not node.attr.startswith("__")
    compose = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "compose_lifecycle_audit"
    )
    assert len(compose.args.args) == 1 and not compose.args.kwonlyargs
    assert compose.args.args[0].annotation.id == "ResearchCandidateLifecyclePageState"


def test_actual_inventory_and_gui_stays_legacy():
    inventory = run_test_certification.discover_inventory(ROOT)
    assert {
        name: len(run_test_certification.select_inventory(inventory, name))
        for name in ("full", "robinhood", "legacy", "exhaustive")
    } == {
        "full": 189,
        "robinhood": 103,
        "legacy": 222,
        "exhaustive": 411,
    }
    assert len(checkpoint_runner.ACTIVE_CI_CHECKPOINTS) == 70
    assert len([path for path in inventory if path.startswith("tests/gui/")]) == 51
    relative = Path(__file__).relative_to(ROOT).as_posix()
    assert relative in run_test_certification.select_inventory(inventory, "legacy")
    assert relative not in run_test_certification.select_inventory(inventory, "full")


def test_exact_successor_pins_and_frozen_a16_digest():
    before = checkpoint_runner.ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    a17 = checkpoint_runner.ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    after = checkpoint_runner.ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    assert sha256(json.dumps(before, sort_keys=True).encode()).hexdigest() == A16_DIGEST
    assert sha256(json.dumps(a17, sort_keys=True).encode()).hexdigest() == A17_DIGEST
    assert set(before) == set(a17) and len(a17) == 7
    assert set(after) == set(a17)
    for path, pin in before.items():
        assert (
            checkpoint_runner._arch140a17_current_inventory_test_pin(path, pin)
            == a17[path]
        )
    for path, pin in before.items():
        assert (
            checkpoint_runner._arch140a18_current_inventory_test_pin(path, pin)
            == after[path]
        )
        expected = checkpoint_runner._arch134_d1r7_test_pin(
            path,
            checkpoint_runner._canonical_current_inventory_test_pin(path, after[path]),
        )
        if path in checkpoint_runner.ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
            expected = checkpoint_runner._arch142_current_inventory_test_pin(
                path, expected
            )
            expected = checkpoint_runner._arch142b_current_inventory_test_pin(
                path, expected
            )
            expected = checkpoint_runner._arch143_current_inventory_test_pin(
                path, expected
            )
            expected = checkpoint_runner._arch132_r3i_current_inventory_test_pin(
                path, expected
            )
            expected = checkpoint_runner._arch144_current_inventory_test_pin(
                path, expected
            )
        assert checkpoint_runner._git_blob_sha1(ROOT / path) == (expected)
    assert (
        checkpoint_runner._arch140a17_current_inventory_test_pin("other", "a" * 40)
        == "a" * 40
    )


@pytest.mark.parametrize("mutation", ["missing", "extra", "product", "after", "before"])
@pytest.mark.parametrize(
    "check",
    [
        checkpoint_runner._arch134_production_paper_runtime_authority_check,
        checkpoint_runner._arch134_authentication_authority_check,
        checkpoint_runner._arch134_d1r5_authority_check,
    ],
)
def test_a17_overlay_rejects_drift(monkeypatch, mutation, check):
    name = "ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES"
    pins = dict(getattr(checkpoint_runner, name))
    path = "tests/scripts/certification_runner/test_profiles.py"
    if mutation == "missing":
        pins.pop(path)
    elif mutation == "extra":
        pins["tests/gui/test_main_window.py"] = "a" * 40
    elif mutation == "product":
        pins["src/trading_bot/review_paper/armed_session.py"] = "a" * 40
    elif mutation == "after":
        pins[path] = "0" * 40
    else:
        name = "ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES"
        pins = dict(getattr(checkpoint_runner, name))
        pins[path] = "0" * 40
    monkeypatch.setattr(checkpoint_runner, name, pins)
    assert check(ROOT)


def test_wrong_before_pin_rejected():
    with pytest.raises(ValueError, match="wrong before pin"):
        checkpoint_runner._arch140a17_current_inventory_test_pin(
            "tests/scripts/certification_runner/test_profiles.py",
            "0" * 40,
        )


def test_a18_overlay_rejects_a17_predecessor_drift(monkeypatch):
    pins = dict(checkpoint_runner.ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
    pins["tests/scripts/certification_runner/test_profiles.py"] = "0" * 40
    monkeypatch.setattr(
        checkpoint_runner, "ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES", pins
    )
    with pytest.raises(ValueError, match="140-A18 frozen A17 predecessor drift"):
        checkpoint_runner._arch140a18_current_inventory_test_pin(
            "tests/scripts/certification_runner/test_profiles.py", "0" * 40
        )


@pytest.mark.parametrize("name,digest", FROZEN_PREDECESSOR_DICTIONARIES)
def test_all_older_authority_dictionaries_frozen(name, digest):
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
def test_older_predecessor_drift_not_masked(monkeypatch, name):
    pins = dict(getattr(checkpoint_runner, name))
    pins[next(iter(pins))] = "0" * 40
    monkeypatch.setattr(checkpoint_runner, name, pins)
    assert checkpoint_runner._arch134_authentication_authority_check(ROOT)
    assert checkpoint_runner._arch134_d1r5_authority_check(ROOT)


@pytest.mark.parametrize(
    "name,pin",
    [
        (
            "research_candidate_lifecycle_models.py",
            "19ca4f9e4e75b4a061e0d8ec8d6515cf35a53352",
        ),
        (
            "research_candidate_lifecycle_service.py",
            "62da586b13a399b5c806cf159b33e47b21ffc56b",
        ),
        ("main_window.py", "11588584e181217996b55c1d36b49fc67f222eb7"),
        ("app.py", "3b19d6bf2be4c0153fa60f33948882510e9f88af"),
        ("startup_composition.py", "d5191aefee2954d0d7aa81c251ca49221e5036c5"),
        ("services.py", "67ed05c453943c02922b7578959123d2624d479f"),
        ("mock_service.py", "405e0787b7538abd6a4e19caa0f9355d059c921f"),
        ("evidence_navigation.py", "72c16b0ab78b973dc28dcb2c512d3303c8132de6"),
        ("evidence_source_navigation.py", "d67b13f4eb336b0710aa0c567eff3424a35c2d84"),
        ("evidence_timeline_adapter.py", "eea97ddfd58e9e6324d96e699aa21376c1190f27"),
        ("evidence_timeline_models.py", "1fa45f24152ecbd92ed79f191c669afb86ab85b7"),
        ("supervisor_adapter.py", "4100459d5f2eb0c9a7bf2fa9693d28fe625aee67"),
        ("supervisor_models.py", "1f01fedf76ac0b91304e6ee3ab0af184c98b60a4"),
        ("supervisor_page.py", "c8376f9c5b0b75b30ec98e6aaf63d8744b96d427"),
        ("system_health_adapter.py", "e49bfc42f83a514e0db48d3c14c2156ff9cbf548"),
    ],
)
def test_a16_frozen_product_blobs(name, pin):
    assert checkpoint_runner._git_blob_sha1(GUI / name) == pin


def test_workflow_bytes_and_five_resolver_sites_unchanged():
    for path, pin in (
        (
            ".github/workflows/gui-source-gates.yml",
            "ff019356795e508b3b2e7a065871edd2d6bad5bd",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "fe6aceac62721338eba4fcb40e2e7fde0d976e18",
        ),
    ):
        assert checkpoint_runner._git_blob_sha1(ROOT / path) == pin
    source = (ROOT / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert (
        sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_arch140a18_current_inventory_test_pin"
            for node in ast.walk(tree)
        )
        == 5
    )
