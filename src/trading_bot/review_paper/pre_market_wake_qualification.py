"""D1R5 timing/source qualification; no trading or credential dependencies."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO
from zoneinfo import ZoneInfo

from trading_bot.review_paper.nyse_published_regular_sessions import (
    NYSEPublishedRegularSessionAuthority,
)
from trading_bot.review_paper.session_admission import (
    ReviewPaperSessionAdmission,
    ReviewPaperSessionSchedule,
    ReviewPaperSessionStatus,
    admit_review_paper_session,
)

QUALIFY_WAKE_INTERLOCK = "AUTHORIZE_ARCH134_D1R5_ONE_PREMARKET_WAKE_QUALIFICATION"
SCHEMA = "arch134-d1r5-pre-market-wake-qualification/v1"
OPENING_BUFFER = CLOSING_BUFFER = timedelta(minutes=5)
MAX_PRE_OPEN_LEAD = timedelta(minutes=15)
MAX_TOTAL_WAIT = timedelta(minutes=20)
MAX_WAKE_LATENESS = timedelta(seconds=60)
MAX_JOURNAL_BYTES = 16384
_NEW_YORK = ZoneInfo("America/New_York")
_EVENTS = (
    "QUALIFICATION_RESERVED",
    "SOURCE_ADMITTED",
    "WAITING_FOR_MARKET",
    "WAKE_OBSERVED",
    "SOURCE_READMITTED",
)
EFFECT_COUNTERS = (
    "credential_reads",
    "provider_requests",
    "robinhood_reads",
    "robinhood_reviews",
    "oauth_interactions",
    "production_sqlite_reads",
    "production_sqlite_writes",
    "armed_session_store_reads",
    "armed_session_store_writes",
    "review_paper_store_reads",
    "review_paper_store_writes",
    "strategy_evaluations",
    "prepare_attempts",
    "execute_attempts",
    "paper_mutations",
    "broker_placements",
    "scheduler_changes",
    "acl_changes",
    "d1_invocations",
    "d2_invocations",
    "live_effects",
)
_FIELDS = frozenset(
    (
        "schema",
        "event",
        "source_head",
        "source_tree",
        "target_session",
        "regular_opens_at",
        "regular_closes_at",
        "admission_opens_at",
        "admission_closes_at",
        "start_observed_at",
        "wait_started_at",
        "wait_seconds",
        "wake_observed_at",
        "source_readmitted",
        "classification",
        *EFFECT_COUNTERS,
    )
)


class WakeClassification(StrEnum):
    PASS = "PASS"
    SOURCE_REJECTED = "SOURCE_REJECTED"
    SESSION_UNAVAILABLE = "SESSION_UNAVAILABLE"
    START_WINDOW_REJECTED = "START_WINDOW_REJECTED"
    WAIT_FAILED = "WAIT_FAILED"
    WAKE_TOO_EARLY = "WAKE_TOO_EARLY"
    WAKE_TOO_LATE = "WAKE_TOO_LATE"
    WAKE_SESSION_INVALID = "WAKE_SESSION_INVALID"


def validate_source_identity(value: str) -> None:
    """Accept only canonical Git SHA-1 identities."""
    if (
        type(value) is not str
        or len(value) != 40
        or any(c not in "0123456789abcdef" for c in value)
        or value == "0" * 40
    ):
        raise ValueError("invalid qualification source identity")


def _utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("invalid qualification clock")
    return value.astimezone(UTC)


def _timestamp(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("invalid qualification timestamp")
    result = _utc(datetime.fromisoformat(value))
    if result.isoformat() != value:
        raise ValueError("noncanonical qualification timestamp")
    return result


def _admission(
    schedule: ReviewPaperSessionSchedule,
    instant: datetime,
) -> ReviewPaperSessionAdmission:
    return admit_review_paper_session(
        schedule=schedule,
        as_of=instant,
        opening_buffer=OPENING_BUFFER,
        closing_buffer=CLOSING_BUFFER,
    )


def _valid_start(schedule: ReviewPaperSessionSchedule, instant: datetime) -> bool:
    admission = _admission(schedule, instant)
    return (
        admission.status
        in {
            ReviewPaperSessionStatus.BEFORE_REGULAR_WINDOW,
            ReviewPaperSessionStatus.OPENING_BUFFER,
        }
        and schedule.opens_at - MAX_PRE_OPEN_LEAD <= instant
        and timedelta(0) < admission.admission_opens_at - instant <= MAX_TOTAL_WAIT
    )


def _wake_classification(
    schedule: ReviewPaperSessionSchedule,
    awake: datetime,
) -> WakeClassification:
    admission = _admission(schedule, awake)
    if admission.status is ReviewPaperSessionStatus.NON_SESSION_DATE:
        return WakeClassification.WAKE_SESSION_INVALID
    if awake < admission.admission_opens_at:
        return WakeClassification.WAKE_TOO_EARLY
    if admission.status is not ReviewPaperSessionStatus.ADMITTED:
        return WakeClassification.WAKE_SESSION_INVALID
    if awake - admission.admission_opens_at > MAX_WAKE_LATENESS:
        return WakeClassification.WAKE_TOO_LATE
    return WakeClassification.PASS


def _validate_records(records: tuple[dict[str, object], ...]) -> None:
    if type(records) is not tuple or not 1 <= len(records) <= 6:
        raise ValueError("invalid qualification event count")
    previous = None
    for index, record in enumerate(records):
        if type(record) is not dict or set(record) != _FIELDS:
            raise ValueError("invalid qualification fields")
        if type(record["schema"]) is not str or record["schema"] != SCHEMA:
            raise ValueError("invalid qualification schema")
        validate_source_identity(record["source_head"])
        validate_source_identity(record["source_tree"])
        for field in EFFECT_COUNTERS:
            if type(record[field]) is not int or record[field] != 0:
                raise ValueError("qualification effect budget violated")
        if type(record["source_readmitted"]) is not bool:
            raise ValueError("invalid qualification source observation")
        event = record["event"]
        final = event == "FINAL"
        if (
            type(event) is not str
            or (final and index != len(records) - 1)
            or (not final and (index >= len(_EVENTS) or event != _EVENTS[index]))
            or (final and index < 2)
        ):
            raise ValueError("invalid qualification event order")
        target = record["target_session"]
        if type(target) is not str or date.fromisoformat(target).isoformat() != target:
            raise ValueError("invalid qualification session")
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(
            date.fromisoformat(target)
        )
        if schedule is None:
            raise ValueError("unpublished qualification session")
        start = _timestamp(record["start_observed_at"])
        admission = _admission(schedule, start)
        for field, value in (
            ("regular_opens_at", schedule.opens_at),
            ("regular_closes_at", schedule.closes_at),
            ("admission_opens_at", admission.admission_opens_at),
            ("admission_closes_at", admission.admission_closes_at),
        ):
            if _timestamp(record[field]) != value:
                raise ValueError("incoherent qualification window")
        if not _valid_start(schedule, start):
            raise ValueError("incoherent qualification start")
        waiting = index >= 2 and not (final and index == 2)
        if waiting:
            wait_start = _timestamp(record["wait_started_at"])
            seconds = record["wait_seconds"]
            if (
                type(seconds) is not float
                or not 0 < seconds <= MAX_TOTAL_WAIT.total_seconds()
                or wait_start < start
                or not _valid_start(schedule, wait_start)
                or seconds
                != (admission.admission_opens_at - wait_start).total_seconds()
            ):
                raise ValueError("incoherent qualification wait")
        elif (
            record["wait_started_at"] is not None or record["wait_seconds"] is not None
        ):
            raise ValueError("unexpected qualification wait")
        woke = index >= 3 and not (final and index == 3)
        if woke:
            awake = _timestamp(record["wake_observed_at"])
        elif record["wake_observed_at"] is not None:
            raise ValueError("unexpected qualification wake")
        readmitted = index >= 4 and not (final and index == 4)
        if record["source_readmitted"] != readmitted:
            raise ValueError("incoherent qualification source observation")
        if (
            readmitted
            and _wake_classification(schedule, awake) is not WakeClassification.PASS
        ):
            raise ValueError("source readmitted after invalid wake")
        if final:
            if type(record["classification"]) is not str:
                raise ValueError("invalid qualification classification")
            classification = WakeClassification(record["classification"])
            allowed = {
                2: {
                    WakeClassification.SOURCE_REJECTED,
                    WakeClassification.START_WINDOW_REJECTED,
                },
                3: {WakeClassification.WAIT_FAILED},
                4: {
                    WakeClassification.SOURCE_REJECTED,
                    WakeClassification.WAKE_TOO_EARLY,
                    WakeClassification.WAKE_TOO_LATE,
                    WakeClassification.WAKE_SESSION_INVALID,
                },
                5: {WakeClassification.PASS},
            }
            if classification not in allowed[index]:
                raise ValueError("incoherent terminal qualification")
            if woke:
                expected = _wake_classification(schedule, awake)
                if classification != expected and not (
                    expected is WakeClassification.PASS
                    and classification is WakeClassification.SOURCE_REJECTED
                ):
                    raise ValueError("incoherent terminal wake")
        elif record["classification"] is not None:
            raise ValueError("premature terminal qualification")
        if previous is not None:
            changed = {
                "event",
                "classification",
                *(
                    {"wait_started_at", "wait_seconds"}
                    if event == "WAITING_FOR_MARKET"
                    else ()
                ),
                *({"wake_observed_at"} if event == "WAKE_OBSERVED" else ()),
                *({"source_readmitted"} if event == "SOURCE_READMITTED" else ()),
            }
            if any(record[k] != previous[k] for k in _FIELDS - changed):
                raise ValueError("qualification facts changed")
        previous = record


def serialize_wake_journal(records: tuple[dict[str, object], ...]) -> bytes:
    """Serialize canonical JSONL; every nonterminal prefix is consumed."""
    _validate_records(records)
    payload = b"".join(
        (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for record in records
    )
    if len(payload) > MAX_JOURNAL_BYTES:
        raise ValueError("qualification journal exceeds bound")
    return payload


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate qualification field")
        result[key] = value
    return result


def parse_wake_journal(payload: bytes) -> tuple[dict[str, object], ...]:
    """Validate complete durable prefixes, never authorize recovery or retry."""
    result = None
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_JOURNAL_BYTES:
            raise ValueError
        records = tuple(
            json.loads(line, object_pairs_hook=_pairs)
            for line in payload.decode("utf-8").splitlines()
        )
        if serialize_wake_journal(records) != payload:
            raise ValueError
        result = records
    except Exception:
        pass
    if result is None:
        raise ValueError("invalid canonical wake qualification journal") from None
    return result


def admit_wake_evidence(path: Path, roots: tuple[Path, ...]) -> Path:
    """Fresh external file under existing real parents; forbid production and links."""
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or path.suffix != ".jsonl"
        or not roots
        or path.exists()
        or path.is_symlink()
        or not path.parent.is_dir()
    ):
        raise ValueError("invalid qualification evidence destination")
    resolved = path.resolve()
    if any(resolved.is_relative_to(root.resolve()) for root in roots) or (
        resolved.is_relative_to(Path(r"F:\AITradingBot").resolve())
    ):
        raise ValueError("qualification evidence must be external")
    for parent in path.parents:
        metadata = parent.lstat()
        if stat.S_ISLNK(metadata.st_mode) or (
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError("linked qualification evidence parent")
    return resolved


class _Journal:
    def __init__(self, output: BinaryIO, facts: dict[str, object]) -> None:
        self.output = output
        self.facts = facts
        self.records: tuple[dict[str, object], ...] = ()

    def record(self, event: str, **updates: object) -> None:
        candidate = {**self.facts, **updates, "event": event}
        records = (*self.records, candidate)
        payload = serialize_wake_journal(records)
        previous_size = len(serialize_wake_journal(self.records)) if self.records else 0
        appended = payload[previous_size:]
        if self.output.write(appended) != len(appended):
            raise ValueError("qualification journal write failed")
        self.output.flush()
        os.fsync(self.output.fileno())
        self.facts = candidate
        self.records = records


def qualify_pre_market_wake(
    *,
    expected_head: str,
    expected_tree: str,
    qualify_wake: str,
    evidence: Path,
    admit_source: Callable[[], tuple[Path, ...]],
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None],
) -> WakeClassification:
    """Qualify one bounded wake, with mandatory fake seams for implementation tests."""
    validate_source_identity(expected_head)
    validate_source_identity(expected_tree)
    if type(qualify_wake) is not str or qualify_wake != QUALIFY_WAKE_INTERLOCK:
        raise ValueError("wake qualification interlock required")
    try:
        roots = admit_source()
    except Exception:
        return WakeClassification.SOURCE_REJECTED
    start = _utc(clock())
    try:
        schedule = NYSEPublishedRegularSessionAuthority().schedule_for(
            start.astimezone(_NEW_YORK).date()
        )
    except Exception:
        return WakeClassification.SESSION_UNAVAILABLE
    if schedule is None:
        return WakeClassification.SESSION_UNAVAILABLE
    if not _valid_start(schedule, start):
        return WakeClassification.START_WINDOW_REJECTED
    destination = admit_wake_evidence(evidence, roots)
    admission = _admission(schedule, start)
    facts = dict.fromkeys(EFFECT_COUNTERS, 0) | {
        "schema": SCHEMA,
        "source_head": expected_head,
        "source_tree": expected_tree,
        "target_session": schedule.session_date.isoformat(),
        "regular_opens_at": schedule.opens_at.isoformat(),
        "regular_closes_at": schedule.closes_at.isoformat(),
        "admission_opens_at": admission.admission_opens_at.isoformat(),
        "admission_closes_at": admission.admission_closes_at.isoformat(),
        "start_observed_at": start.isoformat(),
        "wait_started_at": None,
        "wait_seconds": None,
        "wake_observed_at": None,
        "source_readmitted": False,
        "classification": None,
    }
    with destination.open("xb") as output:
        journal = _Journal(output, facts)
        journal.record("QUALIFICATION_RESERVED")
        journal.record("SOURCE_ADMITTED")

        def finish(classification: WakeClassification) -> WakeClassification:
            journal.record("FINAL", classification=classification.value)
            return classification

        try:
            admit_source()
        except Exception:
            return finish(WakeClassification.SOURCE_REJECTED)
        wait_start = _utc(clock())
        if wait_start < start or not _valid_start(schedule, wait_start):
            return finish(WakeClassification.START_WINDOW_REJECTED)
        wait_seconds = (admission.admission_opens_at - wait_start).total_seconds()
        journal.record(
            "WAITING_FOR_MARKET",
            wait_started_at=wait_start.isoformat(),
            wait_seconds=wait_seconds,
        )
        try:
            sleeper(wait_seconds)
            awake = _utc(clock())
        except Exception:
            return finish(WakeClassification.WAIT_FAILED)
        journal.record("WAKE_OBSERVED", wake_observed_at=awake.isoformat())
        classification = _wake_classification(schedule, awake)
        if classification is not WakeClassification.PASS:
            return finish(classification)
        try:
            admit_source()
        except Exception:
            return finish(WakeClassification.SOURCE_REJECTED)
        journal.record("SOURCE_READMITTED", source_readmitted=True)
        return finish(WakeClassification.PASS)
