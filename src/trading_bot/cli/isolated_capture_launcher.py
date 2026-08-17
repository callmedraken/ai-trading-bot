"""CLI boundary for the secret-free Windows isolated-child launcher."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trading_bot.runtime.isolated_capture_artifacts import (
    IsolatedCaptureChildClassification,
)
from trading_bot.runtime.windows_isolated_capture_launcher import (
    launch_isolated_capture_child,
    load_isolated_capture_launcher_config,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manually launch one isolated Alpaca capture child."
    )
    parser.add_argument("--config", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_isolated_capture_launcher_config(args.config)
        execution = launch_isolated_capture_child(config)
    except Exception:
        print("error: isolated capture launcher failed safely", file=sys.stderr)
        return 10
    print(
        json.dumps(
            {
                "child_classification": (
                    None
                    if execution.child_classification is None
                    else execution.child_classification.value
                ),
                "process_creation_record_id": str(
                    execution.creation_record.process_creation_record_id
                ),
                "resume_authorization_record_id": (
                    None
                    if execution.resume_record is None
                    else str(execution.resume_record.resume_authorization_record_id)
                ),
                "termination_record_id": str(
                    execution.termination_record.termination_record_id
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    if execution.child_classification is IsolatedCaptureChildClassification.SUCCEEDED:
        return 0
    if execution.native_exit_code is not None and 0 <= execution.native_exit_code < 256:
        return execution.native_exit_code
    return 10


if __name__ == "__main__":
    raise SystemExit(main())
