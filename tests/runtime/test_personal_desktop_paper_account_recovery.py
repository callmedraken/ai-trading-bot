"""FR2 memory-only observations: no test opens any real production object."""

import inspect
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from itertools import product
from types import SimpleNamespace

import pytest

from trading_bot.runtime import (
    personal_desktop_paper_account_publication_freeze as freeze_module,
)
from trading_bot.runtime import personal_desktop_paper_account_recovery as recovery
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.paper_account_checkpoint import (
    PaperAccountGenesisRequest,
    create_genesis_paper_account_checkpoint,
    serialize_paper_account_checkpoint,
)
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountAnchor,
    canonical_personal_desktop_paper_json,
    derive_personal_desktop_paper_account_id,
    parse_personal_desktop_paper_account_anchor,
    serialize_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_publication_freeze import (
    PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_security import (
    AuthorityObjectKind,
    SecurityInspection,
)

from .test_personal_desktop_paper_account_publication import (
    ADMIN,
)
from .test_personal_desktop_paper_account_publication import (
    prohibit_production_effects as prohibit_production_effects,
)
from .test_personal_desktop_paper_account_publication_freeze import (
    administrator as administrator,
)
from .test_personal_desktop_paper_account_security import MemoryReadApi, Node

ROOT = security.PERSONAL_DESKTOP_PAPER_V2_STAGING_ROOT
PARENT = security.PERSONAL_DESKTOP_PAPER_PARENT
ANCHOR = ROOT + r"\personal-desktop-paper-account-authority.json"
NAMES = ("Paper", ".Paper.provisioning-v1", "Paper-v2", ".Paper-v2.provisioning")
RECOVERY_NATIVE = recovery._WindowsRecoveryReadApi


def forbidden(*args, **kwargs):
    raise AssertionError("FR2 test reached a real native/C1/effect boundary")


@pytest.fixture(autouse=True)
def block_real_recovery(monkeypatch, prohibit_production_effects):
    monkeypatch.setattr(recovery, "_WindowsRecoveryReadApi", forbidden)
    monkeypatch.setattr(recovery, "WindowsTradingTokenObserver", forbidden)
    monkeypatch.setattr(recovery, "validate_installed_authority_complete", forbidden)
    monkeypatch.setattr(recovery, "require_windows_platform", forbidden)


@pytest.fixture
def freeze():
    return PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE


def artifacts(freeze, *, cash=None, as_of=None):
    checkpoint = create_genesis_paper_account_checkpoint(
        PaperAccountGenesisRequest(
            as_of=as_of or freeze.genesis_as_of,
            cash=freeze.starting_cash if cash is None else cash,
            positions=(),
            realized_profit_loss=Decimal("0"),
            open_orders=(),
            metadata=(),
        )
    )
    payload = serialize_paper_account_checkpoint(checkpoint)
    identity = dict(
        machine_authority_id=freeze.machine_authority_id,
        approved_trading_sid=freeze.approved_trading_sid,
        genesis_checkpoint_id=str(checkpoint.checkpoint_id),
        genesis_sha256=sha256(payload).hexdigest(),
        genesis_byte_length=len(payload),
    )
    anchor = PersonalDesktopPaperAccountAnchor(
        derive_personal_desktop_paper_account_id(**identity), **identity
    )
    return payload, serialize_personal_desktop_paper_account_anchor(anchor)


class MemoryRecoveryApi(MemoryReadApi):
    def install(self, genesis, anchor_bytes, sid):
        anchor = parse_personal_desktop_paper_account_anchor(anchor_bytes)
        self.put(PARENT)
        paths = recovery._RecoveryPaths()
        staged = paths.bind(anchor)
        for path in staged:
            spec = paths.object_spec(path)
            policy = security.paper_security_policy(spec.role, sid)
            payload = (
                anchor_bytes
                if path == ANCHOR
                else genesis
                if spec.kind is AuthorityObjectKind.FILE
                else None
            )
            self.nodes[path] = Node(
                security.PaperObjectObservation(
                    SecurityInspection(
                        path,
                        path,
                        spec.kind,
                        policy.owner_sid,
                        True,
                        policy.aces,
                        False,
                        "F:\\",
                        "NTFS",
                    ),
                    (7, len(self.nodes) + 10),
                    len(payload) if payload else 0,
                    1,
                ),
                payload,
            )
        # Historical v1 has NAME presence only: no v1 node exists to inspect.
        self.overrides[PARENT] = (NAMES[1], NAMES[3], "Authority", "runtime", "temp")
        return staged


@pytest.fixture
def case(monkeypatch, freeze, administrator):
    api = MemoryRecoveryApi()
    genesis, anchor = artifacts(freeze)
    staged = api.install(genesis, anchor, freeze.approved_trading_sid)
    state = SimpleNamespace(
        api=api,
        paths=staged,
        freeze=freeze,
        validation=administrator,
        token=ADMIN,
        native_calls=0,
        c1_calls=0,
    )

    def native(paths):
        state.native_calls += 1
        return api

    def c1():
        state.c1_calls += 1
        return state.validation

    monkeypatch.setattr(recovery, "require_windows_platform", lambda: None)
    monkeypatch.setattr(recovery, "_WindowsRecoveryReadApi", native)
    monkeypatch.setattr(
        recovery,
        "WindowsTradingTokenObserver",
        lambda: SimpleNamespace(observe=lambda: state.token),
    )
    monkeypatch.setattr(recovery, "validate_installed_authority_complete", c1)
    monkeypatch.setattr(
        recovery, "require_production_paper_publication_freeze", lambda: state.freeze
    )
    yield state
    assert not api.handles
    assert all(call[0] in {"open", "close", "names", "read"} for call in api.calls)
    assert not any(
        call[0] == "open" and call[1].startswith(PARENT + "\\" + NAMES[1])
        for call in api.calls
    )


def test_exact_production_freeze_reconstructed_from_observed_bytes(case):
    result = recovery.qualify_personal_desktop_paper_staging_recovery()
    assert not inspect.signature(
        recovery.qualify_personal_desktop_paper_staging_recovery
    ).parameters
    assert result.paper_account_id == case.freeze.paper_account_id
    assert result.genesis_checkpoint_id == "1832a2b5-8b63-501a-8f7d-f1722c32307b"
    for field, value in asdict(case.freeze).items():
        assert getattr(result, field) == value
    assert tuple(path for path, _ in result.objects) == case.paths
    assert len(result.objects) == 6
    assert all(obs == case.api.nodes[path].observation for path, obs in result.objects)
    assert result.v2_state is recovery.PaperPublicationState.STAGING_REQUIRES_REVIEW
    assert result.v1_final_present is False
    assert result.v1_historical_staging_present is True
    assert case.c1_calls == 2
    assert all(count >= 3 for count in case.api.inspections.values())
    with pytest.raises(FrozenInstanceError):
        result.paper_account_id = "changed"
    assert not any(
        callable(getattr(result, name))
        for name in dir(result)
        if not name.startswith("_")
    )


@pytest.mark.parametrize("value", [True, None, 0, 1, "False"])
def test_effect_gate_first_before_any_reader(case, monkeypatch, value):
    with monkeypatch.context() as patch:
        patch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", value
        )
        patch.setattr(
            recovery, "require_production_paper_publication_freeze", forbidden
        )
        with pytest.raises(WindowsAuthorityError, match="disarmed"):
            recovery.qualify_personal_desktop_paper_staging_recovery()
    assert case.native_calls == case.c1_calls == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"elevated": False},
        {"token_type": 2},
        {"thread_token_present": True},
        {"groups": ()},
        {"groups": ((security.ADMINISTRATORS_SID, 16),)},
        {"user_sid": "invalid"},
    ],
)
def test_administrator_gate_precedes_staging(case, changes):
    case.token = replace(ADMIN, **changes)
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()
    assert case.native_calls == case.c1_calls == 0


