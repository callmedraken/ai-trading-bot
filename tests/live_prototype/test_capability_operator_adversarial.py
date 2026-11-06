"""Adversarial fake-only checks for the source-admitted L41 operator."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.current_source_authority import PublicationContext

from trading_bot.live_prototype import capability_operator as operator
from trading_bot.live_prototype.capability_observer import OverallStatus
from trading_bot.live_prototype.capability_transport import CapabilityTransportCounts

_ACCOUNT = "SECRET_ACCOUNT_NUMBER_4831"
_PROVIDER_TEXT = "SECRET_PROVIDER_TEXT_1927"
_TOKEN_TEXT = "SECRET_TOKEN_TEXT_7754"
_OAUTH = object()
_HEAD = "a" * 40
_TREE = "b" * 40
_TRANSPORT_COUNT_FIELDS = (
    "oauth_scope_entry_attempts",
    "mcp_session_open_attempts",
    "get_accounts_attempts",
    "get_equity_tradability_attempts",
)
_COLLECTOR_COUNT_FIELDS = (
    "get_accounts",
    "get_equity_tradability",
)


def _admit_from_test_checkout(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Use this test checkout only after the production root gate."""

    monkeypatch.setattr(operator, "_CANONICAL_ROOT", root.resolve(strict=True))


def _fake_fresh_evidence_dir(sandbox_root: Path):
    """Test-only create-once evidence admission under a pytest sandbox."""

    sandbox = sandbox_root.resolve(strict=True)

    def admit(candidate: Path) -> Path:
        path = Path(candidate)
        if not path.is_absolute() or path.exists() or path.is_symlink():
            raise ValueError("L41_EVIDENCE_PATH_INVALID")
        try:
            parent = path.parent.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError("L41_EVIDENCE_PATH_INVALID") from None
        if parent != path.parent or not parent.is_relative_to(sandbox):
            raise ValueError("L41_EVIDENCE_PATH_INVALID")
        current = parent
        while True:
            if current.resolve(strict=True) != current or current.is_symlink():
                raise ValueError("L41_EVIDENCE_PATH_INVALID")
            if current == sandbox:
                break
            if current.parent == current or not current.is_relative_to(sandbox):
                raise ValueError("L41_EVIDENCE_PATH_INVALID")
            current = current.parent
        path.mkdir()
        return path

    return admit


@pytest.fixture(autouse=True)
def fake_evidence_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    sandbox = tmp_path / "fake-evidence-root"
    sandbox.mkdir()
    monkeypatch.setattr(
        operator, "_fresh_evidence_dir", _fake_fresh_evidence_dir(sandbox)
    )


def _source() -> operator.SourceAdmission:
    return operator.SourceAdmission(
        branch=operator.L41_FEATURE_BRANCH,
        head=_HEAD,
        tree=_TREE,
        origin_feature_head=_HEAD,
        origin_feature_tree=_TREE,
        origin_develop_head=_HEAD,
        origin_develop_tree=_TREE,
        feature_authority="PASS",
        prospective_develop_authority="PASS",
    )


def _accounts() -> dict[str, object]:
    return {
        "data": {
            "accounts": [
                {
                    "account_number": _ACCOUNT,
                    "agentic_allowed": True,
                    "brokerage_account_type": "individual",
                    "state": "active",
                    "deactivated": False,
                    "permanently_deactivated": False,
                }
            ]
        }
    }


def _tradability() -> dict[str, object]:
    return {
        "data": {
            "results": [
                {
                    "symbol": "SPY",
                    "tradeable": True,
                    "state": "active",
                    "fractional_tradability": "tradable",
                    "account_type_tradabilities": [
                        {
                            "account_type": "individual",
                            "account_type_tradability": "tradable",
                        }
                    ],
                }
            ]
        }
    }


