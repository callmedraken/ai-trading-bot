"""Source-only P124-5 provenance regressions; all host boundaries are forbidden."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import d10_activation_scheduler_operator as operator


@pytest.mark.parametrize(
    "name", (*operator._GOVERNED_AUTHORITY_MODULES, *operator._SCRIPT_AUTHORITY_MODULES)
)
@pytest.mark.parametrize(
    "mode",
    (
        "preflight",
        "reconcile",
        "execute",
        "recovery_preflight",
        "recover_partial_installing",
    ),
)
def test_foreign_loaded_authority_blocks_before_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, mode: str
) -> None:
    foreign_file = tmp_path / "foreign_authority.py"
    foreign_file.write_text(
        "# outside the reviewed operator checkout\n", encoding="utf-8"
    )
    module = sys.modules[name]
    monkeypatch.setattr(module, "__file__", str(foreign_file))
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("host boundary must not be reached")

    for boundary in (
        "_host_operator",
        "WindowsD10ReadOnlyReader",
        "WindowsCngVerifier",
        "WindowsActivationLeaseBackend",
        "observe_d5_scheduler",
        "_read_scheduler",
        "_update_scheduler",
        "_interactive_credential",
    ):
        monkeypatch.setattr(operator, boundary, forbidden)
    action = getattr(operator, mode)
    kwargs = (
        {"execute_p1245": True}
        if mode == "execute"
        else {"execute_p1245_recovery": True}
        if mode == "recover_partial_installing"
        else {}
    )
    with pytest.raises(operator.OperatorBlocked, match="source_provenance_mismatch"):
        action(**kwargs)
    assert not calls


@pytest.mark.parametrize("filename", (None, "relative.py", "", 7))
def test_missing_or_relative_loaded_file_blocks(
    monkeypatch: pytest.MonkeyPatch, filename: object
) -> None:
    module = sys.modules[operator._GOVERNED_AUTHORITY_MODULES[2]]
    monkeypatch.setattr(module, "__file__", filename)
    with pytest.raises(operator.OperatorBlocked):
        operator._require_source_provenance()


def test_missing_module_file_and_module_replacement_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = operator._GOVERNED_AUTHORITY_MODULES[2]
    original = sys.modules[name]
    with monkeypatch.context() as patch:
        patch.setattr(original, "__file__", str(tmp_path / "missing.py"))
        with pytest.raises(operator.OperatorBlocked):
            operator._require_source_provenance()
    with monkeypatch.context() as patch:
        patch.setattr(original, "__file__", str(operator._OPERATOR_SOURCE_ROOT))
        with pytest.raises(operator.OperatorBlocked):
            operator._require_source_provenance()
    with monkeypatch.context() as patch:
        patch.delitem(sys.modules, name)
        with pytest.raises(operator.OperatorBlocked):
            operator._require_source_provenance()
    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, name, object())
        with pytest.raises(operator.OperatorBlocked):
            operator._require_source_provenance()


def test_host_factory_itself_checks_before_native_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = "scripts.d10_protected_replacement_windows"
    monkeypatch.setattr(sys.modules[name], "__file__", str(tmp_path / "foreign.py"))
    monkeypatch.setattr(
        operator,
        "WindowsD10ReadOnlyReader",
        lambda: pytest.fail("native construction forbidden"),
    )
    with pytest.raises(operator.OperatorBlocked):
        operator._host_operator(protected=True)


@pytest.mark.parametrize(
    "mode",
    ("preflight", "reconcile", "execute", "recovery-preflight", "recover-partial"),
)
def test_cli_provenance_failure_is_secret_free_and_no_effect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys, mode: str
) -> None:
    module = sys.modules[operator._GOVERNED_AUTHORITY_MODULES[2]]
    monkeypatch.setattr(module, "__file__", str(tmp_path / "foreign.py"))
    monkeypatch.setattr(
        operator, "_host_operator", lambda **_: pytest.fail("host entry forbidden")
    )
    args = (
        [mode, "--execute-p1245"]
        if mode == "execute"
        else [mode, "--execute-p1245-recovery"]
        if mode == "recover-partial"
        else [mode]
    )
    assert operator.main(args) == 1
    captured = capsys.readouterr()
    evidence = json.loads(captured.out)
    assert captured.err == ""
    assert evidence["status"] == "BLOCKED"
    for effect in ("provider", "Paper-v2", "broker", "live"):
        assert evidence[effect] == "NOT_RUN"
    assert "foreign.py" not in captured.out


_PROBE = r"""
import importlib.util
import json
import os
import pathlib
import site
import sys

