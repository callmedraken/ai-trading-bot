from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner
from scripts import current_source_authority as current
from scripts import source_authority as ownership

ROOT = Path(runner.__file__).resolve().parents[1]


def test_classification_has_one_current_owner_and_preserves_security_evidence():
    assert (
        ownership.classify_path("tests/runtime/checkpoint_runner/test_core.py")
        is ownership.PinClass.CURRENT_MUTABLE
    )
    assert (
        ownership.current_owner("tests/runtime/checkpoint_runner/test_core.py")
        == "checkpoint_runner"
    )
    assert (
        ownership.current_owner("tests/scripts/certification_runner/test_profiles.py")
        == "certification"
    )
    assert (
        ownership.current_owner(".github/workflows/checkpoint-source-gates.yml")
        == "ci_workflow"
    )
    assert (
        ownership.classify_path(
            "src/trading_bot/supervised_release/deployment_admission.py"
        )
        is ownership.PinClass.SECURITY_SEMANTIC
    )
    assert (
        ownership.classify_path("docs/history/incident.json")
        is ownership.PinClass.INCIDENT_EVIDENCE
    )
    assert (
        ownership.classify_path("docs/architecture/134-old-contract.md")
        is ownership.PinClass.IMMUTABLE_HISTORICAL
    )
    assert (
        ownership.classify_path(
            "tests/runtime/checkpoint_runner/fixtures/integration_746_authority_failures.json"
        )
        is ownership.PinClass.INCIDENT_EVIDENCE
    )
    assert (
        ownership.current_owner("scripts/current_source_authority.py")
        == "checkpoint_runner"
    )
    for symbol in (
        "PREPUBLICATION_INFRASTRUCTURE_COHERENCE_TESTS",
        "PREPUBLICATION_INFRASTRUCTURE_PATHS",
        "PREPUBLICATION_INFRASTRUCTURE_TEST_PREFIXES",
        "_prepublication_admission_tests",
        "_prepublication_requires_infrastructure_coherence",
    ):
        assert ownership.current_owner(symbol) == "checkpoint_runner"
    assert ownership.current_owner("AGENTS.md") == "workflow_coordination"
    assert ownership.current_owner("pyproject.toml") == "certification"
    assert (
        ownership.current_owner("current_preflight_dispatch_failures")
        == "checkpoint_runner"
    )
    assert ownership.current_owner("preflight_checkpoint") == "checkpoint_runner"


def test_current_preflight_chain_and_observer_registration_pass_without_dispatch(
    monkeypatch,
):
    def forbidden(*args, **kwargs):
        pytest.fail("static authority dispatched a host or protected action")

    monkeypatch.setattr(runner, "_PRE_READONLY_PREFLIGHT", forbidden)
    monkeypatch.setattr(runner, "_arch146_partial_state_preflight", forbidden)
    specs = runner._checkpoint_specs()
    assert specs[runner.ARCH146_PARTIAL_STATE_NAME].execute is None
    assert specs[runner.ARCH146_PRE_B2_NAME].preflight is None
    assert specs[runner.ARCH146_PRE_B2_NAME].execute is None
    assert current.current_preflight_dispatch_failures(ROOT) == ()


@pytest.mark.parametrize("revision", ["r2", "r3"])
def test_current_preflight_predecessor_authority_owns_only_its_security(
    monkeypatch, revision
):
    authority = getattr(
        runner, f"_arch134_readonly_diagnostic_{revision}_authority_check"
    )
    assert (
        runner.preflight_checkpoint
        is runner._arch146_partial_state_preflight_checkpoint
    )
    assert authority(ROOT) == ()
    # The predecessor does not own any later outer alias, even a rejected one.
    monkeypatch.setattr(runner, "preflight_checkpoint", lambda *args, **kwargs: None)
    assert authority(ROOT) == ()
    assert (
        "current preflight outer dispatcher drift"
        in current.current_preflight_dispatch_failures(ROOT)
    )


