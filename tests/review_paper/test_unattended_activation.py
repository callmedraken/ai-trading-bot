"""Pure 133-A activation and wake authority contracts."""

import ast
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from decimal import ROUND_DOWN, Decimal, Inexact, Rounded, localcontext
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

import trading_bot.domain.proposals as proposal_module
import trading_bot.review_paper.unattended_activation as module
from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.review_paper.unattended_activation import (
    ACTIVATION_SCHEMA,
    EXPIRY_RULE,
    WAKE_CONTRACT_ID,
    WAKE_SCHEMA,
    ReviewPaperActivation,
    ReviewPaperWake,
    ReviewPaperWakeState,
    fail_review_paper_wake,
    review_paper_wake_id,
    transition_review_paper_wake,
)
from trading_bot.risk.models import RiskLimits

AT = datetime(2026, 10, 5, 12, 0, 0, 123456, UTC)
PROPOSAL_ID = UUID("11111111-131c-4000-8000-000000000002")
ORDER_ID = UUID("22222222-131c-4000-8000-000000000001")
STORE_ID = UUID("33333333-131c-4000-8000-000000000001")
OTHER_ID = UUID("44444444-131c-4000-8000-000000000001")
State = ReviewPaperWakeState
LEGAL = {
    State.READY: {State.PREPARE_STARTED, State.STOPPED},
    State.PREPARE_STARTED: {State.PREPARED, State.STOPPED},
    State.PREPARED: {State.REVIEW_STARTED, State.STOPPED},
    State.REVIEW_STARTED: {State.COMPLETED, State.INDETERMINATE},
    State.COMPLETED: set(),
    State.STOPPED: set(),
    State.INDETERMINATE: set(),
}


def _proposal(**changes):
    values = dict(
        proposal_id=PROPOSAL_ID,
        symbol=Symbol("SPY"),
        side=OrderSide.SELL,
        desired_quantity=Decimal("1.000"),
        created_at=AT - timedelta(minutes=1),
        reason="one frozen proposal: | : 雪",
        confidence=Decimal("0.80"),
    )
    return TradeProposal(**(values | changes))


def _activation(**changes):
    values = dict(
        source_head="10e72fc5c609802e2704bb6a8b40bd99e8782d6a",
        source_tree="9082aed577a81c163527d3d13bf900c70c23667f",
        deployment_identity="a" * 64,
        target_session_date=date(2026, 10, 5),
        proposal=_proposal(),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        store_identity=STORE_ID,
        store_path=r"F:\AITradingBot\paper\review.sqlite",
        starting_cash=Decimal("10000.00"),
        opening_buffer=timedelta(minutes=15),
        closing_buffer=timedelta(minutes=15),
        max_quote_age=timedelta(minutes=5),
        slippage_basis_points=Decimal("5.00"),
        commission=Decimal("0.00"),
        local_order_id=ORDER_ID,
        created_at=AT,
    )
    return ReviewPaperActivation(**(values | changes))


