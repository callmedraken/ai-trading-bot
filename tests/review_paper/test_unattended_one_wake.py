"""133-C certification: real wake durability; fake quotes/effects/paper reader."""

import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

import trading_bot.review_paper.unattended_one_wake as module
from trading_bot.domain import OrderFill, OrderSide, Symbol, TradeProposal
from trading_bot.ledger import PaperLedger
from trading_bot.review_paper.forward_preview import build_review_paper_forward_preview
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.risk_prices import (
    ReviewPaperRiskPriceMark,
    ReviewPaperRiskPriceSnapshot,
)
from trading_bot.review_paper.session_admission import ReviewPaperSessionStatus
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import ReviewPaperActivation
from trading_bot.review_paper.unattended_activation import ReviewPaperWakeState as State
from trading_bot.review_paper.unattended_one_wake import (
    OneWakeClassification as Classification,
)
from trading_bot.review_paper.unattended_one_wake import (
    OneWakeInstants,
    OneWakeStateError,
    OneWakeSyntheticEffectResult,
)
from trading_bot.review_paper.unattended_one_wake import (
    compose_one_review_paper_wake as compose,
)
from trading_bot.review_paper.unattended_state_schema import UnattendedStateConflict
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.risk.models import RiskLimits, RiskOutcome

AT = datetime(2026, 10, 5, 16, tzinfo=UTC)
SPY = Symbol("SPY")


@pytest.fixture
def harness(tmp_path, monkeypatch):
    paper = object.__new__(ReviewPaperStore)
    paper._path = tmp_path / "inert-paper.sqlite"
    paper._starting_cash = Decimal("10000")
    activation = ReviewPaperActivation(
        source_head="a" * 40,
        source_tree="b" * 40,
        deployment_identity="c" * 64,
        target_session_date=AT.date(),
        proposal=TradeProposal(
            UUID(int=1), SPY, OrderSide.BUY, Decimal("1"), AT, "frozen"
        ),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        store_identity=UUID(int=2),
        store_path=str(paper.path),
        starting_cash=paper.starting_cash,
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=5),
        max_quote_age=timedelta(minutes=1),
        slippage_basis_points=Decimal("5"),
        commission=Decimal("0"),
        local_order_id=UUID(int=3),
        created_at=AT,
    )
    store = UnattendedStateStore(tmp_path / "wake.sqlite")
    h = SimpleNamespace(
        activation=activation,
        state_store=store,
        paper_store=paper,
        instants=OneWakeInstants(
            AT, AT + timedelta(seconds=10), AT + timedelta(seconds=11)
        ),
        history=(),
        ledger=PaperLedger(paper.starting_cash),
        events=[],
        previews=[],
        quote_calls=0,
        effect_calls=0,
        quote_error=None,
        effect_error=None,
        effect_result=None,
        on_quote=None,
        on_transition=None,
        snapshot=ReviewPaperRiskPriceSnapshot(
            AT, (ReviewPaperRiskPriceMark(SPY, Decimal("100"), AT),)
        ),
    )
    h.expected = store.admit(activation)

    def forbidden(*args, **kwargs):
        pytest.fail("production paper/provider boundary reached")

    for name in ("_initialize", "_connect", "record_market_review"):
        monkeypatch.setattr(ReviewPaperStore, name, forbidden)
    monkeypatch.setattr(ReviewPaperStore, "history", lambda self: h.history)
    monkeypatch.setattr(ReviewPaperStore, "reconstruct_ledger", lambda self: h.ledger)
    real_transition = UnattendedStateStore.transition

    def transition(self, expected, *, state, at):
        value = real_transition(self, expected, state=state, at=at)
        assert UnattendedStateStore(self.path).snapshot().current(h.activation) == value
        h.events.append(state)
        if h.on_transition:
            h.on_transition(state)
        return value

    monkeypatch.setattr(UnattendedStateStore, "transition", transition)

    def preview(**kwargs):
        h.events.append("preview")
        value = build_review_paper_forward_preview(**kwargs)
        h.previews.append(value)
        return value

    monkeypatch.setattr(module, "build_review_paper_forward_preview", preview)

    class Quote:
        def prepare_quote(self, **kwargs):
            h.quote_calls += 1
            h.events.append("quote")
            current = UnattendedStateStore(store.path).snapshot().current(h.activation)
            assert current.wake.state is State.PREPARE_STARTED
            assert current.revision == 1
            assert kwargs["activation"] is h.activation
            assert kwargs["required_symbols"] == tuple(
                sorted(
                    set(h.ledger.positions) | {h.activation.proposal.symbol}, key=str
                )
            )
            assert kwargs["as_of"] == h.instants.started_at
            if h.on_quote:
                h.on_quote()
            if h.quote_error:
                raise h.quote_error
            return h.snapshot

    class Effect:
        def simulate_review_paper(self, **kwargs):
            h.effect_calls += 1
            h.events.append("effect")
            current = UnattendedStateStore(store.path).snapshot().current(h.activation)
            assert current.wake.state is State.REVIEW_STARTED
            assert current.revision == 3
            assert current == kwargs["persisted"]
            assert kwargs["activation"] is h.activation
            assert kwargs["preview"] is h.previews[-1]
            assert kwargs["as_of"] == h.instants.pre_effect_at
            if h.effect_error:
                raise h.effect_error
            return h.effect_result or OneWakeSyntheticEffectResult(
                h.activation.activation_id,
                current.wake.wake_id,
                h.activation.local_order_id,
                True,
            )

    h.quote_seam = Quote()
    h.effect_seam = Effect()
    return h


