from __future__ import annotations

import json
from datetime import UTC, datetime
from time import monotonic, sleep

from trading_bot.portfolio_manager.application_service import (
    PortfolioManagerApplicationService,
)
from trading_bot.portfolio_manager.models import AccountBinding, OrderCoverage
from trading_bot.portfolio_manager.synthetic_demo import (
    FakeRobinhoodObservationSource,
    SyntheticDemoObservationSource,
    SyntheticPortfolioPipeline,
    synthetic_account_binding,
)


def _wait_for(condition, timeout: float = 5.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if condition():
            return True
        sleep(0.005)
    return condition()


def _service(state_root, binding, source, now):
    return PortfolioManagerApplicationService(
        account_binding=binding,
        state_root=state_root,
        observation_source=source,
        pipeline=SyntheticPortfolioPipeline(),
        monitoring_interval=0.05,
        clock=lambda: now,
    )


def test_vertical_slice_preview_and_bounded_fake_transport(tmp_path):
    now = datetime(2026, 11, 26, 20, 0, tzinfo=UTC)

    synthetic = _service(
        tmp_path / "synthetic",
        synthetic_account_binding(),
        SyntheticDemoObservationSource(clock=lambda: now),
        now,
    )
    bounded_source = FakeRobinhoodObservationSource(clock=lambda: now)
    bounded = _service(
        tmp_path / "fake-read",
        AccountBinding(bounded_source.account_fingerprint),
        bounded_source,
        now,
    )
    assert not hasattr(synthetic, "place_order")
    assert not hasattr(synthetic, "submit_order")
    assert not hasattr(synthetic, "cancel_order")

    try:
        assert synthetic.start()
        assert _wait_for(lambda: synthetic.snapshot().latest is not None)
        snapshot = synthetic.snapshot()
        observation = snapshot.observation
        result = snapshot.latest
        assert observation is not None and result is not None
        assert len(observation.positions) == 2
        assert observation.positions[0].quantity.as_tuple().exponent == -2
        assert observation.positions[1].average_cost is None
        assert {item.action for item in result.decisions} >= {"BUY", "HOLD", "REDUCE"}
        assert any(
            item.symbol == "GLD"
            and item.action == "BUY"
            and item.risk_status == "PREVIEW_ONLY"
            for item in result.decisions
        )
        assert any(
            item.symbol == "TLT"
            and item.action == "REDUCE"
            and item.risk_status == "PREVIEW_ONLY"
            for item in result.decisions
        )
        assert any(
            item.symbol == "GLD" and item.status == "PREVIEW_ONLY"
            for item in result.preview_legs
        )
        synthetic_entry = snapshot.history[-1]
        synthetic_payload = json.loads(synthetic_entry.stored.payload_json)
        synthetic_plan = synthetic_payload["audit"]["order_plan"]
        assert [leg["side"] for leg in synthetic_plan["legs"]] == ["SELL", "BUY"]
        # These reference actions are independent REDUCE and BUY suggestions.
        # Planning adds dependencies for explicit REBALANCE batches only.
        assert synthetic_plan["legs"][1]["depends_on"] == []
        tlt_audit = next(
            item
            for item in synthetic_payload["audit"]["recommendations"]
            if item["symbol"] == "TLT"
        )
        assert {item["code"] for item in tlt_audit["diagnostics"]} >= {
            "SYNTHETIC_REFERENCE_UNVALIDATED",
            "COST_BASIS_UNKNOWN",
        }
        assert synthetic_plan["sell_proceeds_assumed_available"] == "0"
        assert synthetic_plan["preview_only"] is True
        assert synthetic_plan["dispatch_authorized"] is False

        assert bounded.start()
        assert _wait_for(lambda: bounded.snapshot().latest is not None)
        bounded_snapshot = bounded.snapshot()
        bounded_observation = bounded_snapshot.observation
        bounded_result = bounded_snapshot.latest
        assert bounded_observation is not None and bounded_result is not None
        assert (
            bounded_observation.coverage.order_scope
            is OrderCoverage.ROBINHOOD_AGENTIC_BOUNDED
        )
        assert any(
            item.symbol == "GLD"
            and item.status == "BLOCKED"
            and "ORDER_SCOPE_INCOMPLETE" in item.reasons
            for item in bounded_result.preview_legs
        )
        assert not any(
            item.status == "PREVIEW_ONLY" for item in bounded_result.preview_legs
        )
        assert any(
            item.value == "UNKNOWN_ORDER_OWNER"
            for item in bounded_observation.conditions
        )
        bounded_payload = json.loads(bounded_snapshot.history[-1].stored.payload_json)
        assert (
            bounded_payload["observation"]["coverage"]["order_scope"]
            == "ROBINHOOD_AGENTIC_BOUNDED"
        )
        serialized = json.dumps(bounded_payload)
        assert "PM1-FAKE-ACCOUNT-01" not in serialized
        assert all(
            name in {call[0] for call in bounded_source.calls}
            for name in (
                "get_accounts",
                "get_portfolio",
                "get_equity_positions",
                "get_equity_quotes",
                "get_equity_orders",
            )
        )
        assert all(call[0].startswith("get_") for call in bounded_source.calls)
    finally:
        synthetic.stop()
        bounded.stop()
        assert _wait_for(synthetic.shutdown_complete)
        assert _wait_for(bounded.shutdown_complete)
