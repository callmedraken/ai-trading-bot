"""Pure research projection and bounded explicit report reading for R12."""

from __future__ import annotations

from pathlib import Path

from trading_bot.experiments.filtered_trend_campaign import decimal_text
from trading_bot.experiments.filtered_trend_comparison_bundle_v2 import (
    ResearchComparisonBundle,
    _read_comparison_bundle,
)
from trading_bot.experiments.filtered_trend_comparison_campaign_v2 import (
    CandidateEvidenceStatus,
    ComparisonSummary,
    qualifies_candidate,
)
from trading_bot.live_prototype.contracts import CandidateView, ResearchView


def to_research_view(bundle: ResearchComparisonBundle) -> ResearchView:
    """Project already-validated cached evidence without I/O or selection effects."""
    if type(bundle) is not ResearchComparisonBundle:
        raise TypeError("bundle must be an exact ResearchComparisonBundle")
    control = bundle.summaries[0]
    candidates = tuple(
        _candidate_view(summary, control) for summary in bundle.summaries
    )
    context = bundle.context
    assumptions = tuple(
        f"{key}: {value}" for key, value in sorted(context["economics"].items())
    ) + ("Reused history is robustness evidence, not a fresh holdout.",)
    return ResearchView(
        candidates=candidates,
        selected=bundle.selected_candidate,
        policy=context["qualification_policy"],
        bundle_digest=bundle.digest,
        dataset_digest=context["dataset_id"],
        assumptions=assumptions,
        prior_trials=context["prior_configurations"],
        new_trials=context["comparison_configurations"],
        live_eligible=False,
    )


def read_comparison_report(path: Path) -> ResearchView:
    """Read a supplied bounded path on a worker or return fixed unavailable state."""
    try:
        bundle = _read_comparison_bundle(path)
        return to_research_view(bundle)
    except Exception:
        # Error text can contain a path or report contents; never expose it in the UI.
        return _unavailable_view()


def _unavailable_view() -> ResearchView:
    return ResearchView(
        selected="UNAVAILABLE",
        assumptions=("Comparison report unavailable",),
        live_eligible=False,
    )


def _candidate_view(
    summary: ComparisonSummary,
    control: ComparisonSummary,
) -> CandidateView:
    if summary.status is CandidateEvidenceStatus.FAILED_INCOMPLETE:
        assert summary.failure_code is not None
        return CandidateView(
            candidate=summary.candidate.value,
            qualified=False,
            reasons=(summary.failure_code,),
        )
    is_control = summary.candidate.value == "BASE_MA35_50_V1"
    qualified = not is_control and qualifies_candidate(summary, control)
    if is_control:
        reasons = ("CONTROL",)
    elif qualified:
        reasons = ()
    else:
        reasons = ("QUALIFICATION_FAILED",)
    assert summary.base is not None
    assert summary.stress is not None
    return CandidateView(
        candidate=summary.candidate.value,
        base_return=decimal_text(summary.base.median_continuous_return),
        stress_return=decimal_text(summary.stress.median_continuous_return),
        stress_drawdown=decimal_text(summary.stress.worst_continuous_drawdown),
        turnover=decimal_text(summary.stress.median_turnover),
        qualified=qualified,
        reasons=reasons,
    )
