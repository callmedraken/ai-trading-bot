"""One-shot offline observer for the frozen Architecture 150 G1 population."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Context, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Final
from uuid import UUID, uuid5

from trading_bot.experiments import arch150_d1_requalify as d1r
from trading_bot.experiments import arch150_intraday_ai as arch150
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

FEATURE_BRANCH: Final = "feature/research-arch150-intraday-ai-current"
ACCEPTED_INPUT_ROOT: Final = Path(
    r"F:\AI\temp\arch150-d1r-offline-requalification-a46c4ad1-4287-4e51-8741-0316f784f1de"
)
APPROVED_OUTPUT_ROOT: Final = Path(r"F:\AI\temp")
G1_MANIFEST_ID: Final = "7e179cbc-18cf-59ce-9116-899cc876ece0"
G1_DISCOVERY_REPORT_SCHEMA: Final = "arch150-g1-discovery-observation/v1"
G1_DISCOVERY_ATTEMPT_SCHEMA: Final = "arch150-g1-discovery-attempt/v1"
_REPORT_NAMESPACE: Final = UUID("2b224a19-cc1c-5672-8e68-31636e13b942")
_DECIMAL_CONTEXT: Final = Context(prec=60)
_CSV_HEADER: Final = (
    "timestamp",
    "symbol",
    "resolution",
    "open",
    "high",
    "low",
    "close",
    "volume",
)
_ARTIFACT_LENGTHS: Final = {
    "normalized/SPY.csv": 55_599_367,
    "normalized/QQQ.csv": 55_214_275,
    "dataset.json": 871_998,
    "custody-evidence.json": 310_526,
    "evidence.json": 1_476,
}
_SEMANTIC_SCHEMAS: Final = {
    "dataset.json": (d1r.DATASET_SCHEMA, d1r._DATASET_NAMESPACE),
    "custody-evidence.json": (d1r.CUSTODY_SCHEMA, d1r._CUSTODY_NAMESPACE),
    "evidence.json": (d1r.EVIDENCE_SCHEMA, d1r._EVIDENCE_NAMESPACE),
}
_SEMANTIC_PINS: Final = {
    "dataset.json": (
        str(arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.dataset_id),
        arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.dataset_semantic_sha256,
    ),
    "custody-evidence.json": (
        str(arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.custody_id),
        arch150._ACCEPTED_SPARSE_CUSTODY_AUTHORITY.custody_semantic_sha256,
    ),
    "evidence.json": (
        "c31bb29d-3d53-5e2f-a01f-55a42ec96295",
        "e58a6e5d95c44b33eb34311f705e6cc26982120689f98ddb207768dc304b4ecd",
    ),
}
_REPARSE_POINT: Final = 0x400


class Arch150G1DiscoveryError(ValueError):
    """Stable fail-closed classification for the one-shot observation."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    branch: str
    head: str
    tree: str


@dataclass(frozen=True, slots=True)
class ArtifactCommitment:
    name: str
    byte_length: int
    sha256: str


@dataclass(frozen=True, slots=True)
class InputSnapshot:
    bars: tuple[arch150.IntradayBar, ...]
    artifacts: tuple[ArtifactCommitment, ...]


@dataclass(frozen=True, slots=True)
class DiscoveryObservationResult:
    output_directory: Path
    report_id: str
    report_sha256: str
    report_byte_length: int
    terminal_disposition: str
    ledger_id: str
    discovery_result_freeze_id: str
    candidate_freeze_id: str | None


def run_arch150_g1_discovery(
    output_directory: Path,
) -> DiscoveryObservationResult:
    """Run the fixed accepted-input/canonical-G1 observation exactly once."""

    if not isinstance(output_directory, Path):
        raise Arch150G1DiscoveryError("OUTPUT_DIRECTORY_MUST_BE_PATH")
    return _run_one_shot(
        output_directory,
        input_root=ACCEPTED_INPUT_ROOT,
        output_validator=_validate_production_output_directory,
        input_reader=_read_pinned_input,
        source_reader=_read_source_identity,
        dataset_opener=arch150.open_sparse_discovery_dataset,
        evaluator=arch150.evaluate_frozen_trial,
        progress=lambda line: print(line, flush=True),
    )


