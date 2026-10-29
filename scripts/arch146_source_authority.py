"""Current owner of 146-A compatibility across the additive 146-B extraction."""

import ast
import re
from copy import deepcopy
from pathlib import Path

from scripts.source_authority import historical_blob

DATASET_SOURCE = "src/trading_bot/experiments/historical_research_dataset.py"


def dataset_preserves_146a_contract(repo_root: Path, historical_pin: str) -> bool:
    """Reconstruct the complete immutable old AST from the reviewed extraction.

    No historical declaration is repinned. Current wrappers/signatures must be
    exactly the reviewed composition; all remaining source semantics reconstruct
    the old module including schemas, IDs, serializers and physical checks.
    """
    old = ast.parse(historical_blob(repo_root, historical_pin).decode("utf-8"))
    current = ast.parse((repo_root / DATASET_SOURCE).read_text(encoding="utf-8"))
    declarations = [node for node in current.body if isinstance(node, ast.FunctionDef)]
    functions = {node.name: node for node in declarations}
    if len(functions) != len(declarations):
        return False
    physical = deepcopy(functions["_verify_historical_research_partition_physical"])
    physical.name = "verify_historical_research_partition"
    physical.body.insert(
        -1, ast.parse("validate_historical_research_session_coverage(data)").body[0]
    )
    wrapper = functions[physical.name]
    expected_body = ast.parse(
        "data = _verify_historical_research_partition_physical("
        "material, historical_result); "
        "validate_historical_research_session_coverage(data); return data"
    ).body
    if (
        ast.get_docstring(wrapper) is None
        or [ast.dump(node) for node in wrapper.body[1:]]
        != [ast.dump(node) for node in expected_body]
        or ast.dump(wrapper.args) != ast.dump(physical.args)
        or ast.dump(wrapper.returns) != ast.dump(physical.returns)
        or wrapper.decorator_list
        or wrapper.type_params
    ):
        return False
    full = deepcopy(functions["verify_historical_research_dataset"])
    expected_return = ast.parse(
        "return _complete_historical_research_dataset_verification("
        "snapshot, open_material, holdout_material, opened, holdout)"
    ).body[0]
    if ast.dump(full.body[-1]) != ast.dump(expected_return):
        return False
    complete = functions["_complete_historical_research_dataset_verification"]
    signature = ast.parse(
        "def _complete_historical_research_dataset_verification("
        "snapshot: HistoricalResearchDatasetSnapshot,"
        "open_material: HistoricalResearchPartitionMaterial,"
        "holdout_material: HistoricalResearchPartitionMaterial,"
        "opened: HistoricalDataResult, holdout: HistoricalDataResult"
        ") -> HistoricalResearchDatasetVerification: pass"
    ).body[0]
    if (
        ast.dump(complete.args) != ast.dump(signature.args)
        or ast.dump(complete.returns) != ast.dump(signature.returns)
        or complete.decorator_list
        or complete.type_params
        or ast.get_docstring(complete) is None
    ):
        return False
    full.body[-1:] = deepcopy(complete.body[1:])
    reconstructed = []
    for node in current.body:
        if isinstance(node, ast.FunctionDef):
            if node.name == "_verify_historical_research_partition_physical":
                reconstructed.append(physical)
                continue
            if node.name in {physical.name, complete.name}:
                continue
            if node.name == full.name:
                reconstructed.append(full)
                continue
        reconstructed.append(node)
    current.body = reconstructed
    return ast.dump(current) == ast.dump(old)


def research_credential_boundary_isolated(repo_root: Path) -> bool:
    """Reject production-principal/store/fallback authority in the Arch146 path."""
    if not research_operator_token_semantics_current(repo_root):
        return False
    forbidden_names = {
        "TRADING_SID",
        "approved_trading_sid",
        "PERSONAL_DESKTOP_FIRST_PAPER_OPERATION_PROFILE",
        "read_current_product_alpaca_secrets",
        "read_fixed_current_product_credential",
        "WindowsAlpacaCredentialManagerReader",
        "CredReadW",
        "CredWriteW",
        "environ",
        "getenv",
    }
    for relative in (
        "src/trading_bot/experiments/historical_research_native.py",
        "src/trading_bot/experiments/historical_research_b2_preflight.py",
    ):
        tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                return False
            if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                return False
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if re.fullmatch(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", node.value):
                    return False
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                == ("trading_bot.review_paper.alpaca_windows_credentials")
                and any(
                    alias.name != "validate_alpaca_credential_bytes"
                    for alias in node.names
                )
            ):
                return False
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if any(alias.name in forbidden_names for alias in node.names):
                    return False
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and (
                        "unattended_host_identity" in node.module
                        or "personal_desktop_first_paper_operation" in node.module
                    )
                ):
                    return False
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and any(
                    target in node.value
                    for target in (
                        "AITradingBot/MarketData/Alpaca/",
                        "windows-credential-manager-alpaca-",
                    )
                )
            ):
                return False
    return True


def research_operator_token_semantics_current(repo_root: Path) -> bool:
    """Own the effective-admin observation, without production Trading admission."""
    tree = ast.parse(
        (
            repo_root / "src/trading_bot/experiments/historical_research_native.py"
        ).read_text(encoding="utf-8")
    )
    expected = ast.parse(
        "observed = WindowsTradingTokenObserver().observe(); "
        "\nif observed.token_type != 1 or observed.thread_token_present is not False:"
        "\n    raise HistoricalResearchCustodyError('research token identity unproven')"
        "\nreturn ResearchOperatorToken(observed.user_sid, observed.elevated, "
        "any(sid == ADMINISTRATORS_SID and attributes & SE_GROUP_ENABLED "
        "and not attributes & SE_GROUP_USE_FOR_DENY_ONLY "
        "for sid, attributes in observed.groups))"
    )
    declarations = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "observe_research_operator_token"
    ]
    required = {
        "ADMINISTRATORS_SID",
        "SE_GROUP_ENABLED",
        "SE_GROUP_USE_FOR_DENY_ONLY",
        "WindowsTradingTokenObserver",
    }
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "trading_bot.arch133_verifier.token"
        for alias in node.names
        if alias.asname is None
    }
    return (
        required <= imported
        and len(declarations) == 1
        and ast.get_docstring(declarations[0]) is not None
        and [ast.dump(node) for node in declarations[0].body[1:]]
        == [ast.dump(node) for node in expected.body]
    )
