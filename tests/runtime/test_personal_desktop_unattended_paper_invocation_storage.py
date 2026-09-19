"""Focused PD4-B1 fixed read-only unattended-invocation storage tests."""

import ctypes
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from tests.market_data.daily_snapshot_test_support import calendar
from tests.runtime.test_manual_paper_strategy_plan import _binding
from tests.runtime.test_personal_desktop_paper_account_security import (
    SID,
    MemoryReadApi,
)

from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime import (
    personal_desktop_unattended_paper_invocation_storage as storage,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)
from trading_bot.runtime.personal_desktop_unattended_paper_invocation import (
    create_personal_desktop_unattended_paper_invocation,
    serialize_personal_desktop_unattended_paper_invocation,
    verify_personal_desktop_unattended_paper_invocation,
)

from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)


@pytest.fixture(autouse=True)
def block_real_native(monkeypatch, prohibit_production_effects):
    def forbidden(*_args, **_kwargs):
        pytest.fail("PD4-B1 tests must never load a native DLL")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)


class Observer:
    def __init__(self, *observations):
        self.observations = list(observations) or [_token(), _token()]
        self.calls = 0

    def observe(self):
        value = self.observations[min(self.calls, len(self.observations) - 1)]
        self.calls += 1
        if isinstance(value, BaseException):
            raise value
        return value


def _token(**changes):
    return replace(
        TradingTokenObservation(SID, 1, False, False, ()),
        **changes,
    )


def _expected(*, caller_key="manual-cycle-1"):
    invocation = create_personal_desktop_unattended_paper_invocation(
        _binding(caller_key=caller_key), calendar()
    )
    payload = serialize_personal_desktop_unattended_paper_invocation(invocation)
    return verify_personal_desktop_unattended_paper_invocation(payload, calendar())


def _directory(identity, *, staging=False):
    return (
        security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
        + "\\"
        + storage.unattended_paper_invocation_directory_name(identity, staging=staging)
    )


def _put_final(api, binding, *, directory_id=None, artifact_id=None):
    directory_id = directory_id or binding.invocation.invocation_id
    artifact_id = artifact_id or directory_id
    directory = _directory(directory_id)
    api.put(directory)
    api.put(
        directory
        + "\\"
        + storage.unattended_paper_invocation_artifact_name(artifact_id),
        binding.artifact_bytes,
    )
    return directory


def _read(api, expected, *, observer=None):
    return storage._read_personal_desktop_unattended_invocation_storage_for_test(
        expected,
        SID,
        api=api,
        observer=observer or Observer(),
        calendar=calendar(),
    )


def test_fixed_names_and_canonical_name_helpers_are_exact():
    expected = _expected()
    identity = expected.invocation.invocation_id
    assert security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS == (
        r"F:\AITradingBot\Paper-v2\runtime\unattended-invocations"
    )
    assert storage.unattended_paper_invocation_directory_name(identity) == (
        f"unattended-paper-invocation-{identity}"
    )
    assert (
        storage.unattended_paper_invocation_directory_name(identity, staging=True)
        == f".unattended-paper-invocation-{identity}.staging"
    )
    assert storage.unattended_paper_invocation_artifact_name(identity) == (
        f"personal-desktop-unattended-paper-invocation-{identity}.json"
    )


def test_safe_empty_namespace_is_absent_and_performs_only_reads():
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)

    result = _read(api, expected)

    assert (
        result.classification
        is storage.PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
    )
    assert result.finalized_invocation_count == 0
    assert result.matching_invocation_id is None
    assert {call[0] for call in api.calls} <= {"open", "close", "inspect", "names"}


def test_unprovisioned_fixed_parent_is_blocked_not_absent():
    result = _read(MemoryReadApi(), _expected())

    assert result.classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


def test_expected_finalized_exact_artifact_is_identical():
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    _put_final(api, expected)

    result = _read(api, expected)

    assert result.classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.FINALIZED_IDENTICAL
    )
    assert result.finalized_invocation_count == 1
    assert result.matching_invocation_id == expected.invocation.invocation_id


def test_different_canonical_artifact_in_expected_final_is_conflicting():
    expected = _expected()
    different = _expected(caller_key="manual-cycle-conflict")
    api = MemoryReadApi()
    api.trading_runtime = True
    _put_final(api, different, directory_id=expected.invocation.invocation_id)

    result = _read(api, expected)

    assert result.classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.CONFLICTING
    )
    assert result.finalized_invocation_count == 1


@pytest.mark.parametrize("with_final", (False, True))
def test_any_safe_staging_is_dominant(with_final):
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(_directory(expected.invocation.invocation_id, staging=True))
    if with_final:
        _put_final(api, expected)

    result = _read(api, expected)

    assert result.classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.STAGING_PRESENT
    )
    assert result.finalized_invocation_count == int(with_final)
    assert any(call[0] == "read" for call in api.calls) is with_final


