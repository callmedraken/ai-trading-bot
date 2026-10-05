"""Qualification-only in-process PREPARE, human authorization, accepted EXECUTE."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import warnings
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from trading_bot.domain import OrderSide, OrderType, Symbol, TimeInForce, TradeProposal
from trading_bot.execution.models import ExecutionInstruction
from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionStatus,
    admit_review_paper_session,
)
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.supervised_forward_paper import (
    ReviewPaperSupervisedPreparation,
    ReviewPaperSupervisedPreparationStatus,
    execute_review_paper_supervised_cycle,
)
from trading_bot.risk.models import RiskLimits
from trading_bot.robinhood_execute_qualification_verifier import (
    BRANCH,
    ORDER_ID,
    PROPOSAL_ID,
    SCHEMA,
    qualification_fingerprint,
    read_qualification_json,
    read_qualification_store,
    require_qualification,
    validate_qualification_before,
    verify_robinhood_execute_qualification,
)
from trading_bot.robinhood_prepare_operator import (
    run_robinhood_published_session_prepare_qualification,
)
from trading_bot.robinhood_prepare_qualification_verifier import (
    verify_robinhood_prepare_qualification,
)

_DATETIME_TYPE = datetime


class SupervisedQualificationError(RuntimeError):
    """Fixed, sanitized failure; no automatic retry or upstream error disclosure."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _admit_source(branch: str, head: str, tree: str) -> Path:
    root = Path(__file__).resolve().parents[2]

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()

    require_qualification(
        branch == BRANCH
        and len(head) == len(tree) == 40
        and all(c in "0123456789abcdef" for c in head + tree)
    )
    require_qualification(
        Path(git("rev-parse", "--show-toplevel")).resolve() == root
        and git("branch", "--show-current") == branch
        and git("rev-parse", "HEAD") == head
        and git("rev-parse", "HEAD^{tree}") == tree
        and git("status", "--porcelain", "--untracked-files=no") == ""
        and git("diff", "--cached", "--name-only") == ""
        and git("remote", "get-url", "origin")
        == "https://github.com/callmedraken/ai-trading-bot.git"
    )
    ref = "refs/heads/" + branch
    require_qualification(git("ls-remote", "origin", ref) == head + "\t" + ref)
    # Also require the locally available exact remote tree; never fetch or repair.
    require_qualification(
        git("rev-parse", "origin/" + branch) == head
        and git("rev-parse", "origin/" + branch + "^{tree}") == tree
    )
    for name, module in tuple(sys.modules.items()):
        if name == "trading_bot" or name.startswith("trading_bot."):
            filename = getattr(module, "__file__", None)
            require_qualification(
                type(filename) is str
                and Path(filename).is_absolute()
                and Path(filename).resolve().is_relative_to(root / "src")
            )
    return root


def _discard_log(*args: object, **kwargs: object) -> None:
    pass


@contextmanager
def _quiet_provider() -> Iterator[None]:
    # No capture buffer: discard provider output, including retained FD/log handlers.
    streams = sys.stdout, sys.stderr
    for stream in streams:
        stream.flush()
    previous_disable, previous_handle = (
        logging.root.manager.disable,
        logging.Logger.handle,
    )
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        redirect_stdout(sink),
        redirect_stderr(sink),
        warnings.catch_warnings(),
        ExitStack() as stack,
    ):
        for descriptor in (1, 2):
            saved = os.dup(descriptor)
            stack.callback(os.close, saved)
            stack.callback(os.dup2, saved, descriptor)
            os.dup2(sink.fileno(), descriptor)
        try:
            logging.disable(sys.maxsize)
            logging.Logger.handle = _discard_log
            warnings.simplefilter("ignore")
            warnings.showwarning = _discard_log
            yield
        finally:
            try:
                for stream in streams:
                    stream.flush()
            finally:
                logging.Logger.handle = previous_handle
                logging.disable(previous_disable)


def _risk(preview: object) -> dict:
    context, decision = preview.risk_context, preview.risk_decision
    return {
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
        "projected_position_market_value": str(preview.projected_position_market_value),
        "projected_total_market_exposure": str(preview.projected_total_market_exposure),
    }


