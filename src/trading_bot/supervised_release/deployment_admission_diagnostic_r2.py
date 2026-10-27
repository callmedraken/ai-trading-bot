"""Architecture 134 R2 diagnostic with opaque preserved-incident metadata.

The v1 observer remains the historical coarse contract.  This module reuses
its reviewed collectors and validators while adding only a closed diagnostic
classification to host failures.  No exception payload is ever serialized.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import PureWindowsPath
from typing import Final

from trading_bot.arch133_verifier.token import TradingTokenObservation
from trading_bot.supervised_release import deployment_admission as readonly
from trading_bot.supervised_release.bundle import canonical_json
from trading_bot.supervised_release.deployment_candidate import (
    INCIDENT_RELEASE_IDS,
    INCIDENT_ROOTS,
)
from trading_bot.supervised_release.installation_contract import ANCESTORS, ObjectFacts
from trading_bot.supervised_release.model import ReleaseManifest, release_root

CHECKPOINT: Final = (
    "arch134-fresh-successor-readonly-deployment-admission-diagnostic-r2"
)
BRANCH: Final = (
    "feature/robinhood-production-paper-fresh-successor-"
    "readonly-deployment-admission-diagnostic-r2-current"
)
SCHEMA: Final = CHECKPOINT + "/v1"
READY: Final = readonly.READY
MAX_EVIDENCE_BYTES: Final = readonly.MAX_EVIDENCE_BYTES
ZERO_EFFECTS: Final = readonly.ZERO_EFFECTS
NO_AUTHORITY: Final = readonly.NO_AUTHORITY


@dataclass(frozen=True, slots=True)
class ReviewedInvocation:
    """Successor invocation identity without changing the v1 observer."""

    observer: readonly.SourceIdentity
    principal_sid: str
    elevated: bool

    def __post_init__(self) -> None:
        if (
            type(self.observer) is not readonly.SourceIdentity
            or self.observer.repository != readonly.CANDIDATE.repository
            or self.observer.reference != BRANCH
            or self.observer.head
            in {
                readonly.CANDIDATE.head,
                readonly.DESIGN.head,
                readonly.SUCCESSOR.head,
            }
            or self.observer.tree
            in {
                readonly.CANDIDATE.tree,
                readonly.DESIGN.tree,
                readonly.SUCCESSOR.tree,
            }
            or type(self.elevated) is not bool
        ):
            raise ValueError("REVIEWED_OBSERVER_SOURCE_REQUIRED")


HOST_SESSION: Final = "HOST_SESSION"
HOST_PARENT: Final = "HOST_PARENT"
HOST_ANCESTORS: Final = "HOST_ANCESTORS"
HOST_NAMESPACE_COLLECTION: Final = "HOST_NAMESPACE_COLLECTION"
HOST_NAMESPACE_POLICY: Final = "HOST_NAMESPACE_POLICY"
HOST_DESTINATION_PRESENT: Final = "HOST_DESTINATION_PRESENT"
HOST_INCIDENT_ALIAS: Final = "HOST_INCIDENT_ALIAS"
HOST_SECURITY_COLLECTION: Final = "HOST_SECURITY_COLLECTION"
HOST_TOKEN_POLICY: Final = "HOST_TOKEN_POLICY"
HOST_SACL_POLICY: Final = "HOST_SACL_POLICY"
HOST_RUNTIME_PYTHON_IDENTITY: Final = "HOST_RUNTIME_PYTHON_IDENTITY"
HOST_QUIESCENCE_COLLECTION: Final = "HOST_QUIESCENCE_COLLECTION"
HOST_QUIESCENCE_POLICY: Final = "HOST_QUIESCENCE_POLICY"
HOST_UNKNOWN: Final = "HOST_UNKNOWN"
HOST_SOURCE_GIT_COLLECTION: Final = "HOST_SOURCE_GIT_COLLECTION"
HOST_SOURCE_CHECKOUT_POLICY: Final = "HOST_SOURCE_CHECKOUT_POLICY"
HOST_SOURCE_LINEAGE: Final = "HOST_SOURCE_LINEAGE"
HOST_SOURCE_INVENTORY: Final = "HOST_SOURCE_INVENTORY"
DIAGNOSTIC_CODES: Final = frozenset(
    {
        HOST_SESSION,
        HOST_PARENT,
        HOST_ANCESTORS,
        HOST_NAMESPACE_COLLECTION,
        HOST_NAMESPACE_POLICY,
        HOST_DESTINATION_PRESENT,
        HOST_INCIDENT_ALIAS,
        HOST_SECURITY_COLLECTION,
        HOST_TOKEN_POLICY,
        HOST_SACL_POLICY,
        HOST_RUNTIME_PYTHON_IDENTITY,
        HOST_QUIESCENCE_COLLECTION,
        HOST_QUIESCENCE_POLICY,
        HOST_UNKNOWN,
        HOST_SOURCE_GIT_COLLECTION,
        HOST_SOURCE_CHECKOUT_POLICY,
        HOST_SOURCE_LINEAGE,
        HOST_SOURCE_INVENTORY,
    }
)


class DiagnosticFailure(Exception):
    """Internal typed failure; its code is the only permitted output."""

    def __init__(self, code: str) -> None:
        super().__init__()
        self.code = code if code in DIAGNOSTIC_CODES else HOST_UNKNOWN


def _boundary(code: str, operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except DiagnosticFailure:
        raise
    except BaseException:
        raise DiagnosticFailure(code) from None


def _closed_exception_code(error: BaseException) -> str | None:
    if (
        type(error) is ValueError
        and len(error.args) == 1
        and type(error.args[0]) is str
    ):
        return error.args[0]
    return None


def source_failure_code(error: BaseException) -> str:
    """Translate only exact, reviewed source failures; never return payload text."""
    code = _closed_exception_code(error)
    if code in {"GIT_VOCABULARY", "LOCAL_GIT_OBSERVATION"}:
        return HOST_SOURCE_GIT_COLLECTION
    if code in {
        "SOURCE_NAMESPACE",
        "SOURCE_REPARSE",
        "WORKTREE_IDENTITY",
        "GRAFTS_FORBIDDEN",
        "SOURCE_ADMISSION",
        "INDEX_FLAGS",
        "PARTIAL_CLONE",
    }:
        return HOST_SOURCE_CHECKOUT_POLICY
    if code in {
        "SOURCE_LINEAGE",
        "FROZEN_LINEAGE",
        "R1_IMMUTABLE_CLOSURE",
        "SOURCE_LINEAGE_OR_CLOSURE",
    }:
        return HOST_SOURCE_LINEAGE
    if code in {
        "TREE_BOUND",
        "TREE_OBJECT",
        "TREE_DUPLICATE",
        "COMPLETE_TREE_IDENTITY",
        "CANDIDATE_OBJECT",
        "INVENTORY_BOUND",
        "BLOB_HEADER",
        "BLOB_IDENTITY",
        "BLOB_TRAILING_DATA",
        "MANIFEST_POLICY_IDENTITY",
        "bounded immutable source namespace required",
        "noncanonical or incomplete source namespace",
        "canonical slash-separated relative inventory name required",
        "unsafe inventory name",
        "inventory is limited to source and dependency material",
        "durable data and runtime substrate excluded",
        "nonempty immutable source inventory required",
        "exact inventory entries required",
        "duplicate Windows inventory names",
        "launcher must match the exact source inventory",
    }:
        return HOST_SOURCE_INVENTORY
    return HOST_UNKNOWN


def _source_observation(collectors, invocation):
    try:
        value = collectors.source(invocation)
        readonly.require_source(value, invocation)
        return value
    except BaseException as error:
        raise DiagnosticFailure(source_failure_code(error)) from None


def _security_policy_code(error: BaseException) -> str:
    code = _closed_exception_code(error)
    if code in {"SACL_STATUS", "SACL_UNAVAILABLE_HASH"}:
        return HOST_SACL_POLICY
    if code in {
        "TOKEN_POLICY",
        "GROUP_SHAPE",
        "UNEXPECTED_ADMIN_TOKEN",
        "UNEXPECTED_PRIVILEGE",
    }:
        return HOST_TOKEN_POLICY
    if code in {"PYTHON_OBJECT_IDENTITY", "PYTHON_ALIAS"}:
        return HOST_RUNTIME_PYTHON_IDENTITY
    if code in {"SECURITY_UNAVAILABLE"}:
        return HOST_SECURITY_COLLECTION
    return HOST_UNKNOWN


# Derived exclusively from the frozen incident contract; never runtime input.
PRESERVED_INCIDENT_NAMES: Final = frozenset(
    PureWindowsPath(path).name for path in INCIDENT_ROOTS
)


def safe_namespace_names(names: object, release_id: str) -> tuple[str, ...]:
    """Validate parent metadata only; preserved names confer no child authority."""
    readonly.validate_destination(release_id, release_root(release_id))
    if type(names) is not tuple or len(names) > 20002:
        raise ValueError("NAMESPACE_UNAVAILABLE")
    normalized = []
    for name in names:
        if type(name) is not str:
            raise ValueError("NAMESPACE_ALIAS")
        lowered = name.casefold()
        if lowered.startswith(release_id):
            raise ValueError("DESTINATION_PRESENT")
        if any(lowered.startswith(identifier) for identifier in INCIDENT_RELEASE_IDS):
            if name not in PRESERVED_INCIDENT_NAMES:
                raise ValueError("INCIDENT_ALIAS")
        else:
            if re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", name) is None or name.endswith(
                (".", " ")
            ):
                raise ValueError("NAMESPACE_ALIAS")
            if name != lowered:
                raise ValueError("NAMESPACE_NONCANONICAL")
            # Canonical ordinary historical releases retain UUID5 validation.
            release_root(name)
        normalized.append(name)
    if len(normalized) != len(set(normalized)):
        raise ValueError("NAMESPACE_ALIAS")
    return tuple(sorted(normalized))


def _namespace_policy_code(error: BaseException) -> str:
    code = _closed_exception_code(error)
    if code == "DESTINATION_PRESENT":
        return HOST_DESTINATION_PRESENT
    if code == "INCIDENT_ALIAS":
        return HOST_INCIDENT_ALIAS
    if code in {
        "NAMESPACE_UNAVAILABLE",
        "NAMESPACE_ALIAS",
        "NAMESPACE_NONCANONICAL",
        "canonical release ID required",
        "UUID5 release ID required",
        "DESTINATION_IDENTITY",
        "DESTINATION_NAMESPACE",
    }:
        return HOST_NAMESPACE_POLICY
    return HOST_UNKNOWN


def _legacy_exception_code(error: BaseException) -> str:
    return _closed_exception_code(error) or HOST_UNKNOWN


def _snapshot(
    session: readonly.ReadonlySession,
    collectors: readonly.AdmissionCollectors,
    invocation: ReviewedInvocation,
    source: readonly.SourceObservation,
) -> dict[str, object]:
    parent = _boundary(HOST_PARENT, readonly.observe_parent, session)
    try:
        ancestors = tuple(session.object(path, directory=True) for path in ANCESTORS)
        if ancestors[-1] != parent:
            raise ValueError("PARENT_DRIFT")
        if len({row.identity for row in ancestors}) != len(ANCESTORS):
            raise ValueError("ANCESTOR_ALIAS")
        for path, row in zip(ANCESTORS, ancestors, strict=True):
            readonly.require_object_shape(row)
            readonly.check_object(
                row,
                path,
                directory=True,
                volume=parent.identity[0],
                image_policy=False,
            )
    except DiagnosticFailure:
        raise
    except BaseException:
        raise DiagnosticFailure(HOST_ANCESTORS) from None

    try:
        entries = session.namespace_metadata()
        if type(entries) is not tuple or len(entries) > 20002:
            raise DiagnosticFailure(HOST_NAMESPACE_COLLECTION)
        identifiers = set()
        for entry in entries:
            if type(entry) is not tuple or len(entry) != 4:
                raise DiagnosticFailure(HOST_NAMESPACE_POLICY)
            name, identity, attributes, short_name = entry
            if (
                type(identity) is not int
                or identity <= 0
                or identity in identifiers
                or type(attributes) is not int
                or not attributes & 0x10
                or attributes & 0x400
                or short_name != ""
            ):
                raise DiagnosticFailure(HOST_NAMESPACE_POLICY)
            identifiers.add(identity)
        try:
            names = safe_namespace_names(
                tuple(row[0] for row in entries), source.manifest.release_id
            )
        except DiagnosticFailure:
            raise
        except BaseException as error:
            raise DiagnosticFailure(_namespace_policy_code(error)) from None
    except DiagnosticFailure:
        raise
    except BaseException:
        raise DiagnosticFailure(HOST_NAMESPACE_COLLECTION) from None

    security = _boundary(HOST_SECURITY_COLLECTION, collectors.security, parent)
    try:
        readonly.require_security(security, invocation)
    except DiagnosticFailure:
        raise
    except BaseException as error:
        raise DiagnosticFailure(_security_policy_code(error)) from None
    if any(
        identity[0] != parent.identity[0]
        for identity in (security.runtime_identity, security.python_identity)
    ):
        raise DiagnosticFailure(HOST_RUNTIME_PYTHON_IDENTITY)

    quiet = _boundary(HOST_QUIESCENCE_COLLECTION, collectors.quiescence)
    try:
        readonly.require_quiescence(quiet)
    except DiagnosticFailure:
        raise
    except BaseException:
        raise DiagnosticFailure(HOST_QUIESCENCE_POLICY) from None
    return {
        "ancestors": [asdict(row) for row in ancestors],
        "namespace_sha256": readonly.digest(tuple(sorted(entries))),
        "namespace_entry_count": len(names),
        "security": asdict(security),
        "quiescence": asdict(quiet),
    }


def _snapshot_unknown(*args, **kwargs) -> dict[str, object]:
    try:
        return _snapshot(*args, **kwargs)
    except DiagnosticFailure:
        raise
    except BaseException:
        raise DiagnosticFailure(HOST_UNKNOWN) from None


def _blocked(code: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "reason": "HOST",
        "diagnostic_code": code if code in DIAGNOSTIC_CODES else HOST_UNKNOWN,
        "effects": dict.fromkeys(ZERO_EFFECTS, 0),
        "authority": dict.fromkeys(NO_AUTHORITY, False),
    }


def admission(
    invocation: ReviewedInvocation,
    collectors: readonly.AdmissionCollectors,
    reader: readonly.ReadonlyReader,
) -> dict[str, object]:
    """Run the v1 read-only observation with a closed host diagnostic layer."""
    try:
        if type(invocation) is not ReviewedInvocation:
            raise DiagnosticFailure(HOST_UNKNOWN)
        first_source = _source_observation(collectors, invocation)
        try:
            context = reader.read_session(first_source.manifest.release_id)
            with context as session:
                first = _snapshot_unknown(session, collectors, invocation, first_source)
                second_source = _source_observation(collectors, invocation)
                second = _snapshot_unknown(
                    session, collectors, invocation, second_source
                )
                if first_source != second_source or first != second:
                    raise DiagnosticFailure(HOST_UNKNOWN)
        except DiagnosticFailure:
            raise
        except BaseException:
            raise DiagnosticFailure(HOST_SESSION) from None
        result = {
            "schema": SCHEMA,
            "status": "PASS",
            "reason": READY,
            "source": {
                "observer": invocation.observer.to_dict(),
                "candidate": readonly.CANDIDATE.to_dict(),
                "design": readonly.DESIGN.to_dict(),
                "successor": readonly.SUCCESSOR.to_dict(),
                "r1_state": "CONSUMED",
                "closure_blob": first_source.closure_blob,
            },
            "manifest": json.loads(first_source.manifest.to_json()),
            "destination": release_root(first_source.manifest.release_id),
            "observations": first,
            "stable_repetitions": 2,
            "effects": dict.fromkeys(ZERO_EFFECTS, 0),
            "authority": dict.fromkeys(NO_AUTHORITY, False),
        }
        encode_evidence(result)
        return result
    except DiagnosticFailure as error:
        return _blocked(error.code)
    except BaseException:
        return _blocked(HOST_UNKNOWN)


def exact_fields(value: object, fields: set[str]) -> None:
    if type(value) is not dict or set(value) != fields:
        raise ValueError("EVIDENCE_FIELDS")


def _require_pass_evidence_shape(value: dict[str, object]) -> None:
    exact_fields(
        value,
        {
            "schema",
            "status",
            "reason",
            "source",
            "manifest",
            "destination",
            "observations",
            "stable_repetitions",
            "effects",
            "authority",
        },
    )
    if (
        value["status"] != "PASS"
        or value["reason"] != READY
        or type(value["stable_repetitions"]) is not int
        or value["stable_repetitions"] != 2
    ):
        raise ValueError("PASS_SCOPE")
    source = value["source"]
    exact_fields(
        source,
        {"observer", "candidate", "design", "successor", "r1_state", "closure_blob"},
    )
    for key, expected in (
        ("candidate", readonly.CANDIDATE),
        ("design", readonly.DESIGN),
        ("successor", readonly.SUCCESSOR),
    ):
        if source[key] != expected.to_dict():
            raise ValueError("EVIDENCE_SOURCE")
    observer = readonly.SourceIdentity(**source["observer"])
    manifest = ReleaseManifest.from_json(canonical_json(value["manifest"]))
    observations = value["observations"]
    exact_fields(
        observations,
        {
            "ancestors",
            "namespace_sha256",
            "namespace_entry_count",
            "security",
            "quiescence",
        },
    )
    readonly.require_digest(observations["namespace_sha256"])
    if (
        type(observations["namespace_entry_count"]) is not int
        or not 0 <= observations["namespace_entry_count"] <= 20002
    ):
        raise ValueError("NAMESPACE_COUNT")
    security = observations["security"]
    exact_fields(
        security,
        {
            "token",
            "privileges",
            "sacl_status",
            "sacl_sha256",
            "effective_parent_access",
            "parent_descriptor_sha256",
            "runtime_identity",
            "python_identity",
        },
    )
    exact_fields(
        security["token"],
        {"user_sid", "token_type", "thread_token_present", "elevated", "groups"},
    )
    token_fields = dict(security["token"])
    token_fields["groups"] = tuple(tuple(row) for row in token_fields["groups"])
    token = TradingTokenObservation(**token_fields)
    invocation = ReviewedInvocation(observer, token.user_sid, token.elevated)
    readonly.require_source(
        readonly.SourceObservation(
            observer,
            readonly.CANDIDATE,
            readonly.DESIGN,
            readonly.SUCCESSOR,
            manifest,
            source["r1_state"],
            source["closure_blob"],
        ),
        invocation,
    )
    readonly.require_security(
        readonly.SecurityObservation(
            token,
            tuple(tuple(row) for row in security["privileges"]),
            security["sacl_status"],
            security["sacl_sha256"],
            security["effective_parent_access"],
            security["parent_descriptor_sha256"],
            tuple(security["runtime_identity"]),
            tuple(security["python_identity"]),
        ),
        invocation,
    )
    readonly.validate_destination(manifest.release_id, value["destination"])
    quiet = observations["quiescence"]
    exact_fields(
        quiet,
        {
            "tasks",
            "process_inventory_sha256",
            "relevant_process_count",
            "reboot_manual_start",
        },
    )
    readonly.require_quiescence(
        readonly.QuiescenceObservation(
            tuple(tuple(row) for row in quiet["tasks"]),
            quiet["process_inventory_sha256"],
            quiet["relevant_process_count"],
            quiet["reboot_manual_start"],
        )
    )
    parents = observations["ancestors"]
    if type(parents) is not list or len(parents) != len(ANCESTORS):
        raise ValueError("ANCESTOR_EVIDENCE")
    facts = {}
    for path, row in zip(ANCESTORS, parents, strict=True):
        exact_fields(
            row,
            {
                "path",
                "kind",
                "identity",
                "owner",
                "protected",
                "aces",
                "filesystem",
                "local",
                "persistent_acls",
                "reparse",
                "links",
                "size",
            },
        )
        item = dict(row)
        item["identity"] = tuple(item["identity"])
        item["aces"] = tuple(tuple(ace) for ace in item["aces"])
        facts[path] = ObjectFacts(**item)
        readonly.require_object_shape(facts[path])

    class ReplayParents:
        def object(self, path, *, directory):
            return facts[path]

    readonly.observe_parent(ReplayParents())


def require_evidence_shape(value: dict[str, object]) -> None:
    if type(value) is not dict or value.get("schema") != SCHEMA:
        raise ValueError("EVIDENCE_SCHEMA")
    fields = {"schema", "status", "reason", "diagnostic_code", "effects", "authority"}
    if "diagnostic_process_starts" in value:
        count = value["diagnostic_process_starts"]
        if type(count) is not int or not 0 <= count <= 1000:
            raise ValueError("DIAGNOSTIC_COUNT")
        fields.add("diagnostic_process_starts")
    exact_fields(value["effects"], set(ZERO_EFFECTS))
    if any(item != 0 or type(item) is not int for item in value["effects"].values()):
        raise ValueError("EFFECT_CEILING")
    exact_fields(value["authority"], set(NO_AUTHORITY))
    if any(item is not False for item in value["authority"].values()):
        raise ValueError("AUTHORITY_CEILING")
    if value.get("status") == "BLOCKED":
        exact_fields(value, fields)
        if (
            value["reason"] != "HOST"
            or value["diagnostic_code"] not in DIAGNOSTIC_CODES
        ):
            raise ValueError("BLOCK_DIAGNOSTIC")
        return
    _require_pass_evidence_shape(
        {key: item for key, item in value.items() if key != "diagnostic_process_starts"}
    )


def encode_evidence(value: dict[str, object]) -> bytes:
    require_evidence_shape(value)
    data = canonical_json(value).encode("utf-8")
    if len(data) > MAX_EVIDENCE_BYTES:
        raise ValueError("EVIDENCE_BOUND")
    return data


def verify_evidence(payload: bytes, *, expected: dict[str, object]) -> None:
    if (
        type(payload) is not bytes
        or len(payload) > MAX_EVIDENCE_BYTES
        or payload != encode_evidence(expected)
    ):
        raise ValueError("NONCANONICAL_OR_MISMATCHED_EVIDENCE")
