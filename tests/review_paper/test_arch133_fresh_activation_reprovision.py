"""133-Q inert-filesystem qualification; production/native effects are forbidden."""

import ctypes
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.arch133_acl import primitive, read_only, retained_reads
from trading_bot.arch133_reprovision import (
    generation,
    material,
    namespace,
    native,
    operator,
    predecessor,
    reads,
)
from trading_bot.arch133_verifier import binding, file_policy
from trading_bot.arch133_verifier.activation import ReviewPaperActivation, RiskLimits
from trading_bot.domain import OrderSide, Symbol, TradeProposal

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)
OLD = datetime(2026, 10, 5, 12, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def deny_real_native(monkeypatch):
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda *a, **kw: pytest.fail("real native edge")
    )


def activation(at, runtime, store, seed):
    return ReviewPaperActivation(
        source_head=runtime.source_head,
        source_tree=runtime.source_tree,
        deployment_identity=runtime.deployment_identity,
        target_session_date=at.date(),
        proposal=TradeProposal(
            UUID(int=seed), Symbol("SPY"), OrderSide.BUY, Decimal("1"), at, "reviewed"
        ),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        store_identity=UUID(int=seed + 1),
        store_path=str(store),
        starting_cash=Decimal("10000"),
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=5),
        max_quote_age=timedelta(minutes=1),
        slippage_basis_points=Decimal("5"),
        commission=Decimal("0.1"),
        local_order_id=UUID(int=seed + 2),
        created_at=at,
    )


def reviewed(act, runtime):
    host = binding.HostBinding(
        runtime,
        material.digest(act.to_json().encode()),
        act.store_identity,
        predecessor.expected_empty_paper_sha256(act.starting_cash),
        NOW + timedelta(days=5),
    )
    return material.Material.parse(
        material.canonical(
            {
                "schema": material.MATERIAL_SCHEMA,
                "activation": act.to_json(),
                "host_binding": host.to_json(),
            }
        ).encode()
    )