def _json(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def test_activation_canonical_storage_and_deterministic_identity():
    activation = _activation()
    assert activation == _activation()
    assert activation.activation_id.version == 5
    assert activation.activation_id == UUID("aed397f1-6e02-5042-ac8e-35fd7e8f3fcf")
    text = activation.to_json()
    payload = json.loads(text)
    assert set(payload) == {
        "schema",
        "activation_id",
        "source_head",
        "source_tree",
        "deployment_identity",
        "target_session_date",
        "proposal",
        "risk_limits",
        "new_trading_enabled",
        "store_identity",
        "store_path",
        "starting_cash",
        "opening_buffer_us",
        "closing_buffer_us",
        "max_quote_age_us",
        "slippage_basis_points",
        "commission",
        "local_order_id",
        "wake_contract_id",
        "created_at",
        "expiry_rule",
    }
    assert payload["schema"] == ACTIVATION_SCHEMA
    assert payload["wake_contract_id"] == WAKE_CONTRACT_ID
    assert payload["expiry_rule"] == EXPIRY_RULE
    assert payload["proposal"] == {
        "proposal_id": str(PROPOSAL_ID),
        "symbol": "SPY",
        "side": "SELL",
        "desired_quantity": "1",
        "created_at": "2026-10-05T11:59:00.123456+00:00",
        "reason": "one frozen proposal: | : 雪",
        "confidence": "0.8",
    }
    assert payload["risk_limits"] == {
        "max_position_percent": "0.2",
        "max_total_exposure_percent": "0.8",
        "max_order_notional": None,
        "max_new_position_percent": None,
        "minimum_cash_reserve_percent": "0.1",
        "allow_fractional_shares": True,
        "fractional_increment": "0.001",
        "allow_buying": True,
        "allow_selling": True,
        "estimated_commission": "0",
    }
    assert payload["starting_cash"] == "10000"
    assert payload["opening_buffer_us"] == 900000000
    assert payload["max_quote_age_us"] == 300000000
    assert payload["created_at"] == "2026-10-05T12:00:00.123456+00:00"
    assert ReviewPaperActivation.from_json(text) == activation
    assert ReviewPaperActivation.from_json(text).to_json() == text
    assert text == _json(payload)


@pytest.mark.parametrize(
    "name,value",
    [
        ("source_head", "b" * 40),
        ("source_tree", "c" * 40),
        ("deployment_identity", "d" * 64),
        ("target_session_date", date(2026, 10, 6)),
        ("new_trading_enabled", False),
        ("store_identity", OTHER_ID),
        ("starting_cash", Decimal("10001")),
        ("opening_buffer", timedelta(seconds=1)),
        ("closing_buffer", timedelta(seconds=2)),
        ("max_quote_age", timedelta(seconds=3)),
        ("slippage_basis_points", Decimal("6")),
        ("commission", Decimal("1")),
        ("local_order_id", OTHER_ID),
        ("created_at", AT + timedelta(microseconds=1)),
    ],
)
def test_every_top_level_identity_fact_is_bound(name, value):
    assert _activation(**{name: value}).activation_id != _activation().activation_id


@pytest.mark.parametrize(
    "name,value",
    [
        ("proposal_id", OTHER_ID),
        ("symbol", Symbol("QQQ")),
        ("side", OrderSide.BUY),
        ("desired_quantity", Decimal("2")),
        ("created_at", AT - timedelta(seconds=2)),
        ("reason", "a different reason"),
        ("confidence", None),
    ],
)
def test_every_proposal_fact_is_bound(name, value):
    assert (
        _activation(proposal=_proposal(**{name: value})).activation_id
        != _activation().activation_id
    )


@pytest.mark.parametrize(
    "name,value",
    [
        ("max_position_percent", Decimal("0.3")),
        ("max_total_exposure_percent", Decimal("0.9")),
        ("max_order_notional", Decimal("1234")),
        ("max_new_position_percent", Decimal("0.4")),
        ("minimum_cash_reserve_percent", Decimal("0.2")),
        ("allow_fractional_shares", False),
        ("fractional_increment", Decimal("0.002")),
        ("allow_buying", False),
        ("allow_selling", False),
        ("estimated_commission", Decimal("1")),
    ],
)
def test_every_risk_limit_is_bound(name, value):
    assert (
        _activation(risk_limits=RiskLimits(**{name: value})).activation_id
        != _activation().activation_id
    )


def test_path_is_exact_storage_material_and_not_domain_identity():
    activation = _activation()
    moved = replace(activation, store_path=r"G:\paper\review.sqlite")
    assert activation.activation_id == moved.activation_id
    assert activation.to_json() != moved.to_json()
    assert ReviewPaperActivation.from_json(moved.to_json()) == moved


def test_framing_prevents_delimiter_ambiguity():
    assert module._material("v1", (("a", "x:|"), ("b", "z"))) != module._material(
        "v1", (("a", "x"), ("b", ":|z"))
    )


def test_equivalent_decimals_and_offsets_have_identical_material():
    activation = _activation()
    equivalent = _activation(
        proposal=_proposal(
            desired_quantity=Decimal("1E+0"),
            confidence=Decimal("0.8000"),
            created_at=(AT - timedelta(minutes=1)).astimezone(
                ZoneInfo("America/New_York")
            ),
        ),
        starting_cash=Decimal("1E+4"),
        commission=Decimal("-0E+20"),
        slippage_basis_points=Decimal("5.000000"),
        risk_limits=RiskLimits(max_position_percent=Decimal("0.20000")),
        created_at=AT.astimezone(timezone(timedelta(hours=5, minutes=30))),
    )
    assert equivalent.activation_id == activation.activation_id
    assert equivalent.to_json() == activation.to_json()
    assert equivalent.created_at.tzinfo is UTC


@pytest.mark.parametrize("precision", [1, 2, 7])
def test_decimal_canonicality_is_independent_of_ambient_context(precision):
    changes = dict(
        starting_cash=Decimal("12345678901234567890.12345678901234567890000"),
        commission=Decimal("-0.000"),
        risk_limits=RiskLimits(
            max_order_notional=Decimal("98765432109876543210.123456789")
        ),
    )
    expected = _activation(**changes)
    with localcontext() as context:
        context.prec = precision
        context.rounding = ROUND_DOWN
        context.Emax = 3
        context.Emin = -3
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        context.clear_flags()
        actual = _activation(**changes)
        assert actual.activation_id == expected.activation_id
        assert actual.to_json() == expected.to_json()
        assert ReviewPaperActivation.from_json(actual.to_json()) == actual
        assert not any(context.flags.values())


@pytest.mark.parametrize(
    "name,value",
    [
        ("schema", "v2"),
        ("wake_contract_id", "arbitrary-command"),
        ("expiry_rule", "RENEW"),
        ("source_head", "a" * 39),
        ("source_tree", "A" * 40),
        ("deployment_identity", "deployment"),
        ("target_session_date", AT),
        ("target_session_date", "2026-10-05"),
        ("proposal", {}),
        ("risk_limits", {}),
        ("new_trading_enabled", 1),
        ("store_identity", str(STORE_ID)),
        ("local_order_id", str(ORDER_ID)),
        ("starting_cash", 10000),
        ("starting_cash", Decimal("-1")),
        ("starting_cash", Decimal("0")),
        ("commission", Decimal("-1")),
        ("commission", 0.0),
        ("slippage_basis_points", Decimal("10000")),
        ("slippage_basis_points", Decimal("-1")),
        ("opening_buffer", timedelta(microseconds=-1)),
        ("closing_buffer", timedelta(seconds=-1)),
        ("max_quote_age", timedelta(0)),
        ("max_quote_age", timedelta(seconds=-1)),
        ("opening_buffer", 0),
        ("closing_buffer", True),
        ("max_quote_age", 300),
        ("created_at", AT.replace(tzinfo=None)),
        ("created_at", "2026-10-05T12:00:00Z"),
        ("created_at", AT - timedelta(minutes=2)),
    ],
)
def test_malformed_activation_inputs_fail_closed(name, value):
    with pytest.raises((TypeError, ValueError)):
        _activation(**{name: value})


@pytest.mark.parametrize(
    "name", ["starting_cash", "commission", "slippage_basis_points"]
)
@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_nonfinite_top_level_decimals_are_rejected_without_ambient_arithmetic(
    name, value
):
    with pytest.raises(ValueError, match="finite"):
        _activation(**{name: Decimal(value)})


@pytest.mark.parametrize(
    "owner,name,value",
    [
        ("proposal", "desired_quantity", Decimal("Infinity")),
        ("proposal", "confidence", Decimal("NaN")),
        ("proposal", "desired_quantity", Decimal("0")),
        ("proposal", "reason", ""),
        ("proposal", "side", "SELL"),
        ("proposal", "created_at", AT.replace(tzinfo=None)),
        ("risk_limits", "fractional_increment", Decimal("Infinity")),
        ("risk_limits", "estimated_commission", Decimal("NaN")),
        ("risk_limits", "max_position_percent", Decimal("0")),
        ("risk_limits", "allow_buying", 1),
    ],
)
def test_nested_domain_values_are_revalidated(owner, name, value):
    nested = _proposal() if owner == "proposal" else RiskLimits()
    object.__setattr__(
        nested, name, value
    )  # Emulate a malformed restored domain value.
    with pytest.raises((TypeError, ValueError)):
        _activation(**{owner: nested})


@pytest.mark.parametrize(
    "path",
    [
        "paper.sqlite",
        "/tmp/paper.sqlite",
        r"f:\paper\review.sqlite",
        r"F:/paper/review.sqlite",
        r"F:\paper\..\review.sqlite",
        r"F:\paper\.\review.sqlite",
        "F:\\paper\\\\review.sqlite",
        "F:\\paper\\",
        "F:\\paper\\review.sqlite ",
        "F:\\paper\\review.sqlite.",
        r"F:\paper\NUL",
        "F:\\paper\\bad\n.sqlite",
        r"F:\paper\review.sqlite:stream",
    ],
)
def test_store_path_requires_exact_lexical_identity(path):
    with pytest.raises(ValueError):
        _activation(store_path=path)


class NoOffset(tzinfo):
    def utcoffset(self, value):
        return None


@pytest.mark.parametrize("target", ["activation", "wake", "transition"])
@pytest.mark.parametrize(
    "value", [AT.replace(tzinfo=None), AT.replace(tzinfo=NoOffset()), "now"]
)
def test_timestamps_require_real_timezone_awareness(target, value):
    with pytest.raises((TypeError, ValueError)):
        if target == "activation":
            _activation(created_at=value)
        elif target == "wake":
            ReviewPaperWake(activation=_activation(), updated_at=value)
        else:
            transition_review_paper_wake(
                ReviewPaperWake(activation=_activation(), updated_at=AT),
                state=State.PREPARE_STARTED,
                at=value,
            )


def test_dst_fold_and_utc_canonicalization():
    local = datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York"))
    one = _activation(created_at=local, target_session_date=date(2026, 11, 2))
    two = replace(one, created_at=local.replace(fold=1))
    assert one.created_at == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert two.created_at == datetime(2026, 11, 1, 6, 30, tzinfo=UTC)
    assert one.activation_id != two.activation_id


@pytest.mark.parametrize("model", ["activation", "wake"])
def test_models_and_nested_inputs_are_frozen_and_slotted(model):
    activation = _activation()
    value = (
        activation
        if model == "activation"
        else ReviewPaperWake(activation=activation, updated_at=AT)
    )
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.schema = "changed"
    with pytest.raises((FrozenInstanceError, TypeError, AttributeError)):
        value.retry = True
    with pytest.raises(FrozenInstanceError):
        activation.proposal.reason = "changed"
    with pytest.raises(FrozenInstanceError):
        activation.risk_limits.allow_selling = False
    assert not hasattr(activation.proposal, "__dict__")
    assert not hasattr(activation.risk_limits, "__dict__")
    assert fields(type(value))[-1].init is False


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "nested_extra",
        "nested_missing",
        "risk_extra",
        "risk_missing",
        "identity",
        "schema",
        "whitespace",
        "duplicates",
        "timestamp",
        "uuid",
        "symbol",
        "decimal_float",
        "decimal_trailing",
        "decimal_exponent",
        "decimal_negative_zero",
        "decimal_nan",
        "decimal_bad",
        "confidence_bool",
        "bool_int",
        "duration_bool",
        "date",
    ],
)
def test_activation_reader_is_closed_canonical_and_identity_checked(mutation):
    payload = json.loads(_activation().to_json())
    if mutation == "extra":
        payload["credential"] = "not-allowed"
    elif mutation == "missing":
        del payload["source_head"]
    elif mutation == "nested_extra":
        payload["proposal"]["retry"] = True
    elif mutation == "nested_missing":
        del payload["proposal"]["reason"]
    elif mutation == "risk_extra":
        payload["risk_limits"]["extra"] = "1"
    elif mutation == "risk_missing":
        del payload["risk_limits"]["allow_buying"]
    elif mutation == "identity":
        payload["activation_id"] = str(OTHER_ID)
    elif mutation == "schema":
        payload["schema"] = "v2"
    elif mutation == "timestamp":
        payload["created_at"] = "2026-10-05T08:00:00.123456-04:00"
    elif mutation == "uuid":
        payload["local_order_id"] = str(ORDER_ID).upper()
    elif mutation == "symbol":
        payload["proposal"]["symbol"] = "spy"
    elif mutation == "decimal_float":
        payload["starting_cash"] = 10000.0
    elif mutation == "decimal_trailing":
        payload["starting_cash"] = "10000.00"
    elif mutation == "decimal_exponent":
        payload["starting_cash"] = "1E+4"
    elif mutation == "decimal_negative_zero":
        payload["commission"] = "-0"
    elif mutation == "decimal_nan":
        payload["commission"] = "NaN"
    elif mutation == "decimal_bad":
        payload["commission"] = "wrong"
    elif mutation == "confidence_bool":
        payload["proposal"]["confidence"] = True
    elif mutation == "bool_int":
        payload["new_trading_enabled"] = 1
    elif mutation == "duration_bool":
        payload["opening_buffer_us"] = True
    elif mutation == "date":
        payload["target_session_date"] = "20261005"
    text = _json(payload)
    if mutation == "whitespace":
        text += "\n"
    if mutation == "duplicates":
        text = text.replace('"commission":"0"', '"commission":"0","commission":"0"', 1)
    with pytest.raises((TypeError, ValueError)):
        ReviewPaperActivation.from_json(text)


