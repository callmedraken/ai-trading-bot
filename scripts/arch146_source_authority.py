"""Current owner of 146-A compatibility across the additive 146-B extraction."""

import ast
import re
from copy import deepcopy
from pathlib import Path

from scripts.source_authority import historical_blob

DATASET_SOURCE = "src/trading_bot/experiments/historical_research_dataset.py"
B2_PREFLIGHT_SOURCE = "src/trading_bot/experiments/historical_research_b2_preflight.py"
PARTIAL_STATE_SOURCE = (
    "src/trading_bot/experiments/historical_research_partial_state.py"
)


def partial_state_observer_is_readonly(repo_root: Path) -> bool:
    """Admit only the bounded observer/native call graph, never execute it."""
    observer = ast.parse((repo_root / PARTIAL_STATE_SOURCE).read_text(encoding="utf-8"))
    native = ast.parse(
        (
            repo_root
            / "src/trading_bot/experiments/historical_research_native_custody.py"
        ).read_text(encoding="utf-8")
    )
    methods = [
        method
        for cls in native.body
        if isinstance(cls, ast.ClassDef) and cls.name == "WindowsCustodyNative"
        for method in cls.body
        if isinstance(method, ast.FunctionDef)
        and method.name == "observe_partial_state_readonly"
    ]
    if len(methods) != 1:
        return False
    allowed_imports = {
        "__future__",
        "collections",
        "collections.abc",
        "trading_bot.experiments.historical_research_native_custody",
        "trading_bot.runtime.windows_authority_security",
    }
    allowed_observer_calls = {
        "frozenset",
        "tuple",
        "type",
        "len",
        "any",
        "zip",
        "Counter",
        "casefold",
        "upper",
        "CustodyPartialState",
        "observe",
        "_observe",
        "_classification",
        "WindowsCustodyNative",
        "fromkeys",
    }
    allowed_native_calls = {
        "CustodyPartialState",
        "_api",
        "c_void_p",
        "get_last_error",
        "_error",
        "append",
        "PureWindowsPath",
        "reversed",
        "str",
        "open_existing",
        "inspect_open_authority_object",
        "replace",
        "tuple",
        "sorted",
        "_close",
    }
    for tree, allowed in (
        (observer, allowed_observer_calls),
        (methods[0], allowed_native_calls),
    ):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                return False
            if isinstance(node, ast.ImportFrom) and node.module not in allowed_imports:
                return False
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else None
                )
                if isinstance(node.func, ast.Call):
                    # Only the two explicitly bounded Win32 functions below.
                    inner = node.func
                    if (
                        not isinstance(inner.func, ast.Attribute)
                        or inner.func.attr != "_api"
                        or not isinstance(inner.func.value, ast.Name)
                        or inner.func.value.id != "self"
                    ):
                        return False
                    call = ast.unparse(node)
                    expected = (
                        "self._api('kernel32', 'CreateFileW', "
                        "[ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, "
                        "ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, "
                        "ctypes.c_void_p], ctypes.c_void_p)"
                        "(path, access, 3, None, 3, 0x02200000, None)",
                        "self._api('kernel32', 'GetDriveTypeW', "
                        "[ctypes.c_wchar_p], ctypes.c_uint32)('F:\\\\')",
                    )
                    if not any(
                        call == ast.unparse(ast.parse(item).body[0].value)
                        for item in expected
                    ):
                        return False
                elif name not in allowed:
                    return False
    access_calls = [
        ast.unparse(node)
        for node in ast.walk(methods[0])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open_existing"
    ]
    if sorted(access_calls) != [
        "open_existing(path, 128)",
        "open_existing(path, 131200)",
    ]:
        return False
    runner = ast.parse(
        (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
    )
    dispatch = [
        node
        for node in runner.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_arch146_partial_state_preflight"
    ]
    expected_dispatch = ast.parse(
        "def _arch146_partial_state_preflight() -> dict[str, object]:"
        "\n    from trading_bot.experiments.historical_research_partial_state "
        "import partial_state_readonly_preflight"
        "\n    return partial_state_readonly_preflight()"
    ).body[0]
    return len(dispatch) == 1 and ast.dump(dispatch[0]) == ast.dump(expected_dispatch)


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


def research_source_binding_tracked_only_current(repo_root: Path) -> bool:
    """Own the B2 exact-source cleanliness rule without untracked enumeration."""
    tree = ast.parse((repo_root / B2_PREFLIGHT_SOURCE).read_text(encoding="utf-8"))
    declarations = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_source"
    ]
    if len(declarations) != 1 or ast.get_docstring(declarations[0]) is not None:
        return False
    expected = ast.parse(
        '_git(root, "status", "--porcelain=v1", "--untracked-files=no")',
        mode="eval",
    ).body
    status_calls = [
        node
        for node in ast.walk(declarations[0])
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_git"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "status"
        )
    ]
    return len(status_calls) == 1 and ast.dump(status_calls[0]) == ast.dump(expected)


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


def research_custody_ace_semantics_current(repo_root: Path) -> bool:
    """Own exact all-allow ACE multisets; never execute a native host observer.

    Compare the current method's complete AST with the reviewed composition,
    including owner/protection and binary SID/mask/type/flags. This is a current
    semantic rule, independent of historical blobs and SDDL text ordering.
    """
    tree = ast.parse(
        (
            repo_root
            / "src/trading_bot/experiments/historical_research_native_custody.py"
        ).read_text(encoding="utf-8")
    )
    expected = ast.parse(
        "def _security(self, handle: int, path: str, *, "
        "directory: bool, opened: bool) -> None:"
        "\n    facts = inspect_open_authority_object(handle, path, "
        "AuthorityObjectKind.DIRECTORY if directory else AuthorityObjectKind.FILE)"
        "\n    flags = 3 if directory else 0"
        "\n    expected = [(ADMIN, 0x1F01FF, 0, flags), "
        "(SYSTEM, 0x1F01FF, 0, flags)]"
        "\n    if opened:"
        "\n        expected.append((USERS, 0x1200A9, 0, flags))"
        "\n    actual = tuple((a.principal_sid, a.access_mask, "
        "a.ace_type, a.ace_flags) for a in facts.aces)"
        "\n    if (facts.owner_sid != ADMIN or facts.dacl_protected is not True "
        "or Counter(actual) != Counter(expected)):"
        "\n        raise _error()"
    ).body[0]
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "WindowsCustodyNative"
    ]
    if len(classes) != 1:
        return False
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "_security"
    ]
    imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "collections"
    ]
    constants = {
        "ADMIN": "S-1-5-32-544",
        "SYSTEM": "S-1-5-18",
        "USERS": "S-1-5-32-545",
    }
    for name, value in constants.items():
        assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
        ]
        if len(assignments) != 1 or ast.dump(assignments[0]) != ast.dump(
            ast.parse(f"{name} = {value!r}").body[0]
        ):
            return False
    return (
        len(methods) == 1
        and ast.dump(methods[0]) == ast.dump(expected)
        and any(
            alias.name == "Counter" and alias.asname is None
            for node in imports
            for alias in node.names
        )
        and not any(
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and node.id == "Counter"
            for node in ast.walk(tree)
        )
    )
