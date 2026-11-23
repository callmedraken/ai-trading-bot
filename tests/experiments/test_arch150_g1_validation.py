from __future__ import annotations

import inspect
import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid5

import pytest

from trading_bot.experiments import arch150_g1_discovery as discovery
from trading_bot.experiments import arch150_g1_validation as validation
from trading_bot.experiments import arch150_intraday_ai as arch150
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

SOURCE = discovery.SourceIdentity(discovery.FEATURE_BRANCH, "a" * 40, "b" * 40)


def _session_bars(symbol, day, prices):
    schedule = arch150._SESSION_AUTHORITY.schedule_for(day)
    assert schedule is not None
    for offset, value in enumerate(prices):
        price = Decimal(value)
        yield arch150.IntradayBar(
            symbol,
            schedule.opens_at + timedelta(minutes=offset),
            price,
            price,
            price,
            price,
            100,
        )


def _make_custody(*, profitable=False):
    scheduled = arch150._SESSION_AUTHORITY.published.sessions
    days = (
        tuple(
            day
            for year in (2021, 2022, 2023)
            for day in tuple(day for day in scheduled if day.year == year)[:100]
        )
        if profitable
        else (date(2021, 1, 4),)
    )
    return tuple(
        bar
        for symbol in arch150.INITIAL_UNIVERSE
        for day, prices in (
            (date(2020, 1, 2), ("100", "102", "108")),
            *(
                (day, ("100", "102", "104", "108") if profitable else ("100",))
                for day in days
            ),
        )
        for bar in _session_bars(symbol, day, prices)
    )


def _sign(material):
    identity = uuid5(
        discovery._REPORT_NAMESPACE, canonical_json_bytes(material).decode()
    )
    return identity, canonical_json_bytes({"report_id": str(identity), **material})


def _observation(bars):
    admitted = arch150.validate_universe_minute_bars(bars)
    dataset = arch150._project_accepted_sparse_stage(
        admitted, arch150.ResearchStage.DISCOVERY
    )
    manifest = arch150.freeze_g1_population()
    ledger = arch150.TrialLedger(manifest)
    evaluations = []
    for slot in manifest.slots:
        evaluation = arch150.evaluate_frozen_trial(ledger, slot, dataset)
        evaluations.append(evaluation)
        ledger = ledger.consume(evaluation)
    finalized = arch150.finalize_discovery_population(dataset, ledger)
    freeze = arch150.freeze_candidate_population(finalized, ledger)
    # A single synthetic up session shortlists B1 on each symbol and nothing else.
    assert freeze.candidate_slot_ids == tuple(
        slot.slot_id for slot in manifest.slots[8:10]
    )
    material = discovery._report_material(
        source=SOURCE,
        input_root=discovery.ACCEPTED_INPUT_ROOT,
        snapshot=discovery.InputSnapshot(bars, ()),
        manifest=manifest,
        ledger=ledger,
        evaluations=tuple(evaluations),
        discovery_freeze=finalized,
        candidate_freeze=freeze,
    )
    identity, body = _sign(material)
    accepted = validation._AcceptedDiscovery(
        SOURCE, identity, ledger.ledger_id, finalized.freeze_id, freeze.freeze_id
    )
    return admitted, dataset, accepted, freeze, material, body


def test_authentication_reconstructs_exact_authority_and_blocks_generic_data(
    monkeypatch,
):
    bars = _make_custody()
    admitted, discovery_dataset, accepted, candidate_freeze, _, body = _observation(
        bars
    )
    authority = validation._authenticate_discovery_report(body, accepted)
    assert authority.bind_candidates(discovery_dataset) == candidate_freeze
    with pytest.raises(arch150.Arch150Error):
        arch150.open_sparse_validation_dataset(bars, candidate_freeze)

    def accept(input_bars):
        assert tuple(input_bars) == bars
        return admitted

    monkeypatch.setattr(arch150, "_validate_accepted_sparse_custody", accept)
    dataset = arch150.open_sparse_validation_dataset(bars, candidate_freeze)
    assert (dataset.start, dataset.end_exclusive) == (
        date(2021, 1, 1),
        date(2024, 1, 1),
    )
    assert (
        dataset._sparse_custody_authority is arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY
    )
    assert all(
        bar.session_date == date(2021, 1, 4)
        for stream in dataset.bars.by_symbol.values()
        for bar in stream.bars
    )
    generic = arch150.open_validation_dataset(
        (bar for bar in bars if bar.session_date.year == 2021), candidate_freeze
    )
    with pytest.raises(
        validation.Arch150G1ValidationError, match="VALIDATION_CUSTODY_REQUIRED"
    ):
        validation._replay_validation_slot(generic, authority.slots[0])
    with pytest.raises(
        validation.Arch150G1ValidationError, match="VALIDATION_SLOT_NOT_AUTHORIZED"
    ):
        validation._replay_validation_slot(dataset, authority.manifest.slots[0])
    with pytest.raises(
        arch150.InformationFirewallError, match="bind accepted discovery"
    ):
        arch150.open_sparse_validation_dataset(
            bars, replace_candidate_dataset(candidate_freeze)
        )


