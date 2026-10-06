"""133-H fake-edge tests; production namespace/native effects are unreachable."""

import ast
import ctypes
import hashlib
import io
import json
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.review_paper import unattended_host_identity as identity
from trading_bot.review_paper import unattended_publication as publication
from trading_bot.review_paper import unattended_publication_windows as native
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import ReviewPaperActivation
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.risk import RiskLimits
from trading_bot.robinhood_execute_qualification_verifier import (
    qualification_fingerprint,
    read_qualification_store,
)

SECRET = "sentinel-secret-never-diagnostic"
AT = datetime(2026, 10, 6, 12, tzinfo=UTC)


def envelope(activation, binding):
    return publication.canonical(
        {
            "schema": publication.MATERIAL_SCHEMA,
            "activation_json": activation.to_json(),
            "host_binding_json": binding.to_json(),
        }
    )


class FakePublication:
    def __init__(self):
        self.events = []
        self.failure = None
        self.facts = {"target": publication.TARGET_HEAD, "administrator": "approved"}
        self.armed = False

    def step(self, event):
        self.events.append(event)
        if self.failure == event:
            raise RuntimeError(SECRET)

    @contextmanager
    def parent_guard(self):
        self.step("parent")
        yield

    def observe_absent(self, runtime):
        self.step("observe")
        if identity.HOST_ROOT.exists():
            raise ValueError(SECRET)
        return self.facts.copy()

    def arm_once(self, reviewed, authorization):
        self.step("arm")
        assert authorization == "AUTHORIZE Q133-2 " + reviewed
        self.armed = True

    def create_root_once(self):
        assert self.armed
        identity.HOST_ROOT.mkdir()
        self.step("root")

    def initialize_paper(self, activation):
        ReviewPaperStore(identity.PAPER_PATH, starting_cash=activation.starting_cash)
        self.step("paper")

    def admit_ready(self, activation):
        UnattendedStateStore(identity.STATE_PATH).admit(activation)
        self.step("state")

    def publish_once(self, name, raw):
        with (identity.HOST_ROOT / name).open("xb") as stream:
            stream.write(raw)
        self.step(name)

    def seal_files(self):
        self.step("seal")

    def admit_trading_root(self):
        self.step("trading")

    @contextmanager
    def pin_complete(self):
        self.step("verify")
        yield self

    def names(self):
        return frozenset(item.name for item in identity.HOST_ROOT.iterdir())

    def read(self, name):
        return (identity.HOST_ROOT / name).read_bytes()

    def finish(self):
        self.step("finish")


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / "Arch133"
    for name, value in {
        "HOST_ROOT": root,
        "PAPER_PATH": root / "paper.sqlite",
        "STATE_PATH": root / "wake.sqlite",
        "ACTIVATION_PATH": root / "activation.json",
        "BINDING_PATH": root / "host-binding.json",
    }.items():
        monkeypatch.setattr(identity, name, value)
    # Test-only schema fixture uses accepted store; planning itself writes nothing.
    before = tmp_path / "reference.sqlite"
    ReviewPaperStore(before, starting_cash=Decimal("23456.78"))
    fingerprint = qualification_fingerprint(*read_qualification_store(before))["sha256"]
    runtime = identity.HostRuntimeIdentity(
        publication.TARGET_HEAD,
        publication.TARGET_TREE,
        identity.PRODUCTION_PYTHON_SHA256,
        identity.PRODUCTION_PYTHON_VERSION,
        "b" * 64,
    )
    activation = ReviewPaperActivation(
        source_head=publication.TARGET_HEAD,
        source_tree=publication.TARGET_TREE,
        deployment_identity=runtime.deployment_identity,
        target_session_date=date(2026, 10, 6),
        proposal=TradeProposal(
            proposal_id=UUID(int=17),
            symbol=Symbol("VTI"),
            side=OrderSide.BUY,
            desired_quantity=Decimal("2.5"),
            reason="externally reviewed | : 雪",
            confidence=Decimal("0.83"),
            created_at=AT,
        ),
        risk_limits=RiskLimits(),
        new_trading_enabled=False,
        store_identity=UUID(int=23),
        store_path=str(identity.PAPER_PATH),
        starting_cash=Decimal("23456.78"),
        opening_buffer=timedelta(minutes=7),
        closing_buffer=timedelta(minutes=12),
        max_quote_age=timedelta(seconds=37),
        slippage_basis_points=Decimal("2.3"),
        commission=Decimal("0.27"),
        local_order_id=UUID(int=29),
        created_at=AT,
    )
    binding = identity.HostBinding(
        runtime,
        hashlib.sha256(activation.to_json().encode()).hexdigest(),
        activation.store_identity,
        fingerprint,
        AT + timedelta(days=1),
    )
    raw = envelope(activation, binding)
    material = publication.parse_publication_material(raw)
    backend = FakePublication()
    plan = publication._plan(material, backend)
    backend.events.clear()
    return SimpleNamespace(
        activation=activation,
        binding=binding,
        raw=raw,
        material=material,
        backend=backend,
        plan=plan,
    )


