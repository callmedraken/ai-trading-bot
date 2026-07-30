"""Allocate an offline capture attempt from an exact READY decision."""

# ruff: noqa: I001

from trading_bot.cli.capture_attempt_authority import main_allocate_capture_attempt


if __name__ == "__main__":
    raise SystemExit(main_allocate_capture_attempt())
