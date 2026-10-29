"""Synthetic-only 146-B acquisition/custody and independent OPEN admission."""

import ast
import json
from dataclasses import replace
from datetime import UTC, datetime, time
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

import trading_bot.experiments.historical_research_acquisition as acquisition
import trading_bot.experiments.historical_research_custody as custody
import trading_bot.experiments.historical_research_dataset as dataset

HEAD = "a" * 40
TREE = "b" * 40
ATTEMPT = "930cba37-a96e-4d59-b722-116e232e17cc"
SECRET = "SYNTHETIC_SECRET_NEVER_IN_EVIDENCE"
HOLDOUT_PRICE = "9876.54321"
NY = ZoneInfo("America/New_York")


def wire(value):
    return json.dumps(value, separators=(",", ":")).encode()


@pytest.fixture(scope="module")
def vendor():
    authority = custody.ACCEPTED_HISTORICAL_SESSION_AUTHORITIES[0]
    sessions = authority.sessions
    rows = []
    for item in sessions:
        stamp = datetime.combine(item, time.min, NY).astimezone(UTC)
        price = (
            float(HOLDOUT_PRICE)
            if stamp >= dataset.HISTORICAL_RESEARCH_HOLDOUT_START
            else 100.25
        )
        rows.append(
            {
                "t": stamp.isoformat().replace("+00:00", "Z"),
                "o": price,
                "h": price + 1,
                "l": price - 1,
                "c": price,
                "v": 42,
                "n": 5,
                "vw": price,
            }
        )
    split = len(rows) - 100
    bars = (
        wire({"symbol": "SPY", "bars": rows[:split], "next_page_token": "second"}),
        wire({"symbol": "SPY", "bars": rows[split:], "next_page_token": None}),
    )
    actions = (
        wire(
            {
                "corporate_actions": {
                    "cash_dividends": [
                        {
                            "id": "synthetic-dividend",
                            "symbol": "SPY",
                            "process_date": "2025-01-02",
                            "rate": 1.5,
                        }
                    ]
                },
                "next_page_token": None,
            }
        ),
    )
    return bars, actions, authority


class FakeCredentials:
    def __init__(self):
        self.reads = 0

    def read(self):
        self.reads += 1
        return acquisition.AcquisitionCredentials("SYNTHETIC_KEY", SECRET)


class FakeTransport:
    def __init__(self, vendor):
        self.bars, self.actions = vendor[:2]
        self.calls = []
        self.error = None
        self.status = 200

    def get(self, request, credentials):
        self.calls.append(request)
        if self.error:
            raise self.error
        pages = (
            self.bars
            if request.stream is acquisition.AcquisitionStream.BARS
            else self.actions
        )
        index = sum(previous.stream is request.stream for previous in self.calls) - 1
        return acquisition.HistoricalResearchResponse(
            request, self.status, pages[index]
        )


class FakeCustody:
    def __init__(self):
        self.claimed = set()
        self.protected = {}
        self.opened = {}
        self.events = []
        self.fail = None
        self.inspection = acquisition.CustodyInspection(
            custody.CUSTODY_ROOT,
            custody.OPEN_ROOT,
            "S-1-5-32-544",
            custody.CUSTODY_SDDL,
            True,
            True,
            True,
        )

    def claim_attempt(self, attempt, plan):
        assert plan == acquisition.CustodyPersistencePlan()
        if attempt in self.claimed or self.protected or self.opened:
            return False
        self.claimed.add(attempt)
        self.events.append("claim")
        return True

    def prepare_protected(self, plan):
        self.events.append("prepare")
        if self.fail == "prepare":
            raise OSError(SECRET)

    def inspect(self):
        return self.inspection

    def persist_protected(self, path, body):
        assert path not in self.protected
        self.events.append(path)
        self.protected[path] = body
        if self.fail == path:
            raise OSError(SECRET)
        digest = "0" * 64 if self.fail == "digest" else sha256(body).hexdigest()
        return acquisition.PersistenceReceipt(
            path, digest, len(body), self.fail != "fsync"
        )

    def materialize_open(self, files):
        assert "normalized/holdout/SPY.csv" in self.protected
        assert "manifests/snapshot.json" in self.protected
        self.events.append("open")
        receipts = []
        for path, body in files:
            assert path not in self.opened
            self.opened[path] = body
            receipts.append(
                acquisition.PersistenceReceipt(
                    path, sha256(body).hexdigest(), len(body), True
                )
            )
            if self.fail == "open":
                raise OSError(SECRET)
        return tuple(receipts)

    def record_terminal(self, state, stage):
        self.events.append(state)
        if self.fail == "terminal":
            raise OSError(SECRET)


