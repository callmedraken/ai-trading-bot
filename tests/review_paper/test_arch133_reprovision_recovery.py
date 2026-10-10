"""133-W fake/temp qualification; no production observation or execution."""

import ast
import builtins
import ctypes
import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import checkpoint_runner as runner
from trading_bot.arch133_acl import read_only
from trading_bot.arch133_reprovision import generation, namespace, reads
from trading_bot.arch133_reprovision.material import require_fresh
from trading_bot.arch133_reprovision_recovery import admission, native, operator
from trading_bot.arch133_verifier import binding

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-reprovision-sealed-predecessor-recovery"


@pytest.fixture(autouse=True)
def deny_real_native(monkeypatch):
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda *a, **kw: pytest.fail("real native edge"),
        raising=False,
    )


@pytest.fixture
def fake(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "w_temp_fixture",
        ROOT
        / "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    f = fixture.fake.__wrapped__(tmp_path, monkeypatch)
    # Fixture construction only, under pytest's external temporary root. W itself
    # has no stage/reseal method or ACL/database writer.
    fixture.native.WindowsEdges(dict(operator.ZERO_EFFECTS)).stage(f.material)
    f.policies[str(f.active)] = None
    for name in reads.FINAL_NAMES:
        f.policies[str(f.active / name)] = 0x120089
    monkeypatch.setattr(admission, "MATERIAL_PATH", f.path)
    monkeypatch.setattr(admission, "MATERIAL_SHA256", f.material.sha256)
    monkeypatch.setattr(admission, "observe_runtime", lambda: dict(f.runtime_facts))
    monkeypatch.setattr(admission, "administrator_sid", lambda: None)
    monkeypatch.setattr(operator, "utc_now", lambda: fixture.NOW)
    monkeypatch.setattr(
        operator, "authorize", lambda sha: f.events.append("authorized")
    )
    monkeypatch.setattr(admission, "ROOT_IDENTITY", (42, f.active.stat().st_ino))
    monkeypatch.setattr(admission, "FILE_HASHES", fixture.predecessor.FILE_HASHES)
    monkeypatch.setattr(
        admission, "PREDECESSOR_NAMESPACE", reads.namespace(str(f.active))
    )
    monkeypatch.setattr(admission, "SEALED_SECURITY_SHA256", "e" * 64)
    monkeypatch.setattr(
        admission, "STAGING_PARENT_IDENTITY", (42, f.stage.parent.stat().st_ino)
    )
    monkeypatch.setattr(admission, "STAGING_PARENT_SECURITY_SHA256", "e" * 64)
    fresh = generation.observe_generation(str(f.stage), f.material)
    for key, value in (
        ("STAGE_IDENTITY", tuple(fresh["root_identity"])),
        ("STAGE_SECURITY_SHA256", fresh["root_security_sha256"]),
        (
            "STAGE_FILES",
            {n: (v["identity"][1], v["sha256"]) for n, v in fresh["files"].items()},
        ),
        ("STAGE_STATE_SHA256", fresh["state_sha256"]),
        ("STAGE_PAPER_SHA256", fresh["paper_predecessor_sha256"]),
        ("STAGE_ACTIVATION_ID", fresh["activation_id"]),
        ("STAGE_WAKE_ID", fresh["wake_id"]),
    ):
        monkeypatch.setattr(admission, key, value)

    def presence(path, held):
        if not Path(path).exists():
            return None
        return str(path)

    monkeypatch.setattr(admission, "presence", presence)
    for key in ("ACTIVE", "ARCHIVE", "STAGE"):
        monkeypatch.setattr(native, key, getattr(generation, key))
    monkeypatch.setattr(native, "_open_rename_root", lambda root: root)
    monkeypatch.setattr(native, "_rename", fixture.native._rename)
    security = read_only.inspect_directory_security

    def observed_security(handle, path):
        if path == namespace.PARENTS[1]:
            return read_only.DirectoryObservation(
                read_only.ADMINISTRATORS_SID, True, read_only.ADMIN_ACES, (42, 99)
            ), "g" * 64
        return security(handle, path)

    monkeypatch.setattr(read_only, "inspect_directory_security", observed_security)

    @contextmanager
    def parents():
        yield {
            namespace.PARENTS[1]: {"identity": [42, 99], "security_sha256": "g" * 64}
        }

    monkeypatch.setattr(namespace, "parent_guard", parents)
    f.now = fixture.NOW
    f.fresh = fresh

    def final_namespace():
        assert not list(f.stage.parent.iterdir())
        return {
            generation.STAGING_PARENT: {
                "observation": {"identity": admission.STAGING_PARENT_IDENTITY},
                "security_sha256": "e" * 64,
            }
        }

    monkeypatch.setattr(namespace, "final_namespace", final_namespace)
    return f


def sha(fake):
    return operator.plan_hash(operator.make_plan()[0])


def assert_failure(result, attempted=False, published=False):
    code, evidence = result
    assert code == (4 if attempted else 3)
    assert evidence["status"] == ("INDETERMINATE" if attempted else "BLOCKED")
    assert evidence["disposition"] == (
        "PRESERVE_RECONCILE_NO_RETRY" if attempted else "ADMISSION_REJECTED"
    )
    assert evidence == {
        "schema": operator.RESULT_SCHEMA,
        "status": evidence["status"],
        "disposition": evidence["disposition"],
        **operator.ZERO_EFFECTS,
        "archive_writes": int(attempted),
        "publication_writes": int(published),
    }


def test_complete_plan_is_read_only_and_distinct_from_u(fake):
    code, result = operator.run("plan")
    assert code == 0 and result["disposition"] == "PLANNED_ONLY"
    plan = result["plan"]
    assert plan["schema"] == "arch133w-sealed-predecessor-recovery-plan/v1"
    assert result["schema"] == "arch133w-sealed-predecessor-recovery/v1"
    assert plan["reviewed_u_plan_sha256"] == admission.REVIEWED_U_PLAN_SHA256
    assert plan["material_sha256"] == fake.material.sha256
    assert plan["stage"] == fake.fresh
    assert result["plan_sha256"] != admission.REVIEWED_U_PLAN_SHA256
    assert not fake.events
    assert all(result[k] == plan[k] == 0 for k in operator.ZERO_EFFECTS)
    assert fake.active.exists() and fake.stage.exists() and not fake.archive.exists()
    with pytest.raises(ValueError):
        operator.plan_hash(
            {**plan, "schema": "arch133u-fresh-activation-reprovision-plan/v1"}
        )


def test_execute_reobserves_and_swaps_only_with_exact_preserved_state(
    fake, monkeypatch
):
    calls = []
    original = admission.observe_state

    def observe():
        calls.append("state")
        fake.events.append("state")
        return original()

    monkeypatch.setattr(admission, "observe_state", observe)
    reviewed = sha(fake)
    calls.clear()
    fake.events.clear()
    code, result = operator.run("execute-once", reviewed)
    assert code == 0 and result["disposition"] == "REPROVISION_RECOVERED"
    assert calls == ["state"] * 3
    assert fake.events[0:3] == ["state", "authorized", "state"]
    renames = [e for e in fake.events if isinstance(e, tuple)]
    assert renames == [
        ("rename", str(fake.active), str(fake.archive)),
        ("rename", str(fake.stage), str(fake.active)),
    ]
    assert result["active_generation"] == fake.fresh
    assert fake.archive.exists() and fake.active.exists() and not fake.stage.exists()
    assert all(
        result[k] == (1 if k in ("archive_writes", "publication_writes") else 0)
        for k in operator.ZERO_EFFECTS
    )
    assert (
        result["archived_predecessor"]["files"]["activation.json"]["sha256"]
        == admission.FILE_HASHES["activation.json"]
    )


@pytest.mark.parametrize(
    "target",
    [
        "active_missing",
        "archive_present",
        "stage_missing",
        "extra",
        "staging_extra",
        "sealed_security",
        "sealed_identity",
        "sealed_file",
        "sealed_policy",
        "stage_identity",
        "stage_security",
        "staging_identity",
        "staging_security",
        "stage_bytes",
        "stage_policy",
        "material",
    ],
)
def test_plan_requires_exact_v_state(fake, monkeypatch, target):
    if target == "active_missing":
        fake.active.rename(fake.active.with_name("unobserved"))
    elif target == "archive_present":
        fake.archive.mkdir()
    elif target == "stage_missing":
        fake.stage.rename(fake.stage.with_name("other"))
    elif target == "extra":
        (fake.active / "unexpected").write_bytes(b"x")
    elif target == "staging_extra":
        (fake.stage.parent / "unexpected").mkdir()
    elif target == "sealed_security":
        monkeypatch.setattr(admission, "SEALED_SECURITY_SHA256", "0" * 64)
    elif target == "sealed_identity":
        monkeypatch.setattr(admission, "ROOT_IDENTITY", (42, 1))
    elif target == "sealed_file":
        (fake.active / "activation.json").write_bytes(b"changed")
    elif target == "sealed_policy":
        fake.policies[str(fake.active / "wake.sqlite")] = 0x12019F
    elif target == "stage_identity":
        monkeypatch.setattr(admission, "STAGE_IDENTITY", (42, 1))
    elif target == "stage_security":
        monkeypatch.setattr(admission, "STAGE_SECURITY_SHA256", "0" * 64)
    elif target == "staging_identity":
        monkeypatch.setattr(admission, "STAGING_PARENT_IDENTITY", (42, 1))
    elif target == "staging_security":
        monkeypatch.setattr(admission, "STAGING_PARENT_SECURITY_SHA256", "0" * 64)
    elif target == "stage_bytes":
        (fake.stage / "host-binding.json").write_bytes(b"changed")
    elif target == "stage_policy":
        fake.policies[str(fake.stage / "wake.sqlite")] = 0x120089
    else:
        monkeypatch.setattr(admission, "MATERIAL_SHA256", "0" * 64)
    assert_failure(operator.run("plan"))
    assert not fake.events


@pytest.mark.parametrize(
    "key",
    [
        "root_identity",
        "root_security_sha256",
        "state_sha256",
        "paper_predecessor_sha256",
        "activation_id",
        "wake_id",
        "wake_revision",
        "files",
    ],
)
def test_v_stage_semantic_identity_pins_fail_closed(fake, key):
    fresh = deepcopy(fake.fresh)
    fresh[key] = {} if key == "files" else "drift"
    with pytest.raises((ValueError, TypeError, KeyError)):
        admission.require_stage(fresh)


@pytest.mark.parametrize("phase", ["plan", "pause", "prearchive", "prepublish"])
def test_freshness_expiration_never_publishes(fake, monkeypatch, phase):
    reviewed = sha(fake)
    window = require_fresh(fake.material, fake.old, fake.runtime_facts, fake.now)
    from datetime import datetime

    expires = datetime.fromisoformat(window["start_boundary"])
    if phase == "plan":
        monkeypatch.setattr(operator, "utc_now", lambda: expires)
        assert_failure(operator.run("plan"))
        return
    if phase == "pause":
        monkeypatch.setattr(
            operator,
            "authorize",
            lambda h: monkeypatch.setattr(operator, "utc_now", lambda: expires),
        )
    else:
        clock_calls = 0

        def clock():
            nonlocal clock_calls
            clock_calls += 1
            return (
                expires
                if clock_calls >= (4 if phase == "prearchive" else 5)
                else fake.now
            )

        monkeypatch.setattr(operator, "utc_now", clock)
    assert_failure(
        operator.run("execute-once", reviewed), attempted=phase == "prepublish"
    )
    assert not any(
        isinstance(e, tuple) and e[1] == str(fake.stage) for e in fake.events
    )


@pytest.mark.parametrize(
    "failure",
    [
        "plan",
        "hash",
        "tty",
        "pause_plan",
        "held",
        "pre_rename",
        "archive_call",
        "archive_verify",
        "active_absent",
        "publish_call",
        "active_verify",
        "archive_final",
        "staging_final",
        "runtime_final",
        "material_final",
        "admin_final",
        "guard_close",
    ],
)
def test_exact_attempt_boundary_and_no_retry(fake, monkeypatch, failure):
    reviewed = sha(fake)

    def reject(*a, **kw):
        raise ValueError("fake rejection")

    if failure == "plan":
        monkeypatch.setattr(operator, "make_plan", reject)
    elif failure == "hash":
        reviewed = "0" * 64
    elif failure == "tty":
        monkeypatch.setattr(operator, "authorize", reject)
    elif failure == "pause_plan":
        original = operator.make_plan
        count = 0

        def plans():
            nonlocal count
            count += 1
            result = original()
            if count == 2:
                result[0]["stage"]["wake_id"] = "changed"
            return result

        monkeypatch.setattr(operator, "make_plan", plans)
    elif failure == "held":
        original = native._open_rename_root
        monkeypatch.setattr(
            native,
            "_open_rename_root",
            lambda p: reject() if p == str(fake.active) else original(p),
        )
    elif failure == "pre_rename":
        original = admission.observe_state
        count = 0

        def observe():
            nonlocal count
            count += 1
            if count == 3:
                reject()
            return original()

        monkeypatch.setattr(admission, "observe_state", observe)
    elif failure in ("archive_call", "publish_call"):
        monkeypatch.setattr(
            native.WindowsEdges,
            "archive" if failure == "archive_call" else "publish",
            reject,
        )
    elif failure in ("archive_verify", "active_verify", "archive_final"):
        original = generation.observe_generation
        count = 0

        def observed(root, *a, **kw):
            nonlocal count
            if root == str(fake.archive):
                count += 1
            if (
                (failure == "archive_verify" and root == str(fake.archive))
                or (failure == "active_verify" and root == str(fake.active))
                or (
                    failure == "archive_final"
                    and root == str(fake.archive)
                    and count == 2
                )
            ):
                reject()
            return original(root, *a, **kw)

        monkeypatch.setattr(generation, "observe_generation", observed)
    elif failure == "active_absent":
        monkeypatch.setattr(operator, "require_absent", reject)
    elif failure == "staging_final":
        monkeypatch.setattr(namespace, "final_namespace", reject)
    elif failure in ("runtime_final", "material_final", "admin_final"):
        original = native.WindowsEdges.publish

        def publish(self):
            original(self)
            if failure == "runtime_final":
                monkeypatch.setattr(admission, "observe_runtime", reject)
            elif failure == "material_final":
                monkeypatch.setattr(operator, "read_material", reject)
            else:
                monkeypatch.setattr(admission, "administrator_sid", reject)

        monkeypatch.setattr(native.WindowsEdges, "publish", publish)
    else:

        @contextmanager
        def guard():
            yield {
                namespace.PARENTS[1]: {
                    "identity": [42, 99],
                    "security_sha256": "g" * 64,
                }
            }
            if fake.archive.exists():
                reject()

        monkeypatch.setattr(namespace, "parent_guard", guard)
    attempted = failure in (
        "archive_call",
        "archive_verify",
        "active_absent",
        "publish_call",
        "active_verify",
        "archive_final",
        "staging_final",
        "runtime_final",
        "material_final",
        "admin_final",
        "guard_close",
    )
    published = failure in (
        "publish_call",
        "active_verify",
        "archive_final",
        "staging_final",
        "runtime_final",
        "material_final",
        "admin_final",
        "guard_close",
    )
    assert_failure(operator.run("execute-once", reviewed), attempted, published)
    assert len([e for e in fake.events if isinstance(e, tuple)]) <= 2


def test_archive_verification_and_freshness_precede_publication(fake, monkeypatch):
    reviewed = sha(fake)
    events = []
    original = generation.observe_generation

    def observe(root, *a, **kw):
        if root == str(fake.archive):
            events.append("archive_verified")
        return original(root, *a, **kw)

    monkeypatch.setattr(generation, "observe_generation", observe)
    original_fresh = operator.require_fresh

    def fresh(*a):
        events.append("fresh")
        return original_fresh(*a)

    monkeypatch.setattr(operator, "require_fresh", fresh)
    original_publish = native.WindowsEdges.publish

    def publish(self):
        assert events[-2:] == ["archive_verified", "fresh"]
        events.append("publish")
        original_publish(self)

    monkeypatch.setattr(native.WindowsEdges, "publish", publish)
    assert operator.run("execute-once", reviewed)[0] == 0


@pytest.mark.parametrize(
    "stdin_tty,stdout_tty,phrase",
    [
        (False, True, "exact"),
        (True, False, "exact"),
        (True, True, "bad"),
        (True, True, "exact"),
    ],
)
def test_authorization_requires_exact_tty_phrase(
    monkeypatch, stdin_tty, stdout_tty, phrase
):
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: stdin_tty))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: stdout_tty))
    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt: f"AUTHORIZE ARCH133W {'a' * 64}" if phrase == "exact" else "bad",
    )
    if stdin_tty and stdout_tty and phrase == "exact":
        operator.authorize("a" * 64)
    else:
        with pytest.raises(ValueError):
            operator.authorize("a" * 64)