@pytest.mark.parametrize("text", ["[]", "null", "{", "1", '"text"', 1, None])
def test_readers_reject_nonobjects_and_malformed_json(text):
    with pytest.raises((TypeError, ValueError)):
        ReviewPaperActivation.from_json(text)
    with pytest.raises((TypeError, ValueError)):
        ReviewPaperWake.from_json(text, activation=_activation())


def test_wake_identity_and_exact_canonical_storage():
    activation = _activation()
    wake = ReviewPaperWake(activation=activation, updated_at=AT)
    assert wake.wake_id == UUID("1fdc1095-81b6-59c1-a63a-b693d7eb0ea3")
    assert wake.wake_id.version == 5
    assert json.loads(wake.to_json()) == {
        "schema": WAKE_SCHEMA,
        "wake_id": str(wake.wake_id),
        "activation_id": str(activation.activation_id),
        "target_session_date": "2026-10-05",
        "proposal_id": str(PROPOSAL_ID),
        "local_order_id": str(ORDER_ID),
        "state": "READY",
        "updated_at": "2026-10-05T12:00:00.123456+00:00",
    }
    assert ReviewPaperWake.from_json(wake.to_json(), activation=activation) == wake
    for state in State:
        restored = replace(wake, state=state, updated_at=AT + timedelta(seconds=1))
        assert restored.wake_id == wake.wake_id
        assert (
            ReviewPaperWake.from_json(restored.to_json(), activation=activation)
            == restored
        )


