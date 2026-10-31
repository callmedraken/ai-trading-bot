"""Synthetic-only P3 search, isolation, evidence and explicit-resume tests."""

import ast
import json
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5

import pytest

import trading_bot.experiments.desktop_research_campaign as campaign
import trading_bot.experiments.historical_research_desktop as desktop
from scripts import run_desktop_research_campaign as cli
from trading_bot.experiments.research_strategy_backtest import (
    ResearchStrategyBacktestEvidence,
    derive_backtest_run_id,
    historical_data_fingerprint,
)
from trading_bot.experiments.research_strategy_walk_forward import (
    ResearchStrategyWalkForwardEvidence,
    ResearchStrategyWalkForwardFoldEvidence,
    run_research_strategy_walk_forward,
)
from trading_bot.market_data.models import HistoricalDataRequest, HistoricalDataResult

from .test_historical_research_desktop import _acquire
from .test_historical_research_desktop import vendor as vendor

HEAD, TREE = "c" * 40, "d" * 40
NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def synthetic_binding(storage):
    evidence_bytes = storage.read("evidence.json")
    evidence = json.loads(evidence_bytes)
    summary = desktop.inspect_desktop_dataset_integrity(storage)
    return (
        campaign.DesktopCampaignDatasetBinding(
            summary.profile,
            summary.source_head,
            summary.source_tree,
            summary.attempt_id,
            summary.session_authority_identity,
            summary.session_authority_digest,
            summary.snapshot_identity,
            summary.full_historical_fingerprint,
            summary.open_manifest_identity,
            summary.open_normalized_sha256,
            summary.open_row_count,
            summary.open_first_timestamp,
            summary.open_last_timestamp,
            summary.corporate_action_sha256,
            sha256(evidence_bytes).hexdigest(),
        )
        if evidence["profile"] == "desktop-v1"
        else None
    )


@pytest.fixture
def storage(tmp_path, vendor):
    return _acquire(tmp_path / "synthetic-data", vendor)[0]


def _slice(data, start, end):
    return HistoricalDataResult(
        HistoricalDataRequest(data.request.symbol, start, end),
        tuple(b for b in data.bars if start <= b.timestamp < end),
        data.provider_name,
    )