def _run_one_shot(
    output_directory: Path,
    *,
    input_root: Path,
    output_validator: Callable[[Path], Path],
    input_reader: Callable[[Path], InputSnapshot],
    source_reader: Callable[[], SourceIdentity],
    dataset_opener: Callable[
        [tuple[arch150.IntradayBar, ...]], arch150.ResearchDataset
    ],
    evaluator: Callable[..., arch150.G1TrialEvaluation],
    progress: Callable[[str], None] | None = None,
) -> DiscoveryObservationResult:
    output_root = output_validator(output_directory)
    source = source_reader()
    if source.branch != FEATURE_BRANCH:
        raise Arch150G1DiscoveryError("SOURCE_BRANCH_MISMATCH")

    manifest = arch150.freeze_g1_population()
    if (
        str(manifest.manifest_id) != G1_MANIFEST_ID
        or len(manifest.slots) != 24
        or tuple(slot.ordinal for slot in manifest.slots) != tuple(range(1, 25))
        or any(
            slot.bar_resolution is not arch150.BarResolution.ONE_MINUTE
            for slot in manifest.slots
        )
    ):
        raise Arch150G1DiscoveryError("CANONICAL_G1_MANIFEST_MISMATCH")

    _create_attempt_directory(
        output_root,
        {
            "schema": G1_DISCOVERY_ATTEMPT_SCHEMA,
            "state": "G1_DISCOVERY_ATTEMPT_STARTED",
            "source": _source_material(source),
            "accepted_input_root": str(input_root),
            "expected_artifacts": [
                {"name": name, "byte_length": length}
                for name, length in _ARTIFACT_LENGTHS.items()
            ],
            "dataset_id": _SEMANTIC_PINS["dataset.json"][0],
            "dataset_semantic_sha256": _SEMANTIC_PINS["dataset.json"][1],
            "custody_id": _SEMANTIC_PINS["custody-evidence.json"][0],
            "custody_semantic_sha256": _SEMANTIC_PINS["custody-evidence.json"][1],
            "manifest_id": str(manifest.manifest_id),
            "slot_count": len(manifest.slots),
        },
    )

    try:
        snapshot = input_reader(input_root)
    except Arch150G1DiscoveryError:
        raise
    except Exception:
        raise Arch150G1DiscoveryError("INPUT_VALIDATION_FAILED") from None
    if progress is not None:
        progress("G1_DISCOVERY_STAGE=INPUT_ACCEPTED")
    try:
        discovery_dataset = dataset_opener(snapshot.bars)
    except Exception:
        raise Arch150G1DiscoveryError("SPARSE_CUSTODY_VALIDATION_FAILED") from None
    if (
        discovery_dataset.stage is not arch150.ResearchStage.DISCOVERY
        or discovery_dataset.start != arch150.DISCOVERY_START
        or discovery_dataset.end_exclusive != arch150.DISCOVERY_END
        or any(
            bar.session_date >= arch150.DISCOVERY_END
            for symbol in arch150.INITIAL_UNIVERSE
            for bar in discovery_dataset.bars.by_symbol[symbol].bars
        )
    ):
        raise Arch150G1DiscoveryError("DISCOVERY_DATASET_WINDOW_MISMATCH")
    if progress is not None:
        progress("G1_DISCOVERY_STAGE=SPARSE_DATASET_OPENED")

    ledger = arch150.TrialLedger(manifest)
    evaluations: list[arch150.G1TrialEvaluation] = []
    for slot in manifest.slots:
        if ledger.next_slot is None or ledger.next_slot.slot_id != slot.slot_id:
            raise Arch150G1DiscoveryError("G1_SLOT_ORDER_MISMATCH")
        slot_progress = f"{slot.ordinal}/{len(manifest.slots)}"
        if progress is not None:
            progress(f"G1_SLOT_START={slot_progress}")
        try:
            evaluation = evaluator(
                ledger,
                slot,
                discovery_dataset,
                initial_equity=Decimal("1"),
            )
        except Exception:
            raise Arch150G1DiscoveryError("G1_SLOT_EVALUATION_FAILED") from None
        if type(evaluation) is not arch150.G1TrialEvaluation:
            raise Arch150G1DiscoveryError("G1_EVALUATION_INVALID")
        evaluations.append(evaluation)
        try:
            ledger = ledger.consume(evaluation)
        except Exception:
            raise Arch150G1DiscoveryError("G1_SLOT_CONSUMPTION_FAILED") from None
        if progress is not None:
            disposition = ledger.records[-1].disposition.value
            progress(f"G1_SLOT_COMPLETE={slot_progress} DISPOSITION={disposition}")
    if not ledger.is_complete or ledger.consumed_trial_count != 24:
        raise Arch150G1DiscoveryError("G1_LEDGER_INCOMPLETE")

    try:
        discovery_freeze = arch150.finalize_discovery_population(
            discovery_dataset,
            ledger,
        )
        candidate_freeze = arch150.freeze_candidate_population(
            discovery_freeze,
            ledger,
        )
    except arch150.NoValidationCandidatesError:
        candidate_freeze = None
    except Exception:
        raise Arch150G1DiscoveryError("DISCOVERY_FINALIZATION_FAILED") from None

    report_material = _report_material(
        source=source,
        input_root=input_root,
        snapshot=snapshot,
        manifest=manifest,
        ledger=ledger,
        evaluations=tuple(evaluations),
        discovery_freeze=discovery_freeze,
        candidate_freeze=candidate_freeze,
    )
    report_id = str(
        uuid5(_REPORT_NAMESPACE, canonical_json_bytes(report_material).decode("utf-8"))
    )
    report = {"report_id": report_id, **report_material}
    report_bytes = canonical_json_bytes(report)
    report_hash = hashlib.sha256(report_bytes).hexdigest()
    _write_once(output_root / "discovery.json", report_bytes)

    return DiscoveryObservationResult(
        output_root,
        report_id,
        report_hash,
        len(report_bytes),
        str(report["terminal_disposition"]),
        str(ledger.ledger_id),
        str(discovery_freeze.freeze_id),
        str(candidate_freeze.freeze_id) if candidate_freeze is not None else None,
    )


