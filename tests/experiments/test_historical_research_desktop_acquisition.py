"""Architecture 147 P2: synthetic data, hidden-input fakes and temporary roots."""

import ast
import json
import subprocess
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, time
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import acquire_desktop_research as cli
from trading_bot.experiments import historical_research_acquisition as kernel
from trading_bot.experiments import historical_research_desktop as desktop
from trading_bot.experiments import historical_research_desktop_acquisition as bridge
from trading_bot.experiments import historical_research_native as native
from trading_bot.experiments.historical_research_custody import (
    published_historical_session_authority,
)

HEAD, TREE = "a" * 40, "b" * 40
ATTEMPT = "b96e81a1-d562-493c-949a-84a6b757699b"
SECRET = "SYNTHETIC_P2_SECRET_DO_NOT_PRINT"
ROOT = Path(__file__).resolve().parents[2]


def forbidden(*args, **kwargs):
    pytest.fail("forbidden effect")


@pytest.fixture(autouse=True)
def no_real_effects(monkeypatch):
    monkeypatch.setattr(native, "interactive_research_credentials", forbidden)
    monkeypatch.setattr(native.HttpsHistoricalResearchTransport, "get", forbidden)
    monkeypatch.setattr(native, "observe_research_operator_token", forbidden)
    monkeypatch.setattr(bridge, "interactive_research_credentials", forbidden)


@pytest.fixture(scope="module")
def vendor():
    rows = []
    for day in published_historical_session_authority().sessions:
        stamp = datetime.combine(day, time.min, ZoneInfo("America/New_York"))
        rows.append(
            {
                "t": stamp.astimezone(UTC).isoformat(),
                "o": 123.25,
                "h": 124.25,
                "l": 122.25,
                "c": 123.25,
                "v": 42,
            }
        )
    return (
        json.dumps(
            {"symbol": "SPY", "bars": rows[:-100], "next_page_token": "p2"}
        ).encode(),
        json.dumps(
            {"symbol": "SPY", "bars": rows[-100:], "next_page_token": None}
        ).encode(),
        b'{"corporate_actions":{"cash_dividends":[{"id":"synthetic","symbol":"SPY",'
        b'"process_date":"2025-01-02","rate":1.5}]},"next_page_token":null}',
    )


class FakeTransport:
    def __init__(self, vendor, events):
        self.vendor, self.events, self.requests = vendor, events, []

    def get(self, request, credentials):
        assert self.events == ["prompt"]
        assert credentials.api_secret_key == SECRET
        self.requests.append(request)
        if request.stream is kernel.AcquisitionStream.CORPORATE_ACTIONS:
            body = self.vendor[2]
        else:
            body = self.vendor[0 if request.page_token is None else 1]
        return kernel.HistoricalResearchResponse(request, 200, body)


@pytest.fixture
def composition(tmp_path, monkeypatch, vendor):
    events = []
    storage = desktop.DesktopResearchStorage.for_test(tmp_path / "desktop-v1")

    def prompt():
        assert storage.root.is_dir()
        assert (storage.root / "raw/bars").is_dir()
        assert events == []
        events.append("prompt")
        return kernel.AcquisitionCredentials("SYNTHETIC_KEY", SECRET)

    monkeypatch.setattr(bridge, "interactive_research_credentials", prompt)
    return storage, FakeTransport(vendor, events), events


def acquire(composition):
    storage, transport, _ = composition
    return bridge.acquire_desktop_research(
        bridge.DesktopAcquisitionSource(HEAD, TREE),
        attempt_id=ATTEMPT,
        storage=storage,
        transport=transport,
    )


@pytest.mark.parametrize(
    "head,tree", [("", TREE), (HEAD, ""), ("A" * 40, TREE), (HEAD, "c" * 39)]
)
def test_adapter_requires_exact_valid_identities(head, tree):
    with pytest.raises(bridge.DesktopAcquisitionError):
        bridge.DesktopInteractiveResearchCredentialSource(
            expected_head=head, expected_tree=tree
        )


