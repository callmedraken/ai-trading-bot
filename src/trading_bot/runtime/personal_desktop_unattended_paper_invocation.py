"""Pure canonical unattended Paper-v2 invocation evidence for PD4-A."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from uuid import UUID, uuid5

from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import (
    XNYS_CALENDAR_DESCRIPTOR,
    IdentifiedMarketCalendar,
)
from trading_bot.runtime.manual_paper_strategy_plan import (
    ManualPaperStrategyPlan,
    ManualPaperStrategyPlanArtifactBinding,
    ManualPaperStrategyPlanError,
    parse_manual_paper_strategy_plan,
    verify_manual_paper_strategy_plan,
)

UNATTENDED_PAPER_INVOCATION_SCHEMA = "personal-desktop-unattended-paper-invocation/v1"
UNATTENDED_PAPER_INVOCATION_IDENTITY_MATERIAL_VERSION = (
    "personal-desktop-unattended-paper-invocation-identity/v1"
)
UNATTENDED_PAPER_INVOCATION_NAMESPACE = UUID("fd618526-0508-56be-b8e9-7316b813b585")
UNATTENDED_PAPER_POLICY_VERSION = "personal-desktop-unattended-paper-policy/v1"
MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES = 16 * 1024 * 1024

# The shorter spelling is useful to callers that refer to the artifact without
# repeating the source-owned profile name.
MAX_UNATTENDED_PAPER_INVOCATION_BYTES = (
    MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_PAPER_ACCOUNT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_INTEGER = (1 << 63) - 1
_ROOT_FIELDS = frozenset(
    {
        "execution_session",
        "invocation_id",
        "paper_account_id",
        "plan_artifact_utf8",
        "plan_byte_length",
        "plan_id",
        "plan_sha256",
        "policy_version",
        "predecessor_checkpoint_id",
        "schema",
        "selected_snapshot_id",
        "selection_id",
    }
)


class PersonalDesktopUnattendedPaperInvocationError(Exception):
    """Base class for pure unattended-invocation failures."""


class PersonalDesktopUnattendedPaperInvocationValidationError(
    PersonalDesktopUnattendedPaperInvocationError, ValueError
):
    """Raised when an immutable invocation model is invalid."""


class PersonalDesktopUnattendedPaperInvocationSerializationError(
    PersonalDesktopUnattendedPaperInvocationError, ValueError
):
    """Raised when invocation bytes violate the strict canonical schema."""


class PersonalDesktopUnattendedPaperInvocationVerificationError(
    PersonalDesktopUnattendedPaperInvocationError, ValueError
):
    """Raised when detached invocation or plan evidence fails replay."""


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperInvocation:
    """Exact semantic identity and detached plan bytes for one invocation."""

    invocation_id: UUID
    paper_account_id: str
    predecessor_checkpoint_id: UUID
    execution_session: TradingSession
    selection_id: UUID
    selected_snapshot_id: UUID
    plan_id: UUID
    plan_sha256: str
    plan_byte_length: int
    plan_artifact: bytes
    policy_version: str = UNATTENDED_PAPER_POLICY_VERSION
    schema: str = UNATTENDED_PAPER_INVOCATION_SCHEMA

    def __post_init__(self) -> None:
        if type(self.invocation_id) is not UUID:
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "invocation_id must be an exact UUID"
            )
        if (
            type(self.paper_account_id) is not str
            or _PAPER_ACCOUNT_ID_PATTERN.fullmatch(self.paper_account_id) is None
        ):
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "paper_account_id must be bounded canonical ASCII text"
            )
        for name in (
            "predecessor_checkpoint_id",
            "selection_id",
            "selected_snapshot_id",
            "plan_id",
        ):
            if type(getattr(self, name)) is not UUID:
                raise PersonalDesktopUnattendedPaperInvocationValidationError(
                    f"{name} must be an exact UUID"
                )
        if type(self.execution_session) is not TradingSession:
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "execution_session must be an exact TradingSession"
            )
        if (
            type(self.policy_version) is not str
            or self.policy_version != UNATTENDED_PAPER_POLICY_VERSION
        ):
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "policy_version is not the frozen unattended policy"
            )
        if (
            type(self.schema) is not str
            or self.schema != UNATTENDED_PAPER_INVOCATION_SCHEMA
        ):
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "schema is not the frozen unattended invocation schema"
            )
        _validate_sha(
            self.plan_sha256,
            "plan_sha256",
            PersonalDesktopUnattendedPaperInvocationValidationError,
        )
        _validate_positive_integer(
            self.plan_byte_length,
            "plan_byte_length",
            PersonalDesktopUnattendedPaperInvocationValidationError,
        )
        if type(self.plan_artifact) is not bytes or not self.plan_artifact:
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "plan_artifact must be nonempty exact bytes"
            )
        if len(self.plan_artifact) != self.plan_byte_length:
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "plan_byte_length does not match plan_artifact"
            )
        if sha256(self.plan_artifact).hexdigest() != self.plan_sha256:
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "plan_sha256 does not match plan_artifact"
            )
        try:
            plan = parse_manual_paper_strategy_plan(self.plan_artifact)
        except ManualPaperStrategyPlanError as error:
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "plan_artifact is not an exact canonical ManualPaperStrategyPlan"
            ) from error
        _require_plan_binding(self, plan)
        if self.invocation_id != _invocation_id(self):
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                "invocation_id does not match canonical semantic identity"
            )


@dataclass(frozen=True, slots=True)
class PersonalDesktopUnattendedPaperInvocationArtifactBinding:
    """Immutable non-authorizing outer artifact and replayed plan evidence."""

    invocation: PersonalDesktopUnattendedPaperInvocation
    artifact_bytes: bytes
    artifact_sha256: str
    artifact_byte_length: int
    replayed_plan: ManualPaperStrategyPlanArtifactBinding

    def __post_init__(self) -> None:
        if type(self.invocation) is not PersonalDesktopUnattendedPaperInvocation:
            raise PersonalDesktopUnattendedPaperInvocationVerificationError(
                "invocation must be exact"
            )
        if type(self.artifact_bytes) is not bytes or not self.artifact_bytes:
            raise PersonalDesktopUnattendedPaperInvocationVerificationError(
                "artifact_bytes must be nonempty exact bytes"
            )
        _validate_sha(
            self.artifact_sha256,
            "artifact_sha256",
            PersonalDesktopUnattendedPaperInvocationVerificationError,
        )
        _validate_positive_integer(
            self.artifact_byte_length,
            "artifact_byte_length",
            PersonalDesktopUnattendedPaperInvocationVerificationError,
        )
        if len(self.artifact_bytes) != self.artifact_byte_length:
            raise PersonalDesktopUnattendedPaperInvocationVerificationError(
                "artifact_byte_length does not match artifact_bytes"
            )
        if sha256(self.artifact_bytes).hexdigest() != self.artifact_sha256:
            raise PersonalDesktopUnattendedPaperInvocationVerificationError(
                "artifact_sha256 does not match artifact_bytes"
            )
        if (
            len(self.artifact_bytes)
            > MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES
        ):
            raise PersonalDesktopUnattendedPaperInvocationVerificationError(
                "serialized invocation exceeds the 16 MiB bound"
            )
        if type(self.replayed_plan) is not ManualPaperStrategyPlanArtifactBinding:
            raise PersonalDesktopUnattendedPaperInvocationVerificationError(
                "replayed_plan must be an exact ManualPaperStrategyPlanArtifactBinding"
            )
        if (
            self.invocation.plan_artifact != self.replayed_plan.artifact_bytes
            or self.invocation.plan_sha256 != self.replayed_plan.artifact_sha256
            or self.invocation.plan_byte_length
            != self.replayed_plan.artifact_byte_length
        ):
            raise PersonalDesktopUnattendedPaperInvocationVerificationError(
                "invocation does not retain the replayed plan artifact evidence"
            )
        _require_plan_binding(self.invocation, self.replayed_plan.plan)
        if (
            serialize_personal_desktop_unattended_paper_invocation(self.invocation)
            != self.artifact_bytes
        ):
            raise PersonalDesktopUnattendedPaperInvocationVerificationError(
                "artifact bytes do not serialize the retained invocation"
            )

    @property
    def replayed_plan_binding(self) -> ManualPaperStrategyPlanArtifactBinding:
        """Alias naming the embedded plan's detached binding explicitly."""
        return self.replayed_plan

    @property
    def replayed_manual_paper_strategy_plan(
        self,
    ) -> ManualPaperStrategyPlanArtifactBinding:
        """Alias for callers that use the full predecessor artifact name."""
        return self.replayed_plan