def execute(case, **changes):
    reviewed = changes.get("reviewed", case.plan["plan_sha256"])
    return publication._execute_once(
        changes.get("material", case.material),
        reviewed,
        changes.get("authorization", "AUTHORIZE Q133-2 " + reviewed),
        case.backend,
    )


def test_complete_plan_is_bounded_semantic_material_without_writes(case):
    assert not identity.HOST_ROOT.exists()
    assert case.plan["activation"] == json.loads(case.activation.to_json())
    assert case.plan["host_binding"] == json.loads(case.binding.to_json())
    assert case.plan["activation"]["proposal"]["symbol"] == "VTI"
    assert len(publication.canonical(case.plan)) < 65536
    assert case.plan["scheduler"]["installation_authorized"] is False
    for name in (
        "oauth_reads",
        "provider_calls",
        "scheduler_reads",
        "scheduler_writes",
        "broker_effects",
        "publication_writes",
    ):
        assert case.plan[name] == 0


def test_success_reopens_bytes_stores_and_exact_ready_revision_zero(case):
    result = execute(case)
    assert result["status"] == "PASS"
    assert (result["state"], result["revision"]) == ("READY", 0)
    assert result["paper_predecessor_sha256"] == case.binding.paper_predecessor_sha256
    assert result["store_identity"] == str(case.activation.store_identity)
    assert identity.ACTIVATION_PATH.read_bytes() == case.activation.to_json().encode()
    assert identity.BINDING_PATH.read_bytes() == case.binding.to_json().encode()
    assert (
        frozenset(p.name for p in identity.HOST_ROOT.iterdir())
        == publication.FINAL_NAMES
    )
    assert case.backend.events.count("paper") == case.backend.events.count("state") == 1
    assert case.backend.events.count("verify") == 2
    assert (
        publication.verify_publication(case.material, case.backend)["state_fingerprint"]
        == result["state_fingerprint"]
    )


@pytest.mark.parametrize(
    "step",
    [
        "parent",
        "observe",
        "arm",
        "root",
        "paper",
        "state",
        "activation.json",
        "host-binding.json",
        "seal",
        "verify",
        "trading",
        "finish",
    ],
)
def test_interruption_each_publication_step_no_compensation_or_retry(case, step):
    case.backend.failure = step
    with pytest.raises(publication.PublicationError) as error:
        execute(case)
    assert SECRET not in str(error.value)
    if identity.HOST_ROOT.exists():
        before = {p.name: p.read_bytes() for p in identity.HOST_ROOT.iterdir()}
        case.backend.failure = None
        case.backend.events.clear()
        with pytest.raises(publication.PublicationError):
            execute(case)
        assert {p.name: p.read_bytes() for p in identity.HOST_ROOT.iterdir()} == before
        assert not set(case.backend.events) & {
            "arm",
            "root",
            "paper",
            "state",
            "trading",
        }


@pytest.mark.parametrize(
    "partial",
    [
        None,
        "paper.sqlite",
        "wake.sqlite",
        "activation.json",
        "host-binding.json",
        "operator-evidence.json",
        "no-pycache",
    ],
)
def test_existing_or_partial_namespace_blocks_without_mutation(case, partial):
    identity.HOST_ROOT.mkdir()
    if partial:
        (identity.HOST_ROOT / partial).write_bytes(b"conflict")
    with pytest.raises(publication.PublicationError):
        execute(case)
    assert case.backend.events == ["parent", "observe"]


