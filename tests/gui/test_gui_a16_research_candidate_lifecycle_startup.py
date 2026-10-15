"""All-or-none five-artifact configuration before Qt; no implicit acquisition."""

from itertools import product
from pathlib import Path, PureWindowsPath

import pytest
from tests.gui.test_gui_a16_research_candidate_lifecycle_models import (
    CONFIG_FIELDS,
    write_artifacts,
)

from trading_bot.gui import startup_composition as m
from trading_bot.gui.app import _parse_startup_arguments, run
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageStatus as Status,
)


@pytest.mark.parametrize(
    "selection", [p for p in product((False, True), repeat=5) if any(p) and not all(p)]
)
def test_every_partial_set_rejected_before_gui_construction(selection, monkeypatch):
    kwargs = {
        name: Path(f"{name}.json")
        for name, enabled in zip(CONFIG_FIELDS, selection, strict=True)
        if enabled
    }
    with pytest.raises(ValueError, match="all five"):
        m.GuiStartupConfiguration(**kwargs)
    from trading_bot.gui import app

    def forbidden(*args, **kwargs):
        pytest.fail("Qt must not be constructed for a partial set")

    monkeypatch.setattr(app, "QApplication", forbidden)
    argv = [
        item
        for name in kwargs
        for item in ("--" + name.replace("_", "-"), str(kwargs[name]))
    ]
    with pytest.raises(SystemExit) as error:
        run(argv=argv)
    assert error.value.code == 2


@pytest.mark.parametrize("name", CONFIG_FIELDS)
@pytest.mark.parametrize(
    "value", ["selected.json", PureWindowsPath("selected.json"), 1, True]
)
def test_wrong_path_types_rejected(name, value):
    kwargs = dict.fromkeys(CONFIG_FIELDS, Path("selected.json"))
    kwargs[name] = value
    with pytest.raises(TypeError):
        m.GuiStartupConfiguration(**kwargs)


def test_no_artifacts_no_service_instance_or_file_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No lifecycle artifacts means no inspection or discovery")

    monkeypatch.setattr(m, "ResearchCandidateLifecycleInspectionService", forbidden)
    for name in ("open", "glob", "rglob", "iterdir", "exists", "resolve"):
        monkeypatch.setattr(Path, name, forbidden)
    service = m.ReadOnlyGuiApplicationService(m.GuiStartupConfiguration())
    first = service.get_research_candidate_lifecycle_state()
    assert first.status is Status.UNAVAILABLE
    assert first == service.get_research_candidate_lifecycle_state()
    service.get_overview()


def test_all_flags_consumed_exact_paths_and_qt_forwarding():
    values = {name: Path(f"explicit-{i}.json") for i, name in enumerate(CONFIG_FIELDS)}
    argv = [
        item
        for name, value in values.items()
        for item in ("--" + name.replace("_", "-"), str(value))
    ]
    config, qt = _parse_startup_arguments([*argv, "-platform", "offscreen"])
    assert {name: getattr(config, name) for name in CONFIG_FIELDS} == values
    assert qt == ("-platform", "offscreen")
    default, qt = _parse_startup_arguments([])
    assert all(getattr(default, name) is None for name in CONFIG_FIELDS) and qt == ()


@pytest.mark.parametrize("valid", [True, False])
def test_overview_never_reads_lifecycle_cached_getter_only(
    tmp_path, monkeypatch, valid
):
    paths = write_artifacts(tmp_path)
    if not valid:
        paths[-1].write_text("invalid", encoding="utf-8")
    service = m.ReadOnlyGuiApplicationService(
        m.GuiStartupConfiguration(**dict(zip(CONFIG_FIELDS, paths, strict=True)))
    )
    opens = []
    original = Path.open

    def opened(path, *args, **kwargs):
        opens.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    service.get_overview()
    service.get_overview()
    assert opens == []
    state = service.get_research_candidate_lifecycle_state()
    assert state.status is (Status.AVAILABLE if valid else Status.ATTENTION)
    assert state is service.get_research_candidate_lifecycle_state()
    service.get_overview()
    assert opens == list(paths)


def test_report_configuration_does_not_select_lifecycle(monkeypatch):
    class Report:
        def __init__(self, path):
            pass

    monkeypatch.setattr(m, "CompactReportResearchService", Report)
    service = m.ReadOnlyGuiApplicationService(
        m.GuiStartupConfiguration(research_report=Path("report.json"))
    )
    assert service.get_research_candidate_lifecycle_state().status is Status.UNAVAILABLE
