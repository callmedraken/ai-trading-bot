"""Explicit desktop composition for synthetic and real/disarmed modes."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trading_bot.live_prototype.application_service import (
        ApplicationIdentity,
        RealDisarmedApplicationService,
        ResearchWorker,
        RuntimeWorker,
    )
    from trading_bot.live_prototype.synthetic_service import (
        SyntheticApplicationService,
    )


class ApplicationMode(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    REAL_DISARMED = "REAL_DISARMED"


def compose_application_service(
    mode: ApplicationMode,
    *,
    identity: ApplicationIdentity | None = None,
    research_worker: ResearchWorker | None = None,
    runtime_worker: RuntimeWorker | None = None,
) -> SyntheticApplicationService | RealDisarmedApplicationService:
    """Construct only the explicitly selected, effect-disabled application mode."""
    from trading_bot.live_prototype.application_service import (
        ApplicationIdentity,
        RealDisarmedApplicationService,
    )
    from trading_bot.live_prototype.synthetic_service import SyntheticApplicationService

    if type(mode) is not ApplicationMode:
        raise TypeError("explicit ApplicationMode required")
    if mode is ApplicationMode.SYNTHETIC:
        if (
            identity is not None
            or research_worker is not None
            or runtime_worker is not None
        ):
            raise ValueError("synthetic mode does not accept real/disarmed inputs")
        return SyntheticApplicationService()
    if type(identity) is not ApplicationIdentity:
        raise ValueError("real/disarmed mode requires exact source/config identity")
    return RealDisarmedApplicationService(
        identity,
        research_worker=research_worker,
        runtime_worker=runtime_worker,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Five-page trading research prototype; all modes are disarmed"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=tuple(mode.value for mode in ApplicationMode),
        help="explicitly choose SYNTHETIC or REAL_DISARMED",
    )
    parser.add_argument("--source-head")
    parser.add_argument("--source-tree")
    parser.add_argument("--configuration-digest")
    parser.add_argument("--evidence-digest")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    source_root = str(Path(__file__).resolve().parents[2])
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    mode = ApplicationMode(arguments.mode)
    identity_args = (
        arguments.source_head,
        arguments.source_tree,
        arguments.configuration_digest,
        arguments.evidence_digest,
    )
    identity: ApplicationIdentity | None = None
    if mode is ApplicationMode.REAL_DISARMED:
        if any(value is None for value in identity_args[:3]):
            parser.error(
                "REAL_DISARMED requires --source-head, --source-tree, and "
                "--configuration-digest"
            )
        try:
            identity = ApplicationIdentity(
                source_head=arguments.source_head,
                source_tree=arguments.source_tree,
                configuration_digest=arguments.configuration_digest,
                evidence_digest=arguments.evidence_digest,
            )
        except (TypeError, ValueError):
            parser.error(
                "source, configuration, and evidence identities must be digests"
            )
    elif any(value is not None for value in identity_args):
        parser.error("identity arguments are accepted only in REAL_DISARMED mode")

    service = compose_application_service(mode, identity=identity)
    try:
        from PySide6.QtWidgets import QApplication

        from trading_bot.live_prototype.window import PrototypeWindow
    except ImportError:
        print(
            "GUI dependencies unavailable; install the reviewed gui extra",
            file=sys.stderr,
        )
        return 2

    app = QApplication.instance() or QApplication([])
    window = PrototypeWindow(service, mode=mode.value)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