@pytest.fixture
def fake(tmp_path, monkeypatch):
    active, stage_parent, archive = (
        tmp_path / name for name in ("active", "stage", "archive")
    )
    stage = stage_parent / "generation"
    for mod in (generation, namespace, native):
        monkeypatch.setattr(mod, "ACTIVE", str(active))
        monkeypatch.setattr(mod, "ARCHIVE", str(archive))
        monkeypatch.setattr(mod, "STAGING_PARENT", str(stage_parent))
    for mod in (generation, native):
        monkeypatch.setattr(mod, "STAGE", str(stage))
    monkeypatch.setattr(reads, "ROOTS", (str(active), str(stage), str(archive)))
    monkeypatch.setattr(retained_reads, "TARGET_PATH", str(active))
    for key, name in (
        ("ACTIVATION_PATH", "activation.json"),
        ("BINDING_PATH", "host-binding.json"),
        ("STATE_PATH", "wake.sqlite"),
        ("PAPER_PATH", "paper.sqlite"),
    ):
        monkeypatch.setattr(binding, key, active / name)
    runtime = binding.HostRuntimeIdentity(
        predecessor.PUBLISHED_RUNTIME_HEAD,
        predecessor.PUBLISHED_RUNTIME_TREE,
        binding.PRODUCTION_PYTHON_SHA256,
        binding.PRODUCTION_PYTHON_VERSION,
        "d" * 64,
    )
    old = activation(OLD, runtime, binding.PAPER_PATH, 1)
    fresh = activation(NOW, runtime, binding.PAPER_PATH, 10)
    old_material, fresh_material = reviewed(old, runtime), reviewed(fresh, runtime)
    f = SimpleNamespace(
        active=active,
        stage=stage,
        archive=archive,
        path=tmp_path / "material.json",
        old=old,
        new=fresh,
        material=fresh_material,
        runtime=runtime,
        events=[],
        policies={},
        root_policies={},
    )
    f.path.write_bytes(fresh_material.raw)
    counters = dict(operator.ZERO_EFFECTS)
    monkeypatch.setattr(
        primitive,
        "create_admin_directory",
        lambda path: (
            Path(path).mkdir(),
            f.policies.__setitem__(path, None) if path == str(stage_parent) else None,
        ),
    )
    monkeypatch.setattr(
        native, "_open_mutable_file", lambda root, name, **kw: str(Path(root) / name)
    )
    monkeypatch.setattr(
        native, "_policy", lambda handle, rights: f.policies.__setitem__(handle, rights)
    )
    monkeypatch.setattr(
        native,
        "apply_root_policy_status",
        lambda handle: f.root_policies.__setitem__(handle, "EXACT_INTENDED_ROOT") or 0,
    )
    monkeypatch.setattr(read_only, "open_directory", lambda path, **kw: path)
    monkeypatch.setattr(read_only, "close_handle", lambda handle: None)
    monkeypatch.setattr(reads, "open_generation_directory", lambda path: path)
    # Use the real stage/database builder only beneath pytest's external temp root.
    native.STAGE = str(active)
    native.WindowsEdges(counters).stage(old_material)
    native.STAGE = str(stage)
    # The initial temporary staging parent is deliberately removed by fixture
    # setup only. The operator contains no cleanup or deletion path.
    stage_parent.rmdir()
    old_identity = (42, active.stat().st_ino)
    monkeypatch.setattr(predecessor, "ROOT_IDENTITY", old_identity)
    f.runtime_facts = {
        "operator_source_head": "a" * 40,
        "operator_source_tree": "b" * 40,
        "bound_source_head": predecessor.EXECUTABLE_SOURCE_HEAD,
        "bound_source_tree": predecessor.EXECUTABLE_SOURCE_TREE,
        "python_sha256": binding.PRODUCTION_PYTHON_SHA256,
        "python_version": binding.PRODUCTION_PYTHON_VERSION,
        "wake_launcher_sha256": runtime.launcher_sha256,
    }
    monkeypatch.setattr(predecessor, "observe_runtime", lambda: dict(f.runtime_facts))
    monkeypatch.setattr(predecessor, "require_administrator", lambda: None)
    monkeypatch.setattr(operator, "utc_now", lambda: NOW)
    monkeypatch.setattr(
        operator, "authorize", lambda sha: f.events.append("authorized")
    )

    @contextmanager
    def parents():
        yield {"parent": "fixed-test-identity"}

    monkeypatch.setattr(namespace, "parent_guard", parents)
    monkeypatch.setattr(
        namespace,
        "final_namespace",
        lambda: {"stage_empty": not list(stage_parent.iterdir())},
    )

    def security(handle, path):
        kind = (
            "ADMIN_SYSTEM_ONLY"
            if f.policies.get(path, "unset") is None
            else f.root_policies.get(path, "EXACT_INTENDED_ROOT")
        )
        aces = (
            read_only.ADMIN_ACES if kind == "ADMIN_SYSTEM_ONLY" else read_only.ROOT_ACES
        )
        observation = read_only.DirectoryObservation(
            read_only.ADMINISTRATORS_SID, True, aces, (42, Path(path).stat().st_ino)
        )
        return (
            observation,
            predecessor.ROOT_SECURITY_SHA256
            if kind == "EXACT_INTENDED_ROOT"
            else "e" * 64,
        )

    monkeypatch.setattr(read_only, "inspect_directory_security", security)

    def names(handle):
        found = tuple(sorted((p.name, p.stat().st_ino) for p in Path(handle).iterdir()))
        if tuple(name for name, _ in found) != reads.FINAL_NAMES:
            raise ValueError("namespace rejected")
        return found

    monkeypatch.setattr(reads, "namespace", names)
    monkeypatch.setattr(retained_reads, "namespace", names)
    monkeypatch.setattr(
        reads, "open_generation_file", lambda root, name, **kw: str(Path(root) / name)
    )
    monkeypatch.setattr(
        retained_reads, "open_retained_file", lambda name: str(active / name)
    )

    def snapshot(handle, *args):
        path = Path(handle)
        return (42, path.stat().st_ino), material.digest(path.read_bytes())

    monkeypatch.setattr(reads, "file_snapshot", snapshot)
    monkeypatch.setattr(retained_reads, "file_snapshot", snapshot)

    def policy(handle):
        return file_policy.FilePolicy(
            read_only.ADMINISTRATORS_SID,
            True,
            read_only.ADMIN_ACES + ((read_only.TRADING_SID, f.policies[handle], 0, 0),),
            "f" * 64,
        )

    monkeypatch.setattr(file_policy, "observe_file_policy", policy)
    monkeypatch.setattr(
        predecessor,
        "FILE_HASHES",
        {
            name: material.digest((active / name).read_bytes())
            for name in reads.FINAL_NAMES
        },
    )

    def rename(handle, parent, source, destination):
        f.events.append(("rename", source, destination))
        os.rename(source, destination)
        for mapping in (f.policies, f.root_policies):
            for key, _value in list(mapping.items()):
                if key == source or key.startswith(source + os.sep):
                    mapping[destination + key[len(source) :]] = mapping.pop(key)

    monkeypatch.setattr(native, "_open_rename_root", lambda root: root)
    monkeypatch.setattr(native, "_rename", rename)
    f.old_material = old_material
    return f


