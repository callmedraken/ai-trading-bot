"""133-T frozen-contract tests: fake parent handles and temporary inputs only."""

from __future__ import annotations

import ast
import ctypes
import hashlib
import json
import runpy
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.arch133_acl import read_only
from trading_bot.arch133_parent_policy_diagnostic import admission, operator
from trading_bot.arch133_reprovision import namespace, predecessor
from trading_bot.runtime.windows_authority import AuthoritySecurityError

ROOT = Path(__file__).resolve().parents[2]
PARENT_STAGES = (
    *operator.VOLUME_STAGES,
    *operator.HOST_STAGES,
    *operator.COMBINED_STAGES,
)
SECRET = "S-1-5-21-987654321 ACE=0xD0046 descriptor native-sensitive-detail"
EXPECTED_COUNTERS = (
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
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda *a, **k: pytest.fail("real native edge"), raising=False
    )


def fail(*args):
    raise ValueError(SECRET)


def assert_result(result, stage, passed=False):
    assert result == {
        "schema": operator.SCHEMA,
        "status": "PASS" if passed else "BLOCKED",
        "reason": (
            "PARENT_POLICY_DIAGNOSTIC_COMPLETE"
            if passed
            else "PARENT_POLICY_DIAGNOSTIC_BLOCKED"
        ),
        "stage": stage,
        **dict.fromkeys(EXPECTED_COUNTERS, 0),
    }
    assert len(EXPECTED_COUNTERS) == len(set(EXPECTED_COUNTERS)) == 15


@pytest.fixture
def parents(monkeypatch):
    fake = SimpleNamespace(
        opened=[], closed=[], live=set(), snapshots={}, observations=[], stages=[]
    )
    good = read_only.DirectoryObservation(
        read_only.ADMINISTRATORS_SID, True, read_only.ADMIN_ACES, (42, 100)
    )

    def opened(path):
        handle = len(fake.opened) + 1
        fake.opened.append(handle)
        fake.live.add(handle)
        fake.snapshots[handle] = (good, "fixed-test-security")
        return handle

    def observed(handle, path):
        assert handle in fake.live
        fake.observations.append((handle, frozenset(fake.live)))
        return fake.snapshots[handle]

    def closed(handle):
        assert handle in fake.live
        fake.live.remove(handle)
        fake.closed.append(handle)

    stage = operator._stage

    def traced(name, function, /, *args):
        fake.stages.append(name)
        return stage(name, function, *args)

    monkeypatch.setattr(read_only, "open_directory", opened)
    monkeypatch.setattr(read_only, "inspect_directory_security", observed)
    monkeypatch.setattr(read_only, "close_handle", closed)
    monkeypatch.setattr(operator, "_stage", traced)
    fake.good = good
    return fake


@pytest.fixture
def admitted(monkeypatch, parents, tmp_path):
    monkeypatch.setattr(operator, "read_material", lambda path: object())
    monkeypatch.setattr(
        admission, "observe_predecessor", lambda: ("old", {"runtime": {}})
    )
    monkeypatch.setattr(admission, "require_retained", lambda old: None)
    monkeypatch.setattr(operator, "require_stale", lambda *a: None)
    monkeypatch.setattr(operator, "require_fresh", lambda *a: None)
    monkeypatch.setattr(namespace, "require_vacant", lambda: None)
    parents.path = tmp_path / "material.json"
    return parents


@pytest.mark.parametrize("stage", PARENT_STAGES)
def test_every_parent_substage_stops_and_closes_once(
    admitted, monkeypatch, stage, capsys, caplog
):
    original = operator._stage

    def rejected(name, function, /, *args):
        if name == stage:
            if name.endswith("_CLOSE"):

                def close_then_fail(*values):
                    function(*values)
                    fail()

                return original(name, close_then_fail, *args)
            return original(name, fail)
        return original(name, function, *args)

    monkeypatch.setattr(operator, "_stage", rejected)
    assert operator.main(["--material-file", str(admitted.path)]) == 3
    output = capsys.readouterr()
    assert_result(json.loads(output.out), stage)
    assert output.err == caplog.text == ""
    assert SECRET not in output.out
    stop = admitted.stages.index(stage)
    assert all(item.endswith("_CLOSE") for item in admitted.stages[stop + 1 :])
    assert Counter(admitted.opened) == Counter(admitted.closed)
    assert not admitted.live


def test_success_exact_order_both_combined_handles_held_and_closed(admitted):
    result = operator.diagnose(admitted.path)
    assert_result(result, "ADMISSION_COMPLETE", True)
    assert admitted.stages == list(PARENT_STAGES)
    assert admitted.opened == [1, 2, 3, 4]
    assert admitted.closed == [1, 2, 4, 3]
    assert admitted.observations[-2:] == [
        (3, frozenset({3, 4})),
        (4, frozenset({3, 4})),
    ]
    assert Counter(admitted.opened) == Counter(admitted.closed)