class _FakeTransport:
    """Read-only fake that records attempts before simulated failures."""

    def __init__(
        self,
        oauth_factory,
        events: list[str],
        *,
        failure: str | None = None,
        counts_mode: str = "normal",
    ) -> None:
        self._oauth_factory = oauth_factory
        self._events = events
        self._failure = failure
        self._counts_mode = counts_mode
        self.oauth_attempts = 0
        self.session_attempts = 0
        self.accounts_attempts = 0
        self.tradability_attempts = 0
        self.calls: list[tuple[str, object]] = []

    @property
    def call_counts(self):
        if self._counts_mode == "missing":
            raise AttributeError("missing call_counts")
        if self._counts_mode == "raising":
            raise RuntimeError(_TOKEN_TEXT)
        if self._counts_mode == "malformed":
            return object()
        return CapabilityTransportCounts(
            self.oauth_attempts,
            self.session_attempts,
            self.accounts_attempts,
            self.tradability_attempts,
        )

    def __enter__(self):
        self.oauth_attempts += 1
        self._events.append("oauth_scope_entry")
        if self._failure == "oauth":
            self._oauth_factory()
        self._oauth_factory()
        self.session_attempts += 1
        self._events.append("session_open")
        if self._failure == "session":
            raise RuntimeError(_PROVIDER_TEXT)
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self._events.append("session_close")
        return False

    def get_accounts(self) -> dict[str, object]:
        self.accounts_attempts += 1
        self._events.append("get_accounts")
        self.calls.append(("get_accounts", {}))
        if self._failure == "accounts":
            raise RuntimeError(_PROVIDER_TEXT)
        return _accounts()

    def get_equity_tradability(self, arguments: dict[str, object]) -> dict[str, object]:
        self.tradability_attempts += 1
        self._events.append("get_equity_tradability")
        self.calls.append(("get_equity_tradability", dict(arguments)))
        if self._failure == "tradability":
            raise RuntimeError(_PROVIDER_TEXT)
        return _tradability()


def _install_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    events: list[str],
    *,
    failure: str | None = None,
    counts_mode: str = "normal",
    admission_error: Exception | None = None,
    oauth_builder_error: Exception | None = None,
) -> list[_FakeTransport]:
    transports: list[_FakeTransport] = []

    def source_admitter(repo_root: Path | None = None) -> operator.SourceAdmission:
        events.append("source_admission")
        if admission_error is not None:
            raise admission_error
        return _source()

    def oauth_factory_builder():
        events.append("oauth_factory_builder")
        if oauth_builder_error is not None:
            raise oauth_builder_error

        def oauth_factory():
            if failure == "oauth":
                raise RuntimeError(_TOKEN_TEXT)
            return _OAUTH

        return oauth_factory

    def transport_builder(oauth_factory):
        events.append("transport_construct")
        transport = _FakeTransport(
            oauth_factory,
            events,
            failure=failure,
            counts_mode=counts_mode,
        )
        transports.append(transport)
        return transport

    real_collector = operator.collect_capabilities

    def collector(boundary):
        events.append("collector")
        return real_collector(boundary)

    monkeypatch.setattr(operator, "admit_l41_source", source_admitter)
    monkeypatch.setattr(
        operator, "_create_windows_oauth_factory", oauth_factory_builder
    )
    monkeypatch.setattr(operator, "RobinhoodCapabilityTransport", transport_builder)
    monkeypatch.setattr(operator, "collect_capabilities", collector)
    return transports


def _evidence_json(result: operator.CapabilityOperatorResult) -> dict[str, object]:
    assert result.evidence_path is not None
    return json.loads(result.evidence_path.read_text(encoding="utf-8"))


def _assert_unknown_counts(counts: object, fields: tuple[str, ...]) -> None:
    assert counts is None or all(
        getattr(counts, field, None) is None for field in fields
    )


def _fake_git(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dirty_status: str = "",
    branch: str = operator.L41_FEATURE_BRANCH,
    feature_head: str = _HEAD,
    develop_head: str = _HEAD,
    authority_passes: bool = True,
) -> tuple[list[tuple[str, ...]], list[PublicationContext]]:
    _admit_from_test_checkout(monkeypatch, Path(__file__).resolve().parents[2])
    commands: list[tuple[str, ...]] = []
    contexts: list[PublicationContext] = []

    def run(command: list[str], **_kwargs):
        arguments = tuple(command[3:])
        commands.append(arguments)
        if arguments == ("branch", "--show-current"):
            output = branch
        elif arguments == ("status", "--porcelain=v1", "--untracked-files=all"):
            output = dirty_status
        elif arguments == ("rev-parse", "--verify", "HEAD"):
            output = _HEAD
        elif arguments == ("rev-parse", "HEAD^{tree}"):
            output = _TREE
        elif arguments == ("remote", "get-url", "origin"):
            output = "https://github.com/callmedraken/ai-trading-bot.git"
        elif arguments[:4] == ("ls-remote", "--exit-code", "--heads", "origin"):
            reference = arguments[4]
            remote_head = (
                feature_head
                if reference == f"refs/heads/{operator.L41_FEATURE_BRANCH}"
                else develop_head
            )
            output = f"{remote_head}\t{reference}"
        else:
            raise AssertionError(f"unexpected Git command: {arguments!r}")
        return SimpleNamespace(returncode=0, stdout=output, stderr="")

    def evaluate(_root: Path, *, publication_context: PublicationContext):
        contexts.append(publication_context)
        return SimpleNamespace(
            passed=authority_passes,
            head=_HEAD,
            tree=_TREE,
            checkpoints=(operator.L41_CHECKPOINT_OWNER,),
        )

    monkeypatch.setattr(operator.subprocess, "run", run)
    monkeypatch.setattr(operator, "evaluate_source_authority", evaluate)
    return commands, contexts


