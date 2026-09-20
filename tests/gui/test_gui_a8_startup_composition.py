"""GUI-A8 startup configuration and composite-service contract tests."""

from pathlib import Path

import pytest

from trading_bot.gui import (
    GuiStartupConfiguration,
    MarketDataPageStatus,
    OperatorOperationsPageStatus,
    PaperAccountPageStatus,
    PaperPageStatus,
    ReadOnlyGuiApplicationService,
    ResearchReportStatus,
)


def test_default_configuration_is_fully_read_only_and_unavailable() -> None:
    service = ReadOnlyGuiApplicationService(GuiStartupConfiguration())

    assert service.get_research_state().status is ResearchReportStatus.UNAVAILABLE
    assert service.get_paper_state().status is PaperPageStatus.UNAVAILABLE
    assert service.get_market_data_state().status is MarketDataPageStatus.UNAVAILABLE
    assert (
        service.get_paper_account_state().status
        is PaperAccountPageStatus.UNAVAILABLE
    )
    assert (
        service.get_operator_observability_state().status
        is OperatorOperationsPageStatus.UNAVAILABLE
    )


@pytest.mark.parametrize(
    "field",
    (
        "research_report",
        "market_data_snapshot",
        "paper_account_genesis",
        "paper_account_prior",
        "paper_account_snapshot",
        "paper_account_cycle_report",
        "paper_account_successor",
    ),
)
def test_startup_configuration_rejects_non_path_artifact_fields(field: str) -> None:
    with pytest.raises(TypeError):
        GuiStartupConfiguration(**{field: "private-artifact.json"})


@pytest.mark.parametrize(
    "field",
    (
        "market_data_expected_byte_length",
        "paper_account_expected_byte_length",
        "paper_account_successor_expected_byte_length",
    ),
)
@pytest.mark.parametrize("value", (True, -1, "12"))
def test_startup_configuration_rejects_invalid_byte_lengths(
    field: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {field: value}
    if field == "market_data_expected_byte_length":
        kwargs["market_data_snapshot"] = Path("snapshot.json")
    elif field == "paper_account_expected_byte_length":
        kwargs["paper_account_genesis"] = Path("genesis.json")
    else:
        kwargs.update(
            {
                "paper_account_prior": Path("prior.json"),
                "paper_account_snapshot": Path("snapshot.json"),
                "paper_account_cycle_report": Path("report.json"),
                "paper_account_successor": Path("successor.json"),
            }
        )
    with pytest.raises(ValueError):
        GuiStartupConfiguration(**kwargs)


def test_market_data_evidence_requires_snapshot() -> None:
    with pytest.raises(ValueError):
        GuiStartupConfiguration(market_data_expected_sha256="a" * 64)
    with pytest.raises(ValueError):
        GuiStartupConfiguration(market_data_expected_byte_length=1)


@pytest.mark.parametrize(
    "missing",
    (
        "paper_account_prior",
        "paper_account_snapshot",
        "paper_account_cycle_report",
        "paper_account_successor",
    ),
)
def test_successor_mode_requires_all_four_explicit_artifacts(missing: str) -> None:
    kwargs = {
        "paper_account_prior": Path("prior.json"),
        "paper_account_snapshot": Path("snapshot.json"),
        "paper_account_cycle_report": Path("report.json"),
        "paper_account_successor": Path("successor.json"),
    }
    kwargs[missing] = None
    with pytest.raises(ValueError):
        GuiStartupConfiguration(**kwargs)


def test_genesis_and_successor_modes_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError):
        GuiStartupConfiguration(
            paper_account_genesis=Path("genesis.json"),
            paper_account_prior=Path("prior.json"),
            paper_account_snapshot=Path("snapshot.json"),
            paper_account_cycle_report=Path("report.json"),
            paper_account_successor=Path("successor.json"),
        )


def test_paper_account_expected_evidence_requires_corresponding_mode() -> None:
    with pytest.raises(ValueError):
        GuiStartupConfiguration(paper_account_expected_sha256="a" * 64)
    with pytest.raises(ValueError):
        GuiStartupConfiguration(paper_account_successor_expected_byte_length=1)


def test_composite_service_delegates_only_configured_leaf_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.gui import startup_composition as composition

    calls: list[tuple[str, object]] = []

    class _MarketData:
        def __init__(self, path: Path, **kwargs: object) -> None:
            calls.append(("market-init", (path, kwargs)))

        def get_market_data_state(self):
            calls.append(("market-get", None))
            return composition.unavailable_market_data_state()

    class _Genesis:
        def __init__(self, path: Path, **kwargs: object) -> None:
            calls.append(("genesis-init", (path, kwargs)))

        def get_paper_account_state(self):
            calls.append(("genesis-get", None))
            return composition.unavailable_paper_account_state()

    class _Successor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("successor adapter must not be constructed")

    monkeypatch.setattr(composition, "VerifiedSnapshotInspectionService", _MarketData)
    monkeypatch.setattr(
        composition,
        "VerifiedGenesisPaperAccountInspectionService",
        _Genesis,
    )
    monkeypatch.setattr(
        composition,
        "VerifiedSuccessorPaperAccountInspectionService",
        _Successor,
    )

    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(
            market_data_snapshot=Path("snapshot.json"),
            market_data_expected_sha256="a" * 64,
            market_data_expected_byte_length=123,
            paper_account_genesis=Path("genesis.json"),
            paper_account_expected_sha256="b" * 64,
            paper_account_expected_byte_length=456,
        )
    )

    assert service.get_market_data_state().status is MarketDataPageStatus.UNAVAILABLE
    assert (
        service.get_paper_account_state().status
        is PaperAccountPageStatus.UNAVAILABLE
    )
    assert calls == [
        (
            "market-init",
            (
                Path("snapshot.json"),
                {"expected_sha256": "a" * 64, "expected_byte_length": 123},
            ),
        ),
        (
            "genesis-init",
            (
                Path("genesis.json"),
                {"expected_sha256": "b" * 64, "expected_byte_length": 456},
            ),
        ),
        ("market-get", None),
        ("genesis-get", None),
    ]


def test_successor_service_receives_exact_four_paths_and_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trading_bot.gui import startup_composition as composition

    captured: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class _Successor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            captured.append((args, kwargs))

        def get_paper_account_state(self):
            return composition.unavailable_paper_account_state()

    monkeypatch.setattr(
        composition,
        "VerifiedSuccessorPaperAccountInspectionService",
        _Successor,
    )
    paths = (
        Path("prior.json"),
        Path("snapshot.json"),
        Path("report.json"),
        Path("successor.json"),
    )
    service = ReadOnlyGuiApplicationService(
        GuiStartupConfiguration(
            paper_account_prior=paths[0],
            paper_account_snapshot=paths[1],
            paper_account_cycle_report=paths[2],
            paper_account_successor=paths[3],
            paper_account_successor_expected_sha256="c" * 64,
            paper_account_successor_expected_byte_length=789,
        )
    )

    assert (
        service.get_paper_account_state().status
        is PaperAccountPageStatus.UNAVAILABLE
    )
    assert captured == [
        (
            paths,
            {
                "expected_successor_sha256": "c" * 64,
                "expected_successor_byte_length": 789,
            },
        )
    ]
