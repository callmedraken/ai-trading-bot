"""Current additive proof for reusing certified source across docs-only suffixes.

The exact-head resolver remains the historical owner in ``checkpoint_runner``.
This module only admits the newer, bounded integration composition when every
part of the source and CI lineage is independently proven.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.distributed_full import FULL_JOB_NAMES

REASON = "certified_feature_source_with_docs_only_descendant"
FEATURE_PREFIXES = (
    "feature/robinhood-",
    "feature/research-",
    "feature/test-suite-",
)
WORKFLOW_PATH = ".github/workflows/checkpoint-source-gates.yml"


def _require(condition: object) -> None:
    if not condition:
        raise ValueError("incomplete docs-descendant reuse proof")


def _page(value: object, field: str) -> list[dict[str, Any]]:
    _require(type(value) is dict)
    items = value.get(field)
    _require(type(items) is list and all(type(item) is dict for item in items))
    _require(type(value.get("total_count")) is int)
    _require(value["total_count"] == len(items) <= 100)
    return items


def _run_identity(
    run: Mapping[str, Any],
    *,
    repository: str,
    repository_id: int,
    workflow: Mapping[str, Any],
    head: str,
    branch: str,
    run_id: int,
) -> None:
    _require(type(run.get("id")) is int and run.get("id") == run_id)
    _require(type(run.get("run_attempt")) is int and run.get("run_attempt") == 1)
    _require(run.get("repository", {}).get("full_name") == repository)
    _require(
        type(run.get("repository", {}).get("id")) is int
        and run.get("repository", {}).get("id") == repository_id
    )
    _require(run.get("head_repository", {}).get("full_name") == repository)
    _require(
        type(run.get("head_repository", {}).get("id")) is int
        and run.get("head_repository", {}).get("id") == repository_id
    )
    _require(run.get("name") == workflow["name"])
    _require(run.get("workflow_id") == workflow["id"])
    _require(run.get("path") == WORKFLOW_PATH)
    _require(run.get("head_sha") == head and run.get("head_branch") == branch)
    _require(run.get("event") == "push")
    _require(run.get("status") == "completed")
    _require(run.get("conclusion") == "success")


def _job_success(
    jobs: Mapping[str, Mapping[str, Any]],
    name: str,
    *,
    run_id: int,
    head: str,
    steps: Sequence[str],
) -> None:
    job = jobs.get(name)
    _require(job is not None)
    _require(
        job.get("status") == "completed"
        and job.get("conclusion") == "success"
        and job.get("run_id") == run_id
        and job.get("run_attempt") == 1
        and job.get("head_sha") == head
    )
    step_list = job.get("steps")
    _require(type(step_list) is list)
    step_map = {step.get("name"): step for step in step_list}
    _require(len(step_map) == len(step_list))
    for step in steps:
        selected = step_map.get(step)
        _require(
            type(selected) is dict
            and selected.get("status") == "completed"
            and selected.get("conclusion") == "success"
        )


def _jobs_for_run(
    lookup: Callable[[str], object],
    *,
    prefix: str,
    run_id: int,
    head: str,
) -> dict[str, dict[str, Any]]:
    jobs = _page(
        lookup(f"{prefix}/actions/runs/{run_id}/attempts/1/jobs?per_page=100"),
        "jobs",
    )
    names = [job.get("name") for job in jobs]
    _require(all(type(name) is str for name in names))
    _require(len(names) == len(set(names)))
    _require(all(type(job.get("run_id")) is int for job in jobs))
    _require(all(job.get("run_id") == run_id for job in jobs))
    _require(all(type(job.get("run_attempt")) is int for job in jobs))
    _require(all(job.get("run_attempt") == 1 for job in jobs))
    _require(all(job.get("head_sha") == head for job in jobs))
    return {job["name"]: job for job in jobs}


def _prove_feature_full(
    lookup: Callable[[str], object],
    *,
    prefix: str,
    workflow: Mapping[str, Any],
    repository: str,
    repository_id: int,
    specs: Mapping[str, Any],
    head: str,
    branch: str,
    run: Mapping[str, Any],
    current_run_id: int,
    runner: Any,
) -> dict[str, Any] | None:
    checkpoint = runner.resolve_ci_checkpoint(specs, branch, "push")
    if (
        checkpoint is None
        or runner.resolve_ci_certification_profile(checkpoint) != "full"
    ):
        return None
    run_id = run.get("id")
    if type(run_id) is not int or not 0 < run_id < current_run_id:
        return None
    _run_identity(
        run,
        repository=repository,
        repository_id=repository_id,
        workflow=workflow,
        head=head,
        branch=branch,
        run_id=run_id,
    )
    detail = lookup(f"{prefix}/actions/runs/{run_id}")
    _require(type(detail) is dict)
    _run_identity(
        detail,
        repository=repository,
        repository_id=repository_id,
        workflow=workflow,
        head=head,
        branch=branch,
        run_id=run_id,
    )
    jobs = _jobs_for_run(lookup, prefix=prefix, run_id=run_id, head=head)
    expected = {
        "source-static",
        "active-tests",
        *FULL_JOB_NAMES,
        "full-tests",
        runner.REVIEWED_SKIPPED_CERTIFICATION_JOB,
        "source-gates",
    }
    _require(set(jobs) == expected)
    _job_success(
        jobs,
        "source-static",
        run_id=run_id,
        head=head,
        steps=(
            "Resolve source gate route",
            "Verify active checkpoint static authority",
        ),
    )
    _job_success(
        jobs,
        "active-tests",
        run_id=run_id,
        head=head,
        steps=("Verify active checkpoint tests",),
    )
    for lane in FULL_JOB_NAMES:
        _job_success(
            jobs,
            lane,
            run_id=run_id,
            head=head,
            steps=(
                "Run canonical certification profile",
                "Enforce canonical certification hygiene budget",
            ),
        )
    skipped = jobs["full-tests"]
    _require(
        skipped.get("status") == "completed"
        and skipped.get("conclusion") == "skipped"
        and skipped.get("steps") == []
    )
    skipped_certification = jobs[runner.REVIEWED_SKIPPED_CERTIFICATION_JOB]
    _require(
        skipped_certification.get("status") == "completed"
        and skipped_certification.get("conclusion") == "skipped"
        and skipped_certification.get("steps") == []
    )
    _job_success(
        jobs,
        "source-gates",
        run_id=run_id,
        head=head,
        steps=("Require source gate success",),
    )
    return {
        "head": head,
        "tree": None,
        "branch": branch,
        "run_id": run_id,
        "run_attempt": 1,
        "checkpoint": checkpoint,
        "profile": "full",
    }


def _prove_docs_gate(
    lookup: Callable[[str], object],
    *,
    prefix: str,
    workflow: Mapping[str, Any],
    repository: str,
    repository_id: int,
    head: str,
    branch: str,
    current_run_id: int,
) -> dict[str, Any] | None:
    from scripts import checkpoint_runner as runner

    runs = _page(
        lookup(
            f"{prefix}/actions/workflows/{workflow['id']}/runs"
            f"?head_sha={head}&event=push&per_page=100"
        ),
        "workflow_runs",
    )
    matches: list[dict[str, Any]] = []
    for run in runs:
        run_id = run.get("id")
        if (
            run.get("head_branch") != branch
            or type(run_id) is not int
            or not 0 < run_id < current_run_id
        ):
            continue
        _run_identity(
            run,
            repository=repository,
            repository_id=repository_id,
            workflow=workflow,
            head=head,
            branch=branch,
            run_id=run_id,
        )
        jobs = _jobs_for_run(lookup, prefix=prefix, run_id=run_id, head=head)
        from scripts.distributed_full import SKIPPED_FULL_JOB

        expected = {
            "source-static",
            "active-tests",
            "full-tests",
            runner.REVIEWED_SKIPPED_CERTIFICATION_JOB,
            SKIPPED_FULL_JOB,
            "source-gates",
        }
        if set(jobs) != expected:
            continue
        _job_success(
            jobs,
            "source-static",
            run_id=run_id,
            head=head,
            steps=("Classify changed paths",),
        )
        _job_success(
            jobs,
            "source-gates",
            run_id=run_id,
            head=head,
            steps=("Require source gate success",),
        )
        for name in (
            "active-tests",
            "full-tests",
            runner.REVIEWED_SKIPPED_CERTIFICATION_JOB,
            SKIPPED_FULL_JOB,
        ):
            skipped = jobs[name]
            _require(
                skipped.get("status") == "completed"
                and skipped.get("conclusion") == "skipped"
            )
        matches.append({"run_id": run_id, "run_attempt": 1, "branch": branch})
    if len(matches) != 1:
        return None
    return matches[0]


def _docs_suffix(
    repo_root: Path,
    runner: Any,
    *,
    candidate: str,
    head: str,
) -> tuple[list[dict[str, Any]], str]:
    commits = runner._git_output(
        repo_root, "rev-list", "--ancestry-path", "--reverse", f"{candidate}..{head}"
    ).splitlines()
    _require(commits)
    suffix: list[dict[str, Any]] = []
    for commit in commits:
        _require(re.fullmatch(r"[0-9a-f]{40}", commit))
        parents = runner._git_output(
            repo_root, "rev-list", "--parents", "-n", "1", commit
        ).split()
        _require(len(parents) == 2 and parents[0] == commit)
        paths = runner._git_output(
            repo_root, "diff", "--name-only", parents[1], commit
        ).splitlines()
        _require(paths and runner.classify_changed_paths(paths) == "DOCS_ONLY")
        suffix.append({"commit": commit, "parent": parents[1], "paths": paths})
    digest = hashlib.sha256(
        json.dumps(suffix, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return suffix, digest


def _develop_context(repo_root: Path, mode: str, runner: Any) -> dict[str, Any] | None:
    repository = runner.SOURCE_REPOSITORY
    if not (
        mode == "FULL"
        and runner.os.environ.get("GITHUB_EVENT_NAME") == "push"
        and runner.os.environ.get("GITHUB_REF") == "refs/heads/develop"
        and runner.os.environ.get("GITHUB_REF_NAME") == "develop"
        and runner.os.environ.get("GITHUB_REPOSITORY") == repository
        and runner.os.environ.get("GITHUB_SERVER_URL") == "https://github.com"
        and runner.os.environ.get("GITHUB_WORKFLOW") == "Checkpoint Source Gates"
        and runner.os.environ.get("GITHUB_WORKFLOW_REF")
        == (
            f"{repository}/.github/workflows/"
            "checkpoint-source-gates.yml@refs/heads/develop"
        )
    ):
        return None
    before_state = runner._git_state(repo_root)
    head = before_state["head"]
    if not (
        not before_state["porcelain"]
        and before_state["branch"] == "develop"
        and head == runner.os.environ.get("GITHUB_SHA")
        and runner._git_output(repo_root, "remote", "get-url", "origin")
        in {f"https://github.com/{repository}", f"https://github.com/{repository}.git"}
    ):
        return None
    event = json.loads(
        Path(runner.os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
    )
    base = event.get("before")
    _require(
        type(event) is dict
        and event.get("ref") == "refs/heads/develop"
        and event.get("after") == head
        and event.get("forced") is False
        and event.get("deleted") is False
        and type(base) is str
        and re.fullmatch(r"[0-9a-f]{40}", base)
        and base != "0" * 40
    )
    runner._git_output(repo_root, "merge-base", "--is-ancestor", base, str(head))
    return {
        "repository": repository,
        "before": before_state,
        "base": base,
        "head": str(head),
        "tree": str(before_state["tree"]),
        "current_run_id": int(runner.os.environ["GITHUB_RUN_ID"]),
        "repository_id": int(runner.os.environ["GITHUB_REPOSITORY_ID"]),
    }


def resolve_develop_ci_reuse(
    repo_root: Path,
    mode: str,
    *,
    exact_resolver: Callable[[Path, str], dict[str, object]],
) -> dict[str, object]:
    """Preserve exact reuse, then prove one bounded docs-only descendant."""
    fallback = {"reuse": False, "reason": "provenance_not_proven"}
    try:
        exact = exact_resolver(repo_root, mode)
        if exact.get("reuse"):
            return exact
        from scripts import checkpoint_runner as runner

        context = _develop_context(repo_root, mode, runner)
        if context is None:
            return exact
        prefix = f"repos/{context['repository']}"
        lookup = runner._github_ci_metadata
        repository = context["repository"]
        repository_id = context["repository_id"]
        workflow = lookup(f"{prefix}/actions/workflows/checkpoint-source-gates.yml")
        _require(type(workflow) is dict)
        _require(
            type(workflow.get("id")) is int
            and workflow.get("id") > 0
            and workflow.get("name") == "Checkpoint Source Gates"
            and workflow.get("path") == WORKFLOW_PATH
            and workflow.get("state") == "active"
        )
        specs = runner._checkpoint_specs()
        ancestors = runner._git_output(
            repo_root,
            "rev-list",
            "--ancestry-path",
            "--reverse",
            f"{context['base']}..{context['head']}",
        ).splitlines()
        candidates: list[dict[str, Any]] = []
        for candidate in ancestors:
            _require(re.fullmatch(r"[0-9a-f]{40}", candidate))
            if candidate == context["head"]:
                continue
            commit = lookup(f"{prefix}/git/commits/{candidate}")
            _require(type(commit) is dict)
            _require(commit.get("sha") == candidate)
            tree = commit.get("tree", {}).get("sha")
            _require(type(tree) is str and re.fullmatch(r"[0-9a-f]{40}", tree))
            runs = _page(
                lookup(
                    f"{prefix}/actions/workflows/{workflow['id']}/runs"
                    f"?head_sha={candidate}&event=push&per_page=100"
                ),
                "workflow_runs",
            )
            for run in runs:
                branch = run.get("head_branch")
                if type(branch) is not str or not branch.startswith(FEATURE_PREFIXES):
                    continue
                if run.get("head_sha") != candidate:
                    continue
                certified = _prove_feature_full(
                    lookup,
                    prefix=prefix,
                    workflow=workflow,
                    repository=repository,
                    repository_id=repository_id,
                    specs=specs,
                    head=candidate,
                    branch=branch,
                    run=run,
                    current_run_id=context["current_run_id"],
                    runner=runner,
                )
                if certified is not None:
                    certified["tree"] = tree
                    certified["run"] = run
                    candidates.append(certified)
        if len(candidates) != 1:
            return fallback
        certified = candidates[0]
        runner._git_output(
            repo_root,
            "merge-base",
            "--is-ancestor",
            certified["head"],
            context["head"],
        )
        suffix, suffix_digest = _docs_suffix(
            repo_root, runner, candidate=certified["head"], head=context["head"]
        )
        docs_gate = _prove_docs_gate(
            lookup,
            prefix=prefix,
            workflow=workflow,
            repository=repository,
            repository_id=repository_id,
            head=context["head"],
            branch=certified["branch"],
            current_run_id=context["current_run_id"],
        )
        if docs_gate is None:
            return fallback
        if runner._git_state(repo_root) != context["before"]:
            return {"reuse": False, "reason": "integration_source_changed"}
        return {
            "reuse": True,
            "reason": REASON,
            "reuse_kind": REASON,
            "repository": repository,
            "repository_id": repository_id,
            "current_develop_head": context["head"],
            "current_develop_tree": context["tree"],
            "head": context["head"],
            "tree": context["tree"],
            "develop_event_base": context["base"],
            "certified_source_head": certified["head"],
            "certified_source_tree": certified["tree"],
            "certified_feature_branch": certified["branch"],
            "certified_feature_run_id": certified["run_id"],
            "certified_feature_run_attempt": certified["run_attempt"],
            "checkpoint": certified["checkpoint"],
            "profile": certified["profile"],
            "docs_only_descendants": suffix,
            "docs_only_path_digest": suffix_digest,
            "current_docs_gate_run_id": docs_gate["run_id"],
            "current_docs_gate_run_attempt": docs_gate["run_attempt"],
            "current_docs_gate_branch": docs_gate["branch"],
        }
    except Exception:
        return fallback