def plan_hash(fake):
    plan, _, _ = operator.make_plan(fake.path)
    return material.digest(material.canonical(plan).encode())


def test_exact_stale_plan_is_effect_free_and_binds_all_bytes(fake):
    code, result = operator.run("plan", fake.path)
    assert code == 0
    assert result["plan"]["schema"] == operator.PLAN_SCHEMA
    assert result["plan"]["material_sha256"] == material.digest(fake.path.read_bytes())
    assert all(
        type(result[key]) is int and result[key] == 0 for key in operator.ZERO_EFFECTS
    )
    assert all(result["plan"][key] == 0 for key in operator.ZERO_EFFECTS)
    assert fake.events == [] and not fake.stage.exists() and not fake.archive.exists()


def test_success_requires_preserved_archive_and_exact_new_active(fake):
    sha = plan_hash(fake)
    old_hashes = {
        p.name: material.digest(p.read_bytes()) for p in fake.active.iterdir()
    }
    code, result = operator.run("execute-once", fake.path, sha)
    assert code == 0, result
    assert result["status"] == "PASS"
    assert (
        fake.active.joinpath("activation.json").read_bytes()
        == fake.new.to_json().encode()
    )
    assert {
        p.name: material.digest(p.read_bytes()) for p in fake.archive.iterdir()
    } == old_hashes
    assert result["active_generation"]["wake_revision"] == 0
    assert result["active_generation"]["activation_id"] == str(fake.new.activation_id)
    assert result["archived_predecessor"]["activation_id"] == str(
        fake.old.activation_id
    )
    assert len([x for x in fake.events if isinstance(x, tuple)]) == 2
    assert not fake.stage.exists()
    for key in (
        "scheduler_reads",
        "scheduler_writes",
        "provider_calls",
        "credential_reads",
        "credential_writes",
        "wake_delegations",
        "broker_effects",
        "manual_task_starts",
        "execution_delegations",
        "consumed_wake_authority",
    ):
        assert result[key] == 0
    assert result["archive_writes"] == 1


@pytest.mark.parametrize(
    "corruption",
    ["root", "hash", "extra_name", "wake_revision", "paper_rows", "runtime", "policy"],
)
def test_predecessor_drift_blocks_before_staging(fake, monkeypatch, corruption):
    if corruption == "root":
        monkeypatch.setattr(predecessor, "ROOT_IDENTITY", (42, 999))
    elif corruption == "hash":
        fake.active.joinpath("activation.json").write_bytes(b"invalid")
    elif corruption == "extra_name":
        fake.active.joinpath("unexpected").touch()
    elif corruption == "wake_revision":
        with sqlite3.connect(fake.active / "wake.sqlite") as c:
            c.execute("UPDATE wakes SET revision=1")
        predecessor.FILE_HASHES["wake.sqlite"] = material.digest(
            (fake.active / "wake.sqlite").read_bytes()
        )
    elif corruption == "paper_rows":
        with sqlite3.connect(fake.active / "paper.sqlite") as c:
            c.execute("UPDATE metadata SET value='999' WHERE key='starting_cash'")
        predecessor.FILE_HASHES["paper.sqlite"] = material.digest(
            (fake.active / "paper.sqlite").read_bytes()
        )
    elif corruption == "runtime":
        fake.runtime_facts["wake_launcher_sha256"] = "c" * 64
    else:
        fake.policies[str(fake.active / "wake.sqlite")] = 0x1F01FF
    code, result = operator.run("plan", fake.path)
    assert code == 3 and result["status"] == "BLOCKED"
    assert all(result[key] == 0 for key in operator.ZERO_EFFECTS)
    assert not fake.stage.exists()


