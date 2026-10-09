"""133-W read-only plan and separately authorized sealed-predecessor recovery."""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime

from trading_bot.arch133_reprovision import generation, namespace
from trading_bot.arch133_reprovision.material import (
    Material,
    canonical,
    digest,
    read_material,
    require_fresh,
    require_stale,
)
from trading_bot.arch133_reprovision_recovery import admission

PLAN_SCHEMA = "arch133w-sealed-predecessor-recovery-plan/v1"
RESULT_SCHEMA = "arch133w-sealed-predecessor-recovery/v1"
ZERO_EFFECTS = dict.fromkeys(
    (
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
    ),
    0,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def make_plan() -> tuple[dict, Material, Material]:
    facts, material, retained = admission.observe_state()
    now = utc_now()
    require_stale(retained.activation, now)
    window = require_fresh(material, retained.activation, facts["runtime"], now)
    return (
        {"schema": PLAN_SCHEMA, **facts, "fresh": window, **ZERO_EFFECTS},
        material,
        retained,
    )


def plan_hash(plan: dict) -> str:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("plan schema rejected")
    return digest(canonical(plan).encode())


def authorize(plan_sha256: str) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("interactive authorization required")
    if (
        input(f"Enter AUTHORIZE ARCH133W {plan_sha256}: ")
        != f"AUTHORIZE ARCH133W {plan_sha256}"
    ):
        raise ValueError("authorization rejected")


def require_absent(root: str) -> None:
    from contextlib import ExitStack

    with ExitStack() as held:
        if admission.presence(root, held) is not None:
            raise ValueError("namespace must be absent")


def run(mode: str, reviewed_plan_sha256: str | None = None) -> tuple[int, dict]:
    counters = dict(ZERO_EFFECTS)
    attempted = False
    try:
        if (
            mode not in ("plan", "execute-once")
            or (mode == "plan" and reviewed_plan_sha256 is not None)
            or (
                mode == "execute-once"
                and (
                    type(reviewed_plan_sha256) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", reviewed_plan_sha256) is None
                )
            )
        ):
            raise ValueError("arguments rejected")
        plan, material, retained = make_plan()
        sha = plan_hash(plan)
        if mode == "plan":
            return 0, {
                "schema": RESULT_SCHEMA,
                "status": "PASS",
                "disposition": "PLANNED_ONLY",
                "plan": plan,
                "plan_sha256": sha,
                **counters,
            }
        if reviewed_plan_sha256 != sha:
            raise ValueError("reviewed plan changed")
        authorize(sha)
        fresh_plan, fresh_material, fresh_retained = make_plan()
        if (
            fresh_plan != plan
            or fresh_material != material
            or fresh_retained != retained
        ):
            raise ValueError("authorization admission changed")
        from trading_bot.arch133_reprovision_recovery.native import WindowsEdges

        edges = WindowsEdges()
        with (
            namespace.parent_guard() as parents,
            namespace.staging_guard(),
            edges.publication_guard() as held_roots,
        ):
            if (
                parents != plan["parents"]
                or held_roots["parent"] != parents[namespace.PARENTS[1]]
            ):
                raise ValueError("parent changed")
            for root, key in (
                (generation.ACTIVE, "predecessor"),
                (generation.STAGE, "stage"),
            ):
                if held_roots[root] != {
                    name: plan[key][name] for name in held_roots[root]
                }:
                    raise ValueError("held source changed")
            facts, observed_material, observed_retained = admission.observe_state()
            if (
                facts != {key: plan[key] for key in facts}
                or observed_material != material
                or observed_retained != retained
            ):
                raise ValueError("pre-rename V state changed")
            require_stale(retained.activation, utc_now())
            require_fresh(material, retained.activation, facts["runtime"], utc_now())
            attempted = True
            counters["archive_writes"] += 1
            edges.archive()
            archived = generation.observe_generation(
                generation.ARCHIVE, retained, archive=True
            )
            if archived != plan["predecessor"]:
                raise ValueError("archive changed")
            require_absent(generation.ACTIVE)
            if (
                generation.observe_generation(generation.STAGE, material)
                != plan["stage"]
            ):
                raise ValueError("stage changed")
            require_fresh(material, retained.activation, facts["runtime"], utc_now())
            counters["publication_writes"] += 1
            edges.publish()
            active = generation.observe_generation(generation.ACTIVE, material)
            if (
                active != plan["stage"]
                or generation.observe_generation(
                    generation.ARCHIVE, retained, archive=True
                )
                != archived
            ):
                raise ValueError("final generation changed")
            require_absent(generation.STAGE)
            final = namespace.final_namespace()
            staging = final[generation.STAGING_PARENT]
            if (
                staging["observation"]["identity"]
                != tuple(plan["staging_parent_identity"])
                or staging["security_sha256"] != plan["staging_parent_security_sha256"]
                or admission.observe_runtime() != facts["runtime"]
                or read_material(admission.MATERIAL_PATH).raw != material.raw
            ):
                raise ValueError("final admission changed")
            if admission.administrator_sid() != plan["administrator_sid"]:
                raise ValueError("final administrator changed")
        return 0, {
            "schema": RESULT_SCHEMA,
            "status": "PASS",
            "disposition": "REPROVISION_RECOVERED",
            "plan_sha256": sha,
            "material_sha256": material.sha256,
            "reviewed_u_plan_sha256": admission.REVIEWED_U_PLAN_SHA256,
            "archived_predecessor": archived,
            "active_generation": active,
            "namespace": final,
            **counters,
        }
    except BaseException:
        return (4 if attempted else 3), {
            "schema": RESULT_SCHEMA,
            "status": "INDETERMINATE" if attempted else "BLOCKED",
            "disposition": "PRESERVE_RECONCILE_NO_RETRY"
            if attempted
            else "ADMISSION_REJECTED",
            **counters,
        }


def main() -> int:
    args = sys.argv[1:]
    if args == ["plan"]:
        code, evidence = run("plan")
    elif len(args) == 3 and args[:2] == ["execute-once", "--reviewed-plan-sha256"]:
        code, evidence = run("execute-once", args[2])
    else:
        code, evidence = run("INVALID")
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return code
