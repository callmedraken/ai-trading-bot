"""133-N fake-only stage diagnostic; production state and credentials unreachable."""

import ast
import ctypes
import hashlib
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
from trading_bot.arch133_publication_diagnostic import operator
from trading_bot.arch133_verifier import (
    binding,
    file_policy,
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
        token.WindowsTradingTokenObserver,
        "observe",
        lambda _: pytest.fail("token reached"),
    )


@pytest.fixture
def fake(tmp_path, monkeypatch):
    f = SimpleNamespace(
        calls=[], root_reads=0, namespace_reads=0, runtime_reads=0, drift=None
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
        "diagnostic_source_head": "a" * 40,
        "diagnostic_source_tree": "b" * 40,
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

    return f


BOUND_DOCS_CHECKOUT = (
    "65f0d40217f8ce129224531a5151f4acea889d89",
    "16cb734cbeaa9e97aaf9e2d521d922fbbc7b7ae2",
)


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


@pytest.mark.parametrize(
    "wrong",
    [
        None,
        "git_root",
        "detached",
        "branch",
        "origin",
        "dirty",
        "head",
        "tree",
        "tracking_head",
        "tracking_tree",
    ],
)
def test_exact_diagnostic_source_observation(tmp_path, monkeypatch, wrong):
    root = tmp_path
    monkeypatch.setattr(operator, "SOURCE_ROOT", root)
    head, tree = "a" * 40, "b" * 40
    values = {
        ("rev-parse", "HEAD"): "bad" if wrong == "head" else head,
        ("rev-parse", "HEAD^{tree}"): "bad" if wrong == "tree" else tree,
        ("rev-parse", "--show-toplevel"): str(ROOT if wrong == "git_root" else root),
        ("branch", "--show-current"): ""
        if wrong == "detached"
        else "wrong"
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
        assert operator._diagnostic_source() == (head, tree)
    else:
        with pytest.raises(ValueError):
            operator._diagnostic_source()


@pytest.mark.parametrize(
    "checkout",
    [
        (operator.BOUND_HEAD, operator.BOUND_TREE),
        BOUND_DOCS_CHECKOUT,
    ],
)
def test_bound_source_accepts_reviewed_checkout_pairs_and_reports_frozen(
    tmp_path, monkeypatch, checkout
):
    monkeypatch.setattr(binding, "SOURCE_ROOT", tmp_path)
    values = {
        ("rev-parse", "HEAD"): checkout[0],
        ("rev-parse", "HEAD^{tree}"): checkout[1],
        ("rev-parse", "--show-toplevel"): str(tmp_path),
        ("branch", "--show-current"): binding.SOURCE_BRANCH,
        ("remote", "get-url", "origin"): operator.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "",
    }
    calls = []

    def git(root, *args):
        assert root == tmp_path
        calls.append(args)
        return values[args]

    monkeypatch.setattr(operator, "_git", git)
    assert operator._bound_source() == (operator.BOUND_HEAD, operator.BOUND_TREE)
    assert not any(
        "refs/remotes/origin/" in argument for args in calls for argument in args
    )


@pytest.mark.parametrize(
    "wrong",
    [
        "git_root",
        "detached",
        "branch",
        "origin",
        "dirty",
        "head",
        "tree",
        "mixed_pair",
    ],
)
def test_bound_source_rejects_unreviewed_or_dirty_checkout(
    tmp_path, monkeypatch, wrong
):
    monkeypatch.setattr(binding, "SOURCE_ROOT", tmp_path)
    head, tree = BOUND_DOCS_CHECKOUT
    if wrong == "head":
        head = "a" * 40
    elif wrong == "tree":
        tree = "b" * 40
    elif wrong == "mixed_pair":
        head = operator.BOUND_HEAD
    values = {
        ("rev-parse", "HEAD"): head,
        ("rev-parse", "HEAD^{tree}"): tree,
        ("rev-parse", "--show-toplevel"): str(
            ROOT if wrong == "git_root" else tmp_path
        ),
        ("branch", "--show-current"): ""
        if wrong == "detached"
        else ("wrong" if wrong == "branch" else binding.SOURCE_BRANCH),
        ("remote", "get-url", "origin"): "wrong"
        if wrong == "origin"
        else operator.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=all"): "dirty"
        if wrong == "dirty"
        else "",
    }
    calls = []

    def git(root, *args):
        assert root == tmp_path
        calls.append(args)
        return values[args]

    monkeypatch.setattr(operator, "_git", git)
    with pytest.raises(ValueError):
        operator._bound_source()
    assert not any(
        "refs/remotes/origin/" in argument for args in calls for argument in args
    )


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
        operator,
        "LAUNCHER",
        ROOT / "scripts/run_arch133_publication_state_paper_diagnostic.py",
    )
    monkeypatch.setattr(operator, "_diagnostic_source", lambda: ("a" * 40, "b" * 40))
    monkeypatch.setattr(
        operator,
        "_bound_source",
        lambda: (
            "a" * 40 if wrong == "bound_head" else operator.BOUND_HEAD,
            "b" * 40 if wrong == "bound_tree" else operator.BOUND_TREE,
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


def test_fresh_import_closure_excludes_credentials_and_effect_capabilities(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys, json, ctypes\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "def reject(*a, **k): raise AssertionError('native import effect')\n"
        "ctypes.WinDLL = reject\n"
        "import trading_bot.arch133_publication_diagnostic.operator\n"
        "print(json.dumps(sorted(n for n in sys.modules "
        "if n.startswith('trading_bot'))))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(probe), str(ROOT / "src")],
        capture_output=True,
        text=True,
        check=True,
    )
    from scripts import checkpoint_runner

    names = json.loads(result.stdout)
    assert names == sorted(checkpoint_runner.ARCH133_PUBLICATION_DIAGNOSTIC_MODULES)
    assert "trading_bot.arch133_verifier.credentials" not in names
    assert "trading_bot.arch133_verifier.operator" not in names
    paths = []
    forbidden = {
        "CredReadW",
        "CredWriteW",
        "CredFree",
        "SetSecurityInfo",
        "SetFileSecurityW",
        "run_unattended_host",
        "execute_one_unattended_review_paper_wake",
        "ReviewPaperStore",
        "UnattendedStateStore",
        "transition_review_paper_wake",
        "WindowsOAuthStorage",
        "set_tokens",
        "set_client_info",
        "webbrowser",
        "MCPClient",
        "TaskScheduler",
        "register_task",
        "publish_unattended_host",
    }
    for module in names:
        path = ROOT / "src" / Path(*module.split("."))
        path = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
        paths.append(path.relative_to(ROOT).as_posix())
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
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
        assert "AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1" not in text
        assert "AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1" not in text
        assert "CredReadW" not in text
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                assert all(
                    not a.name.startswith(("mcp", "httpx", "httpx2")) for a in n.names
                )
            if isinstance(n, ast.ImportFrom):
                assert not (n.module or "").startswith(
                    (
                        "mcp",
                        "httpx",
                        "httpx2",
                        "trading_bot.runtime",
                        "trading_bot.review_paper",
                        "trading_bot.robinhood_mcp",
                    )
                )
    assert set(checkpoint_runner.ARCH133_PUBLICATION_DIAGNOSTIC_PINS) == {
        *paths,
        "scripts/run_arch133_publication_state_paper_diagnostic.py",
    }


@pytest.mark.parametrize("args", [[], ["--root", SECRET]])
def test_copied_launcher_fails_before_trading_import(tmp_path, args):
    path = tmp_path / "run.py"
    path.write_text(
        (ROOT / "scripts/run_arch133_publication_state_paper_diagnostic.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(path), *args], capture_output=True, text=True
    )
    assert result.returncode == 3
    assert result.stdout == operator.RUNTIME_BLOCK + "\n"
    assert result.stderr == ""
    assert not (tmp_path / "no-pycache").exists()


def test_fixed_paths_runtime_hashes_and_accepted_launchers_unchanged():
    assert (
        str(operator.SOURCE_ROOT)
        == r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133n"
    )
    assert operator.SOURCE_BRANCH == "feature/robinhood-unattended-review-paper-133n"
    assert (
        operator.LAUNCHER
        == operator.SOURCE_ROOT
        / "scripts/run_arch133_publication_state_paper_diagnostic.py"
    )
    assert operator.NO_PYCACHE == operator.SOURCE_ROOT / "no-pycache"
    assert str(binding.PRODUCTION_PYTHON) == r"F:\AITradingBot\runtime\python.exe"
    assert binding.PRODUCTION_PYTHON_VERSION == "3.14.3"
    assert (
        binding.PRODUCTION_PYTHON_SHA256
        == "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"
    )
    assert (
        str(binding.HOST_ROOT)
        == retained_reads.TARGET_PATH
        == r"F:\AITradingBot\Arch133"
    )
    assert operator.ROOT_IDENTITY == (1855336320, 1407374886183770)
    assert (
        operator.ROOT_SECURITY_SHA256
        == "6f37254510de5246c3d8427a49743f013c339f60c205a2464b46e8aa4f8ab5c7"
    )
    expected = {
        "scripts/run_arch133_post_publication_verifier.py": (
            "07d5298a67819706726dafd2fb48c9a85f4a7fd01fe0228a5f9aa08c89b1c1aa"
        ),
        "src/trading_bot/arch133_verifier/operator.py": (
            "9ba0906f0077ffeb512010939933bf016947a51daabb5f7cd1110939223f490a"
        ),
        "scripts/run_arch133_unattended_review_paper.py": (
            "fb35635b201512c4c4c6e1caa9bfbc30945fd42c5bb5e96968934191db264d7f"
        ),
    }
    for path, digest in expected.items():
        assert (
            hashlib.sha256(
                (ROOT / path).read_text(encoding="utf-8").encode()
            ).hexdigest()
            == digest
        )


def blocked(stage):
    return operator.stage_result(stage)


def test_pass_exact_schema_zero_effects_and_unchanged_bytes(fake):
    before = {p.name: p.read_bytes() for p in binding.PAPER_PATH.parent.iterdir()}
    result = operator.diagnose_publication_state_paper()
    assert result == operator.stage_result("FINAL_REOBSERVATION", passed=True)
    assert result["schema"] == "arch133n-publication-state-paper-diagnostic/v1"
    assert result["stage"] == "PUBLICATION_STATE_PAPER_COMPLETE"
    assert set(result) == {
        "schema",
        "status",
        "reason",
        "stage",
        *operator.ZERO_EFFECTS,
    }
    assert set(operator.ZERO_EFFECTS) == {
        "credential_reads",
        "credential_writes",
        "provider_calls",
        "scheduler_reads",
        "scheduler_writes",
        "paper_mutations",
        "state_mutations",
        "acl_mutations",
        "wake_delegations",
        "execution_delegations",
        "consumed_wake_authority",
        "broker_effects",
    }
    assert all(type(result[k]) is int and result[k] == 0 for k in operator.ZERO_EFFECTS)
    assert before == {
        p.name: p.read_bytes() for p in binding.PAPER_PATH.parent.iterdir()
    }
    assert fake.root_reads == fake.namespace_reads == fake.runtime_reads == 2
    assert fake.calls.count("principal") == 2


@pytest.mark.parametrize("failure", range(9))
def test_every_stage_rejects_stops_later_work_and_suppresses_all_output(
    fake, monkeypatch, failure, capfd
):
    calls, connections = [], []
    original_connect = operator.sqlite3.connect

    def connect(*a, **kw):
        index = 4 if len(connections) == 0 else 6
        calls.append(index)
        if failure == index:
            raise RuntimeError(SECRET)
        connection = original_connect(*a, **kw)
        connections.append(connection)
        return connection

    monkeypatch.setattr(operator.sqlite3, "connect", connect)
    functions = {
        0: "_publication_path_read",
        1: "_publication_parse",
        2: "_publication_semantics",
        3: "_state_path_resolution",
        5: "_state_semantics",
        7: "_paper_semantics",
    }
    for index, name in functions.items():
        original = getattr(operator, name)

        def edge(*a, index=index, original=original, **kw):
            # The second path read starts final reobservation.
            observed = 8 if index == 0 and 7 in calls else index
            calls.append(observed)
            if observed == failure:
                print(SECRET)
                print(SECRET, file=sys.stderr)
                logging.error(SECRET)
                os.write(2, SECRET.encode())
                raise RuntimeError(SECRET)
            return original(*a, **kw)

        monkeypatch.setattr(operator, name, edge)
    assert operator.diagnose_publication_state_paper() == blocked(
        operator.STAGES[failure]
    )
    assert calls == list(range(failure + 1))
    captured = capfd.readouterr()
    assert SECRET not in captured.out + captured.err
    assert [c for c in fake.calls if isinstance(c, tuple) and c[0] == "close"] == [
        *(("close", n) for n in reversed(retained_reads.FINAL_NAMES)),
        ("close", retained_reads.TARGET_PATH),
    ]
    for connection in connections:
        with pytest.raises(operator.sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


@pytest.mark.parametrize(
    "edge",
    ["_runtime", "_principal", "root", "namespace", "identity", "hash", "policy"],
)
def test_prerequisites_are_runtime_block_not_publication_failure(
    fake, monkeypatch, edge, capsys
):
    def fail(*a, **k):
        raise RuntimeError(SECRET)

    if edge in ("_runtime", "_principal"):
        monkeypatch.setattr(operator, edge, fail)
    elif edge == "root":
        fake.root = replace(fake.root, identity=(1, 2))
    elif edge == "namespace":
        fake.names = ()
    elif edge == "identity":
        monkeypatch.setattr(
            retained_reads, "file_snapshot", lambda *a: ((1, 2), "f" * 64)
        )
    elif edge == "hash":
        fake.drift = "hash"
    else:
        monkeypatch.setattr(file_policy, "require_file_policy", fail)
    monkeypatch.setattr(
        operator, "_publication_path_read", lambda: pytest.fail("publication reached")
    )
    assert operator.diagnose_publication_state_paper() is None
    assert operator.main([]) == 3
    assert capsys.readouterr().out == operator.RUNTIME_BLOCK + "\n"


@pytest.mark.parametrize("name", retained_reads.FINAL_NAMES)
@pytest.mark.parametrize("edge", ["open", "snapshot", "policy"])
def test_partial_acquisition_closes_each_acquired_handle(fake, monkeypatch, name, edge):
    module, function = {
        "open": (retained_reads, "open_retained_file"),
        "snapshot": (retained_reads, "file_snapshot"),
        "policy": (file_policy, "observe_file_policy"),
    }[edge]
    original = getattr(module, function)

    def fail(*args):
        if name in args:
            raise RuntimeError(SECRET)
        return original(*args)

    monkeypatch.setattr(module, function, fail)
    assert operator.diagnose_publication_state_paper() is None
    acquired = retained_reads.FINAL_NAMES[
        : retained_reads.FINAL_NAMES.index(name) + (edge != "open")
    ]
    assert [c[1] for c in fake.calls if isinstance(c, tuple) and c[0] == "close"] == [
        *reversed(acquired),
        retained_reads.TARGET_PATH,
    ]


@pytest.mark.parametrize(
    "target", ["root", *retained_reads.FINAL_NAMES, "state", "paper"]
)
@pytest.mark.parametrize("earlier_failure", [False, True])
def test_close_failures_override_stage_and_every_resource_closes_once(
    fake, monkeypatch, target, earlier_failure
):
    closed, sql = [], []

    def close(handle):
        closed.append(handle)
        if handle == (retained_reads.TARGET_PATH if target == "root" else target):
            raise RuntimeError(SECRET)

    monkeypatch.setattr(read_only, "close_handle", close)
    original_connect = operator.sqlite3.connect

    class Connection(operator.sqlite3.Connection):
        def close(self):
            sql.append(self.label)
            super().close()
            if self.label == target:
                raise RuntimeError(SECRET)

    def connect(database, **kw):
        connection = original_connect(database, **kw, factory=Connection)
        connection.label = "state" if "wake.sqlite" in database else "paper"
        return connection

    monkeypatch.setattr(operator.sqlite3, "connect", connect)
    if earlier_failure:
        monkeypatch.setattr(
            operator,
            "_paper_semantics",
            lambda *a: (_ for _ in ()).throw(ValueError(SECRET)),
        )
    assert operator.diagnose_publication_state_paper() == blocked("FINAL_REOBSERVATION")
    assert closed == [*reversed(retained_reads.FINAL_NAMES), retained_reads.TARGET_PATH]
    assert sql == ["paper", "state"]
    assert fake.runtime_reads == 1


@pytest.mark.parametrize("name", ["state", "paper"])
@pytest.mark.parametrize("fail_begin", [False, True])
def test_sqlite_open_stages_are_transport_only_read_only_and_close_on_begin_failure(
    fake, monkeypatch, name, fail_begin
):
    events = []
    original_connect = operator.sqlite3.connect

    class Connection(operator.sqlite3.Connection):
        def execute(self, statement, *a):
            events.append((self.label, statement))
            if fail_begin and self.label == name and statement == "BEGIN":
                raise operator.sqlite3.OperationalError(SECRET)
            return super().execute(statement, *a)

        def close(self):
            events.append((self.label, "close"))
            super().close()

    def connect(database, **kw):
        assert kw == {"uri": True, "timeout": 0}
        assert database in {
            p.as_uri() + "?mode=ro" for p in (binding.STATE_PATH, binding.PAPER_PATH)
        }
        connection = original_connect(database, **kw, factory=Connection)
        connection.label = "state" if "wake.sqlite" in database else "paper"
        return connection

    monkeypatch.setattr(operator.sqlite3, "connect", connect)

    def semantics(*a):
        assert [e for e in events if e[0] == name] == [(name, "BEGIN")]
        raise ValueError(SECRET)

    monkeypatch.setattr(operator, "_" + name + "_semantics", semantics)
    expected = name.upper() + ("_SQLITE_OPEN" if fail_begin else "_SEMANTICS")
    assert operator.diagnose_publication_state_paper() == blocked(expected)
    assert events.count((name, "close")) == 1


@pytest.mark.parametrize("starting_cash", ["10000", "10000.00", "1E+4", "0.01"])
def test_empty_fingerprint_matches_accepted_publication_contract_without_sqlite(
    starting_cash, monkeypatch
):
    from trading_bot.review_paper.unattended_publication import (
        EMPTY_PAPER_COLUMNS,
        expected_empty_paper_sha256,
    )

    cash = Decimal(starting_cash)
    monkeypatch.setattr(
        operator.sqlite3, "connect", lambda *a, **k: pytest.fail("SQLite reached")
    )
    assert operator.EMPTY_PAPER_COLUMNS == EMPTY_PAPER_COLUMNS
    assert operator.expected_empty_paper_sha256(cash) == expected_empty_paper_sha256(
        cash
    )
    assert (
        operator.expected_empty_paper_sha256(cash)
        == qualification_fingerprint(
            [["schema_version", "2"], ["starting_cash", str(cash)]],
            list(EMPTY_PAPER_COLUMNS),
            [],
        )["sha256"]
    )


@pytest.mark.parametrize("which", ["ACTIVATION_PATH", "BINDING_PATH"])
@pytest.mark.parametrize("failure", ["read", "hash", "size", "utf8", "canonical"])
def test_path_access_separate_from_held_admission_and_parse(
    fake, monkeypatch, which, failure
):
    path = getattr(binding, which)
    # Held bytes remain independently accepted; only ordinary path access changes.
    monkeypatch.setattr(
        retained_reads,
        "file_snapshot",
        lambda h, n: (
            (operator.ROOT_IDENTITY[0], dict(fake.names)[n]),
            operator.FILE_HASHES[n],
        ),
    )
    original = Path.read_bytes
    raw = original(path)
    if failure == "read":

        def read(self):
            if self == path:
                raise PermissionError(SECRET)
            return original(self)

        monkeypatch.setattr(Path, "read_bytes", read)
    else:
        value = b"\xff" if failure == "utf8" else raw + b"\n"
        if failure == "size":
            monkeypatch.setattr(operator, "MAX_PUBLICATION_BYTES", 1)
        elif failure in {"utf8", "canonical"}:
            operator.FILE_HASHES[path.name] = hashlib.sha256(value).hexdigest()
            monkeypatch.setattr(
                retained_reads,
                "file_snapshot",
                lambda h, n: (
                    (operator.ROOT_IDENTITY[0], dict(fake.names)[n]),
                    operator.FILE_HASHES[n],
                ),
            )
        monkeypatch.setattr(
            Path, "read_bytes", lambda self: value if self == path else original(self)
        )
    expected = (
        "PUBLICATION_PARSE"
        if failure in {"utf8", "canonical"}
        else "PUBLICATION_PATH_READ"
    )
    assert operator.diagnose_publication_state_paper() == blocked(expected)


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
        "activation_sha",
    ],
)
def test_publication_semantic_disagreement_never_opens_sqlite(fake, monkeypatch, wrong):
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
    elif wrong == "activation_sha":
        host = replace(host, activation_sha256="e" * 64)
    else:
        host = replace(host, oauth_valid_until=AT)
    binding.BINDING_PATH.write_text(host.to_json(), encoding="utf-8")
    operator.FILE_HASHES["host-binding.json"] = hashlib.sha256(
        binding.BINDING_PATH.read_bytes()
    ).hexdigest()
    monkeypatch.setattr(
        operator.sqlite3, "connect", lambda *a, **k: pytest.fail("SQLite reached")
    )
    assert operator.diagnose_publication_state_paper() == blocked(
        "PUBLICATION_SEMANTICS"
    )


@pytest.mark.parametrize(
    "args", [["--help"], ["--root", SECRET], ["--execute"], ["--retry"]]
)
def test_no_semantic_arguments(args, monkeypatch, capsys):
    monkeypatch.setattr(
        operator,
        "diagnose_publication_state_paper",
        lambda: pytest.fail("diagnostic reached"),
    )
    assert operator.main(args) == 3
    assert capsys.readouterr().out == operator.RUNTIME_BLOCK + "\n"


def test_unknown_stage_cannot_escape():
    with pytest.raises(ValueError):
        operator.stage_result(SECRET)


def test_cli_pass(fake, capsys):
    assert operator.main([]) == 0
    assert json.loads(capsys.readouterr().out) == operator.stage_result(
        "FINAL_REOBSERVATION", passed=True
    )


@pytest.mark.parametrize("failure", ["raise", "alternate"])
def test_state_path_resolution_precedes_any_sqlite_open(fake, monkeypatch, failure):
    calls = []

    def resolve(path, **kw):
        calls.append((path, kw))
        if failure == "raise":
            raise OSError(SECRET)
        return path.parent / "alternate.sqlite"

    monkeypatch.setattr(operator, "state_database_path", resolve)
    monkeypatch.setattr(
        operator.sqlite3, "connect", lambda *a, **k: pytest.fail("SQLite reached")
    )
    assert operator.diagnose_publication_state_paper() == blocked(
        "STATE_PATH_RESOLUTION"
    )
    assert calls == [
        (
            binding.STATE_PATH,
            {
                "activation": operator.ReviewPaperActivation.from_json(
                    fake.act.to_json()
                )
            },
        )
    ]


@pytest.mark.parametrize(
    "statement",
    [
        "PRAGMA application_id=0",
        "PRAGMA user_version=2",
        "CREATE TABLE unexpected (value TEXT)",
        "UPDATE metadata SET value='wrong' WHERE key='version'",
        "DELETE FROM wakes",
        "UPDATE wakes SET revision=1",
        "UPDATE activations SET activation_json='invalid'",
    ],
)
def test_closed_state_schema_metadata_binding_and_ready_revision(fake, statement):
    connection = operator.sqlite3.connect(binding.STATE_PATH)
    try:
        connection.execute(statement)
        connection.commit()
    finally:
        connection.close()
    operator.FILE_HASHES["wake.sqlite"] = hashlib.sha256(
        binding.STATE_PATH.read_bytes()
    ).hexdigest()
    assert operator.diagnose_publication_state_paper() == blocked("STATE_SEMANTICS")


@pytest.mark.parametrize(
    "change",
    [
        "READY",
        "PREPARE_STARTED",
        "PREPARED",
        "REVIEW_STARTED",
        "COMPLETED",
        "STOPPED",
        "INDETERMINATE",
        "cardinality",
        "bytes",
    ],
)
def test_state_wake_time_status_cardinality_and_activation_bytes(
    fake, monkeypatch, change
):
    from trading_bot.arch133_verifier import activation as models

    original = operator.read_state_connection

    def read(connection):
        snapshot = original(connection)
        activation = models.ReviewPaperActivation.from_json(fake.act.to_json())
        if change == "cardinality":
            return replace(
                snapshot, activations=snapshot.activations * 2, wakes=snapshot.wakes * 2
            )
        if change == "bytes":
            return replace(
                snapshot,
                activations=(
                    (str(activation.activation_id), activation.to_json() + "\n"),
                ),
            )
        wake = models.ReviewPaperWake(
            activation=activation,
            updated_at=AT + timedelta(seconds=1) if change == "READY" else AT,
            state=models.ReviewPaperWakeState(change),
        )
        return replace(
            snapshot,
            wakes=(
                (str(activation.activation_id), str(wake.wake_id), wake.to_json(), 0),
            ),
        )

    monkeypatch.setattr(operator, "read_state_connection", read)
    assert operator.diagnose_publication_state_paper() == blocked("STATE_SEMANTICS")


@pytest.mark.parametrize(
    "failure",
    [
        "version",
        "cash",
        "key",
        "missing_column",
        "order",
        "duplicate_column",
        "rows",
        "fingerprint",
    ],
)
def test_paper_exact_metadata_columns_empty_rows_and_fingerprint(fake, failure):
    metadata = [["schema_version", "2"], ["starting_cash", "10000"]]
    columns, rows = list(operator.EMPTY_PAPER_COLUMNS), []
    host = fake.host
    if failure == "version":
        metadata[0][1] = "1"
    elif failure == "cash":
        metadata[1][1] = "9999"
    elif failure == "key":
        metadata.append(["unexpected", "value"])
    elif failure == "missing_column":
        columns.pop()
    elif failure == "order":
        columns.reverse()
    elif failure == "duplicate_column":
        columns[-1] = columns[0]
    elif failure == "rows":
        rows = [["private-row-material"] * len(columns)]
    else:
        host = replace(host, paper_predecessor_sha256="f" * 64)

    class Cursor:
        description = [(c,) for c in columns]

        def __iter__(self):
            return iter(metadata)

        def fetchall(self):
            return rows

    class Connection:
        def execute(self, statement):
            assert statement in {
                "SELECT key, value FROM metadata ORDER BY key",
                "SELECT * FROM review_fills ORDER BY filled_at, paper_trade_id",
            }
            return Cursor()

    with pytest.raises(ValueError):
        operator._paper_semantics(Connection(), fake.act, host)


@pytest.mark.parametrize(
    "drift",
    [
        "publication",
        "state",
        "paper",
        "namespace",
        "root",
        "security",
        "file_identity",
        "file_hash",
        "policy",
        "runtime",
        "principal",
    ],
)
def test_final_independent_reobservation_rejects_every_changed_fact(
    fake, monkeypatch, drift
):
    original = operator._paper_semantics
    calls = []

    def paper(*a):
        result = original(*a)
        if not calls:
            calls.append(1)
            if drift == "publication":
                monkeypatch.setattr(
                    operator, "_publication_path_read", lambda: (b"invalid", b"invalid")
                )
            elif drift == "state":
                monkeypatch.setattr(operator, "_state_semantics", lambda *a: None)
            elif drift == "paper":
                monkeypatch.setattr(operator, "_paper_semantics", lambda *a: "f" * 64)
            elif drift in {"namespace", "root", "runtime"}:
                fake.drift = drift
            elif drift == "security":
                fake.drift = "security"
            elif drift in {"file_identity", "file_hash"}:
                observe = retained_reads.file_snapshot

                def snapshot(handle, name):
                    identity, digest = observe(handle, name)
                    return (
                        (1, 2) if drift == "file_identity" else identity,
                        "f" * 64 if drift == "file_hash" else digest,
                    )

                monkeypatch.setattr(retained_reads, "file_snapshot", snapshot)
            elif drift == "policy":
                observe = file_policy.observe_file_policy
                monkeypatch.setattr(
                    file_policy,
                    "observe_file_policy",
                    lambda h: replace(observe(h), protected=False),
                )
            else:
                monkeypatch.setattr(
                    operator,
                    "_principal",
                    lambda: (_ for _ in ()).throw(RuntimeError(SECRET)),
                )
        return result

    monkeypatch.setattr(operator, "_paper_semantics", paper)
    assert operator.diagnose_publication_state_paper() == blocked("FINAL_REOBSERVATION")


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"user_sid": "S-1-5-18"},
        {"elevated": True},
        {"thread_token_present": True},
        {"token_type": 2},
        {"groups": ((token.ADMINISTRATORS_SID, 4),)},
    ],
)
def test_principal_reuses_exact_standard_token_enforcement(monkeypatch, change):
    observation = replace(
        token.TradingTokenObservation(binding.TRADING_SID, 1, False, False, ()),
        **change,
    )
    monkeypatch.setattr(
        token.WindowsTradingTokenObserver, "observe", lambda _: observation
    )
    if change:
        with pytest.raises(token.AuthorityPrincipalError):
            operator._principal()
    else:
        operator._principal()