def test_non_windows_precedes_staging(case, monkeypatch):
    def not_windows():
        raise WindowsAuthorityError("Windows required")

    monkeypatch.setattr(recovery, "require_windows_platform", not_windows)
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()
    assert case.native_calls == 0


@pytest.mark.parametrize(
    "change",
    [
        "uninitialized",
        "unsupported",
        "missing",
        "machine",
        "sid",
        "bootstrap",
        "incomplete",
    ],
)
def test_current_c1_failure(case, change):
    validation = case.validation
    if change == "uninitialized":
        validation = replace(
            validation,
            provisioning=replace(validation.provisioning, database_state="ABSENT"),
        )
    elif change == "unsupported":
        validation = replace(
            validation,
            production_evidence=replace(
                validation.production_evidence, schema_version=999
            ),
        )
    elif change == "missing":
        validation = replace(validation, production_evidence=None)
    elif change in {"machine", "sid"}:
        field, value = (
            ("machine_authority_id", "11111111-1111-4111-8111-111111111111")
            if change == "machine"
            else ("approved_account_sid", "S-1-5-21-1-2-3-1009")
        )
        bootstrap = replace(
            validation.bootstrap_verification.bootstrap, **{field: value}
        )
        validation = replace(
            validation,
            bootstrap_verification=replace(
                validation.bootstrap_verification, bootstrap=bootstrap
            ),
        )
    elif change == "bootstrap":
        validation = replace(
            validation,
            bootstrap_verification=replace(
                validation.bootstrap_verification, signature_length=0
            ),
        )
    else:
        validation = replace(
            validation,
            provisioning=replace(validation.provisioning, database_present=False),
        )
    case.validation = validation
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize(
    "present",
    [p for p in product((False, True), repeat=4) if p != (False, True, False, True)],
)
def test_every_wrong_frozen_occupancy_blocks_before_staging(case, present):
    case.api.overrides[PARENT] = tuple(
        name for name, yes in zip(NAMES, present, strict=True) if yes
    )
    with pytest.raises(WindowsAuthorityError, match="occupancy"):
        recovery.qualify_personal_desktop_paper_staging_recovery()
    assert not any(call[0] == "open" and call[1] == ROOT for call in case.api.calls)


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize(
    "change",
    [
        "path",
        "reparse",
        "kind",
        "owner",
        "acl",
        "unprotected",
        "identity",
        "filesystem",
        "volume",
    ],
)
def test_each_staged_object_security(case, index, change):
    node = case.api.nodes[case.paths[index]]
    if change == "identity":
        node.observation = replace(node.observation, identity=(7, 0))
    else:
        facts = node.observation.security
        updates = {
            "path": {"final_path": facts.final_path.lower()},
            "reparse": {"is_reparse_point": True},
            "kind": {
                "kind": AuthorityObjectKind.FILE
                if facts.kind is AuthorityObjectKind.DIRECTORY
                else AuthorityObjectKind.DIRECTORY
            },
            "owner": {"owner_sid": case.freeze.approved_trading_sid},
            "acl": {"aces": facts.aces[:-1]},
            "unprotected": {"dacl_protected": False},
            "filesystem": {"filesystem": "FAT32"},
            "volume": {"volume_root": "G:\\"},
        }
        node.observation = replace(
            node.observation, security=replace(facts, **updates[change])
        )
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize("place", ["parent", 0, 2, 4, 5])
@pytest.mark.parametrize(
    "change", ["extra", "missing", "duplicate", "case", "alias", "traversal"]
)
def test_unsafe_or_inexact_inventory(case, place, change):
    path = PARENT if place == "parent" else case.paths[place]
    names = case.api.names(None, path, 1024)
    if change == "missing":
        if not names:
            del case.api.nodes[path]
            with pytest.raises(WindowsAuthorityError):
                recovery.qualify_personal_desktop_paper_staging_recovery()
            return
        names = names[1:]
    elif change == "extra":
        names += (
            "Paper"
            if place == "parent"
            else "paper-account-genesis-11111111-1111-5111-8111-111111111111",
        )
    elif change in {"duplicate", "case"}:
        names += ((names[0] if names else "x"),)
        names += ((names[-1].upper() if change == "case" else names[-1]),)
    else:
        names += (("name." if change == "alias" else ".."),)
    case.api.overrides[path] = names
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


