"""Fake-only P124-5 operator, native-policy, transport, and ordering checks."""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.d10_protected_deployment_windows import WindowsActivationLeaseBackend
from scripts.d10_protected_replacement_windows import SchedulerObservation

from scripts import d10_activation_scheduler_operator as o
from scripts import d10_protected_deployment as d
from scripts import d10_protected_replacement as r
from trading_bot.runtime.personal_desktop_d10_activation_lease import (
    D10_ACTIVATION_LEASE_PUBLICATION_CONTRACT as P,
)
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_LAUNCHER_RELATIVE_PATH,
    D10_SIGNING_KEY_ID,
    EXECUTABLE_MANIFEST_SCHEMA,
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
)

NOW = datetime(2026, 9, 28, 22, 0, 0, 123456, UTC)
SECRET = "fake-test-password-NEVER-IN-EVIDENCE"


def native(path, *, directory=False, size=0, index=42):
    owner, protected, aces = (
        d.expected_parent_policy()
        if path == d.D10_PARENT
        else d.expected_policy(directory)
    )
    return d.NativeObject(
        path,
        path,
        directory,
        owner,
        protected,
        aces,
        False,
        3,
        "F:\\",
        "NTFS",
        17,
        index,
        1,
        size,
    )


def observation(semantics, digest="a" * 64):
    return SchedulerObservation(tuple(sorted(semantics.items())), 123, digest)


def extended_d5():
    return {
        **o.frozen_d5_scheduler_semantics(),
        "trigger_end_boundary": "",
        "host_timezone": "Pacific Standard Time",
    }


class FakeReader:
    def __init__(self):
        self.files = {}
        self.directories = {}
        self.identities = {}
        self.events = []
        self.admin = True
        self.bad = {}

    def require_administrator(self):
        self.events.append("admin")
        if not self.admin:
            raise RuntimeError(SECRET)

    def absent(self, path):
        return path not in self.files and path not in self.directories

    def list_directory(self, path):
        children = set(self.directories[path])
        if path == d.D10_ROOT:
            children.update(
                p.rsplit("\\", 1)[-1] for p in self.files if p in o._LEASE_PATHS
            )
        item = self.identities.get(path, native(path, directory=True))
        return d.CheckedDirectory(
            replace(item, **self.bad.get(path, {})), tuple(sorted(children)), True
        )

    def read_file(self, path, limit):
        self.events.append("read:" + path.rsplit("\\", 1)[-1])
        data = self.files[path]
        item = self.identities.get(path, native(path, size=len(data)))
        return d.CheckedFile(replace(item, **self.bad.get(path, {})), data, True)


class FakeVerifier:
    key_id = D10_SIGNING_KEY_ID

    def verify(self, message, signature):
        return True


class FakeWriter:
    def __init__(self, reader):
        self.reader = reader
        self.fail = None

    def require_administrator(self):
        self.reader.require_administrator()

    def create_file(self, path, data):
        self.reader.events.append("create:tmp")
        if self.fail == "create_before":
            raise RuntimeError(SECRET)
        if not self.reader.absent(path):
            raise FileExistsError(SECRET)
        self.reader.files[path] = data
        self.reader.identities[path] = native(path, size=len(data), index=123)
        if self.fail == "create_after":
            raise RuntimeError(SECRET)

    def publish_create_only(self, source, target):
        label = "final" if target == P.final_path else "installing"
        self.reader.events.append("publish:" + label)
        if self.fail == label + "_before":
            raise RuntimeError(SECRET)
        if not self.reader.absent(target):
            raise FileExistsError(SECRET)
        self.reader.files[target] = self.reader.files.pop(source)
        self.reader.identities[target] = replace(
            self.reader.identities.pop(source), path=target, final_path=target
        )
        if self.fail == label + "_after":
            raise RuntimeError(SECRET)


@pytest.fixture
def machine(monkeypatch):
    reader = FakeReader()
    writer = FakeWriter(reader)
    state = {
        "semantics": extended_d5(),
        "outcome": o.Disposition.CALL_RETURNED,
        "update_calls": 0,
        "post_drift": None,
    }
    signed_objects = (
        native(d.D10_PARENT, directory=True),
        native(d.D10_ROOT, directory=True),
    )

    def signed(read, verifier):
        read.require_administrator()
        read.events.append("signed")
        current_objects = tuple(
            read.identities.get(item.path, item) for item in signed_objects
        )
        return o.SignedObservation(
            current_objects, tuple(not read.absent(path) for path in o._LEASE_PATHS)
        )

    monkeypatch.setattr(o, "_stable_signed", signed)

    def d5_read():
        reader.events.append("d5")
        o._require_semantics(
            observation(
                {
                    key: value
                    for key, value in state["semantics"].items()
                    if key in o.frozen_d5_scheduler_semantics()
                }
            ),
            o.frozen_d5_scheduler_semantics(),
        )
        return observation(o.frozen_d5_scheduler_semantics())

    def scheduler_read():
        reader.events.append("scheduler_read")
        values = dict(state["semantics"])
        if state["update_calls"] and state["post_drift"]:
            values.update(state["post_drift"])
        return observation(values)

    def update(lease, secret):
        assert secret == SECRET
        reader.events.append("update")
        state["update_calls"] += 1
        if state["outcome"] is o.Disposition.CALL_RETURNED:
            state["semantics"] = o._expected_d10(
                o._planned(lease.accepted_activation_utc)[1]
            )
        if state["outcome"] == "raise":
            raise RuntimeError(SECRET)
        return state["outcome"]

    def credential():
        reader.events.append("credential")
        return SECRET

    operator = o._Operator(
        reader,
        FakeVerifier(),
        writer,
        d5_read,
        scheduler_read,
        update,
        credential,
        lambda: NOW,
    )
    return operator, reader, writer, state


