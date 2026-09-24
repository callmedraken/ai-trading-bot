"""Verified second-stage D10 import bootstrap.

A124-3 supplies only the sealed launcher entry point. The unattended D10
controller remains blocked until its later authority checkpoint.
"""

from __future__ import annotations

import sys

_SOURCE = r"F:\AITradingBot\D10\source\src"
_PACKAGES = r"F:\AITradingBot\runtime\Lib\site-packages"
_PYTHON = r"F:\AITradingBot\runtime\python.exe"
_SCRIPT = (
    r"F:\AITradingBot\D10\source\scripts"
    r"\run_personal_desktop_unattended_one_week_soak.py"
)
_CACHE = r"F:\AITradingBot\D10\no-pycache"


def main() -> int:
    if (
        sys.executable != _PYTHON
        or sys.argv != [_SCRIPT]
        or not (
            sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
        )
        or sys.pycache_prefix != _CACHE
        or _SOURCE in sys.path
        or _PACKAGES in sys.path
    ):
        return 1
    sys.path.insert(0, _SOURCE)
    sys.path.append(_PACKAGES)
    from trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract import (  # noqa: E402, E501
        D10_SCHEDULER_CONTRACT,
        is_frozen_one_week_soak_scheduler_contract,
    )

    if not is_frozen_one_week_soak_scheduler_contract(D10_SCHEDULER_CONTRACT):
        return 1
    from trading_bot.runtime.personal_desktop_d10_deployment_verifier import (  # noqa: E402
        require_verified_d10_activation_lease,
        require_verified_d10_deployment,
        verify_d10_activation_lease,
        verify_d10_deployment,
    )

    try:
        deployment = require_verified_d10_deployment(verify_d10_deployment())
        lease = verify_d10_activation_lease(deployment)
        require_verified_d10_activation_lease(lease, deployment)
    except Exception:
        return 1
    # The effectful one-wake controller remains a later checkpoint.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
