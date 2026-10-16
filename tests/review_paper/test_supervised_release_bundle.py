"""Fake images and temporary development Git roots only; no production observer."""

import ast
import hashlib
import json
import subprocess
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner
from scripts import run_test_certification as certification
from trading_bot.strategies import MovingAverageCrossoverConfig
from trading_bot.supervised_release import (
    DURABLE_DATA_ROOT,
    LAUNCHER_RELATIVE_PATH,
    STRATEGY_ID,
    ReleaseInventoryEntry,
    ReleaseManifest,
    collector,
)
from trading_bot.supervised_release.binding import RuntimeBinding
from trading_bot.supervised_release.bundle import (
    ReleaseBundle,
    ReleaseFile,
    source_namespace,
    verify_release_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
NAME = "arch133-robinhood-supervised-release-build-verification"
MATERIAL = {
    "pyproject.toml": b"[project]\nname='fake'\n",
    LAUNCHER_RELATIVE_PATH: b"# inert test launcher\n",
    "src/trading_bot/__init__.py": b"# fake package\n",
    "src/trading_bot/nested/model.py": b"# fake model\n",
    "src/trading_bot/nested/schema.json": b"{}\n",
    "src/trading_bot/nested/schema.sql": b"-- fake schema\n",
}


def declaration(head="a" * 40, tree="b" * 40):
    return ReleaseManifest(
        source_head=head,
        source_tree=tree,
        production_python_version="3.14.3",
        production_python_sha256="c" * 64,
        launcher_relative_path=LAUNCHER_RELATIVE_PATH,
        launcher_sha256=hashlib.sha256(MATERIAL[LAUNCHER_RELATIVE_PATH]).hexdigest(),
        source_inventory=tuple(
            ReleaseInventoryEntry(name, hashlib.sha256(data).hexdigest())
            for name, data in sorted(MATERIAL.items())
        ),
        strategy_id=STRATEGY_ID,
        strategy_version="1.0.0",
        strategy_config=MovingAverageCrossoverConfig(5, 20, Decimal("1.00")),
        risk_policy_id="reviewed-policy",
        risk_policy_version="1.0.0",
        risk_policy_sha256="d" * 64,
    )


def image(manifest=None):
    manifest = manifest or declaration()
    files = [ReleaseFile(name, data) for name, data in MATERIAL.items()]
    files.append(ReleaseFile("manifest.json", manifest.to_json().encode()))
    return ReleaseBundle(tuple(sorted(files, key=lambda item: item.relative_path)))


def verified(bundle=None, **pins):
    original = image()
    manifest = next(
        item for item in original.files if item.relative_path == "manifest.json"
    )
    return verify_release_bundle(
        bundle or original,
        **(
            {
                "expected_manifest_sha256": manifest.sha256,
                "expected_source_head": "a" * 40,
                "expected_source_tree": "b" * 40,
                "expected_source_paths": tuple(sorted(MATERIAL)),
            }
            | pins
        ),
    )


def change_file(bundle, name, data):
    return ReleaseBundle(
        tuple(
            replace(item, data=data) if item.relative_path == name else item
            for item in bundle.files
        )
    )


def git(root, *args):
    return (
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )


@pytest.fixture
def checkout(tmp_path):
    for name, data in MATERIAL.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for name in (
        "docs/note.md",
        "tests/test_fake.py",
        "scripts/unrelated.py",
        "README.md",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# excluded\n")
    (tmp_path / ".gitignore").write_text("__pycache__/\n*.db\n.env\n")
    git(tmp_path, "init")
    git(tmp_path, "config", "core.autocrlf", "false")
    git(tmp_path, "config", "user.name", "Source Test")
    git(tmp_path, "config", "user.email", "source-test@example.invalid")
    git(
        tmp_path,
        "add",
        "--",
        *MATERIAL,
        "docs/note.md",
        "tests/test_fake.py",
        "scripts/unrelated.py",
        "README.md",
        ".gitignore",
    )
    git(tmp_path, "commit", "-m", "fake source")
    return tmp_path, declaration(
        git(tmp_path, "rev-parse", "HEAD"), git(tmp_path, "rev-parse", "HEAD^{tree}")
    )


def test_complete_collection_sorted_exact_bytes_and_binding(checkout):
    root, declared = checkout
    result = collector.collect_release_bundle(root, declaration=declared)
    assert tuple(item.relative_path for item in result.bundle.files) == tuple(
        sorted((*MATERIAL, "manifest.json"))
    )
    assert result.manifest.source_inventory == declared.source_inventory
    assert result == collector.collect_release_bundle(root, declaration=declared)
    for item in result.bundle.files:
        if item.relative_path != "manifest.json":
            assert item.data == MATERIAL[item.relative_path]
    assert git(root, "status", "--porcelain") == ""
    assert not (root / "manifest.json").exists()
    binding = RuntimeBinding(result)
    material = binding.to_dict()
    assert material["dependency_closure"] == "UNPROVEN"
    assert material["durable_data_root"] == DURABLE_DATA_ROOT
    assert material["release_root"].startswith("F:\\AITradingBot\\releases\\release-")
    assert not material["release_root"].startswith(DURABLE_DATA_ROOT)
    assert (
        RuntimeBinding.from_json(binding.to_json(), verified_release=result) == binding
    )
    assert binding.sha256 == hashlib.sha256(binding.to_json().encode()).hexdigest()
    for field in (
        "strategy_id",
        "strategy_version",
        "strategy_config_sha256",
        "risk_policy_id",
        "risk_policy_version",
        "risk_policy_sha256",
    ):
        assert material[field] == getattr(declared, field)


@pytest.mark.parametrize("field", ["source_head", "source_tree", "launcher_sha256"])
def test_wrong_source_or_launcher(checkout, field):
    root, declared = checkout
    with pytest.raises(ValueError):
        collector.collect_release_bundle(
            root,
            declaration=replace(
                declared,
                **(
                    {field: "f" * 40}
                    if field != "launcher_sha256"
                    else {
                        field: "f" * 64,
                        "source_inventory": tuple(
                            replace(entry, sha256="f" * 64)
                            if entry.relative_path == LAUNCHER_RELATIVE_PATH
                            else entry
                            for entry in declared.source_inventory
                        ),
                    }
                ),
            ),
        )


@pytest.mark.parametrize("dirty", ["tracked", "index", "untracked", "missing", "extra"])
def test_dirty_checkout_rejected(checkout, dirty):
    root, declared = checkout
    path = root / "src/trading_bot/nested/model.py"
    if dirty == "missing":
        path.unlink()
    elif dirty in {"tracked", "index"}:
        path.write_bytes(b"# changed\n")
        if dirty == "index":
            git(root, "add", "src/trading_bot/nested/model.py")
    else:
        (
            root / ("src/trading_bot/new.py" if dirty == "extra" else "unexpected.txt")
        ).write_text("extra")
    with pytest.raises(ValueError, match="dirty"):
        collector.collect_release_bundle(root, declaration=declared)


@pytest.mark.parametrize("name", ["src/trading_bot/.env", "src/trading_bot/state.db"])
def test_ignored_unsupported_state_is_rejected_before_read(checkout, monkeypatch, name):
    root, declared = checkout
    (root / name).write_bytes(b"must not be read")
    monkeypatch.setattr(
        collector, "_read", lambda *a: pytest.fail("unsupported material read")
    )
    with pytest.raises(ValueError):
        collector.collect_release_bundle(root, declaration=declared)


def test_cache_excluded(checkout):
    root, declared = checkout
    cache = root / "src/trading_bot/__pycache__"
    cache.mkdir()
    (cache / "cached.pyc").write_bytes(b"excluded")
    assert (
        collector.collect_release_bundle(
            root, declaration=declared
        ).manifest.source_inventory
        == declared.source_inventory
    )


@pytest.mark.parametrize("drift", ["head", "tree", "namespace", "bytes"])
def test_before_after_drift(checkout, monkeypatch, drift):
    root, declared = checkout
    if drift in {"head", "tree"}:
        original = collector._state
        calls = 0

        def state(*args):
            nonlocal calls
            calls += 1
            result = original(*args)
            return replace(result, **{drift: "f" * 40}) if calls == 2 else result

        monkeypatch.setattr(collector, "_state", state)
    elif drift == "namespace":
        original = collector._names
        calls = 0

        def names(*args):
            nonlocal calls
            calls += 1
            return original(*args) if calls == 1 else ()

        monkeypatch.setattr(collector, "_names", names)
    else:
        original = collector._read
        calls = 0

        def read(*args):
            nonlocal calls
            calls += 1
            return original(*args) if calls <= len(MATERIAL) else b"drift"

        monkeypatch.setattr(collector, "_read", read)
    with pytest.raises(ValueError, match="drift"):
        collector.collect_release_bundle(root, declaration=declared)


def test_git_blob_byte_drift_even_if_status_is_clean(checkout, monkeypatch):
    root, declared = checkout
    original = collector._git
    (root / "src/trading_bot/nested/model.py").write_bytes(b"hidden drift")
    monkeypatch.setattr(
        collector,
        "_git",
        lambda root, *args, **kwargs: (
            b"" if args[0] == "status" else original(root, *args, **kwargs)
        ),
    )
    with pytest.raises(ValueError, match="Git object"):
        collector.collect_release_bundle(root, declaration=declared)


def test_standard_git_crlf_bytes_are_hashed_exactly(checkout):
    root, declared = checkout
    git(root, "config", "core.autocrlf", "true")
    for name, data in MATERIAL.items():
        (root / name).write_bytes(data.replace(b"\n", b"\r\n"))
    git(root, "add", "--", *MATERIAL)
    assert git(root, "rev-parse", "HEAD^{tree}") == declared.source_tree
    launcher_sha = hashlib.sha256(
        (root / LAUNCHER_RELATIVE_PATH).read_bytes()
    ).hexdigest()
    declared = replace(
        declared,
        launcher_sha256=launcher_sha,
        source_inventory=tuple(
            replace(item, sha256=launcher_sha)
            if item.relative_path == LAUNCHER_RELATIVE_PATH
            else item
            for item in declared.source_inventory
        ),
    )
    result = collector.collect_release_bundle(root, declaration=declared)
    assert next(
        item
        for item in result.bundle.files
        if item.relative_path == LAUNCHER_RELATIVE_PATH
    ).data.endswith(b"\r\n")


@pytest.mark.parametrize(
    "fact",
    [
        {"is_symlink": True},
        {"is_reparse": True},
        {"object_type": "directory"},
        {"object_type": "fifo"},
        {"is_reparse": 1},
    ],
)
def test_supplied_unsafe_object_facts(fact):
    with pytest.raises(ValueError):
        ReleaseFile("pyproject.toml", b"", **fact)


@pytest.mark.parametrize(
    "name",
    [
        "../escape.py",
        "/src/trading_bot/a.py",
        "C:/a.py",
        "src\\trading_bot\\a.py",
        "scripts/other.py",
        "src/other.py",
        "src/trading_bot/a.ps1",
        "src/trading_bot/a.db",
        "src/trading_bot/Arch133/state.json",
        "runtime/python.exe",
        "docs/a.json",
        "src/trading_bot/__pycache__/a.py",
        "src/trading_bot/.git/a.py",
        "src/trading_bot/NUL.py",
    ],
)
def test_unsafe_or_unsupported_names(name):
    with pytest.raises(ValueError):
        ReleaseFile(name, b"")


@pytest.mark.parametrize("bad", ["duplicate", "case_alias", "unsorted"])
def test_inventory_name_alias_and_order(bad):
    paths = list(sorted(MATERIAL))
    if bad == "duplicate":
        paths.append(paths[-1])
    elif bad == "case_alias":
        paths.append("src/trading_bot/nested/MODEL.py")
    else:
        paths.reverse()
    with pytest.raises(ValueError):
        source_namespace(tuple(paths))


def test_canonical_bundle_round_trip():
    bundle = image()
    assert ReleaseBundle.from_json(bundle.to_json()) == bundle
    assert verified(ReleaseBundle.from_json(bundle.to_json())).manifest == declaration()
    for raw in (
        " " + bundle.to_json(),
        json.dumps(json.loads(bundle.to_json()), indent=2),
        bundle.to_json().replace('"schema":', '"schema":"injected","schema":'),
    ):
        with pytest.raises(ValueError):
            ReleaseBundle.from_json(raw)


@pytest.mark.parametrize("name", list(MATERIAL))
def test_every_source_byte_tamper(name):
    with pytest.raises(ValueError):
        verified(change_file(image(), name, b"changed"))


@pytest.mark.parametrize(
    "tamper",
    [
        "missing",
        "extra",
        "manifest",
        "noncanonical",
        "inventory_sha",
        "inventory_entry",
        "launcher_sha",
        "source_head",
        "source_tree",
    ],
)
def test_bundle_tamper(tamper):
    original = image()
    if tamper == "missing":
        bad = ReleaseBundle(
            tuple(
                item
                for item in original.files
                if item.relative_path != "src/trading_bot/nested/model.py"
            )
        )
    elif tamper == "extra":
        bad = ReleaseBundle(
            tuple(
                sorted(
                    (
                        *original.files,
                        ReleaseFile("src/trading_bot/extra.py", b"extra"),
                    ),
                    key=lambda item: item.relative_path,
                )
            )
        )
    else:
        raw = json.loads(declaration().to_json())
        if tamper == "noncanonical":
            text = json.dumps(raw, indent=2)
        else:
            key = {
                "manifest": "release_id",
                "inventory_sha": "source_inventory_sha256",
                "launcher_sha": "launcher_sha256",
            }.get(tamper, tamper)
            if tamper == "inventory_entry":
                raw["source_inventory"][0]["sha256"] = "f" * 64
            else:
                raw[key] = "f" * (
                    40
                    if key.startswith("source_")
                    and key in {"source_head", "source_tree"}
                    else 64
                )
            text = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        bad = change_file(original, "manifest.json", text.encode())
    with pytest.raises(ValueError):
        verified(bad)
    if tamper not in {"missing", "extra"}:
        # Even a caller rebinding the artifact hash cannot hide invalid manifest
        # derived identities or noncanonical encoding.
        with pytest.raises(ValueError):
            verified(
                bad, expected_manifest_sha256=hashlib.sha256(text.encode()).hexdigest()
            )


@pytest.mark.parametrize(
    "pin",
    [
        "expected_source_head",
        "expected_source_tree",
        "expected_manifest_sha256",
        "expected_source_paths",
    ],
)
def test_independent_authority_pins(pin):
    value = (
        tuple(sorted((*MATERIAL, "src/trading_bot/missing.py")))
        if pin.endswith("paths")
        else "f" * (64 if pin.endswith("sha256") else 40)
    )
    with pytest.raises(ValueError):
        verified(**{pin: value})


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "release_id",
        "manifest_sha256",
        "source_head",
        "source_tree",
        "source_inventory_sha256",
        "production_python_version",
        "production_python_sha256",
        "launcher_relative_path",
        "launcher_sha256",
        "strategy_id",
        "strategy_version",
        "strategy_config_sha256",
        "risk_policy_id",
        "risk_policy_version",
        "risk_policy_sha256",
        "release_root",
        "durable_data_root",
        "dependency_closure",
    ],
)
def test_every_binding_field_tamper(field):
    release = verified()
    binding = RuntimeBinding(release)
    raw = binding.to_dict()
    raw[field] = "TAMPER"
    with pytest.raises(ValueError):
        RuntimeBinding.from_json(
            json.dumps(raw, sort_keys=True, separators=(",", ":")),
            verified_release=release,
        )


