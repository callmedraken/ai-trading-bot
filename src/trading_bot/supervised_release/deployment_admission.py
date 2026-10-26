"""Read-only deployment admission; a PASS grants only a later authority review.

Collectors are injected. No collector may open a proposed/incident destination.
The accepted source closure, rather than a consumed latch, proves R1 closure.
"""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from typing import Protocol

from trading_bot.arch133_acl.read_only import ADMINISTRATORS_SID
from trading_bot.arch133_verifier.token import TradingTokenObservation
from trading_bot.supervised_release.bundle import canonical_json
from trading_bot.supervised_release.deployment_candidate import (
    CANDIDATE,
    INCIDENT_RELEASE_IDS,
    SUCCESSOR,
    CandidateFreeze,
    SourceIdentity,
    validate_destination,
)
from trading_bot.supervised_release.installation_contract import (
    ANCESTORS,
    ObjectFacts,
)
from trading_bot.supervised_release.model import (
    ReleaseManifest,
    release_root,
)
from trading_bot.supervised_release.observer import check_object, observe_parent

CHECKPOINT = "arch134-fresh-successor-readonly-deployment-admission"
SCHEMA = CHECKPOINT + "/v1"
BRANCH = (
    "feature/robinhood-production-paper-fresh-successor-"
    "readonly-deployment-admission-current"
)
DESIGN = SourceIdentity(
    CANDIDATE.repository,
    "develop",
    "745b027abfd5cf75ba113b5bb78880af5f55fcce",
    "5f3b784d65d3052e3525fef7a7ed1bad93fa144a",
)
READY = "READY_FOR_SUCCESSOR_ROOT_WRITE_AUTHORITY_AND_ACL_REVIEW"
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
ZERO_EFFECTS = (
    "production_writes",
    "directory_creations",
    "namespace_mutations",
    "acl_mutations",
    "ownership_mutations",
    "privilege_enables",
    "scheduler_mutations",
    "runtime_process_starts",
    "process_stops",
    "credential_accesses",
    "network_requests",
    "provider_calls",
    "paper_calls",
    "broker_calls",
    "live_calls",
    "incident_root_opens",
    "consumed_latch_reads",
    "consumed_latch_writes",
)
NO_AUTHORITY = (
    "materialization_authorized",
    "acl_mutation_authorized",
    "root_creation_authorized",
    "scheduler_binding_authorized",
    "runtime_binding_authorized",
    "f1_authorized",
    "broker_authorized",
    "live_authorized",
    "historical_execute_substitution",
)


def require_sid(value: object) -> None:
    if (
        type(value) is not str
        or re.fullmatch(r"S-1-(?:[0-9]{1,12}-){1,16}[0-9]{1,12}", value) is None
    ):
        raise ValueError("SID_SHAPE")


@dataclass(frozen=True, slots=True)
class ReviewedInvocation:
    observer: SourceIdentity
    principal_sid: str
    elevated: bool

    def __post_init__(self) -> None:
        if (
            type(self.observer) is not SourceIdentity
            or self.observer.repository != CANDIDATE.repository
            or self.observer.reference not in {BRANCH, "develop"}
            or self.observer.head in {CANDIDATE.head, DESIGN.head, SUCCESSOR.head}
            or self.observer.tree in {CANDIDATE.tree, DESIGN.tree, SUCCESSOR.tree}
            or type(self.elevated) is not bool
        ):
            raise ValueError("REVIEWED_OBSERVER_SOURCE_REQUIRED")
        require_sid(self.principal_sid)


@dataclass(frozen=True, slots=True)
class SourceObservation:
    observer: SourceIdentity
    candidate: SourceIdentity
    design: SourceIdentity
    successor: SourceIdentity
    manifest: ReleaseManifest
    r1_state: str
    closure_blob: str


@dataclass(frozen=True, slots=True)
class SecurityObservation:
    token: TradingTokenObservation
    privileges: tuple[tuple[str, int], ...]
    sacl_status: str
    sacl_sha256: str | None
    # Authz/AccessCheck observation of current token, never an attempted write.
    effective_parent_access: int
    parent_descriptor_sha256: str
    runtime_identity: tuple[int, int]
    python_identity: tuple[int, int]


@dataclass(frozen=True, slots=True)
class QuiescenceObservation:
    tasks: tuple[tuple[str, str], ...]
    process_inventory_sha256: str
    relevant_process_count: int
    reboot_manual_start: bool


