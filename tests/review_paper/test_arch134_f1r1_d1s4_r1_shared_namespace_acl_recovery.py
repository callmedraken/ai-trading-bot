"""R1 source/fake-host tests. No production preflight or ACL write is performed."""

import ast
import ctypes
import hashlib
import inspect
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.runtime.checkpoint_runner.test_ci import (
    _use_historical_predecessor_authority,
)

from scripts import checkpoint_runner as runner
from trading_bot import shared_namespace_acl_native as native
from trading_bot import shared_namespace_acl_recovery as r
from trading_bot.arch133_acl.read_only import ADMIN_ACES, ADMINISTRATORS_SID
from trading_bot.supervised_release.installation_contract import IMAGE_ACES

ObjectFacts = r.ObjectFacts

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ("a" * 40, "b" * 40)
NATIVE_PINNED = native._PinnedTargets


def snapshot():
    result = []
    for index, path in enumerate(r.OBSERVED_PATHS):
        aces = ADMIN_ACES
        if index in (1, 2):
            aces = r.PRE_ACES[index - 1]
        elif index in (5, 6):
            aces = IMAGE_ACES + (r.DRIFT_ACE,)
        identity = (
            r.TARGET_IDENTITIES[index - 1]
            if index in (1, 2)
            else (1855336320, index + 1)
        )
        fact = ObjectFacts(
            path,
            "file" if index == 4 else "directory",
            identity,
            ADMINISTRATORS_SID,
            True,
            aces,
        )
        result.append(
            r.SecurityEvidence(
                fact,
                r.PRE_HASHES[index - 1]
                if index in (1, 2)
                else hashlib.sha256(path.encode()).hexdigest(),
            )
        )
    return tuple(result)


class Host:
    def __init__(self):
        self.rows = snapshot()
        self.events = []
        self.codes = [0, 0]
        self.after_call = lambda index: None
        self.close_error = False
        self.observation_error = False

    def observe(self):
        self.events.append("independent_observation")
        if self.observation_error:
            raise OSError("SECRET arbitrary user path")
        return self.rows

    def recover(self, index):
        row = self.rows[index + 1]
        updated = r.SecurityEvidence(
            replace(row.facts, aces=r.POST_ACES[index]), str(index + 1) * 64
        )
        self.rows = (*self.rows[: index + 1], updated, *self.rows[index + 2 :])

    def pinned(self):
        host = self

        class Pinned:
            last_status = None
            index = 0

            def __enter__(self):
                host.events.append("pin_two_targets")
                return self

            def snapshot(self):
                host.events.append("held_observation")
                return host.rows

            def apply_next(self):
                index = self.index
                self.index += 1
                plan = r.recovery_plan(SOURCE, host.rows)
                assert r.observe_attempt(plan) == "CONSUMED"
                assert json.loads(r.ATTEMPT_PATH.read_bytes())["status"] == "CONSUMED"
                host.events.append(("SetSecurityInfo", r.TARGET_PATHS[index]))
                code = host.codes[index]
                if isinstance(code, BaseException):
                    raise code
                host.recover(index)
                host.after_call(index)
                self.last_status = code
                return code

            def __exit__(self, *_exc):
                host.events.append("all_handles_closed")
                if host.close_error:
                    raise OSError("SECRET close")

        return Pinned()


@pytest.fixture
def host(monkeypatch, tmp_path):
    state = Host()
    monkeypatch.setattr(r, "ATTEMPT_PATH", tmp_path / "attempt.json")
    monkeypatch.setattr(r, "_spent", False)
    monkeypatch.setattr(r, "admit_source", lambda: SOURCE)
    monkeypatch.setattr(
        r, "require_administrator", lambda: state.events.append("admin")
    )
    monkeypatch.setattr(r, "observe_fixed_scope", state.observe)
    monkeypatch.setattr(native, "_PinnedTargets", state.pinned)
    monkeypatch.delenv(r.AUTH_ENV, raising=False)
    monkeypatch.delenv(r.PLAN_ENV, raising=False)
    return state


def authorize(monkeypatch):
    report = r.preflight()
    assert report["primary"]["execute_eligible"] is True
    monkeypatch.setenv(r.AUTH_ENV, r.AUTH_VALUE)
    monkeypatch.setenv(r.PLAN_ENV, report["primary"]["plan_sha256"])
    return report


def primary(result):
    return result["primary"]


def test_exact_frozen_incident_and_plan_are_deterministic(host):
    first, second = r.preflight(), r.preflight()
    assert first == second
    row = primary(first)
    assert row["reason"] == "READY_FOR_SHARED_NAMESPACE_ACL_RECOVERY"
    assert row["plan_sha256"] == hashlib.sha256(r.canonical(row["plan"])).hexdigest()
    assert row["plan"]["targets"][0]["target_aces"] == ADMIN_ACES
    assert row["plan"]["targets"][1]["target_aces"] == IMAGE_ACES
    assert row["plan"]["preserved_incident_paths"] == r.PRESERVED_PATHS
    assert not r.ATTEMPT_PATH.exists()
    assert not any(isinstance(event, tuple) for event in host.events)
    assert r.TARGET_PATHS == (r"F:\AITradingBot", r"F:\AITradingBot\releases")
    assert r.MUTATION_ORDER == r.TARGET_PATHS
    assert len(r.OBSERVED_PATHS) == 8


