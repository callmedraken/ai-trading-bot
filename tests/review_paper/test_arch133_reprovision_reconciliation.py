"""133-V fake/temp reconciliation qualification; real namespaces are forbidden."""

import ast
import ctypes
import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.arch133_acl import read_only
from trading_bot.arch133_reprovision import generation, namespace, reads
from trading_bot.arch133_reprovision_reconciliation import operator
from trading_bot.arch133_verifier import binding, file_policy

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-reprovision-indeterminate-reconciliation"
EFFECTS = (
    "credential_reads",
    "credential_writes",
    "provider_calls",
    "scheduler_reads",
    "scheduler_writes",
    "publication_writes",
    "archive_writes",
    "paper_mutations",
    "state_mutations",
    "acl_mutations",
    "wake_delegations",
    "execution_delegations",
    "consumed_wake_authority",
    "broker_effects",
    "manual_task_starts",
)


@pytest.fixture(autouse=True)
def deny_real_native(monkeypatch):
    attempts = []

    def deny(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("real native observation forbidden")

    monkeypatch.setattr(ctypes, "WinDLL", deny, raising=False)
    yield
    assert not attempts, "a real native boundary was attempted"


def blocked(result):
    code, evidence = result
    assert code == 3
    assert evidence == {
        "schema": operator.RESULT_SCHEMA,
        "status": "BLOCKED",
        "disposition": "RECONCILIATION_UNRESOLVED",
        **dict.fromkeys(EFFECTS, 0),
    }


@pytest.fixture
def fake(tmp_path, monkeypatch):
    active, archive, staging = (tmp_path / n for n in ("active", "archive", "staging"))
    stage = staging / "generation"
    active.mkdir()
    stage.mkdir(parents=True)
    for root in (active, stage):
        for name in reads.FINAL_NAMES:
            (root / name).write_bytes((root.name + name).encode())
    for name, value in (
        ("ACTIVE", active),
        ("ARCHIVE", archive),
        ("STAGING_PARENT", staging),
        ("STAGE", stage),
    ):
        monkeypatch.setattr(generation, name, str(value))
    f = SimpleNamespace(
        active=active,
        archive=archive,
        staging=staging,
        stage=stage,
        events=[],
        material=SimpleNamespace(
            raw=b"fixed material", sha256=operator.MATERIAL_SHA256
        ),
        security={},
        policies={},
    )
    monkeypatch.setattr(operator, "observe_runtime", lambda: {"source_head": "a" * 40})
    monkeypatch.setattr(operator, "administrator_sid", lambda: f.events.append("admin"))
    monkeypatch.setattr(operator, "read_material", lambda p: f.material)

    def opening(path, **kwargs):
        f.events.append(("open", path))
        if not Path(path).exists():
            raise read_only.RootOpenError(2)
        return path

    def closing(handle):
        f.events.append(("close", handle))

    def security(handle, path):
        predecessor = path in (str(active), str(archive))
        obs = read_only.DirectoryObservation(
            read_only.ADMINISTRATORS_SID,
            True,
            read_only.ROOT_ACES if path == str(stage) else read_only.ADMIN_ACES,
            operator.ROOT_IDENTITY
            if predecessor
            else (operator.ROOT_IDENTITY[0], Path(path).stat().st_ino),
        )
        return f.security.get(path, (obs, "e" * 64))

    def names(handle):
        found = tuple(sorted(p.name for p in Path(handle).iterdir()))
        if found != reads.FINAL_NAMES:
            raise ValueError("invalid namespace")
        return tuple(
            (n, i + (100 if handle == str(stage) else 0))
            for n, i in operator.PREDECESSOR_NAMESPACE
        )

    def snapshot(handle, root, name):
        index = dict(names(root))[name]
        sha = (
            operator.FILE_HASHES[name]
            if root != str(stage)
            else hashlib.sha256(Path(handle).read_bytes()).hexdigest()
        )
        return (operator.ROOT_IDENTITY[0], index), sha

    def policy(handle):
        name = Path(handle).name
        rights = (
            0x120089
            if Path(handle).parent != stage
            or name in ("activation.json", "host-binding.json")
            else 0x13019F
        )
        return f.policies.get(
            handle,
            file_policy.FilePolicy(
                read_only.ADMINISTRATORS_SID,
                True,
                read_only.ADMIN_ACES + ((read_only.TRADING_SID, rights, 0, 0),),
                "f" * 64,
            ),
        )

    def fresh(root, material, **kwargs):
        assert root == str(stage) and material is f.material and not kwargs
        f.events.append("fresh")
        return {
            "root_identity": list(security(root, root)[0].identity),
            "root_security_sha256": security(root, root)[1],
            "files": {
                n: {
                    "identity": list(snapshot(str(stage / n), root, n)[0]),
                    "sha256": snapshot(str(stage / n), root, n)[1],
                    "policy": asdict(policy(str(stage / n))),
                }
                for n, _ in names(root)
            },
        }

    monkeypatch.setattr(read_only, "open_directory", opening)
    monkeypatch.setattr(read_only, "close_handle", closing)
    monkeypatch.setattr(read_only, "inspect_directory_security", security)
    monkeypatch.setattr(reads, "namespace", names)
    monkeypatch.setattr(
        reads, "open_generation_file", lambda root, n: str(Path(root) / n)
    )
    monkeypatch.setattr(reads, "file_snapshot", snapshot)
    monkeypatch.setattr(file_policy, "observe_file_policy", policy)
    monkeypatch.setattr(generation, "observe_generation", fresh)

    @contextmanager
    def parents():
        f.events.append("parents-enter")
        yield {"fixed": "parents"}
        f.events.append("parents-reobserve")

    monkeypatch.setattr(namespace, "parent_guard", parents)
    return f


@pytest.mark.parametrize("committed", [False, True])
def test_exact_two_pass_dispositions_hold_until_reobservation_and_close(
    fake, committed
):
    if committed:
        fake.active.rename(fake.archive)  # temp fixture only
    code, evidence = operator.run()
    assert code == 0 and evidence["status"] == "PASS"
    assert evidence["disposition"] == (
        "ARCHIVE_RENAME_COMMITTED" if committed else "ARCHIVE_RENAME_NOT_COMMITTED"
    )
    assert evidence["predecessor_root"] == str(
        fake.archive if committed else fake.active
    )
    assert evidence["predecessor_namespace"] == operator.PREDECESSOR_NAMESPACE
    assert evidence["material_sha256"] == operator.MATERIAL_SHA256
    assert evidence["reviewed_u_plan_sha256"] == operator.REVIEWED_U_PLAN_SHA256
    assert all(type(evidence[k]) is int and evidence[k] == 0 for k in EFFECTS)
    assert fake.events.count("fresh") == 2
    assert fake.events[-1] == "parents-reobserve"
    assert any(e[0] == "close" for e in fake.events if isinstance(e, tuple))


@pytest.mark.parametrize("both", [True, False])
def test_rejects_both_present_and_both_absent(fake, both):
    if both:
        fake.archive.mkdir()
    else:
        fake.active.rename(fake.active.with_name("not-an-observed-root"))
    blocked(operator.run())


@pytest.mark.parametrize("target", ["stage", "staging", "file", "extra"])
def test_rejects_missing_or_mixed_stage(fake, target):
    if target == "stage":
        fake.stage.rename(fake.stage.with_name("missing"))
    elif target == "staging":
        fake.staging.rename(fake.staging.with_name("missing"))
    elif target == "file":
        (fake.stage / "wake.sqlite").unlink()
    else:
        (fake.staging / "extra").mkdir()
    blocked(operator.run())


@pytest.mark.parametrize("committed", [False, True])
@pytest.mark.parametrize(
    "change",
    [
        "identity",
        "volume",
        "namespace",
        "hash",
        "root_policy",
        "file_policy",
        "filesystem",
        "reparse",
    ],
)
def test_predecessor_identity_hash_and_sealed_policy_drift(
    fake, monkeypatch, committed, change
):
    root = fake.archive if committed else fake.active
    if committed:
        fake.active.rename(fake.archive)
    obs, digest = read_only.inspect_directory_security(str(root), str(root))
    if change in ("identity", "volume", "root_policy", "filesystem", "reparse"):
        values = {
            "identity": {"identity": (obs.identity[0], 123)},
            "volume": {"identity": (123, obs.identity[1])},
            "root_policy": {"aces": read_only.ROOT_ACES},
            "filesystem": {"filesystem": "FAT"},
            "reparse": {"reparse": True},
        }
        fake.security[str(root)] = (replace(obs, **values[change]), digest)
    elif change == "namespace":
        original = reads.namespace
        monkeypatch.setattr(
            reads,
            "namespace",
            lambda h: (
                tuple((n, i + 1) for n, i in original(h))
                if h == str(root)
                else original(h)
            ),
        )
    elif change == "hash":
        original = reads.file_snapshot
        monkeypatch.setattr(
            reads,
            "file_snapshot",
            lambda h, r, n: (
                (original(h, r, n)[0], "0" * 64)
                if r == str(root)
                else original(h, r, n)
            ),
        )
    else:
        h = str(root / "wake.sqlite")
        fake.policies[h] = replace(file_policy.observe_file_policy(h), protected=False)
    blocked(operator.run())


@pytest.mark.parametrize(
    "phase",
    [
        "runtime",
        "admin",
        "material",
        "parent",
        "stage",
        "root_close",
        "file_close",
        "parent_close",
        "absent_error",
    ],
)
def test_failures_are_sanitized_and_effect_free(fake, monkeypatch, phase):
    def fail(*a, **kw):
        raise RuntimeError("PRIVATE native error or credential text")

    if phase == "runtime":
        monkeypatch.setattr(operator, "observe_runtime", fail)
    elif phase == "admin":
        monkeypatch.setattr(operator, "administrator_sid", fail)
    elif phase == "material":
        monkeypatch.setattr(operator, "read_material", fail)
    elif phase == "stage":
        monkeypatch.setattr(generation, "observe_generation", fail)
    elif phase in ("parent", "parent_close"):

        @contextmanager
        def parents():
            if phase == "parent":
                fail()
            yield {}
            fail()

        monkeypatch.setattr(namespace, "parent_guard", parents)
    elif phase == "absent_error":
        original = read_only.open_directory

        def opening(path, **kw):
            if path == str(fake.archive):
                raise read_only.RootOpenError(5)
            return original(path, **kw)

        monkeypatch.setattr(read_only, "open_directory", opening)
    else:
        original = read_only.close_handle

        def close(handle):
            original(handle)
            if (phase == "file_close") == (Path(handle).suffix != ""):
                fail()

        monkeypatch.setattr(read_only, "close_handle", close)
    blocked(operator.run())


@pytest.mark.parametrize(
    "change",
    [
        "runtime",
        "material",
        "stage",
        "namespace",
        "security",
        "stage_security",
        "file",
        "policy",
        "staging_security",
        "staging_children",
        "absent_present",
    ],
)
def test_final_reobservation_drift_fails_closed(fake, monkeypatch, change):
    original = generation.observe_generation

    def fresh(*args, **kwargs):
        result = original(*args, **kwargs)
        if fake.events.count("fresh") == 1:
            if change == "runtime":
                monkeypatch.setattr(
                    operator, "observe_runtime", lambda: {"drift": True}
                )
            elif change == "material":
                monkeypatch.setattr(
                    operator, "read_material", lambda p: SimpleNamespace(raw=b"changed")
                )
            elif change == "stage":
                result["root_identity"] = [1, 2]
            elif change == "stage_security":
                result["root_security_sha256"] = "drift"
            elif change == "namespace":
                (fake.active / "extra").write_bytes(b"drift")
            elif change in ("security", "staging_security"):
                path = str(fake.active if change == "security" else fake.staging)
                observation, _ = read_only.inspect_directory_security(path, path)
                fake.security[path] = (observation, "drift")
            elif change == "file":
                saved = reads.file_snapshot
                monkeypatch.setattr(
                    reads,
                    "file_snapshot",
                    lambda h, r, n: (
                        (saved(h, r, n)[0], "0" * 64)
                        if r == str(fake.active)
                        else saved(h, r, n)
                    ),
                )
            elif change == "policy":
                h = str(fake.active / "paper.sqlite")
                fake.policies[h] = replace(
                    file_policy.observe_file_policy(h), security_sha256="drift"
                )
            elif change == "staging_children":
                (fake.staging / "extra").mkdir()
            else:
                fake.archive.mkdir()
        return result

    monkeypatch.setattr(generation, "observe_generation", fresh)
    blocked(operator.run())


def test_material_hash_is_exact(fake):
    fake.material.sha256 = "0" * 64
    blocked(operator.run())


def test_read_only_parent_guard_is_reused_and_reobserved(monkeypatch):
    # A separate fake-native guard exercises the actual corrected T implementation.
    events = []
    monkeypatch.setattr(read_only, "open_directory", lambda p: p)
    monkeypatch.setattr(
        read_only, "close_handle", lambda p: events.append(("close", p))
    )

    def observe(h, p):
        events.append(("observe", p))
        aces = (
            read_only.ADMIN_ACES + (("S-1-5-11", 0x10000000, 0, 0x0B),)
            if p == namespace.PARENTS[0]
            else read_only.ADMIN_ACES
        )
        return read_only.DirectoryObservation(
            read_only.ADMINISTRATORS_SID, True, aces, (1, 2)
        ), "x"

    monkeypatch.setattr(read_only, "inspect_directory_security", observe)
    with namespace.parent_guard():
        pass
    assert events[:2] == [("observe", p) for p in namespace.PARENTS]
    assert events[2:4] == events[:2]
    original = observe
    calls = 0

    def drift(h, p):
        nonlocal calls
        calls += 1
        obs, sha = original(h, p)
        return obs, "changed" if calls > 2 else sha

    monkeypatch.setattr(read_only, "inspect_directory_security", drift)
    with pytest.raises(ValueError):
        with namespace.parent_guard():
            pass


def test_exact_frozen_bindings():
    assert operator.SOURCE_ROOT == Path(
        r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133v"
    )
    assert operator.SOURCE_BRANCH == "feature/robinhood-unattended-review-paper-133v"
    assert operator.U_ROOT == Path(
        r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133u"
    )
    assert operator.U_BRANCH == "feature/robinhood-unattended-review-paper-133u"
    assert operator.U_HEAD == "49686d7f61717b9ee7452cee633d23b0c7db873e"
    assert operator.U_TREE == "12b430743786ba6650aa720fc27a6d9b0d95ea74"
    assert operator.MATERIAL_PATH == Path(
        r"F:\AI\temp\arch133q\fresh-material-2026-10-09.json"
    )
    assert (
        operator.MATERIAL_SHA256
        == "7b55cb89e94f09a8271a7c28fad9737c0ddb1ef94aba719968ea2820ea24a686"
    )
    assert (
        operator.REVIEWED_U_PLAN_SHA256
        == "a223d8fa606da9cc129d5d095c6c94ec6be42f350da0bec7fe4825fe6ef8bb81"
    )
    assert operator.ROOT_IDENTITY == (1855336320, 1407374886183770)
    assert operator.PREDECESSOR_NAMESPACE == (
        ("activation.json", 1407374886191165),
        ("host-binding.json", 562949956059198),
        ("paper.sqlite", 562949956054077),
        ("wake.sqlite", 1125899909477979),
    )
    assert tuple(operator.ZERO_EFFECTS) == EFFECTS
    assert binding.PRODUCTION_PYTHON == Path(r"F:\AITradingBot\runtime\python.exe")
    assert binding.PRODUCTION_PYTHON_VERSION == "3.14.3"
    assert (
        binding.PRODUCTION_PYTHON_SHA256
        == "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
    )


@pytest.mark.parametrize(
    "drift",
    [
        None,
        "head",
        "tree",
        "branch",
        "root",
        "origin",
        "dirty",
        "upstream",
        "remote_head",
        "remote_tree",
    ],
)
def test_checkout_admission_binds_every_source_fact(tmp_path, monkeypatch, drift):
    branch = operator.SOURCE_BRANCH
    ref = "refs/remotes/origin/" + branch
    responses = {
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "HEAD^{tree}"): "b" * 40,
        ("rev-parse", "--show-toplevel"): str(tmp_path),
        ("branch", "--show-current"): branch,
        ("remote", "get-url", "origin"): operator.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "origin/"
        + branch,
        ("rev-parse", ref): "a" * 40,
        ("rev-parse", ref + "^{tree}"): "b" * 40,
    }
    keys = dict(
        zip(
            (
                "head",
                "tree",
                "root",
                "branch",
                "origin",
                "dirty",
                "upstream",
                "remote_head",
                "remote_tree",
            ),
            responses,
            strict=True,
        )
    )
    if drift:
        responses[keys[drift]] = "?? drift" if drift == "dirty" else "0" * 40
    monkeypatch.setattr(operator, "_git", lambda r, *args: responses[args])
    if drift:
        with pytest.raises((ValueError, OSError)):
            operator.require_checkout(tmp_path, branch)
    else:
        assert operator.require_checkout(tmp_path, branch) == ("a" * 40, "b" * 40)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    executable = tmp_path / "python.exe"
    executable.write_bytes(b"fake interpreter")
    monkeypatch.setattr(operator, "SOURCE_ROOT", ROOT)
    monkeypatch.setattr(
        operator, "LAUNCHER", ROOT / "scripts/run_arch133_reprovision_reconciliation.py"
    )
    monkeypatch.setattr(operator, "NO_PYCACHE", tmp_path / "missing-cache")
    monkeypatch.setattr(binding, "PRODUCTION_PYTHON", executable)
    monkeypatch.setattr(
        binding,
        "PRODUCTION_PYTHON_SHA256",
        hashlib.sha256(executable.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=1))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(sys, "pycache_prefix", str(operator.NO_PYCACHE))
    monkeypatch.setattr(sys, "argv", [str(operator.LAUNCHER)])
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "version_info", (3, 14, 3))

    def source(root, branch):
        return (
            (operator.U_HEAD, operator.U_TREE)
            if root == operator.U_ROOT
            else ("a" * 40, "b" * 40)
        )

    monkeypatch.setattr(operator, "require_checkout", source)
    return executable


