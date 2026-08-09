"""Explicitly opt-in, non-faking boundary for Windows authority acceptance."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from trading_bot.runtime.windows_authority import (
    PRODUCTION_AUTHORITY_PATHS,
    WindowsAuthorityError,
)
from trading_bot.runtime.windows_authority_provisioning import (
    validate_installed_authority,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("AI_TRADING_BOT_RUN_WINDOWS_AUTHORITY_ACCEPTANCE") != "1",
    reason="Milestone A acceptance requires explicit opt-in",
)


def test_fixed_authority_acceptance_prerequisites_are_present() -> None:
    """Never turn an absent administrator fixture into a passing acceptance."""

    if os.name != "nt":
        pytest.fail("Milestone A acceptance requires Windows")
    root = Path(str(PRODUCTION_AUTHORITY_PATHS.root))
    if not root.is_dir():
        pytest.fail("administrator-provisioned fixed authority root is absent")
    if not Path(str(PRODUCTION_AUTHORITY_PATHS.bootstrap)).is_file():
        pytest.fail("administrator-provisioned bootstrap is absent")
    if not Path(str(PRODUCTION_AUTHORITY_PATHS.signature)).is_file():
        pytest.fail("administrator-provisioned bootstrap signature is absent")
    if not Path(str(PRODUCTION_AUTHORITY_PATHS.database)).is_file():
        pytest.fail("administrator-provisioned authority database is absent")
    if not Path(str(PRODUCTION_AUTHORITY_PATHS.journal)).is_file():
        pytest.fail("administrator-provisioned persistent journal is absent")
    try:
        validate_installed_authority()
    except WindowsAuthorityError as error:
        pytest.fail(
            "administrator-provisioned authority validation is blocked by "
            f"{type(error).__name__}"
        )
