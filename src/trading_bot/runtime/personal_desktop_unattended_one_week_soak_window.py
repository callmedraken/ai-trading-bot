"""Pure, fixed-duration Architecture-122 activation window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class OneWeekSoakState(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


def _utc_instant(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("soak instant must be an aware datetime")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class OneWeekSoakWindow:
    activation_utc: datetime
    end_utc: datetime

    def __post_init__(self) -> None:
        activation = _utc_instant(self.activation_utc)
        end = _utc_instant(self.end_utc)
        if (
            self.activation_utc.tzinfo is not UTC
            or self.end_utc.tzinfo is not UTC
            or self.activation_utc != activation
            or self.end_utc != end
            or end != activation + timedelta(days=7)
        ):
            raise ValueError("soak window must be exact UTC activation plus seven days")

    def state_at(self, observed_at: datetime) -> OneWeekSoakState:
        instant = _utc_instant(observed_at)
        if self.activation_utc <= instant < self.end_utc:
            return OneWeekSoakState.ACTIVE
        return OneWeekSoakState.EXPIRED


def build_one_week_soak_window(activation: datetime) -> OneWeekSoakWindow:
    """Normalize accepted deployment activation to an exact UTC interval."""

    instant = _utc_instant(activation)
    return OneWeekSoakWindow(instant, instant + timedelta(days=7))
