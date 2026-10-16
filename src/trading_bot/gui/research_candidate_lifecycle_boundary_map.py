"""Pure presentation of the retained research lifecycle boundaries."""

from dataclasses import dataclass

from trading_bot.gui.research_candidate_lifecycle_audit import (
    LifecycleAuditPresentation,
)


@dataclass(frozen=True, slots=True)
class LifecycleBoundaryRow:
    """One read-only boundary fact and its non-authoritative meaning."""

    boundary: str
    recorded_status: str
    authority_meaning: str

    def __post_init__(self) -> None:
        if any(
            type(value) is not str or not value
            for value in (self.boundary, self.recorded_status, self.authority_meaning)
        ):
            raise TypeError("Exact boundary presentation text required")


@dataclass(frozen=True, slots=True)
class LifecycleBoundaryMapPresentation:
    """Immutable rows for the lifecycle boundary map."""

    rows: tuple[LifecycleBoundaryRow, ...] = ()

    def __post_init__(self) -> None:
        if type(self.rows) is not tuple or any(
            type(row) is not LifecycleBoundaryRow for row in self.rows
        ):
            raise TypeError("Exact immutable boundary rows required")


def compose_lifecycle_boundary_map(
    audit: LifecycleAuditPresentation,
) -> LifecycleBoundaryMapPresentation:
    """Map retained A17 presentation facts without acquiring or rechecking them."""
    if type(audit) is not LifecycleAuditPresentation:
        raise TypeError("Exact lifecycle audit presentation required")
    if not audit.artifacts:
        return LifecycleBoundaryMapPresentation()
    return LifecycleBoundaryMapPresentation(
        rows=(
            LifecycleBoundaryRow(
                "Local canonical artifacts",
                "VERIFIED_LOCAL",
                "A16 retained local artifact identities; this is not "
                "source acceptance.",
            ),
            LifecycleBoundaryRow(
                "Local SHADOW successor linkage",
                "VERIFIED_LOCAL",
                "The retained immutable linkage is local evidence; no new "
                "lifecycle state is created.",
            ),
            LifecycleBoundaryRow(
                "Retained source provenance",
                "RECORDED",
                "Retained HEAD/TREE values are provenance only; they do not "
                "establish remote acceptance.",
            ),
            LifecycleBoundaryRow(
                "Qualification coverage",
                "RECORDED_SATISFIED",
                "A17 retained B2 coverage facts meeting their minima; coverage "
                "is descriptive only and does not establish profitability, "
                "quality, or readiness.",
            ),
            LifecycleBoundaryRow(
                "Observation effects",
                "RECORDED_ZERO",
                "A17 retained nine zero counters as presentation facts; they "
                "grant no operational authority or observation-origin claim.",
            ),
            LifecycleBoundaryRow(
                "Full historical/external chain",
                "NOT_REVERIFIED",
                "Complete historical and external qualification was not re-run "
                "by this GUI.",
            ),
            LifecycleBoundaryRow(
                "Real observation acquisition",
                "NOT_CONNECTED",
                "No real observation or provider acquisition boundary is connected.",
            ),
            LifecycleBoundaryRow(
                "Production compatibility",
                "NOT_ESTABLISHED",
                "Production compatibility and strategy selection are not established.",
            ),
            LifecycleBoundaryRow(
                "PAPER_CANDIDATE",
                "NOT_MATERIALIZED",
                "No later research lifecycle stage is materialized by this page.",
            ),
            LifecycleBoundaryRow(
                "AWAITING_HUMAN_PROMOTION",
                "NOT_MATERIALIZED",
                "No later research lifecycle stage is materialized by this page.",
            ),
            LifecycleBoundaryRow(
                "Automatic promotion",
                "DISABLED",
                "No automatic stage advancement or promotion control exists.",
            ),
            LifecycleBoundaryRow(
                "Promotion authority",
                "NOT_CONNECTED",
                "No promotion authority boundary is connected.",
            ),
            LifecycleBoundaryRow(
                "Trading authority",
                "NONE",
                "No paper, broker, or live trading authority is connected.",
            ),
        )
    )
