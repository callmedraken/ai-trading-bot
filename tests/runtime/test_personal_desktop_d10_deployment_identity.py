"""Focused Architecture-123 A1/A2 canonical and clean-checkout tests."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.build_d10_deployment_identity import build_d10_deployment_identity

from scripts import build_d10_deployment_identity as builder
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    D10_LAUNCHER_RELATIVE_PATH,
    DEPLOYMENT_ID_NAMESPACE_V1,
    EXECUTABLE_MANIFEST_SCHEMA,
    DeploymentIdentityError,
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
    canonical_json_bytes,
    parse_deployment_attestation,
    parse_executable_manifest,
)

DIGEST = hashlib.sha256(b"x").hexdigest()
HEAD = "a" * 40
TREE = "b" * 40


def entry(path: str, data: bytes = b"x") -> ExecutableManifestEntry:
    return ExecutableManifestEntry(path, len(data), hashlib.sha256(data).hexdigest())


def manifest(*entries: ExecutableManifestEntry) -> ExecutableManifest:
    return ExecutableManifest(EXECUTABLE_MANIFEST_SCHEMA, tuple(entries))


def attestation(**changes: object):
    fields = {
        "certified_source_head": HEAD,
        "certified_source_tree": TREE,
        "production_python_version": "3.12.10",
        "executable_manifest_sha256": DIGEST,
        "executable_file_count": 2,
    }
    fields.update(changes)
    return build_deployment_attestation(**fields)


def test_canonical_round_trip_and_uuid_material() -> None:
    model = manifest(entry(D10_LAUNCHER_RELATIVE_PATH), entry("src/trading_bot/a.py"))
    assert parse_executable_manifest(model.canonical_bytes()) == model
    assert (
        parse_deployment_attestation(attestation().canonical_bytes()) == attestation()
    )
    item = attestation()
    assert item.deployment_id == str(
        uuid.uuid5(
            DEPLOYMENT_ID_NAMESPACE_V1,
            canonical_json_bytes(item.authority_dict()).decode("utf-8"),
        )
    )
    with pytest.raises(DeploymentIdentityError):
        replace(item, certified_source_head="c" * 40)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: b" " + d,
        lambda d: d + b"\n",
        lambda d: d.replace(b":", b": "),
        lambda d: d.replace(b'"schema":', b'"schema":"ignored","schema":', 1),
    ],
)
def test_noncanonical_manifest_rejected(mutate) -> None:
    data = manifest(entry(D10_LAUNCHER_RELATIVE_PATH)).canonical_bytes()
    with pytest.raises(DeploymentIdentityError):
        parse_executable_manifest(mutate(data))


def test_exact_fields_and_attestation_canonical_bytes() -> None:
    data = json.loads(manifest(entry(D10_LAUNCHER_RELATIVE_PATH)).canonical_bytes())
    data["other"] = 1
    with pytest.raises(DeploymentIdentityError):
        parse_executable_manifest(canonical_json_bytes(data))
    data = json.loads(attestation().canonical_bytes())
    del data["approved_trading_sid"]
    with pytest.raises(DeploymentIdentityError):
        parse_deployment_attestation(canonical_json_bytes(data))
    with pytest.raises(DeploymentIdentityError):
        parse_deployment_attestation(attestation().canonical_bytes() + b" ")


@pytest.mark.parametrize(
    "path",
    [
        "/src/trading_bot/a.py",
        "src/trading_bot/../a.py",
        "src/trading_bot/./a.py",
        "src/trading_bot//a.py",
        r"src\trading_bot\a.py",
        "C:/src/trading_bot/a.py",
        "src/trading_bot/a.py:stream",
        "//server/share/a.py",
        "src/trading_bot/CON.py",
        "src/trading_bot/a?.py",
    ],
)
def test_unsafe_paths_rejected(path: str) -> None:
    with pytest.raises(DeploymentIdentityError):
        entry(path)


def test_duplicates_casefold_order_and_bool_rejected() -> None:
    launcher = entry(D10_LAUNCHER_RELATIVE_PATH)
    source = entry("src/trading_bot/a.py")
    with pytest.raises(DeploymentIdentityError):
        manifest(launcher, source, source)
    with pytest.raises(DeploymentIdentityError):
        manifest(launcher, entry("src/trading_bot/A.py"), source)
    with pytest.raises(DeploymentIdentityError):
        manifest(source, launcher)
    with pytest.raises(DeploymentIdentityError):
        ExecutableManifestEntry(D10_LAUNCHER_RELATIVE_PATH, True, DIGEST)
    with pytest.raises(DeploymentIdentityError):
        attestation(executable_file_count=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("certified_source_head", "A" * 40),
        ("certified_source_tree", "b" * 39),
        ("source_root", "C:\\wrong"),
        ("launcher", "wrong"),
        ("signing_key_id", "wrong"),
        ("scheduler_contract_schema", "wrong"),
        ("approved_trading_sid", "S-1-5-18"),
        ("production_python", "C:\\python.exe"),
        ("production_python_version", "3.11.0"),
        ("executable_manifest_sha256", "A" * 64),
    ],
)
def test_attestation_rejects_wrong_authority_fact(field: str, value: str) -> None:
    with pytest.raises(DeploymentIdentityError):
        replace(attestation(), **{field: value})


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _checkout(root: Path) -> tuple[str, str]:
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    for path, data in (
        ("src/trading_bot/z.py", b"z"),
        ("src/trading_bot/a.py", b"a"),
        ("src/trading_bot/runtime/schema/r.json", b"{}"),
        (D10_LAUNCHER_RELATIVE_PATH, b"launcher"),
    ):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    _git(root, "add", "src", "scripts")
    _git(root, "commit", "-qm", "fixture")
    return _git(root, "rev-parse", "HEAD"), _git(
        root, "show", "-s", "--format=%T", "HEAD"
    )


def _build(root: Path, head: str, tree: str):
    return build_d10_deployment_identity(
        repository_root=root,
        expected_head=head,
        expected_tree=tree,
        production_python_version="3.12.10",
    )


def test_builder_stable_order_digest_and_byte_tamper(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    first_blob = builder._tracked_governed_paths(root)["src/trading_bot/a.py"].oid
    first = _build(root, head, tree)
    parsed = parse_executable_manifest(first.executable_manifest_bytes)
    assert [e.relative_path for e in parsed.entries] == sorted(
        e.relative_path for e in parsed.entries
    )
    assert first.executable_file_count == 4
    assert first.executable_manifest_sha256 == parsed.digest
    assert (
        parse_deployment_attestation(
            first.unsigned_deployment_attestation_bytes
        ).deployment_id
        == first.deployment_id
    )
    assert _build(root, head, tree) == first
    (root / "src/trading_bot/a.py").write_bytes(b"tamper")
    with pytest.raises(DeploymentIdentityError, match="dirty"):
        _build(root, head, tree)
    _git(root, "add", "src/trading_bot/a.py")
    _git(root, "commit", "-qm", "changed bytes")
    second = _build(
        root,
        _git(root, "rev-parse", "HEAD"),
        _git(root, "show", "-s", "--format=%T", "HEAD"),
    )
    second_blob = builder._tracked_governed_paths(root)["src/trading_bot/a.py"].oid
    assert first_blob != second_blob
    assert first.executable_manifest_sha256 != second.executable_manifest_sha256


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "untracked-py",
        "untracked-pyi",
        "untracked-resource",
        "dirty-index",
        "dirty-worktree",
        "wrong-head",
        "wrong-tree",
        "missing-launcher",
    ],
)
def test_builder_fails_closed_on_checkout_drift(tmp_path: Path, change: str) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    if change == "missing":
        (root / "src/trading_bot/a.py").unlink()
    elif change.startswith("untracked"):
        suffix = {
            "untracked-py": ".py",
            "untracked-pyi": ".pyi",
            "untracked-resource": ".json",
        }[change]
        (root / "src/trading_bot" / ("extra" + suffix)).write_bytes(b"x")
    elif change == "dirty-index":
        (root / "src/trading_bot/a.py").write_bytes(b"changed")
        _git(root, "add", "src/trading_bot/a.py")
    elif change == "dirty-worktree":
        (root / "src/trading_bot/a.py").write_bytes(b"changed")
    elif change == "missing-launcher":
        (root / D10_LAUNCHER_RELATIVE_PATH).unlink()
    elif change == "wrong-head":
        head = "f" * 40
    else:
        tree = "f" * 40
    with pytest.raises(DeploymentIdentityError):
        _build(root, head, tree)


def test_build_only_modules_have_no_effect_boundaries() -> None:
    root = Path(__file__).resolve().parents[2]
    model = (
        root / "src/trading_bot/runtime/personal_desktop_d10_deployment_identity.py"
    ).read_text()
    builder = (root / "scripts/build_d10_deployment_identity.py").read_text()
    assert "subprocess" not in model
    assert "sign(" not in model + builder
    assert "private_key" not in model + builder
    for forbidden in (
        "TaskScheduler",
        "provider_call",
        "publish_decision",
        "settle_order",
        "recover_receipt",
        "broker_order",
        "live_order",
    ):
        assert forbidden not in model + builder


def test_discovery_order_does_not_change_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    first = _build(root, head, tree)
    original_walk = builder.os.walk

    def reversed_walk(top, *, followlinks=False):
        for directory, dirs, files in original_walk(top, followlinks=followlinks):
            dirs.reverse()
            files.reverse()
            yield directory, dirs, files

    monkeypatch.setattr(builder.os, "walk", reversed_walk)
    assert _build(root, head, tree) == first


def test_ignored_untracked_resource_still_blocks(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    (root / ".git/info/exclude").write_text("*.json\n")
    (root / "src/trading_bot/runtime/schema/extra.json").write_bytes(b"{}")
    assert _git(root, "status", "--porcelain=v1") == ""
    with pytest.raises(DeploymentIdentityError, match="inventories differ"):
        _build(root, head, tree)


def test_entry_field_set_and_unicode_rejected() -> None:
    data = json.loads(manifest(entry(D10_LAUNCHER_RELATIVE_PATH)).canonical_bytes())
    data["entries"][0]["extra"] = 1
    with pytest.raises(DeploymentIdentityError):
        parse_executable_manifest(canonical_json_bytes(data))
    data["entries"][0].pop("extra")
    data["entries"][0]["relative_path"] = "src/trading_bot/\ud800.py"
    with pytest.raises(DeploymentIdentityError):
        canonical_json_bytes(data)


def test_governed_inventory_is_from_head_not_staged_index(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    certified = builder._tracked_governed_paths(root)
    assert certified["src/trading_bot/a.py"].oid == _git(
        root, "rev-parse", "HEAD:src/trading_bot/a.py"
    )
    staged = root / "src/trading_bot/added.py"
    staged.write_bytes(b"staged only")
    _git(root, "add", "src/trading_bot/added.py")
    assert builder._tracked_governed_paths(root) == certified
    assert "src/trading_bot/added.py" not in certified
    with pytest.raises(DeploymentIdentityError, match="dirty"):
        _build(root, head, tree)


def test_local_blob_tamper_blocks_when_status_seam_reports_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    (root / "src/trading_bot/a.py").write_bytes(b"b")
    real_git = builder._git

    def status_clean(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
        if args[0] == "status":
            return b""
        return real_git(repo, *args, input_bytes=input_bytes)

    monkeypatch.setattr(builder, "_git", status_clean)
    with pytest.raises(DeploymentIdentityError, match="HEAD blob"):
        _build(root, head, tree)


@pytest.mark.parametrize(
    "overrides",
    [
        {"GIT_DIR": "invalid-git-dir"},
        {"GIT_WORK_TREE": "invalid-work-tree"},
        {"GIT_INDEX_FILE": "invalid-index"},
        {"GIT_OBJECT_DIRECTORY": "invalid-objects"},
        {"GIT_ALTERNATE_OBJECT_DIRECTORIES": "invalid-alternates"},
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.bare",
            "GIT_CONFIG_VALUE_0": "true",
        },
    ],
)
def test_inherited_git_overrides_cannot_redirect_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overrides: dict[str, str]
) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    expected = _build(root, head, tree)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    observed = _build(root, head, tree)
    assert observed == expected


def test_builder_hashes_stdin_without_writing_git_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    objects = root / ".git" / "objects"
    before = {
        path.relative_to(objects) for path in objects.rglob("*") if path.is_file()
    }
    real_git = builder._git
    calls: list[tuple[str, ...]] = []

    def record(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
        calls.append(args)
        return real_git(repo, *args, input_bytes=input_bytes)

    monkeypatch.setattr(builder, "_git", record)
    result = _build(root, head, tree)
    after = {path.relative_to(objects) for path in objects.rglob("*") if path.is_file()}
    assert before == after
    assert calls.count(("hash-object", "--stdin")) == result.executable_file_count
    assert ("ls-tree", "-r", "-z", "--full-tree", "HEAD") in calls
    assert all("-w" not in args for args in calls)


def test_case_collision_and_symlink_like_governed_state_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    real_git = builder._git
    oid = builder._tracked_governed_paths(root)["src/trading_bot/a.py"].oid

    def colliding_tree(
        repo: Path, *args: str, input_bytes: bytes | None = None
    ) -> bytes:
        data = real_git(repo, *args, input_bytes=input_bytes)
        if args[0] == "ls-tree":
            return data + f"100644 blob {oid}\tsrc/trading_bot/A.py\0".encode()
        return data

    monkeypatch.setattr(builder, "_git", colliding_tree)
    with pytest.raises(DeploymentIdentityError, match="casefold"):
        _build(root, head, tree)
    monkeypatch.setattr(builder, "_git", real_git)

    def symlink_tree(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
        data = real_git(repo, *args, input_bytes=input_bytes)
        if args[0] == "ls-tree":
            old = f"100644 blob {oid}\tsrc/trading_bot/a.py".encode()
            return data.replace(old, old.replace(b"100644", b"120000"), 1)
        return data

    monkeypatch.setattr(builder, "_git", symlink_tree)
    with pytest.raises(DeploymentIdentityError, match="regular"):
        _build(root, head, tree)
    monkeypatch.setattr(builder, "_git", real_git)

    local_file = root / "src/trading_bot/a.py"
    real_lstat = Path.lstat

    def symlink_like(path: Path):
        if path == local_file:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
        return real_lstat(path)

    monkeypatch.setattr(Path, "lstat", symlink_like)
    with pytest.raises(DeploymentIdentityError, match="no-reparse"):
        _build(root, head, tree)


def test_head_case_variant_of_governed_root_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    head, tree = _checkout(root)
    real_git = builder._git

    def wrong_case_tree(
        repo: Path, *args: str, input_bytes: bytes | None = None
    ) -> bytes:
        data = real_git(repo, *args, input_bytes=input_bytes)
        if args[0] == "ls-tree":
            return data.replace(b"src/trading_bot/a.py", b"src/Trading_Bot/a.py", 1)
        return data

    monkeypatch.setattr(builder, "_git", wrong_case_tree)
    with pytest.raises(DeploymentIdentityError, match="governed"):
        _build(root, head, tree)
