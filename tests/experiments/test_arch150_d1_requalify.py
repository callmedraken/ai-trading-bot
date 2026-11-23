from __future__ import annotations

import ast
import hashlib
import inspect
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from trading_bot.experiments import arch150_d1_requalify as requal
from trading_bot.experiments import arch150_intraday_data as data
from trading_bot.experiments.arch150_intraday_ai import BarResolution, IntradayBar
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

_SOURCE_HEAD = "1" * 40
_SOURCE_TREE = "2" * 40
_ATTEMPT_ID = "c18d82fc-08a5-4d64-8fa7-a5b4e8e2ed91"
_SESSION = date(2023, 11, 24)


def _wire(symbol: str, rows: list[dict[str, object]], token: str | None) -> bytes:
    return json.dumps(
        {"bars": {symbol: rows}, "next_page_token": token},
        separators=(",", ":"),
    ).encode("utf-8")


def _row(stamp: datetime) -> dict[str, object]:
    return {
        "t": stamp.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "o": 100,
        "h": 102,
        "l": 99,
        "c": 101,
        "v": 42,
    }


def _bars_for(
    symbol: str,
    stamps: list[datetime],
) -> list[IntradayBar]:
    return [
        IntradayBar(
            symbol,
            stamp,
            data.Decimal("100"),
            data.Decimal("102"),
            data.Decimal("99"),
            data.Decimal("101"),
            42,
            BarResolution.ONE_MINUTE,
        )
        for stamp in stamps
    ]