def execute(vendor, *, transport=None, store=None, credentials=None, authority=None):
    transport = transport or FakeTransport(vendor)
    store = store or FakeCustody()
    credentials = credentials or FakeCredentials()
    operator = acquisition.HistoricalResearchAcquisitionOperator(
        transport, credentials, store
    )
    result = operator.run(
        source_head=HEAD,
        source_tree=TREE,
        attempt_id=ATTEMPT,
        session_authority=authority or vendor[2],
    )
    return result, operator, transport, store, credentials


def admission_for(evidence_bytes):
    evidence = custody.HistoricalResearchCustodyEvidence.from_bytes(evidence_bytes)
    return custody.HistoricalResearchCustodyAdmission(
        sha256(evidence_bytes).hexdigest(),
        evidence.source_head,
        evidence.source_tree,
        evidence.checkpoint,
        evidence.attempt_id,
        str(evidence.snapshot.snapshot_id),
        evidence.calendar_identity,
        evidence.calendar_sha256,
    )


def verify(result, store, admission=None, **changes):
    evidence = custody.HistoricalResearchCustodyEvidence.from_bytes(
        result.evidence_bytes
    )
    arguments = dict(
        normalized_open_bytes=store.opened["normalized/open/SPY.csv"],
        snapshot=evidence.snapshot,
        open_manifest=evidence.open_manifest,
        holdout_commitment=evidence.holdout_manifest,
        custody_evidence_bytes=result.evidence_bytes,
        custody_admission_bytes=(
            admission or admission_for(result.evidence_bytes)
        ).to_bytes(),
    )
    arguments.update(changes)
    return custody.verify_historical_research_open_publication(**arguments)


@pytest.fixture(scope="module")
def completed(vendor):
    result, _, _, store, _ = execute(vendor)
    assert result.evidence_bytes is not None, result
    return result, store


def test_exact_frozen_get_requests():
    bars = acquisition.HistoricalResearchRequest(acquisition.AcquisitionStream.BARS)
    assert bars.method == "GET" and bars.host == "data.alpaca.markets"
    assert bars.descriptor == {
        "method": "GET",
        "host": "data.alpaca.markets",
        "path": "/v2/stocks/SPY/bars",
        "parameters": {
            "timeframe": "1Day",
            "start": "2016-01-01T00:00:00Z",
            "end": "2026-10-24T00:00:00Z",
            "adjustment": "raw",
            "feed": "sip",
            "currency": "USD",
            "sort": "asc",
            "limit": "10000",
        },
    }
    actions = acquisition.HistoricalResearchRequest(
        acquisition.AcquisitionStream.CORPORATE_ACTIONS, "a&x=2"
    )
    assert actions.descriptor["parameters"] == {
        "symbols": "SPY",
        "region": "us",
        "start": "2016-01-01",
        "end": "2026-10-24",
        "data_quality": "complete",
        "sort": "asc",
        "limit": "1000",
    }
    assert "types=" not in actions.target and "page_token=a%26x%3D2" in actions.target
    assert "page_token" not in bars.target


@pytest.mark.parametrize("token", ["", "a\nb", "a\0b", " ", "x" * 1025, 4, True])
def test_request_rejects_invalid_tokens(token):
    with pytest.raises(custody.HistoricalResearchCustodyError):
        acquisition.HistoricalResearchRequest(acquisition.AcquisitionStream.BARS, token)


