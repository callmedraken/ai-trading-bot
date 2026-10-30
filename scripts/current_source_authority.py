"""One deterministic static-authority evaluator for publication and CI.

Only repository source and immutable Git objects are read here. Reporting,
focused tests, remote identity admission and canonical certification are callers.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from scripts import source_authority as ownership


class PublicationContext(StrEnum):
    FEATURE = "FEATURE"
    PROSPECTIVE_DEVELOP = "PROSPECTIVE_DEVELOP"


@dataclass(frozen=True)
class AuthorityResult:
    context: PublicationContext
    head: str
    tree: str
    checkpoints: tuple[str, ...]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def develop_static_checkpoints(repo_root: Path) -> tuple[str, ...]:
    """Read exactly the full-batch source-static routing used by the workflow."""
    from scripts import checkpoint_runner as runner

    workflow = (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"^  AI_TRADING_BOT_ACTIVE_CHECKPOINTS: >-\n((?: +arch[^\n]+\n)+)",
        workflow,
        re.MULTILINE,
    )
    if match is None:
        raise ValueError("develop source-static routing unavailable")
    names = tuple(re.findall(r"^ +(arch[^\s`]+)", match[1], re.MULTILINE))
    if (
        not names
        or len(names) != len(set(names))
        or any(name not in runner._checkpoint_specs() for name in names)
    ):
        raise ValueError("develop source-static routing is not registered and unique")
    return names


def historical_preflight_dispatch_failures(repo_root: Path) -> tuple[str, ...]:
    """Preserve the Architecture 146/134 preflight authority graph exactly.

    This static check never dispatches a preflight. Additive outer layers belong
    here rather than in predecessor authorities that own their own semantics.
    """
    from scripts import checkpoint_runner as runner

    failures = []
    outer = "_arch146_partial_state_preflight_checkpoint"
    if runner.preflight_checkpoint is not getattr(runner, outer):
        failures.append("current preflight outer dispatcher drift")
    tree = ast.parse(
        (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    )
    declarations = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    functions = {node.name: node for node in declarations}
    if len(functions) != len(declarations):
        return (*failures, "current preflight duplicate declarations")
    expected_outer = ast.parse(
        "def _arch146_partial_state_preflight_checkpoint("
        "spec: CheckpointSpec, *, repo_root: Path, evidence_root: Path"
        ") -> tuple[bool, Path | None]:"
        "\n    if spec.name != ARCH146_PARTIAL_STATE_NAME:"
        "\n        return _arch134_readonly_diagnostic_r3_preflight_checkpoint("
        "spec, repo_root=repo_root, evidence_root=evidence_root)"
        "\n    if spec != _checkpoint_specs()[ARCH146_PARTIAL_STATE_NAME] "
        "or _arch146_partial_state_authority_check(repo_root):"
        "\n        raise RuntimeError("
        "'Partial-state observer source/registration rejected')"
        "\n    return _PRE_READONLY_PREFLIGHT("
        "spec, repo_root=repo_root, evidence_root=evidence_root)"
    ).body[0]
    if outer not in functions or ast.dump(functions[outer]) != ast.dump(expected_outer):
        failures.append("current preflight observer routing drift")
    for name, checkpoint, delegate in (
        (
            "_arch134_readonly_diagnostic_r3_preflight_checkpoint",
            "ARCH134_READONLY_DIAGNOSTIC_R3_NAME",
            "_arch134_readonly_diagnostic_r2_preflight_checkpoint",
        ),
        (
            "_arch134_readonly_diagnostic_r2_preflight_checkpoint",
            "ARCH134_READONLY_DIAGNOSTIC_R2_NAME",
            "_readonly_preflight_checkpoint",
        ),
    ):
        expected_guard = ast.parse(
            f"if spec.name != {checkpoint}:"
            f"\n    return {delegate}(spec, repo_root=repo_root, "
            "evidence_root=evidence_root)"
        ).body[0]
        function = functions.get(name)
        if (
            function is None
            or not function.body
            or ast.dump(function.body[0]) != ast.dump(expected_guard)
            or getattr(runner, name).__name__ != name
        ):
            failures.append("current preflight delegation drift: " + name)
    # Existing SECURITY_SEMANTIC maps remain the exact owners of whole R2/R3
    # wrappers, including evidence-root guards and absence of protected dispatch.
    for pins in (
        runner.ARCH134_READONLY_DIAGNOSTIC_R2_DISPATCH_PINS,
        runner.ARCH134_READONLY_DIAGNOSTIC_R3_DISPATCH_PINS,
    ):
        for name, pin in pins.items():
            if name not in functions or not ownership.ast_matches(
                repo_root, name, functions[name], pin
            ):
                failures.append("current preflight security dispatch drift: " + name)
    for name, pin in (
        (
            "_arch134_readonly_diagnostic_r1_preflight",
            runner.ARCH134_READONLY_DIAGNOSTIC_R1_DISPATCH_AST,
        ),
        (
            "_readonly_preflight_checkpoint",
            runner.ARCH134_READONLY_DIAGNOSTIC_R1_PREFLIGHT_AST,
        ),
    ):
        if name not in functions or not ownership.ast_matches(
            repo_root, name, functions[name], pin
        ):
            failures.append("current preflight security dispatch drift: " + name)
    specs = runner._checkpoint_specs()
    for name, preflight in (
        (runner.ARCH146_PARTIAL_STATE_NAME, runner._arch146_partial_state_preflight),
        (
            runner.ARCH134_READONLY_DIAGNOSTIC_R1_NAME,
            runner._arch134_readonly_diagnostic_r1_preflight,
        ),
        (
            runner.ARCH134_READONLY_DIAGNOSTIC_R2_NAME,
            runner._arch134_readonly_diagnostic_r2_preflight,
        ),
        (
            runner.ARCH134_READONLY_DIAGNOSTIC_R3_NAME,
            runner._arch134_readonly_diagnostic_r3_preflight,
        ),
    ):
        spec = specs.get(name)
        if spec is None or spec.preflight is not preflight or spec.execute is not None:
            failures.append("current preflight registration drift: " + name)
    predecessor = specs.get(runner.ARCH146_PRE_B2_NAME)
    if (
        predecessor is None
        or predecessor.preflight is not None
        or predecessor.execute is not None
    ):
        failures.append("current preflight source-only predecessor drift")
    return tuple(failures)


def current_preflight_dispatch_failures(repo_root: Path) -> tuple[str, ...]:
    """Own the current Architecture 147 route without host dispatch."""
    from scripts import checkpoint_runner as runner

    del repo_root
    spec = runner._checkpoint_specs().get(runner.ARCH147_NAME)
    if spec is None:
        return ("Architecture 147 checkpoint registration missing",)
    failures = []
    if spec.preflight is not None:
        failures.append("Architecture 147 current preflight must be None")
    if spec.execute is not None:
        failures.append("Architecture 147 current execute must be None")
    if runner.CURRENT_ACTIVE_CI_CHECKPOINTS[0] != runner.ARCH147_NAME:
        failures.append("Architecture 147 is not the current first checkpoint")
    if any(
        name in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
        for name in (
            runner.ARCH146_PARTIAL_STATE_NAME,
            runner.ARCH146_PRE_B2_NAME,
            runner.ARCH146B1_NAME,
        )
    ):
        failures.append("retired Architecture 146 checkpoint remains current")
    return tuple(failures)


def current_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Compose canonical current owners, independently of historical blobs."""
    from scripts import checkpoint_runner as runner
    from scripts import run_test_certification as certification

    failures = list(ownership.ownership_failures(repo_root))
    failures.extend(current_preflight_dispatch_failures(repo_root))
    failures.extend(certification.static_toolchain_contract_failures(repo_root))
    specs = runner._checkpoint_specs()
    if any(name != spec.name for name, spec in specs.items()):
        failures.append("current checkpoint registry identity drift")
    for name, spec in specs.items():
        if (
            type(spec.tests) is not tuple
            or not spec.tests
            or any(
                type(path) is not str or not (repo_root / path).is_file()
                for path in spec.tests
            )
        ):
            failures.append("current checkpoint test inventory drift: " + name)
        if (
            type(spec.ruff_paths) is not tuple
            or not spec.ruff_paths
            or any(
                type(path) is not str or not (repo_root / path).exists()
                for path in spec.ruff_paths
            )
        ):
            failures.append("current checkpoint static inventory drift: " + name)
    for name, profile in runner.CI_CERTIFICATION_PROFILES.items():
        if name not in specs or profile not in runner.CI_CERTIFICATION_PROFILE_VALUES:
            failures.append("current checkpoint certification mapping drift: " + name)
    workflow = (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
        encoding="utf-8"
    )
    if not runner._arch134_current_batch_workflow_is_reviewed(workflow):
        failures.append("current CI workflow topology drift")
    develop_static_checkpoints(repo_root)
    inventory = certification.discover_inventory(repo_root)
    profiles = {
        p: certification.select_inventory(inventory, p) for p in certification.PROFILES
    }
    certification.validate_classification(inventory, profiles)
    for profile, selected in profiles.items():
        lanes = certification.build_lanes(repo_root, selected, profile)
        if not lanes or any(not modules for modules in lanes.values()):
            failures.append("current certification lane topology drift: " + profile)
        certification.validate_partitions(selected, tuple(lanes.values()))
    # Diagnostic and rename-free security contracts remain current exact-source
    # checks in the checkpoint-specific authority graph, never host execution.
    failures.extend(runner._arch134_readonly_diagnostic_graph_check(repo_root))
    return tuple(failures)