@pytest.mark.parametrize(
    "parent,stages", [(1, operator.VOLUME_STAGES), (2, operator.HOST_STAGES)]
)
@pytest.mark.parametrize(
    "field,value,index",
    [
        ("filesystem", "ntfs", 2),
        ("filesystem", "ReFS", 2),
        ("reparse", True, 3),
        ("reparse", 0, 3),
        ("owner_sid", "S-1-5-21-987654321", 4),
        ("aces", (("S-1-5-21-987654321", 0xD0046, 0, 0),), 5),
        ("aces", (("S-1-5-21-987654321", 0xD0046, 1, 0),), 5),
    ],
)
def test_exact_policy_rejection_stage(
    admitted, monkeypatch, parent, stages, field, value, index
):
    opened = read_only.open_directory

    def altered(path):
        handle = opened(path)
        if handle == parent:
            admitted.snapshots[handle] = (
                replace(admitted.good, **{field: value}),
                "secret",
            )
        return handle

    monkeypatch.setattr(read_only, "open_directory", altered)
    assert_result(operator.diagnose(admitted.path), stages[index])
    assert Counter(admitted.opened) == Counter(admitted.closed)


@pytest.mark.parametrize(
    "aces",
    [
        (),
        read_only.ADMIN_ACES,
        ((read_only.ADMINISTRATORS_SID, 0xFFFFFFFF, 0, 0),),
        ((read_only.SYSTEM_SID, 0xFFFFFFFF, 0, 0),),
        (("other", 0xD0046, 0, 8),),
        (("other", 0xFFFFFFFF, 0, 9),),
        (("other", 0x120089, 0, 0),),
    ],
)
def test_accepted_ace_exceptions_preserve_policy(parents, aces):
    operator._policy(replace(parents.good, aces=aces))


@pytest.mark.parametrize("bit", [0x2, 0x4, 0x40, 0x10000, 0x40000, 0x80000])
def test_each_frozen_mask_bit_rejected(parents, bit):
    with pytest.raises(ValueError):
        operator._acl(replace(parents.good, aces=(("other", bit, 0, 0),)))


@pytest.mark.parametrize(
    "handle,stage",
    [
        (1, "PARENT_VOLUME_REOBSERVATION"),
        (2, "PARENT_HOST_REOBSERVATION"),
        (3, "PARENT_COMBINED_VOLUME_REOBSERVATION"),
        (4, "PARENT_COMBINED_HOST_REOBSERVATION"),
    ],
)
@pytest.mark.parametrize("change", ["observation", "security"])
def test_changed_reobservation_is_rejected(
    admitted, monkeypatch, handle, stage, change
):
    observe = read_only.inspect_directory_security
    calls = Counter()

    def changed(current, path):
        observed, security = observe(current, path)
        calls[current] += 1
        if current == handle and calls[current] == 2:
            return (
                (replace(observed, identity=(42, 101)), security)
                if change == "observation"
                else (observed, SECRET)
            )
        return observed, security

    monkeypatch.setattr(read_only, "inspect_directory_security", changed)
    assert_result(operator.diagnose(admitted.path), stage)
    assert Counter(admitted.opened) == Counter(admitted.closed)


@pytest.mark.parametrize(
    "handles,stage",
    [
        ({1}, "PARENT_VOLUME_CLOSE"),
        ({2}, "PARENT_HOST_CLOSE"),
        ({3}, "PARENT_COMBINED_VOLUME_CLOSE"),
        ({4}, "PARENT_COMBINED_HOST_CLOSE"),
        ({3, 4}, "PARENT_COMBINED_HOST_CLOSE"),
    ],
)
def test_native_close_failure_wins_and_all_handles_close_once(
    admitted, monkeypatch, handles, stage
):
    close = read_only.close_handle

    def failed(handle):
        close(handle)
        if handle in handles:
            fail()

    monkeypatch.setattr(read_only, "close_handle", failed)
    # Also fail observation: CLOSE must still take precedence.
    observe = read_only.inspect_directory_security
    monkeypatch.setattr(
        read_only,
        "inspect_directory_security",
        lambda h, p: (
            fail() if len(handles) == 1 and h == min(handles) else observe(h, p)
        ),
    )
    assert_result(operator.diagnose(admitted.path), stage)
    assert Counter(admitted.opened) == Counter(admitted.closed)


@pytest.mark.parametrize(
    "stage,target,name",
    [
        ("MATERIAL_READ", operator, "read_material"),
        ("PREDECESSOR_ADMISSION", admission, "observe_predecessor"),
        ("PREDECESSOR_MATERIAL", admission, "require_retained"),
        ("PREDECESSOR_STALE", operator, "require_stale"),
        ("FRESH_MATERIAL", operator, "require_fresh"),
        ("NAMESPACE_VACANCY", namespace, "require_vacant"),
    ],
)
def test_predecessor_material_namespace_cannot_be_skipped(
    admitted, monkeypatch, stage, target, name
):
    monkeypatch.setattr(target, name, fail)
    assert_result(operator.diagnose(admitted.path), stage)
    assert admitted.opened == []