def test_mixed_pages_remain_protected_and_open_unadmitted(vendor, completed):
    result, store = completed
    assert result.state == "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION"
    assert store.protected["vendor-raw/bars/0000.json"] == vendor[0][0]
    assert HOLDOUT_PRICE.encode() in vendor[0][0]
    assert all(HOLDOUT_PRICE.encode() not in body for body in store.opened.values())
    assert all(not path.startswith("vendor-raw") for path in store.opened)
    evidence = custody.HistoricalResearchCustodyEvidence.from_bytes(
        result.evidence_bytes
    )
    assert (
        evidence.open_manifest.raw_vendor_page_sha256
        == evidence.holdout_manifest.raw_vendor_page_sha256
        == tuple(sha256(page).hexdigest() for page in vendor[0])
    )
    assert (
        evidence.open_manifest.corporate_action_sha256
        == evidence.holdout_manifest.corporate_action_sha256
    )
    assert (
        store.events.index("vendor-raw/bars/0001.json")
        < store.events.index("normalized/holdout/SPY.csv")
        < store.events.index("open")
    )
    with pytest.raises(
        custody.HistoricalResearchCustodyError, match="independently accepted"
    ):
        verify(result, store)
    assert not custody.ACCEPTED_CUSTODY_ADMISSIONS
    assert (
        custody.real_acquisition_readiness(vendor[2])
        == "HISTORICAL_AUTHORITY_ACCEPTED_OTHER_B2_PREREQUISITES_NOT_EVALUATED"
    )


def test_open_success_requires_independently_pinned_registry(
    completed, vendor, monkeypatch
):
    result, store = completed
    monkeypatch.setattr(
        custody, "ACCEPTED_CUSTODY_ADMISSIONS", (admission_for(result.evidence_bytes),)
    )
    monkeypatch.setattr(
        custody, "ACCEPTED_HISTORICAL_SESSION_AUTHORITIES", (vendor[2],)
    )
    data = verify(result, store)
    assert data.bars[-1].timestamp < dataset.HISTORICAL_RESEARCH_HOLDOUT_START
    assert (
        custody.historical_research_normalized_csv(data.bars)
        == store.opened["normalized/open/SPY.csv"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_head", "c" * 40),
        ("source_tree", "d" * 40),
        ("attempt_id", str(UUID(int=1))),
        ("snapshot_id", str(UUID(int=2))),
        ("calendar_identity", "other"),
        ("calendar_sha256", "1" * 64),
        ("evidence_sha256", "2" * 64),
    ],
)
def test_even_pinned_admission_must_match_every_evidence_field(
    completed, vendor, monkeypatch, field, value
):
    result, store = completed
    admission = replace(admission_for(result.evidence_bytes), **{field: value})
    monkeypatch.setattr(custody, "ACCEPTED_CUSTODY_ADMISSIONS", (admission,))
    monkeypatch.setattr(
        custody, "ACCEPTED_HISTORICAL_SESSION_AUTHORITIES", (vendor[2],)
    )
    with pytest.raises(
        custody.HistoricalResearchCustodyError, match="binding mismatch"
    ):
        verify(result, store, admission)


def test_calendar_admission_is_independent(completed, monkeypatch):
    monkeypatch.setattr(custody, "ACCEPTED_HISTORICAL_SESSION_AUTHORITIES", ())
    result, store = completed
    monkeypatch.setattr(
        custody, "ACCEPTED_CUSTODY_ADMISSIONS", (admission_for(result.evidence_bytes),)
    )
    with pytest.raises(
        custody.HistoricalResearchCustodyError, match="session authority"
    ):
        verify(result, store)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b + b"\n",
        lambda b: b.replace(b'"production_effects":0', b'"production_effects":1'),
        lambda b: b.replace(b'"schema":', b'"extra":1,"schema":'),
        lambda b: b.replace(b'"source_head":', b'"source_head":"c","source_head":'),
    ],
)
def test_evidence_is_exact_canonical_nonprice_schema(completed, mutation):
    result, _ = completed
    with pytest.raises(custody.HistoricalResearchCustodyError):
        custody.HistoricalResearchCustodyEvidence.from_bytes(
            mutation(result.evidence_bytes)
        )


