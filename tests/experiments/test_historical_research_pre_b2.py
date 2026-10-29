"""Published historical authority and fake-only native B2 security regressions."""

import ctypes
import io
import json
import ssl
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import pytest

import trading_bot.experiments.historical_research_acquisition as acquisition
import trading_bot.experiments.historical_research_b2_preflight as preflight
import trading_bot.experiments.historical_research_custody as custody
import trading_bot.experiments.historical_research_dataset as dataset
import trading_bot.experiments.historical_research_native as native
import trading_bot.experiments.historical_research_native_custody as disk
import trading_bot.experiments.historical_research_sessions as sessions

from .test_historical_research_acquisition_custody import (
    ATTEMPT,
    SECRET,
    admission_for,
    execute,
    verify,
    wire,
)
from .test_historical_research_acquisition_custody import (
    completed as completed,
)
from .test_historical_research_acquisition_custody import (
    vendor as vendor,
)

ROOT = Path(__file__).resolve().parents[2]
NY = ZoneInfo("America/New_York")


def test_frozen_source_manifest_bundle_and_derived_vector():
    evidence = ROOT / "docs/validation/evidence/arch146"
    raw = (evidence / "historical-session-source-manifest.json").read_bytes()
    assert sha256(raw).hexdigest() == sessions.SOURCE_MANIFEST_SHA256
    manifest = json.loads(raw)
    bundle = manifest.pop("bundle_sha256")
    recomputed = sha256(
        json.dumps(
            manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    assert bundle == recomputed == sessions.SOURCE_BUNDLE_SHA256
    assert len(manifest["source_documents"]) == 13
    assert manifest["ordered_source_document_ids"] == [
        item["id"] for item in manifest["source_documents"]
    ]
    closures = json.loads(
        (evidence / "source-derived-full-day-closures.json").read_bytes()
    )
    dates = set()
    for item in closures["full_day_closures"]:
        assert set(item["source_ids"]) <= set(manifest["ordered_source_document_ids"])
        dates.add(date.fromisoformat(item["date"]))
    start, end = date(2016, 1, 1), date(2026, 10, 24)
    derived = tuple(
        start + timedelta(days=i)
        for i in range((end - start).days)
        if (start + timedelta(days=i)).weekday() < 5
        and start + timedelta(days=i) not in dates
    )
    authority = sessions.published_historical_session_authority()
    assert authority.sessions == derived
    assert len(derived) == len(set(derived)) == 2718
    assert derived == tuple(sorted(derived))
    assert (derived[0], derived[-1]) == (date(2016, 1, 4), date(2026, 10, 23))
    assert authority.identity == sessions.AUTHORITY_IDENTITY
    assert authority.digest == sessions.AUTHORITY_DIGEST
    assert custody.ACCEPTED_HISTORICAL_SESSION_AUTHORITIES == (authority,)
    assert custody.ACCEPTED_CUSTODY_ADMISSIONS == ()
    for closure in sessions.MODELED_EXCEPTION_GAP:
        assert closure not in derived
        assert closure - timedelta(days=1) in derived
        assert closure + timedelta(days=1) in derived
    assert sessions.reconcile_historical_session_model(authority) == (
        "REPOSITORY_MODELED_CALENDAR_EXCEPTION_GAP"
    )


def test_global_calendar_source_bytes_unchanged():
    import subprocess

    for relative in (
        "src/trading_bot/market_calendar/nyse.py",
        "src/trading_bot/market_calendar/models.py",
    ):
        original = subprocess.run(
            ["git", "show", "d2e9cbcb08c06eb050ee6d131ba3719d5c82ac42:" + relative],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        assert (ROOT / relative).read_bytes().replace(b"\r\n", b"\n") == original


def test_additional_model_delta_fails(monkeypatch):
    from trading_bot.market_calendar.nyse import NYSEMarketCalendar

    original = NYSEMarketCalendar.sessions_between

    def changed(self, start, end):
        result = original(self, start, end)
        return replace(result, sessions=result.sessions[1:])

    monkeypatch.setattr(NYSEMarketCalendar, "sessions_between", changed)
    with pytest.raises(custody.HistoricalResearchCustodyError, match="delta"):
        sessions.reconcile_historical_session_model(
            sessions.published_historical_session_authority()
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity", "arbitrary-v1"),
        ("source_sha256", "0" * 64),
        ("sessions", sessions.published_historical_session_authority().sessions[:-1]),
    ],
)
def test_unregistered_mutated_authorities_fail_before_claim(vendor, field, value):
    authority = replace(vendor[2], **{field: value})
    result, _, transport, store, credentials = execute(vendor, authority=authority)
    assert result.state == "STOP_RECONCILIATION_REQUIRED"
    assert not store.events and not transport.calls and credentials.reads == 0
    with pytest.raises(custody.HistoricalResearchCustodyError):
        custody.require_accepted_historical_session_authority(authority)


def test_arbitrary_registry_or_parsed_hash_cannot_self_admit(monkeypatch):
    authority = replace(
        sessions.published_historical_session_authority(), identity="parsed-v1"
    )
    monkeypatch.setattr(
        custody, "ACCEPTED_HISTORICAL_SESSION_AUTHORITIES", (authority,)
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        custody.require_accepted_historical_session_authority(authority)


def test_complete_published_custodian_and_unchanged_old_verifier(vendor, completed):
    result, store = completed
    evidence = custody.HistoricalResearchCustodyEvidence.from_bytes(
        result.evidence_bytes
    )
    sidecar = store.protected["corporate-actions/sidecar.json"]
    opened = dataset.HistoricalResearchPartitionMaterial(
        evidence.open_manifest,
        store.opened["normalized/open/SPY.csv"],
        vendor[0],
        sidecar,
    )
    held = dataset.HistoricalResearchPartitionMaterial(
        evidence.holdout_manifest,
        store.protected["normalized/holdout/SPY.csv"],
        vendor[0],
        sidecar,
    )
    receipt = custody.verify_historical_research_custodian_dataset(
        evidence.snapshot, opened, held, vendor[2]
    )
    assert receipt.snapshot == evidence.snapshot
    with pytest.raises(dataset.HistoricalResearchSessionCoverageError):
        dataset.verify_historical_research_partition(opened)
    with pytest.raises(dataset.HistoricalResearchSessionCoverageError):
        dataset.verify_historical_research_dataset(evidence.snapshot, opened, held)
    with pytest.raises(dataset.HistoricalResearchDatasetError, match="raw page"):
        custody.verify_historical_research_custodian_dataset(
            evidence.snapshot,
            replace(opened, raw_vendor_pages=(b"changed",)),
            held,
            vendor[2],
        )
    with pytest.raises(dataset.HistoricalResearchDatasetError, match="fingerprint"):
        custody.verify_historical_research_custodian_dataset(
            replace(
                evidence.snapshot,
                full_historical_data_fingerprint=uuid5(NAMESPACE_URL, "changed"),
            ),
            opened,
            held,
            vendor[2],
        )


@pytest.mark.parametrize(
    "mutation", ["missing", "bush", "carter", "saturday", "duplicate"]
)
def test_published_session_coverage_is_exact(vendor, mutation):
    rows = sum((json.loads(page)["bars"] for page in vendor[0]), [])
    if mutation == "missing":
        rows.pop(50)
    else:
        row = dict(rows[10])
        stamp = {
            "bush": "2018-12-05",
            "carter": "2025-01-09",
            "saturday": "2020-01-04",
            "duplicate": rows[10]["t"][:10],
        }[mutation]
        row["t"] = (
            datetime.combine(date.fromisoformat(stamp), time.min, NY)
            .astimezone(UTC)
            .isoformat()
        )
        if mutation == "duplicate":
            row["t"] = (
                datetime.fromisoformat(row["t"]) + timedelta(hours=1)
            ).isoformat()
        rows.append(row)
        rows.sort(key=lambda item: item["t"])
    changed = (
        (wire({"symbol": "SPY", "bars": rows, "next_page_token": None}),),
        vendor[1],
        vendor[2],
    )
    result, _, _, store, _ = execute(changed)
    assert result.state == "STOP_RECONCILIATION_REQUIRED" and not store.opened


def test_open_publication_accepts_exact_published_sessions(
    completed, vendor, monkeypatch
):
    result, store = completed
    monkeypatch.setattr(
        custody, "ACCEPTED_CUSTODY_ADMISSIONS", (admission_for(result.evidence_bytes),)
    )
    data = verify(result, store)
    actual = tuple(bar.timestamp.astimezone(NY).date() for bar in data.bars)
    assert actual == tuple(day for day in vendor[2].sessions if day < date(2024, 1, 1))
    monkeypatch.setattr(
        custody, "ACCEPTED_HISTORICAL_SESSION_AUTHORITIES", (vendor[2], vendor[2])
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        verify(result, store)


# Synthetic identities cover multiple ordinary operators; no host SID is a pin.
OPERATOR = native.ResearchOperatorToken("S-1-5-21-11-22-33-2001", False, False)


@pytest.fixture
def real_report_seam(monkeypatch):
    """Fake OS/source seams only; never call the real host observer."""
    monkeypatch.setattr(preflight, "_source", lambda *args: None)
    monkeypatch.setattr(preflight, "WindowsB2ReadOnlyObserver", ReadOnlyObserver)
    monkeypatch.setattr(native, "observe_research_operator_token", lambda: OPERATOR)
    monkeypatch.setattr(preflight, "_REAL_PREFLIGHTS", [])
    return preflight.run_real_b2_readonly_preflight(
        Path("."), accepted_head="a" * 40, accepted_tree="b" * 40
    )


def accepted(report):
    return preflight.AcceptedB2Preflight(
        report,
        accepted_report_sha256=sha256(
            preflight.preflight_report_bytes(report)
        ).hexdigest(),
    )


def bound_source(report):
    source = native.EphemeralHistoricalResearchCredentialSource(accepted(report))
    source.bind_acquisition(
        source_head=report.source_head,
        source_tree=report.source_tree,
        session_authority=sessions.published_historical_session_authority(),
    )
    return source


@pytest.mark.parametrize("sid", [OPERATOR.sid, "S-1-5-21-55-66-77-9003"])
def test_ordinary_operator_is_observed_without_fixed_sid(sid):
    observer = ReadOnlyObserver()
    observer.operator_token = lambda: replace(OPERATOR, sid=sid)
    report = preflight.evaluate_b2_preflight_for_test(observer)
    assert report.classification == "SIMULATED_B2_PREREQUISITES_PASS"
    assert report.operator_sid == sid
    assert report.operator_elevated is report.operator_administrator is False
    assert report.credential_source == "EPHEMERAL_INTERACTIVE_RESEARCH_CREDENTIALS"
    assert report.credential_persistence == "NONE"
    assert not any(
        (
            report.credential_secret_reads,
            report.provider_calls,
            report.writes,
            report.acl_mutations,
            report.acquisition_authorized,
        )
    )


@pytest.mark.parametrize("field", ["elevated", "administrator"])
def test_privileged_operator_rejected_before_roots(field):
    observer = ReadOnlyObserver()
    observer.operator_token = lambda: replace(OPERATOR, **{field: True})
    report = preflight.evaluate_b2_preflight_for_test(observer)
    assert report.classification == "BLOCKED_RESEARCH_OPERATOR_TOKEN"
    assert observer.calls == ["close"]
    assert getattr(report, "operator_" + field) is True


@pytest.mark.parametrize(
    "sid",
    ["S-1-5-18", "S-1-5-32-544", "", None, "S-1-5-21-1", "S-1-5-21-1-2-3-4294967296"],
)
def test_non_user_sid_rejected(sid):
    observer = ReadOnlyObserver()
    observer.operator_token = lambda: replace(OPERATOR, sid=sid)
    result = preflight.evaluate_b2_preflight_for_test(observer)
    assert result.classification != preflight.READY
    assert observer.calls == ["close"]


def test_fake_ready_arbitrary_hash_and_copied_reports_cannot_admit(real_report_seam):
    fake = preflight.evaluate_b2_preflight_for_test(ReadOnlyObserver())
    for report in (
        fake,
        replace(fake, classification=preflight.READY),
        replace(real_report_seam),
    ):
        with pytest.raises(custody.HistoricalResearchCustodyError):
            accepted(report)
    with pytest.raises(custody.HistoricalResearchCustodyError):
        preflight.AcceptedB2Preflight(real_report_seam, accepted_report_sha256="0" * 64)


def test_ready_and_unaccepted_objects_cannot_prompt(real_report_seam, monkeypatch):
    monkeypatch.setattr(
        native, "interactive_research_credentials", lambda: pytest.fail("no prompt")
    )
    for report in (None, OPERATOR.sid, real_report_seam, object()):
        source = native.EphemeralHistoricalResearchCredentialSource(report)
        with pytest.raises(custody.HistoricalResearchCustodyError):
            source.read()
        with pytest.raises(custody.HistoricalResearchCustodyError):
            source.bind_acquisition(
                source_head="a" * 40,
                source_tree="b" * 40,
                session_authority=sessions.published_historical_session_authority(),
            )


@pytest.mark.parametrize(
    "change",
    [
        "head",
        "tree",
        "authority",
        "sid",
        "elevated",
        "administrator",
        "requests",
        "custody",
        "source",
    ],
)
def test_acquisition_binding_drift_blocks_before_prompt_or_claim(
    real_report_seam, monkeypatch, vendor, change
):
    report = real_report_seam
    source = native.EphemeralHistoricalResearchCredentialSource(accepted(report))
    monkeypatch.setattr(
        native, "interactive_research_credentials", lambda: pytest.fail("no prompt")
    )
    head, tree, authority = "a" * 40, "b" * 40, vendor[2]
    if change == "head":
        head = "c" * 40
    if change == "tree":
        tree = "c" * 40
    if change == "authority":
        authority = replace(authority, identity="unaccepted")
    if change in ("sid", "elevated", "administrator"):
        token = replace(
            OPERATOR, **{change: "S-1-5-21-55-66-77-8004" if change == "sid" else True}
        )
        monkeypatch.setattr(native, "observe_research_operator_token", lambda: token)
    if change == "requests":
        report.binding["requests"] = ()
    if change == "custody":
        report.binding["custody_sddl"] = "wrong"
    if change == "source":

        def fail(*args):
            raise ValueError("source drift")

        monkeypatch.setattr(preflight, "_source", fail)
    from .test_historical_research_acquisition_custody import FakeCustody, FakeTransport

    store, transport = FakeCustody(), FakeTransport(vendor)
    outcome = acquisition.HistoricalResearchAcquisitionOperator(
        transport, source, store
    ).run(
        source_head=head,
        source_tree=tree,
        attempt_id=ATTEMPT,
        session_authority=authority,
    )
    assert outcome.state == "STOP_RECONCILIATION_REQUIRED"
    assert not store.events and not transport.calls


def test_sid_drift_after_binding_blocks_before_input(real_report_seam, monkeypatch):
    source = bound_source(real_report_seam)
    monkeypatch.setattr(
        native,
        "observe_research_operator_token",
        lambda: replace(OPERATOR, sid="S-1-5-21-55-66-77-8004"),
    )
    monkeypatch.setattr(
        native, "interactive_research_credentials", lambda: pytest.fail("no prompt")
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        source.read()


def test_prompt_follows_claim_and_custody_admission_and_scopes_close(
    real_report_seam, monkeypatch, vendor
):
    from .test_historical_research_acquisition_custody import FakeCustody, FakeTransport

    store, transport = FakeCustody(), FakeTransport(vendor)
    values = acquisition.AcquisitionCredentials("KEY", SECRET)

    def prompt():
        assert store.events and not transport.calls
        assert any("prepare" in str(event).lower() for event in store.events)
        return values

    monkeypatch.setattr(native, "interactive_research_credentials", prompt)
    source = native.EphemeralHistoricalResearchCredentialSource(
        accepted(real_report_seam)
    )
    result = acquisition.HistoricalResearchAcquisitionOperator(
        transport, source, store
    ).run(
        source_head="a" * 40,
        source_tree="b" * 40,
        attempt_id=ATTEMPT,
        session_authority=vendor[2],
    )
    assert result.state == "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION"
    assert values.api_key_id == values.api_secret_key == ""
    assert SECRET not in repr(source) + repr(values) + repr(result) + str(
        result.evidence_bytes
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        source.read()


@pytest.mark.parametrize(
    "value",
    ["", " key", "key ", "a\rb", "a\nb", "a\0b", "x" * 1025, "é" * 513, "\ud800"],
)
def test_interactive_shape_rejection_is_sanitized(monkeypatch, value):
    for stream in (native.sys.stdin, native.sys.stdout, native.sys.stderr):
        monkeypatch.setattr(stream, "isatty", lambda: True)
    monkeypatch.setattr(native.getpass, "getpass", lambda *args: value)
    with pytest.raises(custody.HistoricalResearchCustodyError) as error:
        native.interactive_research_credentials()
    assert str(error.value) == "research credential input rejected"
    assert error.value.__context__ is None


@pytest.mark.parametrize("failure", ["echo", "interrupt", "error", "nonterminal"])
def test_hidden_input_has_no_echo_or_fallback_and_sanitized_errors(
    monkeypatch, failure, capsys
):
    import warnings

    for stream in (native.sys.stdin, native.sys.stdout, native.sys.stderr):
        monkeypatch.setattr(stream, "isatty", lambda: failure != "nonterminal")

    def read(*args):
        if failure == "echo":
            warnings.warn(SECRET, native.getpass.GetPassWarning, stacklevel=2)
        if failure == "interrupt":
            raise KeyboardInterrupt(SECRET)
        if failure == "error":
            raise OSError(SECRET)
        pytest.fail("no fallback input")

    monkeypatch.setattr(native.getpass, "getpass", read)
    monkeypatch.setattr("builtins.input", lambda *args: pytest.fail("no echoed input"))
    monkeypatch.setenv("APCA_API_KEY_ID", SECRET)
    monkeypatch.setenv("APCA_API_SECRET_KEY", SECRET)
    with pytest.raises(custody.HistoricalResearchCustodyError) as error:
        native.interactive_research_credentials()
    assert SECRET not in str(error.value) + repr(error.value)
    assert error.value.__context__ is None
    assert SECRET not in str(capsys.readouterr())


def test_utf8_shape_and_close_and_mutable_copy_cleanup(monkeypatch):
    for stream in (native.sys.stdin, native.sys.stdout, native.sys.stderr):
        monkeypatch.setattr(stream, "isatty", lambda: True)
    values, seen = iter(("é-key", SECRET)), []
    monkeypatch.setattr(native.getpass, "getpass", lambda *args: next(values))
    validate = native.validate_alpaca_credential_bytes

    def track(value):
        seen.append(value)
        validate(value)

    monkeypatch.setattr(native, "validate_alpaca_credential_bytes", track)
    result = native.interactive_research_credentials()
    assert result.api_key_id == "é-key" and len(seen) == 2
    assert all(not any(value) for value in seen)
    result.close()
    with pytest.raises(custody.HistoricalResearchCustodyError):
        result.verify()


def test_no_production_identity_or_persistent_secret_paths(monkeypatch):
    from trading_bot.review_paper import alpaca_windows_credentials

    def fail(*args, **kwargs):
        pytest.fail("production credential access")

    monkeypatch.setattr(
        alpaca_windows_credentials, "read_current_product_alpaca_secrets", fail
    )
    monkeypatch.setattr(
        alpaca_windows_credentials, "read_fixed_current_product_credential", fail
    )
    monkeypatch.setattr(alpaca_windows_credentials, "_WindowsCredentialReader", fail)
    result = preflight.evaluate_b2_preflight_for_test(ReadOnlyObserver())
    assert result.classification == "SIMULATED_B2_PREREQUISITES_PASS"
    text = "\n".join(
        (ROOT / path).read_text()
        for path in (
            "src/trading_bot/experiments/historical_research_native.py",
            "src/trading_bot/experiments/historical_research_b2_preflight.py",
        )
    )
    for forbidden in (
        "TRADING_SID",
        "approved_trading_sid",
        "PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE",
        "read_current_product_alpaca_secrets",
        "CredentialManager",
        "CredRead",
        "CredWrite",
        "ApiKeyId/v",
        "ApiSecretKey/v",
        "environ",
        "getenv",
        "argv",
        "config",
    ):
        # argv belongs solely to nonsecret source identity parsing in preflight.
        if forbidden == "argv":
            assert (
                forbidden
                not in (
                    ROOT / "src/trading_bot/experiments/historical_research_native.py"
                ).read_text()
            )
        else:
            assert forbidden not in text


class Connection:
    def __init__(self, body=b' {"raw":1} \n', status=200, error=False):
        self.body, self.status, self.error = io.BytesIO(body), status, error
        self.requests, self.closed = [], False

    def request(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        if self.error:
            raise OSError(SECRET)

    def getresponse(self):
        return self

    def getheaders(self):
        return []

    def read(self, size):
        return self.body.read(size)

    def close(self):
        self.closed = True


@pytest.mark.parametrize("status", [200, 301, 302, 307, 401, 403, 429, 500, 503])
@pytest.mark.parametrize("stream", list(acquisition.AcquisitionStream))
def test_https_exact_host_endpoint_raw_bytes_and_no_retry(status, stream):
    connection = Connection(status=status)
    factories = []

    def factory(*args, **kwargs):
        factories.append((args, kwargs))
        return connection

    transport = native.HttpsHistoricalResearchTransport.for_test(
        factory, ssl.create_default_context
    )
    request = acquisition.HistoricalResearchRequest(stream, "a&b")
    result = transport.get(request, acquisition.AcquisitionCredentials("KEY", SECRET))
    assert result.body == b' {"raw":1} \n' and result.status == status
    assert len(connection.requests) == len(factories) == 1 and connection.closed
    assert factories[0][0] == ("data.alpaca.markets", 443)
    assert connection.requests[0][0] == ("GET", request.target)
    assert "page_token=a%26b" in request.target and "types=" not in request.target
    assert SECRET not in repr(result)


def test_https_errors_and_bad_tls_are_sanitized_and_bounded():
    connection = Connection(error=True)
    transport = native.HttpsHistoricalResearchTransport.for_test(
        lambda *a, **k: connection, ssl.create_default_context
    )
    request = acquisition.HistoricalResearchRequest(acquisition.AcquisitionStream.BARS)
    credentials = acquisition.AcquisitionCredentials("KEY", SECRET)
    with pytest.raises(custody.HistoricalResearchCustodyError) as error:
        transport.get(request, credentials)
    assert SECRET not in str(error.value) and error.value.__suppress_context__
    assert len(connection.requests) == 1 and connection.closed
    connection = Connection(body=b"x" * (acquisition.MAX_RESPONSE_BYTES + 1))
    transport = native.HttpsHistoricalResearchTransport.for_test(
        lambda *a, **k: connection, ssl.create_default_context
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        transport.get(request, credentials)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    transport = native.HttpsHistoricalResearchTransport.for_test(
        lambda *a, **k: pytest.fail("no request"), lambda: context
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        transport.get(request, credentials)


class DisposableNative:
    """Real create-only fsync/readback in disposable roots; no fixed-root access."""

    def __init__(self, root):
        self.root, self.events, self.fail = root, [], None
        self.fresh = disk.CustodyFreshState("FRESH", True, True, True, True, True, True)

    def local(self, path):
        return (
            self.root
            / ("open" if path.startswith(custody.OPEN_ROOT) else "protected")
            / path.replace(":", "").replace("\\", "/")
        )

    def observe_fresh(self):
        self.events.append("observe")
        return self.fresh

    def create_directory(self, path, *, opened):
        self.events.append(("directory", path, opened))
        local = self.local(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.mkdir()

    def create_file(self, path, body, *, opened):
        import os

        self.events.append(("create", path, opened))
        local = self.local(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        with local.open("xb") as target:
            target.write(body)
            target.flush()
            os.fsync(target.fileno())
        assert local.read_bytes() == body
        return acquisition.PersistenceReceipt(
            path, sha256(body).hexdigest(), len(body), self.fail != "flush"
        )

    def inspect_created(self, paths):
        self.events.append("inspect")
        if self.fail == "security":
            raise OSError(SECRET)

    def close(self):
        self.events.append("close")


def test_native_custody_complete_protocol_disposable_roots(vendor, tmp_path):
    backend = DisposableNative(tmp_path)
    store = disk.WindowsHistoricalResearchCustody.for_test(backend)
    result, _, transport, _, credentials = execute(vendor, store=store)
    assert result.state == "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION"
    creates = [
        event
        for event in backend.events
        if isinstance(event, tuple) and event[0] == "create"
    ]
    assert creates[0][1] == disk.ATTEMPT_CLAIM_PATH
    assert len(transport.calls) == 3 and credentials.reads == 1
    assert all(
        not opened
        for _, path, opened in creates
        if "vendor-raw" in path
        or "sidecar" in path
        or "holdout/SPY" in path.replace("\\", "/")
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        store.claim_attempt(ATTEMPT, acquisition.CustodyPersistencePlan())


@pytest.mark.parametrize(
    "field",
    [
        "local_ntfs",
        "non_reparse",
        "parent_policy",
        "claim_absent",
        "protected_absent",
        "open_absent",
    ],
)
def test_custody_unproven_state_precedes_effects(tmp_path, field):
    backend = DisposableNative(tmp_path)
    backend.fresh = replace(backend.fresh, **{field: False})
    store = disk.WindowsHistoricalResearchCustody.for_test(backend)
    with pytest.raises(custody.HistoricalResearchCustodyError):
        store.claim_attempt(ATTEMPT, acquisition.CustodyPersistencePlan())
    assert not list(tmp_path.iterdir())


def test_custody_flush_ambiguity_is_consumed_no_cleanup(tmp_path):
    backend = DisposableNative(tmp_path)
    backend.fail = "flush"
    store = disk.WindowsHistoricalResearchCustody.for_test(backend)
    with pytest.raises(custody.HistoricalResearchCustodyError):
        store.claim_attempt(ATTEMPT, acquisition.CustodyPersistencePlan())
    assert list(tmp_path.rglob("*.json"))
    with pytest.raises(custody.HistoricalResearchCustodyError):
        store.claim_attempt(ATTEMPT, acquisition.CustodyPersistencePlan())
    assert sum(isinstance(e, tuple) and e[0] == "create" for e in backend.events) == 1


@pytest.mark.parametrize(
    "path",
    ["../x", "vendor-raw/bars/../x", "C:/x", "x:stream", "normalized/open/SPY.csv"],
)
def test_custody_path_injection_rejected_before_write(tmp_path, path):
    store = disk.WindowsHistoricalResearchCustody.for_test(DisposableNative(tmp_path))
    with pytest.raises(custody.HistoricalResearchCustodyError):
        store.persist_protected(path, b"x")
    assert not list(tmp_path.iterdir())


class ReadOnlyObserver:
    def __init__(self):
        self.calls = []

    def operator_token(self):
        self.calls.append("token")
        return OPERATOR

    def fresh_state(self):
        self.calls.append("fresh")
        return disk.CustodyFreshState("FRESH", True, True, True, True, True, True)

    def close(self):
        self.calls.append("close")


def test_pure_preflight_closed_and_simulation_never_real_ready(monkeypatch):
    observer = ReadOnlyObserver()
    result = preflight.evaluate_b2_preflight_for_test(observer)
    assert observer.calls == ["token", "fresh", "token", "close"]
    assert result.operator_sid == OPERATOR.sid
    assert result.binding["credential_source"] == native.CREDENTIAL_SOURCE
    assert result.classification == "SIMULATED_B2_PREREQUISITES_PASS"
    assert result.classification != preflight.READY
    assert (
        result.credential_secret_reads,
        result.provider_calls,
        result.writes,
        result.acl_mutations,
    ) == (0, 0, 0, 0)
    assert result.acquisition_authorized is False
    assert (
        result.session_count == 2718
        and result.authority_digest == sessions.AUTHORITY_DIGEST
    )
    assert result.binding["requests"] == custody.frozen_request_descriptors()
    assert SECRET not in json.dumps(asdict(result))


def test_real_preflight_rejects_source_before_constructing_observer(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        preflight, "WindowsB2ReadOnlyObserver", lambda: pytest.fail("no real observer")
    )
    with pytest.raises(ValueError):
        preflight.run_real_b2_readonly_preflight(
            tmp_path, accepted_head="a" * 40, accepted_tree="b" * 40
        )


class Win32Seam:
    def __init__(self, failure=None):
        self.events = []
        self.body = b""
        self.failure = failure

    def api(self, library, name, arguments, result):
        def call(*args):
            self.events.append((name, args))
            if name == "CreateFileW":
                return 71
            if name == "GetDriveTypeW":
                return 3
            if name == "ConvertStringSecurityDescriptorToSecurityDescriptorW":
                args[2]._obj.value = 123
                return 1
            if name == "LocalFree":
                return None
            if name == "WriteFile":
                self.body = ctypes.string_at(args[1], args[2])
                args[3]._obj.value = len(self.body) - (self.failure == "short_write")
                return 1
            if name == "ReadFile":
                body = b"different" if self.failure == "readback" else self.body
                ctypes.memmove(args[1], body, len(body))
                args[3]._obj.value = len(body)
                return 1
            if name == "FlushFileBuffers" and self.failure == "flush":
                return 0
            return 1

        return call


def _fake_inspection(handle, path, kind):
    flags = 3 if kind is disk.AuthorityObjectKind.DIRECTORY else 0
    return SimpleNamespace(
        owner_sid=disk.ADMIN,
        dacl_protected=True,
        aces=tuple(
            SimpleNamespace(
                principal_sid=sid, access_mask=0x1F01FF, ace_type=0, ace_flags=flags
            )
            for sid in (disk.ADMIN, disk.SYSTEM)
        ),
    )


@pytest.mark.parametrize(
    "failure", [None, "short_write", "flush", "readback", "hardlink"]
)
def test_win32_create_new_flush_same_handle_readback_and_link_security(
    monkeypatch, failure
):
    backend = disk.WindowsCustodyNative()
    seam = Win32Seam(failure)
    monkeypatch.setattr(backend, "_api", seam.api)
    monkeypatch.setattr(disk, "inspect_open_authority_object", _fake_inspection)
    monkeypatch.setattr(
        disk,
        "inspect_security_object_identity",
        lambda handle: (11, 22, 2 if failure == "hardlink" else 1),
    )
    body = b"non-price durable claim"
    if failure:
        with pytest.raises(custody.HistoricalResearchCustodyError):
            backend.create_file(disk.ATTEMPT_CLAIM_PATH, body, opened=False)
    else:
        backend.create_file(disk.ATTEMPT_CLAIM_PATH, body, opened=False).verify(
            disk.ATTEMPT_CLAIM_PATH, body
        )
    creates = [
        args
        for name, args in seam.events
        if name == "CreateFileW" and args[0] == disk.ATTEMPT_CLAIM_PATH
    ]
    assert len(creates) == 1
    assert creates[0][2] == 0 and creates[0][4] == 1
    assert creates[0][5] & 0x00200000 and creates[0][5] & 0x80000000
    assert all(
        args[4] == 3 and args[5] & 0x00200000
        for name, args in seam.events
        if name == "CreateFileW" and args[0].endswith("\\")
    )
    names = [name for name, args in seam.events]
    if failure is None:
        assert (
            names.index("WriteFile")
            < names.index("FlushFileBuffers")
            < names.index("ReadFile")
        )
        assert names.count("FlushFileBuffers") == 2
    assert names[-1] == "CloseHandle"
    backend.close()


@pytest.mark.parametrize("change", ["owner", "dacl", "extra_ace", "inheritance"])
def test_native_exact_owner_dacl_policy_rejects_drift(monkeypatch, change):
    backend = disk.WindowsCustodyNative()

    def inspection(handle, path, kind):
        result = _fake_inspection(handle, path, kind)
        if change == "owner":
            result.owner_sid = disk.USERS
        if change == "dacl":
            result.dacl_protected = False
        if change == "extra_ace":
            result.aces += result.aces[:1]
        if change == "inheritance":
            result.aces[0].ace_flags = 16
        return result

    monkeypatch.setattr(disk, "inspect_open_authority_object", inspection)
    with pytest.raises(custody.HistoricalResearchCustodyError):
        backend._security(71, custody.CUSTODY_ROOT, directory=True, opened=False)


def test_native_reparse_ntfs_rejection_is_closed(monkeypatch):
    backend = disk.WindowsCustodyNative()
    seam = Win32Seam()
    monkeypatch.setattr(backend, "_api", seam.api)

    def reject(*args):
        raise ValueError("fake reparse/non-NTFS")

    monkeypatch.setattr(disk, "inspect_open_authority_object", reject)
    with pytest.raises(ValueError):
        backend._open(custody.CUSTODY_ROOT)
    assert seam.events[-1][0] == "CloseHandle"


def test_146a_ast_reconstruction_rejects_semantic_drift(tmp_path):
    from scripts.arch146_source_authority import (
        DATASET_SOURCE,
        dataset_preserves_146a_contract,
    )

    from scripts import checkpoint_runner

    pin = checkpoint_runner.ARCH146A_SOURCE_PINS[DATASET_SOURCE]
    assert dataset_preserves_146a_contract(ROOT, pin)
    target = tmp_path / DATASET_SOURCE
    target.parent.mkdir(parents=True)
    source = (ROOT / DATASET_SOURCE).read_text()
    for changed in (
        source.replace("validate_historical_research_session_coverage(data)", "pass"),
        source.replace('"multiple daily bars for one XNYS session"', '"weakened"'),
        source.replace('"raw page digest/order mismatch"', '"weakened"'),
    ):
        target.write_text(changed)
        assert not dataset_preserves_146a_contract(tmp_path, pin)


@pytest.mark.parametrize(
    "headers",
    [
        [("Content-Length", "999")],
        [("Content-Length", "1"), ("Content-Length", "1")],
        [("Content-Length", "1"), ("Transfer-Encoding", "chunked")],
        [("Content-Encoding", "gzip")],
    ],
)
def test_http_framing_failure_is_closed_without_retry(headers):
    connection = Connection()
    connection.getheaders = lambda: headers
    transport = native.HttpsHistoricalResearchTransport.for_test(
        lambda *a, **k: connection, ssl.create_default_context
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        transport.get(
            acquisition.HistoricalResearchRequest(acquisition.AcquisitionStream.BARS),
            acquisition.AcquisitionCredentials("KEY", SECRET),
        )
    assert len(connection.requests) == 1 and connection.closed


def test_error_body_and_non_json_header_are_preserved():
    body = b"exact non-json error entity"
    connection = Connection(body=body, status=403)
    connection.getheaders = lambda: [
        ("Content-Type", "text/plain"),
        ("Content-Length", str(len(body))),
    ]
    transport = native.HttpsHistoricalResearchTransport.for_test(
        lambda *a, **k: connection, ssl.create_default_context
    )
    result = transport.get(
        acquisition.HistoricalResearchRequest(acquisition.AcquisitionStream.BARS),
        acquisition.AcquisitionCredentials("KEY", SECRET),
    )
    assert result.status == 403 and result.body == body


def test_preflight_invalid_sid_blocks_before_root_observation():
    observer = ReadOnlyObserver()
    observer.operator_token = lambda: replace(OPERATOR, sid="S-1-5-21-1")
    result = preflight.evaluate_b2_preflight_for_test(observer)
    assert result.classification == "BLOCKED_HOST_FRESHNESS_OR_POLICY_UNPROVEN"
    assert observer.calls == ["close"]
    assert (
        result.credential_secret_reads
        == result.provider_calls
        == result.writes
        == result.acl_mutations
        == 0
    )


@pytest.mark.parametrize(
    "field",
    [
        "local_ntfs",
        "non_reparse",
        "parent_policy",
        "claim_absent",
        "protected_absent",
        "open_absent",
    ],
)
def test_pure_preflight_freshness_security_failures_never_ready(field):
    observer = ReadOnlyObserver()
    observer.fresh_state = lambda: replace(
        disk.CustodyFreshState("FRESH", True, True, True, True, True, True),
        **{field: False},
    )
    result = preflight.evaluate_b2_preflight_for_test(observer)
    assert result.classification == "BLOCKED_HOST_FRESHNESS_OR_POLICY_UNPROVEN"
    assert result.acquisition_authorized is False


@pytest.mark.parametrize("attributes", [None, 0, 4, 16, 20, 7, 23])
@pytest.mark.parametrize("elevated", [False, True])
def test_native_effective_admin_facts_and_preflight(monkeypatch, attributes, elevated):
    observation = SimpleNamespace(
        user_sid=OPERATOR.sid,
        elevated=elevated,
        token_type=1,
        thread_token_present=False,
        groups=() if attributes is None else ((native.ADMINISTRATORS_SID, attributes),),
    )
    monkeypatch.setattr(
        native,
        "WindowsTradingTokenObserver",
        lambda: SimpleNamespace(observe=lambda: observation),
    )
    token = native.observe_research_operator_token()
    administrator = attributes in (4, 7)
    assert token.administrator is administrator
    observer = ReadOnlyObserver()
    observer.operator_token = native.observe_research_operator_token
    report = preflight.evaluate_b2_preflight_for_test(observer)
    assert report.operator_administrator is administrator
    assert report.operator_elevated is elevated
    if administrator or elevated:
        with pytest.raises(custody.HistoricalResearchCustodyError):
            token.verify()
        assert report.classification == "BLOCKED_RESEARCH_OPERATOR_TOKEN"
        assert observer.calls == ["close"]
    else:
        token.verify()
        assert report.classification == "SIMULATED_B2_PREREQUISITES_PASS"
    assert report.classification != preflight.READY
    assert report.credential_secret_reads == report.provider_calls == 0
    assert report.writes == report.acl_mutations == 0
    assert report.acquisition_authorized is False


@pytest.mark.parametrize("changes", [{"token_type": 2}, {"thread_token_present": True}])
def test_native_nonprimary_or_impersonated_token_stays_rejected(monkeypatch, changes):
    observation = SimpleNamespace(
        user_sid=OPERATOR.sid,
        elevated=False,
        token_type=1,
        thread_token_present=False,
        groups=(),
    )
    for key, value in changes.items():
        setattr(observation, key, value)
    monkeypatch.setattr(
        native,
        "WindowsTradingTokenObserver",
        lambda: SimpleNamespace(observe=lambda: observation),
    )
    with pytest.raises(custody.HistoricalResearchCustodyError):
        native.observe_research_operator_token()
    observer = ReadOnlyObserver()
    observer.operator_token = native.observe_research_operator_token
    report = preflight.evaluate_b2_preflight_for_test(observer)
    assert report.classification != preflight.READY
    assert observer.calls == ["close"]
    assert report.credential_secret_reads == report.provider_calls == 0
    assert report.writes == report.acl_mutations == 0
    assert report.acquisition_authorized is False


@pytest.mark.parametrize(
    "before,after",
    [
        ("and attributes & SE_GROUP_ENABLED", ""),
        ("and not attributes & SE_GROUP_USE_FOR_DENY_ONLY", ""),
        ("sid == ADMINISTRATORS_SID", 'sid == "S-1-5-32-544"'),
        ("and not attributes & SE_GROUP_USE_FOR_DENY_ONLY", "and True"),
    ],
)
def test_current_authority_rejects_raw_or_incomplete_admin_semantics(
    tmp_path, before, after
):
    from scripts.arch146_source_authority import research_credential_boundary_isolated

    relative = Path("src/trading_bot/experiments/historical_research_native.py")
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    for name in (
        "historical_research_native.py",
        "historical_research_b2_preflight.py",
    ):
        source = relative.parent / name
        (tmp_path / source).write_text((ROOT / source).read_text(), encoding="utf-8")
    assert research_credential_boundary_isolated(tmp_path)
    text = target.read_text()
    assert before in text
    target.write_text(text.replace(before, after), encoding="utf-8")
    assert not research_credential_boundary_isolated(tmp_path)


@pytest.mark.parametrize("failure", ["transport", "custody", "input"])
def test_acquisition_secret_scope_closed_on_failure(
    real_report_seam, monkeypatch, vendor, failure
):
    from .test_historical_research_acquisition_custody import FakeCustody, FakeTransport

    store, transport = FakeCustody(), FakeTransport(vendor)
    value = acquisition.AcquisitionCredentials("KEY", SECRET)
    if failure == "transport":
        transport.error = OSError(SECRET)
    if failure == "custody":
        store.fail = "vendor-raw/bars/0000.json"

    def prompt():
        if failure == "input":
            raise OSError(SECRET)
        return value

    monkeypatch.setattr(native, "interactive_research_credentials", prompt)
    source = native.EphemeralHistoricalResearchCredentialSource(
        accepted(real_report_seam)
    )
    outcome = acquisition.HistoricalResearchAcquisitionOperator(
        transport, source, store
    ).run(
        source_head="a" * 40,
        source_tree="b" * 40,
        attempt_id=ATTEMPT,
        session_authority=vendor[2],
    )
    assert outcome.state == "STOP_RECONCILIATION_REQUIRED"
    assert SECRET not in repr(outcome) + repr(source) + str(store.events)
    if failure != "input":
        assert value.api_key_id == value.api_secret_key == ""
    with pytest.raises(custody.HistoricalResearchCustodyError):
        source.read()


@pytest.mark.parametrize(
    "injection",
    [
        "from trading_bot.review_paper.unattended_host_identity import TRADING_SID",
        "approved_trading_sid = 'arbitrary'",
        "research_sid = 'S-1-5-21-1-2-3-1005'",
        (
            "from trading_bot.review_paper.alpaca_windows_credentials "
            "import ScopedAlpacaSecrets"
        ),
        "credential_target = 'AITradingBot/MarketData/Alpaca/ApiKeyId/v3'",
        "read_current_product_alpaca_secrets()",
        "os.environ['APCA_API_KEY_ID']",
    ],
)
def test_current_authority_rejects_production_coupling(tmp_path, injection):
    from scripts.arch146_source_authority import research_credential_boundary_isolated

    for name in (
        "historical_research_native.py",
        "historical_research_b2_preflight.py",
    ):
        relative = Path("src/trading_bot/experiments") / name
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / relative).read_text(), encoding="utf-8")
    assert research_credential_boundary_isolated(tmp_path)
    target.write_text(target.read_text() + "\n" + injection + "\n", encoding="utf-8")
    assert not research_credential_boundary_isolated(tmp_path)