@pytest.mark.parametrize(
    "changed",
    [
        "only_date",
        "created_at",
        "proposal",
        "order",
        "store",
        "binding",
        "runtime",
        "oauth",
        "buffers",
        "cash",
    ],
)
def test_fresh_material_requires_coherent_reviewed_fields(fake, changed):
    act, host = fake.new, fake.material.host
    if changed == "only_date":
        act = replace(fake.old, target_session_date=fake.new.target_session_date)
        host = reviewed(act, fake.runtime).host
    elif changed == "created_at":
        act = replace(
            act, created_at=OLD, proposal=replace(act.proposal, created_at=OLD)
        )
    elif changed == "proposal":
        act = replace(act, proposal=fake.old.proposal)
    elif changed == "order":
        act = replace(act, local_order_id=fake.old.local_order_id)
    elif changed == "store":
        act = replace(act, store_identity=fake.old.store_identity)
    elif changed == "binding":
        host = replace(host, activation_sha256="c" * 64)
    elif changed == "runtime":
        act = replace(act, source_head="c" * 40)
    elif changed == "oauth":
        host = replace(host, oauth_valid_until=NOW)
    elif changed == "buffers":
        act = replace(act, opening_buffer=timedelta(minutes=6))
    else:
        act = replace(act, starting_cash=Decimal("20000"))
    if changed != "binding":
        host = replace(
            host,
            activation_sha256=material.digest(act.to_json().encode()),
            store_identity=act.store_identity,
        )
    raw = material.canonical(
        {
            "schema": material.MATERIAL_SCHEMA,
            "activation": act.to_json(),
            "host_binding": host.to_json(),
        }
    ).encode()
    fake.path.write_bytes(raw)
    assert operator.run("plan", fake.path)[0] == 3


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"null",
        b"[]",
        b'{"schema":1}',
        b"\xff",
        pytest.param(b" " * 262145, id="oversized"),
    ],
)
def test_bad_material_is_closed(fake, raw):
    fake.path.write_bytes(raw)
    assert operator.run("plan", fake.path)[0] == 3


def test_material_canonicalization_and_exact_hash(fake):
    assert material.Material.parse(fake.material.raw) == fake.material
    with pytest.raises(ValueError):
        material.Material.parse(fake.material.raw + b"\n")
    data = json.loads(fake.material.raw)
    with pytest.raises(ValueError):
        material.Material.parse(json.dumps(data, indent=2).encode())


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 10, 8, 13, 35, tzinfo=UTC),
        datetime(2026, 10, 8, 13, 36, tzinfo=UTC),
        datetime(2026, 10, 9, 12, tzinfo=UTC),
    ],
)
def test_strict_future_window(fake, monkeypatch, instant):
    monkeypatch.setattr(operator, "utc_now", lambda: instant)
    assert operator.run("plan", fake.path)[0] == 3


def test_nonexpired_predecessor_is_independently_rejected(fake, monkeypatch):
    monkeypatch.setattr(operator, "utc_now", lambda: OLD)
    assert operator.run("plan", fake.path)[0] == 3


def test_expiry_during_staging_prevents_archive(fake, monkeypatch):
    sha = plan_hash(fake)
    original = native.WindowsEdges.stage

    def late(self, reviewed_material):
        original(self, reviewed_material)
        monkeypatch.setattr(operator, "utc_now", lambda: NOW + timedelta(hours=2))

    monkeypatch.setattr(native.WindowsEdges, "stage", late)
    code, result = operator.run("execute-once", fake.path, sha)
    assert code == 4 and result["archive_writes"] == 0
    assert (
        fake.active.joinpath("activation.json").read_bytes()
        == fake.old.to_json().encode()
    )


@pytest.mark.parametrize(
    "phase",
    [
        "stage",
        "stage_verify",
        "archive",
        "archive_verify",
        "publish",
        "active_verify",
        "final_namespace",
        "guard_close",
    ],
)
def test_ambiguity_preserves_evidence_without_retry_or_cleanup(
    fake, monkeypatch, phase
):
    sha = plan_hash(fake)

    def fail(*a, **kw):
        raise RuntimeError("PRIVATE_RAW_NATIVE_MESSAGE")

    if phase in ("stage", "archive", "publish"):
        monkeypatch.setattr(native.WindowsEdges, phase, fail)
    elif phase.endswith("verify"):
        original = generation.observe_generation
        target = {
            "stage_verify": generation.STAGE,
            "archive_verify": generation.ARCHIVE,
            "active_verify": generation.ACTIVE,
        }[phase]

        def observe(root, *a, **kw):
            if root == target:
                fail()
            return original(root, *a, **kw)

        monkeypatch.setattr(generation, "observe_generation", observe)
    elif phase == "final_namespace":
        monkeypatch.setattr(namespace, "final_namespace", fail)
    else:

        @contextmanager
        def guard(self):
            yield
            fail()

        monkeypatch.setattr(native.WindowsEdges, "publication_guard", guard)
    code, result = operator.run("execute-once", fake.path, sha)
    assert code == 4 and result["status"] == "INDETERMINATE"
    assert "PRIVATE" not in json.dumps(result)
    assert fake.active.exists() or fake.archive.exists()
    assert len([x for x in fake.events if isinstance(x, tuple)]) <= 2
    # Subsequent invocation always fails closed on occupied fixed namespace.
    if fake.stage.exists() or fake.archive.exists():
        assert operator.run("execute-once", fake.path, sha)[0] == 3