def test_success_latch_fsync_close_before_exact_calls_and_twice_reopen(
    host, monkeypatch
):
    reviewed = authorize(monkeypatch)
    original_fsync = r.os.fsync

    def fsync(fd):
        host.events.append("latch_fsync")
        original_fsync(fd)

    monkeypatch.setattr(r.os, "fsync", fsync)
    before = host.rows
    result = r.execute_once()
    row = primary(result)
    assert (result["status"], row["reason"], result["effect_disposition"]) == (
        "PASS",
        "SHARED_NAMESPACE_ACL_RECOVERY_VERIFIED",
        "CONFIRMED",
    )
    calls = [
        (i, event) for i, event in enumerate(host.events) if isinstance(event, tuple)
    ]
    assert [event[1] for _, event in calls] == list(r.MUTATION_ORDER)
    assert (
        host.events.index("pin_two_targets")
        < host.events.index("latch_fsync")
        < calls[0][0]
    )
    assert host.events[host.events.index("all_handles_closed") + 1 :] == [
        "independent_observation",
        "independent_observation",
    ]
    assert host.rows[0] == before[0] and host.rows[3:] == before[3:]
    assert row["native_results"] == [
        {"path": path, "raw_dword": 0} for path in r.TARGET_PATHS
    ]
    assert row["repeated_observation_stable"] is True
    payload = json.loads(r.ATTEMPT_PATH.read_bytes())
    assert payload["plan_sha256"] == primary(reviewed)["plan_sha256"]
    assert (
        payload["status"] == "CONSUMED"
        and payload["automatic_retry"] == "NOT_AUTHORIZED"
    )
    assert payload["target_identities"] == [
        list(value) for value in r.TARGET_IDENTITIES
    ]
    assert payload["pre_descriptor_sha256"] == list(r.PRE_HASHES)
    assert primary(r.preflight())["reason"] == "SHARED_NAMESPACE_ACL_RECOVERY_VERIFIED"
    assert primary(r.preflight())["execute_eligible"] is False
    assert r.execute_once()["status"] == "BLOCKED"
    assert len([e for e in host.events if isinstance(e, tuple)]) == 2


@pytest.mark.parametrize("target", [1, 2])
@pytest.mark.parametrize(
    "change",
    [
        "sid",
        "mask",
        "flags",
        "order",
        "hash",
        "identity",
        "missing",
        "extra",
        "owner",
        "protected",
        "reparse",
        "filesystem",
        "local",
        "persistent",
        "links",
        "path",
    ],
)
def test_only_exact_reviewed_pre_policy_is_admitted(host, target, change):
    rows = list(host.rows)
    row = rows[target]
    fact = row.facts
    aces = list(fact.aces)
    if change == "sid":
        aces[-1] = ("S-1-5-21-9-8-7-1005", *aces[-1][1:])
    elif change == "mask":
        aces[-1] = (r.DRIFT_SID, 0x1200A9, 0, 3)
    elif change == "flags":
        aces[-1] = (r.DRIFT_SID, 0x1F01FF, 0, 0)
    elif change == "order":
        aces.reverse()
    elif change == "missing":
        aces.pop(0)
    elif change == "extra":
        aces.append(r.DRIFT_ACE)
    elif change == "hash":
        row = replace(row, descriptor_sha256="f" * 64)
    else:
        values = {
            "identity": (1855336320, 12345),
            "owner": r.DRIFT_SID,
            "protected": False,
            "reparse": True,
            "filesystem": "FAT32",
            "local": False,
            "persistent": False,
            "links": 2,
            "path": r"F:\AITradingBot\different",
        }
        fact = replace(
            fact,
            **{"persistent_acls" if change == "persistent" else change: values[change]},
        )
    rows[target] = replace(row, facts=replace(fact, aces=tuple(aces)))
    host.rows = tuple(rows)
    result = r.preflight()
    assert result["status"] != "PASS"
    assert primary(result)["reason"] == "PRE_RECOVERY_BASELINE_DRIFT"
    assert primary(result)["execute_eligible"] is False
    assert not r.ATTEMPT_PATH.exists()


@pytest.mark.parametrize("index", [3, 4, 7])
def test_frozen_no_john_drift_scope(host, index):
    rows = list(host.rows)
    rows[index] = replace(
        rows[index],
        facts=replace(rows[index].facts, aces=rows[index].facts.aces + (r.DRIFT_ACE,)),
    )
    host.rows = tuple(rows)
    assert r.preflight()["status"] == "BLOCKED"


@pytest.mark.parametrize("index", [5, 6, 7])
@pytest.mark.parametrize("change", ["missing", "unprotected", "john_presence"])
def test_preserved_incident_objects_are_required_and_never_targets(host, index, change):
    rows = list(host.rows)
    if change == "missing":
        rows.pop(index)
    elif change == "unprotected":
        rows[index] = replace(
            rows[index], facts=replace(rows[index].facts, protected=False)
        )
    else:
        aces = ADMIN_ACES if index in (5, 6) else IMAGE_ACES + (r.DRIFT_ACE,)
        rows[index] = replace(rows[index], facts=replace(rows[index].facts, aces=aces))
    host.rows = tuple(rows)
    assert r.preflight()["status"] == "BLOCKED"
    assert set(r.PRESERVED_PATHS).isdisjoint(r.TARGET_PATHS)