def _read_pinned_input(root: Path) -> InputSnapshot:
    if not _same_path(root, ACCEPTED_INPUT_ROOT):
        raise Arch150G1DiscoveryError("ACCEPTED_INPUT_ROOT_MISMATCH")
    return _read_input_snapshot(root)


def _read_input_snapshot(
    root: Path,
    *,
    artifact_lengths: Mapping[str, int] = _ARTIFACT_LENGTHS,
    semantic_pins: Mapping[str, tuple[str, str]] = _SEMANTIC_PINS,
) -> InputSnapshot:
    _require_real_directory(root, "INPUT_DIRECTORY_INVALID")
    bodies: dict[str, bytes] = {}
    commitments: dict[str, ArtifactCommitment] = {}

    def read(name: str) -> bytes:
        expected_length = artifact_lengths[name]
        body = _read_regular_file(root / name, expected_length=expected_length)
        if len(body) != expected_length:
            raise Arch150G1DiscoveryError("INPUT_ARTIFACT_COMMITMENT_MISMATCH")
        commitments[name] = ArtifactCommitment(
            name, len(body), hashlib.sha256(body).hexdigest()
        )
        return body

    materials = {}
    try:
        for name, (schema, namespace) in _SEMANTIC_SCHEMAS.items():
            value = _parse_canonical_object(read(name))
            material = value.get("material")
            expected = semantic_pins[name]
            if (
                set(value) != {"schema", "identity", "sha256", "material"}
                or value.get("schema") != schema
                or (value.get("identity"), value.get("sha256")) != expected
                or type(material) is not dict
                or d1r._versioned_identity(schema, material, namespace) != expected
            ):
                raise Arch150G1DiscoveryError("INPUT_SEMANTIC_IDENTITY_MISMATCH")
            materials[name] = material

        normalized = materials["dataset.json"].get("normalized_sparse_regular_bars")
        if type(normalized) is not dict or set(normalized) != set(
            arch150.INITIAL_UNIVERSE
        ):
            raise Arch150G1DiscoveryError("INPUT_NORMALIZED_COMMITMENTS_INVALID")
        for symbol in arch150.INITIAL_UNIVERSE:
            entry = normalized[symbol]
            if type(entry) is not dict or not _is_sha256(entry.get("sha256")):
                raise Arch150G1DiscoveryError("INPUT_NORMALIZED_COMMITMENTS_INVALID")
            name = f"normalized/{symbol}.csv"
            bodies[name] = read(name)
            if commitments[name].sha256 != entry["sha256"]:
                raise Arch150G1DiscoveryError("INPUT_ARTIFACT_COMMITMENT_MISMATCH")
    except Arch150G1DiscoveryError:
        raise
    except OSError:
        raise Arch150G1DiscoveryError("INPUT_ARTIFACT_READ_FAILED") from None

    bars = tuple(
        bar
        for symbol in arch150.INITIAL_UNIVERSE
        for bar in _parse_normalized_csv(
            bodies[f"normalized/{symbol}.csv"],
            symbol,
        )
    )
    return InputSnapshot(
        tuple(bars), tuple(commitments[name] for name in artifact_lengths)
    )


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _parse_normalized_csv(
    body: bytes, expected_symbol: str
) -> tuple[arch150.IntradayBar, ...]:
    if expected_symbol not in arch150.INITIAL_UNIVERSE:
        raise Arch150G1DiscoveryError("UNEXPECTED_CSV_SYMBOL")
    try:
        text = body.decode("utf-8")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader)
        if tuple(header) != _CSV_HEADER:
            raise Arch150G1DiscoveryError("NORMALIZED_CSV_HEADER_MISMATCH")
        bars: list[arch150.IntradayBar] = []
        for row in reader:
            if len(row) != len(_CSV_HEADER):
                raise Arch150G1DiscoveryError("NORMALIZED_CSV_ROW_WIDTH_MISMATCH")
            (
                timestamp_text,
                symbol,
                resolution,
                open_text,
                high_text,
                low_text,
                close_text,
                volume_text,
            ) = row
            if symbol != expected_symbol or resolution != "1Min":
                raise Arch150G1DiscoveryError(
                    "NORMALIZED_CSV_SYMBOL_OR_RESOLUTION_MISMATCH"
                )
            timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise Arch150G1DiscoveryError("NORMALIZED_CSV_TIMESTAMP_INVALID")
            canonical_timestamp = (
                timestamp.astimezone(UTC)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            )
            if timestamp_text != canonical_timestamp:
                raise Arch150G1DiscoveryError("NORMALIZED_CSV_TIMESTAMP_INVALID")
            bar = arch150.IntradayBar(
                symbol,
                timestamp,
                Decimal(open_text),
                Decimal(high_text),
                Decimal(low_text),
                Decimal(close_text),
                _parse_canonical_volume(volume_text),
                arch150.BarResolution.ONE_MINUTE,
            )
            if not date(2016, 1, 1) <= bar.session_date < date(2024, 1, 1):
                raise Arch150G1DiscoveryError("NORMALIZED_CSV_OUTSIDE_CUSTODY_WINDOW")
            canonical_values = (
                arch150._decimal_text(bar.open),
                arch150._decimal_text(bar.high),
                arch150._decimal_text(bar.low),
                arch150._decimal_text(bar.close),
            )
            if canonical_values != (open_text, high_text, low_text, close_text):
                raise Arch150G1DiscoveryError("NORMALIZED_CSV_DECIMAL_NOT_CANONICAL")
            bars.append(bar)
    except Arch150G1DiscoveryError:
        raise
    except (
        csv.Error,
        IndexError,
        InvalidOperation,
        StopIteration,
        TypeError,
        ValueError,
        UnicodeError,
    ):
        raise Arch150G1DiscoveryError("NORMALIZED_CSV_INVALID") from None
    if not bars:
        raise Arch150G1DiscoveryError("NORMALIZED_CSV_EMPTY")
    return tuple(bars)