@pytest.mark.parametrize("binding", ["head", "tree", "authority"])
def test_bad_binding_rejects_without_prompt_and_is_consumed(binding):
    source = bridge.DesktopInteractiveResearchCredentialSource(
        expected_head=HEAD, expected_tree=TREE
    )
    authority = published_historical_session_authority()
    if binding == "authority":
        authority = replace(authority, identity="unaccepted")
    kwargs = dict(
        source_head="c" * 40 if binding == "head" else HEAD,
        source_tree="d" * 40 if binding == "tree" else TREE,
        session_authority=authority,
    )
    with pytest.raises(bridge.DesktopAcquisitionError):
        source.bind_acquisition(**kwargs)
    with pytest.raises(bridge.DesktopAcquisitionError):
        source.read()
    with pytest.raises(bridge.DesktopAcquisitionError):
        source.bind_acquisition(
            source_head=HEAD,
            source_tree=TREE,
            session_authority=published_historical_session_authority(),
        )


@pytest.mark.parametrize("reject", [False, True])
def test_adapter_prompts_once_and_never_retains_secrets(monkeypatch, reject):
    calls = []

    def prompt():
        calls.append(1)
        if reject:
            raise ValueError(SECRET)
        return kernel.AcquisitionCredentials("KEY", SECRET)

    monkeypatch.setattr(bridge, "interactive_research_credentials", prompt)
    source = bridge.DesktopInteractiveResearchCredentialSource(
        expected_head=HEAD, expected_tree=TREE
    )
    with pytest.raises(bridge.DesktopAcquisitionError):
        source.read()
    assert calls == []
    source.bind_acquisition(
        source_head=HEAD,
        source_tree=TREE,
        session_authority=published_historical_session_authority(),
    )
    if reject:
        with pytest.raises(bridge.DesktopAcquisitionError) as error:
            source.read()
        assert error.value.__context__ is None
        assert SECRET not in repr(error.value)
    else:
        credentials = source.read()
        assert SECRET not in repr(credentials)
        credentials.close()
    with pytest.raises(bridge.DesktopAcquisitionError):
        source.read()
    assert calls == [1]
    assert SECRET not in repr(source) + repr(vars(source))


def git_fake(monkeypatch, root, changes=None):
    values = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): "develop",
        ("rev-parse", "HEAD"): HEAD,
        ("rev-parse", "HEAD^{tree}"): TREE,
        ("status", "--porcelain=v1", "--untracked-files=no"): "",
        ("remote", "get-url", "origin"): bridge.CANONICAL_ORIGIN,
        ("rev-parse", "refs/remotes/origin/develop"): HEAD,
    }
    values.update(changes or {})
    calls = []
    monkeypatch.setattr(bridge, "CANONICAL_PROJECT_ROOT", root)

    def run(args, **kwargs):
        assert args[:3] == ["git", "-C", str(root)]
        assert kwargs["check"] and kwargs["capture_output"]
        key = tuple(args[3:])
        calls.append(key)
        return subprocess.CompletedProcess(args, 0, values[key], "")

    monkeypatch.setattr(bridge.subprocess, "run", run)
    return calls


@pytest.mark.parametrize(
    "command,value",
    [
        (("rev-parse", "--show-toplevel"), "wrong-root"),
        (
            ("branch", "--show-current"),
            "feature/research-desktop-product-pivot-current",
        ),
        (("rev-parse", "HEAD"), "c" * 40),
        (("rev-parse", "HEAD^{tree}"), "d" * 40),
        (("status", "--porcelain=v1", "--untracked-files=no"), " M tracked.py"),
        (("status", "--porcelain=v1", "--untracked-files=no"), "M  indexed.py"),
        (("remote", "get-url", "origin"), "https://example.invalid/other.git"),
        (("rev-parse", "refs/remotes/origin/develop"), "e" * 40),
    ],
)
def test_source_failures_precede_storage_prompt_provider(
    monkeypatch, tmp_path, command, value
):
    git_fake(monkeypatch, tmp_path, {command: value})
    monkeypatch.setattr(bridge.DesktopResearchStorage, "production", forbidden)
    monkeypatch.setattr(bridge, "HttpsHistoricalResearchTransport", forbidden)
    with pytest.raises(
        bridge.DesktopAcquisitionError, match="SOURCE_IDENTITY_MISMATCH"
    ):
        bridge.run_production_acquisition(
            tmp_path, expected_head=HEAD, expected_tree=TREE, attempt_id=ATTEMPT
        )


def test_noncanonical_repository_rejects_before_git(monkeypatch, tmp_path):
    git_fake(monkeypatch, tmp_path)
    monkeypatch.setattr(bridge.subprocess, "run", forbidden)
    with pytest.raises(bridge.DesktopAcquisitionError):
        bridge.verify_desktop_acquisition_source(
            tmp_path / "other", expected_head=HEAD, expected_tree=TREE
        )


