"""Entry point for the guarded capture-readiness dry-run runner."""

# ruff: noqa: I001

from trading_bot.cli.guarded_capture_readiness import main


if __name__ == "__main__":
    raise SystemExit(main())
