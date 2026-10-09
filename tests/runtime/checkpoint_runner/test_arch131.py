from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import checkpoint_runner as runner

from .helpers import (
    _R_PREPARE_BOUNDARIES,
    _T_AUTHORITY,
    _T_NAME,
    _T_SOURCE,
    _T_VERIFIER,
    _U_AUTHORITY,
    _U_NAME,
    _U_SOURCE,
    _131i_authority_copy,
    _131j_authority_copy,
    _131k_authority_copy,
    _131l_authority_copy,
    _131lq_authority_copy,
    _131m_authority_copy,
    _131n_authority_copy,
    _131o_authority_copy,
    _131p_authority_copy,
    _131q_authority_copy,
    _131r_copy,
    _131s_authority_copy,
    _131t_copy,
    _131u_copy,
    _authority_fixture_text,
    _runner_contract_source,
)


@pytest.mark.parametrize(
    "before,after",
    [
        ("AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1", "wrong-token-target"),
        (
            "AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1",
            "wrong-client-target",
        ),
        ("CRED_TYPE_GENERIC: Final = 1", "CRED_TYPE_GENERIC: Final = 2"),
        ('LOOPBACK_HOST: Final = "127.0.0.1"', 'LOOPBACK_HOST: Final = "0.0.0.0"'),
        ("host=LOOPBACK_HOST", 'host="192.168.1.2"'),
        ("self._api.CredReadW", "self._api.CredEnumerateW"),
        ("_require_target(target)", "pass"),
    ],
)
def test_131f_authority_detects_boundary_drift(tmp_path, before, after):
    repo = Path(runner.__file__).resolve().parent.parent
    relative = Path("src/trading_bot/robinhood_mcp/windows_oauth.py")
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    source = _authority_fixture_text(repo, relative)
    assert before in source
    destination.write_text(source.replace(before, after), encoding="utf-8")
    script = tmp_path / "scripts/checkpoint_runner.py"
    script.parent.mkdir()
    script.write_text(
        _authority_fixture_text(repo, "scripts/checkpoint_runner.py"), encoding="utf-8"
    )
    assert runner._arch131_windows_oauth_authority_check(tmp_path)


@pytest.mark.parametrize(
    "addition",
    [
        "import keyring",
        "import os\nvalue = os.getenv('TOKEN')",
        "from pathlib import Path\nPath('tokens').write_text('secret')",
        "value = open('tokens', 'w')",
        "value = native.CredEnumerateW()",
        "def place_equity_order(): pass",
        "tool = 'cancel_equity_order'",
        "import socket\nsocket.socket().bind(('0.0.0.0', 1234))",
    ],
)
def test_131f_authority_rejects_new_effects(tmp_path, addition):
    repo = Path(runner.__file__).resolve().parent.parent
    relative = Path("src/trading_bot/robinhood_mcp/windows_oauth.py")
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    destination.write_text(
        _authority_fixture_text(repo, relative) + "\n" + addition,
        encoding="utf-8",
    )
    script = tmp_path / "scripts/checkpoint_runner.py"
    script.parent.mkdir()
    script.write_text(
        _authority_fixture_text(repo, "scripts/checkpoint_runner.py"), encoding="utf-8"
    )
    assert runner._arch131_windows_oauth_authority_check(tmp_path)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131f_authority_rejects_host_registration(tmp_path, capability):
    repo = Path(runner.__file__).resolve().parent.parent
    relative = Path("src/trading_bot/robinhood_mcp/windows_oauth.py")
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    destination.write_bytes((repo / relative).read_bytes())
    script = tmp_path / "scripts/checkpoint_runner.py"
    script.parent.mkdir()
    source = _authority_fixture_text(repo, "scripts/checkpoint_runner.py")
    script.write_text(
        source.replace(f"{capability}=None,", f"{capability}=dangerous_host,"),
        encoding="utf-8",
    )
    assert runner._arch131_windows_oauth_authority_check(tmp_path)


