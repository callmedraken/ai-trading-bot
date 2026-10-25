"""Synthetic-only Architecture 146-A contracts; no acquisition or host custody."""

import ast
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

import pytest

import trading_bot.experiments.historical_research_dataset as subject
import trading_bot.experiments.research_strategy_robustness as robustness
from trading_bot.domain import Symbol
from trading_bot.experiments.research_strategy_backtest import (
    historical_data_fingerprint,
)
from trading_bot.market_calendar.nyse import NYSEMarketCalendar
from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult
from trading_bot.strategies import MovingAverageCrossoverConfig

ROLE = subject.HistoricalResearchPartitionRole
ERROR = subject.HistoricalResearchDatasetError
NY = ZoneInfo("America/New_York")
ID = uuid5(UUID("61a9b6ef-3fe3-564c-8f73-96478e0857a9"), "synthetic-only")
COMMON = {
    "symbol",
    "calendar",
    "timeframe",
    "adjustment",
    "provider",
    "feed",
    "currency",
    "asof",
    "normalization_schema",
    "normalization_version",
    "price_basis",
}
MANIFEST_FIELDS = COMMON | {
    "schema",
    "manifest_id",
    "role",
    "start",
    "end",
    "normalized_file_sha256",
    "normalized_byte_size",
    "row_count",
    "first_bar_timestamp",
    "last_bar_timestamp",
    "historical_data_fingerprint",
    "raw_vendor_page_sha256",
    "corporate_action_sha256",
}
SNAPSHOT_FIELDS = COMMON | {
    "schema",
    "snapshot_id",
    "start",
    "end",
    "development_start",
    "development_end",
    "walk_forward_start",
    "walk_forward_end",
    "final_holdout_start",
    "final_holdout_end",
    "open_manifest_id",
    "holdout_manifest_id",
    "full_historical_data_fingerprint",
    "open_corporate_action_sha256",
    "holdout_corporate_action_sha256",
}


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stamp(value):
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def row(timestamp="2020-01-02T05:00:00.000000Z", **changes):
    values = {
        "timestamp": timestamp,
        "symbol": "SPY",
        "open": "100.1234567890123456789",
        "high": "110",
        "low": "90",
        "close": "101",
        "volume": "42",
    }
    values.update(changes)
    return ",".join(values.values()) + "\n"


def csv_bytes(*rows):
    return ("timestamp,symbol,open,high,low,close,volume\n" + "".join(rows)).encode()


@pytest.fixture(scope="module")
def materials():
    result = []
    for role, start, end in (
        (
            ROLE.OPEN,
            subject.HISTORICAL_RESEARCH_FULL_START,
            subject.HISTORICAL_RESEARCH_HOLDOUT_START,
        ),
        (
            ROLE.FINAL_HOLDOUT,
            subject.HISTORICAL_RESEARCH_HOLDOUT_START,
            subject.HISTORICAL_RESEARCH_FULL_END,
        ),
    ):
        sessions = NYSEMarketCalendar().sessions_between(
            datetime.combine(start.date(), time.min, NY),
            datetime.combine(end.date(), time.min, NY),
        )
        normalized = csv_bytes(
            *(
                row(stamp(datetime.combine(item.session_date, time.min, NY)))
                for item in sessions.sessions
            )
        )
        data = subject.parse_historical_research_csv(normalized, role)
        pages = (b"synthetic raw first page", b"synthetic raw final page")
        sidecar = b'{"synthetic":true,"cash_dividends":[],"continuity_actions":[]}'
        manifest = subject.HistoricalResearchPartitionManifest(
            role=role,
            start=start,
            end=end,
            normalized_file_sha256=sha256(normalized).hexdigest(),
            normalized_byte_size=len(normalized),
            row_count=len(data.bars),
            first_bar_timestamp=data.bars[0].timestamp,
            last_bar_timestamp=data.bars[-1].timestamp,
            historical_data_fingerprint=historical_data_fingerprint(data),
            raw_vendor_page_sha256=tuple(sha256(page).hexdigest() for page in pages),
            corporate_action_sha256=sha256(sidecar).hexdigest(),
        )
        result.append(
            subject.HistoricalResearchPartitionMaterial(
                manifest, normalized, pages, sidecar
            )
        )
    return tuple(result)