def test_staging_does_not_modify_active_and_readback_detects_mixed_generation(fake):
    before = {p.name: p.read_bytes() for p in fake.active.iterdir()}
    native.WindowsEdges(dict(operator.ZERO_EFFECTS)).stage(fake.material)
    assert {p.name: p.read_bytes() for p in fake.active.iterdir()} == before
    assert (
        generation.observe_generation(str(fake.stage), fake.material)["wake_revision"]
        == 0
    )
    fake.stage.joinpath("host-binding.json").write_bytes(before["host-binding.json"])
    with pytest.raises(ValueError):
        generation.observe_generation(str(fake.stage), fake.material)


def test_authorization_pause_revalidates_material(fake, monkeypatch):
    sha = plan_hash(fake)
    monkeypatch.setattr(
        operator,
        "authorize",
        lambda _: fake.path.write_bytes(fake.material.raw + b"\n"),
    )
    code, result = operator.run("execute-once", fake.path, sha)
    assert code == 3 and result["publication_writes"] == 0


def test_bad_review_hash_never_authorizes(fake):
    assert operator.run("execute-once", fake.path, "a" * 64)[0] == 3
    assert not fake.events


def test_fresh_import_closure_is_provider_scheduler_execution_free(tmp_path):
    # Child imports source only; no operator invocation or production observation.
    source = (
        "import sys,json;sys.path.insert(0,sys.argv[1]);"
        "import trading_bot.arch133_reprovision.operator;"
        "print(json.dumps(sorted(sys.modules)))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", source, str(ROOT / "src")],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    imported = json.loads(result.stdout)
    for name in imported:
        assert not name.startswith(
            (
                "trading_bot.robinhood_mcp",
                "trading_bot.arch133_verifier.operator",
                "trading_bot.arch133_diagnostic",
                "trading_bot.arch133_publication",
                "trading_bot.review_paper.unattended_host",
                "trading_bot.review_paper.unattended_execution",
                "trading_bot.arch133_scheduler_installation.operator",
                "trading_bot.arch133_reprovision.native",
            )
        )


def test_consumed_sources_unchanged_and_new_topology_admitted():
    from scripts import checkpoint_runner as runner

    assert runner._arch133_reprovision_authority_check(ROOT) == ()
    spec = runner._checkpoint_specs()["arch133-robinhood-fresh-activation-reprovision"]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert runner.ACTIVE_CI_CHECKPOINTS[-5:-3] == (
        spec.name,
        "arch133-robinhood-reprovision-admission-diagnostic",
    )


def test_native_rename_uses_held_objects_and_never_replaces(fake, monkeypatch):
    calls = []

    class Function:
        def __init__(self, name):
            self.name = name

        def __call__(self, *args):
            calls.append((self.name, args))
            return 91 if self.name == "CreateFileW" else 1

    class Kernel:
        def __getattr__(self, name):
            return Function(name)

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: Kernel())
    # Restore only the source-owned implementation replaced by the fake fixture.
    import importlib.util

    spec = importlib.util.spec_from_file_location("q_native_contract", native.__file__)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    handle = fresh._open_rename_root(fresh.ACTIVE)
    assert handle == 91
    assert calls[0][1][1:6] == (0xF0081, 3, None, 3, 0x02200000)
    fresh._rename(handle, 92, fresh.ACTIVE, fresh.ARCHIVE)
    name, args = calls[-1]
    assert name == "SetFileInformationByHandle"
    assert args[:2] == (91, 3)
    assert args[2].raw[0] == 0  # ReplaceIfExists is always FALSE.
    with pytest.raises(ValueError):
        fresh._rename(handle, 92, fresh.ACTIVE, r"F:\arbitrary")
    assert len(calls) == 2