def replace_candidate_dataset(freeze):
    manifest = arch150.freeze_g1_population()
    wrong = arch150.open_discovery_dataset(
        bar for bar in _make_custody() if bar.session_date.year == 2020
    )
    ledger = arch150.TrialLedger(manifest)
    for slot in manifest.slots:
        ledger = ledger.consume(
            arch150._evaluate_frozen_trial_for_test(ledger, slot, wrong)
        )
    other = arch150.freeze_candidate_population(
        arch150.finalize_discovery_population(wrong, ledger), ledger
    )
    assert other.candidate_slot_ids == freeze.candidate_slot_ids
    return other


@pytest.mark.parametrize(
    "mutation", ["reorder_trials", "drop_candidate", "source", "custody"]
)
def test_report_tampering_fails_even_with_recomputed_report_id(mutation):
    _, _, accepted, _, material, _ = _observation(_make_custody())
    if mutation == "reorder_trials":
        material["trials"].reverse()
    elif mutation == "drop_candidate":
        material["candidate_slots"].pop()
    elif mutation == "source":
        material["source"]["head"] = "c" * 40
    else:
        material["accepted_sparse_custody"]["dataset_id"] = "substituted"
    report_id, edited = _sign(material)
    with pytest.raises(validation.Arch150G1ValidationError, match="REPORT_IDENTITY"):
        validation._authenticate_discovery_report(edited, accepted)
    with pytest.raises(validation.Arch150G1ValidationError, match="MISMATCH"):
        validation._authenticate_discovery_report(
            edited, replace(accepted, report_id=report_id)
        )


def test_rebuilt_evaluation_binding_rejects_tampered_evaluation_id():
    _, dataset, accepted, _, material, _ = _observation(_make_custody())
    material["trials"][0]["evaluation_id"] = str(accepted.ledger_id)
    report_id, body = _sign(material)
    authority = validation._authenticate_discovery_report(
        body, replace(accepted, report_id=report_id)
    )
    with pytest.raises(validation.Arch150G1ValidationError, match="EVALUATION_BINDING"):
        authority.bind_candidates(dataset)