@pytest.mark.parametrize("revision", ["r2", "r3"])
def test_current_preflight_predecessor_registration_remains_exact(
    monkeypatch, revision
):
    name = getattr(runner, f"ARCH134_READONLY_DIAGNOSTIC_{revision.upper()}_NAME")
    authority = getattr(
        runner, f"_arch134_readonly_diagnostic_{revision}_authority_check"
    )
    specs = runner._checkpoint_specs()
    specs[name] = replace(specs[name], preflight=lambda: {})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert f"Diagnostic {revision.upper()} registration drift" in authority(ROOT)
    assert (
        "current preflight registration drift: " + name
        in current.current_preflight_dispatch_failures(ROOT)
    )


@pytest.mark.parametrize("revision", ["r2", "r3"])
@pytest.mark.parametrize("suffix", ["_preflight", "_preflight_checkpoint"])
def test_current_preflight_inner_security_ast_pins_still_fail(
    monkeypatch, revision, suffix
):
    name = f"_arch134_readonly_diagnostic_{revision}{suffix}"
    parse = runner._top_level_functions

    def changed(tree):
        functions = parse(tree)
        functions[name] = copy.deepcopy(functions[name])
        functions[name].body.append(ast.Pass())
        return functions

    monkeypatch.setattr(runner, "_top_level_functions", changed)
    authority = getattr(
        runner, f"_arch134_readonly_diagnostic_{revision}_authority_check"
    )
    assert f"Diagnostic {revision.upper()} dispatch drift: {name}" in authority(ROOT)


@pytest.mark.parametrize(
    "wrapper,old,new,expected",
    [
        (
            "_arch146_partial_state_preflight_checkpoint",
            "_arch134_readonly_diagnostic_r3_preflight_checkpoint(",
            "_arch134_readonly_diagnostic_r2_preflight_checkpoint(",
            "observer routing drift",
        ),
        (
            "_arch134_readonly_diagnostic_r3_preflight_checkpoint",
            "_arch134_readonly_diagnostic_r2_preflight_checkpoint(",
            "_readonly_preflight_checkpoint(",
            "delegation drift",
        ),
        (
            "_arch146_partial_state_preflight_checkpoint",
            "_arch134_readonly_diagnostic_r3_preflight_checkpoint(",
            "_arch146_partial_state_preflight_checkpoint(",
            "observer routing drift",
        ),
        (
            "_arch134_readonly_diagnostic_r3_preflight_checkpoint",
            "return _arch134_readonly_diagnostic_r2_preflight_checkpoint(",
            "return _arch134_readonly_diagnostic_r3_preflight_checkpoint(",
            "delegation drift",
        ),
        (
            "_arch146_partial_state_preflight_checkpoint",
            "spec.name != ARCH146_PARTIAL_STATE_NAME",
            "spec.name != ARCH146_PRE_B2_NAME",
            "observer routing drift",
        ),
        (
            "_arch146_partial_state_preflight_checkpoint",
            "return _PRE_READONLY_PREFLIGHT(",
            "return execute_checkpoint(",
            "observer routing drift",
        ),
        (
            "_arch134_readonly_diagnostic_r2_preflight_checkpoint",
            "return _readonly_preflight_checkpoint(",
            "return _PRE_READONLY_PREFLIGHT(",
            "delegation drift",
        ),
        (
            "_arch134_readonly_diagnostic_r2_preflight",
            "return preflight()",
            "return execute_checkpoint()",
            "security dispatch drift",
        ),
        (
            "_arch134_readonly_diagnostic_r3_preflight",
            "return preflight()",
            "return execute_checkpoint()",
            "security dispatch drift",
        ),
        (
            "_readonly_preflight_checkpoint",
            "return _PRE_READONLY_PREFLIGHT(",
            "return execute_checkpoint(",
            "security dispatch drift",
        ),
    ],
)
def test_current_preflight_structural_owner_rejects_bypass_and_wrong_route(
    tmp_path, wrapper, old, new, expected
):
    source = (ROOT / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    function = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == wrapper
    )
    original = ast.get_source_segment(source, function)
    assert old in original
    modified = original.replace(old, new, 1)
    target = tmp_path / "scripts/checkpoint_runner.py"
    target.parent.mkdir()
    target.write_text(source.replace(original, modified, 1), encoding="utf-8")
    failures = current.current_preflight_dispatch_failures(tmp_path)
    assert any("current preflight " + expected in failure for failure in failures)


