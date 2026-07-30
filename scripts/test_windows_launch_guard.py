"""Smoke entry point for the Windows local single-writer launch guard."""

# ruff: noqa: I001

from trading_bot.cli.windows_launch_guard_smoke import main


if __name__ == "__main__":
    raise SystemExit(main())