@pytest.mark.parametrize(
    "flags,args,cache,passed",
    [
        (["-I", "-B"], [], False, True),
        (["-B"], [], False, False),
        (["-I"], [], False, False),
        (["-I", "-B"], ["--help"], False, False),
        (["-I", "-B"], [], True, False),
    ],
)
def test_synthetic_launcher_enforces_isolation_no_bytecode_and_private_absent_cache(
    tmp_path, flags, args, cache, passed
):
    launcher = tmp_path / "scripts/run.py"
    launcher.parent.mkdir()
    source = (
        ROOT / "scripts/run_arch133_publication_state_paper_diagnostic.py"
    ).read_text()
    source = source.replace(
        'Path(r"F:\\AI\\worktrees\\ai-trading-bot-robinhood-unattended-133n")',
        f"Path({str(tmp_path)!r})",
    )
    launcher.write_text(source, encoding="utf-8")
    package = tmp_path / "src/trading_bot/arch133_publication_diagnostic"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package.parent / "__init__.py").write_text("", encoding="utf-8")
    (package / "operator.py").write_text(
        "import sys\ndef main():\n"
        '    assert sys.pycache_prefix.endswith("no-pycache")\n'
        '    print("SYNTHETIC_PASS")\n    return 0\n',
        encoding="utf-8",
    )
    if cache:
        (tmp_path / "no-pycache").mkdir()
    result = subprocess.run(
        [sys.executable, *flags, str(launcher), *args], capture_output=True, text=True
    )
    assert result.returncode == (0 if passed else 3)
    assert (
        result.stdout == ("SYNTHETIC_PASS" if passed else operator.RUNTIME_BLOCK) + "\n"
    )
    assert result.stderr == ""
    assert not tuple(tmp_path.rglob("*.pyc"))


