from __future__ import annotations

from pathlib import Path

from scripts import run_test_certification as certification


def test_portfolio_manager_directory_automatically_owns_future_full_modules() -> None:
    repository = Path(certification.__file__).resolve().parents[1]
    existing = certification.discover_inventory(repository)
    additions = (
        "tests/portfolio_manager/future_a/test_shared.py",
        "tests/portfolio_manager/future_b/test_shared.py",
        "tests/portfolio_manager/nested/test_future_module.py",
    )

    profiles = certification.classify_inventory(tuple(sorted((*existing, *additions))))

    assert set(additions) <= set(profiles["full"])
    assert not (set(additions) & set(profiles["legacy"]))
    assert not (set(additions) & set(profiles["robinhood"]))