def test_missing_object_fails(case):
    case.api.nodes.pop(case.paths[5], None)
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize("index", [1, 3])
@pytest.mark.parametrize("links", [0, 2, 99])
def test_files_require_single_link(case, index, links):
    node = case.api.nodes[case.paths[index]]
    node.observation = replace(node.observation, links=links)
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize(
    "field",
    [
        "anchor_sha256",
        "anchor_byte_length",
        "genesis_sha256",
        "genesis_byte_length",
        "manifest_sha256",
        "manifest_byte_length",
        "paper_account_id",
        "starting_cash",
        "genesis_as_of",
    ],
)
def test_each_freeze_binding(case, field):
    old = getattr(case.freeze, field)
    value = (
        "0" * 64
        if field.endswith("sha256")
        else old + 1
        if field.endswith("length")
        else {
            "paper_account_id": "11111111-1111-4111-8111-111111111111",
            "starting_cash": Decimal("24999"),
            "genesis_as_of": case.freeze.genesis_as_of + timedelta(microseconds=1),
        }[field]
    )
    case.freeze = replace(case.freeze, **{field: value})
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize(
    "payload", [b"{", b"{}\n", b"\xef\xbb\xbf{}\n", b'{"schema":1,"schema":2}\n']
)
def test_malformed_anchor(case, payload):
    node = case.api.nodes[ANCHOR]
    node.payload = payload
    node.observation = replace(node.observation, byte_length=len(payload))
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize("index", [1, 3])
@pytest.mark.parametrize(
    "change", ["noncanonical", "hash", "length", "account", "checkpoint"]
)
def test_artifact_corruption(case, index, change):
    node = case.api.nodes[case.paths[index]]
    if change == "length":
        node.observation = replace(
            node.observation, byte_length=node.observation.byte_length + 1
        )
    else:
        if change == "noncanonical":
            node.payload += b" "
        elif change == "hash":
            node.payload = (
                node.payload.replace(b"25000", b"25001")
                if index == 3
                else node.payload.replace(b'"layout"', b'"layoux"')
            )
        else:
            target = (
                case.freeze.paper_account_id
                if change == "account" and index == 1
                else "1832a2b5-8b63-501a-8f7d-f1722c32307b"
            )
            node.payload = node.payload.replace(
                target.encode(), b"11111111-1111-4111-8111-111111111111"
            )
        node.observation = replace(node.observation, byte_length=len(node.payload))
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize("place", ["parent", 0, 1, 2, 3, 4, 5])
@pytest.mark.parametrize(
    "change", ["identity", "replacement", "acl", "inventory", "metadata"]
)
def test_pinned_drift_and_independent_named_reopen(case, place, change):
    target = PARENT if place == "parent" else case.paths[place]

    def drift(path, count, node):
        # Parent has an earlier occupancy revalidation; staged objects do not.
        if path != target or count != (4 if place == "parent" else 2):
            return
        if change in {"identity", "replacement"}:
            observed = replace(node.observation, identity=(7, 999))
        elif change == "acl":
            observed = replace(
                node.observation, security=replace(node.observation.security, aces=())
            )
        elif change == "metadata":
            observed = replace(
                node.observation, byte_length=node.observation.byte_length + 1
            )
        else:
            if node.payload is not None:
                node.payload += b" "
            else:
                case.api.overrides[path] = (*case.api.names(None, path, 1024), "extra")
            return
        if change == "replacement":
            case.api.nodes[path] = replace(node, observation=observed)
        else:
            node.observation = observed

    case.api.on_inspect = drift
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize("operation", ["open", "read", "inspect", "names"])
def test_native_failure_never_returns_partial_result(case, operation):
    def fail(*args):
        raise AuthorityObjectError("injected read failure")

    setattr(case.api, operation, fail)
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