@pytest.mark.parametrize(
    "drift",
    [
        None,
        "platform",
        "isolated",
        "bytecode",
        "prefix",
        "cache",
        "launcher",
        "executable",
        "version",
        "hash",
        "u_head",
        "u_tree",
        "source",
    ],
)
def test_exact_runtime_and_consumed_u_checkout(runtime, monkeypatch, drift):
    if drift == "platform":
        monkeypatch.setattr(sys, "platform", "other")
    elif drift == "isolated":
        monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=0))
    elif drift == "bytecode":
        monkeypatch.setattr(sys, "dont_write_bytecode", False)
    elif drift == "prefix":
        monkeypatch.setattr(sys, "pycache_prefix", "wrong")
    elif drift == "cache":
        operator.NO_PYCACHE.mkdir()
    elif drift == "launcher":
        monkeypatch.setattr(sys, "argv", [str(runtime)])
    elif drift == "executable":
        monkeypatch.setattr(sys, "executable", str(operator.LAUNCHER))
    elif drift == "version":
        monkeypatch.setattr(sys, "version_info", (3, 14, 2))
    elif drift == "hash":
        runtime.write_bytes(b"changed")
    elif drift == "source":
        monkeypatch.setattr(operator, "SOURCE_ROOT", runtime.parent)
    elif drift in ("u_head", "u_tree"):
        original = operator.require_checkout
        monkeypatch.setattr(
            operator,
            "require_checkout",
            lambda root, branch: (
                (
                    ("0" * 40, operator.U_TREE)
                    if drift == "u_head"
                    else (operator.U_HEAD, "0" * 40)
                )
                if root == operator.U_ROOT
                else original(root, branch)
            ),
        )
    if drift:
        with pytest.raises(ValueError):
            operator.observe_runtime()
    else:
        assert operator.observe_runtime()["u_source_head"] == operator.U_HEAD


