"""Effect-free help surface for the source-only runtime skeleton."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m trading_bot.live_runtime",
        description=(
            "Architecture 148-A runtime contracts only. No provider or broker "
            "composition is available in this source-only milestone."
        ),
    )
    parser.parse_args(argv)
    parser.error("runtime composition is deferred; this command has no effect path")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