def partial_installing_state(machine, *, activation=NOW):
    operator, reader, writer, state = machine
    lease, spec = o._planned(activation)
    data = lease.canonical_bytes()
    state["semantics"] = o._expected_d10(spec)
    reader.files[P.installing_path] = data
    reader.identities[P.installing_path] = native(
        P.installing_path, size=len(data), index=123
    )
    reader.identities[d.D10_ROOT] = native(
        d.D10_ROOT, directory=True, size=4096, index=42
    )
    return operator, reader, writer, state, lease


def test_happy_path_exact_order_and_seven_day_binding(machine) -> None:
    operator, reader, _, state = machine
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "PASS"
    assert result["scheduler_mutation"] == "CALL_RETURNED"
    assert result["lease_publication"] == "PUBLISHED_VERIFIED"
    lease, spec = o._planned(NOW)
    assert lease.end_utc == NOW + timedelta(days=7) == spec.end_boundary.astimezone(UTC)
    assert reader.files[P.final_path] == lease.canonical_bytes()
    assert state["update_calls"] == 1
    events = reader.events
    update = events.index("update")
    create = events.index("create:tmp")
    final = events.index("publish:final")
    assert "scheduler_read" in events[update + 1 : create]
    assert "signed" in events[update + 1 : create]
    assert (
        events.index("credential")
        < update
        < create
        < events.index("publish:installing")
        < final
    )
    assert "scheduler_read" in events[final + 1 :]
    assert "signed" in events[final + 1 :]
    assert events.count("read:activation.lease.json") == 2
    assert SECRET not in json.dumps(result)
    for effect in ("source_launch", "provider", "Paper-v2", "broker", "live"):
        assert result[effect] == "NOT_RUN"


def test_expected_d10_root_size_change_during_lease_publication_is_allowed(
    machine,
) -> None:
    operator, reader, writer, _ = machine
    reader.identities[d.D10_ROOT] = native(
        d.D10_ROOT, directory=True, size=0, index=42
    )
    original = writer.publish_create_only

    def publish(source, target):
        original(source, target)
        if target == P.installing_path:
            reader.identities[d.D10_ROOT] = replace(
                reader.identities[d.D10_ROOT], size=4096
            )

    writer.publish_create_only = publish
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "PASS"
    assert result["lease_publication"] == "PUBLISHED_VERIFIED"


def test_d10_root_non_size_identity_change_still_blocks(machine) -> None:
    operator, reader, writer, _ = machine
    reader.identities[d.D10_ROOT] = native(
        d.D10_ROOT, directory=True, size=0, index=42
    )
    original = writer.publish_create_only

    def publish(source, target):
        original(source, target)
        if target == P.installing_path:
            reader.identities[d.D10_ROOT] = replace(
                reader.identities[d.D10_ROOT],
                size=4096,
                file_index=999,
            )

    writer.publish_create_only = publish
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "BLOCKED"
    assert result["stage"] == "lease_staging"
    assert reader.absent(P.final_path)


@pytest.mark.parametrize(
    "outcome,status",
    [
        (o.Disposition.NOT_CALLED, "BLOCKED"),
        (o.Disposition.INDETERMINATE, "INDETERMINATE"),
        ("raise", "INDETERMINATE"),
    ],
)
def test_scheduler_failure_or_ambiguity_never_publishes(
    machine, outcome, status
) -> None:
    operator, reader, _, state = machine
    state["outcome"] = outcome
    result = operator.execute(execute_p1245=True)
    assert result["status"] == status
    assert result["reconciliation_required"]
    assert result["lease_publication"] == "NOT_RUN"
    assert reader.files == {}
    assert state["update_calls"] == 1
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize(
    "failure",
    [
        "create_before",
        "create_after",
        "installing_before",
        "installing_after",
        "final_before",
        "final_after",
    ],
)
def test_lease_failures_truthful_no_rollback_or_retry(machine, failure) -> None:
    operator, reader, writer, state = machine
    writer.fail = failure
    result = operator.execute(execute_p1245=True)
    assert result["status"] == (
        "INDETERMINATE" if failure.startswith("final") else "BLOCKED"
    )
    assert result["reconciliation_required"]
    assert result["scheduler_mutation"] == "CALL_RETURNED"
    assert state["update_calls"] == 1
    assert (
        "publish:final" not in reader.events
        if failure.startswith(("create", "installing"))
        else True
    )
    assert reader.absent(P.final_path) is (failure != "final_after")
    assert not result["automatic_retry"] and not result["automatic_rollback"]
    assert SECRET not in json.dumps(result)
    assert dict(state["semantics"])["action_working_directory"] == d.D10_ROOT