# Evidence and binding are the same immutable, non-authorizing result.
PersonalDesktopUnattendedPaperInvocationArtifactEvidence = (
    PersonalDesktopUnattendedPaperInvocationArtifactBinding
)
VerifiedPersonalDesktopUnattendedPaperInvocation = (
    PersonalDesktopUnattendedPaperInvocationArtifactBinding
)


def create_personal_desktop_unattended_paper_invocation(
    binding: ManualPaperStrategyPlanArtifactBinding,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperInvocation:
    """Create one invocation after exact detached plan replay."""
    if type(binding) is not ManualPaperStrategyPlanArtifactBinding:
        raise PersonalDesktopUnattendedPaperInvocationValidationError(
            "binding must be an exact ManualPaperStrategyPlanArtifactBinding"
        )
    replayed = _verify_plan_binding(binding, calendar)
    if replayed != binding:
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "supplied strategy-plan binding differs from exact replay"
        )
    plan = replayed.plan
    try:
        return PersonalDesktopUnattendedPaperInvocation(
            _invocation_id_from_plan(
                plan,
                replayed.artifact_sha256,
                replayed.artifact_byte_length,
            ),
            plan.paper_account_id,
            plan.prior_checkpoint.checkpoint_id,
            _execution_session(plan),
            plan.selected_c3_assertion.selection_id,
            plan.selected_c3_assertion.snapshot_id,
            plan.plan_id,
            replayed.artifact_sha256,
            replayed.artifact_byte_length,
            replayed.artifact_bytes,
        )
    except PersonalDesktopUnattendedPaperInvocationError:
        raise
    except Exception as error:
        raise PersonalDesktopUnattendedPaperInvocationValidationError(
            "verified strategy-plan binding cannot form an invocation"
        ) from error