def _make_fixture(
    tmp_path: Path,
    *,
    fault: str | None = None,
) -> tuple[
    Path,
    Path,
    requal._ExpectedAttempt,
    object,
    list[datetime],
    dict[str, list[IntradayBar]],
]:
    authority = data.published_session_authority()
    slots = list(
        data.expected_regular_minute_slots(
            _SESSION, _SESSION + timedelta(days=1), authority
        )
    )
    assert len(slots) == 210
    missing = {"SPY": {4, 5}, "QQQ": {5, 7}}
    bars_by_symbol: dict[str, list[IntradayBar]] = {}
    pages_by_symbol: dict[str, list[bytes]] = {}
    for symbol in data.INITIAL_UNIVERSE:
        stamps = [
            stamp for index, stamp in enumerate(slots) if index not in missing[symbol]
        ]
        stamps.append(datetime(2023, 11, 24, 18, 0, tzinfo=UTC))
        if fault == "off_grid" and symbol == "SPY":
            stamps[10] += timedelta(seconds=30)
        if fault == "future" and symbol == "SPY":
            stamps[-1] = datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
        bars_by_symbol[symbol] = _bars_for(symbol, stamps)
        provider_rows = [_row(stamp) for stamp in stamps]
        if fault == "malformed" and symbol == "SPY":
            provider_rows[0].pop("v")
        if fault == "wrong_symbol" and symbol == "SPY":
            pages_by_symbol[symbol] = [
                _wire("QQQ", provider_rows[:100], "SPY-cursor-2"),
                _wire("SPY", provider_rows[100:], None),
            ]
            continue
        if fault == "duplicate" and symbol == "SPY":
            split = len(provider_rows) // 2
            first = provider_rows[:split]
            second = [first[-1], *provider_rows[split:]]
            pages_by_symbol[symbol] = [
                _wire(symbol, first, "SPY-cursor-2"),
                _wire(symbol, second, None),
            ]
            continue
        if fault == "reorder" and symbol == "SPY":
            split = len(provider_rows) // 2
            pages_by_symbol[symbol] = [
                _wire(symbol, provider_rows[split:], "SPY-cursor-2"),
                _wire(symbol, provider_rows[:split], None),
            ]
            continue
        if fault == "repeated_token" and symbol == "SPY":
            split1, split2 = len(provider_rows) // 3, 2 * len(provider_rows) // 3
            pages_by_symbol[symbol] = [
                _wire(symbol, provider_rows[:split1], "SPY-cursor-2"),
                _wire(symbol, provider_rows[split1:split2], "SPY-cursor-2"),
                _wire(symbol, provider_rows[split2:], None),
            ]
            continue
        split = len(provider_rows) // 2
        pages_by_symbol[symbol] = [
            _wire(symbol, provider_rows[:split], f"{symbol}-cursor-2"),
            _wire(symbol, provider_rows[split:], None),
        ]

    attempt_root = tmp_path / f"arch150-d1-{_ATTEMPT_ID}"
    raw_root = attempt_root / "raw"
    raw_root.mkdir(parents=True)
    commitments: list[dict[str, object]] = []
    request_descriptors: list[dict[str, object]] = []
    page_hashes: dict[str, list[str]] = {symbol: [] for symbol in data.INITIAL_UNIVERSE}
    diagnostic_facts: dict[str, tuple[tuple[str, object], ...]] = {}
    for symbol in data.INITIAL_UNIVERSE:
        symbol_root = raw_root / symbol
        symbol_root.mkdir()
        token: str | None = None
        for ordinal, payload in enumerate(pages_by_symbol[symbol], start=1):
            request = data.Arch150HistoricalRequest(symbol, token)
            page_document = json.loads(payload)
            next_token = page_document["next_page_token"]
            page_sha = hashlib.sha256(payload).hexdigest()
            next_sha = (
                hashlib.sha256(next_token.encode()).hexdigest() if next_token else None
            )
            terminal = "CONTINUE" if next_token else "NULL_TOKEN_EXHAUSTED"
            if fault == "token_mismatch" and symbol == "SPY" and ordinal == 1:
                next_sha = hashlib.sha256(b"wrong-token").hexdigest()
            commitment = data.RawPageCommitment(
                ordinal,
                symbol,
                request.digest,
                canonical_json_bytes(request.descriptor).decode(),
                request.descriptor["page_token_sha256"],
                page_sha,
                len(payload),
                next_sha,
                terminal,
            )
            commitments.append(commitment.to_dict())
            request_descriptors.append(request.descriptor)
            page_hashes[symbol].append(page_sha)
            (symbol_root / f"{ordinal:04d}.bin").write_bytes(payload)
            token = next_token

        regular = [
            stamp
            for stamp in (bar.timestamp for bar in bars_by_symbol[symbol])
            if stamp in slots
        ]
        missing_stamps = [stamp for stamp in slots if stamp not in regular]
        missing_hash = hashlib.sha256(
            b"".join(
                stamp.isoformat(timespec="microseconds").replace("+00:00", "Z").encode()
                + b"\n"
                for stamp in missing_stamps
            )
        ).hexdigest()
        diagnostic_facts[symbol] = (
            ("pages", len(pages_by_symbol[symbol])),
            (
                "raw_bars",
                sum(
                    len(json.loads(page)["bars"].get(symbol, []))
                    for page in pages_by_symbol[symbol]
                ),
            ),
            ("observed", len(regular)),
            ("missing", len(missing_stamps)),
            ("off_session", len(bars_by_symbol[symbol]) - len(regular)),
            ("missing_sha256", missing_hash),
        )

    diagnostics = []
    for symbol in data.INITIAL_UNIVERSE:
        facts = dict(diagnostic_facts[symbol])
        diagnostics.append(
            {
                "symbol": symbol,
                "raw_page_count": facts["pages"],
                "raw_bar_count": facts["raw_bars"],
                "raw_bar_count_known": True,
                "parsed_page_count": facts["pages"],
                "observed_regular_slot_bar_count": facts["observed"],
                "normalized_regular_bar_count": 0,
                "off_session_excluded_count": facts["off_session"],
                "duplicate_expected_slot_count": 0,
                "duplicate_expected_slot_sha256": hashlib.sha256(b"").hexdigest(),
                "missing_expected_slot_count": facts["missing"],
                "missing_expected_slot_sha256": facts["missing_sha256"],
                "malformed_bar_count": 0,
                "pagination_terminal_state": "NULL_TOKEN_EXHAUSTED",
                "failure_code": None,
            }
        )
    artifact_custody_id = "e077474e-6274-4819-ae3d-9d7a73b86644"
    artifact_custody_sha = hashlib.sha256(
        b"fixture custody semantic material"
    ).hexdigest()
    evidence = {
        "schema": data.ARCH150_CUSTODY_SCHEMA,
        "classification": "BLOCKED",
        "failure_codes": ["MISSING_EXPECTED_SLOT"],
        "identity": artifact_custody_id,
        "sha256": artifact_custody_sha,
        "source": {"head": "3" * 40, "tree": "4" * 40},
        "dataset": {
            "identity": "6085afed-b870-59d7-9c0d-407db940777b",
            "sha256": "5" * 64,
        },
        "request_descriptors": request_descriptors,
        "raw_page_commitments": commitments,
        "raw_page_sha256_by_symbol": page_hashes,
        "diagnostics_by_symbol": diagnostics,
        "effects": {
            "credential_read_attempt_count": 1,
            "provider_request_attempt_count": sum(
                len(items) for items in pages_by_symbol.values()
            ),
            "robinhood_calls": 0,
            "broker_calls": 0,
            "order_mutations": 0,
            "production_state_mutations": 0,
            "strategy_pnl_evaluations": 0,
            "holdout_accesses": 0,
            "extension_accesses": 0,
        },
        "automatic_retry": "FORBIDDEN",
    }
    attempt = {
        "schema": "arch150-data-attempt-claim/v1",
        "attempt_id": _ATTEMPT_ID,
        "source_branch": requal.FEATURE_BRANCH,
        "source_head": "3" * 40,
        "source_tree": "4" * 40,
        "live_feature_head": "3" * 40,
        "live_develop_head": "3" * 40,
        "automatic_retry": "FORBIDDEN",
    }
    artifact_bodies = {
        "attempt.json": canonical_json_bytes(attempt),
        "custody-evidence.json": canonical_json_bytes(evidence),
    }
    result = {
        "schema": "arch150-data-operator-attempt-result/v1",
        "classification": "BLOCKED",
        "failure_code": "MISSING_EXPECTED_SLOT",
        "source_head": "3" * 40,
        "source_tree": "4" * 40,
        "dataset_identity": "6085afed-b870-59d7-9c0d-407db940777b",
        "dataset_sha256": "5" * 64,
        "evidence_sha256": hashlib.sha256(
            artifact_bodies["custody-evidence.json"]
        ).hexdigest(),
        "credential_read_attempt_count": 1,
        "provider_request_attempt_count": sum(
            len(items) for items in pages_by_symbol.values()
        ),
        "successful_page_count": sum(len(items) for items in pages_by_symbol.values()),
        "automatic_retry": "FORBIDDEN",
    }
    artifact_bodies["attempt-result.json"] = canonical_json_bytes(result)
    for name, body in artifact_bodies.items():
        (attempt_root / name).write_bytes(body)
    expected = requal._ExpectedAttempt(
        attempt_id=_ATTEMPT_ID,
        attempt_root=attempt_root,
        source_head="3" * 40,
        source_tree="4" * 40,
        live_feature_head="3" * 40,
        live_develop_head="3" * 40,
        dense_dataset_identity=evidence["dataset"]["identity"],
        dense_dataset_sha256=evidence["dataset"]["sha256"],
        custody_identity=artifact_custody_id,
        custody_semantic_sha256=artifact_custody_sha,
        artifact_facts=tuple(
            (name, len(body), hashlib.sha256(body).hexdigest())
            for name, body in artifact_bodies.items()
        ),
        credential_reads=1,
        provider_requests=sum(len(items) for items in pages_by_symbol.values()),
        successful_pages=sum(len(items) for items in pages_by_symbol.values()),
        failure_code="MISSING_EXPECTED_SLOT",
        classification="BLOCKED",
        symbol_facts=tuple(diagnostic_facts.items()),
    )
    return attempt_root, tmp_path / "output", expected, authority, slots, bars_by_symbol