def test_current_preflight_global_owner_is_composed_into_current_authority(monkeypatch):
    monkeypatch.setattr(runner, "preflight_checkpoint", lambda *args, **kwargs: {})
    assert (
        "current preflight outer dispatcher drift"
        in current.current_authority_check(ROOT)
    )


@pytest.mark.parametrize(
    "name,field",
    [
        (runner.ARCH146_PARTIAL_STATE_NAME, "execute"),
        (runner.ARCH134_READONLY_DIAGNOSTIC_R1_NAME, "execute"),
        (runner.ARCH134_READONLY_DIAGNOSTIC_R2_NAME, "execute"),
        (runner.ARCH134_READONLY_DIAGNOSTIC_R3_NAME, "execute"),
        (runner.ARCH146_PRE_B2_NAME, "preflight"),
        (runner.ARCH146_PRE_B2_NAME, "execute"),
    ],
)
def test_current_preflight_registration_cannot_gain_effects(monkeypatch, name, field):
    specs = runner._checkpoint_specs()
    specs[name] = replace(specs[name], **{field: lambda: {}})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    failures = current.current_preflight_dispatch_failures(ROOT)
    assert any(
        "registration drift" in failure or "source-only predecessor drift" in failure
        for failure in failures
    )


def test_current_preflight_retains_existing_security_functions_and_pin_maps():
    relative = "scripts/checkpoint_runner.py"
    preserved = subprocess.run(
        ["git", "show", "f49dd2d2ef7eb0944fdc8d91ba0c275fbb65dc40:" + relative],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode()
    current_tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    old_tree = ast.parse(preserved)

    def security_declarations(tree):
        return {
            node.name: ast.dump(node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name
            in {
                "_arch134_readonly_diagnostic_r1_preflight",
                "_arch134_readonly_diagnostic_r2_preflight",
                "_arch134_readonly_diagnostic_r2_preflight_checkpoint",
                "_arch134_readonly_diagnostic_r3_preflight",
                "_arch134_readonly_diagnostic_r3_preflight_checkpoint",
            }
        }

    def pins(tree):
        return [
            ast.dump(node)
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id
            in {
                "ARCH134_READONLY_DIAGNOSTIC_R2_SOURCE_PINS",
                "ARCH134_READONLY_DIAGNOSTIC_R3_SOURCE_PINS",
                "ARCH134_READONLY_DIAGNOSTIC_R2_DISPATCH_PINS",
                "ARCH134_READONLY_DIAGNOSTIC_R3_DISPATCH_PINS",
            }
        ]

    assert security_declarations(current_tree) == security_declarations(old_tree)
    assert len(pins(current_tree)) == 4 and pins(current_tree) == pins(old_tree)


def test_historical_harness_reconstructs_immutable_object_independent_of_current_bytes(
    tmp_path,
):
    relative = "tests/runtime/checkpoint_runner/test_core.py"
    pin = next(
        pin for path, pin in ownership.historical_path_pins(ROOT) if path == relative
    )
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("# a future harness revision\n")
    assert ownership.blob_matches(tmp_path, path, pin)
    assert not ownership.blob_matches(tmp_path, path, "0" * 40)
    other = next(
        pin
        for path, pin in ownership.historical_path_pins(ROOT)
        if path == "docs/AI_DEVELOPMENT_WORKFLOW.md"
    )
    assert not ownership.blob_matches(tmp_path, path, other)


def test_security_source_still_requires_exact_current_bytes(tmp_path):
    path = tmp_path / "src/operator.py"
    path.parent.mkdir()
    data = b"authority = False\n"
    path.write_bytes(data)
    pin = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert ownership.blob_matches(tmp_path, path, pin)
    path.write_text("authority = True\n")
    assert not ownership.blob_matches(tmp_path, path, pin)


@pytest.mark.parametrize("new_hash", [False, True])
def test_new_historical_map_cannot_claim_mutable_current_path(tmp_path, new_hash):
    relative = "tests/runtime/checkpoint_runner/test_core.py"
    pin = next(
        pin for path, pin in ownership.historical_path_pins(ROOT) if path == relative
    )
    if new_hash:
        pin = "0" * 40
    for file in (
        "scripts/checkpoint_runner.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
    ):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / file).read_text())
    path = tmp_path / "scripts/checkpoint_runner.py"
    path.write_text(
        path.read_text() + f'\nNEW_HISTORICAL_PINS: Final = {{"{relative}": "{pin}"}}\n'
    )
    assert any(
        "CURRENT_MUTABLE" in failure
        for failure in ownership.ownership_failures(tmp_path)
    )


