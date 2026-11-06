"""Strict, effect-free validation of the consumed L41 predecessor record.

The result is immutable historical evidence only. It is deliberately not a
capability object and carries neither observation retry nor live authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final

from trading_bot.live_prototype.capability_observer import (
    Classification,
    FactId,
    OverallStatus,
)

CONSUMED_L41_SCHEMA: Final = "arch147-l41-capability-observation/v1"
CONSUMED_L41_EVIDENCE_SHA256: Final = (
    "c85ba6d18bf1a3f234d7055dbe564fb7e2df4e1db8cc0f9f16c6b19e0d695c0c"
)
CONSUMED_L41_EVIDENCE_BYTES: Final = 4114
ACCEPTED_L41_BRANCH: Final = "feature/robinhood-live-prototype-current"
ACCEPTED_L41_HEAD: Final = "8ebbbcbf44fcba0e041601a332bc6029692ef396"
ACCEPTED_L41_TREE: Final = "eaf7ee6cd82ed895632725ac682123f3ab8e2ab2"

_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ACCOUNT_TYPE = re.compile(r"[a-z][a-z_]{0,63}\Z")

_ROOT_KEYS = frozenset(
    {"schema", "status", "reason", "source", "capability_report", "attempts"}
)
_SOURCE_KEYS = frozenset(
    {
        "branch",
        "head",
        "tree",
        "origin_feature_head",
        "origin_feature_tree",
        "origin_develop_head",
        "origin_develop_tree",
        "feature_authority",
        "prospective_develop_authority",
    }
)
_REPORT_KEYS = frozenset({"status", "account_fingerprint", "account_type", "facts"})
_FACT_KEYS = frozenset(
    {"fact_id", "classification", "rationale_code", "evidence_sha256", "provenance"}
)
_ATTEMPT_KEYS = frozenset(
    {
        "oauth_scope_entry_attempts",
        "native_credential_read_count",
        "credential_store_accounting",
        "mcp_session_open_attempts",
        "get_accounts_attempts",
        "get_equity_tradability_attempts",
        "collector_invocations",
        "collector_get_accounts_attempts",
        "collector_get_equity_tradability_attempts",
        "other_tool_attempts",
        "review_equity_order_attempts",
        "place_equity_order_attempts",
        "cancel_equity_order_attempts",
    }
)

_EXPECTED_CLASSIFICATIONS: Final = {
    FactId.INTENDED_AGENTIC_ACCOUNT: Classification.PROVEN,
    FactId.SPY_TRADABILITY: Classification.PROVEN,
    FactId.FRACTIONAL_ELIGIBILITY: Classification.PROVEN,
    FactId.INSTANCE_REVIEW_REQUIRES_POSITION: (
        Classification.DEFER_TO_FIRST_OWNED_POSITION
    ),
}
_EXPECTED_RATIONALES: Final = {
    FactId.INTENDED_AGENTIC_ACCOUNT: "ACCOUNT_IDENTITY_PROVEN",
    FactId.SPY_TRADABILITY: "SPY_TRADABILITY_PROVEN",
    FactId.FRACTIONAL_ELIGIBILITY: "SPY_FRACTIONAL_ELIGIBILITY_PROVEN",
    FactId.SELL_QUANTITY_FIELD: "SELL_QUANTITY_INTERFACE_UNPROVEN",
    FactId.DECIMAL_INTERFACE_PRECISION: "SIX_DECIMAL_INTERFACE_BOUND_UNPROVEN",
    FactId.QUANTITY_INCREMENT: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.MINIMUM_QUANTITY: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.MAXIMUM_QUANTITY_OR_ABSENCE: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.BELOW_MINIMUM_FULL_CLOSE: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.RESIDUAL_FULL_OWNED_CLOSE: "OFFICIAL_RULE_UNUNPROVEN",
    FactId.REVIEW_PREVIEW_ONLY: "REVIEW_PREVIEW_SEMANTICS_UNPROVEN",
    FactId.INSTANCE_REVIEW_REQUIRES_POSITION: "EXACT_OWNED_POSITION_REVIEW_DEFERRED",
}


@dataclass(frozen=True, slots=True)
class ConsumedL41Source:
    branch: str
    head: str
    tree: str
    origin_feature_head: str
    origin_feature_tree: str
    origin_develop_head: str
    origin_develop_tree: str
    feature_authority: str
    prospective_develop_authority: str


@dataclass(frozen=True, slots=True)
class ConsumedL41Fact:
    fact_id: FactId
    classification: Classification
    rationale_code: str
    evidence_sha256: str


@dataclass(frozen=True, slots=True)
class ConsumedL41Attempts:
    oauth_scope_entry_attempts: int
    native_credential_read_count: None
    credential_store_accounting: str
    mcp_session_open_attempts: int
    get_accounts_attempts: int
    get_equity_tradability_attempts: int
    collector_invocations: int
    collector_get_accounts_attempts: int
    collector_get_equity_tradability_attempts: int
    other_tool_attempts: int
    review_equity_order_attempts: int
    place_equity_order_attempts: int
    cancel_equity_order_attempts: int


@dataclass(frozen=True, slots=True)
class ConsumedL41Predecessor:
    """Sanitized facts preserved for lineage; never a reusable capability."""

    evidence_sha256: str
    byte_length: int
    status: OverallStatus
    reason: str
    source: ConsumedL41Source
    capability_report_status: OverallStatus
    account_fingerprint: str
    account_type: str
    facts: tuple[ConsumedL41Fact, ...]
    attempts: ConsumedL41Attempts

    @property
    def consumed(self) -> bool:
        return True

    @property
    def retry_authority(self) -> bool:
        return False

    @property
    def capability_authority(self) -> bool:
        return False


def validate_consumed_l41_document(
    document: object, *, evidence_sha256: str, byte_length: int
) -> ConsumedL41Predecessor:
    """Validate coordinator-parsed fields against the one consumed artifact.

    This pure function does not access a path, credentials, a provider, MCP, or
    an observation operator. The coordinator supplies the preserved artifact's
    digest and byte length; both must match this fixed predecessor identity.
    """
    if (
        type(evidence_sha256) is not str
        or evidence_sha256 != CONSUMED_L41_EVIDENCE_SHA256
        or type(byte_length) is not int
        or byte_length != CONSUMED_L41_EVIDENCE_BYTES
    ):
        raise ValueError("L41_CONSUMED_EVIDENCE_IDENTITY_MISMATCH")

    root = _mapping(document, _ROOT_KEYS, "L41_CONSUMED_EVIDENCE_SCHEMA_INVALID")
    if root["schema"] != CONSUMED_L41_SCHEMA:
        raise ValueError("L41_CONSUMED_EVIDENCE_SCHEMA_INVALID")
    if root["status"] != OverallStatus.BLOCKED.value:
        raise ValueError("L41_CONSUMED_EVIDENCE_OUTCOME_INVALID")
    if root["reason"] != "L41_OBSERVATION_FAILED":
        raise ValueError("L41_CONSUMED_EVIDENCE_OUTCOME_INVALID")

    source = _parse_source(root["source"])
    report = _mapping(
        root["capability_report"],
        _REPORT_KEYS,
        "L41_CONSUMED_EVIDENCE_REPORT_INVALID",
    )
    if report["status"] != OverallStatus.BLOCKED.value:
        raise ValueError("L41_CONSUMED_EVIDENCE_REPORT_INVALID")
    fingerprint = report["account_fingerprint"]
    if type(fingerprint) is not str or _SHA256.fullmatch(fingerprint) is None:
        raise ValueError("L41_CONSUMED_EVIDENCE_ACCOUNT_INVALID")
    account_type = report["account_type"]
    if type(account_type) is not str or _ACCOUNT_TYPE.fullmatch(account_type) is None:
        raise ValueError("L41_CONSUMED_EVIDENCE_ACCOUNT_INVALID")
    facts, _ = _parse_facts(report["facts"])
    attempts = _parse_attempts(root["attempts"])

    return ConsumedL41Predecessor(
        evidence_sha256=evidence_sha256,
        byte_length=byte_length,
        status=OverallStatus.BLOCKED,
        reason="L41_OBSERVATION_FAILED",
        source=source,
        capability_report_status=OverallStatus.BLOCKED,
        account_fingerprint=fingerprint,
        account_type=account_type,
        facts=facts,
        attempts=attempts,
    )


def parse_consumed_l41_bytes(raw: bytes) -> ConsumedL41Predecessor:
    """Parse bytes supplied by a caller and verify their fixed artifact identity."""
    if type(raw) is not bytes:
        raise TypeError("L41_CONSUMED_EVIDENCE_BYTES_INVALID")
    digest = hashlib.sha256(raw).hexdigest()
    if (
        digest != CONSUMED_L41_EVIDENCE_SHA256
        or len(raw) != CONSUMED_L41_EVIDENCE_BYTES
    ):
        raise ValueError("L41_CONSUMED_EVIDENCE_IDENTITY_MISMATCH")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ValueError("L41_CONSUMED_EVIDENCE_JSON_INVALID") from None
    return validate_consumed_l41_document(
        document, evidence_sha256=digest, byte_length=len(raw)
    )


def _parse_source(value: object) -> ConsumedL41Source:
    source = _mapping(value, _SOURCE_KEYS, "L41_CONSUMED_EVIDENCE_SOURCE_INVALID")
    expected = {
        "branch": ACCEPTED_L41_BRANCH,
        "head": ACCEPTED_L41_HEAD,
        "tree": ACCEPTED_L41_TREE,
        "origin_feature_head": ACCEPTED_L41_HEAD,
        "origin_feature_tree": ACCEPTED_L41_TREE,
        "origin_develop_head": ACCEPTED_L41_HEAD,
        "origin_develop_tree": ACCEPTED_L41_TREE,
        "feature_authority": "PASS",
        "prospective_develop_authority": "PASS",
    }
    if source != expected:
        raise ValueError("L41_CONSUMED_EVIDENCE_SOURCE_INVALID")
    for key in ("head", "origin_feature_head", "origin_develop_head"):
        if type(source[key]) is not str or _SHA1.fullmatch(source[key]) is None:
            raise ValueError("L41_CONSUMED_EVIDENCE_SOURCE_INVALID")
    for key in ("tree", "origin_feature_tree", "origin_develop_tree"):
        if type(source[key]) is not str or _SHA1.fullmatch(source[key]) is None:
            raise ValueError("L41_CONSUMED_EVIDENCE_SOURCE_INVALID")
    return ConsumedL41Source(**source)


def _parse_facts(value: object) -> tuple[tuple[ConsumedL41Fact, ...], str]:
    if type(value) is not list or len(value) != len(FactId):
        raise ValueError("L41_CONSUMED_EVIDENCE_FACT_INVENTORY_INVALID")
    parsed: list[ConsumedL41Fact] = []
    digests: set[str] = set()
    for expected_id, item in zip(FactId, value, strict=True):
        fact = _mapping(item, _FACT_KEYS, "L41_CONSUMED_EVIDENCE_FACT_INVALID")
        if fact["fact_id"] != expected_id.value:
            raise ValueError("L41_CONSUMED_EVIDENCE_FACT_INVENTORY_INVALID")
        expected_classification = _EXPECTED_CLASSIFICATIONS.get(
            expected_id, Classification.BLOCKING_L42
        )
        if fact["classification"] != expected_classification.value:
            raise ValueError("L41_CONSUMED_EVIDENCE_FACT_INVALID")
        if fact["rationale_code"] != _EXPECTED_RATIONALES[expected_id]:
            raise ValueError("L41_CONSUMED_EVIDENCE_FACT_INVALID")
        fact_digest = fact["evidence_sha256"]
        if type(fact_digest) is not str or _SHA256.fullmatch(fact_digest) is None:
            raise ValueError("L41_CONSUMED_EVIDENCE_FACT_INVALID")
        if fact["provenance"] is not None:
            raise ValueError("L41_CONSUMED_EVIDENCE_FACT_INVALID")
        digests.add(fact_digest)
        parsed.append(
            ConsumedL41Fact(
                fact_id=expected_id,
                classification=expected_classification,
                rationale_code=_EXPECTED_RATIONALES[expected_id],
                evidence_sha256=fact_digest,
            )
        )
    if len(digests) != 1:
        raise ValueError("L41_CONSUMED_EVIDENCE_FACT_INVALID")
    return tuple(parsed), next(iter(digests))


def _parse_attempts(value: object) -> ConsumedL41Attempts:
    attempts = _mapping(value, _ATTEMPT_KEYS, "L41_CONSUMED_EVIDENCE_ATTEMPTS_INVALID")
    expected = {
        "oauth_scope_entry_attempts": 1,
        "native_credential_read_count": None,
        "credential_store_accounting": (
            "NATIVE_READS_SDK_MANAGED_NOT_INDIVIDUALLY_COUNTED"
        ),
        "mcp_session_open_attempts": 1,
        "get_accounts_attempts": 1,
        "get_equity_tradability_attempts": 1,
        "collector_invocations": 1,
        "collector_get_accounts_attempts": 1,
        "collector_get_equity_tradability_attempts": 1,
        "other_tool_attempts": 0,
        "review_equity_order_attempts": 0,
        "place_equity_order_attempts": 0,
        "cancel_equity_order_attempts": 0,
    }
    if attempts != expected:
        raise ValueError("L41_CONSUMED_EVIDENCE_ATTEMPTS_INVALID")
    for key, count in attempts.items():
        if key not in {"credential_store_accounting", "native_credential_read_count"}:
            if type(count) is not int:
                raise ValueError("L41_CONSUMED_EVIDENCE_ATTEMPTS_INVALID")
    return ConsumedL41Attempts(**attempts)


def _mapping(value: object, keys: frozenset[str], error: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(error)
    if any(type(key) is not str for key in value):
        raise ValueError(error)
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("L41_CONSUMED_EVIDENCE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result