def _run_fixture(
    fixture: tuple[
        Path,
        Path,
        requal._ExpectedAttempt,
        object,
        list[datetime],
        dict[str, list[IntradayBar]],
    ],
    *,
    output_directory: Path | None = None,
):
    attempt_root, output, expected, authority, slots, bars = fixture
    return requal._requalify_arch150_d1_for_test(
        attempt_root=attempt_root,
        output_directory=output if output_directory is None else output_directory,
        expected=expected,
        source_head=_SOURCE_HEAD,
        source_tree=_SOURCE_TREE,
        authority=authority,
        schedule_start=_SESSION,
        schedule_end=_SESSION + timedelta(days=1),
        test_root=attempt_root.parent,
    )


def _tree_hash(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_production_constants_and_entry_are_pinned_and_have_no_input_override():
    assert requal.ATTEMPT_ID == "a8d5975b-a3e9-4917-a8a8-2809e191fa20"
    assert requal.ATTEMPT_DIRECTORY == Path(
        r"F:\AI\research-data\arch150-intraday-data-custody\arch150-d1-a8d5975b-a3e9-4917-a8a8-2809e191fa20"
    )
    assert requal.ORIGINAL_SOURCE_HEAD == "50c5ed6204e909534778b07534fee7217117e47e"
    assert requal.ORIGINAL_SOURCE_TREE == "f53588f74266b3ef054ca49f9ea5c8a29e24d630"
    assert requal.ORIGINAL_DENSE_DATASET_ID == "6085afed-b870-59d7-9c0d-407db940777b"
    assert requal.ORIGINAL_DENSE_DATASET_SHA256 == (
        "70bf65d5b5c8726285215ed8337ae06bfaac8371cdb07b5dfd625ed800a96e23"
    )
    assert requal.ORIGINAL_CUSTODY_ID == "c0276e43-7533-5af4-9dbe-bb7e9095e693"
    assert requal.ORIGINAL_CUSTODY_SEMANTIC_SHA256 == (
        "d10a9eac514fe1c9a2e13f3ea6910e33d770b1397d9e56b29ac71e4c70543893"
    )
    assert requal.EXPECTED_CREDENTIAL_READS == 1
    assert requal.EXPECTED_PROVIDER_REQUESTS == requal.EXPECTED_SUCCESSFUL_PAGES == 306
    assert requal.ORIGINAL_ARTIFACTS == {
        "attempt.json": (
            427,
            "b1e6e3069c36d32a9d828d84526cc555a9dbc22c4f1ae1fac0760274aa48725b",
        ),
        "custody-evidence.json": (
            453326,
            "b83ced21f58cc1aa4731b2e72c1cf8cba4fb7d24378b0f206b303583bc658267",
        ),
        "attempt-result.json": (
            588,
            "b579e1617df02d05d909281b90c746c9d23bcdfd968395d36fb0f4f94b64585b",
        ),
    }
    assert {
        symbol: (
            facts["pages"],
            facts["raw_bars"],
            facts["observed"],
            facts["missing"],
            facts["off_session"],
        )
        for symbol, facts in requal.ORIGINAL_SYMBOL_FACTS.items()
    } == {
        "SPY": (158, 1577355, 781876, 104, 795479),
        "QQQ": (148, 1474748, 781865, 115, 692883),
    }
    assert set(inspect.signature(requal.requalify_arch150_d1).parameters) == {
        "output_directory"
    }
    with pytest.raises(TypeError):
        requal.requalify_arch150_d1(
            Path("F:/tmp/output"), attempt_root=Path("D:/fixture")
        )


def test_default_production_output_boundary_rejects_non_f_drive(tmp_path: Path):
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="OUTPUT_MUST_BE_ON_F"
    ):
        requal._validate_output_directory(
            Path("D:/disposable/output"),
            attempt_root=tmp_path / f"arch150-d1-{_ATTEMPT_ID}",
            private_test_root=None,
        )


