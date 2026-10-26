"""Source selection and future read-only admission design; no host dispatch.

All observations are caller-supplied values. Validation cannot certify a host,
materialize a release, renew a consumed attempt, or authorize any later effect.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID, uuid5

from trading_bot.supervised_release.bundle import canonical_json
from trading_bot.supervised_release.model import RELEASES_BASE, release_root

CHECKPOINT = "arch134-fresh-successor-deployment-candidate-admission-source"
SCHEMA = CHECKPOINT + "/v1"
REPOSITORY = "callmedraken/ai-trading-bot"
CANDIDATE_REF = "develop"
CANDIDATE_HEAD = "61836d6adadf25907c0347d42012bc4200a179ff"
CANDIDATE_TREE = "eabbf166db2d14ce7fed603df3f8b6762394e3c7"
SUCCESSOR_REF = (
    "feature/robinhood-production-paper-134f1r1-d1s4-fresh-successor-source-current"
)
SUCCESSOR_HEAD = "b18c6e32606828beeebc540a93c9f05e3e024323"
SUCCESSOR_TREE = "b082c15bc697bf289fc7997b3d7bf87050082dc3"
NEXT_BOUNDARY = "arch134-fresh-successor-readonly-deployment-admission"
INCIDENT_RELEASE_IDS = (
    "release-18d5d329c1d458558e98d7effe523c3b",
    "release-cb94451fc3295a97afffe9fac5d09ff3",
    "release-03c42597246752319956ab96e01ed61c",
)
INCIDENT_ROOTS = tuple(
    release_root(identifier) + (".installing" if index else "")
    for index, identifier in enumerate(INCIDENT_RELEASE_IDS)
)
_SEQUENCE = (
    "terminal-green develop production candidate",
    "exact fresh-successor deployment-admission source",
    "ChatGPT exact-source acceptance",
    "develop integration + terminal gate",
    "local-main reconciliation",
    "real-host READ-ONLY deployment admission",
    "successor-root write-authority / ACL review",
    "separately reviewed protected fresh materialization",
    "manual-start fresh F1 successor soak",
    "fresh F1 evidence",
    "Architecture 145-B",
    "Research Results GUI",
    "large strategy campaigns",
)
_NAMESPACE = UUID("f2268307-a28a-5622-9e8d-84f8426fc062")


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    repository: str
    reference: str
    head: str
    tree: str

    def __post_init__(self) -> None:
        if any(
            type(value) is not str or not value
            for value in (self.repository, self.reference, self.head, self.tree)
        ) or any(
            re.fullmatch("[0-9a-f]{40}", value) is None
            for value in (self.head, self.tree)
        ):
            raise ValueError("canonical source identity required")

    def to_dict(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "reference": self.reference,
            "head": self.head,
            "tree": self.tree,
        }


CANDIDATE = SourceIdentity(REPOSITORY, CANDIDATE_REF, CANDIDATE_HEAD, CANDIDATE_TREE)
SUCCESSOR = SourceIdentity(REPOSITORY, SUCCESSOR_REF, SUCCESSOR_HEAD, SUCCESSOR_TREE)


@dataclass(frozen=True, slots=True)
class CandidateFreeze:
    candidate: SourceIdentity = CANDIDATE
    accepted_successor: SourceIdentity = SUCCESSOR
    r1_state: str = "CONSUMED"

    def __post_init__(self) -> None:
        if (
            type(self.candidate) is not SourceIdentity
            or self.candidate != CANDIDATE
            or type(self.accepted_successor) is not SourceIdentity
            or self.accepted_successor != SUCCESSOR
            or type(self.r1_state) is not str
            or self.r1_state != "CONSUMED"
        ):
            raise ValueError("exact candidate, successor and consumed R1 required")

    @property
    def candidate_id(self) -> str:
        # Versioned logical fields only: no artifact bytes, paths or clocks.
        material = "|".join(
            (
                SCHEMA,
                self.candidate.repository,
                self.candidate.reference,
                self.candidate.head,
                self.candidate.tree,
                self.accepted_successor.reference,
                self.accepted_successor.head,
                self.accepted_successor.tree,
                self.r1_state,
            )
        )
        return str(uuid5(_NAMESPACE, material))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "candidate_id": self.candidate_id,
            "candidate": self.candidate.to_dict(),
            "accepted_successor": self.accepted_successor.to_dict(),
            "selection": "SOURCE_ONLY_NOT_AN_INSTALLED_IMAGE",
            "deployment_mode": "FRESH_SUCCESSOR_ONLY",
            "r1_state": self.r1_state,
            "incident_roots_authoritative": False,
            "forbidden_incident_release_ids": list(INCIDENT_RELEASE_IDS),
            "forbidden_incident_roots": list(INCIDENT_ROOTS),
            "consumed_generation_reuse": False,
            "historical_d1s4_r1_execute_substitution": False,
            "directory_namespace_promotion": False,
            "next_readonly_boundary": NEXT_BOUNDARY,
            "future_sequence": list(_SEQUENCE),
            "host_admission_executed": False,
            "materialization_eligible": False,
            "runtime_binding_eligible": False,
            "successor_soak_eligible": False,
            "scheduler_effects": False,
            "provider_effects": False,
            "broker_effects": False,
            "live_eligible": False,
            "later_steps_authorized": False,
        }

    def to_bytes(self) -> bytes:
        return canonical_json(self.to_dict()).encode("utf-8")


def verify_candidate(
    payload: bytes, *, observed_develop: SourceIdentity
) -> CandidateFreeze:
    """Validate exact canonical source selection against supplied current identity.

    This performs no Git/network/host observation. A later reviewed observer must
    independently establish provenance and freshness of every supplied fact.
    """
    if type(observed_develop) is not SourceIdentity or observed_develop != CANDIDATE:
        raise ValueError("stale or mismatched develop candidate")
    expected = CandidateFreeze()
    if type(payload) is not bytes or len(payload) > 16384:
        raise ValueError("bounded canonical candidate evidence required")
    # Exact byte equality rejects malformed JSON, duplicate keys, extra fields,
    # type coercions, BOMs and noncanonical spellings without parsing untrusted
    # nesting or allocating an arbitrary caller-supplied object graph.
    if payload != expected.to_bytes():
        raise ValueError("noncanonical or mismatched candidate evidence")
    return expected


def validate_destination(release_id: str, destination: str) -> None:
    """Lexical policy only; never resolve, inspect or admit a real destination."""
    if type(release_id) is not str or release_id in INCIDENT_RELEASE_IDS:
        raise ValueError("incident or invalid successor identity forbidden")
    expected = release_root(release_id)
    if type(destination) is not str or destination != expected:
        raise ValueError("unique canonical final destination required")


def readonly_admission_design(freeze: CandidateFreeze) -> dict[str, object]:
    """Describe the next separately reviewed observer, without implementing it."""
    if type(freeze) is not CandidateFreeze or freeze != CandidateFreeze():
        raise ValueError("exact frozen source selection required")
    return {
        "schema": NEXT_BOUNDARY + "/design-v1",
        "candidate_id": freeze.candidate_id,
        "candidate": freeze.candidate.to_dict(),
        "accepted_successor": freeze.accepted_successor.to_dict(),
        "production_namespace": RELEASES_BASE,
        "destination_policy": "ONE_UNIQUE_FINAL_PATH_BEFORE_MATERIALIZATION",
        "forbidden_incident_roots": list(INCIDENT_ROOTS),
        "required_observations": [
            "exact independently accepted candidate repository/ref/HEAD/tree",
            "exact accepted admission implementation HEAD/tree and clean source",
            "Git ancestry and exact accepted fresh-successor HEAD/tree",
            "complete candidate inventory and strategy/config/Python identities",
            "kernel-resolved production namespace, ancestors and object identities",
            "no reparse/link/alias resolution into incident releases or evidence",
            "fresh release-derived final destination absent; "
            "no partial/conflicting material",
            "fresh release-derived attempt absent; R1 remains permanently CONSUMED",
            "current Windows principal SID, token elevation, groups and privileges",
            "parent owner, DACL/SACL availability, inheritance and effective access",
            "filesystem/volume identity and security capabilities "
            "for later root creation",
            "installed immutable predecessor binding "
            "and disabled/quiesced scheduler/runtime",
            "stable repeated observations; no unresolved or unavailable required fact",
        ],
        "observation_limits": [
            "no incident-root traversal, latch renewal or image trust",
            "absence through safe parent metadata; never create a probe root/file",
            "no write, ACL mutation, rename, move, replace or alias publication",
            "no scheduler/runtime mutation or runtime/provider/broker invocation",
            "no credentials, provider/network acquisition or live operation",
        ],
        "failure_policy": "STOP_PRESERVE_NO_REPAIR_RETRY_OR_REUSE",
        "evidence_policy": (
            "EXACT_SOURCE_BOUND_CANONICAL_COMPLETE_STABLE_READONLY_FACTS"
        ),
        "later_review": "SUCCESSOR_ROOT_WRITE_AUTHORITY_AND_ACL_REVIEW",
        "observer_implemented": False,
        "host_admission_pass": False,
        "write_authority": False,
        "materialization_eligible": False,
        "live_eligible": False,
        "later_steps_authorized": False,
    }
