from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from scripts import current_source_authority
from trading_bot.domain import Bar, Symbol
from trading_bot.experiments import arch148_b2_operator as subject
from trading_bot.experiments import arch148_intraday as intraday
from trading_bot.experiments.historical_research_custody import canonical_json_bytes
from trading_bot.market_data.alpaca_http import AlpacaHttpResponse
from trading_bot.market_data.exceptions import (
    AlpacaHttpStatusError,
    AlpacaTransportError,
    AlpacaTransportFailureStage,
)
from trading_bot.review_paper.alpaca_windows_credentials import (
    ScopedAlpacaSecrets,
)

_HEAD = "a" * 40
_TREE = "b" * 40
_EXPECTED = subject.ExpectedSource(_HEAD, _TREE)
_REQUEST_ID = "request-id-raw-test-value"
_PAGE_TOKEN = "pagination-token-raw-test-value"


def _facts(**changes: str) -> subject.SourceFacts:
    values = {
        "canonical_root": str(subject.CANONICAL_WORKTREE),
        "branch": subject.FEATURE_BRANCH,
        "head": _HEAD,
        "tree": _TREE,
        "origin": subject.CANONICAL_ORIGIN,
        "upstream": f"origin/{subject.FEATURE_BRANCH}",
        "porcelain": "",
        "live_feature_head": _HEAD,
        "live_develop_head": _HEAD,
    }
    values.update(changes)
    return subject.SourceFacts(**values)


def _admission(
    *,
    facts: subject.SourceFacts | None = None,
    passed: bool = True,
    code: str | None = None,
) -> subject.SourceAdmission:
    return subject.SourceAdmission(
        passed,
        code,
        _facts() if facts is None else facts,
        passed,
        passed,
    )


