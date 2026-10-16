"""133-Q provider-free plan and separately authorized one-shot reprovision."""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from trading_bot.arch133_reprovision import generation, namespace, predecessor
from trading_bot.arch133_reprovision.material import (
    Material,
    canonical,
    digest,
    read_material,
    require_fresh,
    require_stale,
)

PLAN_SCHEMA = "arch133q-fresh-activation-reprovision-plan/v1"
RESULT_SCHEMA = "arch133q-fresh-activation-reprovision/v1"
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


def make_plan(path: Path) -> tuple[dict, Material, Material]:
    material = read_material(path)
    old, facts = predecessor.observe_admission()
    retained = generation.predecessor_material()
    if (
        retained.activation != old
        or digest(retained.host.to_json().encode())
        != predecessor.FILE_HASHES["host-binding.json"]
    ):
        raise ValueError("predecessor changed")
    now = utc_now()
    require_stale(old, now)
    window = require_fresh(material, old, facts["runtime"], now)
    namespace.require_vacant()
    with namespace.parent_guard() as parents:
        plan = {
            "schema": PLAN_SCHEMA,
            "material_sha256": material.sha256,
            "activation_sha256": digest(material.activation.to_json().encode()),
            "host_binding_sha256": digest(material.host.to_json().encode()),
            "predecessor": facts,
            "parents": parents,
            "fresh": window,
            "active_root": generation.ACTIVE,
            "staging_parent": generation.STAGING_PARENT,
            "staged_root": generation.STAGE,
            "archive_root": generation.ARCHIVE,
            **ZERO_EFFECTS,
        }
    return plan, material, retained


def authorize(plan_sha256: str) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("interactive authorization required")
    if (
        input(f"Enter AUTHORIZE ARCH133Q {plan_sha256}: ")
        != f"AUTHORIZE ARCH133Q {plan_sha256}"
    ):
        raise ValueError("authorization rejected")


def require_preserved(archive: dict, plan: dict) -> None:
    previous = plan["predecessor"]
    if (
        archive["root_identity"] != previous["root_identity"]
        or archive["state_sha256"] != previous["state_sha256"]
        or archive["paper_predecessor_sha256"] != previous["paper_predecessor_sha256"]
    ):
        raise ValueError("predecessor preservation rejected")
    for name, file_id in previous["namespace"]:
        found = archive["files"][name]
        if (
            found["identity"] != [previous["root_identity"][0], file_id]
            or found["sha256"] != previous["publication_files"][name]
        ):
            raise ValueError("predecessor preservation rejected")


def run(
    mode: str, path: Path, reviewed_plan_sha256: str | None = None
) -> tuple[int, dict]:
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
        plan, material, retained = make_plan(path)
        plan_sha256 = digest(canonical(plan).encode())
        if mode == "plan":
            return 0, {
                "schema": RESULT_SCHEMA,
                "status": "PASS",
                "disposition": "PLANNED_ONLY",
                "plan": plan,
                "plan_sha256": plan_sha256,
                **counters,
            }
        if reviewed_plan_sha256 != plan_sha256:
            raise ValueError("reviewed plan changed")
        authorize(plan_sha256)
        fresh_plan, _, _ = make_plan(path)
        if fresh_plan != plan:
            raise ValueError("authorization admission changed")
        # Import writer capability only after review and the independent human
        # authorization gate. No credential or native scheduler capability exists.
        from trading_bot.arch133_reprovision.native import WindowsEdges

        edges = WindowsEdges(counters)
        with namespace.parent_guard() as parents:
            if parents != plan["parents"]:
                raise ValueError("parent changed")
            namespace.require_vacant()
            # The entire fixed staging namespace is single-use. Every failure
            # after this fence is ambiguous and preserves all surviving evidence.
            attempted = True
            edges.stage(material)
            staged = generation.observe_generation(generation.STAGE, material)
            with namespace.staging_guard(), edges.publication_guard():
                old, facts = predecessor.observe_admission()
                if (
                    facts != plan["predecessor"]
                    or read_material(path).raw != material.raw
                    or generation.predecessor_material() != retained
                ):
                    raise ValueError("prepublication admission changed")
                require_stale(old, utc_now())
                # Complete independent re-observation before the only swap boundary.
                if generation.observe_generation(generation.STAGE, material) != staged:
                    raise ValueError("staging changed")
                require_fresh(material, old, facts["runtime"], utc_now())
                edges.archive()
                archived = generation.observe_generation(
                    generation.ARCHIVE, retained, archive=True
                )
                require_preserved(archived, plan)
                # Never publish an activation whose window expired while sealing
                # or independently observing its predecessor.
                require_fresh(material, old, facts["runtime"], utc_now())
                edges.publish()
                active = generation.observe_generation(generation.ACTIVE, material)
                if active != staged:
                    raise ValueError("active generation disagrees")
                if (
                    generation.observe_generation(
                        generation.ARCHIVE, retained, archive=True
                    )
                    != archived
                ):
                    raise ValueError("archive changed")
                final = namespace.final_namespace()
                if predecessor.observe_runtime() != facts["runtime"]:
                    raise ValueError("runtime changed")
                predecessor.require_administrator()
        return 0, {
            "schema": RESULT_SCHEMA,
            "status": "PASS",
            "disposition": "REPROVISIONED",
            "plan_sha256": plan_sha256,
            "material_sha256": material.sha256,
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
    # Only the isolated fixed launcher admits argv. No environment/config paths.
    args = sys.argv[1:]
    if (
        len(args) not in (3, 5)
        or args[1] != "--material-file"
        or (len(args) == 5 and args[3] != "--reviewed-plan-sha256")
    ):
        return 3
    code, evidence = run(args[0], Path(args[2]), args[4] if len(args) == 5 else None)
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return code