class AdmissionCollectors(Protocol):
    def source(self, invocation: ReviewedInvocation) -> SourceObservation: ...
    def security(self, parent: ObjectFacts) -> SecurityObservation: ...
    def quiescence(self) -> QuiescenceObservation: ...


class ReadonlySession(Protocol):
    def object(self, path: str, *, directory: bool) -> ObjectFacts | None: ...
    def namespace_metadata(self) -> tuple[tuple[str, int, int, str], ...]: ...


class ReadonlyReader(Protocol):
    def read_session(
        self, release_id: str
    ) -> AbstractContextManager[ReadonlySession]: ...


def require_source(value: SourceObservation, invocation: ReviewedInvocation) -> None:
    from trading_bot.supervised_release.deployment_admission_source import manifest_for

    if (
        type(value) is not SourceObservation
        or value.observer != invocation.observer
        or value.candidate != CANDIDATE
        or value.design != DESIGN
        or value.successor != SUCCESSOR
        or value.r1_state != "CONSUMED"
        or value.closure_blob != "3bfe6666fe2b0ba151938c191289659eacd5a52b"
        or type(value.manifest) is not ReleaseManifest
        or (value.manifest.source_head, value.manifest.source_tree)
        != (CANDIDATE.head, CANDIDATE.tree)
    ):
        raise ValueError("SOURCE_LINEAGE_OR_CLOSURE")
    if value.manifest != manifest_for(value.manifest.source_inventory):
        raise ValueError("MANIFEST_POLICY_IDENTITY")
    validate_destination(
        value.manifest.release_id, release_root(value.manifest.release_id)
    )
    CandidateFreeze()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def require_digest(value: object) -> None:
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("DIGEST_SHAPE")


def require_object_shape(value: ObjectFacts) -> None:
    if (
        type(value) is not ObjectFacts
        or type(value.aces) is not tuple
        or len(value.aces) > 64
        or type(value.links) is not int
        or value.links != 1
        or type(value.size) is not int
        or value.size < 0
        or any(
            type(flag) is not bool
            for flag in (
                value.protected,
                value.reparse,
                value.local,
                value.persistent_acls,
            )
        )
    ):
        raise ValueError("OBJECT_FACT_SHAPE")
    require_sid(value.owner)
    for row in value.aces:
        if type(row) is not tuple or len(row) != 4:
            raise ValueError("ACE_SHAPE")
        sid, mask, kind, flags = row
        require_sid(sid)
        if (
            any(type(number) is not int for number in (mask, kind, flags))
            or not 0 <= mask <= 0xFFFFFFFF
            or kind not in {0, 1}
            or not 0 <= flags <= 31
        ):
            raise ValueError("ACE_SHAPE")


def require_security(
    value: SecurityObservation, invocation: ReviewedInvocation
) -> None:
    if (
        type(value) is not SecurityObservation
        or type(value.token) is not TradingTokenObservation
    ):
        raise ValueError("SECURITY_UNAVAILABLE")
    token = value.token
    if (
        token.user_sid != invocation.principal_sid
        or token.token_type != 1
        or type(token.token_type) is not int
        or token.thread_token_present is not False
        or token.elevated is not invocation.elevated
        or type(token.groups) is not tuple
        or len(token.groups) > 1024
        or type(value.privileges) is not tuple
        or len(value.privileges) > 128
        or type(value.effective_parent_access) is not int
        or not 0 <= value.effective_parent_access <= 0xFFFFFFFF
    ):
        raise ValueError("TOKEN_POLICY")
    seen = set()
    admin_enabled = False
    for row in token.groups:
        if type(row) is not tuple or len(row) != 2:
            raise ValueError("GROUP_SHAPE")
        sid, attributes = row
        require_sid(sid)
        if (
            type(attributes) is not int
            or not 0 <= attributes <= 0xFFFFFFFF
            or sid in seen
        ):
            raise ValueError("GROUP_SHAPE")
        seen.add(sid)
        if sid == ADMINISTRATORS_SID and attributes & 4 and not attributes & 16:
            admin_enabled = True
    if admin_enabled is not invocation.elevated:
        raise ValueError("UNEXPECTED_ADMIN_TOKEN")
    seen.clear()
    for name, attributes in value.privileges:
        if (
            type(name) is not str
            or re.fullmatch(r"Se[A-Za-z]{1,64}Privilege", name) is None
            or name in seen
            or type(attributes) is not int
            or attributes & ~0x80000007
            or (attributes & 2 and name != "SeChangeNotifyPrivilege")
        ):
            raise ValueError("UNEXPECTED_PRIVILEGE")
        seen.add(name)
    if value.sacl_status not in {"AVAILABLE", "ACCESS_DENIED", "PRIVILEGE_NOT_HELD"}:
        raise ValueError("SACL_STATUS")
    if value.sacl_status == "AVAILABLE":
        require_digest(value.sacl_sha256)
    elif value.sacl_sha256 is not None:
        raise ValueError("SACL_UNAVAILABLE_HASH")
    require_digest(value.parent_descriptor_sha256)
    for identity in (value.runtime_identity, value.python_identity):
        if (
            type(identity) is not tuple
            or len(identity) != 2
            or any(type(item) is not int or item <= 0 for item in identity)
        ):
            raise ValueError("PYTHON_OBJECT_IDENTITY")
    if value.runtime_identity == value.python_identity:
        raise ValueError("PYTHON_ALIAS")


