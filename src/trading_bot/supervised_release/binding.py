"""Pure verified-release runtime binding; no current host admission wiring."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from trading_bot.supervised_release.bundle import VerifiedRelease, canonical_json
from trading_bot.supervised_release.model import DURABLE_DATA_ROOT, release_root

RUNTIME_BINDING_SCHEMA = "arch133-supervised-release-runtime-binding/v1"
DEPENDENCY_CLOSURE = "UNPROVEN"


@dataclass(frozen=True, slots=True)
class RuntimeBinding:
    """Bind verified source evidence, with dependency closure explicitly unproven.

    The supplied Python identity is declarative, not a host observation.
    No durable schema compatibility or migration is asserted here.
    """

    verified_release: VerifiedRelease

    def __post_init__(self) -> None:
        if type(self.verified_release) is not VerifiedRelease:
            raise ValueError("verified release required")

    def to_dict(self) -> dict[str, str]:
        manifest = self.verified_release.manifest
        fields = (
            "source_head",
            "source_tree",
            "source_inventory_sha256",
            "production_python_version",
            "production_python_sha256",
            "launcher_relative_path",
            "launcher_sha256",
            "strategy_id",
            "strategy_version",
            "strategy_config_sha256",
            "risk_policy_id",
            "risk_policy_version",
            "risk_policy_sha256",
        )
        return {
            "schema": RUNTIME_BINDING_SCHEMA,
            "release_id": manifest.release_id,
            "manifest_sha256": self.verified_release.expected_manifest_sha256,
            **{field: getattr(manifest, field) for field in fields},
            "release_root": release_root(manifest.release_id),
            "durable_data_root": DURABLE_DATA_ROOT,
            "dependency_closure": DEPENDENCY_CLOSURE,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @property
    def sha256(self) -> str:
        """Artifact integrity digest; does not define a new domain identity."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(
        cls, text: str, *, verified_release: VerifiedRelease
    ) -> RuntimeBinding:
        """Replay against verified source authority, rejecting any field tamper."""
        result = cls(verified_release)
        if type(text) is not str or text != result.to_json():
            raise ValueError("runtime binding canonical identity mismatch")
        return result