def serialize_personal_desktop_unattended_paper_invocation(
    invocation: PersonalDesktopUnattendedPaperInvocation,
) -> bytes:
    """Serialize one invocation as canonical UTF-8 JSON with one final newline."""
    if type(invocation) is not PersonalDesktopUnattendedPaperInvocation:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation must be an exact PersonalDesktopUnattendedPaperInvocation"
        )
    try:
        plan_text = invocation.plan_artifact.decode("utf-8")
        payload = _canonical_json_bytes(_invocation_tree(invocation, plan_text))
    except (UnicodeDecodeError, TypeError, ValueError, UnicodeError) as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation cannot be serialized as canonical JSON"
        ) from error
    if len(payload) > MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "serialized invocation exceeds the 16 MiB bound"
        )
    return payload


def parse_personal_desktop_unattended_paper_invocation(
    payload: bytes,
    calendar: IdentifiedMarketCalendar,
) -> PersonalDesktopUnattendedPaperInvocation:
    """Parse and exactly replay one canonical invocation artifact."""
    invocation, _ = _parse_and_verify(payload, calendar)
    return invocation


def verify_personal_desktop_unattended_paper_invocation(
    payload: bytes,
    calendar: IdentifiedMarketCalendar,
    *,
    expected_invocation_id: UUID | None = None,
    expected_artifact_sha256: str | None = None,
    expected_artifact_byte_length: int | None = None,
) -> PersonalDesktopUnattendedPaperInvocationArtifactBinding:
    """Verify outer detached evidence and replay its embedded manual plan."""
    if type(payload) is not bytes:
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "payload must be exact bytes"
        )
    _validate_expected_uuid(expected_invocation_id)
    _validate_expected_sha(expected_artifact_sha256)
    _validate_expected_length(expected_artifact_byte_length)
    actual_sha = sha256(payload).hexdigest()
    actual_length = len(payload)
    if expected_artifact_sha256 is not None and actual_sha != expected_artifact_sha256:
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "artifact SHA-256 does not match expected detached evidence"
        )
    if (
        expected_artifact_byte_length is not None
        and actual_length != expected_artifact_byte_length
    ):
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "artifact byte length does not match expected detached evidence"
        )
    invocation, replayed = _parse_and_verify(payload, calendar)
    if (
        expected_invocation_id is not None
        and invocation.invocation_id != expected_invocation_id
    ):
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "invocation_id does not match expected detached evidence"
        )
    return PersonalDesktopUnattendedPaperInvocationArtifactBinding(
        invocation,
        payload,
        actual_sha,
        actual_length,
        replayed,
    )


