"""133-M fake-only stage diagnostic; production state and credentials unreachable."""

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
from trading_bot.arch133_diagnostic import operator
from trading_bot.arch133_verifier import activation as models
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


def blocked(stage):
    return operator.stage_result(stage)


def test_pass_is_canonical_bounded_read_only_and_reobserved(fake):
    before = {
        name: (binding.PAPER_PATH.parent / name).read_bytes()
        for name in retained_reads.FINAL_NAMES
    }
    result = operator.diagnose_post_publication()
    assert result == operator.stage_result("PRE_CREDENTIAL_COMPLETE", passed=True)
    assert set(result) == {
        "schema",
        "status",
        "reason",
        "stage",
        *operator.ZERO_EFFECTS,
    }
    assert all(result[name] == 0 for name in operator.ZERO_EFFECTS)
    assert fake.root_reads == fake.namespace_reads == fake.runtime_reads == 2
    assert fake.calls.count("principal") == 2
    assert before == {
        name: (binding.PAPER_PATH.parent / name).read_bytes()
        for name in retained_reads.FINAL_NAMES
    }
    assert len(operator.canonical(result)) < 1024
    assert SECRET not in operator.canonical(result)


@pytest.mark.parametrize("failure", range(7))
def test_each_stage_blocks_and_never_runs_later_stage(
    fake, monkeypatch, failure, capfd
):
    stages = (
        (operator, "_runtime", "RUNTIME_SOURCE"),
        (operator, "_principal", "TRADING_TOKEN"),
        (read_only, "inspect_directory_security", "ROOT_SECURITY"),
        (retained_reads, "namespace", "NAMESPACE_FILES"),
        (operator, "_publication", "PUBLICATION_STATE_PAPER"),
        (operator, "build_unattended_scheduler_spec", "SCHEDULER_SPEC"),
    )
    calls = []
    for index, (module, name, _stage) in enumerate(stages):
        original = getattr(module, name)

        def edge(*args, index=index, original=original, **kwargs):
            calls.append(index)
            if index == failure or (failure == 6 and calls.count(index) == 2):
                print(SECRET)
                print(SECRET, file=sys.stderr)
                logging.error(SECRET)
                os.write(2, SECRET.encode())
                raise RuntimeError(SECRET)
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, edge)
    expected = stages[failure][2] if failure < 6 else "FINAL_REOBSERVATION"
    assert operator.diagnose_post_publication() == blocked(expected)
    assert calls == (list(range(failure + 1)) if failure < 6 else [0, 1, 2, 3, 4, 5, 4])
    captured = capfd.readouterr()
    assert SECRET not in captured.out + captured.err
    closes = [x[1] for x in fake.calls if isinstance(x, tuple) and x[0] == "close"]
    assert len(closes) == len(set(closes))


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
def test_root_disagreement_blocks(fake, change):
    fake.root = replace(fake.root, **change)
    assert operator.diagnose_post_publication() == blocked("ROOT_SECURITY")
    assert fake.namespace_reads == 0


@pytest.mark.parametrize("names", [(), (("activation.json", 10),), (("extra", 9),)])
def test_exact_namespace(fake, names):
    fake.names = names
    assert operator.diagnose_post_publication() == blocked("NAMESPACE_FILES")


@pytest.mark.parametrize(
    "drift,stage",
    [
        ("security", "ROOT_SECURITY"),
        ("hash", "NAMESPACE_FILES"),
        ("root", "FINAL_REOBSERVATION"),
        ("namespace", "FINAL_REOBSERVATION"),
        ("runtime", "FINAL_REOBSERVATION"),
        ("close", "FINAL_REOBSERVATION"),
    ],
)
def test_drift_has_fixed_stage(fake, drift, stage):
    fake.drift = drift
    assert operator.diagnose_post_publication() == blocked(stage)


@pytest.mark.parametrize(
    "failed_handle", [retained_reads.TARGET_PATH, *retained_reads.FINAL_NAMES]
)
@pytest.mark.parametrize("earlier_failure", [False, True])
def test_all_handles_close_exactly_once_and_failure_overrides_stage(
    fake, monkeypatch, failed_handle, earlier_failure
):
    closed = []

    def close(handle):
        closed.append(handle)
        if handle == failed_handle:
            raise RuntimeError(SECRET)

    monkeypatch.setattr(read_only, "close_handle", close)
    if earlier_failure:
        monkeypatch.setattr(
            operator,
            "_publication",
            lambda _: (_ for _ in ()).throw(ValueError(SECRET)),
        )
    assert operator.diagnose_post_publication() == blocked("FINAL_REOBSERVATION")
    assert closed == [*reversed(retained_reads.FINAL_NAMES), retained_reads.TARGET_PATH]
    assert fake.runtime_reads == 1