def test_untracked_residue_is_ignored_without_enumeration(monkeypatch, tmp_path):
    (tmp_path / "unrelated-artifact").write_bytes(b"preserve")
    calls = git_fake(monkeypatch, tmp_path)
    source = bridge.verify_desktop_acquisition_source(
        tmp_path, expected_head=HEAD, expected_tree=TREE
    )
    assert source == bridge.DesktopAcquisitionSource(HEAD, TREE)
    assert [c for c in calls if c[0] == "status"] == [
        ("status", "--porcelain=v1", "--untracked-files=no")
    ]
    assert (tmp_path / "unrelated-artifact").read_bytes() == b"preserve"


def test_authority_validation_precedes_storage_construction(monkeypatch, tmp_path):
    git_fake(monkeypatch, tmp_path)
    monkeypatch.setattr(bridge.DesktopResearchStorage, "production", forbidden)
    monkeypatch.setattr(bridge, "published_historical_session_authority", lambda: None)
    with pytest.raises(ValueError):
        bridge.run_production_acquisition(
            tmp_path, expected_head=HEAD, expected_tree=TREE, attempt_id=ATTEMPT
        )


def test_binding_failure_precedes_kernel_storage_and_provider(monkeypatch, tmp_path):
    source = bridge.DesktopInteractiveResearchCredentialSource(
        expected_head="c" * 40, expected_tree=TREE
    )
    storage = desktop.DesktopResearchStorage.for_test(tmp_path / "desktop-v1")
    monkeypatch.setattr(storage, "prepare", forbidden)
    result = kernel.HistoricalResearchAcquisitionOperator(
        object(), source, storage
    ).run(
        source_head=HEAD,
        source_tree=TREE,
        attempt_id=ATTEMPT,
        session_authority=published_historical_session_authority(),
    )
    assert result.state == "STOP_RECONCILIATION_REQUIRED"
    assert not storage.root.exists()


def test_production_composition_is_fixed_and_ordered(monkeypatch, tmp_path):
    calls = git_fake(monkeypatch, tmp_path)
    events = []
    storage = desktop.DesktopResearchStorage.for_test(tmp_path / "desktop-v1")
    monkeypatch.setattr(bridge, "DESKTOP_RESEARCH_ROOT", storage.root)

    def production():
        assert len(calls) == 7
        events.append("storage")
        return storage

    def compose(source, *, attempt_id, storage, transport):
        assert events == ["storage"]
        assert source == bridge.DesktopAcquisitionSource(HEAD, TREE)
        assert attempt_id == ATTEMPT and storage.test_only
        assert type(transport) is native.HttpsHistoricalResearchTransport
        return {"status": "synthetic"}

    monkeypatch.setattr(bridge.DesktopResearchStorage, "production", production)
    monkeypatch.setattr(bridge, "acquire_desktop_research", compose)
    assert bridge.run_production_acquisition(
        tmp_path, expected_head=HEAD, expected_tree=TREE, attempt_id=ATTEMPT
    ) == {"status": "synthetic"}


def test_preexisting_production_root_precedes_storage_construction(
    monkeypatch, tmp_path
):
    git_fake(monkeypatch, tmp_path)
    root = tmp_path / "desktop-v1"
    root.mkdir()
    monkeypatch.setattr(bridge, "DESKTOP_RESEARCH_ROOT", root)
    monkeypatch.setattr(bridge.DesktopResearchStorage, "production", forbidden)
    monkeypatch.setattr(bridge, "HttpsHistoricalResearchTransport", forbidden)
    with pytest.raises(bridge.DesktopAcquisitionError, match="PREEXISTING_DESTINATION"):
        bridge.run_production_acquisition(
            tmp_path, expected_head=HEAD, expected_tree=TREE, attempt_id=ATTEMPT
        )