def test_historical_map_declarations_and_catalog_preserve_accepted_source():
    assert ownership.ownership_failures(ROOT) == ()
    catalog = ownership.historical_catalog(ROOT)
    assert {
        "execute_checkpoint",
        "preflight_checkpoint",
        "_readonly_preflight_checkpoint",
    }.isdisjoint(catalog["mutable_symbols"])
    for name in (
        "prepublication_admission",
        "_arch134_r3n_prepublication_authority_check",
        "_arch134_d1s1_authority_check",
    ):
        digest = next(iter(catalog["ast_objects"][name]))
        assert ownership.ast_matches(ROOT, name, ast.Pass(), digest)


@pytest.mark.parametrize("relative_dir", ["tests/review_paper", "tests/experiments"])
def test_historical_test_cannot_hash_current_mutable_runner_symbol(
    tmp_path, relative_dir
):
    for file in (
        "scripts/checkpoint_runner.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
    ):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / file).read_text(encoding="utf-8"), encoding="utf-8")
    bad = tmp_path / relative_dir / "test_stale_current.py"
    bad.parent.mkdir(parents=True)
    bad.write_text(
        "import ast\n"
        "import hashlib\n"
        "from pathlib import Path\n"
        "from scripts import checkpoint_runner as runner\n"
        "ROOT = Path(__file__).resolve().parents[2]\n"
        "def test_stale():\n"
        "    tree = ast.parse((ROOT / 'scripts/checkpoint_runner.py').read_text())\n"
        "    functions = {n.name: n for n in tree.body "
        "if isinstance(n, ast.FunctionDef)}\n"
        "    hashlib.sha256("
        "ast.dump(functions['_checkpoint_specs']).encode()).hexdigest()\n",
        encoding="utf-8",
    )
    failures = ownership.ownership_failures(tmp_path)
    assert any(
        "historical test directly compares CURRENT_MUTABLE source" in failure
        for failure in failures
    )


def test_historical_experiment_cannot_hash_current_inventory_pin_targets(tmp_path):
    for file in (
        "scripts/checkpoint_runner.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
    ):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / file).read_text(encoding="utf-8"), encoding="utf-8")
    bad = tmp_path / "tests/experiments/test_stale_current_inventory.py"
    bad.parent.mkdir(parents=True)
    bad.write_text(
        "from pathlib import Path\n"
        "from scripts import checkpoint_runner as runner\n"
        "ROOT = Path(runner.__file__).resolve().parents[1]\n"
        "def test_stale_inventory():\n"
        "    for path, pin in "
        "runner.ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.items():\n"
        "        current = runner._arch143_current_inventory_test_pin(path, pin)\n"
        "        current = runner._arch132_r3i_current_inventory_test_pin("
        "path, current)\n"
        "        assert runner._git_blob_sha1(ROOT / path) == current\n",
        encoding="utf-8",
    )
    failures = ownership.ownership_failures(tmp_path)
    assert any(
        "historical test directly compares CURRENT_MUTABLE source" in failure
        and "tests/experiments/test_stale_current_inventory.py" in failure
        for failure in failures
    )


