"""Source-owned immutable Architecture-106 first-operation admission profile."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from trading_bot.runtime.paper_operation_execution_inputs import (
    VerifiedPaperOperationExecutionInputs,
)


class PersonalDesktopFirstPaperOperationMismatchError(ValueError):
    """The active post-lock preparation differs from Architecture 106."""


@dataclass(frozen=True, slots=True)
class PersonalDesktopFirstPaperOperationProfile:
    paper_account_id: str
    terminal_checkpoint_id: UUID
    selected_snapshot_id: UUID
    caller_idempotency_key: UUID
    request_id: UUID
    plan_id: UUID
    plan_sha256: str
    plan_byte_length: int
    operation_id: UUID
    application_id: UUID
    operation_root: str
    approved_trading_sid: str


PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE = (
    PersonalDesktopFirstPaperOperationProfile(
        paper_account_id="9415cd7b-bf36-5fba-bd58-a0f99119dc21",
        terminal_checkpoint_id=UUID("1832a2b5-8b63-501a-8f7d-f1722c32307b"),
        selected_snapshot_id=UUID("eba46838-44ae-5bec-97bf-98c6639ae6a7"),
        caller_idempotency_key=UUID("c762ad22-8d10-43d7-a38b-7d95e730c5ea"),
        request_id=UUID("bc0c3aa7-09a0-5534-83bf-0acdf649a2a0"),
        plan_id=UUID("78292abe-6d6c-5ddf-8ffb-46eb8a914fdb"),
        plan_sha256=(
            "7f62c90df051f5c4998cc3303b7a97dfb80294dfd743662c2f9930422cb83666"
        ),
        plan_byte_length=6199,
        operation_id=UUID("307f769a-f09a-539d-b12d-3fb51b973809"),
        application_id=UUID("78a1bae8-51ac-5bf0-b159-500768c758fc"),
        operation_root=r"F:\AITradingBot\Paper-v2\runtime",
        approved_trading_sid=("S-1-5-21-1397534616-3988210162-180023805-1009"),
    )
)


def reconcile_personal_desktop_first_paper_operation(
    *,
    paper_account_id: str,
    plan_id: UUID,
    selected_snapshot_id: UUID,
    plan_sha256: str,
    plan_byte_length: int,
    operation_root: str,
    inputs: VerifiedPaperOperationExecutionInputs,
) -> None:
    """Require every frozen identity from the active mutex-protected binding."""

    if type(inputs) is not VerifiedPaperOperationExecutionInputs:
        raise PersonalDesktopFirstPaperOperationMismatchError(
            "first paper-operation execution inputs are invalid"
        )
    profile = PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE
    observed = (
        paper_account_id,
        inputs.intent.terminal_checkpoint_artifact.artifact_id,
        inputs.verified_prior.checkpoint_id,
        selected_snapshot_id,
        inputs.intent.completed_snapshot_artifact.artifact_id,
        inputs.intent.caller_idempotency_key,
        inputs.request.request_id,
        plan_id,
        plan_sha256,
        plan_byte_length,
        inputs.intent.cycle_configuration_artifact.sha256,
        inputs.intent.cycle_configuration_artifact.byte_length,
        inputs.intent.operation_id,
        inputs.application_id,
        operation_root,
    )
    expected = (
        profile.paper_account_id,
        profile.terminal_checkpoint_id,
        profile.terminal_checkpoint_id,
        profile.selected_snapshot_id,
        profile.selected_snapshot_id,
        profile.caller_idempotency_key,
        profile.request_id,
        profile.plan_id,
        profile.plan_sha256,
        profile.plan_byte_length,
        profile.plan_sha256,
        profile.plan_byte_length,
        profile.operation_id,
        profile.application_id,
        profile.operation_root,
    )
    if observed != expected:
        raise PersonalDesktopFirstPaperOperationMismatchError(
            "active preparation differs from the frozen first paper operation"
        )