def test_fresh_process_import_closure_excludes_effect_surfaces(tmp_path):
    probe = tmp_path / "closure.py"
    probe.write_text(
        "import sys, json\n"
        f"sys.path.insert(0, {str(ROOT / 'src')!r})\n"
        "import trading_bot.arch133_reprovision_reconciliation.operator\n"
        "print(json.dumps(sorted(sys.modules)))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(probe)],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    forbidden = (
        "trading_bot.arch133_reprovision.native",
        "trading_bot.arch133_reprovision.operator",
        "trading_bot.arch133_reprovision_corrected",
        "trading_bot.arch133_acl.primitive",
        "trading_bot.arch133_acl.root_policy_apply",
        "trading_bot.arch133_acl.recovery",
        "trading_bot.arch133_publication",
        "trading_bot.arch133_verifier.credentials",
        "trading_bot.arch133_verifier.operator",
        "trading_bot.arch133_scheduler_installation.operator",
        "trading_bot.robinhood_mcp",
        "trading_bot.review_paper.unattended_execution",
        "trading_bot.review_paper.unattended_host",
    )
    modules = json.loads(result.stdout)
    assert not [m for m in modules if m.startswith(forbidden)]
    assert "trading_bot.arch133_reprovision.generation" in modules
    # The accepted material closure includes this pure specification model.
    assert "trading_bot.arch133_verifier.scheduler" in modules