@pytest.fixture(scope="module")
def snapshot(materials):
    opened, held = (
        subject.verify_historical_research_partition(item) for item in materials
    )
    full = HistoricalDataResult(
        HistoricalDataRequest(
            Symbol("SPY"),
            subject.HISTORICAL_RESEARCH_FULL_START,
            subject.HISTORICAL_RESEARCH_FULL_END,
        ),
        opened.bars + held.bars,
        subject.HISTORICAL_RESEARCH_PROVIDER,
    )
    return subject.HistoricalResearchDatasetSnapshot(
        open_manifest_id=materials[0].manifest.manifest_id,
        holdout_manifest_id=materials[1].manifest.manifest_id,
        full_historical_data_fingerprint=historical_data_fingerprint(full),
        open_corporate_action_sha256=materials[0].manifest.corporate_action_sha256,
        holdout_corporate_action_sha256=materials[1].manifest.corporate_action_sha256,
    )


@pytest.fixture(scope="module")
def policy(snapshot):
    fp = snapshot.full_historical_data_fingerprint
    parts = tuple(
        robustness.ResearchStrategyRobustnessPartition(role, start, end, fp, ID)
        for role, start, end in (
            (
                robustness.ResearchRobustnessPartitionRole.DEVELOPMENT,
                snapshot.development_start,
                snapshot.development_end,
            ),
            (
                robustness.ResearchRobustnessPartitionRole.WALK_FORWARD,
                snapshot.walk_forward_start,
                snapshot.walk_forward_end,
            ),
            (
                robustness.ResearchRobustnessPartitionRole.FINAL_HOLDOUT,
                snapshot.final_holdout_start,
                snapshot.final_holdout_end,
            ),
        )
    )
    scenarios = tuple(
        robustness.ResearchExecutionStressScenario(
            kind.value,
            kind,
            Decimal("1") if kind.value == "HIGHER_COST" else Decimal("0"),
            Decimal("0"),
            1 if kind.value == "DELAYED_FILL" else 0,
            Decimal("0.5") if kind.value == "PARTIAL_FILL" else None,
        )
        for kind in robustness.ResearchExecutionStressKind
    )
    return robustness.ResearchStrategyRobustnessQualificationPolicy(
        ID,
        ID,
        "a" * 40,
        "b" * 40,
        "moving_average_crossover",
        "v1",
        Symbol("SPY"),
        MovingAverageCrossoverConfig(3, 5, Decimal("1")),
        fp,
        *parts,
        1,
        Decimal("100"),
        Decimal("0"),
        2,
        Decimal("0"),
        Decimal("0"),
        Decimal("100"),
        Decimal("100"),
        1,
        0,
        Decimal("100"),
        scenarios,
        None,
        "c" * 40,
        "d" * 40,
    )


def test_exact_schema_namespaces_fields_and_roundtrips(materials, snapshot):
    assert subject.HISTORICAL_RESEARCH_PARTITION_MANIFEST_NAMESPACE == UUID(
        "8fdd2b9e-be93-5aaf-84b2-b9b7a7381edb"
    )
    assert subject.HISTORICAL_RESEARCH_DATASET_SNAPSHOT_NAMESPACE == UUID(
        "61a9b6ef-3fe3-564c-8f73-96478e0857a9"
    )
    for value, expected, schema in (
        (
            materials[0].manifest,
            MANIFEST_FIELDS,
            "historical-research-partition-manifest/v1",
        ),
        (snapshot, SNAPSHOT_FIELDS, "historical-research-dataset-snapshot/v1"),
    ):
        assert set(json.loads(value.to_json())) == expected
        assert value.schema == schema
        assert type(value).from_json(value.to_json()) == value
        with pytest.raises(FrozenInstanceError):
            value.symbol = "QQQ"