def test_historical_strategy_cannot_own_current_pins_or_profile_totals(tmp_path):
    for file in (
        "scripts/checkpoint_runner.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
    ):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / file).read_text(encoding="utf-8"), encoding="utf-8")
    bad = tmp_path / "tests/strategies/test_stale_current.py"
    bad.parent.mkdir(parents=True)
    bad.write_text(
        "from pathlib import Path\n"
        "from scripts import checkpoint_runner as runner\n"
        "from scripts import run_test_certification as certification\n"
        "ROOT = Path(runner.__file__).resolve().parents[1]\n"
        "def test_stale_strategy():\n"
        "    for relative, pin in runner.ARCH134_D1R5_TEST_PIN_OVERRIDES.items():\n"
        "        assert runner._git_blob_sha1(ROOT / relative) == pin\n"
        "    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 80\n"
        "    inventory = certification.discover_inventory(ROOT)\n"
        "    profiles = {name: certification.select_inventory(inventory, name) "
        "for name in ('full',)}\n"
        "    assert {name: len(value) for name, value in profiles.items()} == "
        "{'full': 203}\n",
        encoding="utf-8",
    )
    failures = ownership.ownership_failures(tmp_path)
    assert any(
        "tests/strategies/test_stale_current.py" in failure for failure in failures
    )
    assert len(failures) >= 3


def _contexts(monkeypatch, *, develop_red=False):
    state = {
        "head": "a" * 40,
        "tree": "b" * 40,
        "branch": "feature/test-suite-example",
        "porcelain": "",
    }
    monkeypatch.setattr(runner, "_git_state", lambda _: state.copy())
    monkeypatch.setattr(current, "current_authority_check", lambda _: ())
    feature = runner.CheckpointSpec("feature", "source only", (), (), lambda _: ())
    historical = replace(
        feature,
        name="historical",
        authority_check=lambda _: (
            ("deterministic historical red",) if develop_red else ()
        ),
    )
    specs = {s.name: s for s in (feature, historical)}
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    monkeypatch.setattr(runner, "resolve_ci_checkpoint", lambda *_: "feature")
    monkeypatch.setattr(current, "develop_static_checkpoints", lambda _: tuple(specs))
    return state


def test_feature_green_prospective_develop_red_is_rejected_by_general_admission(
    monkeypatch, capsys
):
    _contexts(monkeypatch, develop_red=True)
    monkeypatch.setattr(runner, "_arch132_r3n_admission_authority_check", lambda _: ())
    feature = current.evaluate_source_authority(
        ROOT, publication_context=current.PublicationContext.FEATURE
    )
    assert feature.passed
    failures = runner._arch134_r3n_prepublication_authority_check(ROOT)
    assert any(
        "PROSPECTIVE_DEVELOP" in failure and "deterministic historical red" in failure
        for failure in failures
    )
    output = capsys.readouterr().out
    assert "FEATURE_AUTHORITY=PASS" in output
    assert "PROSPECTIVE_DEVELOP_AUTHORITY=FAIL" in output


def test_coherent_same_source_passes_both_contexts_without_effects(monkeypatch):
    state = _contexts(monkeypatch)

    def forbidden(*args, **kwargs):
        pytest.fail("effect, profile execution or Git mutation attempted")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    monkeypatch.setattr(runner, "preflight_checkpoint", forbidden)
    monkeypatch.setattr(runner, "execute_checkpoint", forbidden)
    from scripts import run_test_certification as certification

    monkeypatch.setattr(certification, "main", forbidden)
    results = [
        current.evaluate_source_authority(ROOT, publication_context=context)
        for context in current.PublicationContext
    ]
    assert all(
        r.passed and r.head == state["head"] and r.tree == state["tree"]
        for r in results
    )
    assert results[0].checkpoints == ("feature",)
    assert results[1].checkpoints == ("feature", "historical")


def test_prospective_source_evaluator_rejects_changed_git_identity(monkeypatch):
    state = _contexts(monkeypatch)

    def mutate(_):
        state["tree"] = "c" * 40
        return ()

    monkeypatch.setattr(current, "current_authority_check", mutate)
    result = current.evaluate_source_authority(
        ROOT, publication_context=current.PublicationContext.PROSPECTIVE_DEVELOP
    )
    assert result.failures == ("authority evaluation changed candidate Git state",)


