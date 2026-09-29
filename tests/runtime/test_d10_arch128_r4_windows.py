from __future__ import annotations

import ctypes
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import d10_arch128_r4_replacement as r4
from scripts import d10_arch128_r4_windows as r4w
from scripts import d10_protected_replacement_windows as legacy_windows


def _backend() -> r4w.WindowsArch128StagingBackend:
    backend = object.__new__(r4w.WindowsArch128StagingBackend)
    backend._source_files = frozenset()
    backend._source_directories = frozenset()
    backend.bind_source_inventory(
        (
            "scripts/run_personal_desktop_unattended_one_week_soak.py",
            "src/trading_bot/__init__.py",
        )
    )
    return backend


def test_staging_backend_is_exact_new_root() -> None:
    assert r4w.WindowsArch128StagingBackend._creation_root == r4.STAGING_PATH


def test_staging_create_allowlist_includes_only_inert_evidence_root_and_payload() -> None:
    backend = _backend()

    assert backend._allowed_directory_create(r4.STAGING_PATH)
    assert backend._allowed_directory_create(r4.NEW_EVIDENCE_ROOT)
    assert not backend._allowed_directory_create(
        r4.NEW_EVIDENCE_ROOT + r"\unexpected"
    )

    assert backend._allowed_file_create(
        r4.STAGING_PATH + r"\deployment.attestation.json.installing"
    )
    assert backend._allowed_file_create(
        r4.STAGING_PATH + r"\deployment.attestation.sig.installing"
    )
    assert backend._allowed_file_create(
        r4.STAGING_PATH + r"\executable-manifest.json.installing"
    )
    assert not backend._allowed_file_create(
        r4.STAGING_PATH + r"\activation.lease.json"
    )
    assert not backend._allowed_file_create(
        r4.NEW_EVIDENCE_ROOT + r"\wake-test.jsonl"
    )


@pytest.mark.parametrize(
    ("installing", "final"),
    [
        (
            r4.STAGING_PATH + r"\launch-guard.py.installing",
            r4.STAGING_PATH + r"\launch-guard.py",
        ),
        (
            r4.STAGING_PATH + r"\source.installing",
            r4.STAGING_PATH + r"\source",
        ),
        (
            r4.STAGING_PATH + r"\deployment.attestation.json.installing",
            r4.STAGING_PATH + r"\deployment.attestation.json",
        ),
        (
            r4.STAGING_PATH + r"\deployment.attestation.sig.installing",
            r4.STAGING_PATH + r"\deployment.attestation.sig",
        ),
        (
            r4.STAGING_PATH + r"\executable-manifest.json.installing",
            r4.STAGING_PATH + r"\executable-manifest.json",
        ),
    ],
)
def test_staging_publication_pairs_are_fixed(
    installing: str,
    final: str,
) -> None:
    assert r4w.WindowsArch128StagingBackend._allowed_publication_pair(
        installing,
        final,
    )


def test_staging_publication_rejects_lease_and_cross_root_paths() -> None:
    assert not r4w.WindowsArch128StagingBackend._allowed_publication_pair(
        r4.STAGING_PATH + r"\activation.lease.json.installing",
        r4.STAGING_PATH + r"\activation.lease.json",
    )
    assert not r4w.WindowsArch128StagingBackend._allowed_publication_pair(
        r4.STAGING_PATH + r"\launch-guard.py.installing",
        r4.CANONICAL_PATH + r"\launch-guard.py",
    )


def test_staging_readback_allowlist_is_inventory_bound() -> None:
    backend = _backend()
    assert backend._allowed_object_path(r4.PARENT_PATH, directory=True)
    assert backend._allowed_object_path(r4.STAGING_PATH, directory=True)
    assert backend._allowed_object_path(r4.NEW_EVIDENCE_ROOT, directory=True)
    assert backend._allowed_object_path(
        r4.STAGING_PATH + r"\source",
        directory=True,
    )
    assert backend._allowed_object_path(
        r4.STAGING_PATH + r"\source\src\trading_bot\__init__.py",
        directory=False,
    )
    assert backend._allowed_object_path(
        r4.STAGING_PATH + r"\deployment.attestation.sig",
        directory=False,
    )
    assert not backend._allowed_object_path(
        r4.STAGING_PATH + r"\activation.lease.json",
        directory=False,
    )