def run(h):
    return compose(
        **{
            name: getattr(h, name)
            for name in (
                "activation",
                "expected",
                "state_store",
                "paper_store",
                "instants",
                "quote_seam",
                "effect_seam",
            )
        }
    )


def freeze(h, **changes):
    h.activation = replace(h.activation, **changes)
    h.expected = h.state_store.admit(h.activation)


def assert_terminal(h, result, state, quotes, effects):
    assert result.final_state is state
    assert result.quote_attempts == h.quote_calls == quotes
    assert result.effect_attempts == h.effect_calls == effects
    current = UnattendedStateStore(h.state_store.path).snapshot().current(h.activation)
    assert current.wake.state is state
    assert current.revision == result.revisions[-1]
    assert not h.paper_store.path.exists()
    h.expected = current
    before = h.state_store.path.read_bytes()
    replay = run(h)
    assert replay.classification is Classification.REPLAY
    assert replay.quote_attempts == replay.effect_attempts == 0
    assert replay.transitions == (state,)
    assert replay.revisions == (current.revision,)
    assert h.state_store.path.read_bytes() == before
    assert h.quote_calls == quotes and h.effect_calls == effects


def test_success_exact_durable_order_and_revalidation(harness):
    h = harness
    result = run(h)
    assert h.events == [
        State.PREPARE_STARTED,
        "quote",
        "preview",
        State.PREPARED,
        "preview",
        State.REVIEW_STARTED,
        "effect",
        State.COMPLETED,
    ]
    assert result.transitions == (
        State.READY,
        State.PREPARE_STARTED,
        State.PREPARED,
        State.REVIEW_STARTED,
        State.COMPLETED,
    )
    assert result.revisions == (0, 1, 2, 3, 4)
    assert result.schedule == NYSEPublishedRegularSessionAuthority().schedule_for(
        AT.date()
    )
    assert tuple(x.as_of for x in result.admissions) == (
        AT,
        AT,
        h.instants.pre_effect_at,
    )
    assert all(x.status is ReviewPaperSessionStatus.ADMITTED for x in result.admissions)
    assert result.quote_valid_until == AT + h.activation.max_quote_age
    assert result.risk_outcome is RiskOutcome.APPROVED
    assert result.classification is Classification.COMPLETED
    for preview in h.previews:
        assert preview.proposal is h.activation.proposal
        assert preview.risk_limits is h.activation.risk_limits
        assert preview.price_snapshot is h.snapshot
    assert h.previews[0] == h.previews[1]
    assert_terminal(h, result, State.COMPLETED, 1, 1)


