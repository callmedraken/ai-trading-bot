"""Bounded read-only inspection of explicitly selected Architecture-134 JSON."""

from __future__ import annotations

import json
import re
from dataclasses import fields
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from trading_bot.gui.runtime_models import (
    MAX_RUNTIME_EVIDENCE_BYTES,
    MAX_RUNTIME_HISTORY,
    RuntimeAclEvidenceView,
    RuntimeAclStatus,
    RuntimeDiagnostic,
    RuntimePageState,
    RuntimePageStatus,
    RuntimePrepareResult,
    RuntimeProvisionStatus,
    RuntimeQualificationEvidenceView,
    RuntimeQualificationStatus,
    RuntimeResult,
    RuntimeSessionEvidenceView,
    RuntimeSessionStatus,
    RuntimeStrategyOutcome,
    RuntimeWriteReadiness,
    unavailable_runtime_state,
)


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate evidence key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("Non-JSON constant")


def _date(value: object) -> date:
    if type(value) is not str or len(value) != 10:
        raise ValueError("Invalid evidence date")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical evidence date")
    return parsed


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or len(value) > 40
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})",
            value,
        )
        is None
    ):
        raise ValueError("Invalid evidence timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Naive evidence timestamp")
    return parsed.astimezone(UTC)


def _uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if type(value) is not str or len(value) != 36:
        raise ValueError("Invalid evidence identity")
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("Noncanonical evidence identity")
    return parsed


def _read(path: Path, kind: type, schema: str):
    with path.open("rb") as stream:
        payload = stream.read(MAX_RUNTIME_EVIDENCE_BYTES + 1)
    if len(payload) > MAX_RUNTIME_EVIDENCE_BYTES:
        raise ValueError("Oversized evidence")
    value = json.loads(
        payload.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant
    )
    names = {field.name for field in fields(kind)}
    extra = (
        {"snapshot_sha256", "history_seed_sha256"}
        if kind is RuntimeSessionEvidenceView
        else set()
    )
    if (
        type(value) is not dict
        or set(value) != names | extra | {"schema"}
        or value["schema"] != schema
    ):
        raise ValueError("Unsupported evidence schema")
    del value["schema"]
    if kind is RuntimeAclEvidenceView:
        value["status"] = RuntimeAclStatus(value["status"])
        value["result"] = RuntimeResult(value["result"])
    elif kind is RuntimeQualificationEvidenceView:
        value["status"] = RuntimeQualificationStatus(value["status"])
        value["runtime_status"] = RuntimeProvisionStatus(value["runtime_status"])
        for name in ("paper_store_write_readiness", "session_store_write_readiness"):
            value[name] = RuntimeWriteReadiness(value[name])
    else:
        digests = value.pop("snapshot_sha256")
        seed = value.pop("history_seed_sha256")
        if type(digests) is not list or len(digests) > MAX_RUNTIME_HISTORY:
            raise ValueError("Invalid evidence digests")
        for digest in (*digests, *((seed,) if seed is not None else ())):
            if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise ValueError("Invalid evidence digest")
        value["status"] = RuntimeSessionStatus(value["status"])
        for name, enum in (
            ("strategy_outcome", RuntimeStrategyOutcome),
            ("prepare_result", RuntimePrepareResult),
            ("execute_result", RuntimeResult),
        ):
            if value[name] is not None:
                value[name] = enum(value[name])
        for name in (
            "contract_id",
            "operation_id",
            "order_id",
            "fill_id",
            "proposal_id",
        ):
            value[name] = _uuid(value[name])
        for name in (
            "wait_started_at",
            "admitted_at",
            "admission_opens_at",
            "admission_closes_at",
        ):
            value[name] = _timestamp(value[name])
        value["target_session"] = _date(value["target_session"])
        sessions = value["historical_sessions"]
        if type(sessions) is not list or len(sessions) > MAX_RUNTIME_HISTORY:
            raise ValueError("Invalid evidence history")
        value["historical_sessions"] = tuple(_date(item) for item in sessions)
    return kind(**value)