def evaluate_source_authority(
    candidate_source: Path,
    *,
    publication_context: PublicationContext,
    checkpoints: Sequence | None = None,
) -> AuthorityResult:
    """Apply FEATURE or PROSPECTIVE_DEVELOP to the same static implementation.

    A context selects the source-owned authority set, never another evaluator.
    No environment impersonation, merge, checkout, ref update, profile execution,
    host preflight or protected dispatch occurs here.
    """
    from scripts import checkpoint_runner as runner

    context = PublicationContext(publication_context)
    before = runner._git_state(candidate_source)
    if before["porcelain"]:
        return AuthorityResult(
            context,
            str(before["head"]),
            str(before["tree"]),
            (),
            ("candidate source requires a clean committed tree",),
        )
    try:
        failures = list(current_authority_check(candidate_source))
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, RuntimeError) as exc:
        failures = ["current authority unavailable: " + type(exc).__name__]
    specs = runner._checkpoint_specs()
    if checkpoints is None:
        if context is PublicationContext.FEATURE:
            checkpoint = runner.resolve_ci_checkpoint(
                specs, str(before["branch"]), "push"
            )
            names = (
                (checkpoint,)
                if checkpoint is not None
                else develop_static_checkpoints(candidate_source)
            )
        else:
            names = develop_static_checkpoints(candidate_source)
        checks = tuple(specs[name] for name in names)
    else:
        checks = tuple(checkpoints)
        names = tuple(spec.name for spec in checks)
    if (
        context is PublicationContext.PROSPECTIVE_DEVELOP
        and before["branch"] == "develop"
        and names != develop_static_checkpoints(candidate_source)
    ):
        failures.append("develop CI authority set differs from prospective routing")
    if not names or len(names) != len(set(names)):
        failures.append("authority set must be nonempty and unique")
    for spec in checks:
        try:
            failures.extend(
                spec.name + ": " + failure
                for failure in spec.authority_check(candidate_source)
            )
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            SyntaxError,
            RuntimeError,
        ) as exc:
            failures.append(
                spec.name + ": authority unavailable: " + type(exc).__name__
            )
    if runner._git_state(candidate_source) != before:
        failures.append("authority evaluation changed candidate Git state")
    return AuthorityResult(
        context, str(before["head"]), str(before["tree"]), names, tuple(failures)
    )