@pytest.mark.parametrize("kind", ["manifest", "snapshot"])
@pytest.mark.parametrize(
    "bad",
    ["unknown", "missing", "duplicate", "whitespace", "schema", "id", "nonfinite"],
)
def test_strict_json(materials, snapshot, kind, bad):
    value = materials[0].manifest if kind == "manifest" else snapshot
    raw = json.loads(value.to_json())
    if bad == "duplicate":
        encoded = value.to_json()[:-1] + ',"symbol":"SPY"}'
    elif bad == "whitespace":
        encoded = json.dumps(raw, sort_keys=True)
    elif bad == "nonfinite":
        encoded = value.to_json().replace('"symbol":"SPY"', '"symbol":NaN')
    else:
        if bad == "unknown":
            raw["path"] = "irrelevant"
        elif bad == "missing":
            raw.pop("provider")
        elif bad == "schema":
            raw["schema"] = "wrong/v1"
        else:
            raw["manifest_id" if kind == "manifest" else "snapshot_id"] = str(ID)
        encoded = wire(raw)
    with pytest.raises(ERROR):
        type(value).from_json(encoded)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("normalized_file_sha256", "A" * 64),
        ("corporate_action_sha256", ""),
        ("corporate_action_sha256", None),
        ("raw_vendor_page_sha256", []),
        ("raw_vendor_page_sha256", ()),
        ("raw_vendor_page_sha256", ("x",)),
        ("normalized_byte_size", True),
        ("row_count", 1.0),
        ("row_count", 0),
        ("historical_data_fingerprint", UUID(int=1)),
        ("role", "OPEN"),
    ],
)
def test_manifest_type_and_canonical_rejection(materials, field, bad):
    with pytest.raises(ERROR):
        replace(materials[0].manifest, **{field: bad})


@pytest.mark.parametrize(
    "field",
    [
        "symbol",
        "calendar",
        "timeframe",
        "adjustment",
        "provider",
        "feed",
        "currency",
        "asof",
        "normalization_schema",
        "normalization_version",
        "price_basis",
    ],
)
@pytest.mark.parametrize("kind", ["manifest", "snapshot"])
def test_v1_semantic_drift_fails(materials, snapshot, field, kind):
    value = materials[0].manifest if kind == "manifest" else snapshot
    with pytest.raises(ERROR):
        replace(
            value,
            **{
                field: {
                    "feed": "iex",
                    "adjustment": "TOTAL_RETURN",
                    "price_basis": "TOTAL_RETURN",
                }.get(field, "wrong")
            },
        )


@pytest.mark.parametrize(
    "name",
    [
        "path",
        "acquired_at",
        "clock",
        "hostname",
        "pid",
        "locale",
        "object_id",
        "hash_seed",
        "random_uuid",
    ],
)
def test_nonsemantic_material_never_enters_contract(materials, name):
    manifest = materials[0].manifest
    raw = json.loads(manifest.to_json())
    raw[name] = "irrelevant"
    with pytest.raises(ERROR):
        type(manifest).from_json(wire(raw))
    assert replace(manifest).manifest_id == manifest.manifest_id


@pytest.mark.parametrize(
    "field",
    [
        "normalized_file_sha256",
        "normalized_byte_size",
        "row_count",
        "first_bar_timestamp",
        "last_bar_timestamp",
        "historical_data_fingerprint",
        "raw_vendor_page_sha256",
        "corporate_action_sha256",
    ],
)
def test_each_variable_manifest_semantic_field_changes_identity(materials, field):
    value = materials[0].manifest
    old = getattr(value, field)
    new = {
        "normalized_file_sha256": "a" * 64,
        "corporate_action_sha256": "b" * 64,
        "normalized_byte_size": value.normalized_byte_size + 1,
        "row_count": value.row_count + 1,
        "first_bar_timestamp": value.first_bar_timestamp + timedelta(microseconds=1),
        "last_bar_timestamp": value.last_bar_timestamp - timedelta(microseconds=1),
        "historical_data_fingerprint": ID,
        "raw_vendor_page_sha256": tuple(reversed(value.raw_vendor_page_sha256)),
    }[field]
    assert old != new
    assert replace(value, **{field: new}).manifest_id != value.manifest_id