@pytest.mark.parametrize("auth", [None, "", "wrong"])
def test_wrong_authorization_never_pins_or_consumes(host, monkeypatch, auth):
    authorize(monkeypatch)
    if auth is None:
        monkeypatch.delenv(r.AUTH_ENV)
    else:
        monkeypatch.setenv(r.AUTH_ENV, auth)
    assert primary(r.execute_once())["reason"] == "AUTHORIZATION_REJECTED"
    assert "pin_two_targets" not in host.events
    assert not r.ATTEMPT_PATH.exists()


@pytest.mark.parametrize(
    "digest", ["", "x" * 64, "A" * 64, "0" * 63, "0" * 65, "0" * 64]
)
def test_malformed_or_different_reviewed_plan_rejects(host, monkeypatch, digest):
    authorize(monkeypatch)
    monkeypatch.setenv(r.PLAN_ENV, digest)
    assert r.execute_once()["status"] == "BLOCKED"
    assert not r.ATTEMPT_PATH.exists()


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "outcome", [False, 5, OSError("SECRET native"), KeyboardInterrupt(), SystemExit()]
)
def test_native_failures_are_terminal_and_always_read_back(
    host, monkeypatch, index, outcome
):
    authorize(monkeypatch)
    host.codes[index] = outcome
    result = r.execute_once()
    assert result["status"] == "INDETERMINATE"
    assert primary(result)["reason"] == r.PRESERVE
    assert result["effect_disposition"] == "MAY_HAVE_OCCURRED"
    assert len(primary(result)["native_results"]) == index + 1
    assert len(primary(result)["readbacks"]) >= index + 3
    assert host.events[-2:] == ["independent_observation"] * 2
    assert "SECRET" not in json.dumps(result)
    assert r.ATTEMPT_PATH.exists()
    count = len(host.events)
    assert r.execute_once()["status"] == "BLOCKED"
    assert not any(isinstance(e, tuple) for e in host.events[count:])


@pytest.mark.parametrize(
    "change",
    ["close", "source", "identity", "policy", "preserved", "descriptor", "observation"],
)
def test_post_fence_drift_never_confirms_or_retries(host, monkeypatch, change):
    authorize(monkeypatch)
    if change == "close":
        host.close_error = True
    else:

        def drift(index):
            if index != 1:
                return
            if change == "source":
                monkeypatch.setattr(r, "admit_source", lambda: ("c" * 40, "d" * 40))
            elif change == "observation":
                host.observation_error = True
            else:
                rows = list(host.rows)
                at = 5 if change == "preserved" else 1
                row = rows[at]
                if change in {"preserved", "descriptor"}:
                    rows[at] = replace(row, descriptor_sha256="e" * 64)
                else:
                    rows[at] = replace(
                        row,
                        facts=replace(
                            row.facts,
                            **(
                                {"identity": (1855336320, 999)}
                                if change == "identity"
                                else {"aces": ADMIN_ACES + (r.DRIFT_ACE,)}
                            ),
                        ),
                    )
                host.rows = tuple(rows)

        host.after_call = drift
    result = r.execute_once()
    # A stable exact target descriptor can differ from its pre-policy hash.
    expected = "PASS" if change == "descriptor" else "INDETERMINATE"
    assert result["status"] == expected
    assert primary(result)["execute_eligible"] is False


def test_consumed_original_partial_and_unprovable_reconciliation(host):
    plan = r.recovery_plan(SOURCE, host.rows)
    r.ATTEMPT_PATH.write_bytes(r._latch_payload(plan))
    assert primary(r.preflight())["reason"] == "CONSUMED_ATTEMPT_NO_CONFIRMED_RECOVERY"
    host.recover(0)
    assert primary(r.preflight())["reason"] == "PARTIAL_OR_CONFLICTING_ACL_RECOVERY"
    host.recover(1)
    assert primary(r.preflight())["reason"] == "SHARED_NAMESPACE_ACL_RECOVERY_VERIFIED"
    r.ATTEMPT_PATH.write_bytes(b"malformed")
    assert r.preflight()["status"] == "INDETERMINATE"
    assert primary(r.preflight())["execute_eligible"] is False


@pytest.mark.parametrize("failure", ["fsync", "readback", "existing", "pin_drift"])
def test_latch_or_pre_fence_ambiguity_never_mutates(host, monkeypatch, failure):
    authorize(monkeypatch)
    if failure == "fsync":
        monkeypatch.setattr(
            r.os, "fsync", lambda *_: (_ for _ in ()).throw(OSError("SECRET fsync"))
        )
    elif failure == "existing":
        r.ATTEMPT_PATH.write_bytes(b"ambiguous")
    elif failure == "pin_drift":
        original = native._PinnedTargets

        def changed():
            obj = original()
            obj.snapshot = lambda: ()
            return obj

        monkeypatch.setattr(native, "_PinnedTargets", changed)
    else:
        original = r._read_latch
        monkeypatch.setattr(
            r, "_read_latch", lambda: b"wrong" if r._spent else original()
        )
    result = r.execute_once()
    assert result["status"] != "PASS"
    assert not any(isinstance(e, tuple) for e in host.events)
    assert result["effect_disposition"] == "NOT_STARTED"


