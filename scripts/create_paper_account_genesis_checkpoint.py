"""Thin entry point for fixed-layout genesis checkpoint output."""

# ruff: noqa: I001

from trading_bot.cli.checkpoint_transition import genesis_main


if __name__ == "__main__":
    raise SystemExit(genesis_main())