@pytest.mark.parametrize(
    "change",
    [
        "head",
        "tree",
        "python_sha256",
        "python_version",
        "deployment",
        "store",
        "path",
        "activation_sha256",
        "oauth",
    ],
)
def test_material_binding_mismatch(case, change):
    activation, binding = case.activation, case.binding
    if change in {"head", "tree", "python_sha256", "python_version"}:
        key = "source_" + change if change in {"head", "tree"} else change
        value = (
            "3.14.2"
            if key == "python_version"
            else "c" * (40 if change in {"head", "tree"} else 64)
        )
        binding = replace(binding, runtime=replace(binding.runtime, **{key: value}))
    elif change == "store":
        binding = replace(binding, store_identity=UUID(int=99))
    elif change == "activation_sha256":
        binding = replace(binding, activation_sha256="d" * 64)
    elif change == "oauth":
        binding = replace(binding, oauth_valid_until=AT)
    else:
        activation = replace(
            activation,
            **{
                "deployment_identity" if change == "deployment" else "store_path": "a"
                * 64
                if change == "deployment"
                else r"F:\wrong.sqlite"
            },
        )
    with pytest.raises(publication.PublicationError):
        publication.parse_publication_material(envelope(activation, binding))
    assert not identity.HOST_ROOT.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "newline",
        "indent",
        "duplicate",
        "unknown",
        "inner_space",
        "inner_duplicate",
        "utf8_bom",
        "oversize",
        "bad_type",
    ],
)
def test_malformed_noncanonical_changed_bytes_rejected(case, mutation):
    data = json.loads(case.raw)
    if mutation == "newline":
        raw = case.raw + b"\n"
    elif mutation == "indent":
        raw = json.dumps(data, indent=2).encode()
    elif mutation == "duplicate":
        raw = (
            b'{"schema":"' + publication.MATERIAL_SCHEMA.encode() + b'",' + case.raw[1:]
        )
    elif mutation == "utf8_bom":
        raw = b"\xef\xbb\xbf" + case.raw
    elif mutation == "oversize":
        raw = b" " * (publication.MAX_MATERIAL_BYTES + 1)
    else:
        if mutation == "unknown":
            data["token"] = SECRET
        elif mutation == "inner_space":
            data["activation_json"] += " "
        elif mutation == "inner_duplicate":
            data["host_binding_json"] = (
                '{"schema":"bad",' + data["host_binding_json"][1:]
            )
        else:
            data["activation_json"] = {}
        raw = publication.canonical(data)
    with pytest.raises(publication.PublicationError) as error:
        publication.parse_publication_material(raw)
    assert SECRET not in str(error.value)


@pytest.mark.parametrize(
    "kind", ["fingerprint", "authorization", "host_facts", "binding_bytes"]
)
def test_exact_reviewed_plan_required_before_first_mutation(case, kind):
    kwargs = {}
    if kind == "fingerprint":
        kwargs["reviewed"] = "0" * 64
    elif kind == "authorization":
        kwargs["authorization"] = SECRET
    elif kind == "host_facts":
        case.backend.facts["administrator"] = "changed"
    else:
        binding = replace(case.binding, oauth_valid_until=AT + timedelta(days=2))
        kwargs["material"] = publication.parse_publication_material(
            envelope(case.activation, binding)
        )
    with pytest.raises(publication.PublicationError):
        execute(case, **kwargs)
    assert not identity.HOST_ROOT.exists()


@pytest.mark.parametrize(
    "conflict",
    [
        "activation",
        "binding",
        "extra",
        "paper_cash",
        "paper_fingerprint",
        "state_revision",
        "state_material",
    ],
)
def test_independent_verifier_rejects_conflicting_publications(case, conflict):
    execute(case)
    if conflict == "activation":
        identity.ACTIVATION_PATH.write_bytes(case.activation.to_json().encode() + b"\n")
    elif conflict == "binding":
        identity.BINDING_PATH.write_bytes(b"{}")
    elif conflict == "extra":
        (identity.HOST_ROOT / "operator-evidence.json").write_bytes(b"{}")
    elif conflict == "paper_fingerprint":
        case.material = replace(
            case.material,
            binding=replace(case.binding, paper_predecessor_sha256="f" * 64),
        )
    else:
        import sqlite3

        path = identity.PAPER_PATH if conflict == "paper_cash" else identity.STATE_PATH
        with sqlite3.connect(path) as connection:
            if conflict == "paper_cash":
                connection.execute(
                    "UPDATE metadata SET value='1' WHERE key='starting_cash'"
                )
            elif conflict == "state_revision":
                connection.execute("UPDATE wakes SET revision=1")
            else:
                connection.execute("UPDATE activations SET activation_json='{}'")
    with pytest.raises((publication.PublicationError, ValueError)):
        publication.verify_publication(case.material, case.backend)


def test_no_clobber_exact_file(case):
    identity.HOST_ROOT.mkdir()
    identity.ACTIVATION_PATH.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        case.backend.publish_once("activation.json", b"replacement")
    assert identity.ACTIVATION_PATH.read_bytes() == b"existing"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--help"],
        ["execute-once", "--material-file", "-"],
        ["plan", "--material-file", "-", "--activation", SECRET],
        ["plan", "--material-file", "-", "--reviewed-plan-sha256", "a" * 64],
    ],
)
def test_cli_invalid_arguments_or_redirected_execute_sanitized(
    argv, monkeypatch, capsys
):
    monkeypatch.setattr(sys, "stdin", io.StringIO(SECRET))
    assert publication.main(argv) == 3
    captured = capsys.readouterr()
    assert SECRET not in captured.err + captured.out
    assert not captured.out