@pytest.mark.parametrize("status", [301, 400, 401, 403, 429, 500, 503])
def test_http_failures_do_not_retry_or_publish(vendor, status):
    transport = FakeTransport(vendor)
    transport.status = status
    result, operator, _, store, _ = execute(vendor, transport=transport)
    assert result.state == "STOP_RECONCILIATION_REQUIRED"
    assert len(transport.calls) == 1 and not store.opened
    assert (
        operator.run(
            source_head=HEAD,
            source_tree=TREE,
            attempt_id=ATTEMPT,
            session_authority=vendor[2],
        ).state
        == "STOP_NO_RETRY"
    )
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "mode", ["loop", "replay", "missing", "malformed", "nonfinite", "duplicate-key"]
)
def test_pagination_and_json_fail_closed(vendor, mode):
    transport = FakeTransport(vendor)
    page = json.loads(transport.bars[0])
    if mode == "loop":
        second = json.loads(transport.bars[1])
        second["next_page_token"] = "second"
        transport.bars = (transport.bars[0], wire(second))
    elif mode == "replay":
        transport.bars = (transport.bars[0], transport.bars[0])
    elif mode == "missing":
        page.pop("next_page_token")
        transport.bars = (wire(page),)
    else:
        transport.bars = (
            {
                "malformed": b"{",
                "nonfinite": b'{"x":NaN}',
                "duplicate-key": b'{"x":1,"x":2}',
            }[mode],
        )
    result, _, _, store, _ = execute(vendor, transport=transport)
    assert result.state == "STOP_RECONCILIATION_REQUIRED" and not store.opened
    assert "vendor-raw/bars/0000.json" in store.protected


@pytest.mark.parametrize(
    "change",
    [
        "symbol",
        "feed",
        "adjustment",
        "currency",
        "duplicate",
        "reverse",
        "end",
        "negative",
        "bool-volume",
        "bad-ohlc",
        "missing-session",
    ],
)
def test_vendor_bar_drift_rejected_before_open(vendor, change):
    transport = FakeTransport(vendor)
    page = json.loads(transport.bars[0])
    if change in {"symbol", "feed", "adjustment", "currency"}:
        page[change] = "INVALID"
    elif change == "duplicate":
        page["bars"][1] = page["bars"][0]
    elif change == "reverse":
        page["bars"][0], page["bars"][1] = page["bars"][1], page["bars"][0]
    elif change == "end":
        page["bars"][0]["t"] = "2026-10-24T00:00:00Z"
    elif change == "negative":
        page["bars"][0]["o"] = -1
    elif change == "bool-volume":
        page["bars"][0]["v"] = True
    elif change == "bad-ohlc":
        page["bars"][0]["h"] = 1
    else:
        del page["bars"][2]
    transport.bars = (wire(page), transport.bars[1])
    result, _, _, store, _ = execute(vendor, transport=transport)
    assert result.state == "STOP_RECONCILIATION_REQUIRED" and not store.opened


@pytest.mark.parametrize(
    "group", ["forward_splits", "reorganizations", "unfamiliar_future_group"]
)
def test_continuity_or_unknown_actions_preserved_and_block(vendor, group):
    transport = FakeTransport(vendor)
    transport.actions = (
        wire(
            {"corporate_actions": {group: [{"symbol": "SPY"}]}, "next_page_token": None}
        ),
    )
    result, _, _, store, _ = execute(vendor, transport=transport)
    assert "CONTINUITY_ACTION_REVIEW_REQUIRED" in result.stage
    assert (
        store.protected["vendor-raw/corporate-actions/0000.json"]
        == transport.actions[0]
    )
    assert not store.opened


