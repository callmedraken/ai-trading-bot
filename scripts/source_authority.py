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
        "REVIEWED_SKIPPED_CERTIFICATION_JOB",
    }
)


def current_owner(relative: str) -> str | None:
    """Assign each current mutable concept to exactly one semantic owner."""
    if relative in CURRENT_MUTABLE_CONSTANTS:
        return "checkpoint_runner"
    if "/" not in relative and (
        relative in historical_catalog(_ARCHIVE_ROOT)["mutable_symbols"]
        or relative
        in {
            "evaluate_source_authority",
            "current_authority_check",
            "develop_static_checkpoints",
            "current_owner",
            "classify_path",
            "ownership_failures",
            "blob_matches",
            "ast_matches",
            "runner_tree",
            "_source_pytest_basetemp",
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
    }:
        return "checkpoint_runner"
    if relative == "scripts/run_test_certification.py":
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