@pytest.mark.parametrize("key,expected", list(extended_d5().items()))
def test_every_pre_scheduler_semantic_mismatch_blocks(machine, key, expected) -> None:
    operator, reader, _, state = machine
    state["semantics"][key] = (
        not expected
        if type(expected) is bool
        else expected + 1
        if type(expected) is int
        else expected + "-wrong"
    )
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "BLOCKED"
    assert state["update_calls"] == 0 and "credential" not in reader.events
    assert not reader.files


@pytest.mark.parametrize(
    "key,value",
    [
        ("principal_sid", "wrong"),
        ("action_path", "wrong"),
        ("trigger_end_boundary", ""),
        ("action_arguments", "wrong"),
        ("restart_count", 1),
    ],
)
def test_post_scheduler_drift_blocks_lease(machine, key, value) -> None:
    operator, reader, _, state = machine
    state["post_drift"] = {key: value}
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "BLOCKED"
    assert result["stage"] == "scheduler_post_verification"
    assert reader.files == {} and state["update_calls"] == 1


@pytest.mark.parametrize("path", o._LEASE_PATHS)
def test_existing_lease_staging_and_duplicate_new_invocation_block(
    machine, path
) -> None:
    operator, reader, _, state = machine
    reader.files[path] = b"existing"
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "BLOCKED" and state["update_calls"] == 0
    assert reader.files[path] == b"existing"


def test_duplicate_same_operator_and_missing_execution_switch(machine) -> None:
    operator, reader, _, state = machine
    assert operator.execute()["status"] == "BLOCKED"
    assert not reader.events
    assert operator.execute(execute_p1245=True)["status"] == "PASS"
    assert operator.execute(execute_p1245=True)["status"] == "BLOCKED"
    assert state["update_calls"] == 1


def test_lease_create_collision_after_verified_scheduler(machine) -> None:
    operator, reader, writer, state = machine
    original = writer.create_file

    def collide(path, data):
        reader.files[path] = b"concurrent-existing"
        original(path, data)

    writer.create_file = collide
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "BLOCKED"
    assert result["lease_publication"] == "NOT_PUBLISHED"
    assert reader.files[P.temporary_path] == b"concurrent-existing"
    assert state["update_calls"] == 1 and reader.absent(P.final_path)


@pytest.mark.parametrize(
    "drift", ["bytes", "identity", "acl", "links", "reparse", "filesystem"]
)
def test_final_lease_reread_mismatch_is_indeterminate(machine, drift) -> None:
    operator, reader, writer, _ = machine
    original = writer.publish_create_only

    def publish(source, target):
        original(source, target)
        if target == P.final_path:
            if drift == "bytes":
                reader.files[target] = b"bad-final"
            else:
                key, value = {
                    "identity": ("file_index", 999),
                    "acl": ("dacl_protected", False),
                    "links": ("links", 2),
                    "reparse": ("reparse", True),
                    "filesystem": ("filesystem", "FAT32"),
                }[drift]
                reader.bad[target] = {key: value}

    writer.publish_create_only = publish
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "INDETERMINATE" and result["reconciliation_required"]
    assert result["lease_publication"] == "INDETERMINATE"


def test_preflight_and_independent_reconcile_have_no_mutations(machine) -> None:
    operator, reader, _, state = machine
    assert operator.preflight()["status"] == "PASS"
    assert operator.reconcile()["classification"] == "D5_UNARMED"
    assert state["update_calls"] == 0 and reader.files == {}
    assert operator.execute(execute_p1245=True)["status"] == "PASS"
    assert operator.reconcile()["classification"] == "ARMED_VERIFIED"
    assert state["update_calls"] == 1


def test_reconcile_scheduler_changed_but_lease_absent(machine) -> None:
    operator, reader, writer, _ = machine
    writer.fail = "create_before"
    result = operator.execute(execute_p1245=True)
    assert result["post_state"]["classification"] == "D10_SCHEDULER_LEASE_ABSENT"
    assert reader.absent(P.final_path)


def test_partial_recovery_preflight_is_read_only_and_exact(machine) -> None:
    operator, reader, _, state, lease = partial_installing_state(machine)
    result = operator.recovery_preflight()
    assert result["status"] == "PASS"
    assert result["classification"] == "EXACT_INSTALLING_LEASE_D10_SCHEDULER"
    assert result["planned"] == lease.to_dict()
    assert result["reconciliation_required"]
    assert result["lease_publication"] == "NOT_RUN"
    assert state["update_calls"] == 0
    assert reader.files[P.installing_path] == lease.canonical_bytes()
    assert reader.absent(P.final_path)
    assert not any(event.startswith("publish:") for event in reader.events)


def test_partial_recovery_publishes_only_verified_installing_lease(machine) -> None:
    operator, reader, _, state, lease = partial_installing_state(machine)
    result = operator.recover_partial_installing(execute_p1245_recovery=True)
    assert result["status"] == "PASS"
    assert result["stage"] == "complete"
    assert result["lease_publication"] == "PUBLISHED_VERIFIED"
    assert not result["reconciliation_required"]
    assert reader.files[P.final_path] == lease.canonical_bytes()
    assert reader.absent(P.installing_path)
    assert reader.absent(P.temporary_path)
    assert state["update_calls"] == 0
    assert "credential" not in reader.events
    assert reader.events.count("publish:final") == 1


