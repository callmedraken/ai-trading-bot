"""Explicit offline campaign entry point; real acquisition is separately reviewed."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from trading_bot.experiments.filtered_trend_bundle import (
    build_bundle,
    report_csv,
    write_research_bundle,
)
from trading_bot.experiments.filtered_trend_campaign import run_campaign
from trading_bot.experiments.filtered_trend_data import read_dataset


def verify_source(root: Path, head: str, tree: str) -> None:
    """Read-only local source admission; no fetch, provider or credential access."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    if git("branch", "--show-current") != "develop":
        raise ValueError("campaign requires accepted integrated develop")
    if git("rev-parse", "HEAD") != head or git("rev-parse", "HEAD^{tree}") != tree:
        raise ValueError("source identity mismatch")
    if git("rev-parse", "origin/develop") != head:
        raise ValueError("local tracking source mismatch")
    if (
        git("remote", "get-url", "origin")
        != "https://github.com/callmedraken/ai-trading-bot.git"
    ):
        raise ValueError("origin mismatch")
    if git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ValueError("tracked/index changes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        verify_source(root, args.expected_head, args.expected_tree)
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("output already exists; no automatic retry or repair")
        dataset = read_dataset(args.dataset)
        context, cells, summaries = run_campaign(
            dataset, args.expected_head, args.expected_tree
        )
        bundle = build_bundle(context, cells, summaries)
        args.output.mkdir(parents=False, exist_ok=False)
        # A partial output remains visible. Never overwrite or silently resume it.
        with (args.output / "cells.csv").open("xb") as stream:
            stream.write(report_csv(bundle))
        write_research_bundle(args.output / "bundle.json", bundle)
        print("FILTERED_TREND_RESEARCH=PASS")
        print("CAMPAIGN_ID=" + bundle.campaign_id)
        print("BUNDLE_ID=" + bundle.bundle_id)
    except (ValueError, TypeError, OSError, subprocess.SubprocessError):
        print(
            "FILTERED_TREND_RESEARCH=STOP; inspect source/input/output; "
            "no automatic retry"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