def _page_body(
    symbol: str,
    *,
    token: str | None = None,
    stamp: str = "2016-01-04T14:30:00Z",
    bars: bool = True,
) -> bytes:
    data = {
        "bars": {
            symbol: (
                [
                    {
                        "t": stamp,
                        "o": 10,
                        "h": 11,
                        "l": 9,
                        "c": 10,
                        "v": 100,
                    }
                ]
                if bars
                else []
            )
        },
        "next_page_token": token,
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def _response(body: bytes, request_id: str = _REQUEST_ID) -> AlpacaHttpResponse:
    return AlpacaHttpResponse(
        status=200,
        headers=(("Content-Type", "application/json"), ("X-Request-ID", request_id)),
        body=body,
        body_sha256=hashlib.sha256(body).hexdigest(),
        body_byte_length=len(body),
        request_id=request_id,
        media_type="application/json",
    )


class _FakeTransport:
    def __init__(
        self, responses: list[object], *, attempt_directory: Path | None = None
    ):
        self.responses = list(responses)
        self.attempt_directory = attempt_directory
        self.calls: list[tuple[str, str | None]] = []

    def execute(self, request, *, api_key_id: str, api_secret_key: str):
        assert api_key_id == "test-api-key"
        assert api_secret_key == "test-api-secret"
        query = parse_qs(urlsplit(request.target).query)
        symbol = query["symbols"][0]
        token = query.get("page_token", [None])[0]
        self.calls.append((symbol, token))
        if self.attempt_directory is not None:
            sequence = len(self.calls)
            intent = (
                self.attempt_directory / "journal" / "intents" / f"{sequence:04d}.json"
            )
            assert intent.is_file()
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _page_accounting(symbol: str, bars: tuple[Bar, ...]) -> subject._PageAccounting:
    raw = f"raw-page-{symbol}".encode()
    return subject._PageAccounting(
        symbol,
        (hashlib.sha256(raw).hexdigest(),),
        (len(raw),),
        (hashlib.sha256(f"request-{symbol}".encode()).hexdigest(),),
        bars,
    )


def _one_session_dataset() -> tuple[
    intraday.IntradayDataset, intraday.IntradayCustodyEvidence
]:
    session = date(2023, 11, 24)
    slots = intraday.session_slots(session)
    symbols = tuple(
        intraday.IntradaySymbolDataset(
            symbol,
            tuple(
                Bar(
                    Symbol(symbol),
                    stamp,
                    Decimal("10"),
                    Decimal("11"),
                    Decimal("9"),
                    Decimal("10"),
                    100,
                )
                for stamp in slots
            ),
        )
        for symbol in intraday.INTRADAY_SYMBOLS
    )
    dataset = intraday.IntradayDataset(
        datetime(2023, 11, 24, tzinfo=UTC),
        datetime(2023, 11, 25, tzinfo=UTC),
        symbols,
    )
    collected = tuple(
        intraday.CollectedIntradayPages(
            symbol,
            dataset.bars_by_symbol[symbol],
            (hashlib.sha256(f"raw-{symbol}".encode()).hexdigest(),),
            (len(f"raw-{symbol}"),),
        )
        for symbol in intraday.INTRADAY_SYMBOLS
    )
    custody = intraday.build_intraday_custody_evidence(dataset, collected)
    return dataset, custody


def test_import_help_and_source_preflight_have_no_credential_or_provider_effect(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = {"credentials": 0, "provider": 0}

    def credentials():
        calls["credentials"] += 1
        raise AssertionError("credential access is forbidden in preflight")

    def transport_factory():
        calls["provider"] += 1
        raise AssertionError("provider construction is forbidden in preflight")

    monkeypatch.setattr(subject, "read_current_product_alpaca_secrets", credentials)
    monkeypatch.setattr(
        subject, "StdlibAlpacaHistoricalBarsTransport", transport_factory
    )
    monkeypatch.setattr(subject, "_read_source_facts", lambda: _facts())
    monkeypatch.setattr(
        current_source_authority,
        "evaluate_source_authority",
        lambda root, *, publication_context: SimpleNamespace(
            passed=True, head=_HEAD, tree=_TREE
        ),
    )

    assert "zero credential reads" in subject.operator_help()
    with pytest.raises(SystemExit) as help_exit:
        subject.main(["--help"])
    assert help_exit.value.code == 0
    assert subject.main([]) == 0
    result = subject.preflight_source(_EXPECTED)

    assert result.passed
    assert result.feature_authority_passed
    assert result.prospective_develop_authority_passed
    assert calls == {"credentials": 0, "provider": 0}


def test_wrong_interlock_fails_before_any_source_credential_or_provider_action(
    monkeypatch: pytest.MonkeyPatch,
):
    called = {"source": 0, "credentials": 0, "provider": 0}
    monkeypatch.setattr(
        subject,
        "preflight_source",
        lambda expected: called.__setitem__("source", called["source"] + 1),
    )
    monkeypatch.setattr(
        subject,
        "read_current_product_alpaca_secrets",
        lambda: called.__setitem__("credentials", called["credentials"] + 1),
    )
    monkeypatch.setattr(
        subject,
        "StdlibAlpacaHistoricalBarsTransport",
        lambda: called.__setitem__("provider", called["provider"] + 1),
    )

    with pytest.raises(subject.Arch148B2OperatorError) as error:
        subject.acquire_arch148_b2(
            interlock="almost the exact interlock",
            expected_head=_HEAD,
            expected_tree=_TREE,
        )

    assert error.value.code == "INTERLOCK_REQUIRED"
    assert called == {"source": 0, "credentials": 0, "provider": 0}


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    (
        ("canonical_root", r"F:\AI\other", "CANONICAL_WORKTREE_MISMATCH"),
        ("branch", "develop", "SOURCE_BRANCH_MISMATCH"),
        ("head", "c" * 40, "SOURCE_IDENTITY_MISMATCH"),
        ("tree", "d" * 40, "SOURCE_IDENTITY_MISMATCH"),
        ("origin", "https://example.invalid/repo.git", "SOURCE_REMOTE_MISMATCH"),
        ("upstream", "origin/develop", "SOURCE_REMOTE_MISMATCH"),
        ("porcelain", " M tracked.py", "SOURCE_NOT_CLEAN"),
        ("porcelain", "?? untracked.py", "SOURCE_NOT_CLEAN"),
        ("porcelain", "A  staged.py", "SOURCE_NOT_CLEAN"),
        ("live_feature_head", "e" * 40, "LIVE_REF_MISMATCH"),
        ("live_develop_head", "f" * 40, "LIVE_REF_MISMATCH"),
    ),
)
def test_source_admission_rejects_identity_remote_and_cleanliness_drift(
    field: str, value: str, expected_code: str
):
    facts = _facts(**{field: value})

    assert subject._source_facts_failure(_EXPECTED, facts) == expected_code


def test_attempt_directory_must_be_fresh_under_exact_non_reparse_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    attempt_id = "7f5bf84a-220a-4f54-9d85-60d5a9f07abc"
    attempt = tmp_path / f"arch148-b2-{attempt_id}"
    attempt.mkdir()

    with pytest.raises(subject.Arch148B2OperatorError) as existing:
        subject._validate_attempt_location(attempt, evidence_root=tmp_path)
    assert existing.value.code == "ATTEMPT_ALREADY_EXISTS"

    wrong_parent = tmp_path / "elsewhere" / attempt.name
    with pytest.raises(subject.Arch148B2OperatorError) as wrong:
        subject._validate_attempt_location(wrong_parent, evidence_root=tmp_path)
    assert wrong.value.code == "ATTEMPT_PARENT_MISMATCH"

    fresh_attempt = tmp_path / f"arch148-b2-{UUID(int=1)}"
    monkeypatch.setattr(
        subject,
        "_is_reparse_point",
        lambda path: Path(path) == tmp_path,
    )
    with pytest.raises(subject.Arch148B2OperatorError) as alias:
        subject._validate_attempt_location(fresh_attempt, evidence_root=tmp_path)
    assert alias.value.code == "ATTEMPT_PATH_ALIAS"


def test_attempt_claim_and_artifact_writes_are_create_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    attempt_id = "7f5bf84a-220a-4f54-9d85-60d5a9f07abc"
    path = subject._create_attempt_directory(attempt_id, _EXPECTED, _facts())
    claim_path = path / "attempt.json"
    original = claim_path.read_bytes()
    claim = json.loads(original)

    assert claim["attempt_id"] == attempt_id
    assert claim["automatic_retry"] == "FORBIDDEN"
    with pytest.raises(subject.Arch148B2OperatorError) as collision:
        subject._write_once(claim_path, b"replacement")
    assert collision.value.code == "OUTPUT_COLLISION"
    assert claim_path.read_bytes() == original


def test_claim_write_failure_reports_only_the_new_attempt_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_b1_contract_failure_code", lambda: None)
    monkeypatch.setattr(subject, "preflight_source", lambda expected: _admission())
    monkeypatch.setattr(subject, "uuid4", lambda: UUID(int=18))
    original_write_once = subject._write_once

    def fail_claim(path: Path, body: bytes) -> None:
        if path.name == "attempt.json":
            raise subject.Arch148B2OperatorError("OUTPUT_WRITE_FAILED")
        original_write_once(path, body)

    monkeypatch.setattr(subject, "_write_once", fail_claim)
    calls = {"credentials": 0, "provider": 0}
    monkeypatch.setattr(
        subject,
        "read_current_product_alpaca_secrets",
        lambda: calls.__setitem__("credentials", calls["credentials"] + 1),
    )
    monkeypatch.setattr(
        subject,
        "StdlibAlpacaHistoricalBarsTransport",
        lambda: calls.__setitem__("provider", calls["provider"] + 1),
    )

    outcome = subject.acquire_arch148_b2(
        interlock=subject.ACQUISITION_INTERLOCK,
        expected_head=_HEAD,
        expected_tree=_TREE,
    )

    expected_path = tmp_path / f"arch148-b2-{UUID(int=18)}"
    assert outcome.failure_code == "OUTPUT_WRITE_FAILED"
    assert outcome.attempt_id == str(UUID(int=18))
    assert outcome.attempt_directory == expected_path
    assert expected_path.is_dir()
    assert not (expected_path / "attempt.json").exists()
    assert outcome.credential_read_attempt_count == 0
    assert outcome.provider_request_attempt_count == 0
    assert calls == {"credentials": 0, "provider": 0}


def test_preexisting_attempt_collision_is_not_reported_as_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_b1_contract_failure_code", lambda: None)
    monkeypatch.setattr(subject, "preflight_source", lambda expected: _admission())
    monkeypatch.setattr(subject, "uuid4", lambda: UUID(int=19))
    existing = tmp_path / f"arch148-b2-{UUID(int=19)}"
    existing.mkdir()
    calls = {"credentials": 0, "provider": 0}
    monkeypatch.setattr(
        subject,
        "read_current_product_alpaca_secrets",
        lambda: calls.__setitem__("credentials", calls["credentials"] + 1),
    )
    monkeypatch.setattr(
        subject,
        "StdlibAlpacaHistoricalBarsTransport",
        lambda: calls.__setitem__("provider", calls["provider"] + 1),
    )

    outcome = subject.acquire_arch148_b2(
        interlock=subject.ACQUISITION_INTERLOCK,
        expected_head=_HEAD,
        expected_tree=_TREE,
    )

    assert outcome.failure_code == "ATTEMPT_ALREADY_EXISTS"
    assert outcome.attempt_id == str(UUID(int=19))
    assert outcome.attempt_directory is None
    assert list(existing.iterdir()) == []
    assert outcome.credential_read_attempt_count == 0
    assert outcome.provider_request_attempt_count == 0
    assert calls == {"credentials": 0, "provider": 0}


def test_b1_schedule_qualification_counts_are_frozen():
    assert subject._b1_contract_failure_code() is None
    assert len(intraday.expected_open_slots()) == subject.EXPECTED_SLOTS_PER_SYMBOL
    assert subject.EXPECTED_OPEN_SESSIONS == 2012
    assert subject.EXPECTED_EARLY_CLOSE_SESSIONS == 15
    assert subject.EXPECTED_TOTAL_BARS == 469_188
    assert subject.MAX_PAGES_PER_SYMBOL == 64
    assert subject.MAX_PROVIDER_REQUEST_ATTEMPTS == 192


def test_fetches_are_ordered_and_raw_pages_precede_b1_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    attempt = tmp_path / f"arch148-b2-{UUID(int=2)}"
    attempt.mkdir()
    bodies = [
        _page_body("QQQ", token=_PAGE_TOKEN),
        _page_body("QQQ", stamp="2016-01-04T14:35:00Z"),
        _page_body("TQQQ"),
        _page_body("SQQQ"),
    ]
    transport = _FakeTransport(
        [_response(body, f"request-{index}-raw") for index, body in enumerate(bodies)],
        attempt_directory=attempt,
    )
    original_parser = subject.parse_alpaca_intraday_page
    parse_order: list[tuple[str, bool]] = []

    def parse_after_raw_write(body: bytes, request: intraday.HistoricalIntradayRequest):
        ordinal = len(parse_order) + 1
        symbol = request.symbol
        raw_path = (
            attempt
            / "raw"
            / symbol
            / f"{2 if symbol == 'QQQ' and ordinal == 2 else 1:04d}.json"
        )
        if symbol == "QQQ" and ordinal == 2:
            raw_path = attempt / "raw" / symbol / "0002.json"
        parse_order.append(
            (symbol, raw_path.is_file() and raw_path.read_bytes() == body)
        )
        return original_parser(body, request)

    monkeypatch.setattr(subject, "parse_alpaca_intraday_page", parse_after_raw_write)
    collected, attempts, successes, failure = subject._fetch_all_symbols(
        attempt,
        str(UUID(int=2)),
        _EXPECTED,
        transport,
        "test-api-key",
        "test-api-secret",
    )

    assert failure is None
    assert attempts == successes == 4
    assert [symbol for symbol, _ in transport.calls] == ["QQQ", "QQQ", "TQQQ", "SQQQ"]
    assert all(exists for _, exists in parse_order)
    assert tuple(item.symbol for item in collected) == intraday.INTRADAY_SYMBOLS
    assert collected[0].raw_page_sha256 == tuple(
        hashlib.sha256(body).hexdigest() for body in bodies[:2]
    )

    authored = b"".join(
        path.read_bytes()
        for path in attempt.rglob("*")
        if path.is_file() and "raw" not in path.parts
    )
    assert _PAGE_TOKEN.encode() not in authored
    assert _REQUEST_ID.encode() not in authored
    assert all(
        f"request-{index}-raw".encode() not in authored for index in range(len(bodies))
    )
    assert hashlib.sha256(_PAGE_TOKEN.encode()).hexdigest().encode() in authored
    assert hashlib.sha256(b"request-1-raw").hexdigest().encode() in authored
    assert (attempt / "raw" / "QQQ" / "0001.json").read_bytes() == bodies[0]


@pytest.mark.parametrize(
    ("error", "expected_code"),
    (
        (
            AlpacaHttpStatusError(401, request_id=_REQUEST_ID),
            "AUTHENTICATION_OR_ENTITLEMENT",
        ),
        (
            AlpacaHttpStatusError(403, request_id=_REQUEST_ID),
            "AUTHENTICATION_OR_ENTITLEMENT",
        ),
        (AlpacaHttpStatusError(429, request_id=_REQUEST_ID), "RATE_LIMIT"),
        (AlpacaHttpStatusError(503, request_id=_REQUEST_ID), "PROVIDER_SERVER"),
        (
            AlpacaTransportError(AlpacaTransportFailureStage.REQUEST),
            "TRANSPORT_REQUEST",
        ),
        (
            AlpacaTransportError(AlpacaTransportFailureStage.RESPONSE_START),
            "TRANSPORT_RESPONSE_START",
        ),
        (
            AlpacaTransportError(AlpacaTransportFailureStage.RESPONSE_METADATA),
            "TRANSPORT_RESPONSE_METADATA",
        ),
        (
            AlpacaTransportError(AlpacaTransportFailureStage.RESPONSE_BODY),
            "TRANSPORT_RESPONSE_BODY",
        ),
        (RuntimeError("sensitive exception text"), "TRANSPORT_AMBIGUOUS"),
    ),
)
def test_transport_and_http_failures_leave_intent_and_never_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
    expected_code: str,
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    attempt = tmp_path / f"arch148-b2-{UUID(int=3)}"
    attempt.mkdir()
    transport = _FakeTransport([error], attempt_directory=attempt)

    _, attempts, successes, failure = subject._fetch_all_symbols(
        attempt,
        str(UUID(int=3)),
        _EXPECTED,
        transport,
        "test-api-key",
        "test-api-secret",
    )

    assert failure == expected_code
    assert attempts == 1
    assert successes == 0
    assert len(transport.calls) == 1
    intent = attempt / "journal" / "intents" / "0001.json"
    result = attempt / "journal" / "results" / "0001.json"
    assert intent.is_file()
    assert not result.exists()
    assert "MAY_HAVE_OCCURRED" not in intent.read_text(encoding="utf-8")


def test_page_and_global_request_ceilings_stop_before_the_next_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    attempt = tmp_path / f"arch148-b2-{UUID(int=4)}"
    attempt.mkdir()
    responses = [
        _response(_page_body("QQQ", token=f"token-{index}", bars=False))
        for index in range(subject.MAX_PAGES_PER_SYMBOL)
    ]
    transport = _FakeTransport(responses, attempt_directory=attempt)
    _, attempts, successes, failure = subject._fetch_all_symbols(
        attempt,
        str(UUID(int=4)),
        _EXPECTED,
        transport,
        "test-api-key",
        "test-api-secret",
    )
    assert failure == "PAGE_LIMIT_REACHED"
    assert attempts == successes == subject.MAX_PAGES_PER_SYMBOL
    assert len(transport.calls) == subject.MAX_PAGES_PER_SYMBOL

    global_attempt = tmp_path / f"arch148-b2-{UUID(int=5)}"
    global_attempt.mkdir()
    monkeypatch.setattr(subject, "MAX_PROVIDER_REQUEST_ATTEMPTS", 2)
    global_transport = _FakeTransport(
        [
            _response(_page_body("QQQ", token="next-1", bars=False)),
            _response(_page_body("QQQ", token="next-2", bars=False)),
        ],
        attempt_directory=global_attempt,
    )
    _, attempts, successes, failure = subject._fetch_all_symbols(
        global_attempt,
        str(UUID(int=5)),
        _EXPECTED,
        global_transport,
        "test-api-key",
        "test-api-secret",
    )
    assert failure == "GLOBAL_REQUEST_LIMIT_REACHED"
    assert attempts == successes == 2
    assert len(global_transport.calls) == 2


def test_repeated_page_token_stops_before_replaying_the_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    attempt = tmp_path / f"arch148-b2-{UUID(int=6)}"
    attempt.mkdir()
    transport = _FakeTransport(
        [
            _response(_page_body("QQQ", token="loop-token", bars=False)),
            _response(_page_body("QQQ", token="loop-token", bars=False)),
        ],
        attempt_directory=attempt,
    )

    _, attempts, successes, failure = subject._fetch_all_symbols(
        attempt,
        str(UUID(int=6)),
        _EXPECTED,
        transport,
        "test-api-key",
        "test-api-secret",
    )

    assert failure == "PAGINATION_TOKEN_LOOP"
    assert attempts == successes == 2
    assert len(transport.calls) == 2
    authored = b"".join(
        path.read_bytes()
        for path in attempt.rglob("*")
        if path.is_file() and "raw" not in path.parts
    )
    assert b"loop-token" not in authored
    assert hashlib.sha256(b"loop-token").hexdigest().encode() in authored


def test_source_drift_after_an_intent_stops_before_the_next_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    facts = iter((_facts(), _facts(head="c" * 40)))
    monkeypatch.setattr(subject, "_read_source_facts", lambda: next(facts))
    attempt = tmp_path / f"arch148-b2-{UUID(int=13)}"
    attempt.mkdir()
    transport = _FakeTransport(
        [_response(_page_body("QQQ", token="next-page", bars=False))],
        attempt_directory=attempt,
    )

    _, attempts, successes, failure = subject._fetch_all_symbols(
        attempt,
        str(UUID(int=13)),
        _EXPECTED,
        transport,
        "test-api-key",
        "test-api-secret",
    )

    assert failure == "SOURCE_IDENTITY_MISMATCH"
    assert attempts == successes == 1
    assert len(transport.calls) == 1
    assert (attempt / "journal" / "intents" / "0001.json").is_file()
    assert (attempt / "journal" / "results" / "0001.json").is_file()
    assert not (attempt / "journal" / "intents" / "0002.json").exists()


def test_page_order_and_unexpected_symbol_are_rejected_without_filtering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    attempt = tmp_path / f"arch148-b2-{UUID(int=14)}"
    attempt.mkdir()
    out_of_order = _FakeTransport(
        [
            _response(_page_body("QQQ", token="next")),
            _response(_page_body("QQQ", stamp="2016-01-04T14:25:00Z")),
        ],
        attempt_directory=attempt,
    )
    _, attempts, successes, failure = subject._fetch_all_symbols(
        attempt,
        str(UUID(int=14)),
        _EXPECTED,
        out_of_order,
        "test-api-key",
        "test-api-secret",
    )
    assert failure == "PROVIDER_ORDER_INVALID"
    assert attempts == 2
    assert successes == 1
    assert len(out_of_order.calls) == 2

    unexpected_attempt = tmp_path / f"arch148-b2-{UUID(int=15)}"
    unexpected_attempt.mkdir()
    unexpected = _FakeTransport(
        [_response(_page_body("TQQQ"))],
        attempt_directory=unexpected_attempt,
    )
    _, attempts, successes, failure = subject._fetch_all_symbols(
        unexpected_attempt,
        str(UUID(int=15)),
        _EXPECTED,
        unexpected,
        "test-api-key",
        "test-api-secret",
    )
    assert failure == "MALFORMED_PROVIDER_PAGE"
    assert attempts == 1
    assert successes == 0
    assert len(unexpected.calls) == 1
    assert (unexpected_attempt / "raw" / "QQQ" / "0001.json").is_file()


def test_raw_page_is_preserved_before_malformed_body_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    attempt = tmp_path / f"arch148-b2-{UUID(int=7)}"
    attempt.mkdir()
    body = b'{"not":"a valid provider response"}'
    transport = _FakeTransport([_response(body)], attempt_directory=attempt)

    _, attempts, successes, failure = subject._fetch_all_symbols(
        attempt,
        str(UUID(int=7)),
        _EXPECTED,
        transport,
        "test-api-key",
        "test-api-secret",
    )

    assert failure == "MALFORMED_PROVIDER_PAGE"
    assert attempts == 1
    assert successes == 0
    assert (attempt / "raw" / "QQQ" / "0001.json").read_bytes() == body


def test_empty_successful_response_is_preserved_before_parser_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    attempt = tmp_path / f"arch148-b2-{UUID(int=17)}"
    attempt.mkdir()
    transport = _FakeTransport([_response(b"")], attempt_directory=attempt)

    _, attempts, successes, failure = subject._fetch_all_symbols(
        attempt,
        str(UUID(int=17)),
        _EXPECTED,
        transport,
        "test-api-key",
        "test-api-secret",
    )

    assert failure == "MALFORMED_PROVIDER_PAGE"
    assert attempts == 1
    assert successes == 0
    assert len(transport.calls) == 1
    assert (attempt / "journal" / "intents" / "0001.json").is_file()
    assert (attempt / "journal" / "results" / "0001.json").is_file()
    raw_page = attempt / "raw" / "QQQ" / "0001.json"
    assert raw_page.is_file()
    assert raw_page.read_bytes() == b""


def test_acquisition_counts_credential_read_failure_once_and_keeps_failure_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_b1_contract_failure_code", lambda: None)
    monkeypatch.setattr(subject, "preflight_source", lambda expected: _admission())
    monkeypatch.setattr(subject, "uuid4", lambda: UUID(int=8))
    reads = 0

    def failed_reader():
        nonlocal reads
        reads += 1
        raise RuntimeError("credential secret and backend details")

    monkeypatch.setattr(subject, "read_current_product_alpaca_secrets", failed_reader)
    monkeypatch.setattr(
        subject,
        "StdlibAlpacaHistoricalBarsTransport",
        lambda: pytest.fail("transport should not be constructed after reader failure"),
    )

    outcome = subject.acquire_arch148_b2(
        interlock=subject.ACQUISITION_INTERLOCK,
        expected_head=_HEAD,
        expected_tree=_TREE,
    )

    assert reads == 1
    assert outcome.classification == "BLOCKED"
    assert outcome.failure_code == "CREDENTIAL_READ_FAILED"
    assert outcome.credential_read_attempt_count == 1
    assert outcome.provider_request_attempt_count == 0
    failure = (outcome.attempt_directory / "failure.json").read_text(encoding="utf-8")
    assert "credential secret" not in failure
    assert "backend details" not in failure


def test_source_block_before_output_has_zero_credential_and_provider_attempts(
    monkeypatch: pytest.MonkeyPatch,
):
    called = {"credentials": 0, "provider": 0}
    monkeypatch.setattr(
        subject,
        "preflight_source",
        lambda expected: _admission(passed=False, code="SOURCE_IDENTITY_MISMATCH"),
    )
    monkeypatch.setattr(
        subject,
        "read_current_product_alpaca_secrets",
        lambda: called.__setitem__("credentials", called["credentials"] + 1),
    )
    monkeypatch.setattr(
        subject,
        "StdlibAlpacaHistoricalBarsTransport",
        lambda: called.__setitem__("provider", called["provider"] + 1),
    )

    outcome = subject.acquire_arch148_b2(
        interlock=subject.ACQUISITION_INTERLOCK,
        expected_head=_HEAD,
        expected_tree=_TREE,
    )

    assert outcome.failure_code == "SOURCE_IDENTITY_MISMATCH"
    assert outcome.credential_read_attempt_count == 0
    assert outcome.provider_request_attempt_count == 0
    assert called == {"credentials": 0, "provider": 0}


def test_scope_closes_and_arbitrary_transport_text_never_enters_failure_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_b1_contract_failure_code", lambda: None)
    monkeypatch.setattr(subject, "preflight_source", lambda expected: _admission())
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    monkeypatch.setattr(subject, "uuid4", lambda: UUID(int=9))
    scope = ScopedAlpacaSecrets("test-api-key", "test-api-secret")
    transport = _FakeTransport([RuntimeError("sensitive provider exception text")])
    monkeypatch.setattr(subject, "read_current_product_alpaca_secrets", lambda: scope)
    monkeypatch.setattr(
        subject, "StdlibAlpacaHistoricalBarsTransport", lambda: transport
    )

    outcome = subject.acquire_arch148_b2(
        interlock=subject.ACQUISITION_INTERLOCK,
        expected_head=_HEAD,
        expected_tree=_TREE,
    )

    assert outcome.failure_code == "TRANSPORT_AMBIGUOUS"
    assert outcome.credential_read_attempt_count == 1
    assert outcome.provider_request_attempt_count == 1
    assert scope._closed
    assert len(transport.calls) == 1
    attempt = outcome.attempt_directory
    assert (attempt / "journal" / "intents" / "0001.json").is_file()
    assert not (attempt / "journal" / "results" / "0001.json").exists()
    failure = json.loads((attempt / "failure.json").read_text(encoding="utf-8"))
    assert failure["unresolved_intent_status"] == "MAY_HAVE_OCCURRED"
    authored = b"".join(
        path.read_bytes() for path in attempt.rglob("*") if path.is_file()
    )
    assert b"sensitive provider exception text" not in authored
    assert b"test-api-key" not in authored
    assert b"test-api-secret" not in authored


def test_post_provider_source_drift_blocks_success_and_preserves_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(subject, "_b1_contract_failure_code", lambda: None)
    admissions = iter(
        (
            _admission(),
            _admission(),
            _admission(passed=False, code="SOURCE_IDENTITY_MISMATCH"),
        )
    )
    monkeypatch.setattr(subject, "preflight_source", lambda expected: next(admissions))
    monkeypatch.setattr(subject, "_local_live_source_check", lambda expected: None)
    monkeypatch.setattr(subject, "uuid4", lambda: UUID(int=10))
    scope = ScopedAlpacaSecrets("test-api-key", "test-api-secret")
    transport = _FakeTransport(
        [_response(_page_body(symbol)) for symbol in intraday.INTRADAY_SYMBOLS]
    )
    monkeypatch.setattr(subject, "read_current_product_alpaca_secrets", lambda: scope)
    monkeypatch.setattr(
        subject, "StdlibAlpacaHistoricalBarsTransport", lambda: transport
    )

    outcome = subject.acquire_arch148_b2(
        interlock=subject.ACQUISITION_INTERLOCK,
        expected_head=_HEAD,
        expected_tree=_TREE,
    )

    assert outcome.failure_code == "SOURCE_IDENTITY_MISMATCH"
    assert outcome.provider_request_attempt_count == 3
    assert [symbol for symbol, _ in transport.calls] == list(intraday.INTRADAY_SYMBOLS)
    assert (outcome.attempt_directory / "failure.json").is_file()
    assert not (outcome.attempt_directory / "evidence.json").exists()


def test_dataset_custody_roundtrip_and_artifact_write_reuse_b1_canonical_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    attempt = tmp_path / f"arch148-b2-{UUID(int=11)}"
    attempt.mkdir()
    dataset, custody = _one_session_dataset()
    normalized, dataset_bytes, custody_bytes = subject._write_data_artifacts(
        attempt, dataset, custody
    )

    assert intraday.IntradayDataset.from_json(dataset_bytes) == dataset
    assert intraday.IntradayCustodyEvidence.from_json(custody_bytes) == custody
    intraday.verify_intraday_custody_evidence(dataset, custody)
    assert (attempt / "dataset.json").read_bytes() == dataset.to_json().encode()
    assert (
        attempt / "custody-evidence.json"
    ).read_bytes() == custody.to_json().encode()
    for item in dataset.datasets:
        body = (attempt / "normalized" / f"{item.symbol}.csv").read_bytes()
        assert body == item.normalized_bytes
        assert normalized[item.symbol]["sha256"] == hashlib.sha256(body).hexdigest()
        assert normalized[item.symbol]["bar_count"] == len(item.bars)

    mismatched = replace(custody, dataset_identity="different-dataset")
    with pytest.raises(intraday.Arch148IntradayError):
        intraday.verify_intraday_custody_evidence(dataset, mismatched)


def test_artifact_and_raw_page_readback_drift_is_detected(tmp_path: Path):
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b"expected")
    with pytest.raises(subject.Arch148B2OperatorError) as mismatch:
        subject._verify_file(artifact, b"different")
    assert mismatch.value.code == "ARTIFACT_READBACK_MISMATCH"

    with pytest.raises(subject.Arch148B2OperatorError) as missing:
        subject._verify_file(tmp_path / "missing.json", b"expected")
    assert missing.value.code == "ARTIFACT_READBACK_FAILED"