def _parse_canonical_volume(value: str) -> int:
    if not value or any(character not in "0123456789" for character in value):
        raise Arch150G1DiscoveryError("NORMALIZED_CSV_VOLUME_INVALID")
    parsed = int(value)
    if str(parsed) != value:
        raise Arch150G1DiscoveryError("NORMALIZED_CSV_VOLUME_NOT_CANONICAL")
    return parsed


def _report_material(
    *,
    source: SourceIdentity,
    input_root: Path,
    snapshot: InputSnapshot,
    manifest: arch150.G1PopulationManifest,
    ledger: arch150.TrialLedger,
    evaluations: tuple[arch150.G1TrialEvaluation, ...],
    discovery_freeze: arch150.DiscoveryResultFreeze,
    candidate_freeze: arch150.CandidateFreeze | None,
) -> dict[str, object]:
    summaries = []
    for record, evaluation in zip(ledger.records, evaluations, strict=True):
        replay = evaluation.replay_result
        summaries.append(
            {
                "ordinal": record.trial_ordinal,
                "slot_id": str(record.slot_id),
                "family": record.family.value,
                "source_symbol": record.source_symbol,
                "bar_resolution": record.bar_resolution.name,
                "program_id": str(record.program_id) if record.program_id else None,
                "semantic_fingerprint": record.semantic_fingerprint,
                "evaluation_id": str(record.evaluation_id),
                "disposition": record.disposition.value,
                "diagnostic_code": record.diagnostic_code,
                "replay_id": str(replay.replay_id) if replay is not None else None,
                "trade_count": len(replay.trades) if replay is not None else None,
                "initial_equity": (
                    _decimal_text(replay.initial_equity) if replay is not None else None
                ),
                "final_equity": (
                    _decimal_text(replay.final_equity) if replay is not None else None
                ),
                "net_pnl": _decimal_text(replay.net_pnl)
                if replay is not None
                else None,
                "net_return": _net_return(replay) if replay is not None else None,
                "maximum_gross_exposure": (
                    _decimal_text(replay.maximum_gross_exposure)
                    if replay is not None
                    else None
                ),
                "input_digest": replay.input_digest if replay is not None else None,
                "equity_digest": replay.equity_digest if replay is not None else None,
            }
        )

    counts = {
        disposition.value: sum(
            record.disposition is disposition for record in ledger.records
        )
        for disposition in arch150.TrialDisposition
    }
    candidate_slots: list[dict[str, int | str]] = []
    if candidate_freeze is not None:
        slots_by_id = {slot.slot_id: slot for slot in manifest.slots}
        for slot_id in candidate_freeze.candidate_slot_ids:
            slot = slots_by_id.get(slot_id)
            if slot is None:
                raise Arch150G1DiscoveryError("CANDIDATE_SLOT_NOT_IN_FROZEN_MANIFEST")
            candidate_slots.append(
                {
                    "ordinal": slot.ordinal,
                    "slot_id": str(slot.slot_id),
                }
            )
    return {
        "schema": G1_DISCOVERY_REPORT_SCHEMA,
        "source": _source_material(source),
        "accepted_input_root": str(input_root),
        "input_artifacts": [
            {
                "name": artifact.name,
                "byte_length": artifact.byte_length,
                "sha256": artifact.sha256,
            }
            for artifact in snapshot.artifacts
        ],
        "accepted_sparse_custody": {
            "dataset_id": _SEMANTIC_PINS["dataset.json"][0],
            "dataset_semantic_sha256": _SEMANTIC_PINS["dataset.json"][1],
            "custody_id": _SEMANTIC_PINS["custody-evidence.json"][0],
            "custody_semantic_sha256": _SEMANTIC_PINS["custody-evidence.json"][1],
        },
        "discovery_window": {
            "start_inclusive": arch150.DISCOVERY_START.isoformat(),
            "end_exclusive": arch150.DISCOVERY_END.isoformat(),
        },
        "manifest_schema": arch150.G1_POPULATION_SCHEMA,
        "manifest_id": str(manifest.manifest_id),
        "slot_ids": [str(slot.slot_id) for slot in manifest.slots],
        "qualification_cost_case": arch150.CostCase.STRESS.value,
        "starting_equity": "1",
        "trial_count": ledger.consumed_trial_count,
        "ledger_id": str(ledger.ledger_id),
        "discovery_result_freeze_id": str(discovery_freeze.freeze_id),
        "candidate_freeze_id": (
            str(candidate_freeze.freeze_id) if candidate_freeze is not None else None
        ),
        "candidate_slots": candidate_slots,
        "terminal_disposition": (
            "NO_VALIDATION_CANDIDATES"
            if candidate_freeze is None
            else "CANDIDATES_FROZEN"
        ),
        "terminal_disposition_counts": counts,
        "trials": summaries,
        "effect_counters": {
            "validation_strategy_replay_count": 0,
            "2024_plus_data_accessed": False,
            "provider_requests": 0,
            "credential_reads": 0,
            "robinhood_calls": 0,
            "broker_order_effects": 0,
        },
    }


