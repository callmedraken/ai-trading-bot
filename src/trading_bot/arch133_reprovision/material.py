"""Exact externally reviewed activation and binding bytes; no authority invention."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from trading_bot.arch133_reprovision import predecessor
from trading_bot.arch133_scheduler_installation.specification import (
    build_unattended_scheduler_spec,
)
from trading_bot.arch133_verifier import binding
from trading_bot.arch133_verifier.activation import (
    ReviewPaperActivation,
    ReviewPaperWake,
)

MATERIAL_SCHEMA = "arch133q-fresh-activation-material/v1"
MAX_BYTES = 262144


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Material:
    raw: bytes
    activation: ReviewPaperActivation
    host: binding.HostBinding

    @property
    def sha256(self) -> str:
        return digest(self.raw)

    @classmethod
    def parse(cls, raw: bytes) -> Material:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
            raise ValueError("material rejected")
        data = json.loads(raw)
        if type(data) is not dict or set(data) != {
            "schema",
            "activation",
            "host_binding",
        }:
            raise ValueError("material rejected")
        if data["schema"] != MATERIAL_SCHEMA or raw != canonical(data).encode():
            raise ValueError("material rejected")
        act = ReviewPaperActivation.from_json(data["activation"])
        host = binding.HostBinding.from_json(data["host_binding"])
        return cls(raw, act, host)


def read_material(path: Path) -> Material:
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("material path rejected")
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or getattr(before, "st_file_attributes", 0) & 0x400
    ):
        raise ValueError("material path rejected")
    with path.open("rb") as stream:
        held = os.fstat(stream.fileno())
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())

    # Windows path/handle creation-time observations can differ. Bind object
    # identity, size, write time and the exact bytes; never access/creation time.
    def facts(value: os.stat_result) -> tuple[int, ...]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
        )

    if not facts(before) == facts(held) == facts(after) == facts(path.lstat()):
        raise ValueError("material changed")
    return Material.parse(raw)


def require_fresh(
    material: Material, old: ReviewPaperActivation, runtime: dict, now: datetime
) -> dict:
    act, host = material.activation, material.host
    expected = binding.HostRuntimeIdentity(
        predecessor.PUBLISHED_RUNTIME_HEAD,
        predecessor.PUBLISHED_RUNTIME_TREE,
        binding.PRODUCTION_PYTHON_SHA256,
        binding.PRODUCTION_PYTHON_VERSION,
        runtime["wake_launcher_sha256"],
    )
    spec = build_unattended_scheduler_spec(act)
    if (
        now.tzinfo is None
        or now.utcoffset() is None
        or not now < spec.start_boundary < spec.end_boundary
    ):
        raise ValueError("fresh window rejected")
    if (
        host.runtime != expected
        or (act.source_head, act.source_tree, act.deployment_identity)
        != (expected.source_head, expected.source_tree, expected.deployment_identity)
        or host.activation_sha256 != digest(act.to_json().encode())
        or act.store_path != str(binding.PAPER_PATH)
        or act.store_identity != host.store_identity
        or host.paper_predecessor_sha256
        != predecessor.expected_empty_paper_sha256(act.starting_cash)
        or host.oauth_valid_until <= spec.end_boundary
        or not old.created_at < act.created_at <= now
        or act.proposal.created_at != act.created_at
        or act.target_session_date <= old.target_session_date
        or act.local_order_id == old.local_order_id
        or act.proposal.proposal_id == old.proposal.proposal_id
        or act.store_identity == old.store_identity
        or act.activation_id == old.activation_id
        or ReviewPaperWake(activation=act, updated_at=act.created_at).wake_id
        == ReviewPaperWake(activation=old, updated_at=old.created_at).wake_id
        or act.opening_buffer != timedelta(minutes=5)
        or act.closing_buffer != timedelta(minutes=5)
    ):
        raise ValueError("fresh material rejected")
    return {
        "start_boundary": spec.start_boundary.isoformat(),
        "end_boundary": spec.end_boundary.isoformat(),
        "activation_id": str(act.activation_id),
        "wake_id": str(
            ReviewPaperWake(activation=act, updated_at=act.created_at).wake_id
        ),
    }


def require_stale(activation: ReviewPaperActivation, now: datetime) -> None:
    spec = build_unattended_scheduler_spec(activation)
    if now.tzinfo is None or now.utcoffset() is None or now < spec.end_boundary:
        raise ValueError("predecessor is not expired")