@pytest.mark.parametrize(
    "failure",
    [
        "prepare",
        "vendor-raw/bars/0000.json",
        "digest",
        "fsync",
        "normalized/holdout/SPY.csv",
        "open",
        "terminal",
    ],
)
def test_partial_state_requires_reconciliation_without_cleanup_or_retry(
    vendor, failure
):
    store = FakeCustody()
    store.fail = failure
    result, _, transport, _, _ = execute(vendor, store=store)
    assert result.state == "STOP_RECONCILIATION_REQUIRED"
    assert SECRET not in repr(result)
    before = dict(store.protected), dict(store.opened), len(transport.calls)
    again, *_ = execute(vendor, store=store, transport=transport)
    assert again.evidence_bytes is None
    assert (store.protected, store.opened, len(transport.calls)) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("custody_root", r"F:\AI\temp"),
        ("open_root", r"F:\AITradingBot"),
        ("owner_sid", "S-1-1-0"),
        ("sddl", "D:(A;;FA;;;WD)"),
        ("local_ntfs", False),
        ("reparse_free", False),
        ("exclusive_destinations", False),
    ],
)
def test_custody_security_rejection_precedes_credentials_and_network(
    vendor, field, value
):
    store = FakeCustody()
    store.inspection = replace(store.inspection, **{field: value})
    result, _, transport, _, credentials = execute(vendor, store=store)
    assert (
        result.evidence_bytes is None and not transport.calls and credentials.reads == 0
    )


def test_calendar_disagreement_blocks_before_open(vendor):
    authority = replace(vendor[2], sessions=vendor[2].sessions[:-1])
    result, _, _, store, _ = execute(vendor, authority=authority)
    assert result.evidence_bytes is None and not store.opened


def test_no_credentials_or_holdout_values_in_public_evidence(vendor, completed):
    result, store = completed
    output = result.evidence_bytes.decode() + repr(result)
    assert SECRET not in output and HOLDOUT_PRICE not in output
    assert "next_page_token" not in output
    assert (
        repr(acquisition.AcquisitionCredentials("key", SECRET))
        == "AcquisitionCredentials(<redacted>)"
    )
    transport = FakeTransport(vendor)
    transport.error = RuntimeError(SECRET + HOLDOUT_PRICE)
    failed, *_ = execute(vendor, transport=transport)
    assert SECRET not in repr(failed) and HOLDOUT_PRICE not in repr(failed)
    assert not any("vendor-raw" in path for path in store.opened)


def test_decimal_context_does_not_change_normalization():
    raw = (
        b'{"symbol":"SPY","bars":[{"t":"2020-01-02T05:00:00Z",'
        b'"o":100.123456789012345678901,"h":101,"l":99,"c":100,"v":42}],'
        b'"next_page_token":null}'
    )
    outputs = []
    for precision in (2, 28, 70):
        with localcontext() as context:
            context.prec = precision
            outputs.append(
                custody.historical_research_normalized_csv(
                    acquisition.normalize_historical_research_bars((raw,))
                )
            )
    assert len(set(outputs)) == 1 and b"100.123456789012345678901" in outputs[0]
    assert Decimal("100.123456789012345678901") > 0


def test_public_open_api_has_no_raw_or_sidecar_capability():
    import inspect

    parameters = inspect.signature(
        custody.verify_historical_research_open_publication
    ).parameters
    assert not any(
        "raw" in name or "sidecar" in name or "path" in name or "expected_hash" in name
        for name in parameters
    )
    source = Path(custody.__file__).read_text()
    assert "verify_historical_research_partition(" not in source
    assert "verify_historical_research_open_commitment(" not in source