def test_131f_source_registration_and_workflow():
    specs = runner._checkpoint_specs()
    spec = specs["arch131-robinhood-oauth-windows"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.index("arch131-robinhood-oauth-windows") > workflow.index(
        "arch131-robinhood-direct-mcp"
    )


def test_131g_source_registration():
    spec = runner._checkpoint_specs()["arch131-robinhood-agentic-account"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert spec.authority_check is runner._arch131_agentic_account_authority_check
    assert {
        "tests/robinhood_mcp/test_account_resolution.py",
        "tests/robinhood_mcp/test_sdk_transport.py",
        "tests/test_robinhood_paper_cycle.py",
    } <= set(spec.tests)
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert "arch131-robinhood-agentic-account" in workflow
    assert workflow.index("arch131-robinhood-agentic-account") > workflow.index(
        "arch131-robinhood-oauth-windows"
    )


@pytest.mark.parametrize(
    "relative,before,after",
    [
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            '    "get_equity_orders",',
            '    "get_accounts",\n    "get_equity_orders",',
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    def _get_accounts(",
            "    def get_accounts(",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    def get_equity_orders(",
            "    def call_tool(",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "tool_name not in _ALLOWED_TOOL_NAMES",
            "False",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    return RobinhoodAgenticAccountResolver(transport._get_accounts)",
            "    return transport._get_accounts",
        ),
        (
            "src/trading_bot/robinhood_mcp/adapter.py",
            "    def get_equity_orders(",
            "    def get_accounts(",
        ),
        (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "class RobinhoodAgenticAccountResolver:",
            "def call_tool(): pass\n\nclass RobinhoodAgenticAccountResolver:",
        ),
        (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "        return eligible[0]",
            "        print(eligible[0])\n        return eligible[0]",
        ),
        (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "        return eligible[0]",
            '        return "rhs_account_number"',
        ),
        (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "        return eligible[0]",
            '        return "place_equity_order"',
        ),
        (
            "src/trading_bot/robinhood_mcp/__init__.py",
            "__all__ = [",
            "def get_accounts(): pass\n\n__all__ = [",
        ),
        (
            "scripts/checkpoint_runner.py",
            "preflight=None,",
            "preflight=dangerous_host,",
        ),
        ("scripts/checkpoint_runner.py", "execute=None,", "execute=dangerous_host,"),
    ],
)
def test_131g_authority_rejects_boundary_drift(
    tmp_path, monkeypatch, relative, before, after
):
    # Only resolver/package mutations are wholly local to G. Transport, adapter
    # and registration mutations keep their complete real predecessor coverage.
    if relative in {
        "src/trading_bot/robinhood_mcp/account_resolution.py",
        "src/trading_bot/robinhood_mcp/__init__.py",
    }:
        for predecessor in (
            "_arch131_direct_mcp_authority_check",
            "_arch131_mcp_schema_authority_check",
            "_arch131_paper_cycle_authority_check",
        ):
            monkeypatch.setattr(runner, predecessor, lambda _: ())
    repo = Path(runner.__file__).resolve().parent.parent
    paths = (
        "src/trading_bot/robinhood_mcp/sdk_transport.py",
        "src/trading_bot/robinhood_mcp/adapter.py",
        "src/trading_bot/robinhood_mcp/account_resolution.py",
        "src/trading_bot/robinhood_mcp/__init__.py",
        "src/trading_bot/robinhood_paper_cycle.py",
        "scripts/checkpoint_runner.py",
    )
    for path in paths:
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = _authority_fixture_text(repo, path)
        if path == relative:
            assert before in source
            source = source.replace(before, after)
        destination.write_text(source, encoding="utf-8")
    assert runner._arch131_agentic_account_authority_check(tmp_path)


def test_131h_source_registration_and_workflow():
    spec = runner._checkpoint_specs()["arch131-robinhood-paper-operator"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert spec.authority_check is runner._arch131_paper_operator_authority_check
    assert {
        "tests/test_robinhood_paper_operator.py",
        "tests/test_robinhood_paper_cycle.py",
        "tests/robinhood_mcp/test_account_resolution.py",
        "tests/robinhood_mcp/test_sdk_transport.py",
        "tests/robinhood_mcp/test_windows_oauth.py",
    } <= set(spec.tests)
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.index("arch131-robinhood-paper-operator") > workflow.index(
        "arch131-robinhood-agentic-account"
    )


@pytest.mark.parametrize(
    "relative,before,after",
    [
        (
            "src/trading_bot/robinhood_paper_operator.py",
            '"--porcelain=v1", "--untracked-files=all"',
            '"--porcelain"',
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "with localcontext(_decimal_context()), _suppress_downstream_output():",
            "with localcontext(_decimal_context()):",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "logging.Logger.handle = _discard_log",
            "logging.Logger.handle = previous_handle",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            'open(os.devnull, "w", encoding="utf-8") as sink',
            'open("captured-output.txt", "w", encoding="utf-8") as sink',
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "isinstance(value, str) and bool(value.strip())",
            "bool(value)",
        ),
        (
            "src/trading_bot/robinhood_paper_cycle.py",
            "        post_review, post_review_pages = _collect_agentic_orders(",
            "        if review_failure is not None:\n"
            "            raise review_failure\n"
            "        post_review, post_review_pages = _collect_agentic_orders(",
        ),
        (
            "src/trading_bot/robinhood_paper_cycle.py",
            "except Exception as error:",
            "except BaseException as error:",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "browser_opener=observation.forbid_browser",
            "browser_opener=lambda url: True",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            'raise RobinhoodPaperOperatorError("interactive OAuth is forbidden")',
            "return True",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "json.dumps(asdict(evidence), sort_keys=True)",
            'json.dumps({"raw": store.history()}, default=str)',
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "    source_head: str",
            "    account_number: str\n    source_head: str",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "    placement_calls: int = 0",
            "    placement_calls: int = 1",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "if any(resolved == root or resolved.is_relative_to(root) "
            "for root in roots):",
            "if False:",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "    roots = _admit_source(expected_branch, expected_head, expected_tree)",
            "    roots = ()",
        ),
        (
            "src/trading_bot/robinhood_paper_operator.py",
            "    observation = _Observation()",
            "    place_equity_order()\n    observation = _Observation()",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            '    "get_equity_orders",',
            '    "get_accounts",\n    "get_equity_orders",',
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    def _get_accounts(",
            "    def get_accounts(",
        ),
        (
            "src/trading_bot/robinhood_mcp/sdk_transport.py",
            "    def get_equity_orders(",
            "    def call_tool(",
        ),
        ("scripts/checkpoint_runner.py", "preflight=None,", "preflight=host_effect,"),
        ("scripts/checkpoint_runner.py", "execute=None,", "execute=host_effect,"),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "arch131-robinhood-paper-operator",
            "missing-checkpoint",
        ),
    ],
)
def test_131h_authority_rejects_boundary_drift(
    tmp_path, monkeypatch, relative, before, after
):
    # Predecessor-file and registration/workflow mutations retain real chaining.
    if relative == "src/trading_bot/robinhood_paper_operator.py":
        monkeypatch.setattr(
            runner, "_arch131_agentic_account_authority_check", lambda _: ()
        )
        monkeypatch.setattr(
            runner, "_arch131_windows_oauth_authority_check", lambda _: ()
        )
    repo = Path(runner.__file__).resolve().parent.parent
    for path in (
        "src/trading_bot/robinhood_paper_operator.py",
        "src/trading_bot/robinhood_mcp/sdk_transport.py",
        "src/trading_bot/robinhood_mcp/windows_oauth.py",
        "src/trading_bot/robinhood_mcp/adapter.py",
        "src/trading_bot/robinhood_mcp/account_resolution.py",
        "src/trading_bot/robinhood_mcp/__init__.py",
        "src/trading_bot/robinhood_paper_cycle.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        source = _authority_fixture_text(repo, path)
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source, encoding="utf-8")
    destination = tmp_path / relative
    source = destination.read_text(encoding="utf-8")
    assert before in source
    destination.write_text(source.replace(before, after), encoding="utf-8")
    failures = runner._arch131_paper_operator_authority_check(tmp_path)
    assert failures


def test_131i_source_registration_and_workflow() -> None:
    spec = runner._checkpoint_specs()["arch131-robinhood-paper-intent-bridge"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert spec.authority_check is runner._arch131_paper_intent_bridge_authority_check
    assert {
        "tests/review_paper/test_intent_bridge.py",
        "tests/review_paper/test_store.py",
        "tests/risk/test_risk_models.py",
        "tests/risk/test_manager.py",
        "tests/execution/test_execution_models.py",
        "tests/execution/test_order_engine.py",
    } <= set(spec.tests)
    assert {
        "src/trading_bot/review_paper/intent_bridge.py",
        "src/trading_bot/review_paper/__init__.py",
        "tests/review_paper/test_intent_bridge.py",
    } <= set(spec.ruff_paths)
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.index("arch131-robinhood-paper-intent-bridge") > (
        workflow.index("arch131-robinhood-paper-operator")
    )


@pytest.mark.parametrize(
    "mapping",
    [
        "proposal_id=decision.proposal.proposal_id",
        "order_id=order_id",
        "symbol=decision.proposal.symbol",
        "side=decision.proposal.side",
        "desired_quantity=decision.proposal.desired_quantity",
        "approved_quantity=decision.approved_quantity",
        "risk_outcome=decision.outcome",
        "risk_reason_codes=tuple(reason.code.value for reason in decision.reasons)",
        "proposal_reason=decision.proposal.reason",
        "proposal_confidence=decision.proposal.confidence",
        "order_type=instruction.order_type",
        "time_in_force=instruction.time_in_force",
        "proposed_at=decision.proposal.created_at",
        "limit_price=instruction.limit_price",
    ],
)
def test_131i_authority_freezes_each_mapping(tmp_path, mapping) -> None:
    root = _131i_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/intent_bridge.py"
    source = path.read_text(encoding="utf-8")
    field = mapping.split("=", 1)[0]
    assert mapping in source
    path.write_text(source.replace(mapping, field + "=None"), encoding="utf-8")
    assert runner._arch131_paper_intent_bridge_authority_check(root)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("type(decision) is not RiskDecision", "False"),
        ("type(instruction) is not ExecutionInstruction", "False"),
        ("type(order_id) is not UUID", "False"),
        ("decision.outcome is RiskOutcome.REJECTED", "False"),
        ("decision.evaluated_at < decision.proposal.created_at", "False"),
        ("instruction.created_at < decision.evaluated_at", "False"),
        ("order_id: UUID,", "order_id: UUID = UUID(int=0),"),
        ("order_id=order_id", "order_id=uuid4()"),
        ("order_id=order_id", "order_id=UUID(int=0)"),
        (
            "reason.code.value for reason in decision.reasons",
            "reason.code.value for reason in reversed(decision.reasons)",
        ),
        (
            "tuple(reason.code.value for reason in decision.reasons)",
            "tuple(sorted({reason.code.value for reason in decision.reasons}))",
        ),
        ("limit_price=instruction.limit_price", "limit_price=None"),
        ("risk_outcome=decision.outcome", "risk_outcome=RiskOutcome.APPROVED"),
    ],
)
def test_131i_authority_freezes_validation_and_identity(tmp_path, before, after):
    root = _131i_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/intent_bridge.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert runner._arch131_paper_intent_bridge_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    [
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "from trading_bot.robinhood_paper_cycle import RobinhoodReviewPaperCycle",
        "from trading_bot.robinhood_mcp.sdk_transport import "
        "RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_mcp.windows_oauth import WindowsOAuthStorage",
        "from trading_bot.risk import RiskManager",
        "from trading_bot.execution import OrderEngine",
        "from uuid import uuid4",
        "import socket",
        "import subprocess",
        "import http.client",
        "import pathlib",
        "import os",
        "import logging",
        "run_robinhood_paper_operator()",
        "RobinhoodReviewPaperCycle()",
        "RiskManager().evaluate()",
        "OrderEngine().create_order()",
        "open('file')",
        "socket.socket()",
        "subprocess.run([])",
        "os.environ['SECRET']",
        "os.getenv('SECRET')",
        "print('proposal material')",
        "logging.info('proposal material')",
        "eval('effect()')",
        "__import__('socket')",
        "(",
    ],
)
def test_131i_authority_rejects_imports_calls_and_module_effects(tmp_path, addition):
    root = _131i_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/intent_bridge.py"
    path.write_text(
        path.read_text(encoding="utf-8") + addition + "\n", encoding="utf-8"
    )
    assert runner._arch131_paper_intent_bridge_authority_check(root)


@pytest.mark.parametrize(
    ("relative", "before", "after"),
    [
        ("scripts/checkpoint_runner.py", "preflight=None,", "preflight=host_effect,"),
        ("scripts/checkpoint_runner.py", "execute=None,", "execute=host_effect,"),
        (
            "scripts/checkpoint_runner.py",
            "authority_check=_arch131_paper_intent_bridge_authority_check,",
            "authority_check=_arch131_paper_operator_authority_check,",
        ),
        (
            "scripts/checkpoint_runner.py",
            'name="arch131-robinhood-paper-intent-bridge",',
            'name="missing-checkpoint",',
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "arch131-robinhood-paper-intent-bridge",
            "missing-checkpoint",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "verify-batch",
            "$Failures += 'wrong'",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "              arch131-robinhood-paper-intent-bridge",
            "              # arch131-robinhood-paper-intent-bridge",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            "              arch131-robinhood-paper-operator",
            "              # arch131-robinhood-paper-operator",
        ),
        (
            ".github/workflows/checkpoint-source-gates.yml",
            (
                "arch133-robinhood-reprovision-recovery-reconciliation\n"
                "          exit $LASTEXITCODE"
            ),
            ("arch133-robinhood-reprovision-recovery-reconciliation\n          exit 0"),
        ),
    ],
)
def test_131i_authority_freezes_source_only_registration_and_ci(
    tmp_path,
    relative,
    before,
    after,
) -> None:
    root = _131i_authority_copy(tmp_path)
    path = root / relative
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after, 1), encoding="utf-8")
    assert runner._arch131_paper_intent_bridge_authority_check(root)


def test_131i_authority_rejects_reversed_workflow_order(tmp_path) -> None:
    root = _131i_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text(encoding="utf-8")
    operator = "arch131-robinhood-paper-operator"
    bridge = "arch131-robinhood-paper-intent-bridge"
    source = source.replace(operator, "TEMP_CHECKPOINT")
    source = source.replace(bridge, operator).replace("TEMP_CHECKPOINT", bridge)
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_paper_intent_bridge_authority_check(root)