@pytest.mark.parametrize("failure", ["cli-source", "exception"])
def test_cli_failure_output_is_only_sanitized_metadata(monkeypatch, capsys, failure):
    def run(*args, **kwargs):
        if failure == "cli-source":
            raise bridge.DesktopAcquisitionError("SOURCE", "SOURCE_IDENTITY_MISMATCH")
        raise OSError(SECRET)

    monkeypatch.setattr(cli, "run_production_acquisition", run)
    assert (
        cli.main(["--execute", "--expected-head", HEAD, "--expected-tree", TREE]) == 1
    )
    output = capsys.readouterr()
    assert set(json.loads(output.out)) == {"stage", "classification"}
    assert SECRET not in str(output)


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--root", SECRET],
        ["--symbol", "QQQ"],
        ["--feed", "iex"],
        ["--start", "2020-01-01"],
        ["--execute", "--expected-head", HEAD],
    ],
)
def test_cli_shape_fails_sanitized_before_dispatch(monkeypatch, capsys, extra):
    monkeypatch.setattr(cli, "run_production_acquisition", forbidden)
    argv = (
        extra
        if not extra or extra[0] == "--execute"
        else ["--execute", "--expected-head", HEAD, "--expected-tree", TREE, *extra]
    )
    assert cli.main(argv) == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {
        "stage": "CLI",
        "classification": "INVALID_INVOCATION",
    }
    assert SECRET not in str(output)


@pytest.mark.parametrize("kind", ["empty", "partial", "file"])
def test_existing_root_stops_before_prompt_provider(composition, kind):
    storage, transport, events = composition
    if kind == "file":
        storage.root.write_bytes(b"preserve")
    else:
        storage.root.mkdir()
        if kind == "partial":
            (storage.root / "partial").write_bytes(b"preserve")
    with pytest.raises(bridge.DesktopAcquisitionError, match="PREEXISTING_DESTINATION"):
        acquire(composition)
    assert events == transport.requests == []


def test_one_complete_acquisition_uses_kernel_and_frozen_requests(
    composition, monkeypatch
):
    called = []
    original = kernel.HistoricalResearchAcquisitionOperator.run

    def run(self, **kwargs):
        called.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(kernel.HistoricalResearchAcquisitionOperator, "run", run)
    summary = acquire(composition)
    storage, transport, events = composition
    assert len(called) == 1 and events == ["prompt"]
    assert summary["status"] == "SUCCESS"
    assert summary["OPEN_LOADER"] == summary["FULL_DATASET_INTEGRITY"] == "PASS"
    assert summary["open_row_count"] + summary["holdout_row_count"] == 2718
    assert summary["open_row_count"] == 2012
    assert summary["holdout_row_count"] == 706
    assert summary["open_last_timestamp"] < "2024-01-01"
    assert summary["holdout_first_timestamp"] >= "2024-01-01"
    assert summary["attempt_id"] == ATTEMPT
    assert len(summary["evidence_sha256"]) == 64
    assert len(transport.requests) == 3
    bars, actions = transport.requests[0], transport.requests[-1]
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
    assert actions.descriptor == {
        "method": "GET",
        "host": "data.alpaca.markets",
        "path": "/v1/corporate-actions",
        "parameters": {
            "symbols": "SPY",
            "region": "us",
            "start": "2016-01-01",
            "end": "2026-10-24",
            "data_quality": "complete",
            "sort": "asc",
            "limit": "1000",
        },
    }
    for relative in (
        "raw/bars/0000.json",
        "raw/bars/0001.json",
        "raw/corporate-actions/0000.json",
        "corporate-actions/sidecar.json",
        "evidence.json",
    ):
        assert storage.read(relative)
    inspection = desktop.inspect_desktop_dataset_integrity(storage)
    assert (
        inspection.to_dict()["evidence_sha256"]
        == sha256(storage.read("evidence.json")).hexdigest()
    )
    with pytest.raises(FrozenInstanceError):
        inspection.attempt_id = "changed"
    assert desktop.load_desktop_open_research(storage)
    with pytest.raises(desktop.DesktopResearchError, match="admission"):
        desktop.load_desktop_final_holdout(storage, inspection)
    output = json.dumps(summary)
    assert SECRET not in output and "123.25" not in output
    assert (
        not {"bars", "o", "h", "l", "c", "v", "api_key_id", "api_secret_key"}
        & summary.keys()
    )


