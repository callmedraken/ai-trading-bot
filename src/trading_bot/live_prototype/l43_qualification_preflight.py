"""Read-only Q1 qualification over the accepted Architecture 147 seams."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Final

from trading_bot.live_prototype.alpaca_signal_inputs import SignalDecision
from trading_bot.live_prototype.durable_state import (
    ENTRY_LIMIT,
    IntentKind,
    IntentStatus,
    OrderState,
)
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43PlanKind,
    L43PreEffectBlocker,
    L43PreEffectDependencies,
    L43PreEffectOutcome,
    L43PreEffectPlan,
    L43PreEffectResult,
    observe_l43_pre_effect,
)
from trading_bot.live_prototype.l43_production_owner import (
    L43ContinuityResult,
    L43ProductionOwner,
    L43Provenance,
    L43SourceIdentity,
    Q62JournalOrigin,
)
from trading_bot.live_prototype.l43_state import (
    L43StateSnapshot,
    origin_anchor_from_q62,
)
from trading_bot.robinhood_mcp.l43_production_composition import (
    L43ProductionPreEffectComposition,
)

CHECKPOINT: Final = "ARCH147-L43-Q1_QUALIFICATION_PREFLIGHT_SOURCE"
SCHEMA: Final = "arch147-l43-qualification-preflight/v1"
CHALLENGE_SCHEMA: Final = "arch147-l43-qualification-challenge/v1"
RHC4_C2_HEAD: Final = "4f560a74b04ecba85c7b312364a9e4e7b30e57b6"
RHC4_C2_TREE: Final = "b422ef66d88b184bdbe12788546e6b2ffd083846"
ENTRY_RISK_USD: Final = Decimal("10.00")
ENTRY_STAGE: Final = "ENTRY_PLACEMENT"
_HEX40: Final = re.compile(r"[0-9a-f]{40}\Z")
_HEX64: Final = re.compile(r"[0-9a-f]{64}\Z")
_REASON: Final = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_USD_TEXT: Final = re.compile(r"-?(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,2})?\Z")


class QualificationOutcome(StrEnum):
    READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW = (
        "READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW"
    )
    NO_ACTION_SIGNAL = "NO_ACTION_SIGNAL"
    PENDING_SETTLEMENT_REQUIRED = "PENDING_SETTLEMENT_REQUIRED"
    MANUAL_CLOSE_REQUIRED = "MANUAL_CLOSE_REQUIRED"
    BLOCKED = "BLOCKED"


_SourceAncestryCheck = Callable[[Path, L43SourceIdentity], bool]
_OUTCOME_VALUES = frozenset(item.value for item in QualificationOutcome)
_EFFECT_COUNTER_KEYS = frozenset(
    "review placement cancellation broker_mutation durable_state_mutation "
    "q62_journal_mutation".split()
)
_CALL_COUNTER_KEYS = frozenset(
    "robinhood_reads robinhood_pages alpaca_provider_calls credential_reads".split()
)
_RESULT_KEYS = frozenset(
    "schema checkpoint status outcome reason_codes source_head source_tree "
    "config_digest binding_digest q62_journal_digest durable_state_sequence "
    "durable_state_tail_digest fresh_pre_effect_facts_digest account_fingerprint "
    "target_session plan_binding_digest requested_entry_usd stage challenge_sha256 "
    "provider_call_counts effect_counters automatic_retry".split()
)


@dataclass(slots=True)
class _Context:
    origin: Q62JournalOrigin | None = None
    requested_entry_usd: Decimal | None = None
    source: L43SourceIdentity | None = None
    snapshot: L43StateSnapshot | None = None
    pre_effect: L43PreEffectResult | None = None
    counts_unknown: bool = False

    def result(
        self,
        outcome: QualificationOutcome,
        reasons: tuple[str, ...],
        *,
        challenge: str | None = None,
    ) -> dict[str, object]:
        return _safe_result(self, outcome, reasons, challenge=challenge)


def _run_protected_preflight() -> dict[str, object]:
    """The sole runner-owned production entry point; accepts no caller facts."""

    context = _Context(requested_entry_usd=ENTRY_RISK_USD)
    root = Path(__file__).resolve().parents[3]
    try:
        composition = L43ProductionPreEffectComposition.for_production(repo_root=root)
    except Exception:
        return context.result(
            QualificationOutcome.BLOCKED, ("COMPOSITION_UNAVAILABLE",)
        )
    context.origin = composition.origin
    return _evaluate_qualification(
        context=context,
        dependencies=composition.dependencies,
        root=root,
        ancestry_check=_has_accepted_rhc4_ancestor,
    )


def _evaluate_qualification(
    *,
    context: _Context,
    dependencies: L43PreEffectDependencies,
    root: Path,
    ancestry_check: _SourceAncestryCheck,
) -> dict[str, object]:
    """Private dependency-injected core used by deterministic fake tests."""

    origin = context.origin
    try:
        if (
            type(dependencies) is not L43PreEffectDependencies
            or type(origin) is not Q62JournalOrigin
            or dependencies.origin != origin
        ):
            return context.result(
                QualificationOutcome.BLOCKED, ("CANONICAL_ORIGIN_UNAVAILABLE",)
            )
        source = dependencies.source_reader()
        if type(source) is not L43SourceIdentity:
            return context.result(QualificationOutcome.BLOCKED, ("SOURCE_UNAVAILABLE",))
        context.source = source
        if not ancestry_check(root, source):
            return context.result(
                QualificationOutcome.BLOCKED, ("RHC4_C2_ANCESTRY_UNPROVEN",)
            )
        snapshot = dependencies.state_snapshot_reader()
        if type(snapshot) is not L43StateSnapshot or not _valid_snapshot(
            snapshot, origin
        ):
            return context.result(
                QualificationOutcome.BLOCKED, ("STATE_SNAPSHOT_UNAVAILABLE",)
            )
        context.snapshot = snapshot

        early = _state_gate(snapshot)
        if early is not None:
            if not _source_continuity_accepted(dependencies, origin, source):
                return context.result(
                    QualificationOutcome.BLOCKED, ("CONTINUITY_UNPROVEN",)
                )
            after_source = dependencies.source_reader()
            after_snapshot = dependencies.state_snapshot_reader()
            if (
                type(after_source) is not L43SourceIdentity
                or after_source != source
                or type(after_snapshot) is not L43StateSnapshot
                or not _same_snapshot(snapshot, after_snapshot)
            ):
                return context.result(
                    QualificationOutcome.BLOCKED, ("SOURCE_OR_STATE_DRIFT",)
                )
            return context.result(*early)

        risk = context.requested_entry_usd
        if not _valid_entry_risk(risk):
            return context.result(QualificationOutcome.BLOCKED, ("ENTRY_RISK_INVALID",))

        context.pre_effect = observe_l43_pre_effect(
            dependencies,
            requested_entry_risk=risk,
        )
        after_source = dependencies.source_reader()
        after_snapshot = dependencies.state_snapshot_reader()
        if type(after_source) is not L43SourceIdentity or after_source != source:
            return context.result(QualificationOutcome.BLOCKED, ("SOURCE_CHANGED",))
        if type(after_snapshot) is not L43StateSnapshot or not _same_snapshot(
            snapshot, after_snapshot
        ):
            return context.result(QualificationOutcome.BLOCKED, ("STATE_TAIL_CHANGED",))
        return _classify_observation(context)
    except Exception:
        context.counts_unknown = (
            context.pre_effect is None and context.source is not None
        )
        return context.result(
            QualificationOutcome.BLOCKED, ("QUALIFICATION_INDETERMINATE",)
        )


def _state_gate(
    snapshot: L43StateSnapshot,
) -> tuple[QualificationOutcome, tuple[str, ...]] | None:
    state = snapshot.state
    orders = ((state.entry, IntentKind.ENTRY), (state.exit, IntentKind.EXIT))
    pending: list[OrderState] = []
    seen_intents: set[str] = set()
    seen_provider_ids: set[str] = set()
    for order, expected_kind in orders:
        if order is None:
            continue
        if (
            type(order) is not OrderState
            or order.kind is not expected_kind
            or not isinstance(order.status, IntentStatus)
            or not isinstance(order.intent_id, str)
            or not order.intent_id
            or order.intent_id in seen_intents
        ):
            return QualificationOutcome.BLOCKED, ("ORDER_STATE_UNSUPPORTED",)
        seen_intents.add(order.intent_id)
        provider_id = order.provider_order_id
        if provider_id is not None:
            if (
                not isinstance(provider_id, str)
                or not provider_id
                or provider_id in seen_provider_ids
            ):
                return QualificationOutcome.BLOCKED, ("ORDER_BINDING_AMBIGUOUS",)
            seen_provider_ids.add(provider_id)
        if order.status in {
            IntentStatus.RESERVED,
            IntentStatus.MAY_HAVE_OCCURRED,
            IntentStatus.UNKNOWN,
        }:
            return QualificationOutcome.BLOCKED, ("UNRESOLVED_EFFECT",)
        elif order.status in {IntentStatus.WORKING, IntentStatus.PARTIAL}:
            if provider_id is None:
                return QualificationOutcome.BLOCKED, ("UNBOUND_OR_AMBIGUOUS_EFFECT",)
            pending.append(order)
        elif order.status in {
            IntentStatus.FILLED,
            IntentStatus.CANCELED,
            IntentStatus.REJECTED,
        }:
            if provider_id is None:
                return QualificationOutcome.BLOCKED, ("UNBOUND_OR_AMBIGUOUS_EFFECT",)
        else:
            return QualificationOutcome.BLOCKED, ("ORDER_STATE_UNSUPPORTED",)
        if order.kind is IntentKind.ENTRY and not _valid_entry_risk(
            order.requested_dollars
        ):
            return QualificationOutcome.BLOCKED, ("ENTRY_RISK_INVALID",)
        if order.kind is IntentKind.EXIT and (
            type(order.requested_quantity) is not Decimal
            or not order.requested_quantity.is_finite()
            or order.requested_quantity <= 0
        ):
            return QualificationOutcome.BLOCKED, ("EXIT_QUANTITY_INVALID",)

    if state.blocked_reason is not None:
        return QualificationOutcome.BLOCKED, ("STATE_BLOCKED",)
    if pending:
        if len(pending) != 1:
            return QualificationOutcome.BLOCKED, ("ORDER_STATE_AMBIGUOUS",)
        pending_order = pending[0]
        if pending_order.kind is IntentKind.EXIT and (
            state.entry is None
            or state.entry.status
            not in {IntentStatus.FILLED, IntentStatus.CANCELED, IntentStatus.REJECTED}
            or state.owned_quantity <= 0
        ):
            return QualificationOutcome.BLOCKED, ("ORDER_STATE_AMBIGUOUS",)
        if pending_order.kind is IntentKind.ENTRY and state.exit is not None:
            return QualificationOutcome.BLOCKED, ("ORDER_STATE_AMBIGUOUS",)
        return (
            QualificationOutcome.PENDING_SETTLEMENT_REQUIRED,
            ("PENDING_SETTLEMENT_REQUIRED",),
        )
    if snapshot.manual_close_required:
        return (
            QualificationOutcome.MANUAL_CLOSE_REQUIRED,
            ("MANUAL_CLOSE_REQUIRED",),
        )
    if snapshot.manual_follow_up_required:
        return QualificationOutcome.BLOCKED, ("MANUAL_FOLLOW_UP_UNRESOLVED",)
    if snapshot.sell_review_pending or snapshot.review_active:
        return QualificationOutcome.BLOCKED, ("SELL_REVIEW_PENDING",)
    if state.entry is not None or state.entries_used != 0:
        return QualificationOutcome.BLOCKED, ("ENTRY_ALREADY_CONSUMED",)
    if state.exit is not None:
        return QualificationOutcome.BLOCKED, ("EXIT_ALREADY_CONSUMED",)
    if state.baseline_quantity != 0 or state.owned_quantity != 0:
        return QualificationOutcome.BLOCKED, ("STATE_NOT_FLAT",)
    return None


def _classify_observation(context: _Context) -> dict[str, object]:
    source, origin, snapshot, observed = (
        context.source,
        context.origin,
        context.snapshot,
        context.pre_effect,
    )
    if source is None or origin is None or snapshot is None or observed is None:
        return context.result(QualificationOutcome.BLOCKED, ("FACTS_UNAVAILABLE",))
    if observed.outcome is L43PreEffectOutcome.NO_ACTION_SIGNAL:
        return context.result(QualificationOutcome.NO_ACTION_SIGNAL, ())
    if observed.outcome is L43PreEffectOutcome.MANUAL_CLOSE_REQUIRED:
        return context.result(
            QualificationOutcome.MANUAL_CLOSE_REQUIRED, ("MANUAL_CLOSE_REQUIRED",)
        )
    plan = observed.plan
    risk = context.requested_entry_usd
    if (
        observed.outcome is not L43PreEffectOutcome.READY_FOR_L43_ENTRY_EFFECT_REVIEW
        or type(plan) is not L43PreEffectPlan
        or plan.kind is not L43PlanKind.ENTRY
        or plan.current_source != source
        or not plan.provenance.matches(origin.runtime_identity)
        or plan.state_last_sequence != snapshot.last_sequence
        or plan.state_tail_sha256 != snapshot.journal_sha256
        or plan.requested_entry_risk != risk
        or plan.signal.decision is not SignalDecision.BUY
        or not plan.session.proven
        or not plan.recovery.reconciled
        or plan.recovery.unresolved_effects
        or plan.reconciliation_snapshot.identity != origin.runtime_identity
        or plan.reconciliation_snapshot.observed_position != 0
        or plan.reconciliation_snapshot.orders
        or not _valid_entry_risk(risk)
    ):
        reasons = tuple(blocker.value for blocker in observed.blockers)
        return context.result(
            QualificationOutcome.BLOCKED,
            reasons or ("ENTRY_PLAN_UNPROVEN",),
        )
    challenge = _challenge_digest(context, plan)
    return context.result(
        QualificationOutcome.READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW,
        (),
        challenge=challenge,
    )


def _source_continuity_accepted(
    dependencies: L43PreEffectDependencies,
    origin: Q62JournalOrigin,
    source: L43SourceIdentity,
) -> bool:
    if type(dependencies.continuity_owner) is not L43ProductionOwner:
        return False
    identity = origin.runtime_identity
    try:
        provenance = L43Provenance(
            config_digest=identity.config_digest,
            binding_digest=identity.binding_digest,
            account_fingerprint=identity.account_fingerprint,
            strategy=identity.strategy,
            symbol=identity.symbol,
        )
        proof = dependencies.continuity_owner.prove_continuity(
            origin=origin,
            current=source,
            provenance=provenance,
        )
    except Exception:
        return False
    return (
        type(proof) is L43ContinuityResult
        and proof.accepted
        and proof.origin == origin
        and proof.current == source
        and proof.provenance == provenance
    )


def _valid_snapshot(snapshot: L43StateSnapshot, origin: Q62JournalOrigin) -> bool:
    state = snapshot.state
    return (
        snapshot.origin == origin_anchor_from_q62(origin)
        and state.l43_origin == snapshot.origin
        and state.identity == origin.runtime_identity
        and type(snapshot.last_sequence) is int
        and snapshot.last_sequence == state.last_sequence
        and snapshot.journal_sha256 == state.journal_hash
        and snapshot.sell_review_pending == state.sell_review_pending
    )


def _same_snapshot(left: L43StateSnapshot, right: L43StateSnapshot) -> bool:
    return (
        left.origin == right.origin
        and left.state == right.state
        and left.last_sequence == right.last_sequence
        and left.journal_sha256 == right.journal_sha256
        and left.sell_review_pending == right.sell_review_pending
        and left.review_active == right.review_active
        and left.manual_close_required == right.manual_close_required
        and left.manual_follow_up_required == right.manual_follow_up_required
    )


def _valid_entry_risk(value: Decimal | None) -> bool:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        return False
    if value > ENTRY_LIMIT:
        return False
    exponent = value.as_tuple().exponent
    digits = list(value.as_tuple().digits)
    while exponent < 0 and digits and digits[-1] == 0:
        exponent += 1
        digits.pop()
    return max(0, -exponent) <= 2


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _bounded_decimal_text(value: Decimal | None) -> str | None:
    if type(value) is not Decimal or not value.is_finite():
        return None
    digits, exponent = value.as_tuple().digits, value.as_tuple().exponent
    if len(digits) > 64 or abs(exponent) > 64:
        return None
    rendered = _decimal_text(value)
    return rendered if len(rendered) <= 128 else None


def _challenge_digest(context: _Context, plan: L43PreEffectPlan) -> str:
    source, origin, snapshot, observed, risk = (
        context.source,
        context.origin,
        context.snapshot,
        context.pre_effect,
        context.requested_entry_usd,
    )
    if any(item is None for item in (source, origin, snapshot, observed, risk)):
        raise ValueError("READY evidence is incomplete")
    material = {
        "schema": CHALLENGE_SCHEMA,
        "checkpoint": CHECKPOINT,
        "source_head": source.source_head,
        "source_tree": source.source_tree,
        "config_digest": origin.runtime_identity.config_digest,
        "binding_digest": origin.runtime_identity.binding_digest,
        "account_fingerprint": plan.account_fingerprint,
        "target_session": plan.session.target_session,
        "durable_state_sequence": snapshot.last_sequence,
        "durable_state_tail_digest": snapshot.journal_sha256,
        "fresh_pre_effect_facts_digest": observed.evidence_sha256,
        "plan_binding_digest": plan.binding_sha256,
        "requested_entry_usd": _decimal_text(risk),
        "stage": ENTRY_STAGE,
    }
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _safe_result(
    context: _Context,
    outcome: QualificationOutcome,
    reason_codes: tuple[str, ...],
    *,
    challenge: str | None,
) -> dict[str, object]:
    ready = outcome is QualificationOutcome.READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW
    no_action = outcome is QualificationOutcome.NO_ACTION_SIGNAL
    observed = context.pre_effect
    plan = observed.plan if ready and observed is not None else None
    if ready != (plan is not None and challenge is not None):
        raise ValueError("READY requires exactly one plan and challenge")
    result: dict[str, object] = {
        "schema": SCHEMA,
        "checkpoint": CHECKPOINT,
        "status": "PASS" if ready or no_action else "BLOCKED",
        "outcome": outcome.value,
        "reason_codes": reason_codes,
        "source_head": None if context.source is None else context.source.source_head,
        "source_tree": None if context.source is None else context.source.source_tree,
        "config_digest": (
            None
            if context.origin is None
            else context.origin.runtime_identity.config_digest
        ),
        "binding_digest": (
            None
            if context.origin is None
            else context.origin.runtime_identity.binding_digest
        ),
        "q62_journal_digest": (
            None if context.origin is None else context.origin.journal_sha256
        ),
        "durable_state_sequence": (
            None if context.snapshot is None else context.snapshot.last_sequence
        ),
        "durable_state_tail_digest": (
            None if context.snapshot is None else context.snapshot.journal_sha256
        ),
        "fresh_pre_effect_facts_digest": (
            None if observed is None else observed.evidence_sha256
        ),
        "account_fingerprint": None if plan is None else plan.account_fingerprint,
        "target_session": None if plan is None else plan.session.target_session,
        "plan_binding_digest": None if plan is None else plan.binding_sha256,
        "requested_entry_usd": _bounded_decimal_text(context.requested_entry_usd),
        "stage": ENTRY_STAGE if ready else None,
        "challenge_sha256": challenge,
        "provider_call_counts": _provider_call_counts(observed, context.counts_unknown),
        "effect_counters": dict.fromkeys(_EFFECT_COUNTER_KEYS, 0),
        "automatic_retry": "NOT_AUTHORIZED",
    }
    return result


def _provider_call_counts(
    observed: L43PreEffectResult | None,
    unknown: bool,
) -> dict[str, int | None]:
    if observed is None:
        value = None if unknown else 0
        return dict.fromkeys(_CALL_COUNTER_KEYS, value)
    signal_failed = L43PreEffectBlocker.SIGNAL_UNAVAILABLE in observed.blockers
    robinhood_attempted = observed.robinhood_read_count > 0
    return {
        "robinhood_reads": observed.robinhood_read_count,
        "robinhood_pages": observed.robinhood_page_count,
        "alpaca_provider_calls": (
            None if signal_failed else observed.alpaca_provider_call_count
        ),
        "credential_reads": (
            None
            if signal_failed or robinhood_attempted
            else observed.credential_read_count
        ),
    }


def _has_accepted_rhc4_ancestor(root: Path, source: L43SourceIdentity) -> bool:
    if not isinstance(root, Path) or type(source) is not L43SourceIdentity:
        return False
    if _git_text(root, "rev-parse", f"{RHC4_C2_HEAD}^{{tree}}") != RHC4_C2_TREE:
        return False
    process = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "merge-base",
            "--is-ancestor",
            RHC4_C2_HEAD,
            source.source_head,
        ],
        capture_output=True,
        check=False,
        timeout=15,
    )
    return process.returncode == 0


def _git_text(root: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        check=False,
        timeout=15,
    )
    if process.returncode != 0:
        return ""
    try:
        return process.stdout.decode("ascii").strip()
    except (AttributeError, UnicodeDecodeError):
        return ""


def _is_sanitized_result(value: object) -> bool:
    """Validate the exact closed result shape before runner serialization."""
    if type(value) is not dict or set(value) != _RESULT_KEYS:
        return False
    if value["schema"] != SCHEMA or value["checkpoint"] != CHECKPOINT:
        return False
    outcome = value["outcome"]
    if type(outcome) is not str or outcome not in _OUTCOME_VALUES:
        return False
    ready = outcome == "READY_FOR_EXACT_ENTRY_AUTHORIZATION_REVIEW"
    passed = ready or outcome == "NO_ACTION_SIGNAL"
    reasons = value["reason_codes"]
    if type(reasons) is not tuple or any(
        type(item) is not str or _REASON.fullmatch(item) is None for item in reasons
    ):
        return False
    if value["status"] != ("PASS" if passed else "BLOCKED") or passed == bool(reasons):
        return False
    if any(not _optional_hex(value[key], 40) for key in ("source_head", "source_tree")):
        return False
    if any(
        not _optional_hex(value[key], 64)
        for key in (
            "config_digest",
            "binding_digest",
            "q62_journal_digest",
            "durable_state_tail_digest",
            "fresh_pre_effect_facts_digest",
            "account_fingerprint",
            "plan_binding_digest",
            "challenge_sha256",
        )
    ):
        return False
    sequence = value["durable_state_sequence"]
    if sequence is not None and (type(sequence) is not int or sequence < 0):
        return False
    usd = value["requested_entry_usd"]
    if usd is not None and (type(usd) is not str or _USD_TEXT.fullmatch(usd) is None):
        return False
    target = value["target_session"]
    if target is not None and (
        type(target) is not str
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", target) is None
    ):
        return False
    ready_fields = (
        "requested_entry_usd",
        "challenge_sha256",
        "account_fingerprint",
        "target_session",
        "plan_binding_digest",
        "source_head",
        "source_tree",
        "config_digest",
        "binding_digest",
        "q62_journal_digest",
        "fresh_pre_effect_facts_digest",
        "durable_state_sequence",
        "durable_state_tail_digest",
    )
    if ready and (
        value["stage"] != ENTRY_STAGE or any(value[k] is None for k in ready_fields)
    ):
        return False
    if not ready and any(
        value[key] is not None
        for key in (
            "stage",
            "challenge_sha256",
            "account_fingerprint",
            "target_session",
            "plan_binding_digest",
        )
    ):
        return False
    calls, effects = value["provider_call_counts"], value["effect_counters"]
    if type(calls) is not dict or set(calls) != _CALL_COUNTER_KEYS:
        return False
    if any(
        item is not None and (type(item) is not int or item < 0)
        for item in calls.values()
    ):
        return False
    if (
        type(effects) is not dict
        or set(effects) != _EFFECT_COUNTER_KEYS
        or any(type(item) is not int or item != 0 for item in effects.values())
    ):
        return False
    return value["automatic_retry"] == "NOT_AUTHORIZED"


def _optional_hex(value: object, length: int) -> bool:
    if value is None:
        return True
    pattern = _HEX40 if length == 40 else _HEX64
    return type(value) is str and pattern.fullmatch(value) is not None


__all__ = ["_is_sanitized_result", "_run_protected_preflight"]