@pytest.mark.parametrize(
    "changes",
    [
        {"new_trading_enabled": False},
        {"risk_limits": RiskLimits(allow_buying=False)},
        {
            "proposal": TradeProposal(
                UUID(int=4), SPY, OrderSide.SELL, Decimal("1"), AT, "no position"
            )
        },
    ],
)
def test_risk_rejection_never_reaches_review(harness, changes):
    freeze(harness, **changes)
    result = run(harness)
    assert result.classification is Classification.RISK_REJECTED
    assert result.risk_outcome is RiskOutcome.REJECTED
    assert State.PREPARED not in result.transitions
    assert_terminal(harness, result, State.STOPPED, 1, 0)


def test_resized_decision_preserved(harness):
    freeze(harness, risk_limits=RiskLimits(max_order_notional=Decimal("50")))
    result = run(harness)
    assert result.risk_outcome is RiskOutcome.RESIZED
    assert harness.previews[-1].risk_decision.approved_quantity == Decimal("0.5")
    assert_terminal(harness, result, State.COMPLETED, 1, 1)


@pytest.mark.parametrize(
    "at,status",
    [
        (AT.replace(hour=13), ReviewPaperSessionStatus.BEFORE_REGULAR_WINDOW),
        (AT.replace(hour=13, minute=30), ReviewPaperSessionStatus.OPENING_BUFFER),
        (AT.replace(hour=19, minute=55), ReviewPaperSessionStatus.CLOSING_BUFFER),
        (AT.replace(hour=20), ReviewPaperSessionStatus.AFTER_REGULAR_WINDOW),
        (AT + timedelta(days=1), ReviewPaperSessionStatus.NON_SESSION_DATE),
    ],
)
def test_initial_session_exact_date_and_buffers(harness, at, status):
    h = harness
    freeze(
        h,
        created_at=AT.replace(hour=12),
        proposal=replace(h.activation.proposal, created_at=AT.replace(hour=12)),
    )
    h.instants = OneWakeInstants(at, at, at)
    result = run(h)
    assert result.classification is Classification.SESSION_NOT_ADMITTED
    assert result.admissions[-1].status is status
    assert_terminal(h, result, State.STOPPED, 0, 0)


@pytest.mark.parametrize(
    "target", [date(2026, 10, 10), date(2026, 12, 25), date(2029, 10, 5)]
)
def test_no_fallback_from_non_session_or_unsupported_target(harness, target):
    freeze(harness, target_session_date=target)
    result = run(harness)
    assert_terminal(harness, result, State.STOPPED, 0, 0)


def test_nonmatching_resolved_schedule_stops(harness, monkeypatch):
    schedule = NYSEPublishedRegularSessionAuthority().schedule_for(date(2026, 10, 6))
    monkeypatch.setattr(
        NYSEPublishedRegularSessionAuthority, "schedule_for", lambda self, day: schedule
    )
    result = run(harness)
    assert result.classification is Classification.SESSION_NOT_ADMITTED
    assert_terminal(harness, result, State.STOPPED, 0, 0)


@pytest.mark.parametrize("phase", ["observation", "effect"])
def test_session_expires_after_single_acquisition(harness, phase):
    h = harness
    closing = AT.replace(hour=19, minute=55)
    h.instants = OneWakeInstants(closing - timedelta(seconds=10), closing, closing)
    observed = closing if phase == "observation" else h.instants.started_at
    h.snapshot = ReviewPaperRiskPriceSnapshot(
        observed, (ReviewPaperRiskPriceMark(SPY, Decimal("100"), observed),)
    )
    result = run(h)
    assert result.classification is Classification.SESSION_NOT_ADMITTED
    assert_terminal(h, result, State.STOPPED, 1, 0)


@pytest.mark.parametrize(
    "source_delta,observed_delta,effect_delta,completed",
    [
        (-61, 0, 10, False),
        (-50, 0, 11, False),
        (-50, 0, 10, True),
        (0, -1, 10, False),
        (0, 11, 10, False),
    ],
)
def test_exact_freshness_no_extension_or_reacquisition(
    harness, source_delta, observed_delta, effect_delta, completed
):
    h = harness
    h.snapshot = ReviewPaperRiskPriceSnapshot(
        AT + timedelta(seconds=observed_delta),
        (
            ReviewPaperRiskPriceMark(
                SPY,
                Decimal("100"),
                AT + timedelta(seconds=min(source_delta, observed_delta)),
            ),
        ),
    )
    h.instants = OneWakeInstants(
        AT, AT + timedelta(seconds=effect_delta), AT + timedelta(seconds=effect_delta)
    )
    result = run(h)
    assert (
        result.quote_valid_until
        == h.snapshot.marks[0].source_at + h.activation.max_quote_age
    )
    if not completed:
        assert result.classification is Classification.QUOTE_NOT_VALID
    assert_terminal(
        h, result, State.COMPLETED if completed else State.STOPPED, 1, int(completed)
    )