def test_terminal_complete_observes_materialized_open_and_evidence(
    composition, monkeypatch
):
    storage, _, _ = composition
    materialized = {}
    built = {}
    receipts = {}
    events = []
    original_build = storage.build_evidence
    original_materialize = storage.materialize_open
    original_terminal = storage.record_terminal
    original_integrity = bridge.inspect_desktop_dataset_integrity
    original_loader = bridge.load_desktop_open_research

    def build(*args, **kwargs):
        evidence = original_build(*args, **kwargs)
        built["evidence.json"] = evidence
        return evidence

    def materialize(files):
        materialized.update(files)
        receipts["files"] = original_materialize(files)
        return receipts["files"]

    def record_terminal(state, stage):
        assert state == "MATERIALIZED_AWAITING_INDEPENDENT_ADMISSION"
        evidence = materialized["evidence.json"]
        assert evidence == built["evidence.json"]
        receipts["files"][1].verify("evidence.json", evidence)
        assert storage.read("evidence.json") == evidence
        assert (
            sha256(storage.read("evidence.json")).hexdigest()
            == sha256(evidence).hexdigest()
        )
        assert (
            storage.read("normalized/open/SPY.csv")
            == materialized["normalized/open/SPY.csv"]
        )
        events.append("terminal")
        return original_terminal(state, stage)

    def inspect(target):
        events.append("integrity")
        return original_integrity(target)

    def load_open(target):
        events.append("open_loader")
        return original_loader(target)

    monkeypatch.setattr(storage, "build_evidence", build)
    monkeypatch.setattr(storage, "materialize_open", materialize)
    monkeypatch.setattr(storage, "record_terminal", record_terminal)
    monkeypatch.setattr(bridge, "inspect_desktop_dataset_integrity", inspect)
    monkeypatch.setattr(bridge, "load_desktop_open_research", load_open)

    summary = acquire(composition)

    assert tuple(materialized) == ("normalized/open/SPY.csv", "evidence.json")
    assert len(materialized["evidence.json"]) > 0
    assert events == ["terminal", "integrity", "open_loader"]
    assert summary["status"] == "SUCCESS"
    assert summary["OPEN_LOADER"] == summary["FULL_DATASET_INTEGRITY"] == "PASS"
    assert all(
        key not in summary
        for key in ("bars", "o", "h", "l", "c", "v", "api_key_id", "api_secret_key")
    )


def test_evidence_materialization_failure_stops_and_retains_destination(
    composition, monkeypatch
):
    storage, transport, events = composition
    original_create = storage._create
    evidence_attempts = []
    post_kernel = []

    monkeypatch.setattr(
        bridge,
        "inspect_desktop_dataset_integrity",
        lambda target: post_kernel.append(("integrity", target)),
    )
    monkeypatch.setattr(
        bridge,
        "load_desktop_open_research",
        lambda target: post_kernel.append(("open_loader", target)),
    )

    def fail_evidence(relative, body):
        if relative == "evidence.json":
            evidence_attempts.append((relative, body))
            raise OSError(SECRET)
        return original_create(relative, body)

    monkeypatch.setattr(storage, "_create", fail_evidence)
    with pytest.raises(bridge.DesktopAcquisitionError) as error:
        acquire(composition)

    assert error.value.classification == "PERSISTENCE_FAILURE"
    assert post_kernel == []
    assert len(evidence_attempts) == 1
    assert json.loads(storage.read("acquisition.json"))["state"] == "STOPPED"
    assert (storage.root / "normalized/open/SPY.csv").is_file()
    assert not (storage.root / "evidence.json").exists()
    assert storage.root.is_dir()
    provider_calls = len(transport.requests)
    prompt_events = list(events)

    with pytest.raises(bridge.DesktopAcquisitionError) as retry_error:
        acquire(composition)

    assert retry_error.value.classification == "PREEXISTING_DESTINATION"
    assert len(transport.requests) == provider_calls
    assert events == prompt_events
    assert len(evidence_attempts) == 1
    assert json.loads(storage.read("acquisition.json"))["state"] == "STOPPED"


@pytest.mark.parametrize(
    "relative",
    [
        "acquisition.json",
        "evidence.json",
        "manifests/snapshot.json",
        "manifests/open.json",
        "manifests/holdout.json",
        "normalized/open/SPY.csv",
        "normalized/holdout/SPY.csv",
        "raw/bars/0000.json",
        "raw/corporate-actions/0000.json",
        "corporate-actions/sidecar.json",
    ],
)
def test_integrity_detects_tampering(composition, relative):
    acquire(composition)
    path = composition[0].root / relative
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        desktop.inspect_desktop_dataset_integrity(composition[0])