@pytest.mark.parametrize(
    "field",
    [
        "open_manifest_id",
        "holdout_manifest_id",
        "full_historical_data_fingerprint",
        "open_corporate_action_sha256",
        "holdout_corporate_action_sha256",
    ],
)
def test_each_variable_snapshot_semantic_field_changes_identity(snapshot, field):
    value = ID if field.endswith("_id") or field.endswith("fingerprint") else "a" * 64
    assert replace(snapshot, **{field: value}).snapshot_id != snapshot.snapshot_id


@pytest.mark.parametrize(
    "name",
    [
        "start",
        "end",
        "development_start",
        "development_end",
        "walk_forward_start",
        "walk_forward_end",
        "final_holdout_start",
        "final_holdout_end",
    ],
)
@pytest.mark.parametrize("offset", [-1, 1])
def test_frozen_calendar_rejects_gaps_overlap_reversal(snapshot, name, offset):
    with pytest.raises(ERROR):
        replace(snapshot, **{name: getattr(snapshot, name) + timedelta(days=offset)})


@pytest.mark.parametrize(
    "role,timestamp",
    [
        (ROLE.OPEN, "2024-01-01T00:00:00.000000Z"),
        (ROLE.FINAL_HOLDOUT, "2023-12-31T23:59:59.999999Z"),
        (ROLE.OPEN, "2015-12-31T23:59:59.999999Z"),
        (ROLE.FINAL_HOLDOUT, "2026-10-24T00:00:00.000000Z"),
    ],
)
def test_entire_csv_partition_containment(role, timestamp):
    with pytest.raises(ERROR):
        subject.parse_historical_research_csv(csv_bytes(row(timestamp)), role)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("open", "NaN"),
        ("open", "sNaN"),
        ("open", "Infinity"),
        ("open", "-1"),
        ("open", "0"),
        ("open", "1.0"),
        ("open", "1E2"),
        ("open", " 1"),
        ("open", "+1"),
        ("open", ".1"),
        ("high", "99"),
        ("low", "102"),
        ("close", "111"),
        ("volume", "-1"),
        ("volume", "1.0"),
        ("volume", "01"),
        ("volume", "true"),
        ("symbol", "QQQ"),
        ("symbol", "spy"),
        ("timestamp", "2020-01-02T00:00:00"),
        ("timestamp", "2020-01-02T05:00:00+00:00"),
    ],
)
def test_csv_bar_and_canonical_material_rejection(field, bad):
    with pytest.raises(ERROR):
        subject.parse_historical_research_csv(csv_bytes(row(**{field: bad})), ROLE.OPEN)


@pytest.mark.parametrize(
    "rows",
    [
        (row(), row()),
        (row("2020-01-03T05:00:00.000000Z"), row()),
    ],
)
def test_unsorted_and_duplicate_rows_are_not_sorted_away(rows):
    with pytest.raises(ERROR):
        subject.parse_historical_research_csv(csv_bytes(*rows), ROLE.OPEN)


@pytest.mark.parametrize(
    "value",
    [
        b"",
        b"timestamp,symbol,open,high,low,close,volume\n",
        b"timestamp,symbol,open,high,low,close,volume,extra\n",
        b"timestamp,timestamp,open,high,low,close,volume\n",
        b"\xff",
        csv_bytes(row()).replace(b",42\n", b",42,extra\n"),
    ],
)
def test_csv_exact_schema_and_empty_material(value):
    with pytest.raises(ERROR):
        subject.parse_historical_research_csv(value, ROLE.OPEN)


