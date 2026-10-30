"""Explicit, source-pinned one-shot desktop SPY acquisition command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading_bot.experiments.historical_research_desktop_acquisition import (  # noqa: E402
    DesktopAcquisitionError,
    run_production_acquisition,
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default output echoes rejected arguments, potentially secrets.
        raise DesktopAcquisitionError("CLI", "INVALID_INVOCATION")


def main(argv: list[str] | None = None) -> int:
    stage = "CLI"
    output = None
    code = 1
    try:
        parser = _Parser(description=__doc__, allow_abbrev=False)
        parser.add_argument("--execute", action="store_true", required=True)
        parser.add_argument("--expected-head", required=True)
        parser.add_argument("--expected-tree", required=True)
        args = parser.parse_args(argv)
        stage = "ACQUISITION"
        output = run_production_acquisition(
            ROOT,
            expected_head=args.expected_head,
            expected_tree=args.expected_tree,
            attempt_id=str(uuid4()),
        )
        code = 0
    except DesktopAcquisitionError as error:
        output = {"stage": error.stage, "classification": error.classification}
    except (Exception, KeyboardInterrupt):
        output = {"stage": stage, "classification": "UNEXPECTED_FAILURE"}
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