@pytest.mark.parametrize(
    "status,category",
    [
        (401, "HTTP_AUTH_OR_ENTITLEMENT"),
        (403, "HTTP_AUTH_OR_ENTITLEMENT"),
        (429, "HTTP_RATE_LIMIT"),
        (500, "HTTP_SERVER"),
        (503, "HTTP_SERVER"),
    ],
)
def test_provider_failure_is_sanitized_incomplete_and_not_retried(
    composition, status, category
):
    storage, transport, events = composition
    calls = []

    def get(request, credentials):
        assert events == ["prompt"]
        calls.append(1)
        return kernel.HistoricalResearchResponse(
            request, status, b'{"error":"synthetic"}'
        )

    transport.get = get
    with pytest.raises(bridge.DesktopAcquisitionError) as error:
        acquire(composition)
    assert error.value.classification == category
    assert len(calls) == 1
    assert json.loads(storage.read("acquisition.json"))["state"] == "STOPPED"
    with pytest.raises(desktop.DesktopResearchError):
        desktop.load_desktop_open_research(storage)
    with pytest.raises(bridge.DesktopAcquisitionError, match="PREEXISTING_DESTINATION"):
        acquire(composition)
    assert len(calls) == 1 and events == ["prompt"]


@pytest.mark.parametrize(
    "failure,category",
    [
        ("transport", "TRANSPORT_FAILURE"),
        ("shape", "UNEXPECTED_RESPONSE_SHAPE"),
        ("replay", "PAGINATION_REPLAY_FAILURE"),
        ("dataset", "DATASET_VALIDATION_FAILURE"),
        ("persistence", "PERSISTENCE_FAILURE"),
        ("credentials", "CREDENTIAL_INPUT_REJECTED"),
    ],
)
def test_failure_categories_without_exception_text(
    composition, monkeypatch, failure, category
):
    storage, transport, _ = composition
    calls = []

    def get(request, credentials):
        calls.append(1)
        if failure == "transport":
            raise OSError(SECRET)
        body = {
            "shape": b"[]",
            "replay": b'{"bars":[],"next_page_token":"again"}',
            "dataset": b'{"symbol":"SPY","bars":[],"next_page_token":null}',
        }.get(failure, b"{}")
        return kernel.HistoricalResearchResponse(request, 200, body)

    transport.get = get
    if failure == "persistence":
        monkeypatch.setattr(
            storage, "persist_raw", lambda *a: (_ for _ in ()).throw(OSError(SECRET))
        )
    if failure == "credentials":
        monkeypatch.setattr(
            bridge,
            "interactive_research_credentials",
            lambda: (_ for _ in ()).throw(ValueError(SECRET)),
        )
    with pytest.raises(bridge.DesktopAcquisitionError) as error:
        acquire(composition)
    assert error.value.classification == category
    assert error.value.__context__ is None
    assert SECRET not in str(error.value) + repr(error.value)
    assert len(calls) <= 2


def test_new_bridge_has_no_legacy_host_or_broker_dependencies():
    source = Path(bridge.__file__).read_text()
    tree = ast.parse(source)
    native_imports = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        and n.module
        and n.module.endswith("historical_research_native")
    ]
    assert len(native_imports) == 1
    assert {alias.name for alias in native_imports[0].names} == {
        "interactive_research_credentials",
        "HttpsHistoricalResearchTransport",
    }
    for forbidden_text in (
        "AcceptedB2Preflight",
        "EphemeralHistoricalResearchCredentialSource",
        "observe_research_operator_token",
        "win32",
        "ctypes",
        "winreg",
        "robinhood",
        "broker",
        "orders",
        "environ",
        "getenv",
        "CredRead",
        "research-holdout",
        "historical_research_b2_preflight",
        "historical_research_native_custody",
    ):
        assert forbidden_text not in source
    assert desktop.DESKTOP_RESEARCH_ROOT == Path(
        r"F:\AI\ai-trading-bot\data\research\desktop-v1"
    )
    assert bridge.CANONICAL_PROJECT_ROOT == Path(r"F:\AI\ai-trading-bot")
    assert not desktop.DESKTOP_RESEARCH_ROOT.exists()


@pytest.mark.parametrize(
    "file,name,digest",
    [
        (
            "historical_research_native.py",
            "EphemeralHistoricalResearchCredentialSource",
            "6da6ee63946ed5468a981ecff5ed9adc8bc0c3e455d0f357f07d1261097820d9",
        ),
        (
            "historical_research_b2_preflight.py",
            "AcceptedB2Preflight",
            "ca917ffa6359f8d4e8d73491afd2589b424983e6801f5909ec0b9673198da076",
        ),
    ],
)
def test_preserved_historical_classes_unchanged(file, name, digest):
    source = (ROOT / "src/trading_bot/experiments" / file).read_text()
    node = next(
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.ClassDef) and n.name == name
    )
    assert sha256(ast.dump(node).encode()).hexdigest() == digest