@pytest.mark.parametrize(
    "index,value", [(0, OTHER_ID), (1, date(2026, 10, 6)), (2, OTHER_ID), (3, OTHER_ID)]
)
def test_wake_identity_binds_all_four_facts(index, value):
    facts = [_activation().activation_id, date(2026, 10, 5), PROPOSAL_ID, ORDER_ID]
    expected = review_paper_wake_id(*facts)
    facts[index] = value
    assert review_paper_wake_id(*facts) != expected


@pytest.mark.parametrize("index,value", [(0, "uuid"), (1, AT), (2, 1), (3, None)])
def test_wake_identity_rejects_malformed_facts(index, value):
    facts = [_activation().activation_id, date(2026, 10, 5), PROPOSAL_ID, ORDER_ID]
    facts[index] = value
    with pytest.raises(TypeError):
        review_paper_wake_id(*facts)


@pytest.mark.parametrize(
    "key",
    [
        "wake_id",
        "activation_id",
        "target_session_date",
        "proposal_id",
        "local_order_id",
        "state",
        "schema",
        "updated_at",
    ],
)
def test_wake_reader_rejects_changed_binding_or_noncanonical_state(key):
    activation = _activation()
    payload = json.loads(
        ReviewPaperWake(activation=activation, updated_at=AT).to_json()
    )
    payload[key] = "incorrect"
    with pytest.raises((TypeError, ValueError)):
        ReviewPaperWake.from_json(_json(payload), activation=activation)