def _fake_evidence(definition, data, head, tree, *, role="STANDALONE", fold=None):
    """Cheap deterministic engine fake; real adapters have separate replay tests."""
    fingerprint = historical_data_fingerprint(data)
    config = definition.strategy_config
    # Adjacent short windows tie on return so drawdown/tie order is exercised.
    total_return = Decimal(config.short_window // 10) / Decimal("100")
    drawdown = Decimal(config.long_window % 30) / Decimal("1000")
    return ResearchStrategyBacktestEvidence(
        definition.definition_id,
        campaign.evaluation_policy().policy_id,
        head,
        tree,
        fingerprint,
        definition.symbol,
        data.request.start,
        data.request.end,
        data.request.timeframe,
        data.request.adjustment,
        data.provider_name,
        derive_backtest_run_id(
            definition.definition_id,
            campaign.evaluation_policy().policy_id,
            fingerprint,
            fold_role=role,
            fold_id=fold,
        ),
        uuid5(
            NAMESPACE,
            f"synthetic-result/{definition.definition_id}/{fingerprint}/{role}/{fold}",
        ),
        len(data.bars),
        data.bars[0].timestamp,
        data.bars[-1].timestamp,
        total_return,
        drawdown,
        Decimal("100000") * (1 + total_return),
    )


def fake_development(campaign_id, definition, data, head, tree):
    config = definition.strategy_config
    return campaign.DevelopmentResult(
        campaign.candidate_identity(
            campaign_id, config.short_window, config.long_window
        ),
        definition,
        _fake_evidence(definition, data, head, tree),
        4,
        2,
        Decimal("0.5"),
    )


def fake_walk(row, data, head, tree):
    folds, tests = [], []
    for fold in campaign.fold_plan():
        training = _fake_evidence(
            row.definition,
            _slice(data, fold.training_start, fold.training_end),
            head,
            tree,
            role="TRAINING",
            fold=fold.fold_id,
        )
        test = _fake_evidence(
            row.definition,
            _slice(data, fold.test_start, fold.test_end),
            head,
            tree,
            role="TEST",
            fold=fold.fold_id,
        )
        folds.append(
            ResearchStrategyWalkForwardFoldEvidence(
                fold.fold_id,
                training.evidence_id,
                test.evidence_id,
                fold.training_start,
                fold.training_end,
                fold.test_start,
                fold.test_end,
                training.historical_data_fingerprint,
                test.historical_data_fingerprint,
                training.bar_count,
                test.bar_count,
            )
        )
        tests.append(test)
    evidence = ResearchStrategyWalkForwardEvidence(
        row.definition.definition_id,
        campaign.evaluation_policy().policy_id,
        head,
        tree,
        historical_data_fingerprint(data),
        tuple(folds),
    )
    return campaign.WalkForwardResult(row.candidate_id, evidence, tuple(tests))


@pytest.fixture
def engine_fakes(monkeypatch):
    calls = {"development": [], "walk": []}

    def dev(identity, definition, data, head, tree):
        calls["development"].append((definition.strategy_config, data))
        return fake_development(identity, definition, data, head, tree)

    def walk(row, data, head, tree):
        calls["walk"].append(row.candidate_id)
        return fake_walk(row, data, head, tree)

    monkeypatch.setattr(campaign, "_evaluate_development", dev)
    monkeypatch.setattr(campaign, "_evaluate_walk_forward", walk)
    return calls


def run(storage, root, binding, **kwargs):
    return campaign.run_desktop_campaign(
        storage,
        source_head=HEAD,
        source_tree=TREE,
        output_root=root,
        test_binding=binding,
        **kwargs,
    )


def test_grid_is_exact_canonical_255_and_all_valid():
    expected = tuple(
        (short, long)
        for short in range(5, 61, 5)
        for long in range(40, 251, 10)
        if short < long
    )
    assert campaign.GRID == expected == tuple(sorted(set(expected)))
    assert len(expected) == 255
    assert all(short < long for short, long in expected)
    identity = campaign.campaign_identity(campaign.ACCEPTED_DATASET_BINDING, HEAD, TREE)
    ids = [campaign.candidate_identity(identity, *pair) for pair in expected]
    assert len(set(ids)) == 255
    assert all(UUID(value).version == 5 for value in ids)


def test_source_only_frozen_p2_binding_exact_values():
    binding = campaign.ACCEPTED_DATASET_BINDING
    assert asdict(binding) == {
        "profile": "desktop-v1",
        "acquisition_source_head": "108ba9dee6ad593b3f4128ae44750d9f685ffa0d",
        "acquisition_source_tree": "5652ec3e019766a66a05a9588e79e6cc8c46d70c",
        "acquisition_attempt_id": "a81baba7-7123-45eb-945d-9fb048e24607",
        "session_authority_identity": "nyse-published-regular-sessions-2016-2026-v1",
        "session_authority_digest": (
            "7129170764896ad87c8110ec83523c234149393ae53739fed3764ed371ade6e1"
        ),
        "snapshot_identity": "cf9cb708-89ab-589f-a75c-add17dba25a4",
        "full_historical_fingerprint": "5ebeb399-b97b-5c72-90c4-b1f764fd3109",
        "open_manifest_identity": "19ac19ef-aeed-5fcd-a3ee-7e55cec15796",
        "open_normalized_sha256": (
            "45212bab5eab3c618c6c38d0ae00c8f06fecc4e6b025bc9ff3837920aa545421"
        ),
        "open_row_count": 2012,
        "open_first_timestamp": "2016-01-04T05:00:00+00:00",
        "open_last_timestamp": "2023-12-29T05:00:00+00:00",
        "corporate_action_sha256": (
            "9b6a6dbc45f1c5f12e8576b3bf943dec44868ef43e4ec441f37f8ce7fd9a573b"
        ),
        "acquisition_evidence_sha256": (
            "5b90637cd434402962561a42d398cb925bc069420f5d322b55e40ad3cfaeb8f0"
        ),
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("open_normalized_sha256", "0" * 64),
        ("open_manifest_identity", "00000000-0000-5000-8000-000000000000"),
        ("snapshot_identity", "00000000-0000-5000-8000-000000000000"),
        ("full_historical_fingerprint", "00000000-0000-5000-8000-000000000000"),
        ("acquisition_evidence_sha256", "0" * 64),
        ("acquisition_source_head", "0" * 40),
        ("acquisition_source_tree", "0" * 40),
        ("acquisition_attempt_id", "00000000-0000-5000-8000-000000000000"),
        ("corporate_action_sha256", "0" * 64),
        ("session_authority_digest", "0" * 64),
        ("open_row_count", 2011),
    ],
)
def test_binding_rejects_every_wrong_commitment(storage, field, value):
    binding = synthetic_binding(storage)
    with pytest.raises(campaign.DesktopCampaignError, match="exact accepted"):
        campaign.bind_desktop_dataset(
            storage, test_binding=replace(binding, **{field: value})
        )
    with pytest.raises(campaign.DesktopCampaignError):
        campaign.bind_desktop_dataset(
            storage
        )  # Production freeze cannot accept synthetic.