def test_plan_cli_file_boundary_no_execute(case, tmp_path, monkeypatch, capsys):
    path = tmp_path / "material.json"
    path.write_bytes(case.raw)
    monkeypatch.setattr(
        publication,
        "plan_publication",
        lambda raw: case.plan if raw == case.raw else pytest.fail(),
    )
    monkeypatch.setattr(
        publication, "execute_publication", lambda *args: pytest.fail("execute reached")
    )
    assert publication.main(["plan", "--material-file", str(path)]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(
        publication.canonical(case.plan)
    )


def test_native_roles_immutable_files_and_database_mutability():
    for name in ("activation.json", "host-binding.json"):
        assert native.publication_policy(name).aces[-1].access_mask == 0x120089
    for name in ("paper.sqlite", "wake.sqlite"):
        mask = native.publication_policy(name).aces[-1].access_mask
        assert mask & 2 and not mask & (0x10000 | 0x40000 | 0x80000)
    root = native.publication_policy("root")
    effective = root.aces[2].access_mask
    assert effective & 2 and not effective & (0x40 | 0x10000 | 0x40000 | 0x80000)
    assert all(ace.ace_flags == 9 for ace in root.aces[3:])
    with pytest.raises(publication.PublicationError):
        native.publication_policy("arbitrary")


@pytest.mark.parametrize("sid", [identity.TRADING_SID, native.security.SYSTEM_SID])
def test_native_wrong_principal_before_parent_access(monkeypatch, sid):
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    monkeypatch.setattr(native, "require_administrator_token", lambda: None)
    monkeypatch.setattr(native, "resolve_current_token_sid", lambda: sid)
    with pytest.raises(publication.PublicationError), backend.parent_guard():
        pytest.fail("unauthorized principal admitted")


def test_native_nonelevated_rejected_before_parent(monkeypatch):
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    monkeypatch.setattr(
        native,
        "require_administrator_token",
        lambda: (_ for _ in ()).throw(ValueError(SECRET)),
    )
    with pytest.raises(ValueError), backend.parent_guard():
        pytest.fail("nonelevated admitted")


def test_no_oauth_provider_scheduler_broker_reachability():
    sources = [Path(publication.__file__), Path(native.__file__)]
    forbidden = {
        "WindowsOAuthStorage",
        "RobinhoodMCPClient",
        "run_unattended_host",
        "execute_one_unattended_review_paper_wake",
        "RegisterTaskDefinition",
        "schtasks",
        "place_equity_order",
        "cancel_equity_order",
        "TradeProposal",
        "uuid4",
        "sleep",
    }
    for path in sources:
        tree = ast.parse(path.read_text())
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert not forbidden & (names | attributes)
    plan = next(
        node
        for node in ast.parse(Path(publication.__file__).read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "_plan"
    )
    assert not {
        node.attr for node in ast.walk(plan) if isinstance(node, ast.Attribute)
    } & {
        "create_root_once",
        "initialize_paper",
        "admit_ready",
        "publish_once",
        "admit_trading_root",
        "arm_once",
    }


@pytest.mark.parametrize(
    "change", ["branch", "head", "tree", "origin", "dirty", "root"]
)
def test_native_source_observation_rejects_drift(case, tmp_path, change):
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    root = tmp_path
    values = {
        ("rev-parse", "--show-toplevel"): str(root),
        ("branch", "--show-current"): identity.SOURCE_BRANCH,
        ("rev-parse", "HEAD"): publication.TARGET_HEAD,
        ("rev-parse", "HEAD^{tree}"): publication.TARGET_TREE,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
        (
            "remote",
            "get-url",
            "origin",
        ): "https://github.com/callmedraken/ai-trading-bot.git",
    }
    key = {
        "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"),
        "tree": ("rev-parse", "HEAD^{tree}"),
        "origin": ("remote", "get-url", "origin"),
        "dirty": ("status", "--porcelain=v1", "--untracked-files=all"),
        "root": ("rev-parse", "--show-toplevel"),
    }[change]
    values[key] = str(root.parent) if change == "root" else SECRET
    backend._git = lambda root, *args: values[args]
    with pytest.raises(publication.PublicationError):
        backend._source(
            root,
            identity.SOURCE_BRANCH,
            publication.TARGET_HEAD,
            publication.TARGET_TREE,
        )


@pytest.mark.parametrize(
    "change",
    [
        "platform",
        "isolated",
        "bytecode",
        "executable",
        "version",
        "launcher",
        "source_location",
        "runtime_head",
        "runtime_tree",
        "runtime_version",
        "runtime_hash",
    ],
)
def test_native_runtime_observation_rejects_before_opening_runtime(
    case, tmp_path, monkeypatch, change
):
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    backend.finish = lambda: None
    backend._absent = lambda path: None
    executable = tmp_path / "python.exe"
    launcher = tmp_path / "launcher.py"
    executable.write_bytes(b"fixture")
    launcher.write_bytes(b"fixture")
    monkeypatch.setattr(identity, "PRODUCTION_PYTHON", executable)
    monkeypatch.setattr(native, "PUBLISHER_LAUNCHER", launcher)
    monkeypatch.setattr(
        native, "PUBLISHER_ROOT", Path(native.__file__).resolve().parents[3]
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=True))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "argv", [str(launcher)])
    monkeypatch.setattr(sys, "version_info", (3, 14, 3))
    runtime = case.binding.runtime
    if change == "platform":
        monkeypatch.setattr(sys, "platform", "linux")
    elif change == "isolated":
        monkeypatch.setattr(sys, "flags", SimpleNamespace(isolated=False))
    elif change == "bytecode":
        monkeypatch.setattr(sys, "dont_write_bytecode", False)
    elif change == "executable":
        monkeypatch.setattr(sys, "executable", str(launcher))
    elif change == "version":
        monkeypatch.setattr(sys, "version_info", (3, 14, 2))
    elif change == "launcher":
        monkeypatch.setattr(sys, "argv", [str(executable)])
    elif change == "source_location":
        monkeypatch.setattr(native, "PUBLISHER_ROOT", tmp_path)
    else:
        field = {
            "runtime_head": "source_head",
            "runtime_tree": "source_tree",
            "runtime_version": "python_version",
            "runtime_hash": "python_sha256",
        }[change]
        runtime = replace(
            runtime,
            **{
                field: "3.14.2"
                if field == "python_version"
                else "0" * (40 if field.startswith("source") else 64)
            },
        )
    backend.api = SimpleNamespace(
        open=lambda *args: pytest.fail("runtime open reached")
    )
    with pytest.raises(publication.PublicationError):
        backend.observe_absent(runtime)