def test_binding_extra_missing_noncanonical_and_unverified():
    release = verified()
    binding = RuntimeBinding(release)
    for text in (
        binding.to_json() + "\n",
        "{}",
        binding.to_json().replace('"schema":', '"extra":0,"schema":'),
    ):
        with pytest.raises(ValueError):
            RuntimeBinding.from_json(text, verified_release=release)
    with pytest.raises(ValueError):
        RuntimeBinding(image())


@pytest.mark.parametrize(
    "field,value",
    [
        ("strategy_version", "2.0.0"),
        ("strategy_config", MovingAverageCrossoverConfig(6, 21, Decimal("2"))),
        ("risk_policy_id", "changed-policy"),
        ("risk_policy_version", "2.0.0"),
        ("risk_policy_sha256", "f" * 64),
    ],
)
def test_reviewed_strategy_and_risk_change_propagation(field, value):
    declared = replace(declaration(), **{field: value})
    bundle = image(declared)
    manifest_file = next(
        item for item in bundle.files if item.relative_path == "manifest.json"
    )
    release = verified(bundle, expected_manifest_sha256=manifest_file.sha256)
    binding = RuntimeBinding(release)
    assert (
        binding.to_dict()["release_id"]
        == declared.release_id
        != declaration().release_id
    )
    digest_field = "strategy_config_sha256" if field == "strategy_config" else field
    assert binding.to_dict()[digest_field] == getattr(declared, digest_field)
    assert binding.to_dict()["dependency_closure"] == "UNPROVEN"


