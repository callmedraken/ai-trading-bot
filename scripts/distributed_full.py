"Current distributed FULL workflow and exact integration-reuse adapter."

from collections.abc import Callable
from copy import deepcopy
from typing import Any

FULL_JOB_NAMES = tuple(f"certification-full (broad-{index})" for index in range(1, 8))
SKIPPED_FULL_JOB = "certification-full (broad-${{ matrix.lane }})"

# Windows PowerShell 5.1 represents zero native stdout lines as $null. Capture
# the line vector explicitly and keep the detached-only condition in this owner.
FULL_DETACHED_BRANCH_BOOTSTRAP = """$CurrentBranchLines = @(git branch --show-current)
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to inspect certification checkout branch'
}
if ($CurrentBranchLines.Count -eq 0) {
    $CurrentBranch = ''
}
elseif ($CurrentBranchLines.Count -eq 1) {
    $CurrentBranch = ([string]$CurrentBranchLines[0]).Trim()
}
else {
    throw 'Ambiguous certification checkout branch output'
}
if ($CurrentBranch -ne '') {
    throw "Certification branch mismatch: $CurrentBranch"
}
"""


def full_matrix_job(predecessor: str) -> str:
    "Derive isolated FULL execution from the shared canonical toolchain/steps."
    job = predecessor.replace(
        (
            "    name: certification-tests (${{ needs.source-static."
            "outputs.checkpoint }} / ${{ needs.source-static.outputs"
            ".certification_profile }})"
        ),
        "    name: certification-full (broad-${{ matrix.lane }})",
    ).replace(
        "needs.source-static.outputs.certification_profile != ''",
        "needs.source-static.outputs.certification_profile == 'full'",
    )
    job = job.replace(
        "    steps:\n",
        (
            "    strategy:\n      fail-fast: false\n      matrix:\n    "
            "    lane: [1, 2, 3, 4, 5, 6, 7]\n\n    steps:\n"
        ),
        1,
    )
    job = job.replace(
        "          fetch-depth: 0",
        "          fetch-depth: 0\n          ref: ${{ github.sha }}",
        1,
    )
    job = job.replace(
        (
            "          CERT_PROFILE: ${{ needs.source-static.outputs"
            ".certification_profile }}"
        ),
        (
            "          CERT_PROFILE: full\n          FULL_LANE: ${{ m"
            "atrix.lane }}\n          SOURCE_STATIC_RESULT: ${{ needs"
            ".source-static.result }}\n          SOURCE_STATIC_HEAD: "
            "${{ github.sha }}"
        ),
    )
    job = job.replace(
        "              --profile $env:CERT_PROFILE `",
        (
            "              --profile $env:CERT_PROFILE `\n           "
            "   --lane $env:FULL_LANE `\n              --ci-source-st"
            "atic `"
        ),
    )
    job = job.replace(
        "          $CurrentBranch = (git branch --show-current).Trim()\n", ""
    )
    job = job.replace(
        (
            "          if ($CurrentBranch -ne $env:EXPECTED_BRANCH) {\n"
            '            throw "Certification branch mismatch: $CurrentBranch"\n'
            "          }\n"
        ),
        "".join(
            "          " + line + "\n"
            for line in FULL_DETACHED_BRANCH_BOOTSTRAP.splitlines()
        ),
    )
    job = job.replace(
        (
            "canonical-certification-${{ needs.source-static.outputs"
            ".certification_profile }}"
        ),
        "canonical-certification-full-broad-${{ matrix.lane }}",
    )
    # Missing/partial evidence is never a successful hygiene assertion.
    job = job.replace("            exit 0\n", "            exit 86\n")
    job = job.replace("if-no-files-found: ignore", "if-no-files-found: error")
    job = job.replace(
        "          $Wall = [double]$Summary.wall_seconds",
        (
            "          if ($Summary.status -ne 'passed' -or $Summary"
            ".executed_lanes.Count -ne 1 -or $Summary.executed_lanes"
            "[0] -ne 'broad-${{ matrix.lane }}') { exit 86 }\n       "
            "   $Wall = [double]$Summary.wall_seconds"
        ),
    )
    return "  certification-full:\n" + job


def full_aggregate(predecessor: str) -> str:
    "Require the selected canonical route and skip the irrelevant route."
    result = predecessor.replace(
        "full-tests, certification-tests]",
        "full-tests, certification-tests, certification-full]",
    )
    result = result.replace(
        "          REUSE:",
        (
            "          FULL_CERT_RESULT: ${{ needs.certification-ful"
            "l.result }}\n          REUSE:"
        ),
    )
    result = result.replace(
        '            test "$CERT_RESULT" = "skipped"',
        (
            '            test "$CERT_RESULT" = "skipped"\n           '
            ' test "$FULL_CERT_RESULT" = "skipped"'
        ),
    )
    result = result.replace(
        '            test "$CERT_RESULT" = "success"',
        (
            '            if [ "$CERT_PROFILE" = "full" ]; then\n     '
            '         test "$CERT_RESULT" = "skipped"\n              '
            'test "$FULL_CERT_RESULT" = "success"\n            elif ['
            ' "$CERT_PROFILE" = "robinhood" ]; then\n              te'
            'st "$CERT_RESULT" = "success"\n              test "$FULL'
            '_CERT_RESULT" = "skipped"\n            else\n            '
            "  exit 1\n            fi"
        ),
    )
    return result