@pytest.mark.parametrize("name", retained_reads.FINAL_NAMES)
@pytest.mark.parametrize("edge", ["open", "snapshot", "policy"])
def test_partial_acquisition_closes_only_successfully_opened_handles(
    fake, monkeypatch, name, edge
):
    module, function = {
        "open": (retained_reads, "open_retained_file"),
        "snapshot": (retained_reads, "file_snapshot"),
        "policy": (file_policy, "observe_file_policy"),
    }[edge]
    original = getattr(module, function)

    def fail(*args):
        if name in args:
            raise ValueError(SECRET)
        return original(*args)

    monkeypatch.setattr(module, function, fail)
    assert operator.diagnose_post_publication() == blocked("NAMESPACE_FILES")
    index = retained_reads.FINAL_NAMES.index(name) + (edge != "open")
    expected = [
        *reversed(retained_reads.FINAL_NAMES[:index]),
        retained_reads.TARGET_PATH,
    ]
    assert [
        x[1] for x in fake.calls if isinstance(x, tuple) and x[0] == "close"
    ] == expected


def test_only_fixed_target_root_and_held_files_are_observed_twice(fake, monkeypatch):
    observed = []
    for module, name in (
        (read_only, "inspect_directory_security"),
        (retained_reads, "file_snapshot"),
        (file_policy, "observe_file_policy"),
    ):
        original = getattr(module, name)

        def observe(*args, original=original, name=name):
            observed.append((name, args))
            return original(*args)

        monkeypatch.setattr(module, name, observe)
    assert operator.diagnose_post_publication()["status"] == "PASS"
    assert [x for x in fake.calls if isinstance(x, tuple) and x[0] == "open"] == [
        ("open", retained_reads.TARGET_PATH, {})
    ]
    assert (
        observed.count(
            (
                "inspect_directory_security",
                (retained_reads.TARGET_PATH, retained_reads.TARGET_PATH),
            )
        )
        == 2
    )
    for name in retained_reads.FINAL_NAMES:
        assert observed.count(("file_snapshot", (name, name))) == 2
        assert observed.count(("observe_file_policy", (name,))) == 2


@pytest.mark.parametrize(
    "drift",
    [
        "publication",
        "paper",
        "namespace",
        "root",
        "security",
        "file_identity",
        "file_hash",
        "policy",
        "principal",
    ],
)
def test_independent_final_reobservation(fake, monkeypatch, drift):
    build = operator.build_unattended_scheduler_spec

    def scheduler(activation):
        result = build(activation)
        if drift in ("publication", "paper"):
            function = "_publication" if drift == "publication" else "_paper"
            monkeypatch.setattr(operator, function, lambda *a: None)
        elif drift == "namespace":
            monkeypatch.setattr(retained_reads, "namespace", lambda _: ())
        elif drift in ("root", "security"):
            monkeypatch.setattr(
                read_only,
                "inspect_directory_security",
                lambda *a: (
                    replace(fake.root, identity=(5, 6))
                    if drift == "root"
                    else fake.root,
                    "e" * 64 if drift == "security" else operator.ROOT_SECURITY_SHA256,
                ),
            )
        elif drift in ("file_identity", "file_hash"):
            observe = retained_reads.file_snapshot

            def snapshot(handle, name):
                identity, digest = observe(handle, name)
                return (
                    (5, 6) if drift == "file_identity" else identity,
                    "e" * 64 if drift == "file_hash" else digest,
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
                lambda: (_ for _ in ()).throw(ValueError(SECRET)),
            )
        return result

    monkeypatch.setattr(operator, "build_unattended_scheduler_spec", scheduler)
    assert operator.diagnose_post_publication() == blocked("FINAL_REOBSERVATION")


@pytest.mark.parametrize("args", [["--help"], ["--root", SECRET], ["verify"], [SECRET]])
def test_zero_args_only(monkeypatch, args, capsys):
    monkeypatch.setattr(
        operator, "diagnose_post_publication", lambda: pytest.fail("diagnostic reached")
    )
    assert operator.main(args) == 3
    raw = capsys.readouterr().out
    assert raw == operator.canonical(blocked("RUNTIME_SOURCE")) + "\n"


def test_cli_pass_and_block(fake, capsys):
    assert operator.main([]) == 0
    assert (
        capsys.readouterr().out
        == operator.canonical(
            operator.stage_result("PRE_CREDENTIAL_COMPLETE", passed=True)
        )
        + "\n"
    )
    fake.drift = "hash"
    assert operator.main([]) == 3
    assert json.loads(capsys.readouterr().out) == blocked("NAMESPACE_FILES")


