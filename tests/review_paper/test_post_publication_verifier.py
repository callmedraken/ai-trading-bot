"""133-L fake-native verification; no retained-state/credential/provider effects."""

import ast
import ctypes
import hashlib
import inspect
import json
import logging
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from trading_bot.arch133_acl import read_only, retained_reads
from trading_bot.arch133_verifier import activation as models
from trading_bot.arch133_verifier import (
    binding,
    credentials,
    file_policy,
    operator,
    token,
)
from trading_bot.domain import OrderSide, Symbol, TradeProposal
from trading_bot.review_paper.store import ReviewPaperStore
from trading_bot.review_paper.unattended_activation import ReviewPaperActivation
from trading_bot.review_paper.unattended_state_store import UnattendedStateStore
from trading_bot.risk import RiskLimits
from trading_bot.robinhood_execute_qualification_verifier import (
    qualification_fingerprint,
    read_qualification_store,
)

ROOT = Path(__file__).resolve().parents[2]
SECRET = "private-token-client-native-error-material"
AT = datetime(2026, 10, 5, 16, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_real_edges(monkeypatch):
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: pytest.fail("native reached"))
    monkeypatch.setattr(
        credentials,
        "persisted_oauth_availability",
        lambda: pytest.fail("credential reached"),
    )
    monkeypatch.setattr(
        token.WindowsTradingTokenObserver,
        "observe",
        lambda _: pytest.fail("token reached"),
    )


