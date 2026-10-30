"""Current owner of the exact P3 lazy-export compatibility transformation.

Historical source objects and declarations remain immutable. The sole permitted
change is deferring the original imports through an exact resolver. Every other
initializer statement, export name, owning module and requested object survives.
No package code is imported or executed by this static authority check.
"""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

from scripts.source_authority import historical_blob

MARKET_DATA_INITIALIZER = "src/trading_bot/market_data/__init__.py"
EXPERIMENTS_INITIALIZER = "src/trading_bot/experiments/__init__.py"
# Accepted P2 export surface, not a new current-byte pin or historical repin.
EXPERIMENTS_PREDECESSOR_BLOB = "9cae91a03fb02e3f2514f0ae8364960ad6021e8c"
DEFERRED_PROVIDER_MODULES = frozenset(
    {
        "trading_bot.market_data.alpaca_daily_snapshot",
        "trading_bot.market_data.alpaca_http",
    }
)

_RESOLVER = '''
def __getattr__(name: str) -> object:
    """Resolve the unchanged public API only when that export is requested."""
    owner = _LAZY_EXPORTS.get(name)
    if owner is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(owner), name)
    globals()[name] = value
    return value

def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
'''


def _expected_lazy_initializer(
    predecessor: ast.Module,
    deferred_modules: frozenset[str] | None,
) -> ast.Module:
    """Derive the only admitted current AST from immutable predecessor fields."""
    old = deepcopy(predecessor)
    imports = [node for node in old.body if isinstance(node, ast.ImportFrom)]
    deferred = [
        node
        for node in imports
        if deferred_modules is None or node.module in deferred_modules
    ]
    if not deferred or (
        deferred_modules is not None
        and {node.module for node in deferred} != deferred_modules
    ):
        raise ValueError("exact predecessor import owners required")
    groups = {}
    for node in deferred:
        if node.level or not node.module or node.module in groups:
            raise ValueError("unsupported predecessor import shape")
        names = tuple(alias.name for alias in node.names)
        if any(alias.asname is not None or alias.name == "*" for alias in node.names):
            raise ValueError("explicit unaliased predecessor exports required")
        groups[node.module] = names
    if len({name for names in groups.values() for name in names}) != sum(
        len(names) for names in groups.values()
    ):
        raise ValueError("duplicate predecessor lazy exports")
    # Retain all non-deferred statements including the entire public __all__.
    retained = [node for node in old.body if node not in deferred]
    insertion = next(
        i
        for i, node in enumerate(retained)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    )
    mappings = ast.parse(
        f"_LAZY_EXPORT_GROUPS = {groups!r}\n"
        "_LAZY_EXPORTS = {name: owner "
        "for owner, names in _LAZY_EXPORT_GROUPS.items() for name in names}"
    ).body
    retained[insertion:insertion] = mappings
    retained.insert(1, ast.parse("from importlib import import_module").body[0])
    retained.extend(ast.parse(_RESOLVER).body)
    return ast.Module(body=retained, type_ignores=old.type_ignores)


def initializer_preserves_exports(
    repo_root: Path,
    relative: str,
    historical_pin: str,
) -> bool:
    """Fail closed on any additional import, statement, export or resolver drift."""
    try:
        if relative == MARKET_DATA_INITIALIZER:
            from scripts import checkpoint_runner as runner

            if historical_pin != runner.READONLY_SOURCE_PINS[relative]:
                return False
            deferred = DEFERRED_PROVIDER_MODULES
        elif relative == EXPERIMENTS_INITIALIZER:
            if historical_pin != EXPERIMENTS_PREDECESSOR_BLOB:
                return False
            deferred = None
        else:
            return False
        old = ast.parse(historical_blob(repo_root, historical_pin).decode("utf-8"))
        current = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
        expected = _expected_lazy_initializer(old, deferred)
        return ast.dump(current) == ast.dump(expected)
    except (OSError, ValueError, SyntaxError, KeyError, TypeError, StopIteration):
        return False


def desktop_export_authority_failures(repo_root: Path) -> tuple[str, ...]:
    """Own both current initializers; preserve protected source classification."""
    from scripts import checkpoint_runner as runner

    pins = (
        (MARKET_DATA_INITIALIZER, runner.READONLY_SOURCE_PINS[MARKET_DATA_INITIALIZER]),
        (EXPERIMENTS_INITIALIZER, EXPERIMENTS_PREDECESSOR_BLOB),
    )
    return tuple(
        "147 lazy export compatibility drift: " + relative
        for relative, pin in pins
        if not initializer_preserves_exports(repo_root, relative, pin)
    )