def test_staging_does_not_hide_malformed_historical_final():
    expected = _expected()
    historical = _expected(caller_key="manual-cycle-staging-history")
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(_directory(expected.invocation.invocation_id, staging=True))
    historical_directory = _directory(historical.invocation.invocation_id)
    api.put(historical_directory)
    api.overrides[historical_directory] = ()

    assert _read(api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


@pytest.mark.parametrize(
    "entries",
    (
        ("unknown",),
        ("unattended-paper-invocation-not-a-uuid",),
        (
            "unattended-paper-invocation-11111111-1111-5111-8111-111111111111",
            "UNATTENDED-PAPER-INVOCATION-11111111-1111-5111-8111-111111111111",
        ),
    ),
)
def test_unknown_malformed_or_casefold_colliding_parent_entry_blocks(entries):
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
    api.put(parent)
    api.overrides[parent] = entries

    assert _read(api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


@pytest.mark.parametrize("children", ((), ("wrong.json",), ("expected", "extra")))
def test_finalized_directory_missing_wrong_or_extra_child_blocks(children):
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    directory = _directory(expected.invocation.invocation_id)
    api.put(directory)
    artifact = storage.unattended_paper_invocation_artifact_name(
        expected.invocation.invocation_id
    )
    values = tuple(artifact if value == "expected" else value for value in children)
    api.overrides[directory] = values

    assert _read(api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


def test_artifact_filename_identity_mismatch_blocks_before_file_open():
    expected = _expected()
    different = _expected(caller_key="manual-cycle-wrong-name")
    api = MemoryReadApi()
    api.trading_runtime = True
    directory = _directory(expected.invocation.invocation_id)
    api.put(directory)
    wrong_name = storage.unattended_paper_invocation_artifact_name(
        different.invocation.invocation_id
    )
    api.overrides[directory] = (wrong_name,)

    result = _read(api, expected)

    assert (
        result.classification
        is storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )
    assert not any(
        call[0] == "open" and call[1].endswith(wrong_name) for call in api.calls
    )


def test_invalid_noncanonical_or_tampered_artifact_blocks():
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    directory = _put_final(api, expected)
    path = (
        directory
        + "\\"
        + storage.unattended_paper_invocation_artifact_name(
            expected.invocation.invocation_id
        )
    )
    tree = json.loads(expected.artifact_bytes)
    tree["policy_version"] = "tampered"
    payload = (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()
    api.nodes[path].payload = payload
    api.nodes[path].observation = replace(
        api.nodes[path].observation,
        byte_length=len(payload),
    )

    assert _read(api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


def test_malformed_unrelated_historical_final_blocks_expected_read():
    expected = _expected()
    historical = _expected(caller_key="manual-cycle-history")
    api = MemoryReadApi()
    api.trading_runtime = True
    _put_final(api, expected)
    directory = _directory(historical.invocation.invocation_id)
    api.put(directory)
    api.overrides[directory] = ()

    assert _read(api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


def test_historical_directory_and_embedded_artifact_identity_mismatch_blocks():
    expected = _expected()
    historical = _expected(caller_key="manual-cycle-history-name")
    different = _expected(caller_key="manual-cycle-history-payload")
    api = MemoryReadApi()
    api.trading_runtime = True
    _put_final(api, different, directory_id=historical.invocation.invocation_id)

    assert _read(api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


def test_multiple_valid_historical_finals_are_accepted_within_bounds():
    expected = _expected()
    first = _expected(caller_key="manual-cycle-history-1")
    second = _expected(caller_key="manual-cycle-history-2")
    api = MemoryReadApi()
    api.trading_runtime = True
    _put_final(api, first)
    _put_final(api, second)

    result = _read(api, expected)

    assert (
        result.classification
        is storage.PersonalDesktopUnattendedInvocationStorageClassification.ABSENT
    )
    assert result.finalized_invocation_count == 2


def test_parent_and_child_security_must_match_exact_owners():
    expected = _expected()
    parent_api = MemoryReadApi()
    parent_api.trading_runtime = True
    parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
    parent_api.put(parent)
    parent_api.nodes[parent].observation = replace(
        parent_api.nodes[parent].observation,
        security=replace(parent_api.nodes[parent].observation.security, owner_sid=SID),
    )
    assert _read(parent_api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )

    child_api = MemoryReadApi()
    child_api.trading_runtime = True
    directory = _put_final(child_api, expected)
    child_api.nodes[directory].observation = replace(
        child_api.nodes[directory].observation,
        security=replace(
            child_api.nodes[directory].observation.security,
            owner_sid=security.ADMINISTRATORS_SID,
        ),
    )
    assert _read(child_api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


@pytest.mark.parametrize("bound", ("inventory", "bytes", "objects"))
def test_inventory_read_byte_and_pinned_object_bounds_fail_closed(monkeypatch, bound):
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    parent = security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS
    if bound == "inventory":
        api.put(parent)
        api.overrides[parent] = tuple(f"entry-{index}" for index in range(3))
        monkeypatch.setattr(security, "MAX_PAPER_V2_DIRECTORY_ENTRIES", 2)
    else:
        _put_final(api, expected)
        if bound == "bytes":
            monkeypatch.setattr(security, "MAX_PAPER_V2_READ_BYTES", 1)
        else:
            monkeypatch.setattr(security, "MAX_PAPER_V2_PINNED_OBJECTS", 3)

    assert _read(api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


def test_token_drift_and_expected_replay_failure_block_before_trust(monkeypatch):
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)
    drifted = Observer(_token(), _token(elevated=True))
    assert _read(api, expected, observer=drifted).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )

    api.calls.clear()

    def reject(*_args, **_kwargs):
        raise ValueError("replay rejected")

    monkeypatch.setattr(
        storage, "verify_personal_desktop_unattended_paper_invocation", reject
    )
    assert _read(api, expected).classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )
    assert api.calls == []


def _production_read(monkeypatch, api, expected, *, reject_post=False):
    c1 = SimpleNamespace(approved_account_sid=SID)
    calls = 0

    def require(authority):
        nonlocal calls
        calls += 1
        if reject_post and calls == 2:
            raise ValueError("C1 drift")
        assert authority is c1
        return c1

    monkeypatch.setattr(storage, "require_validated_production_authority", require)
    monkeypatch.setattr(storage, "WindowsTradingTokenObserver", Observer)
    monkeypatch.setattr(storage, "WindowsPaperReadNativeApi", lambda: api)
    monkeypatch.setattr(storage, "BoundMarketCalendar", lambda *_args: calendar())
    return storage.read_personal_desktop_unattended_invocation_storage(c1, expected)


@pytest.mark.parametrize("finalized", (False, True))
def test_safe_production_simulation_mints_private_provenance(monkeypatch, finalized):
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    if finalized:
        _put_final(api, expected)
    else:
        api.put(security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)

    result = _production_read(monkeypatch, api, expected)
    evidence = (
        storage.require_validated_personal_desktop_unattended_invocation_storage_read(
            result
        )
    )

    assert evidence.expected == expected
    assert evidence.authority is not None


def test_c1_post_read_drift_blocks_and_never_registers(monkeypatch):
    expected = _expected()
    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)

    result = _production_read(monkeypatch, api, expected, reject_post=True)

    assert (
        result.classification
        is storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )
    with pytest.raises(storage.PersonalDesktopUnattendedInvocationStorageError):
        storage.require_validated_personal_desktop_unattended_invocation_storage_read(
            result
        )


def test_invalid_c1_blocks_before_token_or_filesystem(monkeypatch):
    expected = _expected()

    def reject(_authority):
        raise ValueError("not production C1")

    monkeypatch.setattr(storage, "require_validated_production_authority", reject)
    monkeypatch.setattr(
        storage,
        "WindowsTradingTokenObserver",
        lambda: pytest.fail("token observation must follow genuine C1"),
    )
    monkeypatch.setattr(
        storage,
        "WindowsPaperReadNativeApi",
        lambda: pytest.fail("filesystem construction must follow genuine C1"),
    )

    result = storage.read_personal_desktop_unattended_invocation_storage(
        object(), expected
    )

    assert result.classification is (
        storage.PersonalDesktopUnattendedInvocationStorageClassification.BLOCKED
    )


def test_disposable_constructed_and_unsafe_results_have_no_production_provenance():
    expected = _expected()
    classifications = storage.PersonalDesktopUnattendedInvocationStorageClassification
    diagnostics = storage.PersonalDesktopUnattendedInvocationStorageDiagnostic

    api = MemoryReadApi()
    api.trading_runtime = True
    api.put(security.PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_INVOCATIONS)
    disposable = _read(api, expected)
    constructed = storage.PersonalDesktopUnattendedInvocationStorageReadResult(
        classifications.ABSENT,
        expected.invocation.invocation_id,
        0,
        None,
        diagnostics.VERIFIED_ABSENT,
    )
    unsafe = []
    for classification, diagnostic in (
        (classifications.BLOCKED, diagnostics.VERIFICATION_BLOCKED),
        (classifications.STAGING_PRESENT, diagnostics.STAGING_PRESENT),
        (classifications.CONFLICTING, diagnostics.VERIFIED_CONFLICT),
    ):
        unsafe.append(
            storage.PersonalDesktopUnattendedInvocationStorageReadResult(
                classification,
                expected.invocation.invocation_id,
                0,
                None,
                diagnostic,
            )
        )
    for result in (disposable, constructed, *unsafe):
        with pytest.raises(storage.PersonalDesktopUnattendedInvocationStorageError):
            storage.require_validated_personal_desktop_unattended_invocation_storage_read(
                result
            )


def test_storage_surface_exposes_no_output_recovery_or_execution_callable():
    forbidden_fragments = ("publish", "write", "rename", "recover", "execute")
    public_callables = {
        name
        for name, value in storage.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    assert not any(
        fragment in name
        for name in public_callables
        for fragment in forbidden_fragments
    )
