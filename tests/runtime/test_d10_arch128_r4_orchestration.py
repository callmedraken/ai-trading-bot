from __future__ import annotations

import hashlib
from dataclasses import fields
from pathlib import Path

import pytest

from scripts import d10_arch128_r4_orchestration as r4c
from scripts import d10_arch128_r4_replacement as r4
from scripts.d10_protected_deployment import (
    Ace,
    CertifiedMaterial,
    NativeObject,
    SourceFile,
)
from scripts.build_d10_deployment_identity import D10BuildResult
from trading_bot.runtime.personal_desktop_d10_deployment_identity import (
    ExecutableManifest,
    ExecutableManifestEntry,
    build_deployment_attestation,
)


def _native(path: str, index: int) -> NativeObject:
    return NativeObject(
        path=path,
        final_path=path,
        directory=True,
        owner_sid="S-1-5-32-544",
        dacl_protected=True,
        aces=(Ace("S-1-5-32-544", 1),),
        reparse=False,
        drive_type=3,
        volume_root="F:\\",
        filesystem="NTFS",
        volume_serial=9,
        file_index=index,
        links=1,
        size=0,
    )


def _admission() -> r4c.AdmissionObservation:
    return r4c.AdmissionObservation(
        r4.NamespaceObservation(
            r4.RootObservation(r4.CANONICAL_PATH, True, r4.OLD_IDENTITY),
            r4.RootObservation(r4.STAGING_PATH, True, r4.NEW_IDENTITY),
            r4.RootObservation(r4.RETIRED_PATH, False),
            True,
            True,
        ),
        r4.AdmissionFacts(
            *([True] * len(fields(r4.AdmissionFacts)))
        ),
        _native(r4.PARENT_PATH, 1),
        _native(r4.CANONICAL_PATH, 2),
        _native(r4.STAGING_PATH, 3),
        (("enabled", False),),
    )


def _post(state: r4.NamespaceState) -> r4c.PostRenameObservation:
    if state is r4.NamespaceState.RETIRED_WINDOW:
        namespace = r4.NamespaceObservation(
            r4.RootObservation(r4.CANONICAL_PATH, False),
            r4.RootObservation(r4.STAGING_PATH, True, r4.NEW_IDENTITY),
            r4.RootObservation(r4.RETIRED_PATH, True, r4.OLD_IDENTITY),
            True,
            True,
        )
        old = _native(r4.RETIRED_PATH, 2)
        new = _native(r4.STAGING_PATH, 3)
    else:
        namespace = r4.NamespaceObservation(
            r4.RootObservation(r4.CANONICAL_PATH, True, r4.NEW_IDENTITY),
            r4.RootObservation(r4.STAGING_PATH, False),
            r4.RootObservation(r4.RETIRED_PATH, True, r4.OLD_IDENTITY),
            True,
            True,
        )
        old = _native(r4.RETIRED_PATH, 2)
        new = _native(r4.CANONICAL_PATH, 3)
    return r4c.PostRenameObservation(
        namespace,
        r4.PostRenameFacts(
            *([True] * len(fields(r4.PostRenameFacts)))
        ),
        _native(r4.PARENT_PATH, 1),
        old,
        new,
        (("enabled", False),),
    )


def test_fixed_external_material_paths_are_not_feature_worktree() -> None:
    assert r4c.R1_MANIFEST_PATH.parent == Path(r4.R1_MATERIAL_ROOT)
    assert r4c.R1_ATTESTATION_PATH.parent == Path(r4.R1_MATERIAL_ROOT)
    assert r4c.R2_SIGNATURE_PATH.parent == Path(r4.R2_SIGNING_ROOT)
    assert "d10-arch128-r1-0f9551e-byteexact-r2" in r4.R1_BYTE_EXACT_WORKTREE


def test_material_builder_is_explicitly_bound_to_e6_identity() -> None:
    source = Path(r4c.__file__).read_text(encoding="utf-8")
    assert "expected_head=r4.NEW_IDENTITY.certified_source_head" in source
    assert "expected_tree=r4.NEW_IDENTITY.certified_source_tree" in source
    assert "build_certified_material" not in source


class _Writer:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def require_administrator(self) -> None:
        self.calls.append(("admin",))

    def bind_source_inventory(self, paths: tuple[str, ...]) -> None:
        self.calls.append(("bind", paths))

    def create_directory(self, path: str) -> None:
        self.calls.append(("mkdir", path))

    def create_file(self, path: str, data: bytes) -> None:
        self.calls.append(("file", path, data))

    def publish_create_only(self, installing: str, final: str) -> None:
        self.calls.append(("publish", installing, final))


