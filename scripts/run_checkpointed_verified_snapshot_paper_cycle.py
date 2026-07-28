"""Thin entry point for one fixed-layout checkpoint transition."""

# ruff: noqa: I001

from trading_bot.cli.checkpoint_transition import run_main


if __name__ == "__main__":
    raise SystemExit(run_main())
