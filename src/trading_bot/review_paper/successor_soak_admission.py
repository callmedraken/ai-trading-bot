"""Inert manual-start composition; only injected read-only observation seams.

No production factory/launcher is supplied. A later reviewed installed-release
boundary must supply accepted source policy and real read-only observations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from trading_bot.review_paper.successor_soak_contract import (
    PRODUCTION_ROOT,
    STORE_IDENTITY,
    SuccessorLineage,
)
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import VerifiedRelease, verify_release_bundle
from trading_bot.supervised_release.installation_contract import (
    InstalledEvidence,
    ObserverNative,
)
from trading_bot.supervised_release.runtime_admission import (
    RuntimeObserver,
    RuntimeStatus,
    admit_runtime_host,
)
from trading_bot.supervised_release.runtime_host_composition import (
    Architecture133HostBinding,
    assess_host_qualification_readiness,
    bind_architecture133_host,
)
from trading_bot.supervised_release.runtime_isolation import (
    RuntimeAdmissionStatus,
    admit_installed_runtime,
)


@dataclass(frozen=True, slots=True)
class StoreObservation:
    path: str
    final_path: str
    parent: str
    local_ntfs: bool
    no_reparse: bool
    no_aliases: bool
    stable: bool
    identity: tuple[int, int]

    def validate(self) -> None:
        if (
            self.path != PRODUCTION_ROOT
            or self.final_path != PRODUCTION_ROOT
            or self.parent != r"F:\AITradingBot\Arch133"
            or any(
                value is not True
                for value in (
                    self.local_ntfs,
                    self.no_reparse,
                    self.no_aliases,
                    self.stable,
                )
            )
            or type(self.identity) is not tuple
            or len(self.identity) != 2
            or any(type(value) is not int or value <= 0 for value in self.identity)
        ):
            raise ValueError("exact independently observed successor store required")


@dataclass(frozen=True, slots=True)
class ManualProcessObservation:
    pid: int
    birth: str
    observed_date: str

    def __post_init__(self) -> None:
        if type(self.pid) is not int or self.pid <= 0:
            raise ValueError("observed process identity required")
        if (
            type(self.birth) is not str
            or re.fullmatch(r"windows-filetime:[1-9][0-9]{0,19}", self.birth) is None
        ):
            raise ValueError("closed process birth identity required")
        if (
            type(self.observed_date) is not str
            or date.fromisoformat(self.observed_date).isoformat() != self.observed_date
        ):
            raise ValueError("canonical observed session date required")

    def facts(self) -> dict:
        return {
            "pid": self.pid,
            "birth": self.birth,
            "observed_date": self.observed_date,
        }


class SuccessorObserver(Protocol):
    def observe_store(self) -> StoreObservation: ...

    def observe_manual_process(self) -> ManualProcessObservation: ...


@dataclass(frozen=True, slots=True)
class ManualAdmission:
    host: Architecture133HostBinding
    lineage: SuccessorLineage
    store: StoreObservation
    process: ManualProcessObservation


@dataclass(frozen=True, slots=True)
class ManualStartBoundary:
    """Source composition inputs, fixed before a manual invocation.

    The verified release carries independently reviewed expected HEAD/tree,
    manifest and complete inventory. None are inferred from observed host data.
    These constructor seams are for source tests, not runtime CLI configuration.
    """

    release: VerifiedRelease
    binding: RuntimeBinding
    installed: InstalledEvidence
    image_observer: ObserverNative
    runtime_observer: RuntimeObserver
    successor_observer: SuccessorObserver

    def admit(self) -> ManualAdmission:
        if (
            type(self.release) is not VerifiedRelease
            or type(self.binding) is not RuntimeBinding
        ):
            raise ValueError("exact independently accepted release/binding required")
        replay = verify_release_bundle(
            self.release.bundle,
            expected_manifest_sha256=self.release.expected_manifest_sha256,
            expected_source_head=self.release.expected_source_head,
            expected_source_tree=self.release.expected_source_tree,
            expected_source_paths=self.release.expected_source_paths,
        )
        if replay != self.release:
            raise ValueError("accepted source replay failed")
        RuntimeBinding.from_json(self.binding.to_json(), verified_release=replay)
        admission = admit_runtime_host(
            replay,
            self.binding,
            self.installed,
            image_observer=self.image_observer,
            runtime_observer=self.runtime_observer,
        )
        if admission.status is not RuntimeStatus.VERIFIED:
            raise ValueError("fresh Architecture-133 runtime-host admission required")
        host = bind_architecture133_host(
            replay,
            self.binding,
            self.installed,
            admission,
            durable_store_identities=(STORE_IDENTITY,),
        )
        admitted = admit_installed_runtime(
            host.material,
            expected_runtime_id=host.runtime_id,
            expected_state_identities=(STORE_IDENTITY,),
        )
        if admitted.status is not RuntimeAdmissionStatus.ADMITTED:
            raise ValueError("fresh F1R1-A admission required")
        assess_host_qualification_readiness(host)
        store = self.successor_observer.observe_store()
        if type(store) is not StoreObservation:
            raise ValueError("exact successor store observation required")
        store.validate()
        process = self.successor_observer.observe_manual_process()
        if type(process) is not ManualProcessObservation:
            raise ValueError("exact manual process observation required")
        # A second observation prevents a drifting store/process from being cached.
        if (
            self.successor_observer.observe_store() != store
            or self.successor_observer.observe_manual_process() != process
        ):
            raise ValueError("successor observation drift")
        return ManualAdmission(host, SuccessorLineage(host.material), store, process)
