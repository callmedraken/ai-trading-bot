"""Pure Architecture-133 single-session Task Scheduler specification.

No scheduler access, installation, retry or trading authority. The action is
only the isolated fixed launcher; all semantic authority stays in publication
and accepted durable wake state. The protected shared Python substrate is
reused, but D10 task/deployment/lease authority is never reused.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.unattended_activation import ReviewPaperActivation

SCHEDULER_SCHEMA = "arch133-review-paper-single-session-task/v1"
TASK_PATH = r"\AITradingBot-Arch133-SingleSessionReviewPaper-v1"
PYTHON = r"F:\AITradingBot\runtime\python.exe"
SOURCE = r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133g"
LAUNCHER = SOURCE + r"\scripts\run_arch133_unattended_review_paper.py"


@dataclass(frozen=True, slots=True)
class UnattendedSchedulerSpec:
    start_boundary: datetime
    end_boundary: datetime
    schema: str = field(default=SCHEDULER_SCHEMA, init=False)
    task_path: str = field(default=TASK_PATH, init=False)
    executable: str = field(default=PYTHON, init=False)
    arguments: tuple[str, ...] = field(default=("-I", "-B", LAUNCHER), init=False)
    semantic_arguments: tuple[str, ...] = field(default=(), init=False)
    scheduler_owned_environment: tuple[str, ...] = field(default=(), init=False)
    working_directory: str = field(default=SOURCE, init=False)
    principal: str = field(default=r"DESKTOP-I4DOKM7\Trading", init=False)
    principal_sid: str = field(
        default="S-1-5-21-1397534616-3988210162-180023805-1009", init=False
    )
    run_level: str = field(default="LeastPrivilege", init=False)
    trigger_type: str = field(default="TIME", init=False)
    multiple_instances_policy: str = field(default="IgnoreNew", init=False)
    restart_count: int = field(default=0, init=False)
    restart_interval: None = field(default=None, init=False)
    repetition: None = field(default=None, init=False)
    start_when_available: bool = field(default=False, init=False)
    scheduler_is_authority: bool = field(default=False, init=False)
    installation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for name in ("start_boundary", "end_boundary"):
            value = getattr(self, name)
            if (
                type(value) is not datetime
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError("explicit scheduler UTC boundaries required")
            object.__setattr__(self, name, value.astimezone(UTC))
        if self.start_boundary >= self.end_boundary:
            raise ValueError("scheduler window must be nonempty")


def build_unattended_scheduler_spec(
    activation: ReviewPaperActivation,
) -> UnattendedSchedulerSpec:
    """Derive only the exact activation session, including NYSE early closes."""
    if type(activation) is not ReviewPaperActivation:
        raise TypeError("exact activation required")
    schedule = NYSEPublishedRegularSessionAuthority().schedule_for(
        activation.target_session_date
    )
    if schedule is None:
        raise ValueError("target session unavailable")
    start = max(schedule.opens_at + activation.opening_buffer, activation.created_at)
    end = schedule.closes_at - activation.closing_buffer
    return UnattendedSchedulerSpec(start, end)
