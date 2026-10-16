"""Independent held-handle readback of the fixed staging/active/archive generations."""

from __future__ import annotations

import sqlite3
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

from trading_bot.arch133_acl import read_only
from trading_bot.arch133_reprovision import predecessor, reads
from trading_bot.arch133_reprovision.material import Material
from trading_bot.arch133_verifier import binding, file_policy

ACTIVE = reads.ROOTS[0]
STAGE = reads.ROOTS[1]
ARCHIVE = reads.ROOTS[2]
STAGING_PARENT = r"F:\AITradingBot\Arch133Q-stage"


def require_archive_file(name: str, policy: file_policy.FilePolicy) -> None:
    if (
        policy.owner_sid != read_only.ADMINISTRATORS_SID
        or policy.protected is not True
        or policy.aces
        != read_only.ADMIN_ACES + ((read_only.TRADING_SID, 0x120089, 0, 0),)
    ):
        raise ValueError("archive policy rejected")


def observe_generation(root: str, material: Material, *, archive: bool = False) -> dict:
    if root not in reads.ROOTS or archive != (root == ARCHIVE):
        raise ValueError("generation path rejected")
    with ExitStack() as held:
        directory = reads.open_generation_directory(root)
        held.callback(read_only.close_handle, directory)
        observed, security = read_only.inspect_directory_security(directory, root)
        intended = "ADMIN_SYSTEM_ONLY" if archive else "EXACT_INTENDED_ROOT"
        if (
            observed.classification() != intended
            or observed.filesystem != "NTFS"
            or observed.reparse
            or observed.identity[0] != predecessor.ROOT_IDENTITY[0]
        ):
            raise ValueError("generation root rejected")
        namespace = reads.namespace(directory)
        facts = {}
        for name, identity in namespace:
            handle = reads.open_generation_file(root, name)
            held.callback(read_only.close_handle, handle)
            snapshot = reads.file_snapshot(handle, root, name)
            policy = file_policy.observe_file_policy(handle)
            (require_archive_file if archive else file_policy.require_file_policy)(
                name, policy
            )
            if snapshot[0] != (observed.identity[0], identity):
                raise ValueError("generation identity rejected")
            facts[name] = {
                "identity": list(snapshot[0]),
                "sha256": snapshot[1],
                "policy": asdict(policy),
            }
        path = Path(root)
        raw = (
            (path / "activation.json").read_bytes(),
            (path / "host-binding.json").read_bytes(),
        )
        if raw != (
            material.activation.to_json().encode(),
            material.host.to_json().encode(),
        ):
            raise ValueError("generation publication rejected")
        connections = []
        for name in ("wake.sqlite", "paper.sqlite"):
            connection = sqlite3.connect(
                (path / name).as_uri() + "?mode=ro", uri=True, timeout=0
            )
            held.callback(connection.close)
            connection.execute("BEGIN")
            connections.append(connection)
        state = predecessor.require_ready_state(connections[0], material.activation)
        paper = predecessor.require_empty_paper(
            connections[1], material.activation, material.host
        )
        tables = (
            connections[1]
            .execute("SELECT type, name FROM sqlite_master ORDER BY type, name")
            .fetchall()
        )
        if tables != sorted(
            [
                ("table", "metadata"),
                ("table", "review_fills"),
                ("index", "sqlite_autoindex_metadata_1"),
                ("index", "sqlite_autoindex_review_fills_1"),
                ("index", "sqlite_autoindex_review_fills_2"),
                ("index", "sqlite_autoindex_review_fills_3"),
            ]
        ):
            raise ValueError("paper schema rejected")
        if reads.namespace(
            directory
        ) != namespace or read_only.inspect_directory_security(directory, root) != (
            observed,
            security,
        ):
            raise ValueError("generation changed")
        # All file handles remain held until both database transactions and this
        # second byte/policy observation have completed.
        for name, _ in namespace:
            handle = reads.open_generation_file(root, name)
            held.callback(read_only.close_handle, handle)
            if (
                reads.file_snapshot(handle, root, name)
                != (tuple(facts[name]["identity"]), facts[name]["sha256"])
                or asdict(file_policy.observe_file_policy(handle))
                != facts[name]["policy"]
            ):
                raise ValueError("generation changed")
    return {
        "root_identity": list(observed.identity),
        "root_security_sha256": security,
        "files": facts,
        "state_sha256": state.fingerprint,
        "paper_predecessor_sha256": paper,
        "wake_revision": 0,
        "activation_id": str(material.activation.activation_id),
        "wake_id": str(state.current(material.activation).wake.wake_id),
    }


def predecessor_material() -> Material:
    raw = {
        "schema": "arch133q-fresh-activation-material/v1",
        "activation": binding.ACTIVATION_PATH.read_text(encoding="utf-8"),
        "host_binding": binding.BINDING_PATH.read_text(encoding="utf-8"),
    }
    from trading_bot.arch133_reprovision.material import canonical

    return Material.parse(canonical(raw).encode())