@pytest.fixture
def evidence_dir(tmp_path: Path) -> Path:
    return tmp_path / "fake-evidence-root" / "observation"


def test_admission_rejects_dirty_or_stale_source_before_authority_evaluation(
    monkeypatch: pytest.MonkeyPatch,
):
    cases = (
        {"dirty_status": " M src/trading_bot/live_prototype/live_contract.py"},
        {"feature_head": "c" * 40},
        {"develop_head": "d" * 40},
        {"branch": "feature/unrelated"},
    )
    for case in cases:
        commands, contexts = _fake_git(monkeypatch, **case)
        with pytest.raises(RuntimeError, match="L41_SOURCE_ADMISSION_BLOCKED"):
            operator.admit_l41_source()
        assert contexts == []
        assert all(command[0] != "ls-remote" for command in commands) or (
            "dirty_status" not in case and "branch" not in case
        )


def test_admission_requires_exact_feature_and_develop_identity_and_both_authorities(
    monkeypatch: pytest.MonkeyPatch,
):
    _commands, contexts = _fake_git(monkeypatch)

    admitted = operator.admit_l41_source()

    assert admitted.branch == operator.L41_FEATURE_BRANCH
    assert admitted.head == _HEAD
    assert admitted.tree == _TREE
    assert admitted.origin_feature_head == _HEAD
    assert admitted.origin_feature_tree == _TREE
    assert admitted.origin_develop_head == _HEAD
    assert admitted.origin_develop_tree == _TREE
    assert admitted.feature_authority == "PASS"
    assert admitted.prospective_develop_authority == "PASS"
    assert contexts == [
        PublicationContext.FEATURE,
        PublicationContext.PROSPECTIVE_DEVELOP,
    ]


def test_admission_failure_precedes_oauth_and_returns_sanitized_evidence(
    monkeypatch: pytest.MonkeyPatch, evidence_dir: Path
):
    events: list[str] = []
    _install_fake_runtime(
        monkeypatch,
        events,
        admission_error=RuntimeError(f"{_PROVIDER_TEXT} {_ACCOUNT} {_TOKEN_TEXT}"),
    )

    result = operator.run_l41_read_only_observation(evidence_dir=evidence_dir)

    assert result.status is OverallStatus.BLOCKED
    assert result.reason == "L41_SOURCE_ADMISSION_BLOCKED"
    assert result.evidence.source is None
    assert result.evidence_path is not None
    assert events == ["source_admission"]
    assert result.evidence.transport_counts == CapabilityTransportCounts(0, 0, 0, 0)
    assert result.evidence.collector_invocations == 0
    rendered = repr(result) + json.dumps(_evidence_json(result), sort_keys=True)
    for secret in (_PROVIDER_TEXT, _ACCOUNT, _TOKEN_TEXT):
        assert secret not in rendered


def test_invalid_or_reused_evidence_path_stops_before_source_or_oauth(
    monkeypatch: pytest.MonkeyPatch, evidence_dir: Path, tmp_path: Path
):
    events: list[str] = []
    _install_fake_runtime(monkeypatch, events)

    existing = operator.run_l41_read_only_observation(evidence_dir=evidence_dir.parent)
    outside = operator.run_l41_read_only_observation(
        evidence_dir=Path(r"F:\AI\worktrees\outside-observation")
    )

    assert existing.reason == "L41_EVIDENCE_PATH_INVALID"
    assert outside.reason == "L41_EVIDENCE_PATH_INVALID"
    assert existing.evidence_path is None
    assert outside.evidence_path is None
    assert events == []
    assert not evidence_dir.exists()


