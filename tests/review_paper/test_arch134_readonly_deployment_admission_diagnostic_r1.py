from __future__ import annotations

import ast
from dataclasses import replace
from types import SimpleNamespace

import pytest
from tests.review_paper.test_arch134_f1r1_d1s4_rename_free_direct_installation import (
    readonly_git as readonly_git,
)
from tests.review_paper.test_arch134_readonly_deployment_admission_diagnostic import (
    successor_fake,
)

from scripts import checkpoint_runner as runner
from scripts import source_authority as ownership
from trading_bot.supervised_release import deployment_admission as readonly
from trading_bot.supervised_release import (
    deployment_admission_diagnostic as predecessor,
)
from trading_bot.supervised_release import deployment_admission_diagnostic_r1 as r1
from trading_bot.supervised_release import deployment_admission_source as source

R1_BRANCH = predecessor.BRANCH.replace("-current", "-r1-current")


def dispatch_fake(monkeypatch, git, branch):
    invocation = SimpleNamespace(
        observer=replace(git.invocation.observer, reference=branch)
    )
    git.responses[("branch", "--show-current")] = branch.encode()
    git.responses[("rev-parse", "refs/remotes/origin/" + branch)] = (
        invocation.observer.head.encode()
    )
    calls = []

    def run(command, *, input, **kwargs):
        args = tuple(command[command.index("-C") + 2 :])
        calls.append(args)
        return SimpleNamespace(
            returncode=0, stderr=b"", stdout=git.query(*args, input_bytes=input)
        )

    monkeypatch.setattr(source.subprocess, "run", run)
    return invocation, calls


def test_consumed_predecessor_rejects_tracking_ref_after_exactly_nine_children(
    monkeypatch, readonly_git
):
    invocation, calls = dispatch_fake(monkeypatch, readonly_git, predecessor.BRANCH)
    reader = source.LocalGitReader(readonly_git.root)
    with pytest.raises(ValueError, match="^GIT_VOCABULARY$"):
        source.observe_source(reader, invocation)
    assert reader.diagnostic_process_starts == len(calls) == 9
    assert calls == [
        ("rev-parse", "--show-toplevel"),
        ("rev-parse", "--git-path", "info/grafts"),
        ("rev-parse", "HEAD"),
        ("rev-parse", "HEAD^{tree}"),
        ("branch", "--show-current"),
        ("remote", "get-url", "origin"),
        ("status", "--porcelain=v1", "--untracked-files=all"),
        ("diff", "--cached", "--name-only"),
        ("rev-parse", "--is-shallow-repository"),
    ]


def test_r1_explicit_tracking_binding_passes_nine_child_boundary(
    monkeypatch, readonly_git
):
    invocation, calls = dispatch_fake(monkeypatch, readonly_git, R1_BRANCH)
    reader = source.LocalGitReader(readonly_git.root, tracking_branch=R1_BRANCH)
    result = source.observe_source(reader, invocation)
    assert result.observer == invocation.observer
    assert reader.diagnostic_process_starts == len(calls) > 9
    assert calls[9] == ("rev-parse", "refs/remotes/origin/" + R1_BRANCH)


@pytest.mark.parametrize("binding", [None, R1_BRANCH])
def test_reader_tracking_vocabulary_is_exact_and_preserves_default(
    monkeypatch, tmp_path, binding
):
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=b"a" * 40)

    monkeypatch.setattr(source.subprocess, "run", run)
    reader = source.LocalGitReader(tmp_path, tracking_branch=binding)
    accepted = readonly.BRANCH if binding is None else binding
    reader.query("rev-parse", "refs/remotes/origin/" + accepted)
    assert reader.diagnostic_process_starts == len(calls) == 1
    for branch in {
        readonly.BRANCH,
        R1_BRANCH,
        predecessor.BRANCH,
        "feature/unrelated",
        R1_BRANCH + "-other",
        R1_BRANCH + "^{tree}",
    } - {accepted}:
        with pytest.raises(ValueError, match="^GIT_VOCABULARY$"):
            reader.query("rev-parse", "refs/remotes/origin/" + branch)
        assert reader.diagnostic_process_starts == len(calls) == 1
    # The fixed develop observation was already admitted by v1.
    reader.query("rev-parse", "refs/remotes/origin/develop")
    assert len(calls) == 2


