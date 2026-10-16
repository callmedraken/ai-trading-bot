"""B3Q qualification, fake transport/OAuth only; real effects are tripwires."""

import ast
import json
import logging
import os
import warnings
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from tests.robinhood_mcp.test_historical import payload_for

from scripts import checkpoint_runner, qualify_robinhood_history
from trading_bot import robinhood_history_qualification as subject
from trading_bot.robinhood_mcp import sdk_transport, windows_oauth
from trading_bot.robinhood_mcp.historical import parse_equity_historicals_response
from trading_bot.robinhood_mcp.models import RobinhoodMcpSchemaError

AT = datetime(2026, 10, 12, 13, tzinfo=UTC)
SECRET = "oauth-token-secret https://private.invalid/?code=reusable account-123456"
ROOT = Path(subject.__file__).resolve().parents[2]


@pytest.fixture
def harness(tmp_path, monkeypatch):
    inputs = dict(
        authorization=subject.AUTHORIZATION,
        expected_head="a" * 40,
        expected_tree="b" * 40,
        evidence_path=tmp_path / "b3q.jsonl",
    )
    admit = Mock(return_value=(ROOT,))
    monkeypatch.setattr(subject, "admit_history_qualification_source", admit)
    clock = Mock(now=Mock(return_value=AT))
    monkeypatch.setattr(subject, "datetime", clock)
    request = subject.qualification_request(AT)
    payload = payload_for(request)
    payload["guide"] = SECRET
    calls = []
    tripwire = Mock(side_effect=AssertionError("real provider/OAuth effect"))
    for owner, name in (
        (sdk_transport.RobinhoodMcpStreamableHttpTransport, "_request_once"),
        (windows_oauth.WindowsCredentialApi, "read_generic"),
        (windows_oauth.WindowsCredentialApi, "write_generic"),
        (windows_oauth.WindowsOAuthStorage, "get_tokens"),
        (windows_oauth.WindowsOAuthStorage, "get_client_info"),
        (windows_oauth.LoopbackOAuthCallback, "callback_handler"),
    ):
        monkeypatch.setattr(owner, name, tripwire)

    async def caller(name, arguments):
        calls.append((name, arguments))
        assert name == "get_equity_historicals"
        assert arguments == request.arguments()
        records = read_records(inputs)
        assert records[-1]["status"] == "AMBIGUOUS_PROVIDER_EFFECT"
        if isinstance(payload, BaseException):
            raise payload
        return payload

    transport = sdk_transport.RobinhoodMcpStreamableHttpTransport.for_test(caller)
    constructor = Mock(return_value=transport)
    oauth = Mock(return_value=lambda: None)
    monkeypatch.setattr(subject, "RobinhoodMcpStreamableHttpTransport", constructor)
    monkeypatch.setattr(subject, "create_windows_robinhood_oauth_factory", oauth)
    yield inputs, payload, calls, admit, clock, oauth, constructor
    tripwire.assert_not_called()


def read_records(inputs):
    return [
        json.loads(line) for line in inputs["evidence_path"].read_bytes().splitlines()
    ]


def test_pass_exact_single_tool_request_materialization_and_sanitized_replay(
    harness, monkeypatch
):
    inputs, payload, calls, admit, clock, oauth, constructor = harness
    materialize = Mock(wraps=subject.materialize_production_strategy_history)
    monkeypatch.setattr(subject, "materialize_production_strategy_history", materialize)
    payload["data"]["results"][0]["adjustment_type"] = "none"
    assert subject.run_history_qualification(**inputs) == "PASS"
    request = subject.qualification_request(AT)
    assert calls == [
        (
            "get_equity_historicals",
            {
                "symbols": ["SPY"],
                "start_time": "2026-10-06T13:30:00Z",
                "end_time": "2026-10-09T20:00:00Z",
                "interval": "day",
                "bounds": "regular",
                "adjustment_type": "none",
            },
        )
    ]
    assert len(read_records(inputs)) == 3
    terminal = read_records(inputs)[-1]
    assert terminal["sessions"] == [
        "2026-10-06",
        "2026-10-07",
        "2026-10-08",
        "2026-10-09",
    ]
    assert terminal["source_head"] == inputs["expected_head"]
    assert terminal["source_tree"] == inputs["expected_tree"]
    assert terminal["captured_at"] == AT.isoformat()
    assert terminal["historical_attempts"] == 1
    assert terminal["other_application_calls"] == 0
    assert terminal["response"]["data"] == payload["data"]
    assert SECRET.encode() not in inputs["evidence_path"].read_bytes()
    assert len(inputs["evidence_path"].read_bytes()) <= subject.MAX_EVIDENCE_BYTES
    materialize.assert_called_once()
    assert admit.call_count == 2
    assert clock.now.call_count == 3
    oauth.assert_called_once_with(
        redirect_uri=subject.REDIRECT_URI, browser_opener=subject._forbid_browser
    )
    constructor.assert_called_once()
    monkeypatch.setattr(subject, "datetime", datetime)
    replay = subject.replay_history_qualification(
        inputs["evidence_path"].read_bytes(),
        expected_head="a" * 40,
        expected_tree="b" * 40,
    )
    assert replay.bars == parse_equity_historicals_response(payload, request).bars


