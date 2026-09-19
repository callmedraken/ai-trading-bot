"""Supervised post-lock Paper-v2 account composition without mutation.

The pre-lock account read contributes only immutable account identity to PD2A
mutex admission.  The account authority exposed by this active scope is always
the second, post-lock read made through the same genuine production authority.
PD2B1 performs no paper operation, transition, receipt, recovery, provider, or
broker effect.
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import Protocol, Self

from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
)
from trading_bot.runtime.personal_desktop_paper_account_mutex import (
    PaperAccountMutexAcquisition,
    SupervisedPaperCycleAdmission,
    supervised_paper_cycle_admission,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    PersonalDesktopPaperAccountReadEvidence,
    ValidatedPersonalDesktopPaperAccount,
    read_personal_desktop_paper_account,
    require_validated_personal_desktop_paper_account,
)
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)


class SupervisedPersonalDesktopPaperCycleError(PersonalDesktopPaperAccountError):
    """The supervised post-lock account composition failed closed."""


class _ReadAccount(Protocol):
    def __call__(
        self,
        authority: ValidatedProductionAuthority,
        *,
        historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
    ) -> ValidatedPersonalDesktopPaperAccount: ...


class _AdmitAccount(Protocol):
    def __call__(
        self, authority: ValidatedPersonalDesktopPaperAccount
    ) -> SupervisedPaperCycleAdmission: ...


_SCOPE_KEY = object()


class SupervisedPersonalDesktopPaperCycle:
    """One active PD2A mutex scope exposing only post-lock account evidence."""

    __slots__ = (
        "_acquisition",
        "_admit_account",
        "_authority",
        "_configurations",
        "_exit_stack",
        "_operation_root",
        "_post_lock_account",
        "_read_account",
        "_used",
    )

    def __init__(
        self,
        authority: ValidatedProductionAuthority,
        configurations: tuple[bytes, ...],
        *,
        read_account: _ReadAccount,
        admit_account: _AdmitAccount,
        _key: object,
    ) -> None:
        if _key is not _SCOPE_KEY:
            raise SupervisedPersonalDesktopPaperCycleError(
                "supervised paper cycle requires production authority"
            )
        self._authority = authority
        self._configurations = configurations
        self._read_account = read_account
        self._admit_account = admit_account
        self._exit_stack: ExitStack | None = None
        self._post_lock_account: ValidatedPersonalDesktopPaperAccount | None = None
        self._acquisition: PaperAccountMutexAcquisition | None = None
        self._operation_root: str | None = None
        self._used = False

    def __enter__(self) -> Self:
        if self._used:
            raise SupervisedPersonalDesktopPaperCycleError(
                "supervised paper cycle scope is one-shot"
            )
        self._used = True
        pre_lock_account = self._read_account(
            self._authority,
            historical_cycle_configuration_payloads=self._configurations,
        )
        pre_lock_evidence = require_validated_personal_desktop_paper_account(
            pre_lock_account
        )
        pre_lock_account_id = pre_lock_evidence.anchor.paper_account_id
        admission = self._admit_account(pre_lock_account)
        stack = ExitStack()
        try:
            held_admission = stack.enter_context(admission)
            acquisition = held_admission.acquisition
            if acquisition is None:
                raise SupervisedPersonalDesktopPaperCycleError(
                    "paper-account mutex did not expose acquisition evidence"
                )
            if acquisition.paper_account_id != pre_lock_account_id:
                raise SupervisedPersonalDesktopPaperCycleError(
                    "paper-account mutex acquisition identity does not match "
                    "pre-lock account"
                )
            post_lock_account = self._read_account(
                self._authority,
                historical_cycle_configuration_payloads=self._configurations,
            )
            post_lock_evidence = require_validated_personal_desktop_paper_account(
                post_lock_account
            )
            post_lock_account_id = post_lock_evidence.anchor.paper_account_id
            if (
                post_lock_account_id != pre_lock_account_id
                or post_lock_account_id != acquisition.paper_account_id
            ):
                raise SupervisedPersonalDesktopPaperCycleError(
                    "post-lock paper-account identity does not reconcile"
                )
            operation_root = post_lock_account.operation_root
            self._post_lock_account = post_lock_account
            self._acquisition = acquisition
            self._operation_root = operation_root
            self._exit_stack = stack
            return self
        except BaseException:
            stack.close()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        stack, self._exit_stack = self._exit_stack, None
        if stack is None:
            raise SupervisedPersonalDesktopPaperCycleError(
                "supervised paper cycle scope is not active"
            )
        self._post_lock_account = None
        self._acquisition = None
        self._operation_root = None
        return stack.__exit__(exc_type, exc, traceback)

    def _require_active_account(self) -> ValidatedPersonalDesktopPaperAccount:
        if self._exit_stack is None or self._post_lock_account is None:
            raise SupervisedPersonalDesktopPaperCycleError(
                "supervised paper cycle scope is not active"
            )
        return self._post_lock_account

    @property
    def account(self) -> ValidatedPersonalDesktopPaperAccount:
        """Return the genuine post-lock account authority while ownership is held."""

        return self._require_active_account()

    @property
    def evidence(self) -> PersonalDesktopPaperAccountReadEvidence:
        """Return only the post-lock account/read evidence while ownership is held."""

        return require_validated_personal_desktop_paper_account(
            self._require_active_account()
        )

    @property
    def acquisition(self) -> PaperAccountMutexAcquisition:
        """Return immutable PD2A ownership evidence, including abandonment state."""

        self._require_active_account()
        assert self._acquisition is not None
        return self._acquisition

    @property
    def operation_root(self) -> str:
        """Return the fixed operation root derived by the post-lock authority."""

        self._require_active_account()
        assert self._operation_root is not None
        return self._operation_root

    @property
    def requires_abandoned_owner_reconciliation(self) -> bool:
        """Report whether recovery/reconciliation is required before later work."""

        return self.acquisition.was_abandoned


def supervised_personal_desktop_paper_cycle(
    authority: ValidatedProductionAuthority,
    *,
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
) -> SupervisedPersonalDesktopPaperCycle:
    """Create a source-owned pre-lock -> mutex -> post-lock supervised scope."""

    production_authority = require_validated_production_authority(authority)
    return _supervised_personal_desktop_paper_cycle(
        production_authority,
        historical_cycle_configuration_payloads=historical_cycle_configuration_payloads,
        read_account=read_personal_desktop_paper_account,
        admit_account=supervised_paper_cycle_admission,
    )


def _supervised_personal_desktop_paper_cycle(
    authority: ValidatedProductionAuthority,
    *,
    historical_cycle_configuration_payloads: tuple[bytes, ...] = (),
    read_account: _ReadAccount,
    admit_account: _AdmitAccount,
) -> SupervisedPersonalDesktopPaperCycle:
    """Inject the already-bounded read/admission seams for isolated tests only."""

    return SupervisedPersonalDesktopPaperCycle(
        authority,
        historical_cycle_configuration_payloads,
        read_account=read_account,
        admit_account=admit_account,
        _key=_SCOPE_KEY,
    )