def test_earliest_of_all_marks_controls_deadline(harness):
    h = harness
    other = Symbol("AAPL")
    h.ledger.apply_fill(
        OrderFill(
            UUID(int=90),
            UUID(int=91),
            other,
            OrderSide.BUY,
            Decimal("1"),
            Decimal("100"),
            Decimal("0"),
            AT,
        )
    )
    h.snapshot = ReviewPaperRiskPriceSnapshot(
        AT,
        (
            ReviewPaperRiskPriceMark(other, Decimal("100"), AT - timedelta(seconds=55)),
            ReviewPaperRiskPriceMark(SPY, Decimal("100"), AT),
        ),
    )
    result = run(h)
    assert result.quote_valid_until == AT + timedelta(seconds=5)
    assert result.classification is Classification.QUOTE_NOT_VALID
    assert_terminal(h, result, State.STOPPED, 1, 0)


@pytest.mark.parametrize("moment", ["quote", "prepared"])
def test_predecessor_drift_before_review_fence(harness, moment):
    h = harness

    def drift():
        h.history = (object(),)

    if moment == "quote":
        h.on_quote = drift
    else:
        h.on_transition = lambda state: drift() if state is State.PREPARED else None
    result = run(h)
    assert result.classification is Classification.MATERIAL_DRIFT
    assert_terminal(h, result, State.STOPPED, 1, 0)


@pytest.mark.parametrize(
    "drift", ["context", "decision", "proposal", "snapshot", "limits", "enabled"]
)
def test_exact_risk_and_preview_revalidation(harness, monkeypatch, drift):
    h = harness
    original = module.build_review_paper_forward_preview

    def changed(**kwargs):
        value = original(**kwargs)
        if len(h.previews) != 2:
            return value
        if drift == "context":
            return replace(
                value, risk_context=replace(value.risk_context, cash=Decimal("9999"))
            )
        if drift == "decision":
            return replace(
                value,
                risk_decision=replace(
                    value.risk_decision,
                    outcome=RiskOutcome.RESIZED,
                    approved_quantity=Decimal("0.5"),
                ),
            )
        if drift == "proposal":
            proposal = replace(value.proposal)
            return replace(
                value,
                proposal=proposal,
                risk_decision=replace(value.risk_decision, proposal=proposal),
            )
        if drift == "snapshot":
            return replace(value, price_snapshot=replace(value.price_snapshot))
        if drift == "limits":
            return replace(value, risk_limits=replace(value.risk_limits))
        return replace(
            value, risk_context=replace(value.risk_context, new_trading_enabled=False)
        )

    monkeypatch.setattr(module, "build_review_paper_forward_preview", changed)
    result = run(h)
    assert_terminal(h, result, State.STOPPED, 1, 0)


@pytest.mark.parametrize("kind", ["quote", "preview", "revalidation"])
@pytest.mark.parametrize(
    "error",
    [RuntimeError("secret account payload"), KeyboardInterrupt("private payload")],
)
def test_pre_effect_exception_sanitized_and_durable(harness, monkeypatch, kind, error):
    h = harness
    if kind == "quote":
        h.quote_error = error
    else:
        original = module.build_review_paper_forward_preview

        def fail(**kwargs):
            if kind == "preview" or h.previews:
                raise error
            return original(**kwargs)

        monkeypatch.setattr(module, "build_review_paper_forward_preview", fail)
    result = run(h)
    assert result.classification is Classification.PRE_EFFECT_FAILURE
    assert "payload" not in repr(result)
    assert_terminal(h, result, State.STOPPED, 1, 0)