def test_partial_recovery_requires_dedicated_switch(machine) -> None:
    operator, reader, _, state, lease = partial_installing_state(machine)
    result = operator.recover_partial_installing()
    assert result["status"] == "BLOCKED"
    assert result["stage"] == "recovery_switch_or_duplicate"
    assert reader.files[P.installing_path] == lease.canonical_bytes()
    assert state["update_calls"] == 0
    assert not any(event.startswith("publish:") for event in reader.events)


@pytest.mark.parametrize(
    "failure",
    ["scheduler", "bytes", "final_collision", "temporary_present", "expired"],
)
def test_partial_recovery_preflight_blocks_any_non_exact_state(
    machine, failure
) -> None:
    activation = NOW - timedelta(days=8) if failure == "expired" else NOW
    operator, reader, _, state, lease = partial_installing_state(
        machine, activation=activation
    )
    if failure == "scheduler":
        state["semantics"]["priority"] = 8
    elif failure == "bytes":
        reader.files[P.installing_path] = lease.canonical_bytes() + b"x"
    elif failure == "final_collision":
        reader.files[P.final_path] = lease.canonical_bytes()
    elif failure == "temporary_present":
        reader.files[P.temporary_path] = lease.canonical_bytes()

    result = operator.recovery_preflight()
    assert result["status"] == "BLOCKED"
    assert result["lease_publication"] == "NOT_RUN"
    assert not any(event.startswith("publish:") for event in reader.events)


def test_partial_recovery_ambiguous_final_publication_never_retries(machine) -> None:
    operator, reader, writer, state, _ = partial_installing_state(machine)
    writer.fail = "final_after"
    result = operator.recover_partial_installing(execute_p1245_recovery=True)
    assert result["status"] == "INDETERMINATE"
    assert result["reconciliation_required"]
    assert result["lease_publication"] == "INDETERMINATE"
    assert reader.events.count("publish:final") == 1
    assert state["update_calls"] == 0
    assert "credential" not in reader.events


@pytest.mark.parametrize(
    "instant",
    [
        NOW,
        datetime(2026, 10, 31, 23, 59, 59, 999999, UTC),
        datetime(2027, 3, 13, 23, 30, 0, 0, UTC),
    ],
)
def test_exact_seven_day_binding_across_dst(instant) -> None:
    lease, spec = o._planned(instant)
    assert lease.end_utc == instant + timedelta(days=7)
    assert spec.end_boundary.astimezone(UTC) == lease.end_utc
    assert o._expected_d10(spec)["trigger_end_boundary"] == spec.end_boundary.isoformat(
        timespec="auto"
    )
    assert (
        spec.task.arguments == o.D10_GUARD_ARGUMENTS
        and not spec.task.semantic_arguments
    )


def full_native(monkeypatch):
    reader = FakeReader()
    source_files = {
        D10_LAUNCHER_RELATIVE_PATH: b"launcher",
        "src/trading_bot/__init__.py": b"package",
    }
    entries = tuple(
        ExecutableManifestEntry(path, len(data), hashlib.sha256(data).hexdigest())
        for path, data in sorted(source_files.items())
    )
    manifest = ExecutableManifest(EXECUTABLE_MANIFEST_SCHEMA, entries)
    guard = b"sealed guard"
    attestation = build_deployment_attestation(
        certified_source_head=r.NEW_IDENTITY.certified_source_head,
        certified_source_tree=r.NEW_IDENTITY.certified_source_tree,
        production_python_version="3.14.3",
        launch_guard_byte_length=len(guard),
        launch_guard_sha256=hashlib.sha256(guard).hexdigest(),
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(entries),
    )
    # Compact fake native inventory only; production pins remain tested separately.
    monkeypatch.setattr(
        r,
        "NEW_IDENTITY",
        replace(
            r.NEW_IDENTITY,
            deployment_id=attestation.deployment_id,
            manifest_sha256=manifest.digest,
            executable_file_count=2,
            executable_total_bytes=15,
            guard_byte_length=len(guard),
            guard_sha256=hashlib.sha256(guard).hexdigest(),
            unsigned_attestation_sha256=hashlib.sha256(
                attestation.canonical_bytes()
            ).hexdigest(),
        ),
    )
    reader.directories = {
        d.D10_PARENT: ("D10", "runtime"),
        d.D10_ROOT: (
            "source",
            "launch-guard.py",
            "deployment.attestation.json",
            "deployment.attestation.sig",
            "executable-manifest.json",
        ),
        d.D10_SOURCE: ("scripts", "src"),
        d.D10_SOURCE + r"\scripts": (D10_LAUNCHER_RELATIVE_PATH.split("/")[-1],),
        d.D10_SOURCE + r"\src": ("trading_bot",),
        d.D10_SOURCE + r"\src\trading_bot": ("__init__.py",),
    }
    reader.files = {
        d.D10_GUARD: guard,
        d.D10_MANIFEST: manifest.canonical_bytes(),
        d.D10_ATTESTATION: attestation.canonical_bytes(),
        d.D10_SIGNATURE: (bytes(31) + bytes([1])) * 2,
    }
    reader.files.update(
        {
            d.D10_SOURCE + "\\" + path.replace("/", "\\"): data
            for path, data in source_files.items()
        }
    )
    return reader