@pytest.mark.parametrize("stage", operator.PREDECESSOR_STAGES)
def test_predecessor_fixed_details_remain_sanitized(admitted, monkeypatch, stage):
    def rejected():
        raise admission.AdmissionStageError(stage)

    monkeypatch.setattr(admission, "observe_predecessor", rejected)
    assert_result(operator.diagnose(admitted.path), stage)


def test_unknown_exception_stage_cannot_escape(admitted, monkeypatch):
    def rejected():
        raise admission.AdmissionStageError(SECRET)

    monkeypatch.setattr(admission, "observe_predecessor", rejected)
    assert_result(operator.diagnose(admitted.path), "PREDECESSOR_ADMISSION")


def test_real_material_and_namespace_rejections_before_parents(
    parents, tmp_path, monkeypatch
):
    path = tmp_path / "material.json"
    path.write_text("{}", encoding="utf-8")
    assert_result(operator.diagnose(path), "MATERIAL_READ")
    monkeypatch.setattr(namespace, "ARCHIVE", str(tmp_path / "occupied"))
    monkeypatch.setattr(namespace, "STAGING_PARENT", str(tmp_path / "absent"))
    (tmp_path / "occupied").mkdir()
    with pytest.raises(ValueError):
        namespace.require_vacant()
    assert parents.opened == []


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    own, bound = tmp_path / "own", tmp_path / "bound"
    module = own / "src/trading_bot/arch133_parent_policy_diagnostic/admission.py"
    module.parent.mkdir(parents=True)
    module.touch()
    launcher = own / "scripts/run_arch133_parent_policy_diagnostic.py"
    launcher.parent.mkdir()
    launcher.touch()
    bound.mkdir()
    wake = bound / "wake.py"
    wake.write_bytes(b"fake wake launcher")
    python = tmp_path / "python.exe"
    python.write_bytes(b"fake python")
    monkeypatch.setattr(admission, "SOURCE_ROOT", own)
    monkeypatch.setattr(admission, "LAUNCHER", launcher)
    monkeypatch.setattr(admission, "NO_PYCACHE", own / "no-pycache")
    monkeypatch.setattr(admission, "__file__", str(module))
    monkeypatch.setattr(admission.binding, "SOURCE_ROOT", bound)
    monkeypatch.setattr(admission.binding, "LAUNCHER", wake)
    monkeypatch.setattr(admission.binding, "PRODUCTION_PYTHON", python)
    monkeypatch.setattr(admission.binding, "PRODUCTION_PYTHON_VERSION", "3.14.3")
    monkeypatch.setattr(
        admission.binding,
        "PRODUCTION_PYTHON_SHA256",
        hashlib.sha256(python.read_bytes()).hexdigest(),
    )
    fake_sys = SimpleNamespace(
        platform="win32",
        flags=SimpleNamespace(isolated=1),
        dont_write_bytecode=True,
        pycache_prefix=str(own / "no-pycache"),
        argv=[str(launcher)],
        executable=str(python),
        version_info=(3, 14, 3),
    )
    monkeypatch.setattr(admission, "sys", fake_sys)
    observations = {}
    for root, branch, head, tree in (
        (own, admission.SOURCE_BRANCH, "a" * 40, "b" * 40),
        (
            bound,
            admission.binding.SOURCE_BRANCH,
            predecessor.PUBLISHED_RUNTIME_HEAD,
            predecessor.PUBLISHED_RUNTIME_TREE,
        ),
    ):
        for args, value in (
            (("rev-parse", "HEAD"), head),
            (("rev-parse", "HEAD^{tree}"), tree),
            (("rev-parse", "--show-toplevel"), str(root)),
            (("branch", "--show-current"), branch),
            (("remote", "get-url", "origin"), admission.ORIGIN),
            (("status", "--porcelain=v1", "--untracked-files=all"), ""),
            (("rev-parse", "refs/remotes/origin/" + branch), head),
            (("rev-parse", "refs/remotes/origin/" + branch + "^{tree}"), tree),
            (
                ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
                "origin/" + branch,
            ),
        ):
            observations[root, args] = value
    monkeypatch.setattr(admission, "_git", lambda root, *args: observations[root, args])
    return SimpleNamespace(
        own=own, bound=bound, sys=fake_sys, observations=observations, python=python
    )


def test_exact_runtime_admission_with_fake_paths(runtime):
    result = admission.observe_runtime()
    assert result["operator_source_head"] == "a" * 40
    assert result["bound_source_head"] == predecessor.EXECUTABLE_SOURCE_HEAD