def _blocked(acl, qualification, session) -> bool:
    if acl is not None and (
        acl.result is RuntimeResult.FAIL
        or acl.status
        not in {RuntimeAclStatus.PROVISIONED, RuntimeAclStatus.ALREADY_PROVISIONED}
        or acl.acl_apply_attempts != acl.acl_applies_verified
        or any(
            getattr(acl, name)
            for name in (
                "parent_mutations",
                "recursive_mutations",
                "credential_mutations",
                "scheduler_mutations",
                "provider_calls",
                "paper_mutations",
                "session_mutations",
                "broker_mutations",
            )
        )
    ):
        return True
    if qualification is not None and (
        qualification.status is RuntimeQualificationStatus.BLOCKED
        or qualification.runtime_status is RuntimeProvisionStatus.NOT_QUALIFIED
        or qualification.paper_store_write_readiness
        is not RuntimeWriteReadiness.WRITE_READY
        or qualification.session_store_write_readiness
        is not RuntimeWriteReadiness.WRITE_READY
        or not qualification.persisted_oauth_available
        or not qualification.effect_counts_complete
        or any(
            getattr(qualification, name) is None
            for name in (
                "paper_records",
                "session_reservations",
                "alpaca_credential_reads",
                "robinhood_credential_reads",
            )
        )
        or any(
            getattr(qualification, name)
            for name in (
                "alpaca_http_calls",
                "robinhood_application_calls",
                "paper_trade_mutations",
                "scheduler_mutations",
                "broker_mutations",
            )
        )
    ):
        return True
    return session is not None and (
        not session.effect_counts_complete
        or session.status
        in {
            RuntimeSessionStatus.BLOCKED,
            RuntimeSessionStatus.RISK_REJECTED,
            RuntimeSessionStatus.SESSION_NOT_ADMITTED,
            RuntimeSessionStatus.SESSION_EXPIRED,
            RuntimeSessionStatus.EXECUTE_STARTED,
        }
    )


class ProductionRuntimeEvidenceInspectionService:
    """Acquire each explicit artifact once; subsequent reads return cached state."""

    def __init__(
        self,
        *,
        acl: Path | None = None,
        qualification: Path | None = None,
        session: Path | None = None,
    ) -> None:
        for path in (acl, qualification, session):
            if path is not None and not isinstance(path, Path):
                raise TypeError("Explicit evidence Path required")
        self._paths = (acl, qualification, session)
        self._state: RuntimePageState | None = None

    def get_runtime_state(self) -> RuntimePageState:
        """Read explicit files only, sanitizing every acquisition failure."""
        if self._state is not None:
            return self._state
        if not any(path is not None for path in self._paths):
            self._state = unavailable_runtime_state()
            return self._state
        views = []
        failed = False
        # Identical selected paths share one open even if used for two schema roles.
        seen: set[Path] = set()
        for path, kind, schema in zip(
            self._paths,
            (
                RuntimeAclEvidenceView,
                RuntimeQualificationEvidenceView,
                RuntimeSessionEvidenceView,
            ),
            (
                "production-paper-runtime-acl/v1",
                "production-paper-runtime-qualification/v1",
                "armed-paper-session/v1",
            ),
            strict=True,
        ):
            view = None
            if path is not None:
                try:
                    if path in seen:
                        raise ValueError("Conflicting artifact roles")
                    seen.add(path)
                    view = _read(path, kind, schema)
                except Exception:
                    failed = True
            views.append(view)
        acl, qualification, session = views
        diagnostic = RuntimeDiagnostic.RECORDED
        if failed:
            diagnostic = RuntimeDiagnostic.INVALID
        elif (
            qualification is not None
            and session is not None
            and (
                qualification.source_head != session.source_head
                or qualification.source_tree != session.source_tree
            )
        ):
            diagnostic = RuntimeDiagnostic.CONFLICTING
        elif _blocked(acl, qualification, session):
            diagnostic = RuntimeDiagnostic.BLOCKED
        self._state = RuntimePageState(
            RuntimePageStatus.AVAILABLE
            if diagnostic is RuntimeDiagnostic.RECORDED
            else RuntimePageStatus.ATTENTION,
            diagnostic,
            acl,
            qualification,
            session,
        )
        return self._state