@pytest.mark.parametrize(
    ("path", "directory", "expected"),
    [
        (r4.PARENT_PATH, True, True),
        (r4.CANONICAL_PATH, True, True),
        (r4.CANONICAL_PATH, None, True),
        (r4.STAGING_PATH, True, True),
        (r4.RETIRED_PATH, True, True),
        (r4.HISTORICAL_S5R8_RETIRED_PATH, None, True),
        (r4.STAGING_PATH + r"\source", True, True),
        (r4.STAGING_PATH + r"\evidence", True, True),
        (r4.STAGING_PATH + r"\evidence\wake-x.jsonl", False, False),
        (r4.STAGING_PATH + r"\activation.lease.json", False, True),
        (
            r4.STAGING_PATH + r"\deployment.attestation.json.installing",
            False,
            True,
        ),
        (r4.STAGING_PATH + r"\unexpected", None, False),
    ],
)
def test_read_only_reader_allowlist_is_exact(
    path: str,
    directory: bool | None,
    expected: bool,
) -> None:
    assert r4w.WindowsArch128ReadOnlyReader._allowed(
        path,
        directory=directory,
    ) is expected


def test_read_only_reader_rejects_alternate_path_syntax() -> None:
    assert not r4w.WindowsArch128ReadOnlyReader._allowed(
        r4.STAGING_PATH + r"\source\..\escape",
        directory=True,
    )
    assert not r4w.WindowsArch128ReadOnlyReader._allowed(
        r4.STAGING_PATH.lower(),
        directory=True,
    ) or r4.STAGING_PATH.lower() == r4.STAGING_PATH


@pytest.mark.parametrize(
    "step",
    [r4.RenameStep.OLD_TO_RETIRED, r4.RenameStep.STAGING_TO_CANONICAL],
)
def test_rename_info_is_no_replace_and_parent_relative(step: r4.RenameStep) -> None:
    buffer = r4w._fixed_rename_info(step, 123)
    info = r4w._FileRenameInformation.from_buffer(buffer)
    assert info.replace_if_exists == 0
    assert info.root_directory == 123
    assert info.file_name_length > 0
    assert len(buffer) > r4w._FileRenameInformation.file_name.offset


def test_rename_info_rejects_invalid_parent_handle() -> None:
    with pytest.raises(legacy_windows.AdmissionBlocked):
        r4w._fixed_rename_info(r4.RenameStep.OLD_TO_RETIRED, 0)


def test_adapter_import_has_no_operator_or_scheduler_entrypoint() -> None:
    source = Path(r4w.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "Schedule.Service",
        "subprocess",
        "getpass",
        "provider",
        "Paper-v2",
        "broker",
        "live",
        "def main(",
        "if __name__ ==",
    ):
        assert forbidden not in source


def test_adapter_uses_new_r4_contract_not_legacy_identity_constants() -> None:
    source = Path(r4w.__file__).read_text(encoding="utf-8")
    assert "d10_arch128_r4_replacement as r4" in source
    assert "r4.fixed_rename_paths" in source
    assert "legacy_windows._FILE_RENAME_INFORMATION_CLASS" in source
    assert "legacy_windows.replacement." not in source


def test_rename_success_requires_post_call_handle_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = object()
    source = object()

    class Fake(r4w.WindowsArch128ReadOnlyReader):
        def __init__(self) -> None:
            pass

        def _open_rename_parent(self) -> int:
            return 1

        def _open_rename_source(self, path: str) -> int:
            assert path == r4.CANONICAL_PATH
            return 2

        def _inspect(self, handle: int, path: str):
            if handle == 1:
                return parent
            if path == r4.CANONICAL_PATH:
                return source
            raise AssertionError

        def absent(self, path: str) -> bool:
            assert path == r4.RETIRED_PATH
            return True

        def _close(self, handle: int) -> None:
            assert handle in (1, 2)

    fake = Fake()

    monkeypatch.setattr(r4w, "require_parent_native_object", lambda value: None)
    monkeypatch.setattr(
        r4w,
        "require_native_object",
        lambda value, path, directory: None,
    )
    monkeypatch.setattr(
        r4w,
        "_set_fixed_rename",
        lambda *args: (
            0,
            type("Io", (), {"status": 0, "information": 0})(),
            64,
        ),
    )
    monkeypatch.setattr(r4w, "replace", lambda value, **kwargs: source)

    outcome = r4w.rename_fixed_step(
        fake,
        r4.RenameStep.OLD_TO_RETIRED,
        source,
        parent,
    )
    assert outcome is r4.MutationOutcome.INDETERMINATE


def test_rename_native_status_is_terminal_indeterminate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = Path(r4w.__file__).read_text(encoding="utf-8")
    assert "return r4.MutationOutcome.INDETERMINATE" in source_text
    assert "retry" not in source_text.casefold()
    assert "replace_if_exists = 0" in source_text
