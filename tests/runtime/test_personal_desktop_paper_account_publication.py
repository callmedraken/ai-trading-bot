"""PD1C real disposable filesystem effects with explicitly modeled Windows ACLs."""

import builtins
import inspect
import json
import os
import stat
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_bot.runtime import (
    personal_desktop_paper_account_publication as publication,
)
from trading_bot.runtime import (
    personal_desktop_paper_account_publication_native as native,
)
from trading_bot.runtime import personal_desktop_paper_account_security as security
from trading_bot.runtime.personal_desktop_paper_account_authority import (
    PersonalDesktopPaperAccountError,
    parse_personal_desktop_paper_account_anchor,
)
from trading_bot.runtime.personal_desktop_paper_account_provisioning import (
    prepare_personal_desktop_paper_account_bundle_for_test,
)
from trading_bot.runtime.personal_desktop_paper_account_read_authority import (
    ValidatedPersonalDesktopPaperAccount,
)
from trading_bot.runtime.personal_desktop_paper_account_token import (
    TradingTokenObservation,
)
from trading_bot.runtime.windows_authority import (
    AuthorityObjectError,
    AuthorityPathError,
    AuthorityPrincipalError,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_security import (
    AuthorityObjectKind,
    SecurityInspection,
    WindowsHandle,
)
from trading_bot.runtime.windows_authority_validation import (
    issue_validated_production_authority_for_test,
)

from .test_manual_paper_selected_c3_snapshot import selected_case as selected_case
from .test_personal_desktop_paper_account_provisioning import inputs as inputs

ADMIN = TradingTokenObservation(
    "S-1-5-21-1-2-3-1005", 1, False, True, ((security.ADMINISTRATORS_SID, 4),)
)
State = publication.PaperPublicationState
Status = publication.PaperPublicationStatus
Phase = publication.PaperPublicationPhase

# Python audit hooks cannot be removed. Keep the hook dormant outside this
# module's tests, including teardown, rather than influencing other PD1 suites.
_guard_active = []
_production_events = []


def _production_path_guard(event, args):
    if not _guard_active or event not in {
        "open",
        "os.mkdir",
        "os.remove",
        "os.rmdir",
        "os.rename",
        "os.scandir",
        "os.listdir",
        "os.chmod",
        "os.chown",
        "os.link",
        "os.symlink",
        "os.truncate",
    }:
        return
    for value in args:
        if isinstance(value, (str, bytes, Path)):
            text = os.fsdecode(value).replace("/", "\\").casefold()
            if text.startswith("\\\\?\\"):
                text = text[4:]
            if text.startswith(r"f:\aitradingbot"):
                _production_events.append((event, text))
                raise AssertionError(
                    "PD1C attempted a forbidden production filesystem call"
                )


sys.addaudithook(_production_path_guard)


@pytest.fixture(autouse=True)
def prohibit_production_effects(monkeypatch):
    assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    _guard_active.append(True)
    _production_events.clear()

    def forbidden_native(*args, **kwargs):
        raise AssertionError("PD1C tests must never construct a native filesystem API")

    monkeypatch.setattr(
        security.WindowsPaperReadNativeApi, "__init__", forbidden_native
    )
    try:
        yield
        assert _production_events == []
        assert security.PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED is False
    finally:
        _guard_active.clear()


@dataclass
class DisposableHandle:
    path: Path
    stream: object = None


class FilesystemPublicationApiForTest:
    """Ordinary OS create-new/write/fsync/rename; Windows security is a test model.

    Every call is confined to the fresh pytest root. It never calls a native
    production adapter or changes real ACLs. The parent validation remains in
    the public disposable entry point.
    """

    def __init__(self, root, genesis_id):
        self.root = publication.require_disposable_paper_publication_root_for_test(root)
        self.allowed = {
            Path(publication.publication_entry_path(root / tree, entry))
            for tree in ("Paper-v2", ".Paper-v2.provisioning")
            for entry in publication.paper_publication_layout(genesis_id)
        }
        self.calls = []
        self.policy = {}
        self.handles = []
        self.hook = lambda event, path: None
        self.observe_hook = lambda path, result: result
        self.read_hook = lambda path, result: result

    def event(self, event, path):
        path = Path(path)
        assert path in self.allowed
        assert path.is_relative_to(self.root)
        self.calls.append((event, path))
        self.hook(event, path)

    def _handle(self, path, stream=None):
        handle = DisposableHandle(Path(path), stream)
        self.handles.append(handle)
        return handle

    def occupied(self, path):
        self.event("occupied", path)
        try:
            Path(path).lstat()
        except FileNotFoundError:
            return False
        return True

    def create_directory(self, path):
        self.event("create-directory", path)
        Path(path).mkdir()  # No parents/exist_ok/merge behavior.
        self.event("created-directory", path)
        return self._handle(path)

    def create_file(self, path):
        self.event("create-file", path)
        return self._handle(path, Path(path).open("xb+"))

    def write(self, handle, payload):
        self.event("write", handle.path)
        assert handle.stream.write(payload) == len(payload)
        self.event("written", handle.path)

    def flush(self, handle):
        self.event("flush", handle.path)
        handle.stream.flush()
        os.fsync(handle.stream.fileno())
        self.event("flushed", handle.path)

    def apply_policy(self, handle, policy):
        self.event("acl", handle.path)
        info = handle.path.stat()
        self.policy[info.st_dev, info.st_ino] = policy

    def open(self, path, kind):
        self.event("open", path)
        info = Path(path).lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise AuthorityObjectError("test path is a reparse point")
        actual = (
            AuthorityObjectKind.DIRECTORY
            if stat.S_ISDIR(info.st_mode)
            else AuthorityObjectKind.FILE
        )
        if actual is not kind:
            raise AuthorityObjectError("test object kind differs from layout")
        return self._handle(
            path, Path(path).open("rb") if kind is AuthorityObjectKind.FILE else None
        )

    def close(self, handle):
        self.calls.append(("close", handle.path))
        if handle.stream:
            handle.stream.close()
        self.handles.remove(handle)

    def inspect(self, handle, path, kind):
        self.event("inspect", path)
        info = (
            os.fstat(handle.stream.fileno()) if handle.stream else handle.path.lstat()
        )
        identity = info.st_dev, info.st_ino
        policy = self.policy.get(identity)
        facts = SecurityInspection(
            str(path),
            str(handle.path),
            AuthorityObjectKind.DIRECTORY
            if stat.S_ISDIR(info.st_mode)
            else AuthorityObjectKind.FILE,
            security.ADMINISTRATORS_SID,
            True,
            policy.aces if policy else (),
            bool(getattr(info, "st_file_attributes", 0) & 0x400),
            self.root.anchor,
            "NTFS",
        )
        result = security.PaperObjectObservation(
            facts,
            identity,
            info.st_size if kind is AuthorityObjectKind.FILE else 0,
            info.st_nlink,
        )
        return self.observe_hook(Path(path), result)

    def read(self, handle, maximum):
        self.event("read", handle.path)
        handle.stream.seek(0)
        result = handle.stream.read(maximum + 1)
        if len(result) > maximum:
            raise AuthorityObjectError("test artifact byte bound exceeded")
        return self.read_hook(handle.path, result)

    def names(self, handle, path, maximum):
        self.event("names", path)
        with os.scandir(path) as entries:
            result = []
            for entry in entries:
                if len(result) >= maximum:
                    raise AuthorityObjectError("test inventory bound exceeded")
                result.append(entry.name)
        return tuple(result)

    def rename_no_clobber(self, staging, final):
        self.event("rename", staging)
        assert not self.handles
        assert Path(staging).parent == Path(final).parent == self.root
        # This harness intentionally uses the Windows os.rename contract;
        # POSIX rename may replace an empty destination and is not substituted.
        if os.name != "nt":
            raise AuthorityObjectError(
                "disposable rename requires Windows no-clobber semantics"
            )
        os.rename(staging, final)
        self.event("renamed", final)


@pytest.fixture
def case(inputs, tmp_path):
    root = tmp_path / "publication"
    root.mkdir()
    bundle = prepare_personal_desktop_paper_account_bundle_for_test(**inputs)
    anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    api = FilesystemPublicationApiForTest(root, anchor.genesis_checkpoint_id)
    args = dict(
        disposable_root=root,
        native_api_factory_for_test=lambda *_: api,
        administrator_for_test=ADMIN,
        bundle=bundle,
        **inputs,
    )
    return root, bundle, api, args


def publish(case):
    return publication.publish_personal_desktop_paper_account_for_test(**case[3])


def mutation_calls(api):
    return [
        (event, path)
        for event, path in api.calls
        if event
        in {"create-directory", "create-file", "write", "flush", "acl", "rename"}
    ]


@pytest.mark.parametrize(
    "final,staging,state",
    [
        (False, False, State.EMPTY),
        (False, True, State.STAGING_REQUIRES_REVIEW),
        (True, False, State.FINAL_REQUIRES_VALIDATION),
        (True, True, State.CONFLICT),
    ],
)
def test_pure_crash_classifier_never_performs_io(monkeypatch, final, staging, state):
    def forbidden(*args, **kwargs):
        raise AssertionError("classification must be pure")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(os, "stat", forbidden)
        assert (
            publication.classify_paper_publication_state(
                final_present=final, staging_present=staging
            )
            is state
        )


@pytest.mark.parametrize("value", [None, 0, 1, "false", (), object()])
def test_classifier_rejects_unproven_occupancy(value):
    with pytest.raises(PersonalDesktopPaperAccountError):
        publication.classify_paper_publication_state(
            final_present=value, staging_present=False
        )


def test_complete_disposable_publication_exact_layout_bytes_policies_and_order(case):
    root, bundle, api, _ = case
    result = publish(case)
    assert result.status is Status.PUBLISHED_AND_VERIFIED
    assert result.phase is Phase.COMPLETE
    assert result.state is State.FINAL_REQUIRES_VALIDATION
    assert result.staging_may_have_begun and result.rename_may_have_begun
    assert not isinstance(result, ValidatedPersonalDesktopPaperAccount)
    assert not (root / ".Paper-v2.provisioning").exists()
    final = root / "Paper-v2"
    anchor = parse_personal_desktop_paper_account_anchor(bundle.anchor_bytes)
    entries = publication.paper_publication_layout(anchor.genesis_checkpoint_id)
    assert {str(p.relative_to(final)) for p in final.rglob("*")} == {
        str(Path(*e.relative.split("\\"))) for e in entries if e.relative
    }
    assert (
        final / "personal-desktop-paper-account-authority.json"
    ).read_bytes() == bundle.anchor_bytes
    assert (
        next(final.glob("paper-account-genesis-*/*.json")).read_bytes()
        == bundle.genesis_bytes
    )
    assert not any(
        "manifest" in str(path) or "provisioning.json" in str(path)
        for path in final.rglob("*")
    )
    assert len(api.policy) == 6
    for entry in entries:
        path = Path(publication.publication_entry_path(final, entry))
        info = path.stat()
        assert api.policy[info.st_dev, info.st_ino] == security.paper_security_policy(
            entry.spec.role, anchor.approved_trading_sid
        )
    events = [event for event, _ in api.calls]
    assert events.count("rename") == 1
    assert events.count("write") == 2
    assert events.count("acl") == 6
    assert (
        events.index("flush")
        < events.index("acl")
        < events.index("read")
        < events.index("rename")
    )
    assert max(
        i
        for i, event in enumerate(events)
        if event in {"create-directory", "create-file"}
    ) < events.index("write")
    assert events.index("renamed") < max(
        i for i, event in enumerate(events) if event == "read"
    )
    assert not api.handles


@pytest.mark.parametrize(
    "final,staging,state",
    [
        (True, False, State.FINAL_REQUIRES_VALIDATION),
        (False, True, State.STAGING_REQUIRES_REVIEW),
        (True, True, State.CONFLICT),
    ],
)
@pytest.mark.parametrize("object_kind", ["directory", "file"])
def test_occupied_names_block_before_create_and_preserve_content(
    case, final, staging, state, object_kind
):
    root, _, api, _ = case
    for present, name in ((final, "Paper-v2"), (staging, ".Paper-v2.provisioning")):
        if present:
            path = root / name
            if object_kind == "directory":
                path.mkdir()
                path /= "retained"
            path.write_bytes(b"do not replace")
    result = publish(case)
    assert result.status is Status.BLOCKED and result.state is state
    assert result.phase is Phase.PREFLIGHT
    assert not result.staging_may_have_begun
    assert not mutation_calls(api)
    assert all(
        path.read_bytes() == b"do not replace"
        for path in root.rglob("*")
        if path.is_file()
    )


@pytest.mark.parametrize(
    "collision", ["root", "anchor", "genesis", "directory", "rename"]
)
def test_create_new_and_rename_collisions_never_replace_or_fallback(case, collision):
    root, _, api, _ = case
    target = None

    def collide(event, path):
        nonlocal target
        if target is not None:
            return
        match = (
            (
                collision == "root"
                and event == "create-directory"
                and path == root / ".Paper-v2.provisioning"
            )
            or (
                collision == "anchor"
                and event == "create-file"
                and path.name.startswith("personal")
            )
            or (
                collision == "genesis"
                and event == "create-file"
                and path.name.startswith("paper-account-checkpoint")
            )
            or (
                collision == "directory"
                and event == "create-directory"
                and path.name == "runtime"
            )
            or (collision == "rename" and event == "rename")
        )
        if match:
            target = root / "Paper-v2" if collision == "rename" else path
            if collision in {"root", "directory", "rename"}:
                target.mkdir()
                target /= "retained"
            target.write_bytes(b"original collision")

    api.hook = collide
    result = publish(case)
    assert result.status is Status.BLOCKED
    assert target.read_bytes() == b"original collision"
    assert result.state is (
        State.CONFLICT if collision == "rename" else State.STAGING_REQUIRES_REVIEW
    )
    assert {p.name for p in root.iterdir()} <= {"Paper-v2", ".Paper-v2.provisioning"}
    assert not api.handles


@pytest.mark.parametrize("destination_kind", ["empty-directory", "file"])
def test_rename_never_replaces_even_empty_destination(case, destination_kind):
    root, _, api, _ = case
    final = root / "Paper-v2"
    identity = []

    def collide(event, path):
        if event == "rename":
            if destination_kind == "empty-directory":
                final.mkdir()
            else:
                final.write_bytes(b"original file")
            identity.append(final.stat().st_ino)

    api.hook = collide
    result = publish(case)
    assert result.status is Status.BLOCKED and result.phase is Phase.RENAME
    assert result.state is State.CONFLICT
    assert final.stat().st_ino == identity[0]
    assert (
        list(final.iterdir()) == []
        if final.is_dir()
        else final.read_bytes() == b"original file"
    )
    assert (root / ".Paper-v2.provisioning").is_dir()


@pytest.mark.parametrize(
    "event,where,phase,state",
    [
        ("create-directory", "staging-root", Phase.STAGING_CREATE, State.EMPTY),
        (
            "created-directory",
            "staging-root",
            Phase.STAGING_CREATE,
            State.STAGING_REQUIRES_REVIEW,
        ),
        ("create-file", "anchor", Phase.CHILD_CREATE, State.STAGING_REQUIRES_REVIEW),
        ("write", "anchor", Phase.ANCHOR_WRITE, State.STAGING_REQUIRES_REVIEW),
        ("written", "genesis", Phase.GENESIS_WRITE, State.STAGING_REQUIRES_REVIEW),
        ("flush", "anchor", Phase.FLUSH, State.STAGING_REQUIRES_REVIEW),
        ("flushed", "genesis", Phase.FLUSH, State.STAGING_REQUIRES_REVIEW),
        ("acl", "staging-root", Phase.ACL, State.STAGING_REQUIRES_REVIEW),
        ("open", "staging-root", Phase.STAGED_VERIFY, State.STAGING_REQUIRES_REVIEW),
        ("rename", "staging-root", Phase.RENAME, State.STAGING_REQUIRES_REVIEW),
        ("renamed", "final-root", Phase.RENAME, State.FINAL_REQUIRES_VALIDATION),
        ("open", "final-root", Phase.FINAL_REOPEN, State.FINAL_REQUIRES_VALIDATION),
        ("read", "final-anchor", Phase.FINAL_VERIFY, State.FINAL_REQUIRES_VALIDATION),
    ],
)
def test_failures_preserve_durable_state_without_cleanup_or_retry(
    case, event, where, phase, state
):
    root, _, api, _ = case
    triggered = []

    def inject(current, path):
        locations = {
            "staging-root": path == root / ".Paper-v2.provisioning",
            "final-root": path == root / "Paper-v2",
            "anchor": path.name.startswith("personal"),
            "genesis": path.name.startswith("paper-account-checkpoint"),
            "final-anchor": path
            == root / "Paper-v2" / "personal-desktop-paper-account-authority.json",
        }
        if current == event and locations[where]:
            triggered.append(path)
            raise OSError("injected failure/response loss")

    api.hook = inject
    result = publish(case)
    assert result.status is Status.BLOCKED and result.phase is phase
    assert result.state is state and result.failure_type == "OSError"
    assert result.staging_may_have_begun
    assert result.rename_may_have_begun is (
        phase in {Phase.RENAME, Phase.FINAL_REOPEN, Phase.FINAL_VERIFY}
    )
    assert len(triggered) == 1
    assert (
        Counter(
            event
            for event, path in api.calls
            if path == root / ".Paper-v2.provisioning"
        )["create-directory"]
        == 1
    )
    assert not api.handles
    if state is not State.EMPTY:
        saved = {
            str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()
        }
        before = len(mutation_calls(api))
        api.hook = lambda *_: None
        second = publish(case)  # An explicit second call still cannot merge/retry.
        assert second.status is Status.BLOCKED and second.phase is Phase.PREFLIGHT
        assert len(mutation_calls(api)) == before
        assert saved == {
            str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()
        }


@pytest.mark.parametrize("when", ["staged", "final"])
@pytest.mark.parametrize(
    "corruption",
    [
        "anchor",
        "genesis",
        "noncanonical",
        "genesis-directory",
        "genesis-file",
        "unexpected",
        "object-type",
        "acl",
        "owner",
        "identity",
        "final-path",
        "reparse",
    ],
)
def test_exact_verification_rejects_corruption_and_drift(case, when, corruption):
    root, _, api, _ = case
    target = root / (".Paper-v2.provisioning" if when == "staged" else "Paper-v2")
    changed = []

    def corrupt(event, path):
        if event != "open" or path != target or changed:
            return
        changed.append(True)
        anchor = target / "personal-desktop-paper-account-authority.json"
        genesis_dir = next(target.glob("paper-account-genesis-*"))
        genesis = next(genesis_dir.glob("*.json"))
        if corruption == "anchor":
            anchor.write_bytes(b"invalid anchor\n")
        elif corruption == "genesis":
            genesis.write_bytes(b"invalid GENESIS\n")
        elif corruption == "noncanonical":
            anchor.write_bytes(
                json.dumps(json.loads(anchor.read_bytes()), indent=2).encode()
            )
        elif corruption == "genesis-directory":
            genesis_dir.rename(
                genesis_dir.with_name("paper-account-genesis-" + "0" * 36)
            )
        elif corruption == "genesis-file":
            genesis.rename(genesis.with_name("wrong-checkpoint.json"))
        elif corruption == "unexpected":
            (target / "provisioning-manifest.json").write_bytes(
                b"must not be installed"
            )
        elif corruption == "object-type":
            anchor.unlink()  # Deliberate test-only corruption, never publisher cleanup.
            anchor.mkdir()
        else:

            def drift(observed_path, observed):
                if observed_path != target:
                    return observed
                if corruption == "identity":
                    return replace(
                        observed,
                        identity=(observed.identity[0], observed.identity[1] + 1),
                    )
                change = {
                    "acl": dict(aces=()),
                    "owner": dict(owner_sid="S-1-5-18"),
                    "final-path": dict(final_path=str(target / "alias")),
                    "reparse": dict(is_reparse_point=True),
                }[corruption]
                return replace(observed, security=replace(observed.security, **change))

            api.observe_hook = drift

    api.hook = corrupt
    result = publish(case)
    assert result.status is Status.BLOCKED
    assert result.phase is (
        Phase.STAGED_VERIFY if when == "staged" else Phase.FINAL_VERIFY
    )
    assert result.state is (
        State.STAGING_REQUIRES_REVIEW
        if when == "staged"
        else State.FINAL_REQUIRES_VALIDATION
    )
    assert result.rename_may_have_begun is (when == "final")
    assert changed == [True]
    assert target.exists()
    assert not api.handles


@pytest.mark.parametrize("when", ["staged", "final"])
@pytest.mark.parametrize(
    "drift", ["reread", "pinned-identity", "reopen-identity", "inventory"]
)
def test_verification_repeats_pinned_and_named_observations(case, when, drift):
    root, _, api, _ = case
    target = root / (".Paper-v2.provisioning" if when == "staged" else "Paper-v2")
    reads = Counter()
    inspections = Counter()

    def reread(path, payload):
        reads[path] += 1
        if path.parent == target and drift == "reread" and reads[path] == 2:
            return payload + b"changed"
        return payload

    def observe(path, observed):
        inspections[path] += 1
        # Created root is observed once before staging verification starts.
        baseline = 1 if when == "staged" else 0
        count = 2 if drift == "pinned-identity" else 3
        if (
            path == target
            and drift in {"pinned-identity", "reopen-identity"}
            and inspections[path] == baseline + count
        ):
            return replace(
                observed, identity=(observed.identity[0], observed.identity[1] + 1)
            )
        return observed

    names = Counter()

    def inventory(event, path):
        if event == "names" and path == target:
            names[path] += 1
            if drift == "inventory" and names[path] == 2:
                (target / "unexpected").write_bytes(b"drift")

    api.read_hook, api.observe_hook, api.hook = reread, observe, inventory
    result = publish(case)
    assert result.status is Status.BLOCKED
    assert result.phase is (
        Phase.STAGED_VERIFY if when == "staged" else Phase.FINAL_VERIFY
    )
    assert not api.handles


@pytest.mark.parametrize(
    "field",
    [
        "anchor_sha256",
        "anchor_byte_length",
        "genesis_sha256",
        "genesis_byte_length",
        "machine_authority_id",
        "approved_trading_sid",
        "paper_account_id",
    ],
)
def test_bundle_drift_blocks_before_test_api_construction(case, field):
    _, bundle, api, args = case
    tree = json.loads(bundle.manifest_bytes)
    tree[field] = tree[field] + 1 if isinstance(tree[field], int) else "0" * 64
    changed = object.__new__(type(bundle))
    for name in ("anchor_bytes", "genesis_bytes", "manifest_bytes"):
        object.__setattr__(
            changed,
            name,
            (json.dumps(tree, sort_keys=True, separators=(",", ":")) + "\n").encode()
            if name == "manifest_bytes"
            else getattr(bundle, name),
        )
    with pytest.raises(PersonalDesktopPaperAccountError):
        publication.publish_personal_desktop_paper_account_for_test(
            **(args | {"bundle": changed})
        )
    assert not api.calls


@pytest.mark.parametrize(
    "field,value",
    [
        ("machine_authority_id", "33333333-3333-4333-8333-333333333333"),
        ("approved_account_sid", "S-1-5-21-1-2-3-1010"),
    ],
)
def test_bundle_requires_exact_contextual_c1_binding(case, field, value):
    _, _, api, args = case
    bootstrap = replace(args["bootstrap"], **{field: value})
    with pytest.raises(WindowsAuthorityError):
        publication.publish_personal_desktop_paper_account_for_test(
            **(args | {"bootstrap": bootstrap, "bootstrap_digest": bootstrap.digest})
        )
    assert not api.calls


def test_bundle_requires_exact_approved_cash_and_administrator_before_factory(case):
    _, _, api, args = case
    with pytest.raises(PersonalDesktopPaperAccountError):
        publication.publish_personal_desktop_paper_account_for_test(
            **(args | {"starting_cash": args["starting_cash"] + 1})
        )
    with pytest.raises(AuthorityPrincipalError):
        publication.publish_personal_desktop_paper_account_for_test(
            **(args | {"administrator_for_test": replace(ADMIN, elevated=False)})
        )
    assert not api.calls


@pytest.mark.parametrize(
    "change",
    [
        {"token_type": 2},
        {"token_type": True},
        {"thread_token_present": True},
        {"elevated": False},
        {"elevated": 1},
        {"groups": ()},
        {"groups": ((security.ADMINISTRATORS_SID, 0),)},
        {"groups": ((security.ADMINISTRATORS_SID, 0x14),)},
        {
            "groups": (
                (security.ADMINISTRATORS_SID, 4),
                (security.ADMINISTRATORS_SID, 4),
            )
        },
        {"groups": ((security.ADMINISTRATORS_SID, True),)},
    ],
)
def test_administrator_gate_rejects_invalid_tokens(change):
    with pytest.raises(AuthorityPrincipalError):
        publication.require_paper_publication_administrator(replace(ADMIN, **change))


def test_administrator_gate_accepts_admin_and_rejects_steady_state_trading():
    publication.require_paper_publication_administrator(ADMIN)
    with pytest.raises(AuthorityPrincipalError):
        publication.require_paper_publication_administrator(
            TradingTokenObservation("S-1-5-21-1-2-3-1009", 1, False, False, ())
        )


@pytest.mark.parametrize(
    "path",
    [
        r"F:\AITradingBot",
        r"F:\AITradingBot\Paper-v2",
        r"F:\AITradingBot\.Paper-v2.provisioning",
        r"F:\AITradingBot\Paper",
        r"F:\AITradingBot\.Paper.provisioning-v1",
        r"F:\AITradingBot\other",
        r"F:\AITradingBot-copy",
        r"F:\aitradingbot\paper-v2",
        r"\\?\F:\AITradingBot\Paper-v2",
        r"\\localhost\F$\AITradingBot\Paper-v2",
        r"F:\AI\temp\..\..\AITradingBot\Paper-v2",
        r"F:\AI\temp\stream:alias",
        r"F:\AITRAD~1\Paper-v2",
    ],
)
def test_disposable_roots_reject_production_and_alias_prefixes_before_io(
    monkeypatch, path
):
    def forbidden(*args, **kwargs):
        raise AssertionError("rejected root must not reach filesystem/native APIs")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", forbidden)
        with pytest.raises(AuthorityPathError):
            publication.require_disposable_paper_publication_root_for_test(Path(path))


def test_unrelated_content_and_reparse_root_fail_before_factory(case, monkeypatch):
    root, _, api, args = case
    (root / "unrelated").write_bytes(b"retained")
    with pytest.raises(AuthorityPathError):
        publication.publish_personal_desktop_paper_account_for_test(**args)
    assert not api.calls
    original = Path.lstat

    def reparse(path):
        result = original(path)
        if path == root:

            class ReparseStat:
                st_mode = result.st_mode
                st_file_attributes = 0x400

            return ReparseStat()
        return result

    monkeypatch.setattr(Path, "lstat", reparse)
    with pytest.raises(AuthorityPathError, match="reparse"):
        publication.publish_personal_desktop_paper_account_for_test(**args)
    assert not api.calls


@pytest.mark.parametrize("input_kind", ["none", "hostile", "test-authority"])
def test_production_false_gate_precedes_inputs_native_construction_and_every_effect(
    case, monkeypatch, input_kind
):
    _, bundle, _, args = case
    calls = []

    class Hostile:
        def __getattribute__(self, name):
            raise AssertionError("disabled publisher must not inspect caller input")

    authority = None if input_kind == "none" else Hostile()
    if input_kind == "test-authority":
        authority = issue_validated_production_authority_for_test(
            **{
                k: args[k]
                for k in ("bootstrap", "bootstrap_digest", "production_evidence")
            }
        )

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("disabled production publisher reached a dependency")

    monkeypatch.setattr(native, "WindowsPaperPublicationApi", forbidden)
    monkeypatch.setattr(publication, "require_paper_publication_inputs", forbidden)
    monkeypatch.setenv("PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED", "true")
    with pytest.raises(PersonalDesktopPaperAccountError, match="disabled"):
        publication.publish_personal_desktop_paper_account(
            authority=authority,
            bundle=bundle,
            selected_snapshot=args["selected_snapshot"],
            starting_cash=args["starting_cash"],
        )
    assert calls == []


def test_native_constructor_itself_remains_disabled():
    with pytest.raises(PersonalDesktopPaperAccountError, match="disabled"):
        native.WindowsPaperPublicationApi("not even parsed")


def test_production_admission_rejects_disposable_c1_without_native_mutator(case):
    _, bundle, api, args = case
    authority = issue_validated_production_authority_for_test(
        **{k: args[k] for k in ("bootstrap", "bootstrap_digest", "production_evidence")}
    )
    with pytest.raises(WindowsAuthorityError, match="non-production provenance"):
        publication.require_paper_publication_inputs(
            authority=authority,
            bundle=bundle,
            selected_snapshot=args["selected_snapshot"],
            starting_cash=args["starting_cash"],
        )
    assert not api.calls


def test_production_signature_has_no_root_api_or_enable_override():
    assert set(
        inspect.signature(publication.publish_personal_desktop_paper_account).parameters
    ) == {"authority", "bundle", "selected_snapshot", "starting_cash"}
    assert set(inspect.signature(native.WindowsPaperPublicationApi).parameters) == {
        "genesis_id"
    }
    for override in ("root", "destination", "native_api", "enabled", "test", "config"):
        with pytest.raises(TypeError):
            publication.publish_personal_desktop_paper_account(
                authority=None,
                bundle=None,
                selected_snapshot=None,
                starting_cash=None,
                **{override: True},
            )


def test_occupancy_read_failure_is_unknown_and_never_a_retry(case):
    _, _, api, _ = case

    def fail(event, path):
        if event == "occupied":
            raise PermissionError("unproven absence")

    api.hook = fail
    result = publish(case)
    assert result.status is Status.BLOCKED and result.state is None
    assert not result.staging_may_have_begun and not mutation_calls(api)


@pytest.mark.parametrize("when", ["staged", "final"])
@pytest.mark.parametrize("drift", ["parent-identity", "parent-reparse", "token"])
def test_parent_and_administrator_revalidation_before_and_after_commit(
    case, monkeypatch, when, drift
):
    root, _, api, args = case
    target = root / (".Paper-v2.provisioning" if when == "staged" else "Paper-v2")
    token = replace(ADMIN)
    args["administrator_for_test"] = token
    original = Path.lstat
    triggered = []

    def changed_stat(path):
        result = original(path)
        if path == root and triggered:

            class ChangedStat:
                st_mode = result.st_mode
                st_dev = result.st_dev
                st_ino = result.st_ino + (1 if drift == "parent-identity" else 0)
                st_file_attributes = 0x400 if drift == "parent-reparse" else 0

            return ChangedStat()
        return result

    monkeypatch.setattr(Path, "lstat", changed_stat)

    def inject(event, path):
        if event == "open" and path == target and not triggered:
            triggered.append(True)
            if drift == "token":
                object.__setattr__(token, "thread_token_present", True)

    api.hook = inject
    result = publish(case)
    assert result.status is Status.BLOCKED
    assert result.phase is (
        Phase.STAGED_VERIFY if when == "staged" else Phase.FINAL_VERIFY
    )
    assert result.rename_may_have_begun is (when == "final")
    assert target.exists() and not api.handles


@pytest.mark.parametrize("when", ["writes", "final"])
def test_close_failure_blocks_acceptance_without_cleanup_or_retry(case, when):
    root, _, api, _ = case
    close = api.close
    injected = []

    def fail_close(handle):
        close(handle)
        target = root / (".Paper-v2.provisioning" if when == "writes" else "Paper-v2")
        if handle.path == target and not injected:
            injected.append(True)
            raise OSError("close acknowledgement lost")

    api.close = fail_close
    result = publish(case)
    assert result.status is Status.BLOCKED
    assert result.phase is (
        Phase.CLOSE_WRITES if when == "writes" else Phase.FINAL_VERIFY
    )
    assert result.state is (
        State.STAGING_REQUIRES_REVIEW
        if when == "writes"
        else State.FINAL_REQUIRES_VALIDATION
    )
    assert injected == [True] and not api.handles


@pytest.mark.parametrize("succeeds", [True, False])
def test_native_close_acknowledgement_with_read_only_fake_binding(succeeds):
    # Exercise resource release without constructing a production adapter,
    # enabling the gate, or loading/calling a native library. This fake exposes
    # only CloseHandle, so no create/write/ACL/rename/delete call can occur.
    calls = []

    def close(value):
        calls.append(value)
        return int(succeeds)

    probe = SimpleNamespace(
        _kernel=SimpleNamespace(CloseHandle=close),
        _created={77: "disposable test handle"},
    )
    handle = WindowsHandle(77, close=False)
    if succeeds:
        native.WindowsPaperPublicationApi.close(probe, handle)
        assert handle.value == 0 and probe._created == {}
    else:
        with pytest.raises(AuthorityObjectError, match="close failed"):
            native.WindowsPaperPublicationApi.close(probe, handle)
        assert handle.value == 77 and 77 in probe._created
    assert calls == [77]
