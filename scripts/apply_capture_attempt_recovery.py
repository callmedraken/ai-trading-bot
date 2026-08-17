"""Apply explicit provider-free capture-attempt recovery evidence."""

# ruff: noqa: I001

from trading_bot.cli.capture_attempt_authority import (
    main_apply_capture_attempt_recovery,
)


if __name__ == "__main__":
    raise SystemExit(main_apply_capture_attempt_recovery())