def test_reused_evidence_path_does_not_repeat_admission_or_reads(
    monkeypatch: pytest.MonkeyPatch, evidence_dir: Path
):
    events: list[str] = []
    transports = _install_fake_runtime(monkeypatch, events)

    first = operator.run_l41_read_only_observation(evidence_dir=evidence_dir)
    first_events = list(events)
    second = operator.run_l41_read_only_observation(evidence_dir=evidence_dir)

    assert first.evidence_path == evidence_dir / "evidence.json"
    assert second.evidence_path is None
    assert second.reason == "L41_EVIDENCE_PATH_INVALID"
    assert events == first_events
    assert len(transports) == 1


def test_composition_uses_one_scope_one_session_and_only_the_two_reads(
    monkeypatch: pytest.MonkeyPatch, evidence_dir: Path
):
    events: list[str] = []
    transports = _install_fake_runtime(monkeypatch, events)

    result = operator.run_l41_read_only_observation(evidence_dir=evidence_dir)

    assert events == [
        "source_admission",
        "oauth_factory_builder",
        "transport_construct",
        "oauth_scope_entry",
        "session_open",
        "collector",
        "get_accounts",
        "get_equity_tradability",
        "session_close",
    ]
    assert len(transports) == 1
    boundary = transports[0]
    assert boundary.calls == [
        ("get_accounts", {}),
        (
            "get_equity_tradability",
            {"account_number": _ACCOUNT, "symbols": ["SPY"]},
        ),
    ]
    assert result.evidence.transport_counts == CapabilityTransportCounts(1, 1, 1, 1)
    assert result.evidence.collector_counts.get_accounts == 1
    assert result.evidence.collector_counts.get_equity_tradability == 1
    assert result.evidence.collector_invocations == 1
    assert result.evidence.native_credential_read_count is None
    assert result.evidence.transport_counts.native_credential_read_count is None
    for name in (
        "review_equity_order",
        "place_equity_order",
        "cancel_equity_order",
        "place_order",
        "cancel_order",
    ):
        assert not hasattr(_FakeTransport, name)
    rendered = repr(result) + json.dumps(_evidence_json(result), sort_keys=True)
    assert _ACCOUNT not in rendered
    assert _PROVIDER_TEXT not in rendered


@pytest.mark.parametrize(
    "failure,expected_counts,expected_collector_counts",
    [
        ("oauth", (1, 0, 0, 0), (0, 0)),
        ("session", (1, 1, 0, 0), (0, 0)),
        ("accounts", (1, 1, 1, 0), (1, 0)),
        ("tradability", (1, 1, 1, 1), (1, 1)),
    ],
)
def test_failure_attempt_counters_are_truthful_and_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    evidence_dir: Path,
    failure: str,
    expected_counts: tuple[int, int, int, int],
    expected_collector_counts: tuple[int, int],
):
    events: list[str] = []
    transports = _install_fake_runtime(monkeypatch, events, failure=failure)

    result = operator.run_l41_read_only_observation(evidence_dir=evidence_dir)

    assert result.status is OverallStatus.BLOCKED
    assert result.evidence.transport_counts is not None
    assert (
        tuple(
            getattr(result.evidence.transport_counts, field)
            for field in _TRANSPORT_COUNT_FIELDS
        )
        == expected_counts
    )
    assert (
        tuple(
            getattr(result.evidence.collector_counts, field)
            for field in _COLLECTOR_COUNT_FIELDS
        )
        == expected_collector_counts
    )
    assert result.evidence.collector_invocations == int(
        failure in {"accounts", "tradability"}
    )
    assert len(transports) == 1
    if failure in {"accounts", "tradability"}:
        assert sum(name == "get_accounts" for name, _ in transports[0].calls) == 1
        assert sum(
            name == "get_equity_tradability" for name, _ in transports[0].calls
        ) == int(failure == "tradability")
    rendered = repr(result) + json.dumps(_evidence_json(result), sort_keys=True)
    for secret in (_PROVIDER_TEXT, _ACCOUNT, _TOKEN_TEXT):
        assert secret not in rendered


