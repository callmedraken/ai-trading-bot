"""Verified second-stage D10 import bootstrap and one-wake entry point."""

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
    try:
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

        deployment = require_verified_d10_deployment(verify_d10_deployment())
        lease = verify_d10_activation_lease(deployment)
        require_verified_d10_activation_lease(lease, deployment)

        # Keep the sealed guard/A4/ACTIVE-lease provenance objects intact.
        from trading_bot.runtime.personal_desktop_unattended_one_week_soak import (  # noqa: E402
            D10WakeOutcome,
            run_personal_desktop_unattended_one_week_soak,
            serialize_d10_wake_evidence,
        )

        evidence = run_personal_desktop_unattended_one_week_soak(deployment, lease)
        print(serialize_d10_wake_evidence(evidence), flush=True)
        return 0 if evidence.outcome is not D10WakeOutcome.STOPPED else 1
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
