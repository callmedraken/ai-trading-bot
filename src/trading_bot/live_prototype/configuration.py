"""Effect-disabled v1 configuration and exact completed-close contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

CANDIDATE_NAMES = ("BASE_MA35_50_V1", "PRICE_SMA200_V1", "PRICE_MOM_252_V1")


def _digest(value: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("exact SHA256 required")


def _sha1(value: str) -> None:
    if (
        type(value) is not str
        or len(value) != 40
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("exact executable SHA1 required")


@dataclass(frozen=True, slots=True)
class ResearchCampaignSpec:
    candidates: tuple[str, ...] = CANDIDATE_NAMES
    price_basis: str = "ALPACA_ALL_ADJUSTED_PRICE_V1"
    policy: str = "comparison-v2/qualification-v1"
    prior_configurations: int = 30
    comparison_configurations: int = 3
    independent_holdout: bool = False

    def __post_init__(self) -> None:
        if (
            self.candidates != CANDIDATE_NAMES
            or self.price_basis != "ALPACA_ALL_ADJUSTED_PRICE_V1"
            or self.policy != "comparison-v2/qualification-v1"
            or type(self.prior_configurations) is not int
            or self.prior_configurations != 30
            or type(self.comparison_configurations) is not int
            or self.comparison_configurations != 3
            or self.independent_holdout is not False
        ):
            raise ValueError("frozen research contract required")


@dataclass(frozen=True, slots=True)
class SelectedStrategyBinding:
    candidate: str
    research_digest: str
    dataset_digest: str
    price_basis: str = "ALPACA_ALL_ADJUSTED_PRICE_V1"
    purpose: str = "RESEARCH_COMPARISON"
    live_eligible: bool = False

    def __post_init__(self) -> None:
        _digest(self.research_digest)
        _digest(self.dataset_digest)
        if (
            self.candidate not in CANDIDATE_NAMES
            or self.price_basis != "ALPACA_ALL_ADJUSTED_PRICE_V1"
            or self.purpose != "RESEARCH_COMPARISON"
            or self.live_eligible is not False
        ):
            raise ValueError("research binding grants no live authority")


@dataclass(frozen=True, slots=True)
class CompletedSignalInputs:
    """Exact selected sessions; structural validation grants no provider readiness."""

    symbol: str
    selected_sessions: tuple[date, ...]
    sessions: tuple[date, ...]
    closes: tuple[Decimal, ...]
    price_basis: str
    source_digest: str
    as_of: datetime
    cutoff: datetime

    def __post_init__(self) -> None:
        _digest(self.source_digest)
        if self.symbol != "SPY" or self.price_basis not in (
            "ALPACA_ALL_ADJUSTED_PRICE_V1",
            "ROBINHOOD_HISTORY59_PLUS_OFFICIAL_CLOSE_V1",
        ):
            raise ValueError("unsupported symbol or price basis")
        if (
            type(self.sessions) is not tuple
            or type(self.selected_sessions) is not tuple
            or type(self.closes) is not tuple
            or not self.sessions
            or self.sessions != self.selected_sessions
            or len(self.sessions) != len(self.closes)
            or any(type(s) is not date for s in self.sessions)
            or any(
                a >= b for a, b in zip(self.sessions, self.sessions[1:], strict=False)
            )
            or any(
                type(v) is not Decimal or not v.is_finite() or v <= 0
                for v in self.closes
            )
        ):
            raise ValueError("exact ordered completed sessions and closes required")
        if (
            type(self.as_of) is not datetime
            or type(self.cutoff) is not datetime
            or self.as_of.utcoffset() != timedelta(0)
            or self.cutoff.utcoffset() != timedelta(0)
            or self.cutoff > self.as_of
            or self.sessions[-1] > self.cutoff.date()
            or (
                self.sessions[-1] == self.cutoff.date()
                and self.cutoff.time() == time.min
            )
        ):
            raise ValueError("completed inputs require an explicit completion cutoff")

    @property
    def digest(self) -> str:
        def text(v: Decimal) -> str:
            value = format(v, "f")
            return value.rstrip("0").rstrip(".") if "." in value else value

        material = {
            "schema": "prototype-completed-closes/v1",
            "symbol": self.symbol,
            "sessions": tuple(s.isoformat() for s in self.sessions),
            "closes": tuple(text(v) for v in self.closes),
            "price_basis": self.price_basis,
            "source_digest": self.source_digest,
            "as_of": self.as_of.isoformat(),
            "cutoff": self.cutoff.isoformat(),
        }
        return hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class PrototypeSessionConfiguration:
    mode: str
    source_head: str
    source_tree: str
    state_root: Path
    binding: SelectedStrategyBinding | None = None
    read_policy: str = "NO_PROVIDER_READS"
    risk_policy: str = "NO_EXTERNAL_EFFECTS"

    def __post_init__(self) -> None:
        _sha1(self.source_head)
        _sha1(self.source_tree)
        if (
            self.mode != "SYNTHETIC"
            or self.read_policy != "NO_PROVIDER_READS"
            or self.risk_policy != "NO_EXTERNAL_EFFECTS"
            or not isinstance(self.state_root, Path)
            or not self.state_root.is_absolute()
            or self.state_root.drive.upper() != "F:"
        ):
            raise ValueError("only isolated F: synthetic configuration is supported")