def test_complete_signed_native_inventory_fake(monkeypatch) -> None:
    reader = full_native(monkeypatch)
    result = o._stable_signed(reader, FakeVerifier())
    assert result.leases_present == (False, False, False)
    assert len(result.objects) == 12


@pytest.mark.parametrize(
    "mismatch",
    [
        "administrator",
        "retired",
        "staging",
        "cache",
        "manifest",
        "guard",
        "attestation",
        "source",
        "signature",
        "inventory_extra",
        "inventory_missing",
        "owner",
        "dacl",
        "reparse",
        "hardlink",
        "volume",
        "non_ntfs",
        "native_identity_drift",
        "source_head",
        "source_tree",
        "deployment_id",
    ],
)
def test_native_admission_mismatches(monkeypatch, mismatch) -> None:
    reader = full_native(monkeypatch)
    verifier = FakeVerifier()
    if mismatch == "administrator":
        reader.admin = False
    elif mismatch in ("retired", "staging", "cache"):
        path = {
            "retired": r.RETIRED_PATH,
            "staging": r.STAGING_PATH,
            "cache": d.D10_CACHE_PREFIX,
        }[mismatch]
        reader.directories[path] = ()
    elif mismatch in ("manifest", "guard", "attestation", "source"):
        path = {
            "manifest": d.D10_MANIFEST,
            "guard": d.D10_GUARD,
            "attestation": d.D10_ATTESTATION,
            "source": d.D10_SOURCE + r"\src\trading_bot\__init__.py",
        }[mismatch]
        reader.files[path] += b"bad"
    elif mismatch == "signature":
        verifier.verify = lambda *_: False
    elif mismatch.startswith("inventory_"):
        reader.directories[d.D10_SOURCE] = (
            ("src", "scripts", "__pycache__")
            if mismatch == "inventory_extra"
            else ("src",)
        )
    elif mismatch in ("source_head", "source_tree", "deployment_id"):
        key = {
            "source_head": "certified_source_head",
            "source_tree": "certified_source_tree",
            "deployment_id": "deployment_id",
        }[mismatch]
        monkeypatch.setattr(
            r, "NEW_IDENTITY", replace(r.NEW_IDENTITY, **{key: "0" * 40})
        )
    elif mismatch == "native_identity_drift":
        original = reader.list_directory
        count = 0

        def drift(path):
            nonlocal count
            result = original(path)
            if path == d.D10_PARENT:
                count += 1
                result = replace(
                    result, identity=replace(result.identity, file_index=count)
                )
            return result

        reader.list_directory = drift
    else:
        key, value = {
            "owner": ("owner_sid", "wrong"),
            "dacl": ("dacl_protected", False),
            "reparse": ("reparse", True),
            "hardlink": ("links", 2),
            "volume": ("volume_serial", 18),
            "non_ntfs": ("filesystem", "FAT32"),
        }[mismatch]
        reader.bad[d.D10_GUARD] = {key: value}
    with pytest.raises(
        (o.OperatorBlocked, d.DeploymentBlocked, ValueError, RuntimeError, KeyError)
    ):
        o._stable_signed(reader, verifier)


def record(first=None, second=None):
    value = {**extended_d5(), "xml_byte_length": 123, "xml_sha256": "a" * 64}
    return json.dumps(
        {
            "schema": o.SCHEDULER_SCHEMA,
            "status": "OBSERVED",
            "first": first or value,
            "second": second or value,
        }
    ).encode()


@pytest.mark.parametrize(
    "bad",
    [
        b"",
        b"{}",
        b"[]",
        b"null",
        b'{"schema":1,"schema":2}',
        b"x" * (o.MAX_TRANSPORT + 1),
    ],
)
def test_malformed_scheduler_transport_blocks(bad) -> None:
    with pytest.raises(
        (o.OperatorBlocked, d.DeploymentBlocked, ValueError, RuntimeError, KeyError)
    ):
        o._parse_scheduler(bad)


def test_scheduler_two_read_and_exact_type_checks() -> None:
    first = {**extended_d5(), "xml_byte_length": 123, "xml_sha256": "a" * 64}
    for drift in (
        {"xml_sha256": "b" * 64},
        {"xml_byte_length": 124},
        {"run_level": False},
        {"action_count": 2},
    ):
        with pytest.raises(
            (o.OperatorBlocked, d.DeploymentBlocked, ValueError, RuntimeError, KeyError)
        ):
            observed = o._parse_scheduler(record(first, {**first, **drift}))
            o._require_semantics(observed, extended_d5())


def test_update_transport_has_fixed_args_and_secret_free_evidence(monkeypatch) -> None:
    lease, _ = o._planned(NOW)
    calls = []

    def transport(helper, payload=None):
        calls.append((o._command(helper), payload))
        return (
            0,
            b'{"schema":"p1245-task-scheduler-update/v1","disposition":"CALL_RETURNED"}',
            b"",
        )

    monkeypatch.setattr(o, "_transport", transport)
    assert o._update_scheduler(lease, SECRET) is o.Disposition.CALL_RETURNED
    assert SECRET not in " ".join(calls[0][0])
    assert calls[0][0][-1] == str(o.UPDATE_HELPER)
    assert json.loads(calls[0][1]) == {
        "activation_utc": o.format_utc_instant(NOW),
        "password": SECRET,
    }
    assert "password" not in lease.to_dict()