def test_production_cannot_override_binding_or_output(tmp_path):
    storage = desktop.DesktopResearchStorage.production()
    with pytest.raises(campaign.DesktopCampaignError, match="test seam"):
        campaign.bind_desktop_dataset(
            storage, test_binding=campaign.ACCEPTED_DATASET_BINDING
        )
    with pytest.raises(campaign.DesktopCampaignError, match="reports root"):
        campaign.run_desktop_campaign(
            storage, source_head=HEAD, source_tree=TREE, output_root=tmp_path
        )


def test_campaign_only_open_once_each_shortlist_and_sensitivity(
    storage, tmp_path, monkeypatch, engine_fakes
):
    binding = synthetic_binding(storage)
    reads, opens = [], []
    original_read = desktop.DesktopResearchStorage.read
    original_open = Path.open

    def forbidden(*args, **kwargs):
        raise AssertionError("sealed/integrity/lifecycle operation called")

    def read(self, relative):
        reads.append(relative)
        assert relative != "normalized/holdout/SPY.csv"
        return original_read(self, relative)

    def open_file(self, *args, **kwargs):
        opens.append(str(self))
        assert self != storage.root / "normalized/holdout/SPY.csv"
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(desktop, "load_desktop_final_holdout", forbidden)
    monkeypatch.setattr(desktop, "inspect_desktop_dataset_integrity", forbidden)
    monkeypatch.setattr(desktop.DesktopResearchStorage, "read", read)
    monkeypatch.setattr(Path, "open", open_file)
    artifact = run(storage, tmp_path / "reports", binding)
    bundle = campaign.DesktopCampaignBundle.from_bytes(artifact.read_bytes())
    assert len(engine_fakes["development"]) == 255
    counts = Counter(
        (c.short_window, c.long_window) for c, _ in engine_fakes["development"]
    )
    assert counts == Counter({pair: 1 for pair in campaign.GRID})
    assert all(
        bar.timestamp < datetime(2020, 1, 1, tzinfo=UTC)
        for _, data in engine_fakes["development"]
        for bar in data.bars
    )
    ranked = campaign.rank_development(bundle.development)
    assert engine_fakes["walk"] == [r.candidate_id for r in ranked[:32]]
    assert len(bundle.walk_forward) == 32
    assert "normalized/open/SPY.csv" in reads
    assert all("normalized/holdout/SPY.csv" not in p.replace("\\", "/") for p in opens)
    before = {key: len(value) for key, value in engine_fakes.items()}
    sensitivity = campaign.parameter_sensitivity(bundle.development)
    assert {key: len(value) for key, value in engine_fakes.items()} == before
    assert sensitivity[0]["neighbors"][0]["status"] == "MISSING_GRID_NEIGHBOR"
    assert (
        sensitivity[0]["neighbors"][1]["candidate_id"]
        == bundle.development[22].candidate_id
    )
    assert (
        bundle.to_dict()["recommended_research_only_leader"] == ranked[0].candidate_id
    )
    assert bundle.to_bytes() == artifact.read_bytes()
    assert bundle.to_csv() == artifact.with_name("candidates.csv").read_bytes()
    assert len(bundle.to_csv().decode().splitlines()) == 256
    assert bundle.to_dict()["qualification_policy"] is None
    assert all(w.to_dict()["qualification"] is None for w in bundle.walk_forward)
    # Explicit resume reuses all completed evaluations, without changing bytes.
    assert run(storage, tmp_path / "reports", binding, resume=True) == artifact
    assert before == {key: len(value) for key, value in engine_fakes.items()}
    with pytest.raises(campaign.DesktopCampaignError):
        run(storage, tmp_path / "reports", binding)