@pytest.mark.parametrize(
    "root", [generation.ACTIVE, generation.STAGE, r"F:\AITradingBot"]
)
def test_rename_root_uses_share_7_and_source_delete(monkeypatch, root):
    calls = []

    class Function:
        def __call__(self, *args):
            calls.append(args)
            return 123

    api = SimpleNamespace(CreateFileW=Function())
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: api)
    assert native._open_rename_root(root) == 123
    args = calls[0]
    assert args[2] == 7 and args[4] == 3 and args[5] == 0x02200000
    if root in (generation.ACTIVE, generation.STAGE):
        assert args[1] & 0x10000
    else:
        assert args[1] == 0x20085


@pytest.mark.parametrize("success", [False, True])
@pytest.mark.parametrize(
    "source,destination",
    [(generation.ACTIVE, generation.ARCHIVE), (generation.STAGE, generation.ACTIVE)],
)
def test_fixed_relative_no_replace_single_rename(
    monkeypatch, source, destination, success
):
    calls = []

    class Function:
        def __call__(self, *args):
            calls.append(args)
            assert args[:2] == (123, 3)

            class Info(ctypes.Structure):
                _fields_ = [
                    ("replace", ctypes.c_ubyte),
                    ("root", ctypes.c_void_p),
                    ("length", ctypes.c_uint32),
                    ("name", ctypes.c_wchar * 1),
                ]

            info = Info.from_buffer(args[2])
            assert info.replace == 0 and info.root == 456
            value = ctypes.string_at(
                ctypes.addressof(args[2]) + Info.name.offset, info.length
            ).decode("utf-16-le")
            assert value == (
                "Arch133Q-stale" if destination == generation.ARCHIVE else "Arch133"
            )
            return int(success)

    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda *a, **kw: SimpleNamespace(SetFileInformationByHandle=Function()),
    )
    if success:
        native._rename(123, 456, source, destination)
    else:
        with pytest.raises(ValueError):
            native._rename(123, 456, source, destination)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        native._rename(123, 456, source, "alternate")
    assert len(calls) == 1