@pytest.mark.parametrize("codepoint", [0x09, 0x0D, 0x0A, 0x00, 0x01, 0x1F, 0x7F])
def test_control_characters_are_rejected_before_any_output_create(
    tmp_path: Path, monkeypatch, codepoint: int
):
    fixture = _make_fixture(tmp_path)
    invalid_text = str(fixture[1]) + chr(codepoint)
    invalid_output = Path(invalid_text)
    write_calls: list[Path] = []

    def forbidden_write(path: Path, artifacts: dict[str, bytes]) -> None:
        write_calls.append(path)
        pytest.fail("create-once writer ran for invalid output path text")

    def forbidden_mkdir(_path: Path, *args, **kwargs) -> None:
        pytest.fail("mkdir ran for invalid output path text")

    monkeypatch.setattr(requal, "_write_output_once", forbidden_write)
    monkeypatch.setattr(Path, "mkdir", forbidden_mkdir)
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="OUTPUT_PATH_TEXT_INVALID"
    ):
        _run_fixture(fixture, output_directory=invalid_output)
    assert write_calls == []


@pytest.mark.parametrize("invalid_character", ["<", ">", ":", '"', "|", "?", "*"])
def test_windows_invalid_filename_characters_are_rejected(
    tmp_path: Path, invalid_character: str
):
    invalid_output = Path(f"{tmp_path}{chr(92)}output{invalid_character}")
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="OUTPUT_PATH_TEXT_INVALID"
    ):
        requal._validate_output_directory(
            invalid_output,
            attempt_root=tmp_path / f"arch150-d1-{_ATTEMPT_ID}",
            private_test_root=tmp_path,
        )


