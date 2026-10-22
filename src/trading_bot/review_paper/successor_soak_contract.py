"""Frozen D1 semantic material. Pure declarations; no execution authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5

from trading_bot.supervised_release.binding import RUNTIME_BINDING_SCHEMA
from trading_bot.supervised_release.model import MANIFEST_SCHEMA, ReleaseManifest
from trading_bot.supervised_release.runtime_isolation import (
    DurableStoreIdentity,
    InstalledRuntimeMaterial,
)

DESIGN_SCHEMA = "arch134-f1r1-d1-successor-soak-design/v1"
LINEAGE_SCHEMA = "arch134-f1r1-d1-successor-lineage/v1"
EVIDENCE_SCHEMA = "arch134-f1r1-d1-successor-evidence/v1"
IDENTITY_NAMESPACE = "arch134-f1r1-d1-successor-soak-identity/v1"
PRODUCTION_ROOT = r"F:\AITradingBot\Arch133\arch134-f1r1-d1-successor-soak-v1"
PARENT_NAME = "successor-parent-v1.jsonl"
SESSION_NAMES = ("successor-session-01-v1.jsonl", "successor-session-02-v1.jsonl")
SESSIONS = ("2026-11-02", "2026-11-03")
PRODUCT = ("SPY", "LONG_ONLY", "US_ETF", "SYNTHETIC_REVIEW_PAPER")
MAX_BYTES = 128 * 1024
MAX_RECORDS = 64
# (name, parent ceiling, per-session ceiling); no caller-selected budgets.
EFFECT_CEILINGS = (
    ("parent_creations", 1, 0),
    ("child_grants", 2, 1),
    ("manual_start_admissions", 2, 1),
    ("prerequisite_admissions", 2, 1),
    ("prerequisite_publications", 2, 1),
    ("historical_d1r7_d1r8_reuse", 0, 0),
    ("provider_entries", 2, 1),
    ("provider_retries", 0, 0),
    ("paper_attempts", 2, 1),
    ("paper_fills", 2, 1),
    ("broker_paper_operations", 0, 0),
    ("credential_phases", 2, 1),
    ("release_installations_publications", 0, 0),
    ("scheduler_operations", 0, 0),
    ("automatic_startups", 0, 0),
    ("runtime_reboots_logoffs", 0, 0),
    ("read_only_reconciliations", 2, 0),
    ("broker_orders_cancels_replaces", 0, 0),
    ("d2_operations", 0, 0),
    ("promotion_strategy_mutations", 0, 0),
    ("live_money_effects", 0, 0),
)
ADMISSION_CONTRACTS = (
    MANIFEST_SCHEMA,
    RUNTIME_BINDING_SCHEMA,
    "arch133-robinhood-supervised-runtime-host-admission",
    "arch134-f1r1-a-runtime-isolation/v1",
    "arch134-f1r1-b-host-composition/v1",
    "READY_FOR_F1R1_HOST_QUALIFICATION",
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


STORE_IDENTITY = DurableStoreIdentity(
    "arch134-f1r1-d1-successor-soak-v1",
    digest(
        canonical({"schema": EVIDENCE_SCHEMA, "files": (PARENT_NAME, *SESSION_NAMES)})
    ),
)


class SessionTerminal(StrEnum):
    NO_SIGNAL = "NO_SIGNAL"
    RISK_REJECTED = "RISK_REJECTED"
    PAPER_EXECUTED = "PAPER_EXECUTED"
    SESSION_MISSED = "SESSION_MISSED"
    BLOCKED = "BLOCKED"
    INDETERMINATE = "INDETERMINATE"


PROGRESSING = frozenset(
    (
        SessionTerminal.NO_SIGNAL,
        SessionTerminal.RISK_REJECTED,
        SessionTerminal.PAPER_EXECUTED,
    )
)


class QuoteDisposition(StrEnum):
    NO_SIGNAL = "NO_SIGNAL"
    RISK_REJECTED = "RISK_REJECTED"
    PAPER_REQUIRED = "PAPER_REQUIRED"


def ordinal_index(ordinal: int) -> int:
    if type(ordinal) is not int or ordinal not in (1, 2):
        raise ValueError("exact fixed successor ordinal required")
    return ordinal - 1


def validate_counters(counters: object, *, session: bool) -> dict[str, int]:
    if type(counters) is not dict or set(counters) != {
        n for n, _, _ in EFFECT_CEILINGS
    }:
        raise ValueError("closed complete successor counters required")
    for name, total, child in EFFECT_CEILINGS:
        value = counters[name]
        ceiling = child if session else total
        if type(value) is not int or not 0 <= value <= ceiling:
            raise ValueError("successor effect ceiling rejected")
    return counters


def zero_counters() -> dict[str, int]:
    return {name: 0 for name, _, _ in EFFECT_CEILINGS}


@dataclass(frozen=True, slots=True)
class SuccessorLineage:
    """Exact release and immutable local binding, never operator start options.

    A later reviewed installation boundary must fix this material to accepted
    source. Constructing it here is a source model, not production admission.
    File/process observations are deliberately not identity inputs.
    """

    material: InstalledRuntimeMaterial

    def __post_init__(self) -> None:
        if type(self.material) is not InstalledRuntimeMaterial:
            raise ValueError("exact installed runtime material required")
        if self.material.durable_store_identities != (STORE_IDENTITY,):
            raise ValueError("exact fresh successor durable store required")

    def facts(self) -> dict:
        manifest = self.material.manifest
        return {
            "schema": LINEAGE_SCHEMA,
            "design": DESIGN_SCHEMA,
            "identity_namespace": IDENTITY_NAMESPACE,
            "manifest": json.loads(manifest.to_json()),
            "manifest_sha256": self.material.manifest_sha256,
            "binding_sha256": self.material.binding_sha256,
            "runtime_id": self.material.runtime_id,
            "admission_contracts": list(ADMISSION_CONTRACTS),
            "store": STORE_IDENTITY.to_dict(),
            "product": list(PRODUCT),
            "sessions": list(SESSIONS),
            "ceilings": [list(value) for value in EFFECT_CEILINGS],
        }

    @property
    def parent_id(self) -> str:
        namespace = uuid5(NAMESPACE_URL, IDENTITY_NAMESPACE)
        return str(uuid5(namespace, canonical(self.facts()).decode("utf-8")))

    def child_id(self, ordinal: int) -> str:
        index = ordinal_index(ordinal)
        namespace = uuid5(NAMESPACE_URL, IDENTITY_NAMESPACE + "/session/v1")
        return str(
            uuid5(
                namespace,
                canonical(
                    {
                        "schema": LINEAGE_SCHEMA,
                        "parent_id": self.parent_id,
                        "ordinal": ordinal,
                        "target_session": SESSIONS[index],
                    }
                ).decode("utf-8"),
            )
        )

    @classmethod
    def from_facts(cls, value: dict) -> SuccessorLineage:
        # Reconstruct with accepted public codecs, then require the closed projection.
        manifest = ReleaseManifest.from_json(
            canonical(value["manifest"]).decode("utf-8")
        )
        result = cls(
            InstalledRuntimeMaterial(
                manifest, value["binding_sha256"], (STORE_IDENTITY,)
            )
        )
        if canonical(result.facts()) != canonical(value):
            raise ValueError("successor lineage mismatch")
        return result
