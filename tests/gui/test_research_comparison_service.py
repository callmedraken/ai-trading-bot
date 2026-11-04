"""Read-only report-reader boundary tests for R12 research presentation."""

from __future__ import annotations

from pathlib import Path

import pytest

from trading_bot.experiments import filtered_trend_comparison_bundle_v2 as bundle_module
from trading_bot.experiments.filtered_trend_comparison_bundle_v2 import (
    ResearchComparisonBundle,
)
from trading_bot.gui.research_comparison_service import read_comparison_report
from trading_bot.live_prototype.contracts import ResearchView


def _unavailable() -> ResearchView:
    return ResearchView(
        selected="UNAVAILABLE",
        assumptions=("Comparison report unavailable",),
        live_eligible=False,
    )


def test_missing_relative_and_malformed_reports_return_fixed_unavailable_view(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-report.json"
    assert read_comparison_report(missing) == _unavailable()
    assert read_comparison_report("relative-report.json") == _unavailable()

    marker = "PRIVATE_REPORT_DETAILS_MUST_NOT_LEAK"
    malformed = tmp_path / "malformed-report.json"
    malformed.write_text(marker, encoding="utf-8")
    result = read_comparison_report(malformed)

    assert result == _unavailable()
    assert marker not in repr(result)
    assert str(malformed) not in repr(result)


def test_report_read_is_bounded_before_bundle_decoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "oversized-report.json"
    report.write_bytes(b"x" * 128)
    observed: list[bytes] = []

    def capture_body(cls, body: bytes):
        observed.append(body)
        raise ValueError("private decode details")

    monkeypatch.setattr(bundle_module, "MAX_BUNDLE_BYTES", 8)
    monkeypatch.setattr(
        ResearchComparisonBundle,
        "from_bytes",
        classmethod(capture_body),
    )

    result = read_comparison_report(report)
    assert len(observed) == 1
    assert len(observed[0]) == 9
    assert result == _unavailable()