@pytest.mark.parametrize("counts_mode", ["missing", "raising", "malformed"])
def test_unavailable_transport_counts_are_unknown_not_fabricated_zeroes(
    monkeypatch: pytest.MonkeyPatch,
    evidence_dir: Path,
    counts_mode: str,
):
    events: list[str] = []
    transports = _install_fake_runtime(monkeypatch, events, counts_mode=counts_mode)

    result = operator.run_l41_read_only_observation(evidence_dir=evidence_dir)

    assert len(transports) == 1
    assert transports[0].calls == [
        ("get_accounts", {}),
        (
            "get_equity_tradability",
            {"account_number": _ACCOUNT, "symbols": ["SPY"]},
        ),
    ]
    _assert_unknown_counts(result.evidence.transport_counts, _TRANSPORT_COUNT_FIELDS)
    assert result.evidence.collector_counts.get_accounts == 1
    assert result.evidence.collector_counts.get_equity_tradability == 1
    attempts = _evidence_json(result)["attempts"]
    assert isinstance(attempts, dict)
    for field in _TRANSPORT_COUNT_FIELDS:
        assert attempts[field] is None


def test_collector_exception_after_reads_does_not_report_zero_attempts(
    monkeypatch: pytest.MonkeyPatch, evidence_dir: Path
):
    events: list[str] = []
    transports = _install_fake_runtime(monkeypatch, events)

    def fail_after_reads(boundary):
        boundary.get_accounts()
        boundary.get_equity_tradability(
            {"account_number": _ACCOUNT, "symbols": ["SPY"]}
        )
        raise RuntimeError(_PROVIDER_TEXT)

    monkeypatch.setattr(operator, "collect_capabilities", fail_after_reads)
    result = operator.run_l41_read_only_observation(evidence_dir=evidence_dir)

    assert result.status is OverallStatus.BLOCKED
    assert result.evidence.collector_invocations == 1
    assert transports[0].calls == [
        ("get_accounts", {}),
        (
            "get_equity_tradability",
            {"account_number": _ACCOUNT, "symbols": ["SPY"]},
        ),
    ]
    assert result.evidence.transport_counts == CapabilityTransportCounts(1, 1, 1, 1)
    _assert_unknown_counts(result.evidence.collector_counts, _COLLECTOR_COUNT_FIELDS)
    attempts = _evidence_json(result)["attempts"]
    assert isinstance(attempts, dict)
    assert attempts["collector_get_accounts_attempts"] is None
    assert attempts["collector_get_equity_tradability_attempts"] is None


def test_partial_evidence_write_failure_preserves_known_attempts(
    monkeypatch: pytest.MonkeyPatch, evidence_dir: Path
):
    events: list[str] = []
    _install_fake_runtime(monkeypatch, events)
    original_open = Path.open

    class _PartialWriter:
        def __init__(self, stream) -> None:
            self._stream = stream

        def __enter__(self):
            return self

        def write(self, content: str) -> int:
            self._stream.write(content[:32])
            self._stream.flush()
            raise OSError(_PROVIDER_TEXT)

        def __exit__(self, exc_type, exc, traceback) -> bool:
            self._stream.close()
            return False

    def failing_open(path: Path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        if path.name == "evidence.json":
            return _PartialWriter(stream)
        return stream

    monkeypatch.setattr(Path, "open", failing_open)
    result = operator.run_l41_read_only_observation(evidence_dir=evidence_dir)
    monkeypatch.setattr(Path, "open", original_open)

    partial = evidence_dir / "evidence.json"
    assert result.status is OverallStatus.BLOCKED
    assert result.reason == "L41_EVIDENCE_WRITE_FAILED"
    assert result.evidence_path is None
    assert result.evidence.transport_counts == CapabilityTransportCounts(1, 1, 1, 1)
    assert result.evidence.collector_counts.get_accounts == 1
    assert result.evidence.collector_counts.get_equity_tradability == 1
    assert partial.exists()
    assert partial.read_text(encoding="utf-8")
    assert _PROVIDER_TEXT not in partial.read_text(encoding="utf-8")


def test_help_and_invalid_cli_exit_before_any_admission_or_oauth(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    evidence_dir: Path,
):
    events: list[str] = []
    monkeypatch.setattr(
        operator,
        "run_l41_read_only_observation",
        lambda **_kwargs: events.append("run") or None,
    )
    monkeypatch.setattr(
        operator, "admit_l41_source", lambda *_args: events.append("admission")
    )
    monkeypatch.setattr(
        operator, "_create_windows_oauth_factory", lambda: events.append("oauth")
    )

    with pytest.raises(SystemExit) as help_exit:
        operator.main(["--help"])
    assert help_exit.value.code == 0
    with pytest.raises(SystemExit) as invalid_exit:
        operator.main(["--evidence-dir", str(evidence_dir), "--invalid"])
    assert invalid_exit.value.code == 2

    assert events == []
    assert not evidence_dir.exists()
    assert "--evidence-dir" in capsys.readouterr().out
