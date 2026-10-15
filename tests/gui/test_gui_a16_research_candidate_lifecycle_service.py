"""Exact canonical parsers, bounded once-only reads and fail-closed linkage."""

import io
import json
from dataclasses import fields, is_dataclass, replace
from pathlib import Path

import pytest
from tests.gui.test_gui_a16_research_candidate_lifecycle_models import (
    local_artifacts,
    write_artifacts,
)

from trading_bot.gui import research_candidate_lifecycle_service as m
from trading_bot.gui.research_candidate_lifecycle_models import (
    LOCAL_VERIFICATION_SCOPE,
)
from trading_bot.gui.research_candidate_lifecycle_models import (
    ResearchCandidateLifecyclePageStatus as Status,
)


def test_exact_five_parsers_and_verifier_unmodified_text_once_cached(
    tmp_path, monkeypatch
):
    artifacts = local_artifacts()
    paths = write_artifacts(tmp_path, artifacts)
    texts = [artifact.to_json() for artifact in artifacts]
    calls, opens, reads = [], [], []
    original_open = Path.open

    class Stream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def read(self, count):
            reads.append(count)
            return self.stream.read(count)

    def opened(path, mode):
        assert mode == "rb" and path in paths
        opens.append(path)
        return Stream(original_open(path, mode))

    for index, artifact in enumerate(artifacts):
        model = type(artifact)
        original_parser = model.from_json

        def parsed(cls, text, _index=index, _original=original_parser):
            assert text == texts[_index]
            calls.append(_index)
            return _original(text)

        monkeypatch.setattr(model, "from_json", classmethod(parsed))
    original_verify = m.verify_shadow_research_candidate

    def verify(*args):
        calls.append("linkage")
        assert args == (artifacts[4], *artifacts[:4])
        return original_verify(*args)

    monkeypatch.setattr(m, "verify_shadow_research_candidate", verify)
    monkeypatch.setattr(Path, "open", opened)
    service = m.ResearchCandidateLifecycleInspectionService(*paths)
    state = service.get_research_candidate_lifecycle_state()
    assert state.status is Status.AVAILABLE
    assert state is service.get_research_candidate_lifecycle_state()
    assert calls == [0, 1, 2, 3, 4, "linkage"]
    assert opens == list(paths)
    assert reads == [m.MAX_LIFECYCLE_ARTIFACT_BYTES + 1] * 5
    assert set(vars(service)) == {"_paths", "_cached"}


@pytest.mark.parametrize("index", range(5))
@pytest.mark.parametrize(
    "mutation",
    [
        "utf8",
        "oversize",
        "noncanonical",
        "duplicate",
        "forged",
        "unknown",
        "missing",
        "unrelated",
    ],
)
def test_configured_failures_cached_and_bounded(tmp_path, monkeypatch, index, mutation):
    artifacts = local_artifacts()
    paths = write_artifacts(tmp_path, artifacts)
    text = artifacts[index].to_json()
    raw = json.loads(text)
    identity = (
        "candidate_id",
        "binding_id",
        "observation_batch_id",
        "qualification_id",
        "candidate_id",
    )[index]
    if mutation == "utf8":
        payload = b"\xff"
    elif mutation == "oversize":
        payload = b"x" * (m.MAX_LIFECYCLE_ARTIFACT_BYTES + 1)
    elif mutation == "noncanonical":
        payload = (text + "\n").encode()
    elif mutation == "duplicate":
        payload = (text[:-1] + f',"{identity}":"{raw[identity]}"' + "}").encode()
    elif mutation == "unrelated":
        payload = local_artifacts(seed=100)[index].to_json().encode()
    else:
        if mutation == "forged":
            raw[identity] = "00000000-0000-0000-0000-000000000001"
        elif mutation == "unknown":
            raw["private_path"] = "C:\\private\\sensitive.json"
        else:
            raw.pop(identity)
        payload = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    paths[index].write_bytes(payload)
    opens = []
    original = Path.open

    def opened(path, *args, **kwargs):
        opens.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    service = m.ResearchCandidateLifecycleInspectionService(*paths)
    state = service.get_research_candidate_lifecycle_state()
    assert state.status is Status.ATTENTION and state.evidence is None
    assert state is service.get_research_candidate_lifecycle_state()
    assert len(opens) == len(set(opens)) <= 5
    assert str(tmp_path) not in repr(state) and "private" not in repr(state)
    assert "Traceback" not in state.message


