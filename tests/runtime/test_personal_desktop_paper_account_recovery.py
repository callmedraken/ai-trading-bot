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
    monkeypatch.setattr(recovery, "WindowsPaperRecoveryFinalizeApi", forbidden)
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


# FR3A: the production entry point runs against memory only. Install every
# boundary before test-local enablement; the actual native adapter stays blocked.
FINAL = security.PERSONAL_DESKTOP_PAPER_V2_ROOT
FinalizeStatus = recovery.PaperStagingRecoveryFinalizeStatus
FinalizePhase = recovery.PaperStagingRecoveryFinalizePhase


@pytest.fixture
def finalize_case(case, monkeypatch):
    case.renames = 0
    case.before_move = lambda: None
    case.after_move = lambda: None
    case.events = []
    case.original_objects = tuple(
        (path, case.api.nodes[path].observation) for path in case.paths
    )

    class MemoryRename:
        def rename_no_clobber(self):
            case.renames += 1
            assert case.renames == 1
            # All six tree handles are closed, but BOTH original parent pins
            # survive. This models the real deny-DELETE sharing constraint.
            assert len(case.api.handles) == 2
            assert {
                n.observation.security.expected_path for n in case.api.handles.values()
            } == {"F:\\", PARENT}
            case.events.append("rename")
            case.before_move()
            assert FINAL not in case.api.nodes
            for path in case.paths:
                node = case.api.nodes.pop(path)
                final_path = FINAL + path[len(ROOT) :]
                node.observation = replace(
                    node.observation,
                    security=replace(
                        node.observation.security,
                        expected_path=final_path,
                        final_path=final_path,
                    ),
                )
                case.api.nodes[final_path] = node
            case.api.overrides[PARENT] = (
                NAMES[1],
                NAMES[2],
                "Authority",
                "runtime",
                "temp",
            )
            case.after_move()

    monkeypatch.setattr(recovery, "WindowsPaperRecoveryFinalizeApi", MemoryRename)
    monkeypatch.setattr(
        recovery, "qualify_personal_desktop_paper_staging_recovery", forbidden
    )
    verify = recovery._verify_recovery_tree

    def record_verify(session, paths, freeze, validation):
        case.events.append("verify:" + paths.root)
        return verify(session, paths, freeze, validation)

    monkeypatch.setattr(recovery, "_verify_recovery_tree", record_verify)
    # All C1/token/platform/read/rename boundaries are deterministic fakes now.
    with monkeypatch.context() as enabled:
        enabled.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", True
        )
        case.gates = enabled
        yield case
    assert security.PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED is True
    assert case.renames in {0, 1}


def assert_blocked(case, *, begun=False, phase=None):
    result = recovery.finalize_personal_desktop_paper_staging_recovery()
    assert result.status is FinalizeStatus.BLOCKED
    assert result.rename_may_have_begun is begun
    assert result.failure_type is not None
    assert result.paper_account_id is None
    assert case.renames == int(begun)
    if phase is not None:
        assert result.phase is phase
    return result


@pytest.mark.parametrize("value", [False, None, 0, 1, "True", object()])
def test_finalize_disabled_gate_is_first(case, monkeypatch, value):
    unexpected = []

    def boundary(*args, **kwargs):
        unexpected.append("called")
        forbidden()

    for name in (
        "require_production_paper_publication_freeze",
        "_observe_administrator",
        "_require_disarmed",
        "_WindowsRecoveryReadApi",
        "WindowsPaperRecoveryFinalizeApi",
    ):
        monkeypatch.setattr(recovery, name, boundary)
    monkeypatch.setattr(
        security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", value
    )
    result = recovery.finalize_personal_desktop_paper_staging_recovery()
    assert result.status is FinalizeStatus.BLOCKED
    assert result.phase is FinalizePhase.PREFLIGHT
    assert result.rename_may_have_begun is False
    assert result.state is None
    assert case.api.calls == []
    assert case.c1_calls == case.native_calls == 0

    assert unexpected == []
    assert result.failure_type == "PersonalDesktopPaperAccountError"


@pytest.mark.parametrize("value", [True, None, 0, 1, "False"])
def test_finalize_original_publisher_must_be_exactly_disarmed(
    finalize_case, monkeypatch, value
):
    with monkeypatch.context() as patch:
        patch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", value
        )
        assert_blocked(finalize_case, phase=FinalizePhase.PREFLIGHT)
    assert finalize_case.c1_calls == finalize_case.native_calls == 0