@pytest.mark.parametrize(
    "code,out,err",
    [
        (1, b"bad", b""),
        (0, b"{}", b""),
        (0, b"", SECRET.encode()),
        (
            2,
            b'{"schema":"p1245-task-scheduler-update/v1","disposition":"CALL_RETURNED"}',
            b"",
        ),
    ],
)
def test_update_transport_ambiguous_results(monkeypatch, code, out, err) -> None:
    monkeypatch.setattr(o, "_transport", lambda *_: (code, out, err))
    assert (
        o._update_scheduler(o._planned(NOW)[0], SECRET) is o.Disposition.INDETERMINATE
    )


def test_fixed_pins_and_public_authority_surfaces() -> None:
    assert r.NEW_IDENTITY.deployment_id == "9f3d111b-25bb-5ee4-9abf-f5215a32b826"
    assert (
        r.NEW_IDENTITY.unsigned_attestation_sha256
        == "4e4e44d4129876454bd5d9559af7358f2600466f9291c6626f92e173d541f2c2"
    )
    assert (
        r.NEW_IDENTITY.certified_source_head
        == "c5cc0b01301600daf17f1114f4451dca2c9d7a1f"
    )
    assert (
        r.NEW_IDENTITY.certified_source_tree
        == "bfacfadaa14315d2d378abcc0f1e4bc7c42034f1"
    )
    assert r.NEW_IDENTITY.guard_byte_length == 69259
    assert (
        r.NEW_IDENTITY.guard_sha256
        == "37d78c65800a315a12049b6c278addf609589d121e15d31dd9064dc8ec427298"
    )
    assert not inspect.signature(o.preflight).parameters
    assert not inspect.signature(o.reconcile).parameters
    assert not inspect.signature(o.recovery_preflight).parameters
    assert set(inspect.signature(o.execute).parameters) == {"execute_p1245"}
    assert set(inspect.signature(o.recover_partial_installing).parameters) == {
        "execute_p1245_recovery"
    }
    assert P.final_path == r"F:\AITradingBot\D10\activation.lease.json"
    assert P.trading_read_only_mask == 0x00120089


def test_native_writer_allowlist_and_no_replace_call(monkeypatch) -> None:
    backend = object.__new__(WindowsActivationLeaseBackend)
    assert backend._allowed_file_create(P.temporary_path)
    assert backend._allowed_file_create(P.installing_path)
    assert not backend._allowed_file_create(P.final_path)
    assert not backend._allowed_file_create(d.D10_GUARD + ".installing")
    assert not backend._allowed_directory_create(d.D10_ROOT)
    backend._kernel = object()
    monkeypatch.setattr(backend, "require_administrator", lambda: None)
    calls = []
    monkeypatch.setattr(
        backend,
        "_bind",
        lambda lib, name, args, result: (
            lambda *values: calls.append((name, values)) or True
        ),
    )
    backend.publish_create_only(P.temporary_path, P.installing_path)
    backend.publish_create_only(P.installing_path, P.final_path)
    assert calls == [
        ("MoveFileW", (P.temporary_path, P.installing_path)),
        ("MoveFileW", (P.installing_path, P.final_path)),
    ]
    with pytest.raises(d.DeploymentBlocked):
        backend.publish_create_only(P.final_path, P.final_path)


def test_cli_rejects_authority_and_execute_switch_misuse(capsys) -> None:
    for args in (
        ["execute"],
        ["recover-partial"],
        ["preflight", "--execute-p1245"],
        ["recovery-preflight", "--execute-p1245-recovery"],
        ["reconcile", "--activation-utc", "2026-01-01"],
        ["execute", "--execute-p1245", "--password", SECRET],
        ["recover-partial", "--execute-p1245-recovery", "--password", SECRET],
        ["execute", "--execute-p1245", "--execute-p1245-recovery"],
    ):
        with pytest.raises(SystemExit):
            o.main(args)
        captured = capsys.readouterr()
        assert SECRET not in captured.err + captured.out


def test_no_console_credential_fallback(monkeypatch) -> None:
    monkeypatch.setattr(o.sys.stdin, "isatty", lambda: False)
    with pytest.raises(o.OperatorBlocked):
        o._interactive_credential()


def test_import_inert_and_source_has_no_trading_launch(monkeypatch) -> None:
    import importlib

    def forbidden(*args, **kwargs):
        raise AssertionError("host effect forbidden")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    importlib.reload(o)
    source = Path(o.__file__).read_text(encoding="utf-8")
    assert "run_personal_desktop_d10_launch_guard" not in source
    assert "run_personal_desktop_unattended_one_week_soak.py" not in source
    for script in (o.OBSERVE_HELPER, o.UPDATE_HELPER):
        source = script.read_text(encoding="utf-8")
        for forbidden_token in (
            ".Run(",
            ".DeleteTask(",
            ".Stop(",
            "schtasks",
            "Register-ScheduledTask",
        ):
            assert forbidden_token not in source
    update = o.UPDATE_HELPER.read_text(encoding="utf-8")
    assert (
        "RegisterTaskDefinition('AITradingBot-PD4-UnattendedPaper-v1', $definition, 4,"
        in update
    )
    assert "$password, 1, $null" in update
    observer = o.OBSERVE_HELPER.read_text(encoding="utf-8")
    assert "RegisterTaskDefinition" not in observer