@pytest.mark.parametrize(
    "root,args,value",
    [
        ("own", ("branch", "--show-current"), "wrong"),
        ("own", ("remote", "get-url", "origin"), "wrong"),
        ("own", ("status", "--porcelain=v1", "--untracked-files=all"), " M file"),
        ("own", ("status", "--porcelain=v1", "--untracked-files=all"), "?? file"),
        ("own", ("status", "--porcelain=v1", "--untracked-files=all"), "M  file"),
        (
            "own",
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
            "wrong",
        ),
        ("own", ("rev-parse", "HEAD"), "invalid"),
        ("own", ("rev-parse", "HEAD^{tree}"), "invalid"),
        ("bound", ("rev-parse", "HEAD"), "c" * 40),
        ("bound", ("branch", "--show-current"), "wrong"),
        ("bound", ("remote", "get-url", "origin"), "wrong"),
        ("bound", ("status", "--porcelain=v1", "--untracked-files=all"), "?? file"),
    ],
)
def test_source_drift_fails_before_native(runtime, monkeypatch, root, args, value):
    runtime.observations[getattr(runtime, root), args] = value
    with pytest.raises(admission.AdmissionStageError) as error:
        admission.observe_predecessor()
    assert error.value.stage == "PREDECESSOR_RUNTIME"


@pytest.mark.parametrize(
    "mutation",
    [
        "platform",
        "isolated",
        "bytecode",
        "prefix",
        "pycache_exists",
        "module",
        "launcher",
        "executable",
        "version",
        "python_bytes",
        "head_ref",
        "tree_ref",
        "toplevel",
    ],
)
def test_runtime_identity_drift_fails_before_native(runtime, monkeypatch, mutation):
    if mutation == "platform":
        runtime.sys.platform = "linux"
    elif mutation == "isolated":
        runtime.sys.flags.isolated = 0
    elif mutation == "bytecode":
        runtime.sys.dont_write_bytecode = False
    elif mutation == "prefix":
        runtime.sys.pycache_prefix = "wrong"
    elif mutation == "pycache_exists":
        (runtime.own / "no-pycache").mkdir()
    elif mutation == "module":
        monkeypatch.setattr(admission, "__file__", str(runtime.python))
    elif mutation == "launcher":
        runtime.sys.argv = [str(runtime.python)]
    elif mutation == "executable":
        runtime.sys.executable = str(runtime.own)
    elif mutation == "version":
        runtime.sys.version_info = (3, 14, 4)
    elif mutation == "python_bytes":
        runtime.python.write_bytes(b"changed")
    elif mutation == "toplevel":
        runtime.observations[runtime.own, ("rev-parse", "--show-toplevel")] = str(
            runtime.bound
        )
    else:
        suffix = "^{tree}" if mutation == "tree_ref" else ""
        runtime.observations[
            runtime.own,
            ("rev-parse", "refs/remotes/origin/" + admission.SOURCE_BRANCH + suffix),
        ] = "c" * 40
    with pytest.raises(admission.AdmissionStageError) as error:
        admission.observe_predecessor()
    assert error.value.stage == "PREDECESSOR_RUNTIME"


def test_fresh_import_closure_excludes_all_effect_modules(tmp_path):
    probe = tmp_path / "imports.py"
    probe.write_text(
        "import json,sys\nsys.path.insert(0,sys.argv[1])\n"
        "import trading_bot.arch133_parent_policy_diagnostic.operator\n"
        "print(json.dumps(sorted(sys.modules)))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(probe), str(ROOT / "src")],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    imported = json.loads(result.stdout)
    forbidden = (
        "trading_bot.arch133_reprovision.native",
        "trading_bot.arch133_reprovision.operator",
        "trading_bot.arch133_acl.primitive",
        "trading_bot.arch133_acl.native",
        "trading_bot.arch133_acl.recovery",
        "trading_bot.arch133_scheduler_installation.native",
        "trading_bot.arch133_scheduler_installation.operator",
        "trading_bot.arch133_publication",
        "trading_bot.review_paper.unattended_host",
        "trading_bot.review_paper.unattended_execution",
        "trading_bot.review_paper.unattended_state_store",
        "trading_bot.review_paper.store",
        "trading_bot.robinhood_mcp",
        "trading_bot.execution",
        "trading_bot.brokers",
        "mcp",
        "httpx",
        "httpx2",
        "requests",
        "socket",
        "urllib.request",
        "win32com",
    )
    assert not [name for name in imported if name.startswith(forbidden)]
    # Every project source imported by a fresh process belongs to the pinned chain.
    from scripts import checkpoint_runner as runner

    pinned = set(runner.ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS)
    for name, pins in vars(runner).items():
        if name.startswith("ARCH133_") and name.endswith("_PINS"):
            pinned.update(pins)
    for name in imported:
        if name.startswith("trading_bot."):
            path = "src/" + name.replace(".", "/")
            relative = (
                path + ".py"
                if (ROOT / (path + ".py")).is_file()
                else path + "/__init__.py"
            )
            assert relative in pinned


def test_source_has_no_forbidden_effect_entrypoints():
    source = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "src/trading_bot/arch133_parent_policy_diagnostic/admission.py",
            "src/trading_bot/arch133_parent_policy_diagnostic/operator.py",
            "scripts/run_arch133_parent_policy_diagnostic.py",
        )
    )
    for forbidden in (
        "WindowsEdges",
        "execute-once",
        "SetFileInformationByHandle",
        "CreateDirectoryW",
        "SetSecurityInfo",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "WindowsOAuthStorage",
        "run_unattended_host",
        "execute_one_unattended_review_paper_wake",
        "mutable=True",
        ".mkdir(",
        ".write_bytes(",
        ".write_text(",
        ".rename(",
    ):
        assert forbidden not in source
    tree = ast.parse(
        (
            ROOT / "src/trading_bot/arch133_parent_policy_diagnostic/admission.py"
        ).read_text(encoding="utf-8")
    )
    assert not [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == "predecessor"
        and n.attr.startswith("_")
    ]