def test_authority_chains_u_and_has_exact_source_only_topology():
    assert runner._arch133_reprovision_reconciliation_authority_check(ROOT) == ()
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == operator.SOURCE_BRANCH
    assert runner.ACTIVE_CI_CHECKPOINTS[-6:-4] == (
        "arch133-robinhood-fresh-activation-reprovision-corrected",
        NAME,
    )
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 55


@pytest.mark.parametrize(
    "mutation",
    [
        "init",
        "operator",
        "launcher",
        "inventory",
        "registration",
        "active",
        "workflow",
        "u_chain",
    ],
)
def test_source_inventory_registration_order_workflow_fail_closed(
    tmp_path, monkeypatch, mutation
):
    # Local pin matrix uses a slim parsed runner fixture, never a complete runner copy.
    monkeypatch.setattr(
        runner,
        "_arch133_reprovision_corrected_authority_check",
        lambda r: ("U rejected",) if mutation == "u_chain" else (),
    )
    for relative in runner.ARCH133V_RECONCILIATION_SOURCES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    parsed = ast.parse((ROOT / "scripts/checkpoint_runner.py").read_text())
    nodes = [
        n
        for n in parsed.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id in ("ARCH133V_RECONCILIATION_SOURCES", "ACTIVE_CI_CHECKPOINTS")
    ]
    reg = next(
        n
        for n in ast.walk(parsed)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "CheckpointSpec"
        and any(
            k.arg == "name"
            and isinstance(k.value, ast.Constant)
            and k.value.value == NAME
            for k in n.keywords
        )
    )
    script = tmp_path / "scripts/checkpoint_runner.py"
    script.write_text(
        "\n".join(ast.unparse(n) for n in nodes)
        + "\nregistration = "
        + ast.unparse(reg)
        + "\n"
    )
    workflow = tmp_path / ".github/workflows/checkpoint-source-gates.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_bytes(
        (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_bytes()
    )
    if mutation != "u_chain":
        assert (
            runner._arch133_reprovision_reconciliation_authority_check(tmp_path) == ()
        )
    if mutation in ("init", "operator", "launcher"):
        path = (
            tmp_path
            / runner.ARCH133V_RECONCILIATION_SOURCES[
                ("init", "operator", "launcher").index(mutation)
            ]
        )
        path.write_text(path.read_text(encoding="utf-8-sig") + "\nDRIFT = True\n")
    elif mutation == "inventory":
        script.write_text(
            script.read_text().replace(
                "ARCH133V_RECONCILIATION_SOURCES", "MISSING_INVENTORY"
            )
        )
    elif mutation == "registration":
        script.write_text(
            script.read_text().replace("preflight=None", "preflight=effect")
        )
    elif mutation == "active":
        script.write_text(
            script.read_text().replace("ACTIVE_CI_CHECKPOINTS", "MISSING_ACTIVE")
        )
    elif mutation == "workflow":
        workflow.write_text(workflow.read_text().replace(NAME, "missing-checkpoint"))
    assert runner._arch133_reprovision_reconciliation_authority_check(tmp_path)