@pytest.mark.parametrize("index", [0, 4])
@pytest.mark.parametrize(
    "stage",
    [
        "BACKTESTED",
        "EXPERIMENTAL",
        "PAPER_CANDIDATE",
        "AWAITING_HUMAN_PROMOTION",
        "SHADOW",
        "WALK_FORWARD_PASSED",
    ],
)
def test_wrong_stage_is_not_materialized(tmp_path, index, stage):
    artifacts = local_artifacts()
    if stage == artifacts[index].stage.value:
        return
    paths = write_artifacts(tmp_path, artifacts)
    text = (
        artifacts[index]
        .to_json()
        .replace(f'"stage":"{artifacts[index].stage.value}"', f'"stage":"{stage}"')
    )
    paths[index].write_text(text, encoding="utf-8")
    assert (
        m.ResearchCandidateLifecycleInspectionService(*paths)
        .get_research_candidate_lifecycle_state()
        .status
        is Status.ATTENTION
    )


@pytest.mark.parametrize(
    "path",
    [
        r"\\server\share\file.json",
        r"\\?\C:\file.json",
        r"\\.\pipe\file.json",
        "https://example.com/file.json",
        "file:///C:/file.json",
        "selected.json:stream",
        "C:selected.json",
        "selected.txt",
        "directory",
        "selected\n.json",
        "selected\x7f.json",
    ],
)
def test_all_paths_prevalidated_before_any_open(tmp_path, monkeypatch, path):
    paths = (*write_artifacts(tmp_path)[:4], Path(path))

    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported path must not cause any file open")

    monkeypatch.setattr(Path, "open", forbidden)
    service = m.ResearchCandidateLifecycleInspectionService(*paths)
    assert service.get_research_candidate_lifecycle_state().status is Status.ATTENTION


@pytest.mark.parametrize(
    "failure", [OSError, PermissionError, RuntimeError, RecursionError, UnicodeError]
)
def test_raw_exception_never_escapes_and_failure_is_cached(
    tmp_path, monkeypatch, failure
):
    paths = write_artifacts(tmp_path)
    calls = []

    def failed(*args, **kwargs):
        calls.append(1)
        raise failure("C:\\private\\selected.json RAW JSON SECRET")

    monkeypatch.setattr(Path, "open", failed)
    service = m.ResearchCandidateLifecycleInspectionService(*paths)
    state = service.get_research_candidate_lifecycle_state()
    assert state is service.get_research_candidate_lifecycle_state()
    assert state.status is Status.ATTENTION and calls == [1]
    assert all(word not in repr(state) for word in ("private", "SECRET", "RAW JSON"))


def test_missing_file_and_directory_are_attention(tmp_path):
    paths = write_artifacts(tmp_path)
    paths[0].unlink()
    assert (
        m.ResearchCandidateLifecycleInspectionService(*paths)
        .get_research_candidate_lifecycle_state()
        .status
        is Status.ATTENTION
    )
    paths[0].mkdir()
    assert (
        m.ResearchCandidateLifecycleInspectionService(*paths)
        .get_research_candidate_lifecycle_state()
        .status
        is Status.ATTENTION
    )


def test_exact_bound_is_read_once_and_passed_without_normalization(
    tmp_path, monkeypatch
):
    paths = write_artifacts(tmp_path)
    payload = b"x" * m.MAX_LIFECYCLE_ARTIFACT_BYTES
    sizes = []

    class Bounded(io.BytesIO):
        def read(self, count):
            sizes.append(count)
            return super().read(count)

    monkeypatch.setattr(Path, "open", lambda *args: Bounded(payload))
    monkeypatch.setattr(
        m.WalkForwardPassedResearchStrategyCandidate,
        "from_json",
        lambda text: (
            (_ for _ in ()).throw(ValueError())
            if text == payload.decode()
            else pytest.fail("Text was modified")
        ),
    )
    state = m.ResearchCandidateLifecycleInspectionService(
        *paths
    ).get_research_candidate_lifecycle_state()
    assert state.status is Status.ATTENTION
    assert sizes == [m.MAX_LIFECYCLE_ARTIFACT_BYTES + 1]


