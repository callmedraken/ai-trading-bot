from dataclasses import replace

import pytest

from trading_bot.desktop_live.configuration import (
    LIVE_FAST,
    LIVE_SLOW,
    LIVE_SYMBOL,
    MAX_BOT_GROSS_EXPOSURE_DOLLARS,
    MAX_ORDER_DOLLARS,
    TinyLivePolicy,
)
from trading_bot.domain import Symbol


def test_tiny_live_policy_is_the_narrow_source_owned_contract():
    policy = TinyLivePolicy()
    assert (policy.symbol, policy.fast, policy.slow) == (
        LIVE_SYMBOL,
        LIVE_FAST,
        LIVE_SLOW,
    )
    assert policy.max_order_dollars == MAX_ORDER_DOLLARS
    assert policy.max_gross_exposure_dollars == MAX_BOT_GROSS_EXPOSURE_DOLLARS
    assert policy.purpose == "LIVE_PRODUCTION_TRIAL"
    assert policy.policy_id == TinyLivePolicy().policy_id


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol", Symbol("QQQ")),
        ("fast", 55),
        ("slow", 100),
        ("max_order_dollars", MAX_ORDER_DOLLARS + 1),
    ],
)
def test_tiny_live_policy_rejects_contract_drift(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(TinyLivePolicy(), **{field: value})
