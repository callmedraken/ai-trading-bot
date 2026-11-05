"""Focused D34 cutoff, diagnostics, retirement, and operator tests."""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

import pytest

from trading_bot.live_prototype import alpaca_signal_operator as d33_operator
from trading_bot.live_prototype import alpaca_signal_recovery_inputs as subject
from trading_bot.live_prototype import alpaca_signal_recovery_operator as operator
from trading_bot.live_prototype.alpaca_signal_inputs import (
    select_latest_completed_sessions,
)
from trading_bot.market_data.alpaca_http import AlpacaHttpResponse
from trading_bot.market_data.exceptions import (
    AlpacaHttpStatusError,
    AlpacaResponseMetadataFailureReason,
    AlpacaTransportError,
    AlpacaTransportFailureStage,
)
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)

NEW_YORK = subject._NEW_YORK
OBSERVATION = datetime(2026, 11, 4, 23, 59, 8, 218729, tzinfo=UTC)


def _provider_timestamp(session: date) -> str:
    return (
        datetime.combine(session, time.min, tzinfo=NEW_YORK)
        .astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _selected(observation: datetime = OBSERVATION) -> tuple[date, ...]:
    return select_latest_completed_sessions(observation)


def _body(sessions: tuple[date, ...]) -> bytes:
    payload = {
        "bars": {
            "SPY": [
                {
                    "o": 100 + index,
                    "h": 101 + index,
                    "l": 99 + index,
                    "c": 100 + index,
                    "v": 1000,
                    "t": _provider_timestamp(session),
                }
                for index, session in enumerate(sessions)
            ]
        },
        "next_page_token": None,
        "currency": "USD",
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _response(body: bytes) -> AlpacaHttpResponse:
    return AlpacaHttpResponse(
        status=200,
        headers=(
            ("Content-Type", "application/json"),
            ("X-Request-ID", "d34-test-request"),
        ),
        body=body,
        body_sha256=hashlib.sha256(body).hexdigest(),
        body_byte_length=len(body),
        request_id="d34-test-request",
        media_type="application/json",
    )


class _Scope:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def __enter__(self) -> _Scope:
        self.calls.append("enter")
        return self

    def __exit__(self, *args: object) -> None:
        self.calls.append("close")

    def use(self, consumer):  # type: ignore[no-untyped-def]
        self.calls.append("use")
        return consumer("key", "secret")


class _Transport:
    def __init__(self, response: AlpacaHttpResponse | Exception) -> None:
        self.response = response
        self.calls: list[object] = []

    def execute(self, request, *, api_key_id: str, api_secret_key: str):  # type: ignore[no-untyped-def]
        self.calls.append((request, api_key_id, api_secret_key))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _service(
    response: AlpacaHttpResponse | Exception,
    *,
    authority: object | None = None,
    calls: list[str] | None = None,
) -> tuple[subject.AlpacaSignalRecoveryInputService, _Transport, list[str]]:
    credential_calls = [] if calls is None else calls
    transport = _Transport(response)
    service = subject.AlpacaSignalRecoveryInputService(
        transport_factory=lambda: transport,
        credential_reader=lambda: _Scope(credential_calls),
        session_authority=authority,
    )
    return service, transport, credential_calls


def _end(request) -> str:  # type: ignore[no-untyped-def]
    return dict(parse_qsl(urlsplit(request.target).query, keep_blank_values=True))[
        "end"
    ]


@pytest.mark.parametrize(
    ("observation", "expected_session", "expected_end"),
    [
        (
            datetime(2026, 11, 4, 23, 59, tzinfo=UTC),
            date(2026, 11, 4),
            "2026-11-04T21:00:00.000000Z",
        ),
        (
            datetime(2026, 11, 4, 13, 0, tzinfo=UTC),
            date(2026, 11, 3),
            "2026-11-03T21:00:00.000000Z",
        ),
        (
            datetime(2026, 11, 7, 18, 0, tzinfo=UTC),
            date(2026, 11, 6),
            "2026-11-06T21:00:00.000000Z",
        ),
        (
            datetime(2026, 11, 26, 18, 0, tzinfo=UTC),
            date(2026, 11, 25),
            "2026-11-25T21:00:00.000000Z",
        ),
        (
            datetime(2026, 11, 27, 18, 0, tzinfo=UTC),
            date(2026, 11, 27),
            "2026-11-27T18:00:00.000000Z",
        ),
        (
            datetime(2026, 6, 1, 21, 0, tzinfo=UTC),
            date(2026, 6, 1),
            "2026-06-01T20:00:00.000000Z",
        ),
    ],
)
def test_cutoff_uses_exact_published_close_for_session_boundaries(
    observation: datetime, expected_session: date, expected_end: str
) -> None:
    sessions = _selected(observation)
    body = _body(sessions)
    service, transport, _ = _service(_response(body))
    result = service.observe(observation)

    assert result.status == "READY"
    assert result.selected_sessions[-1] == expected_session
    assert result.request is not None
    assert _end(result.request) == expected_end
    assert result.request.target.endswith("&feed=sip&currency=USD&sort=asc")
    assert result.inputs is not None
    assert result.inputs.cutoff == datetime.fromisoformat(
        expected_end.replace("Z", "+00:00")
    )
    assert result.inputs.cutoff <= observation
    assert len(transport.calls) == 1


def test_consumed_incident_observation_never_uses_calendar_end() -> None:
    sessions = _selected(OBSERVATION)
    service, _, _ = _service(_response(_body(sessions)))
    result = service.observe(OBSERVATION)

    assert result.status == "READY"
    assert result.request is not None
    assert _end(result.request) == "2026-11-04T21:00:00.000000Z"
    assert _end(result.request) != "2026-11-05T04:59:59.999999Z"


def test_request_and_completed_inputs_share_one_derived_cutoff() -> None:
    sessions = _selected()
    service, _, _ = _service(_response(_body(sessions)))
    result = service.observe(OBSERVATION)

    assert result.request is not None
    assert result.inputs is not None
    assert _end(result.request) == "2026-11-04T21:00:00.000000Z"
    assert result.inputs.cutoff == datetime(2026, 11, 4, 21, tzinfo=UTC)


def test_no_request_when_cutoff_authority_fails_before_credentials() -> None:
    class Authority:
        def __init__(self) -> None:
            self.delegate = NYSEPublishedRegularSessionAuthority()
            self.final_calls = 0

        def schedule_for(self, session_date: date) -> object | None:
            schedule = self.delegate.schedule_for(session_date)
            if session_date == date(2026, 11, 4):
                self.final_calls += 1
                if self.final_calls > 1:
                    return None
            return schedule

    calls: list[str] = []
    service, transport, calls = _service(
        _response(_body(_selected())), authority=Authority(), calls=calls
    )
    result = service.observe(OBSERVATION)

    assert result.status == "BLOCKED"
    assert result.reason == "D34_SESSION_AUTHORITY_UNAVAILABLE"
    assert result.failure_kind is subject.D34FailureKind.INTERNAL_FAILED
    assert result.request is None
    assert calls == []
    assert transport.calls == []


@pytest.mark.parametrize(
    "error",
    [
        AlpacaTransportError(AlpacaTransportFailureStage.REQUEST),
        AlpacaTransportError(AlpacaTransportFailureStage.RESPONSE_START),
        AlpacaTransportError(AlpacaTransportFailureStage.RESPONSE_BODY),
    ],
)
def test_transport_failures_preserve_only_closed_stage(error: Exception) -> None:
    service, _, _ = _service(error)
    result = service.observe(OBSERVATION)

    assert result.status == "BLOCKED"
    assert result.failure_kind is subject.D34FailureKind.TRANSPORT_FAILED
    assert result.transport_stage is error.stage  # type: ignore[attr-defined]
    assert result.metadata_reason is None
    assert result.http_status is None
    assert result.provider_code is None
    assert result.credential_read_count == 1
    assert result.provider_call_count == 1


@pytest.mark.parametrize("reason", list(AlpacaResponseMetadataFailureReason))
def test_response_metadata_failure_reasons_are_preserved_closed(
    reason: AlpacaResponseMetadataFailureReason,
) -> None:
    service, _, _ = _service(
        AlpacaTransportError(
            AlpacaTransportFailureStage.RESPONSE_METADATA,
            metadata_reason=reason,
        )
    )
    result = service.observe(OBSERVATION)

    assert result.failure_kind is subject.D34FailureKind.TRANSPORT_FAILED
    assert result.transport_stage is AlpacaTransportFailureStage.RESPONSE_METADATA
    assert result.metadata_reason is reason
    assert "SECRET_PROVIDER_TEXT" not in repr(result)


def test_http_failure_status_code_and_request_id_are_sanitized() -> None:
    service, _, _ = _service(
        AlpacaHttpStatusError(
            403,
            request_id="safe-provider-request",
            provider_code=42210000,
        )
    )
    result = service.observe(OBSERVATION)

    assert result.failure_kind is subject.D34FailureKind.HTTP_FAILED
    assert result.http_status == 403
    assert result.provider_code == 42210000
    assert (
        result.request_id_digest == hashlib.sha256(b"safe-provider-request").hexdigest()
    )
    assert "safe-provider-request" not in repr(result)


@pytest.mark.parametrize("status", [400, 401, 403, 422, 429, 500])
def test_common_http_statuses_remain_distinct(status: int) -> None:
    service, _, _ = _service(AlpacaHttpStatusError(status))
    result = service.observe(OBSERVATION)
    assert result.failure_kind is subject.D34FailureKind.HTTP_FAILED
    assert result.http_status == status


def test_unbounded_http_diagnostics_are_omitted() -> None:
    service, _, _ = _service(
        AlpacaHttpStatusError(
            99,
            request_id="invalid\nrequest-id",
            provider_code=-1,
        )
    )
    result = service.observe(OBSERVATION)
    assert result.failure_kind is subject.D34FailureKind.HTTP_FAILED
    assert result.http_status is None
    assert result.provider_code is None
    assert result.request_id_digest is None
    assert "invalid" not in repr(result)


def test_unexpected_provider_exception_is_fixed_internal_failure() -> None:
    service, _, _ = _service(RuntimeError("SECRET_PROVIDER_TEXT"))
    result = service.observe(OBSERVATION)
    assert result.failure_kind is subject.D34FailureKind.INTERNAL_FAILED
    assert result.reason == "D34_INTERNAL_FAILED"
    assert "SECRET_PROVIDER_TEXT" not in repr(result)


def test_response_invalid_and_session_mismatch_are_distinct() -> None:
    sessions = _selected()
    malformed = _response(b"{")
    service, _, _ = _service(malformed)
    invalid = service.observe(OBSERVATION)
    assert invalid.failure_kind is subject.D34FailureKind.RESPONSE_INVALID

    mismatch_sessions = (*sessions[:-1], date(2026, 11, 5))
    service, _, _ = _service(_response(_body(mismatch_sessions)))
    mismatch = service.observe(OBSERVATION)
    assert mismatch.failure_kind is subject.D34FailureKind.RESPONSE_SESSION_MISMATCH


def test_d34_result_rejects_inconsistent_diagnostic_combinations() -> None:
    with pytest.raises(ValueError):
        subject.D34SignalInputResult(
            "BLOCKED",
            "D34_HTTP_FAILED",
            OBSERVATION,
            (),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            1,
            1,
            subject.D34FailureKind.HTTP_FAILED,
            AlpacaTransportFailureStage.REQUEST,
            None,
            403,
            None,
        )


def _source() -> operator.SourceAdmission:
    return operator.SourceAdmission(
        operator.D34_FEATURE_BRANCH,
        "a" * 40,
        "b" * 40,
        "a" * 40,
        "a" * 40,
    )


def test_d33_cli_is_retired_before_provider_dispatch(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        d33_operator,
        "run_d33_read_only_observation",
        lambda **kwargs: pytest.fail("retired D33 CLI dispatched observation"),
    )
    code = d33_operator.main(["--evidence-dir", r"F:\AI\temp\new-d33-path"])
    output = json.loads(capsys.readouterr().out)
    assert code == 1
    assert output == {
        "evidence_path": None,
        "reason": "D33_CONSUMED_RETIRED",
        "status": "BLOCKED",
    }


def test_d33_help_remains_effect_free(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        d33_operator,
        "run_d33_read_only_observation",
        lambda **kwargs: pytest.fail("help dispatched observation"),
    )
    with pytest.raises(SystemExit) as error:
        d33_operator.main(["--help"])
    assert error.value.code == 0
    assert "--evidence-dir" in capsys.readouterr().out


def test_d34_help_and_construction_are_effect_free(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    assert (
        inspect.signature(operator.run_d34_read_only_observation)
        .parameters["clock"]
        .default
        is None
    )
    monkeypatch.setattr(
        operator,
        "run_d34_read_only_observation",
        lambda **kwargs: pytest.fail("help dispatched observation"),
    )
    with pytest.raises(SystemExit) as error:
        operator.main(["--help"])
    assert error.value.code == 0
    assert "--evidence-dir" in capsys.readouterr().out
    assert subject.AlpacaSignalRecoveryInputService(
        credential_reader=lambda: pytest.fail("construction read credentials")
    )


def test_d34_admission_precedes_credentials_provider_and_writes_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        operator,
        "_fresh_evidence_dir",
        lambda candidate: (candidate.mkdir(), candidate)[1],
    )
    events: list[str] = []
    evidence = tmp_path / "d34"
    sessions = _selected()
    transport = _Transport(_response(_body(sessions)))
    result = operator.run_d34_read_only_observation(
        evidence_dir=evidence,
        source_admitter=lambda root: (events.append("source"), _source())[1],
        credential_reader=lambda: (events.append("credentials"), _Scope(events))[1],
        transport_factory=lambda: (events.append("transport"), transport)[1],
        clock=lambda: OBSERVATION,
    )

    assert result.status == "READY"
    assert events[:3] == ["source", "credentials", "enter"]
    assert len(transport.calls) == 1
    assert result.evidence_path is not None
    evidence_json = json.loads(result.evidence_path.read_text(encoding="utf-8"))
    assert evidence_json["schema"] == "arch147-d34-alpaca-signal-observation/v1"
    assert evidence_json["predecessor"] == "D33"
    assert (
        evidence_json["predecessor_source_head"] == operator.D34_PREDECESSOR_SOURCE_HEAD
    )
    assert (
        evidence_json["predecessor_source_tree"] == operator.D34_PREDECESSOR_SOURCE_TREE
    )
    assert (
        evidence_json["predecessor_evidence_sha256"]
        == operator.D34_PREDECESSOR_EVIDENCE_SHA256
    )
    assert evidence_json["predecessor_evidence_byte_count"] == 1999
    assert evidence_json["failure_kind"] is None
    assert (
        evidence_json["request_id_digest"]
        == hashlib.sha256(b"d34-test-request").hexdigest()
    )


def test_d34_provider_failure_evidence_is_sanitized(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        operator,
        "_fresh_evidence_dir",
        lambda candidate: (candidate.mkdir(), candidate)[1],
    )
    evidence = tmp_path / "d34-failure"
    result = operator.run_d34_read_only_observation(
        evidence_dir=evidence,
        source_admitter=lambda root: _source(),
        credential_reader=lambda: _Scope([]),
        transport_factory=lambda: _Transport(
            AlpacaHttpStatusError(
                422,
                request_id="SECRET_PROVIDER_TEXT",
                provider_code=42210000,
            )
        ),
        clock=lambda: OBSERVATION,
    )

    assert result.status == "BLOCKED"
    assert result.signal_inputs is not None
    assert result.signal_inputs.failure_kind is subject.D34FailureKind.HTTP_FAILED
    assert result.evidence_path is not None
    evidence_text = result.evidence_path.read_text(encoding="utf-8")
    evidence_json = json.loads(evidence_text)
    assert evidence_json["failure_kind"] == "HTTP_FAILED"
    assert evidence_json["http_status"] == 422
    assert evidence_json["provider_code"] == 42210000
    assert (
        evidence_json["request_id_digest"]
        == hashlib.sha256(b"SECRET_PROVIDER_TEXT").hexdigest()
    )
    assert "SECRET_PROVIDER_TEXT" not in evidence_text


def _patch_source_topology(
    monkeypatch,  # type: ignore[no-untyped-def]
    *,
    develop: str,
    feature: str | None = None,
    origin: str = "https://github.com/callmedraken/ai-trading-bot.git",
    dirty: str = "",
    authority_failures: bool = False,
) -> list[str]:
    import scripts.checkpoint_runner as runner
    import scripts.current_source_authority as authority

    candidate = "a" * 40
    tree = "b" * 40
    remote_feature = candidate if feature is None else feature
    calls: list[str] = []

    def state(root):  # type: ignore[no-untyped-def]
        return {
            "branch": operator.D34_FEATURE_BRANCH,
            "porcelain": dirty,
            "head": candidate,
            "tree": tree,
        }

    def output(root, *args: str) -> str:  # type: ignore[no-untyped-def]
        if args == ("remote", "get-url", "origin"):
            return origin
        if args == ("show", "-s", "--format=%T", "HEAD"):
            return tree
        raise AssertionError(args)

    def remote_branch_head(root, branch: str) -> str:  # type: ignore[no-untyped-def]
        calls.append(branch)
        return develop if branch == "develop" else remote_feature

    monkeypatch.setattr(runner, "_git_state", state)
    monkeypatch.setattr(runner, "_git_output", output)
    monkeypatch.setattr(runner, "_remote_branch_head", remote_branch_head)
    monkeypatch.setattr(
        authority,
        "evaluate_source_authority",
        lambda *args, **kwargs: SimpleNamespace(
            failures=("blocked",) if authority_failures else ()
        ),
    )
    return calls


@pytest.mark.parametrize(
    "mutation",
    [
        {"develop": "c" * 40},
        {"feature": "c" * 40},
        {"origin": "https://github.com/other/repository.git"},
        {"dirty": " M source.py"},
        {"authority_failures": True},
    ],
)
def test_d34_source_admission_failures_are_before_provider(
    monkeypatch, mutation: dict[str, object]
) -> None:  # type: ignore[no-untyped-def]
    topology = {"develop": "a" * 40, **mutation}
    calls = _patch_source_topology(monkeypatch, **topology)
    with pytest.raises(RuntimeError):
        operator.admit_current_source(Path(__file__).resolve().parents[2])
    if not mutation.get("origin") and not mutation.get("dirty"):
        assert calls == ["develop", operator.D34_FEATURE_BRANCH]
    else:
        assert calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"develop": "c" * 40},
        {"feature": "c" * 40},
        {"origin": "https://github.com/other/repository.git"},
        {"dirty": " M source.py"},
        {"authority_failures": True},
    ],
)
def test_d34_operator_topology_blocks_before_credential_or_provider(
    monkeypatch, tmp_path: Path, mutation: dict[str, object]
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        operator,
        "_fresh_evidence_dir",
        lambda candidate: (candidate.mkdir(), candidate)[1],
    )
    topology = {"develop": "a" * 40, **mutation}
    _patch_source_topology(monkeypatch, **topology)
    events: list[str] = []
    result = operator.run_d34_read_only_observation(
        evidence_dir=tmp_path / "blocked",
        repo_root=Path(__file__).resolve().parents[2],
        source_admitter=operator.admit_current_source,
        credential_reader=lambda: (events.append("credentials"), _Scope(events))[1],
        transport_factory=lambda: (
            events.append("transport"),
            _Transport(RuntimeError("must not call")),
        )[1],
        clock=lambda: OBSERVATION,
    )
    assert result.status == "BLOCKED"
    assert result.reason == operator.D34_SOURCE_ADMISSION_FAILURE
    assert events == []


def test_d34_module_has_no_robinhood_provider_import() -> None:
    source = inspect.getsource(operator)
    assert "mcp__robinhood" not in source
    assert "robinhood" not in source.casefold().replace(
        "feature/robinhood-live-prototype-current", ""
    )


def test_d34_provenance_constants_bind_consumed_incident() -> None:
    assert operator.D34_PREDECESSOR_RESULT == "BLOCKED"
    assert operator.D34_PREDECESSOR_REASON == "D33_PROVIDER_REQUEST_FAILED"
    assert operator.D34_PREDECESSOR_PROVIDER_CALL_COUNT == 1
    assert operator.D34_PREDECESSOR_CREDENTIAL_READ_COUNT == 1
    assert len(operator.D34_PREDECESSOR_EVIDENCE_SHA256) == 64
    assert operator.D34_PREDECESSOR_EVIDENCE_BYTE_COUNT == 1999