def require_quiescence(value: QuiescenceObservation) -> None:
    if (
        type(value) is not QuiescenceObservation
        or value.relevant_process_count != 0
        or type(value.relevant_process_count) is not int
        or value.reboot_manual_start is not True
        or type(value.tasks) is not tuple
        or len(value.tasks) > 256
    ):
        raise ValueError("RUNTIME_OR_SCHEDULER_OVERLAP")
    require_digest(value.process_inventory_sha256)
    seen = set()
    for name, fingerprint in value.tasks:
        # Only sanitized task identities; never task XML/arguments/account data.
        if (
            type(name) is not str
            or re.fullmatch(r"[0-9a-f]{64}", name) is None
            or name in seen
        ):
            raise ValueError("SCHEDULER_SHAPE")
        seen.add(name)
        require_digest(fingerprint)


def safe_namespace_names(names: object, release_id: str) -> tuple[str, ...]:
    validate_destination(release_id, release_root(release_id))
    if type(names) is not tuple or len(names) > 20002:
        raise ValueError("NAMESPACE_UNAVAILABLE")
    normalized = []
    for name in names:
        if (
            type(name) is not str
            or re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", name) is None
            or name.endswith((".", " "))
        ):
            raise ValueError("NAMESPACE_ALIAS")
        lowered = name.casefold()
        # All incident identities block, including suffix-less and partial forms.
        if any(
            lowered.startswith(identifier)
            for identifier in (*INCIDENT_RELEASE_IDS, release_id)
        ):
            raise ValueError("INCIDENT_OR_DESTINATION_PRESENT")
        if name != lowered:
            raise ValueError("NAMESPACE_NONCANONICAL")
        release_root(name)
        normalized.append(lowered)
    if len(normalized) != len(set(normalized)):
        raise ValueError("NAMESPACE_ALIAS")
    return tuple(sorted(normalized))


def snapshot(
    session: ReadonlySession,
    collectors: AdmissionCollectors,
    invocation: ReviewedInvocation,
    source: SourceObservation,
) -> dict[str, object]:
    # Never call object/read on any child of releases. Held parent enumeration
    # proves absence, so neither a fresh root nor an incident root is opened.
    parent = observe_parent(session)
    ancestors = tuple(session.object(path, directory=True) for path in ANCESTORS)
    if ancestors[-1] != parent:
        raise ValueError("PARENT_DRIFT")
    if len({row.identity for row in ancestors}) != len(ANCESTORS):
        raise ValueError("ANCESTOR_ALIAS")
    for path, row in zip(ANCESTORS, ancestors, strict=True):
        require_object_shape(row)
        check_object(
            row, path, directory=True, volume=parent.identity[0], image_policy=False
        )
    entries = session.namespace_metadata()
    if type(entries) is not tuple or len(entries) > 20002:
        raise ValueError("NAMESPACE_METADATA")
    identifiers = set()
    for entry in entries:
        if type(entry) is not tuple or len(entry) != 4:
            raise ValueError("NAMESPACE_METADATA")
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
            raise ValueError("NAMESPACE_OBJECT_ALIAS")
        identifiers.add(identity)
    names = safe_namespace_names(
        tuple(row[0] for row in entries), source.manifest.release_id
    )
    security = collectors.security(parent)
    require_security(security, invocation)
    if any(
        identity[0] != parent.identity[0]
        for identity in (security.runtime_identity, security.python_identity)
    ):
        raise ValueError("PYTHON_VOLUME")
    quiet = collectors.quiescence()
    require_quiescence(quiet)
    return {
        "ancestors": [asdict(row) for row in ancestors],
        "namespace_sha256": digest(tuple(sorted(entries))),
        "namespace_entry_count": len(names),
        "security": asdict(security),
        "quiescence": asdict(quiet),
    }