def test_terminal_evidence_binds_zero_effects_and_never_contains_token_or_request_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    attempt = tmp_path / f"arch148-b2-{UUID(int=12)}"
    attempt.mkdir()
    dataset, custody = _one_session_dataset()
    normalized, dataset_bytes, custody_bytes = subject._write_data_artifacts(
        attempt, dataset, custody
    )
    accounting = tuple(
        subject._PageAccounting(
            symbol,
            (hashlib.sha256(f"page-{symbol}".encode()).hexdigest(),),
            (len(f"page-{symbol}"),),
            (hashlib.sha256(f"request-id-{symbol}".encode()).hexdigest(),),
            dataset.bars_by_symbol[symbol],
        )
        for symbol in intraday.INTRADAY_SYMBOLS
    )
    evidence = subject._terminal_evidence(
        _EXPECTED,
        _facts(),
        str(UUID(int=12)),
        1,
        3,
        3,
        accounting,
        dataset,
        custody,
        dataset_bytes,
        custody_bytes,
        normalized,
    )
    body = canonical_json_bytes(evidence)

    assert evidence["classification"] == subject.SUCCESS_CLASSIFICATION
    assert evidence["credential_read_attempt_count"] == 1
    assert evidence["provider_request_attempt_count"] == 3
    assert evidence["automatic_retry"] == "FORBIDDEN"
    assert evidence["robinhood_calls"] == 0
    assert evidence["broker_calls"] == 0
    assert evidence["order_mutations"] == 0
    assert evidence["production_state_mutations"] == 0
    assert evidence["final_holdout_accesses"] == 0
    assert evidence["baseline_backtests"] == 0
    assert _PAGE_TOKEN.encode() not in body
    assert _REQUEST_ID.encode() not in body


def test_successful_terminal_artifact_collision_never_overwrites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(subject, "EVIDENCE_ROOT", tmp_path)
    attempt = tmp_path / f"arch148-b2-{UUID(int=16)}"
    attempt.mkdir()
    path = attempt / "evidence.json"
    path.write_bytes(b"prior evidence")

    with pytest.raises(subject.Arch148B2OperatorError) as collision:
        subject._write_once(path, b"new evidence")

    assert collision.value.code == "OUTPUT_COLLISION"
    assert path.read_bytes() == b"prior evidence"