@pytest.mark.parametrize(
    "argument",
    [
        "path",
        "root",
        "qualification",
        "bundle",
        "freeze",
        "sid",
        "account_id",
        "manifest",
        "native_api",
        "c1_evidence",
        "enabled",
        "retry_token",
        "recovery_permit",
    ],
)
def test_finalize_accepts_no_caller_authority(case, argument):
    assert not inspect.signature(
        recovery.finalize_personal_desktop_paper_staging_recovery
    ).parameters
    with pytest.raises(TypeError):
        recovery.finalize_personal_desktop_paper_staging_recovery(
            **{argument: object()}
        )
    with pytest.raises(TypeError):
        recovery.finalize_personal_desktop_paper_staging_recovery(object())
    assert case.api.calls == []


def test_finalize_clean_memory_rename_preserves_all_six_objects(finalize_case):
    case = finalize_case
    result = recovery.finalize_personal_desktop_paper_staging_recovery()
    assert result.status is FinalizeStatus.FINALIZED_AND_VERIFIED
    assert result.phase is FinalizePhase.COMPLETE
    assert result.state is recovery.PaperPublicationState.FINAL_REQUIRES_VALIDATION
    assert result.rename_may_have_begun is True
    assert result.failure_type is None
    assert result.paper_account_id == case.freeze.paper_account_id
    assert case.events == ["verify:" + ROOT, "rename", "verify:" + FINAL]
    assert case.renames == 1
    assert ROOT not in case.api.nodes
    for path, observed in case.original_objects:
        final_path = FINAL + path[len(ROOT) :]
        now = case.api.nodes[final_path].observation
        assert now == replace(
            observed,
            security=replace(
                observed.security, expected_path=final_path, final_path=final_path
            ),
        )
    with pytest.raises(FrozenInstanceError):
        result.rename_may_have_begun = False
    assert not any(
        callable(getattr(result, name))
        for name in dir(result)
        if not name.startswith("_")
    )


@pytest.mark.parametrize(
    "present",
    [p for p in product((False, True), repeat=4) if p != (False, True, False, True)],
)
def test_finalize_every_bad_initial_occupancy(finalize_case, present):
    case = finalize_case
    case.api.overrides[PARENT] = tuple(
        name for name, yes in zip(NAMES, present, strict=True) if yes
    )
    assert_blocked(case, phase=FinalizePhase.PREFLIGHT)
    assert "verify:" + ROOT not in case.events


@pytest.mark.parametrize(
    "change", ["token", "impersonation", "primary", "c1", "freeze", "parent"]
)
def test_finalize_preflight_failures_never_rename(finalize_case, monkeypatch, change):
    case = finalize_case
    if change in {"token", "impersonation", "primary"}:
        case.token = replace(
            ADMIN,
            **{
                "token": {"elevated": False},
                "impersonation": {"thread_token_present": True},
                "primary": {"token_type": 2},
            }[change],
        )
    elif change == "c1":
        case.validation = replace(case.validation, production_evidence=None)
    elif change == "freeze":
        monkeypatch.setattr(
            recovery, "require_production_paper_publication_freeze", forbidden
        )
    else:
        node = case.api.nodes[PARENT]
        node.observation = replace(
            node.observation, security=replace(node.observation.security, aces=())
        )
    assert_blocked(case, phase=FinalizePhase.PREFLIGHT)


@pytest.mark.parametrize(
    "when,index,change",
    [
        (when, index, change)
        for when, index, change in product(
            ("staging", "final"),
            range(6),
            (
                "identity",
                "acl",
                "reparse",
                "kind",
                "owner",
                "metadata",
                "links",
                "content",
            ),
        )
        if not (
            when == "staging"
            and change in {"metadata", "links"}
            and index not in {1, 3}
        )
    ],
)
def test_finalize_complete_tree_verification(finalize_case, when, index, change):
    case = finalize_case

    def corrupt():
        path = case.paths[index]
        if when == "final":
            path = FINAL + path[len(ROOT) :]
        node = case.api.nodes[path]
        obs = node.observation
        if change == "identity":
            obs = replace(obs, identity=(7, 987) if when == "final" else (7, 0))
        elif change == "metadata":
            obs = replace(
                obs, byte_length=obs.byte_length + 1 if when == "final" else -1
            )
        elif change == "links":
            obs = replace(obs, links=2)
        elif change == "content":
            if node.payload is None:
                case.api.overrides[path] = (*case.api.names(None, path, 1024), "extra")
            else:
                node.payload += b" "
        else:
            updates = {
                "acl": {"aces": ()},
                "reparse": {"is_reparse_point": True},
                "kind": {
                    "kind": AuthorityObjectKind.FILE
                    if obs.security.kind is AuthorityObjectKind.DIRECTORY
                    else AuthorityObjectKind.DIRECTORY
                },
                "owner": {"owner_sid": case.freeze.approved_trading_sid},
            }
            obs = replace(obs, security=replace(obs.security, **updates[change]))
        node.observation = obs

    if when == "staging":
        corrupt()
    else:
        case.after_move = corrupt
    assert_blocked(
        case,
        begun=when == "final",
        phase=(
            FinalizePhase.FINAL_REOPEN
            if index == 0 and change in {"acl", "reparse", "kind", "owner"}
            else FinalizePhase.FINAL_VERIFY
        )
        if when == "final"
        else FinalizePhase.STAGING_VERIFY,
    )