def run_robinhood_supervised_qualification(
    *,
    session_date: date,
    store_path: Path,
    intended_store_path: Path,
    expected_before_sha256: str,
    proposal: TradeProposal,
    order_id: UUID,
    risk_limits: RiskLimits,
    expected_branch: str,
    expected_head: str,
    expected_tree: str,
    prepare_evidence_path: Path,
    execute_evidence_path: Path,
    operator_evidence_path: Path,
    redirect_uri: str,
    slippage_basis_points: Decimal,
    commission: Decimal,
) -> dict:
    """Keep the exact preparation alive across one terminal authorization read.

    There is no callback, input stream, alternate executor, retry, or replay API.
    The initial invocation itself requires separate human PREPARE authorization.
    """
    try:
        return _run(
            session_date=session_date,
            store_path=store_path,
            intended_store_path=intended_store_path,
            expected_before_sha256=expected_before_sha256,
            proposal=proposal,
            order_id=order_id,
            risk_limits=risk_limits,
            expected_branch=expected_branch,
            expected_head=expected_head,
            expected_tree=expected_tree,
            prepare_evidence_path=prepare_evidence_path,
            execute_evidence_path=execute_evidence_path,
            operator_evidence_path=operator_evidence_path,
            redirect_uri=redirect_uri,
            slippage_basis_points=slippage_basis_points,
            commission=commission,
        )
    except BaseException:
        raise SupervisedQualificationError(
            "131-V qualification stopped; no retry authorized"
        ) from None


