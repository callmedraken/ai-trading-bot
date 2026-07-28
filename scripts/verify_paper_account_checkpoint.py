"""Thin entry point for offline checkpoint and one-edge verification."""

# ruff: noqa: I001

from trading_bot.cli.checkpoint_transition import verify_main


if __name__ == "__main__":
    raise SystemExit(verify_main())
