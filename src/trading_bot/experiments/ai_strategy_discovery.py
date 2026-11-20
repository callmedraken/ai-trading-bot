"""Immutable, effect-free proposals and append-only discovery trial history.

This module defines closed proposal and ledger records only. Supported strategy
specifications map to the accepted Architecture 147 ``StrategyConfig`` values;
an evaluator may later pass those values to ``filtered_trend_campaign.evaluate_cell``.
No campaign, strategy replay, provider, AI service, or lifecycle action is run here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid5

from trading_bot.experiments.filtered_trend_strategies import StrategyConfig
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

PROPOSAL_SCHEMA = "ai-strategy-discovery-proposal/v1"
LEDGER_SCHEMA = "ai-strategy-discovery-trial-ledger/v1"
INVALID_SUBMISSION_SCHEMA = "ai-strategy-discovery-invalid-submission/v1"
PROPOSAL_IDENTITY_VERSION = "ai-strategy-discovery-proposal-identity/v1"
PROGRAM_IDENTITY_VERSION = "ai-strategy-discovery-program-identity/v1"
LEDGER_IDENTITY_VERSION = "ai-strategy-discovery-ledger-identity/v1"
INVALID_SUBMISSION_IDENTITY_VERSION = (
    "ai-strategy-discovery-invalid-submission-identity/v1"
)
CAMPAIGN_VERSION = "v1"
GENERATION_1_MAX_EVALUATED = 32
GENERATION_2_MAX_EVALUATED = 16
GENERATION_1_MAX_PER_FAMILY = GENERATION_1_MAX_EVALUATED // 4
COUNT_PROVENANCE = "unique-attempted-trial-ordinal/v1"
MAX_PROPOSAL_BYTES = 64 * 1024
MAX_LEDGER_BYTES = 4 * 1024 * 1024
MAX_LEDGER_EVENTS = 4096
MAX_TRIAL_ORDINAL = 10_000
MAX_TEXT_LENGTH = 2048
MAX_LABEL_LENGTH = 96

_PROPOSAL_NAMESPACE = UUID("f1754d6c-9e1f-5f88-bc70-1e8b5747e817")
_PROGRAM_NAMESPACE = UUID("49329858-f53d-5c58-a0ea-71ebd77ad7a7")
_LEDGER_NAMESPACE = UUID("3137117a-b59d-5cf5-94f6-b6c2c3f2e9b7")
_DIAGNOSTIC_NAMESPACE = UUID("cebf7201-7546-57af-8c96-20b51711ba40")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}")
_DIAGNOSTIC = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_SUPPORTED_PAIRS = ((35, 50), (55, 100), (50, 200))


class DiscoveryError(ValueError):
    """Malformed, inconsistent, or unsupported discovery data."""


class StrategyFamily(StrEnum):
    """Frozen campaign vocabulary; only two families compile in this checkpoint."""

    ABSOLUTE_MOMENTUM = "ABSOLUTE_MOMENTUM"
    MULTI_HORIZON_TREND = "MULTI_HORIZON_TREND"
    MOVING_AVERAGE_TREND = "MOVING_AVERAGE_TREND"
    DONCHIAN_BREAKOUT = "DONCHIAN_BREAKOUT"
    VOLATILITY_ADJUSTED_TREND = "VOLATILITY_ADJUSTED_TREND"
    BOUNDED_MEAN_REVERSION = "BOUNDED_MEAN_REVERSION"
    CROSS_SECTIONAL_RELATIVE_STRENGTH = "CROSS_SECTIONAL_RELATIVE_STRENGTH"
    DEFENSIVE_ROTATION = "DEFENSIVE_ROTATION"
    CROSS_ASSET_REGIME_GATE = "CROSS_ASSET_REGIME_GATE"
    FIXED_ENSEMBLE = "FIXED_ENSEMBLE"


class MovingAverageRule(StrEnum):
    """Only accepted A147 baseline and fixed 1% band rules are available."""

    BASE_MA = "BASE_MA"
    MA_PERCENT_BAND_010 = "MA_PERCENT_BAND_010"


class ProposalKind(StrEnum):
    ORIGINAL = "ORIGINAL"
    MUTATION = "MUTATION"
    RECOMBINATION = "RECOMBINATION"
    RETAINED_BASELINE = "RETAINED_BASELINE"


class ProposalSemanticStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID = "INVALID"


class VisibilityStage(StrEnum):
    GENERATION_1_PRE_RESULTS = "GENERATION_1_PRE_RESULTS"
    GENERATION_2_PRE_CONFIRMATION = "GENERATION_2_PRE_CONFIRMATION"


class VisibleEvidenceClassification(StrEnum):
    PRIOR_CANONICAL = "PRIOR_CANONICAL"
    SESSION_NONCANONICAL = "SESSION_NONCANONICAL"
    QUEUED_UNEVALUATED = "QUEUED_UNEVALUATED"
    GENERATION_1_DISCOVERY_RESULT = "GENERATION_1_DISCOVERY_RESULT"
    GENERATION_2_CONFIRMATION_RESULT = "GENERATION_2_CONFIRMATION_RESULT"
    FINAL_HOLDOUT = "FINAL_HOLDOUT"


class VisibleTimeframe(StrEnum):
    DAILY = "DAILY"
    INTRADAY_5MIN = "INTRADAY_5MIN"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class VisibleTimePartition(StrEnum):
    UNKNOWN = "UNKNOWN"
    WARMUP_2016_2018 = "WARMUP_2016_2018"
    DISCOVERY_2019_2021 = "DISCOVERY_2019_2021"
    PRIOR_RESEARCH_2022_2023 = "PRIOR_RESEARCH_2022_2023"
    CAMPAIGN_CONFIRMATION_2022_2023 = "CAMPAIGN_CONFIRMATION_2022_2023"
    OPEN_INTRADAY = "OPEN_INTRADAY"
    QUEUED_DESIGN = "QUEUED_DESIGN"
    FINAL_HOLDOUT = "FINAL_HOLDOUT"


class TrialDisposition(StrEnum):
    ACCEPTED_FOR_EVALUATION = "ACCEPTED_FOR_EVALUATION"
    DUPLICATE_REJECTED = "DUPLICATE_REJECTED"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    ZERO_TRADE = "ZERO_TRADE"
    DETERMINISTIC_EVALUATION_FAILED = "DETERMINISTIC_EVALUATION_FAILED"
    ECONOMICALLY_REJECTED = "ECONOMICALLY_REJECTED"
    SHORTLISTED = "SHORTLISTED"


class _FamilySpecSchema(StrEnum):
    MOVING_AVERAGE_TREND = "moving-average-trend-spec/v1"
    DONCHIAN_BREAKOUT = "donchian-breakout-spec/v1"
    DEFERRED = "deferred-strategy-spec/v1"


@dataclass(frozen=True, slots=True)
class MovingAverageTrendSpec:
    """A frozen A147 BASE_MA or 1.0% band configuration."""

    fast_window: int
    slow_window: int
    rule: MovingAverageRule

    def __post_init__(self) -> None:
        _validate_pair(self.fast_window, self.slow_window)
        if type(self.rule) is not MovingAverageRule:
            raise DiscoveryError("moving-average rule must be a declared value")

    @property
    def family(self) -> StrategyFamily:
        return StrategyFamily.MOVING_AVERAGE_TREND

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": _FamilySpecSchema.MOVING_AVERAGE_TREND.value,
            "family": self.family.value,
            "fast_window": self.fast_window,
            "slow_window": self.slow_window,
            "rule": self.rule.value,
        }


@dataclass(frozen=True, slots=True)
class DonchianBreakoutSpec:
    """A147 MA-gated prior-channel-high entry with its existing MA exit."""

    fast_window: int
    slow_window: int
    channel_lookback_sessions: int

    def __post_init__(self) -> None:
        _validate_pair(self.fast_window, self.slow_window)
        if type(self.channel_lookback_sessions) is not int or (
            self.channel_lookback_sessions not in (20, 55)
        ):
            raise DiscoveryError("Donchian lookback must be 20 or 55 sessions")

    @property
    def family(self) -> StrategyFamily:
        return StrategyFamily.DONCHIAN_BREAKOUT

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": _FamilySpecSchema.DONCHIAN_BREAKOUT.value,
            "family": self.family.value,
            "fast_window": self.fast_window,
            "slow_window": self.slow_window,
            "channel_lookback_sessions": self.channel_lookback_sessions,
        }


_DEFERRED_FAMILIES = frozenset(
    {
        StrategyFamily.ABSOLUTE_MOMENTUM,
        StrategyFamily.MULTI_HORIZON_TREND,
        StrategyFamily.VOLATILITY_ADJUSTED_TREND,
        StrategyFamily.BOUNDED_MEAN_REVERSION,
        StrategyFamily.CROSS_SECTIONAL_RELATIVE_STRENGTH,
        StrategyFamily.DEFENSIVE_ROTATION,
        StrategyFamily.CROSS_ASSET_REGIME_GATE,
        StrategyFamily.FIXED_ENSEMBLE,
    }
)


@dataclass(frozen=True, slots=True)
class DeferredStrategySpec:
    """Closed vocabulary marker for a family without an accepted evaluator map."""

    family: StrategyFamily

    def __post_init__(self) -> None:
        if (
            type(self.family) is not StrategyFamily
            or self.family not in _DEFERRED_FAMILIES
        ):
            raise DiscoveryError("family is not a deferred campaign family")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": _FamilySpecSchema.DEFERRED.value,
            "family": self.family.value,
            "deferred_reason": "NO_ACCEPTED_STANDALONE_EVALUATOR",
        }


StrategySpec = MovingAverageTrendSpec | DonchianBreakoutSpec | DeferredStrategySpec


@dataclass(frozen=True, slots=True)
class Generation1DiagnosticReference:
    """Exact earlier G1 parent trial diagnostic made visible to a G2 proposal."""

    parent_proposal_id: str
    parent_trial_ordinal: int
    diagnostic_id: str

    def __post_init__(self) -> None:
        _uuid5_text(self.parent_proposal_id, "parent proposal id")
        _bounded_positive_int(
            self.parent_trial_ordinal, MAX_TRIAL_ORDINAL, "parent ordinal"
        )
        _uuid5_text(self.diagnostic_id, "diagnostic id")

    def to_dict(self) -> dict[str, object]:
        return {
            "parent_proposal_id": self.parent_proposal_id,
            "parent_trial_ordinal": self.parent_trial_ordinal,
            "diagnostic_id": self.diagnostic_id,
        }


@dataclass(frozen=True, slots=True)
class VisibleEvidenceReference:
    """A visible prior/session artifact label and its declared data chronology."""

    reference_label: str
    dataset_label: str
    timeframe: VisibleTimeframe
    time_partition: VisibleTimePartition
    classification: VisibleEvidenceClassification

    def __post_init__(self) -> None:
        _validate_label(self.reference_label, "visible evidence reference")
        _validate_label(self.dataset_label, "visible dataset reference")
        if type(self.timeframe) is not VisibleTimeframe:
            raise DiscoveryError("visible timeframe must be a declared value")
        if type(self.time_partition) is not VisibleTimePartition:
            raise DiscoveryError("visible time partition must be a declared value")
        if type(self.classification) is not VisibleEvidenceClassification:
            raise DiscoveryError("visible evidence classification must be declared")
        if (
            self.classification is VisibleEvidenceClassification.FINAL_HOLDOUT
            or self.time_partition is VisibleTimePartition.FINAL_HOLDOUT
            or self.classification
            is VisibleEvidenceClassification.GENERATION_2_CONFIRMATION_RESULT
            or self.time_partition
            is VisibleTimePartition.CAMPAIGN_CONFIRMATION_2022_2023
        ):
            raise DiscoveryError("confirmation results and FINAL_HOLDOUT stay sealed")
        if (
            self.classification
            is VisibleEvidenceClassification.GENERATION_1_DISCOVERY_RESULT
            and self.time_partition is not VisibleTimePartition.DISCOVERY_2019_2021
        ):
            raise DiscoveryError("G1 result evidence must bind the discovery partition")

    def to_dict(self) -> dict[str, str]:
        return {
            "reference_label": self.reference_label,
            "dataset_label": self.dataset_label,
            "timeframe": self.timeframe.value,
            "time_partition": self.time_partition.value,
            "classification": self.classification.value,
        }


@dataclass(frozen=True, slots=True)
class InformationVisibility:
    """Typed chronology declaration for evidence visible when a proposal was made."""

    stage: VisibilityStage
    visible_evidence: tuple[VisibleEvidenceReference, ...]
    visible_generation1_diagnostics: tuple[Generation1DiagnosticReference, ...] = ()
    confirmation_results_visible: bool = False
    final_holdout_accessed: bool = False

    def __post_init__(self) -> None:
        if type(self.stage) is not VisibilityStage:
            raise DiscoveryError("visibility stage must be a declared value")
        if type(self.visible_evidence) is not tuple or any(
            type(item) is not VisibleEvidenceReference for item in self.visible_evidence
        ):
            raise DiscoveryError("visible evidence must use immutable typed references")
        if len({item.reference_label for item in self.visible_evidence}) != len(
            self.visible_evidence
        ):
            raise DiscoveryError("duplicate visible evidence reference")
        if self.stage is VisibilityStage.GENERATION_1_PRE_RESULTS and any(
            item.classification
            is VisibleEvidenceClassification.GENERATION_1_DISCOVERY_RESULT
            for item in self.visible_evidence
        ):
            raise DiscoveryError("Generation 1 proposals cannot see their own results")
        if type(self.visible_generation1_diagnostics) is not tuple or any(
            type(item) is not Generation1DiagnosticReference
            for item in self.visible_generation1_diagnostics
        ):
            raise DiscoveryError("visible diagnostics must be immutable references")
        if len(
            {item.parent_proposal_id for item in self.visible_generation1_diagnostics}
        ) != len(self.visible_generation1_diagnostics):
            raise DiscoveryError("duplicate visible parent diagnostic")
        if type(self.confirmation_results_visible) is not bool or (
            self.confirmation_results_visible
        ):
            raise DiscoveryError("confirmation results must remain unseen")
        if type(self.final_holdout_accessed) is not bool or self.final_holdout_accessed:
            raise DiscoveryError("FINAL_HOLDOUT must remain sealed")

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "visible_evidence": [item.to_dict() for item in self.visible_evidence],
            "visible_generation1_diagnostics": [
                item.to_dict() for item in self.visible_generation1_diagnostics
            ],
            "confirmation_results_visible": self.confirmation_results_visible,
            "final_holdout_accessed": self.final_holdout_accessed,
        }


@dataclass(frozen=True, slots=True)
class ResearchProposal:
    """Canonical AI-supplied research hypothesis without execution authority."""

    campaign_version: str
    generation: int
    proposal_kind: ProposalKind
    parent_proposal_ids: tuple[str, ...]
    strategy_spec: StrategySpec
    hypothesis: str
    expected_mechanism: str
    falsification_condition: str
    source_reference_labels: tuple[str, ...]
    information_visibility: InformationVisibility
    producer_label: str
    proposal_id: str = field(init=False)
    schema: str = field(default=PROPOSAL_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (
            type(self.campaign_version) is not str
            or self.campaign_version != CAMPAIGN_VERSION
        ):
            raise DiscoveryError(
                "campaign_version must match the core campaign contract"
            )
        if type(self.generation) is not int or self.generation not in (1, 2):
            raise DiscoveryError("generation must be 1 or 2")
        if type(self.proposal_kind) is not ProposalKind:
            raise DiscoveryError("proposal kind must be a declared value")
        if type(self.parent_proposal_ids) is not tuple:
            raise DiscoveryError("parent proposal ids must be an immutable tuple")
        for item in self.parent_proposal_ids:
            _uuid5_text(item, "parent proposal id")
        if len(set(self.parent_proposal_ids)) != len(self.parent_proposal_ids):
            raise DiscoveryError("duplicate parent proposal id")
        if type(self.strategy_spec) not in (
            MovingAverageTrendSpec,
            DonchianBreakoutSpec,
            DeferredStrategySpec,
        ):
            raise DiscoveryError("strategy_spec must use the closed typed grammar")
        _validate_text(self.hypothesis, "hypothesis")
        _validate_text(self.expected_mechanism, "expected mechanism")
        _validate_text(self.falsification_condition, "falsification condition")
        _validate_labels(self.source_reference_labels, "source/reference labels")
        if type(self.information_visibility) is not InformationVisibility:
            raise DiscoveryError("typed information visibility is required")
        if not self.information_visibility.visible_evidence:
            raise DiscoveryError("valid proposal must declare visible evidence inputs")
        _validate_label(self.producer_label, "producer label")
        self._validate_lineage()
        object.__setattr__(self, "proposal_id", _proposal_id(self))

    def _validate_lineage(self) -> None:
        visibility = self.information_visibility
        if self.generation == 1:
            if (
                self.proposal_kind
                not in (ProposalKind.ORIGINAL, ProposalKind.RETAINED_BASELINE)
                or self.parent_proposal_ids
                or visibility.stage is not VisibilityStage.GENERATION_1_PRE_RESULTS
                or visibility.visible_generation1_diagnostics
            ):
                raise DiscoveryError("invalid Generation 1 proposal chronology")
            return
        if (
            self.proposal_kind
            not in (ProposalKind.MUTATION, ProposalKind.RECOMBINATION)
            or visibility.stage is not VisibilityStage.GENERATION_2_PRE_CONFIRMATION
            or not visibility.visible_generation1_diagnostics
            or tuple(
                item.parent_proposal_id
                for item in visibility.visible_generation1_diagnostics
            )
            != self.parent_proposal_ids
        ):
            raise DiscoveryError(
                "Generation 2 requires exact earlier G1 parent diagnostics"
            )
        if (
            self.proposal_kind is ProposalKind.MUTATION
            and len(self.parent_proposal_ids) != 1
        ):
            raise DiscoveryError("a mutation requires exactly one Generation 1 parent")
        if (
            self.proposal_kind is ProposalKind.RECOMBINATION
            and len(self.parent_proposal_ids) < 2
        ):
            raise DiscoveryError(
                "a recombination requires at least two Generation 1 parents"
            )

    @property
    def family(self) -> StrategyFamily:
        return self.strategy_spec.family

    @property
    def semantic_status(self) -> ProposalSemanticStatus:
        return (
            ProposalSemanticStatus.UNSUPPORTED
            if type(self.strategy_spec) is DeferredStrategySpec
            else ProposalSemanticStatus.SUPPORTED
        )

    @property
    def semantic_program_id(self) -> str:
        """Deduplication identity excludes prose, parents, and producer provenance."""
        material = {
            "identity_version": PROGRAM_IDENTITY_VERSION,
            "specification": self.strategy_spec.to_dict(),
        }
        return str(
            uuid5(_PROGRAM_NAMESPACE, canonical_json_bytes(material).decode("utf-8"))
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "proposal_id": self.proposal_id,
            "campaign_version": self.campaign_version,
            "generation": self.generation,
            "proposal_kind": self.proposal_kind.value,
            "parent_proposal_ids": list(self.parent_proposal_ids),
            "family": self.family.value,
            "semantic_program_id": self.semantic_program_id,
            "semantic_status": self.semantic_status.value,
            "strategy_spec": self.strategy_spec.to_dict(),
            "hypothesis": self.hypothesis,
            "expected_mechanism": self.expected_mechanism,
            "falsification_condition": self.falsification_condition,
            "source_reference_labels": list(self.source_reference_labels),
            "information_visibility": self.information_visibility.to_dict(),
            "producer_label": self.producer_label,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_dict(cls, raw: object) -> ResearchProposal:
        try:
            row = _exact(
                raw,
                {
                    "schema",
                    "proposal_id",
                    "campaign_version",
                    "generation",
                    "proposal_kind",
                    "parent_proposal_ids",
                    "family",
                    "semantic_program_id",
                    "semantic_status",
                    "strategy_spec",
                    "hypothesis",
                    "expected_mechanism",
                    "falsification_condition",
                    "source_reference_labels",
                    "information_visibility",
                    "producer_label",
                },
            )
            if row["schema"] != PROPOSAL_SCHEMA:
                raise DiscoveryError("unsupported proposal schema")
            proposal = cls(
                campaign_version=row["campaign_version"],
                generation=row["generation"],
                proposal_kind=_enum(
                    ProposalKind, row["proposal_kind"], "proposal kind"
                ),
                parent_proposal_ids=_string_tuple(row["parent_proposal_ids"]),
                strategy_spec=_strategy_spec_from_dict(row["strategy_spec"]),
                hypothesis=row["hypothesis"],
                expected_mechanism=row["expected_mechanism"],
                falsification_condition=row["falsification_condition"],
                source_reference_labels=_string_tuple(row["source_reference_labels"]),
                information_visibility=_visibility_from_dict(
                    row["information_visibility"]
                ),
                producer_label=row["producer_label"],
            )
            if (
                row["proposal_id"] != proposal.proposal_id
                or row["family"] != proposal.family.value
                or row["semantic_program_id"] != proposal.semantic_program_id
                or row["semantic_status"] != proposal.semantic_status.value
                or canonical_json_bytes(proposal.to_dict()) != canonical_json_bytes(row)
            ):
                raise DiscoveryError("proposal identity or derived fields disagree")
            return proposal
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise DiscoveryError("invalid canonical research proposal") from None

    @classmethod
    def from_bytes(cls, body: bytes) -> ResearchProposal:
        raw = _parse_canonical_object(body, MAX_PROPOSAL_BYTES)
        return cls.from_dict(raw)


@dataclass(frozen=True, slots=True)
class InvalidProposalReference:
    """Safe reference to malformed input without retaining its arbitrary payload.

    The caller supplies a stable SHA-256 fingerprint over its safe semantic
    envelope. Raw JSON, code, expression text, and artifact bytes are never
    retained or evaluated by this model. Its generation/visibility context is
    caller-known metadata: malformed Generation 2 linkage may be absent and is
    not asserted as a validated parent relation.
    """

    generation: int
    caller_semantic_fingerprint: str
    diagnostic_code: str
    source_reference_labels: tuple[str, ...]
    information_visibility: InformationVisibility
    producer_label: str
    proposal_id: str = field(init=False)
    schema: str = field(default=INVALID_SUBMISSION_SCHEMA, init=False)
    campaign_version: str = field(default=CAMPAIGN_VERSION, init=False)

    def __post_init__(self) -> None:
        if type(self.generation) is not int or self.generation not in (1, 2):
            raise DiscoveryError("generation must be 1 or 2")
        if (
            type(self.caller_semantic_fingerprint) is not str
            or re.fullmatch(r"[0-9a-f]{64}", self.caller_semantic_fingerprint) is None
        ):
            raise DiscoveryError(
                "caller semantic fingerprint must be lowercase SHA-256"
            )
        if (
            type(self.diagnostic_code) is not str
            or _DIAGNOSTIC.fullmatch(self.diagnostic_code) is None
        ):
            raise DiscoveryError("invalid-submission diagnostic code is required")
        _validate_labels(self.source_reference_labels, "source/reference labels")
        if type(self.information_visibility) is not InformationVisibility:
            raise DiscoveryError("typed information visibility is required")
        _validate_label(self.producer_label, "producer label")
        if self.generation == 1:
            if (
                self.information_visibility.stage
                is not VisibilityStage.GENERATION_1_PRE_RESULTS
                or self.information_visibility.visible_generation1_diagnostics
            ):
                raise DiscoveryError("invalid Generation 1 submission chronology")
        elif (
            self.information_visibility.stage
            is not VisibilityStage.GENERATION_2_PRE_CONFIRMATION
        ):
            raise DiscoveryError("invalid Generation 2 submission chronology")
        material = {
            "identity_version": INVALID_SUBMISSION_IDENTITY_VERSION,
            "campaign_version": CAMPAIGN_VERSION,
            "generation": self.generation,
            "caller_semantic_fingerprint": self.caller_semantic_fingerprint,
        }
        object.__setattr__(
            self,
            "proposal_id",
            str(
                uuid5(
                    _PROPOSAL_NAMESPACE, canonical_json_bytes(material).decode("utf-8")
                )
            ),
        )

    @property
    def parent_proposal_ids(self) -> tuple[str, ...]:
        return tuple(
            item.parent_proposal_id
            for item in self.information_visibility.visible_generation1_diagnostics
        )

    @property
    def semantic_program_id(self) -> None:
        return None

    @property
    def semantic_status(self) -> ProposalSemanticStatus:
        return ProposalSemanticStatus.INVALID

    @property
    def family(self) -> None:
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "proposal_id": self.proposal_id,
            "campaign_version": self.campaign_version,
            "generation": self.generation,
            "caller_semantic_fingerprint": self.caller_semantic_fingerprint,
            "diagnostic_code": self.diagnostic_code,
            "source_reference_labels": list(self.source_reference_labels),
            "information_visibility": self.information_visibility.to_dict(),
            "producer_label": self.producer_label,
        }

    @classmethod
    def from_dict(cls, raw: object) -> InvalidProposalReference:
        try:
            row = _exact(
                raw,
                {
                    "schema",
                    "proposal_id",
                    "campaign_version",
                    "generation",
                    "caller_semantic_fingerprint",
                    "diagnostic_code",
                    "source_reference_labels",
                    "information_visibility",
                    "producer_label",
                },
            )
            if row["schema"] != INVALID_SUBMISSION_SCHEMA or (
                row["campaign_version"] != CAMPAIGN_VERSION
            ):
                raise DiscoveryError("unsupported invalid-submission schema")
            result = cls(
                generation=row["generation"],
                caller_semantic_fingerprint=row["caller_semantic_fingerprint"],
                diagnostic_code=row["diagnostic_code"],
                source_reference_labels=_string_tuple(row["source_reference_labels"]),
                information_visibility=_visibility_from_dict(
                    row["information_visibility"]
                ),
                producer_label=row["producer_label"],
            )
            if result.to_dict() != row:
                raise DiscoveryError("invalid-submission identity disagrees")
            return result
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise DiscoveryError("invalid sanitized submission reference") from None


def compile_strategy_config(spec: StrategySpec) -> StrategyConfig:
    """Map only supported typed specs to exact accepted A147 configurations.

    A later evaluator adapter may call ``filtered_trend_campaign.evaluate_cell``
    with this config. This function performs no research or replay.
    """
    if type(spec) is MovingAverageTrendSpec:
        if spec.rule is MovingAverageRule.BASE_MA:
            return StrategyConfig("BASE_MA", spec.fast_window, spec.slow_window, "none")
        return StrategyConfig(
            "MA_PERCENT_BAND", spec.fast_window, spec.slow_window, "0.010"
        )
    if type(spec) is DonchianBreakoutSpec:
        return StrategyConfig(
            "MA_DONCHIAN",
            spec.fast_window,
            spec.slow_window,
            str(spec.channel_lookback_sessions),
        )
    raise DiscoveryError("strategy family has no accepted evaluator mapping")


@dataclass(frozen=True, slots=True)
class TrialLedgerRecord:
    """One immutable event for a proposal; progression appends another event."""

    event_ordinal: int
    trial_ordinal: int
    proposal: ResearchProposal | InvalidProposalReference
    disposition: TrialDisposition
    evaluation_attempt_id: str | None = None
    evaluation_source_head: str | None = None
    evaluation_source_tree: str | None = None
    dataset_evidence_id: str | None = None
    evaluation_id: str | None = None
    result_id: str | None = None
    terminal_diagnostic_code: str | None = None
    pnl_visible: bool = False
    diagnostic_visible: bool = False

    def __post_init__(self) -> None:
        _bounded_positive_int(self.event_ordinal, MAX_LEDGER_EVENTS, "event ordinal")
        _bounded_positive_int(self.trial_ordinal, MAX_TRIAL_ORDINAL, "trial ordinal")
        if type(self.proposal) not in (ResearchProposal, InvalidProposalReference):
            raise DiscoveryError(
                "ledger record requires an immutable typed proposal reference"
            )
        if type(self.disposition) is not TrialDisposition:
            raise DiscoveryError("trial disposition must be a declared value")
        if (
            type(self.pnl_visible) is not bool
            or type(self.diagnostic_visible) is not bool
        ):
            raise DiscoveryError("visibility flags must be booleans")
        if self.evaluation_attempt_id is not None:
            _uuid5_text(self.evaluation_attempt_id, "evaluation attempt id")
        if self.evaluation_id is not None:
            _uuid5_text(self.evaluation_id, "evaluation id")
        if self.result_id is not None:
            _uuid5_text(self.result_id, "result id")
        if self.dataset_evidence_id is not None:
            _uuid5_text(self.dataset_evidence_id, "dataset evidence id")
        _optional_git(self.evaluation_source_head, "evaluation source head")
        _optional_git(self.evaluation_source_tree, "evaluation source tree")
        _validate_record_bindings(self)

    @property
    def proposal_id(self) -> str:
        return self.proposal.proposal_id

    @property
    def generation(self) -> int:
        return self.proposal.generation

    @property
    def semantic_program_id(self) -> str | None:
        return self.proposal.semantic_program_id

    @property
    def diagnostic_id(self) -> str | None:
        if self.terminal_diagnostic_code is None:
            return None
        return str(
            uuid5(
                _DIAGNOSTIC_NAMESPACE,
                canonical_json_bytes(
                    {
                        "schema": "ai-strategy-discovery-diagnostic/v1",
                        "proposal_id": self.proposal_id,
                        "trial_ordinal": self.trial_ordinal,
                        "disposition": self.disposition.value,
                        "attempt_id": self.evaluation_attempt_id,
                        "evaluation_id": self.evaluation_id,
                        "result_id": self.result_id,
                        "diagnostic_code": self.terminal_diagnostic_code,
                    }
                ).decode("utf-8"),
            )
        )

    @property
    def search_trial_count_provenance(self) -> str:
        return (
            "COUNTED_ONCE_BY_TRIAL_ORDINAL"
            if self.evaluation_attempt_id is not None
            else "NOT_COUNTED_BEFORE_EVALUATION_ATTEMPT"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "event_ordinal": self.event_ordinal,
            "trial_ordinal": self.trial_ordinal,
            "proposal_id": self.proposal_id,
            "generation": self.generation,
            "semantic_program_id": self.semantic_program_id,
            "proposal": self.proposal.to_dict(),
            "disposition": self.disposition.value,
            "evaluation_attempt_id": self.evaluation_attempt_id,
            "evaluation_source_head": self.evaluation_source_head,
            "evaluation_source_tree": self.evaluation_source_tree,
            "dataset_evidence_id": self.dataset_evidence_id,
            "evaluation_id": self.evaluation_id,
            "result_id": self.result_id,
            "terminal_diagnostic_code": self.terminal_diagnostic_code,
            "diagnostic_id": self.diagnostic_id,
            "pnl_visible": self.pnl_visible,
            "diagnostic_visible": self.diagnostic_visible,
            "search_trial_count_provenance": self.search_trial_count_provenance,
        }

    @classmethod
    def from_dict(cls, raw: object) -> TrialLedgerRecord:
        try:
            row = _exact(
                raw,
                {
                    "event_ordinal",
                    "trial_ordinal",
                    "proposal_id",
                    "generation",
                    "semantic_program_id",
                    "proposal",
                    "disposition",
                    "evaluation_attempt_id",
                    "evaluation_source_head",
                    "evaluation_source_tree",
                    "dataset_evidence_id",
                    "evaluation_id",
                    "result_id",
                    "terminal_diagnostic_code",
                    "diagnostic_id",
                    "pnl_visible",
                    "diagnostic_visible",
                    "search_trial_count_provenance",
                },
            )
            proposal_raw = row["proposal"]
            if type(proposal_raw) is not dict:
                raise DiscoveryError("typed proposal object required")
            if proposal_raw.get("schema") == PROPOSAL_SCHEMA:
                proposal = ResearchProposal.from_dict(proposal_raw)
            elif proposal_raw.get("schema") == INVALID_SUBMISSION_SCHEMA:
                proposal = InvalidProposalReference.from_dict(proposal_raw)
            else:
                raise DiscoveryError("unknown proposal reference schema")
            if type(row["generation"]) is not int:
                raise DiscoveryError("derived generation must be an exact integer")
            record = cls(
                event_ordinal=row["event_ordinal"],
                trial_ordinal=row["trial_ordinal"],
                proposal=proposal,
                disposition=_enum(TrialDisposition, row["disposition"], "disposition"),
                evaluation_attempt_id=row["evaluation_attempt_id"],
                evaluation_source_head=row["evaluation_source_head"],
                evaluation_source_tree=row["evaluation_source_tree"],
                dataset_evidence_id=row["dataset_evidence_id"],
                evaluation_id=row["evaluation_id"],
                result_id=row["result_id"],
                terminal_diagnostic_code=row["terminal_diagnostic_code"],
                pnl_visible=row["pnl_visible"],
                diagnostic_visible=row["diagnostic_visible"],
            )
            if canonical_json_bytes(record.to_dict()) != canonical_json_bytes(row):
                raise DiscoveryError(
                    "ledger record identity or derived field disagrees"
                )
            return record
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise DiscoveryError("invalid trial ledger record") from None


@dataclass(frozen=True, slots=True)
class TrialLedger:
    """Canonical append-only semantic history, including every rejection/failure."""

    records: tuple[TrialLedgerRecord, ...]
    ledger_id: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.records) is not tuple or len(self.records) > MAX_LEDGER_EVENTS:
            raise DiscoveryError("ledger requires a bounded immutable event tuple")
        if any(type(item) is not TrialLedgerRecord for item in self.records):
            raise DiscoveryError("ledger contains an invalid event type")
        _validate_ledger_history(self.records)
        object.__setattr__(self, "ledger_id", _ledger_id(self.records))

    @property
    def evaluated_trial_count(self) -> int:
        """Count distinct trial ordinals with an actual attempt, including failures."""
        return len(
            {
                (record.generation, record.trial_ordinal)
                for record in self.records
                if record.evaluation_attempt_id is not None
            }
        )

    @property
    def evaluated_trial_counts_by_generation(self) -> tuple[int, int]:
        return tuple(
            len(
                {
                    record.trial_ordinal
                    for record in self.records
                    if record.generation == generation
                    and record.evaluation_attempt_id is not None
                }
            )
            for generation in (1, 2)
        )  # type: ignore[return-value]

    @property
    def evaluated_trial_count_provenance(self) -> str:
        return COUNT_PROVENANCE

    def append(self, record: TrialLedgerRecord) -> TrialLedger:
        """Return a new ledger with exactly one next event; never mutate history."""
        if type(record) is not TrialLedgerRecord:
            raise DiscoveryError("append requires an exact ledger record")
        if record.event_ordinal != len(self.records) + 1:
            raise DiscoveryError(
                "append event ordinal must follow the existing history"
            )
        return TrialLedger(self.records + (record,))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": LEDGER_SCHEMA,
            "ledger_id": self.ledger_id,
            "records": [record.to_dict() for record in self.records],
            "evaluated_trial_count": self.evaluated_trial_count,
            "evaluated_trial_count_by_generation": list(
                self.evaluated_trial_counts_by_generation
            ),
            "evaluated_trial_count_provenance": self.evaluated_trial_count_provenance,
        }

    def to_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_dict(cls, raw: object) -> TrialLedger:
        try:
            row = _exact(
                raw,
                {
                    "schema",
                    "ledger_id",
                    "records",
                    "evaluated_trial_count",
                    "evaluated_trial_count_by_generation",
                    "evaluated_trial_count_provenance",
                },
            )
            if row["schema"] != LEDGER_SCHEMA or type(row["records"]) is not list:
                raise DiscoveryError("unsupported ledger schema")
            if type(row["evaluated_trial_count"]) is not int or (
                type(row["evaluated_trial_count_by_generation"]) is not list
                or len(row["evaluated_trial_count_by_generation"]) != 2
                or any(
                    type(count) is not int
                    for count in row["evaluated_trial_count_by_generation"]
                )
                or type(row["evaluated_trial_count_provenance"]) is not str
            ):
                raise DiscoveryError("ledger count fields have invalid types")
            records = tuple(
                TrialLedgerRecord.from_dict(item) for item in row["records"]
            )
            ledger = cls(records)
            if (
                row["ledger_id"] != ledger.ledger_id
                or row["evaluated_trial_count"] != ledger.evaluated_trial_count
                or row["evaluated_trial_count_by_generation"]
                != list(ledger.evaluated_trial_counts_by_generation)
                or row["evaluated_trial_count_provenance"] != COUNT_PROVENANCE
                or canonical_json_bytes(ledger.to_dict()) != canonical_json_bytes(row)
            ):
                raise DiscoveryError("ledger identity or derived count disagrees")
            return ledger
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise DiscoveryError("invalid canonical trial ledger") from None

    @classmethod
    def from_bytes(cls, body: bytes) -> TrialLedger:
        raw = _parse_canonical_object(body, MAX_LEDGER_BYTES)
        return cls.from_dict(raw)


def _validate_record_bindings(record: TrialLedgerRecord) -> None:
    attempted = record.evaluation_attempt_id is not None
    source_pair = (
        record.evaluation_source_head is not None,
        record.evaluation_source_tree is not None,
    )
    if source_pair not in ((False, False), (True, True)):
        raise DiscoveryError("evaluation source HEAD and tree must be bound together")
    if attempted:
        if (
            not all(source_pair)
            or record.dataset_evidence_id is None
            or record.evaluation_id is None
        ):
            raise DiscoveryError("evaluation attempt lacks exact source/data bindings")
    elif any(
        value is not None
        for value in (
            record.evaluation_source_head,
            record.evaluation_source_tree,
            record.dataset_evidence_id,
            record.evaluation_id,
            record.result_id,
        )
    ):
        raise DiscoveryError("pre-evaluation record cannot carry result bindings")
    if record.pnl_visible and record.result_id is None:
        raise DiscoveryError("P&L visibility requires a deterministic result id")
    if record.diagnostic_visible and record.terminal_diagnostic_code is None:
        raise DiscoveryError("diagnostic visibility requires a terminal diagnostic")
    if record.disposition is TrialDisposition.ACCEPTED_FOR_EVALUATION:
        if (
            attempted
            or record.terminal_diagnostic_code is not None
            or record.pnl_visible
            or record.diagnostic_visible
        ):
            raise DiscoveryError("accepted-for-evaluation is a pre-evaluation event")
        return
    if record.terminal_diagnostic_code is None or (
        type(record.terminal_diagnostic_code) is not str
        or _DIAGNOSTIC.fullmatch(record.terminal_diagnostic_code) is None
    ):
        raise DiscoveryError("terminal disposition requires a bounded diagnostic code")
    if record.disposition is TrialDisposition.DUPLICATE_REJECTED:
        if (
            attempted
            or record.terminal_diagnostic_code != "DUPLICATE_SEMANTIC_PROGRAM"
            or record.pnl_visible
            or record.diagnostic_visible
        ):
            raise DiscoveryError("duplicate rejection must be pre-evaluation")
    elif record.disposition is TrialDisposition.INVALID:
        if attempted or record.pnl_visible:
            raise DiscoveryError("invalid proposals cannot be evaluated")
    elif record.disposition is TrialDisposition.UNSUPPORTED:
        if attempted or record.pnl_visible:
            raise DiscoveryError("unsupported proposals cannot be evaluated")
    elif record.disposition is TrialDisposition.DETERMINISTIC_EVALUATION_FAILED:
        if not attempted or record.result_id is not None or record.pnl_visible:
            raise DiscoveryError(
                "failed evaluation requires an attempt and no result/P&L"
            )
    elif record.disposition in (
        TrialDisposition.ZERO_TRADE,
        TrialDisposition.ECONOMICALLY_REJECTED,
        TrialDisposition.SHORTLISTED,
    ):
        if not attempted or record.result_id is None:
            raise DiscoveryError("completed evaluation requires a result identity")


def _validate_ledger_history(records: tuple[TrialLedgerRecord, ...]) -> None:
    by_trial: dict[
        tuple[str, int],
        tuple[ResearchProposal | InvalidProposalReference, TrialLedgerRecord, bool],
    ] = {}
    first_program_record: dict[str, str] = {}
    first_invalid_submission: set[str] = set()
    attempt_owner: dict[str, tuple[str, int]] = {}
    visible_g1_output = False
    visible_g2_output = False
    current_generation = 1
    last_trial_ordinal = 0

    for index, record in enumerate(records, start=1):
        if record.event_ordinal != index:
            raise DiscoveryError("ledger event ordinals must be contiguous and ordered")
        trial_key = (record.proposal_id, record.trial_ordinal)
        prior = by_trial.get(trial_key)
        if prior is not None:
            prior_proposal, prior_record, terminal = prior
            if (
                record.proposal != prior_proposal
                or terminal
                or prior_record.disposition
                is not TrialDisposition.ACCEPTED_FOR_EVALUATION
                or record.disposition is TrialDisposition.ACCEPTED_FOR_EVALUATION
                or prior_record.evaluation_attempt_id is not None
                or record.evaluation_attempt_id is None
            ):
                raise DiscoveryError(
                    "proposal progression is not append-only and terminal"
                )
            if record.evaluation_attempt_id in attempt_owner:
                raise DiscoveryError(
                    "evaluation attempt id is already bound to another trial"
                )
            attempt_owner[record.evaluation_attempt_id] = trial_key
            by_trial[trial_key] = (prior_proposal, record, True)
            if record.generation == 1 and (
                record.pnl_visible or record.diagnostic_visible
            ):
                visible_g1_output = True
            if record.generation == 2 and (
                record.pnl_visible or record.diagnostic_visible
            ):
                visible_g2_output = True
            continue

        if record.trial_ordinal != last_trial_ordinal + 1:
            raise DiscoveryError("new trial ordinals must be contiguous and ordered")
        if record.generation < current_generation:
            raise DiscoveryError("generation chronology cannot move backwards")
        if record.generation == 2:
            if current_generation == 1:
                g1_trials = tuple(
                    (prior, terminal)
                    for _, prior, terminal in by_trial.values()
                    if prior.generation == 1
                )
                if not g1_trials:
                    raise DiscoveryError(
                        "Generation 2 requires completed Generation 1 history"
                    )
                if any(not terminal for _, terminal in g1_trials):
                    raise DiscoveryError(
                        "Generation 2 cannot start before all G1 trials are terminal"
                    )
            elif visible_g2_output:
                raise DiscoveryError(
                    "Generation 2 proposals must be frozen "
                    "before confirmation is visible"
                )
            current_generation = 2
            for (
                reference
            ) in record.proposal.information_visibility.visible_generation1_diagnostics:
                parent = by_trial.get(
                    (reference.parent_proposal_id, reference.parent_trial_ordinal)
                )
                if parent is None:
                    raise DiscoveryError("Generation 2 parent must precede its child")
                parent_proposal, parent_record, parent_terminal = parent
                if (
                    parent_proposal.generation != 1
                    or not parent_terminal
                    or parent_record.diagnostic_id != reference.diagnostic_id
                    or not parent_record.diagnostic_visible
                    or parent_record.evaluation_attempt_id is None
                ):
                    raise DiscoveryError(
                        "Generation 2 diagnostic is not an earlier visible G1 result"
                    )
        elif current_generation == 2 or visible_g1_output:
            raise DiscoveryError(
                "Generation 1 proposals must be frozen before G2/results"
            )

        if type(record.proposal) is InvalidProposalReference:
            if record.proposal_id in first_invalid_submission:
                if record.disposition is not TrialDisposition.DUPLICATE_REJECTED:
                    raise DiscoveryError(
                        "repeated invalid submission must be duplicate-rejected"
                    )
            else:
                if record.disposition is not TrialDisposition.INVALID:
                    raise DiscoveryError(
                        "first malformed submission must be retained as invalid"
                    )
                first_invalid_submission.add(record.proposal_id)
        else:
            semantic_program_id = record.semantic_program_id
            assert semantic_program_id is not None
            existing_program = first_program_record.get(semantic_program_id)
            if existing_program is None:
                if record.disposition is TrialDisposition.DUPLICATE_REJECTED:
                    raise DiscoveryError(
                        "first occurrence cannot be duplicate-rejected"
                    )
                first_program_record[semantic_program_id] = record.proposal_id
                if (
                    record.proposal.semantic_status
                    is ProposalSemanticStatus.UNSUPPORTED
                ):
                    if record.disposition is not TrialDisposition.UNSUPPORTED:
                        raise DiscoveryError(
                            "first deferred family must be recorded unsupported"
                        )
                elif record.disposition is TrialDisposition.UNSUPPORTED:
                    raise DiscoveryError(
                        "supported family cannot be dispositioned unsupported"
                    )
            elif (
                record.disposition is not TrialDisposition.DUPLICATE_REJECTED
                or record.evaluation_attempt_id is not None
            ):
                raise DiscoveryError(
                    "repeated program semantics must be retained "
                    "as a duplicate rejection"
                )

        if record.evaluation_attempt_id is not None:
            if record.evaluation_attempt_id in attempt_owner:
                raise DiscoveryError(
                    "evaluation attempt id is already bound to another trial"
                )
            attempt_owner[record.evaluation_attempt_id] = trial_key
        by_trial[trial_key] = (
            record.proposal,
            record,
            record.disposition is not TrialDisposition.ACCEPTED_FOR_EVALUATION,
        )
        if record.generation == 1 and (record.pnl_visible or record.diagnostic_visible):
            visible_g1_output = True
        if record.generation == 2 and (record.pnl_visible or record.diagnostic_visible):
            visible_g2_output = True
        last_trial_ordinal = record.trial_ordinal

    evaluated_by_generation = {1: 0, 2: 0}
    evaluated_g1_by_family: dict[StrategyFamily, int] = {}
    for proposal, record, terminal in by_trial.values():
        if terminal and record.evaluation_attempt_id is not None:
            evaluated_by_generation[record.generation] += 1
            if record.generation == 1:
                if type(proposal) is not ResearchProposal:
                    raise DiscoveryError("invalid submissions cannot be evaluated")
                evaluated_g1_by_family[proposal.family] = (
                    evaluated_g1_by_family.get(proposal.family, 0) + 1
                )

    if (
        evaluated_by_generation[1] > GENERATION_1_MAX_EVALUATED
        or evaluated_by_generation[2] > GENERATION_2_MAX_EVALUATED
    ):
        raise DiscoveryError("evaluated trial count exceeds the frozen campaign budget")
    if any(
        count > GENERATION_1_MAX_PER_FAMILY for count in evaluated_g1_by_family.values()
    ):
        raise DiscoveryError("family exceeds one quarter of the Generation 1 budget")


def _proposal_id(proposal: ResearchProposal) -> str:
    material = {
        "identity_version": PROPOSAL_IDENTITY_VERSION,
        "schema": PROPOSAL_SCHEMA,
        "campaign_version": proposal.campaign_version,
        "generation": proposal.generation,
        "proposal_kind": proposal.proposal_kind.value,
        "parent_proposal_ids": list(proposal.parent_proposal_ids),
        "strategy_spec": proposal.strategy_spec.to_dict(),
        "hypothesis": proposal.hypothesis,
        "expected_mechanism": proposal.expected_mechanism,
        "falsification_condition": proposal.falsification_condition,
        "source_reference_labels": list(proposal.source_reference_labels),
        "information_visibility": proposal.information_visibility.to_dict(),
    }
    return str(
        uuid5(_PROPOSAL_NAMESPACE, canonical_json_bytes(material).decode("utf-8"))
    )


def _ledger_id(records: tuple[TrialLedgerRecord, ...]) -> str:
    material = {
        "identity_version": LEDGER_IDENTITY_VERSION,
        "schema": LEDGER_SCHEMA,
        "records": [record.to_dict() for record in records],
    }
    return str(uuid5(_LEDGER_NAMESPACE, canonical_json_bytes(material).decode("utf-8")))


def _strategy_spec_from_dict(raw: object) -> StrategySpec:
    if type(raw) is not dict or type(raw.get("schema")) is not str:
        raise DiscoveryError("strategy specification requires a closed schema")
    schema = raw["schema"]
    if schema == _FamilySpecSchema.MOVING_AVERAGE_TREND.value:
        row = _exact(
            raw,
            {"schema", "family", "fast_window", "slow_window", "rule"},
        )
        if row["family"] != StrategyFamily.MOVING_AVERAGE_TREND.value:
            raise DiscoveryError("moving-average family/schema mismatch")
        return MovingAverageTrendSpec(
            fast_window=row["fast_window"],
            slow_window=row["slow_window"],
            rule=_enum(MovingAverageRule, row["rule"], "moving-average rule"),
        )
    if schema == _FamilySpecSchema.DONCHIAN_BREAKOUT.value:
        row = _exact(
            raw,
            {
                "schema",
                "family",
                "fast_window",
                "slow_window",
                "channel_lookback_sessions",
            },
        )
        if row["family"] != StrategyFamily.DONCHIAN_BREAKOUT.value:
            raise DiscoveryError("Donchian family/schema mismatch")
        return DonchianBreakoutSpec(
            fast_window=row["fast_window"],
            slow_window=row["slow_window"],
            channel_lookback_sessions=row["channel_lookback_sessions"],
        )
    if schema == _FamilySpecSchema.DEFERRED.value:
        row = _exact(raw, {"schema", "family", "deferred_reason"})
        if row["deferred_reason"] != "NO_ACCEPTED_STANDALONE_EVALUATOR":
            raise DiscoveryError("unsupported deferred-family reason")
        return DeferredStrategySpec(
            _enum(StrategyFamily, row["family"], "strategy family")
        )
    raise DiscoveryError("unknown strategy specification schema")


def _visibility_from_dict(raw: object) -> InformationVisibility:
    row = _exact(
        raw,
        {
            "stage",
            "visible_evidence",
            "visible_generation1_diagnostics",
            "confirmation_results_visible",
            "final_holdout_accessed",
        },
    )
    if (
        type(row["visible_evidence"]) is not list
        or type(row["visible_generation1_diagnostics"]) is not list
    ):
        raise DiscoveryError("visible evidence and diagnostic lists required")
    evidence = tuple(
        VisibleEvidenceReference(
            reference_label=_exact(
                item,
                {
                    "reference_label",
                    "dataset_label",
                    "timeframe",
                    "time_partition",
                    "classification",
                },
            )["reference_label"],
            dataset_label=item["dataset_label"],
            timeframe=_enum(VisibleTimeframe, item["timeframe"], "visible timeframe"),
            time_partition=_enum(
                VisibleTimePartition, item["time_partition"], "visible time partition"
            ),
            classification=_enum(
                VisibleEvidenceClassification,
                item["classification"],
                "visible evidence classification",
            ),
        )
        for item in row["visible_evidence"]
    )
    diagnostics = tuple(
        Generation1DiagnosticReference(
            parent_proposal_id=_exact(
                item,
                {"parent_proposal_id", "parent_trial_ordinal", "diagnostic_id"},
            )["parent_proposal_id"],
            parent_trial_ordinal=item["parent_trial_ordinal"],
            diagnostic_id=item["diagnostic_id"],
        )
        for item in row["visible_generation1_diagnostics"]
    )
    return InformationVisibility(
        stage=_enum(VisibilityStage, row["stage"], "visibility stage"),
        visible_evidence=evidence,
        visible_generation1_diagnostics=diagnostics,
        confirmation_results_visible=row["confirmation_results_visible"],
        final_holdout_accessed=row["final_holdout_accessed"],
    )


def _parse_canonical_object(body: bytes, maximum_bytes: int) -> dict[str, object]:
    try:
        if type(body) is not bytes or not 0 < len(body) <= maximum_bytes:
            raise ValueError
        raw = json.loads(
            body, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(raw) is not dict or canonical_json_bytes(raw) != body:
            raise ValueError
        return raw
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise DiscoveryError("invalid bounded canonical JSON object") from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def _exact(value: object, names: set[str]) -> dict[str, object]:
    if type(value) is not dict or set(value) != names:
        raise DiscoveryError("unexpected or missing fields")
    return value


def _enum(enum_type: type[StrEnum], value: object, label: str) -> StrEnum:
    if type(value) is not str:
        raise DiscoveryError(f"{label} must be text")
    try:
        return enum_type(value)
    except ValueError:
        raise DiscoveryError(f"unknown {label}") from None


def _string_tuple(value: object) -> tuple[str, ...]:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise DiscoveryError("string list required")
    return tuple(value)


def _validate_pair(fast: object, slow: object) -> None:
    if (
        type(fast) is not int
        or type(slow) is not int
        or (fast, slow) not in _SUPPORTED_PAIRS
    ):
        raise DiscoveryError("moving-average pair is outside the accepted finite set")


def _bounded_positive_int(value: object, maximum: int, label: str) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise DiscoveryError(f"{label} must be a bounded positive integer")


def _validate_text(value: object, label: str) -> None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > MAX_TEXT_LENGTH
        or any(ord(character) < 32 for character in value)
    ):
        raise DiscoveryError(f"{label} must be bounded canonical text")


def _validate_label(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) > MAX_LABEL_LENGTH
        or _LABEL.fullmatch(value) is None
    ):
        raise DiscoveryError(f"{label} must be a bounded stable label")


def _validate_labels(value: object, label: str) -> None:
    if type(value) is not tuple or not value:
        raise DiscoveryError(f"{label} must be a nonempty immutable tuple")
    for item in value:
        _validate_label(item, label)
    if len(set(value)) != len(value):
        raise DiscoveryError(f"{label} cannot contain duplicates")


def _uuid5_text(value: object, label: str) -> None:
    try:
        if type(value) is not str:
            raise ValueError
        parsed = UUID(value)
        if str(parsed) != value or parsed.version != 5:
            raise ValueError
    except (ValueError, TypeError):
        raise DiscoveryError(f"{label} must be a canonical UUID5") from None


def _optional_git(value: object, label: str) -> None:
    if value is not None and (
        type(value) is not str or _SHA40.fullmatch(value) is None
    ):
        raise DiscoveryError(f"{label} must be lowercase 40-hex")