def test_wake_reader_rejects_unknown_missing_duplicate_fields_and_wrong_activation():
    activation = _activation()
    text = ReviewPaperWake(activation=activation, updated_at=AT).to_json()
    payload = json.loads(text)
    for changed in (
        payload | {"retry": 1},
        {k: v for k, v in payload.items() if k != "state"},
    ):
        with pytest.raises(ValueError):
            ReviewPaperWake.from_json(_json(changed), activation=activation)
    with pytest.raises(ValueError):
        ReviewPaperWake.from_json(
            text.replace('"state":"READY"', '"state":"READY","state":"READY"'),
            activation=activation,
        )
    with pytest.raises(ValueError):
        ReviewPaperWake.from_json(
            text, activation=replace(activation, local_order_id=OTHER_ID)
        )


@pytest.mark.parametrize("before", list(State))
@pytest.mark.parametrize("after", list(State))
def test_exact_transition_matrix(before, after):
    activation = _activation()
    wake = ReviewPaperWake(activation=activation, state=before, updated_at=AT)
    original = wake.to_json()
    if after in LEGAL[before]:
        result = transition_review_paper_wake(
            wake, state=after, at=AT + timedelta(seconds=1)
        )
        assert result.state is after
        assert result.activation is activation
        assert result.wake_id == wake.wake_id
        assert result.updated_at == AT + timedelta(seconds=1)
    else:
        with pytest.raises(ValueError, match="illegal wake transition"):
            transition_review_paper_wake(
                wake, state=after, at=AT + timedelta(seconds=1)
            )
    assert wake.to_json() == original