def test_source_only_registration_and_profiles(tmp_path, monkeypatch):
    spec = runner._checkpoint_specs()[NAME]
    assert spec.preflight is spec.execute is spec.remote_head_env is None
    assert (
        spec.remote_branch == "feature/robinhood-supervised-release-build-verification"
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(NAME) == 1
    assert runner._supervised_release_bundle_authority_check(ROOT) == ()
    inventory = certification.discover_inventory(ROOT)
    module = "tests/review_paper/test_supervised_release_bundle.py"
    for profile in ("full", "robinhood", "exhaustive"):
        assert module in certification.select_inventory(inventory, profile)
    assert module not in certification.select_inventory(inventory, "legacy")
    monkeypatch.setattr(runner, "_git_state", lambda *a: pytest.fail("host access"))
    for function in (runner.preflight_checkpoint, runner.execute_checkpoint):
        with pytest.raises(RuntimeError):
            function(spec, repo_root=tmp_path, evidence_root=tmp_path / "evidence")


@pytest.mark.parametrize(
    "change",
    [
        {"preflight": lambda: None},
        {"execute": lambda: None},
        {"remote_head_env": "INJECTED"},
        {"remote_branch": "wrong"},
        {"tests": ()},
        {"ruff_paths": ()},
    ],
)
def test_registration_drift(monkeypatch, change):
    specs = runner._checkpoint_specs()
    specs[NAME] = replace(specs[NAME], **change)
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert runner._supervised_release_bundle_authority_check(ROOT)


def test_pure_modules_and_collector_have_no_effect_capabilities():
    for module in ("bundle", "binding", "collector"):
        tree = ast.parse(
            (ROOT / f"src/trading_bot/supervised_release/{module}.py").read_text(
                encoding="utf-8-sig"
            )
        )
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module]
                )
                assert not any(
                    any(
                        word in name
                        for word in (
                            "scheduler",
                            "credential",
                            "oauth",
                            "provider",
                            "broker",
                            "review_paper",
                            "ctypes",
                            "winreg",
                        )
                    )
                    for name in names
                )
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                assert name not in {
                    "write_text",
                    "write_bytes",
                    "mkdir",
                    "unlink",
                    "rename",
                    "replace",
                    "system",
                    "Popen",
                    "eval",
                    "exec",
                } - {"replace"}
                if module != "collector":
                    assert name not in {
                        "open",
                        "run",
                        "read_text",
                        "read_bytes",
                        "resolve",
                        "lstat",
                    }