def test_ranking_ties_and_later_observations_do_not_select(storage):
    data = desktop.load_desktop_open_research(storage)
    dev = campaign.development_data(data)
    identity = campaign.campaign_identity(synthetic_binding(storage), HEAD, TREE)
    rows = tuple(
        fake_development(
            identity, campaign._definition(HEAD, TREE, *pair), dev, HEAD, TREE
        )
        for pair in campaign.GRID
    )
    ranked = campaign.rank_development(rows)
    assert campaign.rank_development(tuple(reversed(rows))) == ranked
    assert (
        ranked[:32]
        == tuple(
            sorted(
                rows,
                key=lambda r: (
                    -r.evidence.total_return,
                    r.evidence.maximum_drawdown_percentage,
                    r.definition.strategy_config.short_window,
                    r.definition.strategy_config.long_window,
                ),
            )
        )[:32]
    )
    all_ties = tuple(
        replace(
            r,
            evidence=replace(
                r.evidence,
                total_return=Decimal("0"),
                maximum_drawdown_percentage=Decimal("0"),
            ),
        )
        for r in rows
    )
    assert campaign.rank_development(tuple(reversed(all_ties))) == all_ties
    later = tuple(
        replace(b, close=b.close * 2, high=b.high * 3)
        if b.timestamp >= datetime(2020, 1, 1, tzinfo=UTC)
        else b
        for b in data.bars
    )
    changed = HistoricalDataResult(data.request, later, data.provider_name)
    assert campaign.development_data(changed) == dev
    with localcontext() as context:
        context.prec = 3
        assert campaign.rank_development(rows) == ranked


def test_fold_plan_accepted_contract_and_real_engine_adapters(storage):
    original = desktop.load_desktop_open_research(storage)
    data = campaign.campaign_open_projection(original)
    assert data.bars == original.bars
    assert data.request.end == datetime(2024, 1, 1, 5, tzinfo=UTC)
    folds = campaign.fold_plan()
    assert [
        (f.training_start.year, f.training_end.year, f.test_start.year, f.test_end.year)
        for f in folds
    ] == [(2016, 2020, 2020, 2021), (2021, 2022, 2022, 2024)]
    assert folds[1].training_start == folds[0].test_end
    assert all(
        f.training_start
        < f.training_end
        == f.test_start
        < f.test_end
        <= datetime(2024, 1, 1, 5, tzinfo=UTC)
        for f in folds
    )
    definition = campaign._definition(HEAD, TREE, 5, 40)
    identity = campaign.campaign_identity(synthetic_binding(storage), HEAD, TREE)
    row = campaign._evaluate_development(
        identity, definition, campaign.development_data(data), HEAD, TREE
    )
    walk = campaign._evaluate_walk_forward(row, data, HEAD, TREE)
    assert row.evidence.bar_count == len(campaign.development_data(data).bars)
    assert len(walk.test_evidence) == 2
    assert all(
        e.end_timestamp < datetime(2024, 1, 1, tzinfo=UTC) for e in walk.test_evidence
    )
    assert row.total_fills == 0  # Flat synthetic prices: measured, not fabricated.
    assert row.turnover == 0
    # Existing public runner accepts precisely this plan, with no chronology edits.
    assert (
        run_research_strategy_walk_forward(
            definition,
            campaign.evaluation_policy(),
            data,
            folds,
            evaluation_source_head=HEAD,
            evaluation_source_tree=TREE,
        ).evidence
        == walk.evidence
    )


