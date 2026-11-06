from trading_bot.live_prototype.contracts import EffectDisposition
from trading_bot.live_prototype.emergency_operator import (
    EmergencyExitOperator,
    EmergencyExitStatus,
)


def test_emergency_exit_remains_disarmed_with_zero_mutations() -> None:
    result = EmergencyExitOperator().request_exit()

    assert result.status is EmergencyExitStatus.DISARMED
    assert result.reason == "L43_NOT_RUN"
    assert result.disposition is EffectDisposition.NO_EFFECT
    assert result.provider_mutation_count == 0


def test_operator_has_no_provider_dispatch_surface() -> None:
    operator = EmergencyExitOperator()

    assert not hasattr(operator, "place_order")
    assert not hasattr(operator, "cancel_order")
    assert not hasattr(operator, "sell")
