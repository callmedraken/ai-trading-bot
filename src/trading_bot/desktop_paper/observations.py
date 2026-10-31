"""Single-lane, deterministic OPEN replay observations for desktop paper use."""

from __future__ import annotations

import hashlib
import math
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.domain import Bar, Symbol
from trading_bot.domain._validation import normalize_utc, require_positive_decimal

OPEN_REPLAY_OBSERVATION_SCHEMA = "desktop-paper-open-replay-observation/v1"
OPEN_REPLAY_OBSERVATION_NAMESPACE = UUID("f73f9e8e-53a2-5c0a-a462-479cb2e3bf8a")


class PaperObservationStatus(StrEnum):
    READY = "READY"
    WARMUP = "WARMUP"
    EXHAUSTED = "EXHAUSTED"


@dataclass(frozen=True, slots=True)
class PaperObservation:
    """One session's open and only the history completed before that session."""

    execution_session_id: str
    execution_index: int
    symbol: Symbol
    observation_id: UUID
    completed_history_cutoff: str
    observation_open: Decimal
    executed_at: datetime
    completed_history: tuple[Bar, ...]
    warmup: bool
    source_identity_digest: str
    status: PaperObservationStatus

    def __post_init__(self) -> None:
        if (
            not isinstance(self.execution_session_id, str)
            or not self.execution_session_id
        ):
            raise ValueError("execution_session_id must be nonblank")
        if type(self.execution_index) is not int or self.execution_index < 1:
            raise ValueError("execution_index must be positive")
        if type(self.symbol) is not Symbol:
            raise TypeError("symbol must be an exact Symbol")
        if type(self.observation_id) is not UUID:
            raise TypeError("observation_id must be a UUID")
        if not isinstance(self.completed_history_cutoff, str):
            raise TypeError("completed_history_cutoff must be a string")
        require_positive_decimal(self.observation_open, "observation_open")
        object.__setattr__(
            self, "executed_at", normalize_utc(self.executed_at, "executed_at")
        )
        history = tuple(self.completed_history)
        previous: datetime | None = None
        for bar in history:
            if type(bar) is not Bar or bar.symbol != self.symbol:
                raise ValueError("completed_history must contain matching Bars")
            if bar.timestamp >= self.executed_at:
                raise ValueError("completed_history must precede execution")
            if previous is not None and bar.timestamp <= previous:
                raise ValueError("completed_history must be strictly chronological")
            previous = bar.timestamp
        expected_cutoff = "" if previous is None else previous.isoformat()
        if self.completed_history_cutoff != expected_cutoff:
            raise ValueError("completed_history_cutoff does not match history")
        object.__setattr__(self, "completed_history", history)
        if type(self.warmup) is not bool:
            raise TypeError("warmup must be a bool")
        expected_status = (
            PaperObservationStatus.WARMUP
            if self.warmup
            else PaperObservationStatus.READY
        )
        if self.status is not expected_status:
            raise ValueError("status does not match warmup state")
        if (
            not isinstance(self.source_identity_digest, str)
            or len(self.source_identity_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.source_identity_digest
            )
        ):
            raise ValueError("source_identity_digest must be lowercase SHA256 hex")


@dataclass(frozen=True, slots=True)
class PaperObservationExhausted:
    """Visible terminal state once the OPEN source has no later session."""

    consumed_execution_index: int
    total_sessions: int
    symbol: Symbol
    source_identity_digest: str
    status: PaperObservationStatus = field(
        default=PaperObservationStatus.EXHAUSTED, init=False
    )

    def __post_init__(self) -> None:
        if (
            type(self.consumed_execution_index) is not int
            or self.consumed_execution_index < 0
        ):
            raise ValueError("consumed_execution_index must be nonnegative")
        if type(self.total_sessions) is not int or self.total_sessions < 0:
            raise ValueError("total_sessions must be nonnegative")
        if self.consumed_execution_index > self.total_sessions:
            raise ValueError("consumed cursor exceeds source length")
        if type(self.symbol) is not Symbol:
            raise TypeError("symbol must be an exact Symbol")
        if (
            not isinstance(self.source_identity_digest, str)
            or len(self.source_identity_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.source_identity_digest
            )
        ):
            raise ValueError("source_identity_digest must be lowercase SHA256 hex")