def test_actual_develop_static_routing_and_local_prospective_authority_are_identical():
    workflow = (ROOT / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert "-File .\\ops.ps1 verify-batch @Checkpoints" in workflow
    assert "$env:AI_TRADING_BOT_ACTIVE_CHECKPOINTS -split" in workflow
    names = current.develop_static_checkpoints(ROOT)
    assert names == tuple(
        n
        for n in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
        if n
        not in {
            runner.ARCH134_D1R6_NAME,
            runner.ARCH134_D1R7_NAME,
            runner.ARCH134_D1R8_NAME,
            runner.ARCH134_F1_NAME,
            runner.ARCH144C_NAME,
        }
    )
    tree = ast.parse((ROOT / "scripts/checkpoint_runner.py").read_text())
    for name, callee in (
        ("verify_checkpoint", "evaluate_source_authority"),
        ("verify_batch", "evaluate_source_authority"),
        ("_prepublication_authority_results", "evaluate_source_authority"),
        (
            "_arch134_r3n_prepublication_authority_check",
            "_prepublication_authority_results",
        ),
        ("_docs_only_prepublication_admission", "_prepublication_authority_results"),
    ):
        node = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        assert any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == callee
            for n in ast.walk(node)
        )


def test_correction_source_route_keeps_diagnostic_effect_and_profile_bounds():
    specs = runner._checkpoint_specs()
    name = runner.resolve_ci_checkpoint(
        specs,
        "feature/test-suite-current-authority-historical-decoupling-current",
        "push",
    )
    assert name == runner.ARCH134_READONLY_DIAGNOSTIC_NAME
    assert specs[name].execute is None
    assert runner.resolve_ci_certification_profile(name) == "robinhood"
    assert specs[name].remote_branch == runner.ARCH134_READONLY_DIAGNOSTIC_BRANCH
    assert runner._arch134_readonly_diagnostic_graph_check(ROOT) == ()


def test_d1r6_reconstructs_historical_workflow_and_checks_current_topology(monkeypatch):
    original_hash = runner._git_blob_sha1

    def hash_security_source(path):
        assert path.name != "checkpoint-source-gates.yml", (
            "historical current-byte claim"
        )
        return original_hash(path)

    monkeypatch.setattr(runner, "_git_blob_sha1", hash_security_source)
    assert runner._arch134_d1r6_authority_check(ROOT) == ()
    original_read = Path.read_text

    def read(path, *args, **kwargs):
        text = original_read(path, *args, **kwargs)
        if path.name == "checkpoint-source-gates.yml":
            return text.replace('      - "feature/research-*"\n', "")
        return text

    monkeypatch.setattr(Path, "read_text", read)
    assert "134-D1R6 workflow drift" in runner._arch134_d1r6_authority_check(ROOT)