@pytest.mark.parametrize(
    "error", [RuntimeError("token account raw payload"), KeyboardInterrupt("secret")]
)
def test_post_effect_exception_durable_indeterminate(harness, error):
    harness.effect_error = error
    result = run(harness)
    assert result.classification is Classification.EFFECT_INDETERMINATE
    assert "secret" not in repr(result) and "payload" not in repr(result)
    assert_terminal(harness, result, State.INDETERMINATE, 1, 1)


@pytest.mark.parametrize(
    "change", ["incomplete", "activation", "wake", "order", "wrong_type"]
)
def test_ambiguous_or_mismatched_effect_result_cannot_complete(harness, change):
    h = harness
    value = OneWakeSyntheticEffectResult(
        h.activation.activation_id,
        h.expected.wake.wake_id,
        h.activation.local_order_id,
        True,
    )
    if change == "wrong_type":
        h.effect_result = object()
    elif change == "incomplete":
        h.effect_result = replace(value, completed=False)
    else:
        name = {
            "activation": "activation_id",
            "wake": "wake_id",
            "order": "local_order_id",
        }[change]
        h.effect_result = replace(value, **{name: UUID(int=99)})
    result = run(h)
    assert_terminal(h, result, State.INDETERMINATE, 1, 1)


@pytest.mark.parametrize(
    "state", [State.PREPARE_STARTED, State.PREPARED, State.REVIEW_STARTED]
)
def test_consumed_reopen_is_readonly_reconciliation_only(harness, state):
    h = harness
    for next_state in (State.PREPARE_STARTED, State.PREPARED, State.REVIEW_STARTED):
        h.expected = h.state_store.transition(h.expected, state=next_state, at=AT)
        if next_state is state:
            break
    h.state_store = UnattendedStateStore(h.state_store.path)
    before = h.state_store.path.read_bytes()
    result = run(h)
    assert result.classification is Classification.RECONCILIATION_ONLY
    assert result.final_state is state
    assert result.transitions == (state,) and result.revisions == (h.expected.revision,)
    assert (
        result.quote_attempts
        == result.effect_attempts
        == h.quote_calls
        == h.effect_calls
        == 0
    )
    assert h.state_store.path.read_bytes() == before


@pytest.mark.parametrize(
    "edge",
    [
        State.PREPARE_STARTED,
        State.PREPARED,
        State.REVIEW_STARTED,
        State.COMPLETED,
        State.INDETERMINATE,
    ],
)
def test_failed_durable_edge_never_compensates_or_retries(harness, monkeypatch, edge):
    h = harness
    if edge is State.INDETERMINATE:
        h.effect_error = RuntimeError("secret")
    original = UnattendedStateStore.transition
    calls = []

    def fail(self, expected, *, state, at):
        calls.append(state)
        if state is edge:
            raise RuntimeError("secret write error")
        return original(self, expected, state=state, at=at)

    monkeypatch.setattr(UnattendedStateStore, "transition", fail)
    with pytest.raises(OneWakeStateError, match="reconciliation required") as error:
        run(h)
    assert "secret" not in str(error.value)
    assert calls.count(edge) == 1
    current = h.state_store.snapshot().current(h.activation)
    h.expected = current
    if current.wake.state is not State.READY:
        replay = run(h)
        assert replay.quote_attempts == replay.effect_attempts == 0
    assert h.effect_calls == int(edge in (State.COMPLETED, State.INDETERMINATE))
    assert h.quote_calls == int(edge is not State.PREPARE_STARTED)


@pytest.mark.parametrize(
    "field", ["activation", "expected", "state_store", "paper_store", "instants"]
)
def test_exact_boundary_types_required(harness, field):
    setattr(harness, field, object())
    with pytest.raises(TypeError):
        run(harness)
    assert harness.quote_calls == harness.effect_calls == 0


def test_stale_expected_and_conflicting_activation_zero_edges(harness):
    h = harness
    h.state_store.transition(h.expected, state=State.PREPARE_STARTED, at=AT)
    with pytest.raises(UnattendedStateConflict):
        run(h)
    assert h.quote_calls == h.effect_calls == 0