@pytest.fixture
def fake(tmp_path, monkeypatch):
    f = SimpleNamespace(
        calls=[], root_reads=0, namespace_reads=0, runtime_reads=0, oauth=0, drift=None
    )
    for name, leaf in (
        ("ACTIVATION_PATH", "activation.json"),
        ("BINDING_PATH", "host-binding.json"),
        ("PAPER_PATH", "paper.sqlite"),
        ("STATE_PATH", "wake.sqlite"),
    ):
        monkeypatch.setattr(binding, name, tmp_path / leaf)
    # Only fixtures construct writers, and only under pytest's explicit temp root.
    ReviewPaperStore(binding.PAPER_PATH, starting_cash=Decimal("10000"))
    state = UnattendedStateStore(binding.STATE_PATH)
    runtime = binding.HostRuntimeIdentity(
        operator.BOUND_HEAD,
        operator.BOUND_TREE,
        binding.PRODUCTION_PYTHON_SHA256,
        binding.PRODUCTION_PYTHON_VERSION,
        "d" * 64,
    )
    act = ReviewPaperActivation(
        source_head=runtime.source_head,
        source_tree=runtime.source_tree,
        deployment_identity=runtime.deployment_identity,
        target_session_date=AT.date(),
        proposal=TradeProposal(
            UUID(int=1), Symbol("SPY"), OrderSide.BUY, Decimal("1"), AT, "frozen"
        ),
        risk_limits=RiskLimits(),
        new_trading_enabled=True,
        store_identity=UUID(int=2),
        store_path=str(binding.PAPER_PATH),
        starting_cash=Decimal("10000"),
        opening_buffer=timedelta(minutes=5),
        closing_buffer=timedelta(minutes=5),
        max_quote_age=timedelta(minutes=1),
        slippage_basis_points=Decimal("5"),
        commission=Decimal("0.1"),
        local_order_id=UUID(int=3),
        created_at=AT,
    )
    current = state.admit(act)
    host = binding.HostBinding(
        runtime,
        hashlib.sha256(act.to_json().encode()).hexdigest(),
        act.store_identity,
        qualification_fingerprint(*read_qualification_store(binding.PAPER_PATH))[
            "sha256"
        ],
        AT + timedelta(minutes=5),
    )
    binding.ACTIVATION_PATH.write_bytes(act.to_json().encode())
    binding.BINDING_PATH.write_bytes(host.to_json().encode())
    hashes = {
        name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        for name in retained_reads.FINAL_NAMES
    }
    monkeypatch.setattr(operator, "FILE_HASHES", hashes)
    names = tuple((name, i + 10) for i, name in enumerate(retained_reads.FINAL_NAMES))
    root = read_only.DirectoryObservation(
        read_only.ADMINISTRATORS_SID, True, read_only.ROOT_ACES, operator.ROOT_IDENTITY
    )
    f.root, f.names, f.act, f.host, f.current, f.store = (
        root,
        names,
        act,
        host,
        current,
        state,
    )
    f.runtime = {
        "verifier_source_head": "a" * 40,
        "verifier_source_tree": "b" * 40,
        "bound_source_head": operator.BOUND_HEAD,
        "bound_source_tree": operator.BOUND_TREE,
        "python_sha256": binding.PRODUCTION_PYTHON_SHA256,
        "python_version": binding.PRODUCTION_PYTHON_VERSION,
        "wake_launcher_sha256": runtime.launcher_sha256,
    }

    def runtime_read():
        f.runtime_reads += 1
        return {
            **f.runtime,
            **(
                {"python_sha256": "e" * 64}
                if f.drift == "runtime" and f.runtime_reads > 1
                else {}
            ),
        }

    monkeypatch.setattr(operator, "_runtime", runtime_read)
    monkeypatch.setattr(operator, "_principal", lambda: f.calls.append("principal"))
    monkeypatch.setattr(
        read_only,
        "open_directory",
        lambda path, **kw: f.calls.append(("open", path, kw)) or path,
    )

    def close(handle):
        f.calls.append(("close", handle))
        if f.drift == "close":
            raise RuntimeError(SECRET)

    monkeypatch.setattr(read_only, "close_handle", close)

    def security(handle, path):
        if path != retained_reads.TARGET_PATH:
            return replace(root, identity=(1, 2)), "e" * 64
        f.root_reads += 1
        value = (
            replace(root, identity=(1, 2))
            if f.drift == "root" and f.root_reads > 1
            else f.root
        )
        return value, (
            "e" * 64 if f.drift == "security" else operator.ROOT_SECURITY_SHA256
        )

    monkeypatch.setattr(read_only, "inspect_directory_security", security)

    def namespace(handle):
        f.namespace_reads += 1
        return (
            names[:-1] if f.drift == "namespace" and f.namespace_reads > 1 else f.names
        )

    monkeypatch.setattr(retained_reads, "namespace", namespace)
    monkeypatch.setattr(retained_reads, "open_retained_file", lambda name: name)

    def snapshot(handle, name):
        return (
            (operator.ROOT_IDENTITY[0], dict(names)[name]),
            "e" * 64
            if f.drift == "hash"
            else hashlib.sha256((tmp_path / name).read_bytes()).hexdigest(),
        )

    monkeypatch.setattr(retained_reads, "file_snapshot", snapshot)

    def policy(handle):
        rights = 0x120089 if handle.endswith(".json") else 0x12019F
        return file_policy.FilePolicy(
            read_only.ADMINISTRATORS_SID,
            True,
            read_only.ADMIN_ACES + ((binding.TRADING_SID, rights, 0, 0),),
            "c" * 64,
        )

    monkeypatch.setattr(file_policy, "observe_file_policy", policy)

    def oauth():
        f.oauth += 1
        if f.drift == "oauth":
            print(SECRET)
            print(SECRET, file=sys.stderr)
            logging.error(SECRET)
            os.write(2, SECRET.encode())
            raise RuntimeError(SECRET)
        if f.drift == "state":
            state.transition(
                current,
                state=__import__(
                    "trading_bot.review_paper.unattended_activation",
                    fromlist=["ReviewPaperWakeState"],
                ).ReviewPaperWakeState.PREPARE_STARTED,
                at=AT,
            )
        if f.drift == "paper":
            import sqlite3

            with sqlite3.connect(binding.PAPER_PATH) as connection:
                connection.execute(
                    "UPDATE metadata SET value='9999' WHERE key='starting_cash'"
                )
        return credentials.OAuthAvailability(f.drift != "unavailable", 2)

    monkeypatch.setattr(credentials, "persisted_oauth_availability", oauth)
    return f


def test_pass_is_canonical_bounded_read_only_and_reobserved(fake):
    before = {
        name: (binding.PAPER_PATH.parent / name).read_bytes()
        for name in retained_reads.FINAL_NAMES
    }
    result = operator.verify_post_publication()
    assert result["status"] == "PASS"
    assert result["schema"] == operator.SCHEMA
    assert result["wake_state"] == "READY" and result["revision"] == 0
    assert (
        result["persisted_oauth_available"] is True
        and result["oauth_storage_reads"] == fake.oauth * 2 == 2
    )
    assert all(result[name] == 0 for name in operator.ZERO_EFFECTS)
    assert result["scheduler"]["arguments"] == ("-I", "-B", str(binding.LAUNCHER))
    assert result["scheduler"]["installation_authorized"] is False
    assert fake.root_reads == fake.namespace_reads == fake.runtime_reads == 2
    assert fake.calls.count("principal") == 3
    assert before == {
        name: (binding.PAPER_PATH.parent / name).read_bytes()
        for name in retained_reads.FINAL_NAMES
    }
    assert len(operator.canonical(result)) < 8192
    assert SECRET not in operator.canonical(result)