def _run(
    *,
    session_date: date,
    store_path: Path,
    intended_store_path: Path,
    expected_before_sha256: str,
    proposal: TradeProposal,
    order_id: UUID,
    risk_limits: RiskLimits,
    expected_branch: str,
    expected_head: str,
    expected_tree: str,
    prepare_evidence_path: Path,
    execute_evidence_path: Path,
    operator_evidence_path: Path,
    redirect_uri: str,
    slippage_basis_points: Decimal,
    commission: Decimal,
) -> dict:
    root = _admit_source(expected_branch, expected_head, expected_tree)
    paths = (
        store_path,
        intended_store_path,
        prepare_evidence_path,
        execute_evidence_path,
        operator_evidence_path,
    )
    require_qualification(
        all(type(path) is type(Path()) and path.is_absolute() for path in paths)
    )
    require_qualification(
        store_path == intended_store_path
        and store_path.resolve() == intended_store_path
        and store_path.is_file()
        and not store_path.is_symlink()
    )
    resolved = [
        path.resolve()
        for path in (
            store_path,
            prepare_evidence_path,
            execute_evidence_path,
            operator_evidence_path,
        )
    ]
    require_qualification(len(set(resolved)) == 4)
    for path in paths[2:]:
        require_qualification(
            path == path.resolve()
            and path.parent.is_dir()
            and not path.exists()
            and not path.is_symlink()
            and not path.is_relative_to(root)
            and path
            not in {
                Path(str(store_path) + suffix)
                for suffix in ("-wal", "-shm", "-journal")
            }
        )
    require_qualification(
        sys.stdin.isatty()
        and type(session_date) is date
        and type(proposal) is TradeProposal
        and proposal.proposal_id == PROPOSAL_ID
        and proposal.symbol == Symbol("SPY")
        and proposal.side is OrderSide.SELL
        and proposal.desired_quantity == Decimal("1.000")
        and type(order_id) is UUID
        and order_id == ORDER_ID
        and type(risk_limits) is RiskLimits
        and risk_limits == RiskLimits()
        and type(slippage_basis_points) is Decimal
        and slippage_basis_points == Decimal(0)
        and type(commission) is Decimal
        and commission == Decimal(0)
        and type(redirect_uri) is str
        and redirect_uri == "http://127.0.0.1:8765/callback"
    )
    schedule = NYSEPublishedRegularSessionAuthority().schedule_for(session_date)
    require_qualification(schedule is not None)
    now = datetime.now(UTC)
    require_qualification(
        proposal.created_at <= now
        and admit_review_paper_session(
            schedule=schedule,
            as_of=now,
            opening_buffer=timedelta(minutes=5),
            closing_buffer=timedelta(minutes=5),
        ).status
        is ReviewPaperSessionStatus.ADMITTED
    )
    before = validate_qualification_before(
        *read_qualification_store(store_path), expected_before_sha256
    )
    # Construct the store after read-only admission; prove state is preserved.
    store = ReviewPaperStore(store_path, starting_cash=Decimal("100000"))
    require_qualification(
        qualification_fingerprint(*read_qualification_store(store_path)) == before
    )
    config = {
        "branch": expected_branch,
        "head": expected_head,
        "tree": expected_tree,
        "store_path": str(store_path),
        "operator_evidence_path": str(operator_evidence_path),
        "order_type": "MARKET",
        "time_in_force": "DAY",
        "slippage_basis_points": "0",
        "commission": "0",
        "redirect_uri_sha256": hashlib.sha256(redirect_uri.encode()).hexdigest(),
        "risk_limits": {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in asdict(risk_limits).items()
        },
        "opening_buffer_seconds": 300,
        "closing_buffer_seconds": 300,
        "max_quote_age_seconds": 300,
        "new_trading_enabled": True,
    }
    # Reserve EXECUTE output first; PREPARE/operator own their fresh files.
    with execute_evidence_path.open("x", encoding="utf-8", newline="\n") as output:
        evidence = {
            "schema": SCHEMA,
            "source_head": expected_head,
            "source_tree": expected_tree,
            "proposal_id": str(proposal.proposal_id),
            "order_id": str(order_id),
            "prepare_evidence_path": str(prepare_evidence_path),
            "prepare_evidence_sha256": None,
            "authorization_challenge": None,
            "authorization_accepted": False,
            "authorization_accepted_at": None,
            "instruction_created_at": None,
            "quote_observed_at": None,
            "quote_valid_until": None,
            "execution_configuration": config,
            "execute_admission": None,
            "prepared_risk": None,
            "revalidated_risk": None,
            "durable_before": before,
            "durable_after": None,
            "operator_evidence_path": str(operator_evidence_path),
            "operator_evidence_sha256": None,
            "operator_evidence": None,
            "placement_calls": 0,
            "cancellation_calls": 0,
            "options_mutation_calls": 0,
            "crypto_mutation_calls": 0,
            "interactive_reauth_count": None,
            "prepare_calls": 0,
            "prepare_verifier_calls": 0,
            "stdin_reads": 0,
            "execute_calls": 0,
            "execute_invoked": False,
            "forward_cycle_invoked": False,
            "retry_count": 0,
            "status": "STOP",
        }
        try:
            evidence["prepare_calls"] = 1
            with _quiet_provider():
                preparation = run_robinhood_published_session_prepare_qualification(
                    session_date=session_date,
                    store=store,
                    proposal=proposal,
                    opening_buffer=timedelta(minutes=5),
                    closing_buffer=timedelta(minutes=5),
                    max_quote_age=timedelta(minutes=5),
                    risk_limits=risk_limits,
                    new_trading_enabled=True,
                    expected_source_head=expected_head,
                    expected_source_tree=expected_tree,
                    evidence_path=prepare_evidence_path,
                    redirect_uri=redirect_uri,
                )
            prepare_digest = hashlib.sha256(
                prepare_evidence_path.read_bytes()
            ).hexdigest()
            evidence["prepare_verifier_calls"] = 1
            verified = verify_robinhood_prepare_qualification(
                store_path=store_path,
                evidence_path=prepare_evidence_path,
                expected_source_head=expected_head,
                expected_source_tree=expected_tree,
                expected_proposal_id=proposal.proposal_id,
            )
            require_qualification(
                type(preparation) is ReviewPaperSupervisedPreparation
                and preparation.store is store
                and preparation.proposal is proposal
                and preparation.risk_limits is risk_limits
                and preparation.status
                is ReviewPaperSupervisedPreparationStatus.READY_TO_PROCEED
                and verified.preparation_status == "READY_TO_PROCEED"
                and verified.risk_outcome == "APPROVED"
                and verified.approved_quantity == Decimal("1.000")
                and verified.record_count == 2
                and verified.durable_sha256 == before["sha256"]
                and hashlib.sha256(prepare_evidence_path.read_bytes()).hexdigest()
                == prepare_digest
            )
            risk = _risk(preparation.preview)
            prepare_json = read_qualification_json(prepare_evidence_path)
            require_qualification(
                risk == prepare_json["preparation"]["risk_preview"]
                and preparation.price_snapshot.observed_at == verified.quote_observed_at
                and preparation.quote_valid_until == verified.quote_valid_until
                and preparation.schedule == schedule
                and preparation.max_quote_age == timedelta(minutes=5)
            )
            evidence.update(
                prepare_evidence_sha256=prepare_digest,
                quote_observed_at=preparation.price_snapshot.observed_at.isoformat(),
                quote_valid_until=preparation.quote_valid_until.isoformat(),
                prepared_risk=risk,
            )
            material = {
                key: evidence[key]
                for key in (
                    "schema",
                    "source_head",
                    "source_tree",
                    "proposal_id",
                    "order_id",
                    "prepare_evidence_sha256",
                    "prepare_evidence_path",
                    "quote_observed_at",
                    "quote_valid_until",
                    "execution_configuration",
                )
            }
            material.update(
                risk_outcome=risk["risk_outcome"],
                approved_quantity=risk["approved_quantity"],
            )
            challenge = hashlib.sha256(_canonical(material)).hexdigest()
            evidence["authorization_challenge"] = challenge
            print(
                json.dumps(
                    {
                        "status": "AUTHORIZATION_REQUIRED",
                        "challenge": challenge,
                        **material,
                        "prepared_risk": risk,
                        "durable_before": before,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                flush=True,
            )
            evidence["stdin_reads"] = 1
            # One terminal frame rejects extra lines and empty EOF.
            token = sys.stdin.read()
            require_qualification(
                token == "AUTHORIZE 131-Q EXECUTE " + challenge + "\n"
            )
            require_qualification(
                hashlib.sha256(prepare_evidence_path.read_bytes()).hexdigest()
                == evidence["prepare_evidence_sha256"]
                and qualification_fingerprint(*read_qualification_store(store_path))
                == before
            )
            authorized_at = datetime.now(UTC)
            evidence.update(
                authorization_accepted=True,
                authorization_accepted_at=authorized_at.isoformat(),
            )
            instruction = ExecutionInstruction(
                OrderType.MARKET, TimeInForce.DAY, datetime.now(UTC)
            )
            require_qualification(instruction.created_at >= authorized_at)
            evidence["instruction_created_at"] = instruction.created_at.isoformat()
            evidence.update(
                execute_calls=1,
                execute_invoked=True,
                forward_cycle_invoked=None,
                status="INDETERMINATE",
            )
            with _quiet_provider():
                result = execute_review_paper_supervised_cycle(
                    preparation=preparation,
                    instruction=instruction,
                    order_id=order_id,
                    expected_branch=expected_branch,
                    expected_head=expected_head,
                    expected_tree=expected_tree,
                    evidence_path=operator_evidence_path,
                    redirect_uri=redirect_uri,
                    slippage_basis_points=Decimal("0"),
                    commission=Decimal("0"),
                )
            require_qualification(result.preparation is preparation)
            operator = asdict(result.pipeline_result.operator_evidence)
            evidence.update(
                forward_cycle_invoked=True,
                execute_admission={
                    key: value.isoformat()
                    if isinstance(value, (date, _DATETIME_TYPE))
                    else value
                    for key, value in asdict(result.execute_admission).items()
                },
                revalidated_risk=_risk(result.revalidated_preview),
                operator_evidence=operator,
                operator_evidence_sha256=hashlib.sha256(
                    operator_evidence_path.read_bytes()
                ).hexdigest(),
            )
            for key in (
                "placement_calls",
                "cancellation_calls",
                "options_mutation_calls",
                "crypto_mutation_calls",
                "interactive_reauth_count",
            ):
                evidence[key] = operator[key]
            evidence["status"] = "PASS" if operator["status"] == "PASS" else "FAIL"
        finally:
            try:
                evidence["durable_after"] = qualification_fingerprint(
                    *read_qualification_store(store_path)
                )
            finally:
                output.write(_canonical(evidence).decode() + "\n")
                output.flush()
    result = verify_robinhood_execute_qualification(
        store_path=store_path,
        evidence_path=execute_evidence_path,
        prepare_evidence_path=prepare_evidence_path,
        operator_evidence_path=operator_evidence_path,
        expected_source_head=expected_head,
        expected_source_tree=expected_tree,
        expected_before_sha256=expected_before_sha256,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
    return result