def test_c1_completion_drift_blocks(case):
    def drift(node):
        case.token = replace(ADMIN, thread_token_present=True)

    case.api.on_read = drift
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize(
    "path",
    [
        ROOT.lower(),
        ROOT + ".",
        ROOT + " ",
        ROOT + "\\",
        ROOT + ":ads",
        ROOT + r"\..\Paper-v2",
        "\\\\?\\" + ROOT,
        r"\\?\GLOBALROOT\Device\HarddiskVolume1",
        r"\\server\share",
        security.PERSONAL_DESKTOP_PAPER_V2_ROOT,
        PARENT + r"\.Paper.provisioning-v1",
    ],
)
def test_separate_recovery_resolver_rejects_aliases(path):
    with pytest.raises(AuthorityPathError):
        recovery._RecoveryPaths().object_spec(path)


def test_normal_authority_still_rejects_staging_and_names_do_not_bind_genesis(case):
    with pytest.raises(AuthorityPathError):
        security.paper_object_spec(ROOT)
    with security.PinnedPaperReadSession(
        case.api, case.freeze.approved_trading_sid
    ) as session:
        with pytest.raises(AuthorityPathError):
            session.pin(ROOT)
    paths = recovery._RecoveryPaths()
    with pytest.raises(AuthorityPathError):
        paths.object_spec(case.paths[2])
    assert case.api.calls == []


def test_manifest_reconstruction_cannot_skip_serializer(case, monkeypatch):
    def wrong_manifest(manifest):
        return canonical_personal_desktop_paper_json({**asdict(manifest), "unknown": 1})

    monkeypatch.setattr(
        recovery, "serialize_personal_desktop_paper_account_manifest", wrong_manifest
    )
    with pytest.raises(WindowsAuthorityError):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize("value", [None, {}, "damaged"])
def test_absent_or_wrong_source_freeze_precedes_native(case, monkeypatch, value):
    with monkeypatch.context() as patch:
        patch.setattr(
            freeze_module, "PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE", value
        )
        patch.setattr(
            recovery,
            "require_production_paper_publication_freeze",
            freeze_module.require_production_paper_publication_freeze,
        )
        with pytest.raises(WindowsAuthorityError):
            recovery.qualify_personal_desktop_paper_staging_recovery()
    assert case.native_calls == case.c1_calls == 0