@pytest.mark.parametrize(
    "mutation",
    [
        "session_missing",
        "interpolated_missing",
        "interpolated_true",
        "midnight",
        "not_open",
        "adjusted",
        "bounds",
        "interval",
        "symbol",
        "gap",
        "duplicate",
        "reorder",
        "extra",
        "insufficient",
        "future",
        "unknown",
        "not_found",
        "malformed",
    ],
)
def test_strict_schema_failure_no_fallback_retry_or_unsafe_evidence(harness, mutation):
    inputs, payload, calls, _, _, _, _ = harness
    result = payload["data"]["results"][0]
    bars = result["bars"]
    if mutation.endswith("_missing"):
        del bars[0][mutation.removesuffix("_missing")]
    elif mutation == "interpolated_true":
        bars[0]["interpolated"] = True
    elif mutation in {"midnight", "not_open", "future"}:
        bars[0]["begins_at"] = {
            "midnight": "2026-10-06T00:00:00Z",
            "not_open": "2026-10-06T13:31:00Z",
            "future": "2026-10-12T13:30:00Z",
        }[mutation]
    elif mutation == "adjusted":
        result["adjustment_type"] = "split"
    elif mutation in {"bounds", "interval", "symbol"}:
        result[mutation] = "incompatible"
    elif mutation == "gap":
        bars[1]["begins_at"] = bars[2]["begins_at"]
    elif mutation == "duplicate":
        bars[1] = deepcopy(bars[0])
    elif mutation == "reorder":
        bars.reverse()
    elif mutation == "extra":
        bars.append(deepcopy(bars[-1]))
    elif mutation == "insufficient":
        bars.pop()
    elif mutation == "unknown":
        result["account_number"] = SECRET
    elif mutation == "not_found":
        payload["data"]["not_found"] = [SECRET]
    else:
        payload.clear()
        payload["credentials"] = SECRET
    assert subject.run_history_qualification(**inputs) == "FAIL"
    assert len(calls) == 1
    terminal = read_records(inputs)[-1]
    assert terminal["reason"] == "STRICT_B3_SCHEMA_REJECTED"
    assert terminal["response"] is None
    assert SECRET.encode() not in inputs["evidence_path"].read_bytes()


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError(SECRET),
        sdk_transport.RobinhoodMcpToolCallError(SECRET),
        sdk_transport.RobinhoodMcpStructuredResultError(SECRET),
        RobinhoodMcpSchemaError(SECRET),
    ],
)
def test_transport_uncertainty_preserved_no_retry(harness, error):
    inputs, _, calls, _, _, _, constructor = harness

    async def caller(name, arguments):
        calls.append((name, arguments))
        raise error

    constructor.return_value = (
        sdk_transport.RobinhoodMcpStreamableHttpTransport.for_test(caller)
    )
    assert subject.run_history_qualification(**inputs) == "AMBIGUOUS_PROVIDER_EFFECT"
    assert len(calls) == 1
    assert read_records(inputs)[-1]["response"] is None
    assert SECRET.encode() not in inputs["evidence_path"].read_bytes()


@pytest.mark.parametrize(
    "problem",
    [
        "authorization",
        "source",
        "existing",
        "relative",
        "internal",
        "parent",
        "calendar",
    ],
)
def test_admission_failures_zero_oauth_and_provider(harness, problem):
    inputs, _, calls, admit, clock, oauth, constructor = harness
    if problem == "authorization":
        inputs["authorization"] = "wrong"
    elif problem == "source":
        admit.side_effect = ValueError(SECRET)
    elif problem == "existing":
        inputs["evidence_path"].write_text("preserved")
    elif problem == "relative":
        inputs["evidence_path"] = Path("b3q.jsonl")
    elif problem == "internal":
        inputs["evidence_path"] = ROOT / "b3q.jsonl"
    elif problem == "parent":
        inputs["evidence_path"] = (
            inputs["evidence_path"].parent / "absent" / "b3q.jsonl"
        )
    else:
        clock.now.return_value = AT - timedelta(days=1)
    with pytest.raises(subject.HistoryQualificationError):
        subject.run_history_qualification(**inputs)
    assert calls == []
    oauth.assert_not_called()
    constructor.assert_not_called()
    if problem == "existing":
        assert inputs["evidence_path"].read_text() == "preserved"