@pytest.mark.parametrize("binding", ["feature/unrelated", predecessor.BRANCH, "", 1])
def test_unreviewed_constructor_binding_never_dispatches(
    monkeypatch, tmp_path, binding
):
    monkeypatch.setattr(
        source.subprocess, "run", lambda *a, **k: pytest.fail("dispatch")
    )
    with pytest.raises(ValueError, match="^GIT_VOCABULARY$"):
        source.LocalGitReader(tmp_path, tracking_branch=binding)


def r1_fake():
    fake = successor_fake()
    fake.invocation = r1.ReviewedInvocation(
        replace(fake.invocation.observer, reference=r1.BRANCH),
        fake.invocation.principal_sid,
        fake.invocation.elevated,
    )
    fake.source_value = replace(fake.source_value, observer=fake.invocation.observer)
    return fake


@pytest.mark.parametrize(
    "codes,expected",
    [
        (("GIT_VOCABULARY", "LOCAL_GIT_OBSERVATION"), r1.HOST_SOURCE_GIT_COLLECTION),
        (
            (
                "SOURCE_NAMESPACE",
                "SOURCE_REPARSE",
                "WORKTREE_IDENTITY",
                "GRAFTS_FORBIDDEN",
                "SOURCE_ADMISSION",
                "INDEX_FLAGS",
                "PARTIAL_CLONE",
            ),
            r1.HOST_SOURCE_CHECKOUT_POLICY,
        ),
        (
            (
                "SOURCE_LINEAGE",
                "FROZEN_LINEAGE",
                "R1_IMMUTABLE_CLOSURE",
                "SOURCE_LINEAGE_OR_CLOSURE",
            ),
            r1.HOST_SOURCE_LINEAGE,
        ),
        (
            (
                "TREE_BOUND",
                "TREE_OBJECT",
                "TREE_DUPLICATE",
                "COMPLETE_TREE_IDENTITY",
                "CANDIDATE_OBJECT",
                "INVENTORY_BOUND",
                "BLOB_HEADER",
                "BLOB_IDENTITY",
                "BLOB_TRAILING_DATA",
                "MANIFEST_POLICY_IDENTITY",
                "bounded immutable source namespace required",
                "noncanonical or incomplete source namespace",
            ),
            r1.HOST_SOURCE_INVENTORY,
        ),
    ],
)
@pytest.mark.parametrize("observation", [1, 2])
def test_closed_source_categories_on_both_observations(
    monkeypatch, codes, expected, observation
):
    for code in codes:
        fake = r1_fake()
        calls = []

        def collect(invocation, calls=calls, code=code, fake=fake):
            calls.append(invocation)
            if len(calls) == observation:
                raise ValueError(code)
            return fake.source_value

        monkeypatch.setattr(fake, "source", collect)
        if observation == 1:
            monkeypatch.setattr(
                fake, "read_session", lambda _: pytest.fail("host entered")
            )
        result = r1.admission(fake.invocation, fake, fake)
        assert result["diagnostic_code"] == expected
        assert result["effects"] == dict.fromkeys(readonly.ZERO_EFFECTS, 0)
        assert result["authority"] == dict.fromkeys(readonly.NO_AUTHORITY, False)
        payload = r1.encode_evidence(result)
        assert ('"' + code + '"').encode() not in payload
        r1.verify_evidence(payload, expected=result)


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("GIT_VOCABULARY"),
        ValueError("secret=0xdeadbeef"),
        ValueError("GIT_VOCABULARY", "secret"),
        KeyboardInterrupt("secret"),
        OSError("raw-native-stderr-path-token"),
    ],
)
def test_unknown_source_exceptions_remain_sanitized_host_unknown(monkeypatch, error):
    fake = r1_fake()

    def fail(_):
        raise error

    monkeypatch.setattr(fake, "source", fail)
    result = r1.admission(fake.invocation, fake, fake)
    assert result["diagnostic_code"] == r1.HOST_UNKNOWN
    payload = r1.encode_evidence(result)
    assert b"secret" not in payload and b"raw-native" not in payload
    assert b"GIT_VOCABULARY" not in payload


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("index", r1.HOST_SOURCE_CHECKOUT_POLICY),
        ("lineage", r1.HOST_SOURCE_LINEAGE),
        ("inventory", r1.HOST_SOURCE_INVENTORY),
        ("collection", r1.HOST_SOURCE_GIT_COLLECTION),
    ],
)
def test_actual_source_reader_failures_are_localized_before_host_entry(
    monkeypatch, readonly_git, mutation, expected
):
    fake = r1_fake()
    invocation, _ = dispatch_fake(monkeypatch, readonly_git, r1.BRANCH)
    fake.invocation = r1.ReviewedInvocation(
        invocation.observer, fake.invocation.principal_sid, False
    )
    if mutation == "index":
        readonly_git.responses[("ls-files", "-v", "-z")] = b"h hidden\0"
    elif mutation == "lineage":
        readonly_git.responses[
            ("merge-base", readonly.DESIGN.head, invocation.observer.head)
        ] = b"f" * 40
    elif mutation == "inventory":
        readonly_git.batch += b"raw-secret-trailing-data"
    else:
        monkeypatch.setattr(
            source.subprocess,
            "run",
            lambda *a, **k: SimpleNamespace(
                returncode=1, stdout=b"secret stdout", stderr=b"raw stderr 0xdeadbeef"
            ),
        )
    reader = source.LocalGitReader(readonly_git.root, tracking_branch=r1.BRANCH)
    monkeypatch.setattr(fake, "source", lambda inv: source.observe_source(reader, inv))
    monkeypatch.setattr(fake, "read_session", lambda _: pytest.fail("host entered"))
    result = r1.admission(fake.invocation, fake, fake)
    assert result["diagnostic_code"] == expected
    assert b"secret" not in r1.encode_evidence(result)
    assert b"stderr" not in r1.encode_evidence(result)


