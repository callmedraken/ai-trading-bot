"""Fake-only integrity coverage for offline Architecture 148 B2 requalification."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import trading_bot.experiments.arch148_b2_requalify as subject
from trading_bot.experiments.arch148_intraday import (
    INTRADAY_SYMBOLS,
    HistoricalIntradayRequest,
    session_slots,
)
from trading_bot.experiments.historical_research_custody import canonical_json_bytes

_CANDIDATE_HEAD = "a" * 40
_CANDIDATE_TREE = "b" * 40
_DAY = datetime(2023, 11, 22, tzinfo=UTC)


def _prepare_consumed_attempt(tmp_path: Path, monkeypatch) -> Path:
    end = _DAY + timedelta(days=1)
    slots = session_slots(_DAY.date())
    pages_per_symbol = {symbol: 1 for symbol in INTRADAY_SYMBOLS}
    bars_per_symbol = {symbol: len(slots) for symbol in INTRADAY_SYMBOLS}
    monkeypatch.setattr(subject, "OPEN_START", _DAY)
    monkeypatch.setattr(subject, "OPEN_END_EXCLUSIVE", end)
    monkeypatch.setattr(subject, "EXPECTED_PAGE_COUNTS", pages_per_symbol)
    monkeypatch.setattr(subject, "EXPECTED_RAW_BAR_COUNTS", bars_per_symbol)
    monkeypatch.setattr(subject, "EXPECTED_REGULAR_BAR_COUNTS", bars_per_symbol)
    monkeypatch.setattr(
        subject,
        "EXPECTED_MISSING_COUNTS",
        {symbol: 0 for symbol in INTRADAY_SYMBOLS},
    )
    monkeypatch.setattr(subject, "EXPECTED_COMMON_MISSING_COUNT", 0)
    monkeypatch.setattr(subject, "EXPECTED_UNION_MISSING_COUNT", 0)
    monkeypatch.setattr(subject, "EXPECTED_TOTAL_PAGES", len(INTRADAY_SYMBOLS))
    monkeypatch.setattr(
        subject, "EXPECTED_TOTAL_PROVIDER_ATTEMPTS", len(INTRADAY_SYMBOLS)
    )
    monkeypatch.setattr(subject, "EXPECTED_SLOT_COUNT", len(slots))

    attempt = tmp_path / f"arch148-b2-{subject.ORIGINAL_ATTEMPT_ID}"
    (attempt / "journal" / "intents").mkdir(parents=True)
    (attempt / "journal" / "results").mkdir(parents=True)
    for symbol in INTRADAY_SYMBOLS:
        (attempt / "raw" / symbol).mkdir(parents=True)

    claim = {
        "schema": "arch148-b2-attempt-claim/v1",
        "attempt_id": subject.ORIGINAL_ATTEMPT_ID,
        "source_branch": subject.FEATURE_BRANCH,
        "source_head": subject.ORIGINAL_SOURCE_HEAD,
        "source_tree": subject.ORIGINAL_SOURCE_TREE,
        "live_origin_feature_head": subject.ORIGINAL_SOURCE_HEAD,
        "live_origin_develop_head": subject.ORIGINAL_SOURCE_HEAD,
        "automatic_retry": "FORBIDDEN",
    }
    failure = {
        "schema": "arch148-b2-blocked-attempt/v1",
        "classification": "BLOCKED",
        "failure_code": subject.ORIGINAL_FAILURE_CODE,
        "attempt_id": subject.ORIGINAL_ATTEMPT_ID,
        "credential_read_attempt_count": 1,
        "provider_request_attempt_count": len(INTRADAY_SYMBOLS),
        "successful_page_count": len(INTRADAY_SYMBOLS),
        "unresolved_intent_status": "NONE",
        "automatic_retry": "FORBIDDEN",
        "robinhood_calls": 0,
        "broker_calls": 0,
        "order_mutations": 0,
        "production_state_mutations": 0,
        "final_holdout_accesses": 0,
        "baseline_backtests": 0,
    }
    (attempt / "attempt.json").write_bytes(canonical_json_bytes(claim))
    (attempt / "failure.json").write_bytes(canonical_json_bytes(failure))

    sequence = 0
    for symbol in INTRADAY_SYMBOLS:
        sequence += 1
        raw_bars = [
            {
                "t": stamp.isoformat().replace("+00:00", "Z"),
                "o": 100,
                "h": 101,
                "l": 99,
                "c": 100,
                "v": 100,
            }
            for stamp in slots
        ]
        body = json.dumps(
            {"bars": {symbol: raw_bars}, "next_page_token": None},
            separators=(",", ":"),
        ).encode()
        request = HistoricalIntradayRequest(symbol)
        intent = {
            "schema": "arch148-b2-request-intent/v1",
            "attempt_id": subject.ORIGINAL_ATTEMPT_ID,
            "provider_sequence": sequence,
            "symbol": symbol,
            "symbol_page_ordinal": 1,
            "request_descriptor_sha256": request.digest,
            "page_token_sha256": None,
            "automatic_retry": "FORBIDDEN",
        }
        result = {
            "schema": "arch148-b2-request-result/v1",
            "attempt_id": subject.ORIGINAL_ATTEMPT_ID,
            "provider_sequence": sequence,
            "symbol": symbol,
            "symbol_page_ordinal": 1,
            "response_body_sha256": hashlib.sha256(body).hexdigest(),
            "response_body_byte_length": len(body),
            "request_id_sha256": hashlib.sha256(
                f"fake-request-{symbol}".encode()
            ).hexdigest(),
            "http_classification": "SUCCESS_200",
        }
        (attempt / "journal" / "intents" / f"{sequence:04d}.json").write_bytes(
            canonical_json_bytes(intent)
        )
        (attempt / "journal" / "results" / f"{sequence:04d}.json").write_bytes(
            canonical_json_bytes(result)
        )
        (attempt / "raw" / symbol / "0001.json").write_bytes(body)
    return attempt


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_offline_requalifier_writes_sparse_review_evidence_only_to_fresh_output(
    tmp_path: Path, monkeypatch
) -> None:
    attempt = _prepare_consumed_attempt(tmp_path, monkeypatch)
    original = _tree_bytes(attempt)
    output = tmp_path / "offline-output"
    result = subject.requalify_arch148_b2(
        attempt,
        output,
        candidate_source_head=_CANDIDATE_HEAD,
        candidate_source_tree=_CANDIDATE_TREE,
    )

    assert result.classification == subject.REQUALIFICATION_READY
    assert result.attempt_id == subject.ORIGINAL_ATTEMPT_ID
    assert result.dataset.sparse_evidence_by_symbol["QQQ"].missing_count == 0
    assert result.custody.dataset_identity == result.dataset.identity
    assert _tree_bytes(attempt) == original
    assert {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    } == {
        "dataset.json",
        "custody-evidence.json",
        "evidence.json",
        "normalized/QQQ.csv",
        "normalized/TQQQ.csv",
        "normalized/SQQQ.csv",
    }
    evidence = json.loads((output / "evidence.json").read_bytes())
    assert evidence["classification"] == subject.REQUALIFICATION_READY
    assert evidence["original_attempt"]["classification"] == (
        "CONSUMED / BLOCKED / QUALIFICATION_BAR_COUNT_MISMATCH / NO RETRY"
    )
    assert evidence["requalification_source"] == {
        "candidate_head": _CANDIDATE_HEAD,
        "candidate_tree": _CANDIDATE_TREE,
    }
    assert set(evidence["requalifier_effects"].values()) == {0}
    assert all(
        stream["pagination_exhausted"]
        and len(stream["raw_page_sha256"]) == 1
        and len(stream["request_id_sha256"]) == 1
        for stream in evidence["streams"]
    )


def test_offline_requalifier_stops_on_token_manifest_or_consumed_state_drift(
    tmp_path: Path, monkeypatch
) -> None:
    attempt = _prepare_consumed_attempt(tmp_path, monkeypatch)
    intent_path = attempt / "journal" / "intents" / "0001.json"
    intent = json.loads(intent_path.read_bytes())
    intent["page_token_sha256"] = "c" * 64
    intent_path.write_bytes(canonical_json_bytes(intent))
    with pytest.raises(subject.Arch148B2RequalifierError) as caught:
        subject.requalify_arch148_b2(
            attempt,
            tmp_path / "token-failure-output",
            candidate_source_head=_CANDIDATE_HEAD,
            candidate_source_tree=_CANDIDATE_TREE,
        )
    assert caught.value.code == "REQUEST_TOKEN_CHAIN_MISMATCH"
    assert not (tmp_path / "token-failure-output").exists()

    failure_path = attempt / "failure.json"
    failure = json.loads(failure_path.read_bytes())
    failure["classification"] = "SUCCESS"
    failure_path.write_bytes(canonical_json_bytes(failure))
    with pytest.raises(subject.Arch148B2RequalifierError) as caught:
        subject.requalify_arch148_b2(
            attempt,
            tmp_path / "consumed-state-output",
            candidate_source_head=_CANDIDATE_HEAD,
            candidate_source_tree=_CANDIDATE_TREE,
        )
    assert caught.value.code == "ORIGINAL_CONSUMED_CLASSIFICATION_MISMATCH"
    assert not (tmp_path / "consumed-state-output").exists()


def test_offline_requalifier_rejects_off_grid_bar_inside_regular_session(
    tmp_path: Path, monkeypatch
) -> None:
    attempt = _prepare_consumed_attempt(tmp_path, monkeypatch)
    raw_path = attempt / "raw" / "QQQ" / "0001.json"
    payload = json.loads(raw_path.read_bytes())
    payload["bars"]["QQQ"][0]["t"] = "2023-11-22T14:31:00Z"
    body = json.dumps(payload, separators=(",", ":")).encode()
    raw_path.write_bytes(body)
    result_path = attempt / "journal" / "results" / "0001.json"
    result = json.loads(result_path.read_bytes())
    result["response_body_sha256"] = hashlib.sha256(body).hexdigest()
    result["response_body_byte_length"] = len(body)
    result_path.write_bytes(canonical_json_bytes(result))

    with pytest.raises(subject.Arch148B2RequalifierError) as caught:
        subject.requalify_arch148_b2(
            attempt,
            tmp_path / "off-grid-output",
            candidate_source_head=_CANDIDATE_HEAD,
            candidate_source_tree=_CANDIDATE_TREE,
        )
    assert caught.value.code == "OFF_GRID_REGULAR_SESSION_BAR"
    assert not (tmp_path / "off-grid-output").exists()


def test_offline_requalifier_rejects_existing_output_and_bad_candidate_identity(
    tmp_path: Path, monkeypatch
) -> None:
    attempt = _prepare_consumed_attempt(tmp_path, monkeypatch)
    output = tmp_path / "already-there"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(subject.Arch148B2RequalifierError) as caught:
        subject.requalify_arch148_b2(
            attempt,
            output,
            candidate_source_head=_CANDIDATE_HEAD,
            candidate_source_tree=_CANDIDATE_TREE,
        )
    assert caught.value.code == "OUTPUT_ALREADY_EXISTS"
    assert sentinel.read_text(encoding="utf-8") == "keep"

    with pytest.raises(subject.Arch148B2RequalifierError) as caught:
        subject.requalify_arch148_b2(
            attempt,
            tmp_path / "bad-candidate",
            candidate_source_head="not-a-git-identity",
            candidate_source_tree=_CANDIDATE_TREE,
        )
    assert caught.value.code == "CANDIDATE_HEAD_INVALID"


def test_pinned_entrypoint_proves_exact_local_candidate_without_network(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "checkout"
    module_path = root / "src" / "trading_bot" / "experiments" / "requalify.py"
    module_path.parent.mkdir(parents=True)
    module_path.touch()
    monkeypatch.setattr(subject, "CANONICAL_WORKTREE", root)
    monkeypatch.setattr(subject, "__file__", str(module_path))
    calls = []

    def fake_run(command, **kwargs):
        calls.append(tuple(command))
        assert command[:6] == [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(root),
        ]
        argument = command[6:]
        if argument == ["branch", "--show-current"]:
            output = subject.FEATURE_BRANCH
        elif argument == ["remote", "get-url", "origin"]:
            output = subject.CANONICAL_ORIGIN
        elif argument == ["rev-parse", "HEAD"]:
            output = _CANDIDATE_HEAD
        elif argument == ["rev-parse", "HEAD^{tree}"]:
            output = _CANDIDATE_TREE
        elif argument == ["status", "--porcelain=v1", "--untracked-files=all"]:
            output = ""
        else:
            raise AssertionError("pinned source gate requested an unexpected command")
        return subprocess.CompletedProcess(command, 0, stdout=f"{output}\n", stderr="")

    monkeypatch.setattr(subject.subprocess, "run", fake_run)
    assert subject._candidate_source_identity() == (_CANDIDATE_HEAD, _CANDIDATE_TREE)
    assert len(calls) == 5
    assert all("fetch" not in command and "push" not in command for command in calls)