def test_child_handles_allow_read_delete_but_deny_write(monkeypatch):
    calls = []

    class Function:
        def __call__(self, *args):
            calls.append(args)
            return 123

    monkeypatch.setattr(
        ctypes, "WinDLL", lambda *a, **kw: SimpleNamespace(CreateFileW=Function())
    )
    assert (
        reads.open_generation_file(generation.ACTIVE, "activation.json", renaming=True)
        == 123
    )
    assert calls[0][2] == 5 and not calls[0][2] & 2


def test_native_has_only_fixed_rename_effect_capability():
    source = inspect.getsource(native)
    assert {n for n in vars(native.WindowsEdges) if not n.startswith("_")} == {
        "publication_guard",
        "archive",
        "publish",
    }
    for forbidden in (
        "arch133_reprovision.native",
        "arch133_reprovision_corrected",
        "arch133_reprovision_reconciliation",
        "MoveFile",
        "SetSecurityInfo",
        "sqlite3",
        "create_admin_directory",
        "def _policy",
        "unlink",
        "rmdir",
    ):
        assert forbidden not in source
    assert "namespace.parent_guard()" in inspect.getsource(admission.observe_state)
    assert "namespace.parent_guard()" in inspect.getsource(operator.run)


def test_plan_import_closure_excludes_all_native_and_consumed_operators(tmp_path):
    script = tmp_path / "imports.py"
    script.write_text(
        "import sys\nsys.path.insert(0, "
        + repr(str(ROOT / "src"))
        + ")\nfrom trading_bot.arch133_reprovision_recovery import operator\n"
        "assert not any(x in sys.modules for x in ("
        "'trading_bot.arch133_reprovision_recovery.native',"
        "'trading_bot.arch133_reprovision.native',"
        "'trading_bot.arch133_reprovision_corrected.operator',"
        "'trading_bot.arch133_reprovision_reconciliation.operator'))\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_lazy_native_import_after_authorization_and_second_plan(fake, monkeypatch):
    reviewed = sha(fake)
    saved = builtins.__import__
    events = []
    plan = operator.make_plan

    def plans():
        events.append("plan")
        return plan()

    monkeypatch.setattr(operator, "make_plan", plans)
    monkeypatch.setattr(operator, "authorize", lambda h: events.append("authorize"))

    def imports(name, *a, **kw):
        if name == "trading_bot.arch133_reprovision_recovery.native":
            assert events == ["plan", "authorize", "plan"]
            events.append("native")
        return saved(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", imports)
    assert operator.run("execute-once", reviewed)[0] == 0
    assert events == ["plan", "authorize", "plan", "native"]


def test_source_authority_and_source_only_registration():
    assert runner._arch133_reprovision_recovery_authority_check(ROOT) == ()
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert spec.remote_branch == admission.SOURCE_BRANCH
    assert runner.ACTIVE_CI_CHECKPOINTS[-5:-3] == (
        "arch133-robinhood-reprovision-indeterminate-reconciliation",
        NAME,
    )
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 52


@pytest.mark.parametrize(
    "mutation",
    [
        "init",
        "admission",
        "native",
        "operator",
        "launcher",
        "inventory",
        "registration",
        "active",
        "workflow",
        "v_chain",
    ],
)
def test_source_pins_inventory_registration_order_workflow_fail_closed(
    tmp_path, monkeypatch, mutation
):
    monkeypatch.setattr(
        runner,
        "_arch133_reprovision_reconciliation_authority_check",
        lambda r: ("V rejected",) if mutation == "v_chain" else (),
    )
    for relative in runner.ARCH133W_RECOVERY_SOURCES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    parsed = ast.parse((ROOT / "scripts/checkpoint_runner.py").read_text())
    nodes = [
        n
        for n in parsed.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id in ("ARCH133W_RECOVERY_SOURCES", "ACTIVE_CI_CHECKPOINTS")
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
    if mutation != "v_chain":
        assert runner._arch133_reprovision_recovery_authority_check(tmp_path) == ()
    if mutation in ("init", "admission", "native", "operator", "launcher"):
        path = (
            tmp_path
            / runner.ARCH133W_RECOVERY_SOURCES[
                ("init", "admission", "native", "operator", "launcher").index(mutation)
            ]
        )
        path.write_text(path.read_text() + "\nDRIFT=True\n")
    elif mutation == "inventory":
        script.write_text(
            script.read_text().replace("ARCH133W_RECOVERY_SOURCES", "MISSING")
        )
    elif mutation == "registration":
        script.write_text(
            script.read_text().replace("preflight=None", "preflight=effect")
        )
    elif mutation == "active":
        script.write_text(
            script.read_text().replace("ACTIVE_CI_CHECKPOINTS", "MISSING")
        )
    elif mutation == "workflow":
        workflow.write_text(workflow.read_text().replace(NAME, "missing"))
    assert runner._arch133_reprovision_recovery_authority_check(tmp_path)


def test_cli_and_launcher_reject_overrides_without_importing_authority(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(sys, "argv", ["launcher", "--material-file", "arbitrary"])
    assert operator.main() == 3
    assert_failure((3, json.loads(capsys.readouterr().out)))
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(ROOT / "scripts/run_arch133_reprovision_recovery.py"),
            "--material-file",
            "arbitrary",
        ],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 3
        and result.stdout.strip() == "ARCH133W_RUNTIME_BLOCKED"
        and not result.stderr
    )


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
    branch = admission.SOURCE_BRANCH
    ref = "refs/remotes/origin/" + branch
    responses = {
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "HEAD^{tree}"): "b" * 40,
        ("rev-parse", "--show-toplevel"): str(tmp_path),
        ("branch", "--show-current"): branch,
        ("remote", "get-url", "origin"): admission.ORIGIN,
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
    monkeypatch.setattr(admission, "_git", lambda r, *args: responses[args])
    if drift:
        with pytest.raises((ValueError, OSError)):
            admission.require_checkout(tmp_path, branch)
    else:
        assert admission.require_checkout(tmp_path, branch) == ("a" * 40, "b" * 40)


def test_exact_frozen_bindings():
    assert admission.SOURCE_ROOT == Path(
        r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133w"
    )
    assert admission.SOURCE_BRANCH == "feature/robinhood-unattended-review-paper-133w"
    assert admission.U_ROOT == Path(
        r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133u"
    )
    assert admission.U_BRANCH == "feature/robinhood-unattended-review-paper-133u"
    assert admission.U_HEAD == "49686d7f61717b9ee7452cee633d23b0c7db873e"
    assert admission.U_TREE == "12b430743786ba6650aa720fc27a6d9b0d95ea74"
    assert admission.MATERIAL_PATH == Path(
        r"F:\AI\temp\arch133q\fresh-material-2026-10-09.json"
    )
    assert (
        admission.MATERIAL_SHA256
        == "7b55cb89e94f09a8271a7c28fad9737c0ddb1ef94aba719968ea2820ea24a686"
    )
    assert (
        admission.REVIEWED_U_PLAN_SHA256
        == "a223d8fa606da9cc129d5d095c6c94ec6be42f350da0bec7fe4825fe6ef8bb81"
    )
    assert admission.ROOT_IDENTITY == (1855336320, 1407374886183770)
    assert admission.PREDECESSOR_NAMESPACE == (
        ("activation.json", 1407374886191165),
        ("host-binding.json", 562949956059198),
        ("paper.sqlite", 562949956054077),
        ("wake.sqlite", 1125899909477979),
    )
    assert len(operator.ZERO_EFFECTS) == 15
    assert binding.PRODUCTION_PYTHON == Path(r"F:\AITradingBot\runtime\python.exe")
    assert binding.PRODUCTION_PYTHON_VERSION == "3.14.3"
    assert (
        binding.PRODUCTION_PYTHON_SHA256
        == "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
    )

    assert admission.V_HEAD == "432001e3dcae48e589adf8e60c7dac5ffc08d591"
    assert admission.V_TREE == "96f2f41caa6d17a32fe729ae8786560252a0c9a8"
    assert admission.STAGE_IDENTITY == (1855336320, 844424933411687)
    assert admission.STAGING_PARENT_IDENTITY == (1855336320, 2251799815590570)
    assert (
        admission.STAGE_STATE_SHA256
        == "6454b1132ee93ac5af6694b2c30ae3645ccf42ea0aed98e6bf4035cedf477967"
    )


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    executable = tmp_path / "python.exe"
    executable.write_bytes(b"fake interpreter")
    monkeypatch.setattr(admission, "SOURCE_ROOT", ROOT)
    monkeypatch.setattr(
        admission, "LAUNCHER", ROOT / "scripts/run_arch133_reprovision_recovery.py"
    )
    monkeypatch.setattr(admission, "NO_PYCACHE", tmp_path / "missing-cache")
    monkeypatch.setattr(binding, "PRODUCTION_PYTHON", executable)
    monkeypatch.setattr(
        binding,
        "PRODUCTION_PYTHON_SHA256",
        hashlib.sha256(executable.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=1))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(sys, "pycache_prefix", str(admission.NO_PYCACHE))
    monkeypatch.setattr(sys, "argv", [str(admission.LAUNCHER)])
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "version_info", (3, 14, 3))

    def source(root, branch):
        return (
            (admission.U_HEAD, admission.U_TREE)
            if root == admission.U_ROOT
            else (
                (admission.V_HEAD, admission.V_TREE)
                if root == admission.V_ROOT
                else (
                    (
                        generation.predecessor.PUBLISHED_RUNTIME_HEAD,
                        generation.predecessor.PUBLISHED_RUNTIME_TREE,
                    )
                    if root == binding.SOURCE_ROOT
                    else ("a" * 40, "b" * 40)
                )
            )
        )

    monkeypatch.setattr(admission, "require_checkout", source)
    monkeypatch.setattr(binding, "LAUNCHER", executable)
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
        admission.NO_PYCACHE.mkdir()
    elif drift == "launcher":
        monkeypatch.setattr(sys, "argv", [str(runtime)])
    elif drift == "executable":
        monkeypatch.setattr(sys, "executable", str(admission.LAUNCHER))
    elif drift == "version":
        monkeypatch.setattr(sys, "version_info", (3, 14, 2))
    elif drift == "hash":
        runtime.write_bytes(b"changed")
    elif drift == "source":
        monkeypatch.setattr(admission, "SOURCE_ROOT", runtime.parent)
    elif drift in ("u_head", "u_tree"):
        original = admission.require_checkout
        monkeypatch.setattr(
            admission,
            "require_checkout",
            lambda root, branch: (
                (
                    ("0" * 40, admission.U_TREE)
                    if drift == "u_head"
                    else (admission.U_HEAD, "0" * 40)
                )
                if root == admission.U_ROOT
                else original(root, branch)
            ),
        )
    if drift:
        with pytest.raises(ValueError):
            admission.observe_runtime()
    else:
        facts = admission.observe_runtime()
        assert facts["u_source_head"] == admission.U_HEAD
        assert (
            facts["wake_launcher_sha256"]
            == hashlib.sha256(runtime.read_bytes()).hexdigest()
        )


@pytest.mark.parametrize("which", ["V_ROOT", "U_ROOT", "bound"])
def test_all_consumed_runtime_sources_must_be_exact(runtime, monkeypatch, which):
    original = admission.require_checkout
    target = binding.SOURCE_ROOT if which == "bound" else getattr(admission, which)
    monkeypatch.setattr(
        admission,
        "require_checkout",
        lambda root, branch: (
            ("0" * 40, "0" * 40) if root == target else original(root, branch)
        ),
    )
    with pytest.raises(ValueError):
        admission.observe_runtime()


def test_frozen_v_topology_path():
    assert admission.V_ROOT == Path(
        r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133v"
    )
    assert admission.V_BRANCH == "feature/robinhood-unattended-review-paper-133v"


@pytest.mark.parametrize("error", [2, 3, 5, 32, 87])
def test_presence_shares_delete_and_only_not_found_is_absent(monkeypatch, error):
    calls = []

    class Function:
        def __call__(self, *args):
            calls.append(args)
            return None

    monkeypatch.setattr(
        ctypes, "WinDLL", lambda *a, **kw: SimpleNamespace(CreateFileW=Function())
    )
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    with ExitStack() as held:
        if error in (2, 3):
            assert admission.presence(generation.ACTIVE, held) is None
        else:
            with pytest.raises(read_only.RootOpenError):
                admission.presence(generation.ACTIVE, held)
        with pytest.raises(ValueError):
            admission.presence("arbitrary", held)
    assert calls[0][2] == 7 and calls[0][1] == 0x20081


@pytest.mark.parametrize("phase", ["pause", "final"])
def test_administrator_drift_fails_closed(fake, monkeypatch, phase):
    reviewed = sha(fake)
    if phase == "pause":
        monkeypatch.setattr(
            operator,
            "authorize",
            lambda h: monkeypatch.setattr(
                admission, "administrator_sid", lambda: "changed"
            ),
        )
    else:
        original = native.WindowsEdges.publish

        def publish(self):
            original(self)
            monkeypatch.setattr(admission, "administrator_sid", lambda: "changed")

        monkeypatch.setattr(native.WindowsEdges, "publish", publish)
    assert_failure(
        operator.run("execute-once", reviewed), phase == "final", phase == "final"
    )