@pytest.mark.parametrize("error", [2, 3, 5, 32])
def test_native_absence_requires_exact_child_not_found(case, monkeypatch, error):
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    backend.kernel = object()
    monkeypatch.setattr(native, "_bind", lambda *args: lambda path: 0xFFFFFFFF)
    monkeypatch.setattr(native.ctypes, "get_last_error", lambda: error)
    if error == 2:
        backend._absent(identity.HOST_ROOT)
    else:
        with pytest.raises(publication.PublicationError):
            backend._absent(identity.HOST_ROOT)


@pytest.mark.parametrize(
    "failure",
    [None, "write", "short_write", "flush", "inspect", "read", "close", "rename"],
)
def test_native_file_write_flush_close_and_no_clobber_one_attempt(
    case, monkeypatch, failure
):
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    backend.kernel = object()
    backend._published = set()
    backend._require_new = lambda name: identity.HOST_ROOT / name
    calls = []

    class Handle:
        value = 123

        def close(self):
            calls.append("close")
            if failure == "close":
                raise ValueError(SECRET)

    backend._open_mutable = lambda path, **kwargs: Handle()

    def read(handle, maximum):
        calls.append("read")
        return b"bad" if failure == "read" else b"canonical"

    backend.api = SimpleNamespace(
        read=read, inspect=lambda *args: SimpleNamespace(security=native.ADMIN_POLICY)
    )
    monkeypatch.setattr(
        native,
        "require_security_policy",
        lambda *args: (
            (_ for _ in ()).throw(ValueError(SECRET)) if failure == "inspect" else None
        ),
    )

    def bind(kernel, name, *args):
        def invoke(*values):
            calls.append(name)
            if name == "WriteFile":
                values[3]._obj.value = (
                    1 if failure == "short_write" else len(b"canonical")
                )
                return failure != "write"
            if name == "MoveFileExW":
                assert values == (
                    str(identity.HOST_ROOT / ".activation.json.pending"),
                    str(identity.ACTIVATION_PATH),
                    8,
                )
                assert calls.index("close") < calls.index(name)
                return failure != "rename"
            return failure != "flush"

        return invoke

    monkeypatch.setattr(native, "_bind", bind)
    if failure:
        with pytest.raises((publication.PublicationError, ValueError)):
            backend.publish_once("activation.json", b"canonical")
    else:
        backend.publish_once("activation.json", b"canonical")
        assert calls == [
            "WriteFile",
            "FlushFileBuffers",
            "read",
            "close",
            "MoveFileExW",
        ]
    before = calls.copy()
    with pytest.raises(publication.PublicationError):
        backend.publish_once("activation.json", b"canonical")
    assert calls == before


