"""One explicit bounded local contract read, cached including failures."""

from pathlib import Path, PureWindowsPath

from trading_bot.gui.production_strategy_models import (
    MAX_PRODUCTION_STRATEGY_BYTES,
    ProductionStrategyContractView,
    ProductionStrategyDiagnostic,
    ProductionStrategyPageState,
    ProductionStrategyPageStatus,
)
from trading_bot.strategies.production import ProductionStrategyContract


class ProductionStrategyContractInspectionService:
    """Inspect inert contract material without composing production runtime."""

    def __init__(self, artifact_path: Path) -> None:
        if not isinstance(artifact_path, Path):
            raise TypeError("Explicit Path required")
        self._path = artifact_path
        self._cached: ProductionStrategyPageState | None = None

    def get_production_strategy_state(self) -> ProductionStrategyPageState:
        if self._cached is None:
            self._cached = self._acquire()
        return self._cached

    def _acquire(self) -> ProductionStrategyPageState:
        try:
            text = str(self._path)
            windows = PureWindowsPath(text)
            # Local paths only: reject UNC/device namespaces, URI/ADS syntax,
            # control characters and drive-relative paths before opening anything.
            if (
                self._path.suffix.casefold() != ".json"
                or text.startswith(("\\\\", "//"))
                or "\x00" in text
                or any(ord(char) < 32 for char in text)
                or ":" in text[len(windows.drive) :]
                or (windows.drive and (len(windows.drive) != 2 or not windows.root))
            ):
                raise ValueError("Unsupported local path")
            with self._path.open("rb") as stream:
                payload = stream.read(MAX_PRODUCTION_STRATEGY_BYTES + 1)
            if len(payload) > MAX_PRODUCTION_STRATEGY_BYTES:
                raise ValueError("Oversized contract")
            contract = ProductionStrategyContract.from_json(payload.decode("utf-8"))
            config = contract.strategy_config
            view = ProductionStrategyContractView(
                contract.contract_id,
                contract.target_session_date,
                contract.source_head,
                contract.source_tree,
                contract.strategy_id,
                contract.strategy_version,
                str(contract.symbol),
                config.short_window,
                config.long_window,
                config.desired_quantity,
            )
            return ProductionStrategyPageState(
                ProductionStrategyPageStatus.AVAILABLE,
                ProductionStrategyDiagnostic.RECORDED,
                view,
            )
        except (OSError, ValueError, TypeError, ArithmeticError, RecursionError):
            return ProductionStrategyPageState(
                ProductionStrategyPageStatus.ATTENTION,
                ProductionStrategyDiagnostic.INVALID,
            )