def test_admission_and_credential_pause_detect_two_read_drift(
    machine, monkeypatch
) -> None:
    operator, reader, _, state = machine
    original = o._stable_signed
    count = 0

    def drifting(*args):
        nonlocal count
        count += 1
        signed = original(*args)
        if count >= 3:
            signed = replace(
                signed,
                objects=(
                    replace(signed.objects[0], file_index=999),
                    *signed.objects[1:],
                ),
            )
        return signed

    monkeypatch.setattr(o, "_stable_signed", drifting)
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "BLOCKED"
    assert result["stage"] == "fresh_admission_after_credential"
    assert state["update_calls"] == 0 and reader.files == {}
    assert SECRET not in json.dumps(result)


def test_scheduler_two_read_stability_before_mutation(machine) -> None:
    operator, reader, _, state = machine
    original = operator.scheduler_read
    count = 0

    def drifting():
        nonlocal count
        count += 1
        observed = original()
        return replace(observed, xml_sha256="b" * 64) if count == 2 else observed

    operator.scheduler_read = drifting
    assert operator.execute(execute_p1245=True)["status"] == "BLOCKED"
    assert state["update_calls"] == 0 and "credential" not in reader.events


def test_final_independent_scheduler_drift_is_indeterminate(machine) -> None:
    operator, reader, _, state = machine
    original = operator.scheduler_read

    def drifting():
        observed = original()
        if not reader.absent(P.final_path):
            semantics = dict(observed.semantics)
            semantics["priority"] = 8
            observed = observation(semantics)
        return observed

    operator.scheduler_read = drifting
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "INDETERMINATE"
    assert result["stage"] == "final_independent_reread"
    assert result["lease_publication"] == "INDETERMINATE"
    assert not reader.absent(P.final_path) and state["update_calls"] == 1


def test_second_lease_read_drift_is_indeterminate(machine) -> None:
    operator, reader, _, _ = machine
    original = reader.read_file
    final_reads = 0

    def drifting(path, limit):
        nonlocal final_reads
        checked = original(path, limit)
        if path == P.final_path:
            final_reads += 1
            if final_reads >= 2:
                checked = replace(
                    checked, identity=replace(checked.identity, file_index=456)
                )
        return checked

    reader.read_file = drifting
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "INDETERMINATE"
    assert result["stage"] == "final_independent_reread"


def test_fresh_instance_duplicate_invocation_blocks_before_password(machine) -> None:
    operator, reader, writer, state = machine
    assert operator.execute(execute_p1245=True)["status"] == "PASS"
    second = o._Operator(
        reader,
        operator.verifier,
        writer,
        operator.d5_read,
        operator.scheduler_read,
        operator.update,
        lambda: pytest.fail("password prompt forbidden on duplicate"),
        operator.now,
    )
    assert second.execute(execute_p1245=True)["status"] == "BLOCKED"
    assert state["update_calls"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("deployment_id", "00000000-0000-0000-0000-000000000000"),
        ("certified_source_head", "0" * 40),
        ("certified_source_tree", "0" * 40),
        ("approved_trading_sid", "S-1-5-18"),
        ("production_python", r"F:\wrong\python.exe"),
        ("production_python_version", "3.13.0"),
        ("scheduler_contract_schema", "wrong"),
        ("launch_guard", r"F:\wrong\guard.py"),
        ("launch_guard_sha256", "0" * 64),
    ],
)
def test_signed_authority_field_mismatch_never_admits(
    monkeypatch, field, value
) -> None:
    reader = full_native(monkeypatch)
    payload = json.loads(reader.files[d.D10_ATTESTATION])
    payload[field] = value
    reader.files[d.D10_ATTESTATION] = o.canonical_json_bytes(payload)
    with pytest.raises((o.OperatorBlocked, d.DeploymentBlocked, ValueError)):
        o._stable_signed(reader, FakeVerifier())


def test_source_native_reader_is_public_fixed_and_has_no_mutator() -> None:
    assert not hasattr(o.WindowsD10ReadOnlyReader, "create_file")
    assert not hasattr(o.WindowsD10ReadOnlyReader, "publish_create_only")
    backend = object.__new__(WindowsActivationLeaseBackend)
    assert (backend.final_path, backend.installing_path, backend.temporary_path) == (
        P.final_path,
        P.installing_path,
        P.temporary_path,
    )
    for path in (
        r"F:\other\lease.json",
        P.final_path + ":stream",
        P.final_path + ".other",
    ):
        assert not backend._allowed_file_create(path)
        assert not backend._allowed_object_path(path, directory=False)