def test_partial_resume_and_corruption_stops(
    storage, tmp_path, monkeypatch, engine_fakes
):
    binding = synthetic_binding(storage)
    original = campaign._evaluate_development
    count = 0

    def interrupted(*args):
        nonlocal count
        count += 1
        if count == 4:
            raise KeyboardInterrupt
        return original(*args)

    monkeypatch.setattr(campaign, "_evaluate_development", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(storage, tmp_path / "reports", binding)
    assert len(engine_fakes["development"]) == 3
    monkeypatch.setattr(campaign, "_evaluate_development", original)
    artifact = run(storage, tmp_path / "reports", binding, resume=True)
    assert len(engine_fakes["development"]) == 255
    candidate = next((artifact.parent / "development").glob("*.json"))
    candidate.write_bytes(b'{"partial":')
    with pytest.raises((ValueError, KeyError)):
        run(storage, tmp_path / "reports", binding, resume=True)
    assert candidate.read_bytes() == b'{"partial":'
    assert len(engine_fakes["development"]) == 255


def test_bundle_rejects_tampering_and_is_context_independent(
    storage, tmp_path, engine_fakes
):
    artifact = run(storage, tmp_path / "reports", synthetic_binding(storage))
    body = artifact.read_bytes()
    bundle = campaign.DesktopCampaignBundle.from_bytes(body)
    assert UUID(bundle.bundle_id).version == 5
    with localcontext() as context:
        context.prec = 4
        assert bundle.to_bytes() == body
        assert bundle.to_csv() == artifact.with_name("candidates.csv").read_bytes()
    mutations = (
        lambda r: r.update(bundle_id="00000000-0000-5000-8000-000000000000"),
        lambda r: r["development_ranking"].reverse(),
        lambda r: r["walk_forward"][0].update(median_fold_return="99"),
        lambda r: r["development"][0]["definition"].update(
            strategy_source_head="0" * 40
        ),
        lambda r: r["shortlist"].pop(),
        lambda r: r["parameter_sensitivity"][0]["neighbors"][0].update(
            status="AVAILABLE"
        ),
        lambda r: r.update(qualification_policy={"promote": True}),
    )
    for mutate in mutations:
        raw = json.loads(body)
        mutate(raw)
        with pytest.raises(campaign.DesktopCampaignError):
            campaign.DesktopCampaignBundle.from_bytes(campaign._json(raw))
    for malformed in (
        body + b"\n",
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b"[]",
        b"x" * 10_000_001,
    ):
        with pytest.raises(campaign.DesktopCampaignError):
            campaign.DesktopCampaignBundle.from_bytes(malformed)


def test_cli_verify_never_runs_or_constructs_storage(
    storage, tmp_path, engine_fakes, monkeypatch, capsys
):
    artifact = run(storage, tmp_path / "reports", synthetic_binding(storage))
    assert (
        campaign.read_desktop_campaign_bundle(artifact).to_bytes()
        == artifact.read_bytes()
    )
    with pytest.raises(TypeError, match="exactly pathlib.Path"):
        campaign.read_desktop_campaign_bundle(str(artifact))
    monkeypatch.setattr(
        cli, "run_desktop_campaign", lambda *a, **k: pytest.fail("campaign executed")
    )
    monkeypatch.setattr(cli, "_source_identity", lambda: pytest.fail("source accessed"))
    assert cli.main(["--verify", str(artifact)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "VERIFIED"
    assert cli.main(["--verify", str(artifact), "--resume"]) == 1


def test_import_and_effect_boundary():
    source = Path(campaign.__file__).read_text()
    tree = ast.parse(source)
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        any(
            word in name.lower()
            for word in (
                "credential",
                "robinhood",
                "alpaca",
                "scheduler",
                "native",
                "broker",
                "http",
                "socket",
            )
        )
        for name in imports
    )
    for forbidden in (
        "load_desktop_final_holdout",
        "inspect_desktop_dataset_integrity",
        "normalized/holdout/SPY.csv",
        "PAPER_CANDIDATE",
        "promote",
        "uuid4",
    ):
        assert forbidden not in source
    # Fresh-process imported module inventory catches indirect host/provider adapters.
    root = Path(campaign.__file__).resolve().parents[2]
    code = f"import sys; sys.path.insert(0, {str(root)!r}); " + (
        "import trading_bot.experiments.desktop_research_campaign; "
        "print('\\n'.join(sorted(n for n in sys.modules "
        "if n.startswith('trading_bot.'))))"
    )
    modules = subprocess.run(
        [sys.executable, "-B", "-c", code], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert not any(
        any(
            word in name
            for word in (
                ".credentials",
                ".robinhood",
                ".alpaca",
                ".scheduler",
                "_native",
                "_host",
            )
        )
        for name in modules
    )


def test_production_modules_do_not_import_private_project_symbols():
    root = Path(__file__).resolve().parents[2]
    paths = (
        root / "scripts" / "run_desktop_research_campaign.py",
        root / "src" / "trading_bot" / "gui" / "desktop_campaign_service.py",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not (
                node.module or ""
            ).startswith(("scripts.", "trading_bot.")):
                continue
            private_names = tuple(
                alias.name for alias in node.names if alias.name.startswith("_")
            )
            assert not private_names, (
                f"{path} imports private project symbols {private_names}"
            )


def test_lazy_public_exports_resolve_to_the_original_objects():
    from importlib import import_module

    import trading_bot.experiments as experiments
    import trading_bot.market_data as market_data

    for package in (experiments, market_data):
        assert set(package.__all__) <= set(dir(package))
        for name, owner in package._LAZY_EXPORTS.items():
            assert getattr(package, name) is getattr(import_module(owner), name)
        with pytest.raises(AttributeError):
            assert package.nonexistent_p3_export is None


def test_journal_metric_corruption_and_source_mismatch_stop(tmp_path):
    path = tmp_path / "candidate.json"
    original = campaign._journal("test-campaign", {"total_fills": 4})
    path.write_bytes(original)
    assert campaign._journal_result(path, "test-campaign") == {"total_fills": 4}
    with pytest.raises(campaign.DesktopCampaignError):
        campaign._journal_result(path, "foreign-campaign")
    raw = json.loads(original)
    raw["result"]["total_fills"] = 5
    path.write_bytes(campaign._json(raw))
    with pytest.raises(campaign.DesktopCampaignError):
        campaign._journal_result(path, "test-campaign")
    with pytest.raises(campaign.DesktopCampaignError):
        campaign._write_once(path, original)


def test_development_utc_boundary_is_independent_of_request_projection(storage):
    data = desktop.load_desktop_open_research(storage)
    boundary = replace(data.bars[-1], timestamp=campaign.DEVELOPMENT_END)
    mixed = HistoricalDataResult(
        data.request,
        tuple(b for b in data.bars if b.timestamp < boundary.timestamp) + (boundary,),
        data.provider_name,
    )
    sliced = campaign.development_data(mixed)
    assert all(b.timestamp < campaign.DEVELOPMENT_END for b in sliced.bars)
    assert boundary not in sliced.bars
    assert sliced.request.end == datetime(2020, 1, 1, 5, tzinfo=UTC)
    assert campaign._context(campaign.ACCEPTED_DATASET_BINDING, HEAD, TREE)["grid"][
        "grid_id"
    ]


@pytest.mark.parametrize("mutation", ["branch", "origin", "dirty", "tracking"])
def test_cli_source_guard_precedes_storage_and_campaign(
    tmp_path, monkeypatch, mutation, capsys
):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "MAIN_ROOT", tmp_path)
    answers = {
        ("rev-parse", "--show-toplevel"): str(tmp_path),
        ("rev-parse", "--abbrev-ref", "HEAD"): "develop",
        ("remote", "get-url", "origin"): cli.ORIGIN,
        ("status", "--porcelain=v1", "--untracked-files=no"): "",
        ("rev-parse", "HEAD"): HEAD,
        ("rev-parse", "HEAD^{tree}"): TREE,
        ("rev-parse", "origin/develop"): HEAD,
    }
    keys = {
        "branch": ("rev-parse", "--abbrev-ref", "HEAD"),
        "origin": ("remote", "get-url", "origin"),
        "dirty": ("status", "--porcelain=v1", "--untracked-files=no"),
        "tracking": ("rev-parse", "origin/develop"),
    }
    answers[keys[mutation]] = "unexpected"
    monkeypatch.setattr(cli, "_git", lambda *args: answers[args])
    monkeypatch.setattr(
        cli.DesktopResearchStorage,
        "production",
        lambda: pytest.fail("source guard did not precede storage"),
    )
    assert cli.main(["--run"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "STOPPED"


def test_cli_verify_rejects_price_csv_before_reading(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "read_desktop_campaign_bundle",
        lambda *a: pytest.fail("price file read"),
    )
    assert cli.main(["--verify", "normalized/holdout/SPY.csv"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "STOPPED"