def test_validator_writer_and_result_share_canonical_output_path(
    tmp_path: Path, monkeypatch
):
    fixture = _make_fixture(tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    requested = nested / ".." / "canonical-output"
    canonical = tmp_path.resolve(strict=True) / "canonical-output"
    validate = requal._validate_output_directory
    write = requal._write_output_once
    validated_paths: list[Path] = []
    written_paths: list[Path] = []

    def capture_validation(root: Path, **kwargs) -> Path:
        validated = validate(root, **kwargs)
        validated_paths.append(validated)
        return validated

    def capture_write(root: Path, artifacts: dict[str, bytes]) -> None:
        written_paths.append(root)
        write(root, artifacts)

    monkeypatch.setattr(requal, "_validate_output_directory", capture_validation)
    monkeypatch.setattr(requal, "_write_output_once", capture_write)
    result = _run_fixture(fixture, output_directory=requested)

    assert validated_paths == [canonical]
    assert written_paths == validated_paths
    assert result.output_directory == validated_paths[0]
    assert result.output_directory.is_dir()


def test_cli_uses_exact_argv_path_and_returns_sanitized_result(
    tmp_path: Path, monkeypatch, capsys
):
    argument_text = f"{tmp_path}{chr(92)}t-output"
    received: list[Path] = []

    def fake_requalify(path: Path) -> requal.RequalificationResult:
        received.append(path)
        return requal.RequalificationResult(
            requal.OUTPUT_CLASSIFICATION,
            "dataset-id",
            "a" * 64,
            "custody-id",
            "b" * 64,
            "evidence-id",
            "c" * 64,
            path,
        )

    monkeypatch.setattr(requal, "requalify_arch150_d1", fake_requalify)
    assert requal.main(["--output-directory", argument_text]) == 0
    assert len(received) == 1
    assert str(received[0]) == argument_text
    assert "CLASSIFICATION=" + requal.OUTPUT_CLASSIFICATION in capsys.readouterr().out


def test_cli_help_is_effect_free(monkeypatch, capsys):
    def forbidden(_path: Path) -> requal.RequalificationResult:
        pytest.fail("--help invoked the production requalifier")

    monkeypatch.setattr(requal, "requalify_arch150_d1", forbidden)
    with pytest.raises(SystemExit) as raised:
        requal.main(["--help"])
    assert raised.value.code == 0
    assert "--output-directory" in capsys.readouterr().out


def test_cli_reports_only_sanitized_requalification_error(monkeypatch, capsys):
    def fail(_path: Path) -> requal.RequalificationResult:
        raise requal.Arch150D1RequalificationError("OUTPUT_PATH_TEXT_INVALID")

    monkeypatch.setattr(requal, "requalify_arch150_d1", fail)
    assert requal.main(["--output-directory", "synthetic-output"]) == 1
    assert capsys.readouterr().out.strip() == "FAILURE_CODE=OUTPUT_PATH_TEXT_INVALID"


def test_cli_rejects_duplicate_output_directory_arguments(monkeypatch):
    def forbidden(_path: Path) -> requal.RequalificationResult:
        pytest.fail("CLI accepted multiple output-directory arguments")

    monkeypatch.setattr(requal, "requalify_arch150_d1", forbidden)
    with pytest.raises(SystemExit) as raised:
        requal.main(
            [
                "--output-directory",
                "first-output",
                "--output-directory",
                "second-output",
            ]
        )
    assert raised.value.code == 2


def test_sparse_requalification_commits_absence_early_close_and_no_fill(tmp_path: Path):
    fixture = _make_fixture(tmp_path)
    before = _tree_hash(fixture[0])
    result = _run_fixture(fixture)
    assert _tree_hash(fixture[0]) == before
    assert result.classification == requal.OUTPUT_CLASSIFICATION
    dataset = json.loads((result.output_directory / "dataset.json").read_bytes())
    material = dataset["material"]
    assert material["original_dense_dataset"]["classification"] == "BLOCKED"
    assert material["missing_slot_semantics"] == requal.NO_FILL_SEMANTICS
    sparse = material["sparse_universe"]
    assert sparse["common_missing_count"] == 1
    assert sparse["union_missing_count"] == 3
    assert sparse["affected_session_count"] == 1
    assert sparse["sessions_affected_in_both_symbols"] == 1

    def missing_digest(stamps: set[datetime]) -> str:
        content = b"".join(
            stamp.isoformat(timespec="microseconds").replace("+00:00", "Z").encode()
            + b"\n"
            for stamp in sorted(stamps)
        )
        return hashlib.sha256(content).hexdigest()

    missing_spy = {fixture[4][4], fixture[4][5]}
    missing_qqq = {fixture[4][5], fixture[4][7]}
    assert sparse["common_missing_sha256"] == missing_digest(missing_spy & missing_qqq)
    assert sparse["union_missing_sha256"] == missing_digest(missing_spy | missing_qqq)
    session = sparse["per_session_missing_commitments"][0]
    assert session["session_date"] == _SESSION.isoformat()
    assert session["scheduled_slot_count"] == 210
    for symbol in data.INITIAL_UNIVERSE:
        normalized = (
            result.output_directory / "normalized" / f"{symbol}.csv"
        ).read_bytes()
        regular = [bar for bar in fixture[5][symbol] if bar.timestamp in fixture[4]]
        assert normalized == data.normalized_csv_bytes(regular)
        assert len(normalized.decode().splitlines()) == len(regular) + 1
        diagnostics = next(
            item for item in material["symbol_diagnostics"] if item["symbol"] == symbol
        )
        assert diagnostics["scheduled_slot_count"] == 210
        assert diagnostics["observed_regular_session_count"] == len(regular)
        assert diagnostics["first_observed_timestamp"] == regular[
            0
        ].timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")
        assert diagnostics["last_observed_timestamp"] == regular[
            -1
        ].timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")
        expected_missing = missing_spy if symbol == "SPY" else missing_qqq
        assert diagnostics["missing_slot_count"] == len(expected_missing)
        assert diagnostics["missing_timestamp_sha256"] == missing_digest(
            expected_missing
        )
        assert all(
            stamp.isoformat(timespec="microseconds").replace("+00:00", "Z").encode()
            not in normalized
            for stamp in fixture[4]
            if stamp not in {bar.timestamp for bar in regular}
        )
    assert material["requalification_source"] == {
        "branch": requal.FEATURE_BRANCH,
        "head": _SOURCE_HEAD,
        "tree": _SOURCE_TREE,
    }
    assert material["requalifier_effects"] == requal.ZERO_EFFECTS
    evidence = json.loads((result.output_directory / "evidence.json").read_bytes())
    assert evidence["material"]["classification"] == requal.OUTPUT_CLASSIFICATION
    assert evidence["material"]["effects"] == requal.ZERO_EFFECTS


def test_sparse_identities_and_outputs_are_deterministic(tmp_path: Path):
    first = _make_fixture(tmp_path / "one")
    second = _make_fixture(tmp_path / "two")
    first_result = _run_fixture(first)
    second_result = _run_fixture(second)
    assert first_result.dataset_identity == second_result.dataset_identity
    assert first_result.dataset_sha256 == second_result.dataset_sha256
    assert _tree_hash(first_result.output_directory) == _tree_hash(
        second_result.output_directory
    )


def test_output_is_create_once(tmp_path: Path):
    fixture = _make_fixture(tmp_path)
    result = _run_fixture(fixture)
    before = _tree_hash(result.output_directory)
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="OUTPUT_ALREADY_EXISTS"
    ):
        _run_fixture(fixture)
    assert _tree_hash(result.output_directory) == before


