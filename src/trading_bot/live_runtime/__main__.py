"""Effect-free help for the explicitly injected Architecture 148 desktop service."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m trading_bot.live_runtime",
        description=(
            "No provider, broker, credential, worker, or desktop connection is "
            "created by this module. Compose an Arch148RuntimeService with an "
            "explicit context-owned bindings factory and cross-instance owner "
            "lease, then call service.create_window() from desktop startup. "
            "Order writes remain denied unless an explicit effect authority is "
            "injected."
        ),
        epilog=(
            "This module intentionally has no default connection or effect path. "
            "Import trading_bot.live_runtime.service.Arch148RuntimeService for "
            "explicit application composition; the service exposes create_window()."
        ),
    )
    parser.parse_args(argv)
    parser.error("runtime service requires explicit injected application composition")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