@pytest.mark.parametrize("failure", ["parents", "payload", "create"])
def test_failure_before_exclusive_create_is_not_a_reservation(
    host, monkeypatch, failure
):
    authorize(monkeypatch)
    opens = []
    original_open = Path.open
    original_ancestors = r._safe_ancestors
    ancestor_calls = 0

    def fail():
        assert r._spent is False
        assert not r.ATTEMPT_PATH.exists()
        raise OSError("SECRET pre-reservation")

    def ancestors(path):
        nonlocal ancestor_calls
        ancestor_calls += 1
        # Initial, pinned and consume observations precede explicit admission.
        if failure == "parents" and ancestor_calls == 4:
            fail()
        return original_ancestors(path)

    def opened(path, mode="r", *args, **kwargs):
        if path == r.ATTEMPT_PATH and mode == "xb":
            opens.append(mode)
            assert failure == "create"
            fail()
        return original_open(path, mode, *args, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(Path, "open", opened)
        fault.setattr(r, "_safe_ancestors", ancestors)
        if failure == "payload":
            fault.setattr(r, "_latch_payload", lambda _plan: fail())
        result = r.execute_once()
    assert (result["status"], result["effect_disposition"]) == (
        "BLOCKED",
        "NOT_STARTED",
    )
    assert primary(result)["reason"] == "RECOVERY_ADMISSION_REJECTED"
    assert primary(result)["latch_classification"] == "AVAILABLE"
    assert opens == (["xb"] if failure == "create" else [])
    assert r._spent is False
    assert not r.ATTEMPT_PATH.exists()
    assert not any(isinstance(event, tuple) for event in host.events)
    monkeypatch.setattr(r, "_spent", False)
    row = primary(r.preflight())
    assert row["latch_classification"] == "AVAILABLE"
    assert row["automatic_retry"] == "NOT_AUTHORIZED"


@pytest.mark.parametrize("observation", ["partial", "consumed", "unprovable"])
def test_failed_exclusive_create_never_assumes_absence(host, monkeypatch, observation):
    authorize(monkeypatch)
    original_open = Path.open
    original_read = r._read_latch
    create_failed = False

    def opened(path, mode="r", *args, **kwargs):
        nonlocal create_failed
        if path == r.ATTEMPT_PATH and mode == "xb":
            assert r._spent is False
            if observation != "unprovable":
                payload = (
                    r._latch_payload(r.recovery_plan(SOURCE, host.rows))
                    if observation == "consumed"
                    else b"partial competing reservation"
                )
                with original_open(path, "xb") as handle:
                    handle.write(payload)
            create_failed = True
            raise FileExistsError("SECRET competing or unprovable create")
        return original_open(path, mode, *args, **kwargs)

    def read():
        if create_failed and observation == "unprovable":
            raise OSError("SECRET inaccessible latch")
        return original_read()

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(r, "_read_latch", read)
    result = r.execute_once()
    assert result["status"] == "INDETERMINATE"
    assert result["effect_disposition"] == "NOT_STARTED"
    assert primary(result)["reason"] == "PARTIAL_OR_CONFLICTING_ACL_RECOVERY"
    assert r._spent is False  # This process acquired no reservation object.
    assert not any(isinstance(event, tuple) for event in host.events)
    monkeypatch.setattr(r, "_spent", False)
    for report in (r.preflight(), r.execute_once()):
        row = primary(report)
        assert row["latch_classification"] != "AVAILABLE"
        assert row["execute_eligible"] is False
        assert report["automatic_retry"] == row["automatic_retry"] == "NOT_AUTHORIZED"


@pytest.mark.parametrize(
    "failure",
    [
        "enter",
        "metadata",
        "short_write",
        "failed_write",
        "flush",
        "fsync",
        "close",
        "readback_failure",
        "readback_mismatch",
        "readback_drift",
        "identity_drift",
    ],
)
@pytest.mark.parametrize("error", [OSError, KeyboardInterrupt, SystemExit])
def test_acquired_latch_failures_remain_closed_after_restart(
    host, monkeypatch, failure, error
):
    authorize(monkeypatch)
    original_open = Path.open
    original_fstat = r.os.fstat
    original_fsync = r.os.fsync
    original_lstat = Path.lstat
    original_read = r._read_latch
    metadata_calls = named_calls = 0
    faults_seen = []

    def fail():
        # Every fallible seam after exclusive create must see spent authority.
        assert r._spent is True
        assert r.ATTEMPT_PATH.exists()
        faults_seen.append(failure)
        raise error("SECRET post-create ambiguity")

    class Writer:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            assert r._spent is True
            if failure == "enter":
                self.handle.close()
                fail()
            return self

        def fileno(self):
            assert r._spent is True
            return self.handle.fileno()

        def write(self, payload):
            assert r._spent is True
            if failure in {"short_write", "failed_write"}:
                count = self.handle.write(payload[:7])
                if failure == "failed_write":
                    fail()
                faults_seen.append(failure)
                return count
            return self.handle.write(payload)

        def flush(self):
            assert r._spent is True
            if failure == "flush":
                fail()
            self.handle.flush()

        def __exit__(self, *_exc):
            assert r._spent is True
            self.handle.close()
            if failure == "close":
                fail()

    def opened(path, mode="r", *args, **kwargs):
        handle = original_open(path, mode, *args, **kwargs)
        if path == r.ATTEMPT_PATH and mode == "xb":
            assert r._spent is False
            return Writer(handle)
        return handle

    def fstat(fd):
        nonlocal metadata_calls
        if r._spent:
            metadata_calls += 1
            if failure == "metadata" and metadata_calls == 1:
                fail()
        value = original_fstat(fd)
        if failure == "readback_drift" and metadata_calls == 2:
            faults_seen.append(failure)
            return SimpleNamespace(
                st_dev=value.st_dev,
                st_ino=value.st_ino + 1,
                st_size=value.st_size,
                st_mtime_ns=value.st_mtime_ns,
            )
        return value

    def fsync(fd):
        assert r._spent is True
        if failure == "fsync":
            fail()
        original_fsync(fd)

    def read():
        if r._spent:
            if failure == "readback_failure":
                fail()
            if failure == "readback_mismatch":
                faults_seen.append(failure)
                return b"mismatched readback"
        return original_read()

    def lstat(path, *args, **kwargs):
        nonlocal named_calls
        value = original_lstat(path, *args, **kwargs)
        if path == r.ATTEMPT_PATH and r._spent:
            named_calls += 1
            # Two exact readback observations, then created/named comparison.
            if failure == "identity_drift" and named_calls == 3:
                faults_seen.append(failure)
                return SimpleNamespace(st_dev=value.st_dev, st_ino=value.st_ino + 1)
        return value

    with monkeypatch.context() as fault:
        fault.setattr(Path, "open", opened)
        fault.setattr(r.os, "fstat", fstat)
        fault.setattr(r.os, "fsync", fsync)
        fault.setattr(r, "_read_latch", read)
        fault.setattr(Path, "lstat", lstat)
        result = r.execute_once()
    assert faults_seen == [failure]
    assert result["status"] == "INDETERMINATE"
    assert primary(result)["reason"] == r.PRESERVE
    assert result["effect_disposition"] == "NOT_STARTED"
    assert r._spent is True
    assert r.ATTEMPT_PATH.is_file()
    assert not any(isinstance(event, tuple) for event in host.events)
    assert primary(result)["native_results"] == []
    payload = r.ATTEMPT_PATH.read_bytes()
    exact = r._latch_payload(r.recovery_plan(SOURCE, host.rows))
    if failure in {"enter", "metadata", "short_write", "failed_write"}:
        assert payload != exact
    else:
        assert payload == exact
    monkeypatch.setattr(r, "_spent", False)
    # Faults are removed: only the named durable object closes the new process.
    for report in (r.preflight(), r.execute_once()):
        row = primary(report)
        assert row["latch_classification"] in {"CONSUMED", "INDETERMINATE"}
        assert row["execute_eligible"] is False
        assert report["automatic_retry"] == row["automatic_retry"] == "NOT_AUTHORIZED"
        assert report["effect_disposition"] == "NOT_STARTED"
        assert row["runtime_binding_eligible"] is False
        assert row["successor_soak_eligible"] is False
    assert r.ATTEMPT_PATH.read_bytes() == payload
    assert not any(isinstance(event, tuple) for event in host.events)


def test_no_target_or_path_override_and_no_incident_runtime_authority(host):
    for function in (
        r.preflight,
        r.execute_once,
        r.observe_fixed_scope,
        native._observe,
    ):
        assert not inspect.signature(function).parameters
        with pytest.raises(TypeError):
            function(target=r"F:\elsewhere")
    for path in (
        r"F:\elsewhere",
        r.TARGET_PATHS[0] + "\\..\\elsewhere",
        r.PRESERVED_PATHS[0] + "\\child",
    ):
        with pytest.raises(Exception, match="FIXED_PATH"):
            native._FixedPaths().admit(path)
    row = primary(r.preflight())
    assert row["runtime_binding_eligible"] is False
    assert row["successor_soak_eligible"] is False
    assert r.INCIDENT_RELEASE_IDS[0] == "release-18d5d329c1d458558e98d7effe523c3b"


def test_source_admin_and_repeat_admission_fail_closed(host, monkeypatch):
    original = r.admit_source
    monkeypatch.setattr(
        r, "admit_source", lambda: (_ for _ in ()).throw(ValueError("SECRET source"))
    )
    assert r.preflight()["status"] == "BLOCKED"
    monkeypatch.setattr(r, "admit_source", original)
    monkeypatch.setattr(
        r,
        "require_administrator",
        lambda: (_ for _ in ()).throw(ValueError("SECRET token")),
    )
    assert r.preflight()["status"] == "BLOCKED"
    monkeypatch.setattr(r, "require_administrator", lambda: None)
    count = 0

    def drift():
        nonlocal count
        count += 1
        return SOURCE if count == 1 else ("c" * 40, "d" * 40)

    monkeypatch.setattr(r, "admit_source", drift)
    assert r.preflight()["status"] == "BLOCKED"


def test_registered_route_graph_and_exact_authority(monkeypatch):
    _use_historical_predecessor_authority(monkeypatch, ROOT)
    spec = runner._checkpoint_specs()[r.CHECKPOINT]
    assert spec.preflight is runner._arch134_acl_preflight
    assert spec.execute is runner._arch134_acl_execute
    assert spec.remote_branch == r.BRANCH
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), r.BRANCH, "push")
        == spec.name
    )
    assert runner.CI_CERTIFICATION_PROFILES[r.CHECKPOINT] == "robinhood"
    assert runner._arch134_acl_graph_check(ROOT) == ()
    assert runner._arch134_acl_authority_check(ROOT) == ()


