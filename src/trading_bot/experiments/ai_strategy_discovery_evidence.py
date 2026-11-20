"""Canonical Generation-0 evidence and bounded campaign foundation artifact.

This module is a read-only evidence boundary. It accepts only explicit paths,
uses existing public A147/A148 parsers, and grants no evaluation or lifecycle
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from trading_bot.experiments.ai_strategy_discovery import (
    CAMPAIGN_VERSION,
    GENERATION_1_MAX_EVALUATED,
    GENERATION_2_MAX_EVALUATED,
    DiscoveryError,
    TrialLedger,
)
from trading_bot.experiments.arch148_churn_research import (
    Arch148ChurnResearchError,
    ChurnResearchReport,
)
from trading_bot.experiments.filtered_trend_bundle import (
    MAX_BUNDLE_BYTES,
    ResearchBundle,
)
from trading_bot.experiments.filtered_trend_campaign import decimal_text
from trading_bot.experiments.historical_research_custody import (
    canonical_json_bytes,
)

FOUNDATION_SCHEMA = "ai-strategy-discovery-foundation/v1"
INVENTORY_SCHEMA = "ai-strategy-discovery-generation0-inventory/v1"
MAX_FOUNDATION_BYTES = 8 * 1024 * 1024
MAX_CHURN_REPORT_BYTES = 4 * 1024 * 1024
MAX_SUMMARY_BYTES = 4 * 1024 * 1024
MAX_TEXT_LENGTH = 2048
MAX_SYNTHESIS_ITEMS = 128
AUTHORITY = "RESEARCH_ONLY; NO_LIFECYCLE_AUTHORITY; NO_TRADING_AUTHORITY"

_GIT_ID = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
_IDENTITY_NAMESPACE = UUID("7be70f93-94c5-5e52-89ba-28944c620cb3")
_INVENTORY_IDENTITY_VERSION = "ai-strategy-discovery-generation0-identity/v1"
_FOUNDATION_IDENTITY_VERSION = "ai-strategy-discovery-foundation-identity/v1"

# These are immutable evidence identities from the accepted validation record.
# The file itself is never resolved or opened unless the caller supplies a path.
_A148_CHURN_IDENTITY = "19dcca18-7080-541d-9864-d730c68471e0"
_A148_CHURN_SHA256 = "5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8"
_A148_CHURN_SOURCE_HEAD = "be30617594e197f372438dba19d325fd8737b850"
_A148_CHURN_SOURCE_TREE = "57d5e80bd1933d59faf5da07f0ea293eac34b323"

_EFFECT_COUNTERS = (
    "AI_SERVICE_CALLS",
    "CREDENTIAL_READS",
    "PROVIDER_CALLS",
    "ROBINHOOD_CALLS",
    "BROKER_CALLS",
    "ORDER_EFFECTS",
    "PRODUCTION_STATE_READS",
    "PRODUCTION_STATE_WRITES",
    "FINAL_HOLDOUT_ACCESSES",
    "STRATEGY_PROMOTIONS",
)
_REFERENCE_ORDER = (
    "arch147-filtered-trend-multi-asset",
    "arch148-churn-research",
    "arch148-bullish-band-session-reference",
    "arch148-late-session-momentum-design",
    "prior-canonical-research",
)


def _discovery_error(code: str) -> ValueError:
    return DiscoveryError(code)


class EvidenceStatus(StrEnum):
    CANONICAL_ACCEPTED = "CANONICAL_ACCEPTED"
    CANONICAL_REJECTED = "CANONICAL_REJECTED"
    QUEUED_UNEVALUATED = "QUEUED_UNEVALUATED"
    NONCANONICAL_SESSION_EVIDENCE = "NONCANONICAL_SESSION_EVIDENCE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class MetricEvidence:
    name: str
    value: str
    scope: str

    def __post_init__(self) -> None:
        _require_text(self.name)
        _require_text(self.value)
        _require_text(self.scope)

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "scope": self.scope, "value": self.value}

    @classmethod
    def from_dict(cls, raw: object) -> MetricEvidence:
        row = _exact_object(raw, {"name", "scope", "value"})
        return cls(row["name"], row["value"], row["scope"])


@dataclass(frozen=True, slots=True)
class EvidenceSynthesis:
    family: str
    tested_semantics: tuple[str, ...]
    dataset: str
    universe: tuple[str, ...]
    timeframe: str
    periods: tuple[str, ...]
    cost_cases: tuple[str, ...]
    metrics: tuple[MetricEvidence, ...]
    breadth: tuple[str, ...]
    failure_mode: str
    unanswered_questions: tuple[str, ...]
    canonical_summary_json: str | None = None

    def __post_init__(self) -> None:
        for value in (self.family, self.dataset, self.timeframe, self.failure_mode):
            _require_text(value)
        for values in (
            self.tested_semantics,
            self.universe,
            self.periods,
            self.cost_cases,
            self.breadth,
            self.unanswered_questions,
        ):
            _require_text_tuple(values)
        if type(self.metrics) is not tuple or len(self.metrics) > MAX_SYNTHESIS_ITEMS:
            raise _discovery_error("GENERATION0_SYNTHESIS_INVALID")
        if any(type(item) is not MetricEvidence for item in self.metrics):
            raise _discovery_error("GENERATION0_SYNTHESIS_INVALID")
        if self.canonical_summary_json is not None:
            _validate_canonical_summary(self.canonical_summary_json)

    def to_dict(self) -> dict[str, object]:
        return {
            "breadth": list(self.breadth),
            "canonical_summary_json": self.canonical_summary_json,
            "cost_cases": list(self.cost_cases),
            "dataset": self.dataset,
            "failure_mode": self.failure_mode,
            "family": self.family,
            "metrics": [item.to_dict() for item in self.metrics],
            "periods": list(self.periods),
            "test_semantics": list(self.tested_semantics),
            "timeframe": self.timeframe,
            "unanswered_questions": list(self.unanswered_questions),
            "universe": list(self.universe),
        }

    @classmethod
    def from_dict(cls, raw: object) -> EvidenceSynthesis:
        row = _exact_object(
            raw,
            {
                "family",
                "test_semantics",
                "dataset",
                "universe",
                "timeframe",
                "periods",
                "cost_cases",
                "metrics",
                "breadth",
                "failure_mode",
                "unanswered_questions",
                "canonical_summary_json",
            },
        )
        for name in (
            "test_semantics",
            "universe",
            "periods",
            "cost_cases",
            "metrics",
            "breadth",
            "unanswered_questions",
        ):
            if type(row[name]) is not list:
                raise _discovery_error("GENERATION0_SYNTHESIS_INVALID")
        return cls(
            family=row["family"],
            tested_semantics=tuple(row["test_semantics"]),
            dataset=row["dataset"],
            universe=tuple(row["universe"]),
            timeframe=row["timeframe"],
            periods=tuple(row["periods"]),
            cost_cases=tuple(row["cost_cases"]),
            metrics=tuple(MetricEvidence.from_dict(item) for item in row["metrics"]),
            breadth=tuple(row["breadth"]),
            failure_mode=row["failure_mode"],
            unanswered_questions=tuple(row["unanswered_questions"]),
            canonical_summary_json=row["canonical_summary_json"],
        )


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    reference_id: str
    label: str
    status: EvidenceStatus
    verification: str
    artifact_identity: str | None
    artifact_sha256: str | None
    source_head: str | None
    source_tree: str | None
    synthesis: EvidenceSynthesis
    review_reference: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.reference_id)
        _require_text(self.label)
        if type(self.status) is not EvidenceStatus:
            raise _discovery_error("GENERATION0_STATUS_INVALID")
        _require_text(self.verification)
        for value in (
            self.artifact_identity,
            self.artifact_sha256,
            self.source_head,
            self.source_tree,
        ):
            if value is not None:
                _require_text(value)
        if type(self.synthesis) is not EvidenceSynthesis:
            raise _discovery_error("GENERATION0_SYNTHESIS_INVALID")
        if self.review_reference is not None:
            _require_text(self.review_reference)
        allowed = {
            "arch147-filtered-trend-multi-asset": {
                EvidenceStatus.CANONICAL_ACCEPTED,
                EvidenceStatus.UNAVAILABLE,
            },
            "arch148-churn-research": {
                EvidenceStatus.CANONICAL_REJECTED,
                EvidenceStatus.UNAVAILABLE,
            },
            "arch148-bullish-band-session-reference": {
                EvidenceStatus.NONCANONICAL_SESSION_EVIDENCE,
            },
            "arch148-late-session-momentum-design": {
                EvidenceStatus.QUEUED_UNEVALUATED,
            },
            "prior-canonical-research": {EvidenceStatus.UNAVAILABLE},
        }
        if (
            self.reference_id not in allowed
            or self.status not in allowed[self.reference_id]
        ):
            raise _discovery_error("GENERATION0_STATUS_REFERENCE_MISMATCH")
        binding = (
            self.artifact_identity,
            self.artifact_sha256,
            self.source_head,
            self.source_tree,
        )
        if any(value is not None for value in binding) and any(
            value is None for value in binding
        ):
            raise _discovery_error("GENERATION0_BINDING_INCOMPLETE")
        if self.artifact_identity is not None:
            _require_uuid(self.artifact_identity)
            _require_digest(self.artifact_sha256)
            _require_git_id(self.source_head)
            _require_git_id(self.source_tree)
        canonical_status = self.status in (
            EvidenceStatus.CANONICAL_ACCEPTED,
            EvidenceStatus.CANONICAL_REJECTED,
        )
        if canonical_status != (self.verification == "VERIFIED_EXACT_BINDING"):
            raise _discovery_error("GENERATION0_CANONICAL_EVIDENCE_UNVERIFIED")
        if canonical_status and any(value is None for value in binding):
            raise _discovery_error("GENERATION0_CANONICAL_BINDING_REQUIRED")
        if canonical_status and self.review_reference is None:
            raise _discovery_error("GENERATION0_REVIEW_REFERENCE_REQUIRED")
        if (
            self.reference_id == "arch148-churn-research"
            and self.status is EvidenceStatus.CANONICAL_REJECTED
            and binding
            != (
                _A148_CHURN_IDENTITY,
                _A148_CHURN_SHA256,
                _A148_CHURN_SOURCE_HEAD,
                _A148_CHURN_SOURCE_TREE,
            )
        ):
            raise _discovery_error("A148_CHURN_ACCEPTANCE_BINDING_MISMATCH")
        expected_verification = {
            EvidenceStatus.NONCANONICAL_SESSION_EVIDENCE: (
                "SOURCE_LABEL_ONLY_NO_CANONICAL_ARTIFACT_READ"
            ),
            EvidenceStatus.QUEUED_UNEVALUATED: "DESIGN_ONLY_NO_RESULT_ARTIFACT",
        }
        if (
            self.status in expected_verification
            and self.verification != expected_verification[self.status]
        ):
            raise _discovery_error("GENERATION0_VERIFICATION_STATUS_MISMATCH")

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_identity": self.artifact_identity,
            "artifact_sha256": self.artifact_sha256,
            "label": self.label,
            "reference_id": self.reference_id,
            "source_head": self.source_head,
            "source_tree": self.source_tree,
            "status": self.status.value,
            "synthesis": self.synthesis.to_dict(),
            "verification": self.verification,
            "review_reference": self.review_reference,
        }

    @classmethod
    def from_dict(cls, raw: object) -> EvidenceReference:
        row = _exact_object(
            raw,
            {
                "reference_id",
                "label",
                "status",
                "verification",
                "artifact_identity",
                "artifact_sha256",
                "source_head",
                "source_tree",
                "synthesis",
                "review_reference",
            },
        )
        try:
            status = EvidenceStatus(row["status"])
        except (TypeError, ValueError):
            raise _discovery_error("GENERATION0_STATUS_INVALID") from None
        return cls(
            row["reference_id"],
            row["label"],
            status,
            row["verification"],
            row["artifact_identity"],
            row["artifact_sha256"],
            row["source_head"],
            row["source_tree"],
            EvidenceSynthesis.from_dict(row["synthesis"]),
            row["review_reference"],
        )


@dataclass(frozen=True, slots=True)
class ReviewedA147Binding:
    """Caller-supplied exact A147 acceptance tuple reviewed outside this module."""

    bundle_identity: str
    sha256: str
    source_head: str
    source_tree: str
    review_reference: str

    def __post_init__(self) -> None:
        _require_uuid(self.bundle_identity)
        _require_digest(self.sha256)
        _require_git_id(self.source_head)
        _require_git_id(self.source_tree)
        _require_text(self.review_reference)


@dataclass(frozen=True, slots=True)
class Generation0Inventory:
    references: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if type(self.references) is not tuple or any(
            type(item) is not EvidenceReference for item in self.references
        ):
            raise _discovery_error("GENERATION0_INVENTORY_INVALID")
        if tuple(item.reference_id for item in self.references) != _REFERENCE_ORDER:
            raise _discovery_error("GENERATION0_INVENTORY_ORDER_INVALID")

    @property
    def identity(self) -> str:
        return _identity(
            _INVENTORY_IDENTITY_VERSION, self.to_dict(include_identity=False)
        )

    def to_dict(self, *, include_identity: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "references": [item.to_dict() for item in self.references],
            "schema": INVENTORY_SCHEMA,
        }
        if include_identity:
            value["identity"] = self.identity
        return value

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_dict(cls, raw: object) -> Generation0Inventory:
        row = _exact_object(raw, {"schema", "identity", "references"})
        if row["schema"] != INVENTORY_SCHEMA or type(row["references"]) is not list:
            raise _discovery_error("GENERATION0_INVENTORY_INVALID")
        inventory = cls(
            tuple(EvidenceReference.from_dict(item) for item in row["references"])
        )
        if row["identity"] != inventory.identity:
            raise _discovery_error("GENERATION0_IDENTITY_MISMATCH")
        return inventory

    @classmethod
    def from_bytes(cls, body: bytes) -> Generation0Inventory:
        raw = _parse_canonical_object(
            body, MAX_FOUNDATION_BYTES, "GENERATION0_JSON_INVALID"
        )
        inventory = cls.from_dict(raw)
        if inventory.to_bytes() != body:
            raise _discovery_error("GENERATION0_JSON_NOT_CANONICAL")
        return inventory


def _a147_unavailable(
    binding: ReviewedA147Binding | None = None,
    *,
    verification: str = "NO_EXACT_ACCEPTED_BUNDLE_BINDING_OR_PATH_SUPPLIED",
) -> EvidenceReference:
    return EvidenceReference(
        reference_id="arch147-filtered-trend-multi-asset",
        label="Architecture 147 filtered-trend multi-asset research",
        status=EvidenceStatus.UNAVAILABLE,
        verification=verification,
        artifact_identity=None if binding is None else binding.bundle_identity,
        artifact_sha256=None if binding is None else binding.sha256,
        source_head=None if binding is None else binding.source_head,
        source_tree=None if binding is None else binding.source_tree,
        synthesis=EvidenceSynthesis(
            family="FILTERED_TREND_MULTI_ASSET",
            tested_semantics=(
                "Frozen filtered-trend daily strategy grid; existing A147 rules only.",
                "Accepted source reader is required; no strategy replay is permitted.",
            ),
            dataset="ALPACA_ALL_ADJUSTED_PRICE_V1; daily adjusted-price series",
            universe=("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "PDBC"),
            timeframe="1Day",
            periods=(
                "A147 report's exact evaluated periods are unavailable until "
                "its bundle is bound.",
            ),
            cost_cases=("base: $1 per fill + 5 bps", "stress: $2 per fill + 10 bps"),
            metrics=(),
            breadth=(),
            failure_mode=(
                "Exact accepted bundle identity, digest and source binding are "
                "absent from the bounded current docs."
            ),
            unanswered_questions=(
                "No accepted bundle identity/hash/source tuple was supplied.",
                "Returns, drawdown, turnover and cross-asset/year breadth are not "
                "imported until the bundle is verified.",
            ),
        ),
        review_reference=None if binding is None else binding.review_reference,
    )


def _a148_churn_unavailable() -> EvidenceReference:
    return EvidenceReference(
        reference_id="arch148-churn-research",
        label="Architecture 148 accepted OPEN churn study",
        status=EvidenceStatus.UNAVAILABLE,
        verification="PINNED_ACCEPTANCE_TUPLE_KNOWN_BUT_NO_EXPLICIT_PATH_SUPPLIED",
        artifact_identity=_A148_CHURN_IDENTITY,
        artifact_sha256=_A148_CHURN_SHA256,
        source_head=_A148_CHURN_SOURCE_HEAD,
        source_tree=_A148_CHURN_SOURCE_TREE,
        synthesis=_a148_churn_synthesis(),
        review_reference="docs/validation/arch148-churn-research.md",
    )


def _a148_churn_synthesis(
    canonical_summary_json: str | None = None,
) -> EvidenceSynthesis:
    return EvidenceSynthesis(
        family="SPARSE_INTRADAY_REGIME_EXIT_CHURN",
        tested_semantics=(
            "CONTROL baseline; opposite-regime confirmation; 15-minute and "
            "30-minute session-local cooldowns.",
            "Accepted sparse OPEN simulator, stop, forced-flat and missing-bar "
            "semantics retained.",
        ),
        dataset="Accepted sparse ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1 OPEN data",
        universe=("QQQ", "TQQQ", "SQQQ"),
        timeframe="5-minute sparse intraday",
        periods=("OPEN_FULL 2016-2023", *(str(year) for year in range(2016, 2024))),
        cost_cases=("ZERO_COST", "CONSERVATIVE_10_BPS"),
        metrics=(
            MetricEvidence(
                "baseline_trades", "6233 zero-cost; 6235 conservative", "OPEN_FULL"
            ),
            MetricEvidence(
                "baseline_regime_exits",
                "5446 zero-cost; 5439 conservative",
                "OPEN_FULL",
            ),
            MetricEvidence("baseline_conservative_return", "-99.998648%", "OPEN_FULL"),
            MetricEvidence(
                "opposite_confirmation",
                "3172 trades; approximately -99.5971%",
                "OPEN_FULL conservative",
            ),
            MetricEvidence(
                "cooldown_15m",
                "3067 trades; approximately -99.5245%",
                "OPEN_FULL conservative",
            ),
            MetricEvidence(
                "cooldown_30m",
                "2970 trades; approximately -99.4027%",
                "OPEN_FULL conservative",
            ),
        ),
        breadth=(
            "All four variants lost in every 2016-2023 conservative calendar-year "
            "slice.",
            "Descriptive order: 30-minute cooldown, 15-minute cooldown, opposite "
            "confirmation, CONTROL.",
        ),
        failure_mode=(
            "Churn reduction did not repair conservative-cost economics; no "
            "strategy was selected."
        ),
        unanswered_questions=(
            "No variant is promoted or selected.",
            "The year partitions are OPEN reporting slices, not a pristine holdout.",
            "FINAL_HOLDOUT remains sealed.",
        ),
        canonical_summary_json=canonical_summary_json,
    )


def _session_audit_reference() -> EvidenceReference:
    return EvidenceReference(
        reference_id="arch148-bullish-band-session-reference",
        label="Session-supplied QQQ/TQQQ bullish-band audit reference",
        status=EvidenceStatus.NONCANONICAL_SESSION_EVIDENCE,
        verification="SOURCE_LABEL_ONLY_NO_CANONICAL_ARTIFACT_READ",
        artifact_identity=None,
        artifact_sha256=None,
        source_head=None,
        source_tree=None,
        synthesis=EvidenceSynthesis(
            family="UNCLASSIFIED_SESSION_REFERENCE",
            tested_semantics=(
                "Noncanonical session evidence label retained for later review.",
            ),
            dataset=(
                "Session-supplied reference; no repository artifact binding supplied"
            ),
            universe=("QQQ", "TQQQ"),
            timeframe="unspecified",
            periods=(),
            cost_cases=(),
            metrics=(),
            breadth=(),
            failure_mode="Not verified as canonical research evidence.",
            unanswered_questions=(
                "Exact artifact provenance, data identity and evaluation semantics "
                "remain unbound.",
                "No acceptance, rejection or timestamp-validity conclusion is "
                "asserted here.",
            ),
        ),
    )


def _intraday_design_reference() -> EvidenceReference:
    return EvidenceReference(
        reference_id="arch148-late-session-momentum-design",
        label="Architecture 148 late-session intraday momentum frozen design",
        status=EvidenceStatus.QUEUED_UNEVALUATED,
        verification="DESIGN_ONLY_NO_RESULT_ARTIFACT",
        artifact_identity=None,
        artifact_sha256=None,
        source_head=None,
        source_tree=None,
        synthesis=EvidenceSynthesis(
            family="OPENING_DRIVE_LATE_CAPTURE_V1",
            tested_semantics=(
                "One opening-drive direction; one close-relative entry; one "
                "session-local position; mandatory safety and forced-flat exits.",
                "No result is present in the frozen design.",
            ),
            dataset="Accepted sparse Architecture 148 OPEN data is the proposed input",
            universe=("QQQ", "TQQQ", "SQQQ"),
            timeframe="5-minute sparse intraday",
            periods=("OPEN_FULL 2016-2023", *(str(year) for year in range(2016, 2024))),
            cost_cases=("ZERO_COST", "CONSERVATIVE_10_BPS"),
            metrics=(),
            breadth=(),
            failure_mode="Queued design only; it has not been evaluated.",
            unanswered_questions=(
                "No performance, breadth or failure evidence exists yet.",
                "The source-only foundation must not run this design.",
            ),
        ),
    )


def _prior_research_unavailable() -> EvidenceReference:
    return EvidenceReference(
        reference_id="prior-canonical-research",
        label=(
            "Prior canonical experiment, ranking, Pareto, walk-forward and "
            "candidate evidence"
        ),
        status=EvidenceStatus.UNAVAILABLE,
        verification="NO_EXACT_SOURCE_OWNED_REFERENCE_SUPPLIED",
        artifact_identity=None,
        artifact_sha256=None,
        source_head=None,
        source_tree=None,
        synthesis=EvidenceSynthesis(
            family="MIXED_CANONICAL_RESEARCH",
            tested_semantics=(
                "Existing repository readers remain authoritative when exact "
                "references are supplied.",
            ),
            dataset="Not specified by a single bound reference",
            universe=(),
            timeframe="unspecified",
            periods=(),
            cost_cases=(),
            metrics=(),
            breadth=(),
            failure_mode=(
                "No exact source-owned evidence reference supplied to this inventory."
            ),
            unanswered_questions=(
                "Which immutable prior reports belong in this campaign inventory "
                "remains unresolved.",
            ),
        ),
    )


def build_generation0_inventory(
    *,
    a147_path: Path | None = None,
    a147_binding: ReviewedA147Binding | None = None,
    a148_churn_path: Path | None = None,
) -> Generation0Inventory:
    """Build the fixed inventory from explicit reviewed paths only.

    Inputs must be independently reviewed OPEN artifacts or synthetic fixtures.
    A checksum authenticates contents after reading; it cannot authorize opening
    an arbitrary path. No default path is resolved.
    """

    for candidate_path in (a147_path, a148_churn_path):
        if candidate_path is not None:
            _reject_final_holdout_path(candidate_path)

    if a147_path is None:
        a147 = _a147_unavailable()
    elif a147_binding is None:
        a147 = _a147_unavailable(
            verification="NO_REVIEWED_ACCEPTANCE_BINDING; PATH_NOT_OPENED"
        )
    else:
        try:
            a147 = _verify_a147_bundle(a147_path, a147_binding)
        except DiscoveryError as exc:
            if str(exc) == "EVIDENCE_PATH_UNAVAILABLE":
                a147 = _a147_unavailable(
                    a147_binding,
                    verification="REVIEWED_BINDING_SUPPLIED_BUT_ARTIFACT_NOT_PRESENT",
                )
            else:
                raise

    if a148_churn_path is None:
        a148 = _a148_churn_unavailable()
    else:
        try:
            a148 = _verify_a148_churn_report(a148_churn_path)
        except DiscoveryError as exc:
            if str(exc) == "EVIDENCE_PATH_UNAVAILABLE":
                a148 = _a148_churn_unavailable()
            else:
                raise
    return Generation0Inventory(
        (
            a147,
            a148,
            _session_audit_reference(),
            _intraday_design_reference(),
            _prior_research_unavailable(),
        )
    )


def _verify_a147_bundle(
    path: Path, binding: ReviewedA147Binding | None
) -> EvidenceReference:
    if type(binding) is not ReviewedA147Binding:
        raise _discovery_error("A147_REVIEWED_BINDING_REQUIRED")
    body = _read_explicit_file(path, MAX_BUNDLE_BYTES)
    digest = hashlib.sha256(body).hexdigest()
    if digest != binding.sha256:
        raise _discovery_error("A147_ACCEPTANCE_BINDING_MISMATCH")
    try:
        bundle = ResearchBundle.from_bytes(body)
    except (ValueError, TypeError, KeyError, RecursionError):
        raise _discovery_error("A147_BUNDLE_INVALID") from None
    context = bundle.context
    source_head = context.get("source_head")
    source_tree = context.get("source_tree")
    if (
        bundle.bundle_id != binding.bundle_identity
        or digest != binding.sha256
        or source_head != binding.source_head
        or source_tree != binding.source_tree
    ):
        raise _discovery_error("A147_ACCEPTANCE_BINDING_MISMATCH")
    return EvidenceReference(
        reference_id="arch147-filtered-trend-multi-asset",
        label="Architecture 147 filtered-trend multi-asset research",
        status=EvidenceStatus.CANONICAL_ACCEPTED,
        verification="VERIFIED_EXACT_BINDING",
        artifact_identity=bundle.bundle_id,
        artifact_sha256=digest,
        source_head=source_head,
        source_tree=source_tree,
        synthesis=_a147_synthesis(bundle),
        review_reference=binding.review_reference,
    )


def _a147_synthesis(bundle: ResearchBundle) -> EvidenceSynthesis:
    context = bundle.context
    provenance = context["dataset_provenance"]
    summary_json = canonical_json_bytes(
        {
            "candidate_aggregates": [_json_plain(item) for item in bundle.summaries],
            "schema": "arch147-generation0-synthesis/v1",
            "symbol_regime_cells": [
                {
                    "atr": _json_plain(cell.atr),
                    "base": _metric_projection(cell.base),
                    "buy_and_hold": _metric_projection(cell.buy_and_hold),
                    "buy_and_hold_stress": _metric_projection(cell.buy_and_hold_stress),
                    "candidate_id": cell.candidate_id,
                    "first_session": cell.first_session,
                    "last_session": cell.last_session,
                    "regime": cell.regime,
                    "result_id": cell.result_id,
                    "session_count": cell.session_count,
                    "stress": _metric_projection(cell.stress),
                    "symbol": cell.symbol,
                }
                for cell in bundle.cells
            ],
        }
    ).decode("utf-8")
    periods = tuple(
        f"{label}: {start} .. {end}" for label, start, end in context["regimes"]
    )
    return EvidenceSynthesis(
        family="FILTERED_TREND_MULTI_ASSET",
        tested_semantics=(
            "Frozen filtered-trend configuration grid and existing entry/exit "
            "semantics.",
            "The bundle's tested configurations and aggregate metrics are "
            "retained per candidate below.",
        ),
        dataset=f"{context['price_basis']}; dataset {context['dataset_id']}",
        universe=tuple(row["symbol"] for row in provenance),
        timeframe="1Day",
        periods=("input interval [2016-01-01, 2024-01-01)", *periods),
        cost_cases=("base: $1 per fill + 5 bps", "stress: $2 per fill + 10 bps"),
        metrics=(),
        breadth=(
            "Aggregate positive/negative regime-cell and continuous-symbol "
            "counts are preserved per candidate.",
        ),
        failure_mode=(
            "Descriptive A147 outcomes; this inventory applies no winner rule."
        ),
        unanswered_questions=(
            "A147 evidence is not a pristine holdout; prior OPEN exposure remains "
            "relevant.",
            "No campaign selection or lifecycle transition is authorized by "
            "these metrics.",
        ),
        canonical_summary_json=summary_json,
    )


def _metric_projection(value: Any) -> dict[str, object]:
    return {
        "closed_trades": value.closed_trades,
        "equity_trace_identity": value.equity_trace_identity,
        "fill_count": value.fill_count,
        "maximum_drawdown": decimal_text(value.maximum_drawdown),
        "realized_profit_loss": decimal_text(value.realized_profit_loss),
        "time_invested": decimal_text(value.time_invested),
        "total_return": decimal_text(value.total_return),
        "turnover": decimal_text(value.turnover),
    }


def _verify_a148_churn_report(path: Path) -> EvidenceReference:
    body = _read_explicit_file(path, MAX_CHURN_REPORT_BYTES)
    digest = hashlib.sha256(body).hexdigest()
    if digest != _A148_CHURN_SHA256:
        raise _discovery_error("A148_CHURN_ACCEPTANCE_BINDING_MISMATCH")
    try:
        report = ChurnResearchReport.from_json(body)
        document = report.to_dict()
    except (
        Arch148ChurnResearchError,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
    ):
        raise _discovery_error("A148_CHURN_REPORT_INVALID") from None
    source = document.get("source")
    if (
        report.identity != _A148_CHURN_IDENTITY
        or digest != _A148_CHURN_SHA256
        or type(source) is not dict
        or source.get("candidate_head") != _A148_CHURN_SOURCE_HEAD
        or source.get("candidate_tree") != _A148_CHURN_SOURCE_TREE
    ):
        raise _discovery_error("A148_CHURN_ACCEPTANCE_BINDING_MISMATCH")
    summary_fields = (
        "source",
        "input",
        "scope",
        "accepted_baseline",
        "variant_definitions",
        "cost_models",
        "partitions",
        "equity_mark_timestamp_semantics",
        "runs",
        "descriptive_ranking",
        "selection",
        "effects",
    )
    summary_json = canonical_json_bytes(
        {name: document[name] for name in summary_fields}
    ).decode("utf-8")
    return EvidenceReference(
        reference_id="arch148-churn-research",
        label="Architecture 148 accepted OPEN churn study",
        status=EvidenceStatus.CANONICAL_REJECTED,
        verification="VERIFIED_EXACT_BINDING",
        artifact_identity=report.identity,
        artifact_sha256=digest,
        source_head=_A148_CHURN_SOURCE_HEAD,
        source_tree=_A148_CHURN_SOURCE_TREE,
        synthesis=_a148_churn_synthesis(summary_json),
        review_reference="docs/validation/arch148-churn-research.md",
    )


@dataclass(frozen=True, slots=True)
class CampaignFoundation:
    source_head: str
    source_tree: str
    generation0: Generation0Inventory
    trial_ledger: TrialLedger

    def __post_init__(self) -> None:
        _require_git_id(self.source_head)
        _require_git_id(self.source_tree)
        if type(self.generation0) is not Generation0Inventory:
            raise _discovery_error("CAMPAIGN_FOUNDATION_INVENTORY_INVALID")
        if type(self.trial_ledger) is not TrialLedger:
            raise _discovery_error("CAMPAIGN_FOUNDATION_LEDGER_INVALID")
        _ledger_payload(self.trial_ledger)
        _require_nonnegative_int(self.trial_ledger.evaluated_trial_count)
        counts = self.trial_ledger.evaluated_trial_counts_by_generation
        if (
            type(counts) is not tuple
            or len(counts) != 2
            or any(type(count) is not int or count < 0 for count in counts)
            or counts[0] > GENERATION_1_MAX_EVALUATED
            or counts[1] > GENERATION_2_MAX_EVALUATED
        ):
            raise _discovery_error("CAMPAIGN_FOUNDATION_TRIAL_BUDGET_EXCEEDED")

    @property
    def evaluated_trial_count(self) -> int:
        return self.trial_ledger.evaluated_trial_count

    @property
    def identity(self) -> str:
        return _identity(
            _FOUNDATION_IDENTITY_VERSION, self.to_dict(include_identity=False)
        )

    def to_dict(self, *, include_identity: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "authority": AUTHORITY,
            "budgets": {
                "generation_1_max_evaluated": GENERATION_1_MAX_EVALUATED,
                "generation_2_max_evaluated": GENERATION_2_MAX_EVALUATED,
            },
            "campaign_version": CAMPAIGN_VERSION,
            "effects": {name: 0 for name in _EFFECT_COUNTERS},
            "evaluated_trial_count": self.evaluated_trial_count,
            "final_holdout_sealed": True,
            "generation0": self.generation0.to_dict(),
            "schema": FOUNDATION_SCHEMA,
            "source": {"head": self.source_head, "tree": self.source_tree},
            "trial_ledger": _ledger_payload(self.trial_ledger),
        }
        if include_identity:
            payload["identity"] = self.identity
        return payload

    def to_bytes(self) -> bytes:
        body = canonical_json_bytes(self.to_dict())
        if len(body) > MAX_FOUNDATION_BYTES:
            raise _discovery_error("CAMPAIGN_FOUNDATION_TOO_LARGE")
        return body

    @classmethod
    def from_bytes(
        cls,
        body: bytes,
        *,
        expected_source_head: str,
        expected_source_tree: str,
        expected_generation0: Generation0Inventory,
    ) -> CampaignFoundation:
        _require_git_id(expected_source_head)
        _require_git_id(expected_source_tree)
        if type(expected_generation0) is not Generation0Inventory:
            raise _discovery_error("CAMPAIGN_FOUNDATION_REVIEWED_INVENTORY_REQUIRED")
        raw = _parse_canonical_object(
            body, MAX_FOUNDATION_BYTES, "CAMPAIGN_FOUNDATION_JSON_INVALID"
        )
        row = _exact_object(
            raw,
            {
                "schema",
                "identity",
                "campaign_version",
                "source",
                "generation0",
                "trial_ledger",
                "evaluated_trial_count",
                "budgets",
                "final_holdout_sealed",
                "effects",
                "authority",
            },
        )
        if (
            row["schema"] != FOUNDATION_SCHEMA
            or row["campaign_version"] != CAMPAIGN_VERSION
        ):
            raise _discovery_error("CAMPAIGN_FOUNDATION_SCHEMA_INVALID")
        source = _exact_object(row["source"], {"head", "tree"})
        if (source["head"], source["tree"]) != (
            expected_source_head,
            expected_source_tree,
        ):
            raise _discovery_error("CAMPAIGN_FOUNDATION_SOURCE_MISMATCH")
        if row["authority"] != AUTHORITY or row["final_holdout_sealed"] is not True:
            raise _discovery_error("CAMPAIGN_FOUNDATION_AUTHORITY_INVALID")
        _validate_effects(row["effects"])
        budgets = _exact_object(
            row["budgets"], {"generation_1_max_evaluated", "generation_2_max_evaluated"}
        )
        if budgets != {
            "generation_1_max_evaluated": GENERATION_1_MAX_EVALUATED,
            "generation_2_max_evaluated": GENERATION_2_MAX_EVALUATED,
        }:
            raise _discovery_error("CAMPAIGN_FOUNDATION_BUDGET_INVALID")
        inventory = Generation0Inventory.from_dict(row["generation0"])
        try:
            ledger = TrialLedger.from_dict(row["trial_ledger"])
        except (ValueError, TypeError, KeyError, RecursionError):
            raise _discovery_error("CAMPAIGN_FOUNDATION_LEDGER_INVALID") from None
        if inventory.to_bytes() != expected_generation0.to_bytes():
            raise _discovery_error("CAMPAIGN_FOUNDATION_INVENTORY_MISMATCH")
        evaluated_trial_count = ledger.evaluated_trial_count
        if (
            type(row["evaluated_trial_count"]) is not int
            or evaluated_trial_count != row["evaluated_trial_count"]
        ):
            raise _discovery_error("CAMPAIGN_FOUNDATION_TRIAL_COUNT_MISMATCH")
        artifact = cls(source["head"], source["tree"], inventory, ledger)
        if row["identity"] != artifact.identity:
            raise _discovery_error("CAMPAIGN_FOUNDATION_IDENTITY_MISMATCH")
        if artifact.to_bytes() != body:
            raise _discovery_error("CAMPAIGN_FOUNDATION_NOT_CANONICAL")
        return artifact


def create_campaign_foundation(
    *,
    source_head: str,
    source_tree: str,
    generation0: Generation0Inventory,
    trial_ledger: TrialLedger,
) -> CampaignFoundation:
    return CampaignFoundation(source_head, source_tree, generation0, trial_ledger)


def verify_campaign_foundation(
    body: bytes,
    *,
    expected_source_head: str,
    expected_source_tree: str,
    expected_generation0: Generation0Inventory,
) -> CampaignFoundation:
    return CampaignFoundation.from_bytes(
        body,
        expected_source_head=expected_source_head,
        expected_source_tree=expected_source_tree,
        expected_generation0=expected_generation0,
    )


def read_campaign_foundation(
    path: Path,
    *,
    expected_source_head: str,
    expected_source_tree: str,
    expected_generation0: Generation0Inventory,
) -> CampaignFoundation:
    return verify_campaign_foundation(
        _read_explicit_file(path, MAX_FOUNDATION_BYTES),
        expected_source_head=expected_source_head,
        expected_source_tree=expected_source_tree,
        expected_generation0=expected_generation0,
    )


def _ledger_payload(ledger: TrialLedger) -> dict[str, object]:
    if type(ledger) is not TrialLedger:
        raise _discovery_error("CAMPAIGN_FOUNDATION_LEDGER_INVALID")
    payload = ledger.to_dict()
    if type(payload) is not dict:
        raise _discovery_error("CAMPAIGN_FOUNDATION_LEDGER_INVALID")
    return payload


def _validate_effects(raw: object) -> None:
    effects = _exact_object(raw, set(_EFFECT_COUNTERS))
    if any(type(value) is not int or value != 0 for value in effects.values()):
        raise _discovery_error("CAMPAIGN_FOUNDATION_EFFECTS_INVALID")


def _identity(version: str, value: dict[str, object]) -> str:
    material = canonical_json_bytes([version, value]).decode("utf-8")
    return str(uuid5(_IDENTITY_NAMESPACE, material))


def _parse_canonical_object(body: bytes, maximum: int, code: str) -> dict[str, object]:
    if type(body) is not bytes or not body or len(body) > maximum:
        raise _discovery_error(code)
    try:
        raw = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except DiscoveryError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise _discovery_error(code) from None
    if type(raw) is not dict or canonical_json_bytes(raw) != body:
        raise _discovery_error(code.replace("INVALID", "NOT_CANONICAL"))
    return raw


def _validate_canonical_summary(value: object) -> None:
    if type(value) is not str or len(value.encode("utf-8")) > MAX_SUMMARY_BYTES:
        raise _discovery_error("GENERATION0_SUMMARY_INVALID")
    try:
        summary = json.loads(
            value,
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise _discovery_error("GENERATION0_SUMMARY_INVALID") from None
    if (
        type(summary) not in (list, dict)
        or len(summary) > MAX_SYNTHESIS_ITEMS
        or canonical_json_bytes(summary).decode("utf-8") != value
    ):
        raise _discovery_error("GENERATION0_SUMMARY_INVALID")


def _json_plain(value: object) -> object:
    if isinstance(value, Decimal):
        return decimal_text(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _json_plain(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, (tuple, list)):
        return [_json_plain(item) for item in value]
    if type(value) is dict:
        return {key: _json_plain(item) for key, item in value.items()}
    if value is None or type(value) in (str, int, bool):
        return value
    raise _discovery_error("GENERATION0_SUMMARY_VALUE_INVALID")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _discovery_error("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise _discovery_error("NONFINITE_JSON_VALUE")


def _exact_object(raw: object, expected: set[str]) -> dict[str, Any]:
    if type(raw) is not dict or set(raw) != expected:
        raise _discovery_error("UNKNOWN_OR_MISSING_FIELD")
    return raw


def _read_explicit_file(path: Path, maximum: int) -> bytes:
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        raise _discovery_error("EVIDENCE_PATH_INVALID")
    raw_path = os.fspath(path)
    if (
        raw_path.startswith(("\\\\", "//"))
        or any(":" in part for part in path.parts[1:])
        or (os.name == "nt" and not re.fullmatch(r"[A-Za-z]:", path.drive))
    ):
        raise _discovery_error("EVIDENCE_PATH_INVALID")
    _reject_final_holdout_path(path)
    current = path
    chain = [current, *current.parents]
    for index, item in enumerate(chain):
        try:
            info = os.lstat(item)
        except FileNotFoundError:
            raise _discovery_error("EVIDENCE_PATH_UNAVAILABLE") from None
        except (OSError, ValueError):
            raise _discovery_error("EVIDENCE_PATH_ACCESS_FAILED") from None
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(info.st_mode) or attributes & reparse:
            raise _discovery_error("EVIDENCE_PATH_LINKED")
        if index == 0:
            if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
                raise _discovery_error("EVIDENCE_FILE_INVALID_OR_OVERSIZED")
        elif not stat.S_ISDIR(info.st_mode):
            raise _discovery_error("EVIDENCE_PATH_COMPONENT_INVALID")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        raise _discovery_error("EVIDENCE_PATH_UNAVAILABLE") from None
    except (OSError, ValueError):
        raise _discovery_error("EVIDENCE_PATH_ACCESS_FAILED") from None
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise _discovery_error("EVIDENCE_FILE_INVALID_OR_OVERSIZED")
        try:
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                body = stream.read(maximum + 1)
        except OSError:
            raise _discovery_error("EVIDENCE_READ_FAILED") from None
        after = os.fstat(descriptor)
        if (
            len(body) > maximum
            or len(body) != before.st_size
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        ):
            raise _discovery_error("EVIDENCE_FILE_CHANGED_OR_OVERSIZED")
        return body
    finally:
        os.close(descriptor)


def _reject_final_holdout_path(path: Path) -> None:
    if not isinstance(path, Path):
        raise _discovery_error("EVIDENCE_PATH_INVALID")
    candidate = os.fspath(path).replace("-", "_").casefold()
    if "final_holdout" in candidate:
        raise _discovery_error("FINAL_HOLDOUT_PATH_FORBIDDEN")


def _require_text(value: object) -> None:
    if type(value) is not str or not value or len(value) > MAX_TEXT_LENGTH:
        raise _discovery_error("EVIDENCE_TEXT_INVALID")


def _require_text_tuple(value: object) -> None:
    if type(value) is not tuple or len(value) > MAX_SYNTHESIS_ITEMS:
        raise _discovery_error("EVIDENCE_TEXT_LIST_INVALID")
    for item in value:
        _require_text(item)


def _require_nonnegative_int(value: object) -> None:
    if type(value) is not int or value < 0:
        raise _discovery_error("EVIDENCE_INTEGER_INVALID")


def _require_uuid(value: object) -> None:
    if type(value) is not str or _UUID.fullmatch(value) is None:
        raise _discovery_error("EVIDENCE_IDENTITY_INVALID")


def _require_digest(value: object) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise _discovery_error("EVIDENCE_DIGEST_INVALID")


def _require_git_id(value: object) -> None:
    if type(value) is not str or _GIT_ID.fullmatch(value) is None:
        raise _discovery_error("EVIDENCE_SOURCE_ID_INVALID")


def main(argv: list[str] | None = None) -> int:
    """Expose effect-free module help only; no G0/G1 action is runnable here."""

    parser = argparse.ArgumentParser(
        description=(
            "Read-only AI Strategy Discovery evidence models. This source-only "
            "module exposes no campaign, replay, provider, AI, or trading action."
        )
    )
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