@pytest.mark.parametrize("changed", ["path", "cash"])
def test_paper_store_binding_checked(harness, changed):
    h = harness
    if changed == "path":
        h.paper_store._path = Path(str(h.paper_store.path) + ".other")
    else:
        h.paper_store._starting_cash = Decimal("20000")
    result = run(h)
    assert result.classification is Classification.MATERIAL_DRIFT
    assert_terminal(h, result, State.STOPPED, 0, 0)


def test_results_are_immutable_sanitized_bounded_facts(harness):
    result = run(harness)
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.effect_attempts = 3
    assert {field.name for field in fields(result)} == {
        "activation_id",
        "wake_id",
        "revisions",
        "transitions",
        "schedule",
        "admissions",
        "quote_valid_until",
        "risk_outcome",
        "quote_attempts",
        "effect_attempts",
        "final_state",
        "classification",
    }
    assert "inert-paper" not in repr(result)


@pytest.mark.parametrize(
    "instants",
    [
        (AT.replace(tzinfo=None), AT, AT),
        (AT, AT - timedelta(seconds=1), AT),
        (AT, AT, AT - timedelta(seconds=1)),
        ("bad", AT, AT),
    ],
)
def test_invalid_instants(instants):
    with pytest.raises((TypeError, ValueError)):
        OneWakeInstants(*instants)


def test_instants_normalize_timezone():
    shifted = AT.astimezone(timezone(timedelta(hours=-7)))
    assert OneWakeInstants(shifted, shifted, shifted) == OneWakeInstants(AT, AT, AT)


def test_ambient_decimal_context_does_not_change_result(harness):
    with localcontext() as context:
        context.prec = 2
        result = run(harness)
    assert_terminal(harness, result, State.COMPLETED, 1, 1)


def test_closed_source_imports_and_calls_exclude_production_surfaces():
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8-sig"))
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "typing",
        "uuid",
        "trading_bot.domain",
        "trading_bot.review_paper.forward_preview",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.risk_prices",
        "trading_bot.review_paper.session_admission",
        "trading_bot.review_paper.store",
        "trading_bot.review_paper.unattended_activation",
        "trading_bot.review_paper.unattended_state_schema",
        "trading_bot.review_paper.unattended_state_store",
        "trading_bot.risk.models",
    }
    assert not any(isinstance(node, (ast.Import, ast.While)) for node in ast.walk(tree))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {
        "subprocess",
        "os",
        "sleep",
        "run_robinhood_forward_paper_cycle",
        "execute_review_paper_supervised_cycle",
        "RobinhoodReviewReadAdapter",
    }
    assert not attrs & {
        "now",
        "utcnow",
        "record_market_review",
        "equity_quotes",
        "review_equity_order",
        "place_equity_order",
        "cancel_equity_order",
    }
    assert (
        sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "prepare_quote"
            for node in ast.walk(tree)
        )
        == 1
    )
    assert (
        sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "simulate_review_paper"
            for node in ast.walk(tree)
        )
        == 1
    )


@pytest.mark.parametrize("phase", ["quote", "effect"])
def test_reentrant_same_activation_has_no_new_edge(harness, phase):
    h = harness
    seen = []

    def replay():
        h.expected = h.state_store.snapshot().current(h.activation)
        seen.append(run(h))

    if phase == "quote":
        h.on_quote = replay
    else:
        h.on_transition = lambda state: (
            replay() if state is State.REVIEW_STARTED else None
        )
    result = run(h)
    assert len(seen) == 1
    assert seen[0].classification is Classification.RECONCILIATION_ONLY
    assert seen[0].quote_attempts == seen[0].effect_attempts == 0
    assert_terminal(h, result, State.COMPLETED, 1, 1)


@pytest.mark.parametrize(
    "terminal", [State.COMPLETED, State.STOPPED, State.INDETERMINATE]
)
def test_terminal_replay_after_target_date_does_not_resolve_or_acquire(
    harness, monkeypatch, terminal
):
    h = harness
    if terminal is State.STOPPED:
        h.quote_error = RuntimeError("stop")
    if terminal is State.INDETERMINATE:
        h.effect_error = RuntimeError("ambiguous")
    result = run(h)
    assert result.final_state is terminal
    h.expected = h.state_store.snapshot().current(h.activation)
    tomorrow = AT + timedelta(days=1)
    h.instants = OneWakeInstants(tomorrow, tomorrow, tomorrow)

    def forbidden(*args, **kwargs):
        pytest.fail("terminal replay acquired new session/paper authority")

    monkeypatch.setattr(NYSEPublishedRegularSessionAuthority, "schedule_for", forbidden)
    monkeypatch.setattr(ReviewPaperStore, "history", forbidden)
    replay = run(h)
    assert replay.classification is Classification.REPLAY
    assert replay.quote_attempts == replay.effect_attempts == 0