def test_131j_source_registration_and_workflow() -> None:
    spec = runner._checkpoint_specs()["arch131-robinhood-deterministic-paper-pipeline"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert (
        spec.authority_check
        is runner._arch131_deterministic_paper_pipeline_authority_check
    )
    assert set(spec.tests) == {
        *runner.ARCH131_TESTS,
        "tests/test_robinhood_paper_pipeline.py",
        "tests/review_paper/test_intent_bridge.py",
        "tests/test_robinhood_paper_operator.py",
        "tests/test_robinhood_paper_cycle.py",
        "tests/risk/test_risk_models.py",
        "tests/risk/test_manager.py",
    }
    assert "src/trading_bot/robinhood_paper_pipeline.py" in spec.ruff_paths
    repo = Path(runner.__file__).resolve().parent.parent
    assert spec.authority_check(repo) == ()
    workflow = (repo / ".github/workflows/checkpoint-source-gates.yml").read_text()
    assert workflow.index("arch131-robinhood-deterministic-paper-pipeline") > (
        workflow.index("arch131-robinhood-paper-intent-bridge")
    )


@pytest.mark.parametrize(
    "argument",
    [
        "intent",
        "review_received_at",
        "expected_branch",
        "expected_head",
        "expected_tree",
        "paper_store_path",
        "evidence_path",
        "redirect_uri",
        "starting_cash",
        "slippage_basis_points",
        "commission",
    ],
)
def test_131j_authority_freezes_each_forwarded_argument(tmp_path, argument):
    root = _131j_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_paper_pipeline.py"
    source = path.read_text()
    before = f"{argument}={argument},"
    assert source.count(before) == 1
    path.write_text(source.replace(before, f"{argument}=None,"), encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("RiskManager(risk_limits)", "RiskManager(RiskLimits())"),
        (".evaluate(proposal, risk_context)", ".evaluate(proposal, other_context)"),
        (
            "decision = RiskManager",
            "decision = RiskManager(risk_limits).evaluate(proposal, risk_context)\n"
            "    decision = RiskManager",
        ),
        (
            "return RobinhoodDeterministicPaperPipelineResult(decision, None, None)",
            "pass",
        ),
        (
            "decision.outcome is RiskOutcome.REJECTED",
            "decision.outcome is RiskOutcome.APPROVED",
        ),
        (
            "build_review_paper_intent(decision, instruction, order_id=order_id)",
            "ReviewPaperIntent()",
        ),
        ("order_id=order_id)", "order_id=UUID(int=0))"),
        (
            "intent = build_review_paper_intent",
            "build_review_paper_intent(decision, instruction, order_id=order_id)\n"
            "    intent = build_review_paper_intent",
        ),
        (
            "evidence = run_robinhood_paper_operator(",
            "run_robinhood_paper_operator(intent=intent)\n"
            "    evidence = run_robinhood_paper_operator(",
        ),
        ("decision, intent, evidence)", "decision, intent, None)"),
        ("frozen=True, slots=True", "frozen=False, slots=True"),
        ("if type(order_id) is not UUID:", "if False:"),
        ("if type(self.intent) is not ReviewPaperIntent:", "if False:"),
        (
            "if type(self.operator_evidence) is not RobinhoodPaperOperatorEvidence:",
            "if False:",
        ),
        (
            "if self.intent is not None or self.operator_evidence is not None:",
            "if False:",
        ),
    ],
)
def test_131j_authority_freezes_composition_and_result(tmp_path, before, after):
    root = _131j_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_paper_pipeline.py"
    source = path.read_text()
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    [
        "import os",
        "import random",
        "from uuid import uuid4",
        "from trading_bot.robinhood_mcp import RobinhoodReviewReadAdapter",
        "from trading_bot.robinhood_mcp.windows_oauth import "
        "create_windows_robinhood_oauth_factory",
        "from trading_bot.execution.engine import OrderEngine",
        "open('paper.sqlite', 'w')",
        "print('raw proposal/account')",
        "os.getenv('CONFIG')",
        "subprocess.run(['command'])",
        "transport.call_tool('place_equity_order')",
        "transport.call_tool('cancel_equity_order')",
        "transport.call_tool('place_option_order')",
        "transport.call_tool('place_crypto_order')",
        "create_windows_robinhood_oauth_factory()",
        "resolver.resolve()",
        "OrderEngine.create_order()",
        "OrderEngine.submit_order()",
        "uuid4()",
        "while True:\n    pass",
        "for cycle in range(2):\n    pass",
        "try:\n    run_robinhood_paper_operator()\n"
        "except Exception:\n    run_robinhood_paper_operator()",
    ],
)
def test_131j_authority_rejects_unreviewed_effects(tmp_path, addition):
    root = _131j_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_paper_pipeline.py"
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("preflight=None", "preflight=_r7_preflight"),
        ("execute=None", "execute=_r7_execute"),
        (
            "authority_check=_arch131_deterministic_paper_pipeline_authority_check",
            "authority_check=_arch131_paper_operator_authority_check",
        ),
        ('name="arch131-robinhood-deterministic-paper-pipeline"', 'name="other"'),
        ('"tests/test_robinhood_paper_pipeline.py",', '"tests/other.py",'),
        ("remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH", 'remote_branch="other"'),
    ],
)
def test_131j_authority_freezes_source_only_registration(tmp_path, before, after):
    root = _131j_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    prefix, rest = source.split(
        '        "arch131-robinhood-deterministic-paper-pipeline": CheckpointSpec(', 1
    )
    registration, suffix = rest.split(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', 1
    )
    assert before in registration
    source = (
        prefix
        + '        "arch131-robinhood-deterministic-paper-pipeline": CheckpointSpec('
        + registration.replace(before, after, 1)
        + '        "arch131-robinhood-paper-operator": CheckpointSpec('
        + suffix
    )
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        (
            "              arch131-robinhood-deterministic-paper-pipeline",
            "              # arch131-robinhood-deterministic-paper-pipeline",
        ),
        (
            "exit $LASTEXITCODE",
            "$Failures += 'other'",
        ),
        (
            "              arch131-robinhood-paper-intent-bridge",
            "              # arch131-robinhood-paper-intent-bridge",
        ),
    ],
)
def test_131j_authority_freezes_workflow_invocations(tmp_path, before, after):
    root = _131j_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


def test_131j_authority_rejects_reversed_workflow_order(tmp_path):
    root = _131j_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    pipeline_name = "arch131-robinhood-deterministic-paper-pipeline"
    bridge_name = "arch131-robinhood-paper-intent-bridge"
    source = source.replace(pipeline_name, "TEMP_CHECKPOINT")
    source = source.replace(bridge_name, pipeline_name).replace(
        "TEMP_CHECKPOINT", bridge_name
    )
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_deterministic_paper_pipeline_authority_check(root)


def test_131k_source_only_registration_and_batch():
    name = "arch131-robinhood-virtual-risk-context"
    specs = runner._checkpoint_specs()
    spec = specs[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_virtual_risk_context_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert set(spec.tests) == {
        *runner.ARCH131_TESTS,
        "tests/review_paper/test_risk_context.py",
        "tests/review_paper/test_store.py",
        "tests/ledger/test_ledger.py",
        "tests/risk/test_risk_models.py",
    }
    assert set(spec.ruff_paths) == {
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/review_paper/risk_context.py",
        "src/trading_bot/review_paper/__init__.py",
        "tests/review_paper/test_risk_context.py",
    }
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert (
        runner.ACTIVE_CI_CHECKPOINTS.index(name)
        == runner.ACTIVE_CI_CHECKPOINTS.index(
            "arch131-robinhood-deterministic-paper-pipeline"
        )
        + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "before,after",
    [
        (
            "type(store) is not ReviewPaperStore",
            "not isinstance(store, ReviewPaperStore)",
        ),
        ("type(proposal) is not TradeProposal", "False"),
        ("isinstance(prices, Mapping)", "True"),
        ("type(new_trading_enabled) is not bool", "False"),
        ('normalize_utc(as_of, "as_of")', "as_of"),
        ("as_of < proposal.created_at", "False"),
        ("isinstance(symbol, Symbol)", "True"),
        ("isinstance(price, Decimal)", "True"),
        ("not price.is_finite()", "False"),
        ('price <= Decimal("0")', "False"),
        ("set(prices) != set(ledger.positions) | {proposal.symbol}", "False"),
        (
            "ledger = store.reconstruct_ledger()",
            "ledger = store.reconstruct_ledger()\n"
            "    ledger = store.reconstruct_ledger()",
        ),
        (
            "account = ledger.create_account_snapshot(prices, as_of)",
            "account = ledger.create_account_snapshot(prices, as_of)\n"
            "    account = ledger.create_account_snapshot(prices, as_of)",
        ),
        ("cash=account.cash", "cash=account.buying_power"),
        ("equity=account.equity", "equity=account.cash"),
        ("positions=ledger.positions", "positions={}"),
        ("current_price=prices[proposal.symbol]", "current_price=None"),
        (
            "total_market_exposure=account.positions_market_value",
            "total_market_exposure=account.equity",
        ),
        ("new_trading_enabled=new_trading_enabled", "new_trading_enabled=True"),
        ("as_of=as_of", "as_of=proposal.created_at"),
    ],
)
def test_131k_authority_freezes_builder(tmp_path, before, after):
    root = _131k_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_context.py"
    source = path.read_text()
    assert before in source
    path.write_text(source.replace(before, after, 1), encoding="utf-8")
    assert runner._arch131_virtual_risk_context_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    [
        "from trading_bot.risk import RiskManager",
        "RiskManager().evaluate()",
        "from trading_bot.review_paper.intent_bridge import build_review_paper_intent",
        "from trading_bot.robinhood_paper_pipeline "
        "import run_robinhood_deterministic_paper_pipeline",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "from trading_bot.robinhood_mcp import RobinhoodMCPAdapter",
        "from trading_bot.robinhood_oauth import RobinhoodOAuthClient",
        "store.record_market_review(intent, review)",
        "performance.record_valuation(quotes)",
        "from uuid import uuid4",
        "import random",
        "import socket",
        "import subprocess",
        "import os",
        "import logging",
        "open('paper', 'w')",
        "print('context')",
        "ReviewPaperStore('other', starting_cash=1)",
        "def hidden_effect():\n    pass",
    ],
)
def test_131k_authority_rejects_expanded_effect_surface(tmp_path, addition):
    root = _131k_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_context.py"
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert runner._arch131_virtual_risk_context_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("preflight=None", "preflight=_r7_preflight"),
        ("execute=None", "execute=_r7_execute"),
        (
            "authority_check=_arch131_virtual_risk_context_authority_check",
            "authority_check=_arch131_paper_operator_authority_check",
        ),
        ('name="arch131-robinhood-virtual-risk-context"', 'name="other"'),
        ('"tests/review_paper/test_risk_context.py"', '"tests/other.py"'),
        ('"src/trading_bot/review_paper/risk_context.py"', '"src/other.py"'),
        ("remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH", 'remote_branch="other"'),
    ],
)
def test_131k_authority_freezes_registration(tmp_path, before, after):
    root = _131k_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    prefix, rest = source.split(
        '        "arch131-robinhood-virtual-risk-context": CheckpointSpec(', 1
    )
    registration, suffix = rest.split(
        '        "arch131-robinhood-forward-paper-cycle": CheckpointSpec(', 1
    )
    assert before in registration
    path.write_text(
        prefix
        + '        "arch131-robinhood-virtual-risk-context": CheckpointSpec('
        + registration.replace(before, after, 1)
        + '        "arch131-robinhood-forward-paper-cycle": CheckpointSpec('
        + suffix,
        encoding="utf-8",
    )
    assert runner._arch131_virtual_risk_context_authority_check(root)


@pytest.mark.parametrize("change", ["missing", "duplicate", "reverse", "sequential"])
def test_131k_authority_freezes_batch_workflow(tmp_path, change):
    root = _131k_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    name = "arch131-robinhood-virtual-risk-context"
    if change == "missing":
        source = source.replace(name, "# " + name)
    elif change == "duplicate":
        source = source.replace(name, name + " " + name)
    elif change == "reverse":
        previous = "arch131-robinhood-deterministic-paper-pipeline"
        source = (
            source.replace(previous, "TEMP_CHECKPOINT")
            .replace(name, previous)
            .replace("TEMP_CHECKPOINT", name)
        )
    else:
        source = source.replace("verify-batch", "verify arch")
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_virtual_risk_context_authority_check(root)