@pytest.mark.parametrize(
    "args", [[], ["--material-file", "relative.json"], ["--wrong", "/tmp/file"]]
)
def test_main_argument_drift_is_effect_free(args, capsys):
    assert operator.main(args) == 3
    assert_result(json.loads(capsys.readouterr().out), "ARGUMENTS")


def test_launcher_rejects_unisolated_temp_copy_without_host_reads(
    tmp_path, monkeypatch, capsys
):
    launcher = tmp_path / "launcher.py"
    launcher.write_text(
        (ROOT / "scripts/run_arch133_parent_policy_diagnostic.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", [str(launcher), "--material-file", str(tmp_path / "material.json")]
    )
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(launcher), run_name="__main__")
    assert error.value.code == 3
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert all(result[name] == 0 for name in EXPECTED_COUNTERS)


def test_predecessor_observation_and_material_predicates_preserve_accepted_source():
    # Independent admission avoids rebinding/monkeypatching the consumed R
    # operator. Normalize only public/local helper names, then prove all R
    # observation, reobservation and retained-material predicates survive.
    def functions(relative):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        return {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }

    accepted = functions("src/trading_bot/arch133_reprovision_diagnostic/operator.py")
    current = functions("src/trading_bot/arch133_parent_policy_diagnostic/admission.py")

    class Normalize(ast.NodeTransformer):
        def visit_Name(self, node):
            aliases = {
                "_runtime": "observe_runtime",
                "_observe_predecessor": "observe_predecessor",
                "_require_retained": "require_retained",
            }
            return ast.copy_location(
                ast.Name(aliases.get(node.id, node.id), node.ctx), node
            )

        def visit_Attribute(self, node):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "predecessor"
                and node.attr.startswith("_")
            ):
                return ast.copy_location(ast.Name(node.attr, node.ctx), node)
            return self.generic_visit(node)

    for old, new in (
        ("_observe_predecessor", "observe_predecessor"),
        ("_require_retained", "require_retained"),
    ):
        original = Normalize().visit(accepted[old])
        original.name = new
        assert ast.dump(original, include_attributes=False) == ast.dump(
            current[new], include_attributes=False
        )


def test_observer_held_inputs_and_runtime_reobservation_close_once(
    monkeypatch, tmp_path
):
    root = SimpleNamespace(
        identity=predecessor.ROOT_IDENTITY,
        filesystem="NTFS",
        reparse=False,
        classification=lambda: "EXACT_INTENDED_ROOT",
    )
    names = tuple(
        (name, index) for index, name in enumerate(admission.retained_reads.FINAL_NAMES)
    )
    closed = []
    runtime_calls = []
    monkeypatch.setattr(
        admission,
        "observe_runtime",
        lambda: runtime_calls.append(1) or {"wake_launcher_sha256": "fake"},
    )
    monkeypatch.setattr(admission, "administrator_sid", lambda: None)
    monkeypatch.setattr(
        admission.reads, "open_generation_directory", lambda path: "root"
    )
    monkeypatch.setattr(
        read_only,
        "inspect_directory_security",
        lambda *a: (root, predecessor.ROOT_SECURITY_SHA256),
    )
    monkeypatch.setattr(read_only, "close_handle", closed.append)
    monkeypatch.setattr(admission.retained_reads, "namespace", lambda handle: names)
    monkeypatch.setattr(
        admission.retained_reads, "open_retained_file", lambda name: name
    )
    monkeypatch.setattr(
        admission.retained_reads,
        "file_snapshot",
        lambda handle, name: (
            (predecessor.ROOT_IDENTITY[0], dict(names)[name]),
            predecessor.FILE_HASHES[name],
        ),
    )
    monkeypatch.setattr(
        admission.file_policy, "observe_file_policy", lambda handle: "fake policy"
    )
    monkeypatch.setattr(admission.file_policy, "require_file_policy", lambda *a: None)
    activation = SimpleNamespace(store_identity="fake")
    monkeypatch.setattr(
        admission,
        "_publication_path_read",
        lambda: (b"fake activation", b"fake binding"),
    )
    monkeypatch.setattr(
        admission, "_publication_parse", lambda raw: (activation, "fake host")
    )
    monkeypatch.setattr(admission, "_publication_semantics", lambda *a: None)
    monkeypatch.setattr(
        admission, "_state_path_resolution", lambda act: tmp_path / "state.sqlite"
    )
    monkeypatch.setattr(admission.binding, "PAPER_PATH", (tmp_path / "paper.sqlite"))
    connections = []

    class Connection:
        def __init__(self, uri):
            self.uri, self.commands, self.closes = uri, [], 0

        def execute(self, query):
            self.commands.append(query)

        def close(self):
            self.closes += 1

    def connect(database, **kwargs):
        assert kwargs == {"uri": True, "timeout": 0}
        value = Connection(database)
        connections.append(value)
        return value

    # Keep the real connection function untouched outside this unit boundary.
    monkeypatch.setattr(admission, "sqlite3", SimpleNamespace(connect=connect))
    monkeypatch.setattr(
        predecessor,
        "require_ready_state",
        lambda *a: SimpleNamespace(fingerprint="fake-state"),
    )
    # Stable snapshot object is required by the actual reobservation predicate.
    state = SimpleNamespace(fingerprint="fake-state")
    monkeypatch.setattr(predecessor, "require_ready_state", lambda *a: state)
    monkeypatch.setattr(predecessor, "require_empty_paper", lambda *a: "fake-paper")
    assert admission.observe_predecessor()[0] is activation
    assert len(runtime_calls) == 2
    assert Counter(closed) == Counter(["root", *admission.retained_reads.FINAL_NAMES])
    assert len(connections) == 2
    assert all(
        c.closes == 1 and c.commands == ["BEGIN"] and c.uri.endswith("?mode=ro")
        for c in connections
    )