def test_boundary_metadata_and_role_order_rejection(materials, snapshot):
    opened, held = materials
    for changes in (
        {"first_bar_timestamp": subject.HISTORICAL_RESEARCH_HOLDOUT_START},
        {"last_bar_timestamp": subject.HISTORICAL_RESEARCH_HOLDOUT_START},
        {"end": opened.manifest.start},
        {"role": ROLE.FINAL_HOLDOUT},
    ):
        with pytest.raises(ERROR):
            replace(opened.manifest, **changes)
    with pytest.raises(ERROR):
        replace(
            held.manifest,
            first_bar_timestamp=subject.HISTORICAL_RESEARCH_HOLDOUT_START
            - timedelta(microseconds=1),
        )
    with pytest.raises(ERROR):
        subject.verify_historical_research_dataset(snapshot, held, opened)


@pytest.mark.parametrize("part", [0, 1])
@pytest.mark.parametrize(
    "field", ["normalized_bytes", "raw_vendor_pages", "corporate_action_sidecar"]
)
def test_external_bytes_required_and_corruption_rejected(materials, part, field):
    material = materials[part]
    corruption = (b"wrong",) if field == "raw_vendor_pages" else b"wrong"
    with pytest.raises(ERROR):
        subject.verify_historical_research_partition(
            replace(material, **{field: corruption})
        )


def test_page_order_and_missing_pages_fail(materials):
    material = materials[0]
    for pages in (
        tuple(reversed(material.raw_vendor_pages)),
        material.raw_vendor_pages[:1],
    ):
        with pytest.raises(ERROR):
            subject.verify_historical_research_partition(
                replace(material, raw_vendor_pages=pages)
            )


@pytest.mark.parametrize(
    "field",
    [
        "normalized_file_sha256",
        "normalized_byte_size",
        "row_count",
        "historical_data_fingerprint",
        "first_bar_timestamp",
        "last_bar_timestamp",
        "corporate_action_sha256",
    ],
)
def test_self_consistent_manifest_is_not_external_proof(materials, field):
    material = materials[0]
    value = {
        "normalized_file_sha256": "a" * 64,
        "normalized_byte_size": len(material.normalized_bytes) + 1,
        "row_count": material.manifest.row_count + 1,
        "historical_data_fingerprint": ID,
        "first_bar_timestamp": material.manifest.first_bar_timestamp
        + timedelta(microseconds=1),
        "last_bar_timestamp": material.manifest.last_bar_timestamp
        - timedelta(microseconds=1),
        "corporate_action_sha256": "a" * 64,
    }[field]
    forged = replace(material.manifest, **{field: value})
    assert type(forged).from_json(forged.to_json()) == forged
    with pytest.raises(ERROR):
        subject.verify_historical_research_partition(replace(material, manifest=forged))


def test_missing_unexpected_and_duplicate_daily_sessions_are_explicit(materials):
    data = subject.parse_historical_research_csv(
        materials[0].normalized_bytes, ROLE.OPEN
    )
    missing = replace(data, bars=data.bars[1:])
    with pytest.raises(subject.HistoricalResearchSessionCoverageError) as caught:
        subject.validate_historical_research_session_coverage(missing)
    assert caught.value.missing_sessions == (
        data.bars[0].timestamp.astimezone(NY).date(),
    )
    saturday = replace(data.bars[0], timestamp=datetime(2016, 1, 2, 5, tzinfo=UTC))
    extra = replace(data, bars=(saturday,) + data.bars)
    with pytest.raises(subject.HistoricalResearchSessionCoverageError) as caught:
        subject.validate_historical_research_session_coverage(extra)
    assert caught.value.unexpected_sessions == (
        saturday.timestamp.astimezone(NY).date(),
    )
    duplicate_day = replace(
        data.bars[0], timestamp=data.bars[0].timestamp + timedelta(hours=1)
    )
    with pytest.raises(ERROR, match="multiple daily"):
        subject.validate_historical_research_session_coverage(
            replace(data, bars=(data.bars[0], duplicate_day) + data.bars[1:])
        )