@pytest.mark.parametrize("authorized", [False, True])
def test_native_root_attempt_gate_consumed_before_native_creation(
    case, monkeypatch, authorized
):
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    backend.kernel = object()
    backend._armed, backend._attempted = authorized, False
    backend.finish = lambda: None
    backend._absent = lambda path: None
    monkeypatch.setattr(
        native,
        "build_security_attributes",
        lambda policy: pytest.fail("unexpected native creation"),
    )
    if authorized:
        backend._absent = lambda path: (_ for _ in ()).throw(ValueError(SECRET))
        with pytest.raises(ValueError):
            backend.create_root_once()
        assert backend._attempted
    with pytest.raises(publication.PublicationError):
        backend.create_root_once()


@pytest.mark.parametrize(
    "failure",
    [None, "security", "hardlink", "oversize", "extra", "held_drift", "reopen_drift"],
)
def test_native_independent_pinned_reopen_verification(case, failure):
    from trading_bot.runtime.windows_authority_security import SecurityInspection

    calls = []
    opens = {}
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    backend._trading_root = True
    backend.finish = lambda: calls.append("parent_finish")

    def open_object(path, kind):
        opens[path] = opens.get(path, 0) + 1
        return SimpleNamespace(
            path=path, generation=opens[path], close=lambda: calls.append("close")
        )

    def inspect(handle, path, kind):
        name = "root" if path == str(identity.HOST_ROOT) else Path(path).name
        policy = native.publication_policy(name)
        security = SecurityInspection(
            path,
            path,
            kind,
            policy.owner_sid,
            True,
            policy.aces,
            failure == "security",
            "F:\\",
            "NTFS",
        )
        identity_id = 42
        if failure == "reopen_drift" and handle.generation > 1:
            identity_id = 99
        if failure == "held_drift" and calls.count("inventory") > 0:
            identity_id = 99
        return native.security.PaperObjectObservation(
            security,
            (1, identity_id),
            20 * 1024 * 1024 if failure == "oversize" else 100,
            2 if failure == "hardlink" else 1,
        )

    def names(*args):
        calls.append("inventory")
        return tuple(
            publication.FINAL_NAMES | ({"no-pycache"} if failure == "extra" else set())
        )

    backend.api = SimpleNamespace(
        open=open_object,
        inspect=inspect,
        close=lambda handle: handle.close(),
        names=names,
    )
    if failure:
        with pytest.raises(
            (publication.PublicationError, native.security.AuthoritySecurityError)
        ):
            with native.CompletePublication(backend) as pinned:
                pinned.finish()
    else:
        with native.CompletePublication(backend) as pinned:
            pinned.finish()
        assert len(opens) == 5 and all(count == 2 for count in opens.values())
        assert calls.count("close") == 10


@pytest.mark.parametrize("wrong_trading", [False, True])
def test_native_administrator_guard_checks_trading_account_without_effects(
    monkeypatch, wrong_trading
):
    from contextlib import nullcontext

    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    backend.api = object()
    parent = SimpleNamespace(finish=lambda: None)
    monkeypatch.setattr(native, "require_administrator_token", lambda: None)
    monkeypatch.setattr(native, "resolve_current_token_sid", lambda: "S-1-5-21-1-2-3-4")
    monkeypatch.setattr(
        native,
        "require_trading_standard_account",
        lambda: "wrong" if wrong_trading else identity.TRADING_SID,
    )
    monkeypatch.setattr(
        native.security,
        "PinnedPaperPublicationParent",
        lambda api, sid: nullcontext(parent),
    )
    if wrong_trading:
        with pytest.raises(publication.PublicationError), backend.parent_guard():
            pytest.fail("wrong Trading admitted")
    else:
        with backend.parent_guard():
            assert backend._parent is parent
        assert backend._parent is None