PaperObservationResult = PaperObservation | PaperObservationExhausted


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("replay identity price must be finite")
    sign, digits_tuple, exponent = value.as_tuple()
    digits = list(digits_tuple)
    if not any(digits):
        return "0"
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    digits_text = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        rendered = digits_text + ("0" * exponent)
    else:
        point = len(digits_text) + exponent
        if point > 0:
            rendered = f"{digits_text[:point]}.{digits_text[point:]}"
        else:
            rendered = f"0.{('0' * -point)}{digits_text}"
    return f"-{rendered}" if sign else rendered


def _bar_prefix_material(bar: Bar, *, include_close: bool) -> tuple[str, ...]:
    values = [
        str(bar.symbol),
        bar.timestamp.isoformat(),
        _canonical_decimal(bar.open),
    ]
    if include_close:
        values.extend(
            (
                _canonical_decimal(bar.high),
                _canonical_decimal(bar.low),
                _canonical_decimal(bar.close),
                str(bar.volume),
            )
        )
    return tuple(values)


def _prefix_digest(
    symbol: Symbol, completed_history: tuple[Bar, ...], execution_bar: Bar
) -> str:
    material = [
        OPEN_REPLAY_OBSERVATION_SCHEMA,
        str(symbol),
        "completed",
    ]
    for bar in completed_history:
        material.extend(_bar_prefix_material(bar, include_close=True))
    material.extend(
        (
            "execution-open",
            *_bar_prefix_material(execution_bar, include_close=False),
        )
    )
    return hashlib.sha256("\n".join(material).encode("utf-8")).hexdigest()


