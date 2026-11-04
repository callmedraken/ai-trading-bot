"""Effect-free help and explicit isolated synthetic desktop launcher."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Isolated synthetic trading research desktop"
    )
    result.add_argument(
        "--synthetic", action="store_true", help="use fakes only; no live transport"
    )
    result.add_argument(
        "--state-root", type=Path, help="fresh absolute external F: directory"
    )
    result.add_argument(
        "--comparison-report",
        type=Path,
        help="explicit comparison report, loaded on a worker",
    )
    return result


def prepare_state_root(
    path: Path, source_root: Path, *, allowed_temp_root: Path = Path(r"F:\AI\temp")
) -> None:
    """Create an explicit synthetic marker; never reuse or repair existing state."""
    if (
        not path.is_absolute()
        or ".." in path.parts
        or not allowed_temp_root.is_absolute()
        or allowed_temp_root not in path.parents
        or path == source_root
        or source_root in path.parents
        or path in source_root.parents
    ):
        raise ValueError("fresh external absolute F: state root required")
    for parent in (path, *path.parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("state aliases are not supported")
    if path.exists():
        raise ValueError("state root exists; preserve it and choose a fresh directory")
    path.mkdir(parents=True, exist_ok=False)
    with (path / "synthetic-workspace.json").open("x", encoding="utf-8") as stream:
        json.dump(
            {"schema": "prototype-synthetic-workspace/v1", "mode": "SYNTHETIC"}, stream
        )
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    if not arguments.synthetic or arguments.state_root is None:
        parser().error(
            "--synthetic and --state-root are required; live mode is unavailable"
        )
    if (
        arguments.comparison_report is not None
        and not arguments.comparison_report.is_absolute()
    ):
        parser().error("comparison report path must be absolute")
    root = Path(__file__).resolve().parents[1]
    # This process resolves only this checkout, independent of editable installs.
    sys.path.insert(0, str(root / "src"))
    try:
        from PySide6.QtWidgets import QApplication

        from trading_bot.live_prototype.synthetic_service import (
            SyntheticApplicationService,
        )
        from trading_bot.live_prototype.window import PrototypeWindow
    except ImportError:
        print(
            "GUI dependencies unavailable; install the reviewed gui extra",
            file=sys.stderr,
        )
        return 2
    try:
        prepare_state_root(arguments.state_root, root)
    except (OSError, ValueError):
        print("SYNTHETIC_STATE_ROOT_REJECTED; preserve existing state", file=sys.stderr)
        return 2
    app = QApplication.instance() or QApplication([])
    service = SyntheticApplicationService()
    window = PrototypeWindow(service)
    if arguments.comparison_report is not None:
        service.request_report(arguments.comparison_report)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