@pytest.mark.parametrize(
    "handle,stage",
    [(3, "PARENT_COMBINED_VOLUME_POLICY"), (4, "PARENT_COMBINED_HOST_POLICY")],
)
@pytest.mark.parametrize(
    "change",
    [
        {"filesystem": "ReFS"},
        {"reparse": True},
        {"owner_sid": "other"},
        {"aces": (("other", 0xD0046, 0, 0),)},
    ],
)
def test_combined_exact_policy_rejection_closes_partial_handles(
    admitted, monkeypatch, handle, stage, change
):
    opened = read_only.open_directory

    def altered(path):
        value = opened(path)
        if value == handle:
            admitted.snapshots[value] = (replace(admitted.good, **change), SECRET)
        return value

    monkeypatch.setattr(read_only, "open_directory", altered)
    assert_result(operator.diagnose(admitted.path), stage)
    assert Counter(admitted.opened) == Counter(admitted.closed)


@pytest.mark.parametrize(
    "mutation",
    [
        "accepted",
        "arguments",
        "relative",
        "isolated",
        "bytecode",
        "path",
        "no_pycache",
        "platform",
        "executable",
        "version",
        "python_hash",
        "import",
    ],
)
def test_launcher_all_guards_use_only_fake_runtime_inputs(tmp_path, capsys, mutation):
    import builtins

    own = tmp_path / "own"
    launcher = own / "scripts/run_arch133_parent_policy_diagnostic.py"
    launcher.parent.mkdir(parents=True)
    launcher.touch()
    python = tmp_path / "python.exe"
    python.write_bytes(b"fake executable")
    fake_sys = SimpleNamespace(
        argv=[str(launcher), "--material-file", str(tmp_path / "material.json")],
        flags=SimpleNamespace(isolated=1),
        dont_write_bytecode=True,
        platform="win32",
        executable=str(python),
        version_info=(3, 14, 3),
        pycache_prefix=None,
        path=[],
    )
    current = SimpleNamespace(hash=admission.binding.PRODUCTION_PYTHON_SHA256)
    calls = []
    if mutation == "arguments":
        fake_sys.argv = [str(launcher)]
    elif mutation == "relative":
        fake_sys.argv[-1] = "relative.json"
    elif mutation == "isolated":
        fake_sys.flags.isolated = 0
    elif mutation == "bytecode":
        fake_sys.dont_write_bytecode = False
    elif mutation == "path":
        launcher = tmp_path / "wrong/scripts/launcher.py"
    elif mutation == "no_pycache":
        (own / "no-pycache").mkdir()
    elif mutation == "platform":
        fake_sys.platform = "linux"
    elif mutation == "executable":
        fake_sys.executable = str(own)
    elif mutation == "version":
        fake_sys.version_info = (3, 14, 4)
    elif mutation == "python_hash":
        current.hash = "b" * 64

    def fake_path(value):
        # Map only the frozen host identities to temporary test inputs.
        if str(value) == str(admission.SOURCE_ROOT):
            return own
        if str(value) == str(admission.binding.PRODUCTION_PYTHON):
            return python
        return Path(value)

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sys":
            return fake_sys
        if name == "pathlib":
            return SimpleNamespace(Path=fake_path)
        if name == "hashlib":

            def sha256(raw):
                assert raw == b"fake executable"
                return SimpleNamespace(hexdigest=lambda: current.hash)

            return SimpleNamespace(sha256=sha256)
        if name == "trading_bot.arch133_parent_policy_diagnostic.operator":
            if mutation == "import":
                fail()
            return SimpleNamespace(main=lambda: calls.append(1) or 0)
        return builtins.__import__(name, globals, locals, fromlist, level)

    source = (ROOT / "scripts/run_arch133_parent_policy_diagnostic.py").read_text(
        encoding="utf-8"
    )
    scope = {
        "__name__": "__main__",
        "__file__": str(launcher),
        "__builtins__": {**vars(builtins), "__import__": fake_import},
    }
    with pytest.raises(SystemExit) as error:
        exec(compile(source, str(launcher), "exec"), scope)
    output = capsys.readouterr()
    if mutation == "accepted":
        assert error.value.code == 0 and calls == [1]
        assert fake_sys.pycache_prefix == str(own / "no-pycache")
        assert fake_sys.path == [str(own / "src")]
        assert not (own / "no-pycache").exists()
        assert output.out == output.err == ""
    else:
        assert error.value.code == 3 and not calls
        assert_result(json.loads(output.out), "PREDECESSOR_RUNTIME")
        assert output.err == "" and SECRET not in output.out


