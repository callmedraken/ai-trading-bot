"""Authenticate the consumed A2/RHC2 evidence used by current L43 reads.

This module reads only three fixed, immutable evidence files. It performs no
provider, OAuth, browser, MCP, or broker operation and has no caller-selected
path or digest interface.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from trading_bot.live_prototype.l43_production_owner import Q62JournalOrigin

_MAX_EVIDENCE_BYTES: Final = 16_384
_REPARSE_POINT: Final = 0x400
_HEX40: Final = frozenset("0123456789abcdef")
_HEX64: Final = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class _PinnedEvidenceFile:
    path: Path
    sha256: str


_A2_SCHEMA_EVIDENCE: Final = _PinnedEvidenceFile(
    Path(
        r"F:\AI\temp\arch147-agent-initiated-runtime-proof-eligible-"
        r"0d1c18123732442c9d3f4a14ba0f43e6\evidence.json"
    ),
    "34483478bbf6430ff0e9a139cd33cdc8837be22eff100e53e0f6b2fdde46c3f1",
)
_RHC2_REPORT: Final = _PinnedEvidenceFile(
    Path(
        r"F:\AI\temp\ai-trading-bot-checkpoints\arch147-rhc2-robinhood-"
        r"order-scope-successor-observation\preflight-20261117T064253.945488Z"
        r"\report.json"
    ),
    "25873f5cdbb509b7a93b80a0644affb01e784c1bf0145a1aca20222ac71f56e9",
)
_RHC2_OBSERVER_EVIDENCE: Final = _PinnedEvidenceFile(
    Path(
        r"F:\AI\temp\arch147-agent-initiated-runtime-partition-"
        r"3f05ea6fed42440293ea3d58a1af5074\evidence.json"
    ),
    "99bca426cba77589055be6dc826cf0d72884c51e40f493c19b55625ac2bf2189",
)
_PINNED_EVIDENCE: Final = (
    _A2_SCHEMA_EVIDENCE,
    _RHC2_REPORT,
    _RHC2_OBSERVER_EVIDENCE,
)

_A2_COUNTERS: Final = {
    "account_reads": 0,
    "browser_launches": 0,
    "cancellation_calls": 0,
    "mcp_session_open_attempts": 1,
    "mcp_tool_invocation_attempts": 0,
    "oauth_scope_entry_attempts": 1,
    "order_reads": 0,
    "other_tool_calls": 0,
    "placement_calls": 0,
    "position_reads": 0,
    "review_calls": 0,
    "tools_list_attempts": 1,
    "tools_list_pages_received": 1,
}
_RHC2_COUNTERS: Final = {
    "account_read_attempts": 1,
    "browser_launch_attempts": 0,
    "cancellation_attempts": 0,
    "mcp_session_open_attempts": 1,
    "mcp_tool_invocation_attempts": 5,
    "oauth_scope_entry_attempts": 1,
    "order_read_attempts": 4,
    "other_tool_attempts": 0,
    "placement_attempts": 0,
    "review_attempts": 0,
    "tools_list_attempts": 1,
    "tools_list_pages_received": 1,
}
_EXPECTED_READS: Final = (
    ("ALL_BEFORE", None),
    ("TRUE", True),
    ("FALSE", False),
    ("ALL_AFTER", None),
)
_RHC2_SOURCE_HEAD: Final = "600f1ec55de6bbc65e59db839c5016bbd511b449"
_RHC2_SOURCE_TREE: Final = "245b2789acd2196e05ad0ae544e182d4356bdd25"
_RHC2_BRANCH: Final = "feature/robinhood-live-prototype-current"
_RHC2_ACCOUNT_FINGERPRINT: Final = (
    "f377529245bd1682f382d17b22ac8d55362f7138a4f7fc307593c16847e551cf"
)
_RHC2_INNER_B2_SHA256: Final = (
    "7016e9c9f5a8b52e996a56e5eab4ee89ce993b967513109c09af23aa5e693fc3"
)
_A2_OBSERVATION: Final = "".join(
    (
        "ARCH147_L43_AGENT_INITIATED_RUNTIME_PARTITION_ELIGIBILITY",
        "_SCHEMA_ONLY",
    )
)
_A2_SCHEMA: Final = (
    "arch147-agent-initiated-runtime-partition-eligibility-observation/v1"
)
_RHC2_SCHEMA: Final = "arch147-agent-initiated-runtime-partition-observation/v1"
_RHC2_CONTRACT: Final = "ARCH147_L43_B2_AGENT_INITIATED_RUNTIME_PARTITION/v2"
_RHC2_REPORT_SCHEMA: Final = "ai-trading-bot-checkpoint-runner/v1"
_RHC2_CHECKPOINT: Final = "arch147-rhc2-robinhood-order-scope-successor-observation"
_RHC2_OBSERVER_PATH: Final = (
    r"F:\AI\temp\arch147-agent-initiated-runtime-partition-"
    r"3f05ea6fed42440293ea3d58a1af5074\evidence.json"
)
_AUTHORITY_SEAL = object()


@dataclass(frozen=True, slots=True)
class OrderScopeEvidenceAuthority:
    """Sealed provenance for the fully authenticated consumed evidence chain."""

    account_fingerprint: str
    a2_evidence_sha256: str
    rhc2_report_sha256: str
    rhc2_observer_evidence_sha256: str
    inner_b2_evidence_sha256: str
    _seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _AUTHORITY_SEAL:
            raise ValueError("order-scope evidence authority is source-owned")
        if not _is_sha256(self.account_fingerprint):
            raise ValueError("account fingerprint is invalid")
        if any(
            not _is_sha256(value)
            for value in (
                self.a2_evidence_sha256,
                self.rhc2_report_sha256,
                self.rhc2_observer_evidence_sha256,
                self.inner_b2_evidence_sha256,
            )
        ):
            raise ValueError("evidence provenance contains an invalid digest")


def load_order_scope_evidence_authority(
    origin: Q62JournalOrigin,
) -> OrderScopeEvidenceAuthority | None:
    """Authenticate fixed A2/RHC2 files against the canonical Q62 account.

    All parse, path, digest, schema, and semantic failures are intentionally
    collapsed to ``None`` so production retains ``ORDER_SCOPE_UNPROVEN``.
    """

    try:
        if type(origin) is not Q62JournalOrigin:
            return None
        account_fingerprint = origin.runtime_identity.account_fingerprint
        if not _is_sha256(account_fingerprint):
            return None
        raw_records = tuple(_read_pinned_file(record) for record in _PINNED_EVIDENCE)
        documents = tuple(_parse_json_record(raw) for raw in raw_records)
        a2, report, observer = documents
        _validate_a2(a2)
        _validate_rhc2_report(report)
        _validate_rhc2_observer(observer, account_fingerprint=account_fingerprint)
        return OrderScopeEvidenceAuthority(
            account_fingerprint=account_fingerprint,
            a2_evidence_sha256=_PINNED_EVIDENCE[0].sha256,
            rhc2_report_sha256=_PINNED_EVIDENCE[1].sha256,
            rhc2_observer_evidence_sha256=_PINNED_EVIDENCE[2].sha256,
            inner_b2_evidence_sha256=observer["b2_evidence_sha256"],
            _seal=_AUTHORITY_SEAL,
        )
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, IndexError):
        return None


def _read_pinned_file(record: _PinnedEvidenceFile) -> bytes:
    """Read one small regular file without following reparses or path drift."""

    path = record.path
    if not path.is_absolute():
        raise ValueError("evidence path is not absolute")
    ancestors_before = _directory_facts(path)
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or getattr(before, "st_file_attributes", 0) & _REPARSE_POINT
        or before.st_nlink != 1
        or not 1 <= before.st_size <= _MAX_EVIDENCE_BYTES
    ):
        raise ValueError("evidence file object is not admissible")
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("evidence file changed before open")
        raw = handle.read(_MAX_EVIDENCE_BYTES + 1)
        after = os.fstat(handle.fileno())
    final = path.lstat()
    ancestors_after = _directory_facts(path)
    stable_fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
    stable = tuple(getattr(before, name) for name in stable_fields)
    if (
        any(
            tuple(getattr(fact, name) for name in stable_fields) != stable
            for fact in (opened, after, final)
        )
        or opened.st_ctime_ns != after.st_ctime_ns
        or before.st_ctime_ns != final.st_ctime_ns
        or ancestors_before != ancestors_after
        or len(raw) != before.st_size
        or len(raw) > _MAX_EVIDENCE_BYTES
    ):
        raise ValueError("evidence file changed while being read")
    if hashlib.sha256(raw).hexdigest() != record.sha256:
        raise ValueError("evidence digest does not match its pin")
    return raw


def _directory_facts(path: Path) -> tuple[tuple[str, int, int], ...]:
    facts: list[tuple[str, int, int]] = []
    for ancestor in reversed(path.parents):
        fact = ancestor.lstat()
        if (
            not stat.S_ISDIR(fact.st_mode)
            or stat.S_ISLNK(fact.st_mode)
            or getattr(fact, "st_file_attributes", 0) & _REPARSE_POINT
        ):
            raise ValueError("evidence ancestor is not a plain directory")
        facts.append((str(ancestor), fact.st_dev, fact.st_ino))
    return tuple(facts)


def _parse_json_record(raw: bytes) -> dict[str, object]:
    value = json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )
    if type(value) is not dict:
        raise ValueError("evidence root must be an object")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("evidence contains duplicate object keys")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    del value
    raise ValueError("evidence contains a non-JSON numeric constant")


def _validate_a2(a2: dict[str, object]) -> None:
    _exact_keys(
        a2,
        {
            "agent_initiated_schema_sha256",
            "attempt_counters",
            "classification",
            "classifier_output_authenticated",
            "contract_version",
            "description_sha256",
            "exhaustive_pagination",
            "input_schema_sha256",
            "metadata_source_authenticated",
            "metadata_validation_boundary",
            "observation",
            "output_schema_sha256",
            "partition_equality_proof",
            "production_order_scope_authority",
            "qualifier_evidence_sha256",
            "reason",
            "remote_develop",
            "remote_feature",
            "runtime_proof_eligibility",
            "schema",
            "source_authority",
            "source_head",
            "source_tree",
            "status",
            "tools_list_pages",
        },
    )
    _expect_values(
        a2,
        {
            "classification": "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW",
            "classifier_output_authenticated": False,
            "contract_version": "AGENT_INITIATED_RUNTIME_PARTITION_PROOF_ELIGIBLE/v1",
            "exhaustive_pagination": True,
            "metadata_source_authenticated": True,
            "metadata_validation_boundary": (
                "SDK_PARSED_MODELS; VISIBLE_ALIAS_AND_TOOL_NAME_DUPLICATES_REJECTED; "
                "RAW_JSON_DUPLICATE_KEYS_UNOBSERVABLE"
            ),
            "observation": _A2_OBSERVATION,
            "partition_equality_proof": "NOT_PROVEN",
            "production_order_scope_authority": "NOT_GRANTED",
            "reason": "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW_ONLY",
            "runtime_proof_eligibility": "ELIGIBLE",
            "schema": _A2_SCHEMA,
            "status": "AUTHENTICATED_RUNTIME_PARTITION_SCHEMA_FOR_REVIEW",
            "tools_list_pages": 1,
        },
    )
    for name in (
        "agent_initiated_schema_sha256",
        "description_sha256",
        "input_schema_sha256",
        "output_schema_sha256",
        "qualifier_evidence_sha256",
    ):
        _require_sha256(a2[name])
    _expect_object(a2["attempt_counters"], _A2_COUNTERS)
    _expect_object(
        a2["source_authority"],
        {
            "feature": "PASS",
            "prospective_develop": "PASS",
            "status": "PASS",
        },
    )
    source_head = _require_git_sha(a2["source_head"])
    source_tree = _require_git_sha(a2["source_tree"])
    for name in ("remote_develop", "remote_feature"):
        _expect_object(a2[name], {"head": source_head, "tree": source_tree})


def _validate_rhc2_report(report: dict[str, object]) -> None:
    _exact_keys(
        report,
        {
            "checkpoint",
            "description",
            "kind",
            "production_effects",
            "protected_execution",
            "result",
            "schema",
            "source",
            "status",
        },
    )
    _expect_values(
        report,
        {
            "checkpoint": _RHC2_CHECKPOINT,
            "description": (
                "RHC2 review-only B2 successor observation; explicit read-only "
                "preflight only"
            ),
            "kind": "read_only_preflight",
            "production_effects": "NOT_RUN",
            "protected_execution": "NOT_AUTHORIZED",
            "schema": _RHC2_REPORT_SCHEMA,
            "status": "PASS",
        },
    )
    _expect_object(
        report["result"],
        {
            "attempt_counters": _RHC2_COUNTERS,
            "disposition": "REVIEW_ONLY",
            "observer_evidence_path": _RHC2_OBSERVER_PATH,
            "observer_evidence_sha256": _PINNED_EVIDENCE[2].sha256,
            "observer_status": "PROVEN",
            "production_order_scope_authority": "NOT_GRANTED",
            "provider_dispatch_started": True,
            "reason": "PARTITION_EQUALITY_PROVEN",
            "source_head": _RHC2_SOURCE_HEAD,
            "source_recheck_status": "PASS",
            "source_tree": _RHC2_SOURCE_TREE,
            "status": "PASS",
        },
    )
    _expect_object(
        report["source"],
        {
            "after": {
                "branch": _RHC2_BRANCH,
                "head": _RHC2_SOURCE_HEAD,
                "porcelain": "",
                "tree": _RHC2_SOURCE_TREE,
            },
            "before": {
                "branch": _RHC2_BRANCH,
                "head": _RHC2_SOURCE_HEAD,
                "porcelain": "",
                "tree": _RHC2_SOURCE_TREE,
            },
            "identity_stable": True,
            "remote_branch": _RHC2_BRANCH,
            "remote_head": _RHC2_SOURCE_HEAD,
            "remote_head_source": "LIVE_REMOTE_LOOKUP",
        },
    )


def _validate_rhc2_observer(
    observer: dict[str, object], *, account_fingerprint: str
) -> None:
    _exact_keys(
        observer,
        {
            "account_fingerprint",
            "attempt_counters",
            "b2_evidence_sha256",
            "b2_proof_contract_version",
            "b2_result",
            "b2_result_reason",
            "b2_result_status",
            "canonical_order_material_digest",
            "false_partition_digest",
            "logical_reads",
            "observation",
            "partition_equality_proof",
            "production_order_scope_authority",
            "reason",
            "schema",
            "source_authority",
            "source_branch",
            "source_head",
            "source_recheck_status",
            "source_tree",
            "stable_all_universe_digest",
            "status",
            "true_partition_digest",
        },
    )
    _expect_values(
        observer,
        {
            "account_fingerprint": _RHC2_ACCOUNT_FINGERPRINT,
            "b2_evidence_sha256": _RHC2_INNER_B2_SHA256,
            "b2_proof_contract_version": _RHC2_CONTRACT,
            "b2_result_reason": "PARTITION_EQUALITY_PROVEN",
            "b2_result_status": "PROVEN",
            "observation": "ARCH147_L43_AGENT_INITIATED_RUNTIME_PARTITION_OBSERVER",
            "partition_equality_proof": "PROVEN",
            "production_order_scope_authority": "NOT_GRANTED",
            "reason": "PARTITION_EQUALITY_PROVEN",
            "schema": _RHC2_SCHEMA,
            "source_branch": _RHC2_BRANCH,
            "source_head": _RHC2_SOURCE_HEAD,
            "source_recheck_status": "PASS",
            "source_tree": _RHC2_SOURCE_TREE,
            "status": "PROVEN",
        },
    )
    if account_fingerprint != _RHC2_ACCOUNT_FINGERPRINT:
        raise ValueError("RHC2 account fingerprint differs from Q62")
    _expect_object(
        observer["source_authority"],
        {"feature": "PASS", "prospective_develop": "PASS", "status": "PASS"},
    )
    _expect_object(observer["attempt_counters"], _RHC2_COUNTERS)
    for name in (
        "b2_evidence_sha256",
        "canonical_order_material_digest",
        "false_partition_digest",
        "stable_all_universe_digest",
        "true_partition_digest",
    ):
        _require_sha256(observer[name])
    reads = observer["logical_reads"]
    if type(reads) is not list or len(reads) != len(_EXPECTED_READS):
        raise ValueError("RHC2 logical read count is invalid")
    normalized_reads: list[dict[str, object]] = []
    for read, (label, filter_value) in zip(reads, _EXPECTED_READS, strict=True):
        _exact_keys(
            read,
            {
                "agent_initiated",
                "exhaustive",
                "label",
                "page_count",
                "query_sha256",
                "row_count",
            },
        )
        _expect_values(
            read,
            {
                "agent_initiated": filter_value,
                "exhaustive": True,
                "label": label,
                "page_count": 1,
                "row_count": 0,
            },
        )
        query_sha256 = _require_sha256(read["query_sha256"])
        if query_sha256 != _b2_order_query_sha256(account_fingerprint, filter_value):
            raise ValueError("RHC2 logical query does not bind the SPY filter")
        normalized_reads.append(read)
    if normalized_reads[0]["query_sha256"] != normalized_reads[-1]["query_sha256"]:
        raise ValueError("RHC2 all-order universe changed during the observation")
    b2 = _expect_object(
        observer["b2_result"],
        {
            "account_fingerprint": _RHC2_ACCOUNT_FINGERPRINT,
            "canonical_order_material_digest": observer[
                "canonical_order_material_digest"
            ],
            "contract_version": _RHC2_CONTRACT,
            "evidence_sha256": observer["b2_evidence_sha256"],
            "false_partition_digest": observer["false_partition_digest"],
            "logical_reads": normalized_reads,
            "partition_equality_proof": "PROVEN",
            "reason": "PARTITION_EQUALITY_PROVEN",
            "stable_all_universe_digest": observer["stable_all_universe_digest"],
            "status": "PROVEN",
            "true_partition_digest": observer["true_partition_digest"],
        },
    )
    if _inner_b2_evidence_sha256(b2, observer) != _RHC2_INNER_B2_SHA256:
        raise ValueError("RHC2 inner B2 evidence digest is invalid")


def _expect_object(value: object, expected: dict[str, object]) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError("evidence field must be an object")
    _exact_keys(value, set(expected))
    for name, expected_value in expected.items():
        value_field = value[name]
        if type(expected_value) is bool:
            equal = type(value_field) is bool and value_field is expected_value
        elif expected_value is None:
            equal = value_field is None
        elif type(expected_value) is dict:
            _expect_object(value_field, expected_value)
            equal = True
        else:
            equal = (
                type(value_field) is type(expected_value)
                and value_field == expected_value
            )
        if not equal:
            raise ValueError("evidence field has unexpected semantics")
    return value


def _b2_order_query_sha256(
    account_fingerprint: str, agent_initiated: bool | None
) -> str:
    payload = json.dumps(
        (
            "ARCH147_L43_B2_ORDER_QUERY_V1",
            account_fingerprint,
            "SPY",
            agent_initiated,
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _inner_b2_evidence_sha256(
    b2: dict[str, object], observer: dict[str, object]
) -> str:
    payload = {
        "contract_version": b2["contract_version"],
        "status": b2["status"],
        "reason": b2["reason"],
        "source_head": observer["source_head"],
        "source_tree": observer["source_tree"],
        "account_fingerprint": b2["account_fingerprint"],
        "symbol": "SPY",
        "logical_reads": b2["logical_reads"],
        "stable_all_universe_digest": b2["stable_all_universe_digest"],
        "true_partition_digest": b2["true_partition_digest"],
        "false_partition_digest": b2["false_partition_digest"],
        "canonical_order_material_digest": b2["canonical_order_material_digest"],
        "partition_equality_proof": b2["partition_equality_proof"],
        "production_order_scope_authority": "NOT_GRANTED",
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _expect_values(value: dict[str, object], expected: dict[str, object]) -> None:
    for name, expected_value in expected.items():
        if name not in value:
            raise ValueError("required evidence field is missing")
        item = value[name]
        if type(expected_value) is bool:
            equal = type(item) is bool and item is expected_value
        elif expected_value is None:
            equal = item is None
        else:
            equal = type(item) is type(expected_value) and item == expected_value
        if not equal:
            raise ValueError("evidence field has unexpected semantics")


def _exact_keys(value: dict[str, object], expected: set[str]) -> None:
    if type(value) is not dict or set(value) != expected:
        raise ValueError("evidence object has missing or unexpected fields")


def _require_git_sha(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 40
        or any(char not in _HEX40 for char in value)
    ):
        raise ValueError("Git identity is malformed")
    return value


def _require_sha256(value: object) -> str:
    if not _is_sha256(value):
        raise ValueError("SHA-256 digest is malformed")
    return value


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and not any(char not in _HEX64 for char in value)
    )


__all__ = ["OrderScopeEvidenceAuthority", "load_order_scope_evidence_authority"]
