"""Thin entry point for read-only paper-operation inspection."""

# ruff: noqa: I001

from trading_bot.cli.paper_operation import main


if __name__ == "__main__":
    raise SystemExit(main())