VOLUME_ACCEPT = (0x2, 0x4, 0x10, 0x100, 0x10000, 0x1200A9, 0x1301BF)
VOLUME_REJECT = (
    0x40,
    0x40000,
    0x80000,
    0x80000000,
    0x40000000,
    0x20000000,
    0x10000000,
    0x200,
    0x200000,
    1 << 32,
)


def accepted_volume_contract(observation):
    # Test-only independent oracle; never imported by production Architecture 133.
    from trading_bot.runtime import personal_desktop_paper_account_security as accepted

    inspection = accepted.SecurityInspection(
        "F:\\",
        "F:\\",
        accepted.AuthorityObjectKind.DIRECTORY,
        observation.owner_sid,
        observation.protected,
        tuple(
            accepted.SecurityAce(sid, mask, kind, flags)
            for sid, mask, kind, flags in observation.aces
        ),
        False,
        "F:\\",
        "NTFS",
    )
    accepted._require_parent_security(inspection, accepted.PaperObjectRole.VOLUME)


@pytest.mark.parametrize(
    "mask,allowed",
    [
        *((mask, True) for mask in VOLUME_ACCEPT),
        *((mask, False) for mask in VOLUME_REJECT),
    ],
)
@pytest.mark.parametrize("flags", [0, 1, 2, 3, 0x10, 0x13])
def test_volume_concrete_rights_equivalent_to_accepted_contract(
    parents, mask, allowed, flags
):
    observation = replace(
        parents.good, aces=(*read_only.ADMIN_ACES, ("S-1-5-11", mask, 0, flags))
    )
    for predicate in (
        accepted_volume_contract,
        lambda value: namespace.require_parent_policy(namespace.PARENTS[0], value),
    ):
        if allowed:
            predicate(observation)
        else:
            with pytest.raises(
                ValueError
                if predicate is not accepted_volume_contract
                else AuthoritySecurityError
            ):
                predicate(observation)


@pytest.mark.parametrize(
    "kind,flags,allowed",
    [
        (0, 0x09, True),
        (0, 0x0A, True),
        (0, 0x0B, True),
        (0, 0x19, True),
        (0, 0x1A, True),
        (0, 0x1B, True),
        (0, 0x08, False),
        (0, 0x18, False),
        (0, 0x04, False),
        (0, 0x0D, False),
        (0, 0x20, False),
        (0, 0x40, False),
        (0, 0x80, False),
        (0, 0x100, False),
        (0, -1, False),
        (1, 0, False),
        (2, 0, False),
        (5, 0x09, False),
    ],
)
@pytest.mark.parametrize(
    "sid", ["S-1-5-11", read_only.ADMINISTRATORS_SID, read_only.SYSTEM_SID]
)
def test_volume_type_and_inherit_only_flag_equivalence(
    parents, kind, flags, allowed, sid
):
    observation = replace(
        parents.good, aces=(*read_only.ADMIN_ACES, (sid, 0xFFFFFFFF, kind, flags))
    )
    for predicate in (
        accepted_volume_contract,
        lambda value: namespace.require_parent_acl(namespace.PARENTS[0], value),
    ):
        if allowed:
            predicate(observation)
        else:
            with pytest.raises(
                ValueError
                if predicate is not accepted_volume_contract
                else AuthoritySecurityError
            ):
                predicate(observation)


@pytest.mark.parametrize("sid", [read_only.ADMINISTRATORS_SID, read_only.SYSTEM_SID])
def test_volume_trusted_effective_aces_exempt_from_rights_filter(parents, sid):
    namespace.require_parent_acl(
        namespace.PARENTS[0], replace(parents.good, aces=((sid, 0xFFFFFFFF, 0, 0),))
    )


@pytest.mark.parametrize("mask", [*VOLUME_ACCEPT, *VOLUME_REJECT, 0, 0xD0046])
@pytest.mark.parametrize("flags", [0, 3, 8, 9, 0xFF])
@pytest.mark.parametrize("kind", [0, 1])
def test_host_parent_predicate_equivalent_to_frozen_133s(parents, mask, flags, kind):
    from trading_bot.arch133_parent_security_diagnostic import operator as consumed

    observation = replace(parents.good, aces=(("other", mask, kind, flags),))
    expected = not (not flags & 8 and mask & 0xD0046)
    for predicate in (
        consumed._acl,
        lambda value: namespace.require_parent_acl(namespace.PARENTS[1], value),
    ):
        if expected:
            predicate(observation)
        else:
            with pytest.raises(ValueError):
                predicate(observation)


