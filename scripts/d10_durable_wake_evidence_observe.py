"""Read-only Architecture-127 observation of the exact current-soak D10 log."""

from __future__ import annotations

import json
import sys

from scripts import run_personal_desktop_d10_launch_guard as guard


def observe() -> dict[str, object]:
    """Return the sealed guard's sanitized read-only current-soak observation."""

    return guard.observe_fixed_d10_durable_wake_evidence()


def main() -> int:
    if sys.argv != [sys.argv[0]]:
        return 1
    try:
        record = observe()
    except Exception:
        print("d10_evidence_observation_blocked", file=sys.stderr)
        return 1
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
