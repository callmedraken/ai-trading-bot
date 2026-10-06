"""133-H Q133-2 planning and separately authorized, one-shot publication.

No activation is generated here. The input is an externally reviewed canonical
activation and HostBinding, including the expected empty-paper fingerprint.
Native effects are confined to the fixed Arch133 namespace; source CI registers
this checkpoint with no preflight/execute callback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from trading_bot.review_paper import unattended_host_identity as identity
from trading_bot.review_paper.unattended_activation import (
    ReviewPaperActivation,
    ReviewPaperWakeState,
)
from trading_bot.review_paper.unattended_scheduler import (
    build_unattended_scheduler_spec,
)
from trading_bot.review_paper.unattended_state_verifier import snapshot_unattended_state
from trading_bot.robinhood_execute_qualification_verifier import (
    qualification_fingerprint,
    read_qualification_store,
)

MATERIAL_SCHEMA = "arch133-host-publication-material/v1"
PLAN_SCHEMA = "arch133-host-publication-plan/v1"
TARGET_HEAD = "65f0d40217f8ce129224531a5151f4acea889d89"
TARGET_TREE = "16cb734cbeaa9e97aaf9e2d521d922fbbc7b7ae2"
MAX_MATERIAL_BYTES = 32768
FINAL_NAMES = frozenset(
    {"paper.sqlite", "wake.sqlite", "activation.json", "host-binding.json"}
)


class PublicationError(RuntimeError):
    """Fixed diagnostics only; partial mutation always requires reconciliation."""


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class PublicationMaterial:
    activation: ReviewPaperActivation
    binding: identity.HostBinding
    raw: bytes


def parse_publication_material(raw: bytes) -> PublicationMaterial:
    """One bounded canonical file/stdin envelope; reuse both accepted parsers."""
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_MATERIAL_BYTES:
            raise ValueError
        payload = json.loads(raw)
        if type(payload) is not dict or set(payload) != {
            "schema",
            "activation_json",
            "host_binding_json",
        }:
            raise ValueError
        if payload["schema"] != MATERIAL_SCHEMA or canonical(payload) != raw:
            raise ValueError
        activation = ReviewPaperActivation.from_json(payload["activation_json"])
        binding = identity.HostBinding.from_json(payload["host_binding_json"])
        runtime = binding.runtime
        if (
            (runtime.source_head, runtime.source_tree) != (TARGET_HEAD, TARGET_TREE)
            or runtime.python_sha256 != identity.PRODUCTION_PYTHON_SHA256
            or runtime.python_version != identity.PRODUCTION_PYTHON_VERSION
            or (
                activation.source_head,
                activation.source_tree,
                activation.deployment_identity,
            )
            != (TARGET_HEAD, TARGET_TREE, runtime.deployment_identity)
            or activation.store_path != str(identity.PAPER_PATH)
            or activation.store_identity != binding.store_identity
            or binding.activation_sha256
            != hashlib.sha256(activation.to_json().encode("utf-8")).hexdigest()
            or binding.oauth_valid_until <= activation.created_at
        ):
            raise ValueError
        build_unattended_scheduler_spec(activation)
        return PublicationMaterial(activation, binding, raw)
    except BaseException:
        raise PublicationError("publication material rejected") from None


def _plan(material: PublicationMaterial, backend: object) -> dict:
    facts = backend.observe_absent(material.binding.runtime)
    scheduler = asdict(build_unattended_scheduler_spec(material.activation))
    for key in ("start_boundary", "end_boundary"):
        scheduler[key] = scheduler[key].isoformat(timespec="microseconds")
    payload = {
        "schema": PLAN_SCHEMA,
        "material_sha256": hashlib.sha256(material.raw).hexdigest(),
        "activation": json.loads(material.activation.to_json()),
        "host_binding": json.loads(material.binding.to_json()),
        "host_facts": facts,
        "scheduler": scheduler,
        "final_names": sorted(FINAL_NAMES),
        "oauth_reads": 0,
        "provider_calls": 0,
        "scheduler_reads": 0,
        "scheduler_writes": 0,
        "broker_effects": 0,
        "publication_writes": 0,
    }
    return {**payload, "plan_sha256": hashlib.sha256(canonical(payload)).hexdigest()}


def verify_publication(material: PublicationMaterial, backend: object) -> dict:
    """Independently reopen exact bytes and both databases, with held ACL guards."""
    activation, binding = material.activation, material.binding
    with backend.pin_complete() as pinned:
        if pinned.names() != FINAL_NAMES:
            raise PublicationError("publication inventory disagreement")
        if pinned.read("activation.json") != activation.to_json().encode(
            "utf-8"
        ) or pinned.read("host-binding.json") != binding.to_json().encode("utf-8"):
            raise PublicationError("publication bytes disagreement")
        # Exercise accepted parsers independently on reopened bytes as well.
        if (
            ReviewPaperActivation.from_json(
                pinned.read("activation.json").decode("utf-8")
            )
            != activation
        ):
            raise PublicationError("publication activation disagreement")
        if (
            identity.HostBinding.from_json(
                pinned.read("host-binding.json").decode("utf-8")
            )
            != binding
        ):
            raise PublicationError("publication binding disagreement")
        metadata, columns, rows = read_qualification_store(identity.PAPER_PATH)
        paper = qualification_fingerprint(metadata, columns, rows)["sha256"]
        if (
            metadata
            != [
                ["schema_version", "2"],
                ["starting_cash", str(activation.starting_cash)],
            ]
            or rows
            or paper != binding.paper_predecessor_sha256
        ):
            raise PublicationError("publication paper disagreement")
        state = snapshot_unattended_state(identity.STATE_PATH)
        current = state.current(activation)
        if (
            len(state.activations) != 1
            or len(state.wakes) != 1
            or current.wake.state is not ReviewPaperWakeState.READY
            or current.revision != 0
            or current.wake.updated_at != activation.created_at
        ):
            raise PublicationError("publication state disagreement")
        pinned.finish()
        return {
            "activation_id": str(activation.activation_id),
            "wake_id": str(current.wake.wake_id),
            "state": "READY",
            "revision": 0,
            "state_fingerprint": state.fingerprint,
            "paper_predecessor_sha256": paper,
            "activation_sha256": binding.activation_sha256,
            "host_binding_sha256": hashlib.sha256(
                binding.to_json().encode("utf-8")
            ).hexdigest(),
            "store_identity": str(binding.store_identity),
            "source_head": binding.runtime.source_head,
            "source_tree": binding.runtime.source_tree,
            "python_sha256": binding.runtime.python_sha256,
            "python_version": binding.runtime.python_version,
        }


def _execute_once(
    material: PublicationMaterial, reviewed: str, authorization: str, backend: object
) -> dict:
    """One attempt, no compensation. A partial root permanently blocks re-entry."""
    try:
        with backend.parent_guard():
            plan = _plan(material, backend)
            if (
                type(reviewed) is not str
                or re.fullmatch(r"[0-9a-f]{64}", reviewed) is None
                or plan["plan_sha256"] != reviewed
                or authorization != "AUTHORIZE Q133-2 " + reviewed
            ):
                raise ValueError
            backend.arm_once(reviewed, authorization)
            backend.create_root_once()
            backend.initialize_paper(material.activation)
            backend.admit_ready(material.activation)
            backend.publish_once(
                "activation.json", material.activation.to_json().encode("utf-8")
            )
            backend.publish_once(
                "host-binding.json", material.binding.to_json().encode("utf-8")
            )
            # Verify all content while the root is still Administrator/SYSTEM-only.
            backend.seal_files()
            before = verify_publication(material, backend)
            backend.admit_trading_root()
            after = verify_publication(material, backend)
            if before != after:
                raise ValueError
            backend.finish()
            return {
                **after,
                "schema": "arch133-host-publication-result/v1",
                "status": "PASS",
                "plan_sha256": reviewed,
                "oauth_reads": 0,
                "provider_calls": 0,
                "scheduler_reads": 0,
                "scheduler_writes": 0,
                "broker_effects": 0,
            }
    except BaseException:
        raise PublicationError(
            "publication stopped; no retry or repair authorized"
        ) from None


def plan_publication(raw: bytes) -> dict:
    from trading_bot.review_paper.unattended_publication_windows import (
        WindowsPublication,
    )

    try:
        material = parse_publication_material(raw)
        with WindowsPublication() as backend, backend.parent_guard():
            result = _plan(material, backend)
            if backend.observe_absent(material.binding.runtime) != result["host_facts"]:
                raise ValueError
            backend.finish()
            return result
    except BaseException:
        raise PublicationError("publication planning failed closed") from None


def execute_publication(raw: bytes, reviewed: str, authorization: str) -> dict:
    from trading_bot.review_paper.unattended_publication_windows import (
        WindowsPublication,
    )

    try:
        material = parse_publication_material(raw)
        with WindowsPublication() as backend:
            return _execute_once(material, reviewed, authorization, backend)
    except BaseException:
        raise PublicationError(
            "publication stopped; no retry or repair authorized"
        ) from None


class _PublicationParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PublicationError("publication arguments rejected")


def main(argv: list[str] | None = None) -> int:
    """File or bounded binary stdin for material; execute needs interactive stdin."""
    try:
        parser = _PublicationParser(add_help=False, exit_on_error=False)
        parser.add_argument("mode", choices=("plan", "execute-once"))
        parser.add_argument("--material-file", required=True)
        parser.add_argument("--reviewed-plan-sha256")
        args, unknown = parser.parse_known_args(argv)
        if unknown or (args.mode == "plan" and args.reviewed_plan_sha256 is not None):
            raise ValueError
        if args.mode == "execute-once" and (
            not sys.stdin.isatty()
            or args.material_file == "-"
            or re.fullmatch(r"[0-9a-f]{64}", args.reviewed_plan_sha256 or "") is None
        ):
            raise ValueError
        if args.material_file == "-":
            raw = sys.stdin.buffer.read(MAX_MATERIAL_BYTES + 1)
        else:
            with Path(args.material_file).open("rb") as stream:
                raw = stream.read(MAX_MATERIAL_BYTES + 1)
        if args.mode == "plan":
            result = plan_publication(raw)
        else:
            # Readiness and fingerprint are checked before asking for authority.
            ready = plan_publication(raw)
            if ready["plan_sha256"] != args.reviewed_plan_sha256:
                raise ValueError
            print(
                "Type AUTHORIZE Q133-2 followed by the reviewed plan SHA-256:",
                file=sys.stderr,
            )
            authorization = sys.stdin.readline(128).rstrip("\r\n")
            result = execute_publication(raw, args.reviewed_plan_sha256, authorization)
        print(canonical(result).decode("utf-8"))
        return 0
    except BaseException:
        print(
            '{"reason":"PUBLICATION_FAILED_CLOSED","schema":"arch133-host-publication/v1"}',
            file=sys.stderr,
        )
        return 3
