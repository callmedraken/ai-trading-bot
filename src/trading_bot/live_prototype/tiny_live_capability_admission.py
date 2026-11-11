"""Additive, source-owned admission for the single tiny-live prototype.

This pure adapter accepts only the preserved L41 and L41R5 artifact bytes and
the exact L41R6 composite reconstructed from them. It never changes historical
capability classifications or grants provider, order, or trade authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date
from enum import Enum, StrEnum
from typing import Final

from trading_bot.live_prototype.capability_observer import (
    CapabilityReport,
    Classification,
    FactId,
    FactResult,
    OverallStatus,
)
from trading_bot.live_prototype.capability_rule_binding_l41r6 import (
    L41R6CompositeReport,
    L41R6OfficialClaimScopeBinding,
    classify_l41r6_composite,
)
from trading_bot.live_prototype.consumed_l41_evidence import (
    ACCEPTED_L41_BRANCH,
    ACCEPTED_L41_HEAD,
    ACCEPTED_L41_TREE,
    CONSUMED_L41_EVIDENCE_BYTES,
    CONSUMED_L41_EVIDENCE_SHA256,
)
from trading_bot.live_prototype.consumed_l41r5_evidence import (
    ACCEPTED_L41R5_BRANCH,
    ACCEPTED_L41R5_HEAD,
    ACCEPTED_L41R5_TREE,
    CONSUMED_L41R5_EVIDENCE_BYTES,
    CONSUMED_L41R5_EVIDENCE_SHA256,
    L41R5FieldSemantics,
    L41R5ToolInterface,
)
from trading_bot.live_prototype.official_rule_binding import (
    OfficialClaimId,
    OfficialSourceId,
    TrustedOfficialRuleBindingV2,
    accepted_official_rule_binding_v2,
    resolve_trusted_official_claim_v2,
)
from trading_bot.live_prototype.tiny_live_policy import (
    TINY_LIVE_POLICY,
    TinyLivePolicy,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ADMISSION_SCHEMA: Final = "arch147-tiny-live-capability-admission/v1"
_ACCEPTED_L41R6_HEAD: Final = "17faef900919cf400ce77877b328418e40787842"
_ACCEPTED_L41R6_TREE: Final = "dbf4ea260b15b069a6c5d4d1c6c34627bca09a02"
_ACCEPTED_POLICY_ID: Final = "ARCH147_TINY_LIVE_SPY_SINGLE_ENTRY_V1"
_ACCEPTED_OFFICIAL_BINDING_ID: Final = "RH_L41_OFFICIAL_RULES_2026_11_10_V2"
_ACCEPTED_OFFICIAL_SOURCE_DIGESTS: Final = (
    (
        OfficialSourceId.TRADING_WITH_YOUR_AGENT.value,
        "a7789ee596168e2605ce4fbca73346f9c75ef882995df187c303d7ae7c17d980",
    ),
    (
        OfficialSourceId.FRACTIONAL_SHARES.value,
        "6735222237350f2001da457b75872647c1d4afbe86911cd1759b55f8dc86a3a3",
    ),
    (
        OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT.value,
        "26dae42562b1ef0d50e9afbb33fa6c5f3acdbbd9dc9a814e3a8e88a5f7e2dcf2",
    ),
)
_EXPECTED_FACT_MATRIX: Final = (
    (
        FactId.INTENDED_AGENTIC_ACCOUNT,
        Classification.PROVEN,
        "ACCOUNT_IDENTITY_PROVEN",
        CONSUMED_L41_EVIDENCE_SHA256,
    ),
    (
        FactId.SPY_TRADABILITY,
        Classification.PROVEN,
        "SPY_TRADABILITY_PROVEN",
        CONSUMED_L41_EVIDENCE_SHA256,
    ),
    (
        FactId.FRACTIONAL_ELIGIBILITY,
        Classification.PROVEN,
        "SPY_FRACTIONAL_ELIGIBILITY_PROVEN",
        CONSUMED_L41_EVIDENCE_SHA256,
    ),
    (
        FactId.SELL_QUANTITY_FIELD,
        Classification.PROVEN,
        "L41R6_SELL_QUANTITY_INTERFACE_PROVEN",
        CONSUMED_L41R5_EVIDENCE_SHA256,
    ),
    (
        FactId.DECIMAL_INTERFACE_PRECISION,
        Classification.PROVEN,
        "L41R6_ADVERTISED_SIX_DECIMAL_BOUND_PROVEN",
        CONSUMED_L41R5_EVIDENCE_SHA256,
    ),
    (
        FactId.QUANTITY_INCREMENT,
        Classification.BLOCKING_L42,
        "L41R6_QUANTITY_INCREMENT_UNSUPPORTED",
        None,
    ),
    (
        FactId.MINIMUM_QUANTITY,
        Classification.BLOCKING_L42,
        "L41R6_MINIMUM_QUANTITY_UNSUPPORTED",
        None,
    ),
    (
        FactId.MAXIMUM_QUANTITY_OR_ABSENCE,
        Classification.BLOCKING_L42,
        "L41R6_MAXIMUM_QUANTITY_UNSUPPORTED",
        None,
    ),
    (
        FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
        Classification.PROVEN,
        "L41R6_ORDINARY_MINIMUM_USD_1_PROVEN",
        None,
    ),
    (
        FactId.BELOW_MINIMUM_FULL_CLOSE,
        Classification.BLOCKING_L42,
        "L41R6_BELOW_MINIMUM_CLOSE_UNSUPPORTED",
        None,
    ),
    (
        FactId.RESIDUAL_FULL_OWNED_CLOSE,
        Classification.BLOCKING_L42,
        "L41R6_RESIDUAL_CLOSE_UNSUPPORTED",
        None,
    ),
    (
        FactId.REVIEW_PREVIEW_ONLY,
        Classification.PROVEN,
        "L41R6_OFFICIAL_REVIEW_PREVIEW_PROVEN",
        CONSUMED_L41R5_EVIDENCE_SHA256,
    ),
    (
        FactId.INSTANCE_REVIEW_REQUIRES_POSITION,
        Classification.DEFER_TO_FIRST_OWNED_POSITION,
        "EXACT_OWNED_POSITION_REVIEW_DEFERRED",
        CONSUMED_L41_EVIDENCE_SHA256,
    ),
)
_EXPECTED_OFFICIAL_CLAIM_BINDINGS: Final = (
    (
        FactId.MINIMUM_SELL_NOTIONAL_OR_ABSENCE,
        OfficialClaimId.ORDINARY_FRACTIONAL_TRANSACTION_MINIMUM_USD_1,
        (
            OfficialSourceId.FRACTIONAL_SHARES,
            OfficialSourceId.RHF_RHS_CUSTOMER_AGREEMENT,
        ),
    ),
    (
        FactId.REVIEW_PREVIEW_ONLY,
        OfficialClaimId.REVIEW_EQUITY_ORDER_SIMULATION_PRETRADE_WARNINGS,
        (OfficialSourceId.TRADING_WITH_YOUR_AGENT,),
    ),
)


class TinyLivePrototypeCapabilityStatus(StrEnum):
    """Prototype-specific capability admission state."""

    ELIGIBLE_FOR_TINY_LIVE_Q62 = "ELIGIBLE_FOR_TINY_LIVE_Q62"


@dataclass(frozen=True, slots=True, repr=False)
class TinyLivePrototypeCapabilityAdmission:
    """Validated prototype capability input; it grants no trading authority."""

    status: TinyLivePrototypeCapabilityStatus
    capability_report: CapabilityReport = field(repr=False)
    account_fingerprint: str = field(repr=False)
    admission_digest: str
    consumed_l41_sha256: str
    consumed_l41r5_sha256: str
    official_binding_id: str
    official_source_digests: tuple[tuple[str, str], ...]
    policy_id: str
    policy_sha256: str

    def __post_init__(self) -> None:
        _require(
            type(self.status) is TinyLivePrototypeCapabilityStatus
            and self.status
            is TinyLivePrototypeCapabilityStatus.ELIGIBLE_FOR_TINY_LIVE_Q62,
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )
        _require(
            type(self.account_fingerprint) is str
            and _SHA256.fullmatch(self.account_fingerprint) is not None,
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )
        _validate_report(self.capability_report, self.account_fingerprint)
        _require(
            type(self.admission_digest) is str
            and _SHA256.fullmatch(self.admission_digest) is not None,
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )
        _require(
            type(self.consumed_l41_sha256) is str
            and self.consumed_l41_sha256 == CONSUMED_L41_EVIDENCE_SHA256
            and type(self.consumed_l41r5_sha256) is str
            and self.consumed_l41r5_sha256 == CONSUMED_L41R5_EVIDENCE_SHA256,
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )
        _require(
            type(self.official_binding_id) is str
            and self.official_binding_id == _ACCEPTED_OFFICIAL_BINDING_ID
            and type(self.official_source_digests) is tuple
            and _strict_value_equal(
                self.official_source_digests, _ACCEPTED_OFFICIAL_SOURCE_DIGESTS
            ),
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )
        try:
            expected_policy_sha256 = TINY_LIVE_POLICY.canonical_sha256()
        except (AttributeError, TypeError, ValueError):
            raise ValueError("TINY_LIVE_CAPABILITY_ADMISSION_INVALID") from None
        _require(
            type(self.policy_id) is str
            and self.policy_id == _ACCEPTED_POLICY_ID
            and type(self.policy_sha256) is str
            and self.policy_sha256 == expected_policy_sha256
            and _SHA256.fullmatch(self.policy_sha256) is not None,
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )

    @property
    def provider_mutation_count(self) -> int:
        return 0

    @property
    def live_readiness_granted(self) -> bool:
        return False

    @property
    def trade_authority_granted(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status={self.status.value!r}, "
            f"admission_digest={self.admission_digest!r})"
        )


def admit_tiny_live_capabilities(
    composite: L41R6CompositeReport,
    *,
    consumed_l41_bytes: bytes,
    consumed_l41r5_bytes: bytes,
    account_fingerprint: str,
) -> TinyLivePrototypeCapabilityAdmission:
    """Admit only the exact accepted L41R6 result for the tiny-live prototype.

    The source-owned historical classifier reconstructs the full composite
    from both immutable evidence byte strings. The supplied typed report is
    recursively type-compared with that reconstruction before any prototype
    capability admission is returned.
    """
    _require(
        type(composite) is L41R6CompositeReport
        and type(consumed_l41_bytes) is bytes
        and type(consumed_l41r5_bytes) is bytes
        and type(account_fingerprint) is str
        and _SHA256.fullmatch(account_fingerprint) is not None,
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )
    try:
        reconstructed = classify_l41r6_composite(
            consumed_l41_bytes, consumed_l41r5_bytes
        )
        _require(
            type(reconstructed) is L41R6CompositeReport
            and _strict_value_equal(composite, reconstructed),
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )
        _validate_lineage(reconstructed, account_fingerprint)
        policy_id, policy_material, policy_sha256 = _policy_material()
        material = _admission_digest_material(
            reconstructed,
            account_fingerprint=account_fingerprint,
            policy_id=policy_id,
            policy_sha256=policy_sha256,
            policy_material=policy_material,
        )
        digest = _canonical_json_digest(material)
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ValueError("TINY_LIVE_CAPABILITY_ADMISSION_INVALID") from None

    return TinyLivePrototypeCapabilityAdmission(
        status=TinyLivePrototypeCapabilityStatus.ELIGIBLE_FOR_TINY_LIVE_Q62,
        capability_report=reconstructed.capability_report,
        account_fingerprint=account_fingerprint,
        admission_digest=digest,
        consumed_l41_sha256=reconstructed.consumed_l41.evidence_sha256,
        consumed_l41r5_sha256=reconstructed.consumed_l41r5.evidence_sha256,
        official_binding_id=_ACCEPTED_OFFICIAL_BINDING_ID,
        official_source_digests=_ACCEPTED_OFFICIAL_SOURCE_DIGESTS,
        policy_id=policy_id,
        policy_sha256=policy_sha256,
    )


def exact_l41r6_capability_report_matches(left: object, right: object) -> bool:
    """Return whether two historical capability reports match type-for-type."""
    if type(left) is not CapabilityReport or type(right) is not CapabilityReport:
        return False
    try:
        return _strict_value_equal(left, right)
    except (AttributeError, TypeError, ValueError):
        return False


def _validate_lineage(
    composite: L41R6CompositeReport, account_fingerprint: str
) -> None:
    consumed_l41 = composite.consumed_l41
    source_l41 = consumed_l41.source
    report = composite.capability_report
    _validate_report(
        report,
        account_fingerprint,
        expected_account_type=consumed_l41.account_type,
    )
    _require(
        type(consumed_l41.evidence_sha256) is str
        and consumed_l41.evidence_sha256 == CONSUMED_L41_EVIDENCE_SHA256
        and type(consumed_l41.byte_length) is int
        and consumed_l41.byte_length == CONSUMED_L41_EVIDENCE_BYTES
        and type(source_l41.branch) is str
        and source_l41.branch == ACCEPTED_L41_BRANCH
        and type(source_l41.head) is str
        and source_l41.head == ACCEPTED_L41_HEAD
        and type(source_l41.tree) is str
        and source_l41.tree == ACCEPTED_L41_TREE,
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )

    consumed_l41r5 = composite.consumed_l41r5
    _require(
        type(consumed_l41r5.evidence_sha256) is str
        and consumed_l41r5.evidence_sha256 == CONSUMED_L41R5_EVIDENCE_SHA256
        and type(consumed_l41r5.byte_length) is int
        and consumed_l41r5.byte_length == CONSUMED_L41R5_EVIDENCE_BYTES
        and type(consumed_l41r5.branch) is str
        and consumed_l41r5.branch == ACCEPTED_L41R5_BRANCH
        and type(consumed_l41r5.source_head) is str
        and consumed_l41r5.source_head == ACCEPTED_L41R5_HEAD
        and type(consumed_l41r5.source_tree) is str
        and consumed_l41r5.source_tree == ACCEPTED_L41R5_TREE,
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )

    _validate_official_binding(composite)


def _validate_report(
    report: CapabilityReport,
    account_fingerprint: str,
    *,
    expected_account_type: str | None = None,
) -> None:
    _require(
        type(report) is CapabilityReport
        and type(report.status) is OverallStatus
        and report.status is OverallStatus.BLOCKED
        and type(report.account_fingerprint) is str
        and report.account_fingerprint == account_fingerprint
        and type(report.account_type) is str
        and (
            expected_account_type is None
            or (
                type(expected_account_type) is str
                and report.account_type == expected_account_type
            )
        )
        and type(report.facts) is tuple
        and len(report.facts) == len(_EXPECTED_FACT_MATRIX),
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )
    for actual, (fact_id, classification, rationale, evidence_sha256) in zip(
        report.facts, _EXPECTED_FACT_MATRIX, strict=True
    ):
        _require(
            type(actual) is FactResult
            and type(actual.fact_id) is FactId
            and actual.fact_id is fact_id
            and type(actual.classification) is Classification
            and actual.classification is classification
            and type(actual.rationale_code) is str
            and actual.rationale_code == rationale
            and type(actual.evidence_sha256) is type(evidence_sha256)
            and actual.evidence_sha256 == evidence_sha256
            and actual.provenance is None
            and actual.submitted_rule_value is None,
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )


def _validate_official_binding(composite: L41R6CompositeReport) -> None:
    official_binding = accepted_official_rule_binding_v2()
    _require(
        type(official_binding) is TrustedOfficialRuleBindingV2
        and type(official_binding.binding_id) is str
        and official_binding.binding_id == _ACCEPTED_OFFICIAL_BINDING_ID,
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )
    source_digests = tuple(
        (source.source_id.value, source.content_sha256)
        for source in official_binding.sources
    )
    _require(
        _strict_value_equal(source_digests, _ACCEPTED_OFFICIAL_SOURCE_DIGESTS),
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )
    sources_by_id = {source.source_id: source for source in official_binding.sources}
    claims_by_id = {claim.claim_id: claim for claim in official_binding.claims}
    expected_bindings: list[L41R6OfficialClaimScopeBinding] = []
    for fact_id, claim_id, source_ids in _EXPECTED_OFFICIAL_CLAIM_BINDINGS:
        claim = claims_by_id[claim_id]
        sources = tuple(sources_by_id[source_id] for source_id in source_ids)
        source_digest_map = {
            source.source_id: source.content_sha256 for source in sources
        }
        resolved = resolve_trusted_official_claim_v2(claim_id, source_digest_map)
        _require(
            resolved is claim,
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )
        expected_bindings.append(
            L41R6OfficialClaimScopeBinding(
                fact_id=fact_id,
                claim=resolved,
                sources=sources,
            )
        )
    _require(
        _strict_value_equal(
            composite.official_claim_bindings, tuple(expected_bindings)
        ),
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )


def _policy_material() -> tuple[str, tuple[tuple[str, str | bool | int], ...], str]:
    _require(
        type(TINY_LIVE_POLICY) is TinyLivePolicy,
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )
    policy_id = TINY_LIVE_POLICY.policy_id
    raw_material = TINY_LIVE_POLICY.canonical_material()
    policy_sha256 = TINY_LIVE_POLICY.canonical_sha256()
    _require(
        type(policy_id) is str
        and policy_id == _ACCEPTED_POLICY_ID
        and type(raw_material) is tuple
        and bool(raw_material)
        and type(policy_sha256) is str
        and _SHA256.fullmatch(policy_sha256) is not None,
        "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
    )
    material: list[tuple[str, str | bool | int]] = []
    seen_keys: set[str] = set()
    for entry in raw_material:
        _require(
            type(entry) is tuple
            and len(entry) == 2
            and type(entry[0]) is str
            and entry[0] not in seen_keys
            and type(entry[1]) in {str, bool, int},
            "TINY_LIVE_CAPABILITY_ADMISSION_INVALID",
        )
        seen_keys.add(entry[0])
        material.append((entry[0], entry[1]))
    return policy_id, tuple(material), policy_sha256


def _admission_digest_material(
    composite: L41R6CompositeReport,
    *,
    account_fingerprint: str,
    policy_id: str,
    policy_sha256: str,
    policy_material: tuple[tuple[str, str | bool | int], ...],
) -> dict[str, object]:
    report = composite.capability_report
    official_claims = [
        {
            "fact_id": binding.fact_id.value,
            "claim_id": binding.claim.claim_id.value,
            "sources": [
                [source.source_id.value, source.content_sha256]
                for source in binding.sources
            ],
        }
        for binding in composite.official_claim_bindings
    ]
    interface_records = [
        {
            "fact_id": provenance.fact_id.value,
            "evidence_sha256": provenance.evidence_sha256,
            "source_head": provenance.source_head,
            "source_tree": provenance.source_tree,
            "scope_code": provenance.scope_code,
            "tool_interfaces": [
                _tool_interface_material(interface)
                for interface in provenance.tool_interfaces
            ],
        }
        for provenance in composite.interface_provenance
    ]
    facts = [
        [
            item.fact_id.value,
            item.classification.value,
            item.rationale_code,
            item.evidence_sha256,
        ]
        for item in report.facts
    ]
    return {
        "schema": _ADMISSION_SCHEMA,
        "accepted_l41r6_source": {
            "head": _ACCEPTED_L41R6_HEAD,
            "tree": _ACCEPTED_L41R6_TREE,
        },
        "consumed_l41": {
            "sha256": composite.consumed_l41.evidence_sha256,
            "byte_length": composite.consumed_l41.byte_length,
            "source_head": composite.consumed_l41.source.head,
            "source_tree": composite.consumed_l41.source.tree,
        },
        "consumed_l41r5": {
            "sha256": composite.consumed_l41r5.evidence_sha256,
            "byte_length": composite.consumed_l41r5.byte_length,
            "source_head": composite.consumed_l41r5.source_head,
            "source_tree": composite.consumed_l41r5.source_tree,
        },
        "account": {
            "fingerprint": account_fingerprint,
            "type": report.account_type,
        },
        "official_binding": {
            "binding_id": _ACCEPTED_OFFICIAL_BINDING_ID,
            "source_digests": [
                list(item) for item in _ACCEPTED_OFFICIAL_SOURCE_DIGESTS
            ],
            "claims": official_claims,
        },
        "interface_provenance": interface_records,
        "fact_matrix": facts,
        "policy": {
            "policy_id": policy_id,
            "canonical_sha256": policy_sha256,
            "material": [list(item) for item in policy_material],
        },
        "authority": {
            "provider_mutation_count": 0,
            "live_readiness_granted": False,
            "trade_authority_granted": False,
        },
    }


def _tool_interface_material(interface: L41R5ToolInterface) -> dict[str, object]:
    return {
        "tool_name": interface.tool_name,
        "interface_sha256": interface.interface_sha256,
        "additional_properties_present": interface.additional_properties_present,
        "additional_properties_form": interface.additional_properties_form,
        "quantity": _field_material(interface.quantity),
        "dollar_amount": _field_material(interface.dollar_amount),
        "fractional_precision_decimal_places": list(
            interface.fractional_precision_decimal_places
        ),
        "fractional_precision_conflict": interface.fractional_precision_conflict,
    }


def _field_material(
    semantics: L41R5FieldSemantics | None,
) -> list[bool | str | None] | None:
    if semantics is None:
        return None
    return [
        semantics.present,
        semantics.direct_type,
        semantics.logical_non_null_type,
        semantics.required,
        semantics.nullable,
    ]


def _canonical_json_digest(material: object) -> str:
    try:
        encoded = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise ValueError("TINY_LIVE_CAPABILITY_ADMISSION_INVALID") from None
    return hashlib.sha256(encoded).hexdigest()


def _strict_value_equal(left: object, right: object) -> bool:
    """Compare accepted composite shapes without Python value aliases."""
    if type(left) is not type(right):
        return False
    if left is None:
        return True
    if isinstance(left, Enum):
        return left is right
    if is_dataclass(left) and not isinstance(left, type):
        try:
            return all(
                _strict_value_equal(getattr(left, item.name), getattr(right, item.name))
                for item in fields(left)
            )
        except (AttributeError, TypeError, ValueError):
            return False
    if type(left) is tuple:
        return len(left) == len(right) and all(
            _strict_value_equal(l_item, r_item)
            for l_item, r_item in zip(left, right, strict=True)
        )
    if type(left) is date:
        return left == right
    if type(left) in {str, int, bool}:
        return left == right
    return False


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)