@pytest.mark.parametrize(
    "drift",
    [
        "root",
        "security",
        "namespace",
        "hash",
        "runtime",
        "close",
        "oauth",
        "unavailable",
        "state",
        "paper",
    ],
)
def test_drift_fixed_failure_and_no_retry(fake, drift, capfd):
    fake.drift = drift
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth <= 1
    captured = capfd.readouterr()
    assert SECRET not in captured.out + captured.err


@pytest.mark.parametrize(
    "change",
    [
        dict(identity=(1, 2)),
        dict(filesystem="FAT32"),
        dict(reparse=True),
        dict(protected=False),
        dict(owner_sid=read_only.SYSTEM_SID),
        dict(aces=read_only.ADMIN_ACES),
        dict(aces=tuple(reversed(read_only.ROOT_ACES))),
    ],
)
def test_root_disagreements_reject_before_oauth(fake, change):
    fake.root = replace(fake.root, **change)
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 0


@pytest.mark.parametrize("names", [(), (("activation.json", 10),), (("extra", 9),)])
def test_exact_namespace_before_oauth(fake, names):
    fake.names = names
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 0


@pytest.mark.parametrize(
    "state_name",
    [
        "PREPARE_STARTED",
        "PREPARED",
        "REVIEW_STARTED",
        "COMPLETED",
        "STOPPED",
        "INDETERMINATE",
    ],
)
def test_consumed_authority_before_oauth(fake, monkeypatch, state_name):
    original = operator.snapshot_unattended_state
    snapshot = original(binding.STATE_PATH)
    wake = models.ReviewPaperWake(
        activation=models.ReviewPaperActivation.from_json(fake.act.to_json()),
        updated_at=AT,
        state=models.ReviewPaperWakeState(state_name),
    )
    changed = replace(
        snapshot,
        wakes=((str(fake.act.activation_id), str(wake.wake_id), wake.to_json(), 1),),
    )
    monkeypatch.setattr(operator, "snapshot_unattended_state", lambda _: changed)
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 0


@pytest.mark.parametrize(
    "change",
    [
        dict(user_sid="S-1-5-18"),
        dict(user_sid="S-1-5-21-wrong"),
        dict(elevated=True),
        dict(thread_token_present=True),
        dict(token_type=2),
        dict(groups=((token.ADMINISTRATORS_SID, 4),)),
    ],
)
def test_exact_standard_trading_token(change):
    observation = token.TradingTokenObservation(
        binding.TRADING_SID, 1, False, False, ()
    )
    token.require_trading_token(binding.TRADING_SID, observation)
    with pytest.raises(token.AuthorityPrincipalError):
        token.require_trading_token(binding.TRADING_SID, replace(observation, **change))


@pytest.mark.parametrize("args", [["--help"], ["--root", SECRET], ["verify"], [SECRET]])
def test_zero_semantic_args_reject_before_verification(monkeypatch, args, capsys):
    monkeypatch.setattr(
        operator, "verify_post_publication", lambda: pytest.fail("verification reached")
    )
    assert operator.main(args) == 3
    assert json.loads(capsys.readouterr().out) == operator.FAILURE