def test_no_raw_or_domain_values_survive_adaptation(tmp_path):
    service = m.ResearchCandidateLifecycleInspectionService(*write_artifacts(tmp_path))
    state = service.get_research_candidate_lifecycle_state()

    def inspect(value):
        assert not isinstance(value, (Path, bytes, dict, BaseException))
        assert not type(value).__module__.startswith("trading_bot.experiments")
        if is_dataclass(value):
            for item in fields(value):
                inspect(getattr(value, item.name))
        elif isinstance(value, tuple):
            for item in value:
                inspect(item)
        elif isinstance(value, str):
            assert not value.startswith("{") and str(tmp_path) not in value

    inspect(state)
    assert state.message == LOCAL_VERIFICATION_SCOPE
    assert state.full_external_research_chain_verified_by_gui is False
    # Synthetic bindings have no supplied external report/result/qualification:
    # AVAILABLE must remain strictly a local parser + linkage claim.
    assert state.status is Status.AVAILABLE


def test_recomputed_qualification_facts_fail_on_canonical_but_inconsistent_counts(
    tmp_path,
):
    artifacts = list(local_artifacts())
    artifacts[3] = replace(artifacts[3], observation_count=6)
    paths = write_artifacts(tmp_path, artifacts)
    assert (
        m.ResearchCandidateLifecycleInspectionService(*paths)
        .get_research_candidate_lifecycle_state()
        .status
        is Status.ATTENTION
    )


@pytest.mark.parametrize("name", [f.name for f in fields(m.LifecycleZeroEffectsView)])
def test_nonzero_batch_counter_cannot_weaken_canonical_requirement(tmp_path, name):
    artifacts = local_artifacts()
    paths = write_artifacts(tmp_path, artifacts)
    raw = json.loads(artifacts[2].to_json())
    raw[name] = 1
    paths[2].write_text(
        json.dumps(raw, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    assert (
        m.ResearchCandidateLifecycleInspectionService(*paths)
        .get_research_candidate_lifecycle_state()
        .status
        is Status.ATTENTION
    )


def test_failed_qualification_and_wrong_predecessor_fail_linkage(tmp_path):
    artifacts = list(local_artifacts())
    artifacts[3] = replace(
        artifacts[3],
        policy=replace(artifacts[3].policy, minimum_total_observation_count=6),
    )
    paths = write_artifacts(tmp_path, artifacts)
    assert (
        m.ResearchCandidateLifecycleInspectionService(*paths)
        .get_research_candidate_lifecycle_state()
        .status
        is Status.ATTENTION
    )
    artifacts = list(local_artifacts())
    artifacts[0] = replace(
        artifacts[0], qualification_id=local_artifacts(100)[0].qualification_id
    )
    paths = write_artifacts(tmp_path, artifacts)
    assert (
        m.ResearchCandidateLifecycleInspectionService(*paths)
        .get_research_candidate_lifecycle_state()
        .status
        is Status.ATTENTION
    )


@pytest.mark.parametrize("index", range(5))
def test_service_requires_five_explicit_path_objects(index):
    paths = [Path("selected.json")] * 5
    paths[index] = "selected.json"
    with pytest.raises(TypeError):
        m.ResearchCandidateLifecycleInspectionService(*paths)


def test_unranked_chain_is_retained_without_automatic_selection(tmp_path):
    paths = write_artifacts(tmp_path, local_artifacts(rank=None))
    state = m.ResearchCandidateLifecycleInspectionService(
        *paths
    ).get_research_candidate_lifecycle_state()
    assert state.status is Status.AVAILABLE and state.evidence.rank is None
