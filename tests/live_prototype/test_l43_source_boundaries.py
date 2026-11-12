from __future__ import annotations

from threading import Event
from time import monotonic, sleep

import pytest

from trading_bot.live_prototype.application_service import (
    ApplicationIdentity,
    RealDisarmedApplicationService,
)
from trading_bot.live_prototype.contracts import (
    Command,
    EffectDisposition,
    Lifecycle,
    Reason,
)
from trading_bot.live_prototype.durable_state import RuntimeIdentity
from trading_bot.live_prototype.l43_pre_effect_observation import (
    L43PreEffectBlocker,
    L43PreEffectDependencies,
    L43PreEffectOutcome,
    observe_l43_pre_effect,
)
from trading_bot.live_prototype.l43_production_owner import (
    L43ProductionOwner,
    Q62JournalOrigin,
)


def _wait_for(condition, timeout: float = 2.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if condition():
            return True
        sleep(0.005)
    return condition()


class _EffectTrap:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def _trip(self, name: str, *_args: object, **_kwargs: object) -> None:
        self.calls.append(name)
        raise AssertionError(f"source-only path dispatched {name}")

    def read_final_holdout(self, *_args: object, **_kwargs: object) -> None:
        self._trip("FINAL_HOLDOUT")

    def review(self, *_args: object, **_kwargs: object) -> None:
        self._trip("review")

    def place(self, *_args: object, **_kwargs: object) -> None:
        self._trip("place")

    def cancel(self, *_args: object, **_kwargs: object) -> None:
        self._trip("cancel")

    def liquidate(self, *_args: object, **_kwargs: object) -> None:
        self._trip("liquidate")

    def protected_gui_control(self, *_args: object, **_kwargs: object) -> None:
        self._trip("protected GUI control")


class _AuthorityVerifier:
    def verify(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("continuity must not run after the source read fails")


class _JournalReader:
    def replay(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("journal replay must not run after the source read fails")


def _origin() -> Q62JournalOrigin:
    identity = RuntimeIdentity(
        account_fingerprint="a" * 64,
        source_head="1" * 40,
        source_tree="2" * 40,
        config_digest="3" * 64,
        binding_digest="4" * 64,
        lifecycle_id="00000000-0000-0000-0000-000000000147",
    )
    return Q62JournalOrigin(
        runtime_identity=identity,
        journal_label="fake-q62-origin",
        journal_sha256="5" * 64,
        initialization_event_sha256="6" * 64,
        consumed_observation_sha256="7" * 64,
    )


def _l43_dependencies(trap: _EffectTrap) -> L43PreEffectDependencies:
    def fail_source() -> object:
        raise OSError("synthetic source unavailable")

    def unexpected_callback(name: str):
        def fail(*_args: object, **_kwargs: object) -> object:
            trap._trip(name)

        return fail

    return L43PreEffectDependencies(
        source_reader=fail_source,
        continuity_owner=L43ProductionOwner(
            authority_verifier=_AuthorityVerifier(),
            journal_reader=_JournalReader(),
        ),
        origin=_origin(),
        state_snapshot_reader=unexpected_callback("state snapshot"),
        robinhood_builder=unexpected_callback("Robinhood read builder"),
        signal_provider_builder=unexpected_callback("signal provider builder"),
        clock=unexpected_callback("clock"),
    )


def test_l43_pre_effect_fails_closed_without_holdout_or_protected_dispatch():
    trap = _EffectTrap()
    dependencies = _l43_dependencies(trap)

    forbidden_capabilities = {
        "final_holdout_reader": trap.read_final_holdout,
        "reviewer": trap.review,
        "placer": trap.place,
        "canceller": trap.cancel,
        "liquidator": trap.liquidate,
        "protected_gui_dispatcher": trap.protected_gui_control,
    }
    for forbidden_capability, callback in forbidden_capabilities.items():
        with pytest.raises(TypeError):
            L43PreEffectDependencies(
                **{
                    "source_reader": dependencies.source_reader,
                    "continuity_owner": dependencies.continuity_owner,
                    "origin": dependencies.origin,
                    "state_snapshot_reader": dependencies.state_snapshot_reader,
                    "robinhood_builder": dependencies.robinhood_builder,
                    "signal_provider_builder": dependencies.signal_provider_builder,
                    "clock": dependencies.clock,
                    forbidden_capability: callback,
                }
            )

    result = observe_l43_pre_effect(dependencies)

    assert result.outcome is L43PreEffectOutcome.BLOCKED
    assert result.blockers == (L43PreEffectBlocker.SOURCE_UNAVAILABLE,)
    assert result.robinhood_read_count == 0
    assert result.alpaca_provider_call_count == 0
    assert result.credential_read_count == 0
    assert result.review_count == 0
    assert result.placement_count == 0
    assert result.cancellation_count == 0
    assert result.provider_mutation_count == 0
    assert not result.placement_authority_granted
    assert not result.trade_authority_granted
    assert not result.live_ready
    assert trap.calls == []


def test_real_disarmed_start_stop_and_protected_commands_keep_effect_trap_idle():
    trap = _EffectTrap()
    identity = ApplicationIdentity(
        source_head="1" * 40,
        source_tree="2" * 40,
        configuration_digest="3" * 64,
        evidence_digest="4" * 64,
    )
    research_started = Event()
    runtime_started = Event()
    observations = []
    dependencies = _l43_dependencies(trap)

    def research_worker(stop: Event, _publish: object) -> None:
        research_started.set()
        stop.wait()

    def runtime_worker(stop: Event, _publish: object) -> None:
        observations.append(observe_l43_pre_effect(dependencies))
        runtime_started.set()
        stop.wait()

    service = RealDisarmedApplicationService(
        identity,
        research_worker=research_worker,
        runtime_worker=runtime_worker,
        report_reader=trap.read_final_holdout,
    )
    try:
        started = service.submit(Command.START)
        assert started.accepted
        assert research_started.wait(timeout=2)
        assert runtime_started.wait(timeout=2)
        assert service.snapshot().lifecycle is Lifecycle.RUNNING
        assert not service.snapshot().ready_to_trade
        assert len(observations) == 1
        assert observations[0].outcome is L43PreEffectOutcome.BLOCKED
        assert observations[0].blockers == (L43PreEffectBlocker.SOURCE_UNAVAILABLE,)
        assert observations[0].review_count == 0
        assert observations[0].placement_count == 0
        assert observations[0].cancellation_count == 0
        assert observations[0].provider_mutation_count == 0

        for command in (Command.KILL, Command.EXIT):
            before = service.snapshot()
            rejected = service.submit(command)
            assert not rejected.accepted
            assert rejected.reason is Reason.EXTERNAL_OPERATOR_REQUIRED
            assert rejected.disposition is EffectDisposition.NO_EFFECT
            assert service.snapshot() == before

        stopped = service.submit(Command.STOP)
        assert stopped.accepted
        assert _wait_for(service.shutdown_complete)
        final = service.snapshot()
        assert final.lifecycle is Lifecycle.STOPPED
        assert not final.workers_running
        assert not final.ready_to_trade
        assert trap.calls == []
    finally:
        service.submit(Command.STOP)
        assert _wait_for(service.shutdown_complete)