@pytest.mark.parametrize("phase", ["quote", "prepared"])
def test_concurrent_writer_consumes_wake_before_next_edge(harness, phase):
    h = harness
    original = UnattendedStateStore.transition

    def consume():
        current = h.state_store.snapshot().current(h.activation)
        original(
            h.state_store, current, state=State.STOPPED, at=h.instants.pre_effect_at
        )

    if phase == "quote":
        h.on_quote = consume
    else:
        h.on_transition = lambda state: consume() if state is State.PREPARED else None
    with pytest.raises(OneWakeStateError):
        run(h)
    assert h.quote_calls == 1 and h.effect_calls == 0
    assert h.state_store.snapshot().current(h.activation).wake.state is State.STOPPED


@pytest.mark.parametrize("value", [None, object(), ("raw payload",)])
def test_invalid_quote_return_stops_without_effect(harness, value):
    harness.snapshot = value
    result = run(harness)
    assert result.classification is Classification.PRE_EFFECT_FAILURE
    assert_terminal(harness, result, State.STOPPED, 1, 0)


@pytest.mark.parametrize("phase", ["quote", "prepared"])
def test_paper_store_binding_drift_during_preparation_stops(harness, phase):
    h = harness

    def drift():
        h.paper_store._starting_cash = Decimal("9999")

    if phase == "quote":
        h.on_quote = drift
    else:
        h.on_transition = lambda state: drift() if state is State.PREPARED else None
    result = run(h)
    assert result.classification is Classification.MATERIAL_DRIFT
    assert_terminal(h, result, State.STOPPED, 1, 0)


def test_snapshot_symbols_must_match_exact_predecessor_and_proposal(harness):
    h = harness
    h.snapshot = ReviewPaperRiskPriceSnapshot(
        AT, (ReviewPaperRiskPriceMark(Symbol("AAPL"), Decimal("100"), AT),)
    )
    result = run(h)
    assert result.classification is Classification.PRE_EFFECT_FAILURE
    assert_terminal(h, result, State.STOPPED, 1, 0)


def test_missing_state_never_initializes_or_acquires(harness):
    h = harness
    h.state_store = UnattendedStateStore(h.state_store.path.parent / "missing.sqlite")
    with pytest.raises(OneWakeStateError, match="could not be verified"):
        run(h)
    assert not h.state_store.path.exists()
    assert h.quote_calls == h.effect_calls == 0


def test_conflicting_canonical_activation_material_zero_edges(harness):
    h = harness
    h.activation = replace(h.activation, store_path=h.activation.store_path + ".other")
    assert h.activation.activation_id == h.expected.wake.activation.activation_id
    with pytest.raises(OneWakeStateError, match="could not be verified"):
        run(h)
    assert h.quote_calls == h.effect_calls == 0


@pytest.mark.parametrize(
    "field", ["activation_id", "wake_id", "local_order_id", "completed"]
)
def test_synthetic_effect_acknowledgement_is_closed(field):
    values = dict(
        activation_id=UUID(int=1),
        wake_id=UUID(int=2),
        local_order_id=UUID(int=3),
        completed=True,
    )
    values[field] = "raw provider payload"
    with pytest.raises(TypeError):
        OneWakeSyntheticEffectResult(**values)


def test_early_close_uses_exact_published_session(harness):
    h = harness
    day = date(2026, 11, 27)
    at = datetime(2026, 11, 27, 18, tzinfo=UTC)
    freeze(h, target_session_date=day)
    h.instants = OneWakeInstants(at, at, at)
    result = run(h)
    assert result.schedule.closes_at == at
    assert result.admissions[0].status is ReviewPaperSessionStatus.AFTER_REGULAR_WINDOW
    assert_terminal(h, result, State.STOPPED, 0, 0)