def _signed_material() -> r4c.SignedMaterial:
    entry = ExecutableManifestEntry(
        "scripts/run_personal_desktop_unattended_one_week_soak.py",
        1,
        "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881",
    )
    manifest = ExecutableManifest(
        "personal-desktop-d10-executable-manifest/v1",
        (entry,),
    )
    guard = b"guard"
    attestation = build_deployment_attestation(
        certified_source_head=r4.NEW_IDENTITY.certified_source_head,
        certified_source_tree=r4.NEW_IDENTITY.certified_source_tree,
        production_python_version="3.14.3",
        launch_guard_byte_length=len(guard),
        launch_guard_sha256=hashlib.sha256(guard).hexdigest(),
        executable_manifest_sha256=manifest.digest,
        executable_file_count=len(manifest.entries),
    )
    build = D10BuildResult(
        manifest.canonical_bytes(),
        manifest.digest,
        attestation.canonical_bytes(),
        attestation.deployment_id,
        307,
        r4.NEW_IDENTITY.certified_source_head,
        r4.NEW_IDENTITY.certified_source_tree,
    )
    material = CertifiedMaterial(
        build,
        manifest,
        attestation,
        (SourceFile(entry.relative_path, b"x", entry.sha256),),
        guard,
    )
    return r4c.SignedMaterial(material, b"s" * 64)


def test_write_staging_payload_has_fixed_inert_sequence() -> None:
    signed = _signed_material()
    writer = _Writer()
    r4c.write_staging_payload(signed, writer)

    assert writer.calls[0] == ("admin",)
    assert writer.calls[1][0] == "bind"
    assert ("mkdir", r4.STAGING_PATH) in writer.calls
    assert ("mkdir", r4.NEW_EVIDENCE_ROOT) in writer.calls
    assert not any(
        call[0] == "file" and "activation.lease" in str(call[1])
        for call in writer.calls
    )
    assert not any(
        call[0] == "file" and str(call[1]).endswith(".jsonl")
        for call in writer.calls
    )


def test_construct_staging_requires_pre_and_post_scheduler_stability() -> None:
    signed = _signed_material()
    writer = _Writer()
    admission = _admission()
    pre = r4c.PreStageObservation(
        admission.parent_native,
        admission.old_native,
        admission.scheduler,
    )

    result = r4c.construct_staging(
        signed,
        writer,
        object(),
        object(),
        lambda: {},
        pre_observer=lambda *args: pre,
        ready_observer=lambda *args: admission,
    )
    assert result is admission

    drifted = r4c.AdmissionObservation(
        admission.namespace,
        admission.facts,
        admission.parent_native,
        admission.old_native,
        admission.new_native,
        (("enabled", True),),
    )
    with pytest.raises(Exception):
        r4c.construct_staging(
            signed,
            _Writer(),
            object(),
            object(),
            lambda: {},
            pre_observer=lambda *args: pre,
            ready_observer=lambda *args: drifted,
        )


def test_session_requires_readback_between_both_renames() -> None:
    admission = _admission()
    retired = _post(r4.NamespaceState.RETIRED_WINDOW)
    complete = _post(r4.NamespaceState.COMPLETE)
    calls: list[r4.RenameStep] = []

    def rename(*args):
        step = args[1]
        calls.append(step)
        return r4.MutationOutcome.SUCCESS

    def ready(*args):
        return admission

    def post(*args):
        state = args[3]
        return retired if state is r4.NamespaceState.RETIRED_WINDOW else complete

    session = r4c.ReplacementSession(
        object(),
        object(),
        lambda: {},
        admission,
        rename,
        ready_observer=ready,
        post_observer=post,
    )
    assert session.retire_old().phase is r4.Phase.READY_TO_PUBLISH_NEW
    assert calls == [r4.RenameStep.OLD_TO_RETIRED]
    assert session.publish_new().phase is r4.Phase.COMPLETE
    assert calls == [
        r4.RenameStep.OLD_TO_RETIRED,
        r4.RenameStep.STAGING_TO_CANONICAL,
    ]


def test_session_post_rename_readback_failure_latches_stop() -> None:
    admission = _admission()

    session = r4c.ReplacementSession(
        object(),
        object(),
        lambda: {},
        admission,
        lambda *args: r4.MutationOutcome.SUCCESS,
        ready_observer=lambda *args: admission,
        post_observer=lambda *args: (_ for _ in ()).throw(RuntimeError("drift")),
    )
    result = session.retire_old()
    assert result.phase is r4.Phase.STOPPED_INDETERMINATE
    assert session.stopped is True
    with pytest.raises(Exception):
        session.publish_new()


def test_session_native_indeterminate_never_calls_post_readback() -> None:
    admission = _admission()
    post_calls = 0

    def post(*args):
        nonlocal post_calls
        post_calls += 1
        return _post(r4.NamespaceState.RETIRED_WINDOW)

    session = r4c.ReplacementSession(
        object(),
        object(),
        lambda: {},
        admission,
        lambda *args: r4.MutationOutcome.INDETERMINATE,
        ready_observer=lambda *args: admission,
        post_observer=post,
    )
    result = session.retire_old()
    assert result.phase is r4.Phase.STOPPED_INDETERMINATE
    assert post_calls == 0


def test_r4c_import_has_no_cli_or_backend_construction() -> None:
    source = Path(r4c.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "def main(",
        "if __name__ ==",
        "WindowsArch128StagingBackend(",
        "WindowsArch128ReadOnlyReader(",
        "Schedule.Service",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "getpass",
    ):
        assert forbidden not in source