def test_composition_blocked_and_no_interactive_oauth(harness):
    inputs, _, calls, _, _, oauth, _ = harness
    oauth.side_effect = ValueError(SECRET)
    assert subject.run_history_qualification(**inputs) == "BLOCKED"
    assert calls == []
    assert read_records(inputs)[-1]["historical_attempts"] == 0
    assert SECRET.encode() not in inputs["evidence_path"].read_bytes()
    with pytest.raises(windows_oauth.LoopbackOAuthError, match="forbidden"):
        subject._forbid_browser(SECRET)


def test_provider_output_discarded_and_restored(harness, capfd):
    inputs, _, _, _, _, oauth, _ = harness

    def noisy(**kwargs):
        print(SECRET)
        os.write(2, SECRET.encode())
        logging.getLogger(__name__).error(SECRET)
        warnings.warn(SECRET, stacklevel=1)
        return lambda: None

    oauth.side_effect = noisy
    assert subject.run_history_qualification(**inputs) == "PASS"
    print("restored")
    captured = capfd.readouterr()
    assert SECRET not in captured.out + captured.err
    assert "restored" in captured.out


@pytest.mark.parametrize(
    "problem", ["capture_backwards", "date_rollover", "source_drift"]
)
def test_post_response_failure_preserves_safe_terminal_evidence(harness, problem):
    inputs, _, calls, admit, clock, _, _ = harness
    if problem == "source_drift":
        admit.side_effect = [(ROOT,), ValueError(SECRET)]
    else:
        capture = (
            AT - timedelta(seconds=1)
            if problem == "capture_backwards"
            else AT + timedelta(days=1)
        )
        clock.now.side_effect = [AT, AT, capture]
    assert subject.run_history_qualification(**inputs) == "FAIL"
    assert len(calls) == 1
    assert SECRET.encode() not in inputs["evidence_path"].read_bytes()


def test_interrupted_call_journal_is_ambiguous_and_cannot_replay(harness):
    inputs, _, calls, _, _, _, constructor = harness

    async def interrupted(name, arguments):
        calls.append((name, arguments))
        raise KeyboardInterrupt(SECRET)

    constructor.return_value = (
        sdk_transport.RobinhoodMcpStreamableHttpTransport.for_test(interrupted)
    )
    with pytest.raises(subject.HistoryQualificationError, match="preserve evidence"):
        subject.run_history_qualification(**inputs)
    assert len(calls) == 1
    assert read_records(inputs)[-1]["status"] == "AMBIGUOUS_PROVIDER_EFFECT"
    with pytest.raises(subject.HistoryQualificationError):
        subject.replay_history_qualification(
            inputs["evidence_path"].read_bytes(),
            expected_head="a" * 40,
            expected_tree="b" * 40,
        )


def test_evidence_write_failure_after_call_preserves_ambiguous_journal(
    harness, monkeypatch
):
    inputs, _, calls, _, _, _, _ = harness
    original = subject._append

    def write(output, facts):
        if facts["phase"] == "TERMINAL":
            raise OSError(SECRET)
        original(output, facts)

    monkeypatch.setattr(subject, "_append", write)
    with pytest.raises(subject.HistoryQualificationError, match="preserve evidence"):
        subject.run_history_qualification(**inputs)
    assert len(calls) == 1
    assert read_records(inputs)[-1]["status"] == "AMBIGUOUS_PROVIDER_EFFECT"