def _net_return(replay: arch150.ReplayResult) -> str:
    with localcontext(_DECIMAL_CONTEXT):
        value = replay.final_equity / replay.initial_equity - Decimal("1")
    return _decimal_text(value)


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise Arch150G1DiscoveryError("NONFINITE_REPORT_DECIMAL")
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _read_source_identity() -> SourceIdentity:
    module_path = Path(__file__).resolve()
    repo_root = module_path.parents[3]
    try:
        top = _git(repo_root, "rev-parse", "--show-toplevel")
        branch = _git(repo_root, "branch", "--show-current")
        head = _git(repo_root, "rev-parse", "HEAD")
        tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
        status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    except Arch150G1DiscoveryError:
        raise
    if not _same_path(Path(top), repo_root) or branch != FEATURE_BRANCH:
        raise Arch150G1DiscoveryError("SOURCE_IDENTITY_MISMATCH")
    if status:
        raise Arch150G1DiscoveryError("SOURCE_WORKTREE_NOT_CLEAN")
    return SourceIdentity(branch, head, tree)


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        raise Arch150G1DiscoveryError("SOURCE_GIT_UNAVAILABLE") from None
    if result.returncode != 0:
        raise Arch150G1DiscoveryError("SOURCE_GIT_IDENTITY_FAILED")
    return result.stdout.strip()