class OpenReplayObservationSource:
    """One forward-only chronological observation lane over immutable OPEN bars."""

    def __init__(
        self,
        bars: Iterable[Bar],
        *,
        symbol: Symbol,
        minimum_history_bars: int,
    ) -> None:
        if type(symbol) is not Symbol:
            raise TypeError("symbol must be an exact Symbol")
        if type(minimum_history_bars) is not int or minimum_history_bars < 1:
            raise ValueError("minimum_history_bars must be a positive integer")
        values = tuple(bars)
        previous: datetime | None = None
        for bar in values:
            if type(bar) is not Bar or bar.symbol != symbol:
                raise ValueError("OPEN replay bars must match the selected symbol")
            if previous is not None and bar.timestamp <= previous:
                raise ValueError("OPEN replay bars must be strictly chronological")
            require_positive_decimal(bar.open, "execution open")
            previous = bar.timestamp
        self._bars = values
        self._symbol = symbol
        self._minimum_history_bars = minimum_history_bars
        self._cursor = 0
        self._lock = threading.Lock()
        self._status = (
            PaperObservationStatus.EXHAUSTED
            if not values
            else (
                PaperObservationStatus.WARMUP
                if minimum_history_bars > 0
                else PaperObservationStatus.READY
            )
        )
        self._source_identity_digest = self._full_source_digest()

    @classmethod
    def from_storage(
        cls,
        storage: object,
        *,
        symbol: Symbol,
        minimum_history_bars: int,
    ) -> OpenReplayObservationSource:
        """Load the accepted OPEN projection through its public desktop reader."""
        from trading_bot.experiments.historical_research_desktop import (
            DesktopResearchStorage,
            load_desktop_open_research,
        )

        if type(storage) is not DesktopResearchStorage:
            raise TypeError("storage must be an exact DesktopResearchStorage")
        data = load_desktop_open_research(storage)
        if data.request.symbol != symbol:
            raise ValueError("loaded OPEN data does not match the requested symbol")
        return cls(
            data.bars,
            symbol=symbol,
            minimum_history_bars=minimum_history_bars,
        )

    @classmethod
    def from_bars(
        cls,
        bars: Iterable[Bar],
        *,
        symbol: Symbol,
        minimum_history_bars: int,
    ) -> OpenReplayObservationSource:
        """Build an explicit in-memory source for deterministic synthetic fixtures."""
        return cls(
            bars,
            symbol=symbol,
            minimum_history_bars=minimum_history_bars,
        )

    @property
    def cursor(self) -> int:
        """Number of source sessions already handed to the caller."""
        with self._lock:
            return self._cursor

    @property
    def status(self) -> PaperObservationStatus:
        with self._lock:
            return self._status

    @property
    def source_identity_digest(self) -> str:
        return self._source_identity_digest

    def seek_after(self, consumed_execution_index: int) -> None:
        """Resume after a durable cursor; a live source cursor cannot rewind."""
        if type(consumed_execution_index) is not int or consumed_execution_index < 0:
            raise ValueError("consumed_execution_index must be nonnegative")
        if consumed_execution_index > len(self._bars):
            raise ValueError("consumed cursor exceeds source length")
        with self._lock:
            if consumed_execution_index < self._cursor:
                raise ValueError("OPEN replay source cannot rewind")
            self._cursor = consumed_execution_index
            if self._cursor >= len(self._bars):
                self._status = PaperObservationStatus.EXHAUSTED
            else:
                self._status = (
                    PaperObservationStatus.WARMUP
                    if self._cursor < self._minimum_history_bars
                    else PaperObservationStatus.READY
                )

    def next_observation(self) -> PaperObservationResult:
        """Return one warmup/ready cycle or a stable exhausted state."""
        with self._lock:
            execution_index = self._cursor + 1
            if execution_index > len(self._bars):
                self._status = PaperObservationStatus.EXHAUSTED
                return PaperObservationExhausted(
                    consumed_execution_index=self._cursor,
                    total_sessions=len(self._bars),
                    symbol=self._symbol,
                    source_identity_digest=self._source_identity_digest,
                )
            execution_bar = self._bars[execution_index - 1]
            completed_history = self._bars[: execution_index - 1]
            cutoff = (
                ""
                if not completed_history
                else completed_history[-1].timestamp.isoformat()
            )
            warmup = len(completed_history) < self._minimum_history_bars
            prefix_digest = _prefix_digest(
                self._symbol, completed_history, execution_bar
            )
            observation_id = uuid5(
                OPEN_REPLAY_OBSERVATION_NAMESPACE,
                "\n".join(
                    (
                        OPEN_REPLAY_OBSERVATION_SCHEMA,
                        str(self._symbol),
                        str(execution_index),
                        execution_bar.timestamp.isoformat(),
                        cutoff,
                        _canonical_decimal(execution_bar.open),
                        prefix_digest,
                    )
                ),
            )
            observation = PaperObservation(
                execution_session_id=(
                    f"OPEN_REPLAY:{self._symbol}:{execution_bar.timestamp.isoformat()}:"
                    f"{prefix_digest}"
                ),
                execution_index=execution_index,
                symbol=self._symbol,
                observation_id=observation_id,
                completed_history_cutoff=cutoff,
                observation_open=execution_bar.open,
                executed_at=execution_bar.timestamp,
                completed_history=completed_history,
                warmup=warmup,
                source_identity_digest=prefix_digest,
                status=(
                    PaperObservationStatus.WARMUP
                    if warmup
                    else PaperObservationStatus.READY
                ),
            )
            self._cursor = execution_index
            self._status = observation.status
            return observation

    def wait_interruptibly(
        self,
        stop_event: threading.Event,
        delay_seconds: Decimal | float | int,
    ) -> bool:
        """Wait for a virtual session interval; return False when interrupted."""
        if not isinstance(stop_event, threading.Event):
            raise TypeError("stop_event must be a threading.Event")
        if type(delay_seconds) not in (Decimal, float, int):
            raise TypeError("delay_seconds must be Decimal, float, or int")
        if isinstance(delay_seconds, Decimal):
            if not delay_seconds.is_finite() or delay_seconds < 0:
                raise ValueError("delay_seconds must be finite and nonnegative")
        elif not math.isfinite(float(delay_seconds)) or delay_seconds < 0:
            raise ValueError("delay_seconds must be finite and nonnegative")
        return not stop_event.wait(float(delay_seconds))

    def _full_source_digest(self) -> str:
        material = [OPEN_REPLAY_OBSERVATION_SCHEMA, str(self._symbol), "source"]
        for bar in self._bars:
            material.extend(_bar_prefix_material(bar, include_close=True))
        return hashlib.sha256("\n".join(material).encode("utf-8")).hexdigest()