def test_131l_source_only_registration_and_batch():
    name = "arch131-robinhood-forward-paper-cycle"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_forward_paper_cycle_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-mode"
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/test_robinhood_forward_paper_cycle.py",
        "tests/review_paper/test_risk_context.py",
        "tests/test_robinhood_paper_pipeline.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/robinhood_forward_paper_cycle.py",
        "tests/test_robinhood_forward_paper_cycle.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(name) == (
        runner.ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-virtual-risk-context") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "before,after",
    [
        ("        store,", "        other_store,"),
        ("        proposal,", "        other_proposal,"),
        ("        prices,", "        {},"),
        ("as_of=as_of", "as_of=proposal.created_at"),
        ("new_trading_enabled=new_trading_enabled", "new_trading_enabled=True"),
        ("risk_context=risk_context", "risk_context=other_context"),
        ("paper_store_path=store.path", "paper_store_path=other_store.path"),
        (
            "starting_cash=store.starting_cash",
            "starting_cash=other_store.starting_cash",
        ),
        (
            "    store: ReviewPaperStore,",
            "    store: ReviewPaperStore,\n    paper_store_path: Path,",
        ),
        (
            "    store: ReviewPaperStore,",
            "    store: ReviewPaperStore,\n    starting_cash: Decimal,",
        ),
        (
            "    risk_context = build_review_paper_risk_context(",
            "    build_review_paper_risk_context(store, proposal, prices)\n"
            "    risk_context = build_review_paper_risk_context(",
        ),
        (
            "    return run_robinhood_deterministic_paper_pipeline(",
            "    run_robinhood_deterministic_paper_pipeline()\n"
            "    return run_robinhood_deterministic_paper_pipeline(",
        ),
        (
            "    return run_robinhood_deterministic_paper_pipeline(",
            "    return None\n    run_robinhood_deterministic_paper_pipeline(",
        ),
        (
            "    risk_context = build_review_paper_risk_context(",
            "    return run_robinhood_deterministic_paper_pipeline()\n"
            "    risk_context = build_review_paper_risk_context(",
        ),
        (
            "run_robinhood_deterministic_paper_pipeline,",
            "run_robinhood_deterministic_paper_pipeline as alternate,",
        ),
        *(
            (f"{key}={key}", f"{key}=None")
            for key in (
                "proposal",
                "risk_limits",
                "instruction",
                "order_id",
                "review_received_at",
                "expected_branch",
                "expected_head",
                "expected_tree",
                "evidence_path",
                "redirect_uri",
                "slippage_basis_points",
                "commission",
            )
        ),
    ],
)
def test_131l_authority_freezes_composition_and_every_input(tmp_path, before, after):
    root = _131l_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_forward_paper_cycle.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after, 1), encoding="utf-8")
    assert runner._arch131_forward_paper_cycle_authority_check(root)


@pytest.mark.parametrize(
    "addition",
    [
        "from trading_bot.risk import RiskManager",
        "RiskManager().evaluate()",
        "from trading_bot.review_paper import build_review_paper_intent",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "from trading_bot.robinhood_mcp import RobinhoodMCPAdapter",
        "from trading_bot.robinhood_oauth import RobinhoodOAuthClient",
        "store.reconstruct_ledger()",
        "ReviewPaperStore('other', starting_cash=1)",
        "performance.record_valuation(quotes)",
        "account.get_buying_power()",
        "OrderEngine().submit_order(order)",
        "adapter.place_equity_order()",
        "adapter.cancel_equity_order()",
        "adapter.place_option_order()",
        "adapter.place_crypto_order()",
        "from uuid import uuid4",
        "import socket",
        "import subprocess",
        "import os",
        "import logging",
        "open('paper', 'w')",
        "while True:\n    pass",
        "for attempt in range(2):\n    pass",
        "try:\n    pass\nexcept Exception:\n    pass",
        "def hidden_effect():\n    pass",
        "@scheduler\ndef unattended():\n    pass",
    ],
)
def test_131l_authority_rejects_expanded_effect_or_retry_surface(tmp_path, addition):
    root = _131l_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_forward_paper_cycle.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n", encoding="utf-8"
    )
    assert runner._arch131_forward_paper_cycle_authority_check(root)


@pytest.mark.parametrize(
    "before,after",
    [
        ("preflight=None", "preflight=_r7_preflight"),
        ("execute=None", "execute=_r7_execute"),
        (
            "authority_check=_arch131_forward_paper_cycle_authority_check",
            "authority_check=_arch131_paper_operator_authority_check",
        ),
        ('name="arch131-robinhood-forward-paper-cycle"', 'name="other"'),
        ('"tests/test_robinhood_forward_paper_cycle.py"', '"tests/other.py"'),
        ('"src/trading_bot/robinhood_forward_paper_cycle.py"', '"src/other.py"'),
        ("remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH", 'remote_branch="other"'),
    ],
)
def test_131l_authority_freezes_source_only_registration(tmp_path, before, after):
    root = _131l_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    prefix, rest = source.split(
        '        "arch131-robinhood-forward-paper-cycle": CheckpointSpec(', 1
    )
    registration, suffix = rest.split(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', 1
    )
    assert before in registration
    path.write_text(
        prefix
        + '        "arch131-robinhood-forward-paper-cycle": CheckpointSpec('
        + registration.replace(before, after, 1)
        + '        "arch131-robinhood-paper-operator": CheckpointSpec('
        + suffix,
        encoding="utf-8",
    )
    assert runner._arch131_forward_paper_cycle_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131l_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131l_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-forward-paper-cycle"

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-L checkpoint has host/effect capability" in (
        runner._arch131_forward_paper_cycle_authority_check(root)
    )


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "reverse", "sequential", "exit"]
)
def test_131l_authority_freezes_batch_workflow(tmp_path, change):
    root = _131l_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text(encoding="utf-8")
    name = "arch131-robinhood-forward-paper-cycle"
    if change == "missing":
        source = source.replace(name, "# " + name)
    elif change == "duplicate":
        source = source.replace(name, name + " " + name)
    elif change == "reverse":
        previous = "arch131-robinhood-virtual-risk-context"
        source = (
            source.replace(previous, "TEMP_CHECKPOINT")
            .replace(name, previous)
            .replace("TEMP_CHECKPOINT", name)
        )
    elif change == "sequential":
        source = source.replace("verify-batch", "verify arch")
    else:
        source = source.replace("exit $LASTEXITCODE", "exit 0")
    path.write_text(source, encoding="utf-8")
    assert runner._arch131_forward_paper_cycle_authority_check(root)


@pytest.mark.parametrize(
    "relative",
    [
        "src/trading_bot/robinhood_forward_paper_cycle.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ],
)
def test_131l_authority_fails_closed_when_source_is_unavailable(tmp_path, relative):
    root = _131l_authority_copy(tmp_path)
    (root / relative).unlink()
    assert runner._arch131_forward_paper_cycle_authority_check(root)


def test_131lq_source_only_registration_and_batch():
    name = "arch131-robinhood-live-qualification-verifier"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert (
        spec.authority_check
        is runner._arch131_live_qualification_verifier_authority_check
    )
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/test_robinhood_live_qualification_verifier.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/robinhood_live_qualification_verifier.py",
        "tests/test_robinhood_live_qualification_verifier.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(name) == (
        runner.ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-cycle") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131lq_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131lq_authority_copy(tmp_path)
    path = root / "src/trading_bot/robinhood_live_qualification_verifier.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_live_qualification_verifier_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131lq_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131lq_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-live-qualification-verifier"

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-LQ checkpoint has host/effect capability" in (
        runner._arch131_live_qualification_verifier_authority_check(root)
    )


def test_131m_source_only_registration_and_batch():
    name = "arch131-robinhood-session-admission"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_session_admission_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/review_paper/test_session_admission.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/review_paper/session_admission.py",
        "tests/review_paper/test_session_admission.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(name) == (
        runner.ACTIVE_CI_CHECKPOINTS.index(
            "arch131-robinhood-live-qualification-verifier"
        )
        + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131m_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131m_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/session_admission.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_session_admission_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131m_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131m_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-session-admission"

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-M checkpoint has host/effect capability" in (
        runner._arch131_session_admission_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_session_admission.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_session_admission_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131m_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131m_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-session-admission": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-forward-paper-preview": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-M source-only checkpoint registration drift" in (
        runner._arch131_session_admission_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131m_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131m_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/session_admission.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-live-qualification-verifier",\n'
                '    "arch131-robinhood-session-admission",',
                '    "arch131-robinhood-session-admission",\n'
                '    "arch131-robinhood-live-qualification-verifier",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_session_admission_authority_check(root)


def test_131m_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):

    root = _131m_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-session-admission"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-M checkpoint remote branch drift" in (
        runner._arch131_session_admission_authority_check(root)
    )


def test_131n_source_only_registration_and_batch():
    name = "arch131-robinhood-risk-price-snapshot"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_risk_price_snapshot_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/review_paper/test_risk_prices.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/review_paper/risk_prices.py",
        "tests/review_paper/test_risk_prices.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(name) == (
        runner.ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-session-admission") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131n_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131n_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_prices.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_risk_price_snapshot_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131n_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131n_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-risk-price-snapshot"

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-N checkpoint has host/effect capability" in (
        runner._arch131_risk_price_snapshot_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_risk_prices.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_risk_price_snapshot_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131n_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131n_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-risk-price-snapshot": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-forward-paper-preview": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-N source-only checkpoint registration drift" in (
        runner._arch131_risk_price_snapshot_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131n_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131n_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/risk_prices.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-session-admission",\n'
                '    "arch131-robinhood-risk-price-snapshot",',
                '    "arch131-robinhood-risk-price-snapshot",\n'
                '    "arch131-robinhood-session-admission",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_risk_price_snapshot_authority_check(root)


def test_131n_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):

    root = _131n_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-risk-price-snapshot"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-N checkpoint remote branch drift" in (
        runner._arch131_risk_price_snapshot_authority_check(root)
    )


def test_131o_source_only_registration_and_batch():
    name = "arch131-robinhood-forward-paper-preview"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is runner._arch131_forward_paper_preview_authority_check
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/review_paper/test_forward_preview.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/review_paper/forward_preview.py",
        "tests/review_paper/test_forward_preview.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(name) == (
        runner.ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-risk-price-snapshot") + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131o_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131o_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/forward_preview.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_forward_paper_preview_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131o_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131o_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-forward-paper-preview"

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-O checkpoint has host/effect capability" in (
        runner._arch131_forward_paper_preview_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_forward_preview.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_forward_paper_preview_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131o_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131o_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-forward-paper-preview": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-O source-only checkpoint registration drift" in (
        runner._arch131_forward_paper_preview_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131o_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131o_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/forward_preview.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-risk-price-snapshot",\n'
                '    "arch131-robinhood-forward-paper-preview",',
                '    "arch131-robinhood-forward-paper-preview",\n'
                '    "arch131-robinhood-risk-price-snapshot",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_forward_paper_preview_authority_check(root)


def test_131o_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):

    root = _131o_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-forward-paper-preview"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-O checkpoint remote branch drift" in (
        runner._arch131_forward_paper_preview_authority_check(root)
    )


