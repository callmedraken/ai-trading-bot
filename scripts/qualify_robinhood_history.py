"""134-B3Q reviewed launcher; no provider semantics from command-line arguments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from trading_bot.robinhood_history_qualification import (  # noqa: E402
    MAX_EVIDENCE_BYTES,
    HistoryQualificationError,
    preflight_history_qualification,
    replay_history_qualification,
    run_history_qualification,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--replay", action="store_true")
    mode.add_argument("--authorize", metavar="B3Q_INTERLOCK")
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args(argv)
    inputs = dict(
        expected_head=args.expected_head,
        expected_tree=args.expected_tree,
        evidence_path=args.evidence,
    )
    try:
        if args.replay:
            with args.evidence.open("rb") as journal:
                replay_history_qualification(
                    journal.read(MAX_EVIDENCE_BYTES + 1),
                    expected_head=args.expected_head,
                    expected_tree=args.expected_tree,
                )
            print("PASS_REPLAY")
            return 0
        if args.preflight:
            print(json.dumps(preflight_history_qualification(**inputs), sort_keys=True))
            return 0
        status = run_history_qualification(authorization=args.authorize, **inputs)
        print(status)
        return 0 if status == "PASS" else 1
    except (HistoryQualificationError, OSError):
        print("B3Q STOP; preserve evidence; no automatic retry", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