def test_complete_746_failure_families_are_rechecked():
    evidence = json.loads(
        (
            Path(__file__).parent / "fixtures/integration_746_authority_failures.json"
        ).read_text()
    )
    assert evidence["run_id"] == 40421315451
    assert evidence["attempt"] == 1
    assert len(evidence["failures"]) == 296
    graph_digest = hashlib.sha256(
        json.dumps(evidence["failures"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert (
        graph_digest
        == evidence["failure_graph_sha256"]
        == "e4a522bc7d6c110a99dd3d108d97ca3f048cc79b0a8197b838feaa5a2770eb86"
    )
    affected = {f["checkpoint"] for f in evidence["failures"]}
    assert len(affected) == 13
    assert affected <= set(current.develop_static_checkpoints(ROOT))
    assert all(runner._checkpoint_specs()[name].authority_check for name in affected)


def test_real_git_prospective_evaluation_has_no_git_mutation_or_profile_execution(
    monkeypatch,
    tmp_path,
):
    root = tmp_path / "candidate"
    root.mkdir()

    def prepare(*args):
        runner.subprocess.run(("git", *args), cwd=root, capture_output=True, check=True)

    prepare("init", "--quiet")
    prepare("config", "user.name", "Authority test")
    prepare("config", "user.email", "authority@example.invalid")
    (root / "source.txt").write_text("candidate source\n", encoding="utf-8")
    prepare("add", "--", "source.txt")
    prepare("commit", "--quiet", "-m", "disposable candidate")
    before = runner._git_state(root)
    refs = runner._git_output(root, "show-ref")
    index = Path(runner._git_output(root, "rev-parse", "--git-path", "index"))
    if not index.is_absolute():
        index = root / index
    index_bytes = index.read_bytes()
    spec = runner.CheckpointSpec("example", "static only", (), (), lambda _: ())
    monkeypatch.setattr(current, "current_authority_check", lambda _: ())
    monkeypatch.setattr(current, "develop_static_checkpoints", lambda _: (spec.name,))
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: {spec.name: spec})
    original = runner.subprocess.run
    calls = []

    def read_only(argv, **kwargs):
        assert argv[0] == "git" and argv[1] in {"rev-parse", "status"}
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        calls.append(argv)
        return original(argv, **kwargs)

    with monkeypatch.context() as guarded:
        guarded.setattr(runner.subprocess, "run", read_only)
        result = current.evaluate_source_authority(
            root, publication_context=current.PublicationContext.PROSPECTIVE_DEVELOP
        )
    assert result.passed
    assert result.head == before["head"] and result.tree == before["tree"]
    assert calls
    assert runner._git_state(root) == before
    assert runner._git_output(root, "show-ref") == refs
    assert index.read_bytes() == index_bytes


def test_historical_catalog_cannot_reclassify_unknown_security_symbol(
    monkeypatch, tmp_path
):
    data = json.loads(
        (ROOT / "scripts/historical_authority_objects.json").read_text(encoding="utf-8")
    )
    data["mutable_symbols"].append("execute_checkpoint")
    directory = tmp_path / "scripts"
    directory.mkdir()
    (directory / "historical_authority_objects.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    monkeypatch.setattr(ownership, "_ARCHIVE_ROOT", tmp_path)
    with pytest.raises(ValueError, match="catalog drift"):
        ownership.historical_catalog(tmp_path)


def test_develop_ci_cannot_supply_a_smaller_authority_set(monkeypatch):
    state = _contexts(monkeypatch)
    state["branch"] = "develop"
    specs = runner._checkpoint_specs()
    result = current.evaluate_source_authority(
        ROOT,
        publication_context=current.PublicationContext.PROSPECTIVE_DEVELOP,
        checkpoints=(specs["feature"],),
    )
    assert (
        "develop CI authority set differs from prospective routing" in result.failures
    )


def test_dirty_candidate_is_rejected_before_authority_or_effects(monkeypatch):
    state = _contexts(monkeypatch)
    state["porcelain"] = " M source.py"
    monkeypatch.setattr(
        current,
        "current_authority_check",
        lambda _: pytest.fail("dirty candidate evaluated"),
    )
    result = current.evaluate_source_authority(
        ROOT, publication_context=current.PublicationContext.PROSPECTIVE_DEVELOP
    )
    assert result.failures == ("candidate source requires a clean committed tree",)


def test_future_shared_runner_and_reuse_edits_do_not_repin_history():
    functions = {
        n.name: n
        for n in ast.parse(
            (ROOT / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        ).body
        if isinstance(n, ast.FunctionDef)
    }
    for name in (
        "_batch_workflow_is_reviewed",
        "_checkpoint_specs",
        "find_reusable_ci_certification",
        "resolve_develop_ci_reuse",
    ):
        expected = hashlib.sha256(
            ast.dump(functions[name], include_attributes=False).encode()
        ).hexdigest()
        future = ast.parse(f"def {name}():\n    return False\n").body[0]
        assert ownership.current_owner(name) == "checkpoint_runner"
        assert ownership.ast_matches(ROOT, name, future, expected)
    name = "_readonly_preflight_checkpoint"
    protected = hashlib.sha256(
        ast.dump(functions[name], include_attributes=False).encode()
    ).hexdigest()
    assert not ownership.ast_matches(ROOT, name, ast.Pass(), protected)


def test_historical_layer_cannot_add_current_shared_function_ast_pin(tmp_path):
    for file in (
        "scripts/checkpoint_runner.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
    ):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / file).read_text(encoding="utf-8"), encoding="utf-8")
    path = tmp_path / "scripts/checkpoint_runner.py"
    with path.open("a", encoding="utf-8") as output:
        output.write(
            '\nNEW_HISTORICAL_AST_PINS: Final = {"find_reusable_ci_certification": "'
            + "0" * 64
            + '"}\n'
        )
    assert any(
        "CURRENT_MUTABLE" in failure
        for failure in ownership.ownership_failures(tmp_path)
    )


def test_current_registry_profiles_and_harness_do_not_rehash_historical_material(
    monkeypatch,
):
    runner._readonly_maps()
    runner._arch132_r3n_c4_maps()
    monkeypatch.setattr(
        runner, "CI_CERTIFICATION_PROFILES", {"future-checkpoint": "full"}
    )
    monkeypatch.setattr(runner, "READONLY_ADMISSION_TESTS", ("future/test.py",))
    monkeypatch.setattr(runner, "READONLY_ADMISSION_RUFF", ("future/source.py",))
    monkeypatch.setattr(runner, "REVIEWED_SKIPPED_CERTIFICATION_JOB", "future-caption")
    runner._readonly_maps()
    runner._arch132_r3n_c4_maps()


def test_historical_map_cannot_hash_live_current_registry(tmp_path):
    for file in (
        "scripts/checkpoint_runner.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
    ):
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / file).read_text(encoding="utf-8"), encoding="utf-8")
    path = tmp_path / "scripts/checkpoint_runner.py"
    with path.open("a", encoding="utf-8") as output:
        output.write(
            "\ndef accidental_historical_maps():\n"
            "    return CI_CERTIFICATION_PROFILES\n"
        )
    assert any(
        "live CURRENT_MUTABLE" in failure
        for failure in ownership.ownership_failures(tmp_path)
    )