@pytest.mark.parametrize(
    "change",
    [
        "head",
        "tree",
        "arguments",
        "session",
        "status",
        "data",
        "duplicate_key",
        "whitespace",
        "bound",
    ],
)
def test_replay_exact_binding_and_canonical_bounded_evidence(
    harness, monkeypatch, change
):
    inputs, _, _, _, _, _, _ = harness
    assert subject.run_history_qualification(**inputs) == "PASS"
    monkeypatch.setattr(subject, "datetime", datetime)
    data = inputs["evidence_path"].read_bytes()
    records = read_records(inputs)
    terminal = records[-1]
    expected = dict(expected_head="a" * 40, expected_tree="b" * 40)
    if change in {"head", "tree"}:
        expected["expected_" + change] = "c" * 40
    elif change == "arguments":
        terminal["arguments"]["bounds"] = "extended"
    elif change == "session":
        terminal["sessions"].reverse()
    elif change == "status":
        terminal["status"] = "AMBIGUOUS_PROVIDER_EFFECT"
    elif change == "data":
        terminal["response"]["data"]["results"][0]["bars"].pop()
    if change in {"arguments", "session", "status", "data"}:
        data = b"".join(
            (json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode()
            for r in records
        )
    elif change == "duplicate_key":
        data = data.replace(b'"status":"PASS"', b'"status":"FAIL","status":"PASS"')
    elif change == "whitespace":
        data = data.replace(b'"status":"PASS"', b'"status": "PASS"')
    elif change == "bound":
        data = b" " * (subject.MAX_EVIDENCE_BYTES + 1)
    with pytest.raises(subject.HistoryQualificationError):
        subject.replay_history_qualification(data, **expected)


def test_preflight_has_zero_effects_and_creates_no_output(harness):
    inputs, _, calls, _, _, oauth, constructor = harness
    result = subject.preflight_history_qualification(
        **{k: v for k, v in inputs.items() if k != "authorization"}
    )
    assert result["status"] == "PASS" and result["phase"] == "PREFLIGHT"
    assert calls == []
    assert not inputs["evidence_path"].exists()
    oauth.assert_not_called()
    constructor.assert_not_called()


@pytest.mark.parametrize(
    "mismatch", ["none", "origin", "live", "head", "tree", "root", "imports"]
)
def test_source_admission_exact_origin_head_tree_and_imports(monkeypatch, mismatch):
    monkeypatch.setattr(
        subject, "admit_robinhood_paper_source", Mock(return_value=(ROOT,))
    )
    ref = "refs/heads/" + subject.BRANCH
    outputs = {
        ("remote", "get-url", "origin"): subject.ORIGIN,
        ("ls-remote", "origin", ref): "a" * 40 + "\t" + ref,
        ("rev-parse", "origin/" + subject.BRANCH): "a" * 40,
        ("rev-parse", "origin/" + subject.BRANCH + "^{tree}"): "b" * 40,
    }
    keys = {
        "origin": ("remote", "get-url", "origin"),
        "live": ("ls-remote", "origin", ref),
        "head": ("rev-parse", "origin/" + subject.BRANCH),
        "tree": ("rev-parse", "origin/" + subject.BRANCH + "^{tree}"),
    }
    if mismatch in keys:
        outputs[keys[mismatch]] = "wrong"
    elif mismatch == "root":
        subject.admit_robinhood_paper_source.return_value = ()
    elif mismatch == "imports":
        monkeypatch.setattr(
            subject,
            "sys",
            Mock(modules={"trading_bot.other": Mock(__file__="/other.py")}),
        )
    monkeypatch.setattr(subject, "_git", lambda root, *args: outputs[args])
    if mismatch == "none":
        assert subject.admit_history_qualification_source("a" * 40, "b" * 40) == (ROOT,)
    else:
        with pytest.raises(subject.HistoryQualificationError):
            subject.admit_history_qualification_source("a" * 40, "b" * 40)


def test_one_shot_wrapper_exposes_only_history_and_rejects_changed_args(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(subject, "datetime", Mock(now=Mock(return_value=AT)))
    request = subject.qualification_request(AT)
    transport = Mock(get_equity_historicals=Mock(return_value={}))
    with (tmp_path / "journal").open("xb") as output:
        bounded = subject._HistoryOnlyTransport(transport, request, output, {})
        with pytest.raises(subject.HistoryQualificationError):
            bounded.get_equity_historicals({})
        assert bounded.attempts == 0
        bounded.get_equity_historicals(request.arguments())
        with pytest.raises(subject.HistoryQualificationError):
            bounded.get_equity_historicals(request.arguments())
        for tool in (
            "get_accounts",
            "get_equity_quotes",
            "get_equity_orders",
            "review_equity_order",
            "call_tool",
        ):
            assert not hasattr(bounded, tool)
    transport.get_equity_historicals.assert_called_once_with(request.arguments())


@pytest.mark.parametrize(
    "mode,status,code",
    [
        ("preflight", "PASS", 0),
        ("execute", "PASS", 0),
        ("execute", "FAIL", 1),
        ("execute", "AMBIGUOUS_PROVIDER_EFFECT", 1),
    ],
)
def test_cli_fixed_semantics_and_status(monkeypatch, tmp_path, mode, status, code):
    preflight = Mock(return_value={"status": "PASS"})
    execute = Mock(return_value=status)
    monkeypatch.setattr(
        qualify_robinhood_history, "preflight_history_qualification", preflight
    )
    monkeypatch.setattr(qualify_robinhood_history, "run_history_qualification", execute)
    argv = [
        "--expected-head",
        "a" * 40,
        "--expected-tree",
        "b" * 40,
        "--evidence",
        str(tmp_path / "out"),
    ]
    argv += (
        ["--preflight"]
        if mode == "preflight"
        else ["--authorize", subject.AUTHORIZATION]
    )
    assert qualify_robinhood_history.main(argv) == code
    assert (preflight.call_count, execute.call_count) == (
        (1, 0) if mode == "preflight" else (0, 1)
    )
    with pytest.raises(SystemExit):
        qualify_robinhood_history.main(argv + ["--symbol", "QQQ"])


def test_registration_and_authority_closure():
    spec = checkpoint_runner._checkpoint_specs()[
        "arch134-production-strategy-live-paper"
    ]
    assert spec.preflight is None and spec.execute is None
    assert "tests/review_paper/test_history_qualification.py" in spec.tests
    assert checkpoint_runner._arch134_history_qualification_authority_check(ROOT) == ()
    tree = ast.parse(Path(subject.__file__).read_text())
    calls = [
        getattr(n.func, "attr", getattr(n.func, "id", ""))
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
    ]
    assert calls.count("get_equity_historicals") == 1
    assert calls.count("equity_daily_history") == 1
    assert not set(calls) & {
        "_get_accounts",
        "get_equity_quotes",
        "get_equity_orders",
        "review_equity_order",
        "call_tool",
        "_request_once",
        "record_market_review",
    }


@pytest.mark.parametrize(
    "edge", ["start_backwards", "capture_before_start", "capture_naive"]
)
def test_clock_sequence_fail_closed(harness, edge):
    inputs, _, calls, _, clock, _, _ = harness
    if edge == "start_backwards":
        clock.now.side_effect = [AT, AT - timedelta(seconds=1)]
        assert subject.run_history_qualification(**inputs) == "BLOCKED"
        assert calls == []
    else:
        clock.now.side_effect = [
            AT,
            AT + timedelta(seconds=1),
            AT if edge == "capture_before_start" else AT.replace(tzinfo=None),
        ]
        assert subject.run_history_qualification(**inputs) == "FAIL"
        assert len(calls) == 1


@pytest.mark.parametrize(
    "relative,addition",
    [
        ("src/trading_bot/robinhood_history_qualification.py", "import socket"),
        (
            "src/trading_bot/robinhood_history_qualification.py",
            "def unsafe(t): return t.get_equity_quotes({})",
        ),
        (
            "src/trading_bot/robinhood_history_qualification.py",
            "import trading_bot.runtime.windows_authority",
        ),
        (
            "scripts/qualify_robinhood_history.py",
            "import trading_bot.robinhood_supervised_qualification",
        ),
    ],
)
def test_authority_rejects_import_or_effect_expansion(tmp_path, relative, addition):
    for name in checkpoint_runner.ARCH134_HISTORY_QUALIFICATION_SOURCE_PINS:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    assert (
        checkpoint_runner._arch134_history_qualification_authority_check(tmp_path) == ()
    )
    path = tmp_path / relative
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    failures = checkpoint_runner._arch134_history_qualification_authority_check(
        tmp_path
    )
    assert any("source drift" in item for item in failures)
    assert any(
        "import surface" in item or "effect surface" in item for item in failures
    )


def test_cli_offline_replay_zero_provider(harness, monkeypatch, capsys):
    inputs, _, calls, _, _, oauth, _ = harness
    assert subject.run_history_qualification(**inputs) == "PASS"
    monkeypatch.setattr(subject, "datetime", datetime)
    argv = [
        "--replay",
        "--expected-head",
        inputs["expected_head"],
        "--expected-tree",
        inputs["expected_tree"],
        "--evidence",
        str(inputs["evidence_path"]),
    ]
    assert qualify_robinhood_history.main(argv) == 0
    assert "PASS_REPLAY" in capsys.readouterr().out
    assert len(calls) == 1 and oauth.call_count == 1