@pytest.mark.parametrize(
    "payload",
    [
        (
            "from trading_bot.arch133_acl.root_policy_apply "
            "import apply_root_policy_status"
        ),
        "from trading_bot.arch133_acl import recovery",
        "from trading_bot.supervised_release import successor_installation_operator",
        "from trading_bot.supervised_release import successor_publication_recovery",
        (
            "from trading_bot.supervised_release.successor_direct_installation "
            "import execute_once"
        ),
        "from trading_bot.arch133_rename import qualification",
        "from trading_bot.runtime import scheduler",
        "from scripts import d10_arch125_activation_operator",
        "from trading_bot.market_data import alpaca_http",
        "from trading_bot.robinhood import provider",
        "SetNamedSecurityInfo()",
        "SetFileSecurity()",
        "os.rename()",
        "os.mkdir()",
        "bind(library, 'UnknownMutation', [], None)",
        "bind(library, variable_name, [], None)",
    ],
)
def test_graph_and_native_mutation_allowlist_reject_injection(monkeypatch, payload):
    original = Path.read_text

    def read(path, *args, **kwargs):
        text = original(path, *args, **kwargs)
        if path.name == "shared_namespace_acl_native.py":
            return text + "\n" + payload + "\n"
        return text

    monkeypatch.setattr(Path, "read_text", read)
    assert runner._arch134_acl_graph_check(ROOT)


