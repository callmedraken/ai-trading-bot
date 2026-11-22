from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from trading_bot.experiments import arch150_data_operator as operator
from trading_bot.market_data.alpaca_http import AlpacaHttpResponse

EXPECTED_HEAD = "a" * 40
EXPECTED_TREE = "b" * 40


def test_import_and_help_are_effect_free(monkeypatch, capsys):
    def forbidden():
        raise AssertionError("help must not construct effectful adapters")

    monkeypatch.setattr(operator, "_default_adapters", forbidden)
    assert operator.main([]) == 0
    assert "source boundary" in capsys.readouterr().out


def _facts(
    *, head: str = EXPECTED_HEAD, tree: str = EXPECTED_TREE
) -> operator.SourceFacts:
    return operator.SourceFacts(
        canonical_root=str(operator.CANONICAL_WORKTREE),
        branch=operator.FEATURE_BRANCH,
        head=head,
        tree=tree,
        origin=operator.CANONICAL_ORIGIN,
        upstream=f"origin/{operator.FEATURE_BRANCH}",
        porcelain="",
        live_feature_head=head,
        live_develop_head=head,
    )


def _adapters(
    *,
    source_probe=None,
    credential_reader=None,
    transport_factory=None,
    monotonic_clock=None,
    sleep_fn=None,
    attempt_id_factory=None,
) -> operator.OperatorAdapters:
    return operator.OperatorAdapters(
        source_probe=source_probe or _facts,
        authority_evaluator=lambda _root, _context: SimpleNamespace(
            passed=True, head=EXPECTED_HEAD, tree=EXPECTED_TREE
        ),
        credential_reader=credential_reader or (lambda: object()),
        credential_scope_validator=lambda value: isinstance(value, _FakeScope),
        transport_factory=transport_factory or (lambda: _FakeTransport(())),
        monotonic_clock=monotonic_clock or (lambda: 0),
        sleep_fn=sleep_fn or (lambda _seconds: None),
        attempt_id_factory=attempt_id_factory or (lambda: str(uuid4())),
    )


class _FakeScope:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def use(self, consumer):
        return consumer("fake-key", "fake-secret")

    def close(self) -> None:
        self.closed = True


@dataclass(frozen=True)
class _FakePage:
    body: bytes

    @property
    def response(self) -> AlpacaHttpResponse:
        return AlpacaHttpResponse(
            status=200,
            headers=(("Content-Type", "application/json"),),
            body=self.body,
            body_sha256=hashlib.sha256(self.body).hexdigest(),
            body_byte_length=len(self.body),
            request_id="fake-request-id",
            media_type="application/json",
        )


class _FakeTransport:
    def __init__(self, bodies: tuple[bytes, ...]) -> None:
        self._bodies = iter(bodies)
        self.requests: list[object] = []
        self.credential_pairs: list[tuple[str, str]] = []

    def execute(self, request, *, api_key_id: str, api_secret_key: str):
        self.requests.append(request)
        self.credential_pairs.append((api_key_id, api_secret_key))
        return _FakePage(next(self._bodies)).response


def _page(token: str | None, symbol: str = "SPY") -> bytes:
    return json.dumps(
        {"bars": {symbol: []}, "next_page_token": token}, separators=(",", ":")
    ).encode("utf-8")


def test_bad_interlock_and_source_mismatch_stop_before_effect_adapters(tmp_path):
    calls = {"credentials": 0, "transport": 0, "attempt_id": 0}

    def credentials():
        calls["credentials"] += 1
        raise AssertionError("fake credential reader must not be reached")

    def transport():
        calls["transport"] += 1
        raise AssertionError("fake provider must not be reached")

    adapters = _adapters(
        credential_reader=credentials,
        transport_factory=transport,
        attempt_id_factory=lambda: calls.__setitem__("attempt_id", 1) or "invalid",
    )
    result = operator.acquire_arch150_intraday_data(
        interlock="wrong",
        expected_head=EXPECTED_HEAD,
        expected_tree=EXPECTED_TREE,
        adapters=adapters,
    )
    assert result.failure_code == "INTERLOCK_REQUIRED"
    assert calls == {"credentials": 0, "transport": 0, "attempt_id": 0}

    for facts in (_facts(head="c" * 40), _facts(tree="d" * 40)):
        mismatch = _adapters(
            source_probe=lambda facts=facts: facts,
            credential_reader=credentials,
            transport_factory=transport,
            attempt_id_factory=lambda: calls.__setitem__("attempt_id", 1) or "invalid",
        )
        blocked = operator._run_one_shot(
            operator.ExpectedSource(EXPECTED_HEAD, EXPECTED_TREE),
            mismatch,
            output_root=tmp_path,
        )
        assert blocked.failure_code == "SOURCE_IDENTITY_MISMATCH"
    assert calls == {"credentials": 0, "transport": 0, "attempt_id": 0}
    assert tuple(tmp_path.iterdir()) == ()


def test_source_head_tree_and_authority_are_checked_before_fake_credentials(tmp_path):
    sequence = iter((_facts(), _facts(), _facts(head="c" * 40), _facts(head="c" * 40)))
    calls = {"credential": 0, "transport": 0}

    def read_credentials():
        calls["credential"] += 1
        return _FakeScope()

    def make_transport():
        calls["transport"] += 1
        return _FakeTransport(())

    adapters = _adapters(
        source_probe=lambda: next(sequence),
        credential_reader=read_credentials,
        transport_factory=make_transport,
    )
    outcome = operator._run_one_shot(
        operator.ExpectedSource(EXPECTED_HEAD, EXPECTED_TREE),
        adapters,
        output_root=tmp_path,
    )
    assert outcome.failure_code == "SOURCE_IDENTITY_MISMATCH"
    assert outcome.credential_read_attempt_count == 0
    assert outcome.provider_request_attempt_count == 0
    assert calls == {"credential": 0, "transport": 0}


