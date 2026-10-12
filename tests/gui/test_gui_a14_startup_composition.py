"""Normal startup accepts exactly the explicit optional runtime evidence inputs."""

from pathlib import Path

import pytest

from trading_bot.gui import (
    GuiStartupConfiguration,
    PresentationStatus,
    ReadOnlyGuiApplicationService,
    RuntimePageStatus,
    app,
    startup_composition,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/gui/runtime"


def test_default_startup_zero_runtime_io_and_no_inspection_service(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No runtime evidence should be acquired")

    monkeypatch.setattr(
        startup_composition, "ProductionRuntimeEvidenceInspectionService", forbidden
    )
    monkeypatch.setattr(Path, "open", forbidden)
    service = ReadOnlyGuiApplicationService(GuiStartupConfiguration())
    assert service.get_runtime_state().status is RuntimePageStatus.UNAVAILABLE
    runtime = next(c for c in service.get_overview().components if c.key == "runtime")
    assert runtime.status is PresentationStatus.UNAVAILABLE
    assert runtime.detail == "No production-runtime evidence is selected."


@pytest.mark.parametrize(
    "field",
    [
        "runtime_acl_evidence",
        "runtime_qualification_evidence",
        "runtime_session_evidence",
    ],
)
def test_runtime_config_requires_paths(field):
    with pytest.raises(TypeError):
        GuiStartupConfiguration(**{field: "not-a-path"})


def test_parser_consumes_runtime_inputs_and_forwards_only_qt_arguments():
    config, qt = app._parse_startup_arguments(
        [
            "--runtime-acl-evidence",
            "acl.json",
            "--runtime-qualification-evidence",
            "qual.json",
            "--runtime-session-evidence",
            "session.json",
            "-platform",
            "offscreen",
        ]
    )
    assert config.runtime_acl_evidence == Path("acl.json")
    assert config.runtime_qualification_evidence == Path("qual.json")
    assert config.runtime_session_evidence == Path("session.json")
    assert qt == ("-platform", "offscreen")


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("acl-provisioned.json", PresentationStatus.INFO),
        ("acl-blocked.json", PresentationStatus.BLOCKED),
        ("missing.json", PresentationStatus.BLOCKED),
    ],
)
def test_overview_uses_inspected_cached_evidence_and_never_claims_authority(
    monkeypatch, filename, expected
):
    path = FIXTURES / filename
    original = Path.open
    calls = []

    def recording(selected, mode="r", *args, **kwargs):
        assert selected == path and mode == "rb"
        calls.append(selected)
        return original(selected, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", recording)
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(runtime_acl_evidence=path)
    )
    component = next(c for c in service.get_overview().components if c.key == "runtime")
    assert component.status is expected
    assert "production-ready" not in component.detail
    assert service.get_runtime_state() is service.get_runtime_state()
    assert calls == [path]