def test_source_policy_validation_and_pass_effect_ceiling():
    fake = r1_fake()
    result = r1.admission(fake.invocation, fake, fake)
    assert result["status"] == "PASS" and result["reason"] == readonly.READY
    assert result["effects"] == dict.fromkeys(readonly.ZERO_EFFECTS, 0)
    assert result["authority"] == dict.fromkeys(readonly.NO_AUTHORITY, False)
    fake.source_value = replace(fake.source_value, r1_state="UNCONSUMED")
    assert (
        r1.admission(fake.invocation, fake, fake)["diagnostic_code"]
        == r1.HOST_SOURCE_LINEAGE
    )


def test_r1_registration_and_exact_security_overlay():
    root = runner.Path(runner.__file__).resolve().parents[1]
    spec = runner._checkpoint_specs()[r1.CHECKPOINT]
    assert spec.remote_branch == r1.BRANCH == R1_BRANCH == source.R1_TRACKING_BRANCH
    assert spec.execute is None
    assert spec.preflight is runner._arch134_readonly_diagnostic_r1_preflight
    assert (
        runner.resolve_ci_checkpoint(runner._checkpoint_specs(), r1.BRANCH, "push")
        == r1.CHECKPOINT
    )
    assert runner.CI_CERTIFICATION_PROFILES[r1.CHECKPOINT] == "robinhood"
    assert r1.CHECKPOINT in runner.CURRENT_ACTIVE_CI_CHECKPOINTS
    assert runner._arch134_readonly_diagnostic_r1_authority_check(root) == ()
    path = "src/trading_bot/supervised_release/deployment_admission_source.py"
    before = runner.ARCH134_READONLY_DIAGNOSTIC_R1_BLOB_PREDECESSORS[path]
    assert runner.READONLY_SOURCE_PINS[path] == before
    assert ownership.blob_matches(root, root / path, before)
    assert not ownership.blob_matches(root, root / path, "0" * 40)
    assert b"tracking_branch" not in ownership.historical_blob(root, before)


@pytest.mark.parametrize(
    "reference", [readonly.BRANCH, predecessor.BRANCH, "develop", "feature/unrelated"]
)
def test_r1_invocation_requires_exact_r1_branch(reference):
    fake = r1_fake()
    with pytest.raises(ValueError, match="^REVIEWED_OBSERVER_SOURCE_REQUIRED$"):
        r1.ReviewedInvocation(
            replace(fake.invocation.observer, reference=reference),
            fake.invocation.principal_sid,
            False,
        )