@pytest.mark.parametrize(
    "before,after",
    [
        ("price_snapshot.prices,", "dict(price_snapshot.prices),"),
        ("as_of=price_snapshot.observed_at,", "as_of=proposal.created_at,"),
        ("risk_context=risk_context,", "risk_context=other_context,"),
        ("risk_decision=decision,", "risk_decision=other_decision,"),
        (
            "    decision = RiskManager(risk_limits).evaluate(proposal, risk_context)",
            "    RiskManager(risk_limits).evaluate(proposal, risk_context)\n"
            "    decision = RiskManager(risk_limits).evaluate(proposal, risk_context)",
        ),
        (
            "    risk_context = build_review_paper_risk_context(",
            "    store.reconstruct_ledger()\n"
            "    risk_context = build_review_paper_risk_context(",
        ),
        ("return context.subtract(current, approved)", "return Decimal('0')"),
        ('if self.projected_position_quantity < Decimal("0"):', "if False:"),
    ],
)
def test_131o_authority_pins_composition_validation_and_projection(
    tmp_path, before, after
):
    root = _131o_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/forward_preview.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert (
        "131-O forward-preview boundary drift"
        in runner._arch131_forward_paper_preview_authority_check(root)
    )


def test_131p_source_only_registration_and_batch():
    name = "arch131-robinhood-risk-price-acquisition"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert (
        spec.authority_check is runner._arch131_risk_price_acquisition_authority_check
    )
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/review_paper/test_risk_price_acquisition.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/review_paper/risk_price_acquisition.py",
        "tests/review_paper/test_risk_price_acquisition.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(name) == (
        runner.ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-preview")
        + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131p_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131p_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_price_acquisition.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_risk_price_acquisition_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131p_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131p_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-risk-price-acquisition"

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-P checkpoint has host/effect capability" in (
        runner._arch131_risk_price_acquisition_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_risk_price_acquisition.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_risk_price_acquisition_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131p_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131p_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-risk-price-acquisition": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-P source-only checkpoint registration drift" in (
        runner._arch131_risk_price_acquisition_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131p_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131p_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/risk_price_acquisition.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-forward-paper-preview",\n'
                '    "arch131-robinhood-risk-price-acquisition",',
                '    "arch131-robinhood-risk-price-acquisition",\n'
                '    "arch131-robinhood-forward-paper-preview",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_risk_price_acquisition_authority_check(root)


def test_131p_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):

    root = _131p_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-risk-price-acquisition"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-P checkpoint remote branch drift" in (
        runner._arch131_risk_price_acquisition_authority_check(root)
    )


@pytest.mark.parametrize(
    "before,after",
    [
        ("store.reconstruct_ledger()", "store.create_account_snapshot({})"),
        (
            "response = adapter.equity_quotes(required_symbols)",
            "adapter.equity_quotes(required_symbols)\n"
            "    response = adapter.equity_quotes(required_symbols)",
        ),
        ("datetime.now(UTC)", "datetime.now()"),
        ("observed_at = datetime.now(UTC)", "observed_at = proposal.created_at"),
        ("max_quote_age=max_quote_age,", "max_quote_age=timedelta(days=1),"),
        ("return build_review_paper_risk_price_snapshot(", "return other_builder("),
        ("key=str", "key=repr"),
        ("len(required_symbols) > 20", "len(required_symbols) > 21"),
        (
            "type(store) is not ReviewPaperStore",
            "not isinstance(store, ReviewPaperStore)",
        ),
    ],
)
def test_131p_authority_pins_complete_acquisition(tmp_path, before, after):
    root = _131p_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/risk_price_acquisition.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert "131-P risk-price acquisition boundary drift" in (
        runner._arch131_risk_price_acquisition_authority_check(root)
    )


def test_131q_source_only_registration_and_batch():
    name = "arch131-robinhood-supervised-forward-paper"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert (
        spec.authority_check is runner._arch131_supervised_forward_paper_authority_check
    )
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/review_paper/test_supervised_forward_paper.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/review_paper/supervised_forward_paper.py",
        "tests/review_paper/test_supervised_forward_paper.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(name) == (
        runner.ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-risk-price-acquisition")
        + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131q_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131q_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/supervised_forward_paper.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_supervised_forward_paper_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131q_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131q_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-supervised-forward-paper"

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-Q checkpoint has host/effect capability" in (
        runner._arch131_supervised_forward_paper_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_supervised_forward_paper.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_supervised_forward_paper_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131q_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131q_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-robinhood-supervised-forward-paper": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-Q source-only checkpoint registration drift" in (
        runner._arch131_supervised_forward_paper_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131q_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131q_authority_copy(tmp_path)
    if target == "source_missing":
        (root / "src/trading_bot/review_paper/supervised_forward_paper.py").unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-risk-price-acquisition",\n'
                '    "arch131-robinhood-supervised-forward-paper",',
                '    "arch131-robinhood-supervised-forward-paper",\n'
                '    "arch131-robinhood-risk-price-acquisition",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_supervised_forward_paper_authority_check(root)


def test_131q_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):

    root = _131q_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-robinhood-supervised-forward-paper"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-Q checkpoint remote branch drift" in (
        runner._arch131_supervised_forward_paper_authority_check(root)
    )


@pytest.mark.parametrize(
    "before,after",
    [
        ("datetime.now(UTC)", "datetime.now()"),
        (
            "prepare_started_at = datetime.now(UTC)",
            "prepare_started_at = proposal.created_at",
        ),
        (
            "execute_at = datetime.now(UTC)",
            "execute_at = preparation.price_snapshot.observed_at",
        ),
        ("durable_history_before = store.history()", "durable_history_before = ()"),
        ("durable_history_after = store.history()", "durable_history_after = ()"),
        ("current_history = preparation.store.history()", "current_history = ()"),
        (
            "execute_at > preparation.quote_valid_until",
            "execute_at >= preparation.quote_valid_until",
        ),
        ("durable_history_before != durable_history_after", "False"),
        ("current_history != preparation.durable_history", "False"),
        (
            "revalidated_preview.risk_context != preparation.preview.risk_context",
            "False",
        ),
        (
            "revalidated_preview.risk_decision != preparation.preview.risk_decision",
            "False",
        ),
        (
            "instruction.created_at < preparation.preview.risk_decision.evaluated_at",
            "False",
        ),
        (
            "pipeline_result = run_robinhood_forward_paper_cycle(",
            "pipeline_result = other_pipeline(",
        ),
        (
            "durable_history_before = store.history()",
            "run_robinhood_forward_paper_cycle()\n"
            "    durable_history_before = store.history()",
        ),
        (
            "execute_at = datetime.now(UTC)",
            "run_robinhood_forward_paper_cycle()\n    execute_at = datetime.now(UTC)",
        ),
        (
            "durable_history_before = store.history()",
            "adapter.equity_quotes(())\n    durable_history_before = store.history()",
        ),
        (
            "type(adapter) is not RobinhoodReviewReadAdapter",
            "not isinstance(adapter, RobinhoodReviewReadAdapter)",
        ),
        ("mark.source_at + max_quote_age", "snapshot.observed_at + max_quote_age"),
    ],
)
def test_131q_authority_pins_complete_composition(tmp_path, before, after):
    root = _131q_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/supervised_forward_paper.py"
    source = path.read_text(encoding="utf-8")
    assert before in source
    path.write_text(source.replace(before, after), encoding="utf-8")
    assert "131-Q supervised forward-paper boundary drift" in (
        runner._arch131_supervised_forward_paper_authority_check(root)
    )


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
def test_131r_source_only_registration_and_batch(boundary):
    name, description, source, test, authority, predecessor = boundary
    spec = runner._checkpoint_specs()[name]
    assert spec.description == description
    assert spec.preflight is None and spec.execute is None
    assert spec.authority_check is authority
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (*runner.ARCH131_TESTS, test)
    assert spec.ruff_paths == (*runner.ARCH131_RUFF_PATHS, source, test)
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert (
        runner.ACTIVE_CI_CHECKPOINTS.index(name)
        == runner.ACTIVE_CI_CHECKPOINTS.index(predecessor) + 1
    )
    assert authority(Path(runner.__file__).resolve().parent.parent) == ()
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 47
    assert runner.ACTIVE_CI_CHECKPOINTS[-36:-22] == (
        "arch131-robinhood-forward-paper-cycle",
        "arch131-robinhood-live-qualification-verifier",
        "arch131-robinhood-session-admission",
        "arch131-robinhood-risk-price-snapshot",
        "arch131-robinhood-forward-paper-preview",
        "arch131-robinhood-risk-price-acquisition",
        "arch131-robinhood-supervised-forward-paper",
        "arch131-robinhood-supervised-prepare-qualification",
        "arch131-robinhood-supervised-prepare-verifier",
        "arch131-nyse-published-regular-session-authority",
        "arch131-robinhood-published-session-prepare",
        "arch131-robinhood-published-prepare-operator",
        "arch131-robinhood-supervised-qualification",
        "arch133-robinhood-unattended-activation-core",
    )


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper.store import ReviewPaperStore",
        "from trading_bot.robinhood_mcp.adapter import RobinhoodReviewReadAdapter",
        "from trading_bot.risk.manager import RiskManager",
        "from trading_bot.execution.models import ExecutionInstruction",
        "from trading_bot.review_paper.supervised_forward_paper import "
        "execute_review_paper_supervised_cycle",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131r_complete_module_pinned(tmp_path, boundary, addition):
    root = _131r_copy(tmp_path, boundary)
    path = root / boundary[2]
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert boundary[4](root)


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_r7_execute"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        ("Architecture 131-R", "unreviewed"),
    ],
)
def test_131r_exact_registration_pinned(tmp_path, boundary, old, new):
    root = _131r_copy(tmp_path, boundary)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    start = source.index(f'        "{boundary[0]}": CheckpointSpec(')
    end = source.index("            execute=None,\n        ),", start) + len(
        "            execute=None,\n        ),"
    )
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new) + source[end:], encoding="utf-8"
    )
    assert boundary[4](root)


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
@pytest.mark.parametrize("target", ["source_missing", "branch", "batch", "workflow"])
def test_131r_source_authority_drift(tmp_path, boundary, target):
    root = _131r_copy(tmp_path, boundary)
    if target == "source_missing":
        (root / boundary[2]).unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(
            path.read_text().replace("exit $LASTEXITCODE", "exit 0"), encoding="utf-8"
        )
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"', '"feature/wrong"'
            )
        else:
            source = source.replace(
                f'    "{boundary[0]}",',
                f'    "{boundary[0]}",\n    "{boundary[0]}",',
                1,
            )
        path.write_text(source, encoding="utf-8")
    assert boundary[4](root)


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
@pytest.mark.parametrize(
    "field,value",
    [
        ("preflight", lambda: None),
        ("execute", lambda: None),
        ("remote_branch", "feature/wrong"),
    ],
)
def test_131r_runtime_registration_drift(tmp_path, monkeypatch, boundary, field, value):

    root = _131r_copy(tmp_path, boundary)
    specs = runner._checkpoint_specs()
    specs[boundary[0]] = replace(specs[boundary[0]], **{field: value})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert boundary[4](root)