def predecessor_workflow(workflow: str) -> str:
    "Validate the additive matrix then reconstruct input to the older owner."
    if "  certification-full:\n" not in workflow:
        return workflow
    before, _, rest = workflow.partition("  certification-tests:\n")
    robinhood, _, rest = rest.partition("  certification-full:\n")
    matrix, _, aggregate = rest.partition("  source-gates:\n")
    old = robinhood.replace(
        "needs.source-static.outputs.certification_profile == 'robinhood'",
        "needs.source-static.outputs.certification_profile != ''",
    )
    # Reconstruct the aggregate by reversing only the exact additive changes.
    original = "  source-gates:\n" + aggregate
    original = original.replace(
        "full-tests, certification-tests, certification-full]",
        "full-tests, certification-tests]",
    )
    original = original.replace(
        ("          FULL_CERT_RESULT: ${{ needs.certification-full.result }}\n"), ""
    )
    original = original.replace(
        (
            '            test "$CERT_RESULT" = "skipped"\n           '
            ' test "$FULL_CERT_RESULT" = "skipped"'
        ),
        '            test "$CERT_RESULT" = "skipped"',
    )
    start = original.find('            if [ "$CERT_PROFILE" = "full" ]; then\n')
    if start >= 0:
        end = original.find("            fi\n", start)
        original = (
            original[:start]
            + '            test "$CERT_RESULT" = "success"\n'
            + original[end + len("            fi\n") :]
        )
    if "  certification-full:\n" + matrix != full_matrix_job(
        old
    ) or "  source-gates:\n" + aggregate != full_aggregate(original):
        raise ValueError("Distributed FULL topology drift")
    return before + "  certification-tests:\n" + old + original


def _find_reusable_topology(predecessor: Callable, specs: Any, **kwargs: Any) -> dict:
    "Prove all seven jobs before applying the unchanged run/repository proof."
    lookup = kwargs["lookup"]
    originals = {}
    runs = {}

    def adapted(path: str) -> object:
        value = lookup(path)
        if not path.endswith("/jobs?per_page=100"):
            if type(value) is dict and "head_branch" in value and "id" in value:
                runs[value["id"]] = value
            return value
        if type(value) is not dict or type(value.get("jobs")) is not list:
            raise ValueError("Malformed job page")
        jobs = value["jobs"]
        if value.get("total_count") != len(jobs) or len(jobs) > 100:
            raise ValueError("Incomplete job page")
        names = [job["name"] for job in jobs]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate job identity")
        canonical = [
            job for job in jobs if job["name"].startswith("certification-full")
        ]
        if not canonical:
            # Historical ROBINHOOD/broad evidence remains valid; old FULL cannot
            # prove current distributed FULL execution.
            if any(
                name.startswith("certification-tests (") and name.endswith(" / full)")
                for name in names
            ):
                raise ValueError("Missing distributed FULL jobs")
            return value
        normalized = [deepcopy(job) for job in jobs if job not in canonical]
        if set(job["name"] for job in canonical) == set(FULL_JOB_NAMES):
            skipped = [
                job
                for job in normalized
                if job["name"].startswith("certification-tests (")
            ]
            if (
                len(skipped) != 1
                or skipped[0]["conclusion"] != "skipped"
                or skipped[0]["status"] != "completed"
                or skipped[0].get("steps") != []
            ):
                raise ValueError("Irrelevant canonical route was not skipped")
            binding = skipped[0]
            from scripts.checkpoint_runner import (
                REVIEWED_SKIPPED_CERTIFICATION_JOB,
                resolve_ci_certification_profile,
                resolve_ci_checkpoint,
            )

            run = runs[binding["run_id"]]
            checkpoint = resolve_ci_checkpoint(specs, run["head_branch"], "push")
            expected = f"certification-tests ({checkpoint} / full)"
            if resolve_ci_certification_profile(checkpoint) != "full" or binding[
                "name"
            ] not in {expected, REVIEWED_SKIPPED_CERTIFICATION_JOB}:
                raise ValueError("Wrong canonical profile")
            ids = [job.get("id") for job in canonical]
            if len(set(ids)) != 7 or any(type(value) is not int for value in ids):
                raise ValueError("FULL lanes require seven distinct job IDs")
            for job in canonical:
                if not (
                    job["status"] == "completed"
                    and job["conclusion"] == "success"
                    and job["run_attempt"] == 1
                    and all(
                        job[key] == binding[key]
                        for key in ("run_id", "run_attempt", "head_sha")
                    )
                ):
                    raise ValueError("Incomplete FULL lane success")
                steps = job["steps"]
                step_map = {step["name"]: step for step in steps}
                if len(step_map) != len(steps) or not all(
                    step_map.get(name, {}).get("status") == "completed"
                    and step_map[name].get("conclusion") == "success"
                    for name in (
                        "Run canonical certification profile",
                        "Enforce canonical certification hygiene budget",
                    )
                ):
                    raise ValueError("Missing FULL functional/hygiene success")
            combined = deepcopy(canonical[0])
            combined["name"] = expected
            normalized.remove(binding)
            normalized.append(combined)
        elif len(canonical) == 1 and canonical[0]["name"] == SKIPPED_FULL_JOB:
            job = canonical[0]
            if (
                job["status"] != "completed"
                or job["conclusion"] != "skipped"
                or job.get("steps") not in (None, [])
            ):
                raise ValueError("Unexpected distributed FULL execution")
            if any(name.endswith(" / full)") for name in names):
                raise ValueError("Skipped required FULL lanes")
            # Bind the skipped matrix to the same original run as every other job.
            if not all(
                job[key] == normalized[0][key]
                for key in ("run_id", "run_attempt", "head_sha")
            ):
                raise ValueError("Skipped matrix provenance drift")
        else:
            raise ValueError("Missing, malformed or extra FULL lane identity")
        originals[path] = jobs
        return {**value, "jobs": normalized, "total_count": len(normalized)}

    result = predecessor(specs, **{**kwargs, "lookup": adapted})
    if result.get("reuse"):
        path = (
            f"repos/{result['repository']}/actions/runs/{result['run_id']}"
            "/attempts/1/jobs?per_page=100"
        )
        if path in originals:
            result["jobs"] = originals[path]
            if result.get("profile") == "full":
                result["full_lane_jobs"] = list(FULL_JOB_NAMES)
    return result