def _validate_production_output_directory(path: Path) -> Path:
    if not isinstance(path, Path):
        raise Arch150G1DiscoveryError("OUTPUT_DIRECTORY_MUST_BE_PATH")
    try:
        _validate_path_text(path)
        absolute = Path(os.path.abspath(path))
        if absolute.drive.upper() != "F:" or not _is_within(
            absolute, APPROVED_OUTPUT_ROOT
        ):
            raise Arch150G1DiscoveryError("OUTPUT_MUST_BE_UNDER_F_AI_TEMP")
        parent = absolute.parent
        _require_real_directory(parent, "OUTPUT_PARENT_INVALID")
        candidate = parent.resolve(strict=True) / absolute.name
        protected_paths = (
            _repository_root(),
            Path(r"F:\AI\worktrees"),
            ACCEPTED_INPUT_ROOT,
        )
        if any(
            _is_within(candidate, protected) or _is_within(protected, candidate)
            for protected in protected_paths
        ):
            raise Arch150G1DiscoveryError("OUTPUT_OVERLAPS_PROTECTED_PATH")
        if not _same_path(candidate, absolute):
            raise Arch150G1DiscoveryError("OUTPUT_PATH_ALIAS")
        if candidate.exists() or _is_reparse_point(candidate):
            raise Arch150G1DiscoveryError("OUTPUT_ALREADY_EXISTS")
        return candidate
    except Arch150G1DiscoveryError:
        raise
    except (OSError, RuntimeError, ValueError):
        raise Arch150G1DiscoveryError("OUTPUT_PATH_INVALID") from None


def _create_attempt_directory(root: Path, marker: dict[str, object]) -> None:
    try:
        root.mkdir()
    except FileExistsError:
        raise Arch150G1DiscoveryError("OUTPUT_ALREADY_EXISTS") from None
    except OSError:
        raise Arch150G1DiscoveryError("OUTPUT_CREATE_FAILED") from None
    _require_real_directory(root, "OUTPUT_PATH_ALIAS")
    _write_once(root / "attempt.json", canonical_json_bytes(marker))