@pytest.mark.parametrize(
    "index,old,new",
    [
        (0, "prepare_review_paper_supervised_cycle(", "other_prepare("),
        (0, "after = _read_durable_snapshot(store.path)", "after = before"),
        (0, "if before != after:", "if False:"),
        (0, 'evidence_path.open("x"', 'evidence_path.open("w"'),
        (0, "return preparation", "return None"),
        (0, "SELECT * FROM review_fills", "SELECT paper_trade_id FROM review_fills"),
        (0, "?mode=ro", "?mode=rw"),
        (1, "?mode=ro", "?mode=rw"),
        (1, "SELECT * FROM review_fills", "SELECT paper_trade_id FROM review_fills"),
        (1, '"execute_invoked"] is False', '"execute_invoked"] == False'),
        (
            1,
            "expected_deadline = min(source + age for source in source_times)",
            "expected_deadline = observed + age",
        ),
    ],
)
def test_131r_critical_guards_pinned(tmp_path, index, old, new):
    boundary = _R_PREPARE_BOUNDARIES[index]
    root = _131r_copy(tmp_path, boundary)
    path = root / boundary[2]
    source = path.read_text()
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    assert boundary[4](root)


def test_131s_source_only_registration_and_batch():
    name = "arch131-nyse-published-regular-session-authority"
    spec = runner._checkpoint_specs()[name]
    assert spec.preflight is None and spec.execute is None
    assert (
        spec.authority_check
        is runner._arch131_nyse_published_regular_session_authority_check
    )
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/review_paper/test_nyse_published_regular_sessions.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        "src/trading_bot/review_paper/nyse_published_regular_sessions.py",
        "tests/review_paper/test_nyse_published_regular_sessions.py",
    )
    assert runner.ACTIVE_CI_CHECKPOINTS.count(name) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(name) == (
        runner.ACTIVE_CI_CHECKPOINTS.index(
            "arch131-robinhood-supervised-prepare-verifier"
        )
        + 1
    )
    assert spec.authority_check(Path(runner.__file__).resolve().parent.parent) == ()


@pytest.mark.parametrize(
    "addition",
    [
        "import socket",
        "import subprocess",
        "import os",
        "from trading_bot.review_paper import ReviewPaperStore",
        "from trading_bot.robinhood_mcp import RobinhoodMcpStreamableHttpTransport",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "while True:\n    pass",
        "open('paper.sqlite', 'w')",
    ],
)
def test_131s_authority_rejects_effect_surface_drift(tmp_path, addition):
    root = _131s_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/nyse_published_regular_sessions.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + addition + "\n",
        encoding="utf-8",
    )
    assert runner._arch131_nyse_published_regular_session_authority_check(root)


@pytest.mark.parametrize("capability", ["preflight", "execute"])
def test_131s_authority_rejects_runtime_effect_registration(
    tmp_path, monkeypatch, capability
):
    root = _131s_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-nyse-published-regular-session-authority"

    def forbidden():
        raise AssertionError("effect capability invoked during source certification")

    specs[name] = replace(specs[name], **{capability: forbidden})
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-S checkpoint has host/effect capability" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_arch130_r8i_d1_preflight"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        (
            "tests/review_paper/test_nyse_published_regular_sessions.py",
            "tests/review_paper/test_models.py",
        ),
        (
            "_arch131_nyse_published_regular_session_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131s_authority_rejects_registration_drift(tmp_path, old, new):
    root = _131s_authority_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text(encoding="utf-8")
    start = source.index(
        '        "arch131-nyse-published-regular-session-authority": CheckpointSpec('
    )
    end = source.index(
        '        "arch131-robinhood-published-session-prepare": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    source = source[:start] + registration.replace(old, new) + source[end:]
    path.write_text(source, encoding="utf-8")
    assert "131-S source-only checkpoint registration drift" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


@pytest.mark.parametrize("target", ["branch", "batch", "workflow", "source_missing"])
def test_131s_authority_rejects_source_authority_drift(tmp_path, target):
    root = _131s_authority_copy(tmp_path)
    if target == "source_missing":
        (
            root / "src/trading_bot/review_paper/nyse_published_regular_sessions.py"
        ).unlink()
    elif target == "workflow":
        path = root / ".github/workflows/checkpoint-source-gates.yml"
        path.write_text(path.read_text().replace("exit $LASTEXITCODE", "exit 0"))
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"',
                '"feature/wrong-branch"',
            )
        else:
            source = source.replace(
                '    "arch131-robinhood-supervised-prepare-verifier",\n'
                '    "arch131-nyse-published-regular-session-authority",',
                '    "arch131-nyse-published-regular-session-authority",\n'
                '    "arch131-robinhood-supervised-prepare-verifier",',
            )
        path.write_text(source, encoding="utf-8")
    assert runner._arch131_nyse_published_regular_session_authority_check(root)


def test_131s_authority_rejects_runtime_remote_drift(tmp_path, monkeypatch):

    root = _131s_authority_copy(tmp_path)
    specs = runner._checkpoint_specs()
    name = "arch131-nyse-published-regular-session-authority"
    specs[name] = replace(specs[name], remote_branch="feature/wrong-branch")
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert "131-S checkpoint remote branch drift" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


@pytest.mark.parametrize(
    "old,new",
    [
        ("date(2028, 1, 17)", "date(2028, 1, 1)"),
        ("date(2028, 7, 3)", "date(2028, 7, 5)"),
        ("type(session_date) is not date", "not isinstance(session_date, date)"),
        ("if session_date.year not in self.supported_years:", "if False:"),
        ("session_date.weekday() >= 5", "session_date.weekday() > 5"),
        ("time(9, 30)", "time(9, 31)"),
        ("close_hour = 13 if session_date in _EARLY_CLOSES else 16", "close_hour = 16"),
        ('ZoneInfo("America/New_York")', 'ZoneInfo("UTC")'),
        ('default="NYSE"', 'default="other"'),
        ('default="NYSE core equity regular session"', 'default="other scope"'),
        (
            'default="nyse-published-regular-sessions-2026-2028/v1"',
            'default="unreviewed/v2"',
        ),
        ("default=(2026, 2027, 2028)", "default=(2026, 2027, 2028, 2029)"),
        ("default=date(2026, 10, 4)", "default=date(2026, 10, 5)"),
        ("frozen=True", "frozen=False"),
        ("init=False", "init=True"),
        ("frozenset(", "set("),
        ("return ReviewPaperSessionSchedule(", "return other_schedule("),
    ],
)
def test_131s_authority_pins_manifest_and_schedule(tmp_path, old, new):
    root = _131s_authority_copy(tmp_path)
    path = root / "src/trading_bot/review_paper/nyse_published_regular_sessions.py"
    source = path.read_text(encoding="utf-8")
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    assert "131-S published regular-session boundary drift" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "comment", "reordered"])
def test_131s_authority_rejects_ci_invocation_drift(tmp_path, mutation):
    root = _131s_authority_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text(encoding="utf-8")
    name = "arch131-nyse-published-regular-session-authority"
    previous = "arch131-robinhood-supervised-prepare-verifier"
    line = f"              {name} `\n"
    assert source.count(line) == 1
    if mutation == "missing":
        source = source.replace(line, "")
    elif mutation == "duplicate":
        source = source.replace(line, f"              {name} `\n" + line)
    elif mutation == "comment":
        source = source.replace(line, f"              # {name}\n")
    else:
        source = source.replace(
            f"              {previous} `\n" + line,
            f"              {name} `\n              {previous} `\n",
        )
    path.write_text(source, encoding="utf-8")
    assert "131-S workflow invocation/order drift" in (
        runner._arch131_nyse_published_regular_session_authority_check(root)
    )


def test_131t_source_only_registration_and_batch():
    spec = runner._checkpoint_specs()[_T_NAME]
    assert (
        spec.description
        == "Architecture 131-T explicit-date published-session PREPARE binding"
    )
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.authority_check is _T_AUTHORITY
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/review_paper/test_published_session_prepare.py",
        "tests/test_robinhood_prepare_qualification_verifier.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        _T_SOURCE,
        "tests/review_paper/test_published_session_prepare.py",
        _T_VERIFIER,
        "tests/test_robinhood_prepare_qualification_verifier.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 47
    assert runner.ACTIVE_CI_CHECKPOINTS.count(_T_NAME) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(_T_NAME) == (
        runner.ACTIVE_CI_CHECKPOINTS.index(
            "arch131-nyse-published-regular-session-authority"
        )
        + 1
    )
    assert _T_AUTHORITY(Path(runner.__file__).resolve().parents[1]) == ()


@pytest.mark.parametrize("relative", [_T_SOURCE, _T_VERIFIER])
@pytest.mark.parametrize(
    "addition",
    [
        "from datetime import datetime",
        "datetime.now()",
        "date.today()",
        "import socket",
        "import httpx",
        "import os",
        "import subprocess",
        "import time",
        "sleep(1)",
        "while True:\n    pass",
        "config.read()",
        "scheduler.run()",
        "adapter.acquire_quotes()",
        "store.read_records()",
        "execute_review_paper_supervised_cycle()",
        "retry()",
        "poll()",
        "open('evidence.json', 'w')",
    ],
)
def test_131t_complete_boundaries_pinned(tmp_path, relative, addition):
    root = _131t_copy(tmp_path)
    path = root / relative
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert _T_AUTHORITY(root)


