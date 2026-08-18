"""Non-effectful C3 production composition over reviewed C1/C2 authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from trading_bot.market_data import ALPACA_DAILY_SNAPSHOT_DESCRIPTOR
from trading_bot.runtime.windows_authority import WindowsAuthorityError
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)
from trading_bot.runtime.windows_effectful_capture import (
    BoundProductionCapturePlan,
    ProductionCapturePlan,
    ProductionCaptureRequest,
    ProductionProviderLaunchPlan,
    bind_production_capture_plan,
    build_production_provider_launch_plan,
    prepare_production_capture_plan,
)
from trading_bot.runtime.windows_effectful_capture_protocol import (
    IsolatedCaptureChildRequest,
    build_isolated_capture_child_request,
)
from trading_bot.runtime.windows_transactional_authority import (
    WindowsTransactionalAuthority,
)


class WindowsEffectfulCaptureCompositionError(WindowsAuthorityError):
    """C1/C2/C3 production composition is inconsistent or already closed."""


@dataclass(frozen=True, slots=True)
class PreparedProductionCaptureExecution:
    """Nonsecret C3 material bound to one exact C2 reservation/execution pair."""

    capture_plan: ProductionCapturePlan
    bound_capture: BoundProductionCapturePlan
    provider_launch_plan: ProductionProviderLaunchPlan
    child_request: IsolatedCaptureChildRequest

    def __post_init__(self) -> None:
        if type(self.capture_plan) is not ProductionCapturePlan:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution requires ProductionCapturePlan"
            )
        if type(self.bound_capture) is not BoundProductionCapturePlan:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution requires BoundProductionCapturePlan"
            )
        if type(self.provider_launch_plan) is not ProductionProviderLaunchPlan:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution requires ProductionProviderLaunchPlan"
            )
        if type(self.child_request) is not IsolatedCaptureChildRequest:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution requires IsolatedCaptureChildRequest"
            )
        if self.bound_capture.plan is not self.capture_plan:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution capture plan binding is inconsistent"
            )
        if self.provider_launch_plan.bound_capture is not self.bound_capture:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution provider plan binding is inconsistent"
            )
        if self.child_request.reservation_id != self.bound_capture.reservation_id:
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution child reservation binding is inconsistent"
            )
        if (
            self.child_request.capture_request != self.capture_plan.request
            or self.child_request.c2_request_sha256
            != self.capture_plan.c2_request_digest
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "prepared execution child request binding is inconsistent"
            )


class WindowsEffectfulDailySnapshotCapture:
    """C3 production composition root with no external effects in A3."""

    __slots__ = ("_authority", "_closed", "_transactional")

    def __init__(self, authority: ValidatedProductionAuthority) -> None:
        validated = require_validated_production_authority(authority)
        if (
            validated.provider_id != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.provider_id
            or validated.permitted_provider_operation
            != ALPACA_DAILY_SNAPSHOT_DESCRIPTOR.operation
        ):
            raise WindowsEffectfulCaptureCompositionError(
                "C3 authority is not bound to the exact Alpaca daily snapshot operation"
            )
        self._authority = validated
        self._transactional = WindowsTransactionalAuthority(validated)
        self._closed = False

    @property
    def authority(self) -> ValidatedProductionAuthority:
        return self._authority

    @property
    def approved_account_sid(self) -> str:
        return self._authority.approved_account_sid

    @property
    def release_manifest_sha256(self) -> str:
        return self._authority.release_manifest_digest

    def prepare_capture_plan(
        self,
        request: ProductionCaptureRequest,
        requested_at_utc: datetime,
    ) -> ProductionCapturePlan:
        self._require_open()
        return prepare_production_capture_plan(request, requested_at_utc)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._transactional.close()

    def _prepare_execution(
        self,
        plan: ProductionCapturePlan,
        *,
        reservation_id: str,
        execution_id: str,
    ) -> PreparedProductionCaptureExecution:
        self._require_open()
        bound = bind_production_capture_plan(plan, reservation_id)
        launch = build_production_provider_launch_plan(bound)
        child_request = build_isolated_capture_child_request(
            launch,
            execution_id,
            approved_account_sid=self._authority.approved_account_sid,
            release_manifest_sha256=self._authority.release_manifest_digest,
        )
        return PreparedProductionCaptureExecution(
            capture_plan=plan,
            bound_capture=bound,
            provider_launch_plan=launch,
            child_request=child_request,
        )

    def _require_open(self) -> None:
        if self._closed:
            raise WindowsEffectfulCaptureCompositionError(
                "C3 production capture composition is closed"
            )


def prepare_production_execution_for_test(
    capture: WindowsEffectfulDailySnapshotCapture,
    plan: ProductionCapturePlan,
    *,
    reservation_id: str,
    execution_id: str,
) -> PreparedProductionCaptureExecution:
    """Explicit test seam for the future internal C2-to-child binding step."""

    if type(capture) is not WindowsEffectfulDailySnapshotCapture:
        raise TypeError(
            "test execution preparation requires WindowsEffectfulDailySnapshotCapture"
        )
    return capture._prepare_execution(
        plan,
        reservation_id=reservation_id,
        execution_id=execution_id,
    )