def _write_once(path: Path, body: bytes) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o600,
        )
    except FileExistsError:
        raise Arch150G1DiscoveryError("OUTPUT_ARTIFACT_COLLISION") from None
    except OSError:
        raise Arch150G1DiscoveryError("OUTPUT_ARTIFACT_CREATE_FAILED") from None
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            if stream.write(body) != len(body):
                raise Arch150G1DiscoveryError("OUTPUT_ARTIFACT_WRITE_FAILED")
            stream.flush()
            os.fsync(stream.fileno())
        stored = _read_regular_file(path)
    except Arch150G1DiscoveryError:
        raise
    except OSError:
        raise Arch150G1DiscoveryError("OUTPUT_ARTIFACT_WRITE_FAILED") from None
    if (
        len(stored) != len(body)
        or hashlib.sha256(stored).digest() != hashlib.sha256(body).digest()
    ):
        raise Arch150G1DiscoveryError("OUTPUT_READBACK_MISMATCH")


def _read_regular_file(path: Path, *, expected_length: int | None = None) -> bytes:
    if _is_reparse_point(path) or not path.is_file():
        raise Arch150G1DiscoveryError("INPUT_FILE_INVALID")
    try:
        resolved = path.resolve(strict=True)
        if not _same_path(path, resolved):
            raise Arch150G1DiscoveryError("INPUT_PATH_ALIAS")
        _require_no_reparse_chain(path.parent)
        if expected_length is not None and path.stat().st_size != expected_length:
            raise Arch150G1DiscoveryError("INPUT_ARTIFACT_COMMITMENT_MISMATCH")
        return path.read_bytes()
    except Arch150G1DiscoveryError:
        raise
    except (OSError, RuntimeError):
        raise Arch150G1DiscoveryError("INPUT_FILE_READ_FAILED") from None


def _parse_canonical_object(body: bytes) -> dict[str, object]:
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Arch150G1DiscoveryError("INPUT_JSON_INVALID") from None
    if type(value) is not dict or canonical_json_bytes(value) != body:
        raise Arch150G1DiscoveryError("INPUT_JSON_NOT_CANONICAL")
    return value


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _require_real_directory(path: Path, code: str) -> None:
    if _is_reparse_point(path) or not path.is_dir():
        raise Arch150G1DiscoveryError(code)
    try:
        if not _same_path(path, path.resolve(strict=True)):
            raise Arch150G1DiscoveryError("PATH_ALIAS")
        _require_no_reparse_chain(path)
    except Arch150G1DiscoveryError:
        raise
    except (OSError, RuntimeError):
        raise Arch150G1DiscoveryError(code) from None


def _require_no_reparse_chain(path: Path) -> None:
    for component in (path, *path.parents):
        if _is_reparse_point(component):
            raise Arch150G1DiscoveryError("PATH_ALIAS")


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise Arch150G1DiscoveryError("PATH_INSPECTION_FAILED") from None
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def _validate_path_text(path: Path) -> None:
    try:
        raw_path = os.fspath(path)
    except TypeError:
        raise Arch150G1DiscoveryError("OUTPUT_PATH_TEXT_INVALID") from None
    if type(raw_path) is not str or any(
        ord(character) < 0x20 or ord(character) == 0x7F for character in raw_path
    ):
        raise Arch150G1DiscoveryError("OUTPUT_PATH_TEXT_INVALID")
    if os.name == "nt":
        for index, character in enumerate(raw_path):
            if character in '<>"|?*':
                raise Arch150G1DiscoveryError("OUTPUT_PATH_TEXT_INVALID")
            if character == ":" and not (
                index == 1 and raw_path[0].isascii() and raw_path[0].isalpha()
            ):
                raise Arch150G1DiscoveryError("OUTPUT_PATH_TEXT_INVALID")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(parent)))
        return True
    except ValueError:
        return False


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _source_material(source: SourceIdentity) -> dict[str, str]:
    return {"branch": source.branch, "head": source.head, "tree": source.tree}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_arch150_g1_discovery(args.output_directory)
    except Arch150G1DiscoveryError as error:
        print(f"ERROR={error.code}")
        return 2
    print(f"REPORT_ID={result.report_id}")
    print(f"REPORT_SHA256={result.report_sha256}")
    print(f"REPORT_BYTE_LENGTH={result.report_byte_length}")
    print(f"TERMINAL_DISPOSITION={result.terminal_disposition}")
    print(f"LEDGER_ID={result.ledger_id}")
    print(f"DISCOVERY_RESULT_FREEZE_ID={result.discovery_result_freeze_id}")
    print(f"CANDIDATE_FREEZE_ID={result.candidate_freeze_id or 'NONE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
