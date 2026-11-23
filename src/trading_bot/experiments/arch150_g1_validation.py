"""One-shot offline validation of the accepted Arch150 discovery population."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from decimal import Decimal, localcontext
from pathlib import Path
from statistics import median
from typing import Final
from uuid import UUID, uuid5

from trading_bot.experiments import arch150_g1_discovery as discovery
from trading_bot.experiments import arch150_intraday_ai as arch150
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

ACCEPTED_DISCOVERY_ROOT: Final = Path(
    r"F:\AI\temp\arch150-g1-discovery-3dc75767-c48c-4a99-8624-c25ccd67cbe8"
)
VALIDATION_REPORT_SCHEMA: Final = "arch150-g1-validation-observation/v1"
_REPORT_NAMESPACE: Final = UUID("6b3add18-b48c-4fec-8229-ff03bb23939d")
_FREEZE_NAMESPACE: Final = UUID("b5124cd4-d35e-4710-a575-1ef33b03fd17")


class Arch150G1ValidationError(ValueError):
    """Stable error classification for an aborted validation observation."""


@dataclass(frozen=True, slots=True)
class _AcceptedDiscovery:
    source: discovery.SourceIdentity
    report_id: UUID
    ledger_id: UUID
    discovery_freeze_id: UUID
    candidate_freeze_id: UUID


_ACCEPTED_DISCOVERY: Final = _AcceptedDiscovery(
    discovery.SourceIdentity(
        discovery.FEATURE_BRANCH,
        "dc4ed895a370036fd49c45e7ec50929eaf214fe4",
        "0d838d11535c1ba759181f1fcea98e5c43a37a81",
    ),
    UUID("ec23c374-e069-59e9-9167-14b2adf3fb16"),
    UUID("eef87bad-cf1e-520f-9b95-ebd35d0fd575"),
    UUID("88a7e148-cbf7-5f6b-9ef0-a9858d9396cd"),
    UUID("84367c0f-74d4-5125-a2f3-71f5a9ad6014"),
)


@dataclass(frozen=True, slots=True)
class _DiscoveryTrial:
    evaluation_id: UUID
    replay_id: UUID | None
    input_digest: str | None
    disposition: arch150.TrialDisposition
    diagnostic_code: str | None


@dataclass(frozen=True, slots=True)
class _DiscoveryAuthority:
    accepted: _AcceptedDiscovery
    manifest: arch150.G1PopulationManifest
    trials: tuple[_DiscoveryTrial, ...]
    slots: tuple[arch150.FrozenTrialSlot, ...]

    def bind_candidates(
        self, dataset: arch150.ResearchDataset
    ) -> arch150.CandidateFreeze:
        if (
            type(dataset) is not arch150.ResearchDataset
            or dataset._authority_seal is not arch150._DATASET_SEAL
            or dataset.stage is not arch150.ResearchStage.DISCOVERY
            or dataset._sparse_custody_authority
            is not arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY
        ):
            raise Arch150G1ValidationError("ACCEPTED_DISCOVERY_CUSTODY_REQUIRED")
        dataset_id = arch150._discovery_dataset_id(dataset)
        ledger = arch150.TrialLedger(self.manifest)
        for slot, trial in zip(self.manifest.slots, self.trials, strict=True):
            fixed = (
                None
                if trial.disposition is arch150.TrialDisposition.SHORTLISTED
                else trial.disposition
            )
            expected_evaluation_id = uuid5(
                arch150._G1_RESULT_NAMESPACE,
                arch150._canonical_json(
                    arch150._evaluation_identity_material(
                        self.manifest.manifest_id,
                        slot.slot_id,
                        dataset_id,
                        slot.source_symbol,
                        slot.bar_resolution,
                        trial.replay_id,
                        fixed,
                        trial.diagnostic_code,
                    )
                ).decode("utf-8"),
            )
            if expected_evaluation_id != trial.evaluation_id or (
                trial.replay_id is not None
                and trial.input_digest
                != dataset.bars.by_symbol[slot.source_symbol].input_digest
            ):
                raise Arch150G1ValidationError("DISCOVERY_EVALUATION_BINDING_MISMATCH")
            ledger = ledger._append_result(
                slot,
                dataset_id,
                trial.evaluation_id,
                trial.replay_id,
                trial.disposition,
                trial.diagnostic_code,
            )
        finalized = arch150.finalize_discovery_population(dataset, ledger)
        candidates = arch150.freeze_candidate_population(finalized, ledger)
        if (
            ledger.ledger_id != self.accepted.ledger_id
            or finalized.freeze_id != self.accepted.discovery_freeze_id
            or candidates.freeze_id != self.accepted.candidate_freeze_id
            or candidates.candidate_slot_ids
            != tuple(slot.slot_id for slot in self.slots)
        ):
            raise Arch150G1ValidationError("DISCOVERY_FREEZE_BINDING_MISMATCH")
        return candidates


def _uuid(value: object) -> UUID:
    try:
        if isinstance(value, str):
            parsed = UUID(value)
            if str(parsed) == value:
                return parsed
    except ValueError:
        pass
    raise Arch150G1ValidationError("DISCOVERY_UUID_INVALID")


def _read_pinned_discovery_report() -> bytes:
    discovery._require_real_directory(ACCEPTED_DISCOVERY_ROOT, "DISCOVERY_ROOT_INVALID")
    path = ACCEPTED_DISCOVERY_ROOT / "discovery.json"
    # Bound the read with the reviewed length. The canonical report ID is the
    # authority, and the length is only a file-read guard.
    return discovery._read_regular_file(path, expected_length=26_839)


def _authenticate_discovery_report(
    body: bytes, accepted: _AcceptedDiscovery
) -> _DiscoveryAuthority:
    material = discovery._parse_canonical_object(body)
    report_id = _uuid(material.pop("report_id", None))
    if report_id != accepted.report_id or report_id != uuid5(
        discovery._REPORT_NAMESPACE, canonical_json_bytes(material).decode("utf-8")
    ):
        raise Arch150G1ValidationError("DISCOVERY_REPORT_IDENTITY_MISMATCH")
    manifest = arch150.freeze_g1_population()
    dataset_id, dataset_sha = discovery._SEMANTIC_PINS["dataset.json"]
    custody_id, custody_sha = discovery._SEMANTIC_PINS["custody-evidence.json"]
    expected = {
        "schema": discovery.G1_DISCOVERY_REPORT_SCHEMA,
        "source": asdict(accepted.source),
        "accepted_input_root": str(discovery.ACCEPTED_INPUT_ROOT),
        "accepted_sparse_custody": {
            "dataset_id": dataset_id,
            "dataset_semantic_sha256": dataset_sha,
            "custody_id": custody_id,
            "custody_semantic_sha256": custody_sha,
        },
        "discovery_window": {
            "start_inclusive": arch150.DISCOVERY_START.isoformat(),
            "end_exclusive": arch150.DISCOVERY_END.isoformat(),
        },
        "manifest_schema": arch150.G1_POPULATION_SCHEMA,
        "manifest_id": discovery.G1_MANIFEST_ID,
        "slot_ids": [str(slot.slot_id) for slot in manifest.slots],
        "qualification_cost_case": arch150.CostCase.STRESS.value,
        "starting_equity": "1",
        "trial_count": 24,
        "ledger_id": str(accepted.ledger_id),
        "discovery_result_freeze_id": str(accepted.discovery_freeze_id),
        "candidate_freeze_id": str(accepted.candidate_freeze_id),
        "terminal_disposition": "CANDIDATES_FROZEN",
        "effect_counters": {
            "validation_strategy_replay_count": 0,
            "2024_plus_data_accessed": False,
            "provider_requests": 0,
            "credential_reads": 0,
            "robinhood_calls": 0,
            "broker_order_effects": 0,
        },
    }
    if any(
        canonical_json_bytes(material.get(key)) != canonical_json_bytes(value)
        for key, value in expected.items()
    ):
        raise Arch150G1ValidationError("DISCOVERY_REPORT_CONTRACT_MISMATCH")
    rows = material.get("trials")
    if type(rows) is not list or len(rows) != len(manifest.slots) or len(rows) != 24:
        raise Arch150G1ValidationError("DISCOVERY_TRIAL_POPULATION_MISMATCH")
    trials = []
    slots = []
    counts = {disposition.value: 0 for disposition in arch150.TrialDisposition}
    for slot, row in zip(manifest.slots, rows, strict=True):
        trial = _read_discovery_trial(slot, row)
        trials.append(trial)
        counts[trial.disposition.value] += 1
        if trial.disposition is arch150.TrialDisposition.SHORTLISTED:
            slots.append(slot)
    if (
        not slots
        or canonical_json_bytes(material.get("terminal_disposition_counts"))
        != canonical_json_bytes(counts)
        or canonical_json_bytes(material.get("candidate_slots"))
        != canonical_json_bytes(
            [{"ordinal": slot.ordinal, "slot_id": str(slot.slot_id)} for slot in slots]
        )
    ):
        raise Arch150G1ValidationError("DISCOVERY_CANDIDATE_POPULATION_MISMATCH")
    return _DiscoveryAuthority(accepted, manifest, tuple(trials), tuple(slots))


def _read_discovery_trial(
    slot: arch150.FrozenTrialSlot, row: object
) -> _DiscoveryTrial:
    if (
        type(row) is not dict
        or any(
            canonical_json_bytes(row.get(key)) != canonical_json_bytes(value)
            for key, value in _slot_fields(slot).items()
        )
        or row.get("family") != slot.family.value
    ):
        raise Arch150G1ValidationError("DISCOVERY_TRIAL_SLOT_MISMATCH")
    try:
        disposition = arch150.TrialDisposition(row["disposition"])
    except (KeyError, ValueError):
        raise Arch150G1ValidationError("DISCOVERY_TRIAL_DISPOSITION_INVALID") from None
    count = row.get("trade_count")
    replay_id = row.get("replay_id")
    input_digest = row.get("input_digest")
    diagnostic = row.get("diagnostic_code")
    if disposition in (
        arch150.TrialDisposition.SHORTLISTED,
        arch150.TrialDisposition.ZERO_TRADE,
    ):
        if (
            type(count) is not int
            or count < 0
            or (count > 0) != (disposition is arch150.TrialDisposition.SHORTLISTED)
            or diagnostic is not None
            or not discovery._is_sha256(input_digest)
            or not discovery._is_sha256(row.get("equity_digest"))
        ):
            raise Arch150G1ValidationError("DISCOVERY_TRIAL_REPLAY_MISMATCH")
        replay_id = _uuid(replay_id)
        expected_replay_id = uuid5(
            arch150._REPLAY_NAMESPACE,
            arch150._canonical_json(
                {
                    "program_id": str(slot.program_id),
                    "input_digest": input_digest,
                    "cost_case": arch150.CostCase.STRESS.value,
                    "equity_digest": row["equity_digest"],
                }
            ).decode("utf-8"),
        )
        if replay_id != expected_replay_id:
            raise Arch150G1ValidationError("DISCOVERY_TRIAL_REPLAY_MISMATCH")
    elif (
        disposition is not arch150.TrialDisposition.FAILED
        or not isinstance(diagnostic, str)
        or not diagnostic.startswith("REPLAY_")
        or any(
            value is not None
            for value in (count, replay_id, input_digest, row.get("equity_digest"))
        )
    ):
        # The canonical manifest has only valid, distinct typed proposals.
        raise Arch150G1ValidationError("DISCOVERY_TRIAL_DISPOSITION_INVALID")
    return _DiscoveryTrial(
        _uuid(row.get("evaluation_id")),
        replay_id,
        input_digest,
        disposition,
        diagnostic,
    )


def _slot_fields(slot: arch150.FrozenTrialSlot) -> dict[str, object]:
    return {
        "ordinal": slot.ordinal,
        "slot_id": str(slot.slot_id),
        "program_id": str(slot.program_id),
        "semantic_fingerprint": slot.semantic_fingerprint,
        "source_symbol": slot.source_symbol,
        "bar_resolution": slot.bar_resolution.name,
    }


def _replay_validation_slot(
    dataset: arch150.ResearchDataset, slot: arch150.FrozenTrialSlot
) -> arch150.ReplayResult:
    if (
        type(dataset) is not arch150.ResearchDataset
        or dataset._authority_seal is not arch150._DATASET_SEAL
        or dataset.stage is not arch150.ResearchStage.VALIDATION
        or (dataset.start, dataset.end_exclusive)
        != (arch150.VALIDATION_START, arch150.VALIDATION_END)
        or dataset._sparse_custody_authority
        is not arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY
    ):
        raise Arch150G1ValidationError("VALIDATION_CUSTODY_REQUIRED")
    freeze = dataset.candidate_freeze
    if freeze is None or not arch150._candidate_freeze_is_valid(freeze):
        raise Arch150G1ValidationError("VALIDATION_CANDIDATE_FREEZE_REQUIRED")
    manifest = arch150.freeze_g1_population()
    if (
        freeze.population_manifest_id != manifest.manifest_id
        or type(slot) is not arch150.FrozenTrialSlot
        or not 1 <= slot.ordinal <= len(manifest.slots)
        or slot != manifest.slots[slot.ordinal - 1]
        or slot.slot_id not in freeze.candidate_slot_ids
    ):
        raise Arch150G1ValidationError("VALIDATION_SLOT_NOT_AUTHORIZED")
    # Replay the source-owned program and never use a caller-supplied program.
    canonical = manifest.slots[slot.ordinal - 1]
    if canonical._program is None:
        raise Arch150G1ValidationError("VALIDATION_PROGRAM_BINDING_REQUIRED")
    bars = dataset.bars.by_symbol[canonical.source_symbol]
    return arch150._replay_validated(
        canonical._program,
        bars.bars,
        bars.symbol,
        bars.input_digest,
        canonical.bar_resolution,
        cost_case=arch150.CostCase.STRESS,
        initial_equity=Decimal("1"),
    )


def _relative_return(before: Decimal, after: Decimal) -> Decimal:
    # A depleted account has no subsequent exposure; keep its later returns flat.
    return (after - before) / before if before > 0 else Decimal("0")


def _validation_metrics(
    replay: arch150.ReplayResult, frequency: arch150.FrequencyDiagnostics
) -> arch150.ValidationRankingMetrics:
    sessions = tuple(
        day
        for day in arch150._SESSION_AUTHORITY.published.sessions
        if arch150.VALIDATION_START <= day < arch150.VALIDATION_END
    )
    if replay.cost_case is not arch150.CostCase.STRESS or (
        frequency.cost_case is not arch150.CostCase.STRESS
        or frequency.regular_sessions != len(sessions)
    ):
        raise Arch150G1ValidationError("VALIDATION_STRESS_REQUIRED")
    closes = {trade.session: trade.equity_after for trade in replay.trades}
    with localcontext(arch150._DECIMAL_CONTEXT):
        equity = replay.initial_equity
        peak = equity
        drawdown = Decimal("0")
        daily = []
        equity_sum = Decimal("0")
        months: dict[tuple[int, int], tuple[Decimal, Decimal]] = {}
        years: dict[int, tuple[Decimal, Decimal]] = {}
        for day in sessions:
            close = closes.get(day, equity)
            month = (day.year, day.month)
            months[month] = (months.get(month, (equity, equity))[0], close)
            years[day.year] = (years.get(day.year, (equity, equity))[0], close)
            daily.append(_relative_return(equity, close))
            equity = close
            equity_sum += close
            peak = max(peak, close)
            drawdown = max(drawdown, (peak - close) / peak)
        count = Decimal(len(daily))
        average = sum(daily, Decimal("0")) / count
        variance = sum((value - average) ** 2 for value in daily) / (count - 1)
        sharpe = (
            average * Decimal(252).sqrt() / variance.sqrt()
            if variance
            else Decimal("0")
        )
        gains = sum(
            (trade.net_pnl for trade in replay.trades if trade.net_pnl > 0),
            Decimal("0"),
        )
        losses = sum(
            (-trade.net_pnl for trade in replay.trades if trade.net_pnl < 0),
            Decimal("0"),
        )
        factor = gains / losses if losses else Decimal("Infinity" if gains else "0")
        expectancy = (
            median(trade.net_pnl / trade.equity_before for trade in replay.trades)
            if replay.trades
            else Decimal("0")
        )
        notional = sum(
            (
                fill.execution_price * fill.quantity
                for trade in replay.trades
                for fill in (trade.entry, trade.exit)
            ),
            Decimal("0"),
        )
        turnover = (
            notional / (equity_sum / count)
            if equity_sum > 0
            else Decimal("Infinity" if notional else "0")
        )
        return arch150.ValidationRankingMetrics(
            net_return=_relative_return(replay.initial_equity, replay.final_equity),
            sharpe=sharpe,
            maximum_drawdown=drawdown,
            profit_factor=factor,
            median_trade_expectancy=expectancy,
            positive_month_breadth=Decimal(
                sum(_relative_return(*endpoints) > 0 for endpoints in months.values())
            )
            / Decimal(len(months)),
            active_session_fraction=frequency.active_session_fraction,
            turnover=turnover,
            worst_calendar_year_return=min(
                _relative_return(*endpoints) for endpoints in years.values()
            ),
        )


def _qualification_failures(
    metrics: arch150.ValidationRankingMetrics, frequency: arch150.FrequencyDiagnostics
) -> tuple[str, ...]:
    if (
        metrics.cost_case is not arch150.CostCase.STRESS
        or frequency.cost_case is not arch150.CostCase.STRESS
    ):
        return ("STRESS_REQUIRED",)
    failures = []
    if metrics.net_return <= 0:
        failures.append("NONPOSITIVE_STRESS_RETURN")
    if metrics.profit_factor <= 1:
        failures.append("STRESS_PROFIT_FACTOR_NOT_ABOVE_ONE")
    if not arch150.passes_frequency_gate(
        frequency, arch150.VALIDATION_FREQUENCY_POLICY
    ):
        failures.append("VALIDATION_FREQUENCY_GATE_FAILED")
    return tuple(failures)


def _decimal_fields(
    value: arch150.FrequencyDiagnostics | arch150.ValidationRankingMetrics,
) -> dict[str, object]:
    result = {}
    for field in fields(value):
        item = getattr(value, field.name)
        if isinstance(item, Decimal):
            item = (
                "Infinity"
                if item == Decimal("Infinity")
                else discovery._decimal_text(item)
            )
        result[field.name] = item
    return result


@dataclass(frozen=True, slots=True)
class ValidationObservationResult:
    output_directory: Path
    report_id: UUID
    report_sha256: str
    report_byte_length: int
    terminal_disposition: str
    validation_freeze_id: UUID


def _validate_output_directory(path: Path) -> Path:
    output = discovery._validate_production_output_directory(path)
    if discovery._is_within(output, ACCEPTED_DISCOVERY_ROOT) or discovery._is_within(
        ACCEPTED_DISCOVERY_ROOT, output
    ):
        raise Arch150G1ValidationError("OUTPUT_OVERLAPS_DISCOVERY_EVIDENCE")
    return output


def run_arch150_g1_validation(output_directory: Path) -> ValidationObservationResult:
    """Use only the reviewed report and D1R custody at their accepted roots."""
    return _run_one_shot(
        output_directory,
        output_validator=_validate_output_directory,
        source_reader=discovery._read_source_identity,
        report_reader=_read_pinned_discovery_report,
        input_reader=lambda: discovery._read_pinned_input(
            discovery.ACCEPTED_INPUT_ROOT
        ),
        accepted=_ACCEPTED_DISCOVERY,
        progress=lambda line: print(line, flush=True),
    )


def _run_one_shot(
    output_directory: Path,
    *,
    output_validator: Callable[[Path], Path],
    source_reader: Callable[[], discovery.SourceIdentity],
    report_reader: Callable[[], bytes],
    input_reader: Callable[[], discovery.InputSnapshot],
    accepted: _AcceptedDiscovery,
    progress: Callable[[str], None],
) -> ValidationObservationResult:
    output = output_validator(output_directory)
    source = source_reader()
    if source.branch != discovery.FEATURE_BRANCH:
        raise Arch150G1ValidationError("SOURCE_BRANCH_MISMATCH")
    discovery._create_attempt_directory(
        output,
        {
            "schema": "arch150-g1-validation-attempt/v1",
            "state": "G1_VALIDATION_ATTEMPT_STARTED",
            "source": asdict(source),
            "accepted_discovery_report_id": str(accepted.report_id),
            "automatic_retry": "FORBIDDEN",
        },
    )
    authority = _authenticate_discovery_report(report_reader(), accepted)
    progress("ARCH150_VALIDATION_STAGE=DISCOVERY_AUTHORITY_ACCEPTED")
    snapshot = input_reader()
    dataset = arch150._open_sparse_validation(snapshot.bars, authority.bind_candidates)
    progress("ARCH150_VALIDATION_STAGE=SPARSE_VALIDATION_OPENED")

    records = []
    evaluations = {}
    qualified = []
    for index, slot in enumerate(authority.slots, 1):
        position = f"{index}/{len(authority.slots)}"
        progress(f"ARCH150_VALIDATION_SLOT_START={position}")
        replay = _replay_validation_slot(dataset, slot)
        frequency = arch150.compute_validation_frequency_diagnostics(replay.trades)
        metrics = _validation_metrics(replay, frequency)
        rejected = _qualification_failures(metrics, frequency)
        if not rejected:
            qualified.append(_slot_fields(slot))
        record = arch150.ValidationRankingRecord(
            slot.slot_id,
            slot.program_id,
            slot.semantic_fingerprint,
            slot.source_symbol,
            slot.bar_resolution,
            metrics,
        )
        records.append(record)
        evaluations[slot.slot_id] = {
            **_slot_fields(slot),
            "replay_id": str(replay.replay_id),
            "input_digest": replay.input_digest,
            "equity_digest": replay.equity_digest,
            "metrics": _decimal_fields(metrics),
            "frequency": _decimal_fields(frequency),
            "qualification_failures": rejected,
        }
        progress(f"ARCH150_VALIDATION_SLOT_COMPLETE={position}")

    disposition = (
        "VALIDATION_CANDIDATES_FROZEN_PENDING_SELECTION_BIAS"
        if qualified
        else "NO_HOLDOUT_CANDIDATES"
    )
    freeze_material = {
        "schema": "arch150-g1-validation-freeze/v1",
        "discovery_report_id": str(accepted.report_id),
        "discovery_candidate_freeze_id": str(accepted.candidate_freeze_id),
        "validation_input_digest": dataset.bars.input_digest,
        "qualification_cost_case": arch150.CostCase.STRESS.value,
        "evaluated_slots": list(evaluations.values()),
        "qualified_slots": qualified,
        "terminal_disposition": disposition,
        "holdout_authorized": False,
    }
    freeze_id = uuid5(
        _FREEZE_NAMESPACE, canonical_json_bytes(freeze_material).decode("utf-8")
    )
    report = {
        "schema": VALIDATION_REPORT_SCHEMA,
        "source": asdict(source),
        "manifest_id": str(authority.manifest.manifest_id),
        "validation_window": [
            dataset.start.isoformat(),
            dataset.end_exclusive.isoformat(),
        ],
        "validation_freeze_id": str(freeze_id),
        "validation_freeze": freeze_material,
        "ranking_slot_ids": [
            str(record.slot_id) for record in arch150.rank_validation_records(records)
        ],
        "effect_counters": {
            "discovery_strategy_replay_count": 0,
            "validation_strategy_replay_count": len(records),
            "2024_plus_data_accessed": False,
            "provider_requests": 0,
            "credential_reads": 0,
            "robinhood_calls": 0,
            "broker_order_effects": 0,
        },
    }
    report_id = uuid5(_REPORT_NAMESPACE, canonical_json_bytes(report).decode("utf-8"))
    body = canonical_json_bytes({"report_id": str(report_id), **report})
    discovery._write_once(output / "validation.json", body)
    return ValidationObservationResult(
        output,
        report_id,
        hashlib.sha256(body).hexdigest(),
        len(body),
        disposition,
        freeze_id,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_arch150_g1_validation(args.output_directory)
    except discovery.Arch150G1DiscoveryError as exc:
        print(f"ERROR={exc.code}")
        return 2
    except (Arch150G1ValidationError, arch150.Arch150Error) as exc:
        print(f"ERROR={exc}")
        return 2
    print(f"REPORT_ID={result.report_id}")
    print(f"REPORT_SHA256={result.report_sha256}")
    print(f"REPORT_BYTES={result.report_byte_length}")
    print(f"VALIDATION_FREEZE_ID={result.validation_freeze_id}")
    print(f"TERMINAL_DISPOSITION={result.terminal_disposition}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
