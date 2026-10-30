"""Bounded read-only desktop campaign adapter for the existing Research page."""

import json
from decimal import Decimal
from pathlib import Path

from trading_bot.experiments.desktop_research_campaign import (
    MAX_ARTIFACT_BYTES,
    DesktopCampaignBundle,
    _read,
    rank_development,
)
from trading_bot.gui.models import (
    ResearchPageState,
    ResearchReportStatus,
    ResearchReportView,
    ResearchResultRow,
)
from trading_bot.gui.research_service import (
    CompactReportResearchService,
    _bounded_source_path,
    _is_supported_local_json_path,
    unavailable_research_state,
)


class DesktopCampaignResearchService:
    """Read an artifact only; never construct storage or execute a campaign."""

    def __init__(self, artifact_path: Path) -> None:
        if not isinstance(artifact_path, Path):
            raise TypeError("artifact_path must be pathlib.Path")
        self._path = artifact_path

    def get_research_state(self) -> ResearchPageState:
        try:
            if not _is_supported_local_json_path(self._path):
                raise ValueError
            bundle = DesktopCampaignBundle.from_bytes(_read(self._path))
            walks = {w.candidate_id: w for w in bundle.walk_forward}
            ranks = {
                row.candidate_id: rank
                for rank, row in enumerate(rank_development(bundle.development), 1)
            }
            rows = []
            for ordinal, result in enumerate(bundle.development):
                walk = walks.get(result.candidate_id)
                tests = () if walk is None else walk.test_evidence
                summary = {} if walk is None else walk.to_dict()
                config = result.definition.strategy_config
                rows.append(
                    ResearchResultRow(
                        caller_ordinal=ordinal,
                        rank=ranks[result.candidate_id],
                        variant_label=f"MA {config.short_window}/{config.long_window}",
                        parameter_label=(
                            f"short_window={config.short_window}, "
                            f"long_window={config.long_window}"
                        ),
                        total_return=result.evidence.total_return,
                        maximum_drawdown_percentage=result.evidence.maximum_drawdown_percentage,
                        aggregate_one_way_turnover=None,
                        total_fills=result.total_fills,
                        exposure=None,
                        return_over_drawdown=None,
                        performance_turnover=result.turnover,
                        closed_trade_count=result.closed_trade_count,
                        walk_forward_fold_count=None if walk is None else len(tests),
                        minimum_walk_forward_return=None
                        if walk is None
                        else Decimal(summary["minimum_fold_return"]),
                        median_walk_forward_return=None
                        if walk is None
                        else Decimal(summary["median_fold_return"]),
                        maximum_walk_forward_drawdown=None
                        if walk is None
                        else Decimal(summary["maximum_fold_drawdown"]),
                        shortlisted=walk is not None,
                        research_only_leader=ranks[result.candidate_id] == 1,
                    )
                )
            return ResearchPageState(
                ResearchReportStatus.LOADED,
                "Desktop OPEN campaign loaded read-only. "
                "Research only; no trading authority.",
                ResearchReportView(
                    report_id=bundle.bundle_id,
                    experiment_result_id=bundle.campaign_id,
                    variant_source="DESKTOP_OPEN_CAMPAIGN",
                    ranking_summary=(
                        "Development return descending; drawdown ascending; "
                        "short/long ascending. Top 32 walk-forward. "
                        "Research-only leader."
                    ),
                    metadata_summary=(
                        "OPEN only; snapshot "
                        f"{bundle.dataset_binding.snapshot_identity}; "
                        "FINAL_HOLDOUT sealed; walk-forward qualification not applied."
                    ),
                    rows=tuple(rows),
                    source_path=_bounded_source_path(self._path),
                ),
            )
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            return ResearchPageState(
                ResearchReportStatus.UNAVAILABLE,
                "No valid bounded desktop research campaign is available.",
                None,
            )


class ResearchArtifactService:
    """Add campaign loading while retaining the compact-report service unchanged."""

    def __init__(self, artifact_path: Path) -> None:
        if not isinstance(artifact_path, Path):
            raise TypeError("artifact_path must be pathlib.Path")
        self._path = artifact_path

    def get_research_state(self) -> ResearchPageState:
        # A small bounded schema probe; malformed input stays unavailable.
        try:
            if not _is_supported_local_json_path(self._path):
                raise ValueError
            with self._path.open("rb") as handle:
                body = handle.read(MAX_ARTIFACT_BYTES + 1)
            if len(body) > MAX_ARTIFACT_BYTES:
                raise ValueError
            raw = json.loads(body)
            if (
                type(raw) is dict
                and raw.get("schema") == "desktop-research-campaign/v1"
            ):
                return DesktopCampaignResearchService(self._path).get_research_state()
        except (OSError, ValueError, RecursionError):
            return unavailable_research_state()
        return CompactReportResearchService(self._path).get_research_state()
