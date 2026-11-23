from __future__ import annotations

import ast
import hashlib
import inspect
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trading_bot.experiments import arch150_g1_discovery as discovery
from trading_bot.experiments import arch150_intraday_ai as arch150
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

_TEST_SOURCE = discovery.SourceIdentity(
    discovery.FEATURE_BRANCH,
    "1234567890abcdef1234567890abcdef12345678",
    "abcdef1234567890abcdef1234567890abcdef12",
)


def _csv_body(symbol: str, *, minutes: tuple[int, ...] = (0, 1, 2, 3, 4)) -> bytes:
    rows = [",".join(discovery._CSV_HEADER)]
    start = datetime(2016, 1, 4, 14, 30, tzinfo=UTC)
    for minute in minutes:
        timestamp = (
            (start + timedelta(minutes=minute))
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        rows.append(f"{timestamp},{symbol},1Min,100,100,100,100,100")
    return ("\n".join(rows) + "\n").encode("utf-8")


def _artifact_body(name: str, *, identity: str | None = None) -> bytes:
    schema, expected_identity, semantic_sha256 = discovery._SEMANTIC_PINS[name]
    return canonical_json_bytes(
        {
            "schema": schema,
            "identity": identity or expected_identity,
            "sha256": semantic_sha256,
            "material": {},
        }
    )


def _make_inputs(
    root: Path,
    *,
    wrong_identity: tuple[str, str] | None = None,
    minutes: tuple[int, ...] = (0, 1, 2, 3, 4),
) -> tuple[dict[str, tuple[int, str]], Path]:
    root.mkdir()
    (root / "normalized").mkdir()
    bodies = {
        "normalized/SPY.csv": _csv_body("SPY", minutes=minutes),
        "normalized/QQQ.csv": _csv_body("QQQ", minutes=minutes),
    }
    for name in discovery._SEMANTIC_PINS:
        identity = "wrong" if wrong_identity == (name, "wrong") else None
        bodies[name] = _artifact_body(name, identity=identity)
    for name, body in bodies.items():
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(body)
    pins = {
        name: (len(body), hashlib.sha256(body).hexdigest())
        for name, body in bodies.items()
    }
    return pins, root


def _run_fake(
    output_directory: Path,
    input_root: Path,
    input_reader,
    *,
    evaluator=None,
    dataset_opener=arch150._open_sparse_discovery_dataset_for_test,
    source_reader=lambda: _TEST_SOURCE,
):
    calls = []

    def evaluate(ledger, slot, dataset, *, initial_equity):
        calls.append((ledger.consumed_trial_count, slot.ordinal, initial_equity))
        assert dataset.stage is arch150.ResearchStage.DISCOVERY
        assert dataset.start == arch150.DISCOVERY_START
        assert dataset.end_exclusive == arch150.DISCOVERY_END
        assert all(
            bar.session_date < arch150.DISCOVERY_END
            for symbol in arch150.INITIAL_UNIVERSE
            for bar in dataset.bars.by_symbol[symbol].bars
        )
        selected = evaluator or arch150._evaluate_frozen_trial_for_test
        return selected(
            ledger,
            slot,
            dataset,
            initial_equity=initial_equity,
        )

    result = discovery._run_one_shot(
        output_directory,
        input_root=input_root,
        output_validator=lambda path: path.resolve(),
        input_reader=input_reader,
        source_reader=source_reader,
        dataset_opener=dataset_opener,
        evaluator=evaluate,
    )
    return result, calls


def test_published_input_artifact_and_semantic_pins_are_exact():
    assert discovery.ACCEPTED_INPUT_ROOT == Path(
        r"F:\AI\temp\arch150-d1r-offline-requalification-a46c4ad1-4287-4e51-8741-0316f784f1de"
    )
    assert discovery._ARTIFACT_PINS == {
        "normalized/SPY.csv": (
            55_599_367,
            "f7c1a708db72f9f73bd0d05c45dfffed26f5b5fa36c9428c8069af28d897c8ed",
        ),
        "normalized/QQQ.csv": (
            55_214_275,
            "c9c95664f1a0112d410cdc01273be8146f0136ca57591b18ddb6a7f1fbd3c471",
        ),
        "dataset.json": (
            871_998,
            "5f1fa356baaf6830bb3e9a7e045db156912a64b130fa63ebfc4cc34d1518e2",
        ),
        "custody-evidence.json": (
            310_526,
            "2422a9ca8528dce9f41fa1a24d3e983e9d580ba18c236975f87b3d27a9b83c1e",
        ),
        "evidence.json": (
            1_476,
            "1e481ac8d9f48f6c3f4ce6c9c4a49325e7e63ae2021d03f9c600278f37e9e528",
        ),
    }
    assert discovery._SEMANTIC_PINS["dataset.json"][1:] == (
        "ff5a3847-09c2-5902-b174-9e77eebf7d53",
        "0070a5c0cfa5cd7878253d93bc0895b46da28d8b5e2a71395e66ce904b3f85dd",
    )
    assert discovery._SEMANTIC_PINS["custody-evidence.json"][1:] == (
        "21e121dc-a9da-538f-bc88-c15fe7ea7f50",
        "5b6ac554eda73b588f2f6d664c14e5c7fca3c151966cb546c17621d0c7e6ad83",
    )


def test_production_entry_pins_input_and_strict_output_validator(monkeypatch, tmp_path):
    assert tuple(inspect.signature(discovery.run_arch150_g1_discovery).parameters) == (
        "output_directory",
    )
    captured = {}

    def inspect_call(output_directory, **kwargs):
        captured["output_directory"] = output_directory
        captured.update(kwargs)
        return "sentinel"

    monkeypatch.setattr(discovery, "_run_one_shot", inspect_call)
    output = tmp_path / "output"
    assert discovery.run_arch150_g1_discovery(output) == "sentinel"
    assert captured["input_root"] == discovery.ACCEPTED_INPUT_ROOT
    assert captured["input_reader"] is discovery._read_pinned_input
    assert (
        captured["output_validator"] is discovery._validate_production_output_directory
    )
    assert captured["dataset_opener"] is arch150.open_sparse_discovery_dataset
    assert captured["dataset_opener"] is not arch150.open_discovery_dataset
    assert captured["evaluator"] is arch150.evaluate_frozen_trial


def test_strict_production_output_validator_rejects_non_f_root():
    with pytest.raises(discovery.Arch150G1DiscoveryError) as error:
        discovery._validate_production_output_directory(Path(r"D:\temp\g1-output"))
    assert error.value.code == "OUTPUT_MUST_BE_UNDER_F_AI_TEMP"


def test_parser_preserves_missing_minutes_without_inventing_bars():
    bars = discovery._parse_normalized_csv(
        _csv_body("SPY", minutes=(0, 2)),
        "SPY",
    )
    assert len(bars) == 2
    assert (bars[1].timestamp - bars[0].timestamp) == timedelta(minutes=2)


@pytest.mark.parametrize(
    "body",
    (
        b"",
        b"timestamp,symbol,symbol,open,high,low,close,volume\n",
        b"timestamp,symbol,resolution,open,high,low,close,volume,extra\n",
        b"timestamp,symbol,resolution,open,high,low,close,volume\n"
        b"2016-01-04T14:30:00.000000Z,QQQ,1Min,100,100,100,100,100\n",
        b"timestamp,symbol,resolution,open,high,low,close,volume\n"
        b"2016-01-04T14:30:00.000000Z,SPY,5Min,100,100,100,100,100\n",
        b"timestamp,symbol,resolution,open,high,low,close,volume\n"
        b"2016-01-04T14:30:00.000000Z,SPY,1Min,not-a-decimal,100,100,100,100\n",
        b"timestamp,symbol,resolution,open,high,low,close,volume\n"
        b"2024-01-02T14:30:00.000000Z,SPY,1Min,100,100,100,100,100\n",
        b"timestamp,symbol,resolution,open,high,low,close,volume\n"
        b"2016-01-04T14:30:00.000000Z,SPY,1Min,100,100,100,100\n",
    ),
)
def test_parser_fails_closed_on_malformed_or_out_of_scope_csv(body):
    with pytest.raises(discovery.Arch150G1DiscoveryError):
        discovery._parse_normalized_csv(body, "SPY")


@pytest.mark.parametrize("name", ("normalized/SPY.csv", "normalized/QQQ.csv"))
def test_wrong_normalized_csv_hash_fails_before_any_trial(name, tmp_path):
    pins, root = _make_inputs(tmp_path / "input")
    path = root / name
    original = path.read_bytes()
    tampered = original.replace(
        b",100,100,100,100,100\n",
        b",101,100,100,100,100\n",
        1,
    )
    assert len(tampered) == len(original)
    path.write_bytes(tampered)
    output = tmp_path / "wrong-hash-output"
    calls = []

    def forbidden_evaluator(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("evaluation ran before the input hash was accepted")

    with pytest.raises(discovery.Arch150G1DiscoveryError) as error:
        _run_fake(
            output,
            root,
            discovery._read_input_snapshot,
            evaluator=forbidden_evaluator,
        )
    assert error.value.code == "INPUT_ARTIFACT_COMMITMENT_MISMATCH"
    assert calls == []
    assert (output / "attempt.json").is_file()
    assert not (output / "discovery.json").exists()
    assert pins[name] != (
        path.stat().st_size,
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


@pytest.mark.parametrize("name", ("dataset.json", "custody-evidence.json"))
def test_wrong_dataset_or_custody_semantics_fail_before_replay(name, tmp_path):
    _, root = _make_inputs(tmp_path / "input", wrong_identity=(name, "wrong"))
    custom_physical_pins = {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in root.rglob("*")
        if path.is_file()
    }
    calls = []

    def forbidden_evaluator(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("evaluation ran before semantic evidence was accepted")

    def input_reader(path):
        return discovery._read_input_snapshot(
            path,
            artifact_pins=custom_physical_pins,
            semantic_pins=discovery._SEMANTIC_PINS,
        )

    with pytest.raises(discovery.Arch150G1DiscoveryError) as error:
        _run_fake(
            tmp_path / "wrong-semantics-output",
            root,
            input_reader,
            evaluator=forbidden_evaluator,
        )
    assert error.value.code == "INPUT_SEMANTIC_IDENTITY_MISMATCH"
    assert calls == []


def test_exact_24_slot_stress_discovery_is_reported_deterministically(
    monkeypatch,
    tmp_path,
):
    pins, input_root = _make_inputs(tmp_path / "input")
    evaluator_calls = []
    finalization_calls = []
    candidate_calls = []
    original_finalize = arch150.finalize_discovery_population
    original_freeze = arch150.freeze_candidate_population

    def evaluator(ledger, slot, dataset, *, initial_equity):
        evaluator_calls.append(slot.ordinal)
        assert initial_equity == Decimal("1")
        result = arch150._evaluate_frozen_trial_for_test(
            ledger,
            slot,
            dataset,
            initial_equity=initial_equity,
        )
        assert result.replay_result is not None
        assert result.replay_result.cost_case is arch150.CostCase.STRESS
        return result

    def finalize(dataset, ledger):
        finalization_calls.append(ledger.consumed_trial_count)
        assert ledger.is_complete
        assert ledger.consumed_trial_count == 24
        return original_finalize(dataset, ledger)

    def freeze(discovery_freeze, ledger):
        candidate_calls.append((discovery_freeze, ledger.consumed_trial_count))
        assert ledger.is_complete
        return original_freeze(discovery_freeze, ledger)

    monkeypatch.setattr(arch150, "finalize_discovery_population", finalize)
    monkeypatch.setattr(arch150, "freeze_candidate_population", freeze)

    def input_reader(path):
        return discovery._read_input_snapshot(path, artifact_pins=pins)

    first, calls = _run_fake(
        tmp_path / "result-one",
        input_root,
        input_reader,
        evaluator=evaluator,
    )
    second, _ = _run_fake(
        tmp_path / "result-two",
        input_root,
        input_reader,
        evaluator=evaluator,
    )

    assert calls == [(ordinal - 1, ordinal, Decimal("1")) for ordinal in range(1, 25)]
    assert evaluator_calls == list(range(1, 25)) * 2
    assert finalization_calls == [24, 24]
    assert [item[1] for item in candidate_calls] == [24, 24]
    assert first.terminal_disposition == "NO_VALIDATION_CANDIDATES"
    assert first.candidate_freeze_id is None
    assert first.report_id == second.report_id
    assert first.report_sha256 == second.report_sha256
    first_bytes = (first.output_directory / "discovery.json").read_bytes()
    second_bytes = (second.output_directory / "discovery.json").read_bytes()
    assert first_bytes == second_bytes
    assert hashlib.sha256(first_bytes).hexdigest() == first.report_sha256
    assert len(first_bytes) == first.report_byte_length
    report = json.loads(first_bytes)
    manifest = arch150.freeze_g1_population()
    assert report["schema"] == discovery.G1_DISCOVERY_REPORT_SCHEMA
    assert report["manifest_id"] == discovery.G1_MANIFEST_ID
    assert report["manifest_schema"] == arch150.G1_POPULATION_SCHEMA
    assert report["slot_ids"] == [str(slot.slot_id) for slot in manifest.slots]
    assert report["trial_count"] == 24
    assert [trial["ordinal"] for trial in report["trials"]] == list(range(1, 25))
    assert all(trial["bar_resolution"] == "ONE_MINUTE" for trial in report["trials"])
    assert report["qualification_cost_case"] == "STRESS"
    assert report["terminal_disposition"] == "NO_VALIDATION_CANDIDATES"
    assert report["terminal_disposition_counts"]["SHORTLISTED"] == 0
    assert "validation" not in report
    assert "holdout" not in report
    assert report["effect_counters"]["validation_strategy_replay_count"] == 0
    assert report["effect_counters"]["2024_plus_data_accessed"] is False
    assert report["input_artifacts"][-1]["name"] == "evidence.json"


def test_nonprefix_shortlists_report_manifest_ordinals_and_unknown_slots_fail_closed(
    monkeypatch,
    tmp_path,
):
    pins, input_root = _make_inputs(tmp_path / "input")
    manifest = arch150.freeze_g1_population()
    eligible_session_dates = tuple(
        session
        for session in arch150._SESSION_AUTHORITY.published.sessions
        if arch150.DISCOVERY_START <= session < arch150.DISCOVERY_END
    )

    def evaluator(ledger, slot, dataset, *, initial_equity):
        if slot.ordinal not in (2, 5):
            return arch150._evaluate_frozen_trial_for_test(
                ledger,
                slot,
                dataset,
                initial_equity=initial_equity,
            )

        lookback_sessions = slot._program.lookback_sessions
        sessions = eligible_session_dates[: lookback_sessions + 1]
        assert len(sessions) == lookback_sessions + 1
        bars = []
        for session_index, session in enumerate(sessions):
            schedule = arch150._SESSION_AUTHORITY.schedule_for(session)
            assert schedule is not None
            opening = schedule.opens_at.astimezone(UTC)
            prices = (
                ("100", "100", "100", "100", "100")
                if session_index < lookback_sessions
                else ("100", "100", "102.5", "102.5", "102.5")
            )
            bars.extend(
                arch150.IntradayBar(
                    slot.source_symbol,
                    opening + timedelta(minutes=minute),
                    Decimal(price),
                    Decimal(price),
                    Decimal(price),
                    Decimal(price),
                    100,
                )
                for minute, price in enumerate(prices)
            )

        replay = arch150.replay_program(
            slot._program,
            bars,
            cost_case=arch150.CostCase.STRESS,
            initial_equity=initial_equity,
        )
        assert replay.trades
        return arch150._make_g1_evaluation(
            slot,
            arch150._discovery_dataset_id(dataset),
            replay,
            None,
            None,
        )

    def input_reader(path):
        return discovery._read_input_snapshot(path, artifact_pins=pins)

    result, _ = _run_fake(
        tmp_path / "nonprefix-output",
        input_root,
        input_reader,
        evaluator=evaluator,
    )
    report = json.loads((result.output_directory / "discovery.json").read_bytes())
    assert report["candidate_slots"] == [
        {"ordinal": 2, "slot_id": str(manifest.slots[1].slot_id)},
        {"ordinal": 5, "slot_id": str(manifest.slots[4].slot_id)},
    ]
    assert report["trials"][0]["disposition"] == "ZERO_TRADE"
    assert report["trials"][1]["disposition"] == "SHORTLISTED"
    assert report["trials"][4]["disposition"] == "SHORTLISTED"
    assert report["effect_counters"]["validation_strategy_replay_count"] == 0
    assert report["effect_counters"]["2024_plus_data_accessed"] is False

    monkeypatch.setattr(
        arch150,
        "freeze_candidate_population",
        lambda *_args: type(
            "InvalidCandidateFreeze",
            (),
            {"freeze_id": "synthetic-invalid", "candidate_slot_ids": ("unknown",)},
        )(),
    )
    with pytest.raises(discovery.Arch150G1DiscoveryError) as error:
        _run_fake(
            tmp_path / "unknown-candidate-output",
            input_root,
            input_reader,
            evaluator=evaluator,
        )
    assert error.value.code == "CANDIDATE_SLOT_NOT_IN_FROZEN_MANIFEST"
    assert not (tmp_path / "unknown-candidate-output" / "discovery.json").exists()


def test_source_identity_requires_clean_feature_worktree(monkeypatch, tmp_path):
    values = {
        ("rev-parse", "--show-toplevel"): str(tmp_path),
        ("branch", "--show-current"): discovery.FEATURE_BRANCH,
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "HEAD^{tree}"): "b" * 40,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
    }
    module_path = tmp_path / "src" / "trading_bot" / "experiments" / "m.py"
    module_path.parent.mkdir(parents=True)
    monkeypatch.setattr(discovery, "__file__", str(module_path))
    monkeypatch.setattr(
        discovery,
        "_git",
        lambda _root, *arguments: values[arguments],
    )
    identity = discovery._read_source_identity()
    assert identity == discovery.SourceIdentity(
        discovery.FEATURE_BRANCH,
        "a" * 40,
        "b" * 40,
    )

    values[("status", "--porcelain=v1", "--untracked-files=all")] = "?? untracked.txt"
    with pytest.raises(discovery.Arch150G1DiscoveryError) as error:
        discovery._read_source_identity()
    assert error.value.code == "SOURCE_WORKTREE_NOT_CLEAN"


def test_output_is_create_once_and_failed_attempt_is_preserved(tmp_path):
    existing = tmp_path / "already-exists"
    existing.mkdir()
    called = []
    with pytest.raises(discovery.Arch150G1DiscoveryError) as error:
        _run_fake(
            existing,
            tmp_path,
            lambda _path: called.append(True),
        )
    assert error.value.code == "OUTPUT_ALREADY_EXISTS"
    assert called == []


def test_operator_import_and_call_boundary_stays_offline():
    path = Path(discovery.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_imports = ("alpaca", "robinhood", "broker", "credential", "web")
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(
        token in module.lower() for module in imported for token in forbidden_imports
    )
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "replay_program" not in calls
    assert "open_validation_dataset" not in calls
    assert "open_holdout_dataset" not in calls