def test_fake_pagination_pacing_and_immutable_raw_page_accounting(tmp_path):
    bodies = (_page("cursor-2"), _page(None), _page(None, "QQQ"))
    transport = _FakeTransport(bodies)
    scope = _FakeScope()
    clock = {"now": 0}
    sleeps: list[float] = []
    credential_reads: list[bool] = []

    def read_credentials() -> _FakeScope:
        credential_reads.append(True)
        return scope

    def sleep_for(seconds: float) -> None:
        sleeps.append(seconds)
        clock["now"] += int(seconds * 1_000_000_000)

    adapters = _adapters(
        credential_reader=read_credentials,
        transport_factory=lambda: transport,
        monotonic_clock=lambda: clock["now"],
        sleep_fn=sleep_for,
        attempt_id_factory=lambda: "00000000-0000-4000-8000-000000000123",
    )
    outcome = operator._run_one_shot(
        operator.ExpectedSource(EXPECTED_HEAD, EXPECTED_TREE),
        adapters,
        output_root=tmp_path,
    )

    assert outcome.classification == "BLOCKED"
    assert outcome.failure_code == "MISSING_EXPECTED_SLOT"
    assert outcome.credential_read_attempt_count == 1
    assert outcome.provider_request_attempt_count == 3
    assert outcome.successful_page_count == 3
    assert credential_reads == [True]
    assert scope.closed
    assert sleeps == [0.5, 0.5]
    assert transport.credential_pairs == [("fake-key", "fake-secret")] * 3
    assert len(transport.requests) == 3
    queries = [
        parse_qs(urlsplit(request.target).query) for request in transport.requests
    ]
    assert [query["symbols"] for query in queries] == [["SPY"], ["SPY"], ["QQQ"]]
    assert [query.get("page_token") for query in queries] == [None, ["cursor-2"], None]
    assert all(query["timeframe"] == ["1Min"] for query in queries)
    assert all(query["end"] == ["2023-12-31T23:59:59.999999Z"] for query in queries)

    assert outcome.attempt_directory is not None
    attempt = outcome.attempt_directory
    assert (attempt / "attempt.json").is_file()
    assert (attempt / "custody-evidence.json").is_file()
    assert (attempt / "attempt-result.json").is_file()
    assert not (attempt / "normalized.csv").exists()
    assert (attempt / "raw" / "SPY" / "0001.bin").read_bytes() == bodies[0]
    assert (attempt / "raw" / "SPY" / "0002.bin").read_bytes() == bodies[1]
    assert (attempt / "raw" / "QQQ" / "0001.bin").read_bytes() == bodies[2]
    evidence = json.loads((attempt / "custody-evidence.json").read_bytes())
    assert [
        (
            entry["symbol"],
            entry["ordinal"],
            entry["byte_length"],
            entry["terminal_state"],
        )
        for entry in evidence["raw_page_commitments"]
    ] == [
        ("SPY", 1, len(bodies[0]), "CONTINUE"),
        ("SPY", 2, len(bodies[1]), "NULL_TOKEN_EXHAUSTED"),
        ("QQQ", 1, len(bodies[2]), "NULL_TOKEN_EXHAUSTED"),
    ]
    assert evidence["effects"]["broker_calls"] == 0
    assert evidence["effects"]["order_mutations"] == 0
    assert evidence["effects"]["production_state_mutations"] == 0
    assert evidence["effects"]["strategy_pnl_evaluations"] == 0
    assert evidence["effects"]["holdout_accesses"] == 0
    assert evidence["effects"]["extension_accesses"] == 0
    assert "replay_program" not in operator.__dict__
    assert "evaluate_frozen_trial" not in operator.__dict__


def test_fake_request_failure_is_not_retried_and_qqq_is_not_started(tmp_path):
    requests = {"count": 0}

    class FailingTransport:
        def execute(self, _request, **_kwargs):
            requests["count"] += 1
            raise OSError("fake ambiguous request")

    adapters = _adapters(
        credential_reader=lambda: _FakeScope(),
        transport_factory=FailingTransport,
        attempt_id_factory=lambda: "00000000-0000-4000-8000-000000000124",
    )
    outcome = operator._run_one_shot(
        operator.ExpectedSource(EXPECTED_HEAD, EXPECTED_TREE),
        adapters,
        output_root=tmp_path,
    )
    assert outcome.failure_code == "PROVIDER_REQUEST_FAILED"
    assert outcome.provider_request_attempt_count == 1
    assert requests["count"] == 1
    assert not (outcome.attempt_directory / "raw" / "QQQ").exists()


def test_output_root_cannot_be_inside_repository_or_worktree(tmp_path):
    with pytest.raises(operator.Arch150OperatorError, match="OUTPUT_ROOT_INSIDE"):
        operator._validate_output_root(operator.CANONICAL_WORKTREE / "data")
    with pytest.raises(operator.Arch150OperatorError, match="OUTPUT_ROOT_MUST_BE_ON_F"):
        operator._validate_output_root(type(tmp_path)("C:/outside"))