operator_file = pathlib.Path(sys.argv[1])
editable_site = pathlib.Path(sys.argv[2])
foreign_source = pathlib.Path(sys.argv[3])
site.addsitedir(str(editable_site))
# Model an editable .pth checkout available ahead of other installed copies.
sys.path.insert(0, str(foreign_source))
foreign_origin = importlib.util.find_spec("trading_bot").origin
assert pathlib.Path(foreign_origin).resolve().is_relative_to(foreign_source)

# No production observation/mutation may occur, even during import. Only source
# path inspection and pure contract imports are permitted in this child.
def audit(event, args):
    if event == "subprocess.Popen":
        raise AssertionError("host subprocess forbidden")
    if event == "ctypes.dlopen" and args[0] and "Windows" in str(args[0]):
        raise AssertionError("native host library forbidden")
    if event in ("open", "os.listdir", "os.scandir") and args:
        path = str(args[0]).replace("/", "\\").casefold()
        if path.startswith("f:\\aitradingbot"):
            raise AssertionError("protected namespace forbidden")
sys.addaudithook(audit)

spec = importlib.util.spec_from_file_location("p1245_provenance_probe", operator_file)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module._require_source_provenance()

def forbidden(*args, **kwargs):
    raise AssertionError("host authority boundary forbidden")
for name in (
    "WindowsD10ReadOnlyReader", "WindowsCngVerifier", "WindowsActivationLeaseBackend",
    "observe_d5_scheduler", "_read_scheduler", "_update_scheduler",
    "_interactive_credential",
):
    setattr(module, name, forbidden)

print(json.dumps({
    "repo_root": str(module._OPERATOR_REPO_ROOT),
    "source_root": str(module._OPERATOR_SOURCE_ROOT),
    "scripts_root": str(module._OPERATOR_SCRIPTS_ROOT),
    "first_import_path": sys.path[0],
    "loaded": {name: str(pathlib.Path(loaded.__file__).resolve())
               for name, loaded, root in module._SOURCE_PROVENANCE},
    "foreign_origin": foreign_origin,
    "host": "NOT_RUN",
}))
"""


@pytest.mark.parametrize("poison_environment", (False, True))
def test_fresh_subprocess_ignores_foreign_editable_and_environment_source(
    tmp_path: Path, poison_environment: bool
) -> None:
    foreign = tmp_path / "other-checkout"
    foreign_src = foreign / "src"
    package = foreign_src / "trading_bot"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "raise AssertionError('foreign trading authority imported')\n", encoding="utf-8"
    )
    scripts = foreign / "scripts"
    scripts.mkdir()
    (scripts / "__init__.py").write_text(
        "raise AssertionError('foreign script authority imported')\n", encoding="utf-8"
    )
    editable_site = tmp_path / "editable-site"
    editable_site.mkdir()
    (editable_site / "foreign-editable.pth").write_text(
        str(foreign_src) + "\n", encoding="utf-8"
    )
    unrelated_cwd = tmp_path / "unrelated-cwd"
    unrelated_cwd.mkdir()
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if poison_environment:
        environment.update(
            {
                "PYTHONPATH": os.pathsep.join((str(foreign_src), str(foreign))),
                "P1245_SOURCE_ROOT": str(foreign_src),
                "P1245_SCRIPTS_ROOT": str(scripts),
            }
        )
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            _PROBE,
            str(Path(operator.__file__).resolve()),
            str(editable_site),
            str(foreign_src),
        ],
        cwd=unrelated_cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    root = Path(operator.__file__).resolve().parent.parent
    assert Path(evidence["repo_root"]) == root
    assert Path(evidence["source_root"]) == root / "src"
    assert Path(evidence["scripts_root"]) == root / "scripts"
    assert Path(evidence["first_import_path"]) == root / "src"
    assert Path(evidence["foreign_origin"]).is_relative_to(foreign_src)
    for name, filename in evidence["loaded"].items():
        required_root = (
            root / "src" if name.startswith("trading_bot") else root / "scripts"
        )
        assert Path(filename).is_relative_to(required_root)
    assert evidence["host"] == "NOT_RUN"


def test_fixed_roots_are_derived_only_from_operator_file() -> None:
    root = Path(operator.__file__).resolve().parent.parent
    assert operator._OPERATOR_REPO_ROOT == root
    assert operator._OPERATOR_SOURCE_ROOT == root / "src"
    assert operator._OPERATOR_SCRIPTS_ROOT == root / "scripts"
    operator._require_source_provenance()
    expected = {
        "trading_bot.runtime.personal_desktop_d10_activation_lease",
        "trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract",
        "trading_bot.runtime.personal_desktop_unattended_scheduler_contract",
        "trading_bot.runtime.personal_desktop_unattended_capture_warmup_scheduler_contract",
    }
    assert expected <= set(operator._GOVERNED_AUTHORITY_MODULES)