def admission(
    invocation: ReviewedInvocation,
    collectors: AdmissionCollectors,
    reader: ReadonlyReader,
) -> dict[str, object]:
    """One bounded observation window; no repair, retry or consumed-path use."""
    stage = "SOURCE"
    try:
        if type(invocation) is not ReviewedInvocation:
            raise ValueError("INVOCATION_REQUIRED")
        first_source = collectors.source(invocation)
        require_source(first_source, invocation)
        stage = "HOST"
        with reader.read_session(first_source.manifest.release_id) as session:
            first = snapshot(session, collectors, invocation, first_source)
            stage = "STABILITY"
            second_source = collectors.source(invocation)
            require_source(second_source, invocation)
            second = snapshot(session, collectors, invocation, second_source)
            if first_source != second_source or first != second:
                raise ValueError("OBSERVATION_DRIFT")
        stage = "EVIDENCE"
        result = {
            "schema": SCHEMA,
            "status": "PASS",
            "reason": READY,
            "source": {
                "observer": invocation.observer.to_dict(),
                "candidate": CANDIDATE.to_dict(),
                "design": DESIGN.to_dict(),
                "successor": SUCCESSOR.to_dict(),
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
    except (Exception, KeyboardInterrupt):
        # Never serialize collector errors, descriptors, command output or secrets.
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": stage,
            "effects": dict.fromkeys(ZERO_EFFECTS, 0),
            "authority": dict.fromkeys(NO_AUTHORITY, False),
        }


def encode_evidence(value: dict[str, object]) -> bytes:
    require_evidence_shape(value)
    data = canonical_json(value).encode("utf-8")
    if len(data) > MAX_EVIDENCE_BYTES:
        raise ValueError("EVIDENCE_BOUND")
    return data


def exact_fields(value: object, fields: set[str]) -> None:
    if type(value) is not dict or set(value) != fields:
        raise ValueError("EVIDENCE_FIELDS")


def require_evidence_shape(value: dict[str, object]) -> None:
    """Closed typed output schema, including nested sanitized security facts."""
    if type(value) is not dict or value.get("schema") != SCHEMA:
        raise ValueError("EVIDENCE_SCHEMA")
    fields = {"schema", "status", "reason", "effects", "authority"}
    if "diagnostic_process_starts" in value:
        count = value["diagnostic_process_starts"]
        if type(count) is not int or not 0 <= count <= 1000:
            raise ValueError("DIAGNOSTIC_COUNT")
        fields.add("diagnostic_process_starts")
    exact_fields(value["effects"], set(ZERO_EFFECTS))
    if any(type(item) is not int or item != 0 for item in value["effects"].values()):
        raise ValueError("EFFECT_CEILING")
    exact_fields(value["authority"], set(NO_AUTHORITY))
    if any(item is not False for item in value["authority"].values()):
        raise ValueError("AUTHORITY_CEILING")
    if value["status"] == "BLOCKED":
        exact_fields(value, fields)
        if value["reason"] not in {
            "SOURCE",
            "HOST",
            "STABILITY",
            "EVIDENCE",
            "INVOCATION",
        }:
            raise ValueError("BLOCK_REASON")
        return
    exact_fields(
        value,
        fields
        | {"source", "manifest", "destination", "observations", "stable_repetitions"},
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
        ("candidate", CANDIDATE),
        ("design", DESIGN),
        ("successor", SUCCESSOR),
    ):
        if source[key] != expected.to_dict():
            raise ValueError("EVIDENCE_SOURCE")
    observer = SourceIdentity(**source["observer"])
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
    require_digest(observations["namespace_sha256"])
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
    require_source(
        SourceObservation(
            observer,
            CANDIDATE,
            DESIGN,
            SUCCESSOR,
            manifest,
            source["r1_state"],
            source["closure_blob"],
        ),
        invocation,
    )
    require_security(
        SecurityObservation(
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
    validate_destination(manifest.release_id, value["destination"])
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
    require_quiescence(
        QuiescenceObservation(
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
        require_object_shape(facts[path])

    class ReplayParents:
        def object(self, path, *, directory):
            return facts[path]

    observe_parent(ReplayParents())


def verify_evidence(payload: bytes, *, expected: dict[str, object]) -> None:
    """Replay only exact independently reconstructed evidence, without parsing it."""
    if (
        type(payload) is not bytes
        or len(payload) > MAX_EVIDENCE_BYTES
        or payload != encode_evidence(expected)
    ):
        raise ValueError("NONCANONICAL_OR_MISMATCHED_EVIDENCE")