@pytest.mark.parametrize("bit", [0x2, 0x4, 0x40, 0x10000, 0x40000, 0x80000])
def test_host_parent_each_frozen_rejection_bit_unchanged(parents, bit):
    with pytest.raises(ValueError):
        namespace.require_parent_policy(
            namespace.PARENTS[1], replace(parents.good, aces=(("other", bit, 0, 0),))
        )


@pytest.mark.parametrize("change", [None, "volume", "host", "body"])
def test_production_parent_guard_roles_held_handles_reobservation_cleanup(
    parents, change
):
    original_open = read_only.open_directory

    def opened(path):
        handle = original_open(path)
        if path == namespace.PARENTS[0]:
            parents.snapshots[handle] = (
                replace(
                    parents.good,
                    aces=(*read_only.ADMIN_ACES, ("other", 0x1301BF, 0, 0)),
                ),
                "volume",
            )
        return handle

    # All opens/observations/closes use the fixture, never a host ACL read.
    from unittest.mock import patch

    with patch.object(read_only, "open_directory", opened):

        def guarded():
            with namespace.parent_guard() as facts:
                assert parents.live == {1, 2}
                assert tuple(facts) == namespace.PARENTS
                if change == "body":
                    raise ValueError("guard body")
                if change:
                    handle = 1 if change == "volume" else 2
                    observation, _ = parents.snapshots[handle]
                    parents.snapshots[handle] = observation, "changed"

        if change:
            with pytest.raises(ValueError):
                guarded()
        else:
            guarded()
            assert parents.observations[-2:] == [
                (1, frozenset({1, 2})),
                (2, frozenset({1, 2})),
            ]
    assert parents.closed == [2, 1]
    assert not parents.live


@pytest.mark.parametrize("mask", VOLUME_ACCEPT)
def test_success_diagnostic_uses_corrected_volume_policy(admitted, monkeypatch, mask):
    opened = read_only.open_directory

    def altered(path):
        handle = opened(path)
        if path == namespace.PARENTS[0]:
            admitted.snapshots[handle] = (
                replace(
                    admitted.good, aces=(*read_only.ADMIN_ACES, ("other", mask, 0, 0))
                ),
                "volume",
            )
        return handle

    monkeypatch.setattr(read_only, "open_directory", altered)
    assert_result(operator.diagnose(admitted.path), "ADMISSION_COMPLETE", True)
    assert admitted.closed == [1, 2, 4, 3]


def test_successor_predecessor_admission_is_independent_and_source_equivalent():
    old = ast.parse(
        (
            ROOT / "src/trading_bot/arch133_parent_security_diagnostic/admission.py"
        ).read_text(encoding="utf-8")
    )
    new = ast.parse(
        (
            ROOT / "src/trading_bot/arch133_parent_policy_diagnostic/admission.py"
        ).read_text(encoding="utf-8")
    )

    def functions(tree):
        return {
            node.name: ast.dump(node, include_attributes=False)
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }

    assert functions(old) == functions(new)
    assert admission.SOURCE_BRANCH.endswith("133t")
    assert "133t" in str(admission.SOURCE_ROOT)


@pytest.mark.parametrize("path", namespace.PARENTS)
@pytest.mark.parametrize(
    "field,value",
    [
        ("filesystem", "ntfs"),
        ("filesystem", "ReFS"),
        ("reparse", True),
        ("owner_sid", read_only.SYSTEM_SID),
        ("owner_sid", "other"),
    ],
)
def test_production_parent_metadata_rejections_preserved(parents, path, field, value):
    with pytest.raises(ValueError):
        namespace.require_parent_policy(path, replace(parents.good, **{field: value}))


@pytest.mark.parametrize("path", namespace.PARENTS)
def test_production_guard_policy_failure_closes_acquired_handles(
    parents, monkeypatch, path
):
    opened = read_only.open_directory

    def altered(current):
        handle = opened(current)
        if current == path:
            parents.snapshots[handle] = (
                replace(parents.good, aces=(("other", 0x40, 0, 0),)),
                "fake",
            )
        return handle

    monkeypatch.setattr(read_only, "open_directory", altered)
    with pytest.raises(ValueError):
        with namespace.parent_guard():
            pytest.fail("rejected policy entered guarded interval")
    assert Counter(parents.opened) == Counter(parents.closed)
    assert not parents.live


def test_parent_role_is_fixed(parents):
    with pytest.raises(ValueError):
        namespace.require_parent_policy("G:\\", parents.good)


def test_host_metadata_predicate_retains_frozen_truthiness(parents):
    namespace.require_parent_policy(
        namespace.PARENTS[1], replace(parents.good, reparse=0)
    )
    with pytest.raises(ValueError):
        namespace.require_parent_policy(
            namespace.PARENTS[0], replace(parents.good, reparse=0)
        )
