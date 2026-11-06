"""Emergency exit interlock; this source checkpoint keeps dispatch disarmed."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trading_bot.live_prototype.contracts import EffectDisposition


class EmergencyExitStatus(StrEnum):
    DISARMED = "DISARMED"


class EmergencyExitReason(StrEnum):
    L43_NOT_RUN = "L43_NOT_RUN"


@dataclass(frozen=True, slots=True)
class EmergencyExitResult:
    status: EmergencyExitStatus = EmergencyExitStatus.DISARMED
    reason: EmergencyExitReason = EmergencyExitReason.L43_NOT_RUN
    disposition: EffectDisposition = EffectDisposition.NO_EFFECT
    provider_mutation_count: int = 0

    def __post_init__(self) -> None:
        if self.status is not EmergencyExitStatus.DISARMED:
            raise ValueError("emergency exit remains disarmed in this source scope")
        if self.reason is not EmergencyExitReason.L43_NOT_RUN:
            raise ValueError("emergency exit remains disarmed until L43")
        if self.disposition is not EffectDisposition.NO_EFFECT:
            raise ValueError("disarmed emergency exit cannot report an effect")
        if self.provider_mutation_count != 0:
            raise ValueError("disarmed emergency exit cannot mutate a provider")


class EmergencyExitOperator:
    """No provider dependency or dispatch method exists before reviewed L43."""

    __slots__ = ()

    def request_exit(self) -> EmergencyExitResult:
        return EmergencyExitResult()
