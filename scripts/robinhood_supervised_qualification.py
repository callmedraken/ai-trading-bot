"""Qualification-only PowerShell entry point; launch requires PREPARE authorization."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

# Bootstrap only the reviewed launcher's sibling source directory.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from trading_bot.domain import OrderSide, Symbol, TradeProposal  # noqa: E402
from trading_bot.risk.models import RiskLimits  # noqa: E402
from trading_bot.robinhood_supervised_qualification import (  # noqa: E402
    SupervisedQualificationError,
    run_robinhood_supervised_qualification,
)

_INTENDED_STORE = Path(
    r"F:\AI\temp\robinhood-131j-source-live-91b4bf7f665947f79a6a94fd44ecae39\paper.sqlite"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="131-V: one PREPARE, one human stdin frame, one EXECUTE; no retry"
    )
    parser.add_argument("--session-date", type=date.fromisoformat, required=True)
    parser.add_argument("--proposal-id", type=UUID, required=True)
    parser.add_argument("--order-id", type=UUID, required=True)
    parser.add_argument(
        "--proposal-created-at", type=datetime.fromisoformat, required=True
    )
    for name in ("store", "prepare-evidence", "execute-evidence", "operator-evidence"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in (
        "expected-branch",
        "expected-head",
        "expected-tree",
        "expected-before-sha256",
        "redirect-uri",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--slippage-basis-points", type=Decimal, required=True)
    parser.add_argument("--commission", type=Decimal, required=True)
    args = parser.parse_args()
    try:
        proposal = TradeProposal(
            args.proposal_id,
            Symbol("SPY"),
            OrderSide.SELL,
            Decimal("1.000"),
            args.proposal_created_at,
            "131-V supervised qualification",
        )
        run_robinhood_supervised_qualification(
            session_date=args.session_date,
            store_path=args.store,
            intended_store_path=_INTENDED_STORE,
            expected_before_sha256=args.expected_before_sha256,
            proposal=proposal,
            order_id=args.order_id,
            risk_limits=RiskLimits(),
            expected_branch=args.expected_branch,
            expected_head=args.expected_head,
            expected_tree=args.expected_tree,
            prepare_evidence_path=args.prepare_evidence,
            execute_evidence_path=args.execute_evidence,
            operator_evidence_path=args.operator_evidence,
            redirect_uri=args.redirect_uri,
            slippage_basis_points=args.slippage_basis_points,
            commission=args.commission,
        )
    except (SupervisedQualificationError, ValueError, TypeError):
        print(
            '{"schema":"arch131-q-execute-qualification/v1","status":"STOP","retry_authorized":false}'
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
