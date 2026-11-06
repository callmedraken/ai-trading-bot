import os
from threading import Event
from time import monotonic, sleep

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QListWidget, QPushButton

from trading_bot.live_prototype.application import main
from trading_bot.live_prototype.application_service import (
    ApplicationIdentity,
    RealDisarmedApplicationService,
)
from trading_bot.live_prototype.contracts import Command
from trading_bot.live_prototype.window import PrototypeWindow


def _wait_for(application: QApplication, condition, timeout: float = 3.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        application.processEvents()
        if condition():
            return True
        sleep(0.005)
    application.processEvents()
    return condition()


def test_desktop_entrypoint_requires_explicit_mode_and_identity(capsys):
    with pytest.raises(SystemExit) as missing_mode:
        main([])
    assert missing_mode.value.code == 2
    assert "--mode" in capsys.readouterr().err

    with pytest.raises(SystemExit) as missing_identity:
        main(["--mode", "REAL_DISARMED"])
    assert missing_identity.value.code == 2
    assert "requires --source-head" in capsys.readouterr().err


def test_real_disarmed_window_preserves_pages_and_waits_for_shutdown():
    application = QApplication.instance() or QApplication([])
    worker_started = Event()
    release_worker = Event()
    identity = ApplicationIdentity(
        source_head="a" * 40,
        source_tree="b" * 40,
        configuration_digest="c" * 64,
    )

    def delayed_research_worker(_stop, _publish):
        worker_started.set()
        release_worker.wait(timeout=4)

    service = RealDisarmedApplicationService(
        identity, research_worker=delayed_research_worker
    )
    window = PrototypeWindow(service, mode="REAL_DISARMED")
    window.show()
    application.processEvents()
    navigation = window.findChild(QListWidget, "prototypeNavigation")
    assert navigation is not None and navigation.count() == 5
    start = window.findChild(QPushButton, "sessionStartDisarmedWorkers")
    assert start is not None

    try:
        start.click()
        assert worker_started.wait(timeout=2)
        window.close()
        application.processEvents()
        assert window.isVisible()
        assert not service.shutdown_complete()

        release_worker.set()
        assert _wait_for(application, service.shutdown_complete)
        assert _wait_for(application, lambda: not window.isVisible())
    finally:
        release_worker.set()
        service.submit(Command.STOP)
        assert _wait_for(application, service.shutdown_complete)
        window.close()
        application.processEvents()