def test_launcher_and_cli_reject_overrides_with_zero_counters(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(sys, "argv", ["launcher", "--material-file", "arbitrary"])
    monkeypatch.setattr(operator, "run", lambda: pytest.fail("override admitted"))
    assert operator.main() == 3
    evidence = json.loads(capsys.readouterr().out)
    blocked((3, evidence))
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(ROOT / "scripts/run_arch133_reprovision_reconciliation.py"),
            "--override",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    blocked((result.returncode, json.loads(result.stdout)))
    assert result.stderr == ""


@pytest.mark.parametrize("corruption", [None, "activation", "wake", "paper", "policy"])
def test_accepted_stage_observer_checks_exact_material_and_stores(
    tmp_path, monkeypatch, corruption
):
    # Reuse the established inert U generation fixture instead of duplicating
    # predecessor setup. No operator plan/execute or real native edge is invoked.
    spec = importlib.util.spec_from_file_location(
        "v_temp_generation_fixture",
        ROOT
        / "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    f = fixture.fake.__wrapped__(tmp_path, monkeypatch)
    fixture.native.WindowsEdges(dict.fromkeys(EFFECTS, 0)).stage(f.material)
    if corruption == "activation":
        (f.stage / "activation.json").write_bytes(
            f.old_material.activation.to_json().encode()
        )
    elif corruption == "wake":
        (f.stage / "wake.sqlite").write_bytes((f.active / "wake.sqlite").read_bytes())
    elif corruption == "paper":
        with sqlite3.connect(f.stage / "paper.sqlite") as connection:
            connection.execute(
                "UPDATE metadata SET value = '1' WHERE key = 'starting_cash'"
            )
    elif corruption == "policy":
        f.policies[str(f.stage / "wake.sqlite")] = 0x120089
    if corruption:
        with pytest.raises((ValueError, RuntimeError)):
            generation.observe_generation(generation.STAGE, f.material)
    else:
        result = generation.observe_generation(generation.STAGE, f.material)
        assert result["activation_id"] == str(f.new.activation_id)
        assert result["wake_revision"] == 0


@pytest.mark.parametrize("status", [2, 3, 5, 32, 87])
def test_presence_only_classifies_explicit_not_found_as_absent(monkeypatch, status):
    calls = []

    def opening(path, **kwargs):
        calls.append((path, kwargs))
        raise read_only.RootOpenError(status)

    monkeypatch.setattr(read_only, "open_directory", opening)
    with ExitStack() as held:
        if status in (2, 3):
            assert operator.presence(generation.ACTIVE, held) is None
        else:
            with pytest.raises(read_only.RootOpenError):
                operator.presence(generation.ACTIVE, held)
        with pytest.raises(ValueError):
            operator.presence("unreviewed-root", held)
    assert calls == [(generation.ACTIVE, {})]


def test_reconciliation_does_not_readmit_a_scheduler_time_window(fake, monkeypatch):
    from trading_bot.arch133_reprovision import material

    def deny(*a, **kw):
        pytest.fail("execution time admission attempted")

    monkeypatch.setattr(material, "require_fresh", deny)
    monkeypatch.setattr(material, "require_stale", deny)
    assert operator.run()[0] == 0