def test_damaged_freeze_instance_is_revalidated(case, monkeypatch):
    damaged = replace(case.freeze)
    object.__setattr__(damaged, "manifest_byte_length", 0)
    with monkeypatch.context() as patch:
        patch.setattr(
            freeze_module, "PERSONAL_DESKTOP_PAPER_V2_PUBLICATION_FREEZE", damaged
        )
        patch.setattr(
            recovery,
            "require_production_paper_publication_freeze",
            freeze_module.require_production_paper_publication_freeze,
        )
        with pytest.raises(WindowsAuthorityError):
            recovery.qualify_personal_desktop_paper_staging_recovery()
    assert case.native_calls == case.c1_calls == 0


def test_native_recovery_flags_and_admission_are_read_only(case):
    calls = []

    class CreateFile:
        def __call__(self, *args):
            calls.append(args)
            return 9

    api = object.__new__(RECOVERY_NATIVE)
    api._kernel = SimpleNamespace(CreateFileW=CreateFile())
    api._paths = recovery._RecoveryPaths()
    for path in (ROOT, ANCHOR):
        handle = api.open(path, api.object_spec(path).kind)
        handle._close = False  # A fake integer must never reach CloseHandle.
    assert [call[2] for call in calls] == [3, 1]
    assert all(
        call[1] == 0x20081 and call[4] == 3 and call[5] == 0x02200000 for call in calls
    )
    for path in (ROOT + ".", case.paths[2], security.PERSONAL_DESKTOP_PAPER_V2_ROOT):
        with pytest.raises(AuthorityPathError):
            api.open(path, AuthorityObjectKind.DIRECTORY)
    assert len(calls) == 2
    assert {name for name in dir(api) if not name.startswith("_")} == {
        "open",
        "close",
        "inspect",
        "read",
        "names",
        "object_spec",
    }
    ordinary = object.__new__(security.WindowsPaperReadNativeApi)
    ordinary._kernel = api._kernel
    with pytest.raises(AuthorityPathError):
        ordinary.open(ROOT, AuthorityObjectKind.DIRECTORY)
    assert len(calls) == 2


def test_wrong_checkpoint_id_even_with_rederived_account_is_rejected(case):
    original = parse_personal_desktop_paper_account_anchor(
        case.api.nodes[ANCHOR].payload
    )
    identity = {
        key: getattr(original, key)
        for key in (
            "machine_authority_id",
            "approved_trading_sid",
            "genesis_checkpoint_id",
            "genesis_sha256",
            "genesis_byte_length",
        )
    }
    identity["genesis_checkpoint_id"] = "11111111-1111-5111-8111-111111111111"
    wrong = PersonalDesktopPaperAccountAnchor(
        derive_personal_desktop_paper_account_id(**identity), **identity
    )
    anchor_bytes = serialize_personal_desktop_paper_account_anchor(wrong)
    genesis = case.api.nodes[case.paths[3]].payload
    case.api.nodes.clear()
    case.paths = case.api.install(
        genesis, anchor_bytes, case.freeze.approved_trading_sid
    )
    case.freeze = replace(
        case.freeze,
        anchor_sha256=sha256(anchor_bytes).hexdigest(),
        anchor_byte_length=len(anchor_bytes),
        paper_account_id=wrong.paper_account_id,
    )
    with pytest.raises(WindowsAuthorityError, match="GENESIS"):
        recovery.qualify_personal_desktop_paper_staging_recovery()


@pytest.mark.parametrize("change", ["freeze", "c1", "token", "gate"])
def test_final_revalidation_is_inside_pinned_interval(case, monkeypatch, change):
    def drift(path, count, node):
        if path != ANCHOR or count != 2:
            return
        assert len(case.api.handles) == 8  # Both ancestors and all six staged objects.
        if change == "freeze":
            case.freeze = replace(case.freeze, starting_cash=Decimal("1"))
        elif change == "c1":
            case.validation = replace(
                case.validation,
                production_evidence=replace(
                    case.validation.production_evidence, metadata_digest="77" * 32
                ),
            )
        elif change == "token":
            case.token = replace(ADMIN, elevated=False)
        else:
            monkeypatch.setattr(
                security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", True
            )

    case.api.on_inspect = drift
    try:
        with pytest.raises(WindowsAuthorityError):
            recovery.qualify_personal_desktop_paper_staging_recovery()
    finally:
        monkeypatch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", False
        )