def test_cli_pass_and_fixed_failure(fake, capsys):
    assert operator.main([]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
    fake.drift = "oauth"
    assert operator.main([]) == 3
    assert json.loads(capsys.readouterr().out) == operator.FAILURE


@pytest.mark.parametrize("name", retained_reads.FINAL_NAMES)
@pytest.mark.parametrize(
    "change",
    [
        dict(owner_sid=read_only.SYSTEM_SID),
        dict(protected=False),
        dict(aces=read_only.ADMIN_ACES),
    ],
)
def test_final_file_policy_fail_closed(name, change):
    rights = 0x120089 if name.endswith(".json") else 0x12019F
    valid = file_policy.FilePolicy(
        read_only.ADMINISTRATORS_SID,
        True,
        read_only.ADMIN_ACES + ((binding.TRADING_SID, rights, 0, 0),),
        "c" * 64,
    )
    file_policy.require_file_policy(name, valid)
    with pytest.raises(ValueError):
        file_policy.require_file_policy(name, replace(valid, **change))


@pytest.mark.parametrize("which", ["ACTIVATION_PATH", "BINDING_PATH"])
def test_noncanonical_publication_before_oauth(fake, which):
    path = getattr(binding, which)
    path.write_bytes(path.read_bytes() + b"\n")
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 0


def test_ready_revision_updated_at_cardinality(fake, monkeypatch):
    original = operator.snapshot_unattended_state(binding.STATE_PATH)
    for changed in (
        replace(original, activations=original.activations * 2),
        replace(original, wakes=original.wakes * 2),
        replace(original, wakes=tuple((*row[:3], 1) for row in original.wakes)),
    ):
        monkeypatch.setattr(
            operator, "snapshot_unattended_state", lambda _, changed=changed: changed
        )
        assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 0


@pytest.mark.parametrize(
    "token_record,client_record",
    [
        (
            {"access_token": SECRET, "token_type": "bearer", "expires_in": 60},
            {"client_id": SECRET},
        ),
        (None, None),
        ({"access_token": SECRET}, None),
        ({"access_token": SECRET, "expires_in": 0}, {"client_id": SECRET}),
        ({"access_token": SECRET, "expires_in": True}, {"client_id": SECRET}),
        ({"access_token": SECRET, "token_type": "wrong"}, {"client_id": SECRET}),
        ({"access_token": ""}, {"client_id": SECRET}),
    ],
)
def test_bounded_credentials_only_two_reads_and_zeroized(
    monkeypatch, token_record, client_record
):
    reads, buffers = [], []

    class Native:
        def read_generic(self, target):
            reads.append(target)
            record = (
                token_record if target == credentials.TOKEN_TARGET else client_record
            )
            blob = None if record is None else bytearray(json.dumps(record).encode())
            buffers.append(blob)
            return blob

    monkeypatch.setattr(credentials, "WindowsCredentialReader", Native)
    # Undo autouse only for this fake native availability boundary.
    implementation = CREDENTIAL_AVAILABILITY
    if (
        token_record
        and client_record
        and token_record.get("access_token")
        and token_record.get("token_type", "bearer") in ("bearer", "Bearer")
        and token_record.get("expires_in", 60) == 60
    ):
        result = implementation()
        assert result == credentials.OAuthAvailability(True, 2)
        assert SECRET not in repr(result)
    elif token_record is None:
        assert implementation() == credentials.OAuthAvailability(False, 2)
    else:
        with pytest.raises(
            credentials.WindowsOAuthStorageError,
            match="^OAuth availability failed closed$",
        ):
            implementation()
    assert reads == [credentials.TOKEN_TARGET, credentials.CLIENT_INFO_TARGET]
    assert all(blob is None or not any(blob) for blob in buffers)


CREDENTIAL_AVAILABILITY = credentials.persisted_oauth_availability


def _definitions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        n.name: ast.dump(n, include_attributes=False)
        for n in tree.body
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_frozen_read_only_projections_match_accepted_definitions():
    pairs = [
        ("arch133_verifier/activation.py", "review_paper/unattended_activation.py"),
        ("arch133_verifier/activation.py", "risk/models.py"),
        ("arch133_verifier/binding.py", "review_paper/unattended_host_identity.py"),
        ("arch133_verifier/state.py", "review_paper/unattended_state_verifier.py"),
        ("arch133_verifier/state_schema.py", "review_paper/unattended_state_schema.py"),
        ("arch133_verifier/scheduler.py", "review_paper/unattended_scheduler.py"),
        (
            "arch133_verifier/sessions.py",
            "review_paper/nyse_published_regular_sessions.py",
        ),
        ("arch133_verifier/sessions.py", "review_paper/session_admission.py"),
        (
            "arch133_verifier/token.py",
            "runtime/personal_desktop_paper_account_token.py",
        ),
    ]
    compared = set()
    for projected, accepted in pairs:
        projected_definitions = _definitions(ROOT / "src/trading_bot" / projected)
        accepted_definitions = _definitions(ROOT / "src/trading_bot" / accepted)
        for name in projected_definitions.keys() & accepted_definitions.keys():
            assert projected_definitions[name] == accepted_definitions[name], name
            compared.add(name)
    assert {
        "ReviewPaperActivation",
        "ReviewPaperWake",
        "RiskLimits",
        "HostBinding",
        "WindowsTradingTokenObserver",
        "require_trading_token",
        "snapshot_unattended_state",
        "build_unattended_scheduler_spec",
    } <= compared
    assert "transition_review_paper_wake" not in _definitions(
        ROOT / "src/trading_bot/arch133_verifier/activation.py"
    )
    # Exact native read + cleanup body, with no write-capable constructor.
    import textwrap

    from trading_bot.robinhood_mcp.windows_oauth import WindowsCredentialApi

    assert ast.dump(
        ast.parse(
            textwrap.dedent(
                inspect.getsource(credentials.WindowsCredentialReader.read_generic)
            )
        ),
        include_attributes=False,
    ) == ast.dump(
        ast.parse(
            textwrap.dedent(inspect.getsource(WindowsCredentialApi.read_generic))
        ),
        include_attributes=False,
    )


def test_fresh_import_closure_is_exact_and_has_no_effect_modules(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys, json\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import trading_bot.arch133_verifier.operator\n"
        "print(json.dumps(sorted(n for n in sys.modules "
        "if n.startswith('trading_bot'))))\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(probe), str(ROOT / "src")],
        capture_output=True,
        text=True,
        check=True,
    )
    from scripts import checkpoint_runner

    names = json.loads(completed.stdout)
    expected = checkpoint_runner.ARCH133_VERIFIER_MODULES
    assert names == sorted(expected)
    forbidden = {
        "run_unattended_host",
        "execute_one_unattended_review_paper_wake",
        "ReviewPaperStore",
        "UnattendedStateStore",
        "transition_review_paper_wake",
        "SetSecurityInfo",
        "CredWriteW",
        "set_tokens",
        "set_client_info",
        "webbrowser",
    }
    for module in names:
        path = ROOT / "src" / Path(*module.split("."))
        path = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = (
            {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            | {
                n.value
                for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            }
        )
        assert not forbidden & found, (module, forbidden & found)


def test_fixed_paths_and_no_argv_impersonation():
    assert (
        str(operator.SOURCE_ROOT)
        == r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133l"
    )
    assert str(binding.HOST_ROOT) == r"F:\AITradingBot\Arch133"
    assert operator.ROOT_IDENTITY == (1855336320, 1407374886183770)
    assert operator.BOUND_HEAD == "4677ba442eafdcec56933b992f230a702012d573"
    assert operator.BOUND_TREE == "6ce181b2900df0bf8c88cdd7509eb86a2b36d8dc"
    for path in (
        ROOT / "scripts/run_arch133_post_publication_verifier.py",
        Path(operator.__file__),
    ):
        tree = ast.parse(path.read_text())
        assert not any(
            isinstance(n, ast.Subscript)
            and isinstance(n.ctx, ast.Store)
            and ast.unparse(n.value) == "sys.argv"
            for n in ast.walk(tree)
        )
    launcher = ROOT / "scripts/run_arch133_unattended_review_paper.py"
    assert (
        hashlib.sha256(launcher.read_text().encode()).hexdigest() == WAKE_LAUNCHER_HASH
    )


WAKE_LAUNCHER_HASH = "fb35635b201512c4c4c6e1caa9bfbc30945fd42c5bb5e96968934191db264d7f"


@pytest.mark.parametrize(
    "wrong",
    [
        None,
        "git_root",
        "branch",
        "origin",
        "dirty",
        "head",
        "tree",
        "tracking_head",
        "tracking_tree",
    ],
)
def test_exact_source_observation(tmp_path, monkeypatch, wrong):
    root = tmp_path
    head, tree = "a" * 40, "b" * 40
    values = {
        ("rev-parse", "HEAD"): "bad" if wrong == "head" else head,
        ("rev-parse", "HEAD^{tree}"): "bad" if wrong == "tree" else tree,
        ("rev-parse", "--show-toplevel"): str(ROOT if wrong == "git_root" else root),
        ("branch", "--show-current"): "wrong"
        if wrong == "branch"
        else operator.SOURCE_BRANCH,
        ("remote", "get-url", "origin"): "wrong"
        if wrong == "origin"
        else operator.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "dirty"
        if wrong == "dirty"
        else "",
        ("rev-parse", "refs/remotes/origin/" + operator.SOURCE_BRANCH): tree
        if wrong == "tracking_head"
        else head,
        ("rev-parse", "refs/remotes/origin/" + operator.SOURCE_BRANCH + "^{tree}"): head
        if wrong == "tracking_tree"
        else tree,
    }
    monkeypatch.setattr(operator, "_git", lambda root, *args: values[args])
    if wrong is None:
        assert operator._source(root, operator.SOURCE_BRANCH) == (head, tree)
    else:
        with pytest.raises(ValueError):
            operator._source(root, operator.SOURCE_BRANCH)


@pytest.mark.parametrize(
    "wrong",
    [
        None,
        "platform",
        "isolated",
        "bytecode",
        "cache",
        "location",
        "launcher",
        "python",
        "version",
        "python_hash",
        "bound_head",
        "bound_tree",
        "arguments",
    ],
)
def test_independent_runtime_admission(tmp_path, monkeypatch, wrong):
    executable = tmp_path / "python.exe"
    executable.write_bytes(b"fake-runtime-bytes")
    monkeypatch.setattr(binding, "PRODUCTION_PYTHON", executable)
    monkeypatch.setattr(
        binding,
        "PRODUCTION_PYTHON_SHA256",
        "e" * 64
        if wrong == "python_hash"
        else hashlib.sha256(executable.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        binding, "LAUNCHER", ROOT / "scripts/run_arch133_unattended_review_paper.py"
    )
    monkeypatch.setattr(
        operator, "SOURCE_ROOT", tmp_path if wrong == "location" else ROOT
    )
    monkeypatch.setattr(
        operator, "LAUNCHER", ROOT / "scripts/run_arch133_post_publication_verifier.py"
    )
    monkeypatch.setattr(
        operator,
        "_source",
        lambda root, branch: (
            ("a" * 40, "b" * 40)
            if branch == operator.SOURCE_BRANCH
            else (
                ("a" * 40 if wrong == "bound_head" else operator.BOUND_HEAD),
                ("b" * 40 if wrong == "bound_tree" else operator.BOUND_TREE),
            )
        ),
    )
    with monkeypatch.context() as context:
        context.setattr(sys, "platform", "other" if wrong == "platform" else "win32")
        context.setattr(sys, "flags", SimpleNamespace(isolated=wrong != "isolated"))
        context.setattr(sys, "dont_write_bytecode", wrong != "bytecode")
        context.setattr(
            sys,
            "pycache_prefix",
            "wrong" if wrong == "cache" else str(operator.NO_PYCACHE),
        )
        context.setattr(
            sys,
            "argv",
            [str(executable if wrong == "launcher" else operator.LAUNCHER)]
            + ([SECRET] if wrong == "arguments" else []),
        )
        context.setattr(
            sys,
            "executable",
            str(operator.LAUNCHER if wrong == "python" else executable),
        )
        context.setattr(sys, "version_info", (3, 14, 2 if wrong == "version" else 3))
        if wrong is None:
            assert operator._runtime()["bound_source_head"] == operator.BOUND_HEAD
        else:
            with pytest.raises(ValueError):
                operator._runtime()


@pytest.mark.parametrize(
    "wrong",
    [
        "runtime_head",
        "runtime_tree",
        "python_sha",
        "python_version",
        "launcher_sha",
        "store_identity",
        "predecessor",
        "oauth_bound",
    ],
)
def test_binding_disagreements_before_oauth(fake, wrong):
    host = fake.host
    field = {
        "runtime_head": "source_head",
        "runtime_tree": "source_tree",
        "python_sha": "python_sha256",
        "python_version": "python_version",
        "launcher_sha": "launcher_sha256",
    }.get(wrong)
    if field:
        value = (
            "3.14.2"
            if field == "python_version"
            else "e" * (40 if field.startswith("source_") else 64)
        )
        host = replace(host, runtime=replace(host.runtime, **{field: value}))
    elif wrong == "store_identity":
        host = replace(host, store_identity=UUID(int=7))
    elif wrong == "predecessor":
        host = replace(host, paper_predecessor_sha256="e" * 64)
    else:
        host = replace(host, oauth_valid_until=AT)
    raw = host.to_json().encode()
    binding.BINDING_PATH.write_bytes(raw)
    operator.FILE_HASHES["host-binding.json"] = hashlib.sha256(raw).hexdigest()
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 0


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE metadata SET value='1' WHERE key='schema_version'",
        "INSERT INTO metadata VALUES ('unexpected','value')",
        "UPDATE metadata SET value='9999' WHERE key='starting_cash'",
    ],
)
def test_paper_schema_and_metadata_before_oauth(fake, statement):
    import sqlite3

    with sqlite3.connect(binding.PAPER_PATH) as connection:
        connection.execute(statement)
    operator.FILE_HASHES["paper.sqlite"] = hashlib.sha256(
        binding.PAPER_PATH.read_bytes()
    ).hexdigest()
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 0


def test_wake_created_at_and_cardinality_before_oauth(fake, monkeypatch):
    original = operator.snapshot_unattended_state(binding.STATE_PATH)
    activation = models.ReviewPaperActivation.from_json(fake.act.to_json())
    wake = models.ReviewPaperWake(
        activation=activation, updated_at=AT + timedelta(seconds=1)
    )
    changed = replace(
        original,
        wakes=((str(activation.activation_id), str(wake.wake_id), wake.to_json(), 0),),
    )
    monkeypatch.setattr(operator, "snapshot_unattended_state", lambda _: changed)
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 0


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "security",
        "control",
        "acl",
        "count",
        "get_ace",
        "ace_kind",
        "sid",
        "length",
    ],
)
def test_binary_final_file_observation_without_mutation(monkeypatch, failure):
    descriptor = ctypes.create_string_buffer(b"fixed descriptor payload bytes")
    aces, sid_map, calls, strings = [], {301: read_only.ADMINISTRATORS_SID}, [], []
    for sid, mask, kind, _flags in read_only.ADMIN_ACES + (
        (binding.TRADING_SID, 0x120089, 0, 0),
    ):
        raw = ctypes.create_string_buffer(24)
        ctypes.cast(raw, ctypes.POINTER(ctypes.c_ubyte))[0] = (
            1 if failure == "ace_kind" else kind
        )
        ctypes.cast(ctypes.addressof(raw) + 4, ctypes.POINTER(ctypes.c_uint32))[0] = (
            mask
        )
        sid_map[ctypes.addressof(raw) + 8] = sid
        aces.append(raw)

    def bind(library, name, arguments, result):
        def invoke(*values):
            calls.append(name)
            if name == "GetSecurityInfo":
                assert values[:3] == (77, 1, 7)
                values[3]._obj.value, values[5]._obj.value = 301, 302
                values[7]._obj.value = ctypes.addressof(descriptor)
                return 5 if failure == "security" else 0
            if name == "GetSecurityDescriptorControl":
                values[1]._obj.value = 0x1000
                return failure != "control"
            if name == "GetAclInformation":
                values[1]._obj.count = 4 if failure == "count" else 3
                return failure != "acl"
            if name == "GetAce":
                values[2]._obj.value = ctypes.addressof(aces[values[1]])
                return failure != "get_ace"
            if name == "ConvertSidToStringSidW":
                string = ctypes.create_unicode_buffer(sid_map[values[0].value])
                strings.append(string)
                values[1]._obj.value = string.value
                return failure != "sid"
            if name == "GetSecurityDescriptorLength":
                return 1 if failure == "length" else len(descriptor)
            return 1

        return invoke

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: object())
    monkeypatch.setattr(file_policy, "_bind", bind)
    if failure is None:
        result = file_policy.observe_file_policy(77)
        file_policy.require_file_policy("activation.json", result)
        assert result.security_sha256 == hashlib.sha256(descriptor.raw).hexdigest()
    else:
        with pytest.raises(ValueError):
            file_policy.observe_file_policy(77)
    assert calls[-1] == "LocalFree"
    assert set(calls) <= {
        "GetSecurityInfo",
        "GetSecurityDescriptorControl",
        "GetAclInformation",
        "GetAce",
        "ConvertSidToStringSidW",
        "GetSecurityDescriptorLength",
        "LocalFree",
    }