def test_pure_scheduler_construction(fake, monkeypatch):
    calls = []
    build = operator.build_unattended_scheduler_spec

    def scheduler(activation):
        result = build(activation)
        calls.append(result)
        assert result.arguments == ("-I", "-B", str(binding.LAUNCHER))
        assert result.installation_authorized is False
        return result

    monkeypatch.setattr(operator, "build_unattended_scheduler_spec", scheduler)
    assert operator.diagnose_post_publication()["status"] == "PASS"
    assert len(calls) == 1


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
def test_consumed_authority_credential_free(fake, monkeypatch, state_name):
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
    assert operator.diagnose_post_publication() == blocked("PUBLICATION_STATE_PAPER")


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


@pytest.mark.parametrize("which", ["ACTIVATION_PATH", "BINDING_PATH"])
def test_noncanonical_publication_credential_free(fake, which):
    path = getattr(binding, which)
    path.write_bytes(path.read_bytes() + b"\n")
    operator.FILE_HASHES[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert operator.diagnose_post_publication() == blocked("PUBLICATION_STATE_PAPER")


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
        assert operator.diagnose_post_publication() == blocked(
            "PUBLICATION_STATE_PAPER"
        )


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


BOUND_DOCS_CHECKOUT = (
    "65f0d40217f8ce129224531a5151f4acea889d89",
    "16cb734cbeaa9e97aaf9e2d521d922fbbc7b7ae2",
)


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
        ROOT / "scripts/run_arch133_post_publication_stage_diagnostic.py",
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
def test_binding_disagreements_credential_free(fake, wrong):
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
    assert operator.diagnose_post_publication() == blocked("PUBLICATION_STATE_PAPER")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE metadata SET value='1' WHERE key='schema_version'",
        "INSERT INTO metadata VALUES ('unexpected','value')",
        "UPDATE metadata SET value='9999' WHERE key='starting_cash'",
    ],
)
def test_paper_schema_and_metadata_credential_free(fake, statement):
    import sqlite3

    with sqlite3.connect(binding.PAPER_PATH) as connection:
        connection.execute(statement)
    operator.FILE_HASHES["paper.sqlite"] = hashlib.sha256(
        binding.PAPER_PATH.read_bytes()
    ).hexdigest()
    assert operator.diagnose_post_publication() == blocked("PUBLICATION_STATE_PAPER")


def test_wake_created_at_and_cardinality_credential_free(fake, monkeypatch):
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
    assert operator.diagnose_post_publication() == blocked("PUBLICATION_STATE_PAPER")


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


def test_independent_projections_match_accepted_verifier_ast():
    accepted = ast.parse(
        (ROOT / "src/trading_bot/arch133_verifier/operator.py").read_text(
            encoding="utf-8"
        )
    )
    diagnostic = ast.parse(Path(operator.__file__).read_text(encoding="utf-8"))

    def definitions(tree):
        return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    old, new = definitions(accepted), definitions(diagnostic)
    for name in (
        "canonical",
        "_git",
        "_clean_source",
        "_bound_source",
        "_principal",
        "_paper",
        "_publication",
        "_discard_log",
    ):
        assert ast.dump(new[name], include_attributes=False) == ast.dump(
            old[name], include_attributes=False
        ), name
    prior = old["_verifier_source"]
    prior.name = "_diagnostic_source"
    assert ast.dump(new["_diagnostic_source"], include_attributes=False) == ast.dump(
        prior, include_attributes=False
    )
    for name in (
        "BOUND_HEAD",
        "BOUND_TREE",
        "BOUND_CHECKOUTS",
        "ROOT_IDENTITY",
        "ROOT_SECURITY_SHA256",
        "FILE_HASHES",
    ):

        def assignment(tree, name=name):
            return next(
                n
                for n in tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
            )

        assert ast.dump(assignment(accepted), include_attributes=False) == ast.dump(
            assignment(diagnostic), include_attributes=False
        )