def test_retained_generation_byte_identity_is_independent(fake):
    plan, _, _ = operator.make_plan(fake.path)
    native.WindowsEdges(dict(operator.ZERO_EFFECTS)).stage(fake.material)
    staged = generation.observe_generation(generation.STAGE, fake.material)
    assert staged["root_identity"] != plan["predecessor"]["root_identity"]
    fake.stage.joinpath("wake.sqlite").write_bytes(
        fake.active.joinpath("wake.sqlite").read_bytes()
    )
    with pytest.raises(ValueError):
        generation.observe_generation(generation.STAGE, fake.material)


@pytest.mark.parametrize("phase", ["before_archive", "after_archive"])
def test_expiry_at_publication_never_publishes(fake, monkeypatch, phase):
    sha = plan_hash(fake)
    original = generation.observe_generation

    def observe(root, *args, **kwargs):
        result = original(root, *args, **kwargs)
        if (phase == "before_archive" and root == generation.STAGE) or (
            phase == "after_archive" and root == generation.ARCHIVE
        ):
            monkeypatch.setattr(operator, "utc_now", lambda: NOW + timedelta(hours=2))
        return result

    monkeypatch.setattr(generation, "observe_generation", observe)
    code, result = operator.run("execute-once", fake.path, sha)
    assert code == 4 and result["publication_writes"] == 4
    assert fake.stage.exists()
    if phase == "after_archive":
        assert fake.archive.exists() and not fake.active.exists()
    else:
        assert fake.active.exists() and not fake.archive.exists()


@pytest.mark.parametrize(
    "relative",
    [
        "src/trading_bot/arch133_reprovision/operator.py",
        "src/trading_bot/arch133_reprovision/native.py",
        "src/trading_bot/arch133_reprovision/material.py",
        "scripts/run_arch133_fresh_activation_reprovision.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ],
)
def test_new_checkpoint_rejects_source_and_topology_drift(
    tmp_path, monkeypatch, relative
):
    from scripts import checkpoint_runner as runner

    # Isolate this checkpoint's local pin tests; predecessor pins have their own
    # existing focused drift matrix and remain chained in the real source gate.
    monkeypatch.setattr(
        runner, "_arch133_scheduler_installation_authority_check", lambda root: ()
    )
    for path in (
        *runner.ARCH133_REPROVISION_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / path).read_bytes())
    assert runner._arch133_reprovision_authority_check(tmp_path) == ()
    path = tmp_path / relative
    text = path.read_text(encoding="utf-8-sig")
    if relative == "scripts/checkpoint_runner.py":
        text = text.replace(
            'description="Architecture 133-Q source-only fresh activation reprovision"',
            'description="drift"',
        )
    elif relative.endswith(".yml"):
        text = text.replace(
            "              arch133-robinhood-fresh-activation-reprovision",
            "              # drift",
        )
    else:
        text += "\nDRIFT = True\n"
    path.write_text(text, encoding="utf-8")
    assert runner._arch133_reprovision_authority_check(tmp_path)


def test_complete_staging_guard_precedes_any_archive_mutation(fake):
    plan, reviewed_material, _ = operator.make_plan(fake.path)
    counters = dict(operator.ZERO_EFFECTS)
    edges = native.WindowsEdges(counters)
    edges.stage(reviewed_material)
    with namespace.staging_guard(), edges.publication_guard():
        _, facts = predecessor.observe_admission()
        assert facts == plan["predecessor"]
        assert generation.observe_generation(generation.STAGE, reviewed_material)[
            "activation_id"
        ] == str(fake.new.activation_id)
        assert counters["archive_writes"] == 0


def test_windows_material_stat_transport_binds_content(fake):
    # Windows lstat/fstat creation-time fields can differ even on an unchanged
    # newly closed file. The canonical byte hash and stable content facts govern.
    assert material.read_material(fake.path).sha256 == material.digest(
        fake.path.read_bytes()
    )


def test_source_inventory_cannot_drop_native_capability(tmp_path, monkeypatch):
    from scripts import checkpoint_runner as runner

    monkeypatch.setattr(
        runner, "_arch133_scheduler_installation_authority_check", lambda root: ()
    )
    for relative in (
        *runner.ARCH133_REPROVISION_SOURCES,
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    path = tmp_path / "scripts/checkpoint_runner.py"
    source = path.read_text().replace(
        '    "src/trading_bot/arch133_reprovision/native.py",', "", 1
    )
    path.write_text(source)
    assert (
        "133-Q source inventory drift"
        in runner._arch133_reprovision_authority_check(tmp_path)
    )
