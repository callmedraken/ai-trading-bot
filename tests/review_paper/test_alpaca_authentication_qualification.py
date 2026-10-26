"""D1R4 fake-only transport, authority and canonical evidence verification."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.runtime.checkpoint_runner.test_ci import (
    _use_historical_predecessor_authority,
)

from trading_bot.market_data.alpaca_http import (
    MAX_ALPACA_RESPONSE_BYTES,
    StdlibAlpacaHistoricalBarsTransport,
)
from trading_bot.review_paper import alpaca_authentication_host as host
from trading_bot.review_paper import alpaca_authentication_qualification as auth
from trading_bot.review_paper import alpaca_windows_credentials as creds
from trading_bot.review_paper.alpaca_credential_generation import (
    ROLES,
    GenerationJournal,
    credential_witness,
)

HEAD, TREE = "a" * 40, "b" * 40
SENSITIVE = "fake-SECRET-key-free-text"
BODY = (
    b'{"bars":{"SPY":[{"t":"2026-10-07T04:00:00Z","o":600,"h":601,'
    b'"l":599,"c":600,"v":100}]},"next_page_token":null}'
)


@pytest.fixture
def boundary(monkeypatch):
    class Exclusion:
        owned = False
        abandoned = False

        def acquire(self):
            self.owned = True
            return True

        def release(self):
            self.owned = False

    monkeypatch.setattr(host, "WindowsV3Exclusion", Exclusion)
    state = SimpleNamespace(
        reads=[],
        blobs=[],
        requests=[],
        admissions=0,
        status=200,
        body=BODY,
        headers=[("Content-Type", "application/json"), ("X-Request-ID", SENSITIVE)],
        stage=None,
        drift=None,
        credential_error=None,
        closures=0,
    )

    class Reader:
        def read_fixed(self, target):
            state.reads.append(target)
            if state.credential_error:
                raise state.credential_error
            value = bytearray(SENSITIVE.encode())
            state.blobs.append(value)
            return value

    monkeypatch.setattr(creds, "_WindowsCredentialReader", Reader)

    class Response:
        @property
        def status(self):
            return state.status

        def getheaders(self):
            if state.stage == "metadata":
                raise OSError(SENSITIVE)
            return state.headers

        def read(self, amount):
            if state.stage == "body":
                raise OSError(SENSITIVE)
            if state.stage == "nonbytes":
                return SENSITIVE
            body, state.body = state.body, b""
            return body

    class Connection:
        def request(self, method, url, body=None, headers=None):
            state.requests.append((method, url))
            assert headers["APCA-API-KEY-ID"] == SENSITIVE
            assert headers["APCA-API-SECRET-KEY"] == SENSITIVE
            if state.stage == "request":
                raise OSError(SENSITIVE)
            if len(state.requests) > 1:
                pytest.fail("second provider request")

        def getresponse(self):
            if state.stage == "start":
                raise OSError(SENSITIVE)
            return Response()

        def close(self):
            state.closures += 1

    state.transport = StdlibAlpacaHistoricalBarsTransport(
        connection_factory=lambda *a, **kw: Connection()
    )

    def admit():
        state.admissions += 1
        if state.drift == state.admissions:
            raise ValueError(SENSITIVE)
        return ()

    state.admit = admit
    return state


def qualify(state):
    return auth.qualify_alpaca_authentication(
        expected_head=HEAD,
        expected_tree=TREE,
        qualify_auth=auth.QUALIFY_AUTH_INTERLOCK,
        admit_source=state.admit,
        transport=state.transport,
        credential_reader=creds.read_current_product_alpaca_secrets,
    )


def sanitized(result, capsys):
    payload = auth.serialize_authentication_qualification(result)
    assert auth.parse_authentication_qualification(payload) == result
    assert SENSITIVE not in payload.decode() + str(result) + repr(result)
    captured = capsys.readouterr()
    assert SENSITIVE not in captured.out + captured.err
    return payload


def test_valid_pair_and_compatible_200_pass(boundary, capsys):
    result = qualify(boundary)
    assert result.status == "PASS"
    assert result.reason is auth.AuthQualificationReason.PASS
    assert result.http_status == 200 and result.source_readmitted
    assert result.alpaca_request_attempts == result.credential_pair_read_attempts == 1
    assert boundary.reads == [creds.API_KEY_TARGET, creds.API_SECRET_TARGET]
    assert len(boundary.requests) == boundary.closures == 1
    assert boundary.admissions == 3
    assert all(blob == bytearray(len(blob)) for blob in boundary.blobs)
    sanitized(result, capsys)


@pytest.mark.parametrize("status", [201, 301, 401, 403, 429, 500, 503, 599])
def test_http_rejected_without_retry(boundary, capsys, status):
    boundary.status = status
    boundary.body = json.dumps({"code": 40110000, "message": SENSITIVE}).encode()
    result = qualify(boundary)
    assert result.status == "BLOCKED"
    assert result.reason is auth.AuthQualificationReason.HTTP_REJECTED
    assert result.http_status == status and result.provider_code == 40110000
    assert len(boundary.requests) == 1
    sanitized(result, capsys)


@pytest.mark.parametrize("stage", ["request", "start", "metadata", "body", "nonbytes"])
def test_transport_stages_fail_closed(boundary, capsys, stage):
    boundary.stage = stage
    result = qualify(boundary)
    assert result.reason is auth.AuthQualificationReason.TRANSPORT_FAILED
    assert result.http_status is None
    assert len(boundary.requests) == 1
    sanitized(result, capsys)


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("Content-Type", "text/html"), ("X-Request-ID", "fake-id")],
        [
            ("Content-Type", "application/json"),
            ("X-Request-ID", "a"),
            ("X-Request-ID", "b"),
        ],
        [
            ("Content-Type", "application/json"),
            ("X-Request-ID", "a"),
            ("Content-Encoding", "gzip"),
        ],
        [
            ("Content-Type", "application/json"),
            ("X-Request-ID", "a"),
            ("Content-Length", "999"),
        ],
    ],
)
def test_response_metadata_invalid(boundary, capsys, headers):
    boundary.headers = headers
    result = qualify(boundary)
    assert result.reason is auth.AuthQualificationReason.TRANSPORT_FAILED
    assert len(boundary.requests) == 1
    sanitized(result, capsys)


def test_oversize_body_is_blocked(boundary, capsys):
    boundary.body = b"x" * (MAX_ALPACA_RESPONSE_BYTES + 1)
    result = qualify(boundary)
    assert result.reason is auth.AuthQualificationReason.TRANSPORT_FAILED
    sanitized(result, capsys)


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"{",
        b"\xff",
        b"{}",
        b'{"bars":{},"next_page_token":null}',
        BODY.replace(b"SPY", b"QQQ"),
        BODY.replace(b"2026-10-07", b"2026-10-08"),
        BODY.replace(b"04:00:00", b"13:30:00"),
        BODY.replace(b'"next_page_token":null', b'"next_page_token":"more"'),
        BODY.replace(b'"v":100', b'"v":true'),
        BODY.replace(b'"c":600', b'"c":NaN'),
        BODY.replace(b'"o":600', b'"o":0'),
        BODY.replace(b'"h":601', b'"h":599'),
        BODY.replace(b'"c":600', b'"c":600,"c":601'),
        BODY.replace(b'"v":100', b'"v":100,"unknown":"secret"'),
        BODY.replace(b'"bars":', b'"bars":{},"bars":'),
        BODY.replace(b'"SPY":[', b'"QQQ":[],"SPY":['),
    ],
)
def test_strict_or_wrong_probe_response_is_blocked(boundary, capsys, body):
    boundary.body = body
    result = qualify(boundary)
    # An empty extra symbol map is accepted by the existing parser, but the
    # qualification must reject it as a different exact SPY probe response.
    assert result.reason is auth.AuthQualificationReason.RESPONSE_INVALID
    assert result.http_status == 200 and len(boundary.requests) == 1
    sanitized(result, capsys)


@pytest.mark.parametrize("error", [OSError(SENSITIVE), ValueError(SENSITIVE)])
def test_credential_read_failure_has_zero_provider_calls(boundary, capsys, error):
    boundary.credential_error = error
    result = qualify(boundary)
    assert result.reason is auth.AuthQualificationReason.CREDENTIAL_READ_FAILED
    assert not boundary.requests and result.alpaca_request_attempts == 0
    assert not result.credential_pair_read_succeeded
    sanitized(result, capsys)


@pytest.mark.parametrize("drift,requests,reads", [(1, 0, 0), (2, 0, 2), (3, 1, 2)])
def test_source_drift_before_and_after_request(
    boundary, capsys, drift, requests, reads
):
    boundary.drift = drift
    result = qualify(boundary)
    assert result.reason is auth.AuthQualificationReason.SOURCE_DRIFT
    assert result.status == "BLOCKED" and not result.source_readmitted
    assert len(boundary.requests) == requests and len(boundary.reads) == reads
    sanitized(result, capsys)


def test_fixed_request_and_provider_semantics():
    probe = auth.build_authentication_probe()
    assert probe.method == "GET" and probe.host == "data.alpaca.markets"
    assert probe.target == (
        "/v2/stocks/bars?symbols=SPY&timeframe=1Day&start=2026-10-07T04%3A00%3A00Z"
        "&end=2026-10-08T03%3A59%3A59.999999Z&limit=1&adjustment=raw&asof=-"
        "&feed=sip&currency=USD&sort=asc"
    )
    assert not any("key" in k.lower() for k, v in probe.public_headers)


@pytest.mark.parametrize(
    "change",
    [
        {"unknown": 0},
        {"status": "FAIL"},
        {"reason": "UNKNOWN"},
        {"alpaca_request_attempts": True},
        {"alpaca_request_attempts": 2},
        {"source_readmitted": 1},
        {"source_readmitted": False},
        {"http_status": 401},
        {"source_head": "A" * 40},
        {"credential_pair_read_succeeded": False},
        {"provider_code": "free text"},
        {"probe_target": "changed"},
        {"probe_session": "2026-10-08"},
    ],
)
def test_parser_exact_fields_and_strict_types(boundary, capsys, change):
    material = json.loads(sanitized(qualify(boundary), capsys))
    material.update(change)
    payload = (
        json.dumps(material, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    with pytest.raises(ValueError) as error:
        auth.parse_authentication_qualification(payload)
    assert error.value.__context__ is None
    assert SENSITIVE not in str(error.value) + repr(error.value)


@pytest.mark.parametrize(
    "transform",
    [
        lambda b: b[:-1],
        lambda b: b + b"\n",
        lambda b: b.replace(b":", b": ", 1),
        lambda b: b.replace(b"{", b'{"status":"PASS",', 1),
        lambda b: b.replace(b'"schema":"alpaca-authentication-qualification/v1",', b""),
        lambda b: b"\xef\xbb\xbf" + b,
        lambda b: b"x" * 4097,
        lambda b: b.replace(b'"http_status":200', b'"http_status":NaN'),
    ],
)
def test_parser_rejects_noncanonical_and_missing(boundary, transform):
    payload = auth.serialize_authentication_qualification(qualify(boundary))
    with pytest.raises(ValueError):
        auth.parse_authentication_qualification(transform(payload))


def test_interlock_and_exact_transport_required(boundary):
    for changes in [
        {"qualify_auth": "wrong"},
        {"transport": object()},
        {"expected_head": "bad"},
    ]:
        arguments = dict(
            expected_head=HEAD,
            expected_tree=TREE,
            qualify_auth=auth.QUALIFY_AUTH_INTERLOCK,
            transport=boundary.transport,
            admit_source=boundary.admit,
        )
        arguments.update(changes)
        with pytest.raises(ValueError):
            auth.qualify_alpaca_authentication(**arguments)
    assert not boundary.reads and not boundary.requests


def argv(path):
    generation = path.parent / "generation.json"
    if not generation.exists():
        with generation.open("xb") as output:
            journal = GenerationJournal(output, HEAD, TREE)
            journal.witnesses = tuple(
                credential_witness(role, bytearray(SENSITIVE.encode()))
                for role in ROLES
            )
            journal.record("EXPECTED_GENERATION")
            journal.record("PAIR_CONFIRMED")
            journal.record("FINAL", "LOCAL_EXACT_MATCH")
    return [
        "--expected-head",
        HEAD,
        "--expected-tree",
        TREE,
        "--evidence",
        str(path),
        "--qualify-auth",
        auth.QUALIFY_AUTH_INTERLOCK,
        "--generation-evidence",
        str(generation),
        "--generation-sha256",
        hashlib.sha256(generation.read_bytes()).hexdigest(),
    ]


@pytest.mark.parametrize("status", [200, 401])
def test_host_emits_canonical_artifact_and_closed_exit(
    boundary, tmp_path, monkeypatch, capsys, status
):
    path = tmp_path / "result.json"
    boundary.status = status
    monkeypatch.setattr(
        host, "admit_authentication_source", lambda *a: boundary.admit()
    )
    monkeypatch.setattr(
        host, "StdlibAlpacaHistoricalBarsTransport", lambda: boundary.transport
    )
    assert host.main(argv(path)) == (0 if status == 200 else 1)
    captured = capsys.readouterr()
    assert path.read_bytes() == captured.out.encode()
    result = auth.parse_authentication_qualification(path.read_bytes())
    assert result.status == ("PASS" if status == 200 else "BLOCKED")
    assert SENSITIVE not in captured.out + captured.err
    assert len(boundary.requests) == 1
    original = path.read_bytes()
    assert host.main(argv(path)) == 2
    assert path.read_bytes() == original and len(boundary.requests) == 1


def test_host_source_failure_sanitized_and_effect_free(
    boundary, tmp_path, monkeypatch, capsys
):
    def fail(*a):
        raise ValueError(SENSITIVE)

    monkeypatch.setattr(host, "admit_authentication_source", fail)
    path = tmp_path / "result.json"
    assert host.main(argv(path)) == 2
    assert not path.exists() and not boundary.reads and not boundary.requests
    captured = capsys.readouterr()
    assert SENSITIVE not in captured.out + captured.err


@pytest.mark.parametrize("failure", ["open", "fsync"])
def test_evidence_failure_does_not_retry(
    boundary, tmp_path, monkeypatch, capsys, failure
):
    monkeypatch.setattr(
        host, "admit_authentication_source", lambda *a: boundary.admit()
    )
    monkeypatch.setattr(
        host, "StdlibAlpacaHistoricalBarsTransport", lambda: boundary.transport
    )
    path = tmp_path / "result.json"
    arguments = argv(path)

    def fail(*a, **kw):
        raise OSError(SENSITIVE)

    if failure == "open":
        monkeypatch.setattr(Path, "open", fail)
    else:
        monkeypatch.setattr(host.os, "fsync", fail)
    exit_code = host.main(arguments)
    assert exit_code == 2
    assert len(boundary.requests) == 0
    captured = capsys.readouterr()
    assert SENSITIVE not in captured.out + captured.err


def test_fresh_external_destination(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for path in [
        Path("relative.json"),
        root / "file.json",
        tmp_path / "missing" / "file.json",
    ]:
        with pytest.raises(ValueError):
            host.admit_authentication_evidence(path, (root,))
    path = tmp_path / "file.json"
    assert host.admit_authentication_evidence(path, (root,)) == path.resolve()
    path.write_bytes(b"old")
    with pytest.raises(ValueError):
        host.admit_authentication_evidence(path, (root,))
    assert path.read_bytes() == b"old"


def test_no_session_trading_or_broker_imports_or_calls():
    forbidden = {
        "sqlite3",
        "armed_session",
        "armed_session_store",
        "armed_session_host",
        "run_armed_production_paper_session",
        "ReviewPaperStore",
        "Robinhood",
        "strategies",
        "scheduler",
        "broker",
        "execute_attempts",
        "prepare",
    }
    for module in (auth, host):
        tree = ast.parse(Path(module.__file__).read_text())
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imports |= {
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
        }
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & forbidden
        assert not any(any(part in i for part in forbidden) for i in imports)
    assert Path(auth.__file__).read_text().count("transport.execute(") == 1


def test_host_module_entry_help_is_zero_effect(tmp_path):
    environment = {**os.environ, "PYTHONPATH": str(Path(auth.__file__).parents[2])}
    process = subprocess.run(
        [os.sys.executable, "-B", "-m", host.__name__, "--help"],
        capture_output=True,
        text=True,
        env=environment,
        timeout=15,
    )
    assert process.returncode == 0
    assert "--qualify-auth" in process.stdout and SENSITIVE not in process.stderr


def test_reentrant_credential_consumer_cannot_make_second_request(
    boundary, monkeypatch
):
    original = creds.ScopedAlpacaSecrets.use

    def twice(self, consumer):
        original(self, consumer)
        return original(self, consumer)

    monkeypatch.setattr(creds.ScopedAlpacaSecrets, "use", twice)
    result = qualify(boundary)
    assert result.status == "BLOCKED"
    assert len(boundary.requests) == 1 and result.alpaca_request_attempts == 1


@pytest.mark.parametrize(
    "mismatch",
    ["root", "branch", "head", "tree", "dirty", "origin", "tracking", "remote"],
)
def test_exact_local_and_live_origin_source_admission(monkeypatch, mismatch):
    root = Path(host.__file__).resolve().parents[3]
    monkeypatch.setattr(host, "WORKTREE", root)
    outputs = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): host.BRANCH,
        ("rev-parse", "HEAD"): HEAD,
        ("rev-parse", "HEAD^{tree}"): TREE,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("remote", "get-url", "origin"): host.ORIGIN,
        ("rev-parse", "origin/" + host.BRANCH): HEAD,
        ("rev-parse", "origin/" + host.BRANCH + "^{tree}"): TREE,
        ("ls-remote", "origin", "refs/heads/" + host.BRANCH): HEAD
        + "\trefs/heads/"
        + host.BRANCH,
        ("worktree", "list", "--porcelain"): "worktree " + str(root),
    }
    # Test this admission in isolation from unrelated modules pytest loaded.
    monkeypatch.setattr(host.sys, "modules", {auth.__name__: auth, host.__name__: host})

    def git(argv, **kw):
        return subprocess.CompletedProcess(argv, 0, outputs[tuple(argv[3:])], "")

    monkeypatch.setattr(host.subprocess, "run", git)
    monkeypatch.setattr(host.os, "name", "nt")
    assert host.admit_authentication_source(HEAD, TREE) == (root,)
    keys = {
        "root": ("rev-parse", "--show-toplevel"),
        "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        "dirty": ("status", "--porcelain=v1", "--untracked-files=all"),
        "origin": ("remote", "get-url", "origin"),
        "tracking": ("rev-parse", "origin/" + host.BRANCH),
        "remote": ("ls-remote", "origin", "refs/heads/" + host.BRANCH),
    }
    outputs[keys[mismatch]] = "unexpected"
    with pytest.raises(ValueError):
        host.admit_authentication_source(HEAD, TREE)


def test_linked_evidence_parent_is_rejected(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    parent.mkdir()
    original = Path.lstat

    def metadata(path, *a, **kw):
        if path == parent:
            return SimpleNamespace(st_mode=0, st_file_attributes=0x400)
        return original(path, *a, **kw)

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(ValueError, match="linked"):
        host.admit_authentication_evidence(parent / "file.json", ())


def test_d1r4_source_only_registration_and_frozen_predecessors(monkeypatch):
    from scripts import checkpoint_runner as runner

    root = Path(runner.__file__).resolve().parents[1]
    _use_historical_predecessor_authority(monkeypatch, root)
    spec = runner._checkpoint_specs()[runner.ARCH134_AUTH_NAME]
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), host.BRANCH, "push")
        == spec.name
    )
    assert runner.resolve_ci_certification_profile(spec.name) == "robinhood"
    assert spec.preflight is None and spec.execute is None
    assert runner._arch134_authentication_authority_check(root) == ()
    assert runner.ACTIVE_CI_CHECKPOINTS[-6:] == (
        runner.ARCH134_ARMED_PAPER_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_DECISION_NAME,
        runner.ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME,
        runner.ARCH134_PRODUCTION_PAPER_RUNTIME_NAME,
        runner.ARCH134_RUNTIME_ACL_NAME,
    )
    pins = dict(runner.ARCH134_D1R4_SOURCE_PINS)
    pins["src/trading_bot/review_paper/alpaca_authentication_host.py"] = "0" * 40
    monkeypatch.setattr(runner, "ARCH134_D1R4_SOURCE_PINS", pins)
    assert any(
        "source drift" in x
        for x in runner._arch134_authentication_authority_check(root)
    )


def test_consumed_generation_cannot_authorize_second_qualification(
    boundary, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        host, "admit_authentication_source", lambda *a: boundary.admit()
    )
    monkeypatch.setattr(
        host, "StdlibAlpacaHistoricalBarsTransport", lambda: boundary.transport
    )
    first = tmp_path / "first.json"
    assert host.main(argv(first)) == 0
    reads = list(boundary.reads)
    assert host.main(argv(tmp_path / "second.json")) == 2
    assert boundary.reads == reads and len(boundary.requests) == 1


def test_generation_witness_mismatch_prevents_provider_attempt(
    boundary, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        host, "admit_authentication_source", lambda *a: boundary.admit()
    )
    monkeypatch.setattr(
        host, "StdlibAlpacaHistoricalBarsTransport", lambda: boundary.transport
    )
    arguments = argv(tmp_path / "mismatch.json")
    monkeypatch.setattr(
        host,
        "read_current_product_alpaca_secrets",
        lambda: creds.ScopedAlpacaSecrets("different-fake-key", SENSITIVE),
    )
    assert host.main(arguments) == 1
    assert not boundary.requests
    result = auth.parse_authentication_qualification(
        (tmp_path / "mismatch.json").read_bytes()
    )
    assert result.reason is auth.AuthQualificationReason.CREDENTIAL_READ_FAILED


def test_authentication_publication_failure_after_request_never_reopens_staging(
    boundary, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        host, "admit_authentication_source", lambda *a: boundary.admit()
    )
    monkeypatch.setattr(
        host, "StdlibAlpacaHistoricalBarsTransport", lambda: boundary.transport
    )
    arguments = argv(tmp_path / "fsync.json")
    original = host.os.fsync
    calls = []

    def fsync(fd):
        calls.append(fd)
        if len(calls) == 2:
            raise OSError(SENSITIVE)
        return original(fd)

    monkeypatch.setattr(host.os, "fsync", fsync)
    assert host.main(arguments) == 2 and len(boundary.requests) == 1
    assert host.main(argv(tmp_path / "later.json")) == 2
    assert len(boundary.requests) == 1