@pytest.mark.parametrize("drift", [False, True])
def test_public_planner_rechecks_absence_and_stable_facts_without_mutation(
    case, monkeypatch, drift
):
    backend = case.backend
    monkeypatch.setattr(FakePublication, "__enter__", lambda self: self, raising=False)
    monkeypatch.setattr(
        FakePublication, "__exit__", lambda self, *args: None, raising=False
    )
    observe = backend.observe_absent
    count = 0

    def observation(runtime):
        nonlocal count
        count += 1
        result = observe(runtime)
        if drift and count == 2:
            result["administrator"] = SECRET
        return result

    backend.observe_absent = observation
    monkeypatch.setattr(native, "WindowsPublication", lambda: backend)
    if drift:
        with pytest.raises(publication.PublicationError) as error:
            publication.plan_publication(case.raw)
        assert SECRET not in str(error.value)
    else:
        assert publication.plan_publication(case.raw) == case.plan
    assert not identity.HOST_ROOT.exists()
    assert not set(backend.events) & {"arm", "root", "paper", "state", "trading"}


@pytest.mark.parametrize("cash", ["1", "10000", "23456.78", "99999.123400"])
def test_pure_empty_predecessor_matches_frozen_store_contract(tmp_path, cash):
    starting_cash = Decimal(cash)
    expected = publication.expected_empty_paper_sha256(starting_cash)
    assert list(tmp_path.iterdir()) == []
    path = tmp_path / "test-only.sqlite"
    ReviewPaperStore(path, starting_cash=starting_cash)
    assert (
        expected == qualification_fingerprint(*read_qualification_store(path))["sha256"]
    )


@pytest.mark.parametrize("entry", ["parse", "plan", "execute"])
def test_wrong_predecessor_rejected_before_native_backend(case, monkeypatch, entry):
    raw = envelope(
        case.activation, replace(case.binding, paper_predecessor_sha256="f" * 64)
    )
    monkeypatch.setattr(
        native,
        "WindowsPublication",
        lambda: pytest.fail(
            "material rejection must precede native observation/arming"
        ),
    )
    with pytest.raises(publication.PublicationError):
        if entry == "parse":
            publication.parse_publication_material(raw)
        elif entry == "plan":
            publication.plan_publication(raw)
        else:
            publication.execute_publication(
                raw, "a" * 64, "AUTHORIZE Q133-2 " + "a" * 64
            )
    assert case.backend.events == []
    assert not identity.HOST_ROOT.exists()


def test_cash_change_requires_new_empty_predecessor(case):
    assert publication.parse_publication_material(case.raw) == case.material
    activation = replace(case.activation, starting_cash=Decimal("34567.89"))
    binding = replace(
        case.binding,
        activation_sha256=hashlib.sha256(activation.to_json().encode()).hexdigest(),
    )
    with pytest.raises(publication.PublicationError):
        publication.parse_publication_material(envelope(activation, binding))
    predecessor = publication.expected_empty_paper_sha256(activation.starting_cash)
    assert predecessor != case.binding.paper_predecessor_sha256
    binding = replace(binding, paper_predecessor_sha256=predecessor)
    assert (
        publication.parse_publication_material(envelope(activation, binding)).binding
        == binding
    )


@pytest.fixture
def root_win32(monkeypatch):
    """Fake only Win32 entry points; exercise the real local policy encoder."""
    calls, failure = [], []

    def output(argument, value, kind=ctypes.c_void_p):
        ctypes.cast(argument, ctypes.POINTER(kind))[0] = value

    def convert(sddl, revision, descriptor, size):
        calls.append(("convert", sddl, revision, size))
        output(descriptor, 101)
        return "convert" not in failure

    def owner(descriptor, result, defaulted):
        assert descriptor.value == 101
        output(result, 0 if "null_owner" in failure else 102)
        return "owner" not in failure

    def dacl(descriptor, present, result, defaulted):
        assert descriptor.value == 101
        output(present, "absent_dacl" not in failure, ctypes.c_int32)
        output(result, 0 if "null_dacl" in failure else 103)
        return "dacl" not in failure

    def set_security(handle, kind, information, owner, group, dacl, sacl):
        calls.append(
            ("set", handle, kind, information, owner.value, group, dacl.value, sacl)
        )
        return 5 if "apply" in failure else 0

    def free(descriptor):
        calls.append(("free", descriptor.value))

    advapi = SimpleNamespace(
        ConvertStringSecurityDescriptorToSecurityDescriptorW=convert,
        GetSecurityDescriptorOwner=owner,
        GetSecurityDescriptorDacl=dacl,
        SetSecurityInfo=set_security,
    )
    kernel = SimpleNamespace(LocalFree=free)
    monkeypatch.setattr(
        native.ctypes,
        "WinDLL",
        lambda name, **kwargs: {"advapi32": advapi, "kernel32": kernel}[name],
    )
    return SimpleNamespace(calls=calls, failure=failure)