@pytest.mark.parametrize("profitable", [False, True])
def test_one_shot_ranks_and_freezes_by_slot_not_shared_program(
    tmp_path, monkeypatch, profitable
):
    bars = _make_custody(profitable=profitable)
    admitted, _, accepted, _, _, body = _observation(bars)
    calls = []

    def validate(candidate):
        assert tuple(candidate) == bars
        calls.append("custody")
        return admitted

    monkeypatch.setattr(arch150, "_validate_accepted_sparse_custody", validate)
    progress = []
    kwargs = dict(
        output_validator=lambda path: path,
        source_reader=lambda: SOURCE,
        report_reader=lambda: body,
        input_reader=lambda: discovery.InputSnapshot(bars, ()),
        accepted=accepted,
        progress=progress.append,
    )
    output = tmp_path / "validation"
    result = validation._run_one_shot(output, **kwargs)
    clone = validation._run_one_shot(tmp_path / "same-validation", **kwargs)
    assert calls == ["custody", "custody"]
    assert result.report_id == clone.report_id
    assert result.validation_freeze_id == clone.validation_freeze_id
    report_bytes = (output / "validation.json").read_bytes()
    assert report_bytes == (clone.output_directory / "validation.json").read_bytes()
    report = json.loads(report_bytes)
    freeze = report["validation_freeze"]
    first, second = freeze["evaluated_slots"]
    assert first["program_id"] == second["program_id"]
    assert first["slot_id"] != second["slot_id"]
    assert [first["source_symbol"], second["source_symbol"]] == ["SPY", "QQQ"]
    assert report["ranking_slot_ids"] == sorted((first["slot_id"], second["slot_id"]))
    assert [item["slot_id"] for item in freeze["qualified_slots"]] == (
        [first["slot_id"], second["slot_id"]] if profitable else []
    )
    assert freeze["holdout_authorized"] is False
    assert result.terminal_disposition == (
        "VALIDATION_CANDIDATES_FROZEN_PENDING_SELECTION_BIAS"
        if profitable
        else "NO_HOLDOUT_CANDIDATES"
    )
    assert report["effect_counters"]["validation_strategy_replay_count"] == 2
    assert report["effect_counters"]["discovery_strategy_replay_count"] == 0
    assert progress[:6] == [
        "ARCH150_VALIDATION_STAGE=DISCOVERY_AUTHORITY_ACCEPTED",
        "ARCH150_VALIDATION_STAGE=SPARSE_VALIDATION_OPENED",
        "ARCH150_VALIDATION_SLOT_START=1/2",
        "ARCH150_VALIDATION_SLOT_COMPLETE=1/2",
        "ARCH150_VALIDATION_SLOT_START=2/2",
        "ARCH150_VALIDATION_SLOT_COMPLETE=2/2",
    ]
    with pytest.raises(
        discovery.Arch150G1DiscoveryError, match="OUTPUT_ALREADY_EXISTS"
    ):
        validation._run_one_shot(output, **kwargs)


def test_report_rejection_precedes_custody_read_and_public_entry_is_closed(
    tmp_path, monkeypatch
):
    _, _, accepted, _, material, _ = _observation(_make_custody())
    material["candidate_slots"].reverse()
    _, body = _sign(material)
    output = tmp_path / "rejected"

    def forbidden():
        pytest.fail(
            "custody was accessed before the discovery report was authenticated"
        )

    with pytest.raises(validation.Arch150G1ValidationError, match="REPORT_IDENTITY"):
        validation._run_one_shot(
            output,
            output_validator=lambda path: path,
            source_reader=lambda: SOURCE,
            report_reader=lambda: body,
            input_reader=forbidden,
            accepted=accepted,
            progress=lambda _: None,
        )
    assert sorted(path.name for path in output.iterdir()) == ["attempt.json"]
    assert tuple(
        inspect.signature(validation.run_arch150_g1_validation).parameters
    ) == ("output_directory",)

    def capture(path, **kwargs):
        assert path == Path("synthetic")
        assert kwargs["accepted"] is validation._ACCEPTED_DISCOVERY
        assert kwargs["report_reader"] is validation._read_pinned_discovery_report

    monkeypatch.setattr(validation, "_run_one_shot", capture)
    validation.run_arch150_g1_validation(Path("synthetic"))


def test_validation_gates_are_inclusive_for_frequency_and_strict_for_economics():
    freq = replace(
        arch150.compute_validation_frequency_diagnostics(()),
        average_completed_round_trips_per_validation_year=Decimal("100"),
        active_session_fraction=Decimal("0.35"),
        median_trades_per_active_session=Decimal("3"),
    )
    replay = arch150.replay_program(
        arch150.VwapTrendReversalProgram(),
        tuple(_session_bars("SPY", date(2021, 1, 4), ("100",))),
    )
    metrics = replace(
        validation._validation_metrics(replay, freq),
        net_return=Decimal(".01"),
        profit_factor=Decimal("1.01"),
    )
    assert validation._qualification_failures(metrics, freq) == ()
    assert validation._qualification_failures(
        replace(metrics, net_return=Decimal("0"), profit_factor=Decimal("1")), freq
    ) == ("NONPOSITIVE_STRESS_RETURN", "STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE")
    assert validation._qualification_failures(
        replace(metrics, cost_case=arch150.CostCase.ZERO), freq
    ) == ("STRESS_REQUIRED",)