@pytest.mark.parametrize(
    "phase,index,count",
    [
        ("tests", None, None),
        ("static", None, None),
        ("all", "0", "2"),
        ("all", "0", None),
    ],
)
def test_general_admission_cannot_bypass_both_contexts_with_ci_controls(
    monkeypatch, tmp_path, phase, index, count
):
    monkeypatch.setenv(runner.SOURCE_GATE_PHASE_ENV, phase)
    for name, value in (
        (runner.SOURCE_GATE_SHARD_INDEX_ENV, index),
        (runner.SOURCE_GATE_SHARD_COUNT_ENV, count),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        runner,
        "verify_checkpoint",
        lambda *a, **k: pytest.fail("partial admission ran"),
    )
    monkeypatch.setattr(
        runner,
        "_prepublication_source",
        lambda *a, **k: pytest.fail("partial admission collected source"),
    )
    with pytest.raises(RuntimeError):
        runner.prepublication_admission(
            repo_root=tmp_path, evidence_root=tmp_path / "evidence"
        )


def test_current_owner_rejects_malformed_harness_without_changing_history(monkeypatch):
    monkeypatch.setattr(runner, "READONLY_ADMISSION_TESTS", {})
    runner._readonly_maps()
    assert runner._readonly_candidate_authority_check(ROOT) == ()
    assert any(
        "current checkpoint test inventory drift" in failure
        for failure in current.current_authority_check(ROOT)
    )


def test_general_admission_static_scope_covers_prospective_source_static():
    assert runner.ARCH132_R3N_ADMISSION_RUFF_PATHS == (".",)


def test_historical_toolchain_pin_reconstructs_without_repinning_current_dependencies(
    tmp_path,
):
    relative = "pyproject.toml"
    pin = runner.ARCH132_R3M_FROZEN_SOURCE_PINS[relative]
    path = tmp_path / relative
    path.write_text('ruff = "future current toolchain"\n', encoding="utf-8")
    assert ownership.classify_path(relative) is ownership.PinClass.CURRENT_MUTABLE
    assert ownership.blob_matches(tmp_path, path, pin)
    assert not ownership.blob_matches(tmp_path, path, "0" * 40)