def test_native_target_open_is_existing_exclusive_no_follow(monkeypatch):
    session = object.__new__(native._Session)
    session.paths = native._FixedPaths()
    session._mutable = True
    session.handles = {r.VOLUME_PATH: 10}
    session.kernel = object()
    calls = []

    def fake_bind(_library, name, _args, _result):
        assert name == "CreateFileW"

        def call(*args):
            calls.append(args)
            return 20

        return call

    monkeypatch.setattr(native, "_bind", fake_bind)
    assert session.open_object(r.TARGET_PATHS[0], directory=True) == 20
    assert calls[0] == (r.TARGET_PATHS[0], 0x160089, 0, None, 3, 0x02200000, None)
    assert calls[0][1] & 0x80000 == 0  # No WRITE_OWNER.
    assert calls[0][1] & 0x10000 == 0  # No DELETE.


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("code", [0, 5])
def test_exact_handle_dacl_only_native_abi_and_raw_status(
    host, monkeypatch, index, code
):
    authorize(monkeypatch)
    plan = r.recovery_plan(SOURCE, host.rows)
    r._consume_attempt(plan)
    if index:
        host.recover(0)
    pinned = object.__new__(NATIVE_PINNED)
    pinned._session = SimpleNamespace(
        advapi=object(),
        kernel=object(),
        handles=dict(zip(r.TARGET_PATHS, (100, 200), strict=True)),
    )
    pinned._source, pinned._plan, pinned._next = SOURCE, plan, index
    pinned.snapshot = lambda: host.rows
    calls = []

    def fake_bind(_library, name, _args, _result):
        def call(*args):
            calls.append((name, args))
            if name == "ConvertStringSecurityDescriptorToSecurityDescriptorW":
                ctypes.cast(args[2], ctypes.POINTER(ctypes.c_void_p))[0] = 300
                return 1
            if name == "GetSecurityDescriptorDacl":
                ctypes.cast(args[1], ctypes.POINTER(ctypes.c_int32))[0] = 1
                ctypes.cast(args[2], ctypes.POINTER(ctypes.c_void_p))[0] = 400
                return 1
            if name == "SetSecurityInfo":
                return code
            if name == "LocalFree":
                return None
            raise AssertionError(name)

        return call

    monkeypatch.setattr(native, "_bind", fake_bind)
    assert pinned.apply_next() == code
    assert pinned.last_status == code
    set_call = next(args for name, args in calls if name == "SetSecurityInfo")
    assert set_call[:5] == (100 if index == 0 else 200, 1, 0x80000004, None, None)
    assert set_call[5].value == 400 and set_call[6] is None
    sddl = calls[0][1][0]
    assert sddl == "D:P" + "".join(
        f"(A;;0x{mask:x};;;{sid})" for sid, mask, _, _ in r.POST_ACES[index]
    )
    assert r.DRIFT_SID not in sddl
    if index or code:
        with pytest.raises(Exception, match="AUTHORITY"):
            pinned.apply_next()


def test_native_module_has_no_public_writer_and_fixed_binding_set():
    tree = ast.parse(Path(native.__file__).read_text())
    assert not [
        n.name
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")
    ]
    names = [
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_bind"
    ]
    assert names.count("SetSecurityInfo") == 1
    assert set(names) == {
        "SetSecurityInfo",
        "GetAclInformation",
        "GetSecurityInfo",
        "LocalFree",
        "CloseHandle",
        "GetVolumeInformationByHandleW",
        "GetSecurityDescriptorLength",
        "GetFileType",
        "GetSecurityDescriptorControl",
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        "GetFinalPathNameByHandleW",
        "GetAce",
        "GetSecurityDescriptorDacl",
        "GetFileInformationByHandle",
        "ConvertSidToStringSidW",
        "CreateFileW",
        "GetDriveTypeW",
    }