def test_no_production_or_scratch_access_before_admission(monkeypatch):
    monkeypatch.setattr(
        collector, "_fact", lambda *a, **kw: pytest.fail("protected filesystem access")
    )
    for root in (
        "F:/AITradingBot/releases",
        "F:/AITradingBot/Arch133",
        "F:/AI/temp/arch133y-rename-qualification",
        "F:/AI/temp/arch133y-rename-qualification/child",
        "F:/AI/temp/arch133z-rename-qualification",
        "F:/AI/temp/arch133z-rename-qualification/child",
        "Y:/scratch",
        "Z:/scratch",
    ):
        # Reject protected roots lexically before the first filesystem observation.
        with pytest.raises(ValueError):
            collector.collect_release_bundle(Path(root), declaration=declaration())


@pytest.mark.parametrize("fact", ["symlink", "reparse", "wrong_type"])
def test_collector_rejects_source_object_facts_before_read(checkout, monkeypatch, fact):
    import stat
    from types import SimpleNamespace

    root, declared = checkout
    target = root / "src/trading_bot/nested"
    original = Path.lstat

    def lstat(path):
        if path == target:
            return SimpleNamespace(
                st_mode=stat.S_IFLNK
                if fact == "symlink"
                else stat.S_IFDIR
                if fact == "reparse"
                else stat.S_IFIFO,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
                if fact == "reparse"
                else 0,
            )
        return original(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(
        collector, "_read", lambda *args: pytest.fail("unsafe source read")
    )
    with pytest.raises(ValueError, match="object type"):
        collector.collect_release_bundle(root, declaration=declared)


def test_collector_rejects_ignored_source_namespace_drift(checkout):
    root, declared = checkout
    (root / ".git/info/exclude").write_text("src/trading_bot/extra.py\n")
    (root / "src/trading_bot/extra.py").write_bytes(b"ignored extra")
    assert git(root, "status", "--porcelain") == ""
    with pytest.raises(ValueError, match="namespace drift"):
        collector.collect_release_bundle(root, declaration=declared)


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_hidden_index_flags_rejected(checkout, flag):
    root, declared = checkout
    git(root, "update-index", flag, "src/trading_bot/nested/model.py")
    with pytest.raises(ValueError, match="index flags"):
        collector.collect_release_bundle(root, declaration=declared)


def test_external_git_filters_rejected_before_status(checkout, monkeypatch):
    root, declared = checkout
    (root / ".git/info/attributes").write_text("*.py filter=blocked\n")
    original = collector._git

    def local_git(root, *args, **kwargs):
        assert args[0] != "status", "active source filter reached Git status"
        return original(root, *args, **kwargs)

    monkeypatch.setattr(collector, "_git", local_git)
    with pytest.raises(ValueError, match="filters"):
        collector.collect_release_bundle(root, declaration=declared)


def test_source_byte_budgets(checkout, monkeypatch):
    root, declared = checkout
    monkeypatch.setattr(collector, "MAX_FILE_BYTES", 1)
    with pytest.raises(ValueError, match="byte budget"):
        collector.collect_release_bundle(root, declaration=declared)


@pytest.mark.parametrize(
    "tamper",
    [
        "duplicate",
        "case_alias",
        "manifest_alias",
        "object_type",
        "is_reparse",
        "is_symlink",
        "unknown_field",
        "invalid_base64",
    ],
)
def test_bundle_transport_facts_and_namespace_tamper(tamper):
    raw = json.loads(image().to_json())
    if tamper == "duplicate":
        raw["files"].append(raw["files"][-1])
    elif tamper == "case_alias":
        extra = dict(raw["files"][-1])
        extra["relative_path"] = extra["relative_path"].replace(
            "schema.sql", "SCHEMA.sql"
        )
        raw["files"].append(extra)
    elif tamper == "manifest_alias":
        raw["files"][0]["relative_path"] = "MANIFEST.json"
    elif tamper == "unknown_field":
        raw["files"][0]["unknown"] = "injected"
    elif tamper == "invalid_base64":
        raw["files"][0]["data_base64"] = "!"
    else:
        raw["files"][0][tamper] = "directory" if tamper == "object_type" else True
    with pytest.raises(ValueError):
        ReleaseBundle.from_json(json.dumps(raw, sort_keys=True, separators=(",", ":")))


@pytest.mark.parametrize(
    "mutation", ["missing", "source_bytes", "native_import", "write", "workflow"]
)
def test_source_and_workflow_boundary_drift(tmp_path, mutation):
    paths = (
        *runner.SUPERVISED_RELEASE_SOURCES,
        *runner.SUPERVISED_RELEASE_BUNDLE_SOURCES,
        ".github/workflows/checkpoint-source-gates.yml",
    )
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    target = tmp_path / "src/trading_bot/supervised_release/collector.py"
    if mutation == "missing":
        target.unlink()
    elif mutation == "workflow":
        workflow = tmp_path / ".github/workflows/checkpoint-source-gates.yml"
        workflow.write_text(workflow.read_text().replace(NAME, "unregistered"))
    else:
        addition = {
            "source_bytes": "# drift\n",
            "native_import": "import ctypes\n",
            "write": "Path('forbidden').write_bytes(b'effect')\n",
        }[mutation]
        target.write_text(target.read_text() + addition)
    assert runner._supervised_release_bundle_authority_check(tmp_path)


def test_partial_promisor_checkout_cannot_fetch_source(checkout, monkeypatch):
    root, declared = checkout
    git(root, "config", "remote.fake.promisor", "true")
    original = collector._git

    def local_git(root, *args, **kwargs):
        assert args[0] not in {"status", "cat-file"}, (
            "partial checkout reached source objects"
        )
        return original(root, *args, **kwargs)

    monkeypatch.setattr(collector, "_git", local_git)
    with pytest.raises(ValueError, match="partial/promisor"):
        collector.collect_release_bundle(root, declaration=declared)