def find_reusable(predecessor: Callable, specs: Any, **kwargs: Any) -> dict:
    """Validate one reviewed canonical retry without repinning historical policy.

    Attempt 2 is invoked only by the operator after independent review. This
    read-only adapter does not decide retry eligibility or launch retries.
    The historical evaluator consumes a projection of the *current attempt's*
    complete job view. Only attempt numbers are projected after consistency
    checks; all repository/workflow/source/topology/step checks still apply.
    Original run/job metadata is returned as evidence, including carried jobs'
    original timestamps. No attempt-1 API evidence is modified or replaced.
    """
    from scripts.checkpoint_runner import (
        resolve_ci_certification_profile,
        resolve_ci_checkpoint,
    )

    lookup = kwargs["lookup"]
    runs = {}
    details = {}
    job_views = {}

    def project_run(run):
        checkpoint = resolve_ci_checkpoint(specs, run.get("head_branch"), "push")
        if (
            type(run.get("run_attempt")) is int
            and run["run_attempt"] == 2
            and resolve_ci_certification_profile(checkpoint) in {"full", "robinhood"}
        ):
            return {**run, "run_attempt": 1}
        return run

    def current_attempt_view(path: str) -> object:
        if "/attempts/1/jobs?" in path:
            run_id = int(path.split("/actions/runs/", 1)[1].split("/", 1)[0])
            run = runs[run_id]
            attempt = run["run_attempt"]
            if type(attempt) is not int or attempt not in (1, 2):
                raise ValueError("Canonical attempts are limited to 1 and 2")
            actual_path = path.replace("/attempts/1/", f"/attempts/{attempt}/")
            value = lookup(actual_path)
            if type(value) is not dict or type(value.get("jobs")) is not list:
                raise ValueError("Malformed current-attempt job view")
            jobs = value["jobs"]
            if any(
                type(job) is not dict
                or type(job.get("run_attempt")) is not int
                or job["run_attempt"] != attempt
                or job.get("run_id") != run_id
                or job.get("head_sha") != run["head_sha"]
                for job in jobs
            ):
                raise ValueError("Current-attempt job provenance mismatch")
            job_views[run_id] = jobs
            return {**value, "jobs": [{**job, "run_attempt": 1} for job in jobs]}

        value = lookup(path)
        if type(value) is dict and type(value.get("workflow_runs")) is list:
            for run in value["workflow_runs"]:
                runs[run["id"]] = run
            return {
                **value,
                "workflow_runs": [project_run(run) for run in value["workflow_runs"]],
            }
        if type(value) is dict and "head_branch" in value and "id" in value:
            listed = runs[value["id"]]
            if (
                type(value.get("run_attempt")) is not int
                or value["run_attempt"] != listed["run_attempt"]
            ):
                raise ValueError("Run attempt changed during proof")
            details[value["id"]] = value
            return project_run(value)
        return value

    try:
        result = _find_reusable_topology(
            predecessor, specs, **{**kwargs, "lookup": current_attempt_view}
        )
    except (KeyError, ValueError, TypeError, IndexError):
        return {"reuse": False, "reason": "provenance_not_proven"}
    if result.get("reuse"):
        run_id = result["run_id"]
        result["run_attempt"] = details[run_id]["run_attempt"]
        result["run"] = details[run_id]
        result["jobs"] = job_views[run_id]
    return result
