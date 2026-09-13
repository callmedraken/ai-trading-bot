"""Process-local Architecture-111 proof of one selected C3 daily-bar open."""

from __future__ import annotations

from decimal import Decimal

from trading_bot.domain import Symbol
from trading_bot.market_calendar import TradingSession
from trading_bot.market_data import replay_verified_daily_snapshot
from trading_bot.runtime.manual_paper_selected_c3_snapshot import (
    SelectedC3SnapshotReadResult,
    require_disposable_selected_c3_snapshot_matches_identity_for_test,
    require_selected_c3_snapshot_matches_authority,
)
from trading_bot.runtime.windows_authority import WindowsAuthorityError
from trading_bot.runtime.windows_authority_validation import (
    ValidatedProductionAuthority,
    require_validated_production_authority,
)


class C3VerifiedDailyBarOpenBindingError(ValueError):
    """Raised when selected-C3 open provenance does not reconcile."""


_BINDING_ISSUER = object()
_PRODUCTION_PROVENANCE = object()
_DISPOSABLE_TEST_PROVENANCE = object()


class C3VerifiedDailyBarOpenBinding:
    """Immutable process-local proof of the exact open in one selected C3 bar."""

    __slots__ = (
        "_authority",
        "_authority_identity",
        "_open_price",
        "_provenance",
        "_selected_snapshot",
        "_session",
        "_symbol",
    )

    def __init__(
        self,
        *,
        _issuer: object | None = None,
        selected_snapshot: SelectedC3SnapshotReadResult | None = None,
        authority: ValidatedProductionAuthority | None = None,
        authority_identity: tuple[str, str, str] | None = None,
        provenance: object | None = None,
        symbol: Symbol | None = None,
        session: TradingSession | None = None,
        open_price: Decimal | None = None,
    ) -> None:
        if (
            _issuer is not _BINDING_ISSUER
            or type(selected_snapshot) is not SelectedC3SnapshotReadResult
            or (
                provenance is not _PRODUCTION_PROVENANCE
                and provenance is not _DISPOSABLE_TEST_PROVENANCE
            )
            or type(symbol) is not Symbol
            or type(session) is not TradingSession
            or type(open_price) is not Decimal
        ):
            raise TypeError(
                "C3 verified daily-bar open bindings require a reviewed constructor"
            )
        if provenance is _PRODUCTION_PROVENANCE:
            if authority_identity is not None:
                raise TypeError("production C3 open binding identity is invalid")
        elif authority is not None or (
            type(authority_identity) is not tuple or len(authority_identity) != 3
        ):
            raise TypeError("disposable C3 open binding identity is invalid")
        object.__setattr__(self, "_selected_snapshot", selected_snapshot)
        object.__setattr__(self, "_authority", authority)
        object.__setattr__(self, "_authority_identity", authority_identity)
        object.__setattr__(self, "_provenance", provenance)
        object.__setattr__(self, "_symbol", symbol)
        object.__setattr__(self, "_session", session)
        object.__setattr__(self, "_open_price", open_price)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("C3 verified daily-bar open bindings are immutable")

    def __copy__(self) -> object:
        raise TypeError("C3 verified daily-bar open bindings cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError("C3 verified daily-bar open bindings cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("C3 verified daily-bar open bindings cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("C3 verified daily-bar open bindings cannot be pickled")

    def __getstate__(self) -> object:
        raise TypeError("C3 verified daily-bar open bindings cannot be serialized")

    @property
    def symbol(self) -> Symbol:
        """Return the exact selected snapshot symbol."""
        return self._symbol

    @property
    def session(self) -> TradingSession:
        """Return the exact selected snapshot session."""
        return self._session

    @property
    def open_price(self) -> Decimal:
        """Return the exact selected daily-bar open."""
        return self._open_price


def build_c3_verified_daily_bar_open_binding(
    selected_snapshot: SelectedC3SnapshotReadResult,
    authority: ValidatedProductionAuthority,
) -> C3VerifiedDailyBarOpenBinding:
    """Bind one exact production P2 result to its current C1 authority and open."""
    if type(selected_snapshot) is not SelectedC3SnapshotReadResult:
        raise C3VerifiedDailyBarOpenBindingError(
            "selected_snapshot must be an exact SelectedC3SnapshotReadResult"
        )
    try:
        authority = require_validated_production_authority(authority)
        require_selected_c3_snapshot_matches_authority(
            selected_snapshot.permit, selected_snapshot.audit, authority
        )
        symbol, session, open_price = _exact_selected_open(selected_snapshot)
    except (WindowsAuthorityError, TypeError, ValueError) as error:
        raise C3VerifiedDailyBarOpenBindingError(
            "selected C3 snapshot cannot be bound to the current C1 authority"
        ) from error
    return C3VerifiedDailyBarOpenBinding(
        _issuer=_BINDING_ISSUER,
        selected_snapshot=selected_snapshot,
        authority=authority,
        provenance=_PRODUCTION_PROVENANCE,
        symbol=symbol,
        session=session,
        open_price=open_price,
    )


def build_disposable_c3_verified_daily_bar_open_binding_for_test(
    selected_snapshot: SelectedC3SnapshotReadResult,
    *,
    machine_authority_id: str,
    approved_trading_sid: str,
    authority_epoch_id: str,
) -> C3VerifiedDailyBarOpenBinding:
    """Bind explicit disposable P2 evidence without minting production provenance."""
    if type(selected_snapshot) is not SelectedC3SnapshotReadResult:
        raise C3VerifiedDailyBarOpenBindingError(
            "selected_snapshot must be an exact SelectedC3SnapshotReadResult"
        )
    try:
        require_disposable_selected_c3_snapshot_matches_identity_for_test(
            selected_snapshot.permit,
            selected_snapshot.audit,
            machine_authority_id=machine_authority_id,
            approved_trading_sid=approved_trading_sid,
            authority_epoch_id=authority_epoch_id,
        )
        symbol, session, open_price = _exact_selected_open(selected_snapshot)
    except (WindowsAuthorityError, TypeError, ValueError) as error:
        raise C3VerifiedDailyBarOpenBindingError(
            "disposable selected C3 snapshot identity is invalid"
        ) from error
    return C3VerifiedDailyBarOpenBinding(
        _issuer=_BINDING_ISSUER,
        selected_snapshot=selected_snapshot,
        authority_identity=(
            machine_authority_id,
            approved_trading_sid,
            authority_epoch_id,
        ),
        provenance=_DISPOSABLE_TEST_PROVENANCE,
        symbol=symbol,
        session=session,
        open_price=open_price,
    )


def require_c3_verified_daily_bar_open_binding(
    binding: C3VerifiedDailyBarOpenBinding,
) -> C3VerifiedDailyBarOpenBinding:
    """Revalidate exact production P2/C1 provenance and selected-bar material."""
    if type(binding) is not C3VerifiedDailyBarOpenBinding:
        raise C3VerifiedDailyBarOpenBindingError(
            "verified_open_binding must be an exact C3 binding"
        )
    if binding._provenance is not _PRODUCTION_PROVENANCE:
        raise C3VerifiedDailyBarOpenBindingError(
            "production completion requires production C3 open provenance"
        )
    try:
        authority = require_validated_production_authority(binding._authority)
        require_selected_c3_snapshot_matches_authority(
            binding._selected_snapshot.permit,
            binding._selected_snapshot.audit,
            authority,
        )
        exact = _exact_selected_open(binding._selected_snapshot)
    except (WindowsAuthorityError, TypeError, ValueError) as error:
        raise C3VerifiedDailyBarOpenBindingError(
            "verified C3 daily-bar open provenance is no longer valid"
        ) from error
    if exact != (binding.symbol, binding.session, binding.open_price):
        raise C3VerifiedDailyBarOpenBindingError(
            "verified C3 daily-bar open does not match retained selected evidence"
        )
    return binding


def require_disposable_c3_verified_daily_bar_open_binding_for_test(
    binding: C3VerifiedDailyBarOpenBinding,
) -> C3VerifiedDailyBarOpenBinding:
    """Revalidate an explicitly disposable binding for focused offline tests."""
    if (
        type(binding) is not C3VerifiedDailyBarOpenBinding
        or binding._provenance is not _DISPOSABLE_TEST_PROVENANCE
        or binding._authority_identity is None
    ):
        raise C3VerifiedDailyBarOpenBindingError(
            "disposable verified-open binding provenance is invalid"
        )
    machine, sid, epoch = binding._authority_identity
    try:
        require_disposable_selected_c3_snapshot_matches_identity_for_test(
            binding._selected_snapshot.permit,
            binding._selected_snapshot.audit,
            machine_authority_id=machine,
            approved_trading_sid=sid,
            authority_epoch_id=epoch,
        )
        exact = _exact_selected_open(binding._selected_snapshot)
    except (WindowsAuthorityError, TypeError, ValueError) as error:
        raise C3VerifiedDailyBarOpenBindingError(
            "disposable verified-open binding provenance is no longer valid"
        ) from error
    if exact != (binding.symbol, binding.session, binding.open_price):
        raise C3VerifiedDailyBarOpenBindingError(
            "disposable verified-open binding does not match selected evidence"
        )
    return binding


def _exact_selected_open(
    selected_snapshot: SelectedC3SnapshotReadResult,
) -> tuple[Symbol, TradingSession, Decimal]:
    if (
        not selected_snapshot.verification.passed
        or selected_snapshot.verification.snapshot is None
        or selected_snapshot.verification.diagnostics
    ):
        raise C3VerifiedDailyBarOpenBindingError(
            "selected snapshot verification must be exact PASS"
        )
    replay = replay_verified_daily_snapshot(selected_snapshot.verification)
    if len(replay.symbols) != 1 or len(replay.bars) != 1:
        raise C3VerifiedDailyBarOpenBindingError(
            "selected snapshot must contain exactly one usable daily bar"
        )
    symbol = replay.symbols[0]
    selected_bar = replay.bars[0]
    open_price = selected_bar.bar.open
    if (
        selected_bar.bar.symbol != symbol
        or selected_bar.session != replay.target_session
        or type(open_price) is not Decimal
        or not open_price.is_finite()
        or open_price <= 0
    ):
        raise C3VerifiedDailyBarOpenBindingError(
            "selected snapshot daily-bar open is invalid"
        )
    return symbol, replay.target_session, open_price