def test_exact_closed_states_and_single_forward_path():
    assert tuple(item.value for item in State) == (
        "READY",
        "PREPARE_STARTED",
        "PREPARED",
        "REVIEW_STARTED",
        "COMPLETED",
        "STOPPED",
        "INDETERMINATE",
    )
    wake = ReviewPaperWake(activation=_activation(), updated_at=AT)
    identity = wake.wake_id
    for state in (
        State.PREPARE_STARTED,
        State.PREPARED,
        State.REVIEW_STARTED,
        State.COMPLETED,
    ):
        wake = transition_review_paper_wake(wake, state=state, at=AT)
    assert wake.wake_id == identity
    assert wake.state is State.COMPLETED


@pytest.mark.parametrize("state", list(State))
def test_failure_terminates_without_retry_and_review_failure_is_indeterminate(state):
    wake = ReviewPaperWake(activation=_activation(), state=state, updated_at=AT)
    if state in (State.COMPLETED, State.STOPPED, State.INDETERMINATE):
        with pytest.raises(ValueError):
            fail_review_paper_wake(wake, at=AT)
    else:
        result = fail_review_paper_wake(wake, at=AT)
        assert result.state is (
            State.INDETERMINATE if state is State.REVIEW_STARTED else State.STOPPED
        )


@pytest.mark.parametrize("state", [State.COMPLETED, State.STOPPED, State.INDETERMINATE])
def test_terminal_replay_is_read_only_and_restoration_adds_no_authority(state):
    activation = _activation()
    terminal = ReviewPaperWake(activation=activation, updated_at=AT, state=state)
    original = terminal.to_json()
    for _ in range(2):
        terminal = ReviewPaperWake.from_json(original, activation=activation)
        assert terminal.to_json() == original
        for next_state in State:
            with pytest.raises(ValueError):
                transition_review_paper_wake(
                    terminal, state=next_state, at=AT + timedelta(days=1)
                )


@pytest.mark.parametrize(
    "name,value",
    [
        ("activation", None),
        ("state", "READY"),
        ("schema", "v2"),
        ("updated_at", AT - timedelta(microseconds=1)),
    ],
)
def test_malformed_wake_inputs(name, value):
    values = dict(activation=_activation(), updated_at=AT)
    with pytest.raises((TypeError, ValueError)):
        ReviewPaperWake(**(values | {name: value}))


def test_transition_timestamp_monotonic_and_normalized_and_types_closed():
    wake = ReviewPaperWake(activation=_activation(), updated_at=AT)
    with pytest.raises(ValueError, match="backward"):
        transition_review_paper_wake(
            wake, state=State.PREPARE_STARTED, at=AT - timedelta(microseconds=1)
        )
    normalized = transition_review_paper_wake(
        wake,
        state=State.PREPARE_STARTED,
        at=AT.astimezone(ZoneInfo("America/New_York")),
    )
    assert normalized.updated_at.tzinfo is UTC
    for value in ("PREPARE_STARTED", None):
        with pytest.raises(TypeError):
            transition_review_paper_wake(wake, state=value, at=AT)
    with pytest.raises(TypeError):
        transition_review_paper_wake(None, state=State.PREPARE_STARTED, at=AT)
    with pytest.raises(TypeError):
        fail_review_paper_wake(None, at=AT)