def derive_personal_desktop_unattended_paper_invocation_id(
    *,
    paper_account_id: str,
    predecessor_checkpoint_id: UUID,
    execution_session: TradingSession,
    selection_id: UUID,
    selected_snapshot_id: UUID,
    plan_id: UUID,
    plan_sha256: str,
    plan_byte_length: int,
    policy_version: str = UNATTENDED_PAPER_POLICY_VERSION,
) -> UUID:
    """Derive the frozen UUID5 identity from explicit semantic fields only."""
    if (
        type(paper_account_id) is not str
        or _PAPER_ACCOUNT_ID_PATTERN.fullmatch(paper_account_id) is None
    ):
        raise PersonalDesktopUnattendedPaperInvocationValidationError(
            "paper_account_id must be bounded canonical ASCII text"
        )
    if type(execution_session) is not TradingSession:
        raise PersonalDesktopUnattendedPaperInvocationValidationError(
            "execution_session must be an exact TradingSession"
        )
    for name, value in (
        ("predecessor_checkpoint_id", predecessor_checkpoint_id),
        ("selection_id", selection_id),
        ("selected_snapshot_id", selected_snapshot_id),
        ("plan_id", plan_id),
    ):
        if type(value) is not UUID:
            raise PersonalDesktopUnattendedPaperInvocationValidationError(
                f"{name} must be an exact UUID"
            )
    _validate_sha(
        plan_sha256,
        "plan_sha256",
        PersonalDesktopUnattendedPaperInvocationValidationError,
    )
    _validate_positive_integer(
        plan_byte_length,
        "plan_byte_length",
        PersonalDesktopUnattendedPaperInvocationValidationError,
    )
    if (
        type(policy_version) is not str
        or policy_version != UNATTENDED_PAPER_POLICY_VERSION
    ):
        raise PersonalDesktopUnattendedPaperInvocationValidationError(
            "policy_version is not the frozen unattended policy"
        )
    return uuid5(
        UNATTENDED_PAPER_INVOCATION_NAMESPACE,
        _framed_material(
            (
                UNATTENDED_PAPER_INVOCATION_IDENTITY_MATERIAL_VERSION,
                policy_version,
                paper_account_id,
                str(predecessor_checkpoint_id),
                execution_session.session_date.isoformat(),
                str(selection_id),
                str(selected_snapshot_id),
                str(plan_id),
                plan_sha256,
                str(plan_byte_length),
            )
        ),
    )


def _parse_and_verify(
    payload: bytes,
    calendar: IdentifiedMarketCalendar,
) -> tuple[
    PersonalDesktopUnattendedPaperInvocation,
    ManualPaperStrategyPlanArtifactBinding,
]:
    root = _object(_load_json(payload), _ROOT_FIELDS, "root")
    try:
        plan_text = _string(root["plan_artifact_utf8"], "plan_artifact_utf8")
        try:
            plan_artifact = plan_text.encode("utf-8")
        except UnicodeEncodeError as error:
            raise PersonalDesktopUnattendedPaperInvocationSerializationError(
                "plan_artifact_utf8 cannot be encoded as UTF-8"
            ) from error
        invocation = PersonalDesktopUnattendedPaperInvocation(
            _uuid(root["invocation_id"], "invocation_id"),
            _paper_account_id(root["paper_account_id"]),
            _uuid(
                root["predecessor_checkpoint_id"],
                "predecessor_checkpoint_id",
            ),
            _session(root["execution_session"], "execution_session"),
            _uuid(root["selection_id"], "selection_id"),
            _uuid(root["selected_snapshot_id"], "selected_snapshot_id"),
            _uuid(root["plan_id"], "plan_id"),
            _sha(root["plan_sha256"], "plan_sha256"),
            _positive_integer(root["plan_byte_length"], "plan_byte_length"),
            plan_artifact,
            _string(root["policy_version"], "policy_version"),
            _string(root["schema"], "schema"),
        )
    except PersonalDesktopUnattendedPaperInvocationSerializationError:
        raise
    except PersonalDesktopUnattendedPaperInvocationValidationError as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation fields do not reconcile"
        ) from error
    except Exception as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation model does not reconcile"
        ) from error

    try:
        replayed = verify_manual_paper_strategy_plan(
            invocation.plan_artifact,
            calendar,
            expected_sha256=invocation.plan_sha256,
            expected_byte_length=invocation.plan_byte_length,
        )
    except ManualPaperStrategyPlanError as error:
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "embedded manual strategy plan failed exact detached replay"
        ) from error
    if replayed.artifact_bytes != invocation.plan_artifact:
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "replayed plan bytes differ from embedded plan bytes"
        )
    try:
        _require_plan_binding(invocation, replayed.plan)
    except PersonalDesktopUnattendedPaperInvocationValidationError as error:
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "top-level invocation identity does not match replayed plan"
        ) from error
    if serialize_personal_desktop_unattended_paper_invocation(invocation) != payload:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation bytes are not the canonical representation"
        )
    return invocation, replayed


