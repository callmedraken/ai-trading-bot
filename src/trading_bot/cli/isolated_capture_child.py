"""CLI boundary for one manually invoked isolated capture child."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trading_bot.runtime.isolated_capture_child import (
    execute_isolated_capture_child,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute one exact isolated Alpaca capture child request."
    )
    parser.add_argument("--request", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        execution = execute_isolated_capture_child(args.request)
    except Exception:
        print("error: isolated capture child failed safely", file=sys.stderr)
        return 8
    result = execution.result
    print(
        json.dumps(
            {
                "attempt_id": str(result.attempt_id),
                "child_result_id": str(result.child_result_id),
                "classification": result.classification.value,
                "provider_call_disposition": result.provider_call_disposition.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return result.native_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