def test_bad_artifact_hash_fails_before_parser_or_output(tmp_path: Path, monkeypatch):
    fixture = _make_fixture(tmp_path)
    attempt_root, output = fixture[0], fixture[1]
    path = attempt_root / "custody-evidence.json"
    path.write_bytes(path.read_bytes() + b" ")

    def forbidden(*args, **kwargs):
        pytest.fail("page parser ran before retained artifact hash validation")

    monkeypatch.setattr(requal, "parse_alpaca_page", forbidden)
    with pytest.raises(
        requal.Arch150D1RequalificationError,
        match="ATTEMPT_ARTIFACT_COMMITMENT_MISMATCH",
    ):
        _run_fixture(fixture)
    assert not output.exists()


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_missing_or_unexpected_raw_page_fails_closed(tmp_path: Path, mutation: str):
    fixture = _make_fixture(tmp_path)
    directory = fixture[0] / "raw" / "SPY"
    target = directory / "0001.bin"
    if mutation == "missing":
        target.unlink()
    else:
        (directory / "9999.bin").write_bytes(b"unexpected")
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="INPUT_MANIFEST_MISMATCH"
    ):
        _run_fixture(fixture)
    assert not fixture[1].exists()


@pytest.mark.parametrize("artifact", ["normalized.csv", "unexpected.json"])
def test_attempt_rejects_extra_top_level_artifacts(tmp_path: Path, artifact: str):
    fixture = _make_fixture(tmp_path)
    (fixture[0] / artifact).write_bytes(b"unexpected")
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="INPUT_MANIFEST_MISMATCH"
    ):
        _run_fixture(fixture)
    assert not fixture[1].exists()


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        ("token_mismatch", "PAGE_TOKEN_CHAIN_MISMATCH"),
        ("repeated_token", "PAGE_TOKEN_REPEATED"),
        ("wrong_symbol", "UNEXPECTED_PROVIDER_SYMBOL"),
        ("reorder", "RAW_STREAM_ORDER_INVALID"),
        ("duplicate", "RAW_STREAM_DUPLICATE"),
        ("off_grid", "OFF_GRID_REGULAR_BAR"),
        ("future", "PROVIDER_TIMESTAMP_OUT_OF_RANGE"),
        ("malformed", "MALFORMED_PROVIDER_BAR"),
    ],
)
def test_invalid_raw_pages_stop_before_output(tmp_path: Path, fault: str, code: str):
    fixture = _make_fixture(tmp_path, fault=fault)
    with pytest.raises(requal.Arch150D1RequalificationError, match=code):
        _run_fixture(fixture)
    assert not fixture[1].exists()