@pytest.mark.parametrize(
    "change",
    [
        "recovery_gate",
        "publication_gate",
        "c1",
        "token",
        "freeze",
        "parent_identity",
        "parent_acl",
        "occupancy",
        "v1",
    ],
)
def test_finalize_commit_seam_drift(finalize_case, monkeypatch, change):
    case = finalize_case
    close = case.api.close
    fired = False

    def drift_after_staging_close(handle):
        nonlocal fired
        close(handle)
        if fired or "verify:" + ROOT not in case.events or len(case.api.handles) != 2:
            return
        fired = True
        if change == "recovery_gate":
            case.gates.setattr(
                security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", False
            )
        elif change == "publication_gate":
            monkeypatch.setattr(
                security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", True
            )
        elif change == "c1":
            case.validation = replace(case.validation, production_evidence=None)
        elif change == "token":
            case.token = replace(ADMIN, elevated=False)
        elif change == "freeze":
            case.freeze = replace(case.freeze, starting_cash=Decimal("1"))
        elif change.startswith("parent"):
            node = case.api.nodes[PARENT]
            node.observation = replace(
                node.observation,
                **(
                    {"identity": (7, 999)}
                    if change.endswith("identity")
                    else {"security": replace(node.observation.security, aces=())}
                ),
            )
        else:
            case.api.overrides[PARENT] = (
                (NAMES[1], NAMES[2], NAMES[3]) if change == "occupancy" else (NAMES[3],)
            )

    monkeypatch.setattr(case.api, "close", drift_after_staging_close)
    try:
        assert_blocked(case, phase=FinalizePhase.COMMIT_REVALIDATE)
        assert fired
    finally:
        monkeypatch.setattr(
            security, "PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", False
        )


@pytest.mark.parametrize("after_effect", [False, True])
@pytest.mark.parametrize("trust_lost", [False, True])
def test_finalize_rename_failure_and_response_loss_never_retry(
    finalize_case, after_effect, trust_lost
):
    case = finalize_case

    def fail():
        if trust_lost:
            case.validation = replace(case.validation, production_evidence=None)
        raise OSError("injected lost native response")

    if after_effect:
        case.after_move = fail
    else:
        case.before_move = fail
    result = assert_blocked(case, begun=True, phase=FinalizePhase.RENAME)
    expected = (
        recovery.PaperPublicationState.FINAL_REQUIRES_VALIDATION
        if after_effect
        else recovery.PaperPublicationState.STAGING_REQUIRES_REVIEW
    )
    assert result.state is (None if trust_lost else expected)
    assert "verify:" + FINAL not in case.events
    assert not any(call[0] == "open" and call[1] == FINAL for call in case.api.calls)


@pytest.mark.parametrize(
    "present",
    [p for p in product((False, True), repeat=4) if p != (False, True, True, False)],
)
def test_finalize_bad_postrename_occupancy_never_succeeds(finalize_case, present):
    case = finalize_case

    def drift():
        case.api.overrides[PARENT] = tuple(
            name for name, yes in zip(NAMES, present, strict=True) if yes
        )

    case.after_move = drift
    assert_blocked(case, begun=True, phase=FinalizePhase.FINAL_REOPEN)


@pytest.mark.parametrize("operation", ["open", "read", "inspect", "names"])
def test_finalize_reader_failure_is_blocked(finalize_case, monkeypatch, operation):
    monkeypatch.setattr(finalize_case.api, operation, forbidden)
    assert_blocked(finalize_case)


def test_finalize_final_reopen_failure(finalize_case, monkeypatch):
    case = finalize_case
    original = case.api.open

    def fail_final(path, kind):
        if path == FINAL:
            raise AuthorityObjectError("final reopen failed")
        return original(path, kind)

    monkeypatch.setattr(case.api, "open", fail_final)
    assert_blocked(case, begun=True, phase=FinalizePhase.FINAL_REOPEN)


