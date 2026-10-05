"""PREPARE-only qualification evidence; checkout admission belongs to the caller."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path

from trading_bot.domain import TradeProposal
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionAdmission,
    ReviewPaperSessionSchedule,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedPreparation,
    prepare_review_paper_supervised_cycle,
)
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter


@dataclass(frozen=True, slots=True)
class _DurableSnapshot:
    metadata: tuple[tuple[str, str], ...]
    record_count: int
    sha256: str


def _read_durable_snapshot(path: Path) -> _DurableSnapshot:
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        connection.execute("BEGIN")
        metadata = tuple(
            connection.execute(
                "SELECT key, value FROM metadata ORDER BY key"
            ).fetchall()
        )
        cursor = connection.execute(
            "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id"
        )
        columns = tuple(column[0] for column in cursor.description)
        rows = cursor.fetchall()
    payload = {
        "metadata": metadata,
        "columns": columns,
        "rows": rows,
        "record_count": len(rows),
    }
    material = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _DurableSnapshot(metadata, len(rows), hashlib.sha256(material).hexdigest())


def _admission(
    admission: ReviewPaperSessionAdmission | None,
) -> dict[str, object] | None:
    if admission is None:
        return None
    return {
        "status": admission.status.value,
        "as_of": admission.as_of.isoformat(),
        "session_date": admission.session_date.isoformat(),
        "opens_at": admission.opens_at.isoformat(),
        "closes_at": admission.closes_at.isoformat(),
        "admission_opens_at": admission.admission_opens_at.isoformat(),
        "admission_closes_at": admission.admission_closes_at.isoformat(),
    }


def _preparation_evidence(
    preparation: ReviewPaperSupervisedPreparation,
) -> dict[str, object]:
    snapshot = preparation.price_snapshot
    preview = preparation.preview
    risk_preview = None
    if preview is not None:
        context = preview.risk_context
        decision = preview.risk_decision
        risk_preview = {
            "requested_quantity": str(preview.proposal.desired_quantity),
            "risk_outcome": decision.outcome.value,
            "approved_quantity": str(decision.approved_quantity),
            "reason_codes": [reason.code.value for reason in decision.reasons],
            "cash": str(context.cash),
            "equity": str(context.equity),
            "current_price": str(context.current_price),
            "total_market_exposure": str(context.total_market_exposure),
            "current_position_quantity": str(preview.current_position_quantity),
            "current_position_market_value": str(preview.current_position_market_value),
            "projected_position_quantity": str(preview.projected_position_quantity),
            "projected_position_market_value": str(
                preview.projected_position_market_value
            ),
            "projected_total_market_exposure": str(
                preview.projected_total_market_exposure
            ),
        }
    return {
        "status": preparation.status.value,
        "initial_admission": _admission(preparation.initial_admission),
        "price_snapshot": None
        if snapshot is None
        else {
            "observed_at": snapshot.observed_at.isoformat(),
            "marks": [
                {
                    "symbol": str(mark.symbol),
                    "price": str(mark.price),
                    "source_at": mark.source_at.isoformat(),
                }
                for mark in snapshot.marks
            ],
        },
        "quote_admission": _admission(preparation.quote_admission),
        "risk_preview": risk_preview,
        "quote_valid_until": None
        if preparation.quote_valid_until is None
        else preparation.quote_valid_until.isoformat(),
    }


def run_review_paper_prepare_qualification(
    *,
    store: ReviewPaperStore,
    proposal: TradeProposal,
    schedule: ReviewPaperSessionSchedule,
    opening_buffer: timedelta,
    closing_buffer: timedelta,
    adapter: RobinhoodReviewReadAdapter,
    max_quote_age: timedelta,
    risk_limits: RiskLimits,
    new_trading_enabled: bool,
    expected_source_head: str,
    expected_source_tree: str,
    evidence_path: Path,
) -> ReviewPaperSupervisedPreparation:
    """Bracket exactly one preparation with full read-only durable fingerprints."""
    for name, value, expected in (
        ("store", store, ReviewPaperStore),
        ("proposal", proposal, TradeProposal),
        ("schedule", schedule, ReviewPaperSessionSchedule),
        ("opening_buffer", opening_buffer, timedelta),
        ("closing_buffer", closing_buffer, timedelta),
        ("adapter", adapter, RobinhoodReviewReadAdapter),
        ("max_quote_age", max_quote_age, timedelta),
        ("risk_limits", risk_limits, RiskLimits),
        ("new_trading_enabled", new_trading_enabled, bool),
        ("evidence_path", evidence_path, type(Path())),
    ):
        if type(value) is not expected:
            raise TypeError(f"{name} must be exactly {expected.__name__}")
    for name, value in (
        ("expected_source_head", expected_source_head),
        ("expected_source_tree", expected_source_tree),
    ):
        if (
            type(value) is not str
            or len(value) != 40
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"{name} must be a lowercase 40-character Git SHA")
    if max_quote_age <= timedelta(0):
        raise ValueError("max_quote_age must be strictly positive")
    if opening_buffer < timedelta(0) or closing_buffer < timedelta(0):
        raise ValueError("buffers must be nonnegative")
    duration = schedule.closes_at - schedule.opens_at
    if opening_buffer >= duration or closing_buffer >= duration - opening_buffer:
        raise ValueError("buffers must leave a nonempty admission interval")
    if not evidence_path.is_absolute():
        raise ValueError("evidence_path must be absolute")
    if evidence_path.resolve() == store.path.resolve():
        raise ValueError("evidence_path must differ from store.path")
    if evidence_path.exists() or evidence_path.is_symlink():
        raise FileExistsError("evidence_path must be fresh")
    if not store.path.is_file():
        raise ValueError("store.path must be an existing file")

    before = _read_durable_snapshot(store.path)
    preparation = prepare_review_paper_supervised_cycle(
        store=store,
        proposal=proposal,
        schedule=schedule,
        opening_buffer=opening_buffer,
        closing_buffer=closing_buffer,
        adapter=adapter,
        max_quote_age=max_quote_age,
        risk_limits=risk_limits,
        new_trading_enabled=new_trading_enabled,
    )
    after = _read_durable_snapshot(store.path)
    if before != after:
        raise RuntimeError("durable state changed during PREPARE qualification")
    payload = {
        "schema": "arch131-q-prepare-qualification/v1",
        "source_head": expected_source_head,
        "source_tree": expected_source_tree,
        "store_path": str(store.path.resolve()),
        "starting_cash": str(store.starting_cash),
        "proposal": {
            "proposal_id": str(proposal.proposal_id),
            "symbol": str(proposal.symbol),
            "side": proposal.side.value,
            "desired_quantity": str(proposal.desired_quantity),
            "created_at": proposal.created_at.isoformat(),
        },
        "schedule": {
            "session_date": schedule.session_date.isoformat(),
            "opens_at": schedule.opens_at.isoformat(),
            "closes_at": schedule.closes_at.isoformat(),
        },
        "opening_buffer_seconds": opening_buffer.total_seconds(),
        "closing_buffer_seconds": closing_buffer.total_seconds(),
        "max_quote_age_seconds": max_quote_age.total_seconds(),
        "new_trading_enabled": new_trading_enabled,
        "durable_before": asdict(before),
        "preparation": _preparation_evidence(preparation),
        "durable_after": asdict(after),
        "execute_invoked": False,
        "pipeline_result_present": False,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    with evidence_path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(encoded)
    return preparation