def test_output_cannot_overlap_attempt_repository_or_worktrees(tmp_path: Path):
    fixture = _make_fixture(tmp_path)
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="OUTPUT_OVERLAPS_PROTECTED_PATH"
    ):
        requal._validate_output_directory(
            fixture[0] / "nested",
            attempt_root=fixture[0],
            private_test_root=tmp_path,
        )
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="OUTPUT_OVERLAPS_PROTECTED_PATH"
    ):
        requal._validate_output_directory(
            Path(r"F:\AI\worktrees\some-output"),
            attempt_root=fixture[0],
            private_test_root=tmp_path,
        )
    with pytest.raises(
        requal.Arch150D1RequalificationError, match="OUTPUT_OVERLAPS_PROTECTED_PATH"
    ):
        requal._validate_output_directory(
            Path(r"F:\AI\ai-trading-bot\some-output"),
            attempt_root=fixture[0],
            private_test_root=tmp_path,
        )


def test_module_has_no_provider_broker_or_strategy_execution_imports():
    tree = ast.parse(Path(requal.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    forbidden = ("alpaca", "robinhood", "broker", "strategy", "replay", "holdout")
    assert not any(token in name.lower() for name in imports for token in forbidden)
    assert requal.ZERO_EFFECTS == {
        "credential_reads": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "robinhood_calls": 0,
        "broker_calls": 0,
        "order_mutations": 0,
        "production_state_mutations": 0,
        "strategy_pnl_evaluations": 0,
        "holdout_accesses": 0,
        "extension_accesses": 0,
    }