def test_exact_inheritable_root_policy_uses_local_win32_boundary(
    root_win32, monkeypatch
):
    monkeypatch.setattr(
        native,
        "build_security_attributes",
        lambda *args: pytest.fail("shared builder reached"),
    )
    native.apply_publication_root_policy(77, native.publication_policy("root"))
    assert root_win32.calls == [
        (
            "convert",
            "O:S-1-5-32-544D:P"
            "(A;;0x1f01ff;;;S-1-5-32-544)(A;;0x1f01ff;;;S-1-5-18)"
            f"(A;;0x1200ab;;;{identity.TRADING_SID})"
            f"(A;OIIO;0x13019f;;;{identity.TRADING_SID})"
            "(A;OIIO;0x1f01ff;;;S-1-5-32-544)(A;OIIO;0x1f01ff;;;S-1-5-18)",
            1,
            None,
        ),
        ("set", 77, 1, 0x80000005, 102, None, 103, None),
        ("free", 101),
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "owner",
        "unprotected",
        "count",
        "order",
        "type",
        "flags",
        "mask",
        "principal",
        "semantic_file",
        "database_file",
    ],
)
def test_local_root_boundary_rejects_unsupported_policy_before_native(
    root_win32, mutation
):
    policy = native.publication_policy("root")
    if mutation == "owner":
        policy = replace(policy, owner_sid=identity.TRADING_SID)
    elif mutation == "unprotected":
        policy = replace(policy, dacl_protected=False)
    elif mutation == "count":
        policy = replace(policy, aces=policy.aces[:-1])
    elif mutation == "order":
        policy = replace(policy, aces=tuple(reversed(policy.aces)))
    elif mutation == "semantic_file":
        policy = native.publication_policy("activation.json")
    elif mutation == "database_file":
        policy = native.publication_policy("paper.sqlite")
    else:
        field, value = {
            "type": ("ace_type", 1),
            "flags": ("ace_flags", 3),
            "mask": ("access_mask", 0x1F01FF),
            "principal": ("principal_sid", native.security.SYSTEM_SID),
        }[mutation]
        aces = list(policy.aces)
        aces[3] = replace(aces[3], **{field: value})
        policy = replace(policy, aces=tuple(aces))
    with pytest.raises(publication.PublicationError, match="root policy rejected"):
        native.apply_publication_root_policy(77, policy)
    assert root_win32.calls == []


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "convert",
        "owner",
        "null_owner",
        "dacl",
        "absent_dacl",
        "null_dacl",
        "apply",
        "readback",
        "readback_drift",
    ],
)
def test_root_admission_requires_successful_local_application_and_readback(
    root_win32, monkeypatch, failure
):
    backend = native.WindowsPublication.__new__(native.WindowsPublication)
    backend._root_handle = SimpleNamespace(value=77)
    backend._trading_root = False
    if failure:
        root_win32.failure.append(failure)
    policy = native.publication_policy("root")

    def inspect(handle, path, kind):
        assert backend._trading_root is False
        assert handle is backend._root_handle
        assert (path, kind) == (
            str(identity.HOST_ROOT),
            native.AuthorityObjectKind.DIRECTORY,
        )
        root_win32.calls.append(("readback",))
        if failure == "readback":
            raise publication.PublicationError("inspection failed")
        return SimpleNamespace(
            security=SimpleNamespace(
                owner_sid=policy.owner_sid,
                dacl_protected=True,
                is_reparse_point=False,
                aces=policy.aces[:-1] if failure == "readback_drift" else policy.aces,
            )
        )

    backend.api = SimpleNamespace(inspect=inspect)
    monkeypatch.setattr(
        native,
        "apply_security_policy",
        lambda *args: pytest.fail("shared application reached"),
    )
    if failure:
        with pytest.raises(
            (publication.PublicationError, native.security.AuthoritySecurityError)
        ):
            backend.admit_trading_root()
        assert backend._trading_root is False
    else:
        backend.admit_trading_root()
        assert backend._trading_root is True
        assert root_win32.calls[-1] == ("readback",)
    assert ("free", 101) in root_win32.calls
    if failure not in {None, "readback", "readback_drift"}:
        assert ("readback",) not in root_win32.calls


def test_final_file_policies_remain_explicit_and_unchanged():
    for name in sorted(publication.FINAL_NAMES):
        policy = native.publication_policy(name)
        assert policy.owner_sid == "S-1-5-32-544" and policy.dacl_protected is True
        assert policy.aces == (
            native.SecurityAce("S-1-5-32-544", 0x1F01FF),
            native.SecurityAce("S-1-5-18", 0x1F01FF),
            native.SecurityAce(
                identity.TRADING_SID, 0x120089 if name.endswith(".json") else 0x12019F
            ),
        )
