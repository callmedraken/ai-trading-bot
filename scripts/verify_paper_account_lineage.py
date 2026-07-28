"""Thin entry point for deterministic full-lineage offline verification."""

# ruff: noqa: I001

from trading_bot.cli.checkpoint_lineage import main


if __name__ == "__main__":
    raise SystemExit(main())
