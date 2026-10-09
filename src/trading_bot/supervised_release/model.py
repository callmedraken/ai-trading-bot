"""Versioned release material and inert scheduler action projection.

All inputs are caller-supplied values. No filesystem/native/provider access.
Absolute deployment locations never participate in deterministic identities.
Inventory names are logical release-relative names, not host filesystem paths.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import PureWindowsPath
from uuid import UUID, uuid5

from trading_bot.strategies import MovingAverageCrossoverConfig

RELEASES_BASE = r"F:\AITradingBot\releases"
DURABLE_DATA_ROOT = r"F:\AITradingBot\Arch133"
PRODUCTION_PYTHON = r"F:\AITradingBot\runtime\python.exe"
LAUNCHER_RELATIVE_PATH = "scripts/run_arch133_unattended_review_paper.py"
MANIFEST_SCHEMA = "arch133-supervised-release/v1"
INVENTORY_SCHEMA = "arch133-release-source-inventory/v1"
CONFIG_SCHEMA = "moving-average-crossover-config/v1"
STRATEGY_ID = "MovingAverageCrossoverStrategy"
STRATEGY_VERSION = "1.0.0"
_RELEASE_NAMESPACE = UUID("e00c6e04-069f-5fa4-bd9f-a339058b15e7")


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: object, length: int = 64) -> None:
    if type(value) is not str or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError("invalid lowercase digest")


def _version(value: object, *, python: bool = False) -> None:
    if (
        type(value) is not str
        or re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
        is None
    ):
        raise ValueError("canonical major.minor.patch version required")
    if python and (int(value.split(".")[0]) != 3 or int(value.split(".")[1]) < 12):
        raise ValueError("production Python must be 3.12 or newer within Python 3")


def _relative_name(value: object) -> None:
    if type(value) is not str or not value or "\\" in value:
        raise ValueError("canonical slash-separated relative inventory name required")
    parts = value.split("/")
    for part in parts:
        if (
            not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
            or part in {".", ".."}
            or part.endswith((".", " "))
            or part.split(".")[0].upper()
            in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
            or re.fullmatch(r"(?:COM|LPT)[0-9]", part.split(".")[0].upper())
        ):
            raise ValueError("unsafe inventory name")
    # Only executable source/script material and the project dependency declaration.
    # Durable account/wake/paper data, runtime substrate, and generated reports
    # cannot be represented as inventory entries, even with a relative alias.
    if value != "pyproject.toml" and not (
        len(parts) > 1
        and parts[0] in {"src", "scripts"}
        and parts[-1].endswith((".py", ".ps1", ".json", ".sql"))
    ):
        raise ValueError("inventory is limited to source and dependency material")
    if any(part.lower() in {"arch133", "runtime", "releases"} for part in parts[1:-1]):
        # src/trading_bot/runtime is executable source, unlike an embedded data root.
        if not (
            parts[:3] == ["src", "trading_bot", "runtime"]
            and all(part.lower() != "arch133" for part in parts)
        ):
            raise ValueError("durable data and runtime substrate excluded")


def _quantity(value: Decimal) -> str:
    # as_tuple uses no arithmetic and never rounds under the caller's context.
    sign, digits, exponent = value.as_tuple()
    coefficient = "".join(str(digit) for digit in digits).lstrip("0")
    while coefficient.endswith("0"):
        coefficient = coefficient[:-1]
        exponent += 1
    return ("-" if sign else "") + coefficient + "e" + str(exponent)


def canonical_strategy_config(
    config: MovingAverageCrossoverConfig,
) -> dict[str, object]:
    """Describe exactly the existing public config; do not evaluate the strategy."""
    if type(config) is not MovingAverageCrossoverConfig:
        raise TypeError("exact MovingAverageCrossoverConfig required")
    return {
        "schema": CONFIG_SCHEMA,
        "short_window": config.short_window,
        "long_window": config.long_window,
        "desired_quantity": _quantity(config.desired_quantity),
    }


def strategy_config_sha256(config: MovingAverageCrossoverConfig) -> str:
    """Hash versioned logical config material, independent of JSON input bytes."""
    return hashlib.sha256(_json(canonical_strategy_config(config)).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ReleaseInventoryEntry:
    relative_path: str
    sha256: str

    def __post_init__(self) -> None:
        _relative_name(self.relative_path)
        _sha(self.sha256)

    def to_dict(self) -> dict[str, str]:
        return {"relative_path": self.relative_path, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """A declaration of reviewed release material, not proof of installed bytes."""

    source_head: str
    source_tree: str
    production_python_version: str
    production_python_sha256: str
    launcher_relative_path: str
    launcher_sha256: str
    source_inventory: tuple[ReleaseInventoryEntry, ...]
    strategy_id: str
    strategy_version: str
    strategy_config: MovingAverageCrossoverConfig
    risk_policy_id: str
    risk_policy_version: str
    risk_policy_sha256: str

    def __post_init__(self) -> None:
        _sha(self.source_head, 40)
        _sha(self.source_tree, 40)
        _version(self.production_python_version, python=True)
        _sha(self.production_python_sha256)
        _relative_name(self.launcher_relative_path)
        if self.launcher_relative_path != LAUNCHER_RELATIVE_PATH:
            raise ValueError("only the reviewed unattended launcher is supported")
        _sha(self.launcher_sha256)
        if type(self.source_inventory) is not tuple or not self.source_inventory:
            raise ValueError("nonempty immutable source inventory required")
        if any(
            type(entry) is not ReleaseInventoryEntry for entry in self.source_inventory
        ):
            raise ValueError("exact inventory entries required")
        names = [entry.relative_path.casefold() for entry in self.source_inventory]
        if len(set(names)) != len(names):
            raise ValueError("duplicate Windows inventory names")
        launcher = [
            entry
            for entry in self.source_inventory
            if entry.relative_path == self.launcher_relative_path
        ]
        if len(launcher) != 1 or launcher[0].sha256 != self.launcher_sha256:
            raise ValueError("launcher must match the exact source inventory")
        if type(self.strategy_id) is not str or self.strategy_id != STRATEGY_ID:
            raise ValueError("only MovingAverageCrossoverStrategy is supported")
        _version(self.strategy_version)
        canonical_strategy_config(self.strategy_config)
        if (
            type(self.risk_policy_id) is not str
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", self.risk_policy_id)
            is None
        ):
            raise ValueError("canonical risk policy identity required")
        _version(self.risk_policy_version)
        _sha(self.risk_policy_sha256)

    @property
    def source_inventory_sha256(self) -> str:
        material = {
            "schema": INVENTORY_SCHEMA,
            "entries": [entry.to_dict() for entry in self.source_inventory],
        }
        return hashlib.sha256(_json(material).encode()).hexdigest()

    @property
    def strategy_config_sha256(self) -> str:
        return strategy_config_sha256(self.strategy_config)

    def _material(self) -> dict[str, object]:
        return {
            "schema": MANIFEST_SCHEMA,
            "source_head": self.source_head,
            "source_tree": self.source_tree,
            "production_python_version": self.production_python_version,
            "production_python_sha256": self.production_python_sha256,
            "launcher_relative_path": self.launcher_relative_path,
            "launcher_sha256": self.launcher_sha256,
            "source_inventory": [entry.to_dict() for entry in self.source_inventory],
            "source_inventory_sha256": self.source_inventory_sha256,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "strategy_config": canonical_strategy_config(self.strategy_config),
            "strategy_config_sha256": self.strategy_config_sha256,
            "risk_policy_id": self.risk_policy_id,
            "risk_policy_version": self.risk_policy_version,
            "risk_policy_sha256": self.risk_policy_sha256,
        }

    @property
    def release_id(self) -> str:
        # UUID5 over versioned logical material, never supplied artifact bytes.
        return "release-" + uuid5(_RELEASE_NAMESPACE, _json(self._material())).hex

    def to_json(self) -> str:
        return _json({**self._material(), "release_id": self.release_id})

    @classmethod
    def from_json(cls, text: str) -> ReleaseManifest:
        """Reject unknown/missing/duplicate fields and inconsistent derived digests."""
        if type(text) is not str:
            raise ValueError("manifest JSON text required")
        try:
            raw = json.loads(text, object_pairs_hook=_unique_object)
            _fields(
                raw,
                {
                    "schema",
                    "release_id",
                    "source_head",
                    "source_tree",
                    "production_python_version",
                    "production_python_sha256",
                    "launcher_relative_path",
                    "launcher_sha256",
                    "source_inventory",
                    "source_inventory_sha256",
                    "strategy_id",
                    "strategy_version",
                    "strategy_config",
                    "strategy_config_sha256",
                    "risk_policy_id",
                    "risk_policy_version",
                    "risk_policy_sha256",
                },
            )
            config = raw["strategy_config"]
            _fields(
                config, {"schema", "short_window", "long_window", "desired_quantity"}
            )
            if (
                config["schema"] != CONFIG_SCHEMA
                or type(config["desired_quantity"]) is not str
            ):
                raise ValueError("invalid config schema or quantity")
            typed_config = MovingAverageCrossoverConfig(
                config["short_window"],
                config["long_window"],
                Decimal(config["desired_quantity"]),
            )
            if canonical_strategy_config(typed_config) != config:
                raise ValueError("noncanonical strategy configuration")
            if type(raw["source_inventory"]) is not list:
                raise ValueError("inventory array required")
            entries = []
            for item in raw["source_inventory"]:
                _fields(item, {"relative_path", "sha256"})
                entries.append(ReleaseInventoryEntry(**item))
            supplied = dict(raw)
            for name in (
                "schema",
                "release_id",
                "source_inventory_sha256",
                "strategy_config_sha256",
            ):
                supplied.pop(name)
            supplied["source_inventory"] = tuple(entries)
            supplied["strategy_config"] = typed_config
            result = cls(**supplied)
            if {**result._material(), "release_id": result.release_id} != raw:
                raise ValueError("manifest identity/schema/digest mismatch")
            return result
        except (TypeError, KeyError, ArithmeticError) as exc:
            raise ValueError("malformed release manifest") from exc


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _fields(value: object, fields: set[str]) -> None:
    if type(value) is not dict or set(value) != fields:
        raise ValueError("exact manifest fields required")


def release_root(release_id: str) -> str:
    """Derive a lexical root only; do not create or inspect it."""
    if (
        type(release_id) is not str
        or re.fullmatch(r"release-[0-9a-f]{32}", release_id) is None
    ):
        raise ValueError("canonical release ID required")
    identifier = UUID(hex=release_id[8:])
    if identifier.version != 5:
        raise ValueError("UUID5 release ID required")
    return str(PureWindowsPath(RELEASES_BASE) / release_id)


def validate_release_root(root: str, release_id: str) -> str:
    """Require the exact derived spelling; reject aliases and normalization tricks."""
    expected = release_root(release_id)
    if type(root) is not str or root != expected:
        raise ValueError("root must equal the fixed base plus exact release ID")
    return expected


@dataclass(frozen=True, slots=True)
class SchedulerActionProjection:
    """Inert action values with no task identity, mutation, or execution capability."""

    manifest: ReleaseManifest

    def __post_init__(self) -> None:
        if type(self.manifest) is not ReleaseManifest:
            raise TypeError("exact release manifest required")

    @property
    def executable(self) -> str:
        return PRODUCTION_PYTHON

    @property
    def working_directory(self) -> str:
        return release_root(self.manifest.release_id)

    @property
    def arguments(self) -> tuple[str, ...]:
        launcher = str(
            PureWindowsPath(self.working_directory)
            / self.manifest.launcher_relative_path
        )
        return ("-I", "-B", launcher)


def project_scheduler_action(
    manifest: ReleaseManifest, *, root: str | None = None
) -> SchedulerActionProjection:
    """Describe a future reviewed action; this does not admit or rebind a task."""
    result = SchedulerActionProjection(manifest)
    if root is not None:
        validate_release_root(root, manifest.release_id)
    return result