def test_source_has_only_pure_allowlisted_imports_and_calls():
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports == {
        "__future__",
        "json",
        "re",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "uuid",
        "trading_bot.domain",
        "trading_bot.risk.models",
    }
    calls = {
        ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)
    }
    assert calls <= {
        "UUID",
        "uuid5",
        "type",
        "TypeError",
        "ValueError",
        "Decimal",
        "format",
        "getattr",
        "fields",
        "field",
        "dataclass",
        "object.__setattr__",
        "TradeProposal",
        "RiskLimits",
        "Symbol",
        "OrderSide",
        "ReviewPaperWakeState",
        "cls",
        "replace",
        "tuple",
        "set",
        "str",
        "len",
        "re.fullmatch",
        "json.dumps",
        "json.loads",
        "datetime.fromisoformat",
        "date.fromisoformat",
        "timedelta",
        "text.encode",
        "''.join",
        "value.astimezone",
        "value.utcoffset",
        "value.is_finite",
        "value[3:].split",
        "part.strip().rstrip",
        "part.strip",
        "text.rstrip('0').rstrip",
        "text.rstrip",
        "_utc(value, 'timestamp').isoformat",
        "proposal.side.value",
        "self.target_session_date.isoformat",
        "self.activation.target_session_date.isoformat",
        "target_session_date.isoformat",
        "payload.items",
        "limits.items",
        "_proposal_payload(self.proposal).items",
        "_risk_payload(self.risk_limits).items",
        "self._payload",
        "self.to_json",
        "result.to_json",
        "_exact",
        "_utc",
        "_timestamp",
        "_finite",
        "_canonical_decimal",
        "_digest",
        "_store_path",
        "_duration_us",
        "_proposal_payload",
        "_risk_payload",
        "_scalar",
        "_material",
        "_json",
        "_object",
        "_load",
        "_decimal_text",
        "_uuid_text",
        "_datetime_text",
        "_date_text",
        "_duration_value",
        "review_paper_wake_id",
        "transition_review_paper_wake",
    }
    assert not any(
        isinstance(node, (ast.While, ast.AsyncFunctionDef, ast.Await))
        for node in ast.walk(tree)
    )


def test_build_serialize_and_transition_never_use_uuid4_or_external_authority(
    monkeypatch,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("prohibited authority invoked")

    monkeypatch.setattr(proposal_module, "uuid4", forbidden)
    monkeypatch.setattr("builtins.open", forbidden)
    activation = _activation()
    assert activation.proposal.proposal_id == PROPOSAL_ID
    wake = ReviewPaperWake(
        activation=ReviewPaperActivation.from_json(activation.to_json()), updated_at=AT
    )
    wake = transition_review_paper_wake(wake, state=State.PREPARE_STARTED, at=AT)
    restored = ReviewPaperWake.from_json(wake.to_json(), activation=activation)
    assert fail_review_paper_wake(restored, at=AT).state is State.STOPPED


@pytest.mark.parametrize("invalid_trap", [True, False])
def test_malformed_decimal_reader_does_not_depend_on_context(invalid_trap):
    from decimal import InvalidOperation

    payload = json.loads(_activation().to_json())
    payload["commission"] = "malformed"
    with localcontext() as context:
        context.traps[InvalidOperation] = invalid_trap
        context.clear_flags()
        with pytest.raises(ValueError, match="Decimal text must be canonical"):
            ReviewPaperActivation.from_json(_json(payload))
        assert not any(context.flags.values())


def test_closed_constructor_fields_and_derived_ids_cannot_be_supplied():
    activation = _activation()
    with pytest.raises(TypeError):
        replace(activation, credential="forbidden")
    with pytest.raises((TypeError, ValueError)):
        replace(activation, activation_id=OTHER_ID)
    with pytest.raises(TypeError):
        ReviewPaperWake(activation=activation, updated_at=AT, retry=True)
    with pytest.raises(TypeError):
        ReviewPaperWake(activation=activation, updated_at=AT, wake_id=OTHER_ID)
