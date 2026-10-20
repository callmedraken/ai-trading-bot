"""Unified source-checkpoint runner for AI Trading Bot development.

This module centralizes source verification, read-only host preflight, and
registered protected checkpoint execution. Protected execution remains opt-in,
checkpoint-specific, and authorization-gated.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_SRC_ROOT = _REPOSITORY_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

SCHEMA: Final = "ai-trading-bot-checkpoint-runner/v1"
REMOTE_LOOKUP_TIMEOUT_SECONDS: Final = 30
R5_TRADING_PID_ENV: Final = "AI_TRADING_BOT_ARCH128_R5_TRADING_PID"
R5_TRADING_REMOTE_HEAD_ENV: Final = "AI_TRADING_BOT_ARCH128_R5_ADMIN_REMOTE_HEAD"
R5_PRODUCTION_PYTHON: Final = Path(r"F:\AITradingBot\runtime\python.exe")
R5_PYCACHE_PREFIX: Final = r"F:\AITradingBot\D10\no-pycache"


@dataclass(frozen=True, slots=True)
class CheckpointSpec:
    name: str
    description: str
    tests: tuple[str, ...]
    ruff_paths: tuple[str, ...]
    authority_check: Callable[[Path], tuple[str, ...]]
    preflight: Callable[[], dict[str, object]] | None = None
    execute: Callable[[], dict[str, object]] | None = None
    remote_branch: str | None = None
    remote_head_env: str | None = None


@dataclass(frozen=True, slots=True)
class Step:
    name: str
    argv: tuple[str, ...]
    diagnostic_argv: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    name: str
    argv: tuple[str, ...]
    exit_code: int
    stdout_bytes: int
    stderr_bytes: int
    stdout_sha256: str
    stderr_sha256: str
    stdout_path: str
    stderr_path: str
    elapsed_seconds: float = 0.0


COMMON_TESTS: Final = (
    "tests/runtime/checkpoint_runner/test_core.py",
    "tests/runtime/checkpoint_runner/test_ci.py",
)
COMMON_RUFF_PATHS: Final = (
    "scripts/checkpoint_runner.py",
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/helpers.py",
    "tests/runtime/checkpoint_runner/__init__.py",
)
ARCH131_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_arch131.py",
)
ARCH131_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_arch131.py",
)
ARCH133_A_G_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
)
ARCH133_A_G_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py",
)
ARCH133_H_K_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
)
ARCH133_H_K_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py",
)
ARCH133_L_M_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
)
ARCH133_L_M_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py",
)
RETAINED_TESTS: Final = (
    *COMMON_TESTS,
    "tests/runtime/checkpoint_runner/test_retained_arch128_130.py",
)
RETAINED_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "tests/runtime/checkpoint_runner/test_retained_arch128_130.py",
)


RETAINED_CHECKPOINTS: Final = (
    "arch128-parent-acl-repair",
    "arch128-r4",
    "arch128-r5-substrate",
    "arch128-r5-trading",
    "arch128-r6",
    "arch128-r7",
    "arch128-r8-terminal-halt",
    "arch130-r8i-d1",
)

# Reviewed pin of the complete active tuple AST; refresh only with topology review.
REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256: Final = (
    "5a9f7a0a069cbcd89b07ca9114f5618e44b0ba07ace5d3bd81fae423e0649515"
)

# Registered historical recovery remains closed; it is excluded from active CI.
ACTIVE_CI_CHECKPOINTS: Final = (
    "arch133-robinhood-supervised-release-installation-operator",
    "arch133-robinhood-supervised-deployment-qualification",
    "arch133-robinhood-supervised-runtime-host-admission",
    "arch133-robinhood-supervised-maintenance-rebind",
    "arch133-robinhood-supervised-release-installation",
    "arch133-robinhood-supervised-release-build-verification",
    "arch133-robinhood-supervised-release-foundation",
    "arch131-robinhood-review-paper",
    "arch131-robinhood-mcp-schema",
    "arch131-robinhood-paper-cycle",
    "arch131-robinhood-performance",
    "arch131-robinhood-direct-mcp",
    "arch131-robinhood-oauth-windows",
    "arch131-robinhood-agentic-account",
    "arch131-robinhood-paper-operator",
    "arch131-robinhood-paper-intent-bridge",
    "arch131-robinhood-deterministic-paper-pipeline",
    "arch131-robinhood-virtual-risk-context",
    "arch131-robinhood-forward-paper-cycle",
    "arch131-robinhood-live-qualification-verifier",
    "arch131-robinhood-session-admission",
    "arch131-robinhood-risk-price-snapshot",
    "arch131-robinhood-forward-paper-preview",
    "arch131-robinhood-risk-price-acquisition",
    "arch131-robinhood-supervised-forward-paper",
    "arch131-robinhood-supervised-prepare-qualification",
    "arch131-robinhood-supervised-prepare-verifier",
    "arch131-nyse-published-regular-session-authority",
    "arch131-robinhood-published-session-prepare",
    "arch131-robinhood-published-prepare-operator",
    "arch131-robinhood-supervised-qualification",
    "arch133-robinhood-unattended-activation-core",
    "arch133-robinhood-unattended-state-store",
    "arch133-robinhood-unattended-one-wake-composition",
    "arch133-robinhood-unattended-review-paper-execution",
    "arch133-robinhood-unattended-host-scheduler-surface",
    "arch133-robinhood-unattended-host-bootstrap",
    "arch133-robinhood-unattended-host-publication",
    "arch133-robinhood-scratch-root-acl-qualification",
    "arch133-robinhood-retained-root-diagnostic",
    "arch133-robinhood-retained-root-acl-recovery",
    "arch133-robinhood-post-publication-verifier",
    "arch133-robinhood-post-publication-stage-diagnostic",
    "arch133-robinhood-publication-state-paper-diagnostic",
    "arch133-robinhood-publication-state-paper-corrected",
    "arch133-robinhood-single-session-scheduler-installation",
    "arch133-robinhood-fresh-activation-reprovision",
    "arch133-robinhood-reprovision-admission-diagnostic",
    "arch133-robinhood-reprovision-parent-security-diagnostic",
    "arch133-robinhood-reprovision-parent-policy-diagnostic",
    "arch133-robinhood-fresh-activation-reprovision-corrected",
    "arch133-robinhood-reprovision-indeterminate-reconciliation",
    "arch133-robinhood-reprovision-sealed-predecessor-recovery",
    "arch133-robinhood-reprovision-recovery-reconciliation",
    "arch133-robinhood-windows-rename-qualification",
    "arch133-robinhood-closed-descendant-rename-qualification",
    "arch144-c-f1-paper-evidence-admission",
    "arch134-f2-five-session-soak-readiness",
    "arch134-f1-five-session-soak",
    "arch134-d1r8-d1-session-execution-consumer",
    "arch134-d1r7-d1-session-authorization",
    "arch134-d1r6-overnight-wake-arming",
    "arch134-d1r5-pre-market-wake-qualification",
    "arch134-alpaca-authentication-qualification",
    "arch134-armed-paper-mvp",
    "arch134-production-strategy-contract",
    "arch134-production-strategy-decision",
    "arch134-production-strategy-live-paper",
    "arch134-production-paper-runtime",
    "arch134-production-paper-runtime-acl",
)


# Canonical certification profiles that GitHub owns for exact active checkpoints.
# Keep this mapping explicit; adding a checkpoint/profile is a reviewed workflow change.
CI_CERTIFICATION_PROFILES: Final = {
    "arch134-f2-five-session-soak-readiness": "robinhood",
    "arch134-f1-five-session-soak": "robinhood",
    "arch134-d1r8-d1-session-execution-consumer": "robinhood",
    "arch134-d1r7-d1-session-authorization": "robinhood",
    "arch134-d1r6-overnight-wake-arming": "robinhood",
    "arch134-d1r5-pre-market-wake-qualification": "robinhood",
    "arch134-alpaca-authentication-qualification": "robinhood",
    "arch134-armed-paper-mvp": "robinhood",
    "arch134-production-paper-runtime": "robinhood",
    "arch134-production-paper-runtime-acl": "robinhood",
}
CI_CERTIFICATION_PROFILE_VALUES: Final = frozenset({"robinhood", "full"})


CI_TEST_DURATION_WEIGHTS: Final = {
    # Frozen from successful source gate #422 (2026-10-10); unknown tests use 1s.
    "tests/execution/test_execution_models.py": 0.002,
    "tests/execution/test_order_engine.py": 0.019,
    "tests/ledger/test_ledger.py": 0.004,
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": 12.464,
    "tests/review_paper/test_arch133_fresh_activation_reprovision.py": 7.501,
    "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py": 8.189,
    "tests/review_paper/test_arch133_parent_policy_diagnostic.py": 1.474,
    "tests/review_paper/test_arch133_parent_security_diagnostic.py": 1.054,
    "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py": 0.295,
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": 6.222,
    "tests/review_paper/test_arch133_reprovision_recovery.py": 9.650,
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": 6.140,
    "tests/review_paper/test_arch133_scheduler_installation.py": 25.803,
    "tests/review_paper/test_arch133_windows_rename_qualification.py": 10.021,
    "tests/review_paper/test_forward_preview.py": 0.405,
    "tests/review_paper/test_intent_bridge.py": 0.034,
    "tests/review_paper/test_nyse_published_regular_sessions.py": 0.065,
    "tests/review_paper/test_performance.py": 0.106,
    "tests/review_paper/test_post_publication_stage_diagnostic.py": 2.494,
    "tests/review_paper/test_post_publication_verifier.py": 1.479,
    "tests/review_paper/test_prepare_qualification.py": 0.356,
    "tests/review_paper/test_publication_state_paper_corrected.py": 2.944,
    "tests/review_paper/test_publication_state_paper_diagnostic.py": 2.726,
    "tests/review_paper/test_published_session_prepare.py": 0.265,
    "tests/review_paper/test_retained_root_acl_recovery.py": 0.281,
    "tests/review_paper/test_retained_root_diagnostic.py": 0.220,
    "tests/review_paper/test_risk_context.py": 0.267,
    "tests/review_paper/test_risk_price_acquisition.py": 0.209,
    "tests/review_paper/test_risk_prices.py": 0.145,
    "tests/review_paper/test_scratch_root_acl.py": 0.309,
    "tests/review_paper/test_session_admission.py": 0.111,
    "tests/review_paper/test_store.py": 0.077,
    "tests/review_paper/test_supervised_deployment_qualification.py": 8.361,
    "tests/review_paper/test_supervised_forward_paper.py": 0.438,
    "tests/review_paper/test_supervised_maintenance_rebind.py": 3.949,
    "tests/review_paper/test_supervised_release_bundle.py": 20.551,
    "tests/review_paper/test_supervised_release_foundation.py": 0.538,
    "tests/review_paper/test_supervised_release_installation.py": 1.782,
    "tests/review_paper/test_supervised_release_installation_operator.py": 13.822,
    "tests/review_paper/test_supervised_runtime_host_admission.py": 2.087,
    "tests/review_paper/test_unattended_activation.py": 0.240,
    "tests/review_paper/test_unattended_execution.py": 2.264,
    "tests/review_paper/test_unattended_host.py": 1.256,
    "tests/review_paper/test_unattended_one_wake.py": 1.923,
    "tests/review_paper/test_unattended_publication.py": 1.204,
    "tests/review_paper/test_unattended_state_store.py": 1.437,
    "tests/risk/test_manager.py": 0.013,
    "tests/risk/test_risk_models.py": 0.012,
    "tests/robinhood_mcp/test_account_resolution.py": 0.027,
    "tests/robinhood_mcp/test_adapter.py": 0.004,
    "tests/robinhood_mcp/test_sdk_transport.py": 0.010,
    "tests/robinhood_mcp/test_windows_oauth.py": 0.575,
    "tests/runtime/checkpoint_runner/test_arch131.py": 25.801,
    "tests/runtime/checkpoint_runner/test_arch133_a_g.py": 5.962,
    "tests/runtime/checkpoint_runner/test_arch133_h_k.py": 34.414,
    "tests/runtime/checkpoint_runner/test_arch133_l_m.py": 72.117,
    "tests/runtime/checkpoint_runner/test_ci.py": 6.567,
    "tests/runtime/checkpoint_runner/test_core.py": 0.113,
    "tests/scripts/certification_runner/test_profiles.py": 1.662,
    "tests/test_robinhood_forward_paper_cycle.py": 0.173,
    "tests/test_robinhood_live_qualification_verifier.py": 0.360,
    "tests/test_robinhood_paper_cycle.py": 0.145,
    "tests/test_robinhood_paper_operator.py": 0.404,
    "tests/test_robinhood_paper_pipeline.py": 0.047,
    "tests/test_robinhood_prepare_operator.py": 0.102,
    "tests/test_robinhood_prepare_qualification_verifier.py": 1.121,
    "tests/test_robinhood_supervised_qualification.py": 3.394,
}
SOURCE_GATE_PHASE_ENV: Final = "AI_TRADING_BOT_SOURCE_GATE_PHASE"
SOURCE_GATE_SHARD_INDEX_ENV: Final = "AI_TRADING_BOT_SOURCE_GATE_SHARD_INDEX"
SOURCE_GATE_SHARD_COUNT_ENV: Final = "AI_TRADING_BOT_SOURCE_GATE_SHARD_COUNT"


def resolve_ci_checkpoint(
    specs: Mapping[str, CheckpointSpec],
    branch: str,
    event_name: str,
) -> str | None:
    """Use exactly one registered active branch on push; otherwise fail broad."""
    if event_name != "push" or type(branch) is not str or not branch:
        return None
    matches = [spec.name for spec in specs.values() if spec.remote_branch == branch]
    if len(matches) != 1 or matches[0] not in ACTIVE_CI_CHECKPOINTS:
        return None
    return matches[0]


def resolve_ci_certification_profile(checkpoint: str | None) -> str | None:
    """Return the reviewed GitHub-owned certification profile for one checkpoint."""
    if checkpoint is None:
        return None
    profile = CI_CERTIFICATION_PROFILES.get(checkpoint)
    if profile is not None and profile not in CI_CERTIFICATION_PROFILE_VALUES:
        raise RuntimeError(f"Unsupported CI certification profile: {profile}")
    return profile


def _batch_workflow_is_reviewed(workflow: str) -> bool:
    # Freeze active routing, CI-owned certification, broad fallback and aggregation.
    # The frozen D1R5 fallback stays unchanged; D1R6/D1R7/D1R8/F1 route dynamically.
    workflow_active = tuple(
        name
        for name in ACTIVE_CI_CHECKPOINTS
        if name
        not in {
            ARCH134_D1R6_NAME,
            ARCH134_D1R7_NAME,
            ARCH134_D1R8_NAME,
            ARCH134_F1_NAME,
            ARCH144C_NAME,
            ARCH134_F2_NAME,
        }
    )
    checkpoint_block = (
        "  AI_TRADING_BOT_ACTIVE_CHECKPOINTS: >-\n"
        + "".join(f"              {name} `\n" for name in workflow_active[:-1])
        + f"              {workflow_active[-1]}\n"
    )
    local_active = 'verify "${{ steps.route.outputs.checkpoint }}"'
    needs_active = 'verify "${{ needs.source-static.outputs.checkpoint }}"'
    batch = "verify-batch @Checkpoints"
    active_job = workflow.partition("  active-tests:\n")[2].partition(
        "\n  full-tests:\n"
    )[0]
    full_job = workflow.partition("  full-tests:\n")[2].partition(
        "\n  certification-tests:\n"
    )[0]
    certification_job = workflow.partition("  certification-tests:\n")[2].partition(
        "\n  source-gates:\n"
    )[0]
    aggregate_job = workflow.partition("  source-gates:\n")[2]

    active_header = (
        "    needs: source-static\n"
        "    if: needs.source-static.outputs.mode != 'DOCS_ONLY' && "
        "needs.source-static.outputs.route == 'ACTIVE'\n"
        "    runs-on: windows-latest\n"
        "    timeout-minutes: 20\n"
    )
    full_header = (
        "    needs: source-static\n"
        "    if: needs.source-static.outputs.mode != 'DOCS_ONLY' && "
        "needs.source-static.outputs.certification_profile == ''\n"
        "    runs-on: windows-latest\n"
        "    timeout-minutes: 20\n"
        "    strategy:\n"
        "      fail-fast: false\n"
        "      matrix:\n"
        "        shard: [0, 1, 2, 3]\n"
    )
    certification_header = (
        "    needs: source-static\n"
        "    if: needs.source-static.outputs.mode != 'DOCS_ONLY' && "
        "needs.source-static.outputs.certification_profile != ''\n"
        "    runs-on: windows-latest\n"
        "    timeout-minutes: 20\n"
    )
    broad_start = (
        "      - name: Record broad test shard start\n"
        "        shell: powershell\n"
        "        run: |\n"
        "          $Started = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()\n"
        '          "AI_TRADING_BOT_BROAD_SHARD_STARTED_MS=$Started" |\n'
        "            Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append\n"
        "\n"
    )
    broad_execution = (
        "      - name: Verify full batch test shard\n"
        "        env:\n"
        "          AI_TRADING_BOT_SOURCE_GATE_PHASE: tests\n"
        "          AI_TRADING_BOT_SOURCE_GATE_SHARD_INDEX: ${{ matrix.shard }}\n"
        "          AI_TRADING_BOT_SOURCE_GATE_SHARD_COUNT: 4\n"
        "          AI_TRADING_BOT_CHECKPOINT_EVIDENCE_ROOT: ${{ "
        "runner.temp }}/ai-trading-bot-checkpoints\n"
        "        shell: powershell\n"
        "        run: |\n"
        "          $Checkpoints = @(\n"
        "            $env:AI_TRADING_BOT_ACTIVE_CHECKPOINTS -split '\\s+' |\n"
        "              Where-Object { $_ -like 'arch*' }\n"
        "          )\n"
        "          & powershell.exe -NoProfile -ExecutionPolicy "
        "Bypass -File .\\ops.ps1 verify-batch @Checkpoints\n"
        "          exit $LASTEXITCODE\n"
        "\n"
    )
    broad_hygiene = (
        "      - name: Enforce broad test hygiene budget\n"
        "        if: always()\n"
        "        shell: powershell\n"
        "        run: |\n"
        "          $Started = [int64]$env:AI_TRADING_BOT_BROAD_SHARD_STARTED_MS\n"
        "          $Finished = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()\n"
        "          $Seconds = [math]::Round(($Finished - $Started) / 1000.0, 3)\n"
        '          Write-Host "BROAD_TEST_SHARD_SECONDS=$Seconds"\n'
        "          if ($Seconds -ge 300) {\n"
        '            Write-Host "::error::Broad test shard exceeded '
        "the 300-second hygiene threshold ($Seconds s). Run a test "
        'topology/hygiene audit before accepting this source."\n'
        "            exit 86\n"
        "          }\n"
        "\n"
    )
    certification_run_marker = (
        "      - name: Run canonical certification profile\n"
        "        env:\n"
        "          CERT_PROFILE: "
        "${{ needs.source-static.outputs.certification_profile }}\n"
    )
    certification_hygiene_marker = (
        "      - name: Enforce canonical certification hygiene budget\n"
        "        if: always()\n"
    )
    aggregate_policy = (
        "    needs: [source-static, active-tests, full-tests, "
        "certification-tests]\n"
        "    if: always()\n"
        "    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 5\n"
        "\n"
        "    steps:\n"
        "      - name: Require source gate success\n"
        "        shell: bash\n"
        "        env:\n"
        "          STATIC_RESULT: ${{ needs.source-static.result }}\n"
        "          ACTIVE_RESULT: ${{ needs.active-tests.result }}\n"
        "          FULL_RESULT: ${{ needs.full-tests.result }}\n"
        "          CERT_RESULT: ${{ needs.certification-tests.result }}\n"
        "          MODE: ${{ needs.source-static.outputs.mode }}\n"
        "          ROUTE: ${{ needs.source-static.outputs.route }}\n"
        "          CERT_PROFILE: "
        "${{ needs.source-static.outputs.certification_profile }}\n"
        "        run: |\n"
        "          set -euo pipefail\n"
        '          test "$STATIC_RESULT" = "success"\n'
        "\n"
        '          if [ "$MODE" = "DOCS_ONLY" ]; then\n'
        '            test "$ACTIVE_RESULT" = "skipped"\n'
        '            test "$FULL_RESULT" = "skipped"\n'
        '            test "$CERT_RESULT" = "skipped"\n'
        '          elif [ "$ROUTE" = "ACTIVE" ] && [ -n "$CERT_PROFILE" ]; then\n'
        '            test "$ACTIVE_RESULT" = "success"\n'
        '            test "$FULL_RESULT" = "skipped"\n'
        '            test "$CERT_RESULT" = "success"\n'
        '          elif [ "$ROUTE" = "ACTIVE" ]; then\n'
        '            test "$ACTIVE_RESULT" = "success"\n'
        '            test "$FULL_RESULT" = "success"\n'
        '            test "$CERT_RESULT" = "skipped"\n'
        "          else\n"
        '            test "$ACTIVE_RESULT" = "skipped"\n'
        '            test "$FULL_RESULT" = "success"\n'
        '            test "$CERT_RESULT" = "skipped"\n'
        "          fi\n"
    )
    return (
        active_job.startswith(active_header + "\n    steps:\n")
        and full_job.startswith(full_header + "\n    steps:\n")
        and certification_job.startswith(certification_header + "\n    steps:\n")
        and workflow.count("  active-tests:\n") == 1
        and workflow.count("  full-tests:\n") == 1
        and workflow.count("  certification-tests:\n") == 1
        and aggregate_job == aggregate_policy
        and full_job.count(broad_start) == 1
        and full_job.count(broad_hygiene) == 1
        and full_job.count(broad_execution) == 1
        and full_job.count("      - name: Upload full test evidence\n") == 1
        and full_job.index(broad_start)
        < full_job.index(broad_execution)
        < full_job.index(broad_hygiene)
        < full_job.index("      - name: Upload full test evidence\n")
        and certification_job.count(certification_run_marker) == 1
        and certification_job.count(certification_hygiene_marker) == 1
        and certification_job.count(
            ".\\scripts\\run_test_certification.py `\n"
            "              --profile $env:CERT_PROFILE"
        )
        == 1
        and certification_job.count(
            'Write-Host "CANONICAL_CERTIFICATION_WALL_SECONDS=$Wall"'
        )
        == 1
        and certification_job.count("if ($Wall -ge 300)") == 1
        and certification_job.count("exit 86") == 1
        and certification_job.count(
            "      - name: Upload canonical certification evidence\n"
        )
        == 1
        and workflow.count(checkpoint_block) == 1
        and workflow.count(batch) == 2
        and workflow.count(batch + "\n          exit $LASTEXITCODE") == 2
        and workflow.count(local_active) == 1
        and workflow.count(local_active + "\n          exit $LASTEXITCODE") == 1
        and workflow.count(needs_active) == 1
        and workflow.count(needs_active + "\n          exit $LASTEXITCODE") == 1
        and workflow.count("AI_TRADING_BOT_SOURCE_GATE_PHASE: static") == 2
        and workflow.count("AI_TRADING_BOT_SOURCE_GATE_PHASE: tests") == 2
        and "resolve_ci_checkpoint(" in workflow
        and "resolve_ci_certification_profile(" in workflow
        and "shard: [0, 1, 2, 3]" in workflow
        and "group: ${{ github.workflow }}-${{ github.ref }}" in workflow
        and "cancel-in-progress: true" in workflow
        and "workflow_dispatch:" in workflow
        and workflow.count(
            "  source-gates:\n"
            "    needs: [source-static, active-tests, full-tests, "
            "certification-tests]\n"
            "    if: always()\n"
        )
        == 1
        and workflow.count("  source-static:\n") == 1
        and workflow.count("- name: Require source gate success") == 1
        and "verify arch" not in workflow
    )


def _git_blob_sha1(path: Path) -> str:
    # Text mode normalizes Git's LF source across Windows checkout CRLF.
    data = path.read_text(encoding="utf-8").encode("utf-8")
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
    ).hexdigest()


def _qualified_names(node: ast.AST) -> set[str]:
    result: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            result.add(item.id)
        elif isinstance(item, ast.Attribute):
            parts: list[str] = []
            current: ast.AST = item
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                result.add(".".join(reversed(parts)))
    return result


def _top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _r4_authority_check(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "scripts" / "d10_arch128_r4_operator.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level_functions(tree)
    failures: list[str] = []

    required_functions = {
        "_read_only_preflight",
        "_execute_once",
        "_dispatch",
        "main",
    }
    missing_functions = sorted(required_functions - set(functions))
    if missing_functions:
        failures.append(f"missing functions: {missing_functions}")
        return tuple(failures)

    readonly_names = _qualified_names(functions["_read_only_preflight"])
    forbidden_readonly = {
        "r4w.WindowsArch128StagingBackend",
        "r4w.rename_fixed_step",
        "r4c._construct_staging",
        "r4c._ReplacementSession",
    }
    bad_readonly = sorted(forbidden_readonly & readonly_names)
    if bad_readonly:
        failures.append(
            f"read-only mode references protected mutation symbols: {bad_readonly}"
        )

    execute_names = _qualified_names(functions["_execute_once"])
    required_execute = {
        "r4w.WindowsArch128StagingBackend",
        "r4w.WindowsArch128ReadOnlyReader",
        "r4c._construct_staging",
        "r4c._ReplacementSession",
        "r4w.rename_fixed_step",
    }
    missing_execute = sorted(required_execute - execute_names)
    if missing_execute:
        failures.append(f"protected mode missing fixed bindings: {missing_execute}")

    dispatch_source = ast.get_source_segment(source, functions["_dispatch"]) or ""
    for required in ("READ_ONLY_FLAG", "EXECUTE_FLAG", "AUTH_ENV", "AUTH_VALUE"):
        if required not in dispatch_source:
            failures.append(f"dispatch interlock missing: {required}")

    for forbidden in (
        "RegisterTask",
        "RegisterTaskDefinition",
        "DeleteTask",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "WindowsActivationLeaseBackend",
        "publish_activation",
        "rmtree",
        "unlink(",
        "os.rename",
    ):
        if forbidden in source:
            failures.append(
                f"operator contains forbidden authority surface: {forbidden}"
            )

    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    runner_source = runner_path.read_text(encoding="utf-8")
    runner_tree = ast.parse(runner_source, filename=str(runner_path))
    runner_functions = _top_level_functions(runner_tree)
    r4_execute = runner_functions.get("_r4_execute")
    if r4_execute is None:
        failures.append("runner missing _r4_execute")
    else:
        execute_names = _qualified_names(r4_execute)
        for required in (
            "operator._dispatch",
            "operator.EXECUTE_FLAG",
            "os.environ",
        ):
            if required not in execute_names:
                failures.append(
                    f"runner R4 execute missing reviewed dispatch binding: {required}"
                )
        for forbidden in (
            "operator._execute_once",
            "r4c._construct_staging",
            "r4c._ReplacementSession",
            "r4w.WindowsArch128StagingBackend",
            "r4w.rename_fixed_step",
        ):
            if forbidden in execute_names:
                failures.append(
                    f"runner R4 execute bypasses reviewed interlock: {forbidden}"
                )

    return tuple(failures)


def _r5_authority_check(repo_root: Path) -> tuple[str, ...]:
    child_path = repo_root / "scripts" / "d10_arch128_r5_trading_child.py"
    child_source = child_path.read_text(encoding="utf-8")
    child_tree = ast.parse(child_source, filename=str(child_path))
    child_functions = _top_level_functions(child_tree)
    failures: list[str] = []

    qualify = child_functions.get("_qualify")
    if qualify is None:
        failures.append("R5 Trading child missing _qualify")
    else:
        names = _qualified_names(qualify)
        for required in (
            "guard_module._verify_pre_source",
            "guard_module._Native",
            "guard_module._require_facts",
            "guard_module._stable",
            "backend.require_absent",
            "backend.listdir",
        ):
            if required not in names:
                failures.append(
                    f"R5 Trading child missing read-only binding: {required}"
                )
        for forbidden in (
            "guard_module.main",
            "guard_module._run_second_stage_with_evidence",
            "backend.append_exact",
            "backend.open_evidence_file",
        ):
            if forbidden in names:
                failures.append(
                    f"R5 Trading child references effect binding: {forbidden}"
                )

    for forbidden in (
        "RegisterTask",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "WindowsActivationLeaseBackend",
        "publish_activation",
        "WriteFile",
        "MoveFile",
        "os.rename",
        "unlink(",
        "rmtree",
    ):
        if forbidden in child_source:
            failures.append(f"R5 Trading child contains forbidden surface: {forbidden}")

    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    runner_source = runner_path.read_text(encoding="utf-8")
    runner_tree = ast.parse(runner_source, filename=str(runner_path))
    runner_functions = _top_level_functions(runner_tree)
    substrate = runner_functions.get("_r5_substrate_preflight")
    trading = runner_functions.get("_r5_trading_preflight")
    if substrate is None:
        failures.append("runner missing _r5_substrate_preflight")
    else:
        names = _qualified_names(substrate)
        for required in ("h.collect", "w.WindowsCollector", "os.environ"):
            if required not in names:
                failures.append(f"R5 substrate runner missing binding: {required}")
    if trading is None:
        failures.append("runner missing _r5_trading_preflight")
    else:
        names = _qualified_names(trading)
        for required in ("subprocess.run", "json.loads"):
            if required not in names:
                failures.append(f"R5 Trading runner missing binding: {required}")

    return tuple(failures)


def _r6_authority_check(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "scripts" / "d10_arch128_r6_reactivation.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level_functions(tree)
    failures: list[str] = []

    for required in (
        "derive_reactivation_plan",
        "_require_evidence",
        "_require_trading_probe",
        "_require_admission",
    ):
        if required not in functions:
            failures.append(f"R6 source missing required function: {required}")

    forbidden = (
        "subprocess",
        "ctypes",
        "Start-ScheduledTask",
        "RegisterTask",
        "RegisterTaskDefinition",
        "WindowsActivationLeaseBackend",
        "WindowsDeploymentBackend",
        "CreateFileW",
        "MoveFile",
        "os.remove",
        "os.unlink",
        "shutil.rmtree",
    )
    for token in forbidden:
        if token in source:
            failures.append(f"R6 source contains protected host surface: {token}")

    if "execute_r7: bool = False" not in source:
        failures.append("R6 execution interlock is not explicit")
    if '"manual_task_start": "NOT_RUN"' not in source:
        failures.append("R6 source does not freeze manual task start closed")
    if "LEASE_PUBLICATION_STEPS" not in source:
        failures.append("R6 source does not bind tmp/installing/final publication")

    return tuple(failures)


# Canonical AST pins freeze the complete reviewed incident policy, native helper,
# accepted observation chain, and runner composition. Formatting is not authority.
R8_HALT_SOURCE_PINS: Final = {
    "scripts/d10_arch128_r8_terminal_halt.py": (
        "45c7e7fab0e48ea74995211e59758b6f27ea974b785e62ab5c2510be43c851cf"
    ),
    "scripts/d10_arch128_r8_halt_windows.py": (
        "c85efb5913c986384608234c282191831d3f254784db225733465aeb1dfc98ff"
    ),
    "scripts/d10_arch128_r8_halt_diagnostic.py": (
        "6369c8fcfd719171538b34d4d0842735e863cfb5609c8de180569c2a28ef29e5"
    ),
    "scripts/d10_arch128_r8_terminal_halt_diagnose.ps1": (
        "c07c054b01fc1bb0e2b4a720e3b82ff85c2c100432f66854ab7e132ddc9a37ce"
    ),
    "scripts/d10_arch128_r8_terminal_halt.ps1": (
        "0a6001494e265e79d443d6aaa1506a9791bd97c30c775e99d050056b512eb9a5"
    ),
    "scripts/d10_arch128_r8_readonly.py": (
        "59762e5d7dbd748f9525b51ea67b5bcdf1d1b1f4ec177992fed3ac5a0e29bdfc"
    ),
    "scripts/d10_durable_wake_evidence_observe.py": (
        "db64b72f9daaf74c0ff73d52378d407a29fbc8aeabcb30b5e7d4b47f5994ddb3"
    ),
    "scripts/run_personal_desktop_d10_launch_guard.py": (
        "a2bd8eea6dcd5e4df78a6ce94f070ef3bbafc243d1c27d79fbeb93f3a30cd1f6"
    ),
    "scripts/d10_arch128_r3_scheduler_observe.ps1": (
        "e688aab821028cedfca4a6fc6ebff2af847e645f25f8442f5c2ba772c3413505"
    ),
    "scripts/d10_p1245_scheduler_observe.ps1": (
        "a1bc4ef906806014bf15bed1e02c69742870f9977e99621bef14619c00b6058e"
    ),
    "scripts/d10_arch128_r6_reactivation.py": (
        "369b0feec8421e6a3470171fdf1285cf4c6d22b5c99308c7b427b505b919dea9"
    ),
    "scripts/d10_arch128_r7_observation.py": (
        "84238e6f11cc8fb82b5f0c73eee0dfcc63a3f7bc14b24e42038304ce0533f978"
    ),
    "scripts/d10_arch128_r4_replacement.py": (
        "2ec31172f0daeef152b8e4b6cf03ee3674d82ea5f07208eda32de3a58ecad54f"
    ),
    (
        "src/trading_bot/runtime/"
        "personal_desktop_unattended_one_week_soak_scheduler_contract.py"
    ): ("64a6cc2e44e98e7f301a64ae6777f57f7ca19339419ce6b8d90820e9dd4addf2"),
    "src/trading_bot/runtime/personal_desktop_d10_activation_lease.py": (
        "ff2885d6ee5cfd3998cb8c1ece5462c48a70ce704ab335fb71f3f3173c8d4e54"
    ),
}
R8_HALT_RUNNER_PINS: Final = {
    "_r8_halt_authority_check": (
        "d0e00ab3d3596828592c94483c9a114588f81bf40daa00fca29208d31b5a0ff1"
    ),
    "_r8_halt_preflight": (
        "3a7244189088f41c17e001a7aad8c60c4c85bf5a9cbbab497a3a2f194019ec53"
    ),
    "_r8_halt_execute": (
        "f0a9c6388f63b1184426f6b7072213e3e7af4bb16f27435d81f98ad0566c97ef"
    ),
    "execute_checkpoint": (
        "35164fc0985154d41a9f35f7b6b144df6ce86658941a083e7f5705fcee9366ed"
    ),
    "preflight_checkpoint": (
        "a5e63c447cb53e2998b4234dc0ecb2f81c2954b7677bc78d8414f6d278b8b15f"
    ),
    "_remote_branch_head": (
        "46ea1a2afa1e52622b257c9d635bb115529ae99b1c09aa6bb18ede99a5c2d27e"
    ),
    "_git_state": ("c63292862490a972afd8c7ffafe01dcdd90dc19d5973eca83be876ebd611c113"),
    "_write_json": ("bd3cabc882528e471e226c434eb3657c3f461b520112f60782eb0bda4b3d5f82"),
}
R8_HALT_REGISTRATION_PIN: Final = (
    "d610b7fc74b3c670d83188641d7f0e00425c1c83e052d32b08cf76b87bf1b991"
)

ARCH130_R8I_D1_SOURCE_BLOB_SHA1: Final = "4dece99d8993934e9747f091415927353b70a2e3"
ARCH130_R8I_D1_REMOTE_BRANCH: Final = "feature/d10c-r8-incident-reconciliation"
ARCH131_REVIEW_PAPER_REMOTE_BRANCH: Final = "feature/robinhood-review-paper-mode"
ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH: Final = (
    "feature/robinhood-review-paper-side-foundation"
)
ARCH131_LQ_SOURCE_BLOB_SHA1: Final = "3283793abed5320d778d28d72e49eeabed98ccf1"


def _arch131_windows_oauth_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/robinhood_mcp/windows_oauth.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = {
            node.target.id: node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        expected = {
            "TOKEN_TARGET": "AITradingBot/Brokerage/Robinhood/MCP/OAuthTokens/v1",
            "CLIENT_INFO_TARGET": (
                "AITradingBot/Brokerage/Robinhood/MCP/OAuthClientInfo/v1"
            ),
            "CRED_TYPE_GENERIC": 1,
            "CRED_PERSIST_LOCAL_MACHINE": 2,
            "CRED_MAX_CREDENTIAL_BLOB_SIZE": 2560,
            "LOOPBACK_HOST": "127.0.0.1",
        }
        for name, value in expected.items():
            if name not in constants or ast.literal_eval(constants[name]) != value:
                failures.append(f"131-F frozen constant drift: {name}")

        names = _qualified_names(tree)
        required = {
            "self._api.CredReadW",
            "self._api.CredWriteW",
            "self._api.CredFree",
            "WindowsCredentialApi",
            "WindowsOAuthStorage",
            "_require_target",
            "asyncio.start_server",
            "create_robinhood_oauth_factory",
        }
        if required - names:
            failures.append("131-F Windows storage/composition boundary is missing")
        forbidden_tools = {
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        }
        strings = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        identifiers = {name.rsplit(".", 1)[-1] for name in names}
        identifiers.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        if forbidden_tools & (strings | identifiers):
            failures.append("131-F exposes a forbidden Robinhood tool")
        forbidden = {
            "CredEnumerateW",
            "CredEnumerateA",
            "environ",
            "getenv",
            "Path",
            "write_text",
            "write_bytes",
            "read_text",
            "read_bytes",
            "load_dotenv",
            "call_tool",
            "socket",
            "bind",
            "listen",
        }
        unsafe_open = any(
            name == "open" or name.endswith(".open") and name != "webbrowser.open"
            for name in names
        )
        if forbidden & (identifiers | strings) or unsafe_open:
            failures.append("131-F enumeration/fallback/unreviewed effect boundary")
        allowed_imports = {
            "__future__",
            "asyncio",
            "ctypes",
            "ctypes.wintypes",
            "math",
            "os",
            "re",
            "threading",
            "webbrowser",
            "collections.abc",
            "typing",
            "urllib.parse",
            "mcp.shared.auth",
            "trading_bot.robinhood_mcp.sdk_transport",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name not in allowed_imports for alias in node.names):
                    failures.append("131-F unreviewed persistence/effect import")
            elif (
                isinstance(node, ast.ImportFrom) and node.module not in allowed_imports
            ):
                failures.append("131-F unreviewed persistence/effect import")
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "os" and node.attr != "name":
                    failures.append("131-F unreviewed OS boundary")
        listeners = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "start_server"
        ]
        if len(listeners) != 1:
            failures.append("131-F exact loopback listener is missing")
        else:
            keywords = {item.arg: item.value for item in listeners[0].keywords}
            host = keywords.get("host")
            port = keywords.get("port")
            if not (
                isinstance(host, ast.Name)
                and host.id == "LOOPBACK_HOST"
                and isinstance(port, ast.Attribute)
                and port.attr == "_port"
                and isinstance(port.value, ast.Name)
                and port.value.id == "self"
            ):
                failures.append("131-F loopback bind drift")
        native = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "WindowsCredentialApi"
        )
        for method_name, operation in (
            ("read_generic", "CredReadW"),
            ("write_generic", "CredWriteW"),
        ):
            method = next(
                node
                for node in native.body
                if isinstance(node, ast.FunctionDef) and node.name == method_name
            )
            method_names = _qualified_names(method)
            if "_require_target" not in method_names:
                failures.append("131-F exact target guard missing")
            if "CRED_TYPE_GENERIC" not in method_names:
                failures.append(f"131-F generic credential type missing: {operation}")
        guard = _top_level_functions(tree).get("_require_target")
        if guard is None or not any(
            isinstance(node, ast.Set)
            and {item.id for item in node.elts if isinstance(item, ast.Name)}
            == {"TOKEN_TARGET", "CLIENT_INFO_TARGET"}
            and len(node.elts) == 2
            for node in ast.walk(guard)
        ):
            failures.append("131-F exact target set drift")
        calls = [node for node in ast.walk(native) if isinstance(node, ast.Call)]
        for call in calls:
            if isinstance(call.func, ast.Attribute) and call.func.attr == "CredReadW":
                if not (
                    len(call.args) == 4
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == "target"
                    and isinstance(call.args[1], ast.Name)
                    and call.args[1].id == "CRED_TYPE_GENERIC"
                ):
                    failures.append("131-F exact generic read call drift")
            if isinstance(call.func, ast.Attribute) and call.func.attr == "_credential":
                fields = {item.arg: item.value for item in call.keywords}
                for field, constant in (
                    ("Type", "CRED_TYPE_GENERIC"),
                    ("Persist", "CRED_PERSIST_LOCAL_MACHINE"),
                    ("TargetName", "target"),
                ):
                    value = fields.get(field)
                    if not isinstance(value, ast.Name) or value.id != constant:
                        failures.append("131-F generic write record drift")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == "arch131-robinhood-oauth-windows"
                for item in node.keywords
            )
        ]
        if len(registrations) != 1:
            failures.append("131-F source-only registration missing")
        else:
            for item in registrations[0].keywords:
                if item.arg in {"preflight", "execute"} and not (
                    isinstance(item.value, ast.Constant) and item.value.value is None
                ):
                    failures.append("131-F checkpoint has host/effect capability")
        spec = _checkpoint_specs()["arch131-robinhood-oauth-windows"]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-F checkpoint has host/effect capability")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        StopIteration,
    ):
        failures.append("131-F source or structural boundary unavailable")
    return tuple(failures)


def _arch131_forward_paper_cycle_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (repo_root / "src/trading_bot/robinhood_forward_paper_cycle.py").read_text(
                encoding="utf-8"
            )
        )
        # Pin the entire narrow binder: closed imports and signature, one exact
        # 131-K call followed by one exact 131-J call, sole store identity,
        # unchanged explicit arguments/context/result, and no alternate effects.
        # Helpers, decorators, extra calls, loops, retries, UUID generation,
        # risk/operator/MCP/OAuth/config/host/performance access all drift.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "2528528ce13770c5aefe3481f3527d856c9d3ea19ffb3ab994de9b2b5fcb736a"
        ):
            failures.append("131-L sole-account/context/pipeline/effect boundary drift")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-forward-paper-cycle"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        # Pin source-only flags, authority, remote, and test/lint coverage.
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "15be2da1498de847845d155f0f0b5e65544fa6c307b9a5a3727a59250f976e07"
        ):
            failures.append("131-L source-only checkpoint registration drift")
        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-L checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-L workflow invocation/131-K ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-L source or structural boundary unavailable")
    return tuple(failures)


def _arch133_host_scheduler_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_host_identity.py": (
                "cb8b624c70f0792f8eba0336cf6e372d3b78f612"
            ),
            "src/trading_bot/review_paper/unattended_scheduler.py": (
                "153395ce66ff11f7d0978541cbf9193ae4df3f30"
            ),
            "src/trading_bot/review_paper/unattended_host.py": (
                "eb41d518af9ead0e4260b081af63d48b11560023"
            ),
            "scripts/run_arch133_unattended_review_paper.py": (
                "661023c46a3e088d338b67282effb7f35b00a93d"
            ),
        }
        for relative, expected in pins.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-E closed composition boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-host-scheduler-surface"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "9b526e5cca493208ec999ce427c09df0d731b039a897382f1b085d07f7481cbb"
        ):
            failures.append("133-E source-only registration drift")
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-E batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133e"
            or spec.authority_check is not _arch133_host_scheduler_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-E source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch133-robinhood-unattended-review-paper-execution"
            )
            + 1
        ):
            failures.append("133-E checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-E workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-E source or structural boundary unavailable")
    return tuple(failures)


ARCH133_RETAINED_SOURCES: Final = (
    "src/trading_bot/arch133_acl/__init__.py",
    "src/trading_bot/arch133_acl/read_only.py",
    "src/trading_bot/arch133_acl/retained_reads.py",
    "src/trading_bot/arch133_acl/retained_diagnostic.py",
    "scripts/run_arch133_retained_root_diagnostic.py",
)
ARCH133_RETAINED_PINS: Final = {
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/retained_reads.py": (
        "98fdab5017615be21bd95ec3f0ca25f792018f6325e20d11736df8842e47cbbb"
    ),
    "src/trading_bot/arch133_acl/retained_diagnostic.py": (
        "0ee93781d97db0b4377bbb0f724cf87d4329b05d18467d4687e965ee7eb72da6"
    ),
    "scripts/run_arch133_retained_root_diagnostic.py": (
        "cd35722017eca8560ccf0ca22a6be632e5581705db09441150d296ea87f2d0e9"
    ),
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
}
ARCH133_RETAINED_REGISTRATION_PIN: Final = (
    "f800d31cde47819f296db53593130d21b122139ca95383444f0debb7dd858246"
)


ARCH133_RECOVERY_SOURCES: Final = (
    "src/trading_bot/arch133_acl/__init__.py",
    "src/trading_bot/arch133_acl/read_only.py",
    "src/trading_bot/arch133_acl/retained_reads.py",
    "src/trading_bot/arch133_acl/root_policy_apply.py",
    "src/trading_bot/arch133_acl/administrator.py",
    "src/trading_bot/arch133_acl/recovery.py",
    "scripts/run_arch133_retained_root_acl_recovery.py",
)
ARCH133_RECOVERY_PINS: Final = {
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/retained_reads.py": (
        "98fdab5017615be21bd95ec3f0ca25f792018f6325e20d11736df8842e47cbbb"
    ),
    "src/trading_bot/arch133_acl/root_policy_apply.py": (
        "d3777322118c9fb1353102fd083251c4b59ac9ee552572818a87546a0cf41dde"
    ),
    "src/trading_bot/arch133_acl/administrator.py": (
        "286d4ab228fdad27b719a0673a19583bfe3cc667dcec958fa34bad30e8742611"
    ),
    "src/trading_bot/arch133_acl/recovery.py": (
        "7a7c8c058229665c89c7a3a8e736eb2d7cd141feee00812a27c03f8c391e4386"
    ),
    "scripts/run_arch133_retained_root_acl_recovery.py": (
        "524e622ae9653ed2c6f30fd056b97974c96aff04e485722ce8879e3ce58af75b"
    ),
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
}
ARCH133_RECOVERY_REGISTRATION_PIN: Final = (
    "825e732a03cf568a9b4be81e9ecd6d2b0707028a1fe7a2cb27f226888477d66c"
)


ARCH133_VERIFIER_MODULES: Final = (
    "trading_bot",
    "trading_bot.config",
    "trading_bot.arch133_acl",
    "trading_bot.arch133_acl.read_only",
    "trading_bot.arch133_acl.retained_reads",
    "trading_bot.arch133_verifier",
    "trading_bot.arch133_verifier.activation",
    "trading_bot.arch133_verifier.binding",
    "trading_bot.arch133_verifier.credentials",
    "trading_bot.arch133_verifier.file_policy",
    "trading_bot.arch133_verifier.operator",
    "trading_bot.arch133_verifier.scheduler",
    "trading_bot.arch133_verifier.sessions",
    "trading_bot.arch133_verifier.state",
    "trading_bot.arch133_verifier.state_schema",
    "trading_bot.arch133_verifier.token",
    "trading_bot.domain",
    "trading_bot.domain._validation",
    "trading_bot.domain.enums",
    "trading_bot.domain.market",
    "trading_bot.domain.orders",
    "trading_bot.domain.positions",
    "trading_bot.domain.proposals",
)
ARCH133_VERIFIER_PINS: Final = {
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/retained_reads.py": (
        "98fdab5017615be21bd95ec3f0ca25f792018f6325e20d11736df8842e47cbbb"
    ),
    "src/trading_bot/arch133_verifier/__init__.py": (
        "ece882f6a0f8605cae553bd80be524421a98f25c3d6fd2276c44558612cfc980"
    ),
    "src/trading_bot/arch133_verifier/activation.py": (
        "3e842e244576abcc5d560e942cd355c598ce42df5c2ffea71e120d1e254482b5"
    ),
    "src/trading_bot/arch133_verifier/binding.py": (
        "f24ee022779619e3a19915835ac3fd766135b1fba4f90f94a9e8b65764835262"
    ),
    "src/trading_bot/arch133_verifier/credentials.py": (
        "6896de10afc779a847a63640ffcf6fd5e9e634ba4199159599038e644de5c213"
    ),
    "src/trading_bot/arch133_verifier/file_policy.py": (
        "628d121da26a0474fc98e7f7556ce8d3dbc8c189d04a7ecc6b4ec47eb7bd6a08"
    ),
    "src/trading_bot/arch133_verifier/operator.py": (
        "a574acf2fa95e7623e8e8530728f33a82e9c273dec1006ce20c809eb54860572"
    ),
    "src/trading_bot/arch133_verifier/scheduler.py": (
        "327d092c852e762719e0c1d27eb9be0d1c470b6ffa5b7dd7a113352c1cf4946a"
    ),
    "src/trading_bot/arch133_verifier/sessions.py": (
        "278c43c61461c7163e8a641b27aaea8e2b9a6782b77ad805144c7137aa75b503"
    ),
    "src/trading_bot/arch133_verifier/state.py": (
        "0753b532ef58cc7699863e3114e1e3dd2caaa0e1aab7b48b2d546a7f8142d5e4"
    ),
    "src/trading_bot/arch133_verifier/state_schema.py": (
        "902525afadbaabd0afc997b7702de06b5160a7df61f8f97e6d38ec351b74c7d3"
    ),
    "src/trading_bot/arch133_verifier/token.py": (
        "b93236774ee2509947024786fd54ed6a9e702e8d68ef10a8a0ad6376706c5cb6"
    ),
    "src/trading_bot/domain/__init__.py": (
        "5d0baf9be17341641d07504176366c5041be9d73e17230377b8167e012f082ee"
    ),
    "src/trading_bot/domain/_validation.py": (
        "b94d183b2dceff5c844bf3584fabf4a21b4a58cabb0b3088e78099c0dbd7c101"
    ),
    "src/trading_bot/domain/enums.py": (
        "c47b5894f80cb271573e0be4869dde81a4b2a0cf9dc97019864f19f96712cd39"
    ),
    "src/trading_bot/domain/market.py": (
        "eb82f9727ce3fd83f41b96411f49b77e34ff5f75d39372bdb97ce94a3efc7040"
    ),
    "src/trading_bot/domain/orders.py": (
        "3f21c1f9ad197b187ac6a4588ef470ef7266a3b30e026df6288b7b2337a0070a"
    ),
    "src/trading_bot/domain/positions.py": (
        "e9a8d7615a6bd86ed206196d03ced50ae8aee273f632a56bece4427b212c68a9"
    ),
    "src/trading_bot/domain/proposals.py": (
        "eb47d71dcfab0ce64ff03a0d5b8a4091e6dca6d7a53c134f6f842ea40672d738"
    ),
    "scripts/run_arch133_post_publication_verifier.py": (
        "3503070f151862f9f11f3994003390ece6fbdf4205afd602975c8607f95c00e3"
    ),
}
ARCH133_VERIFIER_SOURCES: Final = tuple(ARCH133_VERIFIER_PINS)
ARCH133_VERIFIER_REGISTRATION_PIN: Final = (
    "478391462b59486e3a5432ec859eb8ec0bd867dbf8634c84df57e0043c7e4bb2"
)


ARCH133_DIAGNOSTIC_MODULES: Final = tuple(
    module
    for module in ARCH133_VERIFIER_MODULES
    if module
    not in {
        "trading_bot.arch133_verifier.credentials",
        "trading_bot.arch133_verifier.operator",
    }
) + ("trading_bot.arch133_diagnostic", "trading_bot.arch133_diagnostic.operator")
ARCH133_DIAGNOSTIC_PINS: Final = {
    path: digest
    for path, digest in ARCH133_VERIFIER_PINS.items()
    if path
    not in {
        "src/trading_bot/arch133_verifier/credentials.py",
        "src/trading_bot/arch133_verifier/operator.py",
        "scripts/run_arch133_post_publication_verifier.py",
    }
} | {
    "src/trading_bot/arch133_diagnostic/__init__.py": (
        "39dc89385e9450efec209706797f62de72d0e5a424dabf5edec0c2b1134dfb3e"
    ),
    "src/trading_bot/arch133_diagnostic/operator.py": (
        "61adcee90d2691bcaabaa85cf0329e8093e3570dd361d67f86532eff6613a78c"
    ),
    "scripts/run_arch133_post_publication_stage_diagnostic.py": (
        "6d8a6b54df85320eedb84bb1f6a15d218ab6f6260ab2dce620a2ec9f44aadce3"
    ),
}
ARCH133_DIAGNOSTIC_SOURCES: Final = tuple(ARCH133_DIAGNOSTIC_PINS)
ARCH133_DIAGNOSTIC_REGISTRATION_PIN: Final = (
    "3d91876e57fb5bfe7f2ce7ffb62040fe9f0953e9a5b33337692d2b1c4fe9653f"
)


ARCH133_PUBLICATION_DIAGNOSTIC_MODULES: Final = tuple(
    module
    for module in ARCH133_DIAGNOSTIC_MODULES
    if module
    not in {
        "trading_bot.arch133_verifier.scheduler",
        "trading_bot.arch133_verifier.sessions",
        "trading_bot.arch133_diagnostic",
        "trading_bot.arch133_diagnostic.operator",
    }
) + (
    "trading_bot.arch133_publication_diagnostic",
    "trading_bot.arch133_publication_diagnostic.operator",
)
ARCH133_PUBLICATION_DIAGNOSTIC_PINS: Final = {
    path: digest
    for path, digest in ARCH133_DIAGNOSTIC_PINS.items()
    if path
    not in {
        "src/trading_bot/arch133_verifier/scheduler.py",
        "src/trading_bot/arch133_verifier/sessions.py",
        "src/trading_bot/arch133_diagnostic/__init__.py",
        "src/trading_bot/arch133_diagnostic/operator.py",
        "scripts/run_arch133_post_publication_stage_diagnostic.py",
    }
} | {
    "src/trading_bot/arch133_publication_diagnostic/__init__.py": (
        "be2ef19da93cb7ea14b040db8fb7c97572ee7218f75699350f420570d0d4b692"
    ),
    "src/trading_bot/arch133_publication_diagnostic/operator.py": (
        "5eb8825eb4dc4aeb4d691efea5bb0fc7e50af4efbdac07e505c3c33d99331fb6"
    ),
    "scripts/run_arch133_publication_state_paper_diagnostic.py": (
        "8611b042fea0b8c925746593a30c2799652597c9be9b9ff9736b22ba029971e6"
    ),
}
ARCH133_PUBLICATION_DIAGNOSTIC_SOURCES: Final = tuple(
    ARCH133_PUBLICATION_DIAGNOSTIC_PINS
)
ARCH133_PUBLICATION_DIAGNOSTIC_REGISTRATION_PIN: Final = (
    "03f1c492c51dd6ca6e74f12bd6fb0fdf6f43464b8d815304b1aee98dd3e83c98"
)


ARCH133_PUBLICATION_CORRECTED_MODULES: Final = tuple(
    module
    for module in ARCH133_PUBLICATION_DIAGNOSTIC_MODULES
    if not module.startswith("trading_bot.arch133_publication_diagnostic")
) + (
    "trading_bot.arch133_publication_state_paper_corrected",
    "trading_bot.arch133_publication_state_paper_corrected.operator",
)
ARCH133_PUBLICATION_CORRECTED_PINS: Final = {
    path: digest
    for path, digest in ARCH133_PUBLICATION_DIAGNOSTIC_PINS.items()
    if "/arch133_publication_diagnostic/" not in path
    and path != "scripts/run_arch133_publication_state_paper_diagnostic.py"
} | {
    "src/trading_bot/arch133_publication_state_paper_corrected/__init__.py": (
        "819ac91ea5e47f258100c45c10f1c92f9624bfd23c9a04e608eebd1620a2ea5e"
    ),
    "src/trading_bot/arch133_publication_state_paper_corrected/operator.py": (
        "57743791949781089e2aa7f83d9b36d9a2aa10efcaba161cb941b84dbf055484"
    ),
    "scripts/run_arch133_publication_state_paper_corrected.py": (
        "353dea7dff0d0a2bffd85841e1c87bd8bd63aa4f2f7fe9ac2e9c0ac16bce75e4"
    ),
}
ARCH133_PUBLICATION_CORRECTED_SOURCES: Final = tuple(ARCH133_PUBLICATION_CORRECTED_PINS)
ARCH133_PUBLICATION_CORRECTED_REGISTRATION_PIN: Final = (
    "1e19a84ed6ae2a4be90b2245bee1ad38b7beceb1b4613b94c1201252472e6d5d"
)


ARCH133_SCHEDULER_MODULES: Final = (
    "trading_bot",
    "trading_bot.arch133_acl",
    "trading_bot.arch133_acl.read_only",
    "trading_bot.arch133_acl.retained_reads",
    "trading_bot.arch133_scheduler_installation",
    "trading_bot.arch133_scheduler_installation.admission",
    "trading_bot.arch133_scheduler_installation.operator",
    "trading_bot.arch133_scheduler_installation.specification",
    "trading_bot.arch133_verifier",
    "trading_bot.arch133_verifier.activation",
    "trading_bot.arch133_verifier.binding",
    "trading_bot.arch133_verifier.file_policy",
    "trading_bot.arch133_verifier.scheduler",
    "trading_bot.arch133_verifier.sessions",
    "trading_bot.arch133_verifier.state",
    "trading_bot.arch133_verifier.state_schema",
    "trading_bot.arch133_verifier.token",
    "trading_bot.config",
    "trading_bot.domain",
    "trading_bot.domain._validation",
    "trading_bot.domain.enums",
    "trading_bot.domain.market",
    "trading_bot.domain.orders",
    "trading_bot.domain.positions",
    "trading_bot.domain.proposals",
)
ARCH133_SCHEDULER_PINS: Final = {
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/retained_reads.py": (
        "98fdab5017615be21bd95ec3f0ca25f792018f6325e20d11736df8842e47cbbb"
    ),
    "src/trading_bot/arch133_scheduler_installation/__init__.py": (
        "67726876bbccbf569d95cc6e9c7dca42ca5d3cc50601cbbfd2f848bf98e08d21"
    ),
    "src/trading_bot/arch133_scheduler_installation/admission.py": (
        "2c426ea952ee109f26481003e53670f36054b09781385aec078bb60746ff931b"
    ),
    "src/trading_bot/arch133_scheduler_installation/operator.py": (
        "b6db26e036e52d688257e27723509c6e541f462a789c2044d0b6d01f80fcd27c"
    ),
    "src/trading_bot/arch133_scheduler_installation/specification.py": (
        "bdd841b4d2acfd7dec09cb9c7df16f14082602fd63f59e0351dac505cbd6d985"
    ),
    "src/trading_bot/arch133_verifier/__init__.py": (
        "ece882f6a0f8605cae553bd80be524421a98f25c3d6fd2276c44558612cfc980"
    ),
    "src/trading_bot/arch133_verifier/activation.py": (
        "3e842e244576abcc5d560e942cd355c598ce42df5c2ffea71e120d1e254482b5"
    ),
    "src/trading_bot/arch133_verifier/binding.py": (
        "f24ee022779619e3a19915835ac3fd766135b1fba4f90f94a9e8b65764835262"
    ),
    "src/trading_bot/arch133_verifier/file_policy.py": (
        "628d121da26a0474fc98e7f7556ce8d3dbc8c189d04a7ecc6b4ec47eb7bd6a08"
    ),
    "src/trading_bot/arch133_verifier/scheduler.py": (
        "327d092c852e762719e0c1d27eb9be0d1c470b6ffa5b7dd7a113352c1cf4946a"
    ),
    "src/trading_bot/arch133_verifier/sessions.py": (
        "278c43c61461c7163e8a641b27aaea8e2b9a6782b77ad805144c7137aa75b503"
    ),
    "src/trading_bot/arch133_verifier/state.py": (
        "0753b532ef58cc7699863e3114e1e3dd2caaa0e1aab7b48b2d546a7f8142d5e4"
    ),
    "src/trading_bot/arch133_verifier/state_schema.py": (
        "902525afadbaabd0afc997b7702de06b5160a7df61f8f97e6d38ec351b74c7d3"
    ),
    "src/trading_bot/arch133_verifier/token.py": (
        "b93236774ee2509947024786fd54ed6a9e702e8d68ef10a8a0ad6376706c5cb6"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
    "src/trading_bot/domain/__init__.py": (
        "5d0baf9be17341641d07504176366c5041be9d73e17230377b8167e012f082ee"
    ),
    "src/trading_bot/domain/_validation.py": (
        "b94d183b2dceff5c844bf3584fabf4a21b4a58cabb0b3088e78099c0dbd7c101"
    ),
    "src/trading_bot/domain/enums.py": (
        "c47b5894f80cb271573e0be4869dde81a4b2a0cf9dc97019864f19f96712cd39"
    ),
    "src/trading_bot/domain/market.py": (
        "eb82f9727ce3fd83f41b96411f49b77e34ff5f75d39372bdb97ce94a3efc7040"
    ),
    "src/trading_bot/domain/orders.py": (
        "3f21c1f9ad197b187ac6a4588ef470ef7266a3b30e026df6288b7b2337a0070a"
    ),
    "src/trading_bot/domain/positions.py": (
        "e9a8d7615a6bd86ed206196d03ced50ae8aee273f632a56bece4427b212c68a9"
    ),
    "src/trading_bot/domain/proposals.py": (
        "eb47d71dcfab0ce64ff03a0d5b8a4091e6dca6d7a53c134f6f842ea40672d738"
    ),
    "scripts/run_arch133_scheduler_installation.py": (
        "64f50e19cf72a234ae8cd76c01704fdea9a9d2ed10728545e30d72d62544800a"
    ),
    "scripts/arch133_scheduler_definition.ps1": (
        "e705dbd03ad10bbcd619538156d6f88c961fb074d35c9f7956b4fb04efa8e88e"
    ),
    "scripts/arch133_scheduler_observe.ps1": (
        "45e1c9dbf62738ff2667969ed3716b39313c1977ee7693572a17c078616c0a2a"
    ),
    "scripts/arch133_scheduler_install.ps1": (
        "9764b40dc6953b3fda2028e35f6e68a39d71c8b052dde9710fe60ce9bd4eaa8f"
    ),
    "src/trading_bot/review_paper/unattended_scheduler.py": (
        "79fe37f5e4c36c70096f86414f5e32151556c617b82bc086742a44470c7dde29"
    ),
}
ARCH133_SCHEDULER_SOURCES: Final = tuple(ARCH133_SCHEDULER_PINS)
ARCH133_SCHEDULER_REGISTRATION_PIN: Final = (
    "e6f119c53e5ecc7ea2d56fba3b0da9d661823f553b80bb64a5913877cb57206a"
)


ARCH133_REPROVISION_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision/__init__.py",
    "src/trading_bot/arch133_reprovision/predecessor.py",
    "src/trading_bot/arch133_reprovision/reads.py",
    "src/trading_bot/arch133_reprovision/material.py",
    "src/trading_bot/arch133_reprovision/generation.py",
    "src/trading_bot/arch133_reprovision/namespace.py",
    "src/trading_bot/arch133_reprovision/native.py",
    "src/trading_bot/arch133_reprovision/operator.py",
    "scripts/run_arch133_fresh_activation_reprovision.py",
)
ARCH133_REPROVISION_PINS: Final = {
    "src/trading_bot/arch133_reprovision/__init__.py": (
        "4a6c81929bd649707d26db3b7751e76c3fe6977be98fece1be65b6daae95fbfa"
    ),
    "src/trading_bot/arch133_reprovision/predecessor.py": (
        "22fa7166311b669314aabf76499ada463dd40290a23de8694e2f4668f4f9f59a"
    ),
    "src/trading_bot/arch133_reprovision/reads.py": (
        "48b42cb5d9fac1b88b5a532e4f4ad4e180556d222bc8da21c78be2ef3068bad7"
    ),
    "src/trading_bot/arch133_reprovision/material.py": (
        "fd6c2c3dd321e0b47cf0d344636a5b2ec4f2aec7feb981c0426b672eb19c0212"
    ),
    "src/trading_bot/arch133_reprovision/generation.py": (
        "8936195c3692f7654a5c692715ce9511a238a91019e06b67ca7c42ed5e47bfbe"
    ),
    "src/trading_bot/arch133_reprovision/namespace.py": (
        "b4afbba5d22e2874df2e3345f89c0764103b86ffb3729cc7a6e59380996e38d7"
    ),
    "src/trading_bot/arch133_reprovision/native.py": (
        "de93039a5a04053a51da6dd88e83aed121ca6debb4bcbbaa7e2f5b7246bf3bc8"
    ),
    "src/trading_bot/arch133_reprovision/operator.py": (
        "aa9eedd322bef79f61241864e954f281aefd6f9ea484b9907dca399a32c8a6a0"
    ),
    "scripts/run_arch133_fresh_activation_reprovision.py": (
        "d1824adb159ff11a171040ebab43c380ad27de13d897bff9cbe457c19f4d99df"
    ),
}
ARCH133_REPROVISION_REGISTRATION_PIN: Final = (
    "54882c9d46d181d465e03fdff642317c4af373c6bda759685c6dff745404df1b"
)


ARCH133U_REPROVISION_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_corrected/__init__.py",
    "src/trading_bot/arch133_reprovision_corrected/admission.py",
    "src/trading_bot/arch133_reprovision_corrected/operator.py",
    "scripts/run_arch133_fresh_activation_reprovision_corrected.py",
)
ARCH133U_REPROVISION_PINS: Final = {
    "src/trading_bot/arch133_reprovision_corrected/__init__.py": (
        "cc04b3a697950ac1d02ea39c1f57e5c2747430a2a0b9bbbd1f753d2ea4bba8f8"
    ),
    "src/trading_bot/arch133_reprovision_corrected/admission.py": (
        "62935b26f9cd2624ed89059987eeb38996d1c3288d2744640e0c84947531f349"
    ),
    "src/trading_bot/arch133_reprovision_corrected/operator.py": (
        "7d439154bd4c7713ee3a9c366f3c7c6db47438785f1796168c512b9fadbc665b"
    ),
    "scripts/run_arch133_fresh_activation_reprovision_corrected.py": (
        "03d61973408c4039e119ea4d06670c728cde411df05427cda9824127b90f8086"
    ),
}
ARCH133U_REPROVISION_REGISTRATION_PIN: Final = (
    "f8e25032969974459fd99e589831daaf8d30e0150656dd06c30f28a198297a60"
)


ARCH133_REPROVISION_DIAGNOSTIC_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_diagnostic/__init__.py",
    "src/trading_bot/arch133_reprovision_diagnostic/operator.py",
    "scripts/run_arch133_reprovision_admission_diagnostic.py",
)
ARCH133_REPROVISION_DIAGNOSTIC_PINS: Final = {
    "src/trading_bot/arch133_reprovision_diagnostic/__init__.py": (
        "a161e6533bcdc3bb7c9caa29cc27422fc2120b2d"
    ),
    "src/trading_bot/arch133_reprovision_diagnostic/operator.py": (
        "4699aac0761df76c2c9ed67f7c4810c98dabb8b0"
    ),
    "scripts/run_arch133_reprovision_admission_diagnostic.py": (
        "6479389ccbfc3da4401e38b338f979376a5f418f"
    ),
}


ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES: Final = (
    "src/trading_bot/arch133_parent_security_diagnostic/__init__.py",
    "src/trading_bot/arch133_parent_security_diagnostic/admission.py",
    "src/trading_bot/arch133_parent_security_diagnostic/operator.py",
    "scripts/run_arch133_parent_security_diagnostic.py",
)
ARCH133_PARENT_SECURITY_DIAGNOSTIC_PINS: Final = {
    "src/trading_bot/arch133_parent_security_diagnostic/__init__.py": (
        "c59623e697cd19f3fd9c6cc0d9b0774dfcc22bdd"
    ),
    "src/trading_bot/arch133_parent_security_diagnostic/admission.py": (
        "2b6039da799db0a4f15a883782858bfc87f1a492"
    ),
    "src/trading_bot/arch133_parent_security_diagnostic/operator.py": (
        "1659266adf9e1f82d338fba601810e6edd491dec"
    ),
    "scripts/run_arch133_parent_security_diagnostic.py": (
        "5e0c64b9fe4b627110deba75f5572cca0a7e1afc"
    ),
}
ARCH133_PARENT_SECURITY_DIAGNOSTIC_REGISTRATION_PIN: Final = (
    "f78ba2bfee91356acbc077cdddd1a52102a0d45a5a49058836ae1195390493e4"
)


def _arch133_parent_security_diagnostic_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the separate 133-S read-only surface and retained predecessor chain."""
    failures = list(_arch133_reprovision_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_PARENT_SECURITY_DIAGNOSTIC_PINS.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-S diagnostic source drift: {relative}")
        if (
            tuple(ARCH133_PARENT_SECURITY_DIAGNOSTIC_PINS)
            != ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES
        ):
            failures.append("133-S diagnostic inventory drift")
        name = "arch133-robinhood-reprovision-parent-security-diagnostic"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(inventories) != 1
            or ast.literal_eval(inventories[0]) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-S diagnostic active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_PARENT_SECURITY_DIAGNOSTIC_REGISTRATION_PIN
        ):
            failures.append("133-S diagnostic source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_parent_security_diagnostic_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133s"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-S diagnostic registration drift")
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 1
            ]
            != (
                "arch133-robinhood-reprovision-admission-diagnostic",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-S diagnostic ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-S diagnostic workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-S diagnostic boundary unavailable")
    return tuple(failures)


ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES: Final = (
    "src/trading_bot/arch133_parent_policy_diagnostic/__init__.py",
    "src/trading_bot/arch133_parent_policy_diagnostic/admission.py",
    "src/trading_bot/arch133_parent_policy_diagnostic/operator.py",
    "scripts/run_arch133_parent_policy_diagnostic.py",
)
ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS: Final = {
    "src/trading_bot/arch133_parent_policy_diagnostic/__init__.py": (
        "37a59becbfb288ed9ba61d2d30ee9ad4548acb1a"
    ),
    "src/trading_bot/arch133_parent_policy_diagnostic/admission.py": (
        "fa7d762d5699ec5fc19ed1948ebc1c328f2c1931"
    ),
    "src/trading_bot/arch133_parent_policy_diagnostic/operator.py": (
        "c06b3d575443ead6624b27cca5c95a3ce10d4206"
    ),
    "scripts/run_arch133_parent_policy_diagnostic.py": (
        "9e8d7aa959d40bc689cd1c3ae17506bdbddb16ba"
    ),
}
ARCH133_PARENT_POLICY_DIAGNOSTIC_REGISTRATION_PIN: Final = (
    "33753d52734b0358250e79b442ef6d5759fab043709154299a919aee594370b8"
)


def _arch133_parent_policy_diagnostic_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the separate 133-T read-only surface and retained predecessor chain."""
    failures = list(_arch133_parent_security_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-T diagnostic source drift: {relative}")
        if (
            tuple(ARCH133_PARENT_POLICY_DIAGNOSTIC_PINS)
            != ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES
        ):
            failures.append("133-T diagnostic inventory drift")
        name = "arch133-robinhood-reprovision-parent-policy-diagnostic"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(inventories) != 1
            or ast.literal_eval(inventories[0]) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-T diagnostic active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_PARENT_POLICY_DIAGNOSTIC_REGISTRATION_PIN
        ):
            failures.append("133-T diagnostic source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_parent_policy_diagnostic_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133t"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-T diagnostic registration drift")
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 1
            ]
            != (
                "arch133-robinhood-reprovision-parent-security-diagnostic",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-T diagnostic ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-T diagnostic workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-T diagnostic boundary unavailable")
    return tuple(failures)


def _arch133_reprovision_corrected_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the corrected 133-U source surface and the complete T authority chain."""
    failures = list(_arch133_parent_policy_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133U_REPROVISION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-U reprovision source drift: {relative}")
        name = "arch133-robinhood-fresh-activation-reprovision-corrected"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133U_REPROVISION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "4759c440268cdb3a7d96b7449b1219a1dc4e6e8afa070d9ad098268257dad319"
            or tuple(ARCH133U_REPROVISION_PINS) != ARCH133U_REPROVISION_SOURCES
        ):
            failures.append("133-U source inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133U_REPROVISION_REGISTRATION_PIN
        ):
            failures.append("133-U registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_reprovision_corrected_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133u"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133U_REPROVISION_SOURCES,
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-U registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-reprovision-parent-policy-diagnostic",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-U ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-U workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-U source boundary unavailable")
    return tuple(failures)


ARCH133V_RECONCILIATION_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_reconciliation/__init__.py",
    "src/trading_bot/arch133_reprovision_reconciliation/operator.py",
    "scripts/run_arch133_reprovision_reconciliation.py",
)
ARCH133V_RECONCILIATION_PINS: Final = {
    "src/trading_bot/arch133_reprovision_reconciliation/__init__.py": (
        "292384cf303c6a68144ecebd4d3f51606c1427f1e647834688a08dc3e7b183fb"
    ),
    "src/trading_bot/arch133_reprovision_reconciliation/operator.py": (
        "260f337c627a195046eadfa0b00bdd131d51bb393cbbda2277a796442fa78f05"
    ),
    "scripts/run_arch133_reprovision_reconciliation.py": (
        "ea5730bb29cefac8b7355f8d5041d938bc39ab4937c20bf5cf58dcbe6b36e16f"
    ),
}
ARCH133V_RECONCILIATION_REGISTRATION_PIN: Final = (
    "ecfb923f10ce676138b34e422d28d2f387dd5f33f59116a69fabba6e58ede741"
)


def _arch133_reprovision_reconciliation_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the read-only 133-V surface and complete consumed U authority chain."""
    failures = list(_arch133_reprovision_corrected_authority_check(repo_root))
    try:
        for relative, expected in ARCH133V_RECONCILIATION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-V reprovision source drift: {relative}")
        name = "arch133-robinhood-reprovision-indeterminate-reconciliation"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133V_RECONCILIATION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "f9ef00b1314c337868a49894c201e936df01cf1ce549695b8812a7b2f9923394"
            or tuple(ARCH133V_RECONCILIATION_PINS) != ARCH133V_RECONCILIATION_SOURCES
        ):
            failures.append("133-V source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-V active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133V_RECONCILIATION_REGISTRATION_PIN
        ):
            failures.append("133-V registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_reprovision_reconciliation_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133v"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133V_RECONCILIATION_SOURCES,
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-V registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-fresh-activation-reprovision-corrected",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-V ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-V workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-V source boundary unavailable")
    return tuple(failures)


ARCH133W_RECOVERY_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_recovery/__init__.py",
    "src/trading_bot/arch133_reprovision_recovery/admission.py",
    "src/trading_bot/arch133_reprovision_recovery/native.py",
    "src/trading_bot/arch133_reprovision_recovery/operator.py",
    "scripts/run_arch133_reprovision_recovery.py",
)
ARCH133W_RECOVERY_PINS: Final = {
    "src/trading_bot/arch133_reprovision_recovery/__init__.py": (
        "61104f164e26ce56f30f981ac1263e817bc2e38643a5a27d84fddb6bd5445c08"
    ),
    "src/trading_bot/arch133_reprovision_recovery/admission.py": (
        "d974c87e07c081396ecad04ea7ef0ba1b39653d5ce6f8f820f7e64fae3693a64"
    ),
    "src/trading_bot/arch133_reprovision_recovery/native.py": (
        "0553efac4da5258b2fc8c9b5534d5aaee3aae52f4baa856182592d2747837d97"
    ),
    "src/trading_bot/arch133_reprovision_recovery/operator.py": (
        "fe8e57cb4b936b0552708801112a139a411e1c3aa3d76e412777475e6536cdb2"
    ),
    "scripts/run_arch133_reprovision_recovery.py": (
        "404912297cc3ff595491d38d8f3c746f0bf5e39086a2b08e79657e19723db194"
    ),
}
ARCH133W_RECOVERY_REGISTRATION_PIN: Final = (
    "5061f8dbbbff58794c7ee4f3b1266988fab1f7313c3e3570e1f2c7e1908b8736"
)


def _arch133_reprovision_recovery_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the read-only 133-W surface and complete accepted V authority chain."""
    failures = list(_arch133_reprovision_reconciliation_authority_check(repo_root))
    try:
        for relative, expected in ARCH133W_RECOVERY_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-W reprovision source drift: {relative}")
        name = "arch133-robinhood-reprovision-sealed-predecessor-recovery"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133W_RECOVERY_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "3d78d2447e55f43ada40c18aad6700d965158f34f33b87efdd8358c118f823af"
            or tuple(ARCH133W_RECOVERY_PINS) != ARCH133W_RECOVERY_SOURCES
        ):
            failures.append("133-W source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-W active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133W_RECOVERY_REGISTRATION_PIN
        ):
            failures.append("133-W registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check is not _arch133_reprovision_recovery_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133w"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_recovery.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133W_RECOVERY_SOURCES,
                "tests/review_paper/test_arch133_reprovision_recovery.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-W registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-reprovision-indeterminate-reconciliation",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-W ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-W workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-W source boundary unavailable")
    return tuple(failures)


ARCH133X_RECONCILIATION_SOURCES: Final = (
    "src/trading_bot/arch133_reprovision_recovery_reconciliation/__init__.py",
    "src/trading_bot/arch133_reprovision_recovery_reconciliation/operator.py",
    "scripts/run_arch133_reprovision_recovery_reconciliation.py",
)
ARCH133X_RECONCILIATION_PINS: Final = {
    "src/trading_bot/arch133_reprovision_recovery_reconciliation/__init__.py": (
        "ce48f46c0ee51292736cd61a658d8da43cc3ea0683a5b325a31a560deefc0b3d"
    ),
    "src/trading_bot/arch133_reprovision_recovery_reconciliation/operator.py": (
        "4ad752d4634075244ebe614a2da271741deeb759b59de801788d92e6ddf188b5"
    ),
    "scripts/run_arch133_reprovision_recovery_reconciliation.py": (
        "fad91e7fad8f1c9c52adc4e1b5ba8f7d79f382afc0fd8f0c8dbc9ecbf3c34b89"
    ),
}
ARCH133X_RECONCILIATION_REGISTRATION_PIN: Final = (
    "0a9ea47f85b1f5feca156c8720377c4a2ae9476ac474c5b9dc0739522906d710"
)


def _arch133_reprovision_recovery_reconciliation_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the read-only 133-X surface and complete accepted W authority chain."""
    failures = list(_arch133_reprovision_recovery_authority_check(repo_root))
    try:
        for relative, expected in ARCH133X_RECONCILIATION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-X reprovision source drift: {relative}")
        name = "arch133-robinhood-reprovision-recovery-reconciliation"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133X_RECONCILIATION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "a8510efa09c2293c965f6ce998f6be79850864859ad3bf67a76f26e5a6c78160"
            or tuple(ARCH133X_RECONCILIATION_PINS) != ARCH133X_RECONCILIATION_SOURCES
        ):
            failures.append("133-X source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-X active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133X_RECONCILIATION_REGISTRATION_PIN
        ):
            failures.append("133-X registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_reprovision_recovery_reconciliation_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133x"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133X_RECONCILIATION_SOURCES,
                "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-X registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-reprovision-sealed-predecessor-recovery",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-X ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-X workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-X source boundary unavailable")
    return tuple(failures)


ARCH133Y_QUALIFICATION_SOURCES: Final = (
    "src/trading_bot/arch133_windows_rename_qualification/__init__.py",
    "src/trading_bot/arch133_windows_rename_qualification/native.py",
    "src/trading_bot/arch133_windows_rename_qualification/operator.py",
    "scripts/run_arch133_windows_rename_qualification.py",
)
ARCH133Y_QUALIFICATION_PINS: Final = {
    "src/trading_bot/arch133_windows_rename_qualification/__init__.py": (
        "f0662e01d82fed62613c366bf4b83e351e5faa792ea5af4315f6493cb4ca8dec"
    ),
    "src/trading_bot/arch133_windows_rename_qualification/native.py": (
        "df75e8bbb291a01484510f1a3d373a3236e6ecd764fb06e7e821c8800ebc4b2f"
    ),
    "src/trading_bot/arch133_windows_rename_qualification/operator.py": (
        "65c30f88ac91bd2fbf816da02d8fce6a64b8d95d205dde40c74737c6b5ec0296"
    ),
    "scripts/run_arch133_windows_rename_qualification.py": (
        "d9ec4f0dfbf62ac373e9e6db159f1089d78372925f148d695b7067bbca16c89c"
    ),
}
ARCH133Y_QUALIFICATION_REGISTRATION_PIN: Final = (
    "1e923b6612c5abb15763dfe19281e02f8515287f654d2fbf577fbf1bc4511fde"
)


def _arch133_windows_rename_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the scratch-only 133-Y surface and complete accepted X authority chain."""
    failures = list(
        _arch133_reprovision_recovery_reconciliation_authority_check(repo_root)
    )
    try:
        for relative, expected in ARCH133Y_QUALIFICATION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-Y reprovision source drift: {relative}")
        name = "arch133-robinhood-windows-rename-qualification"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133Y_QUALIFICATION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "ff3b2b1ad278beaad14d996c5d523982edb419025e73728a29050ebaede9001a"
            or tuple(ARCH133Y_QUALIFICATION_PINS) != ARCH133Y_QUALIFICATION_SOURCES
        ):
            failures.append("133-Y source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-Y active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133Y_QUALIFICATION_REGISTRATION_PIN
        ):
            failures.append("133-Y registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_windows_rename_qualification_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133y"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_windows_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133Y_QUALIFICATION_SOURCES,
                "tests/review_paper/test_arch133_windows_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-Y registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-reprovision-recovery-reconciliation",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-Y ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-Y workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-Y source boundary unavailable")
    return tuple(failures)


ARCH133Z_QUALIFICATION_SOURCES: Final = (
    "src/trading_bot/arch133_closed_descendant_rename_qualification/__init__.py",
    "src/trading_bot/arch133_closed_descendant_rename_qualification/native.py",
    "src/trading_bot/arch133_closed_descendant_rename_qualification/operator.py",
    "scripts/run_arch133_closed_descendant_rename_qualification.py",
)
ARCH133Z_QUALIFICATION_PINS: Final = {
    "src/trading_bot/arch133_closed_descendant_rename_qualification/__init__.py": (
        "0600fc6ebb08096c191f7bb3e1c740e3e5e51bd513bc17fd9a7541b3cba18ad3"
    ),
    "src/trading_bot/arch133_closed_descendant_rename_qualification/native.py": (
        "b252da668fdffd24038307b0ca2849b15caa735a380d9b160a5b8ab40a624c6e"
    ),
    "src/trading_bot/arch133_closed_descendant_rename_qualification/operator.py": (
        "f9bb8a867a9afe1c20aed6b0387dffd6adc8eea17eee4ec391395cae8c07aeec"
    ),
    "scripts/run_arch133_closed_descendant_rename_qualification.py": (
        "bfd8a858a224ce7779ad16bba13585443f845cd2b1eb754d810f408e824761b9"
    ),
}
ARCH133Z_QUALIFICATION_REGISTRATION_PIN: Final = (
    "a9b6d9a36abd32929f33285065e9cfdc96c876e876b822bfac08a0c3347d9c23"
)


def _arch133_closed_descendant_rename_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Pin the scratch-only 133-Z surface and complete accepted Y authority chain."""
    failures = list(_arch133_windows_rename_qualification_authority_check(repo_root))
    try:
        for relative, expected in ARCH133Z_QUALIFICATION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-Z reprovision source drift: {relative}")
        name = "arch133-robinhood-closed-descendant-rename-qualification"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH133Z_QUALIFICATION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "f6d0914d71238b1d7a3c06a36240eb988918882246dc88cd473b78e568e5c967"
            or tuple(ARCH133Z_QUALIFICATION_PINS) != ARCH133Z_QUALIFICATION_SOURCES
        ):
            failures.append("133-Z source inventory drift")
        active = [
            node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if len(active) != 1 or ast.literal_eval(active[0]) != ACTIVE_CI_CHECKPOINTS:
            failures.append("133-Z active inventory drift")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                key.arg == "name"
                and isinstance(key.value, ast.Constant)
                and key.value.value == name
                for key in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133Z_QUALIFICATION_REGISTRATION_PIN
        ):
            failures.append("133-Z registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_closed_descendant_rename_qualification_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133z"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133Z_QUALIFICATION_SOURCES,
                "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-Z registration drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != (
                "arch133-robinhood-windows-rename-qualification",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-Z ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-Z workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-Z source boundary unavailable")
    return tuple(failures)


def _arch133_reprovision_diagnostic_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the 133-R zero-effect staged admission diagnostic."""
    failures = list(_arch133_reprovision_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_REPROVISION_DIAGNOSTIC_PINS.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-R diagnostic source drift: {relative}")
        if (
            tuple(ARCH133_REPROVISION_DIAGNOSTIC_PINS)
            != ARCH133_REPROVISION_DIAGNOSTIC_SOURCES
        ):
            failures.append("133-R diagnostic inventory drift")
        name = "arch133-robinhood-reprovision-admission-diagnostic"
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check
            is not _arch133_reprovision_diagnostic_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133r"
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_REPROVISION_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-R diagnostic registration drift")
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 1
            ]
            != (
                "arch133-robinhood-fresh-activation-reprovision",
                name,
            )
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-R diagnostic ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-R diagnostic workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-R diagnostic boundary unavailable")
    return tuple(failures)


def _arch133_reprovision_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin new source, workflow and registration; preserve consumed sources."""
    failures = list(_arch133_scheduler_installation_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_REPROVISION_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8-sig")
            if (
                hashlib.sha256(
                    ast.dump(ast.parse(source), include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-Q reprovision source drift: {relative}")
        name = "arch133-robinhood-fresh-activation-reprovision"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        inventories = [
            n.value
            for n in tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "ARCH133_REPROVISION_SOURCES"
        ]
        if (
            len(inventories) != 1
            or hashlib.sha256(
                ast.dump(inventories[0], include_attributes=False).encode()
            ).hexdigest()
            != "e8b866d14b9914dad4920ec6fb049c68f8aa5f4a0b0cb39f26dc65444a2edf21"
            or tuple(ARCH133_REPROVISION_PINS) != ARCH133_REPROVISION_SOURCES
        ):
            failures.append("133-Q source inventory drift")
        registrations = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_REPROVISION_REGISTRATION_PIN
        ):
            failures.append("133-Q registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.authority_check is not _arch133_reprovision_authority_check
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133q"
        ):
            failures.append("133-Q source-only capability drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != ("arch133-robinhood-single-session-scheduler-installation", name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-Q ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-Q workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-Q source boundary unavailable")
    return tuple(failures)


def _arch133_scheduler_installation_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin full inert closure, canonical builder and native transport; no invocation."""
    failures = list(_arch133_publication_corrected_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_SCHEDULER_PINS.items():
            source = (repo_root / relative).read_text(encoding="utf-8")
            material = (
                ast.dump(ast.parse(source), include_attributes=False)
                if relative.endswith(".py")
                else source
            )
            if hashlib.sha256(material.encode()).hexdigest() != expected:
                failures.append(f"133-P installation boundary drift: {relative}")
        name = "arch133-robinhood-single-session-scheduler-installation"
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        registrations = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_SCHEDULER_REGISTRATION_PIN
        ):
            failures.append("133-P source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133p"
            or spec.authority_check
            is not _arch133_scheduler_installation_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *(p for p in ARCH133_SCHEDULER_SOURCES if p.endswith(".py")),
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-P source-only capability drift")
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1]
            != ("arch133-robinhood-publication-state-paper-corrected", name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-P checkpoint ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("133-P source workflow drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-P installation boundary unavailable")
    return tuple(failures)


def _arch133_publication_corrected_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the exact read-only import closure; never import/invoke the operator."""
    failures = list(_arch133_publication_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_PUBLICATION_CORRECTED_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-O verifier boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-publication-state-paper-corrected"
        registrations = [
            n
            for n in ast.walk(runner_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_PUBLICATION_CORRECTED_REGISTRATION_PIN
        ):
            failures.append("133-O source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133o"
            or spec.authority_check
            is not _arch133_publication_corrected_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PUBLICATION_CORRECTED_SOURCES,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-O source-only capability drift")
        predecessor = "arch133-robinhood-publication-state-paper-diagnostic"
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 1 : index + 1] != (predecessor, name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-O checkpoint ordering drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-O verifier boundary unavailable")
    return tuple(failures)


def _arch133_publication_diagnostic_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the exact read-only import closure; never import/invoke the operator."""
    failures = list(_arch133_diagnostic_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_PUBLICATION_DIAGNOSTIC_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-N verifier boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-publication-state-paper-diagnostic"
        registrations = [
            n
            for n in ast.walk(runner_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_PUBLICATION_DIAGNOSTIC_REGISTRATION_PIN
        ):
            failures.append("133-N source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133n"
            or spec.authority_check
            is not _arch133_publication_diagnostic_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PUBLICATION_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-N source-only capability drift")
        predecessor = "arch133-robinhood-post-publication-verifier"
        prior = "arch133-robinhood-post-publication-stage-diagnostic"
        index = ACTIVE_CI_CHECKPOINTS.index(name)
        if (
            ACTIVE_CI_CHECKPOINTS[index - 2 : index + 1] != (predecessor, prior, name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-N checkpoint ordering drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-N verifier boundary unavailable")
    return tuple(failures)


def _arch133_diagnostic_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the exact read-only import closure; never import/invoke the operator."""
    failures = list(_arch133_verifier_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_DIAGNOSTIC_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-M verifier boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-post-publication-stage-diagnostic"
        registrations = [
            n
            for n in ast.walk(runner_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_DIAGNOSTIC_REGISTRATION_PIN
        ):
            failures.append("133-M source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133m"
            or spec.authority_check is not _arch133_diagnostic_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-M source-only capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 1
            ]
            != ("arch133-robinhood-post-publication-verifier", name)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-M checkpoint ordering drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-M verifier boundary unavailable")
    return tuple(failures)


def _arch133_verifier_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the exact read-only import closure; never import/invoke the operator."""
    failures = list(_arch133_recovery_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_VERIFIER_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-L verifier boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-post-publication-verifier"
        registrations = [
            n
            for n in ast.walk(runner_tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in n.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_VERIFIER_REGISTRATION_PIN
        ):
            failures.append("133-L source registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133l"
            or spec.authority_check is not _arch133_verifier_authority_check
            or spec.tests
            != (
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_VERIFIER_SOURCES,
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-L source-only capability drift")
        predecessor = "arch133-robinhood-retained-root-acl-recovery"
        successor = "arch133-robinhood-post-publication-stage-diagnostic"
        if (
            ACTIVE_CI_CHECKPOINTS[
                ACTIVE_CI_CHECKPOINTS.index(name) - 1 : ACTIVE_CI_CHECKPOINTS.index(
                    name
                )
                + 2
            ]
            != (predecessor, name, successor)
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-L checkpoint ordering drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("133-L verifier boundary unavailable")
    return tuple(failures)


def _arch133_recovery_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Source-only pins; never import or invoke either recovery operator mode."""
    failures = list(_arch133_retained_root_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_RECOVERY_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-K recovery boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-retained-root-acl-recovery"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_RECOVERY_REGISTRATION_PIN
        ):
            failures.append("133-K source-only registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133k"
            or spec.authority_check is not _arch133_recovery_authority_check
            or spec.tests
            != (
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_RECOVERY_SOURCES,
                "tests/review_paper/test_retained_root_acl_recovery.py",
            )
        ):
            failures.append("133-K runtime capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS.count(name) != 1
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) + 1]
            != "arch133-robinhood-post-publication-verifier"
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) - 1]
            != "arch133-robinhood-retained-root-diagnostic"
        ):
            failures.append("133-K batch successor registration drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-K recovery boundary unavailable")
    return tuple(failures)


def _arch133_retained_root_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Source-only pins; never import or invoke the operator diagnostic."""
    failures = list(_arch133_scratch_root_acl_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_RETAINED_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-J read-only boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-retained-root-diagnostic"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_RETAINED_REGISTRATION_PIN
        ):
            failures.append("133-J source-only registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133j"
            or spec.authority_check is not _arch133_retained_root_authority_check
            or spec.tests
            != (
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_RETAINED_SOURCES,
                "tests/review_paper/test_retained_root_diagnostic.py",
            )
        ):
            failures.append("133-J runtime capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS.count(name) != 1
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) - 1]
            != "arch133-robinhood-scratch-root-acl-qualification"
        ):
            failures.append("133-J batch successor registration drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-J read-only boundary unavailable")
    return tuple(failures)


ARCH133_SCRATCH_SOURCES: Final = (
    "src/trading_bot/arch133_acl/__init__.py",
    "src/trading_bot/arch133_acl/primitive.py",
    "src/trading_bot/arch133_acl/read_only.py",
    "src/trading_bot/arch133_acl/qualification.py",
    "scripts/run_arch133_scratch_root_acl.py",
    "src/trading_bot/arch133_acl/root_policy_apply.py",
    "src/trading_bot/arch133_acl/administrator.py",
)
ARCH133_SCRATCH_PINS: Final = {
    "src/trading_bot/arch133_acl/root_policy_apply.py": (
        "d3777322118c9fb1353102fd083251c4b59ac9ee552572818a87546a0cf41dde"
    ),
    "src/trading_bot/arch133_acl/administrator.py": (
        "286d4ab228fdad27b719a0673a19583bfe3cc667dcec958fa34bad30e8742611"
    ),
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/primitive.py": (
        "f68c54990fefc2f82eaf7758b41193b9450123cbb7fb13458576c8d427e3cd13"
    ),
    "src/trading_bot/arch133_acl/qualification.py": (
        "c798ee76ea0680395a0bb32223250fcb58c810afad4c771a5822157e4c47e7f1"
    ),
    "scripts/run_arch133_scratch_root_acl.py": (
        "6ef171aa76609dc48a4f3632b7e29845e1f5fe7e6cfadb6db946fb774252db73"
    ),
    # Pin package initializers too: fresh-process import closure is effect-free.
    "src/trading_bot/__init__.py": (
        "730b3821629d6650b3b3bcde8969d18fdcdc8061d1c023a810b3d0dbc266decb"
    ),
    "src/trading_bot/config.py": (
        "fde1712ad80a4b9c734397dcb6615d2edbd227fd1b0be6b567b1f2bbf3ca2304"
    ),
}
ARCH133_SCRATCH_REGISTRATION_PIN: Final = (
    "93e30428d22ce71372e9cd9d29b7511feb9875b1bd5830186404a8c307092afa"
)


def _arch133_scratch_root_acl_authority_check(repo_root: Path) -> tuple[str, ...]:
    """133-I is SOURCE ONLY: no preflight/execute callback or production import."""
    failures = list(_arch133_host_publication_authority_check(repo_root))
    try:
        for relative, expected in ARCH133_SCRATCH_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            actual = hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode()
            ).hexdigest()
            if actual != expected:
                failures.append(f"133-I scratch boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-scratch-root-acl-qualification"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != ARCH133_SCRATCH_REGISTRATION_PIN
        ):
            failures.append("133-I source-only registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133i"
            or spec.authority_check is not _arch133_scratch_root_acl_authority_check
            or spec.tests
            != (
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_SCRATCH_SOURCES,
                "src/trading_bot/review_paper/unattended_publication_windows.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            )
        ):
            failures.append("133-I runtime capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS.count(name) != 1
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) - 1]
            != "arch133-robinhood-unattended-host-publication"
        ):
            failures.append("133-I batch successor registration drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-I scratch boundary unavailable")
    return tuple(failures)


def _arch133_host_publication_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin all 133-H operator/native composition and reused security boundaries."""
    failures: list[str] = []
    try:
        for relative, expected in ARCH133_PUBLICATION_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            actual = hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            if actual != expected:
                failures.append(f"133-H closed publication boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-host-publication"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                k.arg == "name"
                and isinstance(k.value, ast.Constant)
                and k.value.value == name
                for k in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != ARCH133_PUBLICATION_REGISTRATION_PIN
        ):
            failures.append("133-H source-only registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133h"
            or spec.authority_check is not _arch133_host_publication_authority_check
            or spec.tests
            != (*ARCH133_H_K_TESTS, "tests/review_paper/test_unattended_publication.py")
            or spec.ruff_paths
            != (
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_PUBLICATION_SOURCES,
                "tests/review_paper/test_unattended_publication.py",
            )
        ):
            failures.append("133-H runtime source-only registration drift")
        ci = next(
            n
            for n in runner_tree.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "ACTIVE_CI_CHECKPOINTS"
        )
        if (
            tuple(ast.literal_eval(ci.value)) != ACTIVE_CI_CHECKPOINTS
            or ACTIVE_CI_CHECKPOINTS[ACTIVE_CI_CHECKPOINTS.index(name) - 1]
            != "arch133-robinhood-unattended-host-bootstrap"
            or ACTIVE_CI_CHECKPOINTS.count(name) != 1
        ):
            failures.append("133-H batch registration drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-H workflow invocation drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        StopIteration,
    ):
        failures.append("133-H source or structural boundary unavailable")
    return tuple(failures)


ARCH133_PUBLICATION_SOURCES: Final = (
    "src/trading_bot/review_paper/unattended_publication.py",
    "src/trading_bot/review_paper/unattended_publication_windows.py",
    "scripts/run_arch133_host_publication.py",
    "src/trading_bot/arch133_acl/__init__.py",
    "src/trading_bot/arch133_acl/primitive.py",
    "src/trading_bot/arch133_acl/read_only.py",
    "src/trading_bot/arch133_acl/root_policy_apply.py",
    "src/trading_bot/arch133_acl/administrator.py",
)
ARCH133_PUBLICATION_PINS: Final = {
    "src/trading_bot/arch133_acl/root_policy_apply.py": (
        "d3777322118c9fb1353102fd083251c4b59ac9ee552572818a87546a0cf41dde"
    ),
    "src/trading_bot/arch133_acl/administrator.py": (
        "286d4ab228fdad27b719a0673a19583bfe3cc667dcec958fa34bad30e8742611"
    ),
    # 133-I successor owns the extracted native leaf; all other 133-H pins remain.
    "src/trading_bot/arch133_acl/__init__.py": (
        "7d6b3b0876d48dcc83a686c48b0baea181339b62006ee312e2f4a1773b87f1d7"
    ),
    "src/trading_bot/arch133_acl/read_only.py": (
        "3cfc44181b7dec97f0308c5ff87070992add05bbd3e84648658326d298061d8f"
    ),
    "src/trading_bot/arch133_acl/primitive.py": (
        "f68c54990fefc2f82eaf7758b41193b9450123cbb7fb13458576c8d427e3cd13"
    ),
    "src/trading_bot/review_paper/unattended_publication.py": (
        "820b6d0f86f56c22a03bbd734b6a3a98d0042d8ac167f28b39230d99d89da128"
    ),
    "src/trading_bot/review_paper/unattended_publication_windows.py": (
        "44397d1ba3594c12ab85e76d4bf891a424e646c67f12f20f67a9c36c2cce7756"
    ),
    "scripts/run_arch133_host_publication.py": (
        "5b5bb84080d916d18383657d8d6c2f96e7fa3a47d4e74b137cbe42b5ff7df5d1"
    ),
    "src/trading_bot/runtime/windows_authority_security.py": (
        "1b034fc0ca0e066a0a9c8baf67c30415059141744ac0f981b1f35f1366f63f22"
    ),
    "src/trading_bot/runtime/personal_desktop_paper_account_security.py": (
        "8e81affbb85f98f6a6b11e65e9a97f6e66b9113a5aca22080d3fb4183748d95d"
    ),
    "src/trading_bot/review_paper/unattended_host_identity.py": (
        "987ea024d33025e3da26993df7768435e5a031666d72cdc73613f9b69a24a27c"
    ),
    "src/trading_bot/review_paper/unattended_activation.py": (
        "7fc65af97b2465d82b907a67365d898a028226c2145b4cc77f6cdc6634f60b27"
    ),
    "src/trading_bot/review_paper/unattended_state_schema.py": (
        "02859147d4d476c3b23b56f3c63f0ae5857caa372eaaf8cc9eeb230d88e34b77"
    ),
    "src/trading_bot/review_paper/unattended_scheduler.py": (
        "79fe37f5e4c36c70096f86414f5e32151556c617b82bc086742a44470c7dde29"
    ),
    "src/trading_bot/review_paper/store.py": (
        "02c546abd42849bee94b5c08e00c54cfb726d6ffddf235fa844d21471ce965c9"
    ),
    "src/trading_bot/review_paper/unattended_state_store.py": (
        "93ffd82253c22803ff318721779e892f5f20dd9f996c8a2cdf3ba8f154ced822"
    ),
    "src/trading_bot/review_paper/unattended_state_verifier.py": (
        "95e20d01781879a8c0637973fdc0a6b5efaff17d8377ffa59dbe865cb9c14d1c"
    ),
    "src/trading_bot/robinhood_execute_qualification_verifier.py": (
        "e978006d124ff8945065b5e1ae240914068a80ce1ac3043174eb2e887e4043ff"
    ),
}
ARCH133_PUBLICATION_REGISTRATION_PIN: Final = (
    "14b2fabf7c5c7bcbc029bea006456f8dcc7ff54e329aaa09e3b389782d74c74a"
)


def _arch133_host_bootstrap_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_host_identity.py": (
                "cb8b624c70f0792f8eba0336cf6e372d3b78f612"
            ),
            "src/trading_bot/review_paper/unattended_scheduler.py": (
                "153395ce66ff11f7d0978541cbf9193ae4df3f30"
            ),
            "src/trading_bot/review_paper/unattended_host.py": (
                "eb41d518af9ead0e4260b081af63d48b11560023"
            ),
            "src/trading_bot/review_paper/unattended_host_bootstrap.py": (
                "54623c8c1933b227194532ca9d1ed702d3797279"
            ),
            "scripts/run_arch133_unattended_review_paper.py": (
                "661023c46a3e088d338b67282effb7f35b00a93d"
            ),
            "scripts/run_arch133_unattended_host_preflight.py": (
                "7916c2a9c90e33302e9313e5d35d9a282b90b149"
            ),
        }
        for relative, expected in pins.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-G closed bootstrap boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-host-bootstrap"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-G batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            len(registrations) != 1
            or spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133g"
            or spec.authority_check is not _arch133_host_bootstrap_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-G source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch133-robinhood-unattended-host-scheduler-surface"
            )
            + 1
        ):
            failures.append("133-G checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-G workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-G source or structural boundary unavailable")
    return tuple(failures)


def _arch133_execution_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_execution.py": (
                "2c74a68708b99f7813806c50f0519046b90982f3"
            ),
        }
        for relative, expected in pins.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-D closed composition boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-review-paper-execution"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "2ceac689f87333f29d7389a315199bd580fc250a45d00856efd3829e554475e9"
        ):
            failures.append("133-D source-only registration drift")
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-D batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133d"
            or spec.authority_check is not _arch133_execution_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/test_robinhood_paper_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_execution.py",
                "src/trading_bot/robinhood_paper_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-D source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch133-robinhood-unattended-one-wake-composition"
            )
            + 1
        ):
            failures.append("133-D checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-D workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-D source or structural boundary unavailable")
    return tuple(failures)


def _arch133_one_wake_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_one_wake.py": (
                "9fbcb9d303bc8aa52362a92eef472fd6419a8e66"
            ),
        }
        for relative, expected in pins.items():
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append(f"133-C closed composition boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-one-wake-composition"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "4cefb0203b851fde16f5ee5f35cbff4e54f3fae04df508bfe84a4341c460a10c"
        ):
            failures.append("133-C source-only registration drift")
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-C batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133c"
            or spec.authority_check is not _arch133_one_wake_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/scripts/certification_runner/test_profiles.py",
            )
        ):
            failures.append("133-C source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch133-robinhood-unattended-state-store") + 1
        ):
            failures.append("133-C checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-C workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-C source or structural boundary unavailable")
    return tuple(failures)


def _arch133_unattended_state_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        pins = {
            "src/trading_bot/review_paper/unattended_state_schema.py": (
                "02859147d4d476c3b23b56f3c63f0ae5857caa372eaaf8cc9eeb230d88e34b77"
            ),
            "src/trading_bot/review_paper/unattended_state_store.py": (
                "93ffd82253c22803ff318721779e892f5f20dd9f996c8a2cdf3ba8f154ced822"
            ),
            "src/trading_bot/review_paper/unattended_state_verifier.py": (
                "95e20d01781879a8c0637973fdc0a6b5efaff17d8377ffa59dbe865cb9c14d1c"
            ),
        }
        for relative, expected in pins.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode("utf-8")
                ).hexdigest()
                != expected
            ):
                failures.append(f"133-B closed state boundary drift: {relative}")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-state-store"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "33a9e39be9c3094ee8cdd31c2b11b00e0a5bc3e7dfd6770a54f867f322fed594"
        ):
            failures.append("133-B source-only registration drift")
        assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or hashlib.sha256(
                ast.dump(assignments[0].value, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-B batch registration drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-unattended-review-paper-133b"
            or spec.authority_check is not _arch133_unattended_state_authority_check
            or spec.tests
            != (
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
            )
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                *pins,
                "tests/review_paper/test_unattended_state_store.py",
            )
        ):
            failures.append("133-B source-only coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch133-robinhood-unattended-activation-core")
            + 1
        ):
            failures.append("133-B checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-B workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-B source or structural boundary unavailable")
    return tuple(failures)


def _arch133_unattended_activation_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/unattended_activation.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "7fc65af97b2465d82b907a67365d898a028226c2145b4cc77f6cdc6634f60b27"
        ):
            failures.append("133-A pure activation/wake boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch133-robinhood-unattended-activation-core"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "fc97901789ef914ecc1550919cab9a04ab3f8969ea3a380a20b522d99b53221e"
        ):
            failures.append("133-A source-only checkpoint registration drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("133-A checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("133-A checkpoint has host/effect capability")
        if spec.remote_branch != "feature/robinhood-unattended-review-paper-133a":
            failures.append("133-A checkpoint remote branch drift")
        if (
            spec.tests
            != (*ARCH133_A_G_TESTS, "tests/review_paper/test_unattended_activation.py")
            or spec.ruff_paths
            != (
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_activation.py",
                "tests/review_paper/test_unattended_activation.py",
            )
            or spec.authority_check
            is not _arch133_unattended_activation_authority_check
        ):
            failures.append("133-A checkpoint coverage/authority drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-supervised-qualification")
            + 1
        ):
            failures.append("133-A checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("133-A workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("133-A source or structural boundary unavailable")
    return tuple(failures)


def _arch131_nyse_published_regular_session_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = (
            repo_root
            / "src/trading_bot/review_paper/nyse_published_regular_sessions.py"
        )
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "a71d7b4c0ff130fa32a11e5e827e41722dd2044940f4c2259b3d985cc893e7d6"
        ):
            failures.append("131-S published regular-session boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-nyse-published-regular-session-authority"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "0016427c31d574f73132803031404ff293ffdda00ef7f113d5bbb238177b1a71"
        ):
            failures.append("131-S source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-S remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-S checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-S checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-S checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-supervised-prepare-verifier")
            + 1
        ):
            failures.append("131-S checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-S workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-S source or structural boundary unavailable")
    return tuple(failures)


def _arch131_published_session_prepare_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/published_session_prepare.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "831c75256addd7a779a8f776c30c7ce9bbe2b16381f71231dbc71dfc9efde42a"
        ):
            failures.append("131-T published regular-session boundary drift")

        verifier = (
            repo_root / "src/trading_bot/robinhood_prepare_qualification_verifier.py"
        ).read_text(encoding="utf-8")
        if (
            hashlib.sha256(
                ast.dump(ast.parse(verifier), include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "c618e667286ff06fdda772ca78af29affb1b0cd9b9158c3267e42920b89d677a"
        ):
            failures.append("131-T canonical schedule verifier boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-published-session-prepare"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "0c83b9828c88cb93dce677e6bc229cff6070457146e659c344aa062b9db84a82"
        ):
            failures.append("131-T source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-T remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-T checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-T checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-T checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch131-nyse-published-regular-session-authority"
            )
            + 1
        ):
            failures.append("131-T checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-T workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-T source or structural boundary unavailable")
    return tuple(failures)


def _arch131_supervised_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        digests = {
            "src/trading_bot/robinhood_supervised_qualification.py": (
                "743d11a3bb049f33aacba0d6cda126580e9cf636e4899745999a08438cf63e86"
            ),
            "src/trading_bot/robinhood_execute_qualification_verifier.py": (
                "e978006d124ff8945065b5e1ae240914068a80ce1ac3043174eb2e887e4043ff"
            ),
            "scripts/robinhood_supervised_qualification.py": (
                "823ddad595d7d72068c5393bf7bcea81ff276685dc86e29be758480dbaf53fa9"
            ),
            "src/trading_bot/review_paper/__init__.py": (
                "bbbedff7dde18395e8576984a6e914c8cd761329ee5fc6d25defca5e43e1bd75"
            ),
        }
        for relative, expected in digests.items():
            source = (repo_root / relative).read_text(encoding="utf-8")
            actual = hashlib.sha256(
                ast.dump(ast.parse(source), include_attributes=False).encode()
            ).hexdigest()
            if actual != expected:
                failures.append(
                    "131-V qualification boundary drift: "
                    + relative
                    + " actual="
                    + actual
                )
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-supervised-qualification"
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != "66d7c5b592b044a3e6803c48d927d58688792df3fe7fa0c0da82617298972993"
        ):
            failures.append("131-V source-only registration drift")
        ci = [
            node
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci) != 1
            or hashlib.sha256(
                ast.dump(ci[0].value, include_attributes=False).encode()
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-V checkpoint batch drift")
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_branch != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-V source-only capability drift")
        if (
            ACTIVE_CI_CHECKPOINTS.count(name) != 1
            or ACTIVE_CI_CHECKPOINTS.index(name)
            != ACTIVE_CI_CHECKPOINTS.index(
                "arch131-robinhood-published-prepare-operator"
            )
            + 1
        ):
            failures.append("131-V checkpoint ordering drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("131-V workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-V source or structural boundary unavailable")
    return tuple(failures)


def _arch131_published_prepare_operator_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/robinhood_prepare_operator.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "874122a602008c0e85cd9f3ac1cafc2d86acbd71581a47fe1dba23d39221785d"
        ):
            failures.append("131-U PREPARE composition/browser/effect boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-published-prepare-operator"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "284134d18999c57e6804b38aed32fe314a55997f64a4d2d398cec172bec892ed"
        ):
            failures.append("131-U source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-U remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-U checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-U checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-U checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-published-session-prepare")
            + 1
        ):
            failures.append("131-U checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-U workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-U source or structural boundary unavailable")
    return tuple(failures)


def _arch131_session_admission_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/session_admission.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "12afcc9014383695b0b10ca7a8d71bd61f40ebc60e07588eabe6dd98fba49d92"
        ):
            failures.append("131-M deterministic temporal boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-session-admission"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "1bc810681800fe4ee34053bb0dde0458f916ad1e445e2c8996a09e7754e8d95f"
        ):
            failures.append("131-M source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-M remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-M checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-M checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-M checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-live-qualification-verifier")
            + 1
        ):
            failures.append("131-M checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-M workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-M source or structural boundary unavailable")
    return tuple(failures)


def _arch131_risk_price_snapshot_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/risk_prices.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "5987785d351218fbd452bcd13dc5e9239341345a922f6d097d8f28c4ae68112b"
        ):
            failures.append("131-N canonical risk-price boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-risk-price-snapshot"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "8ce08250dfb33311c8755a086c93a5ef72618834c100b326662af1b50f6fa6cd"
        ):
            failures.append("131-N source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-N remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-N checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-N checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-N checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-session-admission") + 1):
            failures.append("131-N checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-N workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-N source or structural boundary unavailable")
    return tuple(failures)


def _arch131_forward_paper_preview_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/forward_preview.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "d5f9746abeb119336773a82e3a5d5de4e66c72147ee0a7eac45fd7e0a9b384b0"
        ):
            failures.append("131-O forward-preview boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-forward-paper-preview"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "aea7a5069b96a9d9467751fe4fb2a6a894967bb9115969bdda3f2cd9c02e8408"
        ):
            failures.append("131-O source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-O remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-O checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-O checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-O checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-risk-price-snapshot") + 1):
            failures.append("131-O checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-O workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-O source or structural boundary unavailable")
    return tuple(failures)


def _arch131_risk_price_acquisition_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/risk_price_acquisition.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "57f86533abdd21e3cc673dd5c0bcbfb14298b1fdc057de32e7aa458218425f61"
        ):
            failures.append("131-P risk-price acquisition boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-risk-price-acquisition"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "bdbab6decc92b66f3e7973910b4c0f8e4d6f552249ac5562dacaf1e5cd7b58a5"
        ):
            failures.append("131-P source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-P remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-P checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-P checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-P checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-preview") + 1
        ):
            failures.append("131-P checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-P workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-P source or structural boundary unavailable")
    return tuple(failures)


def _arch131_supervised_forward_paper_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/supervised_forward_paper.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "2f7c34cbe29fafac41ee004817b4dcd25f470a0962d716972e738b98253a76ee"
        ):
            failures.append("131-Q supervised forward-paper boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-supervised-forward-paper"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "883effee55b5a3e0ac0888575d0a3079ae33c0df22add5e8f9e46f651e5f696e"
        ):
            failures.append("131-Q source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-Q remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-Q checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-Q checkpoint has host/effect capability")
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-Q checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-risk-price-acquisition") + 1
        ):
            failures.append("131-Q checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-Q workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-Q source or structural boundary unavailable")
    return tuple(failures)


def _arch131_prepare_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/review_paper/prepare_qualification.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        if (
            hashlib.sha256(
                ast.dump(ast.parse(text_value), include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != "b8d00a714e5bb8e8e05af950db0fb0b9e6634f4573149ba71dedd567a386b21d"
        ):
            failures.append("131-R PREPARE qualification boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-supervised-prepare-qualification"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "609db74ff7dc0436e06dfec6a2127ccd248882b1d4c1d5dcb722081c95769fbe"
        ):
            failures.append(
                "131-R PREPARE qualification source-only checkpoint registration drift"
            )

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-R PREPARE qualification remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append(
                "131-R PREPARE qualification checkpoint batch registration drift"
            )

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append(
                "131-R PREPARE qualification checkpoint has host/effect capability"
            )
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append(
                "131-R PREPARE qualification checkpoint remote branch drift"
            )
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-supervised-forward-paper")
            + 1
        ):
            failures.append("131-R PREPARE qualification checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append(
                "131-R PREPARE qualification workflow invocation/order drift"
            )
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append(
            "131-R PREPARE qualification source or structural boundary unavailable"
        )
    return tuple(failures)


def _arch131_prepare_verifier_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/robinhood_prepare_qualification_verifier.py"
        text_value = path.read_text(encoding="utf-8")
        # Pin the complete module, including every import, helper and call.
        data = text_value.encode("utf-8")
        actual_blob = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
        ).hexdigest()
        if actual_blob != "8636e91df74ce8153930817c471043fdb21737f9":
            failures.append("131-R PREPARE verifier boundary drift")

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-supervised-prepare-verifier"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "b9efd873a9705fea3130b8d74e45d6d2628d499c85507504645b5bc5cf1a5a89"
        ):
            failures.append(
                "131-R PREPARE verifier source-only checkpoint registration drift"
            )

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-R PREPARE verifier remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or hashlib.sha256(
                ast.dump(ci_assignments[0].value, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest()
            != REVIEWED_ACTIVE_CI_CHECKPOINTS_SHA256
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append(
                "131-R PREPARE verifier checkpoint batch registration drift"
            )

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append(
                "131-R PREPARE verifier checkpoint has host/effect capability"
            )
        if spec.remote_branch != ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH:
            failures.append("131-R PREPARE verifier checkpoint remote branch drift")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (
            ACTIVE_CI_CHECKPOINTS.index(
                "arch131-robinhood-supervised-prepare-qualification"
            )
            + 1
        ):
            failures.append("131-R PREPARE verifier checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-R PREPARE verifier workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append(
            "131-R PREPARE verifier source or structural boundary unavailable"
        )
    return tuple(failures)


def _arch131_live_qualification_verifier_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        path = repo_root / "src/trading_bot/robinhood_live_qualification_verifier.py"
        text_value = path.read_text(encoding="utf-8")
        data = text_value.encode("utf-8")
        actual = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
        ).hexdigest()
        if actual != ARCH131_LQ_SOURCE_BLOB_SHA1:
            failures.append("131-LQ read-only reconciliation boundary drift")
        ast.parse(text_value)

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-live-qualification-verifier"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "e122534ab36defb989812bdf1575806a0eeada2c9a1db286b58d22fce848339c"
        ):
            failures.append("131-LQ source-only checkpoint registration drift")

        side_branch_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH"
        ]
        if (
            len(side_branch_assignments) != 1
            or ast.literal_eval(side_branch_assignments[0].value)
            != "feature/robinhood-review-paper-side-foundation"
        ):
            failures.append("131-LQ remote branch authority drift")

        ci_assignments = [
            node
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(ci_assignments) != 1
            or tuple(ast.literal_eval(ci_assignments[0].value)) != ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("131-LQ checkpoint batch registration drift")

        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-LQ checkpoint has host/effect capability")
        if ACTIVE_CI_CHECKPOINTS.count(name) != 1 or ACTIVE_CI_CHECKPOINTS.index(
            name
        ) != (ACTIVE_CI_CHECKPOINTS.index("arch131-robinhood-forward-paper-cycle") + 1):
            failures.append("131-LQ checkpoint ordering drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-LQ workflow invocation/order drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-LQ source or structural boundary unavailable")
    return tuple(failures)


def _arch131_virtual_risk_context_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (repo_root / "src/trading_bot/review_paper/risk_context.py").read_text(
                encoding="utf-8"
            )
        )
        # Pin the whole module: closed imports/calls, strict inputs, UTC ordering,
        # exact prices, one reconstruction, one snapshot, and all context fields.
        # Any added helper, risk/bridge/operator/performance use, identity creation
        # or network/host/config mutation changes this structural boundary.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "92f04d726f30bca61cb245456b782185fc183c10c71752664b0ba171e6a2d241"
        ):
            failures.append("131-K durable ledger/snapshot/context boundary drift")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-virtual-risk-context"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        # Pin test/lint coverage, authority binding, remote, and source-only flags.
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "94fc142aa4272e37708964b62244b280213a9a26b63fa3520c5d262a9b9f6cec"
        ):
            failures.append("131-K source-only checkpoint registration drift")
        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-K checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-K workflow invocation/131-J ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-K source or structural boundary unavailable")
    return tuple(failures)


def _arch131_deterministic_paper_pipeline_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (repo_root / "src/trading_bot/robinhood_paper_pipeline.py").read_text(
                encoding="utf-8"
            )
        )
        # Freeze the whole module: immutable result invariants, caller-owned
        # identities/context/limits, exactly one evaluation, rejected early
        # return, authoritative bridge, and one exact operator forwarding call.
        # Extra helpers/imports/calls, UUID creation, OrderEngine/MCP/OAuth,
        # config/logging/host effects, loops, retries and schedulers all drift.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "ee8b2a62bc434d4f611a27e786e3c30fcf1e7b0243f4b9fd70cb4686aae276b2"
        ):
            failures.append(
                "131-J deterministic composition/result/effect boundary drift"
            )
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-deterministic-paper-pipeline"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        # Also freeze test/lint surfaces, remote branch, authority binding and
        # explicit preflight=None/execute=None; no host capability is registered.
        if len(registrations) != 1 or (
            hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "59c840ae9e36569ba06afc08624d9bb8e47de59bd19d20f217866c51d3fcc8dc"
        ):
            failures.append("131-J source-only checkpoint registration drift")
        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-J checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-J workflow invocation/131-I ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-J source or structural boundary unavailable")
    return tuple(failures)


def _arch131_paper_intent_bridge_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    try:
        tree = ast.parse(
            (repo_root / "src/trading_bot/review_paper/intent_bridge.py").read_text(
                encoding="utf-8"
            )
        )
        # Freeze every mapping, exact type guard, timestamp guard, and explicit
        # identity parameter. Whole-module coverage also forbids extra helpers,
        # dynamic calls, imports, logging, or module-level effects.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "48579d59a3940db668d2381b87a2ff63b02327f7f1bfca8d823926b78519054a"
        ):
            failures.append("131-I exact mapping/type/time/identity boundary drift")
        allowed_imports = {
            "__future__": {"annotations"},
            "uuid": {"UUID"},
            "trading_bot.execution.models": {"ExecutionInstruction"},
            "trading_bot.review_paper.models": {"ReviewPaperIntent"},
            "trading_bot.risk.models": {"RiskDecision", "RiskOutcome"},
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                failures.append("131-I unreviewed import/effect surface")
            elif isinstance(node, ast.ImportFrom):
                if (
                    node.level != 0
                    or node.module not in allowed_imports
                    or any(
                        name.asname is not None
                        or name.name not in allowed_imports[node.module]
                        for name in node.names
                    )
                ):
                    failures.append("131-I unreviewed import/effect surface")
            elif isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in {
                    "type",
                    "TypeError",
                    "ValueError",
                    "tuple",
                    "ReviewPaperIntent",
                }:
                    failures.append("131-I unreviewed call/effect surface")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        name = "arch131-robinhood-paper-intent-bridge"
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == name
                for item in node.keywords
            )
        ]
        if len(registrations) != 1:
            failures.append("131-I source-only registration missing")
        else:
            fields = {item.arg: item.value for item in registrations[0].keywords}
            for field in ("preflight", "execute"):
                value = fields.get(field)
                if not isinstance(value, ast.Constant) or value.value is not None:
                    failures.append("131-I checkpoint has host/effect capability")
            check = fields.get("authority_check")
            if (
                not isinstance(check, ast.Name)
                or check.id != "_arch131_paper_intent_bridge_authority_check"
            ):
                failures.append("131-I authority registration drift")
        spec = _checkpoint_specs()[name]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-I checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-I workflow invocation/131-H ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-I source or structural boundary unavailable")
    return tuple(failures)


def _arch131_paper_operator_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = list(_arch131_agentic_account_authority_check(repo_root))
    failures.extend(_arch131_windows_oauth_authority_check(repo_root))
    try:
        source = (repo_root / "src/trading_bot/robinhood_paper_operator.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        # Freeze the complete composition, browser denial, path/source admission,
        # closed evidence schema and serialization boundary independent of format.
        if (
            hashlib.sha256(
                ast.dump(tree, include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "d8ba2b1efdda9ea075e1cdf5b400742500bc4793af337351f7d35c566ed48b87"
        ):
            failures.append("131-H operator composition/redaction boundary drift")
        status_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_git"
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "status"
        ]
        if len(status_calls) != 1 or tuple(
            argument.value if isinstance(argument, ast.Constant) else None
            for argument in status_calls[0].args[1:]
        ) != ("status", "--porcelain=v1", "--untracked-files=all"):
            failures.append("131-H source cleanliness arguments drift")
        cycle_tree = ast.parse(
            (repo_root / "src/trading_bot/robinhood_paper_cycle.py").read_text(
                encoding="utf-8"
            )
        )
        cycle_runs = [
            node
            for node in ast.walk(cycle_tree)
            if isinstance(node, ast.FunctionDef) and node.name == "run"
        ]
        if (
            len(cycle_runs) != 1
            or hashlib.sha256(
                ast.dump(cycle_runs[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != "a86c598165ddb9334c771f6490571f46f102575202ff477208e92f1d65e04bed"
        ):
            failures.append("131-H post-review failure guard drift")
        for token in (
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        ):
            if token in source:
                failures.append("131-H forbidden mutation surface")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == "arch131-robinhood-paper-operator"
                for item in node.keywords
            )
        ]
        if len(registrations) != 1:
            failures.append("131-H source-only registration missing")
        else:
            fields = {item.arg: item.value for item in registrations[0].keywords}
            for field in ("preflight", "execute"):
                value = fields.get(field)
                if not isinstance(value, ast.Constant) or value.value is not None:
                    failures.append("131-H checkpoint has host/effect capability")
        spec = _checkpoint_specs()["arch131-robinhood-paper-operator"]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-H checkpoint has host/effect capability")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("131-H workflow ordering drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-H source or structural boundary unavailable")
    return tuple(failures)


def _arch131_agentic_account_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = list(_arch131_direct_mcp_authority_check(repo_root))
    failures.extend(_arch131_mcp_schema_authority_check(repo_root))
    failures.extend(_arch131_paper_cycle_authority_check(repo_root))
    # Freeze the reviewed dispatch/result boundaries by AST, independent of formatting.
    expected_boundaries = {
        "create_robinhood_agentic_account_resolver": (
            "46c9aefd35d30a33144f9c5df8e38f73440ae160c46c70ac01d29d7e4aef6e3d"
        ),
        "_accounts_structured_result": (
            "85c5807dffab7b33a9863e5d568fbe309159188374c0d7274cd19b153cd6a17c"
        ),
        "_require_review_read_tools": (
            "fa32303576c5bde08977352c878113bb7c687ae62c0863499c4fb56f70b41ad6"
        ),
        "_structured_result": (
            "d915278f59306fd2f4037859cbfa24e66886b96d9b79dd7fc71ee0eff87bba83"
        ),
        "review_equity_order": (
            "89462d4a8178a599feb6eaf076aceb8dba57f3dbb026c630f654fb86f732441c"
        ),
        "get_equity_quotes": (
            "d7abf621e34cd63b373bc1315a85f2a75cd960c3bbd43ff2f4dabe3b7526b182"
        ),
        "get_equity_orders": (
            "79ea648678d31543e48877310ea0862583ca769c06c781dddaf214dd02e88e21"
        ),
        "_invoke": ("43928e96254633e219999afaafb132755b23cc489fe73cc38b702c76f515b24e"),
        "_call_tool_once": (
            "684a89f8028f3deb6f4a84753b0b7cbe77be2e40293368837f5eb0d8cd0d2105"
        ),
        "_get_accounts": (
            "67bdf9bcf91217f7bb07a595882b72e1aa4e9347b7610d257892bae9ed8f1575"
        ),
        "_request_once": (
            "5fb0c878f9ead1b967cb1e996824e12c36674abcbd84ea8edceae17ea3530816"
        ),
    }
    try:
        sdk_source = (
            repo_root / "src/trading_bot/robinhood_mcp/sdk_transport.py"
        ).read_text(encoding="utf-8")
        sdk_tree = ast.parse(sdk_source)
        for name, expected in expected_boundaries.items():
            nodes = [
                node
                for node in ast.walk(sdk_tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name
            ]
            if (
                len(nodes) != 1
                or hashlib.sha256(
                    ast.dump(nodes[0], include_attributes=False).encode("utf-8")
                ).hexdigest()
                != expected
            ):
                failures.append(f"131-G internal/public MCP boundary drift: {name}")
        public_functions = {
            node.name
            for node in sdk_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        }
        if public_functions != {
            "create_robinhood_oauth_factory",
            "create_robinhood_agentic_account_resolver",
        }:
            failures.append("131-G exposes an unreviewed public MCP function")
        for relative in (
            "src/trading_bot/robinhood_mcp/account_resolution.py",
            "src/trading_bot/robinhood_mcp/__init__.py",
        ):
            source = (repo_root / relative).read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and node.name in {"get_accounts", "call_tool"}:
                    failures.append("131-G exposes a raw account/generic MCP tool")
            for token in (
                "place_equity_order",
                "cancel_equity_order",
                "place_option_order",
                "cancel_option_order",
                "exercise_option",
                "place_crypto_order",
                "cancel_crypto_order",
            ):
                if token in source:
                    failures.append(f"131-G exposes forbidden tool: {token}")
            if relative.endswith("account_resolution.py"):
                names = _qualified_names(tree)
                if any(
                    name == "print"
                    or name == "open"
                    or name.endswith(
                        (
                            ".call_tool",
                            ".write_text",
                            ".write_bytes",
                            ".info",
                            ".debug",
                            ".warning",
                            ".error",
                        )
                    )
                    for name in names
                ):
                    failures.append(
                        "131-G resolver contains raw-tool/log/persistence exposure"
                    )
                if "rhs_account_number" in source:
                    failures.append(
                        "131-G resolver contains alternate account identity"
                    )
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                item.arg == "name"
                and isinstance(item.value, ast.Constant)
                and item.value.value == "arch131-robinhood-agentic-account"
                for item in node.keywords
            )
        ]
        if len(registrations) != 1:
            failures.append("131-G source-only registration missing")
        else:
            fields = {item.arg: item.value for item in registrations[0].keywords}
            for field in ("preflight", "execute"):
                value = fields.get(field)
                if not isinstance(value, ast.Constant) or value.value is not None:
                    failures.append("131-G checkpoint has host/effect capability")
        spec = _checkpoint_specs()["arch131-robinhood-agentic-account"]
        if spec.preflight is not None or spec.execute is not None:
            failures.append("131-G checkpoint has host/effect capability")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("131-G source or structural boundary unavailable")
    return tuple(failures)


def _arch131_direct_mcp_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    relative = "src/trading_bot/robinhood_mcp/sdk_transport.py"
    try:
        source = (repo_root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        constants = {
            node.target.id: node.value
            for node in tree.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        expected_tools = (
            "get_equity_historicals",
            "get_equity_orders",
            "get_equity_quotes",
            "review_equity_order",
        )
        try:
            if ast.literal_eval(constants["_ALLOWED_TOOL_NAMES"]) != expected_tools:
                failures.append("Architecture 131-E direct MCP allowlist is not exact")
            if ast.literal_eval(constants["ROBINHOOD_TRADING_MCP_URL"]) != (
                "https://agent.robinhood.com/mcp/trading"
            ):
                failures.append("Architecture 131-E Robinhood endpoint drift")
        except (KeyError, ValueError, TypeError):
            failures.append("Architecture 131-E frozen constants are invalid")

        transport = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef)
                and node.name == "RobinhoodMcpStreamableHttpTransport"
            ),
            None,
        )
        if transport is None:
            failures.append("Architecture 131-E transport class is missing")
        else:
            public = {
                node.name
                for node in transport.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
            }
            expected_public = {
                "get_equity_historicals",
                "for_test",
                "review_equity_order",
                "get_equity_quotes",
                "get_equity_orders",
            }
            if public != expected_public:
                failures.append(
                    "Architecture 131-E public transport surface is not exact"
                )

        names = _qualified_names(tree)
        required = {
            "httpx2.AsyncClient",
            "streamable_http_client",
            "Client",
            "client.list_tools",
            "client.call_tool",
        }
        missing = sorted(required - names)
        if missing:
            failures.append(
                f"Architecture 131-E missing direct MCP bindings: {missing}"
            )
        for token in (
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        ):
            if token in source:
                failures.append(
                    f"Architecture 131-E exposes forbidden Robinhood tool: {token}"
                )
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 131-E direct MCP source unavailable")
    return tuple(failures)


def _arch131_performance_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    relative = "src/trading_bot/review_paper/performance.py"
    try:
        source = (repo_root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = _qualified_names(tree)
        forbidden = {
            "subprocess.run",
            "subprocess.Popen",
            "socket.socket",
            "requests.get",
            "requests.post",
            "httpx.get",
            "httpx.post",
            "urllib.request.urlopen",
        }
        if names & forbidden:
            failures.append("Architecture 131-D contains a network/effect boundary")
        for token in (
            "review_equity_order",
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "place_crypto_order",
        ):
            if token in source:
                failures.append(
                    f"Architecture 131-D references Robinhood effect tool: {token}"
                )
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 131-D performance source unavailable")
    return tuple(failures)


def _arch131_paper_cycle_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    relative = "src/trading_bot/robinhood_paper_cycle.py"
    try:
        source = (repo_root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = _qualified_names(tree)
        required = {
            "adapter.agentic_equity_orders",
            "self._adapter.review_market_order",
            "self._store.get_by_order_id",
            "self._store.record_market_review",
        }
        missing = sorted(required - names)
        if missing:
            failures.append(f"Architecture 131-C missing reviewed bindings: {missing}")
        forbidden = {
            "subprocess.run",
            "subprocess.Popen",
            "socket.socket",
            "requests.get",
            "requests.post",
            "httpx.get",
            "httpx.post",
            "urllib.request.urlopen",
        }
        if names & forbidden:
            failures.append("Architecture 131-C contains a concrete network boundary")
        for token in (
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        ):
            if token in source:
                failures.append(
                    f"Architecture 131-C exposes forbidden Robinhood tool: {token}"
                )
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 131-C paper cycle source unavailable")
    return tuple(failures)


def _arch131_mcp_schema_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    relative = "src/trading_bot/robinhood_mcp/adapter.py"
    try:
        source = (repo_root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        protocol = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef)
                and node.name == "RobinhoodReviewReadTransport"
            ),
            None,
        )
        if protocol is None:
            failures.append("Architecture 131-B transport protocol is missing")
        else:
            methods = {
                node.name for node in protocol.body if isinstance(node, ast.FunctionDef)
            }
            expected = {
                "get_equity_historicals",
                "review_equity_order",
                "get_equity_quotes",
                "get_equity_orders",
            }
            if methods != expected:
                failures.append(
                    "Architecture 131-B transport surface is not exact allowlist"
                )
        names = _qualified_names(tree)
        forbidden = {
            "subprocess.run",
            "subprocess.Popen",
            "socket.socket",
            "requests.get",
            "requests.post",
            "httpx.get",
            "httpx.post",
            "urllib.request.urlopen",
        }
        if names & forbidden:
            failures.append("Architecture 131-B contains a concrete network boundary")
        for token in (
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "cancel_option_order",
            "exercise_option",
            "place_crypto_order",
            "cancel_crypto_order",
        ):
            if token in source:
                failures.append(
                    f"Architecture 131-B exposes forbidden Robinhood tool: {token}"
                )
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 131-B adapter source unavailable")
    return tuple(failures)


def _arch131_review_paper_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    names: set[str] = set()
    for relative in (
        "src/trading_bot/review_paper/models.py",
        "src/trading_bot/review_paper/store.py",
    ):
        path = repo_root / relative
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names.update(_qualified_names(tree))
        except (OSError, UnicodeError, SyntaxError):
            failures.append(f"Architecture 131 source unavailable: {relative}")
    forbidden = {
        "subprocess.run",
        "subprocess.Popen",
        "socket.socket",
        "requests.get",
        "requests.post",
        "httpx.get",
        "httpx.post",
        "urllib.request.urlopen",
    }
    if names & forbidden:
        failures.append("Architecture 131 phase A contains a network/effect boundary")
    return tuple(failures)


def _arch130_r8i_d1_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    path = repo_root / "scripts/d10_arch130_r8i_d1.py"
    try:
        text = path.read_text(encoding="utf-8")
        data = text.encode("utf-8")
        actual = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
        ).hexdigest()
        if actual != ARCH130_R8I_D1_SOURCE_BLOB_SHA1:
            failures.append("Architecture 130 D1 reconciler source drift")
        tree = ast.parse(text)
        names = _qualified_names(tree)
        forbidden = {
            "subprocess.run",
            "open_writable_authority_sqlite_connection",
            "run_personal_desktop_unattended_one_week_soak",
            "run_personal_desktop_unattended_market_data_capture",
        }
        if names & forbidden:
            failures.append("Architecture 130 D1 effect boundary appeared")
    except (OSError, UnicodeError, SyntaxError):
        failures.append("Architecture 130 D1 reconciler source unavailable")
    return tuple(failures)


def _r8_halt_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    for name, expected in R8_HALT_SOURCE_PINS.items():
        try:
            text = (repo_root / name).read_text(encoding="utf-8")
            material = (
                ast.dump(ast.parse(text), include_attributes=False)
                if name.endswith(".py")
                else text
            )
            actual = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if actual != expected:
                failures.append(f"R8 halt frozen source drift: {name}")
        except (OSError, SyntaxError, UnicodeError):
            failures.append(f"R8 halt frozen source unavailable: {name}")
    try:
        tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        functions = _top_level_functions(tree)
        for name, expected in R8_HALT_RUNNER_PINS.items():
            material = ast.dump(functions[name], include_attributes=False)
            if hashlib.sha256(material.encode("utf-8")).hexdigest() != expected:
                failures.append(f"R8 halt runner composition drift: {name}")
        registrations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                kw.arg == "name"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value == "arch128-r8-terminal-halt"
                for kw in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode("utf-8")
            ).hexdigest()
            != R8_HALT_REGISTRATION_PIN
        ):
            failures.append("R8 halt registration drift")
    except (OSError, SyntaxError, UnicodeError, KeyError):
        failures.append("R8 halt runner source unavailable")
    return tuple(failures)


def _r8_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Freeze R8's public observer delegation, policy, and closed registration."""
    path = repo_root / "scripts" / "d10_arch128_r8_readonly.py"
    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        runner_tree = ast.parse(runner_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ("R8 source missing or invalid",)
    failures: list[str] = []
    functions = _top_level_functions(tree)
    preflight = functions.get("preflight")
    if set(functions) != {"_base", "_timestamp", "preflight"}:
        failures.append("R8 contains an unreviewed function surface")
    if preflight is None or ast.unparse(preflight.args) != "":
        failures.append("R8 requires zero-argument preflight")
    imports = {
        "from __future__ import annotations",
        "import re",
        "from datetime import UTC, datetime",
        "from typing import Final",
        "from scripts import d10_durable_wake_evidence_observe as observer",
        "from trading_bot.runtime.personal_desktop_d10_wake_evidence_log "
        "import MAX_D10_EVIDENCE_LOG_BYTES",
    }
    actual_imports = {
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    }
    if actual_imports != imports:
        failures.append("R8 contains unreviewed imports or direct host authority")
    allowed_calls = {
        "_base",
        "_timestamp",
        "type",
        "set",
        "dict",
        "any",
        "ValueError",
        "observer.observe",
        "EXPECTED_IDENTITY.items",
        "re.fullmatch",
        "datetime.fromisoformat",
        "parsed.isoformat",
        "parsed.isoformat().replace",
        "result.update",
    }
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    for call in calls:
        called = ast.unparse(call.func)
        if called not in allowed_calls:
            failures.append(f"R8 contains unreviewed authority call: {called}")
    observer_calls = [
        call for call in calls if ast.unparse(call.func) == "observer.observe"
    ]
    if (
        len(observer_calls) != 1
        or observer_calls[0].args
        or observer_calls[0].keywords
        or preflight is None
        or not any(
            isinstance(node, ast.Try)
            and isinstance(node.body[0], ast.Assign)
            and ast.unparse(node.body[0]) == "observation = observer.observe()"
            for node in preflight.body
        )
    ):
        failures.append("R8 must delegate exactly once to observer.observe()")
    for forbidden in (
        "ctypes",
        "subprocess",
        "os.system",
        "Popen",
        "guard.",
        "d10_arch128_r7",
        "scheduler_update",
        "_update_scheduler",
        "credential",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "RegisterTask",
        ".Run(",
    ):
        if forbidden in source:
            failures.append(f"R8 contains forbidden host/effect surface: {forbidden}")
    constants = {
        node.target.id: node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    expected_identity = {
        "schema": "personal-desktop-d10-evidence-observation/v1",
        "status": "OBSERVED",
        "deployment_id": "d2071f25-5a7c-5293-a28f-5b722c9917a2",
        "attestation_sha256": (
            "3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71"
        ),
        "soak_id": "30e31396-9f51-57ca-a480-d2a3e9cae4a0",
        "activation_utc": "2026-09-30T22:07:24.000000Z",
        "end_utc": "2026-10-07T22:07:24.000000Z",
        "evidence_path": (
            r"F:\AITradingBot\D10\evidence\wake-30e31396-9f51-57ca-a480-d2a3e9cae4a0.jsonl"
        ),
    }
    try:
        if ast.literal_eval(constants["EXPECTED_IDENTITY"]) != expected_identity:
            failures.append("R8 accepted R7 identity drift")
        if ast.literal_eval(constants["SCHEMA"]) != (
            "architecture-128-r8-readonly-first-wake/v1"
        ):
            failures.append("R8 schema drift")
    except (KeyError, ValueError, TypeError):
        failures.append("R8 frozen constants missing or invalid")
    effects = (
        "production_filesystem_mutation",
        "evidence_mutation",
        "scheduler_mutation",
        "lease_mutation",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    )
    expected_base = ast.parse(
        "def _base() -> dict[str, object]:\n    return "
        + repr(
            {
                "schema": "SCHEMA",
                "status": "BLOCKED",
                **dict.fromkeys(effects, "NOT_RUN"),
            }
        ).replace("'SCHEMA'", "SCHEMA")
    ).body[0]
    base = functions.get("_base")
    if base is None or ast.dump(base, include_attributes=False) != ast.dump(
        expected_base, include_attributes=False
    ):
        failures.append("R8 closed result effect fields drift")
    try:
        if (
            ast.literal_eval(constants["OBSERVER_EFFECT_FIELDS"])
            != effects[2:3] + effects[5:]
        ):
            failures.append("R8 accepted observer effect fields drift")
    except (KeyError, ValueError, TypeError):
        failures.append("R8 accepted observer effect fields invalid")
    comparisons = {
        ast.unparse(node)
        for node in ast.walk(preflight or tree)
        if isinstance(node, ast.Compare)
    }
    for required in (
        "type(observation) is not dict",
        "set(observation) != set(OBSERVATION_FIELDS)",
        "type(observation[field]) is not str",
        "observation[field] != expected",
        "observation[field] != 'NOT_RUN'",
        "type(observation['record_count']) is not int",
        "observation['record_count'] != 3",
        "type(observation['wake_count']) is not int",
        "observation['wake_count'] != 1",
        "observation['terminal'] is not False",
        "observation['terminal_kind'] is not None",
        "type(observation['last_outcome']) is not str",
        "observation['last_outcome'] not in ('COMPLETED', 'NO_ACTION')",
        "observation['last_stop_reason'] is not None",
        "observation['last_guard_reason'] is not None",
        "type(observation['evidence_byte_length']) is not int",
        "0 < observation['evidence_byte_length'] <= MAX_D10_EVIDENCE_LOG_BYTES",
        "type(observation['evidence_sha256']) is not str",
        "re.fullmatch('[0-9a-f]{64}', observation['evidence_sha256']) is None",
        "first > last",
    ):
        if required not in comparisons:
            failures.append(f"R8 acceptance policy drift: {required}")
    wrapper = _top_level_functions(runner_tree).get("_r8_preflight")
    if wrapper is None:
        failures.append("R8 runner missing read-only wrapper")
    else:
        wrapper_imports = [
            ast.unparse(node)
            for node in ast.walk(wrapper)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        if wrapper_imports != [
            "from scripts import d10_arch128_r8_readonly as admission"
        ]:
            failures.append("R8 wrapper contains unreviewed imports")
        for node in ast.walk(wrapper):
            if isinstance(node, ast.Call) and ast.unparse(node.func) not in {
                "admission.preflight",
                "_require_not_run",
                "primary.get",
                "type",
                "RuntimeError",
            }:
                failures.append("R8 wrapper contains direct host/effect authority")
        effects = (
            "production_filesystem_mutation",
            "evidence_mutation",
            "scheduler_mutation",
            "lease_mutation",
            "manual_task_start",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        )
        effect_calls = [
            node
            for node in ast.walk(wrapper)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "_require_not_run"
        ]
        try:
            if (
                len(effect_calls) != 1
                or ast.literal_eval(effect_calls[0].args[1]) != effects
            ):
                failures.append("R8 wrapper effect-field closure drift")
        except (IndexError, ValueError, TypeError):
            failures.append("R8 wrapper effect-field closure invalid")
    registrations = [
        node
        for node in ast.walk(runner_tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "CheckpointSpec"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "arch128-r8"
            for keyword in node.keywords
        )
    ]
    if len(registrations) != 1:
        failures.append("R8 registration missing or duplicated")
    else:
        keywords = {
            keyword.arg: ast.unparse(keyword.value)
            for keyword in registrations[0].keywords
        }
        for field, expected in (
            ("preflight", "_r8_preflight"),
            ("authority_check", "_r8_authority_check"),
            ("remote_branch", "'feature/d10c-durable-wake-evidence'"),
        ):
            if keywords.get(field) != expected:
                failures.append(f"R8 registration drift: {field}")
        if "execute" in keywords or "remote_head_env" in keywords:
            failures.append("R8 must have no execute or remote handoff surface")
    spec = _checkpoint_specs()["arch128-r8"]
    if spec.execute is not None or spec.preflight is not _r8_preflight:
        failures.append("R8 runtime registration must remain preflight-only")
    return tuple(failures)


def _r7_authority_check(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "scripts" / "d10_arch128_r7_readonly.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level_functions(tree)
    failures: list[str] = []

    preflight = functions.get("preflight")
    if preflight is None:
        failures.append("R7 read-only source missing preflight")
        return tuple(failures)

    names = _qualified_names(preflight)
    for required in (
        "r4c.observe_post",
        "r4w.WindowsArch128ReadOnlyReader",
        "WindowsCngVerifier",
        "r3._observe_scheduler",
        "r4.NamespaceState.COMPLETE",
    ):
        if required not in names:
            failures.append(f"R7 read-only source missing binding: {required}")

    for forbidden in (
        "WindowsArch128StagingBackend",
        "WindowsActivationLeaseBackend",
        "create_file",
        "publish_create_only",
        "rename_fixed_step",
        "RegisterTask",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "_update_scheduler",
        "_interactive_credential",
        "subprocess.run",
    ):
        if forbidden in source:
            failures.append(f"R7 read-only source contains effect surface: {forbidden}")

    protected_path = repo_root / "scripts" / "d10_arch128_r7_protected.py"
    if not protected_path.is_file():
        failures.append("R7 protected-dispatch source missing")
        return tuple(failures)
    protected_source = protected_path.read_text(encoding="utf-8")
    protected_tree = ast.parse(protected_source, filename=str(protected_path))
    protected_functions = _top_level_functions(protected_tree)
    dispatch = protected_functions.get("_dispatch")
    if dispatch is None:
        failures.append("R7 protected-dispatch source missing _dispatch")
    else:
        dispatch_source = ast.get_source_segment(protected_source, dispatch) or ""
        for required in (
            "EXECUTE_FLAG",
            "AUTH_ENV",
            "AUTH_VALUE",
            "r6.ReactivationOperator",
            "execute_r7=True",
        ):
            if required not in dispatch_source:
                failures.append(f"R7 protected dispatch missing: {required}")

    for forbidden in (
        "ctypes",
        "subprocess",
        "WindowsActivationLeaseBackend",
        "WindowsDeploymentBackend",
        "CreateFileW",
        "RegisterTask",
        "RegisterTaskDefinition",
        "Start-ScheduledTask",
        "_update_scheduler",
        "_interactive_credential",
    ):
        if forbidden in protected_source:
            failures.append(
                f"R7B dispatch contains premature host authority surface: {forbidden}"
            )

    failures.extend(_r7c_authority_check(repo_root))
    failures.extend(_r7d_authority_check(repo_root))
    return tuple(failures)


def _r7c_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Allow native bindings only in the separately reviewed fixed R7C surfaces."""
    import re

    failures = []
    sources = {}
    for name in ("d10_arch128_r7_windows.py", "d10_arch128_r7_observation.py"):
        path = repo_root / "scripts" / name
        if not path.is_file():
            failures.append(f"R7C source missing: {name}")
            continue
        source = path.read_text(encoding="utf-8")
        sources[name] = source
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = (
                    (node.module,)
                    if isinstance(node, ast.ImportFrom)
                    else tuple(alias.name for alias in node.names)
                )
                if isinstance(node, ast.ImportFrom) and node.module in (
                    "scripts",
                    "trading_bot.runtime",
                ):
                    modules = tuple(
                        node.module + "." + alias.name for alias in node.names
                    )
                allowed_imports = {
                    "__future__",
                    "ctypes",
                    "subprocess",
                    "getpass",
                    "json",
                    "os",
                    "re",
                    "sys",
                    "weakref",
                    "ntpath",
                    "collections.abc",
                    "concurrent.futures",
                    "dataclasses",
                    "datetime",
                    "pathlib",
                    "uuid",
                    "scripts.d10_arch128_r4_orchestration",
                    "scripts.d10_arch128_r4_windows",
                    "scripts.d10_arch128_r6_reactivation",
                    "scripts.d10_arch128_r7_observation",
                    "scripts.d10_python_substrate_windows",
                    "scripts.run_personal_desktop_d10_launch_guard",
                    "scripts.d10_protected_deployment",
                    "scripts.d10_protected_deployment_windows",
                    "scripts.d10_protected_replacement_windows",
                    "trading_bot.runtime.personal_desktop_d10_activation_lease",
                    "trading_bot.runtime.personal_desktop_d10_wake_evidence_log",
                    "trading_bot.runtime.personal_desktop_unattended_one_week_soak_scheduler_contract",
                }
                for module in modules:
                    if module not in allowed_imports:
                        failures.append(f"R7C unreviewed import: {module}")
            if isinstance(node, ast.Call):
                called = ast.unparse(node.func)
                if called in (
                    "eval",
                    "exec",
                    "__import__",
                    "open",
                    "os.system",
                    "subprocess.run",
                    "subprocess.call",
                ) or called.endswith(
                    (
                        ".unlink",
                        ".rmdir",
                        ".rmtree",
                        ".write_bytes",
                        ".write_text",
                        ".rename",
                        ".replace",
                    )
                ):
                    # datetime.replace is the fixed exact-second source clock.
                    if called != "datetime.now(UTC).replace":
                        failures.append(f"R7C unreviewed effect call: {called}")
                if called == "self._bind":
                    if (
                        len(node.args) < 2
                        or not isinstance(node.args[1], ast.Constant)
                        or node.args[1].value
                        not in (
                            "CreateFileW",
                            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
                        )
                    ):
                        failures.append("R7C unreviewed native binding")
        for forbidden in (
            "DeleteFile",
            "ReplaceFile",
            "SetEndOfFile",
            "WriteFile",
            "FlushFileBuffers",
            "Start-ScheduledTask",
            "Enable-ScheduledTask",
            "schtasks",
            "RegisterTaskDefinition",
            "rollback(",
            "cleanup(",
            "retry(",
            "guard.main",
            "guard._run_second_stage",
        ):
            if forbidden in source:
                failures.append(f"R7C forbidden authority: {name}:{forbidden}")
    validation = sources.get("d10_arch128_r7_observation.py", "")
    for required in (
        "D10_WAKE_EVIDENCE_ROOT",
        "ntpath.dirname(path) != str(D10_WAKE_EVIDENCE_ROOT)",
        "r6.derive_reactivation_plan",
        "guard.TRADING_EVIDENCE_FILE_ACCESS",
        "item.aces != aces",
        "item.size != 0",
        "item.links != 1",
        "PREDECESSOR_XML_SHA256",
        "scheduler_semantics(spec)",
    ):
        if required not in validation:
            failures.append(f"R7C exact validation missing: {required}")
    host = sources.get("d10_arch128_r7_windows.py", "")
    for required in (
        "class WindowsR7Boundaries:",
        "class WindowsR7EvidenceBackend(WindowsDeploymentBackend):",
        'TRADING_PID_ENV = "AI_TRADING_BOT_ARCH128_R7_TRADING_PID"',
        "d10_arch128_r7_scheduler_update.ps1",
        "d10_arch128_r3_scheduler_observe.ps1",
        "r4c.observe_r7_complete",
        "substrate.probe_trading_evidence_append_open",
        "guard.TRADING_EVIDENCE_FILE_ACCESS",
        "observation.require_plan",
        "observation.require_evidence_path",
        "observation.require_scheduler",
        "WindowsActivationLeaseBackend()",
        'payload = b""',
        'credential.password = ""',
        'self._phase = "PROBE_ATTEMPTED"',
        'self._require_phase("PROBED")',
        'self._evidence.create_file(path, b"")',
        "sys.stdin is not sys.__stdin__",
    ):
        if required not in host:
            failures.append(f"R7C fixed binding missing: {required}")
    if host:
        tree = ast.parse(host)
        classes = {
            node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
        }
        boundary = classes.get("WindowsR7Boundaries")
        methods = (
            {}
            if boundary is None
            else {
                node.name: node
                for node in boundary.body
                if isinstance(node, ast.FunctionDef)
            }
        )
        for method in (
            "observe_admission",
            "create_empty_evidence",
            "observe_evidence",
            "probe_trading_append_open",
            "acquire_scheduler_credential",
            "update_scheduler",
            "read_scheduler",
            "publish_lease",
        ):
            if method not in methods:
                failures.append(f"R7C fixed R6 boundary missing: {method}")
        factory = _top_level_functions(tree).get("host_factory")
        if (
            factory is None
            or factory.args.args
            or factory.args.kwonlyargs
            or factory.args.vararg
            or factory.args.kwarg
        ):
            failures.append("R7C factory accepts caller authority")
        transport = _top_level_functions(tree).get("_transport")
        if (
            transport is None
            or "helper not in (OBSERVE_HELPER, UPDATE_HELPER)"
            not in ast.get_source_segment(host, transport)
        ):
            failures.append("R7C transport is not fixed")
    native_path = repo_root / "scripts" / "d10_python_substrate_windows.py"
    native_source = native_path.read_text(encoding="utf-8")
    probe = _top_level_functions(ast.parse(native_source)).get(
        "probe_trading_evidence_append_open"
    )
    probe_source = "" if probe is None else ast.get_source_segment(native_source, probe)
    for required in (
        "_trading_token(trading_pid)",
        "ImpersonateLoggedOnUser",
        "RevertToSelf",
        "CreateFileW",
        "r6.guard.TRADING_EVIDENCE_FILE_ACCESS",
        "FILE_SHARE_READ",
        "OPEN_EXISTING",
        "FILE_FLAG_OPEN_REPARSE_POINT | r6.guard.FILE_FLAG_WRITE_THROUGH",
        '_check(revert(), "RevertToSelf")',
        "owned.callback(_close, token)",
        "_close(int(handle))",
    ):
        if required not in probe_source:
            failures.append(f"R7C Trading zero-write binding missing: {required}")
    for forbidden in (
        "WriteFile",
        "FlushFileBuffers",
        "SetEndOfFile",
        "DeleteFile",
        "MoveFile",
        "ReplaceFile",
    ):
        if forbidden in probe_source:
            failures.append(f"R7C Trading probe has forbidden effect: {forbidden}")
    helper_path = repo_root / "scripts" / "d10_arch128_r7_scheduler_update.ps1"
    helper = helper_path.read_text(encoding="utf-8") if helper_path.is_file() else ""
    assignments = re.findall(
        r"(?m)^\s*(\$(?:definition|trigger|action)[.][\w.]+)\s*=", helper
    )
    if assignments != [
        "$trigger.StartBoundary",
        "$trigger.EndBoundary",
        "$definition.Settings.Enabled",
    ]:
        failures.append("R7C scheduler mutations exceed frozen three-field scope")
    for required in (
        "arch128-r7-scheduler-update/v1",
        "activation_utc,password",
        "Read-FixedTask",
        "State -ne 1",
        "enabled = $false",
        "8d592a71258529fa88cd85866b0be1e91cf407d91e9acf5891a1bd82c0bf09b0",
        "$definition, 4,",
        "$callAttempted = $true",
        "$activation.AddDays(7)",
    ):
        if required not in helper:
            failures.append(f"R7C scheduler helper missing: {required}")
    for forbidden in (
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        ".Run(",
        "NewTask",
        "TASK_CREATE",
        "Remove-Item",
        "schtasks",
        "Start-Process",
    ):
        if forbidden in helper:
            if forbidden != "TASK_CREATE" or "TASK_CREATE" in re.sub(
                r"(?m)#.*$", "", helper
            ):
                failures.append(
                    f"R7C scheduler helper forbidden authority: {forbidden}"
                )
    if re.search(
        r"[.]\s*(?:Run|CreateTask)\s*[(]|Invoke-Expression|Invoke-Command|[&]", helper
    ):
        failures.append("R7C scheduler contains arbitrary invocation or manual start")
    if helper.count("RegisterTaskDefinition(") != 1:
        failures.append("R7C scheduler mutation must be a single fixed TASK_UPDATE")
    if host:
        host_functions = _top_level_functions(ast.parse(host))
        transport = host_functions.get("_transport")
        launches = [
            node
            for node in ast.walk(ast.parse(host))
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "subprocess.Popen"
        ]
        expected_command = ast.parse(
            "(POWERSHELL, '-NoProfile', '-NonInteractive', "
            "'-ExecutionPolicy', 'Bypass', '-File', str(helper))",
            mode="eval",
        ).body
        if (
            len(launches) != 1
            or not launches[0].args
            or ast.dump(launches[0].args[0]) != ast.dump(expected_command)
            or transport is None
            or launches[0].lineno < transport.lineno
            or launches[0].lineno > transport.end_lineno
        ):
            failures.append("R7C process transport exceeds the fixed helper command")
        for node in ast.walk(ast.parse(host)):
            if isinstance(node, ast.Call) and ast.unparse(node.func) in (
                "ctypes.CDLL",
                "os.open",
                "os.mkdir",
                "os.makedirs",
                "WindowsDeploymentBackend",
            ):
                failures.append(
                    "R7C contains unreviewed direct native/filesystem authority"
                )
    if host:
        console = _top_level_functions(ast.parse(host)).get(
            "_require_interactive_console"
        )
        dll_calls = [
            node
            for node in ast.walk(ast.parse(host))
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "ctypes.WinDLL"
        ]
        if (
            len(dll_calls) != 1
            or console is None
            or dll_calls[0].lineno < console.lineno
            or dll_calls[0].lineno > console.end_lineno
            or ast.literal_eval(dll_calls[0].args[0])
            != r"C:\Windows\System32\kernel32.dll"
        ):
            failures.append(
                "R7C native DLL binding exceeds the fixed read-only console proof"
            )
    if probe is not None:
        calls = [node for node in ast.walk(probe) if isinstance(node, ast.Call)]
        opens = [
            node
            for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == "create"
        ]
        expected_open = [
            "plan.evidence_path",
            "r6.guard.TRADING_EVIDENCE_FILE_ACCESS",
            "FILE_SHARE_READ",
            "None",
            "OPEN_EXISTING",
            "FILE_FLAG_OPEN_REPARSE_POINT | r6.guard.FILE_FLAG_WRITE_THROUGH",
            "None",
        ]
        if (
            len(opens) != 1
            or [ast.unparse(arg) for arg in opens[0].args] != expected_open
        ):
            failures.append("R7C Trading open policy is not exact")
        results = [
            node
            for node in calls
            if ast.unparse(node.func) == "r6.TradingOpenObservation"
        ]
        if len(results) != 1 or ast.unparse(results[0].args[-1]) != "0":
            failures.append("R7C Trading probe does not construct zero bytes written")
    return tuple(failures)


def _r7d_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Constrain the runner to reviewed dispatch and result classification."""
    path = repo_root / "scripts" / "checkpoint_runner.py"
    if not path.is_file():
        return ("R7D runner source missing",)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wrapper = _top_level_functions(tree).get("_r7_execute")
    if wrapper is None:
        return ("R7D runner missing _r7_execute",)
    failures: list[str] = []
    imports = [
        ast.unparse(node)
        for node in ast.walk(wrapper)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    if imports != [
        "from scripts import d10_arch128_r7_protected as r7_protected",
        "from scripts import d10_arch128_r7_windows as r7_windows",
    ]:
        failures.append("R7D runner imports are not the reviewed composition")
    calls = [node for node in ast.walk(wrapper) if isinstance(node, ast.Call)]
    dispatches = [
        node for node in calls if ast.unparse(node.func) == "r7_protected._dispatch"
    ]
    if (
        len(dispatches) != 1
        or [ast.unparse(arg) for arg in dispatches[0].args]
        != [
            "(r7_protected.EXECUTE_FLAG,)",
            "dict(os.environ)",
            "r7_windows.host_factory",
        ]
        or dispatches[0].keywords
    ):
        failures.append("R7D runner dispatch composition is not exact")
    effect_guards = [
        node for node in calls if ast.unparse(node.func) == "_require_not_run"
    ]
    expected_closed = (
        "production_filesystem_mutation",
        "manual_task_start",
        "source_launch",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    )
    if (
        len(effect_guards) != 1
        or len(effect_guards[0].args) != 2
        or ast.unparse(effect_guards[0].args[0]) != "primary"
        or ast.literal_eval(effect_guards[0].args[1]) != expected_closed
        or effect_guards[0].keywords
    ):
        failures.append("R7D runner forbidden-effect guard is not exact")
    allowed_calls = {
        "r7_protected._dispatch",
        "dict",
        "type",
        "_require_not_run",
        "primary.get",
        "RuntimeError",
        "any",
        "all",
        "completion.items",
        "blocked.items",
    }
    for node in calls:
        called = ast.unparse(node.func)
        if called not in allowed_calls:
            failures.append(f"R7D runner contains unreviewed authority call: {called}")
    for node in ast.walk(wrapper):
        if isinstance(node, (ast.For, ast.While, ast.Try, ast.With)):
            failures.append("R7D runner contains unreviewed retry/recovery flow")
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(
            node.ctx, ast.Store
        ):
            failures.append("R7D runner mutates external state")
    allowed_bindings = {
        "r7_protected._dispatch",
        "r7_protected.EXECUTE_FLAG",
        "r7_protected.SCHEMA",
        "r7_windows.host_factory",
        "os.environ",
    }
    for name in _qualified_names(wrapper):
        if name.startswith(("r7_protected.", "r7_windows.", "os.")):
            if name not in allowed_bindings:
                failures.append(f"R7D runner bypasses reviewed interlock: {name}")

    expected_completion = {
        "stage": "COMPLETE",
        "authorization": "ACCEPTED",
        "evidence_provision": "CALL_RETURNED",
        "scheduler_mutation": "CALL_RETURNED",
        "lease_publication": "PUBLISHED_VERIFIED",
        "reconciliation_required": False,
    }
    expected_blocked = {
        "stage": "EXECUTION_INTERLOCK",
        "authorization": "NOT_ACCEPTED",
        "evidence_provision": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "lease_publication": "NOT_RUN",
        "reconciliation_required": False,
    }
    for name, expected in (
        ("completion", expected_completion),
        ("blocked", expected_blocked),
    ):
        values = [
            node.value
            for node in ast.walk(wrapper)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            )
        ]
        if len(values) != 1 or ast.literal_eval(values[0]) != expected:
            failures.append(f"R7D runner {name} evidence contract changed")

    wrapper_source = ast.unparse(wrapper)
    for required in (
        "primary.get('automatic_retry') is not False",
        "primary.get('automatic_rollback') is not False",
        "primary.get('automatic_cleanup') is not False",
        "type(primary.get('reconciliation_required')) is not bool",
        "if status == 'PASS':",
        "any((primary.get(field) != value for field, value in completion.items()))",
        "elif status == 'BLOCKED' and all",
        "disposition = 'CONFIRMED'",
        "disposition = 'NOT_STARTED'",
        "disposition = 'MAY_HAVE_OCCURRED'",
    ):
        if required not in wrapper_source:
            failures.append(f"R7D runner missing conservative result guard: {required}")

    expected_classification = ast.parse(
        """
if status == "PASS":
    if any(primary.get(field) != value for field, value in completion.items()):
        raise RuntimeError("R7 PASS lacked exact verified completion evidence")
    disposition = "CONFIRMED"
elif status == "BLOCKED" and all(
    primary.get(field) == value for field, value in blocked.items()
):
    disposition = "NOT_STARTED"
else:
    disposition = "MAY_HAVE_OCCURRED"
"""
    ).body[0]
    classifications = [
        node
        for node in wrapper.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "status == 'PASS'"
    ]
    assignments = [
        node
        for node in ast.walk(wrapper)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "disposition"
            for target in node.targets
        )
    ]
    if (
        len(classifications) != 1
        or ast.dump(classifications[0]) != ast.dump(expected_classification)
        or len(assignments) != 3
    ):
        failures.append("R7D runner effect classification is not conservative")

    registrations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "CheckpointSpec"
        and any(
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "arch128-r7"
            for keyword in node.keywords
        )
    ]
    if len(registrations) != 1 or not any(
        keyword.arg == "execute" and ast.unparse(keyword.value) == "_r7_execute"
        for keyword in registrations[0].keywords
    ):
        failures.append("R7D runner registration is not the reviewed wrapper")
    if _checkpoint_specs()["arch128-r7"].execute is not _r7_execute:
        failures.append("R7D R7 execute wrapper is not registered")

    for filename, expected in (
        (
            "d10_arch128_r7_protected.py",
            {
                "EXECUTE_FLAG": "--execute-reviewed-r7-protected-activation",
                "AUTH_ENV": "AI_TRADING_BOT_ARCH128_R7_AUTHORIZATION",
                "AUTH_VALUE": "ARCH128_R7_PROTECTED_ACTIVATION_AUTHORIZED",
            },
        ),
        (
            "d10_arch128_r7_windows.py",
            {
                "TRADING_PID_ENV": "AI_TRADING_BOT_ARCH128_R7_TRADING_PID",
            },
        ),
    ):
        module = ast.parse(
            (repo_root / "scripts" / filename).read_text(encoding="utf-8")
        )
        constants = {}
        for node in module.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                constants[node.target.id] = node.value
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value
        for name, value in expected.items():
            literal = constants.get(name)
            if not isinstance(literal, ast.Constant) or literal.value != value:
                failures.append(f"R7D reviewed interlock changed: {name}")
    return tuple(failures)


def _parent_acl_authority_check(repo_root: Path) -> tuple[str, ...]:
    path = repo_root / "scripts" / "d10_arch128_parent_acl_repair.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = _top_level_functions(tree)
    failures: list[str] = []

    required_functions = {
        "_read_only",
        "_repair_once",
        "_dispatch",
        "_open_parent_for_acl",
        "main",
    }
    missing_functions = sorted(required_functions - set(functions))
    if missing_functions:
        failures.append(f"missing functions: {missing_functions}")
        return tuple(failures)

    readonly_names = _qualified_names(functions["_read_only"])
    for forbidden in (
        "_open_parent_for_acl",
        "apply_security_policy",
        "_repair_once",
    ):
        if forbidden in readonly_names:
            failures.append(f"read-only mode references mutation symbol: {forbidden}")

    repair_names = _qualified_names(functions["_repair_once"])
    for required in (
        "_observe_exact_drift",
        "_open_parent_for_acl",
        "apply_security_policy",
        "_target_policy",
        "_observe_exact_target",
    ):
        if required not in repair_names:
            failures.append(f"repair mode missing fixed binding: {required}")

    dispatch_source = ast.get_source_segment(source, functions["_dispatch"]) or ""
    for required in ("READ_ONLY_FLAG", "EXECUTE_FLAG", "AUTH_ENV", "AUTH_VALUE"):
        if required not in dispatch_source:
            failures.append(f"dispatch interlock missing: {required}")

    required_text = (
        "S-1-5-21-1397534616-3988210162-180023805-1005",
        "DRIFT_FLAGS: Final = 3",
        "_WRITE_DAC",
        "_WRITE_OWNER",
        "apply_security_policy(handle, _target_policy())",
        "STOPPED_AFTER_APPLY",
        "recursive_acl_mutation",
        "d10_child_mutation",
    )
    for required in required_text:
        if required not in source:
            failures.append(f"required repair invariant missing: {required}")

    for forbidden in (
        "os.walk",
        "rglob",
        "glob(",
        "SetNamedSecurityInfo",
        "icacls",
        "takeown",
        "RegisterTask",
        "Start-ScheduledTask",
        "Enable-ScheduledTask",
        "rename_fixed_step",
        "create_directory",
        "create_file",
        "publish_activation",
    ):
        if forbidden in source:
            failures.append(f"repair contains forbidden authority surface: {forbidden}")

    # Importing this source is deliberately side-effect free. Resolve the shared
    # fixed path from the reviewed contract rather than requiring a duplicated
    # raw literal in the repair module.
    from scripts import d10_arch128_parent_acl_repair as repair

    if repair.D10_PARENT != r"F:\AITradingBot":
        failures.append(f"fixed parent differs: {repair.D10_PARENT!r}")

    runner_path = repo_root / "scripts" / "checkpoint_runner.py"
    runner_source = runner_path.read_text(encoding="utf-8")
    runner_tree = ast.parse(runner_source, filename=str(runner_path))
    runner_functions = _top_level_functions(runner_tree)
    parent_execute = runner_functions.get("_parent_acl_execute")
    if parent_execute is None:
        failures.append("runner missing _parent_acl_execute")
    else:
        execute_names = _qualified_names(parent_execute)
        for required in ("repair._dispatch", "repair.EXECUTE_FLAG", "os.environ"):
            if required not in execute_names:
                failures.append(
                    "runner parent execute missing reviewed dispatch binding: "
                    f"{required}"
                )
        for forbidden in (
            "repair._repair_once",
            "repair._open_parent_for_acl",
            "apply_security_policy",
        ):
            if forbidden in execute_names:
                failures.append(
                    f"runner parent execute bypasses reviewed interlock: {forbidden}"
                )

    return tuple(failures)


def _require_not_run(
    result: Mapping[str, object],
    fields: Sequence[str],
) -> None:
    for field in fields:
        if result.get(field) != "NOT_RUN":
            raise RuntimeError(
                f"checkpoint result reported unexpected effect for {field}: "
                f"{result.get(field)!r}"
            )


def _parent_acl_preflight() -> dict[str, object]:
    from scripts import d10_arch128_parent_acl_repair as repair

    primary = repair._read_only()
    _require_not_run(
        primary,
        (
            "acl_mutation",
            "recursive_acl_mutation",
            "d10_child_mutation",
            "scheduler_mutation",
            "activation",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )
    return {
        "status": primary.get("status"),
        "primary": primary,
        "diagnostics": {},
    }


def _parent_acl_execute() -> dict[str, object]:
    from scripts import d10_arch128_parent_acl_repair as repair

    primary = repair._dispatch((repair.EXECUTE_FLAG,), dict(os.environ))
    _require_not_run(
        primary,
        (
            "recursive_acl_mutation",
            "d10_child_mutation",
            "scheduler_mutation",
            "activation",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )

    status = primary.get("status")
    if status == "PASS":
        if primary.get("acl_mutation") != "EXACT_PARENT_POLICY_APPLIED_AND_VERIFIED":
            raise RuntimeError(
                "parent ACL PASS lacked exact verified mutation evidence"
            )
        disposition = "CONFIRMED"
    elif status == "BLOCKED":
        if primary.get("acl_mutation") != "NOT_RUN":
            raise RuntimeError("blocked parent ACL execution reported a mutation")
        disposition = "NOT_STARTED"
    else:
        disposition = "MAY_HAVE_OCCURRED"

    return {
        "status": status,
        "primary": primary,
        "effect_disposition": disposition,
    }


def _r4_execute() -> dict[str, object]:
    from scripts import d10_arch128_r4_operator as operator

    primary = operator._dispatch((operator.EXECUTE_FLAG,), dict(os.environ))
    _require_not_run(
        primary,
        (
            "scheduler_mutation",
            "activation",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )

    status = primary.get("status")
    mutation = primary.get("production_filesystem_mutation")
    rename_1 = primary.get("rename_1")
    rename_2 = primary.get("rename_2")

    if status == "PASS":
        if (
            mutation != "REPLACEMENT_COMPLETE_AND_VERIFIED"
            or rename_1 != "SUCCESS"
            or rename_2 != "SUCCESS"
        ):
            raise RuntimeError(
                "R4 PASS lacked exact verified replacement completion evidence"
            )
        disposition = "CONFIRMED"
    elif status == "BLOCKED":
        if mutation != "NOT_RUN" or rename_1 != "NOT_RUN" or rename_2 != "NOT_RUN":
            raise RuntimeError("blocked R4 execution reported filesystem mutation")
        disposition = "NOT_STARTED"
    elif (
        status == "STOPPED"
        and mutation == "NOT_STARTED"
        and rename_1 == "NOT_RUN"
        and rename_2 == "NOT_RUN"
    ):
        disposition = "NOT_STARTED"
    else:
        disposition = "MAY_HAVE_OCCURRED"

    return {
        "status": status,
        "primary": primary,
        "effect_disposition": disposition,
    }


def _r5_effect_fields() -> tuple[str, ...]:
    return (
        "activation",
        "source_launch",
        "scheduler",
        "provider",
        "Paper-v2",
        "broker",
        "live",
    )


def _r5_substrate_preflight() -> dict[str, object]:
    from scripts import d10_arch128_r4_replacement as r4
    from scripts import d10_python_substrate_harness as h
    from scripts import d10_python_substrate_windows as w

    raw_pid = os.environ.get(R5_TRADING_PID_ENV, "")
    if not raw_pid.isascii() or not raw_pid.isdigit() or int(raw_pid) <= 0:
        primary = {
            "status": "BLOCKED",
            "reason": "trading_pid_interlock_not_exact",
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
        return {"status": "BLOCKED", "primary": primary}

    try:
        transcript_bytes = h.collect(w.WindowsCollector(int(raw_pid)))
        transcript = json.loads(transcript_bytes.decode("utf-8"))
        signed = transcript.get("signed_a123")
        if (
            type(signed) is not dict
            or signed.get("attestation_sha256")
            != r4.NEW_IDENTITY.unsigned_attestation_sha256
            or signed.get("python") != str(R5_PRODUCTION_PYTHON)
            or signed.get("version") != "3.14.3"
        ):
            raise RuntimeError("r5_substrate_signed_identity_drift")
        primary = {
            "status": "PASS",
            "production_python_substrate": "PASS",
            "trading_pid": int(raw_pid),
            "transcript_sha256": hashlib.sha256(transcript_bytes).hexdigest(),
            "transcript_byte_length": len(transcript_bytes),
            "substrate_transcript": transcript,
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
    except Exception as exc:
        primary = {
            "status": "BLOCKED",
            "reason": type(exc).__name__,
            "detail": str(exc),
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }

    _require_not_run(primary, _r5_effect_fields())
    return {"status": primary.get("status"), "primary": primary}


def _r5_trading_preflight() -> dict[str, object]:
    helper = Path(__file__).resolve().with_name("d10_arch128_r5_trading_child.py")
    command = (
        str(R5_PRODUCTION_PYTHON),
        "-I",
        "-S",
        "-B",
        "-X",
        f"pycache_prefix={R5_PYCACHE_PREFIX}",
        str(helper),
    )
    try:
        completed = subprocess.run(
            command,
            input=b"",
            capture_output=True,
            cwd=str(_REPOSITORY_ROOT),
            env={"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows"},
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        primary = {
            "status": "BLOCKED",
            "reason": type(exc).__name__,
            "detail": "r5_trading_child_transport_failed",
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
        return {"status": "BLOCKED", "primary": primary}

    if len(completed.stdout) > 2 * 1024 * 1024 or len(completed.stderr) > 64 * 1024:
        primary = {
            "status": "BLOCKED",
            "reason": "r5_trading_child_output_bound",
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
        return {"status": "BLOCKED", "primary": primary}

    try:
        primary = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, ValueError):
        primary = {
            "status": "BLOCKED",
            "reason": "r5_trading_child_json_invalid",
            **{field: "NOT_RUN" for field in _r5_effect_fields()},
        }
        return {"status": "BLOCKED", "primary": primary}

    if type(primary) is not dict:
        raise RuntimeError("R5 Trading child result type differs")
    _require_not_run(primary, _r5_effect_fields())
    if primary.get("second_stage_launch_trap") != "NOT_CALLED":
        raise RuntimeError("R5 Trading child reported second-stage launch")
    status = primary.get("status")
    if (completed.returncode == 0) != (status == "PASS"):
        raise RuntimeError("R5 Trading child exit/status disagree")
    if completed.returncode not in (0, 1):
        raise RuntimeError("R5 Trading child exit code differs")
    return {"status": status, "primary": primary}


def _r4_preflight() -> dict[str, object]:
    from scripts import d10_arch128_parent_acl_repair as repair
    from scripts import d10_arch128_r4_operator as operator

    primary = operator._read_only_preflight()
    _require_not_run(
        primary,
        (
            "production_filesystem_mutation",
            "rename_1",
            "rename_2",
            "scheduler_mutation",
            "activation",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )

    diagnostics: dict[str, object] = {}
    if (
        primary.get("status") != "PASS"
        and primary.get("detail") == "d10_parent_policy_mismatch"
    ):
        parent = repair._read_only()
        _require_not_run(
            parent,
            (
                "acl_mutation",
                "recursive_acl_mutation",
                "d10_child_mutation",
                "scheduler_mutation",
                "activation",
                "source_launch",
                "provider",
                "Paper-v2",
                "broker",
                "live",
            ),
        )
        diagnostics["parent_acl"] = parent

    return {
        "status": primary.get("status"),
        "primary": primary,
        "diagnostics": diagnostics,
    }


def _r7_preflight() -> dict[str, object]:
    from scripts import d10_arch128_r7_readonly as admission

    primary = admission.preflight()
    _require_not_run(
        primary,
        (
            "production_filesystem_mutation",
            "evidence_provision",
            "scheduler_mutation",
            "lease_publication",
            "manual_task_start",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )
    return {"status": primary.get("status"), "primary": primary}


def _arch130_r8i_d1_preflight() -> dict[str, object]:
    from scripts import d10_arch130_r8i_d1 as d1

    primary = d1.preflight()
    if type(primary) is not dict:
        raise RuntimeError("Architecture 130 D1 result must be an exact dictionary")
    _require_not_run(primary, d1.CLOSED_EFFECTS)
    return {"status": primary.get("status"), "primary": primary}


def _r8_preflight() -> dict[str, object]:
    from scripts import d10_arch128_r8_readonly as admission

    primary = admission.preflight()
    if type(primary) is not dict:
        raise RuntimeError("R8 preflight result must be an exact dictionary")
    _require_not_run(
        primary,
        (
            "production_filesystem_mutation",
            "evidence_mutation",
            "scheduler_mutation",
            "lease_mutation",
            "manual_task_start",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )
    return {"status": primary.get("status"), "primary": primary}


def _r8_halt_preflight() -> dict[str, object]:
    from scripts import d10_arch128_r8_halt_diagnostic as diagnostic
    from scripts import d10_arch128_r8_halt_windows as windows
    from scripts import d10_arch128_r8_terminal_halt as halt

    primary = halt.preflight(windows.ReadOnlyWindowsHost())
    closed = all(primary.get(field) == "NOT_RUN" for field in halt.CLOSED_EFFECTS)
    closed = closed and primary.get("scheduler_mutation") == "NOT_RUN"
    passed = primary.get("status") == "PASS" and closed
    passed = (
        passed
        and primary.get("call_attempted") is False
        and primary.get("disposition") == "NOT_CALLED"
    )
    if passed:
        try:
            halt.require_snapshot(
                halt.Snapshot(
                    primary["evidence"], primary["lease"], primary["scheduler"]
                ),
                enabled=True,
            )
        except Exception:
            passed = False

    diagnostics: dict[str, object] = {}
    if passed:
        try:
            native = diagnostic.observe()
        except Exception:
            native = {
                "status": "BLOCKED",
                "reason": "diagnostic_transport_failed",
            }
        diagnostics["native_pre_call"] = native
        expected_native = {
            "schema": diagnostic.SCHEMA,
            "status": diagnostic.READY,
            "reason": None,
            "call_attempted": False,
            "scheduler_mutation": "NOT_RUN",
        }
        native_ready = type(native) is dict and all(
            type(native.get(key)) is type(value) and native.get(key) == value
            for key, value in expected_native.items()
        )
        native_ready = native_ready and type(native.get("scheduler")) is dict
        if native_ready:
            try:
                halt.require_scheduler(native["scheduler"], enabled=True)
                halt.require_exact(
                    native["scheduler"],
                    primary["scheduler"],
                    "native_pre_call_scheduler_drift",
                )
            except Exception:
                native_ready = False
        passed = native_ready

    return {
        "status": "PASS" if passed else "BLOCKED",
        "primary": primary,
        "diagnostics": diagnostics,
    }


def _r8_halt_execute() -> dict[str, object]:
    from scripts import d10_arch128_r8_halt_windows as windows
    from scripts import d10_arch128_r8_terminal_halt as halt

    primary = halt.execute(
        (halt.EXECUTE_FLAG,), os.environ, windows.ProtectedWindowsHost
    )
    required = {
        "schema": halt.SCHEMA,
        "status": "PASS",
        "call_attempted": True,
        "disposition": "CALL_RETURNED",
        "incident": "EXACT_TERMINAL_FIRST_WAKE",
        "scheduler_pre": "ENABLED_NON_RUNNING_EXACT",
        "scheduler_mutation": "DISABLED_VERIFIED",
        "scheduler_post": "DISABLED_NON_RUNNING_EXACT",
        "evidence_before_after": "IDENTICAL",
        "lease_before_after": "IDENTICAL",
        "automatic_retry": False,
        "automatic_rollback": False,
        "automatic_cleanup": False,
        "failed_child_effects": "UNKNOWN_REQUIRES_READ_ONLY_RECONCILIATION",
        **dict.fromkeys(halt.CLOSED_EFFECTS, "NOT_RUN"),
    }
    passed = type(primary) is dict and all(
        type(primary.get(key)) is type(value) and primary.get(key) == value
        for key, value in required.items()
    )
    if passed:
        try:
            halt.require_snapshot(
                halt.Snapshot(
                    primary["evidence"], primary["lease"], primary["scheduler_before"]
                ),
                enabled=True,
            )
            halt.require_snapshot(
                halt.Snapshot(
                    primary["evidence"], primary["lease"], primary["scheduler_after"]
                ),
                enabled=False,
            )
        except Exception:
            passed = False
    not_called = (
        type(primary) is dict
        and primary.get("call_attempted") is False
        and primary.get("disposition") == "NOT_CALLED"
        and primary.get("scheduler_mutation") == "NOT_RUN"
        and all(primary.get(field) == "NOT_RUN" for field in halt.CLOSED_EFFECTS)
    )
    disposition = (
        "CONFIRMED" if passed else ("NOT_RUN" if not_called else "MAY_HAVE_OCCURRED")
    )
    return {
        "status": "PASS" if passed else "STOPPED",
        "primary": primary,
        "effect_disposition": disposition,
        "automatic_retry": "NOT_AUTHORIZED",
    }


def _r7_execute() -> dict[str, object]:
    from scripts import d10_arch128_r7_protected as r7_protected
    from scripts import d10_arch128_r7_windows as r7_windows

    primary = r7_protected._dispatch(
        (r7_protected.EXECUTE_FLAG,),
        dict(os.environ),
        r7_windows.host_factory,
    )
    if type(primary) is not dict or primary.get("schema") != r7_protected.SCHEMA:
        raise RuntimeError("R7 dispatch returned malformed evidence")
    _require_not_run(
        primary,
        (
            "production_filesystem_mutation",
            "manual_task_start",
            "source_launch",
            "provider",
            "Paper-v2",
            "broker",
            "live",
        ),
    )
    if (
        primary.get("automatic_retry") is not False
        or primary.get("automatic_rollback") is not False
        or primary.get("automatic_cleanup") is not False
        or type(primary.get("reconciliation_required")) is not bool
    ):
        raise RuntimeError("R7 dispatch returned invalid recovery evidence")

    status = primary.get("status")
    completion = {
        "stage": "COMPLETE",
        "authorization": "ACCEPTED",
        "evidence_provision": "CALL_RETURNED",
        "scheduler_mutation": "CALL_RETURNED",
        "lease_publication": "PUBLISHED_VERIFIED",
        "reconciliation_required": False,
    }
    blocked = {
        "stage": "EXECUTION_INTERLOCK",
        "authorization": "NOT_ACCEPTED",
        "evidence_provision": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "lease_publication": "NOT_RUN",
        "reconciliation_required": False,
    }
    if status == "PASS":
        if any(primary.get(field) != value for field, value in completion.items()):
            raise RuntimeError("R7 PASS lacked exact verified completion evidence")
        disposition = "CONFIRMED"
    elif status == "BLOCKED" and all(
        primary.get(field) == value for field, value in blocked.items()
    ):
        disposition = "NOT_STARTED"
    else:
        disposition = "MAY_HAVE_OCCURRED"
    return {
        "status": status,
        "primary": primary,
        "effect_disposition": disposition,
    }


SUPERVISED_RELEASE_SOURCES: Final = (
    "src/trading_bot/supervised_release/__init__.py",
    "src/trading_bot/supervised_release/model.py",
)
SUPERVISED_RELEASE_TESTS: Final = (
    *COMMON_TESTS,
    "tests/review_paper/test_supervised_release_foundation.py",
    "tests/scripts/certification_runner/test_profiles.py",
)
SUPERVISED_RELEASE_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    *SUPERVISED_RELEASE_SOURCES,
    "tests/review_paper/test_supervised_release_foundation.py",
    "tests/scripts/certification_runner/test_profiles.py",
)


def _supervised_release_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Source-only structural check; no host/native/scheduler callback."""
    failures = []
    try:
        spec = _checkpoint_specs()["arch133-robinhood-supervised-release-foundation"]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-supervised-release-foundation"
            or spec.tests != SUPERVISED_RELEASE_TESTS
            or spec.ruff_paths != SUPERVISED_RELEASE_RUFF_PATHS
            or spec.authority_check is not _supervised_release_authority_check
        ):
            failures.append("supervised release source-only registration drift")
        allowed = {
            "__future__",
            "hashlib",
            "json",
            "re",
            "dataclasses",
            "decimal",
            "pathlib",
            "uuid",
            "trading_bot.strategies",
            "trading_bot.supervised_release.model",
        }
        forbidden = {
            "open",
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "mkdir",
            "resolve",
            "exists",
            "run",
            "Popen",
            "system",
        }
        for relative in SUPERVISED_RELEASE_SOURCES:
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(alias.name not in allowed for alias in node.names):
                        failures.append("supervised release import boundary drift")
                if isinstance(node, ast.ImportFrom):
                    if node.module not in allowed or (
                        node.module == "pathlib"
                        and [alias.name for alias in node.names] != ["PureWindowsPath"]
                    ):
                        failures.append("supervised release import boundary drift")
                if isinstance(node, ast.Call):
                    function = node.func
                    name = (
                        function.id
                        if isinstance(function, ast.Name)
                        else getattr(function, "attr", "")
                    )
                    if name in forbidden:
                        failures.append("supervised release capability boundary drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("supervised release workflow drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("supervised release source unavailable")
    return tuple(failures)


SUPERVISED_RELEASE_BUNDLE_SOURCES: Final = (
    "src/trading_bot/supervised_release/bundle.py",
    "src/trading_bot/supervised_release/binding.py",
    "src/trading_bot/supervised_release/collector.py",
)
SUPERVISED_RELEASE_BUNDLE_PINS: Final = {
    "src/trading_bot/supervised_release/bundle.py": (
        "1a3edc3186da17851106810c7f34c43c17b56b7c"
    ),
    "src/trading_bot/supervised_release/binding.py": (
        "acdd2dfa17398afc822e770dd18166b747514cc1"
    ),
    "src/trading_bot/supervised_release/collector.py": (
        "fa914cc84d4e0c10818015b38b206ef0caf8c4e1"
    ),
}
SUPERVISED_RELEASE_BUNDLE_TESTS: Final = (
    *SUPERVISED_RELEASE_TESTS,
    "tests/review_paper/test_supervised_release_bundle.py",
)
SUPERVISED_RELEASE_BUNDLE_RUFF_PATHS: Final = (
    *SUPERVISED_RELEASE_RUFF_PATHS,
    *SUPERVISED_RELEASE_BUNDLE_SOURCES,
    "tests/review_paper/test_supervised_release_bundle.py",
)


def _supervised_release_bundle_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Read source only; never invoke the collector or a production observer."""
    failures = list(_supervised_release_authority_check(repo_root))
    try:
        spec = _checkpoint_specs()[
            "arch133-robinhood-supervised-release-build-verification"
        ]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch
            != "feature/robinhood-supervised-release-build-verification"
            or spec.tests != SUPERVISED_RELEASE_BUNDLE_TESTS
            or spec.ruff_paths != SUPERVISED_RELEASE_BUNDLE_RUFF_PATHS
            or spec.authority_check is not _supervised_release_bundle_authority_check
        ):
            failures.append("release bundle source-only registration drift")
        pure = {
            "__future__",
            "base64",
            "hashlib",
            "json",
            "dataclasses",
            "trading_bot.supervised_release.model",
            "trading_bot.supervised_release.bundle",
        }
        forbidden = {
            "write_text",
            "write_bytes",
            "mkdir",
            "unlink",
            "rename",
            "system",
            "Popen",
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
        }
        for relative in SUPERVISED_RELEASE_BUNDLE_SOURCES:
            if (
                _git_blob_sha1(repo_root / relative)
                != SUPERVISED_RELEASE_BUNDLE_PINS[relative]
            ):
                failures.append("release bundle reviewed source drift")
            collector = relative.endswith("/collector.py")
            allowed = pure | (
                {"os", "stat", "subprocess", "pathlib"} if collector else set()
            )
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                    alias.name not in allowed for alias in node.names
                ):
                    failures.append("release bundle import boundary drift")
                if isinstance(node, ast.ImportFrom) and node.module not in allowed:
                    failures.append("release bundle import boundary drift")
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                    if name in forbidden or (
                        not collector
                        and name
                        in {
                            "open",
                            "run",
                            "read_bytes",
                            "read_text",
                            "lstat",
                            "resolve",
                        }
                    ):
                        failures.append("release bundle capability boundary drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("release bundle workflow drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("release bundle source unavailable")
    return tuple(failures)


SUPERVISED_RELEASE_INSTALLATION_SOURCES: Final = (
    "src/trading_bot/supervised_release/installation_contract.py",
    "src/trading_bot/supervised_release/observer.py",
    "src/trading_bot/supervised_release/installer.py",
    "src/trading_bot/supervised_release/native_read.py",
    "src/trading_bot/supervised_release/native_write.py",
)
SUPERVISED_RELEASE_INSTALLATION_PINS: Final = {
    "src/trading_bot/supervised_release/installation_contract.py": (
        "ffff404ed16c7a476a0a3ecb622b8bdfbd701ef1"
    ),
    "src/trading_bot/supervised_release/observer.py": (
        "7b08981a06b5df123355abef678c6d17a54339ec"
    ),
    "src/trading_bot/supervised_release/installer.py": (
        "de510dbec9c72fea2fd3178accf9e2a5742dabaa"
    ),
    "src/trading_bot/supervised_release/native_read.py": (
        "bcbfd75043d6c31cad725425278dd7c80baff642"
    ),
    "src/trading_bot/supervised_release/native_write.py": (
        "fd059cd6363583d3923d073b8be78f8d3a1519ea"
    ),
}
SUPERVISED_RELEASE_INSTALLATION_TESTS: Final = (
    *SUPERVISED_RELEASE_BUNDLE_TESTS,
    "tests/review_paper/test_supervised_release_installation.py",
)
SUPERVISED_RELEASE_INSTALLATION_RUFF_PATHS: Final = (
    *SUPERVISED_RELEASE_BUNDLE_RUFF_PATHS,
    *SUPERVISED_RELEASE_INSTALLATION_SOURCES,
    "tests/review_paper/test_supervised_release_installation.py",
)


def _supervised_release_installation_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Source-only 133-AC admission; never instantiate a native backend."""
    failures = list(_supervised_release_bundle_authority_check(repo_root))
    try:
        spec = _checkpoint_specs()["arch133-robinhood-supervised-release-installation"]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-supervised-release-installation"
            or spec.tests != SUPERVISED_RELEASE_INSTALLATION_TESTS
            or spec.ruff_paths != SUPERVISED_RELEASE_INSTALLATION_RUFF_PATHS
            or spec.authority_check
            is not _supervised_release_installation_authority_check
        ):
            failures.append("release installation source-only registration drift")
        common = {
            "__future__",
            "dataclasses",
            "enum",
            "pathlib",
            "typing",
            "contextlib",
            "collections.abc",
            "trading_bot.supervised_release.model",
            "trading_bot.supervised_release.bundle",
            "trading_bot.supervised_release.binding",
            "trading_bot.supervised_release.installation_contract",
            "trading_bot.arch133_acl.read_only",
        }
        allowed_by_file = {
            "installation_contract.py": common,
            "observer.py": common
            | {"hashlib", "trading_bot.supervised_release.native_read"},
            "installer.py": common
            | {
                "trading_bot.supervised_release.observer",
                "trading_bot.supervised_release.native_write",
            },
            "native_read.py": common | {"ctypes", "sys"},
            "native_write.py": common
            | {
                "ctypes",
                "trading_bot.arch133_acl.administrator",
                "trading_bot.supervised_release.native_read",
                "trading_bot.supervised_release.observer",
            },
        }
        forbidden = {
            "unlink",
            "rmtree",
            "rename",
            "remove",
            "sleep",
            "run",
            "Popen",
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
        }
        for relative in SUPERVISED_RELEASE_INSTALLATION_SOURCES:
            if (
                _git_blob_sha1(repo_root / relative)
                != SUPERVISED_RELEASE_INSTALLATION_PINS[relative]
            ):
                failures.append("release installation reviewed source drift")
            allowed = allowed_by_file[Path(relative).name]
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                    alias.name not in allowed for alias in node.names
                ):
                    failures.append("release installation import boundary drift")
                if isinstance(node, ast.ImportFrom) and (
                    node.module not in allowed or node.level
                ):
                    failures.append("release installation import boundary drift")
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                    if name in forbidden:
                        failures.append(
                            "release installation capability boundary drift"
                        )
        # The two reused native read/token primitives remain pinned too; no
        # mutation-capable historical deployment module is admitted through them.
        for relative, pin in SUPERVISED_RELEASE_NATIVE_PRIMITIVE_PINS.items():
            if _git_blob_sha1(repo_root / relative) != pin:
                failures.append("release installation native primitive source drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("release installation source unavailable")
    return tuple(failures)


SUPERVISED_RELEASE_NATIVE_PRIMITIVE_PINS: Final = {
    "src/trading_bot/arch133_acl/read_only.py": (
        "09bdfb69953b155a1a75a9f2235456815f179b31"
    ),
    "src/trading_bot/arch133_acl/administrator.py": (
        "d3498b3fc9771e0cdccee76653e20a2ecf34b4d5"
    ),
}


SUPERVISED_MAINTENANCE_SOURCES: Final = (
    "src/trading_bot/supervised_release/maintenance.py",
)
SUPERVISED_MAINTENANCE_PINS: Final = {
    "src/trading_bot/supervised_release/maintenance.py": (
        "c06ce9728a9f5f36ef7015877ba5a6a875dd1097"
    ),
}
SUPERVISED_MAINTENANCE_TESTS: Final = (
    *SUPERVISED_RELEASE_INSTALLATION_TESTS,
    "tests/review_paper/test_supervised_maintenance_rebind.py",
    "tests/review_paper/test_arch133_scheduler_installation.py",
)
SUPERVISED_MAINTENANCE_RUFF_PATHS: Final = (
    *SUPERVISED_RELEASE_INSTALLATION_RUFF_PATHS,
    *SUPERVISED_MAINTENANCE_SOURCES,
    "tests/review_paper/test_supervised_maintenance_rebind.py",
)


def _supervised_maintenance_authority_check(repo_root: Path) -> tuple[str, ...]:
    """133-AD source-only closure; reuse the accepted AC pins unchanged."""
    failures = list(_supervised_release_installation_authority_check(repo_root))
    try:
        spec = _checkpoint_specs()["arch133-robinhood-supervised-maintenance-rebind"]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-supervised-maintenance-rebind"
            or spec.tests != SUPERVISED_MAINTENANCE_TESTS
            or spec.ruff_paths != SUPERVISED_MAINTENANCE_RUFF_PATHS
            or spec.authority_check is not _supervised_maintenance_authority_check
        ):
            failures.append("maintenance source-only registration drift")
        allowed = {
            "__future__",
            "re",
            "dataclasses",
            "datetime",
            "enum",
            "typing",
            "xml.etree",
            "trading_bot.arch133_acl.read_only",
            "trading_bot.supervised_release.binding",
            "trading_bot.supervised_release.bundle",
            "trading_bot.supervised_release.installation_contract",
            "trading_bot.supervised_release.model",
            "trading_bot.supervised_release.observer",
        }
        forbidden = {
            "open",
            "run",
            "Popen",
            "WinDLL",
            "read_text",
            "read_bytes",
            "unlink",
            "delete",
            "remove",
            "rename",
            "rmtree",
            "sleep",
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
            "install_release",
            "publish",
            "enable",
            "start",
        }
        for relative in SUPERVISED_MAINTENANCE_SOURCES:
            if (
                _git_blob_sha1(repo_root / relative)
                != SUPERVISED_MAINTENANCE_PINS[relative]
            ):
                failures.append("maintenance reviewed source drift")
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                    alias.name not in allowed for alias in node.names
                ):
                    failures.append("maintenance import boundary drift")
                if isinstance(node, ast.ImportFrom) and (
                    node.module not in allowed or node.level
                ):
                    failures.append("maintenance import boundary drift")
                if (
                    isinstance(node, ast.Call)
                    and getattr(node.func, "attr", getattr(node.func, "id", ""))
                    in forbidden
                ):
                    failures.append("maintenance capability boundary drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("maintenance workflow drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("maintenance source unavailable")
    return tuple(failures)


SUPERVISED_RUNTIME_ADMISSION_SOURCES: Final = (
    "src/trading_bot/supervised_release/model.py",
    "src/trading_bot/supervised_release/maintenance.py",
    "src/trading_bot/supervised_release/runtime_admission.py",
    "scripts/run_arch133_supervised_release_review_paper.py",
)
SUPERVISED_RUNTIME_ADMISSION_PINS: Final = {
    "src/trading_bot/supervised_release/model.py": (
        "1619bf29a3c0c8b262912dfaf517ae44e4b77708"
    ),
    "src/trading_bot/supervised_release/maintenance.py": (
        "c06ce9728a9f5f36ef7015877ba5a6a875dd1097"
    ),
    "src/trading_bot/supervised_release/runtime_admission.py": (
        "ef95b314c527d5f2e773b06c9d2a5f217ae8d09b"
    ),
    "scripts/run_arch133_supervised_release_review_paper.py": (
        "89178cd8f7dd3341a4016d005f388df4c85a55dc"
    ),
}
SUPERVISED_RUNTIME_ADMISSION_TESTS: Final = (
    *SUPERVISED_MAINTENANCE_TESTS,
    "tests/review_paper/test_supervised_runtime_host_admission.py",
)
SUPERVISED_RUNTIME_ADMISSION_RUFF_PATHS: Final = (
    *SUPERVISED_MAINTENANCE_RUFF_PATHS,
    "src/trading_bot/supervised_release/runtime_admission.py",
    "scripts/run_arch133_supervised_release_review_paper.py",
    "tests/review_paper/test_supervised_runtime_host_admission.py",
)


def _supervised_runtime_admission_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """133-AE source-only runtime admission; no real-host observer is constructed."""
    failures = list(_supervised_maintenance_authority_check(repo_root))
    try:
        spec = _checkpoint_specs()[
            "arch133-robinhood-supervised-runtime-host-admission"
        ]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch
            != "feature/robinhood-supervised-runtime-host-admission"
            or spec.tests != SUPERVISED_RUNTIME_ADMISSION_TESTS
            or spec.ruff_paths != SUPERVISED_RUNTIME_ADMISSION_RUFF_PATHS
            or spec.authority_check is not _supervised_runtime_admission_authority_check
        ):
            failures.append("runtime admission source-only registration drift")
        for relative, pin in SUPERVISED_RUNTIME_ADMISSION_PINS.items():
            if _git_blob_sha1(repo_root / relative) != pin:
                failures.append("runtime admission reviewed source drift")

        relative = "src/trading_bot/supervised_release/runtime_admission.py"
        tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
        allowed = {
            "__future__",
            "dataclasses",
            "enum",
            "pathlib",
            "typing",
            "trading_bot.arch133_acl.read_only",
            "trading_bot.supervised_release.binding",
            "trading_bot.supervised_release.bundle",
            "trading_bot.supervised_release.installation_contract",
            "trading_bot.supervised_release.model",
            "trading_bot.supervised_release.observer",
        }
        forbidden = {
            "open",
            "run",
            "Popen",
            "WinDLL",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "unlink",
            "delete",
            "remove",
            "rename",
            "rmtree",
            "sleep",
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
            "install_release",
            "publish",
            "enable",
            "start",
            "credential",
            "provider",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name not in allowed for alias in node.names
            ):
                failures.append("runtime admission import boundary drift")
            if isinstance(node, ast.ImportFrom) and (
                node.module not in allowed or node.level
            ):
                failures.append("runtime admission import boundary drift")
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", getattr(node.func, "id", ""))
                in forbidden
            ):
                failures.append("runtime admission capability boundary drift")

        launcher = ast.parse(
            (
                repo_root / "scripts/run_arch133_supervised_release_review_paper.py"
            ).read_text(encoding="utf-8")
        )
        launcher_imports = {
            alias.name
            for node in launcher.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        launcher_from = {
            node.module for node in launcher.body if isinstance(node, ast.ImportFrom)
        }
        if launcher_imports != {"sys"} or launcher_from != {
            "pathlib",
            "trading_bot.supervised_release",
        }:
            failures.append("runtime launcher import boundary drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("runtime admission workflow drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("runtime admission source unavailable")
    return tuple(failures)


SUPERVISED_DEPLOYMENT_QUALIFICATION_SOURCE: Final = (
    "src/trading_bot/supervised_release/qualification.py"
)
SUPERVISED_DEPLOYMENT_QUALIFICATION_PIN: Final = (
    "0cfa5453657519ab2db741a95e2b187cc7c789c3"
)
SUPERVISED_DEPLOYMENT_QUALIFICATION_TESTS: Final = (
    *SUPERVISED_RUNTIME_ADMISSION_TESTS,
    "tests/review_paper/test_supervised_deployment_qualification.py",
)
SUPERVISED_DEPLOYMENT_QUALIFICATION_RUFF_PATHS: Final = (
    *SUPERVISED_RUNTIME_ADMISSION_RUFF_PATHS,
    SUPERVISED_DEPLOYMENT_QUALIFICATION_SOURCE,
    "tests/review_paper/test_supervised_deployment_qualification.py",
)


def _supervised_deployment_qualification_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """133-AF inert qualification, chained to unchanged AC/AD/AE authority."""
    failures = list(_supervised_runtime_admission_authority_check(repo_root))
    try:
        name = "arch133-robinhood-supervised-deployment-qualification"
        spec = _checkpoint_specs()[name]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch
            != "feature/robinhood-supervised-deployment-qualification"
            or spec.tests != SUPERVISED_DEPLOYMENT_QUALIFICATION_TESTS
            or spec.ruff_paths != SUPERVISED_DEPLOYMENT_QUALIFICATION_RUFF_PATHS
            or spec.authority_check
            is not _supervised_deployment_qualification_authority_check
            or ACTIVE_CI_CHECKPOINTS[1] != name
        ):
            failures.append("deployment qualification source-only registration drift")
        path = repo_root / SUPERVISED_DEPLOYMENT_QUALIFICATION_SOURCE
        if _git_blob_sha1(path) != SUPERVISED_DEPLOYMENT_QUALIFICATION_PIN:
            failures.append("deployment qualification reviewed source drift")
        allowed = {
            "__future__",
            "dataclasses",
            "enum",
            "typing",
            "trading_bot.supervised_release.binding",
            "trading_bot.supervised_release.bundle",
            "trading_bot.supervised_release.installation_contract",
            "trading_bot.supervised_release.maintenance",
            "trading_bot.supervised_release.model",
            "trading_bot.supervised_release.observer",
            "trading_bot.supervised_release.runtime_admission",
        }
        forbidden = {
            "open",
            "run",
            "Popen",
            "WinDLL",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "unlink",
            "delete",
            "remove",
            "rename",
            "rmtree",
            "sleep",
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
            "install_release",
            "publish",
            "enable",
            "start",
            "credential",
            "provider",
            "begin",
            "finish",
            "repair",
            "cleanup",
            "retry",
            "activate",
            "rebind",
        }
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import) and any(
                alias.name not in allowed for alias in node.names
            ):
                failures.append("deployment qualification import boundary drift")
            if isinstance(node, ast.ImportFrom) and (
                node.module not in allowed or node.level
            ):
                failures.append("deployment qualification import boundary drift")
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", getattr(node.func, "id", ""))
                in forbidden
            ):
                failures.append("deployment qualification capability boundary drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("deployment qualification workflow drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("deployment qualification source unavailable")
    return tuple(failures)


SUPERVISED_INSTALLATION_OPERATOR_NAME: Final = (
    "arch133-robinhood-supervised-release-installation-operator"
)
SUPERVISED_INSTALLATION_OPERATOR_SOURCE: Final = (
    "src/trading_bot/supervised_release/installation_operator.py"
)
SUPERVISED_INSTALLATION_OPERATOR_PIN: Final = "91d3fa845825f02b525b3f578a9f1a011c422ba6"
SUPERVISED_INSTALLATION_REGISTRATION_PIN: Final = (
    "d771a020f19aea6a13e39cfc78316b9037cfd8fa4d9e1c668cd732a8aebb96ce"
)
SUPERVISED_INSTALLATION_OPERATOR_TESTS: Final = (
    *SUPERVISED_DEPLOYMENT_QUALIFICATION_TESTS,
    "tests/review_paper/test_supervised_release_installation_operator.py",
    "tests/review_paper/test_supervised_release_installation_reconciliation.py",
)
SUPERVISED_INSTALLATION_OPERATOR_RUFF_PATHS: Final = (
    *SUPERVISED_DEPLOYMENT_QUALIFICATION_RUFF_PATHS,
    SUPERVISED_INSTALLATION_OPERATOR_SOURCE,
    "tests/review_paper/test_supervised_release_installation_operator.py",
    "src/trading_bot/supervised_release/installation_reconciliation.py",
    "tests/review_paper/test_supervised_release_installation_reconciliation.py",
)
# This fixed external latch is independent of per-invocation evidence roots,
# release IDs, authorization tokens and source revisions. Never remove/reset it.
SUPERVISED_INSTALLATION_ATTEMPT: Final = Path(
    r"F:\AI\temp\arch133-ag-installation-attempt\attempt.json"
)
SUPERVISED_INSTALLATION_ATTEMPT_PIN: Final = (
    "7644631afa639683c4fa1c9f87773d631373901edd3d1db63d1950406a0b47fb"
)
_installation_execution_admitted = False
_installation_execution_source: tuple[str, str] | None = None


def _supervised_installation_operator_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Read source only; chain accepted AC/AD/AE/AF and freeze the AG bridge."""
    failures = list(_supervised_deployment_qualification_authority_check(repo_root))
    try:
        spec = _checkpoint_specs()[SUPERVISED_INSTALLATION_OPERATOR_NAME]
        if (
            spec.preflight is not _supervised_installation_preflight
            or spec.execute is not _supervised_installation_execute
            or spec.remote_head_env is not None
            or spec.remote_branch
            != "feature/robinhood-supervised-release-installation-operator"
            or spec.tests != SUPERVISED_INSTALLATION_OPERATOR_TESTS
            or spec.ruff_paths != SUPERVISED_INSTALLATION_OPERATOR_RUFF_PATHS
            or spec.authority_check
            is not _supervised_installation_operator_authority_check
            or ACTIVE_CI_CHECKPOINTS[0] != SUPERVISED_INSTALLATION_OPERATOR_NAME
        ):
            failures.append("installation operator registration drift")
        path = repo_root / SUPERVISED_INSTALLATION_OPERATOR_SOURCE
        if _git_blob_sha1(path) != SUPERVISED_INSTALLATION_OPERATOR_PIN:
            failures.append("installation operator reviewed source drift")
        allowed = {
            "__future__",
            "hashlib",
            "os",
            "re",
            "stat",
            "subprocess",
            "collections.abc",
            "dataclasses",
            "decimal",
            "pathlib",
            "trading_bot.arch133_acl.administrator",
            "trading_bot.strategies",
            "trading_bot.supervised_release.binding",
            "trading_bot.supervised_release.bundle",
            "trading_bot.supervised_release.collector",
            "trading_bot.supervised_release.installation_contract",
            "trading_bot.supervised_release.model",
            "trading_bot.supervised_release.native_read",
            "trading_bot.supervised_release.observer",
            "trading_bot.supervised_release.installer",
        }
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import) and any(
                alias.name not in allowed for alias in node.names
            ):
                failures.append("installation operator import boundary drift")
            if isinstance(node, ast.ImportFrom) and (
                node.module not in allowed or node.level
            ):
                failures.append("installation operator import boundary drift")
        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        functions = _top_level_functions(runner_tree)
        latch_declarations = [
            node.value
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "SUPERVISED_INSTALLATION_ATTEMPT"
        ]
        if (
            len(latch_declarations) != 1
            or hashlib.sha256(
                ast.dump(latch_declarations[0], include_attributes=False).encode()
            ).hexdigest()
            != SUPERVISED_INSTALLATION_ATTEMPT_PIN
        ):
            failures.append("installation attempt namespace source drift")
        registrations = [
            node
            for node in ast.walk(runner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CheckpointSpec"
            and any(
                keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == SUPERVISED_INSTALLATION_OPERATOR_NAME
                for keyword in node.keywords
            )
        ]
        if (
            len(registrations) != 1
            or hashlib.sha256(
                ast.dump(registrations[0], include_attributes=False).encode()
            ).hexdigest()
            != SUPERVISED_INSTALLATION_REGISTRATION_PIN
        ):
            failures.append("installation operator source registration drift")
        if set(SUPERVISED_INSTALLATION_RUNNER_PINS) != {
            "_supervised_installation_operator_authority_check",
            "_supervised_installation_admission",
            "_supervised_installation_preflight",
            "_supervised_installation_latch_consumed",
            "_consume_supervised_installation_attempt",
            "_supervised_installation_execute",
            "preflight_checkpoint",
            "execute_checkpoint",
            "main",
        }:
            failures.append("installation runner pin inventory drift")
        for name, pin in SUPERVISED_INSTALLATION_RUNNER_PINS.items():
            if (
                name not in functions
                or hashlib.sha256(
                    ast.dump(functions[name], include_attributes=False).encode()
                ).hexdigest()
                != pin
            ):
                failures.append("installation runner authority drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("installation operator source unavailable")
    return tuple(failures)


SUPERVISED_INSTALLATION_RUNNER_PINS: Final = {
    "_supervised_installation_operator_authority_check": (
        "d8538e6574915327f19929256da57f94a99de33109629b38132c445bf45cac5b"
    ),
    "_supervised_installation_admission": (
        "decdbd5c7afbd951a005c536ad479a63e8144d3be4e47cf46ff078e4a682dc7a"
    ),
    "_supervised_installation_preflight": (
        "eb7ef3df4a4344e57b36a3507bafdbbdc481f0b2dbd4857678d915fbba304e1b"
    ),
    "_supervised_installation_latch_consumed": (
        "03b801f9bd4213246b06cec716a6b95e60da5f33fa7c98c90a877a5a5d5a0376"
    ),
    "_consume_supervised_installation_attempt": (
        "fb58adf0e5d0c9ee78d16995abb49b1b654050099088aab00bfa050d1286358f"
    ),
    "_supervised_installation_execute": (
        "c4584e649ea5a947fe26d7ebe7db41d5a47f3b7812c2b73fc8d01faac877f9ce"
    ),
    "preflight_checkpoint": (
        "a5e63c447cb53e2998b4234dc0ecb2f81c2954b7677bc78d8414f6d278b8b15f"
    ),
    "execute_checkpoint": (
        "35164fc0985154d41a9f35f7b6b144df6ce86658941a083e7f5705fcee9366ed"
    ),
    "main": ("7327e8425a2c6b9f65250bc004b694a6f39a4c79cd654df9425ce73df0efd810"),
}


def _supervised_installation_admission(
    repo_root: Path, state: Mapping[str, object]
) -> None:
    from trading_bot.supervised_release import installation_operator as operator

    if (
        repo_root.resolve() != operator.WORKTREE.resolve()
        or _REPOSITORY_ROOT.resolve() != operator.WORKTREE.resolve()
        or state["branch"] != operator.BRANCH
        or state["porcelain"]
        or _git_output(repo_root, "remote", "get-url", "origin") != operator.ORIGIN
        or _git_output(repo_root, "merge-base", operator.BASE_HEAD, "HEAD")
        != operator.BASE_HEAD
        or _supervised_installation_operator_authority_check(repo_root)
    ):
        raise RuntimeError("installation source authority rejected")


def _supervised_installation_preflight() -> dict[str, object]:
    from trading_bot.supervised_release import installation_operator as operator

    state = _git_state(_REPOSITORY_ROOT)
    _supervised_installation_admission(_REPOSITORY_ROOT, state)
    if _remote_branch_head(_REPOSITORY_ROOT, operator.BRANCH) != state["head"]:
        raise RuntimeError("installation live remote authority rejected")
    result = operator._preflight()
    if (
        _supervised_installation_latch_consumed()
        and result.get("primary", {}).get("status") != "ALREADY_INSTALLED_VERIFIED"
    ):
        return {
            "status": "BLOCKED",
            "effect_disposition": "MAY_HAVE_OCCURRED",
            "primary": {
                "status": "INDETERMINATE",
                "disposition": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
                "reason": "CONSUMED_ATTEMPT",
            },
        }
    return result


def _supervised_installation_latch_consumed() -> bool:
    for path in reversed(
        (SUPERVISED_INSTALLATION_ATTEMPT, *SUPERVISED_INSTALLATION_ATTEMPT.parents)
    ):
        try:
            facts = path.lstat()
        except FileNotFoundError:
            return False
        if (
            stat.S_ISLNK(facts.st_mode)
            or getattr(facts, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or (
                path != SUPERVISED_INSTALLATION_ATTEMPT
                and not stat.S_ISDIR(facts.st_mode)
            )
        ):
            raise RuntimeError("installation attempt namespace rejected")
    return True


def _consume_supervised_installation_attempt() -> None:
    from trading_bot.supervised_release import installation_operator as operator

    if not _installation_execution_admitted:
        raise RuntimeError("installation runner admission required")
    state = _git_state(_REPOSITORY_ROOT)
    _supervised_installation_admission(_REPOSITORY_ROOT, state)
    if (
        state["head"],
        state["tree"],
    ) != _installation_execution_source or _remote_branch_head(
        _REPOSITORY_ROOT, operator.BRANCH
    ) != state["head"]:
        raise RuntimeError("installation source changed before attempt fence")
    # Exclusive creation is the cross-process one-attempt fence. A failed write
    # or flush leaves the latch consumed; no cleanup or reset is permitted.
    if _supervised_installation_latch_consumed():
        raise FileExistsError("installation attempt consumed")
    SUPERVISED_INSTALLATION_ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
    if _supervised_installation_latch_consumed():
        raise FileExistsError("installation attempt consumed")
    with SUPERVISED_INSTALLATION_ATTEMPT.open("x", encoding="utf-8") as handle:
        handle.write(
            '{"schema":"arch133-ag-installation-attempt/v1","status":"CONSUMED","automatic_retry":"NOT_AUTHORIZED"}\n'
        )
        handle.flush()
        os.fsync(handle.fileno())


def _supervised_installation_execute() -> dict[str, object]:
    from trading_bot.supervised_release import installation_operator as operator

    if (
        not _installation_execution_admitted
        or os.environ.get(operator.AUTH_ENV) != operator.AUTH_VALUE
    ):
        raise RuntimeError("installation authorization interlock rejected")
    return operator._execute_once(_consume_supervised_installation_attempt)


SUPERVISED_INSTALLATION_RECONCILIATION_NAME: Final = (
    "arch133-robinhood-supervised-release-installation-reconciliation"
)
SUPERVISED_INSTALLATION_RECONCILIATION_SOURCE: Final = (
    "src/trading_bot/supervised_release/installation_reconciliation.py"
)
SUPERVISED_INSTALLATION_RECONCILIATION_PIN: Final = (
    "ab51944d25252ccce9a0740ba5d62fc15ebea10c"
)
SUPERVISED_INSTALLATION_RECONCILIATION_TESTS: Final = (
    SUPERVISED_INSTALLATION_OPERATOR_TESTS
)
SUPERVISED_INSTALLATION_RECONCILIATION_RUFF_PATHS: Final = (
    SUPERVISED_INSTALLATION_OPERATOR_RUFF_PATHS
)


def _supervised_installation_reconciliation_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Freeze the read-only 133-AI incident reconciliation boundary."""
    failures = list(_supervised_installation_operator_authority_check(repo_root))
    try:
        from trading_bot.supervised_release import (
            installation_reconciliation as operator,
        )

        spec = _checkpoint_specs()[SUPERVISED_INSTALLATION_RECONCILIATION_NAME]
        if (
            spec.preflight is not _supervised_installation_reconciliation_preflight
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch
            != "feature/robinhood-supervised-release-installation-reconciliation"
            or spec.tests != SUPERVISED_INSTALLATION_RECONCILIATION_TESTS
            or spec.ruff_paths != SUPERVISED_INSTALLATION_RECONCILIATION_RUFF_PATHS
            or spec.authority_check
            is not _supervised_installation_reconciliation_authority_check
            or ACTIVE_CI_CHECKPOINTS[0] != SUPERVISED_INSTALLATION_OPERATOR_NAME
            or SUPERVISED_INSTALLATION_RECONCILIATION_NAME in ACTIVE_CI_CHECKPOINTS
        ):
            failures.append("installation reconciliation registration drift")

        path = repo_root / SUPERVISED_INSTALLATION_RECONCILIATION_SOURCE
        if _git_blob_sha1(path) != SUPERVISED_INSTALLATION_RECONCILIATION_PIN:
            failures.append("installation reconciliation reviewed source drift")

        allowed = {
            "__future__",
            "json",
            "stat",
            "dataclasses",
            "pathlib",
            "typing",
            "trading_bot.supervised_release.installation_operator",
            "trading_bot.arch133_acl.administrator",
            "trading_bot.supervised_release.binding",
            "trading_bot.supervised_release.bundle",
            "trading_bot.supervised_release.installation_contract",
            "trading_bot.supervised_release.native_read",
            "trading_bot.supervised_release.observer",
        }
        forbidden = {
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
            "delete",
            "repair",
            "cleanup",
            "retry",
            "activate",
            "rebind",
            "enable",
            "start",
            "run",
            "Popen",
            "provider",
            "credential",
            "submit",
            "launch",
            "wake",
            "install_release",
            "create_directory",
            "write_file",
            "seal_staging",
            "publish",
            "mkdir",
            "unlink",
            "write_text",
            "write_bytes",
            "rename",
            "replace",
            "rmtree",
            "remove",
            "chmod",
        }
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name not in allowed for alias in node.names
            ):
                failures.append("installation reconciliation import boundary drift")
            if isinstance(node, ast.ImportFrom) and (
                node.module not in allowed or node.level
            ):
                failures.append("installation reconciliation import boundary drift")
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", getattr(node.func, "id", ""))
                in forbidden
            ):
                failures.append("installation reconciliation capability boundary drift")

        if (
            operator.WORKTREE
            != Path(
                r"F:\AI\worktrees\ai-trading-bot-supervised-release-installation-reconciliation"
            )
            or operator.BRANCH
            != "feature/robinhood-supervised-release-installation-reconciliation"
            or operator.ORIGIN != "https://github.com/callmedraken/ai-trading-bot.git"
            or operator.FAILED_AG_HEAD != "513b60029f459ad6ecb4938f8fea2d54209a29d1"
            or operator.FAILED_AG_TREE != "14e8d161ac95e57982c576ebd19681bb204b22fd"
            or operator.EXPECTED_RELEASE_ID
            != "release-03c42597246752319956ab96e01ed61c"
        ):
            failures.append("installation reconciliation fixed incident drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("installation reconciliation source unavailable")
    return tuple(failures)


def _supervised_installation_reconciliation_admission(
    repo_root: Path, state: Mapping[str, object]
) -> None:
    from trading_bot.supervised_release import installation_reconciliation as operator

    if (
        repo_root.resolve() != operator.WORKTREE.resolve()
        or _REPOSITORY_ROOT.resolve() != operator.WORKTREE.resolve()
        or state["branch"] != operator.BRANCH
        or state["porcelain"]
        or _git_output(repo_root, "remote", "get-url", "origin") != operator.ORIGIN
        or _git_output(repo_root, "merge-base", operator.FAILED_AG_HEAD, "HEAD")
        != operator.FAILED_AG_HEAD
        or _supervised_installation_reconciliation_authority_check(repo_root)
    ):
        raise RuntimeError("installation reconciliation source authority rejected")


def _supervised_installation_reconciliation_preflight() -> dict[str, object]:
    from trading_bot.supervised_release import installation_reconciliation as operator

    state = _git_state(_REPOSITORY_ROOT)
    _supervised_installation_reconciliation_admission(_REPOSITORY_ROOT, state)
    if _remote_branch_head(_REPOSITORY_ROOT, operator.BRANCH) != state["head"]:
        raise RuntimeError("installation reconciliation live remote authority rejected")
    return operator._preflight()


SUPERVISED_PUBLICATION_RECOVERY_NAME: Final = (
    "arch133-robinhood-supervised-release-publication-recovery"
)
SUPERVISED_PUBLICATION_RECOVERY_TESTS: Final = (
    *COMMON_TESTS,
    "tests/review_paper/test_supervised_release_publication_recovery.py",
    "tests/review_paper/test_supervised_release_installation_reconciliation.py",
    "tests/review_paper/test_supervised_release_installation_operator.py",
)
SUPERVISED_PUBLICATION_RECOVERY_RUFF_PATHS: Final = (
    "tests/runtime/checkpoint_runner/helpers.py",
    "tests/runtime/checkpoint_runner/test_arch131.py",
    "scripts/checkpoint_runner.py",
    "src/trading_bot/supervised_release/publication_recovery.py",
    "src/trading_bot/supervised_release/native_publication.py",
    "src/trading_bot/supervised_release/installation_reconciliation.py",
    *SUPERVISED_PUBLICATION_RECOVERY_TESTS,
)
SUPERVISED_PUBLICATION_RECOVERY_PINS: Final = {
    "src/trading_bot/supervised_release/publication_recovery.py": (
        "2432d7626ad8b263cb96cda0a858ca7fe0f7d579"
    ),
    "src/trading_bot/supervised_release/native_publication.py": (
        "4f9458d9d1d473d9df36ce94ca296bc8e0299acc"
    ),
}
SUPERVISED_PUBLICATION_RUNNER_PINS: Final = {
    "_supervised_publication_recovery_authority_check": (
        "0a2edef62a5432341f769b7a9fd77e965582cdf79fa105a5b98bf5849deb653b"
    ),
    "_supervised_publication_admission": (
        "914ca755f622d42784990d060816b7956955fad7a435c0a6b3091b357a967d11"
    ),
    "_supervised_publication_live_source": (
        "836bbac33df7d46208cca4d305b39be9873b090297810c642624e9c39444f54d"
    ),
    "_supervised_publication_preflight": (
        "c78dc33a422ef7897941f9f00ca2f3da2aa5926c2bc35338e656b96d0a05567e"
    ),
    "_supervised_publication_execute": (
        "24c45ba0ccfaadc7bcb2c784b097306e7b8c89bb9469ce0ae1dc90802bada425"
    ),
    "execute_checkpoint": (
        "35164fc0985154d41a9f35f7b6b144df6ce86658941a083e7f5705fcee9366ed"
    ),
    "preflight_checkpoint": (
        "a5e63c447cb53e2998b4234dc0ecb2f81c2954b7677bc78d8414f6d278b8b15f"
    ),
    "_checkpoint_specs": (
        "34f185a02ffa550fc497bca5d3d2a36daefbe997f1c0b0cdf511c99d40898b20"
    ),
}
_publication_execution_source: tuple[str, str] | None = None


def _supervised_publication_recovery_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    failures = list(_supervised_installation_reconciliation_authority_check(repo_root))
    if set(SUPERVISED_PUBLICATION_RECOVERY_PINS) != {
        "src/trading_bot/supervised_release/publication_recovery.py",
        "src/trading_bot/supervised_release/native_publication.py",
    } or set(SUPERVISED_PUBLICATION_RUNNER_PINS) != {
        "_supervised_publication_recovery_authority_check",
        "_supervised_publication_admission",
        "_supervised_publication_live_source",
        "_supervised_publication_preflight",
        "_supervised_publication_execute",
        "execute_checkpoint",
        "preflight_checkpoint",
        "_checkpoint_specs",
    }:
        failures.append("publication recovery source-pin inventory drift")
    try:
        spec = _checkpoint_specs()[SUPERVISED_PUBLICATION_RECOVERY_NAME]
        if (
            spec.preflight is not _supervised_publication_preflight
            or spec.execute is not _supervised_publication_execute
            or spec.authority_check
            is not _supervised_publication_recovery_authority_check
            or spec.tests != SUPERVISED_PUBLICATION_RECOVERY_TESTS
            or spec.ruff_paths != SUPERVISED_PUBLICATION_RECOVERY_RUFF_PATHS
            or spec.remote_branch
            != "feature/robinhood-supervised-release-publication-recovery"
            or spec.remote_head_env is not None
            or ACTIVE_CI_CHECKPOINTS.count(SUPERVISED_PUBLICATION_RECOVERY_NAME) != 1
        ):
            failures.append("publication recovery registration drift")
        allowed = {
            "__future__",
            "hashlib",
            "json",
            "os",
            "stat",
            "ctypes",
            "collections.abc",
            "dataclasses",
            "pathlib",
            "typing",
            "trading_bot.supervised_release",
            "trading_bot.supervised_release.binding",
            "trading_bot.supervised_release.bundle",
            "trading_bot.supervised_release.installation_contract",
            "trading_bot.supervised_release.model",
            "trading_bot.supervised_release.native_read",
            "trading_bot.supervised_release.native_publication",
            "trading_bot.supervised_release.observer",
        }
        forbidden = {
            "exec",
            "eval",
            "compile",
            "__import__",
            "reload",
            "delete",
            "repair",
            "cleanup",
            "retry",
            "activate",
            "rebind",
            "enable",
            "start",
            "run",
            "Popen",
            "provider",
            "credential",
            "submit",
            "launch",
            "wake",
            "install_release",
            "create_directory",
            "write_file",
            "seal_staging",
            "mkdir",
            "unlink",
            "write_text",
            "write_bytes",
            "rename",
            "replace",
            "rmtree",
            "remove",
            "chmod",
            "WindowsInstaller",
            "WindowsWriteSession",
        }
        for relative, pin in SUPERVISED_PUBLICATION_RECOVERY_PINS.items():
            path = repo_root / relative
            if _git_blob_sha1(path) != pin:
                failures.append("publication recovery source drift")
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                    alias.name not in allowed for alias in node.names
                ):
                    failures.append("publication recovery import drift")
                if isinstance(node, ast.ImportFrom) and (
                    node.module not in allowed
                    or node.level
                    or (
                        node.module == "trading_bot.supervised_release"
                        and any(
                            alias.name != "installation_reconciliation"
                            for alias in node.names
                        )
                    )
                ):
                    failures.append("publication recovery import drift")
                if (
                    isinstance(node, ast.Call)
                    and getattr(node.func, "attr", getattr(node.func, "id", ""))
                    in forbidden
                ):
                    failures.append("publication recovery forbidden capability")
        functions = _top_level_functions(
            ast.parse(
                (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
            )
        )
        for name, pin in SUPERVISED_PUBLICATION_RUNNER_PINS.items():
            if (
                hashlib.sha256(
                    ast.dump(functions[name], include_attributes=False).encode()
                ).hexdigest()
                != pin
            ):
                failures.append("publication recovery runner authority drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("publication recovery source unavailable")
    return tuple(failures)


def _supervised_publication_admission(
    repo_root: Path, state: Mapping[str, object]
) -> None:
    from trading_bot.supervised_release import publication_recovery as operator

    if (
        repo_root.resolve() != operator.WORKTREE.resolve()
        or _REPOSITORY_ROOT.resolve() != operator.WORKTREE.resolve()
        or state["branch"] != operator.BRANCH
        or state["porcelain"]
        or _git_output(repo_root, "remote", "get-url", "origin") != operator.ORIGIN
        or _git_output(repo_root, "merge-base", operator.BASE_HEAD, "HEAD")
        != operator.BASE_HEAD
        or _supervised_publication_recovery_authority_check(repo_root)
    ):
        raise RuntimeError("publication recovery source authority rejected")


def _supervised_publication_live_source() -> tuple[str, str]:
    from trading_bot.supervised_release import publication_recovery as operator

    state = _git_state(_REPOSITORY_ROOT)
    _supervised_publication_admission(_REPOSITORY_ROOT, state)
    if _remote_branch_head(_REPOSITORY_ROOT, operator.BRANCH) != state["head"]:
        raise RuntimeError("publication recovery live remote rejected")
    return str(state["head"]), str(state["tree"])


def _supervised_publication_preflight() -> dict[str, object]:
    from trading_bot.supervised_release import publication_recovery as operator

    expected = _supervised_publication_live_source()

    def admit_source() -> None:
        if _supervised_publication_live_source() != expected:
            raise RuntimeError("publication recovery source drift")

    return operator.preflight(admit_source)


def _supervised_publication_execute() -> dict[str, object]:
    from trading_bot.supervised_release import publication_recovery as operator

    if _publication_execution_source is None:
        raise RuntimeError("publication recovery runner interlock rejected")

    def admit_source() -> None:
        if _supervised_publication_live_source() != _publication_execution_source:
            raise RuntimeError("publication recovery source drift")

    return operator.execute_once(admit_source)


ARCH134_PRODUCTION_STRATEGY_NAME: Final = "arch134-production-strategy-contract"
ARCH134_PRODUCTION_STRATEGY_SOURCE: Final = "src/trading_bot/strategies/production.py"
ARCH134_PRODUCTION_STRATEGY_SOURCE_PIN: Final = (
    "243deb4986f7a5c6d37f1d7336b6ca3d400ded03"
)
ARCH134_PRODUCTION_STRATEGY_TESTS: Final = (
    *COMMON_TESTS,
    "tests/strategies/test_production_strategy_contract.py",
    "tests/scripts/certification_runner/test_profiles.py",
)
ARCH134_PRODUCTION_STRATEGY_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    ARCH134_PRODUCTION_STRATEGY_SOURCE,
    "tests/strategies/test_production_strategy_contract.py",
    "tests/scripts/certification_runner/test_profiles.py",
)


def _arch134_production_strategy_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Freeze the inert session-scoped production strategy selection boundary."""
    failures: list[str] = []
    try:
        path = repo_root / ARCH134_PRODUCTION_STRATEGY_SOURCE
        if _git_blob_sha1(path) != ARCH134_PRODUCTION_STRATEGY_SOURCE_PIN:
            failures.append("134-A production strategy source drift")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        allowed = {
            "__future__",
            "json",
            "re",
            "dataclasses",
            "datetime",
            "decimal",
            "uuid",
            "trading_bot.domain",
            "trading_bot.strategies.moving_average",
        }
        if not imported <= allowed:
            failures.append(
                "134-A production strategy import surface expanded: "
                + repr(sorted(imported - allowed))
            )
        names = _qualified_names(tree)
        forbidden = {
            "open",
            "eval",
            "exec",
            "__import__",
            "time.sleep",
            "datetime.now",
            "subprocess.run",
            "subprocess.Popen",
            "sqlite3.connect",
            "os.environ",
        }
        if names & forbidden:
            failures.append(
                "134-A production strategy effect surface expanded: "
                + repr(sorted(names & forbidden))
            )

        runner_tree = ast.parse(
            (repo_root / "scripts/checkpoint_runner.py").read_text(encoding="utf-8")
        )
        assignments = [
            node.value
            for node in runner_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ACTIVE_CI_CHECKPOINTS"
        ]
        if (
            len(assignments) != 1
            or tuple(ast.literal_eval(assignments[0])) != ACTIVE_CI_CHECKPOINTS
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_PRODUCTION_STRATEGY_NAME) != 1
            or ACTIVE_CI_CHECKPOINTS.index(ARCH134_PRODUCTION_STRATEGY_NAME) + 1
            != ACTIVE_CI_CHECKPOINTS.index(ARCH134_PRODUCTION_STRATEGY_DECISION_NAME)
        ):
            failures.append("134-A active checkpoint inventory drift")

        spec = _checkpoint_specs()[ARCH134_PRODUCTION_STRATEGY_NAME]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-production-strategy-contract"
            or spec.authority_check is not _arch134_production_strategy_authority_check
            or spec.tests != ARCH134_PRODUCTION_STRATEGY_TESTS
            or spec.ruff_paths != ARCH134_PRODUCTION_STRATEGY_RUFF_PATHS
        ):
            failures.append("134-A source-only registration drift")

        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("134-A workflow route/topology drift")
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError):
        failures.append("134-A production strategy boundary unavailable")
    return tuple(failures)


ARCH134_PRODUCTION_STRATEGY_DECISION_NAME: Final = (
    "arch134-production-strategy-decision"
)
ARCH134_PRODUCTION_STRATEGY_DECISION_SOURCE: Final = (
    "src/trading_bot/strategies/production_decision.py"
)
ARCH134_PRODUCTION_STRATEGY_DECISION_SOURCE_PIN: Final = (
    "3bbd352495cd2b50b9e2557089a0b1b70a0dfce8"
)
ARCH134_PRODUCTION_STRATEGY_DECISION_TESTS: Final = (
    *COMMON_TESTS,
    "tests/strategies/test_production_strategy_contract.py",
    "tests/strategies/test_production_strategy_decision.py",
    "tests/scripts/certification_runner/test_profiles.py",
)
ARCH134_PRODUCTION_STRATEGY_DECISION_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    ARCH134_PRODUCTION_STRATEGY_SOURCE,
    ARCH134_PRODUCTION_STRATEGY_DECISION_SOURCE,
    "tests/strategies/test_production_strategy_contract.py",
    "tests/strategies/test_production_strategy_decision.py",
    "tests/scripts/certification_runner/test_profiles.py",
)


def _arch134_production_strategy_decision_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Freeze the pure Architecture-94 -> production strategy decision bridge."""
    failures = list(_arch134_production_strategy_authority_check(repo_root))
    try:
        path = repo_root / ARCH134_PRODUCTION_STRATEGY_DECISION_SOURCE
        if _git_blob_sha1(path) != ARCH134_PRODUCTION_STRATEGY_DECISION_SOURCE_PIN:
            failures.append("134-B production decision source drift")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        allowed = {
            "__future__",
            "dataclasses",
            "enum",
            "typing",
            "trading_bot.strategies.daily_decision",
            "trading_bot.strategies.history_seed",
            "trading_bot.domain",
            "trading_bot.market_data",
            "trading_bot.runtime.manual_paper_strategy_plan",
            "trading_bot.runtime.strategy_history_seed",
            "trading_bot.strategies.production",
        }
        if not imported <= allowed:
            failures.append(
                "134-B production decision import surface expanded: "
                + repr(sorted(imported - allowed))
            )
        names = _qualified_names(tree)
        forbidden = {
            "open",
            "eval",
            "exec",
            "__import__",
            "time.sleep",
            "datetime.now",
            "subprocess.run",
            "subprocess.Popen",
            "sqlite3.connect",
            "os.environ",
            "review_equity_order",
            "place_order",
        }
        if names & forbidden:
            failures.append(
                "134-B production decision effect surface expanded: "
                + repr(sorted(names & forbidden))
            )
        spec = _checkpoint_specs()[ARCH134_PRODUCTION_STRATEGY_DECISION_NAME]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-production-strategy-decision"
            or spec.authority_check
            is not _arch134_production_strategy_decision_authority_check
            or spec.tests != ARCH134_PRODUCTION_STRATEGY_DECISION_TESTS
            or spec.ruff_paths != ARCH134_PRODUCTION_STRATEGY_DECISION_RUFF_PATHS
        ):
            failures.append("134-B source-only registration drift")
        a = ACTIVE_CI_CHECKPOINTS.index(ARCH134_PRODUCTION_STRATEGY_NAME)
        if (
            ACTIVE_CI_CHECKPOINTS[a : a + 2]
            != (
                ARCH134_PRODUCTION_STRATEGY_NAME,
                ARCH134_PRODUCTION_STRATEGY_DECISION_NAME,
            )
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_PRODUCTION_STRATEGY_DECISION_NAME)
            != 1
        ):
            failures.append("134-B checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("134-B workflow route/topology drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("134-B production decision boundary unavailable")
    return tuple(failures)


ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME: Final = (
    "arch134-production-strategy-live-paper"
)
ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_SOURCE: Final = (
    "src/trading_bot/review_paper/production_strategy_cycle.py"
)
ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_SOURCE_PIN: Final = (
    "3636889acaddf0de0a27e4dc4de0687839c59ee8"
)
ARCH134_PRODUCTION_STRATEGY_PREPARE_OPERATOR_SOURCE: Final = (
    "src/trading_bot/production_strategy_prepare_operator.py"
)
ARCH134_PRODUCTION_STRATEGY_PREPARE_OPERATOR_PIN: Final = (
    "6e13a8f1f45acd458dc0002d5cf338460b3b1d5b"
)
ARCH134_CURRENT_DECISION_SOURCE_PINS: Final = {
    "src/trading_bot/review_paper/production_strategy_decision.py": (
        "3b2d0c6301d35c4800e05e5b4309b2f6d2a0d247"
    ),
    "src/trading_bot/review_paper/strategy_prior.py": (
        "d358aad1cd11f4e5f8c820f08c5a7619f7960df0"
    ),
    "src/trading_bot/strategies/daily_decision.py": (
        "8df232b80047d913d43814e193d7a2788fc27116"
    ),
    "src/trading_bot/strategies/history_seed.py": (
        "b20e41206c3d6d2e8eca6cbbd0dfef2e701b3177"
    ),
    "src/trading_bot/runtime/manual_paper_strategy_plan.py": (
        "9692d39ece0d15d3da6ca83dd8a5f4b994510b12"
    ),
    "src/trading_bot/runtime/strategy_history_seed.py": (
        "6cc0670b169ed9afa430a8de87f36f2dd79fc695"
    ),
}


def _arch134_current_decision_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Pin the shared pure core and reject new current-product effect capabilities."""
    failures: list[str] = []
    allowed_imports = {
        "__future__",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "hashlib",
        "json",
        "re",
        "types",
        "typing",
        "uuid",
        "zoneinfo",
        "trading_bot.backtesting",
        "trading_bot.domain",
        "trading_bot.ledger",
        "trading_bot.market_calendar",
        "trading_bot.market_data",
        "trading_bot.market_data.daily_snapshot_identity",
        "trading_bot.review_paper.store",
        "trading_bot.review_paper.strategy_prior",
        "trading_bot.strategies",
        "trading_bot.strategies.daily_decision",
        "trading_bot.strategies.history_seed",
        "trading_bot.strategies.production",
        "trading_bot.strategies.production_decision",
    }
    forbidden = {
        "VerifiedPriorCheckpoint",
        "_VERIFIED_PRIOR_AUTHORITY",
        "record_market_review",
        "ReviewPaperStore",
        "_initialize",
        "review_equity_order",
        "place_order",
        "execute",
        "connect",
        "sleep",
        "now",
        "utcnow",
        "eval",
        "exec",
        "__import__",
        "run",
        "Popen",
        "chmod",
        "write_text",
        "write_bytes",
    }
    try:
        for relative, pin in ARCH134_CURRENT_DECISION_SOURCE_PINS.items():
            path = repo_root / relative
            if _git_blob_sha1(path) != pin:
                failures.append("134-B2 source drift: " + relative)
            # Historical adapters retain separately validated compatibility.
            if relative.startswith("src/trading_bot/runtime/"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module is not None
            } | {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            if not imported <= allowed_imports:
                failures.append("134-B2 import surface expanded: " + relative)
            calls = {
                getattr(node.func, "attr", getattr(node.func, "id", ""))
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
            }
            if calls & forbidden or "_VERIFIED_PRIOR_AUTHORITY" in _qualified_names(
                tree
            ):
                failures.append("134-B2 authority/effect surface expanded: " + relative)
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError):
        failures.append("134-B2 current decision boundary unavailable")
    return tuple(failures)


ARCH134_MARKET_HISTORY_SOURCE_PINS: Final = {
    "src/trading_bot/robinhood_mcp/historical.py": (
        "fda1a7fb47139a3d7e60baf76bf94126326d220f"
    ),
    "src/trading_bot/review_paper/strategy_market_history.py": (
        "86d821e38e84ca0146f5808585bb33de1f8a0e4c"
    ),
}


def _arch134_market_history_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Freeze B3 read/materialization authority without granting protected effects."""
    failures = list(_arch131_direct_mcp_authority_check(repo_root))
    failures.extend(_arch131_mcp_schema_authority_check(repo_root))
    allowed_imports = {
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "decimal",
        "hashlib",
        "json",
        "re",
        "uuid",
        "zoneinfo",
        "trading_bot.domain",
        "trading_bot.market_calendar",
        "trading_bot.market_data",
        "trading_bot.market_data.daily_snapshot_identity",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.production_strategy_decision",
        "trading_bot.review_paper.store",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.robinhood_mcp.historical",
        "trading_bot.robinhood_mcp.models",
        "trading_bot.strategies.history_seed",
        "trading_bot.strategies.production",
        "trading_bot.strategies.production_decision",
    }
    forbidden = {
        "get_accounts",
        "_get_accounts",
        "get_equity_quotes",
        "get_equity_orders",
        "review_equity_order",
        "review_market_order",
        "call_tool",
        "_invoke",
        "_request_once",
        "record_market_review",
        "ReviewPaperStore",
        "connect",
        "execute",
        "now",
        "utcnow",
        "sleep",
        "eval",
        "exec",
        "__import__",
        "open",
        "write_text",
        "write_bytes",
        "run",
        "Popen",
        "chmod",
    }
    try:
        for relative, pin in ARCH134_MARKET_HISTORY_SOURCE_PINS.items():
            path = repo_root / relative
            if _git_blob_sha1(path) != pin:
                failures.append("134-B3 source drift: " + relative)
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module is not None
            } | {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            if not imported <= allowed_imports:
                failures.append("134-B3 import surface expanded: " + relative)
            calls = {
                getattr(node.func, "attr", getattr(node.func, "id", ""))
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
            }
            if calls & forbidden:
                failures.append("134-B3 effect surface expanded: " + relative)
            if relative.endswith("strategy_market_history.py"):
                required = {
                    "adapter.equity_daily_history",
                    "parse_equity_historicals_response",
                    "accept_daily_provider_response",
                    "serialize_daily_snapshot",
                    "verify_daily_snapshot",
                    "create_strategy_history_seed",
                    "serialize_strategy_history_seed",
                    "verify_strategy_history_seed",
                    "build_current_production_strategy_decision",
                }
                if not required <= _qualified_names(tree):
                    failures.append(
                        "134-B3 reviewed evidence/decision bindings missing"
                    )
                for name in (
                    "equity_daily_history",
                    "build_current_production_strategy_decision",
                ):
                    count = sum(
                        getattr(node.func, "attr", getattr(node.func, "id", "")) == name
                        for node in ast.walk(tree)
                        if isinstance(node, ast.Call)
                    )
                    if count != 1:
                        failures.append("134-B3 composition call is not exact: " + name)
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError):
        failures.append("134-B3 market-history boundary unavailable")
    return tuple(failures)


ARCH134_HISTORY_QUALIFICATION_SOURCE_PINS: Final = {
    "src/trading_bot/robinhood_history_qualification.py": (
        "a50921d45e69a875afcca054b33b8362aff16d07"
    ),
    "scripts/qualify_robinhood_history.py": "88d3d9c6e282fb3f69e8c39cd146cd2acad15b67",
}


def _arch134_history_qualification_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Source-only B3Q admission; no execute registration or real provider check."""
    failures: list[str] = []
    allowed_imports = {
        "__future__",
        "argparse",
        "collections.abc",
        "contextlib",
        "datetime",
        "decimal",
        "hashlib",
        "json",
        "logging",
        "os",
        "pathlib",
        "subprocess",
        "sys",
        "typing",
        "warnings",
        "zoneinfo",
        "trading_bot.domain",
        "trading_bot.market_calendar",
        "trading_bot.market_data",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.strategy_market_history",
        "trading_bot.robinhood_history_qualification",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.robinhood_mcp.historical",
        "trading_bot.robinhood_mcp.models",
        "trading_bot.robinhood_mcp.sdk_transport",
        "trading_bot.robinhood_mcp.windows_oauth",
        "trading_bot.robinhood_paper_operator",
        "trading_bot.strategies",
        "trading_bot.strategies.production",
    }
    forbidden_calls = {
        "get_accounts",
        "_get_accounts",
        "get_equity_quotes",
        "get_equity_orders",
        "review_equity_order",
        "review_market_order",
        "call_tool",
        "_invoke",
        "_request_once",
        "ReviewPaperStore",
        "record_market_review",
        "connect",
        "execute",
        "Popen",
        "sleep",
        "eval",
        "exec",
        "__import__",
        "prepare_production_strategy_paper_cycle",
        "execute_production_strategy_paper_cycle",
    }
    try:
        for relative, pin in ARCH134_HISTORY_QUALIFICATION_SOURCE_PINS.items():
            path = repo_root / relative
            if _git_blob_sha1(path) != pin:
                failures.append("134-B3Q source drift: " + relative)
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module is not None
            } | {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            if not imported <= allowed_imports:
                failures.append("134-B3Q import surface expanded: " + relative)
            calls = [
                getattr(node.func, "attr", getattr(node.func, "id", ""))
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
            ]
            if set(calls) & forbidden_calls:
                failures.append("134-B3Q effect surface expanded: " + relative)
            if relative.startswith("src/"):
                if (
                    calls.count("get_equity_historicals") != 1
                    or calls.count("equity_daily_history") != 1
                ):
                    failures.append("134-B3Q single-history binding drift")
                if not {
                    "parse_equity_historicals_response",
                    "materialize_production_strategy_history",
                    "RobinhoodDailyHistoryRequest",
                    "RobinhoodReviewReadAdapter",
                    "RobinhoodMcpStreamableHttpTransport",
                    "admit_robinhood_paper_source",
                } <= set(calls):
                    failures.append("134-B3Q accepted boundary binding missing")
    except (OSError, UnicodeError, SyntaxError, TypeError, ValueError):
        failures.append("134-B3Q source boundary unavailable")
    return tuple(failures)


ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_TESTS: Final = (
    "tests/review_paper/test_history_qualification.py",
    "tests/robinhood_mcp/test_historical.py",
    "tests/review_paper/test_strategy_market_history.py",
    "tests/robinhood_mcp/test_adapter.py",
    "tests/robinhood_mcp/test_sdk_transport.py",
    "tests/robinhood_mcp/test_account_resolution.py",
    "tests/test_robinhood_paper_operator.py",
    *COMMON_TESTS,
    "tests/strategies/test_production_strategy_contract.py",
    "tests/strategies/test_production_strategy_decision.py",
    "tests/review_paper/test_production_strategy_cycle.py",
    "tests/review_paper/test_production_strategy_prepare_operator.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/review_paper/test_current_production_strategy_decision.py",
    "tests/runtime/test_manual_paper_strategy_plan.py",
    "tests/runtime/test_strategy_history_seed.py",
)
ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_RUFF_PATHS: Final = (
    *ARCH134_HISTORY_QUALIFICATION_SOURCE_PINS,
    "tests/review_paper/test_history_qualification.py",
    *ARCH134_MARKET_HISTORY_SOURCE_PINS,
    "src/trading_bot/robinhood_mcp/adapter.py",
    "src/trading_bot/robinhood_mcp/sdk_transport.py",
    "tests/robinhood_mcp/test_historical.py",
    "tests/review_paper/test_strategy_market_history.py",
    "tests/robinhood_mcp/test_adapter.py",
    "tests/robinhood_mcp/test_sdk_transport.py",
    "tests/robinhood_mcp/test_account_resolution.py",
    "tests/test_robinhood_paper_operator.py",
    *COMMON_RUFF_PATHS,
    ARCH134_PRODUCTION_STRATEGY_SOURCE,
    ARCH134_PRODUCTION_STRATEGY_DECISION_SOURCE,
    ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_SOURCE,
    ARCH134_PRODUCTION_STRATEGY_PREPARE_OPERATOR_SOURCE,
    *ARCH134_CURRENT_DECISION_SOURCE_PINS,
    "tests/strategies/test_production_strategy_contract.py",
    "tests/strategies/test_production_strategy_decision.py",
    "tests/review_paper/test_production_strategy_cycle.py",
    "tests/review_paper/test_production_strategy_prepare_operator.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/review_paper/test_current_production_strategy_decision.py",
    "tests/runtime/test_manual_paper_strategy_plan.py",
    "tests/runtime/test_strategy_history_seed.py",
)


def _arch134_production_strategy_live_paper_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """Freeze the 134-C composition onto the accepted 131 PREPARE/EXECUTE path."""
    failures = list(_arch134_production_strategy_decision_authority_check(repo_root))
    failures.extend(_arch134_current_decision_authority_check(repo_root))
    failures.extend(_arch134_market_history_authority_check(repo_root))
    failures.extend(_arch134_history_qualification_authority_check(repo_root))
    try:
        path = repo_root / ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_SOURCE
        if _git_blob_sha1(path) != ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_SOURCE_PIN:
            failures.append("134-C production live-paper source drift")
        operator_path = repo_root / ARCH134_PRODUCTION_STRATEGY_PREPARE_OPERATOR_SOURCE
        if (
            _git_blob_sha1(operator_path)
            != ARCH134_PRODUCTION_STRATEGY_PREPARE_OPERATOR_PIN
        ):
            failures.append("134-C production shadow PREPARE operator drift")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        allowed = {
            "__future__",
            "dataclasses",
            "datetime",
            "decimal",
            "enum",
            "pathlib",
            "uuid",
            "trading_bot.execution.models",
            "trading_bot.review_paper.session_admission",
            "trading_bot.review_paper.store",
            "trading_bot.review_paper.supervised_forward_paper",
            "trading_bot.risk.models",
            "trading_bot.robinhood_mcp.adapter",
            "trading_bot.strategies.production_decision",
        }
        if not imported <= allowed:
            failures.append(
                "134-C production live-paper import surface expanded: "
                + repr(sorted(imported - allowed))
            )
        names = _qualified_names(tree)
        forbidden = {
            "run_robinhood_forward_paper_cycle",
            "record_market_review",
            "acquire_review_paper_risk_price_snapshot",
            "review_equity_order",
            "place_equity_order",
            "cancel_equity_order",
            "place_option_order",
            "place_crypto_order",
            "time.sleep",
            "subprocess.run",
            "subprocess.Popen",
            "os.environ",
        }
        if names & forbidden:
            failures.append(
                "134-C bypass/effect surface expanded: "
                + repr(sorted(names & forbidden))
            )

        spec = _checkpoint_specs()[ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != "feature/robinhood-production-strategy-live-paper"
            or spec.authority_check
            is not _arch134_production_strategy_live_paper_authority_check
            or spec.tests != ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_TESTS
            or spec.ruff_paths != ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_RUFF_PATHS
        ):
            failures.append("134-C source-only registration drift")
        if (
            ACTIVE_CI_CHECKPOINTS[-5:-2]
            != (
                ARCH134_PRODUCTION_STRATEGY_NAME,
                ARCH134_PRODUCTION_STRATEGY_DECISION_NAME,
                ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME,
            )
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME)
            != 1
        ):
            failures.append("134-C checkpoint ordering drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("134-C workflow route/topology drift")
    except (
        OSError,
        UnicodeError,
        SyntaxError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ):
        failures.append("134-C production live-paper boundary unavailable")
    return tuple(failures)


ARCH134_ARMED_PAPER_NAME: Final = "arch134-armed-paper-mvp"
ARCH134_ARMED_PAPER_SOURCE_PINS: Final = {
    "src/trading_bot/review_paper/alpaca_strategy_history.py": (
        "945776dcb152a4c4673a3b375d235297a45f2aa4"
    ),
    "src/trading_bot/review_paper/armed_session.py": (
        "5c395cf692dd387b53688ebb25d2a9007a3a535c"
    ),
    "src/trading_bot/review_paper/armed_session_store.py": (
        "94288880c8899ddee7e5d5505c69d6ad093ec559"
    ),
    "src/trading_bot/review_paper/armed_session_host.py": (
        "221bf261c89062fdc766168daca444231d4d4bb4"
    ),
    "scripts/run_production_paper_session.py": (
        "b2c99d36bfc8ee80f04a6e3a0be06e36feee547b"
    ),
    "src/trading_bot/market_data/alpaca_daily_snapshot.py": (
        "82e30b6b486915acadb85c95faf538ee9d828451"
    ),
    "src/trading_bot/market_data/alpaca_http.py": (
        "a45037d821460d5fa0bab937f7085250890225d7"
    ),
}
ARCH134_ARMED_PAPER_TESTS: Final = (
    "tests/review_paper/test_armed_production_paper_session.py",
    "tests/review_paper/test_current_production_strategy_decision.py",
    "tests/review_paper/test_production_strategy_cycle.py",
    "tests/review_paper/test_supervised_forward_paper.py",
    "tests/review_paper/test_risk_price_acquisition.py",
    "tests/market_data/test_alpaca_daily_snapshot.py",
    "tests/market_data/test_alpaca_http.py",
    "tests/review_paper/test_strategy_market_history.py",
    "tests/review_paper/test_history_qualification.py",
    "tests/scripts/certification_runner/test_profiles.py",
    *COMMON_TESTS,
)
ARCH134_ARMED_PAPER_RUFF_PATHS: Final = (
    *ARCH134_ARMED_PAPER_SOURCE_PINS,
    *ARCH134_ARMED_PAPER_TESTS,
    *COMMON_RUFF_PATHS,
)
ARCH134_ARMED_PAPER_IMPORTS: Final = {
    "src/trading_bot/review_paper/alpaca_strategy_history.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "trading_bot.market_calendar",
        "trading_bot.market_data",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.strategies.history_seed",
        "trading_bot.strategies.production",
        "uuid",
        "zoneinfo",
    ),
    "src/trading_bot/review_paper/armed_session.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "decimal",
        "hashlib",
        "pathlib",
        "trading_bot.domain",
        "trading_bot.execution.models",
        "trading_bot.market_data",
        "trading_bot.review_paper.alpaca_strategy_history",
        "trading_bot.review_paper.armed_session_store",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.production_strategy_cycle",
        "trading_bot.review_paper.production_strategy_decision",
        "trading_bot.review_paper.session_admission",
        "trading_bot.review_paper.store",
        "trading_bot.risk.models",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.strategies.production",
        "trading_bot.strategies.production_decision",
        "uuid",
        "zoneinfo",
    ),
    "src/trading_bot/review_paper/armed_session_store.py": (
        "__future__",
        "contextlib",
        "datetime",
        "enum",
        "json",
        "os",
        "pathlib",
        "sqlite3",
        "uuid",
    ),
    "src/trading_bot/review_paper/armed_session_host.py": (
        "__future__",
        "argparse",
        "collections.abc",
        "datetime",
        "decimal",
        "json",
        "pathlib",
        "subprocess",
        "sys",
        "time",
        "trading_bot.domain",
        "trading_bot.market_data",
        "trading_bot.market_data.alpaca_http",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "trading_bot.review_paper.armed_session",
        "trading_bot.review_paper.armed_session_store",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.production_paper_runtime",
        "trading_bot.review_paper.store",
        "trading_bot.risk.models",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.robinhood_mcp.sdk_transport",
        "trading_bot.robinhood_mcp.windows_oauth",
        "trading_bot.robinhood_paper_operator",
        "trading_bot.strategies",
        "trading_bot.strategies.production",
        "zoneinfo",
    ),
    "scripts/run_production_paper_session.py": (
        "pathlib",
        "sys",
        "trading_bot.review_paper.armed_session_host",
    ),
}


# D1R1 is an exact successor overlay; accepted predecessor material stays frozen.
ARCH134_ARMED_PAPER_SUCCESSOR_PIN_OVERRIDES: Final = {
    "src/trading_bot/review_paper/alpaca_strategy_history.py": (
        "ad99796a7b89ac29450047dfad9cb0e87db52cc6"
    ),
    "src/trading_bot/review_paper/armed_session.py": (
        "8133bed61cc8f6924876ce41b05ef9124bfb2701"
    ),
    "src/trading_bot/review_paper/armed_session_host.py": (
        "0fe62babc2dafc67bca6b0c56463dce49439df6d"
    ),
}
ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES: Final = {
    "src/trading_bot/review_paper/alpaca_strategy_history.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "trading_bot.market_calendar",
        "trading_bot.market_data",
        "trading_bot.review_paper.armed_history_failure",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.strategies.history_seed",
        "trading_bot.strategies.production",
        "uuid",
        "zoneinfo",
    ),
    "src/trading_bot/review_paper/armed_session.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "decimal",
        "hashlib",
        "pathlib",
        "trading_bot.domain",
        "trading_bot.execution.models",
        "trading_bot.market_data",
        "trading_bot.review_paper.alpaca_strategy_history",
        "trading_bot.review_paper.armed_history_failure",
        "trading_bot.review_paper.armed_session_store",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.production_strategy_cycle",
        "trading_bot.review_paper.production_strategy_decision",
        "trading_bot.review_paper.session_admission",
        "trading_bot.review_paper.store",
        "trading_bot.risk.models",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.strategies.production",
        "trading_bot.strategies.production_decision",
        "uuid",
        "zoneinfo",
    ),
    "src/trading_bot/review_paper/armed_session_host.py": (
        "__future__",
        "argparse",
        "collections.abc",
        "datetime",
        "decimal",
        "json",
        "pathlib",
        "subprocess",
        "sys",
        "time",
        "trading_bot.domain",
        "trading_bot.market_data",
        "trading_bot.market_data.alpaca_http",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "trading_bot.review_paper.armed_history_failure",
        "trading_bot.review_paper.armed_session",
        "trading_bot.review_paper.armed_session_store",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.production_paper_runtime",
        "trading_bot.review_paper.store",
        "trading_bot.risk.models",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.robinhood_mcp.sdk_transport",
        "trading_bot.robinhood_mcp.windows_oauth",
        "trading_bot.robinhood_paper_operator",
        "trading_bot.strategies",
        "trading_bot.strategies.production",
        "zoneinfo",
    ),
}


ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES: Final = {
    "src/trading_bot/review_paper/armed_session.py": (
        "f96d31447c0c25115d0f629e2cbcd47dc99ebd05"
    ),
    "src/trading_bot/review_paper/armed_session_store.py": (
        "aa57fd196c24856f81af81b3ae9294362a1b01a3"
    ),
    "src/trading_bot/review_paper/armed_session_host.py": (
        "a510ec78b984b4fcc6143176b15f35e367fd6311"
    ),
}
ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES: Final = {
    "src/trading_bot/review_paper/armed_session.py": (
        *ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES[
            "src/trading_bot/review_paper/armed_session.py"
        ],
        "json",
    ),
    "src/trading_bot/review_paper/armed_session_host.py": (
        ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES[
            "src/trading_bot/review_paper/armed_session_host.py"
        ]
    ),
    "src/trading_bot/review_paper/armed_session_store.py": (
        *ARCH134_ARMED_PAPER_IMPORTS[
            "src/trading_bot/review_paper/armed_session_store.py"
        ],
        "hashlib",
        "trading_bot.review_paper.armed_history_failure",
        "trading_bot.strategies.production",
    ),
}


def _arch134_armed_paper_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Exact source/AST closure; D1 gains no protected qualification authority."""
    failures = list(_arch134_production_strategy_live_paper_authority_check(repo_root))
    forbidden_calls = {
        "call_tool",
        "_invoke",
        "equity_daily_history",
        "get_equity_historicals",
        "place_equity_order",
        "cancel_equity_order",
        "place_order",
        "cancel_order",
        "place_options_order",
        "place_crypto_order",
        "register_task",
        "schtasks",
        "evaluate",
        "build_production_strategy_decision",
        "build_manual_paper_strategy_decision",
        "eval",
        "exec",
        "__import__",
        "import_module",
    }
    try:
        reviewed_overrides = {
            "src/trading_bot/review_paper/alpaca_strategy_history.py",
            "src/trading_bot/review_paper/armed_session.py",
            "src/trading_bot/review_paper/armed_session_host.py",
        }
        if (
            set(ARCH134_ARMED_PAPER_SUCCESSOR_PIN_OVERRIDES) != reviewed_overrides
            or set(ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES) != reviewed_overrides
        ):
            failures.append("134-D1 unreviewed successor override")
        recovery_overrides = {
            "src/trading_bot/review_paper/armed_session.py",
            "src/trading_bot/review_paper/armed_session_store.py",
            "src/trading_bot/review_paper/armed_session_host.py",
        }
        if (
            set(ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES) != recovery_overrides
            or set(ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES) != recovery_overrides
        ):
            failures.append("134-D1R2 unreviewed recovery override")
        pins = {
            **ARCH134_ARMED_PAPER_SOURCE_PINS,
            **ARCH134_ARMED_PAPER_SUCCESSOR_PIN_OVERRIDES,
            **ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES,
        }
        imports = {
            **ARCH134_ARMED_PAPER_IMPORTS,
            **ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES,
            **ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES,
        }
        for relative, pin in pins.items():
            path = repo_root / relative
            if _git_blob_sha1(path) != pin:
                failures.append("134-D1 source drift: " + relative)
            if relative not in imports:
                continue  # unchanged reviewed concrete provider/HTTPS pins
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module is not None
            } | {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            if imported != set(imports[relative]):
                failures.append("134-D1 import closure drift: " + relative)
            calls = [
                getattr(node.func, "attr", getattr(node.func, "id", ""))
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
            ]
            if set(calls) & forbidden_calls:
                failures.append("134-D1 forbidden authority call: " + relative)
            if relative.endswith("armed_session.py"):
                for name in (
                    "build_current_production_strategy_decision",
                    "prepare_production_strategy_paper_cycle",
                    "execute_production_strategy_paper_cycle",
                    "acquire_current_production_strategy_history_from_alpaca",
                ):
                    if calls.count(name) != 1:
                        failures.append("134-D1 exact composition drift: " + name)
            if relative.endswith("alpaca_strategy_history.py"):
                for name in (
                    "fetch",
                    "accept_daily_provider_response",
                    "verify_daily_snapshot",
                    "verify_strategy_history_seed",
                ):
                    if calls.count(name) != 1:
                        failures.append("134-D1 exact history drift: " + name)
        spec = _checkpoint_specs()[ARCH134_ARMED_PAPER_NAME]
        if (
            spec.tests != ARCH134_ARMED_PAPER_TESTS
            or spec.ruff_paths != ARCH134_ARMED_PAPER_RUFF_PATHS
            or spec.remote_branch != "feature/robinhood-production-paper-mvp"
            or spec.authority_check is not _arch134_armed_paper_authority_check
            or spec.preflight is not None
            or spec.execute is not None
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_ARMED_PAPER_NAME) != 1
        ):
            failures.append("134-D1 registration authority drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("134-D1 source-gate workflow drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("134-D1 authority unavailable")
    return tuple(failures)


ARCH134_PRODUCTION_PAPER_RUNTIME_NAME: Final = "arch134-production-paper-runtime"
ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS: Final = {
    **ARCH134_ARMED_PAPER_SOURCE_PINS,
    "src/trading_bot/review_paper/alpaca_windows_credentials.py": (
        "2554a8e0d5b86d68db6a277e530005e6dae87745"
    ),
    "src/trading_bot/review_paper/production_paper_runtime.py": (
        "1771a63bca73c7a3bf82f91d7448b70a15043e59"
    ),
    "scripts/qualify_production_paper_runtime.py": (
        "7772ab5495b38d87ac50d2ad54b9633115b3d5de"
    ),
    "src/trading_bot/review_paper/store.py": (
        "c9875c20ec6d6b1fc788dd6649fe419aeae8fed8"
    ),
    "src/trading_bot/arch133_verifier/credentials.py": (
        "a334b1bf1097477b1ff0807a07c81ffc7f7fcffb"
    ),
    "tests/review_paper/test_production_paper_runtime.py": (
        "863f172f271ac87a13d610fce7753b186b699c1d"
    ),
    "tests/review_paper/test_armed_production_paper_session.py": (
        "82cbf0785399afd95e0065160d2a3e43245faaae"
    ),
    "tests/review_paper/test_store.py": ("09dffb1e0d0a1a1881d6a6f85649be6baaaba42a"),
    "tests/scripts/certification_runner/test_profiles.py": (
        "71903964f3bc13039d49451740f16a14470673ac"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "a8470acf3f263ba8b4a9b888ce168b56c95f33a6"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "c99bb51c67ef1d0c475ebb4f58ec869c59a3c253"
    ),
    "src/trading_bot/review_paper/production_strategy_cycle.py": (
        "3636889acaddf0de0a27e4dc4de0687839c59ee8"
    ),
    "src/trading_bot/review_paper/production_strategy_decision.py": (
        "3b2d0c6301d35c4800e05e5b4309b2f6d2a0d247"
    ),
    "src/trading_bot/review_paper/supervised_forward_paper.py": (
        "150926efd7b909a53ea897a23d2e76d37ff8c32d"
    ),
    "src/trading_bot/review_paper/risk_price_acquisition.py": (
        "28d37020f26d26cc58a842eefc4e2bbe5d46fb91"
    ),
    "src/trading_bot/robinhood_paper_operator.py": (
        "ebed3361c1c9d0fbfc63aab3e308c7e54b0e4d2e"
    ),
    "src/trading_bot/robinhood_paper_pipeline.py": (
        "4ab15822bded9c6e76e7badb78b9e7fe0db63b40"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "529911f2dba657bcaa36596203608985168faad2"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "5dbb515c077e000fa56bb0aebc2ec2681a2e1074"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "5a124f1d02d3809a18d31b95ba1e8d52cc11baef"
    ),
}
ARCH134_PRODUCTION_PAPER_RUNTIME_TESTS: Final = (
    "tests/review_paper/test_production_paper_runtime.py",
    "tests/review_paper/test_store.py",
    "tests/review_paper/test_post_publication_verifier.py",
    "tests/strategies/test_production_strategy_contract.py",
    "tests/strategies/test_production_strategy_decision.py",
    *ARCH134_ARMED_PAPER_TESTS,
)
ARCH134_PRODUCTION_PAPER_RUNTIME_RUFF_PATHS: Final = (
    *ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS,
    *ARCH134_PRODUCTION_PAPER_RUNTIME_TESTS,
    *COMMON_RUFF_PATHS,
)
ARCH134_PRODUCTION_PAPER_RUNTIME_IMPORTS: Final = {
    "src/trading_bot/review_paper/alpaca_windows_credentials.py": (
        "__future__",
        "collections.abc",
        "ctypes",
        "os",
        "typing",
    ),
    "src/trading_bot/review_paper/production_paper_runtime.py": (
        "__future__",
        "argparse",
        "contextlib",
        "decimal",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "sqlite3",
        "stat",
        "sys",
        "trading_bot.arch133_verifier.credentials",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "trading_bot.review_paper.armed_session_host",
        "trading_bot.review_paper.armed_session_store",
        "trading_bot.review_paper.store",
    ),
    "scripts/qualify_production_paper_runtime.py": (
        "pathlib",
        "sys",
        "trading_bot.review_paper.production_paper_runtime",
    ),
    "src/trading_bot/review_paper/store.py": (
        "__future__",
        "collections.abc",
        "datetime",
        "decimal",
        "pathlib",
        "sqlite3",
        "trading_bot.domain",
        "trading_bot.domain._validation",
        "trading_bot.ledger",
        "trading_bot.review_paper.models",
        "trading_bot.risk",
        "uuid",
    ),
    "src/trading_bot/arch133_verifier/credentials.py": (
        "__future__",
        "ctypes",
        "dataclasses",
        "json",
        "os",
        "urllib.parse",
    ),
}


# Current D1R1 runtime authority: exact changed source/tests plus one diagnostic.
ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_SOURCE_PINS: Final = {
    **ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS,
    "src/trading_bot/review_paper/alpaca_strategy_history.py": (
        "ad99796a7b89ac29450047dfad9cb0e87db52cc6"
    ),
    "src/trading_bot/review_paper/armed_session.py": (
        "8133bed61cc8f6924876ce41b05ef9124bfb2701"
    ),
    "src/trading_bot/review_paper/armed_session_host.py": (
        "0fe62babc2dafc67bca6b0c56463dce49439df6d"
    ),
    "src/trading_bot/review_paper/armed_history_failure.py": (
        "07265a0a2259290e6629ee9a901822c4ee49d5a2"
    ),
    "tests/review_paper/test_armed_production_paper_session.py": (
        "d997fd8520be5e29a38877677b18a4c7c5b8dcd1"
    ),
    "tests/review_paper/test_production_paper_runtime.py": (
        "21811c26f3a5be014e5d5966da2830c0670a4076"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "bddff88dbefbe4907437080a3d6261803b30ff44"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "93da0226ad50d95602e0b3297e1f9f8acc44e3d7"
    ),
}
ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_IMPORTS: Final = {
    **ARCH134_PRODUCTION_PAPER_RUNTIME_IMPORTS,
    "src/trading_bot/review_paper/alpaca_strategy_history.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "trading_bot.market_calendar",
        "trading_bot.market_data",
        "trading_bot.review_paper.armed_history_failure",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.strategies.history_seed",
        "trading_bot.strategies.production",
        "uuid",
        "zoneinfo",
    ),
    "src/trading_bot/review_paper/armed_session.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "decimal",
        "hashlib",
        "pathlib",
        "trading_bot.domain",
        "trading_bot.execution.models",
        "trading_bot.market_data",
        "trading_bot.review_paper.alpaca_strategy_history",
        "trading_bot.review_paper.armed_history_failure",
        "trading_bot.review_paper.armed_session_store",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.production_strategy_cycle",
        "trading_bot.review_paper.production_strategy_decision",
        "trading_bot.review_paper.session_admission",
        "trading_bot.review_paper.store",
        "trading_bot.risk.models",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.strategies.production",
        "trading_bot.strategies.production_decision",
        "uuid",
        "zoneinfo",
    ),
    "src/trading_bot/review_paper/armed_session_host.py": (
        "__future__",
        "argparse",
        "collections.abc",
        "datetime",
        "decimal",
        "json",
        "pathlib",
        "subprocess",
        "sys",
        "time",
        "trading_bot.domain",
        "trading_bot.market_data",
        "trading_bot.market_data.alpaca_http",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "trading_bot.review_paper.armed_history_failure",
        "trading_bot.review_paper.armed_session",
        "trading_bot.review_paper.armed_session_store",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.production_paper_runtime",
        "trading_bot.review_paper.store",
        "trading_bot.risk.models",
        "trading_bot.robinhood_mcp.adapter",
        "trading_bot.robinhood_mcp.sdk_transport",
        "trading_bot.robinhood_mcp.windows_oauth",
        "trading_bot.robinhood_paper_operator",
        "trading_bot.strategies",
        "trading_bot.strategies.production",
        "zoneinfo",
    ),
    "src/trading_bot/review_paper/armed_history_failure.py": (
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "json",
        "os",
        "pathlib",
        "trading_bot.market_data",
        "uuid",
    ),
}
ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_TESTS: Final = (
    *ARCH134_PRODUCTION_PAPER_RUNTIME_TESTS,
)
ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS: Final = {
    **ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_SOURCE_PINS,
    **ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES,
    "tests/review_paper/test_armed_production_paper_session.py": (
        "e4f799b2a002311ed448c59406765fd675707b36"
    ),
    "tests/review_paper/test_production_paper_runtime.py": (
        "a48f763db9c6b7a8fd64d787a16c378cc5cbc6c4"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "c904cdb38e09f004c6479bdf43bdfd64cf5366e1"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "1ccfe438470886b4d1db9d1dded254bbe49e577e"
    ),
}
ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS: Final = {
    **ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_IMPORTS,
    **ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES,
}
ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_RUFF_PATHS: Final = (
    *ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS,
    *ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_TESTS,
    *COMMON_RUFF_PATHS,
)


def _arch134_production_paper_runtime_authority_check(
    repo_root: Path,
) -> tuple[str, ...]:
    """D1Q exact fixed-source closure; qualification remains separately protected."""
    failures = list(_arch134_armed_paper_authority_check(repo_root))
    forbidden = {
        "SetNamedSecurityInfoW",
        "SetFileSecurityW",
        "SetSecurityInfo",
        "chmod",
        "chown",
        "icacls",
        "takeown",
        "CredWriteW",
        "CredDeleteW",
        "getenv",
        "getenvb",
        "call_tool",
        "_invoke",
        "get_equity_historicals",
        "equity_daily_history",
        "place_equity_order",
        "cancel_equity_order",
        "place_options_order",
        "place_crypto_order",
        "register_task",
        "schtasks",
        "eval",
        "exec",
        "__import__",
        "import_module",
    }
    try:
        reviewed_changes = {
            "src/trading_bot/review_paper/alpaca_strategy_history.py",
            "src/trading_bot/review_paper/armed_session.py",
            "src/trading_bot/review_paper/armed_session_host.py",
            "src/trading_bot/review_paper/armed_session_store.py",
            "tests/review_paper/test_armed_production_paper_session.py",
            "tests/review_paper/test_production_paper_runtime.py",
            "tests/runtime/checkpoint_runner/test_ci.py",
            "tests/runtime/checkpoint_runner/test_core.py",
        }
        diagnostic = "src/trading_bot/review_paper/armed_history_failure.py"
        pins = ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS
        if set(pins) != set(ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS) | {
            diagnostic
        } or any(
            pins.get(relative) != pin
            for relative, pin in ARCH134_PRODUCTION_PAPER_RUNTIME_SOURCE_PINS.items()
            if relative not in reviewed_changes
        ):
            failures.append("134-D1Q unreviewed successor source override")
        imports = ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS
        expected_imports = (
            set(ARCH134_PRODUCTION_PAPER_RUNTIME_IMPORTS)
            | set(ARCH134_ARMED_PAPER_SUCCESSOR_IMPORT_OVERRIDES)
            | set(ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES)
            | {diagnostic}
        )
        if set(imports) != expected_imports or any(
            imports.get(relative) != value
            for relative, value in ARCH134_PRODUCTION_PAPER_RUNTIME_IMPORTS.items()
            if relative not in ARCH134_ARMED_PAPER_RECOVERY_IMPORT_OVERRIDES
        ):
            failures.append("134-D1Q unreviewed successor import override")
        for (
            relative,
            pin,
        ) in ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_SOURCE_PINS.items():
            path = repo_root / relative
            expected_pin = ARCH134_AUTH_CORRECTION_TEST_PINS.get(
                relative, ARCH134_AUTH_TEST_PIN_OVERRIDES.get(relative, pin)
            )
            expected_pin = ARCH134_D1R4_SOURCE_PINS.get(relative, expected_pin)
            expected_pin = ARCH134_D1R4R_SOURCE_PINS.get(relative, expected_pin)
            expected_pin = ARCH134_HIST2_TEST_PIN_OVERRIDES.get(relative, expected_pin)
            expected_pin = _arch134_d1r5_test_pin(relative, expected_pin)
            expected_pin = _arch138_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139a_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b1_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b2_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140a18_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _canonical_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch134_d1r7_test_pin(relative, expected_pin)
            expected_pin = _arch142_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch142b_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch143_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch132_r3i_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _arch144_current_inventory_test_pin(relative, expected_pin)
            if _git_blob_sha1(path) != expected_pin:
                failures.append("134-D1Q source drift: " + relative)
            if relative not in ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            } | {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            if imports != set(
                ARCH134_PRODUCTION_PAPER_RUNTIME_RECOVERY_IMPORTS[relative]
            ):
                failures.append("134-D1Q import closure drift: " + relative)
            names = {
                node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
            } | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            if names & (forbidden | {"environ", "environb"}):
                failures.append("134-D1Q forbidden authority: " + relative)
        spec = _checkpoint_specs()[ARCH134_PRODUCTION_PAPER_RUNTIME_NAME]
        if (
            spec.tests != ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_TESTS
            or spec.ruff_paths != ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_RUFF_PATHS
            or spec.remote_branch
            != "feature/robinhood-production-paper-history-recovery"
            or spec.authority_check
            is not _arch134_production_paper_runtime_authority_check
            or spec.preflight is not None
            or spec.execute is not None
            or ACTIVE_CI_CHECKPOINTS[-2:]
            != (ARCH134_PRODUCTION_PAPER_RUNTIME_NAME, ARCH134_RUNTIME_ACL_NAME)
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_PRODUCTION_PAPER_RUNTIME_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_PRODUCTION_PAPER_RUNTIME_NAME)
            != "robinhood"
        ):
            failures.append("134-D1Q registration authority drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("134-D1Q authority unavailable")
    return tuple(failures)


ARCH134_AUTH_NAME: Final = "arch134-alpaca-authentication-qualification"
ARCH134_AUTH_BRANCH: Final = (
    "feature/robinhood-production-paper-alpaca-auth-qualification"
)
ARCH134_AUTH_SOURCE_PINS: Final = {
    "src/trading_bot/review_paper/alpaca_authentication_qualification.py": (
        "171101537f96271988c35683ed22ba85a1b37661"
    ),
    "src/trading_bot/review_paper/alpaca_authentication_host.py": (
        "f7d23b2edc2292f980970ca4deea8ce6d942925d"
    ),
    "tests/review_paper/test_alpaca_authentication_qualification.py": (
        "ac40ce84d910bbe93986490acaecac66c43f7dfb"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "4793e8935fa5af1c60e1bf0dfdc186956c330058"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "d3c4965c51d6ca79070af5e7319768af5d75122b"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "d495b90c6d47da6959fa539cd1f3504a4989e631"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "a44e5181f33c2d52c11726477b3240da94c3ff6e"
    ),
}
ARCH134_AUTH_TEST_PIN_OVERRIDES: Final = {
    relative: ARCH134_AUTH_SOURCE_PINS[relative]
    for relative in (
        "tests/runtime/checkpoint_runner/test_ci.py",
        "tests/runtime/checkpoint_runner/test_core.py",
        "tests/runtime/checkpoint_runner/helpers.py",
        "tests/scripts/certification_runner/test_profiles.py",
    )
}
# D1R3 correction: only the directly changed retained concurrency test evolves.
# Accepted D1/R1/R2 and initial D1R3 dictionaries remain frozen.
ARCH134_AUTH_CORRECTION_TEST_PINS: Final = {
    "tests/review_paper/test_armed_production_paper_session.py": (
        "4e06e2d922f6ca784681cffe8ccda6b4806bc14f"
    ),
}
ARCH134_AUTH_IMPORTS: Final = {
    "src/trading_bot/review_paper/alpaca_authentication_qualification.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "enum",
        "json",
        "trading_bot.domain",
        "trading_bot.market_calendar",
        "trading_bot.market_data.alpaca_daily_snapshot",
        "trading_bot.market_data.alpaca_http",
        "trading_bot.market_data.daily_snapshot_models",
        "trading_bot.market_data.daily_snapshot_provider",
        "trading_bot.market_data.exceptions",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "uuid",
    ),
    "src/trading_bot/review_paper/alpaca_authentication_host.py": (
        "__future__",
        "argparse",
        "os",
        "pathlib",
        "stat",
        "subprocess",
        "sys",
        "trading_bot.market_data.alpaca_http",
        "trading_bot.review_paper.alpaca_authentication_qualification",
    ),
}
# D1R4 current overlay only. All accepted D1/D1Q/R1/R2/R3 pins above are historical.
ARCH134_D1R4_PATHS: Final = (
    "src/trading_bot/review_paper/alpaca_windows_credentials.py",
    "src/trading_bot/review_paper/alpaca_authentication_qualification.py",
    "src/trading_bot/review_paper/alpaca_authentication_host.py",
    "src/trading_bot/review_paper/alpaca_credential_generation.py",
    "src/trading_bot/review_paper/alpaca_credential_native.py",
    "src/trading_bot/review_paper/alpaca_credential_host.py",
    "tests/review_paper/test_alpaca_authentication_qualification.py",
    "tests/review_paper/test_alpaca_credential_generation.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/review_paper/test_supervised_deployment_qualification.py",
    "tests/review_paper/test_supervised_runtime_host_admission.py",
    "tests/review_paper/test_supervised_maintenance_rebind.py",
    "tests/review_paper/test_production_strategy_cycle.py",
)
ARCH134_D1R4_SOURCE_PINS: Final = {
    "src/trading_bot/review_paper/alpaca_windows_credentials.py": (
        "e01fd44cd2eec663ac5f3eab78b3a7499b6ada7e"
    ),
    "src/trading_bot/review_paper/alpaca_authentication_qualification.py": (
        "331351635e522e6e05d4d2d82dc1ac25def6341b"
    ),
    "src/trading_bot/review_paper/alpaca_authentication_host.py": (
        "c3377e757372f9a33ddabc5ac15f1b124a49d570"
    ),
    "src/trading_bot/review_paper/alpaca_credential_generation.py": (
        "5dbdd29a2fe64febce8ea22be9294f047e0a4f8d"
    ),
    "src/trading_bot/review_paper/alpaca_credential_native.py": (
        "4c3a6857156275a443eecded5cf7915c71f05724"
    ),
    "src/trading_bot/review_paper/alpaca_credential_host.py": (
        "07d6dec0f73c9313e4a8c76a5eb819d9ea6fe8fb"
    ),
    "tests/review_paper/test_alpaca_authentication_qualification.py": (
        "25f1bfa4e5c6f1e1ff3912b3cd163a86761a9d5f"
    ),
    "tests/review_paper/test_alpaca_credential_generation.py": (
        "c607965ea0d73d66982c3c762e4801d321fdf553"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "1162c2bfa9c548c77227971bcac38726ab0ad075"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "deb80454ffae2c7f579752b2728b2b9551a09a66"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "a8240b76945f2aef0de956eb2bd99cceda71595a"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "74527e1ad3d83bee153f82a628c202c3d6e48f43"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "a5eebc024445f4c4629876aaeb69fd9497be40fc"
    ),
}  # D1R4_GENERATED_PINS
ARCH134_D1R4_IMPORTS: Final = {
    "src/trading_bot/review_paper/alpaca_windows_credentials.py": (
        "__future__",
        "collections.abc",
        "ctypes",
        "os",
        "typing",
    ),
    "src/trading_bot/review_paper/alpaca_authentication_qualification.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "datetime",
        "enum",
        "json",
        "trading_bot.domain",
        "trading_bot.market_calendar",
        "trading_bot.market_data.alpaca_daily_snapshot",
        "trading_bot.market_data.alpaca_http",
        "trading_bot.market_data.daily_snapshot_models",
        "trading_bot.market_data.daily_snapshot_provider",
        "trading_bot.market_data.exceptions",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "uuid",
    ),
    "src/trading_bot/review_paper/alpaca_authentication_host.py": (
        "__future__",
        "argparse",
        "hashlib",
        "os",
        "pathlib",
        "stat",
        "subprocess",
        "sys",
        "trading_bot.market_data.alpaca_http",
        "trading_bot.review_paper.alpaca_authentication_qualification",
        "trading_bot.review_paper.alpaca_credential_generation",
        "trading_bot.review_paper.alpaca_credential_native",
        "trading_bot.review_paper.alpaca_windows_credentials",
    ),
    "src/trading_bot/review_paper/alpaca_credential_generation.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "typing",
    ),
    "src/trading_bot/review_paper/alpaca_credential_native.py": (
        "__future__",
        "ctypes",
        "os",
        "threading",
        "trading_bot.review_paper.alpaca_credential_generation",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "trading_bot.runtime.windows_authority_security",
    ),
    "src/trading_bot/review_paper/alpaca_credential_host.py": (
        "__future__",
        "argparse",
        "getpass",
        "hashlib",
        "pathlib",
        "sys",
        "trading_bot.review_paper.alpaca_authentication_host",
        "trading_bot.review_paper.alpaca_credential_generation",
        "trading_bot.review_paper.alpaca_credential_native",
        "warnings",
    ),
}  # D1R4_GENERATED_IMPORTS

# D1R4R incident recovery successor; ALL predecessor dictionaries stay frozen.
ARCH134_D1R4R_PATHS: Final = (
    "src/trading_bot/review_paper/alpaca_windows_credentials.py",
    "src/trading_bot/review_paper/alpaca_credential_generation.py",
    "src/trading_bot/review_paper/alpaca_credential_host.py",
    "src/trading_bot/review_paper/alpaca_credential_staging_cleanup.py",
    "src/trading_bot/review_paper/alpaca_credential_cleanup_host.py",
    "tests/review_paper/test_alpaca_credential_generation.py",
    "tests/review_paper/test_alpaca_credential_staging_cleanup.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/review_paper/test_supervised_deployment_qualification.py",
    "tests/review_paper/test_supervised_runtime_host_admission.py",
    "tests/review_paper/test_supervised_maintenance_rebind.py",
    "tests/review_paper/test_production_strategy_cycle.py",
)
ARCH134_D1R4R_SOURCE_PINS: Final = {
    "src/trading_bot/review_paper/alpaca_windows_credentials.py": (
        "f76962b00bc9c51196d5234e03620972763e2bf7"
    ),
    "src/trading_bot/review_paper/alpaca_credential_generation.py": (
        "ee3ea56bdd1e820663b7d4b71dd71216c2a1eccc"
    ),
    "src/trading_bot/review_paper/alpaca_credential_host.py": (
        "4d452bbb923e5ca5deecfa2ddaa5d514aed681d6"
    ),
    "src/trading_bot/review_paper/alpaca_credential_staging_cleanup.py": (
        "8af64b8007f94c530b106999084b0c8454725dc6"
    ),
    "src/trading_bot/review_paper/alpaca_credential_cleanup_host.py": (
        "1b86cf4b380f20564a17a59e83e0f228b25abac6"
    ),
    "tests/review_paper/test_alpaca_credential_generation.py": (
        "e17c3bf76b12f2b2cc0fd353c0c4a0b05c6174f8"
    ),
    "tests/review_paper/test_alpaca_credential_staging_cleanup.py": (
        "feb410ab64cbe6c19cbc2c86b03854e383339b42"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "30bcf0d14a78d02dd82438d532eaae26e3649f63"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "26fa20c5ab46bf20b202594f8cc973e54be532a2"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "b5eed90bbd5d468623a70efb6e61e3d61acf4c42"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "60e59e64087bd71ec27f7f372bcb8c1b64c82b64"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "6c65be330e18bbdd9a9e0e564c635948201e20f4"
    ),
}  # D1R4R_GENERATED_PINS
ARCH134_D1R4R_IMPORTS: Final = {
    "src/trading_bot/review_paper/alpaca_windows_credentials.py": (
        "__future__",
        "collections.abc",
        "ctypes",
        "os",
        "typing",
    ),
    "src/trading_bot/review_paper/alpaca_credential_generation.py": (
        "__future__",
        "collections.abc",
        "dataclasses",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "typing",
    ),
    "src/trading_bot/review_paper/alpaca_credential_host.py": (
        "__future__",
        "argparse",
        "getpass",
        "hashlib",
        "pathlib",
        "sys",
        "trading_bot.review_paper.alpaca_authentication_host",
        "trading_bot.review_paper.alpaca_credential_generation",
        "trading_bot.review_paper.alpaca_credential_native",
        "warnings",
    ),
    "src/trading_bot/review_paper/alpaca_credential_staging_cleanup.py": (
        "__future__",
        "collections.abc",
        "contextlib",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "trading_bot.review_paper.alpaca_credential_generation",
        "trading_bot.review_paper.alpaca_windows_credentials",
        "typing",
    ),
    "src/trading_bot/review_paper/alpaca_credential_cleanup_host.py": (
        "__future__",
        "argparse",
        "pathlib",
        "sys",
        "trading_bot.review_paper.alpaca_authentication_host",
        "trading_bot.review_paper.alpaca_credential_generation",
        "trading_bot.review_paper.alpaca_credential_native",
        "trading_bot.review_paper.alpaca_credential_staging_cleanup",
        "trading_bot.review_paper.alpaca_windows_credentials",
    ),
}  # D1R4R_GENERATED_IMPORTS

# HIST-2 certification-inventory descendant overlay only. All D1/D1Q/R1/R2/R3/
# D1R4/D1R4R dictionaries above remain frozen.
ARCH134_HIST2_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "ded8139e15785ed6c05cc77a1921160f24854689"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "fe06a99bed79f6a1e6ff1b0633939d855fdcf537"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "3897e232387636f6fae29fa25989aa54dd7ae3aa"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "b1d46618abb4e8f9eef1062ff0dd978230a1b9cf"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "2925a26cc00238b6fa9675e6e68d6f6acd8fa138"
    ),
}

# D1R5 successor only; all predecessor dictionaries remain byte-for-byte frozen.
ARCH134_D1R5_NAME: Final = "arch134-d1r5-pre-market-wake-qualification"
ARCH134_D1R5_BRANCH: Final = (
    "feature/robinhood-production-paper-premarket-wake-qualification"
)
ARCH134_D1R5_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "a02a7c0d489fe679b69813748bc24a9800f8428e"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "577e30be94451da671d50a76c6d25882bef3a43a"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "583939144200ac633907ef80956732064648ca3c"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "d1ea3594fdb1cdec6047b51ef6ce03cc2336fa2f"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "c2199a4c64befeaba238583a3ac53fb347757ef8"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "df5497ab5193204ebcf34eb20fac203307d47948"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "5ff9ac6035cc10335fec916fb8d9fde4a6c18bae"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "2c1b28cff7f0a0812246d79b6650bd2adaad3b44"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "bc9c49ac7df48753c49b7b5df7087a9a0bc55660"
    ),
}
ARCH134_D1R5_PATHS: Final = (
    "src/trading_bot/review_paper/pre_market_wake_qualification.py",
    "src/trading_bot/review_paper/pre_market_wake_qualification_host.py",
    "tests/review_paper/test_pre_market_wake_qualification.py",
    "docs/validation/arch134-d1r5-pre-market-wake-qualification.md",
)
ARCH134_D1R5_SOURCE_PINS: Final = {
    "src/trading_bot/review_paper/pre_market_wake_qualification.py": (
        "c751590126453a51442ae10bbaf638f0a32c92b8"
    ),
    "src/trading_bot/review_paper/pre_market_wake_qualification_host.py": (
        "809da0dd5f1d0fbe5fea515e51b0b6af3497ac8a"
    ),
    "tests/review_paper/test_pre_market_wake_qualification.py": (
        "f6f4dfaf3b13e9d2d643ebf085b6ddacfbd168cd"
    ),
    "docs/validation/arch134-d1r5-pre-market-wake-qualification.md": (
        "3449492fd680a813c1fbc59aad1f16bf6cc378fc"
    ),
}
ARCH134_D1R5_IMPORTS: Final = {
    "src/trading_bot/review_paper/pre_market_wake_qualification.py": (
        "__future__",
        "collections.abc",
        "datetime",
        "enum",
        "json",
        "os",
        "pathlib",
        "stat",
        "trading_bot.review_paper.nyse_published_regular_sessions",
        "trading_bot.review_paper.session_admission",
        "typing",
        "zoneinfo",
    ),
    "src/trading_bot/review_paper/pre_market_wake_qualification_host.py": (
        "__future__",
        "argparse",
        "datetime",
        "os",
        "pathlib",
        "subprocess",
        "sys",
        "time",
        "trading_bot.review_paper.pre_market_wake_qualification",
    ),
}
ARCH134_D1R5_TESTS: Final = (
    "tests/review_paper/test_pre_market_wake_qualification.py",
    "tests/review_paper/test_armed_production_paper_session.py",
    "tests/review_paper/test_session_admission.py",
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
    "tests/review_paper/test_supervised_release_installation.py",
    "tests/review_paper/test_arch133_reprovision_recovery.py",
    "tests/review_paper/test_arch133_windows_rename_qualification.py",
    "tests/review_paper/test_supervised_deployment_qualification.py",
    "tests/review_paper/test_supervised_runtime_host_admission.py",
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
    "tests/review_paper/test_arch133_reprovision_reconciliation.py",
    "tests/review_paper/test_supervised_maintenance_rebind.py",
    "tests/review_paper/test_production_strategy_cycle.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/scripts/certification_runner/test_lanes.py",
    *COMMON_TESTS,
)
ARCH134_D1R5_RUFF_PATHS: Final = (
    *ARCH134_D1R5_PATHS[:3],
    *ARCH134_D1R5_TEST_PIN_OVERRIDES,
    *ARCH134_D1R5_TESTS,
    "scripts/run_test_certification.py",
    *COMMON_RUFF_PATHS,
)


# Architecture 138 succeeds D1R5 only for these live-discovery inventory tests.
# Every predecessor dictionary and executable/native/AST pin remains frozen.
ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "a3512cef7de7c2482c649f43f4e9c4b00c62c403"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "5cee9a1c55618c06b478ffb2e792a7648c6f5e4c"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "8c5330f855b44cd63c3dfc99e3b2f5565b55bd9f"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "3dab5e5f166a9fc4d7893ed20741e627a95e035c"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "f67561da61aab33d295538689c75225bbd690bc8"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "62617f9f9fbab1c90a8b2d84482220caee98796f"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "52b1fd4e3257976e3d5014d0af1aecde62da7ee0"
    ),
}


def _arch138_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != {
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/strategies/test_production_strategy_decision.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
    }:
        raise ValueError("138 unreviewed current inventory test pin override")
    return ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(relative, predecessor)


# Architecture 139-A succeeds 138 only for the same live-discovery tests.
# All predecessor dictionaries and executable/native/AST pins remain frozen.
ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "cacc61cc25e1b6ba9db866767758b13c91f92aff"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "2f72359ba9338ea0969469de216ee602be6df4d4"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "411d18876f33ac456c5fd5efa4d73bf6294bb3ea"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "ca217d4214141bcdac7e2e7ecd1b8f7b5d058853"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "11471897d25ae60cb8bf893b2f8ce39217f2082d"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "e623a7eb9483e540f13f8e97d4b4b6c1e4a285d7"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "0d71948f511aa7cf2c2313e78cda6c9326bd6f65"
    ),
}


def _arch139a_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != {
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/strategies/test_production_strategy_decision.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
    }:
        raise ValueError("139-A unreviewed current inventory test pin override")
    return ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(relative, predecessor)


# Architecture 139-B1 succeeds its predecessor only for live inventory tests.
ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "958b5d94d3b2a9b7e40d5771c25040f4cda4fa25"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "ad2e0dd1438552b96f8583f4f8a7767f6fe6787c"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "a52f921843857af48464a34d02d981226cd7c587"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "2e72b98b93195639daa5bf2ffa6ff03eb951d27a"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "376521fbce38b348bce9bc17f520b2bf979a483d"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "f28f28d4afb79db9c56ca60530df4f4ab3cbeded"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "610878dbe011260d3c60855cdfb2c72ae5a105f9"
    ),
}


def _arch139b1_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != {
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_decision.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
    }:
        raise ValueError("139-B1 unreviewed current inventory override")
    for name, digest in (
        (
            "ARCH134_HIST2_TEST_PIN_OVERRIDES",
            "1d005a7fa62d7172d58be3a9b61443e548f0c62c92ad8652bc883b8df302d950",
        ),
        (
            "ARCH134_D1R5_TEST_PIN_OVERRIDES",
            "bcdb35cb77572df147ea12a9db54d22da2cbe8933140a6c1a7b448dba8be287b",
        ),
        (
            "ARCH138_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "8a4021b92a5354cfbdb5394692eb50c14f6a13982b9a50aeb7d259553c7e5988",
        ),
        (
            "ARCH139A_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "9ec72c131a25b962a7d3e49124f99aa712dc2a8e0182d297f4a78507b6e0fb69",
        ),
    ):
        material = json.dumps(globals()[name], sort_keys=True).encode()
        if hashlib.sha256(material).hexdigest() != digest:
            raise ValueError("139-B1 frozen predecessor drift: " + name)
    return ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(relative, predecessor)


# Architecture 139-B2 succeeds its predecessor only for live inventory tests.
ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "3da7aea48cf0e04e0bf905b06a6720e8eb4107a5"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "c275cdc141d2692ac39cc2e7b37bccb9bd2753a1"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "852f0fb0f1f7e5dcc9dd72d927afa0ec1c0daa67"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "43530aa484e450b8c1d53f8bb971c6fac63d50b3"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "336fc83f75a3500cb6d2c65a93cd99413e9348a0"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "f89d3757b29f272f917422b5806b75241d0b4c1e"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "1485933612289b843ad407f50e64d66598aeca78"
    ),
}


def _arch139b2_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != {
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_decision.py",
    }:
        raise ValueError("139-B2 unreviewed current inventory override")
    for name, digest in (
        (
            "ARCH139B1_CURRENT_INVENTORY_TEST_PIN_OVERRIDES",
            "d66e134a5491e1e2966728e27558f05c51946c5e89930707e1471f339324634c",
        ),
    ):
        material = json.dumps(globals()[name], sort_keys=True).encode()
        if hashlib.sha256(material).hexdigest() != digest:
            raise ValueError("139-B2 frozen predecessor drift: " + name)
    return ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(relative, predecessor)


# Architecture 140 / GUI-A16 succeeds B2 for exactly seven inventory tests.
ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "cfa0ad5b217b6493c6eab748efeff09b17e6a7d3"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "4e694f9e8ac110b422f1ae2b1eafc401ce6bbf7f"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "57d1053f46b4a86a80cdc8d575dc6ec8e8d9ddb1"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "bf9afe45f42a8d8cd6334ff295f7a76ca07697d3"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "c98d6252257ace3d8b876dc0c36fab474e089e92"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "544e0b9ac6d0276467872ce2ae0481504cd31a79"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "36e9c0802f19cec5fe0ed771be5a599fa584e84c"
    ),
}


def _arch140_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != {
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/strategies/test_production_strategy_decision.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
    }:
        raise ValueError("140 unreviewed current inventory override")
    material = json.dumps(
        ARCH139B2_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        hashlib.sha256(material).hexdigest()
        != "32ef60967164da03e02c8cfe40928b8839f89a2c4bb90074e967bb08213d6458"
    ):
        raise ValueError("140 frozen 139-B2 predecessor drift")
    return ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(relative, predecessor)


# GUI-A17 succeeds A16 only for the same seven current inventory tests.
ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "e8212d9d29b648868472812e3b87d86ba0a52b7e"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "71a795f9a52568fd0459fbd84b0ce9c08e61d60b"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "a188f948e335a25d611991465a93c8de93b5ec3f"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "83a50eb19dc230a366a39dae293f4006b7dbef52"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "8f9a142d408fcaaaa3ef55a049445859cef3377a"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "2a9d81b1cb2a4d0969251db45bff88ca114c0e3f"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "e200dc0d0357ddc654d8253fc311464d28992ff6"
    ),
}


def _arch140a17_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    material = json.dumps(
        ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        hashlib.sha256(material).hexdigest()
        != "887064885ca3be46514075efed384ccf1c6eb778d78dcc3f06bc402bff1a4e4f"
    ):
        raise ValueError("140-A17 frozen A16 predecessor drift")
    if set(ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != set(
        ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    ):
        raise ValueError("140-A17 unreviewed current inventory override")
    if relative in ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        if predecessor != ARCH140_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]:
            raise ValueError("140-A17 wrong before pin")
    return ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(relative, predecessor)


# GUI-A18 succeeds A17 for the same seven current inventory tests.
ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "e1d74224317534373f2374bb0b90d927e80e8247"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "7812c989b5c358ca0788bdaabd8febc664fa835f"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "1af48ae395c03801a7fdbe86804cf4845d141427"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "8630a2da95dca4580fbfc0ececc7021b6b3d0b07"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "0b4e8c07e7dd8cce9f9c132224a6c5cbed0288da"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "ec3421cd69257778e45f908ff65e607407b1b9f0"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "14df3fad18150a48c12114d4e902ed62c17d5efa"
    ),
}


def _arch140a18_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    material = json.dumps(
        ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        hashlib.sha256(material).hexdigest()
        != "dc11d4c1e6099c1eec3346cafb85220e42f495e472d220cf81ac741ccff524c3"
    ):
        raise ValueError("140-A18 frozen A17 predecessor drift")
    if set(ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != set(
        ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    ):
        raise ValueError("140-A18 unreviewed current inventory override")
    predecessor = _arch140a17_current_inventory_test_pin(relative, predecessor)
    if relative in ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        if predecessor != ARCH140A17_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]:
            raise ValueError("140-A18 wrong before pin")
    return ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(relative, predecessor)


# D1R6 successor: only shared tests changed by registration/inventory.
ARCH134_D1R6_NAME: Final = "arch134-d1r6-overnight-wake-arming"
ARCH134_D1R6_BRANCH: Final = "feature/robinhood-production-paper-overnight-wake-arming"
ARCH134_D1R6_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "30d2280bc5e031796ce06febc3562cbe5e6be982"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "1b6447063b1401cf1d930b71e0ec703287623b77"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "4721a9ba5e2fc6a052ab7c6f1066b9ef924a7117"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "0093fdf868065d4dff932427b037b21f74f1bbff"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "7e86ab4182bf21577c061836b77269066410707b"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "ecd2074d3f4e9b42f314a6556e32b57b70753a1e"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "b31d8a5055ebaa763abf1e2e6ed1a5485f1b2f31"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "9a7b88f8363b0c7c89ee6e23659b6a444679c7c4"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "de7a77d3b0cf58fd9d5d58450181f8a1957fc7b2"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "ea7ca9f8a0ec33449f70101e2e27aa72d2f27a39"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "127db46d0211570727c2a9fb6118bb8f6a3b45d2"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "292f4b3fa8fc3b667f6b60c6498da99aa8b687b5"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "3c1fafd75920ba3346918fd3c44fb3a390e73678"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "e3a85fd7a71e9e83c89faf60bf25dea6d26a49d2"
    ),
}
ARCH134_D1R6_REVIEWED_TEST_PINS_SHA256: Final = (
    "dfe1999400e0a6fdea245ccdd7d77a62e49aa1a169dbd42c0f89e2e88868ef4b"
)
ARCH134_D1R6_PREDECESSOR_DIGESTS: Final = {
    "ARCH134_D1R5_TEST_PIN_OVERRIDES": (
        "6a95f4afc8640dfa0c672f5d77cda06ae57171c0199128a3ddd1d8b0debaac4a"
    ),
    "ARCH134_D1R5_SOURCE_PINS": (
        "370e14ff9a9453b4e001278921c3d1084c6ff94c8e34be76d430cb2b2adae575"
    ),
}
ARCH134_D1R6_PATHS: Final = (
    "src/trading_bot/review_paper/pre_market_wake_overnight.py",
    "src/trading_bot/review_paper/pre_market_wake_overnight_host.py",
    "scripts/run_arch134_d1r6.py",
    "scripts/arch134_d1r6_d1r5_child.py",
    "scripts/arch134_d1r6_scheduler_create.ps1",
    "scripts/arch134_d1r6_task_launcher.ps1",
    "tests/review_paper/test_pre_market_wake_overnight.py",
    "docs/architecture/134-d1r6-overnight-pre-market-wake-arming.md",
    "docs/validation/arch134-d1r6-overnight-pre-market-wake-arming.md",
)
ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS: Final = {
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "541637b761793075b3db7f12425beb41c4ab3c9d"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "a0eea1de674e55f547fd3f958b572484919e7566"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "aa7985c1ba7e08320665b554900ec57ca981eed7"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "8e2c645257767a306bf941e06c458050e63cd711"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "b056de4a599699b83cc6194e5ce7b34393823d52"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "1f9443823652c8931507030c60ddbdad2a4a360e"
    ),
}
ARCH134_D1R6_ADDITIONAL_PREDECESSOR_SHA256: Final = (
    "572d83c4a3938678894c0cb9072c182373fbce4f596c4b66c26b51f07e2089ab"
)

ARCH134_D1R6_SOURCE_PINS: Final = {
    "src/trading_bot/review_paper/pre_market_wake_overnight.py": (
        "666d43948fa812050bb0bd4d761c387e41b766e6"
    ),
    "src/trading_bot/review_paper/pre_market_wake_overnight_host.py": (
        "b64a1c2a580b895450fe6d3c0245728ed1df63a3"
    ),
    "scripts/run_arch134_d1r6.py": ("593eacf9495fcc4fe75a51f54f8947266a93b676"),
    "scripts/arch134_d1r6_d1r5_child.py": ("c03f163f5bbc1cb4a6c78428298f16ebc5f71368"),
    "scripts/arch134_d1r6_scheduler_create.ps1": (
        "827a3798e6ca0f6c3d3fe76a75f9feadbabc1976"
    ),
    "scripts/arch134_d1r6_task_launcher.ps1": (
        "62072df35376c5abb6adb4ff7ec764199621cb7c"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "99efdaa678ef63541f3c583d7c3bcb5f965c357b"
    ),
    "docs/architecture/134-d1r6-overnight-pre-market-wake-arming.md": (
        "1cb021dd04deddc9c932156db57413145ae8fae4"
    ),
    "docs/validation/arch134-d1r6-overnight-pre-market-wake-arming.md": (
        "a7a7045cb1c308ac9f69870dae7a1beaa81b86e1"
    ),
}
ARCH134_D1R6_TESTS: Final = (
    "tests/review_paper/test_pre_market_wake_overnight.py",
    "tests/review_paper/test_nyse_published_regular_sessions.py",
    *ARCH134_D1R5_TESTS,
)
ARCH134_D1R6_RUFF_PATHS: Final = (
    *(p for p in ARCH134_D1R6_PATHS if p.endswith(".py")),
    *ARCH134_D1R5_RUFF_PATHS,
)


def _arch134_d1r6_test_pin(relative: str, predecessor: str) -> str:
    def digest(value: object) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    if (
        set(ARCH134_D1R6_TEST_PIN_OVERRIDES)
        != {
            "tests/scripts/certification_runner/test_profiles.py",
            "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
            "tests/review_paper/test_supervised_release_installation.py",
            "tests/review_paper/test_arch133_reprovision_recovery.py",
            "tests/review_paper/test_arch133_windows_rename_qualification.py",
            "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
            "tests/review_paper/test_arch133_reprovision_reconciliation.py",
            "tests/runtime/checkpoint_runner/test_ci.py",
            "tests/runtime/checkpoint_runner/helpers.py",
            "tests/review_paper/test_supervised_runtime_host_admission.py",
            "tests/review_paper/test_supervised_maintenance_rebind.py",
            "tests/runtime/checkpoint_runner/test_core.py",
            "tests/review_paper/test_supervised_deployment_qualification.py",
            "tests/review_paper/test_production_strategy_cycle.py",
        }
        or digest(ARCH134_D1R6_TEST_PIN_OVERRIDES)
        != ARCH134_D1R6_REVIEWED_TEST_PINS_SHA256
    ):
        raise ValueError("134-D1R6 unreviewed successor test override")
    for name, expected in ARCH134_D1R6_PREDECESSOR_DIGESTS.items():
        if digest(globals()[name]) != expected:
            raise ValueError("134-D1R6 predecessor drift")
    if (
        digest(ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS)
        != ARCH134_D1R6_ADDITIONAL_PREDECESSOR_SHA256
    ):
        raise ValueError("134-D1R6 additional predecessor drift")
    if (
        relative in ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS
        and predecessor != ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS[relative]
    ):
        raise ValueError("134-D1R6 additional predecessor resolution drift")
    if (
        relative in ARCH134_D1R5_TEST_PIN_OVERRIDES
        and predecessor != ARCH134_D1R5_TEST_PIN_OVERRIDES[relative]
    ):
        raise ValueError("134-D1R6 predecessor resolution drift")
    return ARCH134_D1R6_TEST_PIN_OVERRIDES.get(relative, predecessor)


def _arch134_d1r6_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = list(_arch134_d1r5_authority_check(repo_root))
    try:
        if set(ARCH134_D1R6_SOURCE_PINS) != set(ARCH134_D1R6_PATHS):
            failures.append("134-D1R6 unreviewed source override")
        for relative, pin in ARCH134_D1R6_SOURCE_PINS.items():
            pin = _arch134_d1r7_test_pin(relative, pin)
            pin = _arch142_current_inventory_test_pin(relative, pin)
            pin = _arch142b_current_inventory_test_pin(relative, pin)
            pin = _arch143_current_inventory_test_pin(relative, pin)
            pin = _arch132_r3i_current_inventory_test_pin(relative, pin)
            pin = _arch144_current_inventory_test_pin(relative, pin)
            if _git_blob_sha1(repo_root / relative) != pin:
                failures.append("134-D1R6 source drift: " + relative)
        for relative in ARCH134_D1R6_TEST_PIN_OVERRIDES:
            expected = _arch134_d1r6_test_pin(
                relative,
                ARCH134_D1R5_TEST_PIN_OVERRIDES.get(
                    relative, ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS.get(relative)
                ),
            )
            # D1R6 has already resolved these pins. Only the seven integrated
            # inventory paths have a further canonical successor; the fallback
            # must not pass a resolved pin into D1R6's strict predecessor gate.
            if relative in CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
                expected = _canonical_current_inventory_test_pin(relative, expected)
            expected = _arch134_d1r7_test_pin(relative, expected)
            expected = _arch142_current_inventory_test_pin(relative, expected)
            expected = _arch142b_current_inventory_test_pin(relative, expected)
            expected = _arch143_current_inventory_test_pin(relative, expected)
            expected = _arch132_r3i_current_inventory_test_pin(relative, expected)
            expected = _arch144_current_inventory_test_pin(relative, expected)
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append("134-D1R6 successor drift: " + relative)
        if (
            _git_blob_sha1(repo_root / ".github/workflows/checkpoint-source-gates.yml")
            != "fe6aceac62721338eba4fcb40e2e7fde0d976e18"
        ):
            failures.append("134-D1R6 workflow drift")
        spec = _checkpoint_specs()[ARCH134_D1R6_NAME]
        if (
            spec.remote_branch != ARCH134_D1R6_BRANCH
            or spec.tests != ARCH134_D1R6_TESTS
            or spec.ruff_paths != ARCH134_D1R6_RUFF_PATHS
            or spec.authority_check is not _arch134_d1r6_authority_check
            or spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_D1R6_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_D1R6_NAME) != "robinhood"
        ):
            failures.append("134-D1R6 source-only registration drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("134-D1R6 authority unavailable")
    return tuple(failures)


# Canonical product + safe-side integration: the seven live-inventory tests
# are the only files whose current bytes must combine D1R6 and GUI-A18 state.
CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/scripts/certification_runner/test_profiles.py": (
        "6d5a7eaa49cbe6a9c67900d8e0ae99476cded215"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "4fae6dc080f6b9080025cc4dc2860725cbbaa1f8"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "d608cad8d3b5c4d52373e7b4ea4d5b0b23ad7748"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "b189e5ba3a792f7f0375b1df228cb706134e6fb6"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "ae8df8b5b3e32c84028ace2103f5b932635edea1"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "36f5849f5df62682713860f053b87879b97d37cc"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "588d9d71bf2e6513754e7a0ec8e2c2627b435458"
    ),
}
CANONICAL_CURRENT_INVENTORY_TEST_PINS_SHA256: Final = (
    "0683b8810167b83d95275bf2173e3431ba28fcca022e3572be90f8c64be48c96"
)


def _canonical_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    material = json.dumps(
        CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        set(CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
        != set(ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES)
        or hashlib.sha256(material).hexdigest()
        != CANONICAL_CURRENT_INVENTORY_TEST_PINS_SHA256
    ):
        raise ValueError("canonical integration inventory override drift")
    a18_material = json.dumps(
        ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        hashlib.sha256(a18_material).hexdigest()
        != "a82247963625dea0f6842d4dc59a851c6986d9f3d8d0c0f40d452aaea2a35af5"
    ):
        raise ValueError("canonical integration A18 predecessor drift")
    if relative in CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        accepted = {ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]}
        if relative in ARCH134_D1R6_TEST_PIN_OVERRIDES:
            accepted.add(ARCH134_D1R6_TEST_PIN_OVERRIDES[relative])
        if predecessor not in accepted:
            raise ValueError("canonical integration predecessor resolution drift")
        return CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]
    return _arch134_d1r6_test_pin(relative, predecessor)


# Architecture 142-A succeeds the frozen D1R8 current-inventory overlay for
# the strategy-native research admission and its mechanically refreshed
# current-inventory assertions. All predecessor overlays and their reviewed
# pin values remain frozen.
ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "956d96c13f469dc18b70b574b5b317cd8a27c83c"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "0cc588a8d7109f23ff5123da96e4aa236c7054f1"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "fb1e5ad72def5c1205cc3832e8e14a2b7a5d0b1e"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "621014459327b2695a233ba5dd6318438ace35b3"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "1ef12dcf031d448ab159a23b3d349498425fdd0a"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "010ede8d9fa2c7f32d3dd7bdbca61239446aaf07"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "775100d0125d3c93b7078284dcdc624c4f4b0164"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "73b8570a787a76ac35a2aaff9943c3407cffe641"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "baae4aa11d8659f179001773ec33f9b259f36562"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "fcad01a8f7ed8ef7ccdc32df50e8888b3eca8728"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "5c76156286beb0466a945a2b7dacc18be3418fa7"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "5455ed80bff5a9bb07a7eede59f9d8940fd999d5"
    ),
}
ARCH142_CURRENT_INVENTORY_TEST_PINS_SHA256: Final = (
    "515392eb1213323ab2bc0a62a4bd848a21b9fe60b6afcdaeac14b44523c43366"
)


def _arch142_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != {
        "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py",
        "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py",
        "tests/review_paper/test_d1_session_authorization.py",
        "tests/review_paper/test_d1_session_execution.py",
        "tests/review_paper/test_pre_market_wake_overnight.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/strategies/test_production_strategy_decision.py",
    }:
        raise ValueError("142-A unreviewed current inventory override")
    material = json.dumps(
        ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        hashlib.sha256(material).hexdigest()
        != ARCH142_CURRENT_INVENTORY_TEST_PINS_SHA256
    ):
        raise ValueError("142-A current inventory override drift")
    if relative in ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        d1r8_predecessor = ARCH134_D1R8_TEST_PIN_OVERRIDES.get(
            relative, ARCH134_D1R8_SOURCE_PINS.get(relative)
        )
        if predecessor != d1r8_predecessor:
            raise ValueError("142-A wrong before current inventory pin")
        return ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]
    return predecessor


# Architecture 142-B succeeds 142-A only for the same current-inventory tests
# whose expected counts changed when the new strategy-native test was added.
# The accepted 142-A dictionary and digest remain frozen predecessors.
ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "6f3d93d908117f701e7855c174fb33a573146065"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "8cee7f825b3e3430a7e38973a2c20038d8bee782"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "c681ac6fe36b1f20838dd6a3269a262fa57ad172"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "c7386859077da04d85049ccfb0124f1436beb9d3"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "3f4af45b2a9fa84dbb9f98e25cc09acc702d5aeb"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "946c490a42d8c8d59777a920db6226c5610c3446"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "084108033a3fdbb896c581dc3d878c5f5e65d241"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "e52300d66e8fa97e15ce5c7b549ad252384b31f6"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "08adb0cc888b74dd1dd6801d9b5d4637d60c7bcc"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "267083e1bc82ed64b211524e73735d032ffb45c5"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "498e0f197fc7880ddfe93d4c5aebfc7942a1c0d9"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "3a851b74bec21c170360f0aa7c68ee38d5732c5f"
    ),
}
ARCH142B_CURRENT_INVENTORY_TEST_PINS_SHA256: Final = (
    "8a7ddd8184e1beadecdce88207ed75b02dce75be870892957b9ae5ae5d7e33c6"
)


def _arch142b_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != set(
        ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES
    ):
        raise ValueError("142-B unreviewed current inventory override")
    material = json.dumps(
        ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        hashlib.sha256(material).hexdigest()
        != ARCH142B_CURRENT_INVENTORY_TEST_PINS_SHA256
    ):
        raise ValueError("142-B current inventory override drift")
    if relative in ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        if predecessor != ARCH142_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]:
            raise ValueError("142-B wrong before current inventory pin")
        return ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]
    return predecessor


ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "f85f5f44f8d2e90ddbba1daf734f92c468314af6"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "0f552f56a72419f4b3a2b84416759526300c2875"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "8d1c3739d9c5e70d16643124ab6e705fb3e6ca00"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "1349d66944d4b5adc08d3b0309c2b373aef4075d"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "8b1f47ad18a4af8b38c50fc518ef1cf8b64646a5"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "fa288b6db3671eab07cdac83f5b763975c3e3a49"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "a0ac8e53e6ddd266ea8acc5bbd25da9f8d6be197"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "b2e17f5f0301cdced36e2223ef6d3c6d2c9a6717"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "df9734fb68b6719b2cb500386977f735ad2e9ebf"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "435714e8f6789d0b51f7451673d4428e624c5d20"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "86b9711c2d105e9e1dc27ac12b85b5c5b4749d8d"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "643e0f87bdee1c6ae5f470672c2f04364481c050"
    ),
}
ARCH143_CURRENT_INVENTORY_TEST_PINS_SHA256: Final = (
    "394bc4086d09ab842e7773ec322e60fb01cbd1683c580e9828d09a531d3e1bc2"
)


def _arch143_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != {
        "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py",
        "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py",
        "tests/review_paper/test_d1_session_authorization.py",
        "tests/review_paper/test_d1_session_execution.py",
        "tests/review_paper/test_pre_market_wake_overnight.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/strategies/test_production_strategy_decision.py",
    }:
        raise ValueError("143 unreviewed current inventory override")
    material = json.dumps(
        ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        hashlib.sha256(material).hexdigest()
        != ARCH143_CURRENT_INVENTORY_TEST_PINS_SHA256
    ):
        raise ValueError("143 current inventory override drift")
    if relative in ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        if predecessor != ARCH142B_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]:
            raise ValueError("143 wrong before current inventory pin")
        return ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]
    return predecessor


# Architecture 132-R3I succeeds only the mechanically changed pinned tests.
# Executable predecessor: 33b14eab4e9577f15b2afa559918415e4d471d55 /
# d19ef77620881343cc38010290029865fd43c1f4. Every earlier overlay stays frozen.
ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "ed105665af321fe51a97124671ca322b4d671ab1"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "c9299c24aed846f655e071c44a7fb4e825bf0d58"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "d807a79b9e5db83b2644a0ea58939af1edafc248"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "269fbb0437ba080504f9b87a9ca03ed8ab380395"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "25d7f8bf7a1835a9fa594963b4ac49fc36966513"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "413a1d5d578d5767c441965ad23020f17af95b35"
    ),
}
ARCH132_R3I_CURRENT_TEST_PINS_SHA256: Final = (
    "8ee71a5929cf3aa073cbb2d25fd2f7996137d2ef20cd22529dd3816f74ae43d5"
)


def _arch132_r3i_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    accepted_143_digest = (
        "394bc4086d09ab842e7773ec322e60fb01cbd1683c580e9828d09a531d3e1bc2"
    )
    if (
        type(ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) is not dict
        or ARCH143_CURRENT_INVENTORY_TEST_PINS_SHA256 != accepted_143_digest
        or hashlib.sha256(
            json.dumps(
                ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
            ).encode()
        ).hexdigest()
        != accepted_143_digest
    ):
        raise ValueError("R3I wrong Architecture-143 predecessor material")
    if type(ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES) is not dict or set(
        ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES
    ) != {
        "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py",
        "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py",
        "tests/review_paper/test_d1_session_execution.py",
        "tests/scripts/certification_runner/test_lanes.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_contract.py",
    }:
        raise ValueError("R3I unreviewed successor override")
    if any(
        type(pin) is not str
        or len(pin) != 40
        or any(character not in "0123456789abcdef" for character in pin)
        for pin in ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES.values()
    ):
        raise ValueError("R3I malformed successor blob")
    material = json.dumps(
        ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if hashlib.sha256(material).hexdigest() != ARCH132_R3I_CURRENT_TEST_PINS_SHA256:
        raise ValueError("R3I successor override drift")
    if relative in ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES:
        expected = ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES.get(relative)
        if relative == "tests/scripts/certification_runner/test_lanes.py":
            expected = "bc9c49ac7df48753c49b7b5df7087a9a0bc55660"
        if predecessor != expected:
            raise ValueError("R3I wrong before successor pin")
        return ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES[relative]
    return predecessor


# Architecture 144 succeeds the accepted R3I/current-inventory chain only for
# the mechanically refreshed current assertions. All predecessor overlays
# remain frozen, including the R3I successor material.
ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "507979e4cfcf4b8140da2e234a2f5bbb2d6f4255"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "046864c016aa9089dfda9887759a53494f78ea25"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "d02acf70e9cfd31c581433eaba965abe8f475d0c"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "d3ae1d8289058ff692a102261711cc858e9bfe48"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "26e73bf98457310421b3460803c44d3a56ce7adb"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "bc78742d0854b5d0e03e9285b0d933e9e04d8969"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "866043e4a02d222e1f3fe6f88b131750d44bdfb0"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "112f2cbd5042d92b224ebccf99568c63ae0e92fb"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "44bb6d4606b7e7c89818db22bca912f973d57eab"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "e857d1b360e19109dc0caa7b3195227d2e05d59a"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "1b93c9568ce476c92b109a1b12e8bcdd67377d84"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "2a68830609ace599f5cc0eabe766692799a232c9"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "7697ae59eb5ef6eefc2c506679a1aad875f4a90a"
    ),
}
ARCH144_CURRENT_INVENTORY_TEST_PINS_SHA256: Final = (
    "8debe5182901b67ef26ea2745481b14d1931d4ab752422dfe9fb6f839e6f24be"
)


def _arch144_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES) != {
        *ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES,
        "tests/scripts/certification_runner/test_lanes.py",
    }:
        raise ValueError("144 unreviewed current inventory override")
    material = json.dumps(
        ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES, sort_keys=True
    ).encode()
    if (
        hashlib.sha256(material).hexdigest()
        != ARCH144_CURRENT_INVENTORY_TEST_PINS_SHA256
    ):
        raise ValueError("144 current inventory override drift")
    if relative in ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES:
        expected = ARCH132_R3I_CURRENT_TEST_PIN_OVERRIDES.get(relative)
        if expected is None:
            expected = ARCH143_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]
        if predecessor != expected:
            raise ValueError("144 wrong before current inventory pin")
        return _arch134_f1_current_inventory_test_pin(
            relative, ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES[relative]
        )
    return _arch134_f1_current_inventory_test_pin(relative, predecessor)


def _arch134_d1r5_test_pin(relative: str, predecessor: str) -> str:
    if set(ARCH134_D1R5_TEST_PIN_OVERRIDES) != {
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/runtime/checkpoint_runner/test_core.py",
        "tests/runtime/checkpoint_runner/test_ci.py",
        "tests/runtime/checkpoint_runner/helpers.py",
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/scripts/certification_runner/test_lanes.py",
    }:
        raise ValueError("134-D1R5 unreviewed successor test pin override")
    return ARCH134_D1R5_TEST_PIN_OVERRIDES.get(relative, predecessor)


def _arch134_d1r5_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Separate source-only checkpoint; no real clock/sleep/evidence CI operation."""
    failures = list(_arch134_authentication_authority_check(repo_root))
    try:
        if set(ARCH134_D1R5_SOURCE_PINS) != set(ARCH134_D1R5_PATHS):
            failures.append("134-D1R5 unreviewed source override")
        if set(ARCH134_D1R5_IMPORTS) != set(ARCH134_D1R5_PATHS[:2]):
            failures.append("134-D1R5 unreviewed import override")
        for relative, pin in {
            **ARCH134_D1R5_SOURCE_PINS,
            **ARCH134_D1R5_TEST_PIN_OVERRIDES,
        }.items():
            expected_pin = _arch138_current_inventory_test_pin(relative, pin)
            expected_pin = _arch139a_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b1_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b2_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140a18_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _canonical_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch134_d1r7_test_pin(relative, expected_pin)
            expected_pin = _arch142_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch142b_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch143_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch132_r3i_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _arch144_current_inventory_test_pin(relative, expected_pin)
            if _git_blob_sha1(repo_root / relative) != expected_pin:
                failures.append("134-D1R5 source drift: " + relative)
        for relative, allowed in ARCH134_D1R5_IMPORTS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            imports = {
                n.module
                for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module
            } | {
                a.name
                for n in ast.walk(tree)
                if isinstance(n, ast.Import)
                for a in n.names
            }
            if imports != set(allowed):
                failures.append("134-D1R5 import closure drift: " + relative)
        spec = _checkpoint_specs()[ARCH134_D1R5_NAME]
        if (
            spec.remote_branch != ARCH134_D1R5_BRANCH
            or spec.tests != ARCH134_D1R5_TESTS
            or spec.ruff_paths != ARCH134_D1R5_RUFF_PATHS
            or spec.authority_check is not _arch134_d1r5_authority_check
            or spec.preflight is not None
            or spec.execute is not None
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_D1R5_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_D1R5_NAME) != "robinhood"
        ):
            failures.append("134-D1R5 source-only registration drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("134-D1R5 authority unavailable")
    return tuple(failures)


ARCH134_AUTH_TESTS: Final = (
    "tests/review_paper/test_alpaca_credential_staging_cleanup.py",
    "tests/review_paper/test_alpaca_authentication_qualification.py",
    "tests/review_paper/test_alpaca_credential_generation.py",
    "tests/review_paper/test_production_paper_runtime.py",
    "tests/review_paper/test_armed_production_paper_session.py",
    "tests/market_data/test_alpaca_daily_snapshot.py",
    "tests/market_data/test_alpaca_http.py",
    "tests/review_paper/test_supervised_deployment_qualification.py",
    "tests/review_paper/test_supervised_runtime_host_admission.py",
    "tests/review_paper/test_supervised_maintenance_rebind.py",
    "tests/review_paper/test_production_strategy_cycle.py",
    *COMMON_TESTS,
)
ARCH134_AUTH_RUFF_PATHS: Final = (
    *ARCH134_AUTH_SOURCE_PINS,
    *ARCH134_D1R4_PATHS,
    *ARCH134_D1R4R_PATHS,
    *ARCH134_AUTH_TESTS,
    *COMMON_RUFF_PATHS,
)


def _arch134_authentication_authority_check(repo_root: Path) -> tuple[str, ...]:
    """D1R4 source closure; credential/provider operations are never CI gates."""
    failures = list(_arch134_production_paper_runtime_authority_check(repo_root))
    forbidden = {
        "sqlite3",
        "ReviewPaperStore",
        "ArmedSessionStore",
        "run_armed_production_paper_session",
        "run",
        "Popen",
        "environ",
        "getenv",
        "CredWriteW",
        "CredDeleteW",
        "chmod",
        "chown",
        "icacls",
        "schtasks",
        "register_task",
        "evaluate",
        "prepare",
        "place_equity_order",
        "execute_paper",
        "eval",
        "exec",
        "__import__",
        "import_module",
    }
    try:
        if set(ARCH134_D1R4_SOURCE_PINS) != set(ARCH134_D1R4_PATHS):
            failures.append("134-D1R4 unreviewed source override")
        if set(ARCH134_D1R4_IMPORTS) != {
            p for p in ARCH134_D1R4_PATHS if p.startswith("src/")
        }:
            failures.append("134-D1R4 unreviewed import override")
        if set(ARCH134_D1R4R_SOURCE_PINS) != set(ARCH134_D1R4R_PATHS):
            failures.append("134-D1R4R unreviewed source override")
        if set(ARCH134_D1R4R_IMPORTS) != {
            p for p in ARCH134_D1R4R_PATHS if p.startswith("src/")
        }:
            failures.append("134-D1R4R unreviewed import override")
        if set(ARCH134_HIST2_TEST_PIN_OVERRIDES) != {
            "tests/scripts/certification_runner/test_profiles.py",
            "tests/review_paper/test_supervised_deployment_qualification.py",
            "tests/review_paper/test_supervised_runtime_host_admission.py",
            "tests/review_paper/test_supervised_maintenance_rebind.py",
            "tests/review_paper/test_production_strategy_cycle.py",
        }:
            failures.append("134-HIST2 unreviewed test pin override")
        for relative, pin in ARCH134_D1R4R_SOURCE_PINS.items():
            expected_pin = ARCH134_HIST2_TEST_PIN_OVERRIDES.get(relative, pin)
            expected_pin = _arch134_d1r5_test_pin(relative, expected_pin)
            expected_pin = _arch138_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139a_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b1_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b2_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140a18_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _canonical_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch134_d1r7_test_pin(relative, expected_pin)
            expected_pin = _arch142_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch142b_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch143_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch132_r3i_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _arch144_current_inventory_test_pin(relative, expected_pin)
            if _git_blob_sha1(repo_root / relative) != expected_pin:
                failures.append("134-D1R4R source drift: " + relative)
        for relative, pin in ARCH134_D1R4_SOURCE_PINS.items():
            expected_pin = ARCH134_D1R4R_SOURCE_PINS.get(relative, pin)
            expected_pin = ARCH134_HIST2_TEST_PIN_OVERRIDES.get(relative, expected_pin)
            expected_pin = _arch134_d1r5_test_pin(relative, expected_pin)
            expected_pin = _arch138_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139a_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b1_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b2_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140a18_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _canonical_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch134_d1r7_test_pin(relative, expected_pin)
            expected_pin = _arch142_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch142b_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch143_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch132_r3i_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _arch144_current_inventory_test_pin(relative, expected_pin)
            if _git_blob_sha1(repo_root / relative) != expected_pin:
                failures.append("134-D1R4 source drift: " + relative)
        if set(ARCH134_AUTH_CORRECTION_TEST_PINS) != {
            "tests/review_paper/test_armed_production_paper_session.py"
        }:
            failures.append("134-D1R3 unreviewed correction test override")
        for relative, pin in ARCH134_AUTH_CORRECTION_TEST_PINS.items():
            if _git_blob_sha1(repo_root / relative) != pin:
                failures.append("134-D1R3 correction test drift: " + relative)
        for relative, pin in ARCH134_AUTH_SOURCE_PINS.items():
            expected_pin = ARCH134_D1R4R_SOURCE_PINS.get(
                relative, ARCH134_D1R4_SOURCE_PINS.get(relative, pin)
            )
            expected_pin = ARCH134_HIST2_TEST_PIN_OVERRIDES.get(relative, expected_pin)
            expected_pin = _arch134_d1r5_test_pin(relative, expected_pin)
            expected_pin = _arch138_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139a_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b1_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch139b2_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch140a18_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _canonical_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch134_d1r7_test_pin(relative, expected_pin)
            expected_pin = _arch142_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch142b_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch143_current_inventory_test_pin(relative, expected_pin)
            expected_pin = _arch132_r3i_current_inventory_test_pin(
                relative, expected_pin
            )
            expected_pin = _arch144_current_inventory_test_pin(relative, expected_pin)
            if _git_blob_sha1(repo_root / relative) != expected_pin:
                failures.append("134-D1R3 source drift: " + relative)
        for relative, allowed in {
            **ARCH134_AUTH_IMPORTS,
            **ARCH134_D1R4_IMPORTS,
            **ARCH134_D1R4R_IMPORTS,
        }.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            imports = {
                n.module
                for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module
            } | {
                a.name
                for n in ast.walk(tree)
                if isinstance(n, ast.Import)
                for a in n.names
            }
            if imports != set(allowed):
                failures.append("134-D1R3 import closure drift: " + relative)
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
                n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
            }
            # The host alone needs the fixed argument-array Git admission helper.
            disallowed = forbidden - (
                {"run"} if relative.endswith("_host.py") else set()
            )
            if relative.endswith("alpaca_credential_native.py"):
                disallowed -= {"CredWriteW", "CredDeleteW"}
            if names & disallowed:
                failures.append("134-D1R3 forbidden authority: " + relative)
            if relative.endswith("alpaca_authentication_qualification.py"):
                calls = [
                    n
                    for n in ast.walk(tree)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "execute"
                ]
                if len(calls) != 1:
                    failures.append("134-D1R3 provider call budget drift")
        spec = _checkpoint_specs()[ARCH134_AUTH_NAME]
        if (
            spec.remote_branch != ARCH134_AUTH_BRANCH
            or spec.tests != ARCH134_AUTH_TESTS
            or spec.ruff_paths != ARCH134_AUTH_RUFF_PATHS
            or spec.authority_check is not _arch134_authentication_authority_check
            or spec.preflight is not None
            or spec.execute is not None
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_AUTH_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_AUTH_NAME) != "robinhood"
        ):
            failures.append("134-D1R3 source-only registration drift")
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("134-D1R3 workflow drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("134-D1R3 authority unavailable")
    return tuple(failures)


ARCH134_RUNTIME_ACL_NAME: Final = "arch134-production-paper-runtime-acl"
ARCH134_RUNTIME_ACL_SOURCE_PINS: Final = {
    "src/trading_bot/__init__.py": ("844df369681914646c4bb522bfc2c3fda615cf87"),
    "src/trading_bot/backtesting/__init__.py": (
        "8dee77f6ba26af8ee3ef06bf63981fcf3547882c"
    ),
    "src/trading_bot/backtesting/engine.py": (
        "f20a8fa25701f192ee6922c825281c1233f1d722"
    ),
    "src/trading_bot/backtesting/exceptions.py": (
        "439824b66042a5b48e9b6843409dbac8de03716f"
    ),
    "src/trading_bot/backtesting/models.py": (
        "78c5df9ee7d4181974516209962f8655695af26b"
    ),
    "src/trading_bot/backtesting/strategy.py": (
        "686ffe9b0eb0898cf49f0a8e471e2cfba9b85af5"
    ),
    "src/trading_bot/config.py": ("2e20646923701f402cd42d71e2b64aeef804f800"),
    "src/trading_bot/domain/__init__.py": ("646cc3901b3c83af2fbe528ca9b71d9582ad9592"),
    "src/trading_bot/domain/_validation.py": (
        "e6949f366e64f8c859b9bb75334f5534adf28aa3"
    ),
    "src/trading_bot/domain/enums.py": ("fd15367ec77cb9ac080ee1f40f9397e000b93f7b"),
    "src/trading_bot/domain/market.py": ("d5e059b78a5a876cf36dd2e9501a1f0321bcc35d"),
    "src/trading_bot/domain/orders.py": ("4029e1c8d2180b3a35673648339bed84aa2386f7"),
    "src/trading_bot/domain/positions.py": ("eb992456bfb6da38fd9026ce5d74f9f366397421"),
    "src/trading_bot/domain/proposals.py": ("4c221e2a9d4f887107cfa15e44fe1b3470eca64a"),
    "src/trading_bot/execution/__init__.py": (
        "143f8b481ff01e91f21f242a798ffed19a502183"
    ),
    "src/trading_bot/execution/engine.py": ("5c7a916901a4d2e2a35d6b9605995542b6fe004a"),
    "src/trading_bot/execution/exceptions.py": (
        "3f3d2836074589da6a6c66af087e9d4e1a35d2e4"
    ),
    "src/trading_bot/execution/models.py": ("388895fa3c193f8f7353f4ffa569b4e584f28e27"),
    "src/trading_bot/execution/paper_fill_application.py": (
        "1ad41675a1390a6b188620f3ad501a1134d0f47e"
    ),
    "src/trading_bot/execution/paper_fills.py": (
        "f55f1a401411bb35f866e6bdaeed282bc07b642d"
    ),
    "src/trading_bot/execution/paper_submission.py": (
        "f742fa1ccced5eb3a854e8a4566576eacfac16db"
    ),
    "src/trading_bot/execution/portfolio_orders.py": (
        "9ceb187ff61ee902ed4c9f86deed3b96e23eb7bb"
    ),
    "src/trading_bot/execution/state_fingerprints.py": (
        "1570e92c63c14e1c3c1ca7f11283a61720e45af3"
    ),
    "src/trading_bot/ledger/__init__.py": ("493bca4924ff88887997b8181042217c28231302"),
    "src/trading_bot/ledger/checkpoint_state.py": (
        "ada513596a1d30f68e45be56e2bf47b6bf8ca3c5"
    ),
    "src/trading_bot/ledger/exceptions.py": (
        "5f3d2e439747a6abf22eae473b38173f15fa9dc6"
    ),
    "src/trading_bot/ledger/initialization.py": (
        "e16d146e47a2c3bb7c80311aa0522259a986b50b"
    ),
    "src/trading_bot/ledger/ledger.py": ("ba2062cfcc87da65d90a4085bb0597eddfabd145"),
    "src/trading_bot/ledger/models.py": ("69ee12ba4c73698c5fe6f62f17cc97261941122d"),
    "src/trading_bot/market_calendar/__init__.py": (
        "be7457147506cf3bb7cf3719b97546c1f5c3e9b0"
    ),
    "src/trading_bot/market_calendar/calendar.py": (
        "0a9fbf47448eb3e7ae985b35f99f2c3f7568220b"
    ),
    "src/trading_bot/market_calendar/exceptions.py": (
        "7d8950c729ce6bf886bd4aad115d704dc83fa4a9"
    ),
    "src/trading_bot/market_calendar/models.py": (
        "1f09e0015d25651a09c8bc89dcd83d6ad0138d05"
    ),
    "src/trading_bot/market_calendar/nyse.py": (
        "b93a54bb2bb7ecac36cf5a116886c7fdfb2a2038"
    ),
    "src/trading_bot/market_data/__init__.py": (
        "3b5237e5f7a6bbfa34213f48db9aa8dc3f52fe66"
    ),
    "src/trading_bot/market_data/alpaca_daily_snapshot.py": (
        "82e30b6b486915acadb85c95faf538ee9d828451"
    ),
    "src/trading_bot/market_data/alpaca_http.py": (
        "a45037d821460d5fa0bab937f7085250890225d7"
    ),
    "src/trading_bot/market_data/csv_provider.py": (
        "b636804c53a631c2e308b89b15c5dbb51090aa57"
    ),
    "src/trading_bot/market_data/daily_snapshot_acceptance.py": (
        "0c8cbc498a84c90776ccc0bac19877f721921399"
    ),
    "src/trading_bot/market_data/daily_snapshot_identity.py": (
        "80618f77b5ce8e54b817ae8ccc665d717f199425"
    ),
    "src/trading_bot/market_data/daily_snapshot_models.py": (
        "5a194695a558668baef4cc8d4c4b0062d088c580"
    ),
    "src/trading_bot/market_data/daily_snapshot_provider.py": (
        "397de9c14be6297754e49703df117a07222d2f84"
    ),
    "src/trading_bot/market_data/daily_snapshot_serialization.py": (
        "16a707c515179a1c83a6e264912ea25066a41ecf"
    ),
    "src/trading_bot/market_data/daily_snapshot_verification.py": (
        "a913ab3c2fd35a2d111f691b571f28d4d37550cd"
    ),
    "src/trading_bot/market_data/exceptions.py": (
        "ce264675c48e5259cefdd58a319a0858dcef8d4d"
    ),
    "src/trading_bot/market_data/fingerprints.py": (
        "677f8a46910ff8c1892ba0929b0d8fab02b0698d"
    ),
    "src/trading_bot/market_data/models.py": (
        "b7eb7559eed7215e0cc3d917fc0857777093e273"
    ),
    "src/trading_bot/market_data/multi_provider.py": (
        "4357ac2742791e5893a682d77bbcb453e45938bc"
    ),
    "src/trading_bot/market_data/provider.py": (
        "3437be6a4a12e4641b9e75f983bd5e50385767a2"
    ),
    "src/trading_bot/portfolio/__init__.py": (
        "8d0b391158b7837f0d1d4b0f4f1211d5bd11e52d"
    ),
    "src/trading_bot/portfolio/exceptions.py": (
        "ca6743753b2dd7943f15953516068632fe5a7f38"
    ),
    "src/trading_bot/portfolio/historical_scenarios.py": (
        "3a1120f0c0647104a0515dbb85122ada9259039a"
    ),
    "src/trading_bot/portfolio/mean_cvar.py": (
        "4b97df92574797f49a454ee5196ddae29fab1d9d"
    ),
    "src/trading_bot/portfolio/models.py": ("3fcf379824ae4b727452aab5966da4363d463a12"),
    "src/trading_bot/portfolio/optimized_targets.py": (
        "4c8d617ba8d673ae04d0be70877f7e2d216e0a81"
    ),
    "src/trading_bot/portfolio/optimizer.py": (
        "936ed13a8f42581b46b84ecb252e9e67a6368ad5"
    ),
    "src/trading_bot/portfolio/scenarios.py": (
        "f29c94d5b2714379bca3a3765535d9a7360f03f6"
    ),
    "src/trading_bot/rebalancing/__init__.py": (
        "f504b1e6a076119f05ed6ce7ecd6985004531d17"
    ),
    "src/trading_bot/rebalancing/exceptions.py": (
        "124fd80fb06c477492f7b8126689899d39c890a6"
    ),
    "src/trading_bot/rebalancing/models.py": (
        "b1db577d886f83670e258e3ed5d3624b5b6a4865"
    ),
    "src/trading_bot/rebalancing/planner.py": (
        "659e3ab58cae4c74893660c715fd4e068ea34916"
    ),
    "src/trading_bot/rebalancing/proposals.py": (
        "72c3f5aacbab25c117528e5f16ed25613dc564a6"
    ),
    "src/trading_bot/review_paper/__init__.py": (
        "729418b848745fa32e43e8ed5dff108ecf545e2b"
    ),
    "src/trading_bot/review_paper/intent_bridge.py": (
        "ad732415540c6cba376e1ebfacefc4cf5d724eb2"
    ),
    "src/trading_bot/review_paper/models.py": (
        "e7d725c601b8a5ff16b0fffda4c31bace77f1e0a"
    ),
    "src/trading_bot/review_paper/production_paper_runtime_acl.py": (
        "a3e47fba3edff57c027181e985d72a17219393d3"
    ),
    "src/trading_bot/review_paper/risk_context.py": (
        "05cce6037f8550a688474697a779a3655a323aa7"
    ),
    "src/trading_bot/review_paper/store.py": (
        "c9875c20ec6d6b1fc788dd6649fe419aeae8fed8"
    ),
    "src/trading_bot/risk/__init__.py": ("2b38b6c92b0b7e2604340d56e63f91656da10f5a"),
    "src/trading_bot/risk/exceptions.py": ("e96140eb7c16c5164d36ee35efab600ef07db68e"),
    "src/trading_bot/risk/manager.py": ("0a13fcd15de2d46b7f76172f0f2ab541c2aa1e06"),
    "src/trading_bot/risk/models.py": ("29f3a0294e3d29029d62d8722db18fb315be64cc"),
    "src/trading_bot/risk/orchestration.py": (
        "f8aefdfbcbce09c50b687d0fcd7757fd51e5258c"
    ),
    "src/trading_bot/runtime/__init__.py": ("cbe6afa3bc006f1dc609985ef2dccf0198bbbfab"),
    "src/trading_bot/runtime/checkpointed_paper_cycle_report.py": (
        "01b37772312548d6859db99b5642701e1d8a9b37"
    ),
    "src/trading_bot/runtime/checkpointed_verified_snapshot_execution.py": (
        "55cad09ab18c08e37b6d5fc47d0ca4cb04afdc7e"
    ),
    "src/trading_bot/runtime/exceptions.py": (
        "403c827c38e2449fd8e1c17ee6a64bfef3a80dc9"
    ),
    "src/trading_bot/runtime/manual_paper_selected_c3_snapshot.py": (
        "4354c9cc0c6ec11f86e9894b8aeeb4c635a7b519"
    ),
    "src/trading_bot/runtime/manual_paper_strategy_plan.py": (
        "9692d39ece0d15d3da6ca83dd8a5f4b994510b12"
    ),
    "src/trading_bot/runtime/paper_account_checkpoint.py": (
        "5d6e383b4afa29945027e745ff14803c52ba653b"
    ),
    "src/trading_bot/runtime/paper_account_lineage_verification.py": (
        "f05aff9cea8da0cec7c517b938fc3be40f423ac1"
    ),
    "src/trading_bot/runtime/paper_account_successor_checkpoint.py": (
        "28822688addcf3346ebaafd31cc69038fffdd7ca"
    ),
    "src/trading_bot/runtime/paper_operation.py": (
        "616132888c03838ff0cd751a929b952c3c43043a"
    ),
    "src/trading_bot/runtime/paper_operation_execution_inputs.py": (
        "8f924181ca2725618c00b5dd72c11db8f9393abb"
    ),
    "src/trading_bot/runtime/paper_portfolio.py": (
        "da21260d8c5956f94bf3e86ab994005603cd4e16"
    ),
    "src/trading_bot/runtime/personal_desktop_paper_account_security.py": (
        "5604b89bf038e772518ab757ceec683c92f54711"
    ),
    "src/trading_bot/runtime/personal_desktop_paper_account_token.py": (
        "bbcb246e65065978e3bbdacb6f504aed8eebe21a"
    ),
    "src/trading_bot/runtime/personal_desktop_unattended_c3_history.py": (
        "c217ae6ea4bb7b5a748cb992cb0b69fb0a0dc301"
    ),
    "src/trading_bot/runtime/personal_desktop_unattended_daily_cycle_timing.py": (
        "797a33afd451cb06f403af7d7d5c8d405084d2c9"
    ),
    "src/trading_bot/runtime/personal_desktop_unattended_market_data_capture.py": (
        "48102d1ff82daf8a126d3cf49ac320bec7bdc6f4"
    ),
    "src/trading_bot/runtime/personal_desktop_unattended_paper_decision_intent.py": (
        "c22a069a286ed86b1dbb58e4060c00a0c6af983c"
    ),
    (
        "src/trading_bot/runtime/"
        "personal_desktop_unattended_paper_decision_publication.py"
    ): ("3d6ac4267dfe797322ec912891bee1d501808dd3"),
    ("src/trading_bot/runtime/personal_desktop_unattended_paper_decision_storage.py"): (
        "e74c1e389ab29aecf2208ba0fbad65941b91bf54"
    ),
    "src/trading_bot/runtime/personal_desktop_unattended_paper_invocation.py": (
        "7c4d8ebc51e906821e52e84028ec37f9cfb5453d"
    ),
    (
        "src/trading_bot/runtime/"
        "personal_desktop_unattended_paper_invocation_storage.py"
    ): ("a184158bcdde09ce0ea0f7aa9cdc5a31693535b5"),
    "src/trading_bot/runtime/personal_desktop_unattended_scheduler_contract.py": (
        "292b6abab453167f9803b70d7c9f0af86cbc5876"
    ),
    "src/trading_bot/runtime/schema/__init__.py": (
        "0aa21da6aa4ae5b8c6d1be2a3387a3f10a9711ed"
    ),
    "src/trading_bot/runtime/strategy_history_seed.py": (
        "6cc0670b169ed9afa430a8de87f36f2dd79fc695"
    ),
    "src/trading_bot/runtime/verified_c3_daily_bar_open.py": (
        "13653e1664e2213a124a43253508080b8a9b06ef"
    ),
    "src/trading_bot/runtime/verified_snapshot_execution.py": (
        "278e136c99823b542de4dc36a92fcfc1e62a4447"
    ),
    "src/trading_bot/runtime/verified_snapshot_preparation.py": (
        "663ab5b16fe67f9c118f73c07286f5f52d168946"
    ),
    "src/trading_bot/runtime/verified_snapshot_serialization.py": (
        "8243342acaedf9fa5d96ef1f897b31bf4e166b2d"
    ),
    "src/trading_bot/runtime/windows_authority.py": (
        "ad2b219ec4953013617c2411e6ae736e9683e898"
    ),
    "src/trading_bot/runtime/windows_authority_mutex.py": (
        "aa60edd9d19a0c31038fd27ffd618366f637402d"
    ),
    "src/trading_bot/runtime/windows_authority_schema.py": (
        "c28ab9ba03964d9183153fee3d8523ce882ca4d1"
    ),
    "src/trading_bot/runtime/windows_authority_security.py": (
        "8bb65aaee828314f3f4dc07b5d61f38c5bdea58e"
    ),
    "src/trading_bot/runtime/windows_authority_sqlite.py": (
        "6f557dbfb609288d16c74925dff5cd10220ffcdb"
    ),
    "src/trading_bot/runtime/windows_authority_validation.py": (
        "c4b72121b838f49749d623c8e2c2e37bce81e825"
    ),
    "src/trading_bot/runtime/windows_effectful_capture.py": (
        "637145e8bb2e1b763f3852cd819a1cd7e1880ef4"
    ),
    "src/trading_bot/runtime/windows_effectful_capture_native.py": (
        "f4d2ea972f60f4d39f059e6d6103965cc21b72d1"
    ),
    "src/trading_bot/runtime/windows_effectful_capture_protocol.py": (
        "29a973aab22afeddae45454d66e8a25347b91951"
    ),
    "src/trading_bot/runtime/windows_effectful_capture_service.py": (
        "44a09790af565f434f7325e9015b208aa0267a07"
    ),
    "src/trading_bot/runtime/windows_transactional_authority.py": (
        "a7aa0bdf441466702ad7ef26fcb00bd904b2d35c"
    ),
    "src/trading_bot/strategies/__init__.py": (
        "ce050824fd1e7dfb86a08f4ad15a607016d1afe2"
    ),
    "src/trading_bot/strategies/daily_decision.py": (
        "8df232b80047d913d43814e193d7a2788fc27116"
    ),
    "src/trading_bot/strategies/exceptions.py": (
        "180194bf44df19563f9586e314c437f60206241c"
    ),
    "src/trading_bot/strategies/history_seed.py": (
        "b20e41206c3d6d2e8eca6cbbd0dfef2e701b3177"
    ),
    "src/trading_bot/strategies/moving_average.py": (
        "2ce246a1305bf4514ee26bcb5113207e56f95cf8"
    ),
    "scripts/provision_production_paper_runtime_acl.py": (
        "9a890b523f4c330b5284271a51bcca34331bdf56"
    ),
    "tests/review_paper/test_production_paper_runtime_acl.py": (
        "a77edf7dfdaa2e6932594ae77601203f975bbff2"
    ),
}
ARCH134_RUNTIME_ACL_IMPORTS: Final = {
    "src/trading_bot/review_paper/production_paper_runtime_acl.py": (
        "__future__",
        "argparse",
        "collections.abc",
        "dataclasses",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "re",
        "stat",
        "subprocess",
        "sys",
        "trading_bot.runtime.windows_authority_security",
    ),
    "scripts/provision_production_paper_runtime_acl.py": (
        "pathlib",
        "sys",
        "trading_bot.review_paper.production_paper_runtime_acl",
    ),
}
ARCH134_RUNTIME_ACL_AST_PINS: Final = {
    "src/trading_bot/review_paper/production_paper_runtime_acl.py": (
        "39c5c8cd080d3328ee1ede03ec114893ff5acfa58f08e649ae2c9ae001225c0f"
    ),
    "scripts/provision_production_paper_runtime_acl.py": (
        "6d645af95e4500c581b5b42d3f7fc9ab680dd6d8645590b7b2fb4c8cfe5d8073"
    ),
    "src/trading_bot/runtime/windows_authority_security.py": (
        "1b034fc0ca0e066a0a9c8baf67c30415059141744ac0f981b1f35f1366f63f22"
    ),
}
ARCH134_RUNTIME_ACL_TESTS: Final = (
    *COMMON_TESTS,
    "tests/review_paper/test_production_paper_runtime_acl.py",
    "tests/review_paper/test_production_paper_runtime.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/strategies/test_production_strategy_contract.py",
    "tests/strategies/test_production_strategy_decision.py",
)
ARCH134_RUNTIME_ACL_RUFF_PATHS: Final = (
    *ARCH134_RUNTIME_ACL_SOURCE_PINS,
    *ARCH134_RUNTIME_ACL_TESTS,
    *COMMON_RUFF_PATHS,
)


def _arch134_runtime_acl_authority_check(repo_root: Path) -> tuple[str, ...]:
    """R2 is isolated: exact closure plus independent structural policy pins."""
    failures: list[str] = []
    forbidden = {
        "icacls",
        "takeown",
        "wmic",
        "chmod",
        "chown",
        "walk",
        "rglob",
        "SetNamedSecurityInfoW",
        "SetFileSecurityW",
        "register_task",
        "schtasks",
        "CredWriteW",
        "CredDeleteW",
        "call_tool",
        "place_equity_order",
        "cancel_equity_order",
        "connect",
        "urlopen",
        "eval",
        "exec",
        "__import__",
        "import_module",
        "environ",
        "getenv",
    }
    try:
        for relative, pin in ARCH134_RUNTIME_ACL_SOURCE_PINS.items():
            path = repo_root / relative
            if _git_blob_sha1(path) != pin:
                failures.append("134-D1Q-R2 source drift: " + relative)
            if relative not in ARCH134_RUNTIME_ACL_IMPORTS:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = {
                n.module
                for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module
            } | {
                a.name
                for n in ast.walk(tree)
                if isinstance(n, ast.Import)
                for a in n.names
            }
            if imports != set(ARCH134_RUNTIME_ACL_IMPORTS[relative]):
                failures.append("134-D1Q-R2 import closure drift: " + relative)
            names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
                n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
            }
            if names & forbidden:
                failures.append("134-D1Q-R2 forbidden authority: " + relative)
        for relative, pin in ARCH134_RUNTIME_ACL_AST_PINS.items():
            tree = ast.parse((repo_root / relative).read_text(encoding="utf-8"))
            if (
                hashlib.sha256(
                    ast.dump(tree, include_attributes=False).encode()
                ).hexdigest()
                != pin
            ):
                failures.append("134-D1Q-R2 structural authority drift: " + relative)
        # Keep R1 security mutation prohibitions and accepted executable pins intact.
        failures.extend(_arch134_production_paper_runtime_authority_check(repo_root))
        spec = _checkpoint_specs()[ARCH134_RUNTIME_ACL_NAME]
        if (
            spec.tests != ARCH134_RUNTIME_ACL_TESTS
            or spec.ruff_paths != ARCH134_RUNTIME_ACL_RUFF_PATHS
            or spec.remote_branch != "feature/robinhood-production-paper-runtime-acl"
            or spec.authority_check is not _arch134_runtime_acl_authority_check
            or spec.preflight is not None
            or spec.execute is not None
            or ACTIVE_CI_CHECKPOINTS[-1] != ARCH134_RUNTIME_ACL_NAME
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_RUNTIME_ACL_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_RUNTIME_ACL_NAME) != "robinhood"
        ):
            failures.append("134-D1Q-R2 registration authority drift")
        workflow = (
            repo_root / ".github/workflows/checkpoint-source-gates.yml"
        ).read_text(encoding="utf-8")
        if not _batch_workflow_is_reviewed(workflow):
            failures.append("134-D1Q-R2 workflow drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("134-D1Q-R2 authority unavailable")
    return tuple(failures)


# D1R7 is a final bounded successor overlay; every earlier dictionary stays frozen.
ARCH134_D1R7_NAME: Final = "arch134-d1r7-d1-session-authorization"
ARCH134_D1R7_BRANCH: Final = (
    "feature/robinhood-production-paper-d1-session-authorization"
)
ARCH134_D1R7_PATHS: Final = (
    "src/trading_bot/review_paper/d1_session_authorization.py",
    "src/trading_bot/review_paper/d1_session_authorization_host.py",
    "scripts/run_arch134_d1r7.py",
    "tests/review_paper/test_d1_session_authorization.py",
    "docs/architecture/134-d1r7-d1-session-authorization.md",
    "docs/validation/arch134-d1r7-d1-session-authorization.md",
)
ARCH134_D1R7_SOURCE_PINS: Final = {
    "src/trading_bot/review_paper/d1_session_authorization.py": (
        "acb7b549160737343020603faf094e65f477bc86"
    ),
    "src/trading_bot/review_paper/d1_session_authorization_host.py": (
        "dee1f1d978ddb72f9c3e78268c1401cfa91908c1"
    ),
    "scripts/run_arch134_d1r7.py": ("9e10464dacfe49c186b683fa107fc0fa1eb06dd8"),
    "tests/review_paper/test_d1_session_authorization.py": (
        "89985d9c7caf4275f14a23b9bae177f1d5d6bc35"
    ),
    "docs/architecture/134-d1r7-d1-session-authorization.md": (
        "7d8aeadc2dc983628026d89e813531191952a197"
    ),
    "docs/validation/arch134-d1r7-d1-session-authorization.md": (
        "80ba625fa95d991b09ce7640ea1477c783380e79"
    ),
}
ARCH134_D1R7_PREDECESSOR_TEST_PINS: Final = {
    "tests/gui/test_gui_a16_research_candidate_lifecycle_composition.py": (
        "29acabcaeed972637eccd8deae3d18983418292d"
    ),
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "90dabcf4aa057a0e1a9bf83c60b36d41e20d695f"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "a22e1cdbc48e76040082d9b21da72b1e4909c661"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "de7a77d3b0cf58fd9d5d58450181f8a1957fc7b2"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "e3a85fd7a71e9e83c89faf60bf25dea6d26a49d2"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "127db46d0211570727c2a9fb6118bb8f6a3b45d2"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "3c1fafd75920ba3346918fd3c44fb3a390e73678"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "292f4b3fa8fc3b667f6b60c6498da99aa8b687b5"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "99efdaa678ef63541f3c583d7c3bcb5f965c357b"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "b189e5ba3a792f7f0375b1df228cb706134e6fb6"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "ae8df8b5b3e32c84028ace2103f5b932635edea1"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "588d9d71bf2e6513754e7a0ec8e2c2627b435458"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "ea7ca9f8a0ec33449f70101e2e27aa72d2f27a39"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "36f5849f5df62682713860f053b87879b97d37cc"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "0093fdf868065d4dff932427b037b21f74f1bbff"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "4721a9ba5e2fc6a052ab7c6f1066b9ef924a7117"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "1b6447063b1401cf1d930b71e0ec703287623b77"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "6d5a7eaa49cbe6a9c67900d8e0ae99476cded215"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "4fae6dc080f6b9080025cc4dc2860725cbbaa1f8"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "d608cad8d3b5c4d52373e7b4ea4d5b0b23ad7748"
    ),
}
ARCH134_D1R7_TEST_PIN_OVERRIDES: Final = {
    "tests/gui/test_gui_a16_research_candidate_lifecycle_composition.py": (
        "cc08251a8d4738ddb03ab8e89e7a18d2efd35039"
    ),
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "b8cf5ec928475f95c657dd25f7b66ff4f9e0fa5a"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "47d3314696b0c3669dee26fe23faaaeb13b25b63"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "29b5b9a865021ddc55d45661cdeec3d344076856"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "cfe36905819f4cc0eb2272b8f4f0eb615905081d"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "712cd081e20442a0a83ad41c362ccc467283a5cc"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "76dd6c121c0e5cf3e83540bb08dce76a5ec04944"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "6847395a4bf937d64ef4d4cbf639706ae8dea97b"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "06206b41712a332cba80562f761fb2a5b9fdb272"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "e14511f1647628c95bccf44341d2760c5cd00e87"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "41be1b2eac4cff05298d8320761bb306157f7835"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "374edb6bd516e8d726eef71e9ce8d74797879b81"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "a5b36071b80c09abd6f5728e633cf09fd5e1230f"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "695a690c83bb6406688f9986314cab038bd3fff7"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "10fac0222eeac1d15487952f874735f171cdc7e0"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "1c27d44ce445d2cc17f8690196350c3972a01236"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "7bb200a28c2b46549550ba3a528ac43611c593c2"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "4fd45c4ddc734fbe0bc023ac05f84dbe9ec5c1ac"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "6acf5524e7a113d45e43a3e4d0d41e4495d4854a"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "c8f4911b0dc22f7daf0f71ef36de032ae7d9be44"
    ),
}
ARCH134_D1R7_PREDECESSOR_DIGESTS: Final = {
    "ARCH134_D1R5_TEST_PIN_OVERRIDES": (
        "6a95f4afc8640dfa0c672f5d77cda06ae57171c0199128a3ddd1d8b0debaac4a"
    ),
    "ARCH134_D1R5_SOURCE_PINS": (
        "370e14ff9a9453b4e001278921c3d1084c6ff94c8e34be76d430cb2b2adae575"
    ),
    "ARCH134_D1R5_IMPORTS": (
        "1e00ebdb9916d624591ecf41818a458dabf545cb8654c5e93f1e4e6e35402f03"
    ),
    "ARCH140A18_CURRENT_INVENTORY_TEST_PIN_OVERRIDES": (
        "00a2195aca3ca844209f27437ebce3e179cc2060aaa8c334999180c7b5b4094f"
    ),
    "ARCH134_D1R6_TEST_PIN_OVERRIDES": (
        "dfe1999400e0a6fdea245ccdd7d77a62e49aa1a169dbd42c0f89e2e88868ef4b"
    ),
    "ARCH134_D1R6_PREDECESSOR_DIGESTS": (
        "f17583c1a1e519c001acb9d3751ec3c0cdcbe1974589580c1836e75c3ac2e3bf"
    ),
    "ARCH134_D1R6_ADDITIONAL_PREDECESSOR_PINS": (
        "572d83c4a3938678894c0cb9072c182373fbce4f596c4b66c26b51f07e2089ab"
    ),
    "ARCH134_D1R6_SOURCE_PINS": (
        "bbf14101519464b7cd4495e32b5b402a845befd89e2ef1e9a1597efb0e236425"
    ),
    "CANONICAL_CURRENT_INVENTORY_TEST_PIN_OVERRIDES": (
        "1e00670b28dfbad915c34ec4657143deb40a0b7932207c302f9ea87ab12c7d51"
    ),
}
ARCH134_D1R7_PREDECESSOR_TEST_PINS_SHA256: Final = (
    "a07ac0ce7dbb1ae2ddab299f3839a778bd469b5e7aa3ff65f044942a7f895aaa"
)
ARCH134_D1R7_REVIEWED_TEST_PINS_SHA256: Final = (
    "15925f6d9c6e3e9407ac8893b36be95a1eb53b5704430ac94ac5471c5bfabb37"
)
ARCH134_D1R7_TESTS: Final = (
    "tests/review_paper/test_d1_session_authorization.py",
    *ARCH134_D1R6_TESTS,
)
ARCH134_D1R7_RUFF_PATHS: Final = (
    *(p for p in ARCH134_D1R7_PATHS if p.endswith(".py")),
    *ARCH134_D1R7_TEST_PIN_OVERRIDES,
    *ARCH134_D1R6_RUFF_PATHS,
)


def _arch134_d1r7_test_pin(relative: str, predecessor: str) -> str:
    """Apply only after historical/canonical resolution; reject all drift."""

    def digest(value: object) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    if (
        set(ARCH134_D1R7_TEST_PIN_OVERRIDES) != set(ARCH134_D1R7_PREDECESSOR_TEST_PINS)
        or any(
            not p.startswith("tests/") or not p.endswith(".py")
            for p in ARCH134_D1R7_TEST_PIN_OVERRIDES
        )
        or digest(ARCH134_D1R7_TEST_PIN_OVERRIDES)
        != ARCH134_D1R7_REVIEWED_TEST_PINS_SHA256
        or digest(ARCH134_D1R7_PREDECESSOR_TEST_PINS)
        != ARCH134_D1R7_PREDECESSOR_TEST_PINS_SHA256
    ):
        raise ValueError("D1R7 successor overlay drift")
    for name, expected in ARCH134_D1R7_PREDECESSOR_DIGESTS.items():
        if digest(globals()[name]) != expected:
            raise ValueError("D1R7 frozen predecessor drift")
    if relative in ARCH134_D1R7_TEST_PIN_OVERRIDES:
        if predecessor != ARCH134_D1R7_PREDECESSOR_TEST_PINS[relative]:
            raise ValueError("D1R7 predecessor resolution drift")
        predecessor = ARCH134_D1R7_TEST_PIN_OVERRIDES[relative]
    return _arch134_d1r8_test_pin(relative, predecessor)


def _arch134_d1r7_authority_check(repo_root: Path) -> tuple[str, ...]:
    """Source-only successor: real publication/effects have no runner surface."""
    failures = list(_arch134_d1r6_authority_check(repo_root))
    try:
        if set(ARCH134_D1R7_SOURCE_PINS) != set(ARCH134_D1R7_PATHS):
            failures.append("D1R7 source pin set drift")
        for relative, pin in ARCH134_D1R7_SOURCE_PINS.items():
            pin = _arch134_d1r8_test_pin(relative, pin)
            pin = _arch142_current_inventory_test_pin(relative, pin)
            pin = _arch142b_current_inventory_test_pin(relative, pin)
            pin = _arch143_current_inventory_test_pin(relative, pin)
            pin = _arch132_r3i_current_inventory_test_pin(relative, pin)
            pin = _arch144_current_inventory_test_pin(relative, pin)
            if _git_blob_sha1(repo_root / relative) != pin:
                failures.append("D1R7 source drift: " + relative)
        for relative, predecessor in ARCH134_D1R7_PREDECESSOR_TEST_PINS.items():
            expected = _arch134_d1r7_test_pin(relative, predecessor)
            expected = _arch142_current_inventory_test_pin(relative, expected)
            expected = _arch142b_current_inventory_test_pin(relative, expected)
            expected = _arch143_current_inventory_test_pin(relative, expected)
            expected = _arch132_r3i_current_inventory_test_pin(relative, expected)
            expected = _arch144_current_inventory_test_pin(relative, expected)
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append("D1R7 successor drift: " + relative)
        if not _batch_workflow_is_reviewed(
            (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                encoding="utf-8"
            )
        ):
            failures.append("D1R7 workflow fallback drift")
        spec = _checkpoint_specs()[ARCH134_D1R7_NAME]
        if (
            spec.remote_branch != ARCH134_D1R7_BRANCH
            or spec.tests != ARCH134_D1R7_TESTS
            or spec.ruff_paths != ARCH134_D1R7_RUFF_PATHS
            or spec.authority_check is not _arch134_d1r7_authority_check
            or spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_D1R7_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_D1R7_NAME) != "robinhood"
        ):
            failures.append("D1R7 source-only registration drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("D1R7 authority unavailable")
    return tuple(failures)


# D1R8 final test-only successor; all predecessor dictionaries/digests stay frozen.
ARCH134_D1R8_NAME: Final = "arch134-d1r8-d1-session-execution-consumer"
ARCH134_D1R8_BRANCH: Final = "feature/robinhood-production-paper-d1-session-execution"
ARCH134_D1R8_PATHS: Final = (
    "src/trading_bot/review_paper/d1_session_execution.py",
    "src/trading_bot/review_paper/d1_session_execution_store.py",
    "src/trading_bot/review_paper/d1_session_execution_host.py",
    "scripts/run_arch134_d1r8.py",
    "tests/review_paper/test_d1_session_execution.py",
    "docs/architecture/134-d1r8-d1-session-execution-consumer.md",
    "docs/validation/arch134-d1r8-d1-session-execution-consumer.md",
)
ARCH134_D1R8_SOURCE_PINS: Final = {
    "docs/architecture/134-d1r8-d1-session-execution-consumer.md": (
        "73c35a21bad24425465ccfc06f259775ee6cc733"
    ),
    "docs/validation/arch134-d1r8-d1-session-execution-consumer.md": (
        "b4d0750ac9ebfa7cf97f2cc575f09761a6591e94"
    ),
    "scripts/run_arch134_d1r8.py": ("cf79737d0c7c47d4ae2573c2f5670783021fbc5f"),
    "src/trading_bot/review_paper/d1_session_execution.py": (
        "cd58ab046feff22a9dfda19c2c861b97c20e4446"
    ),
    "src/trading_bot/review_paper/d1_session_execution_host.py": (
        "d6873fe3852aa14997156013500012f54fe7e28b"
    ),
    "src/trading_bot/review_paper/d1_session_execution_store.py": (
        "e35b0d528cecb396d5b7ffadcd158647becddba5"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "6dff9d532b3243af3c26afe403df694c591ca3cd"
    ),
}
ARCH134_D1R8_PREDECESSOR_TEST_PINS: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "b8cf5ec928475f95c657dd25f7b66ff4f9e0fa5a"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "47d3314696b0c3669dee26fe23faaaeb13b25b63"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "29b5b9a865021ddc55d45661cdeec3d344076856"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "cfe36905819f4cc0eb2272b8f4f0eb615905081d"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "712cd081e20442a0a83ad41c362ccc467283a5cc"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "76dd6c121c0e5cf3e83540bb08dce76a5ec04944"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "6847395a4bf937d64ef4d4cbf639706ae8dea97b"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "89985d9c7caf4275f14a23b9bae177f1d5d6bc35"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "06206b41712a332cba80562f761fb2a5b9fdb272"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "e14511f1647628c95bccf44341d2760c5cd00e87"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "41be1b2eac4cff05298d8320761bb306157f7835"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "374edb6bd516e8d726eef71e9ce8d74797879b81"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "a5b36071b80c09abd6f5728e633cf09fd5e1230f"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "695a690c83bb6406688f9986314cab038bd3fff7"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "10fac0222eeac1d15487952f874735f171cdc7e0"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "1c27d44ce445d2cc17f8690196350c3972a01236"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "7bb200a28c2b46549550ba3a528ac43611c593c2"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "4fd45c4ddc734fbe0bc023ac05f84dbe9ec5c1ac"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "6acf5524e7a113d45e43a3e4d0d41e4495d4854a"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "c8f4911b0dc22f7daf0f71ef36de032ae7d9be44"
    ),
}
ARCH134_D1R8_TEST_PIN_OVERRIDES: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "4091b4425ca93b7cb05dc28266f462df49133afa"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "e5d1f905262eedd5c058595a2b26d608430d7ef1"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "02289416a57bfb2c5a526cbb216575c0e5e0ad36"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "8e04de2cf1b8f2b9b53729734013c3ad1b1ea125"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "a9aca0091710ee9c69eeb07f043465b931171650"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "85af47ddb199756650b156922411fca4529337c7"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "365bd172d072bc39b8c20b9879bafed16a4c50c5"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "f68fb73613595c6c9d3dd7b2d47bf432bcb0127b"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "a8714f5408d9e57de4cc4c032a2171361ec632b2"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "bd9ac03cca10a6a33a88da1bbfb4c77c96fa86d4"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "aa105f40f1d5110bc94dd192313c551ee0d0b812"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "9bc515170e7e30813e40bb07b33331ecb770943e"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "7b4eaa4992f234eb279a9d30de69fa2d02cad3b1"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "7da67612dd8ff6c70cc7c38f018e51b9449e6262"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "65ad4cce1fafad4887a9fd743ae66a0508a2fe0a"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "810521c86df6241c2472c6ef4b8f2d034c66bce7"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "f564d92900f4265770884c970a22c98e60b18329"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "51f4404eacc526d8108921642b670f93290bcd33"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "b5918a61b2b446fa0702fa88e1c4d5fd12a9cd57"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "e7c3bce13f6a33c8276e9272d7920a13f78fc1fb"
    ),
}
ARCH134_D1R8_PREDECESSOR_DIGESTS: Final = {
    "ARCH134_ARMED_PAPER_RECOVERY_PIN_OVERRIDES": (
        "883a60d81edf1b71aa7daa376e6b8067e2833484254ba7bc1967c03b8fa587ba"
    ),
    "ARCH134_D1R5_SOURCE_PINS": (
        "370e14ff9a9453b4e001278921c3d1084c6ff94c8e34be76d430cb2b2adae575"
    ),
    "ARCH134_D1R6_SOURCE_PINS": (
        "bbf14101519464b7cd4495e32b5b402a845befd89e2ef1e9a1597efb0e236425"
    ),
    "ARCH134_D1R7_PREDECESSOR_DIGESTS": (
        "f65852b2a75e45d4637c2452b15ff8f2833c4a7f6ae1a1cea847b148dc50819f"
    ),
    "ARCH134_D1R7_PREDECESSOR_TEST_PINS": (
        "a07ac0ce7dbb1ae2ddab299f3839a778bd469b5e7aa3ff65f044942a7f895aaa"
    ),
    "ARCH134_D1R7_SOURCE_PINS": (
        "e194e364fb2278a8dfcaf789f5cc8c7d07b1785f4e68fa182f0982c93fa1274d"
    ),
    "ARCH134_D1R7_TEST_PIN_OVERRIDES": (
        "15925f6d9c6e3e9407ac8893b36be95a1eb53b5704430ac94ac5471c5bfabb37"
    ),
}
ARCH134_D1R8_PREDECESSOR_TEST_PINS_SHA256: Final = (
    "148bfa0eeefe831392380966a68e760b2c473f08101a1d3930b5186d3128c3b1"
)
ARCH134_D1R8_REVIEWED_TEST_PINS_SHA256: Final = (
    "2214e2c87a24034851f7a171cd80715849a8843dba3e402e6707e79e85b88853"
)
ARCH134_D1R8_TESTS: Final = (
    "tests/review_paper/test_d1_session_execution.py",
    *ARCH134_D1R7_TESTS,
)
ARCH134_D1R8_RUFF_PATHS: Final = (
    *(p for p in ARCH134_D1R8_PATHS if p.endswith(".py")),
    *ARCH134_D1R8_TEST_PIN_OVERRIDES,
    *ARCH134_D1R7_RUFF_PATHS,
)


def _arch134_d1r8_test_pin(relative: str, predecessor: str) -> str:
    def digest(value: object) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    if (
        set(ARCH134_D1R8_TEST_PIN_OVERRIDES) != set(ARCH134_D1R8_PREDECESSOR_TEST_PINS)
        or any(
            not p.startswith("tests/") or not p.endswith(".py")
            for p in ARCH134_D1R8_TEST_PIN_OVERRIDES
        )
        or digest(ARCH134_D1R8_TEST_PIN_OVERRIDES)
        != ARCH134_D1R8_REVIEWED_TEST_PINS_SHA256
        or digest(ARCH134_D1R8_PREDECESSOR_TEST_PINS)
        != ARCH134_D1R8_PREDECESSOR_TEST_PINS_SHA256
    ):
        raise ValueError("D1R8 successor overlay drift")
    for name, expected in ARCH134_D1R8_PREDECESSOR_DIGESTS.items():
        if digest(globals()[name]) != expected:
            raise ValueError("D1R8 frozen predecessor drift")
    if relative in ARCH134_D1R8_TEST_PIN_OVERRIDES:
        if predecessor != ARCH134_D1R8_PREDECESSOR_TEST_PINS[relative]:
            raise ValueError("D1R8 predecessor resolution drift")
        return ARCH134_D1R8_TEST_PIN_OVERRIDES[relative]
    return predecessor


def _arch134_d1r8_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = list(_arch134_d1r7_authority_check(repo_root))
    try:
        if set(ARCH134_D1R8_SOURCE_PINS) != set(ARCH134_D1R8_PATHS):
            failures.append("D1R8 source pin set drift")
        for relative, pin in ARCH134_D1R8_SOURCE_PINS.items():
            pin = _arch142_current_inventory_test_pin(relative, pin)
            pin = _arch142b_current_inventory_test_pin(relative, pin)
            pin = _arch143_current_inventory_test_pin(relative, pin)
            pin = _arch132_r3i_current_inventory_test_pin(relative, pin)
            pin = _arch144_current_inventory_test_pin(relative, pin)
            if _git_blob_sha1(repo_root / relative) != pin:
                failures.append("D1R8 source drift: " + relative)
        for relative, predecessor in ARCH134_D1R8_PREDECESSOR_TEST_PINS.items():
            expected = _arch134_d1r8_test_pin(relative, predecessor)
            expected = _arch142_current_inventory_test_pin(relative, expected)
            expected = _arch142b_current_inventory_test_pin(relative, expected)
            expected = _arch143_current_inventory_test_pin(relative, expected)
            expected = _arch132_r3i_current_inventory_test_pin(relative, expected)
            expected = _arch144_current_inventory_test_pin(relative, expected)
            if _git_blob_sha1(repo_root / relative) != expected:
                failures.append("D1R8 successor drift: " + relative)
        spec = _checkpoint_specs()[ARCH134_D1R8_NAME]
        if (
            spec.remote_branch != ARCH134_D1R8_BRANCH
            or spec.tests != ARCH134_D1R8_TESTS
            or spec.ruff_paths != ARCH134_D1R8_RUFF_PATHS
            or spec.authority_check is not _arch134_d1r8_authority_check
            or spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_D1R8_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_D1R8_NAME) != "robinhood"
        ):
            failures.append("D1R8 source-only registration drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("D1R8 authority unavailable")
    return tuple(failures)


ARCH134_F1_NAME: Final = "arch134-f1-five-session-soak"
ARCH134_F1_BRANCH: Final = "feature/robinhood-production-paper-134f-five-session-soak"
ARCH134_F1_TESTS: Final = (
    *COMMON_TESTS,
    "tests/review_paper/test_five_session_soak.py",
    "tests/review_paper/test_five_session_soak_child.py",
)
ARCH134_F1_PATHS: Final = (
    ".github/workflows/checkpoint-source-gates.yml",
    "docs/AI_TRADING_BOT_HANDOFF.md",
    "docs/PROJECT_STATUS.md",
    "docs/architecture/134-f1-five-session-live-paper-soak-authority.md",
    "docs/validation/arch134-f1-five-session-live-paper-soak-plan.md",
    "scripts/arch134_f1_bridge.py",
    "scripts/arch134_f1_d1r7_child.py",
    "scripts/arch134_f1_d1r8_child.py",
    "scripts/arch134_f1_scheduler.ps1",
    "scripts/run_arch134_f1.py",
    "scripts/run_test_certification.py",
    "src/trading_bot/experiments/research_strategy_paper_candidate_eligibility.py",
    "src/trading_bot/experiments/research_strategy_paper_evidence_verification.py",
    "src/trading_bot/review_paper/d1_session_authorization.py",
    "src/trading_bot/review_paper/d1_session_execution.py",
    "src/trading_bot/review_paper/d1_session_execution_store.py",
    "src/trading_bot/review_paper/five_session_soak.py",
    "src/trading_bot/review_paper/five_session_soak_child.py",
    "src/trading_bot/review_paper/five_session_soak_host.py",
    "src/trading_bot/review_paper/five_session_soak_store.py",
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py",
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py",
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
    "tests/review_paper/test_arch133_reprovision_reconciliation.py",
    "tests/review_paper/test_arch133_reprovision_recovery.py",
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
    "tests/review_paper/test_arch133_windows_rename_qualification.py",
    "tests/review_paper/test_d1_session_authorization.py",
    "tests/review_paper/test_d1_session_execution.py",
    "tests/review_paper/test_five_session_soak.py",
    "tests/review_paper/test_five_session_soak_child.py",
    "tests/review_paper/test_pre_market_wake_overnight.py",
    "tests/review_paper/test_production_strategy_cycle.py",
    "tests/review_paper/test_supervised_deployment_qualification.py",
    "tests/review_paper/test_supervised_maintenance_rebind.py",
    "tests/review_paper/test_supervised_release_installation.py",
    "tests/review_paper/test_supervised_runtime_host_admission.py",
    "tests/runtime/checkpoint_runner/helpers.py",
    "tests/runtime/checkpoint_runner/test_ci.py",
    "tests/runtime/checkpoint_runner/test_core.py",
    "tests/scripts/certification_runner/helpers.py",
    "tests/scripts/certification_runner/test_lanes.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/strategies/test_production_strategy_contract.py",
    "tests/strategies/test_production_strategy_decision.py",
)
ARCH134_F1_SOURCE_PINS: Final = {
    ".github/workflows/checkpoint-source-gates.yml": (
        "fe6aceac62721338eba4fcb40e2e7fde0d976e18"
    ),
    "docs/AI_TRADING_BOT_HANDOFF.md": ("3b8689b1cee9a5f546b1ca51a330af19a4a83cca"),
    "docs/PROJECT_STATUS.md": ("bc63399171fa94c139bfedacf2686e65195ac9dc"),
    "docs/architecture/134-f1-five-session-live-paper-soak-authority.md": (
        "72fdd7ede0ced6c51ed001e272296ff06aff3656"
    ),
    "docs/validation/arch134-f1-five-session-live-paper-soak-plan.md": (
        "6c2d704e60476168aa68e60192cd0a57d5c14513"
    ),
    "scripts/arch134_f1_bridge.py": ("1e35f11bf623ac333df37a45dc45e4a0fe282427"),
    "scripts/arch134_f1_d1r7_child.py": ("218b1d7b229025f993e0044ed0114d062d3cb38d"),
    "scripts/arch134_f1_d1r8_child.py": ("a89754f4589780c11d500743f229c7d6d2f66176"),
    "scripts/arch134_f1_scheduler.ps1": ("0cb85477f4958cce32c5b409be66e6013aa9f575"),
    "scripts/run_arch134_f1.py": ("3528cd65d77484d9ab58868b75699a6edcc9aa84"),
    "scripts/run_test_certification.py": ("3987e5708689de72a9604290d6e875c574c37c08"),
    "src/trading_bot/experiments/research_strategy_paper_candidate_eligibility.py": (
        "fd6b0ad650fb3fb97f587deb7cffc7286e685813"
    ),
    "src/trading_bot/experiments/research_strategy_paper_evidence_verification.py": (
        "915bdd84bee3ad0b57efcafb0a78da01fce94e66"
    ),
    "src/trading_bot/review_paper/d1_session_authorization.py": (
        "acb7b549160737343020603faf094e65f477bc86"
    ),
    "src/trading_bot/review_paper/d1_session_execution.py": (
        "cd58ab046feff22a9dfda19c2c861b97c20e4446"
    ),
    "src/trading_bot/review_paper/d1_session_execution_store.py": (
        "e35b0d528cecb396d5b7ffadcd158647becddba5"
    ),
    "src/trading_bot/review_paper/five_session_soak.py": (
        "9de15257fc9b6fe97e90314450b097849ff81320"
    ),
    "src/trading_bot/review_paper/five_session_soak_child.py": (
        "6afcdfe42ac1691bc477efcfb4764c227a0c1bc2"
    ),
    "src/trading_bot/review_paper/five_session_soak_host.py": (
        "9c3197005811ec0cd2b38f8ce4c7717f6c9e2108"
    ),
    "src/trading_bot/review_paper/five_session_soak_store.py": (
        "3813837e8d10ee2b19150405143704a7f03d474f"
    ),
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "9f503ac713d27a243c813e6c097a3f9643036ebb"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "f83282083640056fdc6d375e351a7090f50a7d0c"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "6a00303e094b8aa04462c01b2940aa07db8e0a09"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "07df0bfdbe105d244a811e1d47b06df345108346"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "0ec06381ed1b6953833ed6c32aa28ec8296b23cd"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "a7f9143e134da395a7dcbf0de0bdc8e485d489de"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "084af2e3c7fe579137ef841801751a5adf135d3c"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "df4ca610849e82e779f119ad2173023c5cbc8101"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "485c6a646c35241870299a304f8ae7a086a536e9"
    ),
    "tests/review_paper/test_five_session_soak.py": (
        "c0ee2404e8d79d58c8ba4d4470318a09792ace85"
    ),
    "tests/review_paper/test_five_session_soak_child.py": (
        "f789ed6273b6fa9d67d5a90d790c0f4c1f5b2ea4"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "278d0036c56ccba3b9270ebdb7890e01f4be8d2e"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "6fa506e3b6670811207b126c551102772566818c"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "93802bd4b08010fa77b2a3785d03452cf4ea51e7"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "082cf69f3eca0ebe924c3350ceaa09f74608469c"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "5a5108858c929b840d673f54a991865891ac21a2"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "dcb50173b387787bf9eb06fed03bd2599bfc1ca9"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "5d5ae606db41c356970a3c1e5192a547a1b93246"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "37c191db072f131123969aebff40d80371fd5e30"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "9997d36af38bd278c032cc01719680490cf3eeb1"
    ),
    "tests/scripts/certification_runner/helpers.py": (
        "6bc9e74d4f1e735aebd5d207990967e0d8ae9680"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "1eff7951e0c56d2721e74cf52ca5b397fffe3864"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "839c16571dc2185fe3d8bf86d5c54712527d349b"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "ff7d02a5cca084ce466cf52a2b88cd8b4b3b5347"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "c12dff7b401cdcc29a299aea4d2f5c77c5f0df84"
    ),
}
ARCH134_F1_PREDECESSOR_TEST_PINS: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "507979e4cfcf4b8140da2e234a2f5bbb2d6f4255"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "046864c016aa9089dfda9887759a53494f78ea25"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "d02acf70e9cfd31c581433eaba965abe8f475d0c"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "d3ae1d8289058ff692a102261711cc858e9bfe48"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "26e73bf98457310421b3460803c44d3a56ce7adb"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "bc78742d0854b5d0e03e9285b0d933e9e04d8969"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "866043e4a02d222e1f3fe6f88b131750d44bdfb0"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "112f2cbd5042d92b224ebccf99568c63ae0e92fb"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "44bb6d4606b7e7c89818db22bca912f973d57eab"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "e857d1b360e19109dc0caa7b3195227d2e05d59a"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "1b93c9568ce476c92b109a1b12e8bcdd67377d84"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "2a68830609ace599f5cc0eabe766692799a232c9"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "7697ae59eb5ef6eefc2c506679a1aad875f4a90a"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "810521c86df6241c2472c6ef4b8f2d034c66bce7"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "f564d92900f4265770884c970a22c98e60b18329"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "65ad4cce1fafad4887a9fd743ae66a0508a2fe0a"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "02289416a57bfb2c5a526cbb216575c0e5e0ad36"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "85af47ddb199756650b156922411fca4529337c7"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "365bd172d072bc39b8c20b9879bafed16a4c50c5"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "8e04de2cf1b8f2b9b53729734013c3ad1b1ea125"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "a9aca0091710ee9c69eeb07f043465b931171650"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "7b4eaa4992f234eb279a9d30de69fa2d02cad3b1"
    ),
}
ARCH134_F1_TEST_PIN_OVERRIDES: Final = {
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "9f503ac713d27a243c813e6c097a3f9643036ebb"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "f83282083640056fdc6d375e351a7090f50a7d0c"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "df4ca610849e82e779f119ad2173023c5cbc8101"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "485c6a646c35241870299a304f8ae7a086a536e9"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "278d0036c56ccba3b9270ebdb7890e01f4be8d2e"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "6fa506e3b6670811207b126c551102772566818c"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "93802bd4b08010fa77b2a3785d03452cf4ea51e7"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "082cf69f3eca0ebe924c3350ceaa09f74608469c"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "dcb50173b387787bf9eb06fed03bd2599bfc1ca9"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "839c16571dc2185fe3d8bf86d5c54712527d349b"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "ff7d02a5cca084ce466cf52a2b88cd8b4b3b5347"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "c12dff7b401cdcc29a299aea4d2f5c77c5f0df84"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "1eff7951e0c56d2721e74cf52ca5b397fffe3864"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "37c191db072f131123969aebff40d80371fd5e30"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "9997d36af38bd278c032cc01719680490cf3eeb1"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "5d5ae606db41c356970a3c1e5192a547a1b93246"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "6a00303e094b8aa04462c01b2940aa07db8e0a09"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "a7f9143e134da395a7dcbf0de0bdc8e485d489de"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "084af2e3c7fe579137ef841801751a5adf135d3c"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "07df0bfdbe105d244a811e1d47b06df345108346"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "0ec06381ed1b6953833ed6c32aa28ec8296b23cd"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "5a5108858c929b840d673f54a991865891ac21a2"
    ),
}
ARCH134_F1_TEST_PINS_SHA256: Final = (
    "e1e3f23a5325519a3929db5682fa89e006877ac5c495b9618a40b441fb0fc62f"
)
ARCH134_F1_RUFF_PATHS: Final = (
    "scripts/checkpoint_runner.py",
    *(p for p in ARCH134_F1_PATHS if p.endswith(".py")),
)


def _arch134_f1_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    before = ARCH134_F1_PREDECESSOR_TEST_PINS
    after = ARCH134_F1_TEST_PIN_OVERRIDES
    if (
        set(before) != set(after)
        or before
        != {
            **ARCH144_CURRENT_INVENTORY_TEST_PIN_OVERRIDES,
            (
                "tests/review_paper/"
                "test_arch133_closed_descendant_rename_qualification.py"
            ): (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py"
                ]
            ),
            "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py"
                ]
            ),
            "tests/review_paper/test_arch133_windows_rename_qualification.py": (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/review_paper/test_arch133_windows_rename_qualification.py"
                ]
            ),
            "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/review_paper/test_arch133_reprovision_reconciliation.py"
                ]
            ),
            "tests/review_paper/test_arch133_reprovision_recovery.py": (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/review_paper/test_arch133_reprovision_recovery.py"
                ]
            ),
            "tests/review_paper/test_supervised_release_installation.py": (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/review_paper/test_supervised_release_installation.py"
                ]
            ),
            "tests/runtime/checkpoint_runner/test_core.py": (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/runtime/checkpoint_runner/test_core.py"
                ]
            ),
            "tests/runtime/checkpoint_runner/helpers.py": (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/runtime/checkpoint_runner/helpers.py"
                ]
            ),
            "tests/runtime/checkpoint_runner/test_ci.py": (
                ARCH134_D1R8_TEST_PIN_OVERRIDES[
                    "tests/runtime/checkpoint_runner/test_ci.py"
                ]
            ),
        }
        or any(not p.startswith("tests/") for p in after)
        or any(
            len(v) != 40 or any(c not in "0123456789abcdef" for c in v)
            for v in after.values()
        )
        or hashlib.sha256(
            json.dumps([before, after], sort_keys=True).encode()
        ).hexdigest()
        != ARCH134_F1_TEST_PINS_SHA256
    ):
        raise ValueError("F1 current-inventory successor drift")
    if relative in after:
        if predecessor != before[relative]:
            raise ValueError("F1 current-inventory predecessor drift")
        return _arch144c_current_inventory_test_pin(relative, after[relative])
    return _arch144c_current_inventory_test_pin(relative, predecessor)


def _arch134_f1_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = []
    try:
        if set(ARCH134_F1_SOURCE_PINS) != set(ARCH134_F1_PATHS):
            failures.append("F1 source pin set drift")
        for relative, pin in ARCH134_F1_SOURCE_PINS.items():
            if _git_blob_sha1(repo_root / relative) != _arch144c_current_source_pin(
                relative, pin
            ):
                failures.append("F1 source drift: " + relative)
        for relative, pin in ARCH134_F1_PREDECESSOR_TEST_PINS.items():
            if _git_blob_sha1(
                repo_root / relative
            ) != _arch134_f1_current_inventory_test_pin(relative, pin):
                failures.append("F1 current-inventory drift: " + relative)
        spec = _checkpoint_specs()[ARCH134_F1_NAME]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != ARCH134_F1_BRANCH
            or spec.tests != ARCH134_F1_TESTS
            or spec.ruff_paths != ARCH134_F1_RUFF_PATHS
            or spec.authority_check is not _arch134_f1_authority_check
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_F1_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_F1_NAME) != "robinhood"
            or not _batch_workflow_is_reviewed(
                (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                    encoding="utf-8"
                )
            )
        ):
            failures.append("F1 source-only registration drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("F1 authority unavailable")
    return tuple(failures)


ARCH144C_NAME: Final = "arch144-c-f1-paper-evidence-admission"
ARCH144C_BRANCH: Final = (
    "feature/test-suite-arch144-c-f1-paper-evidence-admission-current"
)
ARCH144C_TESTS: Final = (
    *COMMON_TESTS,
    "tests/experiments/test_research_strategy_paper_candidate_eligibility.py",
    "tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py",
    "tests/experiments/test_research_strategy_f1_paper_evidence_verification.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/scripts/certification_runner/test_lanes.py",
)
ARCH144C_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "src/trading_bot/experiments/research_strategy_paper_candidate_eligibility_v2.py",
    "src/trading_bot/experiments/research_strategy_f1_paper_evidence_verification.py",
    "tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py",
    "tests/experiments/test_research_strategy_f1_paper_evidence_verification.py",
    "scripts/run_test_certification.py",
    "tests/scripts/certification_runner/test_lanes.py",
    "tests/scripts/certification_runner/test_profiles.py",
)
ARCH144C_PATHS: Final = (
    ("src/trading_bot/experiments/research_strategy_paper_candidate_eligibility_v2.py"),
    ("src/trading_bot/experiments/research_strategy_f1_paper_evidence_verification.py"),
    ("tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py"),
    ("tests/experiments/test_research_strategy_f1_paper_evidence_verification.py"),
    ("src/trading_bot/experiments/research_strategy_paper_candidate_eligibility.py"),
    ("src/trading_bot/experiments/research_strategy_paper_evidence_verification.py"),
    "src/trading_bot/review_paper/five_session_soak_store.py",
    "src/trading_bot/review_paper/five_session_soak.py",
    "src/trading_bot/review_paper/five_session_soak_child.py",
    "docs/architecture/144-c-f1-paper-evidence-admission.md",
    "docs/validation/arch144-c-f1-paper-evidence-admission-plan.md",
    "docs/AI_TRADING_BOT_HANDOFF.md",
    "docs/PROJECT_STATUS.md",
    "scripts/run_test_certification.py",
)
ARCH144C_SOURCE_PINS: Final = {
    (
        "src/trading_bot/experiments/"
        "research_strategy_paper_candidate_eligibility_v2.py"
    ): ("5facbd8e6350aba91ed5116c10d137c9c38a94ac"),
    (
        "src/trading_bot/experiments/"
        "research_strategy_f1_paper_evidence_verification.py"
    ): ("421feb247b1ff6f6ea82009f434e3a702c4bac90"),
    ("tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py"): (
        "bed21a65cb7b23a9f0c81ae9814a67aea376cda6"
    ),
    ("tests/experiments/test_research_strategy_f1_paper_evidence_verification.py"): (
        "b54bf149d7de89ebdefca87ef5ac1dadc2cc7c4d"
    ),
    ("src/trading_bot/experiments/research_strategy_paper_candidate_eligibility.py"): (
        "fd6b0ad650fb3fb97f587deb7cffc7286e685813"
    ),
    ("src/trading_bot/experiments/research_strategy_paper_evidence_verification.py"): (
        "915bdd84bee3ad0b57efcafb0a78da01fce94e66"
    ),
    "src/trading_bot/review_paper/five_session_soak_store.py": (
        "3813837e8d10ee2b19150405143704a7f03d474f"
    ),
    "src/trading_bot/review_paper/five_session_soak.py": (
        "9de15257fc9b6fe97e90314450b097849ff81320"
    ),
    "src/trading_bot/review_paper/five_session_soak_child.py": (
        "6afcdfe42ac1691bc477efcfb4764c227a0c1bc2"
    ),
    "docs/architecture/144-c-f1-paper-evidence-admission.md": (
        "29f7c7b11f7f026723022b4d71361f26dcdc6dd5"
    ),
    "docs/validation/arch144-c-f1-paper-evidence-admission-plan.md": (
        "9488dd302f9012af4e4fba291bb771711934ed56"
    ),
    "docs/AI_TRADING_BOT_HANDOFF.md": ("fb33dc10b30e1fbba836002c2271f386885f17b2"),
    "docs/PROJECT_STATUS.md": ("7cd434843b0942e3d51caf3a9791582b0aac7c4a"),
    "scripts/run_test_certification.py": ("1a1362efb4bf8694461e51cae9ad7d71b4797cbe"),
}
ARCH144C_PREDECESSOR_TEST_PINS: Final = {
    ("tests/review_paper/test_arch133_closed_descendant_rename_qualification.py"): (
        "6a00303e094b8aa04462c01b2940aa07db8e0a09"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "07df0bfdbe105d244a811e1d47b06df345108346"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "0ec06381ed1b6953833ed6c32aa28ec8296b23cd"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "a7f9143e134da395a7dcbf0de0bdc8e485d489de"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "084af2e3c7fe579137ef841801751a5adf135d3c"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "df4ca610849e82e779f119ad2173023c5cbc8101"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "485c6a646c35241870299a304f8ae7a086a536e9"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "278d0036c56ccba3b9270ebdb7890e01f4be8d2e"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "6fa506e3b6670811207b126c551102772566818c"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "93802bd4b08010fa77b2a3785d03452cf4ea51e7"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "082cf69f3eca0ebe924c3350ceaa09f74608469c"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "5a5108858c929b840d673f54a991865891ac21a2"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "dcb50173b387787bf9eb06fed03bd2599bfc1ca9"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "5d5ae606db41c356970a3c1e5192a547a1b93246"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "37c191db072f131123969aebff40d80371fd5e30"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "9997d36af38bd278c032cc01719680490cf3eeb1"
    ),
    "tests/scripts/certification_runner/helpers.py": (
        "6bc9e74d4f1e735aebd5d207990967e0d8ae9680"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "1eff7951e0c56d2721e74cf52ca5b397fffe3864"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "839c16571dc2185fe3d8bf86d5c54712527d349b"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "ff7d02a5cca084ce466cf52a2b88cd8b4b3b5347"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "c12dff7b401cdcc29a299aea4d2f5c77c5f0df84"
    ),
}
ARCH144C_TEST_PIN_OVERRIDES: Final = {
    ("tests/review_paper/test_arch133_closed_descendant_rename_qualification.py"): (
        "b94e0857df8617d6c64c1a2e5d634cf067ab5996"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "351e0f22db0b9f08a17f8c6b8d6a8cb0918970ac"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "c4ce9a36ae5d5f59b12bf665eea6893e7e671c7c"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "02253a169829ecd34520cc2a14c45232aef23496"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "ffcb9925026e754c01623ec3a8509202f71da2cf"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "d02f79c72fe8dc4a5df216f45d6f63f093b4c1f5"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "ad02aa9d7674f7309826062cad8dc5d5e703c091"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "6f4a6f473d546470207a2bdcc7adf0cd1490e227"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "08e6ec14fd6651d880380af4c7a8447739f7f84a"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "8f1f364538771936fddc318302dacf39d8b0ce19"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "5101c2003da3c642c8110a43d8c7c8d43c525d1a"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "cd8b750c23876476f4ff18c63da33ce5944914e2"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "300ba87491b4bf0d5faf4ce985043968a053a5c1"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "a4cac2aa60397f1a3de3b6ad623855aca3a54f38"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "c5668bcb6146cbd14152d90a79df8ef86dc16189"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "eacf80ebd36a7cca06d9f293670686d9f412e9ec"
    ),
    "tests/scripts/certification_runner/helpers.py": (
        "a2b1baf6558e8a922f37c42ae982c04154cd8e65"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "7f93948cd1d1b154ed7dc82c82c339dd7d2dc099"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "7bef72906d3a063a8d18cd29af02f81c9666c0af"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "b8c5d893245bb3051649205e595b42328072a260"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "008e1729075c16573db634329d0f7cd14baec4c4"
    ),
}
ARCH144C_TEST_PINS_SHA256: Final = (
    "f32b912083f75cdc38b4c1e7ea07612446145442ecf9154f84d856a361524623"
)
ARCH144C_PREDECESSOR_SOURCE_PINS: Final = {
    "docs/AI_TRADING_BOT_HANDOFF.md": ("3b8689b1cee9a5f546b1ca51a330af19a4a83cca"),
    "docs/PROJECT_STATUS.md": ("bc63399171fa94c139bfedacf2686e65195ac9dc"),
    "docs/architecture/134-f1-five-session-live-paper-soak-authority.md": (
        "72fdd7ede0ced6c51ed001e272296ff06aff3656"
    ),
    "docs/validation/arch134-f1-five-session-live-paper-soak-plan.md": (
        "6c2d704e60476168aa68e60192cd0a57d5c14513"
    ),
    "scripts/run_test_certification.py": ("3987e5708689de72a9604290d6e875c574c37c08"),
}
ARCH144C_SOURCE_PIN_OVERRIDES: Final = {
    "docs/AI_TRADING_BOT_HANDOFF.md": ("fb33dc10b30e1fbba836002c2271f386885f17b2"),
    "docs/PROJECT_STATUS.md": ("7cd434843b0942e3d51caf3a9791582b0aac7c4a"),
    "docs/architecture/134-f1-five-session-live-paper-soak-authority.md": (
        "f5e53dfcd9f97f3b49b183edf815d19faa17ed13"
    ),
    "docs/validation/arch134-f1-five-session-live-paper-soak-plan.md": (
        "402fbfdfe6cbf9eb2caa691b0fd924e6fb7d2943"
    ),
    "scripts/run_test_certification.py": ("1a1362efb4bf8694461e51cae9ad7d71b4797cbe"),
}


def _arch144c_current_inventory_test_pin(relative: str, predecessor: str) -> str:
    before = ARCH144C_PREDECESSOR_TEST_PINS
    after = ARCH144C_TEST_PIN_OVERRIDES
    if (
        set(before) != set(after)
        or any(not p.startswith("tests/") for p in after)
        or any(
            ARCH134_F1_TEST_PIN_OVERRIDES.get(p, ARCH134_F1_SOURCE_PINS.get(p)) != v
            for p, v in before.items()
        )
        or hashlib.sha256(
            json.dumps([before, after], sort_keys=True).encode()
        ).hexdigest()
        != ARCH144C_TEST_PINS_SHA256
    ):
        raise ValueError("144-C current-inventory successor drift")
    if relative in after:
        if predecessor != before[relative]:
            raise ValueError("144-C current-inventory predecessor drift")
        return _arch134_f2_current_pin(relative, after[relative])
    return _arch134_f2_current_pin(relative, predecessor)


def _arch144c_current_source_pin(relative: str, predecessor: str) -> str:
    # Only current docs/timing metadata move; accepted executable pins stay fixed.
    before = ARCH144C_PREDECESSOR_SOURCE_PINS
    after = ARCH144C_SOURCE_PIN_OVERRIDES
    allowed = {
        "docs/AI_TRADING_BOT_HANDOFF.md",
        "docs/PROJECT_STATUS.md",
        "docs/architecture/134-f1-five-session-live-paper-soak-authority.md",
        "docs/validation/arch134-f1-five-session-live-paper-soak-plan.md",
        "scripts/run_test_certification.py",
    }
    if set(before) != allowed or set(after) != allowed:
        raise ValueError("144-C source metadata override drift")
    if any(ARCH134_F1_SOURCE_PINS.get(p) != v for p, v in before.items()):
        raise ValueError("144-C source metadata predecessor drift")
    if relative.startswith("tests/"):
        return _arch144c_current_inventory_test_pin(relative, predecessor)
    if relative in after:
        if predecessor != before[relative]:
            raise ValueError("144-C wrong source metadata predecessor")
        return _arch134_f2_current_pin(relative, after[relative])
    return _arch134_f2_current_pin(relative, predecessor)


def _arch144c_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = []
    try:
        for relative, pin in ARCH144C_SOURCE_PINS.items():
            if _git_blob_sha1(repo_root / relative) != _arch134_f2_current_pin(
                relative, pin
            ):
                failures.append("144-C source drift: " + relative)
        if not ARCH144C_SOURCE_PINS or set(ARCH144C_SOURCE_PINS) != set(ARCH144C_PATHS):
            failures.append("144-C missing source pins")
        for relative, pin in ARCH144C_PREDECESSOR_TEST_PINS.items():
            if _git_blob_sha1(
                repo_root / relative
            ) != _arch144c_current_inventory_test_pin(relative, pin):
                failures.append("144-C current-inventory drift: " + relative)
        spec = _checkpoint_specs()[ARCH144C_NAME]
        if (
            spec.preflight is not None
            or spec.execute is not None
            or spec.remote_head_env is not None
            or spec.remote_branch != ARCH144C_BRANCH
            or spec.tests != ARCH144C_TESTS
            or spec.ruff_paths != ARCH144C_RUFF_PATHS
            or spec.authority_check is not _arch144c_authority_check
            or ACTIVE_CI_CHECKPOINTS.count(ARCH144C_NAME) != 1
            or ARCH144C_NAME in CI_CERTIFICATION_PROFILES
            or not _batch_workflow_is_reviewed(
                (repo_root / ".github/workflows/checkpoint-source-gates.yml").read_text(
                    encoding="utf-8"
                )
            )
        ):
            failures.append("144-C source-only registration drift")
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("144-C authority unavailable")
    return tuple(failures)


ARCH134_F2_NAME: Final = "arch134-f2-five-session-soak-readiness"
ARCH134_F2_BRANCH: Final = (
    "feature/robinhood-production-paper-134f2-five-session-soak-readiness"
)
ARCH134_F2_TESTS: Final = (
    *ARCH134_F1_TESTS,
    "tests/review_paper/test_five_session_soak_readiness.py",
    "tests/scripts/certification_runner/test_profiles.py",
    "tests/scripts/certification_runner/test_lanes.py",
)
ARCH134_F2_RUFF_PATHS: Final = (
    *COMMON_RUFF_PATHS,
    "src/trading_bot/review_paper/five_session_soak_readiness.py",
    *ARCH134_F2_TESTS,
    "scripts/run_test_certification.py",
    "tests/scripts/certification_runner/helpers.py",
)
ARCH134_F2_PREDECESSOR_PINS: Final = {
    "docs/AI_TRADING_BOT_HANDOFF.md": ("fb33dc10b30e1fbba836002c2271f386885f17b2"),
    "docs/PROJECT_STATUS.md": ("7cd434843b0942e3d51caf3a9791582b0aac7c4a"),
    "scripts/run_test_certification.py": ("1a1362efb4bf8694461e51cae9ad7d71b4797cbe"),
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "9f503ac713d27a243c813e6c097a3f9643036ebb"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "f83282083640056fdc6d375e351a7090f50a7d0c"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "b94e0857df8617d6c64c1a2e5d634cf067ab5996"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "351e0f22db0b9f08a17f8c6b8d6a8cb0918970ac"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "c4ce9a36ae5d5f59b12bf665eea6893e7e671c7c"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "02253a169829ecd34520cc2a14c45232aef23496"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "ffcb9925026e754c01623ec3a8509202f71da2cf"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "d02f79c72fe8dc4a5df216f45d6f63f093b4c1f5"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "ad02aa9d7674f7309826062cad8dc5d5e703c091"
    ),
    "tests/review_paper/test_five_session_soak.py": (
        "c0ee2404e8d79d58c8ba4d4470318a09792ace85"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "6f4a6f473d546470207a2bdcc7adf0cd1490e227"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "08e6ec14fd6651d880380af4c7a8447739f7f84a"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "8f1f364538771936fddc318302dacf39d8b0ce19"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "5101c2003da3c642c8110a43d8c7c8d43c525d1a"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "cd8b750c23876476f4ff18c63da33ce5944914e2"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "300ba87491b4bf0d5faf4ce985043968a053a5c1"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "a4cac2aa60397f1a3de3b6ad623855aca3a54f38"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "c5668bcb6146cbd14152d90a79df8ef86dc16189"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "eacf80ebd36a7cca06d9f293670686d9f412e9ec"
    ),
    "tests/scripts/certification_runner/helpers.py": (
        "a2b1baf6558e8a922f37c42ae982c04154cd8e65"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "7f93948cd1d1b154ed7dc82c82c339dd7d2dc099"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "7bef72906d3a063a8d18cd29af02f81c9666c0af"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "b8c5d893245bb3051649205e595b42328072a260"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "008e1729075c16573db634329d0f7cd14baec4c4"
    ),
}
ARCH134_F2_PIN_OVERRIDES: Final = {
    "docs/AI_TRADING_BOT_HANDOFF.md": ("7e902ef66b67e5d796e910d5ab90119c99a9dc98"),
    "docs/PROJECT_STATUS.md": ("fc8b193738d3a623da74ed7b739e280786125d48"),
    "scripts/run_test_certification.py": ("3a09acf61fd9b5e54d942564cc2a99d9060e37de"),
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "456e59868db61becb579e153db06b56f6e7c4992"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "085746772a6e7d9f76f0bb75df07b67920dd44da"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "81cf462bafd937bad63b35055e73dee31037b56a"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "cf51d08220ab6c7436e8a2d919db6af5c9f6d31e"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "09f7cf0ebb18cf5617fbd46a53b23e476e2169ab"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "7512a93e8d0e83be3147ebeccb75ec35b8a5202b"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "f586a8b44582f47cc5f49a61ad246a19b5ffa59b"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "cdeb8b458c5638eac5d30b05263ee36572869759"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "47e1d208748665e85012a794925f9445bd481273"
    ),
    "tests/review_paper/test_five_session_soak.py": (
        "7a21d77e65cbf0ba719b5aae8bf3069636c75400"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "c1449078efc47b15f3cd5112bf96b0c9a0d86356"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "7e67d6dd98d4db5a5651302a86ac7468d6deda58"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "bbbadd5b7edafa84d0899911a7ff04df9dae868f"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "420945abd795e13e09a9a165f864e0efd0ff21ec"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "4c2b77217e0905de6113a7f5e4be6a95420b4440"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "08fb5278f463ef99a659b529ef8c8801d10e963b"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "61489f21c8c9e5d9e69696018e3b0e058f9d9d95"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "494deee45f7a8de75dcca3e7ee6b7a3468ea8715"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "5a1db4f1151ace1828406ff1d3defe676b9aaf91"
    ),
    "tests/scripts/certification_runner/helpers.py": (
        "a9902b03775563c60b9da56b4d1273d68e15b765"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "c71c063039cc993bdd52b19eaf26c8a32bdb189d"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "1e52ccb8dfa0d00a5f312ed1db6b7e878724d97b"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "2aa393208e25b0bdc67bcbbfa794242f9b3eab56"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "57f13856cce37926a45d6d442fdbb97c4680e539"
    ),
}
ARCH134_F2_SOURCE_PINS: Final = {
    "docs/AI_TRADING_BOT_HANDOFF.md": ("7e902ef66b67e5d796e910d5ab90119c99a9dc98"),
    "docs/PROJECT_STATUS.md": ("fc8b193738d3a623da74ed7b739e280786125d48"),
    "docs/architecture/134-f2-five-session-live-paper-soak-readiness.md": (
        "a43201a61f25c4af3e5219c3bd939f8b735f97c5"
    ),
    "docs/validation/arch134-f2-five-session-live-paper-soak-readiness.md": (
        "3d51e7a33df87e12fd2e995c387c3f72d170bc4b"
    ),
    "scripts/run_test_certification.py": ("3a09acf61fd9b5e54d942564cc2a99d9060e37de"),
    "src/trading_bot/review_paper/five_session_soak_readiness.py": (
        "6b9196a7812bf854ac55d443cbd3d34b979de2d8"
    ),
    "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py": (
        "456e59868db61becb579e153db06b56f6e7c4992"
    ),
    "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py": (
        "085746772a6e7d9f76f0bb75df07b67920dd44da"
    ),
    "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py": (
        "81cf462bafd937bad63b35055e73dee31037b56a"
    ),
    "tests/review_paper/test_arch133_reprovision_reconciliation.py": (
        "cf51d08220ab6c7436e8a2d919db6af5c9f6d31e"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery.py": (
        "09f7cf0ebb18cf5617fbd46a53b23e476e2169ab"
    ),
    "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py": (
        "7512a93e8d0e83be3147ebeccb75ec35b8a5202b"
    ),
    "tests/review_paper/test_arch133_windows_rename_qualification.py": (
        "f586a8b44582f47cc5f49a61ad246a19b5ffa59b"
    ),
    "tests/review_paper/test_d1_session_authorization.py": (
        "cdeb8b458c5638eac5d30b05263ee36572869759"
    ),
    "tests/review_paper/test_d1_session_execution.py": (
        "47e1d208748665e85012a794925f9445bd481273"
    ),
    "tests/review_paper/test_five_session_soak.py": (
        "7a21d77e65cbf0ba719b5aae8bf3069636c75400"
    ),
    "tests/review_paper/test_five_session_soak_readiness.py": (
        "2507819f2cd37180432720879663fecec6bbcf44"
    ),
    "tests/review_paper/test_pre_market_wake_overnight.py": (
        "c1449078efc47b15f3cd5112bf96b0c9a0d86356"
    ),
    "tests/review_paper/test_production_strategy_cycle.py": (
        "7e67d6dd98d4db5a5651302a86ac7468d6deda58"
    ),
    "tests/review_paper/test_supervised_deployment_qualification.py": (
        "bbbadd5b7edafa84d0899911a7ff04df9dae868f"
    ),
    "tests/review_paper/test_supervised_maintenance_rebind.py": (
        "420945abd795e13e09a9a165f864e0efd0ff21ec"
    ),
    "tests/review_paper/test_supervised_release_installation.py": (
        "4c2b77217e0905de6113a7f5e4be6a95420b4440"
    ),
    "tests/review_paper/test_supervised_runtime_host_admission.py": (
        "08fb5278f463ef99a659b529ef8c8801d10e963b"
    ),
    "tests/runtime/checkpoint_runner/helpers.py": (
        "61489f21c8c9e5d9e69696018e3b0e058f9d9d95"
    ),
    "tests/runtime/checkpoint_runner/test_ci.py": (
        "494deee45f7a8de75dcca3e7ee6b7a3468ea8715"
    ),
    "tests/runtime/checkpoint_runner/test_core.py": (
        "5a1db4f1151ace1828406ff1d3defe676b9aaf91"
    ),
    "tests/scripts/certification_runner/helpers.py": (
        "a9902b03775563c60b9da56b4d1273d68e15b765"
    ),
    "tests/scripts/certification_runner/test_lanes.py": (
        "c71c063039cc993bdd52b19eaf26c8a32bdb189d"
    ),
    "tests/scripts/certification_runner/test_profiles.py": (
        "1e52ccb8dfa0d00a5f312ed1db6b7e878724d97b"
    ),
    "tests/strategies/test_production_strategy_contract.py": (
        "2aa393208e25b0bdc67bcbbfa794242f9b3eab56"
    ),
    "tests/strategies/test_production_strategy_decision.py": (
        "57f13856cce37926a45d6d442fdbb97c4680e539"
    ),
}
ARCH134_F2_PINS_SHA256: Final = (
    "52cd7342e6ed9caa186b3bd37b88046bb08e6321232b299bc4834c89c8bafb57"
)


def _arch134_f2_current_pin(relative: str, predecessor: str) -> str:
    before = ARCH134_F2_PREDECESSOR_PINS
    after = ARCH134_F2_PIN_OVERRIDES
    allowed = {
        "docs/AI_TRADING_BOT_HANDOFF.md",
        "docs/PROJECT_STATUS.md",
        "scripts/run_test_certification.py",
        "tests/gui/test_gui_a17_research_candidate_lifecycle_audit_qt.py",
        "tests/gui/test_gui_a18_research_candidate_lifecycle_boundary_map.py",
        "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
        "tests/review_paper/test_arch133_reprovision_reconciliation.py",
        "tests/review_paper/test_arch133_reprovision_recovery.py",
        "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
        "tests/review_paper/test_arch133_windows_rename_qualification.py",
        "tests/review_paper/test_d1_session_authorization.py",
        "tests/review_paper/test_d1_session_execution.py",
        "tests/review_paper/test_five_session_soak.py",
        "tests/review_paper/test_pre_market_wake_overnight.py",
        "tests/review_paper/test_production_strategy_cycle.py",
        "tests/review_paper/test_supervised_deployment_qualification.py",
        "tests/review_paper/test_supervised_maintenance_rebind.py",
        "tests/review_paper/test_supervised_release_installation.py",
        "tests/review_paper/test_supervised_runtime_host_admission.py",
        "tests/runtime/checkpoint_runner/helpers.py",
        "tests/runtime/checkpoint_runner/test_ci.py",
        "tests/runtime/checkpoint_runner/test_core.py",
        "tests/scripts/certification_runner/helpers.py",
        "tests/scripts/certification_runner/test_lanes.py",
        "tests/scripts/certification_runner/test_profiles.py",
        "tests/strategies/test_production_strategy_contract.py",
        "tests/strategies/test_production_strategy_decision.py",
    }
    if (
        set(before) != allowed
        or set(after) != allowed
        or hashlib.sha256(
            json.dumps([before, after], sort_keys=True).encode()
        ).hexdigest()
        != ARCH134_F2_PINS_SHA256
    ):
        raise ValueError("F2 metadata successor rejected")
    if relative in after:
        if predecessor != before[relative]:
            raise ValueError("F2 metadata predecessor rejected")
        return after[relative]
    return predecessor


def _arch134_f2_authority_check(repo_root: Path) -> tuple[str, ...]:
    failures = []
    try:
        from trading_bot.review_paper import five_session_soak_readiness as readiness

        for relative, pin in ARCH134_F2_SOURCE_PINS.items():
            if _git_blob_sha1(repo_root / relative) != pin:
                failures.append("F2 source drift: " + relative)
        required = set(ARCH134_F2_PIN_OVERRIDES) | {
            "src/trading_bot/review_paper/five_session_soak_readiness.py",
            "tests/review_paper/test_five_session_soak_readiness.py",
            "docs/architecture/134-f2-five-session-live-paper-soak-readiness.md",
            "docs/validation/arch134-f2-five-session-live-paper-soak-readiness.md",
        }
        if set(ARCH134_F2_SOURCE_PINS) != required:
            failures.append("F2 pin inventory rejected")
        for relative, pin in readiness.F1_BLOBS.items():
            if _git_blob_sha1(repo_root / relative) != pin:
                failures.append("F2 frozen F1 drift: " + relative)
        spec = _checkpoint_specs()[ARCH134_F2_NAME]
        if (
            spec.preflight is not _arch134_f2_preflight
            or spec.execute is not None
            or spec.remote_branch != ARCH134_F2_BRANCH
            or spec.remote_head_env is not None
            or spec.tests != ARCH134_F2_TESTS
            or spec.ruff_paths != ARCH134_F2_RUFF_PATHS
            or spec.authority_check is not _arch134_f2_authority_check
            or ACTIVE_CI_CHECKPOINTS.count(ARCH134_F2_NAME) != 1
            or CI_CERTIFICATION_PROFILES.get(ARCH134_F2_NAME) != "robinhood"
        ):
            failures.append("F2 registration rejected")
        failures.extend(_arch134_f1_authority_check(repo_root))
        failures.extend(_arch144c_authority_check(repo_root))
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, KeyError):
        failures.append("F2 authority unavailable")
    return tuple(failures)


def _arch134_f2_preflight() -> dict[str, object]:
    from trading_bot.review_paper.five_session_soak_readiness import preflight

    return preflight()


def _checkpoint_specs() -> dict[str, CheckpointSpec]:
    parent_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_parent_acl_repair.py",
        "tests/runtime/test_d10_arch128_r4_operator.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_replacement.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_protected_deployment.py",
        "tests/runtime/test_d10_protected_replacement.py",
        "tests/runtime/test_d10_protected_replacement_windows.py",
        "tests/runtime/test_windows_authority.py",
    )
    parent_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_parent_acl_repair.py",
        "tests/runtime/test_d10_arch128_parent_acl_repair.py",
        "scripts/d10_arch128_r4_operator.py",
        "tests/runtime/test_d10_arch128_r4_operator.py",
        "scripts/d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "scripts/d10_arch128_r4_replacement.py",
        "tests/runtime/test_d10_arch128_r4_replacement.py",
        "scripts/d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
    )
    r4_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r4_operator.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_replacement.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r3_preflight.py",
        "tests/runtime/test_d10_activation_scheduler_operator.py",
        "tests/runtime/test_d10_protected_deployment.py",
        "tests/runtime/test_d10_protected_replacement.py",
        "tests/runtime/test_d10_protected_replacement_windows.py",
    )
    r4_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r4_operator.py",
        "tests/runtime/test_d10_arch128_r4_operator.py",
        "scripts/d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "scripts/d10_arch128_r4_replacement.py",
        "tests/runtime/test_d10_arch128_r4_replacement.py",
        "scripts/d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
    )
    r5_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r5_trading_child.py",
        "tests/runtime/test_d10_python_substrate_harness.py",
        "tests/runtime/test_d10_python_substrate_windows.py",
        "tests/runtime/test_personal_desktop_d10_python_substrate.py",
    )
    r5_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r5_trading_child.py",
        "tests/runtime/test_d10_arch128_r5_trading_child.py",
        "scripts/d10_python_substrate_harness.py",
        "scripts/d10_python_substrate_windows.py",
    )
    r6_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
        "tests/runtime/test_personal_desktop_d10_activation_lease.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_personal_desktop_unattended_scheduler_contract.py",
    )
    r6_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r6_reactivation.py",
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
    )
    r7_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r7_readonly.py",
        "tests/runtime/test_d10_arch128_r7_protected.py",
        "tests/runtime/test_d10_arch128_r7_windows.py",
        "tests/runtime/test_d10_python_substrate_windows.py",
        "tests/runtime/test_d10_arch128_r6_reactivation.py",
        "tests/runtime/test_d10_activation_scheduler_operator.py",
        "tests/runtime/test_d10_arch128_r4_orchestration.py",
        "tests/runtime/test_d10_arch128_r4_windows.py",
        "tests/runtime/test_d10_arch128_r3_preflight.py",
    )
    r7_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r7_readonly.py",
        "tests/runtime/test_d10_arch128_r7_readonly.py",
        "scripts/d10_arch128_r7_protected.py",
        "tests/runtime/test_d10_arch128_r7_protected.py",
        "scripts/d10_arch128_r7_windows.py",
        "scripts/d10_arch128_r7_observation.py",
        "scripts/d10_arch128_r4_orchestration.py",
        "scripts/d10_python_substrate_windows.py",
        "tests/runtime/test_d10_arch128_r7_windows.py",
        "tests/runtime/test_d10_python_substrate_windows.py",
    )
    r8_tests = (
        *RETAINED_TESTS,
        "tests/runtime/test_d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_durable_wake_evidence_observe.py",
        "tests/runtime/test_personal_desktop_d10_wake_evidence_log.py",
        "tests/runtime/test_personal_desktop_d10_guard_evidence.py",
    )
    r8_ruff = (
        *RETAINED_RUFF_PATHS,
        "scripts/d10_arch128_r8_readonly.py",
        "tests/runtime/test_d10_arch128_r8_readonly.py",
    )
    return {
        ARCH134_F2_NAME: CheckpointSpec(
            name=ARCH134_F2_NAME,
            description="Architecture 134-F2 read-only five-session readiness",
            tests=ARCH134_F2_TESTS,
            ruff_paths=ARCH134_F2_RUFF_PATHS,
            authority_check=_arch134_f2_authority_check,
            remote_branch=ARCH134_F2_BRANCH,
            preflight=_arch134_f2_preflight,
            execute=None,
        ),
        ARCH144C_NAME: CheckpointSpec(
            name=ARCH144C_NAME,
            description="Architecture 144-C pure F1 evidence admission source only",
            tests=ARCH144C_TESTS,
            ruff_paths=ARCH144C_RUFF_PATHS,
            authority_check=_arch144c_authority_check,
            remote_branch=ARCH144C_BRANCH,
            preflight=None,
            execute=None,
        ),
        ARCH134_F1_NAME: CheckpointSpec(
            name=ARCH134_F1_NAME,
            description="Architecture 134-F1 five-session soak source only",
            tests=ARCH134_F1_TESTS,
            ruff_paths=ARCH134_F1_RUFF_PATHS,
            authority_check=_arch134_f1_authority_check,
            remote_branch=ARCH134_F1_BRANCH,
            preflight=None,
            execute=None,
        ),
        ARCH134_D1R8_NAME: CheckpointSpec(
            name=ARCH134_D1R8_NAME,
            description="Architecture 134-D1R8 execution consumer source only",
            tests=ARCH134_D1R8_TESTS,
            ruff_paths=ARCH134_D1R8_RUFF_PATHS,
            authority_check=_arch134_d1r8_authority_check,
            remote_branch=ARCH134_D1R8_BRANCH,
        ),
        ARCH134_D1R7_NAME: CheckpointSpec(
            name=ARCH134_D1R7_NAME,
            description="Architecture 134-D1R7 prerequisite evidence source only",
            tests=ARCH134_D1R7_TESTS,
            ruff_paths=ARCH134_D1R7_RUFF_PATHS,
            authority_check=_arch134_d1r7_authority_check,
            remote_branch=ARCH134_D1R7_BRANCH,
            preflight=None,
            execute=None,
        ),
        ARCH134_D1R6_NAME: CheckpointSpec(
            name=ARCH134_D1R6_NAME,
            description="Architecture 134-D1R6 source-only overnight wake arming",
            tests=ARCH134_D1R6_TESTS,
            ruff_paths=ARCH134_D1R6_RUFF_PATHS,
            authority_check=_arch134_d1r6_authority_check,
            remote_branch=ARCH134_D1R6_BRANCH,
        ),
        ARCH134_D1R5_NAME: CheckpointSpec(
            name=ARCH134_D1R5_NAME,
            description="Architecture 134-D1R5 bounded pre-market wake source only",
            tests=ARCH134_D1R5_TESTS,
            ruff_paths=ARCH134_D1R5_RUFF_PATHS,
            authority_check=_arch134_d1r5_authority_check,
            remote_branch=ARCH134_D1R5_BRANCH,
            preflight=None,
            execute=None,
        ),
        ARCH134_AUTH_NAME: CheckpointSpec(
            name=ARCH134_AUTH_NAME,
            description="Architecture 134-D1R4R incident recovery source only",
            tests=ARCH134_AUTH_TESTS,
            ruff_paths=ARCH134_AUTH_RUFF_PATHS,
            authority_check=_arch134_authentication_authority_check,
            remote_branch=ARCH134_AUTH_BRANCH,
            preflight=None,
            execute=None,
        ),
        ARCH134_RUNTIME_ACL_NAME: CheckpointSpec(
            name=ARCH134_RUNTIME_ACL_NAME,
            description=(
                "Architecture 134-D1Q-R2 fixed runtime principal ACL source only"
            ),
            tests=ARCH134_RUNTIME_ACL_TESTS,
            ruff_paths=ARCH134_RUNTIME_ACL_RUFF_PATHS,
            authority_check=_arch134_runtime_acl_authority_check,
            remote_branch="feature/robinhood-production-paper-runtime-acl",
            preflight=None,
            execute=None,
        ),
        ARCH134_PRODUCTION_PAPER_RUNTIME_NAME: CheckpointSpec(
            name=ARCH134_PRODUCTION_PAPER_RUNTIME_NAME,
            description="Architecture 134-D1Q fixed runtime and credential readiness",
            tests=ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_TESTS,
            ruff_paths=ARCH134_PRODUCTION_PAPER_RUNTIME_SUCCESSOR_RUFF_PATHS,
            authority_check=_arch134_production_paper_runtime_authority_check,
            remote_branch="feature/robinhood-production-paper-history-recovery",
            preflight=None,
            execute=None,
        ),
        ARCH134_ARMED_PAPER_NAME: CheckpointSpec(
            name=ARCH134_ARMED_PAPER_NAME,
            description=(
                "Architecture 134-D1 current Alpaca history and armed paper session"
            ),
            tests=ARCH134_ARMED_PAPER_TESTS,
            ruff_paths=ARCH134_ARMED_PAPER_RUFF_PATHS,
            authority_check=_arch134_armed_paper_authority_check,
            remote_branch="feature/robinhood-production-paper-mvp",
            preflight=None,
            execute=None,
        ),
        ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME: CheckpointSpec(
            name=ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_NAME,
            description=(
                "Architecture 134-C human-started production live-paper composition"
            ),
            tests=ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_TESTS,
            ruff_paths=ARCH134_PRODUCTION_STRATEGY_LIVE_PAPER_RUFF_PATHS,
            authority_check=_arch134_production_strategy_live_paper_authority_check,
            remote_branch="feature/robinhood-production-strategy-live-paper",
            preflight=None,
            execute=None,
        ),
        ARCH134_PRODUCTION_STRATEGY_DECISION_NAME: CheckpointSpec(
            name=ARCH134_PRODUCTION_STRATEGY_DECISION_NAME,
            description="Architecture 134-B pure production strategy decision bridge",
            tests=ARCH134_PRODUCTION_STRATEGY_DECISION_TESTS,
            ruff_paths=ARCH134_PRODUCTION_STRATEGY_DECISION_RUFF_PATHS,
            authority_check=_arch134_production_strategy_decision_authority_check,
            remote_branch="feature/robinhood-production-strategy-decision",
            preflight=None,
            execute=None,
        ),
        ARCH134_PRODUCTION_STRATEGY_NAME: CheckpointSpec(
            name=ARCH134_PRODUCTION_STRATEGY_NAME,
            description="Architecture 134-A inert session production strategy contract",
            tests=ARCH134_PRODUCTION_STRATEGY_TESTS,
            ruff_paths=ARCH134_PRODUCTION_STRATEGY_RUFF_PATHS,
            authority_check=_arch134_production_strategy_authority_check,
            remote_branch="feature/robinhood-production-strategy-contract",
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-paper-intent-bridge": CheckpointSpec(
            name="arch131-robinhood-paper-intent-bridge",
            description="Architecture 131-I deterministic risk-to-paper-intent bridge",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_intent_bridge.py",
                "tests/review_paper/test_store.py",
                "tests/risk/test_risk_models.py",
                "tests/risk/test_manager.py",
                "tests/execution/test_execution_models.py",
                "tests/execution/test_order_engine.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/intent_bridge.py",
                "src/trading_bot/review_paper/__init__.py",
                "tests/review_paper/test_intent_bridge.py",
            ),
            authority_check=_arch131_paper_intent_bridge_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-deterministic-paper-pipeline": CheckpointSpec(
            name="arch131-robinhood-deterministic-paper-pipeline",
            description="Architecture 131-J one-cycle deterministic paper pipeline",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_paper_pipeline.py",
                "tests/review_paper/test_intent_bridge.py",
                "tests/test_robinhood_paper_operator.py",
                "tests/test_robinhood_paper_cycle.py",
                "tests/risk/test_risk_models.py",
                "tests/risk/test_manager.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_paper_pipeline.py",
                "tests/test_robinhood_paper_pipeline.py",
            ),
            authority_check=_arch131_deterministic_paper_pipeline_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-virtual-risk-context": CheckpointSpec(
            name="arch131-robinhood-virtual-risk-context",
            description="Architecture 131-K durable virtual-paper risk context",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_risk_context.py",
                "tests/review_paper/test_store.py",
                "tests/ledger/test_ledger.py",
                "tests/risk/test_risk_models.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/risk_context.py",
                "src/trading_bot/review_paper/__init__.py",
                "tests/review_paper/test_risk_context.py",
            ),
            authority_check=_arch131_virtual_risk_context_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-forward-paper-cycle": CheckpointSpec(
            name="arch131-robinhood-forward-paper-cycle",
            description="Architecture 131-L human-started durable-context paper cycle",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_forward_paper_cycle.py",
                "tests/review_paper/test_risk_context.py",
                "tests/test_robinhood_paper_pipeline.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_forward_paper_cycle.py",
                "tests/test_robinhood_forward_paper_cycle.py",
            ),
            authority_check=_arch131_forward_paper_cycle_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-live-qualification-verifier": CheckpointSpec(
            name="arch131-robinhood-live-qualification-verifier",
            description="Architecture 131-LQ read-only live-qualification verifier",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_live_qualification_verifier.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_live_qualification_verifier.py",
                "tests/test_robinhood_live_qualification_verifier.py",
            ),
            authority_check=_arch131_live_qualification_verifier_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-session-admission": CheckpointSpec(
            name="arch131-robinhood-session-admission",
            description=(
                "Architecture 131-M explicit-schedule regular-session admission"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_session_admission.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/session_admission.py",
                "tests/review_paper/test_session_admission.py",
            ),
            authority_check=_arch131_session_admission_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-risk-price-snapshot": CheckpointSpec(
            name="arch131-robinhood-risk-price-snapshot",
            description=(
                "Architecture 131-N canonical Robinhood quote-to-risk-price snapshot"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_risk_prices.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/risk_prices.py",
                "tests/review_paper/test_risk_prices.py",
            ),
            authority_check=_arch131_risk_price_snapshot_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-forward-paper-preview": CheckpointSpec(
            name="arch131-robinhood-forward-paper-preview",
            description=(
                "Architecture 131-O effect-free durable forward-paper risk preview"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_forward_preview.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/forward_preview.py",
                "tests/review_paper/test_forward_preview.py",
            ),
            authority_check=_arch131_forward_paper_preview_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-risk-price-acquisition": CheckpointSpec(
            name="arch131-robinhood-risk-price-acquisition",
            description=(
                "Architecture 131-P bounded read-only Robinhood risk-price acquisition"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_risk_price_acquisition.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/risk_price_acquisition.py",
                "tests/review_paper/test_risk_price_acquisition.py",
            ),
            authority_check=_arch131_risk_price_acquisition_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-supervised-forward-paper": CheckpointSpec(
            name="arch131-robinhood-supervised-forward-paper",
            description=(
                "Architecture 131-Q two-phase supervised forward-paper "
                "operator composition"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_supervised_forward_paper.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/supervised_forward_paper.py",
                "tests/review_paper/test_supervised_forward_paper.py",
            ),
            authority_check=_arch131_supervised_forward_paper_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-supervised-prepare-qualification": CheckpointSpec(
            name="arch131-robinhood-supervised-prepare-qualification",
            description="Architecture 131-R supervised PREPARE qualification harness",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_prepare_qualification.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/prepare_qualification.py",
                "tests/review_paper/test_prepare_qualification.py",
            ),
            authority_check=_arch131_prepare_qualification_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-supervised-prepare-verifier": CheckpointSpec(
            name="arch131-robinhood-supervised-prepare-verifier",
            description="Architecture 131-R read-only PREPARE qualification verifier",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_prepare_qualification_verifier.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_prepare_qualification_verifier.py",
                "tests/test_robinhood_prepare_qualification_verifier.py",
            ),
            authority_check=_arch131_prepare_verifier_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-nyse-published-regular-session-authority": CheckpointSpec(
            name="arch131-nyse-published-regular-session-authority",
            description=("Architecture 131-S NYSE published regular-session authority"),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_nyse_published_regular_sessions.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/nyse_published_regular_sessions.py",
                "tests/review_paper/test_nyse_published_regular_sessions.py",
            ),
            authority_check=_arch131_nyse_published_regular_session_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-published-session-prepare": CheckpointSpec(
            name="arch131-robinhood-published-session-prepare",
            description=(
                "Architecture 131-T explicit-date published-session PREPARE binding"
            ),
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_published_session_prepare.py",
                "tests/test_robinhood_prepare_qualification_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/published_session_prepare.py",
                "tests/review_paper/test_published_session_prepare.py",
                "src/trading_bot/robinhood_prepare_qualification_verifier.py",
                "tests/test_robinhood_prepare_qualification_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch131_published_session_prepare_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-published-prepare-operator": CheckpointSpec(
            name="arch131-robinhood-published-prepare-operator",
            description="Architecture 131-U source-owned PREPARE transport composition",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_prepare_operator.py",
                "tests/review_paper/test_published_session_prepare.py",
                "tests/review_paper/test_prepare_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_prepare_operator.py",
                "tests/test_robinhood_prepare_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch131_published_prepare_operator_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-supervised-qualification": CheckpointSpec(
            name="arch131-robinhood-supervised-qualification",
            description=("Architecture 131-V supervised qualification and verifier"),
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_supervised_qualification.py",
                "tests/review_paper/test_supervised_forward_paper.py",
                "tests/review_paper/test_prepare_qualification.py",
                "tests/test_robinhood_prepare_qualification_verifier.py",
                "tests/test_robinhood_prepare_operator.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_supervised_qualification.py",
                "src/trading_bot/robinhood_execute_qualification_verifier.py",
                "scripts/robinhood_supervised_qualification.py",
                "src/trading_bot/review_paper/__init__.py",
                "tests/test_robinhood_supervised_qualification.py",
            ),
            authority_check=_arch131_supervised_qualification_authority_check,
            remote_branch=ARCH131_SIDE_FOUNDATION_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-activation-core": CheckpointSpec(
            name="arch133-robinhood-unattended-activation-core",
            description=(
                "Architecture 133-A pure activation and wake identity/state core"
            ),
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_activation.py",
                "tests/review_paper/test_unattended_activation.py",
            ),
            authority_check=_arch133_unattended_activation_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133a",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-state-store": CheckpointSpec(
            name="arch133-robinhood-unattended-state-store",
            description="Architecture 133-B durable wake store and read-only verifier",
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_state_schema.py",
                "src/trading_bot/review_paper/unattended_state_store.py",
                "src/trading_bot/review_paper/unattended_state_verifier.py",
                "tests/review_paper/test_unattended_state_store.py",
            ),
            authority_check=_arch133_unattended_state_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133b",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-one-wake-composition": CheckpointSpec(
            name="arch133-robinhood-unattended-one-wake-composition",
            description="Architecture 133-C effect-free one-wake composition",
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_one_wake.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_one_wake_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133c",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-review-paper-execution": CheckpointSpec(
            name="arch133-robinhood-unattended-review-paper-execution",
            description="Architecture 133-D bounded unattended review-paper execution",
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/test_robinhood_paper_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_execution.py",
                "tests/review_paper/test_unattended_execution.py",
                "src/trading_bot/robinhood_paper_operator.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_execution_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133d",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-host-scheduler-surface": CheckpointSpec(
            name="arch133-robinhood-unattended-host-scheduler-surface",
            description=(
                "Architecture 133-E zero-argument host and pure scheduler surface"
            ),
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_host_identity.py",
                "src/trading_bot/review_paper/unattended_scheduler.py",
                "src/trading_bot/review_paper/unattended_host.py",
                "scripts/run_arch133_unattended_review_paper.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_host_scheduler_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133e",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-post-publication-stage-diagnostic": CheckpointSpec(
            name="arch133-robinhood-post-publication-stage-diagnostic",
            description="Architecture 133-M source-only stage diagnostic",
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_post_publication_stage_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133m",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-publication-state-paper-diagnostic": CheckpointSpec(
            name="arch133-robinhood-publication-state-paper-diagnostic",
            description=(
                "Architecture 133-N source-only publication/state/paper diagnostic"
            ),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PUBLICATION_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_publication_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133n",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-admission-diagnostic": CheckpointSpec(
            name="arch133-robinhood-reprovision-admission-diagnostic",
            description=(
                "Architecture 133-R source-only reprovision admission diagnostic"
            ),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_REPROVISION_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133r",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-parent-security-diagnostic": CheckpointSpec(
            name="arch133-robinhood-reprovision-parent-security-diagnostic",
            description=("Architecture 133-S source-only parent-security diagnostic"),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PARENT_SECURITY_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_parent_security_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133s",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-parent-policy-diagnostic": CheckpointSpec(
            name="arch133-robinhood-reprovision-parent-policy-diagnostic",
            description=("Architecture 133-T source-only parent-security diagnostic"),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PARENT_POLICY_DIAGNOSTIC_SOURCES,
                "tests/review_paper/test_arch133_reprovision_admission_diagnostic.py",
                "tests/review_paper/test_arch133_parent_security_diagnostic.py",
                "tests/review_paper/test_arch133_parent_policy_diagnostic.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_parent_policy_diagnostic_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133t",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-fresh-activation-reprovision": CheckpointSpec(
            name="arch133-robinhood-fresh-activation-reprovision",
            description="Architecture 133-Q source-only fresh activation reprovision",
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_REPROVISION_SOURCES,
                "tests/review_paper/test_arch133_fresh_activation_reprovision.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133q",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-fresh-activation-reprovision-corrected": CheckpointSpec(
            name="arch133-robinhood-fresh-activation-reprovision-corrected",
            description="Architecture 133-U source-only corrected fresh activation reprovision",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133U_REPROVISION_SOURCES,
                "tests/review_paper/test_arch133_fresh_activation_reprovision_corrected.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_corrected_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133u",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-indeterminate-reconciliation": CheckpointSpec(
            name="arch133-robinhood-reprovision-indeterminate-reconciliation",
            description="Architecture 133-V source-only indeterminate reconciliation",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133V_RECONCILIATION_SOURCES,
                "tests/review_paper/test_arch133_reprovision_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_reconciliation_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133v",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-sealed-predecessor-recovery": CheckpointSpec(
            name="arch133-robinhood-reprovision-sealed-predecessor-recovery",
            description="Architecture 133-W source-only sealed-predecessor recovery",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_recovery.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133W_RECOVERY_SOURCES,
                "tests/review_paper/test_arch133_reprovision_recovery.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_recovery_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133w",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-reprovision-recovery-reconciliation": CheckpointSpec(
            name="arch133-robinhood-reprovision-recovery-reconciliation",
            description="Architecture 133-X source-only post-W recovery reconciliation",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133X_RECONCILIATION_SOURCES,
                "tests/review_paper/test_arch133_reprovision_recovery_reconciliation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_reprovision_recovery_reconciliation_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133x",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-windows-rename-qualification": CheckpointSpec(
            name="arch133-robinhood-windows-rename-qualification",
            description="Architecture 133-Y source-only scratch Windows rename qualification",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_windows_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133Y_QUALIFICATION_SOURCES,
                "tests/review_paper/test_arch133_windows_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_windows_rename_qualification_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133y",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-closed-descendant-rename-qualification": CheckpointSpec(
            name="arch133-robinhood-closed-descendant-rename-qualification",
            description="Architecture 133-Z source-only scratch Windows rename qualification",  # noqa: E501
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133Z_QUALIFICATION_SOURCES,
                "tests/review_paper/test_arch133_closed_descendant_rename_qualification.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_closed_descendant_rename_qualification_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133z",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-supervised-release-installation-operator": CheckpointSpec(
            name="arch133-robinhood-supervised-release-installation-operator",
            description=(
                "133-AG installation-only operator; "
                "protected execution requires fresh authorization"
            ),
            tests=SUPERVISED_INSTALLATION_OPERATOR_TESTS,
            ruff_paths=SUPERVISED_INSTALLATION_OPERATOR_RUFF_PATHS,
            authority_check=_supervised_installation_operator_authority_check,
            preflight=_supervised_installation_preflight,
            execute=_supervised_installation_execute,
            remote_branch="feature/robinhood-supervised-release-installation-operator",
            remote_head_env=None,
        ),
        SUPERVISED_PUBLICATION_RECOVERY_NAME: CheckpointSpec(
            name=SUPERVISED_PUBLICATION_RECOVERY_NAME,
            description=(
                "133-AJ preserved immutable-release publication recovery; "
                "fresh authorization required"
            ),
            tests=SUPERVISED_PUBLICATION_RECOVERY_TESTS,
            ruff_paths=SUPERVISED_PUBLICATION_RECOVERY_RUFF_PATHS,
            authority_check=_supervised_publication_recovery_authority_check,
            preflight=_supervised_publication_preflight,
            execute=_supervised_publication_execute,
            remote_branch="feature/robinhood-supervised-release-publication-recovery",
            remote_head_env=None,
        ),
        SUPERVISED_INSTALLATION_RECONCILIATION_NAME: CheckpointSpec(
            name=SUPERVISED_INSTALLATION_RECONCILIATION_NAME,
            description=(
                "133-AI read-only reconciliation of the consumed AG "
                "publication ambiguity"
            ),
            tests=SUPERVISED_INSTALLATION_RECONCILIATION_TESTS,
            ruff_paths=SUPERVISED_INSTALLATION_RECONCILIATION_RUFF_PATHS,
            authority_check=_supervised_installation_reconciliation_authority_check,
            preflight=_supervised_installation_reconciliation_preflight,
            execute=None,
            remote_branch=(
                "feature/robinhood-supervised-release-installation-reconciliation"
            ),
            remote_head_env=None,
        ),
        "arch133-robinhood-supervised-deployment-qualification": CheckpointSpec(
            name="arch133-robinhood-supervised-deployment-qualification",
            description="Architecture 133-AF inert deployment/rollback qualification",
            tests=SUPERVISED_DEPLOYMENT_QUALIFICATION_TESTS,
            ruff_paths=SUPERVISED_DEPLOYMENT_QUALIFICATION_RUFF_PATHS,
            authority_check=_supervised_deployment_qualification_authority_check,
            remote_branch="feature/robinhood-supervised-deployment-qualification",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-supervised-runtime-host-admission": CheckpointSpec(
            name="arch133-robinhood-supervised-runtime-host-admission",
            description="Architecture 133-AE inert immutable runtime-host admission",
            tests=SUPERVISED_RUNTIME_ADMISSION_TESTS,
            ruff_paths=SUPERVISED_RUNTIME_ADMISSION_RUFF_PATHS,
            authority_check=_supervised_runtime_admission_authority_check,
            remote_branch="feature/robinhood-supervised-runtime-host-admission",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-supervised-maintenance-rebind": CheckpointSpec(
            name="arch133-robinhood-supervised-maintenance-rebind",
            description="Architecture 133-AD inert maintenance and immutable rebind",
            tests=SUPERVISED_MAINTENANCE_TESTS,
            ruff_paths=SUPERVISED_MAINTENANCE_RUFF_PATHS,
            authority_check=_supervised_maintenance_authority_check,
            remote_branch="feature/robinhood-supervised-maintenance-rebind",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-supervised-release-installation": CheckpointSpec(
            name="arch133-robinhood-supervised-release-installation",
            description="Architecture 133-AC immutable installation and observation",
            tests=SUPERVISED_RELEASE_INSTALLATION_TESTS,
            ruff_paths=SUPERVISED_RELEASE_INSTALLATION_RUFF_PATHS,
            authority_check=_supervised_release_installation_authority_check,
            remote_branch="feature/robinhood-supervised-release-installation",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-supervised-release-build-verification": CheckpointSpec(
            name="arch133-robinhood-supervised-release-build-verification",
            description="Architecture 133-AB source bundle and runtime binding",
            tests=SUPERVISED_RELEASE_BUNDLE_TESTS,
            ruff_paths=SUPERVISED_RELEASE_BUNDLE_RUFF_PATHS,
            authority_check=_supervised_release_bundle_authority_check,
            remote_branch="feature/robinhood-supervised-release-build-verification",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-supervised-release-foundation": CheckpointSpec(
            name="arch133-robinhood-supervised-release-foundation",
            description="Architecture 133 pure immutable-release foundation",
            tests=SUPERVISED_RELEASE_TESTS,
            ruff_paths=SUPERVISED_RELEASE_RUFF_PATHS,
            authority_check=_supervised_release_authority_check,
            remote_branch="feature/robinhood-supervised-release-foundation",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-single-session-scheduler-installation": CheckpointSpec(
            name="arch133-robinhood-single-session-scheduler-installation",
            description="Architecture 133-P source-only protected Q133-3 installation",
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *(p for p in ARCH133_SCHEDULER_SOURCES if p.endswith(".py")),
                "tests/review_paper/test_arch133_scheduler_installation.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_scheduler_installation_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133p",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-publication-state-paper-corrected": CheckpointSpec(
            name="arch133-robinhood-publication-state-paper-corrected",
            description=(
                "Architecture 133-O source-only publication/state/paper diagnostic"
            ),
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_PUBLICATION_CORRECTED_SOURCES,
                "tests/review_paper/test_publication_state_paper_diagnostic.py",
                "tests/review_paper/test_publication_state_paper_corrected.py",
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_publication_corrected_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133o",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-post-publication-verifier": CheckpointSpec(
            name="arch133-robinhood-post-publication-verifier",
            description="Architecture 133-L source-only post-publication verifier",
            tests=(
                *ARCH133_L_M_TESTS,
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_L_M_RUFF_PATHS,
                *ARCH133_VERIFIER_SOURCES,
                "tests/review_paper/test_post_publication_verifier.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_verifier_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133l",
            preflight=None,
            execute=None,
            remote_head_env=None,
        ),
        "arch133-robinhood-retained-root-acl-recovery": CheckpointSpec(
            name="arch133-robinhood-retained-root-acl-recovery",
            description="Architecture 133-K source-only retained-root ACL recovery",
            tests=(
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_retained_root_acl_recovery.py",
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            ),
            ruff_paths=(
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_RECOVERY_SOURCES,
                "tests/review_paper/test_retained_root_acl_recovery.py",
            ),
            authority_check=_arch133_recovery_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133k",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-retained-root-diagnostic": CheckpointSpec(
            name="arch133-robinhood-retained-root-diagnostic",
            description="Architecture 133-J source-only retained-root diagnostic",
            tests=(
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_retained_root_diagnostic.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            ),
            ruff_paths=(
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_RETAINED_SOURCES,
                "tests/review_paper/test_retained_root_diagnostic.py",
            ),
            authority_check=_arch133_retained_root_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133j",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-scratch-root-acl-qualification": CheckpointSpec(
            name="arch133-robinhood-scratch-root-acl-qualification",
            description=(
                "Architecture 133-I source-only scratch native root ACL qualification"
            ),
            tests=(
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            ),
            ruff_paths=(
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_SCRATCH_SOURCES,
                "src/trading_bot/review_paper/unattended_publication_windows.py",
                "tests/review_paper/test_scratch_root_acl.py",
                "tests/review_paper/test_unattended_publication.py",
            ),
            authority_check=_arch133_scratch_root_acl_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133i",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-host-publication": CheckpointSpec(
            name="arch133-robinhood-unattended-host-publication",
            description=(
                "Architecture 133-H source-only Q133-2 publication prerequisite"
            ),
            tests=(
                *ARCH133_H_K_TESTS,
                "tests/review_paper/test_unattended_publication.py",
            ),
            ruff_paths=(
                *ARCH133_H_K_RUFF_PATHS,
                *ARCH133_PUBLICATION_SOURCES,
                "tests/review_paper/test_unattended_publication.py",
            ),
            authority_check=_arch133_host_publication_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133h",
            preflight=None,
            execute=None,
        ),
        "arch133-robinhood-unattended-host-bootstrap": CheckpointSpec(
            name="arch133-robinhood-unattended-host-bootstrap",
            description=(
                "Architecture 133-G pre-publication host/runtime bootstrap surface"
            ),
            tests=(
                *ARCH133_A_G_TESTS,
                "tests/review_paper/test_unattended_activation.py",
                "tests/review_paper/test_unattended_state_store.py",
                "tests/review_paper/test_unattended_one_wake.py",
                "tests/review_paper/test_unattended_execution.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            ruff_paths=(
                *ARCH133_A_G_RUFF_PATHS,
                "src/trading_bot/review_paper/unattended_host_identity.py",
                "src/trading_bot/review_paper/unattended_scheduler.py",
                "src/trading_bot/review_paper/unattended_host.py",
                "src/trading_bot/review_paper/unattended_host_bootstrap.py",
                "scripts/run_arch133_unattended_review_paper.py",
                "scripts/run_arch133_unattended_host_preflight.py",
                "tests/review_paper/test_unattended_host.py",
                "tests/scripts/certification_runner/test_profiles.py",
            ),
            authority_check=_arch133_host_bootstrap_authority_check,
            remote_branch="feature/robinhood-unattended-review-paper-133g",
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-paper-operator": CheckpointSpec(
            name="arch131-robinhood-paper-operator",
            description="Architecture 131-H one-cycle Robinhood paper operator",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_paper_operator.py",
                "tests/test_robinhood_paper_cycle.py",
                "tests/robinhood_mcp/test_account_resolution.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
                "tests/robinhood_mcp/test_windows_oauth.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_paper_operator.py",
                "tests/test_robinhood_paper_operator.py",
            ),
            authority_check=_arch131_paper_operator_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-agentic-account": CheckpointSpec(
            name="arch131-robinhood-agentic-account",
            description="Architecture 131-G internal Agentic-account resolution",
            tests=(
                *ARCH131_TESTS,
                "tests/robinhood_mcp/test_account_resolution.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
                "tests/test_robinhood_paper_cycle.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_mcp/account_resolution.py",
                "src/trading_bot/robinhood_mcp/sdk_transport.py",
                "src/trading_bot/robinhood_mcp/__init__.py",
                "src/trading_bot/robinhood_paper_cycle.py",
                "tests/robinhood_mcp/test_account_resolution.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
                "tests/test_robinhood_paper_cycle.py",
            ),
            authority_check=_arch131_agentic_account_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-oauth-windows": CheckpointSpec(
            name="arch131-robinhood-oauth-windows",
            description="Architecture 131-F Windows OAuth persistence and callback",
            tests=(
                *ARCH131_TESTS,
                "tests/robinhood_mcp/test_windows_oauth.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_mcp/windows_oauth.py",
                "tests/robinhood_mcp/test_windows_oauth.py",
            ),
            authority_check=_arch131_windows_oauth_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
            preflight=None,
            execute=None,
        ),
        "arch131-robinhood-direct-mcp": CheckpointSpec(
            name="arch131-robinhood-direct-mcp",
            description="Architecture 131-E direct Robinhood MCP transport",
            tests=(
                *ARCH131_TESTS,
                "tests/robinhood_mcp/test_sdk_transport.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_mcp/__init__.py",
                "src/trading_bot/robinhood_mcp/sdk_transport.py",
                "tests/robinhood_mcp/test_sdk_transport.py",
            ),
            authority_check=_arch131_direct_mcp_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch131-robinhood-performance": CheckpointSpec(
            name="arch131-robinhood-performance",
            description="Architecture 131-D durable Robinhood paper performance",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_performance.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/__init__.py",
                "src/trading_bot/review_paper/performance.py",
                "tests/review_paper/test_performance.py",
            ),
            authority_check=_arch131_performance_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch131-robinhood-paper-cycle": CheckpointSpec(
            name="arch131-robinhood-paper-cycle",
            description="Architecture 131-C fail-closed Robinhood paper cycle",
            tests=(
                *ARCH131_TESTS,
                "tests/test_robinhood_paper_cycle.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_paper_cycle.py",
                "tests/test_robinhood_paper_cycle.py",
            ),
            authority_check=_arch131_paper_cycle_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch131-robinhood-mcp-schema": CheckpointSpec(
            name="arch131-robinhood-mcp-schema",
            description="Architecture 131-B typed Robinhood MCP read/review schema",
            tests=(
                *ARCH131_TESTS,
                "tests/robinhood_mcp/test_adapter.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/robinhood_mcp/__init__.py",
                "src/trading_bot/robinhood_mcp/models.py",
                "src/trading_bot/robinhood_mcp/parsing.py",
                "src/trading_bot/robinhood_mcp/adapter.py",
                "tests/robinhood_mcp/test_adapter.py",
            ),
            authority_check=_arch131_mcp_schema_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch131-robinhood-review-paper": CheckpointSpec(
            name="arch131-robinhood-review-paper",
            description="Architecture 131 Robinhood review-based paper ledger",
            tests=(
                *ARCH131_TESTS,
                "tests/review_paper/test_store.py",
            ),
            ruff_paths=(
                *ARCH131_RUFF_PATHS,
                "src/trading_bot/review_paper/__init__.py",
                "src/trading_bot/review_paper/models.py",
                "src/trading_bot/review_paper/store.py",
                "tests/review_paper/test_store.py",
            ),
            authority_check=_arch131_review_paper_authority_check,
            remote_branch=ARCH131_REVIEW_PAPER_REMOTE_BRANCH,
        ),
        "arch130-r8i-d1": CheckpointSpec(
            name="arch130-r8i-d1",
            description=(
                "Architecture 130 failed first-wake read-only effect reconciliation"
            ),
            tests=(
                *RETAINED_TESTS,
                "tests/runtime/test_d10_arch130_r8i_d1.py",
            ),
            ruff_paths=(
                *RETAINED_RUFF_PATHS,
                "scripts/d10_arch130_r8i_d1.py",
                "tests/runtime/test_d10_arch130_r8i_d1.py",
            ),
            authority_check=_arch130_r8i_d1_authority_check,
            preflight=_arch130_r8i_d1_preflight,
            remote_branch=ARCH130_R8I_D1_REMOTE_BRANCH,
        ),
        "arch128-r8-terminal-halt": CheckpointSpec(
            name="arch128-r8-terminal-halt",
            description="R8I-H1 exact terminal first-wake scheduler halt source",
            tests=(
                *RETAINED_TESTS,
                "tests/runtime/test_d10_arch128_r8_terminal_halt.py",
                "tests/runtime/test_d10_arch128_r8_readonly.py",
                "tests/runtime/test_d10_durable_wake_evidence_observe.py",
            ),
            ruff_paths=(
                *RETAINED_RUFF_PATHS,
                "scripts/d10_arch128_r8_terminal_halt.py",
                "scripts/d10_arch128_r8_halt_windows.py",
                "scripts/d10_arch128_r8_halt_diagnostic.py",
                "tests/runtime/test_d10_arch128_r8_terminal_halt.py",
            ),
            authority_check=_r8_halt_authority_check,
            preflight=_r8_halt_preflight,
            execute=_r8_halt_execute,
            remote_branch="feature/d10c-r8-terminal-halt",
        ),
        "arch128-r8": CheckpointSpec(
            name="arch128-r8",
            description="Architecture 128 first-wake read-only observation",
            tests=r8_tests,
            ruff_paths=r8_ruff,
            authority_check=_r8_authority_check,
            preflight=_r8_preflight,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-parent-acl-repair": CheckpointSpec(
            name="arch128-parent-acl-repair",
            description="Architecture 128 exact parent-ACL repair source gate",
            tests=parent_tests,
            ruff_paths=parent_ruff,
            authority_check=_parent_acl_authority_check,
            preflight=_parent_acl_preflight,
            execute=_parent_acl_execute,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-r4": CheckpointSpec(
            name="arch128-r4",
            description="Architecture 128 protected replacement source gate",
            tests=r4_tests,
            ruff_paths=r4_ruff,
            authority_check=_r4_authority_check,
            preflight=_r4_preflight,
            execute=_r4_execute,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-r5-substrate": CheckpointSpec(
            name="arch128-r5-substrate",
            description=(
                "Architecture 128 fresh protected Python substrate qualification"
            ),
            tests=r5_tests,
            ruff_paths=r5_ruff,
            authority_check=_r5_authority_check,
            preflight=_r5_substrate_preflight,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-r5-trading": CheckpointSpec(
            name="arch128-r5-trading",
            description="Architecture 128 non-admin Trading deployment qualification",
            tests=r5_tests,
            ruff_paths=r5_ruff,
            authority_check=_r5_authority_check,
            preflight=_r5_trading_preflight,
            remote_branch="feature/d10c-durable-wake-evidence",
            remote_head_env=R5_TRADING_REMOTE_HEAD_ENV,
        ),
        "arch128-r6": CheckpointSpec(
            name="arch128-r6",
            description="Architecture 128 source-only reactivation ordering gate",
            tests=r6_tests,
            ruff_paths=r6_ruff,
            authority_check=_r6_authority_check,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
        "arch128-r7": CheckpointSpec(
            name="arch128-r7",
            description="Architecture 128 R7 read-only activation admission",
            tests=r7_tests,
            ruff_paths=r7_ruff,
            authority_check=_r7_authority_check,
            preflight=_r7_preflight,
            execute=_r7_execute,
            remote_branch="feature/d10c-durable-wake-evidence",
        ),
    }


def _default_evidence_root(repo_root: Path) -> Path:
    configured = os.environ.get("AI_TRADING_BOT_CHECKPOINT_EVIDENCE_ROOT")
    if configured:
        return Path(configured)

    if os.name == "nt":
        preferred = Path(r"F:\AI\temp")
        if preferred.is_dir():
            return preferred / "ai-trading-bot-checkpoints"

    return Path(tempfile.gettempdir()) / "ai-trading-bot-checkpoints"


def _git_output(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _remote_branch_head(repo_root: Path, branch: str) -> str:
    environment = dict(os.environ)
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    try:
        completed = subprocess.run(
            ("git", "ls-remote", "origin", f"refs/heads/{branch}"),
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
            timeout=REMOTE_LOOKUP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"git ls-remote timed out after {REMOTE_LOOKUP_TIMEOUT_SECONDS} seconds"
        ) from exc
    if completed.returncode != 0:
        raise RuntimeError(f"git ls-remote failed: {completed.stderr.strip()}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(
            f"remote branch lookup returned {len(lines)} rows for {branch}"
        )
    parts = lines[0].split()
    if len(parts) != 2 or parts[1] != f"refs/heads/{branch}":
        raise RuntimeError("remote branch lookup returned an unexpected row")
    return parts[0]


def _trusted_remote_head_from_env(variable: str) -> str:
    value = os.environ.get(variable, "")
    if (
        len(value) != 40
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeError(
            f"trusted remote-head handoff is missing or malformed: {variable}"
        )
    return value


def _git_state(repo_root: Path) -> dict[str, object]:
    return {
        "head": _git_output(repo_root, "rev-parse", "HEAD"),
        "tree": _git_output(repo_root, "rev-parse", "HEAD^{tree}"),
        "branch": _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "porcelain": _git_output(
            repo_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ),
    }


def build_verification_steps(
    spec: CheckpointSpec,
    *,
    python_executable: str,
    basetemp: Path,
    tests: Sequence[str] | None = None,
) -> tuple[Step, ...]:
    test_paths = spec.tests if tests is None else tuple(tests)
    return (
        Step("git_diff_check", ("git", "diff", "--check")),
        Step(
            "ruff_check",
            (
                python_executable,
                "-m",
                "ruff",
                "check",
                "--no-cache",
                *spec.ruff_paths,
            ),
            (
                python_executable,
                "-m",
                "ruff",
                "check",
                "--diff",
                "--no-cache",
                *spec.ruff_paths,
            ),
        ),
        Step(
            "ruff_format",
            (
                python_executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "--no-cache",
                *spec.ruff_paths,
            ),
            (
                python_executable,
                "-m",
                "ruff",
                "format",
                "--diff",
                "--no-cache",
                *spec.ruff_paths,
            ),
        ),
        Step(
            "pytest",
            (
                python_executable,
                "-m",
                "pytest",
                *test_paths,
                f"--basetemp={basetemp}",
                "-p",
                "no:cacheprovider",
                "--durations=100",
                "--durations-min=0.0",
                f"--junitxml={basetemp.parent / 'pytest-results.xml'}",
            ),
        ),
    )


def _safe_step_name(name: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in name)


def _execute_step(
    step: Step,
    *,
    repo_root: Path,
    command_dir: Path,
    index: int,
    diagnostic: bool = False,
) -> CommandOutcome:
    label = f"{step.name}_diagnostic" if diagnostic else step.name
    argv = step.diagnostic_argv if diagnostic else step.argv
    if argv is None:
        raise ValueError("diagnostic command is unavailable")

    environment = None
    if step.name == "pytest":
        environment = os.environ.copy()
        for variable in (
            SOURCE_GATE_PHASE_ENV,
            SOURCE_GATE_SHARD_INDEX_ENV,
            SOURCE_GATE_SHARD_COUNT_ENV,
        ):
            environment.pop(variable, None)

    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=repo_root,
        capture_output=True,
        check=False,
        env=environment,
    )
    elapsed_seconds = time.monotonic() - started
    stdout = completed.stdout
    stderr = completed.stderr
    prefix = f"{index:02d}-{_safe_step_name(label)}"
    stdout_path = command_dir / f"{prefix}.stdout.txt"
    stderr_path = command_dir / f"{prefix}.stderr.txt"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)

    if completed.returncode != 0:
        if stdout:
            sys.stdout.buffer.write(stdout)
        if stderr:
            sys.stderr.buffer.write(stderr)

    return CommandOutcome(
        name=label,
        argv=tuple(argv),
        exit_code=int(completed.returncode),
        stdout_bytes=len(stdout),
        stderr_bytes=len(stderr),
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        elapsed_seconds=elapsed_seconds,
    )


def run_verification_steps(
    steps: Sequence[Step],
    execute: Callable[[Step, bool], CommandOutcome],
) -> tuple[CommandOutcome, ...]:
    outcomes: list[CommandOutcome] = []
    for step in steps:
        primary = execute(step, False)
        outcomes.append(primary)
        if primary.exit_code != 0 and step.diagnostic_argv is not None:
            outcomes.append(execute(step, True))
    return tuple(outcomes)


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _source_gate_phase() -> str:
    phase = os.environ.get(SOURCE_GATE_PHASE_ENV, "all")
    if phase not in {"all", "static", "tests"}:
        raise RuntimeError("source gate phase rejected")
    return phase


def _source_gate_shard() -> tuple[int, int] | None:
    raw_index = os.environ.get(SOURCE_GATE_SHARD_INDEX_ENV)
    raw_count = os.environ.get(SOURCE_GATE_SHARD_COUNT_ENV)
    if raw_index is None and raw_count is None:
        return None
    if raw_index is None or raw_count is None:
        raise RuntimeError("source gate shard configuration incomplete")
    try:
        index, count = int(raw_index), int(raw_count)
    except ValueError as exc:
        raise RuntimeError("source gate shard configuration rejected") from exc
    if not 1 <= count <= 16 or not 0 <= index < count:
        raise RuntimeError("source gate shard configuration rejected")
    return index, count


def duration_balanced_test_shards(
    tests: Sequence[str],
    count: int,
) -> tuple[tuple[str, ...], ...]:
    """Deterministic LPT balance using the latest accepted CI duration evidence."""
    if not tests or len(set(tests)) != len(tests):
        raise ValueError("test sharding requires distinct nonempty paths")
    if type(count) is not int or not 1 <= count <= min(16, len(tests)):
        raise ValueError("test shard count rejected")
    positions = {path: index for index, path in enumerate(tests)}
    loads = [0.0] * count
    shards: list[list[str]] = [[] for _ in range(count)]
    ordered = sorted(
        tests,
        key=lambda path: (-CI_TEST_DURATION_WEIGHTS.get(path, 1.0), path),
    )
    for path in ordered:
        target = min(range(count), key=lambda index: (loads[index], index))
        shards[target].append(path)
        loads[target] += CI_TEST_DURATION_WEIGHTS.get(path, 1.0)
    return tuple(tuple(sorted(shard, key=positions.__getitem__)) for shard in shards)


def _source_gate_steps(
    steps: Sequence[Step],
    phase: str,
) -> tuple[tuple[Step, ...], tuple[Step, ...]]:
    static = tuple(step for step in steps if step.name != "pytest")
    tests = tuple(step for step in steps if step.name == "pytest")
    if phase == "static":
        return static, ()
    if phase == "tests":
        return (), tests
    return static, tests


def verify_checkpoint(
    spec: CheckpointSpec,
    *,
    repo_root: Path,
    evidence_root: Path,
) -> tuple[bool, Path]:
    state_before = _git_state(repo_root)
    if state_before["porcelain"]:
        raise RuntimeError(
            f"source gate requires a clean worktree; found: {state_before['porcelain']}"
        )

    evidence_dir = evidence_root / spec.name / f"source-gate-{_stamp()}"
    command_dir = evidence_dir / "commands"
    command_dir.mkdir(parents=True, exist_ok=False)
    basetemp = evidence_dir / "pytest"
    phase = _source_gate_phase()
    shard = _source_gate_shard()
    if phase != "tests" and shard is not None:
        raise RuntimeError("test shard is valid only for tests phase")
    selected_tests = spec.tests
    if phase == "tests" and shard is not None:
        selected_tests = duration_balanced_test_shards(spec.tests, shard[1])[shard[0]]

    steps = build_verification_steps(
        spec,
        python_executable=sys.executable,
        basetemp=basetemp,
        tests=selected_tests,
    )
    static_steps, test_steps = _source_gate_steps(steps, phase)
    counter = 0

    def execute(step: Step, diagnostic: bool) -> CommandOutcome:
        nonlocal counter
        counter += 1
        return _execute_step(
            step,
            repo_root=repo_root,
            command_dir=command_dir,
            index=counter,
            diagnostic=diagnostic,
        )

    outcomes: list[CommandOutcome] = []
    authority_requested = phase in {"all", "static"}
    authority_checked = False
    authority_failures: tuple[str, ...] = ()
    if static_steps:
        outcomes.extend(run_verification_steps(static_steps, execute))
    static_pass = all(
        outcome.exit_code == 0
        for outcome in outcomes
        if not outcome.name.endswith("_diagnostic")
    )
    if authority_requested and static_pass:
        authority_checked = True
        authority_failures = spec.authority_check(repo_root)
    if test_steps and (phase == "tests" or (static_pass and not authority_failures)):
        outcomes.extend(run_verification_steps(test_steps, execute))
    state_after = _git_state(repo_root)

    primary = {
        outcome.name: outcome.exit_code
        for outcome in outcomes
        if not outcome.name.endswith("_diagnostic")
    }
    required = {
        "all": ("git_diff_check", "ruff_check", "ruff_format", "pytest"),
        "static": ("git_diff_check", "ruff_check", "ruff_format"),
        "tests": ("pytest",),
    }[phase]
    commands_pass = all(primary.get(name) == 0 for name in required)
    if (
        phase == "all"
        and static_pass
        and authority_failures
        and "pytest" not in primary
    ):
        commands_pass = True
    identity_stable = (
        state_before["head"] == state_after["head"]
        and state_before["tree"] == state_after["tree"]
        and not state_after["porcelain"]
    )
    passed = (
        commands_pass
        and (not authority_checked or not authority_failures)
        and identity_stable
    )

    report = {
        "schema": SCHEMA,
        "kind": "source_gate",
        "checkpoint": spec.name,
        "description": spec.description,
        "status": "PASS" if passed else "FAIL",
        "phase": phase,
        "test_shard": None if shard is None else {"index": shard[0], "count": shard[1]},
        "executed_tests": list(selected_tests) if "pytest" in primary else [],
        "authority_checked": authority_checked,
        "started_from": state_before,
        "finished_at": state_after,
        "identity_stable": identity_stable,
        "authority_failures": list(authority_failures),
        "commands": [asdict(outcome) for outcome in outcomes],
        "production_effects": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "provider_effects": "NOT_RUN",
        "broker_live_effects": "NOT_RUN",
    }
    report_path = evidence_dir / "report.json"
    _write_json(report_path, report)

    print(f"CHECKPOINT={spec.name} PHASE={phase}")
    for name in ("git_diff_check", "ruff_check", "ruff_format", "pytest"):
        exit_code = primary.get(name)
        status = (
            "SKIP"
            if exit_code is None
            else ("PASS" if exit_code == 0 else f"FAIL({exit_code})")
        )
        print(f"{name.upper()}={status}")
    print(
        "AUTHORITY="
        + (
            "NOT_RUN"
            if not authority_checked
            else (
                "PASS" if not authority_failures else f"FAIL({len(authority_failures)})"
            )
        )
    )
    for failure in authority_failures:
        print(f"AUTHORITY_FAILURE={failure}")
    print(f"IDENTITY_STABLE={identity_stable}")
    print(f"EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'FAIL'}")
    return passed, report_path


def batch_requirements(
    specs: Sequence[CheckpointSpec],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Collect source requirements in deterministic caller/first-seen order."""
    if not specs or len({spec.name for spec in specs}) != len(specs):
        raise ValueError("batch requires distinct registered checkpoints")
    return (
        tuple(dict.fromkeys(path for spec in specs for path in spec.tests)),
        tuple(dict.fromkeys(path for spec in specs for path in spec.ruff_paths)),
    )


def verify_batch(
    specs: Sequence[CheckpointSpec],
    *,
    repo_root: Path,
    evidence_root: Path,
) -> tuple[bool, Path]:
    """Share source commands while independently checking every authority."""
    tests, ruff_paths = batch_requirements(specs)
    state_before = _git_state(repo_root)
    if state_before["porcelain"]:
        raise RuntimeError("source gate requires a clean worktree")
    evidence_dir = evidence_root / f"source-gate-batch-{_stamp()}"
    command_dir = evidence_dir / "commands"
    command_dir.mkdir(parents=True, exist_ok=False)
    shared = CheckpointSpec(
        name="source_gate_batch",
        description="shared source requirements",
        tests=tests,
        ruff_paths=ruff_paths,
        authority_check=lambda repo: (),
    )
    phase = _source_gate_phase()
    shard = _source_gate_shard()
    if phase != "tests" and shard is not None:
        raise RuntimeError("test shard is valid only for tests phase")
    selected_tests = tests
    if phase == "tests" and shard is not None:
        selected_tests = duration_balanced_test_shards(tests, shard[1])[shard[0]]
    steps = build_verification_steps(
        shared,
        python_executable=sys.executable,
        basetemp=evidence_dir / "pytest",
        tests=selected_tests,
    )
    static_steps, test_steps = _source_gate_steps(steps, phase)
    counter = 0

    def execute(step: Step, diagnostic: bool) -> CommandOutcome:
        nonlocal counter
        counter += 1
        return _execute_step(
            step,
            repo_root=repo_root,
            command_dir=command_dir,
            index=counter,
            diagnostic=diagnostic,
        )

    outcomes: list[CommandOutcome] = []
    authority_requested = phase in {"all", "static"}
    authority_checked = False
    authority_failures: dict[str, tuple[str, ...]] = {spec.name: () for spec in specs}
    if static_steps:
        outcomes.extend(run_verification_steps(static_steps, execute))
    static_pass = all(
        outcome.exit_code == 0
        for outcome in outcomes
        if not outcome.name.endswith("_diagnostic")
    )
    if authority_requested and static_pass:
        authority_checked = True
        for spec in specs:
            try:
                authority_failures[spec.name] = spec.authority_check(repo_root)
            except Exception as exc:
                authority_failures[spec.name] = (f"{type(exc).__name__}: {exc}",)
    if test_steps and (
        phase == "tests" or (static_pass and not any(authority_failures.values()))
    ):
        outcomes.extend(run_verification_steps(test_steps, execute))
    state_after = _git_state(repo_root)
    primary = {
        outcome.name: outcome.exit_code
        for outcome in outcomes
        if not outcome.name.endswith("_diagnostic")
    }
    required = {
        "all": ("git_diff_check", "ruff_check", "ruff_format", "pytest"),
        "static": ("git_diff_check", "ruff_check", "ruff_format"),
        "tests": ("pytest",),
    }[phase]
    commands_pass = all(primary.get(name) == 0 for name in required)
    if (
        phase == "all"
        and static_pass
        and any(authority_failures.values())
        and "pytest" not in primary
    ):
        commands_pass = True
    identity_stable = (
        state_before["head"] == state_after["head"]
        and state_before["tree"] == state_after["tree"]
        and not state_after["porcelain"]
    )
    passed = (
        commands_pass
        and identity_stable
        and (not authority_checked or not any(authority_failures.values()))
    )
    report_path = evidence_dir / "report.json"
    participants = {}
    for spec in specs:
        participants[spec.name] = {
            "checkpoint": spec.name,
            "batch_report": str(report_path),
            "tests": list(spec.tests),
            "ruff_paths": list(spec.ruff_paths),
            "tests_covered": all(path in tests for path in spec.tests),
            "ruff_paths_covered": all(path in ruff_paths for path in spec.ruff_paths),
            "authority_failures": list(authority_failures[spec.name]),
            "authority_status": (
                "NOT_RUN"
                if not authority_checked
                else ("FAIL" if authority_failures[spec.name] else "PASS")
            ),
            "source_before": state_before,
            "source_after": state_after,
            "status": "PASS"
            if commands_pass and identity_stable and not authority_failures[spec.name]
            else "FAIL",
        }
    report = {
        "schema": SCHEMA,
        "kind": "source_gate_batch",
        "checkpoints": [spec.name for spec in specs],
        "source_before": state_before,
        "source_after": state_after,
        "identity_stable": identity_stable,
        "tests": list(tests),
        "ruff_paths": list(ruff_paths),
        "commands": [asdict(outcome) for outcome in outcomes],
        "authority_failures": authority_failures,
        "participants": participants,
        "production_effects": "NOT_RUN",
        "scheduler_mutation": "NOT_RUN",
        "provider_effects": "NOT_RUN",
        "broker_live_effects": "NOT_RUN",
        "phase": phase,
        "test_shard": None if shard is None else {"index": shard[0], "count": shard[1]},
        "executed_tests": list(selected_tests) if "pytest" in primary else [],
        "authority_checked": authority_checked,
        "status": "PASS" if passed else "FAIL",
    }
    _write_json(report_path, report)
    print(
        f"CHECKPOINTS={len(specs)} TEST_PATHS={len(tests)} "
        f"EXECUTED_TEST_PATHS={len(selected_tests) if 'pytest' in primary else 0} "
        f"RUFF_PATHS={len(ruff_paths)} PHASE={phase}"
    )
    for name in ("git_diff_check", "ruff_check", "ruff_format", "pytest"):
        exit_code = primary.get(name)
        print(f"{name.upper()}={'SKIP' if exit_code is None else exit_code}")
    for name, failures in authority_failures.items():
        print(
            f"AUTHORITY[{name}]="
            + ("NOT_RUN" if not authority_checked else ("FAIL" if failures else "PASS"))
        )
        for failure in failures:
            print(f"AUTHORITY_FAILURE[{name}]={failure}")
    print(f"IDENTITY_STABLE={identity_stable}")
    print(f"EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'FAIL'}")
    return passed, report_path


def classify_changed_paths(paths: Sequence[str]) -> str:
    """Only a nonempty, known set of strictly docs/ paths takes the fast path."""
    if paths and all(
        path.startswith("docs/")
        and all(part not in {"", ".", ".."} for part in path.split("/"))
        and "\\" not in path
        and "\x00" not in path
        for path in paths
    ):
        return "DOCS_ONLY"
    return "FULL"


def _ci_changes(repo_root: Path, head: str) -> dict[str, object]:
    """Read a closed event base; unavailable/unknown ranges always run FULL."""
    fallback = {
        "mode": "FULL",
        "base": None,
        "changed_paths": [],
        "reason": "event base unavailable",
    }
    try:
        event = json.loads(
            Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
        )
        if not isinstance(event, dict):
            return fallback
        event_name = os.environ.get("GITHUB_EVENT_NAME")
        if event_name == "push":
            base = event.get("before")
        elif event_name == "pull_request":
            base = event["pull_request"]["base"]["sha"]
        else:
            return fallback
        if (
            not isinstance(base, str)
            or len(base) != 40
            or set(base) == {"0"}
            or any(char not in "0123456789abcdef" for char in base)
        ):
            return fallback
        if _git_output(repo_root, "cat-file", "-t", base) != "commit":
            return fallback
        _git_output(repo_root, "merge-base", "--is-ancestor", base, head)
        # Disable rename detection: moving source into docs must include deletion
        # of the old source path. NUL delimiters preserve unusual filenames.
        changed = subprocess.run(
            ("git", "diff", "--name-only", "-z", "--no-renames", base, head, "--"),
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        raw = changed.stdout.decode("utf-8")
        if changed.returncode != 0 or (raw and not raw.endswith("\x00")):
            return fallback
        paths = raw.removesuffix("\x00").split("\x00") if raw else []
        mode = classify_changed_paths(paths)
        return {
            "mode": mode,
            "base": base,
            "changed_paths": paths,
            "reason": "all changed paths under docs/"
            if mode == "DOCS_ONLY"
            else "non-docs or empty diff",
        }
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RuntimeError):
        return fallback


def verify_ci_changes(
    *,
    repo_root: Path,
    evidence_root: Path,
    docs_only: bool = False,
) -> tuple[bool, Path]:
    """Classify CI changes or validate the docs-only range without dependencies."""
    before = _git_state(repo_root)
    if before["porcelain"]:
        raise RuntimeError("CI change gate requires a clean worktree")
    changes = _ci_changes(repo_root, str(before["head"]))
    evidence_dir = (
        evidence_root / f"{'docs-only' if docs_only else 'ci-changes'}-{_stamp()}"
    )
    evidence_dir.mkdir(parents=True, exist_ok=False)
    outcomes = ()
    if docs_only and changes["mode"] == "DOCS_ONLY":
        command_dir = evidence_dir / "commands"
        command_dir.mkdir()
        step = Step(
            "git_range_diff_check",
            ("git", "diff", "--check", str(changes["base"]), str(before["head"]), "--"),
        )
        outcomes = (
            _execute_step(step, repo_root=repo_root, command_dir=command_dir, index=1),
        )
    after = _git_state(repo_root)
    stable = (
        before["head"] == after["head"]
        and before["tree"] == after["tree"]
        and not after["porcelain"]
    )
    passed = stable and (
        not docs_only or (changes["mode"] == "DOCS_ONLY" and outcomes[0].exit_code == 0)
    )
    report_path = evidence_dir / "report.json"
    _write_json(
        report_path,
        {
            "schema": SCHEMA,
            "kind": "docs_only_gate" if docs_only else "ci_change_classification",
            **changes,
            "source_before": before,
            "source_after": after,
            "identity_stable": stable,
            "status": "PASS" if passed else "FAIL",
            "commands": [asdict(outcome) for outcome in outcomes],
            "production_effects": "NOT_RUN",
            "scheduler_mutation": "NOT_RUN",
            "provider_effects": "NOT_RUN",
            "broker_live_effects": "NOT_RUN",
        },
    )
    if not docs_only and os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"mode={changes['mode'] if passed else 'FULL'}\n")
    print(f"MODE={changes['mode']} EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'FAIL'}")
    return passed, report_path


def preflight_checkpoint(
    spec: CheckpointSpec,
    *,
    repo_root: Path,
    evidence_root: Path,
) -> tuple[bool, Path | None]:
    if spec.preflight is None:
        raise RuntimeError(f"checkpoint has no read-only preflight: {spec.name}")

    state_before = _git_state(repo_root)
    if state_before["porcelain"]:
        raise RuntimeError(
            f"preflight requires a clean worktree; found: {state_before['porcelain']}"
        )
    if spec.name == SUPERVISED_INSTALLATION_OPERATOR_NAME:
        _supervised_installation_admission(repo_root, state_before)
        if spec != _checkpoint_specs()[SUPERVISED_INSTALLATION_OPERATOR_NAME]:
            raise RuntimeError("installation registration rejected")
    if spec.name == SUPERVISED_PUBLICATION_RECOVERY_NAME:
        _supervised_publication_admission(repo_root, state_before)
        if spec != _checkpoint_specs()[SUPERVISED_PUBLICATION_RECOVERY_NAME]:
            raise RuntimeError("publication recovery registration rejected")

    if spec.name == ARCH134_F2_NAME:
        from trading_bot.review_paper.five_session_soak_readiness import PARENT, ROOT

        if (
            repo_root.resolve() != ROOT
            or spec != _checkpoint_specs()[ARCH134_F2_NAME]
            or state_before["branch"] != ARCH134_F2_BRANCH
            or _arch134_f2_authority_check(repo_root)
        ):
            raise RuntimeError("F2 preflight source admission rejected")
        candidate = evidence_root.resolve()
        if any(
            candidate.is_relative_to(p.resolve())
            for p in (
                ROOT,
                PARENT,
                Path(r"F:\AITradingBot"),
                *tuple(
                    Path(line[9:])
                    for line in _git_output(
                        repo_root, "worktree", "list", "--porcelain"
                    ).splitlines()
                    if line.startswith("worktree ")
                ),
            )
        ):
            raise RuntimeError("F2 external evidence required")

    local_branch = str(state_before["branch"])
    remote_branch = spec.remote_branch
    if remote_branch is None:
        if local_branch == "HEAD":
            raise RuntimeError(
                "detached preflight requires a checkpoint-pinned remote branch"
            )
        remote_branch = local_branch

    if spec.remote_head_env is None:
        remote_head = _remote_branch_head(repo_root, remote_branch)
        remote_head_source = "LIVE_REMOTE_LOOKUP"
    else:
        remote_head = _trusted_remote_head_from_env(spec.remote_head_env)
        remote_head_source = f"TRUSTED_ENV:{spec.remote_head_env}"

    if remote_head != state_before["head"]:
        raise RuntimeError(
            "preflight source is not the live remote branch head: "
            f"local={state_before['head']} "
            f"remote={remote_head} branch={remote_branch}"
        )

    installation = spec.name in {
        SUPERVISED_INSTALLATION_OPERATOR_NAME,
        SUPERVISED_PUBLICATION_RECOVERY_NAME,
    }
    evidence_dir = None
    if not installation:
        evidence_dir = evidence_root / spec.name / f"preflight-{_stamp()}"
        evidence_dir.mkdir(parents=True, exist_ok=False)

    result = spec.preflight()
    state_after = _git_state(repo_root)
    identity_stable = (
        state_before["head"] == state_after["head"]
        and state_before["tree"] == state_after["tree"]
        and state_before["branch"] == state_after["branch"]
        and not state_after["porcelain"]
    )
    if spec.name == ARCH134_F2_NAME:
        from trading_bot.review_paper.five_session_soak_readiness import (
            READY,
            validate_result,
        )

        try:
            validate_result(result)
            ready = result["status"] == READY
        except (ValueError, TypeError, KeyError):
            raise RuntimeError("F2 readiness evidence rejected") from None
        passed = ready and identity_stable
    else:
        passed = result.get("status") == "PASS" and identity_stable

    report = {
        "schema": SCHEMA,
        "kind": "read_only_preflight",
        "checkpoint": spec.name,
        "description": spec.description,
        "status": "PASS" if passed else "BLOCKED",
        "source": {
            "before": state_before,
            "after": state_after,
            "remote_branch": remote_branch,
            "remote_head": remote_head,
            "remote_head_source": remote_head_source,
            "identity_stable": identity_stable,
        },
        "result": result,
        "production_effects": "NOT_RUN",
        "protected_execution": "NOT_AUTHORIZED",
    }
    report_path = None if evidence_dir is None else evidence_dir / "report.json"
    if report_path is None:
        print("PREFLIGHT_EVIDENCE=" + json.dumps(report, sort_keys=True))
    else:
        _write_json(report_path, report)

    primary = result.get("primary")
    if isinstance(primary, dict):
        print(f"PRIMARY_STATUS={primary.get('status')}")
        if primary.get("reason") is not None:
            print(f"PRIMARY_REASON={primary.get('reason')}")
        if primary.get("detail") is not None:
            print(f"PRIMARY_DETAIL={primary.get('detail')}")

    diagnostics = result.get("diagnostics")
    if isinstance(diagnostics, dict):
        for name, diagnostic in diagnostics.items():
            if isinstance(diagnostic, dict):
                print(f"DIAGNOSTIC={name}")
                print(f"DIAGNOSTIC_STATUS={diagnostic.get('status')}")
                if diagnostic.get("reason") is not None:
                    print(f"DIAGNOSTIC_REASON={diagnostic.get('reason')}")
                if diagnostic.get("detail") is not None:
                    print(f"DIAGNOSTIC_DETAIL={diagnostic.get('detail')}")

    print(f"IDENTITY_STABLE={identity_stable}")
    print(f"EVIDENCE={report_path if report_path is not None else 'STDOUT'}")
    print(f"OVERALL={'PASS' if passed else 'BLOCKED'}")
    return passed, report_path


def execute_checkpoint(
    spec: CheckpointSpec,
    *,
    repo_root: Path,
    evidence_root: Path,
) -> tuple[bool, Path]:
    global _installation_execution_admitted, _installation_execution_source
    global _publication_execution_source
    if spec.execute is None:
        raise RuntimeError(f"checkpoint has no protected execution: {spec.name}")

    state_before = _git_state(repo_root)
    if state_before["porcelain"]:
        raise RuntimeError(
            f"protected execution requires a clean worktree; "
            f"found: {state_before['porcelain']}"
        )

    installation = spec.name == SUPERVISED_INSTALLATION_OPERATOR_NAME
    if installation:
        from trading_bot.supervised_release import installation_operator as operator

        _supervised_installation_admission(repo_root, state_before)
        if spec != _checkpoint_specs()[SUPERVISED_INSTALLATION_OPERATOR_NAME]:
            raise RuntimeError("installation registration rejected")
        if os.environ.get(operator.AUTH_ENV) != operator.AUTH_VALUE:
            raise RuntimeError("installation authorization interlock rejected")
        if _supervised_installation_latch_consumed():
            raise RuntimeError(
                "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY: "
                "consumed installation attempt; MAY_HAVE_OCCURRED"
            )

    local_branch = str(state_before["branch"])
    remote_branch = spec.remote_branch
    if remote_branch is None:
        if local_branch == "HEAD":
            raise RuntimeError(
                "detached protected execution requires a checkpoint-pinned "
                "remote branch"
            )
        remote_branch = local_branch

    remote_head = _remote_branch_head(repo_root, remote_branch)
    if remote_head != state_before["head"]:
        raise RuntimeError(
            "protected execution source is not the live remote branch head: "
            f"local={state_before['head']} "
            f"remote={remote_head} branch={remote_branch}"
        )

    evidence_dir = evidence_root / spec.name / f"execute-{_stamp()}"
    evidence_dir.mkdir(parents=True, exist_ok=False)
    attempt_path = evidence_dir / "attempt.json"
    _write_json(
        attempt_path,
        {
            "schema": SCHEMA,
            "kind": "protected_execution_attempt",
            "checkpoint": spec.name,
            "description": spec.description,
            "status": "STARTED",
            "source": {
                "before": state_before,
                "remote_branch": remote_branch,
                "remote_head": remote_head,
            },
            "automatic_retry": "NOT_AUTHORIZED",
        },
    )

    try:
        if installation:
            _installation_execution_admitted = True
            _installation_execution_source = (
                str(state_before["head"]),
                str(state_before["tree"]),
            )
        if spec.name == SUPERVISED_PUBLICATION_RECOVERY_NAME:
            _supervised_publication_admission(repo_root, state_before)
            if spec != _checkpoint_specs()[SUPERVISED_PUBLICATION_RECOVERY_NAME]:
                raise RuntimeError("publication recovery registration rejected")
            _publication_execution_source = (
                str(state_before["head"]),
                str(state_before["tree"]),
            )
        try:
            result = spec.execute()
        finally:
            _publication_execution_source = None
            if installation:
                _installation_execution_admitted = False
                _installation_execution_source = None
    except Exception as exc:
        state_after = _git_state(repo_root)
        identity_stable = (
            state_before["head"] == state_after["head"]
            and state_before["tree"] == state_after["tree"]
            and state_before["branch"] == state_after["branch"]
            and not state_after["porcelain"]
        )
        report = {
            "schema": SCHEMA,
            "kind": "protected_execution",
            "checkpoint": spec.name,
            "description": spec.description,
            "status": "STOPPED",
            "source": {
                "before": state_before,
                "after": state_after,
                "remote_branch": remote_branch,
                "remote_head": remote_head,
                "identity_stable": identity_stable,
            },
            "runner_error": {
                "type": "INSTALLATION_STOPPED" if installation else type(exc).__name__,
                "detail": "PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY"
                if installation
                else str(exc),
            },
            "effect_disposition": "MAY_HAVE_OCCURRED",
            "protected_execution": "ATTEMPTED",
            "automatic_retry": "NOT_AUTHORIZED",
        }
        report_path = evidence_dir / "report.json"
        _write_json(report_path, report)
        if installation:
            print(
                "RUNNER_EXECUTION_ERROR=INSTALLATION_STOPPED:PRESERVE_INSTALLATION_EVIDENCE_NO_RETRY",
                file=sys.stderr,
            )
        else:
            print(f"RUNNER_EXECUTION_ERROR={type(exc).__name__}:{exc}", file=sys.stderr)
        print(f"IDENTITY_STABLE={identity_stable}")
        print(f"EVIDENCE={report_path}")
        print("OVERALL=STOPPED")
        return False, report_path

    state_after = _git_state(repo_root)
    identity_stable = (
        state_before["head"] == state_after["head"]
        and state_before["tree"] == state_after["tree"]
        and state_before["branch"] == state_after["branch"]
        and not state_after["porcelain"]
    )
    passed = result.get("status") == "PASS" and identity_stable
    if spec.name == SUPERVISED_PUBLICATION_RECOVERY_NAME and not identity_stable:
        result = {
            "status": "INDETERMINATE",
            "effect_disposition": "MAY_HAVE_OCCURRED",
            "automatic_retry": "NOT_AUTHORIZED",
            "primary": {
                "status": "INDETERMINATE",
                "reason": "RUNNER_SOURCE_DRIFT",
                "disposition": "PRESERVE_PUBLICATION_EVIDENCE_NO_RETRY",
            },
        }
    effect_disposition = result.get("effect_disposition", "MAY_HAVE_OCCURRED")

    report = {
        "schema": SCHEMA,
        "kind": "protected_execution",
        "checkpoint": spec.name,
        "description": spec.description,
        "status": "PASS" if passed else "STOPPED",
        "source": {
            "before": state_before,
            "after": state_after,
            "remote_branch": remote_branch,
            "remote_head": remote_head,
            "identity_stable": identity_stable,
        },
        "result": result,
        "effect_disposition": effect_disposition,
        "protected_execution": "ATTEMPTED",
        "automatic_retry": "NOT_AUTHORIZED",
    }
    report_path = evidence_dir / "report.json"
    _write_json(report_path, report)

    primary = result.get("primary")
    if isinstance(primary, dict):
        print(f"PRIMARY_STATUS={primary.get('status')}")
        if primary.get("reason") is not None:
            print(f"PRIMARY_REASON={primary.get('reason')}")
        if primary.get("detail") is not None:
            print(f"PRIMARY_DETAIL={primary.get('detail')}")
    print(f"EFFECT_DISPOSITION={effect_disposition}")
    print(f"IDENTITY_STABLE={identity_stable}")
    print(f"EVIDENCE={report_path}")
    print(f"OVERALL={'PASS' if passed else 'STOPPED'}")
    return passed, report_path


def _status(repo_root: Path, specs: Mapping[str, CheckpointSpec]) -> int:
    state = _git_state(repo_root)
    print(f"SCHEMA={SCHEMA}")
    print(f"REPO={repo_root}")
    print(f"HEAD={state['head']}")
    print(f"TREE={state['tree']}")
    print(f"BRANCH={state['branch']}")
    print(f"CLEAN={not bool(state['porcelain'])}")
    print("READ_ONLY_PREFLIGHT=IMPLEMENTED_FOR_REGISTERED_PROFILES")
    execute_specs = sorted(
        name for name, spec in specs.items() if spec.execute is not None
    )
    print(
        "PROTECTED_EXECUTION="
        + (
            "IMPLEMENTED_FOR_" + ",".join(execute_specs)
            if execute_specs
            else "NOT_IMPLEMENTED"
        )
    )
    print("CHECKPOINTS=" + ",".join(sorted(specs)))
    for name in sorted(specs):
        print(f"{name}: {specs[name].description}")
    return 0


def _parser(specs: Mapping[str, CheckpointSpec]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="show runner and repository status")

    verify = subparsers.add_parser(
        "verify",
        help="run a source-only checkpoint gate",
    )
    verify.add_argument("checkpoint", choices=sorted(specs))
    verify.add_argument(
        "--evidence-root",
        type=Path,
        help="override the external checkpoint evidence root",
    )

    batch = subparsers.add_parser("verify-batch", help="share registered source gates")
    batch.add_argument("checkpoints", nargs="+", choices=sorted(specs))
    batch.add_argument("--evidence-root", type=Path)
    for command in ("classify-ci", "verify-docs"):
        changes = subparsers.add_parser(command, help="source-only CI change gate")
        changes.add_argument("--evidence-root", type=Path)

    preflight_specs = sorted(
        name for name, spec in specs.items() if spec.preflight is not None
    )
    preflight = subparsers.add_parser(
        "preflight",
        help="run a registered read-only host preflight",
    )
    preflight.add_argument("checkpoint", choices=preflight_specs)
    preflight.add_argument(
        "--evidence-root",
        type=Path,
        help="override the external checkpoint evidence root",
    )

    execute_specs = sorted(
        name for name, spec in specs.items() if spec.execute is not None
    )
    execute = subparsers.add_parser(
        "execute",
        help="run a registered protected checkpoint after explicit authorization",
    )
    execute.add_argument("checkpoint", choices=execute_specs)
    execute.add_argument(
        "--evidence-root",
        type=Path,
        help="override the external checkpoint evidence root",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    specs = _checkpoint_specs()
    parser = _parser(specs)
    args = parser.parse_args(argv)
    if args.command == "verify-batch" and len(set(args.checkpoints)) != len(
        args.checkpoints
    ):
        parser.error("duplicate checkpoint names are not allowed")

    if args.command == "status":
        return _status(repo_root, specs)

    evidence_root = (
        args.evidence_root
        if args.evidence_root is not None
        else _default_evidence_root(repo_root)
    )

    try:
        if args.command == "verify-batch":
            passed, _ = verify_batch(
                [specs[name] for name in args.checkpoints],
                repo_root=repo_root,
                evidence_root=evidence_root,
            )
            return 0 if passed else 1
        if args.command in {"classify-ci", "verify-docs"}:
            passed, _ = verify_ci_changes(
                repo_root=repo_root,
                evidence_root=evidence_root,
                docs_only=args.command == "verify-docs",
            )
            return 0 if passed else 1
        spec = specs[args.checkpoint]
        if args.command == "verify":
            passed, _ = verify_checkpoint(
                spec,
                repo_root=repo_root,
                evidence_root=evidence_root,
            )
        elif args.command == "preflight":
            passed, _ = preflight_checkpoint(
                spec,
                repo_root=repo_root,
                evidence_root=evidence_root,
            )
        else:
            passed, _ = execute_checkpoint(
                spec,
                repo_root=repo_root,
                evidence_root=evidence_root,
            )
    except Exception as exc:
        if getattr(
            args, "checkpoint", None
        ) == SUPERVISED_INSTALLATION_OPERATOR_NAME and args.command in {
            "preflight",
            "execute",
        }:
            print(
                "RUNNER_ERROR=INSTALLATION_AUTHORITY_REJECTED_OR_CONSUMED:NO_RETRY",
                file=sys.stderr,
            )
        else:
            print(f"RUNNER_ERROR={type(exc).__name__}:{exc}", file=sys.stderr)
        return 2

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