@pytest.mark.parametrize(
    "relative,old,new",
    [
        (_T_SOURCE, "if schedule is None:", "if False:"),
        (_T_SOURCE, "return schedule", "return None"),
        (_T_SOURCE, "schedule=schedule,", "schedule=None,"),
        (_T_SOURCE, "store=store,", "store=None,"),
        (_T_SOURCE, "schedule_for(session_date)", "schedule_for(date(2026, 10, 2))"),
        (
            _T_SOURCE,
            "return prepare_review_paper_supervised_cycle(",
            "return execute_review_paper_supervised_cycle(",
        ),
        (
            _T_SOURCE,
            "return run_review_paper_prepare_qualification(",
            "return other_qualification(",
        ),
        (_T_VERIFIER, "canonical is not None", "True"),
        (_T_VERIFIER, "opens_at == canonical.opens_at", "True"),
        (_T_VERIFIER, "closes_at == canonical.closes_at", "True"),
        (_T_VERIFIER, "schedule_for(session_date)", "schedule_for(date(2026, 10, 2))"),
        (_T_VERIFIER, "?mode=ro", "?mode=rw"),
    ],
)
def test_131t_resolution_delegation_and_verifier_guards_pinned(
    tmp_path, relative, old, new
):
    root = _131t_copy(tmp_path)
    path = root / relative
    source = path.read_text()
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    assert _T_AUTHORITY(root)


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_r7_execute"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        ("tests/scripts/certification_runner/test_profiles.py", "tests/missing.py"),
        (
            "_arch131_published_session_prepare_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131t_registration_drift(tmp_path, old, new):
    root = _131t_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    start = source.index(f'        "{_T_NAME}": CheckpointSpec(')
    end = source.index(
        '        "arch131-robinhood-published-prepare-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new) + source[end:], encoding="utf-8"
    )
    assert "131-T source-only checkpoint registration drift" in _T_AUTHORITY(root)


@pytest.mark.parametrize("field", ["preflight", "execute", "remote_branch"])
def test_131t_runtime_capability_drift(tmp_path, monkeypatch, field):

    root = _131t_copy(tmp_path)
    specs = runner._checkpoint_specs()

    def forbidden():
        pytest.fail("source gate must never invoke host/effect capabilities")

    specs[_T_NAME] = replace(
        specs[_T_NAME], **{field: "wrong" if field == "remote_branch" else forbidden}
    )
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert _T_AUTHORITY(root)


@pytest.mark.parametrize(
    "target", ["branch", "batch", "source_missing", "verifier_missing"]
)
def test_131t_authority_drift(tmp_path, target):
    root = _131t_copy(tmp_path)
    if target.endswith("missing"):
        (root / (_T_SOURCE if target == "source_missing" else _T_VERIFIER)).unlink()
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"', '"feature/wrong"'
            )
        else:
            previous = "arch131-nyse-published-regular-session-authority"
            source = source.replace(
                f'    "{previous}",\n    "{_T_NAME}",',
                f'    "{_T_NAME}",\n    "{previous}",',
            )
        path.write_text(source, encoding="utf-8")
    assert _T_AUTHORITY(root)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "comment", "reordered"])
def test_131t_ci_invocation_drift(tmp_path, mutation):
    root = _131t_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    line = f"              {_T_NAME} `\n"
    previous = "arch131-nyse-published-regular-session-authority"
    assert source.count(line) == 1
    if mutation == "missing":
        source = source.replace(line, "")
    elif mutation == "duplicate":
        source = source.replace(line, f"              {_T_NAME} `\n" + line)
    elif mutation == "comment":
        source = source.replace(line, f"              # {_T_NAME}\n")
    else:
        source = source.replace(
            f"              {previous} `\n" + line,
            f"              {_T_NAME} `\n              {previous} `\n",
        )
    path.write_text(source, encoding="utf-8")
    assert "131-T workflow invocation/order drift" in _T_AUTHORITY(root)


def test_131u_source_only_registration_and_batch():
    spec = runner._checkpoint_specs()[_U_NAME]
    assert (
        spec.description
        == "Architecture 131-U source-owned PREPARE transport composition"
    )
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert spec.authority_check is _U_AUTHORITY
    assert spec.tests == (
        *runner.ARCH131_TESTS,
        "tests/test_robinhood_prepare_operator.py",
        "tests/review_paper/test_published_session_prepare.py",
        "tests/review_paper/test_prepare_qualification.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert spec.ruff_paths == (
        *runner.ARCH131_RUFF_PATHS,
        _U_SOURCE,
        "tests/test_robinhood_prepare_operator.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
    assert len(runner.ACTIVE_CI_CHECKPOINTS) == 47
    assert runner.ACTIVE_CI_CHECKPOINTS.count(_U_NAME) == 1
    assert runner.ACTIVE_CI_CHECKPOINTS.index(_U_NAME) == (
        runner.ACTIVE_CI_CHECKPOINTS.index(
            "arch131-robinhood-published-session-prepare"
        )
        + 1
    )
    assert _U_AUTHORITY(Path(runner.__file__).resolve().parents[1]) == ()


@pytest.mark.parametrize("relative", [_U_SOURCE])
@pytest.mark.parametrize(
    "addition",
    [
        "from datetime import datetime",
        "datetime.now()",
        "date.today()",
        "import socket",
        "import httpx",
        "import os",
        "import subprocess",
        "import time",
        "sleep(1)",
        "while True:\n    pass",
        "config.read()",
        "scheduler.run()",
        "adapter.acquire_quotes()",
        "from trading_bot.execution.models import ExecutionInstruction",
        "from trading_bot.robinhood_paper_operator import run_robinhood_paper_operator",
        "run_robinhood_deterministic_paper_pipeline()",
        "run_robinhood_forward_paper_cycle()",
        "build_review_paper_intent()",
        "transport.get_accounts()",
        "transport.get_equity_orders()",
        "transport.review_equity_order()",
        "place_order()",
        "cancel_order()",
        "options_mutation()",
        "crypto_mutation()",
        "storage.get_tokens()",
        "storage.get_client_info()",
        "api.read_generic()",
        "webbrowser.open('private')",
        "uuid4()",
        "store.read_records()",
        "execute_review_paper_supervised_cycle()",
        "retry()",
        "poll()",
        "open('evidence.json', 'w')",
    ],
)
def test_131u_complete_boundaries_pinned(tmp_path, relative, addition):
    root = _131u_copy(tmp_path)
    path = root / relative
    path.write_text(path.read_text() + "\n" + addition + "\n", encoding="utf-8")
    assert _U_AUTHORITY(root)


@pytest.mark.parametrize(
    "old,new",
    [
        ("browser_opener=_block_interactive_authorization", "browser_opener=None"),
        (
            'raise LoopbackOAuthError("Interactive OAuth authorization is forbidden")',
            "return True",
        ),
        ("redirect_uri=redirect_uri", "redirect_uri='http://127.0.0.1:9999/callback'"),
        (
            "RobinhoodMcpStreamableHttpTransport(oauth_factory)",
            "RobinhoodMcpStreamableHttpTransport(None)",
        ),
        ("RobinhoodReviewReadAdapter(transport)", "RobinhoodReviewReadAdapter(None)"),
        ("adapter=adapter", "adapter=None"),
        ("session_date=session_date", "session_date=None"),
        ("store=store", "store=None"),
        ("evidence_path=evidence_path", "evidence_path=None"),
        (
            "return run_review_paper_published_session_prepare_qualification(",
            "return execute_review_paper_supervised_cycle(",
        ),
    ],
)
def test_131u_composition_and_blocker_pinned(tmp_path, old, new):
    root = _131u_copy(tmp_path)
    path = root / _U_SOURCE
    source = path.read_text()
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    assert _U_AUTHORITY(root)


@pytest.mark.parametrize(
    "old,new",
    [
        ("preflight=None", "preflight=_r7_execute"),
        ("execute=None", "execute=_r7_execute"),
        ("ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH", "ARCH131_REVIEW_PAPER_REMOTE_BRANCH"),
        ("*ARCH131_TESTS,", ""),
        ("*ARCH131_RUFF_PATHS,", ""),
        ("tests/scripts/certification_runner/test_profiles.py", "tests/missing.py"),
        (
            "_arch131_published_prepare_operator_authority_check",
            "_arch131_review_paper_authority_check",
        ),
    ],
)
def test_131u_registration_drift(tmp_path, old, new):
    root = _131u_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    start = source.index(f'        "{_U_NAME}": CheckpointSpec(')
    end = source.index(
        '        "arch131-robinhood-paper-operator": CheckpointSpec(', start
    )
    registration = source[start:end]
    assert old in registration
    path.write_text(
        source[:start] + registration.replace(old, new) + source[end:], encoding="utf-8"
    )
    assert "131-U source-only checkpoint registration drift" in _U_AUTHORITY(root)


@pytest.mark.parametrize("field", ["preflight", "execute", "remote_branch"])
def test_131u_runtime_capability_drift(tmp_path, monkeypatch, field):

    root = _131u_copy(tmp_path)
    specs = runner._checkpoint_specs()

    def forbidden():
        pytest.fail("source gate must never invoke host/effect capabilities")

    specs[_U_NAME] = replace(
        specs[_U_NAME], **{field: "wrong" if field == "remote_branch" else forbidden}
    )
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: specs)
    assert _U_AUTHORITY(root)


@pytest.mark.parametrize(
    "target", ["branch", "batch", "source_missing", "source_duplicate"]
)
def test_131u_authority_drift(tmp_path, target):
    root = _131u_copy(tmp_path)
    if target == "source_missing":
        (root / _U_SOURCE).unlink()
    elif target == "source_duplicate":
        path = root / _U_SOURCE
        path.write_text(
            path.read_text() + "\ndef helper(): return None\n", encoding="utf-8"
        )
    else:
        path = root / "scripts/checkpoint_runner.py"
        source = path.read_text()
        if target == "branch":
            source = source.replace(
                '"feature/robinhood-review-paper-side-foundation"', '"feature/wrong"'
            )
        else:
            previous = "arch131-robinhood-published-session-prepare"
            source = source.replace(
                f'    "{previous}",\n    "{_U_NAME}",',
                f'    "{_U_NAME}",\n    "{previous}",',
            )
        path.write_text(source, encoding="utf-8")
    assert _U_AUTHORITY(root)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "comment", "reordered"])
def test_131u_ci_invocation_drift(tmp_path, mutation):
    root = _131u_copy(tmp_path)
    path = root / ".github/workflows/checkpoint-source-gates.yml"
    source = path.read_text()
    line = f"              {_U_NAME} `\n"
    previous = "arch131-robinhood-published-session-prepare"
    assert source.count(line) == 1
    if mutation == "missing":
        source = source.replace(line, "")
    elif mutation == "duplicate":
        source = source.replace(line, f"              {_U_NAME} `\n" + line)
    elif mutation == "comment":
        source = source.replace(line, f"              # {_U_NAME}\n")
    else:
        source = source.replace(
            f"              {previous} `\n" + line,
            f"              {_U_NAME} `\n              {previous}\n",
        )
    path.write_text(source, encoding="utf-8")
    assert "131-U workflow invocation/order drift" in _U_AUTHORITY(root)


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_131u_source_gate_participant_drift(tmp_path, mutation):
    root = _131u_copy(tmp_path)
    path = root / "scripts/checkpoint_runner.py"
    source = path.read_text()
    line = f'    "{_U_NAME}",\n'
    assert source.count(line) == 1
    source = source.replace(line, "" if mutation == "missing" else line * 2)
    path.write_text(source, encoding="utf-8")
    assert "131-U checkpoint batch registration drift" in _U_AUTHORITY(root)