@pytest.mark.parametrize("change", ["c1", "freeze", "parent", "gate", "manifest"])
def test_finalize_final_verification_drift(finalize_case, monkeypatch, change):
    case = finalize_case
    serialize = recovery.serialize_personal_desktop_paper_account_manifest

    def drift(node):
        if not case.renames:
            return
        if change == "c1":
            case.validation = replace(case.validation, production_evidence=None)
        elif change == "freeze":
            case.freeze = replace(case.freeze, starting_cash=Decimal("1"))
        elif change == "parent":
            parent = case.api.nodes[PARENT]
            parent.observation = replace(parent.observation, identity=(7, 999))
        elif change == "gate":
            case.gates.setattr(
                security, "PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED", False
            )

    case.api.on_read = drift
    if change == "manifest":
        monkeypatch.setattr(
            recovery,
            "serialize_personal_desktop_paper_account_manifest",
            lambda m: serialize(m) + (b" " if case.renames else b""),
        )
    assert_blocked(case, begun=True, phase=FinalizePhase.FINAL_VERIFY)


def test_final_resolver_is_fixed_and_does_not_admit_staging(case):
    paths = recovery._FinalRecoveryPaths()
    assert paths.object_spec(FINAL).role is security.PaperObjectRole.ROOT
    for path in (
        ROOT,
        PARENT + "\\" + NAMES[1],
        FINAL.lower(),
        FINAL + ".",
        FINAL + r"\runtime",
    ):
        with pytest.raises(AuthorityPathError):
            paths.object_spec(path)


@pytest.mark.parametrize("when", ["staging", "final", "parent"])
def test_finalize_close_failure_cannot_report_success(finalize_case, monkeypatch, when):
    case = finalize_case
    close = case.api.close
    failed = False

    def fail_close(handle):
        nonlocal failed
        close(handle)
        # Fail after the last tree-session handle closes, or after outer parent
        # close. Other handles are not leaked by the fake failure injection.
        target = (
            when == "staging"
            and not case.renames
            and "verify:" + ROOT in case.events
            or when == "final"
            and "verify:" + FINAL in case.events
        ) and len(case.api.handles) == 2
        if when == "parent":
            target = "verify:" + FINAL in case.events and not case.api.handles
        if target and not failed:
            failed = True
            raise AuthorityObjectError("injected close response failure")

    monkeypatch.setattr(case.api, "close", fail_close)
    result = assert_blocked(case, begun=when != "staging")
    assert failed
    if when == "parent":
        assert result.state is None


@pytest.mark.parametrize("when", ["staging", "final"])
def test_finalize_close_interval_reopen_detects_replacement(finalize_case, when):
    case = finalize_case
    target = (ROOT if when == "staging" else FINAL) + r"\runtime\paper-operations"
    fired = False

    def drift(path, count, node):
        nonlocal fired
        # First finish checks the held object, then the independently reopened
        # name. Swap only the name, leaving the held object intact.
        if path == target and count == 2:
            fired = True
            case.api.nodes[path] = replace(
                node, observation=replace(node.observation, identity=(7, 999))
            )

    case.api.on_inspect = drift
    assert_blocked(case, begun=when == "final")
    assert fired


@pytest.mark.parametrize("change", ["c1", "freeze", "parent"])
def test_finalize_response_loss_with_untrusted_state_does_not_probe_names(
    finalize_case, change
):
    case = finalize_case
    stop_at = None

    def lost():
        nonlocal stop_at
        stop_at = len(case.api.calls)
        if change == "c1":
            case.validation = replace(case.validation, production_evidence=None)
        elif change == "freeze":
            case.freeze = replace(case.freeze, starting_cash=Decimal("1"))
        else:
            node = case.api.nodes[PARENT]
            node.observation = replace(node.observation, identity=(7, 999))
        raise OSError("lost native response and trust")

    case.after_move = lost
    result = assert_blocked(case, begun=True)
    assert result.state is None
    assert not any(call[0] == "names" for call in case.api.calls[stop_at:])


def test_finalize_c1_precedes_freeze_and_both_precede_native(
    finalize_case, monkeypatch
):
    ordered = []
    c1 = recovery.validate_installed_authority_complete
    freeze = recovery.require_production_paper_publication_freeze
    reader = recovery._WindowsRecoveryReadApi

    def observe_c1():
        ordered.append("c1")
        return c1()

    def observe_freeze():
        ordered.append("freeze")
        return freeze()

    def construct_reader(paths):
        ordered.append("read")
        return reader(paths)

    monkeypatch.setattr(recovery, "validate_installed_authority_complete", observe_c1)
    monkeypatch.setattr(
        recovery, "require_production_paper_publication_freeze", observe_freeze
    )
    monkeypatch.setattr(recovery, "_WindowsRecoveryReadApi", construct_reader)
    result = recovery.finalize_personal_desktop_paper_staging_recovery()
    assert result.status is FinalizeStatus.FINALIZED_AND_VERIFIED
    assert ordered[:3] == ["c1", "freeze", "read"]