def test_credential_constructor_binds_only_read_and_cleanup(monkeypatch):
    bound = []

    class Function:
        def __call__(self, *args):
            return 1

    class Library:
        def __getattr__(self, name):
            bound.append(name)
            return Function()

    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: Library())
    native = credentials.WindowsCredentialReader()
    assert not hasattr(native, "write_generic")
    assert set(bound) == {
        "CredReadW",
        "CredFree",
        "RtlSecureZeroMemory",
        "RtlZeroMemory",
    }


@pytest.mark.parametrize("args", [[], ["--root", SECRET]])
def test_launcher_rejection_sanitized_before_trading_import(tmp_path, args):
    # This is a copied launcher at a wrong source root, never the real verifier.
    path = tmp_path / "run.py"
    path.write_text(
        (ROOT / "scripts/run_arch133_post_publication_verifier.py").read_text()
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(path), *args], capture_output=True, text=True
    )
    assert result.returncode == 3
    assert json.loads(result.stdout) == operator.FAILURE
    assert result.stderr == ""


@pytest.mark.parametrize(
    "client",
    [
        {
            "client_id": SECRET,
            "redirect_uris": ["http://127.0.0.1:8765/oauth/callback"],
        },
        {"client_id": SECRET, "grant_types": None, "issuer": ""},
    ],
)
def test_registration_available_without_client_construction(client):
    assert credentials._client_available(client)