def _verify_plan_binding(
    binding: ManualPaperStrategyPlanArtifactBinding,
    calendar: IdentifiedMarketCalendar,
) -> ManualPaperStrategyPlanArtifactBinding:
    _require_xnys_calendar(calendar)
    try:
        replayed = verify_manual_paper_strategy_plan(
            binding.artifact_bytes,
            calendar,
            expected_sha256=binding.artifact_sha256,
            expected_byte_length=binding.artifact_byte_length,
            expected_checkpointed_request=binding.checkpointed_request,
        )
    except ManualPaperStrategyPlanError as error:
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "supplied manual strategy plan failed exact detached replay"
        ) from error
    return replayed


def _require_xnys_calendar(calendar: IdentifiedMarketCalendar) -> None:
    if getattr(calendar, "descriptor", None) != XNYS_CALENDAR_DESCRIPTOR or any(
        not callable(getattr(calendar, name, None))
        for name in (
            "is_trading_session",
            "next_session",
            "previous_session",
            "sessions_between",
        )
    ):
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "calendar must expose the exact identified XNYS calendar"
        )


def _invocation_id_from_plan(
    plan: ManualPaperStrategyPlan,
    plan_sha256: str,
    plan_byte_length: int,
) -> UUID:
    return derive_personal_desktop_unattended_paper_invocation_id(
        paper_account_id=plan.paper_account_id,
        predecessor_checkpoint_id=plan.prior_checkpoint.checkpoint_id,
        execution_session=_execution_session(plan),
        selection_id=plan.selected_c3_assertion.selection_id,
        selected_snapshot_id=plan.selected_c3_assertion.snapshot_id,
        plan_id=plan.plan_id,
        plan_sha256=plan_sha256,
        plan_byte_length=plan_byte_length,
    )


def _invocation_id(invocation: PersonalDesktopUnattendedPaperInvocation) -> UUID:
    return derive_personal_desktop_unattended_paper_invocation_id(
        paper_account_id=invocation.paper_account_id,
        predecessor_checkpoint_id=invocation.predecessor_checkpoint_id,
        execution_session=invocation.execution_session,
        selection_id=invocation.selection_id,
        selected_snapshot_id=invocation.selected_snapshot_id,
        plan_id=invocation.plan_id,
        plan_sha256=invocation.plan_sha256,
        plan_byte_length=invocation.plan_byte_length,
        policy_version=invocation.policy_version,
    )


def _execution_session(plan: ManualPaperStrategyPlan) -> TradingSession:
    references = plan.request_core.open_references
    if len(references) != 1:
        raise PersonalDesktopUnattendedPaperInvocationValidationError(
            "unattended Paper-v2 v1 requires exactly one open reference"
        )
    return references[0].session


def _require_plan_binding(
    invocation: PersonalDesktopUnattendedPaperInvocation,
    plan: ManualPaperStrategyPlan,
) -> None:
    if (
        plan.paper_account_id != invocation.paper_account_id
        or plan.prior_checkpoint.checkpoint_id != invocation.predecessor_checkpoint_id
        or plan.selected_c3_assertion.selection_id != invocation.selection_id
        or plan.selected_c3_assertion.snapshot_id != invocation.selected_snapshot_id
        or plan.plan_id != invocation.plan_id
        or _execution_session(plan) != invocation.execution_session
    ):
        raise PersonalDesktopUnattendedPaperInvocationValidationError(
            "top-level identity fields do not match the embedded manual plan"
        )


def _invocation_tree(
    invocation: PersonalDesktopUnattendedPaperInvocation,
    plan_text: str,
) -> dict[str, object]:
    return {
        "execution_session": invocation.execution_session.session_date.isoformat(),
        "invocation_id": str(invocation.invocation_id),
        "paper_account_id": invocation.paper_account_id,
        "plan_artifact_utf8": plan_text,
        "plan_byte_length": invocation.plan_byte_length,
        "plan_id": str(invocation.plan_id),
        "plan_sha256": invocation.plan_sha256,
        "policy_version": invocation.policy_version,
        "predecessor_checkpoint_id": str(invocation.predecessor_checkpoint_id),
        "schema": invocation.schema,
        "selected_snapshot_id": str(invocation.selected_snapshot_id),
        "selection_id": str(invocation.selection_id),
    }


