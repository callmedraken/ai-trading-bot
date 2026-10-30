"""Ownership of mutable source contracts and immutable checkpoint evidence.

Historical exact pins reconstruct immutable Git objects. They never authorize the
current runner, workflow, certification implementation or tests. Current semantic
contracts are composed separately by checkpoint_runner.evaluate_source_authority.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from copy import deepcopy
from enum import StrEnum
from functools import cache, lru_cache
from pathlib import Path


class PinClass(StrEnum):
    IMMUTABLE_HISTORICAL = "IMMUTABLE_HISTORICAL"
    SECURITY_SEMANTIC = "SECURITY_SEMANTIC"
    CURRENT_MUTABLE = "CURRENT_MUTABLE"
    INCIDENT_EVIDENCE = "INCIDENT_EVIDENCE"


_ARCHIVE_ROOT = Path(__file__).resolve().parents[1]

HISTORICAL_COMMIT = "29e9487b7a4e831dc6f306de66184cb6f8bb2723"
HISTORICAL_RUNNER_BLOB = "e31fd6bd860fdc752a65915735bb230f96afa475"
HISTORICAL_CATALOG_SHA256 = (
    "34929e21a7153d9ad5ac2280d47941f23c2f053e9d44db04d2b1b7fc596b2562"
)


CURRENT_MUTABLE_CONSTANTS = frozenset(
    {
        "CURRENT_ACTIVE_CI_CHECKPOINTS",
        "CI_CERTIFICATION_PROFILES",
        "COMMON_TESTS",
        "COMMON_RUFF_PATHS",
        "READONLY_ADMISSION_TESTS",
        "READONLY_ADMISSION_RUFF",
        "PREPUBLICATION_INFRASTRUCTURE_COHERENCE_TESTS",
        "PREPUBLICATION_INFRASTRUCTURE_PATHS",
        "PREPUBLICATION_INFRASTRUCTURE_TEST_PREFIXES",
        "REVIEWED_SKIPPED_CERTIFICATION_JOB",
    }
)


def current_owner(relative: str) -> str | None:
    """Assign each current mutable concept to exactly one semantic owner."""
    if relative in CURRENT_MUTABLE_CONSTANTS:
        return "checkpoint_runner"
    if relative in {"discover_inventory", "select_inventory"}:
        return "certification"
    if "/" not in relative and (
        relative in historical_catalog(_ARCHIVE_ROOT)["mutable_symbols"]
        or relative
        in {
            "evaluate_source_authority",
            "current_authority_check",
            "current_preflight_dispatch_failures",
            "preflight_checkpoint",
            "develop_static_checkpoints",
            "current_owner",
            "classify_path",
            "ownership_failures",
            "blob_matches",
            "ast_matches",
            "runner_tree",
            "_source_pytest_basetemp",
            "_prepublication_admission_tests",
            "_prepublication_requires_infrastructure_coherence",
            "ACTIVE_CI_CHECKPOINTS",
        }
    ):
        return "checkpoint_runner"
    if relative.startswith("tests/runtime/checkpoint_runner/") and relative.endswith(
        ".py"
    ):
        return "checkpoint_runner"
    if relative.startswith("tests/scripts/certification_runner/") and relative.endswith(
        ".py"
    ):
        return "certification"
    if relative.startswith("tests/") and relative.endswith(".py"):
        return "test_harness"
    if relative in {
        "ops.ps1",
        "scripts/checkpoint_runner.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
        "scripts/distributed_full.py",
    }:
        return "checkpoint_runner"
    if relative in {"scripts/run_test_certification.py", "pyproject.toml"}:
        return "certification"
    if relative == ".github/workflows/checkpoint-source-gates.yml":
        return "ci_workflow"
    if relative in {
        "AGENTS.md",
        "docs/PROJECT_STATUS.md",
        "docs/AI_TRADING_BOT_HANDOFF.md",
        "docs/AI_DEVELOPMENT_WORKFLOW.md",
        "docs/architecture/132-tiered-certification-profiles.md",
    }:
        return "workflow_coordination"
    return None


def classify_path(relative: str) -> PinClass:
    if current_owner(relative) is not None:
        return PinClass.CURRENT_MUTABLE
    if "/fixtures/" in relative or relative.startswith("docs/history/"):
        return PinClass.INCIDENT_EVIDENCE
    if (
        relative.startswith("docs/")
        or relative == "scripts/historical_authority_objects.json"
    ):
        return PinClass.IMMUTABLE_HISTORICAL
    return PinClass.SECURITY_SEMANTIC


@cache
def historical_blob(repo_root: Path, oid: str) -> bytes:
    """Read and validate one immutable object; no checkout or Git mutation."""
    if re.fullmatch(r"[0-9a-f]{40}", oid) is None:
        raise ValueError("invalid historical blob identity")
    result = subprocess.run(
        ("git", "cat-file", "blob", oid),
        cwd=_ARCHIVE_ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("historical blob unavailable: " + oid)
    data = result.stdout
    if (
        hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        != oid
    ):
        raise ValueError("historical blob identity mismatch")
    return data


@cache
def historical_tree(repo_root: Path) -> ast.Module:
    return ast.parse(historical_blob(repo_root, HISTORICAL_RUNNER_BLOB).decode("utf-8"))


@cache
def historical_path_pins(repo_root: Path) -> frozenset[tuple[str, str]]:
    pairs = set()
    for node in ast.walk(historical_tree(repo_root)):
        values = (
            zip(node.keys, node.values, strict=True)
            if isinstance(node, ast.Dict)
            else (
                (node.elts,)
                if isinstance(node, (ast.Tuple, ast.List)) and len(node.elts) == 2
                else ()
            )
        )
        for key, value in values:
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and re.fullmatch(r"[0-9a-f]{40}", value.value)
            ):
                pairs.add((key.value, value.value))
    return frozenset(pairs)


def blob_matches(repo_root: Path, path: Path, expected: str | None) -> bool:
    relative = path.relative_to(repo_root).as_posix()
    if classify_path(relative) is PinClass.CURRENT_MUTABLE:
        # The accepted declaration binds the path to the historical object.
        # Object existence alone is insufficient: a different path/hash fails.
        if (relative, expected) not in historical_path_pins(_ARCHIVE_ROOT):
            return False
        replacement = historical_catalog(_ARCHIVE_ROOT)[
            "retired_unmaterialized_harness_declarations"
        ].get(relative + "@" + expected)
        if replacement is not None:
            # A retired planned harness hash was never a materialized Git blob.
            # Preserve the declaration as fact; reconstruct actual predecessor
            # source separately, without claiming the planned bytes were accepted.
            if (
                replacement["path"] != relative
                or replacement["recorded_pin"] != expected
            ):
                return False
            if not _historical_replacement_binding(
                relative, replacement["source_commit"], replacement["source_blob"]
            ):
                return False
            historical_blob(_ARCHIVE_ROOT, replacement["source_blob"])
        else:
            historical_blob(_ARCHIVE_ROOT, expected)
        return True
    # Keep the existing Windows-normalized exact-byte primitive as the single
    # security source hash owner.
    from scripts import checkpoint_runner

    if (
        relative in checkpoint_runner.ARCH134_READONLY_DIAGNOSTIC_R1_BLOB_PREDECESSORS
        and expected
        == checkpoint_runner.ARCH134_READONLY_DIAGNOSTIC_R1_BLOB_PREDECESSORS[relative]
    ):
        historical_blob(_ARCHIVE_ROOT, expected)
        expected = checkpoint_runner.ARCH134_READONLY_DIAGNOSTIC_R1_SOURCE_PINS[
            relative
        ]
    from scripts.arch146_source_authority import (
        DATASET_SOURCE,
        dataset_preserves_146a_contract,
    )

    if relative == DATASET_SOURCE:
        # One current semantic owner proves the complete old contract after the
        # reviewed physical-helper extraction. Historical pins remain immutable.
        return expected == checkpoint_runner.ARCH146A_SOURCE_PINS[
            DATASET_SOURCE
        ] and dataset_preserves_146a_contract(repo_root, expected)
    return checkpoint_runner._git_blob_sha1(path) == expected


@cache
def historical_catalog(repo_root: Path) -> dict:
    source = (_ARCHIVE_ROOT / "scripts/historical_authority_objects.json").read_text(
        encoding="utf-8"
    )
    if hashlib.sha256(source.encode()).hexdigest() != HISTORICAL_CATALOG_SHA256:
        raise ValueError("immutable historical catalog drift")
    data = json.loads(source)
    if (
        data["record_commit"] != HISTORICAL_COMMIT
        or data["record_runner_blob"] != HISTORICAL_RUNNER_BLOB
        or set(data["mutable_symbols"]) != set(data["ast_objects"])
    ):
        raise ValueError("historical catalog identity mismatch")
    if any(
        name
        in {
            "execute_checkpoint",
            "preflight_checkpoint",
            "_readonly_preflight_checkpoint",
        }
        or name.endswith(("_execute", "_preflight"))
        for name in data["mutable_symbols"]
    ):
        raise ValueError("protected symbol cannot be classified CURRENT_MUTABLE")
    return data


@cache
def _historical_symbol_digests(
    repo_root: Path, blob: str
) -> frozenset[tuple[str, str]]:
    # Retain digests, not dozens of complete runner ASTs. Historical ASTs are
    # temporary parsing values, avoiding unbounded memory use in a batch.
    tree = ast.parse(historical_blob(repo_root, blob).decode("utf-8-sig"))
    names = set(historical_catalog(_ARCHIVE_ROOT)["mutable_symbols"])
    return frozenset(
        (
            item.name,
            hashlib.sha256(
                ast.dump(item, include_attributes=False).encode()
            ).hexdigest(),
        )
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name in names
    )


def _historical_ast_match(repo_root: Path, blob: str, name: str, expected: str) -> bool:
    return (name, expected) in _historical_symbol_digests(repo_root, blob)


def ast_matches(repo_root: Path, name: str, node: ast.AST, expected: str) -> bool:
    catalog = historical_catalog(_ARCHIVE_ROOT)
    if name in catalog["mutable_symbols"]:
        blob = catalog["ast_objects"][name].get(expected)
        if blob is None:
            return False
        return _historical_ast_match(_ARCHIVE_ROOT, blob, name, expected)
    # Exact implementation remains authoritative for protected dispatch and
    # other security-sensitive symbols. No mutable-symbol fallback is allowed.
    if name == "_readonly_preflight_checkpoint":
        from scripts import checkpoint_runner

        if (
            expected
            == checkpoint_runner.ARCH134_READONLY_DIAGNOSTIC_R1_PREFLIGHT_PREDECESSOR
        ):
            predecessor = next(
                item
                for item in historical_tree(_ARCHIVE_ROOT).body
                if isinstance(item, ast.FunctionDef) and item.name == name
            )
            if (
                hashlib.sha256(
                    ast.dump(predecessor, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                return False
            expected = checkpoint_runner.ARCH134_READONLY_DIAGNOSTIC_R1_PREFLIGHT_AST
    return (
        hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        == expected
    )


def _mutable_pin_literals(tree: ast.AST) -> list[str]:
    result = []
    for node in ast.walk(tree):
        pairs = (
            zip(node.keys, node.values, strict=True)
            if isinstance(node, ast.Dict)
            else (
                (node.elts,)
                if isinstance(node, (ast.Tuple, ast.List)) and len(node.elts) == 2
                else ()
            )
        )
        for key, value in pairs:
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and current_owner(key.value) is not None
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and re.fullmatch(r"[0-9a-f]{40,64}", value.value)
            ):
                result.append(
                    ast.dump(
                        ast.Tuple(elts=[key, value], ctx=ast.Load()),
                        include_attributes=False,
                    )
                )
    return result


_HASH_METHODS = frozenset(
    {
        "blake2b",
        "blake2s",
        "md5",
        "sha1",
        "sha224",
        "sha256",
        "sha384",
        "sha512",
    }
)
_SOURCE_READ_METHODS = frozenset({"read_bytes", "read_text"})
_SOURCE_AUTHORITY_APIS = frozenset({"ast_matches", "blob_matches"})


def _assignment_targets(node: ast.AST) -> tuple[str, ...]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
        targets.append(node.target)
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def _target_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(name for element in node.elts for name in _target_names(element))
    if isinstance(node, ast.Starred):
        return _target_names(node.value)
    return ()


def _module_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if node.module == "scripts" and alias.name in {
                    "checkpoint_runner",
                    "current_source_authority",
                    "run_test_certification",
                    "source_authority",
                }:
                    aliases[alias.asname or alias.name] = f"scripts/{alias.name}.py"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {
                    "scripts.checkpoint_runner",
                    "scripts.current_source_authority",
                    "scripts.run_test_certification",
                    "scripts.source_authority",
                }:
                    aliases[alias.asname or alias.name.split(".")[-1]] = (
                        alias.name.replace(".", "/") + ".py"
                    )
    return aliases


def _current_module_file(node: ast.AST, aliases: dict[str, str]) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "__file__"
        and isinstance(node.value, ast.Name)
        and classify_path(aliases.get(node.value.id, "")) is PinClass.CURRENT_MUTABLE
    )


def _current_symbol(node: ast.AST, aliases: dict[str, str]) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and classify_path(aliases.get(node.value.id, "")) is PinClass.CURRENT_MUTABLE
        and current_owner(node.attr) is not None
    )


def _literal_current_path(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and classify_path(node.value.replace("\\", "/")) is PinClass.CURRENT_MUTABLE
    )


def _path_is_current_mutable(
    node: ast.AST, path_names: set[str], aliases: dict[str, str]
) -> bool:
    if _literal_current_path(node) or _current_module_file(node, aliases):
        return True
    if isinstance(node, ast.Name):
        return node.id in path_names
    if isinstance(node, ast.Attribute) and node.attr in {"parent", "parents"}:
        # Path(runner.__file__).parents[1] is the repository root, not the
        # current-mutable runner file itself.
        return False
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr in {"parent", "parents"}
    ):
        return False
    if isinstance(node, (ast.BinOp, ast.JoinedStr, ast.Subscript)):
        return any(
            _path_is_current_mutable(child, path_names, aliases)
            for child in ast.iter_child_nodes(node)
        )
    if isinstance(node, ast.Call):
        return any(
            _path_is_current_mutable(child, path_names, aliases)
            for child in ast.iter_child_nodes(node)
        )
    if isinstance(node, ast.Attribute):
        return _path_is_current_mutable(node.value, path_names, aliases)
    return False


def _source_is_current_mutable(
    node: ast.AST,
    path_names: set[str],
    source_names: set[str],
    aliases: dict[str, str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in source_names
    if isinstance(node, ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in _SOURCE_READ_METHODS
            and _path_is_current_mutable(node.func.value, path_names, aliases)
        ):
            return True
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "getsource"
            and any(_current_symbol(arg, aliases) for arg in node.args)
        ):
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in {
            "decode",
            "encode",
            "strip",
            "splitlines",
        }:
            return _source_is_current_mutable(
                node.func.value, path_names, source_names, aliases
            )
        return False
    if isinstance(node, ast.Attribute):
        return False
    if isinstance(node, ast.Subscript):
        return _source_is_current_mutable(node.value, path_names, source_names, aliases)
    return False


def _current_inventory_value(
    node: ast.AST, aliases: dict[str, str], source_names: set[str]
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in source_names
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in {"discover_inventory", "select_inventory"}:
            return _current_symbol(node.func, aliases)
        if node.func.attr == "items":
            return _current_inventory_value(node.func.value, aliases, source_names)
    if isinstance(node, (ast.DictComp, ast.ListComp, ast.GeneratorExp, ast.SetComp)):
        return any(
            _current_inventory_value(child, aliases, source_names)
            for child in ast.iter_child_nodes(node)
        )
    return False


def _ast_is_current_mutable(
    node: ast.AST,
    path_names: set[str],
    source_names: set[str],
    ast_names: set[str],
    aliases: dict[str, str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in ast_names
    if isinstance(node, ast.Subscript):
        return _ast_is_current_mutable(
            node.value, path_names, source_names, ast_names, aliases
        )
    if isinstance(node, ast.Attribute):
        return _ast_is_current_mutable(
            node.value, path_names, source_names, ast_names, aliases
        )
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "parse":
            return any(
                _source_is_current_mutable(arg, path_names, source_names, aliases)
                for arg in node.args
            )
        return False
    if isinstance(node, (ast.DictComp, ast.ListComp, ast.GeneratorExp, ast.SetComp)):
        return any(
            _ast_is_current_mutable(child, path_names, source_names, ast_names, aliases)
            for child in ast.iter_child_nodes(node)
        )
    return any(
        _ast_is_current_mutable(child, path_names, source_names, ast_names, aliases)
        for child in ast.iter_child_nodes(node)
    )


def _current_mutable_pin_map(node: ast.AST, aliases: dict[str, str]) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "items"
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and classify_path(aliases.get(node.func.value.value.id, ""))
        is PinClass.CURRENT_MUTABLE
        and "PIN" in node.func.value.attr.upper()
    )


def _historical_test_ownership_failures(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    historical_roots = (
        repo_root / "tests/review_paper",
        repo_root / "tests/strategies",
        repo_root / "tests/experiments",
    )
    paths = [
        path
        for historical_root in historical_roots
        if historical_root.is_dir()
        for path in sorted(historical_root.rglob("*.py"))
    ]
    for path in paths:
        relative = path.relative_to(repo_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            failures.append(
                "historical test authority unavailable: "
                f"{relative} ({type(exc).__name__})"
            )
            continue

        aliases = _module_aliases(tree)

        def analyze(scope: ast.AST, *, aliases=aliases, relative=relative) -> None:
            inventory_scope = relative.startswith(
                ("tests/strategies/", "tests/experiments/")
            )
            path_names: set[str] = set()
            source_names: set[str] = set()
            ast_names: set[str] = set()
            changed = True
            while changed:
                changed = False
                for item in ast.walk(scope):
                    if inventory_scope and isinstance(
                        item, (ast.For, ast.comprehension)
                    ):
                        targets = _target_names(item.target)
                        if _current_mutable_pin_map(item.iter, aliases):
                            for target in targets:
                                if target not in path_names:
                                    path_names.add(target)
                                    changed = True
                        if _source_is_current_mutable(
                            item.iter, path_names, source_names, aliases
                        ) or _current_inventory_value(item.iter, aliases, source_names):
                            for target in targets:
                                if target not in source_names:
                                    source_names.add(target)
                                    changed = True
                    value = (
                        item.value
                        if isinstance(item, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
                        else None
                    )
                    if value is None:
                        continue
                    targets = _assignment_targets(item)
                    if not targets:
                        continue
                    if inventory_scope and _current_inventory_value(
                        value, aliases, source_names
                    ):
                        for target in targets:
                            if target not in source_names:
                                source_names.add(target)
                                changed = True
                    if _path_is_current_mutable(value, path_names, aliases):
                        for target in targets:
                            if target not in path_names:
                                path_names.add(target)
                                changed = True
                    if _source_is_current_mutable(
                        value, path_names, source_names, aliases
                    ):
                        for target in targets:
                            if target not in source_names:
                                source_names.add(target)
                                changed = True
                    if _ast_is_current_mutable(
                        value, path_names, source_names, ast_names, aliases
                    ):
                        for target in targets:
                            if target not in ast_names:
                                ast_names.add(target)
                                changed = True

            def authority_api(node: ast.Call) -> bool:
                return (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in _SOURCE_AUTHORITY_APIS
                    and isinstance(node.func.value, ast.Name)
                    and aliases.get(node.func.value.id) == "scripts/source_authority.py"
                )

            def exact_current_use(node: ast.AST) -> bool:
                if isinstance(node, ast.Call):
                    if authority_api(node):
                        return False
                    if (
                        inventory_scope
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "len"
                    ):
                        return any(
                            _current_symbol(arg, aliases)
                            or _source_is_current_mutable(
                                arg, path_names, source_names, aliases
                            )
                            for arg in node.args
                        )
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr == "_git_blob_sha1" and any(
                            _path_is_current_mutable(arg, path_names, aliases)
                            for arg in node.args
                        ):
                            return True
                        if node.func.attr == "dump" and node.args:
                            if _ast_is_current_mutable(
                                node.args[0],
                                path_names,
                                source_names,
                                ast_names,
                                aliases,
                            ):
                                return True
                        if node.func.attr in _HASH_METHODS and any(
                            _current_symbol(arg, aliases)
                            or _source_is_current_mutable(
                                arg, path_names, source_names, aliases
                            )
                            or _ast_is_current_mutable(
                                arg,
                                path_names,
                                source_names,
                                ast_names,
                                aliases,
                            )
                            for arg in node.args
                        ):
                            return True
                    return any(
                        exact_current_use(child)
                        for child in ast.iter_child_nodes(node)
                        if isinstance(child, (ast.Call, ast.Compare))
                    )
                if isinstance(node, ast.Compare):
                    exact_call = any(
                        exact_current_use(child) for child in ast.iter_child_nodes(node)
                    )
                    if exact_call:
                        return True
                    if not any(
                        isinstance(operator, (ast.Eq, ast.NotEq))
                        for operator in node.ops
                    ):
                        return False
                    return any(
                        _source_is_current_mutable(
                            child, path_names, source_names, aliases
                        )
                        for child in ast.iter_child_nodes(node)
                    )
                return False

            for node in ast.walk(scope):
                if isinstance(node, ast.Call) and authority_api(node):
                    continue
                if isinstance(node, (ast.Call, ast.Compare)) and exact_current_use(
                    node
                ):
                    failures.append(
                        "historical test directly compares CURRENT_MUTABLE source: "
                        f"{relative}:{node.lineno}"
                    )

        module_scope = ast.Module(
            body=[
                node
                for node in tree.body
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ],
            type_ignores=[],
        )
        scopes = [module_scope] + [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for scope in scopes:
            analyze(scope)
    return tuple(sorted(set(failures)))


def ownership_failures(repo_root: Path) -> tuple[str, ...]:
    """Frozen historical records cannot grow new current-path exact claims.

    This is structural ownership, with no numeric fan-out allowance. Every
    existing historical pin declaration must remain byte/AST-identical to its
    immutable source; new mutable-path literals are rejected everywhere in the
    source-owned authority implementation. Current owners use semantic checks.
    """
    current = ast.parse(
        (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    )
    accepted = historical_tree(_ARCHIVE_ROOT)
    failures = []

    def declarations(tree):
        return {
            n.target.id: ast.dump(n, include_attributes=False)
            for n in tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and ("PIN" in n.target.id or "BLOB" in n.target.id)
        }

    old, new = declarations(accepted), declarations(current)
    for name, definition in old.items():
        if new.get(name) != definition:
            failures.append("immutable historical pin declaration changed: " + name)

    # Claims are keyed by their owner, preventing a new map/family from copying
    # an already-known path/hash and silently increasing fan-out.
    def claims(tree):
        result = Counter()
        for item in tree.body:
            owner = (
                item.name
                if isinstance(item, ast.FunctionDef)
                else (
                    item.target.id
                    if isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                    else ast.dump(item, include_attributes=False)
                )
            )
            result.update((owner, pin) for pin in _mutable_pin_literals(item))
        return result

    for function in current.body:
        if isinstance(function, ast.FunctionDef) and function.name.endswith("_maps"):
            if any(
                isinstance(n, ast.Name)
                and isinstance(n.ctx, ast.Load)
                and n.id in CURRENT_MUTABLE_CONSTANTS
                for n in ast.walk(function)
            ):
                failures.append(
                    "historical map depends on live CURRENT_MUTABLE authority: "
                    + function.name
                )

    literals = claims(accepted)
    for relative in (
        "scripts/checkpoint_runner.py",
        "scripts/source_authority.py",
        "scripts/current_source_authority.py",
    ):
        tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
        if claims(tree) - literals:
            failures.append(
                "historical exact dependency on CURRENT_MUTABLE: " + relative
            )
    failures.extend(_historical_test_ownership_failures(repo_root))
    return tuple(failures)


@lru_cache(maxsize=2)
def _parse_runner_source(source: str) -> ast.Module:
    return ast.parse(source)


def runner_tree(repo_root: Path) -> ast.Module:
    """Parse today's exact source, invalidating naturally when its text changes."""
    return _parse_runner_source(
        (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    )


@cache
def _historical_replacement_binding(relative: str, commit: str, blob: str) -> bool:
    binding = subprocess.run(
        ("git", "rev-parse", commit + ":" + relative),
        cwd=_ARCHIVE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return binding.returncode == 0 and binding.stdout.strip() == blob


def historical_constant(name: str) -> object:
    """Reconstruct immutable historical map material without current globals."""
    return deepcopy(historical_catalog(_ARCHIVE_ROOT)["historical_constants"][name])