def test_131v_source_only_registration_and_boundaries(tmp_path):
    repo = Path(runner.__file__).resolve().parents[1]
    authority = runner._arch131_supervised_qualification_authority_check
    spec = runner._checkpoint_specs()["arch131-robinhood-supervised-qualification"]
    assert spec.preflight is None and spec.execute is None
    assert spec.remote_branch == "feature/robinhood-review-paper-side-foundation"
    assert authority(repo) == ()
    for relative in (
        "src/trading_bot/robinhood_supervised_qualification.py",
        "src/trading_bot/robinhood_execute_qualification_verifier.py",
        "scripts/robinhood_supervised_qualification.py",
        "src/trading_bot/review_paper/__init__.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_authority_fixture_text(repo, relative), encoding="utf-8")
    assert authority(tmp_path) == ()
    source = tmp_path / "src/trading_bot/robinhood_supervised_qualification.py"
    text_value = source.read_text(encoding="utf-8")
    for addition in (
        "callback()",
        "execute_review_paper_supervised_cycle()",
        "place_order()",
        "sleep(1)",
    ):
        source.write_text(text_value + "\n" + addition + "\n", encoding="utf-8")
        assert authority(tmp_path)


@pytest.mark.parametrize(
    "copy,authority",
    [
        (_131i_authority_copy, runner._arch131_paper_intent_bridge_authority_check),
        (
            _131j_authority_copy,
            runner._arch131_deterministic_paper_pipeline_authority_check,
        ),
        (_131k_authority_copy, runner._arch131_virtual_risk_context_authority_check),
        (_131l_authority_copy, runner._arch131_forward_paper_cycle_authority_check),
        (
            _131lq_authority_copy,
            runner._arch131_live_qualification_verifier_authority_check,
        ),
        (_131m_authority_copy, runner._arch131_session_admission_authority_check),
        (_131n_authority_copy, runner._arch131_risk_price_snapshot_authority_check),
        (_131o_authority_copy, runner._arch131_forward_paper_preview_authority_check),
        (_131p_authority_copy, runner._arch131_risk_price_acquisition_authority_check),
        (
            _131q_authority_copy,
            runner._arch131_supervised_forward_paper_authority_check,
        ),
        (
            _131s_authority_copy,
            runner._arch131_nyse_published_regular_session_authority_check,
        ),
        (_131t_copy, _T_AUTHORITY),
        (_131u_copy, _U_AUTHORITY),
    ],
)
def test_copied_local_authority_baseline_passes(tmp_path, copy, authority):
    # Prove compact and complete runner material once per accepted closure.
    root = copy(tmp_path)
    assert authority(root) == ()
    (root / "scripts/checkpoint_runner.py").write_bytes(
        Path(runner.__file__).read_bytes()
    )
    assert authority(root) == ()


@pytest.mark.parametrize("boundary", _R_PREPARE_BOUNDARIES)
def test_copied_prepare_authority_baseline_passes(tmp_path, boundary):
    root = _131r_copy(tmp_path, boundary)
    assert boundary[4](root) == ()
    (root / "scripts/checkpoint_runner.py").write_bytes(
        Path(runner.__file__).read_bytes()
    )
    assert boundary[4](root) == ()


@pytest.mark.parametrize(
    "authority,predecessor",
    [
        (
            "_arch131_agentic_account_authority_check",
            "_arch131_direct_mcp_authority_check",
        ),
        (
            "_arch131_agentic_account_authority_check",
            "_arch131_mcp_schema_authority_check",
        ),
        (
            "_arch131_agentic_account_authority_check",
            "_arch131_paper_cycle_authority_check",
        ),
        (
            "_arch131_paper_operator_authority_check",
            "_arch131_agentic_account_authority_check",
        ),
        (
            "_arch131_paper_operator_authority_check",
            "_arch131_windows_oauth_authority_check",
        ),
    ],
)
@pytest.mark.parametrize("failure", [(), ("predecessor rejected",)])
def test_predecessor_called_once_and_failure_propagates(
    monkeypatch, authority, predecessor, failure
):
    repo = Path(runner.__file__).resolve().parents[1]
    seen = []

    def previous(root):
        seen.append(root)
        return failure

    monkeypatch.setattr(runner, predecessor, previous)
    assert getattr(runner, authority)(repo) == failure
    assert seen == [repo]


def test_full_real_authority_chain_passes_and_visits_every_predecessor(monkeypatch):
    repo = Path(runner.__file__).resolve().parents[1]
    seen = []
    names = (
        "_arch131_agentic_account_authority_check",
        "_arch131_direct_mcp_authority_check",
        "_arch131_mcp_schema_authority_check",
        "_arch131_paper_cycle_authority_check",
        "_arch131_windows_oauth_authority_check",
    )
    for name in names:
        original = getattr(runner, name)

        def traced(root, original=original, name=name):
            seen.append((name, root))
            return original(root)

        monkeypatch.setattr(runner, name, traced)
    # Wrappers execute every real body; registry identities match the wrappers.
    registry = runner._checkpoint_specs()
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: registry)
    assert runner._arch131_paper_operator_authority_check(repo) == ()
    assert seen == [(name, repo) for name in names]


def test_runner_contract_fixture_preserves_registration_and_authority_material():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    full, compact = ast.parse(source), ast.parse(_runner_contract_source(source))

    def registrations(tree):
        return [
            ast.dump(node, include_attributes=False)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
        ]

    # Includes the batch constructor outside _checkpoint_specs, all retained and
    # active registrations, and any future constructor wherever it is declared.
    assert registrations(full) == registrations(compact)
    for name in ("ACTIVE_CI_CHECKPOINTS", "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"):

        def declaration(tree, name=name):
            return [
                ast.dump(node, include_attributes=False)
                for node in tree.body
                if isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == name
            ]

        assert declaration(full) == declaration(compact)

    def registry(tree):
        return next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_checkpoint_specs"
        )

    assert ast.dump(registry(full), include_attributes=False) == ast.dump(
        registry(compact), include_attributes=False
    )


def test_later_authority_implementation_growth_does_not_grow_runner_fixture():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    addition = (
        "\n\ndef later_authority_implementation():\n    return (\n"
        + "        'later source',\n" * 1000
        + "    )\n"
    )
    assert _runner_contract_source(source + addition) == _runner_contract_source(source)


@pytest.mark.parametrize(
    "name",
    [
        "ACTIVE_CI_CHECKPOINTS",
        "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH",
        "_checkpoint_specs",
    ],
)
@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_runner_contract_fixture_rejects_missing_or_duplicate_contract(name, mutation):
    source = _runner_contract_source(Path(runner.__file__).read_text(encoding="utf-8"))
    tree = ast.parse(source)
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == name
        or isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == name
    )
    material = ast.get_source_segment(source, node)
    assert source.count(material) == 1
    changed = source.replace(
        material, "" if mutation == "missing" else material + "\n\n" + material
    )
    with pytest.raises(ValueError, match="runner fixture requires one"):
        _runner_contract_source(changed)


@pytest.mark.parametrize(
    "mutation", ["accepted", "predecessor_pin", "registration", "workflow"]
)
def test_complete_real_chain_with_full_runner_material(tmp_path, monkeypatch, mutation):
    repo = Path(runner.__file__).resolve().parents[1]
    for relative in (
        "src/trading_bot/robinhood_paper_operator.py",
        "src/trading_bot/robinhood_mcp/sdk_transport.py",
        "src/trading_bot/robinhood_mcp/windows_oauth.py",
        "src/trading_bot/robinhood_mcp/adapter.py",
        "src/trading_bot/robinhood_mcp/account_resolution.py",
        "src/trading_bot/robinhood_mcp/__init__.py",
        "src/trading_bot/robinhood_paper_cycle.py",
        "scripts/checkpoint_runner.py",
        ".github/workflows/checkpoint-source-gates.yml",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((repo / relative).read_bytes())
    if mutation == "predecessor_pin":
        path = tmp_path / "src/trading_bot/robinhood_mcp/windows_oauth.py"
        before, after = "CRED_TYPE_GENERIC: Final = 1", "CRED_TYPE_GENERIC: Final = 2"
    elif mutation == "registration":
        path = tmp_path / "scripts/checkpoint_runner.py"
        before, after = "preflight=None,", "preflight=host_effect,"
    elif mutation == "workflow":
        path = tmp_path / ".github/workflows/checkpoint-source-gates.yml"
        before, after = "arch131-robinhood-paper-operator", "missing-checkpoint"
    if mutation != "accepted":
        source = path.read_text(encoding="utf-8")
        assert before in source
        path.write_text(source.replace(before, after), encoding="utf-8")
    names = (
        "_arch131_agentic_account_authority_check",
        "_arch131_direct_mcp_authority_check",
        "_arch131_mcp_schema_authority_check",
        "_arch131_paper_cycle_authority_check",
        "_arch131_windows_oauth_authority_check",
    )
    seen, outcomes, workflow_results = [], {}, []
    for name in names:
        original = getattr(runner, name)

        def traced(root, name=name, original=original):
            seen.append((name, root))
            result = original(root)
            outcomes[name] = result
            return result

        monkeypatch.setattr(runner, name, traced)
    workflow_check = runner._batch_workflow_is_reviewed

    def traced_workflow(workflow):
        result = workflow_check(workflow)
        workflow_results.append(result)
        return result

    monkeypatch.setattr(runner, "_batch_workflow_is_reviewed", traced_workflow)
    registry = runner._checkpoint_specs()
    monkeypatch.setattr(runner, "_checkpoint_specs", lambda: registry)
    failures = runner._arch131_paper_operator_authority_check(tmp_path)
    assert seen == [(name, tmp_path) for name in names]
    assert workflow_results == [mutation != "workflow"]
    if mutation == "accepted":
        assert failures == ()
    elif mutation == "workflow":
        assert failures
    else:
        propagated = outcomes["_arch131_windows_oauth_authority_check"]
        assert propagated
        assert set(propagated) <= set(failures)