def test_public_result_reconciliation_and_decimal_context(materials, snapshot):
    material = materials[0]
    data = subject.verify_historical_research_partition(material)
    assert subject.verify_historical_research_partition(material, data) == data
    with pytest.raises(ERROR):
        subject.verify_historical_research_partition(
            material, replace(data, provider_name="wrong")
        )
    with localcontext() as context:
        context.prec = 2
        assert (
            historical_data_fingerprint(data)
            == material.manifest.historical_data_fingerprint
        )
        assert (
            subject.verify_historical_research_dataset(snapshot, *materials).snapshot
            == snapshot
        )


def test_full_fingerprint_distinction_and_nonprice_receipt(materials, snapshot):
    receipt = subject.verify_historical_research_dataset(snapshot, *materials)
    assert (
        len(
            {
                materials[0].manifest.historical_data_fingerprint,
                materials[1].manifest.historical_data_fingerprint,
                snapshot.full_historical_data_fingerprint,
            }
        )
        == 3
    )
    assert receipt.snapshot == snapshot
    assert not any(
        "bars" in item.name or "bytes" in item.name for item in fields(receipt)
    )
    assert subject.verify_historical_research_dataset(snapshot, *materials) == receipt
    with pytest.raises(ERROR):
        subject.HistoricalResearchDatasetVerification()


@pytest.mark.parametrize(
    "field",
    [
        "open_manifest_id",
        "holdout_manifest_id",
        "full_historical_data_fingerprint",
        "open_corporate_action_sha256",
        "holdout_corporate_action_sha256",
    ],
)
def test_self_consistent_snapshot_requires_external_manifests_and_full_data(
    materials, snapshot, field
):
    value = ID if field.endswith("_id") or field.endswith("fingerprint") else "a" * 64
    forged = replace(snapshot, **{field: value})
    assert type(forged).from_json(forged.to_json()) == forged
    with pytest.raises(ERROR):
        subject.verify_historical_research_dataset(forged, *materials)


def test_open_verifier_never_receives_holdout_bytes_or_proves_full_commitment(
    materials, snapshot, monkeypatch
):
    calls = []
    original = subject.verify_historical_research_partition

    def verify(material, historical_result=None):
        assert material.manifest.role is ROLE.OPEN
        calls.append(material.manifest.role)
        return original(material, historical_result)

    monkeypatch.setattr(subject, "verify_historical_research_partition", verify)
    # A changed full commitment remains unproven here; full verification rejects it.
    committed = replace(snapshot, full_historical_data_fingerprint=ID)
    opened = subject.verify_historical_research_open_commitment(
        committed, materials[0], materials[1].manifest
    )
    assert calls == [ROLE.OPEN]
    assert opened.request.end == subject.HISTORICAL_RESEARCH_HOLDOUT_START


def test_policy_bridge_is_additive_nonprice_and_never_admits_holdout(
    materials, snapshot, policy, monkeypatch
):
    before = policy.to_json()

    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden Architecture-145 effect")

    monkeypatch.setattr(robustness, "admit_research_strategy_final_holdout", forbidden)
    monkeypatch.setattr(
        robustness, "build_research_strategy_live_canary_eligibility", forbidden
    )
    receipt = subject.verify_historical_research_dataset(snapshot, *materials)
    subject.verify_historical_research_policy_binding(policy, receipt)
    assert policy.to_json() == before
    with pytest.raises(ERROR):
        subject.verify_historical_research_policy_binding(policy, snapshot)