def test_source_imports_no_native_network_filesystem_or_trading_effects():
    for module in (acquisition, custody):
        tree = ast.parse(Path(module.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any(
                name.startswith(
                    (
                        "http",
                        "socket",
                        "ctypes",
                        "subprocess",
                        "winreg",
                        "trading_bot.runtime",
                        "trading_bot.review_paper",
                        "trading_bot.supervised_release",
                    )
                )
                for name in names
            )


def test_corporate_actions_paginate_to_exhaustion_without_losing_original_bytes(vendor):
    transport = FakeTransport(vendor)
    first = json.loads(transport.actions[0])
    first["next_page_token"] = "actions-2"
    second = {
        "corporate_actions": {
            "cash_dividends": [
                {
                    "id": "second-dividend",
                    "symbol": "SPY",
                    "process_date": "2026-01-02",
                    "rate": 2,
                }
            ]
        },
        "next_page_token": None,
    }
    transport.actions = wire(first), wire(second)
    result, _, _, store, _ = execute(vendor, transport=transport)
    assert result.evidence_bytes is not None
    assert store.protected["vendor-raw/corporate-actions/0000.json"] == wire(first)
    assert store.protected["vendor-raw/corporate-actions/0001.json"] == wire(second)
    sidecar = store.protected["corporate-actions/sidecar.json"]
    assert wire(first) in sidecar and wire(second) in sidecar
    assert [request.page_token for request in transport.calls] == [
        None,
        "second",
        None,
        "actions-2",
    ]


@pytest.mark.parametrize("mode", ["symbol", "duplicate", "date", "rate", "shape"])
def test_corporate_action_malformed_material_blocks(vendor, mode):
    transport = FakeTransport(vendor)
    page = json.loads(transport.actions[0])
    action = page["corporate_actions"]["cash_dividends"][0]
    if mode == "symbol":
        action["symbol"] = "QQQ"
    elif mode == "duplicate":
        page["corporate_actions"]["cash_dividends"].append(dict(action))
    elif mode == "date":
        action["process_date"] = "2015-12-31"
    elif mode == "rate":
        action["rate"] = True
    else:
        page["corporate_actions"] = []
    transport.actions = (wire(page),)
    result, _, _, store, _ = execute(vendor, transport=transport)
    assert result.evidence_bytes is None and not store.opened


@pytest.mark.parametrize("mode", ["body", "status", "binding", "size"])
def test_response_binding_and_resource_bounds(vendor, monkeypatch, mode):
    class BadTransport(FakeTransport):
        def get(self, request, credentials):
            original = super().get(request, credentials)
            if mode == "body":
                return replace(original, body="not-bytes")
            if mode == "status":
                return replace(original, status=True)
            if mode == "binding":
                return replace(
                    original,
                    request=acquisition.HistoricalResearchRequest(
                        acquisition.AcquisitionStream.CORPORATE_ACTIONS
                    ),
                )
            return original

    if mode == "size":
        monkeypatch.setattr(acquisition, "MAX_STREAM_BYTES", 10)
    result, _, transport, store, _ = execute(vendor, transport=BadTransport(vendor))
    assert (
        result.evidence_bytes is None and not store.opened and len(transport.calls) == 1
    )


def test_pagination_bound_is_terminal(vendor, monkeypatch):
    monkeypatch.setattr(acquisition, "MAX_PAGES", 1)
    result, _, transport, store, _ = execute(vendor)
    assert "PAGINATION_BOUND" in result.stage
    assert len(transport.calls) == 1 and not store.opened


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_head", "invalid"),
        ("source_tree", "invalid"),
        ("attempt_id", "invalid"),
        ("session_authority", None),
    ],
)
def test_source_and_attempt_fail_before_effects(vendor, field, value):
    transport, store, credentials = (
        FakeTransport(vendor),
        FakeCustody(),
        FakeCredentials(),
    )
    operator = acquisition.HistoricalResearchAcquisitionOperator(
        transport, credentials, store
    )
    args = dict(
        source_head=HEAD,
        source_tree=TREE,
        attempt_id=ATTEMPT,
        session_authority=vendor[2],
    )
    args[field] = value
    result = operator.run(**args)
    assert (
        result.evidence_bytes is None
        and not store.events
        and not transport.calls
        and credentials.reads == 0
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b.replace(b"100.25", b"100.26", 1),
        lambda b: b.replace(b"\n", b"\r\n"),
        lambda b: b + b"\n",
    ],
)
def test_open_csv_drift_never_admitted(completed, vendor, monkeypatch, mutation):
    result, store = completed
    monkeypatch.setattr(
        custody, "ACCEPTED_CUSTODY_ADMISSIONS", (admission_for(result.evidence_bytes),)
    )
    monkeypatch.setattr(
        custody, "ACCEPTED_HISTORICAL_SESSION_AUTHORITIES", (vendor[2],)
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        verify(
            result,
            store,
            normalized_open_bytes=mutation(store.opened["normalized/open/SPY.csv"]),
        )


def test_public_manifests_cannot_be_substituted(completed, vendor, monkeypatch):
    result, store = completed
    monkeypatch.setattr(
        custody, "ACCEPTED_CUSTODY_ADMISSIONS", (admission_for(result.evidence_bytes),)
    )
    monkeypatch.setattr(
        custody, "ACCEPTED_HISTORICAL_SESSION_AUTHORITIES", (vendor[2],)
    )
    evidence = custody.HistoricalResearchCustodyEvidence.from_bytes(
        result.evidence_bytes
    )
    with pytest.raises(custody.HistoricalResearchCustodyError, match="membership"):
        verify(
            result,
            store,
            open_manifest=replace(
                evidence.open_manifest, row_count=evidence.open_manifest.row_count + 1
            ),
        )
    with pytest.raises(custody.HistoricalResearchCustodyError, match="exact public"):
        verify(result, store, snapshot=None)


def test_stored_failure_and_no_stdout_leakage(vendor, capsys):
    result, *_ = execute(vendor)
    assert result.evidence_bytes is not None
    assert capsys.readouterr() == ("", "")


def test_oversized_or_nonfinite_numeric_material_rejected():
    template = (
        '{"symbol":"SPY","bars":[{"t":"2020-01-02T05:00:00Z",'
        '"o":%s,"h":101,"l":99,"c":100,"v":42}],"next_page_token":null}'
    )
    for text in ("1e99999999", "true", '"100"'):
        with pytest.raises(custody.HistoricalResearchCustodyError):
            acquisition.normalize_historical_research_bars(
                ((template % text).encode(),)
            )


def test_dependency_cannot_inject_an_open_error_message(vendor):
    transport = FakeTransport(vendor)
    transport.error = acquisition._Stop(SECRET)
    result, *_ = execute(vendor, transport=transport)
    assert SECRET not in result.stage and SECRET not in repr(result)


@pytest.mark.parametrize("mode", ["noncanonical", "count", "fingerprint", "timestamp"])
def test_independent_open_checks_do_not_trust_consistent_evidence(
    completed, vendor, monkeypatch, mode
):
    from uuid import uuid5

    result, store = completed
    original = custody.HistoricalResearchCustodyEvidence.from_bytes(
        result.evidence_bytes
    )
    normalized = store.opened["normalized/open/SPY.csv"]
    manifest = original.open_manifest
    if mode == "noncanonical":
        normalized = normalized.replace(b"\n", b"\r\n")
        manifest = replace(
            manifest,
            normalized_file_sha256=sha256(normalized).hexdigest(),
            normalized_byte_size=len(normalized),
        )
    elif mode == "count":
        manifest = replace(manifest, row_count=manifest.row_count + 1)
    elif mode == "fingerprint":
        manifest = replace(
            manifest, historical_data_fingerprint=uuid5(UUID(int=0), "synthetic-other")
        )
    else:
        manifest = replace(
            manifest, first_bar_timestamp=manifest.first_bar_timestamp.replace(hour=6)
        )
    snapshot = replace(original.snapshot, open_manifest_id=manifest.manifest_id)
    evidence = replace(original, snapshot=snapshot, open_manifest=manifest)
    changed = replace(result, evidence_bytes=evidence.to_bytes())
    monkeypatch.setattr(
        custody, "ACCEPTED_CUSTODY_ADMISSIONS", (admission_for(changed.evidence_bytes),)
    )
    monkeypatch.setattr(
        custody, "ACCEPTED_HISTORICAL_SESSION_AUTHORITIES", (vendor[2],)
    )
    with pytest.raises(
        custody.HistoricalResearchCustodyError,
        match="noncanonical OPEN|physical metadata",
    ):
        verify(changed, store, normalized_open_bytes=normalized)