@pytest.mark.parametrize(
    "change",
    [
        "head_interlock",
        "tree_interlock",
        "head_shape",
        "branch",
        "origin",
        "dirty",
        "index",
        "ancestry",
        "base_tree",
        "worktree",
        "hidden_flags",
        "remote",
    ],
)
def test_exact_source_admission_rejects_every_mismatch(monkeypatch, change):
    monkeypatch.setattr(r, "WORKTREE", ROOT)
    monkeypatch.setenv(r.HEAD_ENV, SOURCE[0])
    monkeypatch.setenv(r.TREE_ENV, SOURCE[1])
    commands = {
        ("rev-parse", "HEAD"): SOURCE[0],
        ("rev-parse", "HEAD^{tree}"): SOURCE[1],
        ("branch", "--show-current"): r.BRANCH,
        ("remote", "get-url", "origin"): r.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("diff", "--cached", "--name-only"): "",
        ("merge-base", r.BASE_HEAD, "HEAD"): r.BASE_HEAD,
        ("rev-parse", r.BASE_HEAD + "^{tree}"): r.BASE_TREE,
        ("rev-parse", "--show-toplevel"): str(ROOT),
        ("ls-files", "-v"): "H tracked.py",
        ("ls-remote", "origin", "refs/heads/" + r.BRANCH): SOURCE[0]
        + "\trefs/heads/"
        + r.BRANCH,
    }
    monkeypatch.setattr(r, "_git", lambda *args: commands[args])
    assert r.admit_source() == SOURCE
    if change == "head_interlock":
        monkeypatch.setenv(r.HEAD_ENV, "c" * 40)
    elif change == "tree_interlock":
        monkeypatch.setenv(r.TREE_ENV, "d" * 40)
    else:
        key = {
            "head_shape": ("rev-parse", "HEAD"),
            "branch": ("branch", "--show-current"),
            "origin": ("remote", "get-url", "origin"),
            "dirty": ("status", "--porcelain=v1", "--untracked-files=all"),
            "index": ("diff", "--cached", "--name-only"),
            "ancestry": ("merge-base", r.BASE_HEAD, "HEAD"),
            "base_tree": ("rev-parse", r.BASE_HEAD + "^{tree}"),
            "worktree": ("rev-parse", "--show-toplevel"),
            "hidden_flags": ("ls-files", "-v"),
            "remote": ("ls-remote", "origin", "refs/heads/" + r.BRANCH),
        }[change]
        commands[key] = "invalid"
    with pytest.raises(r.RecoveryRejected):
        r.admit_source()


def test_target_descriptor_readbacks_must_repeat_stably(host, monkeypatch):
    authorize(monkeypatch)
    calls = 0
    original = host.observe

    def unstable():
        nonlocal calls
        calls += 1
        if calls == 3:
            rows = list(host.rows)
            rows[1] = replace(rows[1], descriptor_sha256="e" * 64)
            host.rows = tuple(rows)
        return original()

    monkeypatch.setattr(r, "observe_fixed_scope", unstable)
    assert r.execute_once()["status"] == "INDETERMINATE"


def test_native_free_ambiguity_retains_raw_dword(host, monkeypatch):
    authorize(monkeypatch)
    original = host.pinned

    def ambiguous():
        obj = original()
        apply = obj.apply_next

        def call():
            apply()
            raise OSError("SECRET descriptor free")

        obj.apply_next = call
        return obj

    monkeypatch.setattr(native, "_PinnedTargets", ambiguous)
    report = r.execute_once()
    assert report["status"] == "INDETERMINATE"
    assert primary(report)["native_results"] == [
        {"path": r.TARGET_PATHS[0], "raw_dword": 0}
    ]
    assert host.events[-2:] == ["independent_observation"] * 2


def test_each_non_target_security_observation_is_bound_into_reviewed_plan(
    host, monkeypatch
):
    authorize(monkeypatch)
    rows = list(host.rows)
    rows[3] = replace(rows[3], descriptor_sha256="e" * 64)
    host.rows = tuple(rows)
    assert primary(r.execute_once())["reason"] == "REVIEWED_PLAN_REJECTED"
    assert not r.ATTEMPT_PATH.exists()


def test_consumed_latch_never_grants_a_new_attempt_after_restart(host, monkeypatch):
    authorize(monkeypatch)
    assert r.execute_once()["status"] == "PASS"
    payload = r.ATTEMPT_PATH.read_bytes()
    monkeypatch.setattr(r, "_spent", False)
    assert r.observe_attempt(r.recovery_plan(SOURCE, host.rows)) == "CONSUMED"
    assert primary(r.preflight())["latch_classification"] == "CONSUMED"
    blocked = r.execute_once()
    assert blocked["status"] == "BLOCKED"
    for report in (r.preflight(), blocked):
        row = primary(report)
        assert row["execute_eligible"] is False
        assert report["automatic_retry"] == row["automatic_retry"] == "NOT_AUTHORIZED"
    assert r.ATTEMPT_PATH.read_bytes() == payload
    assert len([event for event in host.events if isinstance(event, tuple)]) == 2


def test_reviewed_plan_drift_is_also_closed_in_read_only_preflight(host, monkeypatch):
    authorize(monkeypatch)
    rows = list(host.rows)
    rows[3] = replace(rows[3], descriptor_sha256="e" * 64)
    host.rows = tuple(rows)
    row = primary(r.preflight())
    assert row["reason"] == "PRE_RECOVERY_BASELINE_DRIFT"
    assert row["execute_eligible"] is False