@pytest.mark.parametrize(
    "change",
    [
        {"client_id": ""},
        {"client_secret": 5},
        {"issuer": []},
        {"client_id_issued_at": True},
        {"grant_types": "authorization_code"},
        {"response_types": [5]},
        {"redirect_uris": ["not-a-url"]},
        {"client_uri": 5},
        {"client_uri": "ftp://example.test"},
    ],
)
def test_malformed_persisted_registration_rejected(change):
    assert not credentials._client_available({"client_id": SECRET, **change})


@pytest.mark.parametrize("drift", ["file_policy", "ancestor", "principal"])
def test_post_oauth_reobservation_required(fake, monkeypatch, drift):
    original = credentials.persisted_oauth_availability

    def oauth():
        available = original()
        if drift == "file_policy":
            observe = file_policy.observe_file_policy
            monkeypatch.setattr(
                file_policy,
                "observe_file_policy",
                lambda handle: replace(observe(handle), protected=False),
            )
        elif drift == "ancestor":
            observe = read_only.inspect_directory_security

            def changed(handle, path):
                observation, digest = observe(handle, path)
                return (
                    replace(observation, identity=(5, 6))
                    if path != retained_reads.TARGET_PATH
                    else observation
                ), digest

            monkeypatch.setattr(read_only, "inspect_directory_security", changed)
        else:
            monkeypatch.setattr(
                operator,
                "_principal",
                lambda: (_ for _ in ()).throw(ValueError(SECRET)),
            )
        return available

    monkeypatch.setattr(credentials, "persisted_oauth_availability", oauth)
    assert operator.verify_post_publication() == operator.FAILURE
    assert fake.oauth == 1