def test_fresh_import_closure_excludes_credentials_and_effect_capabilities(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys, json, ctypes\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "def reject(*a, **k): raise AssertionError('native import effect')\n"
        "ctypes.WinDLL = reject\n"
        "import trading_bot.arch133_diagnostic.operator\n"
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
    assert names == sorted(checkpoint_runner.ARCH133_DIAGNOSTIC_MODULES)
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
    assert set(checkpoint_runner.ARCH133_DIAGNOSTIC_PINS) == {
        *paths,
        "scripts/run_arch133_post_publication_stage_diagnostic.py",
    }


@pytest.mark.parametrize("args", [[], ["--root", SECRET]])
def test_copied_launcher_fails_before_trading_import(tmp_path, args):
    path = tmp_path / "run.py"
    path.write_text(
        (ROOT / "scripts/run_arch133_post_publication_stage_diagnostic.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(path), *args], capture_output=True, text=True
    )
    assert result.returncode == 3
    assert result.stdout == operator.canonical(blocked("RUNTIME_SOURCE")) + "\n"
    assert result.stderr == ""
    assert not (tmp_path / "no-pycache").exists()


def test_fixed_paths_runtime_hashes_and_accepted_launchers_unchanged():
    assert (
        str(operator.SOURCE_ROOT)
        == r"F:\AI\worktrees\ai-trading-bot-robinhood-unattended-133m"
    )
    assert operator.SOURCE_BRANCH == "feature/robinhood-unattended-review-paper-133m"
    assert (
        operator.LAUNCHER
        == operator.SOURCE_ROOT
        / "scripts/run_arch133_post_publication_stage_diagnostic.py"
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


def test_git_is_local_read_only_bounded_and_environment_is_scrubbed(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setenv("GIT_DIR", SECRET)
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", SECRET)

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(stdout="a" * 40 + "\n", stderr="")

    monkeypatch.setattr(operator.subprocess, "run", run)
    assert operator._git(tmp_path, "rev-parse", "HEAD") == "a" * 40
    argv, kwargs = calls[0]
    assert argv == [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(tmp_path),
        "rev-parse",
        "HEAD",
    ]
    assert not any(k.upper().startswith("GIT_") for k in kwargs["env"])
    assert kwargs["input"] == "" and kwargs["timeout"] == 10
    assert kwargs["capture_output"] is kwargs["check"] is True


def test_missing_diagnostic_cache_namespace_required(tmp_path, monkeypatch):
    cache = tmp_path / "no-pycache"
    cache.mkdir()
    monkeypatch.setattr(operator, "NO_PYCACHE", cache)
    with monkeypatch.context() as context:
        context.setattr(sys, "argv", [str(operator.LAUNCHER)])
        context.setattr(sys, "platform", "win32")
        context.setattr(sys, "flags", SimpleNamespace(isolated=True))
        context.setattr(sys, "dont_write_bytecode", True)
        context.setattr(sys, "pycache_prefix", str(cache))
        with pytest.raises(ValueError):
            operator._runtime()


@pytest.mark.parametrize("name", retained_reads.FINAL_NAMES)
@pytest.mark.parametrize("drift", ["identity", "hash", "policy"])
def test_retained_identity_hash_policy_reject_in_namespace_stage(
    fake, monkeypatch, name, drift
):
    if drift == "policy":
        observe = file_policy.observe_file_policy

        def policy(handle):
            value = observe(handle)
            return replace(value, protected=False) if handle == name else value

        monkeypatch.setattr(file_policy, "observe_file_policy", policy)
    else:
        observe = retained_reads.file_snapshot

        def snapshot(handle, leaf):
            identity, digest = observe(handle, leaf)
            if leaf == name:
                identity = (1, 2) if drift == "identity" else identity
                digest = "e" * 64 if drift == "hash" else digest
            return identity, digest

        monkeypatch.setattr(retained_reads, "file_snapshot", snapshot)
    assert operator.diagnose_post_publication() == blocked("NAMESPACE_FILES")


@pytest.mark.parametrize("final", [False, True])
@pytest.mark.parametrize("drift", ["sid", "elevated", "impersonating", "administrator"])
def test_exact_observer_token_admission_initial_and_final(
    fake, monkeypatch, final, drift
):
    monkeypatch.setattr(operator, "_principal", ACTUAL_PRINCIPAL)
    calls = []
    observation = token.TradingTokenObservation(
        binding.TRADING_SID, 1, False, False, ()
    )
    bad = replace(
        observation,
        **{
            "sid": {"user_sid": "S-1-5-18"},
            "elevated": {"elevated": True},
            "impersonating": {"thread_token_present": True},
            "administrator": {"groups": ((token.ADMINISTRATORS_SID, 4),)},
        }[drift],
    )

    def observe(_):
        calls.append("token")
        return bad if not final or len(calls) == 2 else observation

    monkeypatch.setattr(token.WindowsTradingTokenObserver, "observe", observe)
    expected = "FINAL_REOBSERVATION" if final else "TRADING_TOKEN"
    assert operator.diagnose_post_publication() == blocked(expected)
    assert len(calls) == (2 if final else 1)
    if final:
        assert fake.runtime_reads == 2
        assert (
            len([x for x in fake.calls if isinstance(x, tuple) and x[0] == "close"])
            == 5
        )
    else:
        assert not fake.calls


ACTUAL_PRINCIPAL = operator._principal