def test_r1_host_entry_binds_reviewed_branch_without_host_or_process_dispatch(
    monkeypatch,
):
    from trading_bot.supervised_release import (
        deployment_admission_diagnostic_r1_host as host,
    )

    fake = r1_fake()
    for name, value in {
        "HEAD": fake.invocation.observer.head,
        "TREE": fake.invocation.observer.tree,
        "REFERENCE": r1.BRANCH,
        "PRINCIPAL_SID": fake.invocation.principal_sid,
        "ELEVATED": "false",
    }.items():
        monkeypatch.setenv(host.PREFIX + name, value)
    captured = []

    def collect(root, reader):
        assert reader._tracking_branch == r1.BRANCH
        assert reader.diagnostic_process_starts == 0
        captured.append(reader)
        return fake

    fake.diagnostic_process_starts = 0
    monkeypatch.setattr(host, "HostCollectors", collect)
    monkeypatch.setattr(host, "HostReader", lambda collectors: fake)
    monkeypatch.setattr(
        source.subprocess, "run", lambda *a, **k: pytest.fail("process")
    )
    result = host.preflight()
    assert result["status"] == "PASS"
    assert result["diagnostic_process_starts"] == 0
    assert len(captured) == 1


def test_r1_runner_rejects_existing_evidence_before_observer(monkeypatch, tmp_path):
    monkeypatch.setattr(
        runner, "_arch134_readonly_diagnostic_r1_authority_check", lambda _: ()
    )
    spec = replace(
        runner._checkpoint_specs()[r1.CHECKPOINT],
        authority_check=lambda _: (),
        preflight=lambda: pytest.fail("observer"),
    )
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: {spec.name: spec})
    with pytest.raises(RuntimeError, match="fresh evidence root required"):
        runner.preflight_checkpoint(
            spec, repo_root=tmp_path / "source", evidence_root=tmp_path
        )


def test_future_operator_contract_is_complete_and_does_not_precreate_evidence():
    root = runner.Path(runner.__file__).resolve().parents[1]
    doc = (
        root
        / "docs/architecture"
        / "134-fresh-successor-readonly-deployment-admission-diagnostic-r1.md"
    ).read_text(encoding="utf-8")
    block = doc.split("```powershell\n", 1)[1].split("```", 1)[0]
    assert block.startswith("& {") and block.rstrip().endswith("}")
    for suffix in ("HEAD", "TREE", "REFERENCE", "PRINCIPAL_SID", "ELEVATED"):
        assert "$env:AI_TRADING_BOT_ARCH134_ADMISSION_" + suffix in block
    assert "WindowsIdentity]::GetCurrent()" in block
    assert ".User.Value" in block and ".IsInRole(" in block
    assert "[guid]::NewGuid()" in block
    assert "--evidence-root $EvidenceRoot" in block
    assert "New-Item" not in block and "mkdir" not in block
    assert "ELEVATED = 'true'" not in block
    assert r1.BRANCH in block and r1.CHECKPOINT in block


@pytest.mark.parametrize("count", [False, -1, 1001, "9"])
def test_r1_pass_process_count_is_optional_bounded_and_not_an_effect_bypass(count):
    fake = r1_fake()
    result = r1.admission(fake.invocation, fake, fake)
    valid = {**result, "diagnostic_process_starts": 9}
    r1.verify_evidence(r1.encode_evidence(valid), expected=valid)
    with pytest.raises(ValueError):
        r1.encode_evidence({**result, "diagnostic_process_starts": count})
    with pytest.raises(ValueError):
        r1.encode_evidence({**valid, "raw_exception": "secret"})
    valid["effects"]["production_writes"] = 1
    with pytest.raises(ValueError):
        r1.encode_evidence(valid)


def test_source_admission_and_default_branch_policy_keep_predecessor_ast():
    root = runner.Path(runner.__file__).resolve().parents[1]
    path = "src/trading_bot/supervised_release/deployment_admission_source.py"
    old = runner.ARCH134_READONLY_DIAGNOSTIC_R1_BLOB_PREDECESSORS[path]
    before = ast.parse(ownership.historical_blob(root, old).decode("utf-8"))
    after = ast.parse((root / path).read_text(encoding="utf-8"))
    for name in (
        "invocation_branch",
        "observe_source",
        "require_checkout_path",
        "verify_tree_listing",
        "manifest_for",
    ):

        def function(tree, name=name):
            return next(
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == name
            )

        assert ast.dump(function(before)) == ast.dump(function(after))