def test_native_create_new_flush_protected_acl_and_exact_bytes(monkeypatch) -> None:
    import ctypes

    import scripts.d10_protected_deployment_windows as native_module

    backend = object.__new__(WindowsActivationLeaseBackend)
    backend._kernel = object()
    calls = []
    attributes = native_module._SecurityAttributes()
    monkeypatch.setattr(
        backend, "_security_attributes", lambda *, directory: (object(), attributes)
    )
    monkeypatch.setattr(backend, "_free_security_descriptor", lambda _: None)
    monkeypatch.setattr(
        backend,
        "_set_acl",
        lambda handle, *, directory: calls.append(("acl", handle, directory)),
    )

    def bind(library, name, args, result):
        def call(*values):
            if name == "CreateFileW":
                assert values[0] == P.temporary_path
                assert values[4] == 1  # CREATE_NEW, never truncate/open existing.
                assert values[5] & native_module.FILE_FLAG_OPEN_REPARSE_POINT
                assert values[5] & native_module.FILE_FLAG_WRITE_THROUGH
                calls.append(("create_new",))
                return 101
            if name == "WriteFile":
                data = ctypes.string_at(values[1], values[2])
                assert data == b"canonical bytes"
                values[3]._obj.value = values[2]
                calls.append(("write",))
                return True
            calls.append((name,))
            return True

        return call

    monkeypatch.setattr(backend, "_bind", bind)
    backend.create_file(P.temporary_path, b"canonical bytes")
    assert calls == [
        ("create_new",),
        ("write",),
        ("FlushFileBuffers",),
        ("acl", 101, False),
        ("CloseHandle",),
    ]
    with pytest.raises(d.DeploymentBlocked):
        backend.create_file(P.final_path, b"renewal forbidden")


def test_bounded_transport_uses_private_pipe_and_fixed_command(monkeypatch) -> None:
    import io

    lease, _ = o._planned(NOW)
    command_calls = []

    class Sink(io.BytesIO):
        def close(self):
            self.saved = self.getvalue()

    class Process:
        def __init__(self, command, **kwargs):
            assert kwargs["stdin"] is subprocess.PIPE
            assert (
                kwargs["stdout"] is subprocess.PIPE
                and kwargs["stderr"] is subprocess.PIPE
            )
            command_calls.append(command)
            self.stdin = Sink()
            self.stdout = io.BytesIO(
                b'{"schema":"p1245-task-scheduler-update/v1","disposition":"CALL_RETURNED"}'
            )
            self.stderr = io.BytesIO()
            instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def wait(self, *, timeout=None):
            assert timeout == 60
            return 0

    instances = []
    monkeypatch.setattr(subprocess, "Popen", Process)
    assert o._update_scheduler(lease, SECRET) is o.Disposition.CALL_RETURNED
    assert command_calls == [o._command(o.UPDATE_HELPER)]
    assert SECRET not in " ".join(command_calls[0])
    assert json.loads(instances[0].stdin.saved)["password"] == SECRET


def test_oversized_private_credential_never_starts_child(monkeypatch) -> None:
    monkeypatch.setattr(o, "_transport", lambda *_: pytest.fail("child must not start"))
    assert (
        o._update_scheduler(o._planned(NOW)[0], "x" * o.MAX_TRANSPORT)
        is o.Disposition.NOT_CALLED
    )


def test_full_fake_native_operator_happy_path_without_signed_shortcut(
    monkeypatch,
) -> None:
    reader = full_native(monkeypatch)
    writer = FakeWriter(reader)
    state = {"semantics": extended_d5(), "calls": 0}

    def update(lease, secret):
        assert secret == SECRET
        state["semantics"] = o._expected_d10(
            o._planned(lease.accepted_activation_utc)[1]
        )
        state["calls"] += 1
        return o.Disposition.CALL_RETURNED

    operator = o._Operator(
        reader,
        FakeVerifier(),
        writer,
        lambda: observation(o.frozen_d5_scheduler_semantics()),
        lambda: observation(state["semantics"]),
        update,
        lambda: SECRET,
        lambda: NOW,
    )
    result = operator.execute(execute_p1245=True)
    assert result["status"] == "PASS"
    assert state["calls"] == 1
    assert result["pre_state"]["signed_deployment"]["native_object_count"] == 12
    assert (
        result["post_state"]["lease"]["bytes_sha256"]
        == hashlib.sha256(reader.files[P.final_path]).hexdigest()
    )
    assert SECRET not in json.dumps(result)


def test_native_acl_masks_exactly_match_publication_contract() -> None:
    owner, protected, aces = d.expected_policy(False)
    assert owner == P.owner_sid and protected is P.protected_dacl
    assert tuple(ace.mask for ace in aces) == (
        P.administrators_access_mask,
        P.system_access_mask,
        P.trading_read_only_mask,
    )
    assert tuple(ace.flags for ace in aces) == (0, 0, 0)
    assert d.expected_policy(True)[2][-1].mask == P.parent_trading_read_only_mask


def test_update_uses_the_same_verified_com_definition_and_utf8_private_input() -> None:
    update = o.UPDATE_HELPER.read_text(encoding="utf-8")
    observer = o.OBSERVE_HELPER.read_text(encoding="utf-8")
    assert "$third = Read-FixedTask $folder ([ref]$definition)" in update
    assert "param($FixedFolder, $CapturedDefinition = $null)" in observer
    assert "[ref]$CapturedDefinition = $null" not in observer
    assert (
        "$CapturedDefinition -isnot [System.Management.Automation.PSReference]"
        in observer
    )
    assert "$CapturedDefinition.Value = $definition" in observer
    assert (
        "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false, $true)"
        in update
    )
    assert "$definition = $task.Definition" not in update
