"""Offline OPEN research; run only after P3 exact-source acceptance/integration."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading_bot.experiments.desktop_research_campaign import (  # noqa: E402
    DesktopCampaignBundle,
    DesktopCampaignError,
    _read,
    run_desktop_campaign,
)
from trading_bot.experiments.historical_research_desktop import (  # noqa: E402
    DesktopResearchStorage,
)

MAIN_ROOT = Path(r"F:\AI\ai-trading-bot")
ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _source_identity() -> tuple[str, str]:
    """Local source guards only; never fetch or otherwise access the network."""
    if (
        ROOT.resolve(strict=True) != MAIN_ROOT.resolve(strict=True)
        or Path(_git("rev-parse", "--show-toplevel")).resolve(strict=True) != ROOT
        or _git("rev-parse", "--abbrev-ref", "HEAD") != "develop"
        or _git("remote", "get-url", "origin") != ORIGIN
        or _git("status", "--porcelain=v1", "--untracked-files=no")
    ):
        raise DesktopCampaignError("run from the exact clean integrated main develop")
    head, tree = _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")
    if _git("rev-parse", "origin/develop") != head:
        raise DesktopCampaignError("local origin/develop identity differs")
    return head, tree


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--run", action="store_true")
    modes.add_argument("--verify", type=Path, metavar="BUNDLE_JSON")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify is not None:
            if args.resume:
                raise DesktopCampaignError("resume requires --run")
            if (
                args.verify.suffix.casefold() != ".json"
                or args.verify.anchor.startswith("\\\\")
            ):
                raise DesktopCampaignError("verify requires a local JSON report")
            bundle = DesktopCampaignBundle.from_bytes(_read(args.verify))
            output = {"status": "VERIFIED", "bundle_id": bundle.bundle_id}
        else:
            head, tree = _source_identity()
            path = run_desktop_campaign(
                DesktopResearchStorage.production(),
                source_head=head,
                source_tree=tree,
                resume=args.resume,
            )
            # Source drift during a long run stops the command; preserve reports.
            if _source_identity() != (head, tree):
                raise DesktopCampaignError("source changed during campaign")
            bundle = DesktopCampaignBundle.from_bytes(_read(path))
            output = {
                "status": "COMPLETE",
                "artifact": str(path),
                "campaign_id": bundle.campaign_id,
                "bundle_id": bundle.bundle_id,
                "candidate_count": len(bundle.development),
                "shortlist_count": len(bundle.walk_forward),
                "research_only_leader": bundle.to_dict()[
                    "recommended_research_only_leader"
                ],
            }
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return 0
    except (Exception, KeyboardInterrupt):
        print('{"status":"STOPPED","reason":"INVALID_OR_INCOMPLETE_CAMPAIGN"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
