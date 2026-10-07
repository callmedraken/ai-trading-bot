"""Architecture-133 fixed host locations and read-only runtime admission.

The administrator-reviewed host binding is published separately from activation.
Publication/provisioning is outside this source checkpoint. Architecture 133-G
reuses the already protected shared production Python substrate, but does not
reuse D10 deployment/lease/scheduler authority. Exact source facts remain
independently checked by 131-H; executable bytes/version and launch isolation
are independently checked here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

TRADING_SID = "S-1-5-21-1397534616-3988210162-180023805-1009"

HOST_SCHEMA = "arch133-review-paper-host-binding/v1"
RUNTIME_SCHEMA = "arch133-review-paper-runtime/v1"
SOURCE_BRANCH = "feature/robinhood-unattended-review-paper-133g"
SOURCE_ROOT = Path(r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133g")
HOST_ROOT = Path(r"F:\AITradingBot\Arch133")
PRODUCTION_PYTHON = Path(r"F:\AITradingBot\runtime\python.exe")
PRODUCTION_PYTHON_SHA256 = (
    "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
)
PRODUCTION_PYTHON_VERSION = "3.14.3"
LAUNCHER = SOURCE_ROOT / "scripts" / "run_arch133_unattended_review_paper.py"
BINDING_PATH = HOST_ROOT / "host-binding.json"
ACTIVATION_PATH = HOST_ROOT / "activation.json"
STATE_PATH = HOST_ROOT / "wake.sqlite"
PAPER_PATH = HOST_ROOT / "paper.sqlite"
EVIDENCE_PATH = HOST_ROOT / "operator-evidence.json"
NO_PYCACHE = HOST_ROOT / "no-pycache"
REDIRECT_URI = "http://127.0.0.1:8765/oauth/callback"


class UnattendedHostError(RuntimeError):
    """Only fixed sanitized diagnostics cross the host boundary."""


def _digest(value: object, length: int) -> None:
    if type(value) is not str or re.fullmatch(f"[0-9a-f]{{{length}}}", value) is None:
        raise UnattendedHostError("host binding invalid")


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True, slots=True)
class HostRuntimeIdentity:
    source_head: str
    source_tree: str
    python_sha256: str
    python_version: str
    launcher_sha256: str

    def __post_init__(self) -> None:
        _digest(self.source_head, 40)
        _digest(self.source_tree, 40)
        _digest(self.python_sha256, 64)
        _digest(self.launcher_sha256, 64)
        if (
            type(self.python_version) is not str
            or re.fullmatch(r"3\.(?:1[2-9]|[2-9][0-9])\.[0-9]+", self.python_version)
            is None
        ):
            raise UnattendedHostError("host binding invalid")

    @property
    def deployment_identity(self) -> str:
        # Deployment digest, not a deterministic domain UUID. Locations are fixed
        # by source; no caller path, activation, clock or serialized artifact bytes.
        facts = (RUNTIME_SCHEMA, SOURCE_BRANCH, TRADING_SID, *asdict(self).values())
        material = "".join(f"{len(value)}:{value}" for value in facts)
        return hashlib.sha256(material.encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class HostBinding:
    """Exact separately published deployment + activation + paper predecessor.

    oauth_valid_until is a reviewed explicit upper bound, never token renewal.
    It cannot be supplied by a scheduler, command line or environment variable.
    """

    runtime: HostRuntimeIdentity
    activation_sha256: str
    store_identity: UUID
    paper_predecessor_sha256: str
    oauth_valid_until: datetime

    def __post_init__(self) -> None:
        if (
            type(self.runtime) is not HostRuntimeIdentity
            or type(self.store_identity) is not UUID
        ):
            raise UnattendedHostError("host binding invalid")
        _digest(self.activation_sha256, 64)
        _digest(self.paper_predecessor_sha256, 64)
        value = self.oauth_valid_until
        if (
            type(value) is not datetime
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise UnattendedHostError("host binding invalid")
        object.__setattr__(self, "oauth_valid_until", value.astimezone(UTC))

    def to_json(self) -> str:
        return _json(
            {
                "schema": HOST_SCHEMA,
                "runtime": asdict(self.runtime),
                "activation_sha256": self.activation_sha256,
                "store_identity": str(self.store_identity),
                "paper_predecessor_sha256": self.paper_predecessor_sha256,
                "oauth_valid_until": self.oauth_valid_until.isoformat(
                    timespec="microseconds"
                ),
            }
        )

    @classmethod
    def from_json(cls, value: str) -> HostBinding:
        try:
            data = json.loads(value)
            if (
                type(data) is not dict
                or set(data)
                != {
                    "schema",
                    "runtime",
                    "activation_sha256",
                    "store_identity",
                    "paper_predecessor_sha256",
                    "oauth_valid_until",
                }
                or data.pop("schema") != HOST_SCHEMA
            ):
                raise ValueError
            data["runtime"] = HostRuntimeIdentity(**data["runtime"])
            data["store_identity"] = UUID(data["store_identity"])
            data["oauth_valid_until"] = datetime.fromisoformat(
                data["oauth_valid_until"]
            )
            result = cls(**data)
            if result.to_json() != value:
                raise ValueError
            return result
        except Exception:
            raise UnattendedHostError("host binding invalid") from None