def test_read_only_runtime_projections_and_retained_pins_match_accepted_133m():
    accepted = ast.parse(
        (ROOT / "src/trading_bot/arch133_diagnostic/operator.py").read_text()
    )
    current = ast.parse(Path(operator.__file__).read_text())

    def functions(tree):
        return {
            n.name: ast.dump(n, include_attributes=False)
            for n in tree.body
            if isinstance(n, ast.FunctionDef)
        }

    old, new = functions(accepted), functions(current)
    for name in (
        "canonical",
        "_git",
        "_clean_source",
        "_diagnostic_source",
        "_bound_source",
        "_runtime",
        "_principal",
        "_discard_log",
        "_quiet_edges",
    ):
        assert new[name] == old[name]
    for name in (
        "BOUND_HEAD",
        "BOUND_TREE",
        "BOUND_CHECKOUTS",
        "ROOT_IDENTITY",
        "ROOT_SECURITY_SHA256",
        "FILE_HASHES",
        "ZERO_EFFECTS",
    ):

        def assignment(tree, name=name):
            return next(
                n
                for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
            )

        assert ast.dump(assignment(accepted), include_attributes=False) == ast.dump(
            assignment(current), include_attributes=False
        )


@pytest.mark.parametrize(
    "change",
    [
        {"identity": (1, 2)},
        {"filesystem": "FAT32"},
        {"reparse": True},
        {"protected": False},
        {"owner_sid": read_only.SYSTEM_SID},
        {"aces": read_only.ADMIN_ACES},
        {"aces": tuple(reversed(read_only.ROOT_ACES))},
    ],
)
def test_root_identity_and_closed_security_prerequisite(fake, change):
    fake.root = replace(fake.root, **change)
    assert operator.diagnose_publication_state_paper() is None
    assert fake.namespace_reads == 0


@pytest.mark.parametrize("names", [(), (("activation.json", 10),), (("extra", 9),)])
def test_exact_namespace_prerequisite(fake, names):
    fake.names = names
    assert operator.diagnose_publication_state_paper() is None