def test_nonempty_paper_rejected_even_with_matching_predecessor(fake, monkeypatch):
    metadata = [["schema_version", "2"], ["starting_cash", "10000"]]
    columns, rows, calls = ["paper_trade_id"], [["example"]], []

    class Connection:
        description = [("paper_trade_id",)]

        def execute(self, statement):
            calls.append(statement)
            return self

        def __iter__(self):
            return iter(metadata)

        def fetchall(self):
            return rows

        def close(self):
            calls.append("close")

    def connect(database, **kwargs):
        assert database == binding.PAPER_PATH.as_uri() + "?mode=ro"
        assert kwargs == {"uri": True, "timeout": 0}
        return Connection()

    monkeypatch.setattr(operator.sqlite3, "connect", connect)
    host = replace(
        fake.host,
        paper_predecessor_sha256=qualification_fingerprint(metadata, columns, rows)[
            "sha256"
        ],
    )
    with pytest.raises(ValueError):
        operator._paper(
            models.ReviewPaperActivation.from_json(fake.act.to_json()), host
        )
    assert calls == [
        "BEGIN",
        "SELECT key, value FROM metadata ORDER BY key",
        "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id",
        "close",
    ]


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"[]",
        b'{"access_token":"a","access_token":"b"}',
        b'{"access_token":NaN}',
        b"x" * 2561,
    ],
)
def test_invalid_credential_records_are_bounded_and_sanitized(monkeypatch, raw):
    blobs = []

    class Native:
        def read_generic(self, target):
            blob = bytearray(
                raw
                if target == credentials.TOKEN_TARGET
                else b'{"client_id":"example"}'
            )
            blobs.append(blob)
            return blob

    monkeypatch.setattr(credentials, "WindowsCredentialReader", Native)
    with pytest.raises(
        credentials.WindowsOAuthStorageError, match="^OAuth availability failed closed$"
    ):
        CREDENTIAL_AVAILABILITY()
    assert all(not any(blob) for blob in blobs)