@pytest.mark.parametrize("directory", [True, False])
def test_fixed_native_read_abi_identity_descriptor_and_aces(monkeypatch, directory):
    session = object.__new__(native._Session)
    session.paths = native._FixedPaths()
    session._mutable = False
    session.kernel = session.advapi = object()
    path = r.TARGET_PATHS[0] if directory else r.RUNTIME_PATHS[1]
    session.handles = {name: index + 10 for index, name in enumerate(r.OBSERVED_PATHS)}
    descriptor = ctypes.create_string_buffer(b"frozen descriptor bytes")
    aces, sid_names = [], {1000: ADMINISTRATORS_SID}
    for sid, mask, kind, flags in r.PRE_ACES[0]:
        raw = ctypes.create_string_buffer(12)
        raw[0], raw[1] = bytes((kind,)), bytes((flags,))
        raw[2], raw[3] = b"\x0c", b"\x00"
        ctypes.cast(ctypes.addressof(raw) + 4, ctypes.POINTER(ctypes.c_uint32))[0] = (
            mask
        )
        sid_names[ctypes.addressof(raw) + 8] = sid
        aces.append(raw)
    calls = []

    def bind(_library, name, _args, _result):
        def call(*args):
            calls.append(name)
            if name == "GetFinalPathNameByHandleW":
                args[1].value = "\\\\?\\" + path
                return len(args[1].value)
            if name == "GetFileType":
                return 1
            if name == "GetFileInformationByHandle":
                info = args[1]._obj
                info.attributes = 0x10 if directory else 0
                info.volume = 1855336320
                info.index_low, info.index_high, info.links = 55, 1, 1
                return 1
            if name == "GetVolumeInformationByHandleW":
                args[3]._obj.value = 1855336320
                args[5]._obj.value = 8
                args[6].value = "NTFS"
                return 1
            if name == "GetSecurityInfo":
                for at, value in (
                    (3, 1000),
                    (4, 2000),
                    (5, 3000),
                    (7, ctypes.addressof(descriptor)),
                ):
                    ctypes.cast(args[at], ctypes.POINTER(ctypes.c_void_p))[0] = value
                return 0
            if name == "GetSecurityDescriptorLength":
                return len(descriptor.raw)
            if name == "GetSecurityDescriptorControl":
                args[1]._obj.value, args[2]._obj.value = 0x1000, 1
                return 1
            if name == "GetAclInformation":
                args[1]._obj.count = len(aces)
                return 1
            if name == "GetAce":
                ctypes.cast(args[2], ctypes.POINTER(ctypes.c_void_p))[0] = (
                    ctypes.addressof(aces[args[1]])
                )
                return 1
            if name == "GetDriveTypeW":
                return 3
            if name == "LocalFree":
                return None
            raise AssertionError(name)

        return call

    monkeypatch.setattr(native, "_bind", bind)
    monkeypatch.setattr(native, "_sid", lambda _a, _k, sid: sid_names[sid.value])
    evidence = session._evidence(path, directory=directory)
    assert evidence.facts.path == path
    assert evidence.facts.kind == ("directory" if directory else "file")
    assert evidence.facts.identity == (1855336320, (1 << 32) | 55)
    assert evidence.facts.aces == r.PRE_ACES[0]
    assert evidence.facts.owner == ADMINISTRATORS_SID
    assert evidence.facts.protected is True
    assert evidence.descriptor_sha256 == hashlib.sha256(descriptor.raw).hexdigest()
    assert calls[-1] == "LocalFree"


def test_native_close_attempts_all_handles_even_on_ambiguity(monkeypatch):
    session = object.__new__(native._Session)
    session.handles = {"first": 1, "second": 2}
    session.kernel = object()
    calls = []

    def bind(_library, name, *_rest):
        assert name == "CloseHandle"

        def close(handle):
            calls.append(handle)
            return 0 if handle == 2 else 1

        return close

    monkeypatch.setattr(native, "_bind", bind)
    with pytest.raises(Exception, match="HANDLE_CLOSE"):
        session.close()
    assert calls == [2, 1] and session.handles == {}


def test_registered_protected_interlocks_and_fixed_dispatch(
    host, monkeypatch, tmp_path
):
    spec = runner._checkpoint_specs()[r.CHECKPOINT]
    monkeypatch.setattr(runner, "_git_state", lambda _: {"porcelain": ""})
    with pytest.raises(RuntimeError, match="R1 authorization"):
        runner.execute_checkpoint(spec, repo_root=tmp_path, evidence_root=tmp_path)
    monkeypatch.setenv(r.AUTH_ENV, r.AUTH_VALUE)
    with pytest.raises(RuntimeError, match="reviewed-plan"):
        runner.execute_checkpoint(spec, repo_root=tmp_path, evidence_root=tmp_path)
    monkeypatch.setenv(r.PLAN_ENV, "0" * 64)
    with pytest.raises(RuntimeError, match="R1 registration"):
        runner.execute_checkpoint(
            replace(spec, description="tampered"),
            repo_root=tmp_path,
            evidence_root=tmp_path,
        )
    monkeypatch.setattr(r, "preflight", lambda: {"route": "R1_READ_ONLY"})
    monkeypatch.setattr(r, "execute_once", lambda: {"route": "R1_PROTECTED"})
    assert spec.preflight() == {"route": "R1_READ_ONLY"}
    assert spec.execute() == {"route": "R1_PROTECTED"}


def test_fresh_leaf_import_is_inert_and_excludes_provider_runtime_graph():
    import subprocess
    import sys

    code = """
import ctypes
import sys
sys.path.insert(0, sys.argv[1])
def forbid(*args, **kwargs):
    raise AssertionError("native API touched at import")
ctypes.WinDLL = forbid
from trading_bot import shared_namespace_acl_native
from trading_bot import shared_namespace_acl_recovery
for name in sys.modules:
    assert not name.startswith((
        "trading_bot.supervised_release", "trading_bot.strategies",
        "trading_bot.market_data", "trading_bot.runtime", "trading_bot.robinhood",
        "trading_bot.brokers", "trading_bot.execution",
    )), name
print("ISOLATED_IMPORT_PASS")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-", str(ROOT / "src")],
        input=code,
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )
    assert result.stdout.strip() == "ISOLATED_IMPORT_PASS"
