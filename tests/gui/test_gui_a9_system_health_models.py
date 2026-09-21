"""GUI-A9 System Health presentation-model tests."""

import pytest

from trading_bot.gui import (
    SystemAuditEntryView,
    SystemComponentHealthView,
    SystemComponentStatus,
    SystemHealthPageState,
    SystemHealthStatus,
)


def _component(
    key: str = "research",
    status: SystemComponentStatus = SystemComponentStatus.AVAILABLE,
) -> SystemComponentHealthView:
    return SystemComponentHealthView(key, "Research", status, "Bounded detail.")


def test_system_health_state_accepts_bounded_presentation_values() -> None:
    state = SystemHealthPageState(
        SystemHealthStatus.READ_ONLY_READY,
        "No explicit blocked presentation state is present.",
        "Local read-only GUI",
        "Research",
        (_component(),),
        (
            SystemAuditEntryView(
                "Market Data",
                "Snapshot ID",
                "12345678-1234-1234-1234-123456789abc",
                "a" * 64,
            ),
        ),
    )

    assert state.status is SystemHealthStatus.READ_ONLY_READY
    assert state.components[0].status is SystemComponentStatus.AVAILABLE
    assert state.audit_entries[0].sha256 == "a" * 64


@pytest.mark.parametrize("value", ("A" * 64, "not-a-sha", "", None))
def test_audit_sha256_is_exact_lowercase_or_none(value: object) -> None:
    if value is None:
        entry = SystemAuditEntryView("Source", "Kind", "id", None)
        assert entry.sha256 is None
        return
    with pytest.raises(ValueError):
        SystemAuditEntryView("Source", "Kind", "id", value)  # type: ignore[arg-type]


def test_system_health_rejects_duplicate_component_keys() -> None:
    with pytest.raises(ValueError):
        SystemHealthPageState(
            SystemHealthStatus.READ_ONLY_READY,
            "Message",
            "Environment",
            "Research",
            (_component(), _component()),
            (),
        )


def test_system_health_rejects_duplicate_audit_identity() -> None:
    entry = SystemAuditEntryView("Source", "Kind", "id")
    with pytest.raises(ValueError):
        SystemHealthPageState(
            SystemHealthStatus.READ_ONLY_READY,
            "Message",
            "Environment",
            "Research",
            (_component(),),
            (entry, entry),
        )