def _canonical_json_bytes(tree: object) -> bytes:
    try:
        return (
            json.dumps(
                tree,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation cannot be serialized as canonical JSON"
        ) from error


def _load_json(payload: bytes) -> object:
    if type(payload) is not bytes:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "payload must be exact bytes"
        )
    if len(payload) > MAX_PERSONAL_DESKTOP_UNATTENDED_PAPER_INVOCATION_BYTES:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation payload exceeds the 16 MiB bound"
        )
    if payload.startswith(b"\xef\xbb\xbf"):
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "UTF-8 BOM is not permitted"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation payload is not valid UTF-8"
        ) from error
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation JSON must have exactly one final newline"
        )
    core = text[:-1]
    if not core or core != core.strip():
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "invocation JSON has leading or trailing whitespace"
        )
    try:
        return json.loads(
            core,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"invocation JSON is invalid at line {error.lineno} column {error.colno}"
        ) from error


def _object(value: object, fields: frozenset[str], path: str) -> dict[str, object]:
    if type(value) is not dict:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: expected object"
        )
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        unknown = sorted(actual - fields)
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown fields: {', '.join(unknown)}")
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: {'; '.join(details)}"
        )
    return value


def _string(value: object, path: str) -> str:
    if type(value) is not str:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: expected string"
        )
    return value


def _uuid(value: object, path: str) -> UUID:
    text = _string(value, path)
    try:
        parsed = UUID(text)
    except ValueError as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: expected canonical UUID"
        ) from error
    if str(parsed) != text:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: UUID is not canonical"
        )
    return parsed


def _session(value: object, path: str) -> TradingSession:
    text = _string(value, path)
    if _DATE_PATTERN.fullmatch(text) is None:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: expected canonical session date"
        )
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: invalid session date"
        ) from error
    if parsed.isoformat() != text:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: session date is not canonical"
        )
    try:
        return TradingSession(parsed)
    except (TypeError, ValueError) as error:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            f"{path}: invalid session date"
        ) from error


def _sha(value: object, path: str) -> str:
    text = _string(value, path)
    _validate_sha(
        text, path, PersonalDesktopUnattendedPaperInvocationSerializationError
    )
    return text


def _positive_integer(value: object, path: str) -> int:
    _validate_positive_integer(
        value, path, PersonalDesktopUnattendedPaperInvocationSerializationError
    )
    return value  # type: ignore[return-value]


def _paper_account_id(value: object) -> str:
    if type(value) is not str or _PAPER_ACCOUNT_ID_PATTERN.fullmatch(value) is None:
        raise PersonalDesktopUnattendedPaperInvocationSerializationError(
            "paper_account_id must be bounded canonical ASCII text"
        )
    return value


def _validate_sha(
    value: object,
    name: str,
    error_type: type[Exception],
) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise error_type(f"{name} must be lowercase SHA-256")


def _validate_positive_integer(
    value: object,
    name: str,
    error_type: type[Exception],
) -> None:
    if type(value) is not int or not 1 <= value <= _MAX_INTEGER:
        raise error_type(f"{name} must be a bounded positive integer")


def _validate_expected_uuid(value: UUID | None) -> None:
    if value is not None and type(value) is not UUID:
        raise PersonalDesktopUnattendedPaperInvocationVerificationError(
            "expected_invocation_id must be an exact UUID or None"
        )


def _validate_expected_sha(value: str | None) -> None:
    if value is not None:
        _validate_sha(
            value,
            "expected_artifact_sha256",
            PersonalDesktopUnattendedPaperInvocationVerificationError,
        )


def _validate_expected_length(value: int | None) -> None:
    if value is not None:
        _validate_positive_integer(
            value,
            "expected_artifact_byte_length",
            PersonalDesktopUnattendedPaperInvocationVerificationError,
        )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PersonalDesktopUnattendedPaperInvocationSerializationError(
                f"duplicate JSON object key: {key}"
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise PersonalDesktopUnattendedPaperInvocationSerializationError(
        f"nonstandard JSON constant is not permitted: {value}"
    )


def _framed_material(parts: tuple[str, ...]) -> str:
    return "".join(f"{len(part.encode('utf-8'))}:{part}" for part in parts)