@pytest.mark.parametrize(
    "drift", ["fingerprint", "symbol", "development", "walk_forward", "final_holdout"]
)
def test_policy_bridge_rejects_lineage_drift(materials, snapshot, policy, drift):
    receipt = subject.verify_historical_research_dataset(snapshot, *materials)
    if drift == "symbol":
        changed = replace(policy, symbol=Symbol("QQQ"))
    elif drift == "fingerprint":
        changed = replace(
            policy,
            historical_data_fingerprint=ID,
            **{
                name: replace(getattr(policy, name), historical_data_fingerprint=ID)
                for name in (
                    "development_partition",
                    "walk_forward_partition",
                    "final_holdout_partition",
                )
            },
        )
    else:
        name = drift + "_partition"
        changed = replace(
            policy,
            **{
                name: replace(
                    getattr(policy, name),
                    start=getattr(policy, name).start + timedelta(days=1),
                )
            },
        )
    with pytest.raises(ERROR):
        subject.verify_historical_research_policy_binding(changed, receipt)


def test_145_source_bytes_and_identity_contract_are_frozen():
    source = Path(robustness.__file__).read_text(encoding="utf-8").encode()
    import hashlib

    assert (
        hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
        == "80073f28c98ff81792e16b01098eaf61437d4690"
    )


def test_no_io_acquisition_effect_or_clock_capabilities():
    tree = ast.parse(Path(subject.__file__).read_text(encoding="utf-8"))
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports == {
        "__future__",
        "csv",
        "io",
        "json",
        "re",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "hashlib",
        "uuid",
        "zoneinfo",
        "trading_bot.domain",
        "trading_bot.experiments.research_strategy_backtest",
        "trading_bot.experiments.research_strategy_robustness",
        "trading_bot.market_calendar.nyse",
        "trading_bot.market_data.exceptions",
        "trading_bot.market_data.models",
    }
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert not called & {
        "open",
        "read_bytes",
        "read_text",
        "write_bytes",
        "write_text",
        "connect",
        "getenv",
        "now",
        "utcnow",
        "time",
        "uuid4",
        "hash",
        "id",
        "get_bars",
        "admit_research_strategy_final_holdout",
        "build_research_strategy_live_canary_eligibility",
    }


@pytest.mark.parametrize("kind", ["manifest", "snapshot"])
def test_every_canonical_field_is_required(materials, snapshot, kind):
    value = materials[0].manifest if kind == "manifest" else snapshot
    raw = json.loads(value.to_json())
    for key in raw:
        incomplete = dict(raw)
        incomplete.pop(key)
        with pytest.raises(ERROR):
            type(value).from_json(wire(incomplete))


@pytest.mark.parametrize("kind", ["manifest", "snapshot"])
@pytest.mark.parametrize(
    "bad", ["2016-01-01T00:00:00Z", "2016-01-01T00:00:00.000000+00:00", "2016-01-01"]
)
def test_noncanonical_json_timestamps_fail(materials, snapshot, kind, bad):
    value = materials[0].manifest if kind == "manifest" else snapshot
    raw = json.loads(value.to_json())
    raw["start"] = bad
    with pytest.raises(ERROR):
        type(value).from_json(wire(raw))


def test_self_consistent_missing_session_partition_cannot_verify(materials):
    material = materials[0]
    normalized = material.normalized_bytes.splitlines(keepends=True)
    changed = b"".join(normalized[:2] + normalized[3:])
    data = subject.parse_historical_research_csv(changed, ROLE.OPEN)
    manifest = replace(
        material.manifest,
        normalized_file_sha256=sha256(changed).hexdigest(),
        normalized_byte_size=len(changed),
        row_count=len(data.bars),
        historical_data_fingerprint=historical_data_fingerprint(data),
    )
    with pytest.raises(subject.HistoricalResearchSessionCoverageError):
        subject.verify_historical_research_partition(
            replace(material, manifest=manifest, normalized_bytes=changed)
        )


def test_receipt_cannot_be_rebound_to_self_consistent_unverified_snapshot(
    materials, snapshot, policy
):
    receipt = subject.verify_historical_research_dataset(snapshot, *materials)
    object.__setattr__(
        receipt, "snapshot", replace(snapshot, full_historical_data_fingerprint=ID)
    )
    with pytest.raises(ERROR, match="receipt"):
        subject.verify_historical_research_policy_binding(policy, receipt)
