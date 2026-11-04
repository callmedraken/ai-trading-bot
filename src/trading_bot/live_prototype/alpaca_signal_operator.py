"""D33 one-shot read-only operator for Alpaca current signal inputs."""

from __future__ import annotations

import json
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from trading_bot.live_prototype.alpaca_signal_inputs import (
    AlpacaSignalInputService,
    SignalInputResult,
)
from trading_bot.market_data.alpaca_http import AlpacaHistoricalBarsTransport
from trading_bot.review_paper.alpaca_windows_credentials import (
    read_current_product_alpaca_secrets,
)

D33_FEATURE_BRANCH = "feature/robinhood-live-prototype-current"
D33_SOURCE_ADMISSION_FAILURE = "D33_SOURCE_ADMISSION_BLOCKED"
D33_EVIDENCE_SCHEMA = "arch147-d33-alpaca-signal-observation/v1"
_EXPECTED_ORIGIN = "https://github.com/callmedraken/ai-trading-bot.git"
_EVIDENCE_PARENT = Path(r"F:\AI\temp")


@dataclass(frozen=True, slots=True)
class SourceAdmission:
    """Read-only source identities proved before any provider construction."""

    branch: str
    head: str
    tree: str
    origin_develop: str
    origin_feature: str


@dataclass(frozen=True, slots=True)
class D33ObservationResult:
    """Sanitized operator outcome and external evidence location."""

    status: str
    reason: str
    evidence_path: Path | None
    source: SourceAdmission | None
    signal_inputs: SignalInputResult | None


def admit_current_source(repo_root: Path | None = None) -> SourceAdmission:
    """Require the clean, exact current Architecture-147 feature source.

    The shared current source evaluator owns Architecture-147 authority.  Git
    reads here prove the additional feature/origin relationship and do not
    fetch, merge, switch, or mutate any ref.
    """

    root = (
        Path(__file__).resolve().parents[3]
        if repo_root is None
        else Path(repo_root).resolve(strict=True)
    )
    from scripts.current_source_authority import (
        PublicationContext,
        evaluate_source_authority,
    )

    from scripts import checkpoint_runner as runner

    state = runner._git_state(root)
    if state["branch"] != D33_FEATURE_BRANCH or state["porcelain"]:
        raise RuntimeError("D33 source is not clean on its reviewed feature branch")
    origin = runner._git_output(root, "remote", "get-url", "origin")
    if origin != _EXPECTED_ORIGIN:
        raise RuntimeError("D33 origin is not the reviewed repository")
    origin_develop = runner._git_output(root, "rev-parse", "origin/develop")
    origin_feature = runner._git_output(
        root, "rev-parse", f"origin/{D33_FEATURE_BRANCH}"
    )
    if origin_feature != state["head"]:
        raise RuntimeError("D33 feature source is not the exact remote source")
    runner._git_output(root, "merge-base", "--is-ancestor", origin_develop, "HEAD")
    specs = runner._checkpoint_specs()
    spec = specs[runner.ARCH147_PROTOTYPE_NAME]
    authority = evaluate_source_authority(
        root,
        publication_context=PublicationContext.FEATURE,
        checkpoints=(spec,),
    )
    if authority.failures:
        raise RuntimeError("D33 current source authority is unavailable")
    return SourceAdmission(
        branch=str(state["branch"]),
        head=str(state["head"]),
        tree=str(state["tree"]),
        origin_develop=origin_develop,
        origin_feature=origin_feature,
    )


def run_d33_read_only_observation(
    *,
    observation_as_of: datetime,
    evidence_dir: Path | None = None,
    repo_root: Path | None = None,
    source_admitter: Callable[[Path], SourceAdmission] | None = None,
    credential_reader: Callable[[], object] | None = None,
    transport_factory: Callable[[], AlpacaHistoricalBarsTransport] | None = None,
) -> D33ObservationResult:
    """Run one source-admitted, one-request, non-broker observation.

    No retry exists in this operator.  Source admission runs before the
    credential reader or transport factory is touched.  The default transport
    is the accepted stdlib Alpaca HTTPS transport selected by the data service.
    """

    root = (
        Path(__file__).resolve().parents[3]
        if repo_root is None
        else Path(repo_root).resolve(strict=True)
    )
    try:
        output_dir = _fresh_evidence_dir(evidence_dir)
    except (OSError, ValueError):
        return D33ObservationResult(
            "BLOCKED", "D33_EVIDENCE_PATH_INVALID", None, None, None
        )

    admit = admit_current_source if source_admitter is None else source_admitter
    try:
        source = admit(root)
    except Exception:
        result = D33ObservationResult(
            "BLOCKED", D33_SOURCE_ADMISSION_FAILURE, None, None, None
        )
        evidence_path = _write_evidence(output_dir, result, observation_as_of)
        return D33ObservationResult(
            result.status,
            result.reason,
            evidence_path,
            result.source,
            result.signal_inputs,
        )

    service = AlpacaSignalInputService(
        credential_reader=(
            read_current_product_alpaca_secrets
            if credential_reader is None
            else credential_reader
        ),
        transport_factory=transport_factory,
    )
    signal_result = service.observe(observation_as_of)
    result = D33ObservationResult(
        signal_result.status,
        signal_result.reason,
        None,
        source,
        signal_result,
    )
    evidence_path = _write_evidence(output_dir, result, observation_as_of)
    return D33ObservationResult(
        result.status,
        result.reason,
        evidence_path,
        result.source,
        result.signal_inputs,
    )


def _fresh_evidence_dir(candidate: Path | None) -> Path:
    if candidate is None:
        candidate = _EVIDENCE_PARENT / ("arch147-d33-" + uuid4().hex)
    path = Path(candidate)
    parent = _EVIDENCE_PARENT.resolve(strict=True)
    if not path.is_absolute() or path.drive.casefold() != "f:":
        raise ValueError("D33 evidence path must be an absolute F: path")
    if path.exists() or path.is_symlink():
        raise ValueError("D33 evidence output already exists")
    if not path.parent.exists() or path.parent.resolve(strict=True) != path.parent:
        raise ValueError("D33 evidence parent must not be an alias")
    if not path.parent.resolve(strict=True).is_relative_to(parent):
        raise ValueError("D33 evidence path is outside F:\\AI\\temp")
    current = path.parent
    while True:
        if current.resolve(strict=True) != current:
            raise ValueError("D33 evidence ancestor must not be an alias")
        if _has_reparse_point(current):
            raise ValueError("D33 evidence ancestor is a reparse point")
        if current == parent:
            break
        if current.parent == current:
            raise ValueError("D33 evidence path escaped allowed parent")
        current = current.parent
    path.mkdir()
    return path


def _has_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _write_evidence(
    output_dir: Path,
    result: D33ObservationResult,
    observation_as_of: datetime,
) -> Path:
    signal = result.signal_inputs
    body: dict[str, object] = {
        "schema": D33_EVIDENCE_SCHEMA,
        "status": result.status,
        "reason": result.reason,
        "observation_as_of": _safe_timestamp(observation_as_of),
        "source": None
        if result.source is None
        else {
            "branch": result.source.branch,
            "head": result.source.head,
            "tree": result.source.tree,
            "origin_develop": result.source.origin_develop,
            "origin_feature": result.source.origin_feature,
        },
        "request": None,
        "selected_sessions": [],
        "response_body_sha256": None,
        "response_body_byte_length": None,
        "request_id_digest": None,
        "completed_signal_inputs_digest": None,
        "fast_average": None,
        "slow_average": None,
        "flat_signal": None,
        "invested_signal": None,
        "provider_call_count": 0,
        "credential_read_count": 0,
        "production_mutations": 0,
        "broker_mutations": 0,
        "runtime_binding_mutations": 0,
        "campaign_runs": 0,
        "final_holdout_accesses": 0,
    }
    if signal is not None:
        body.update(
            {
                "request": None
                if signal.request is None
                else {
                    "method": signal.request.method,
                    "host": signal.request.host,
                    "target": signal.request.target,
                    "public_headers": list(signal.request.public_headers),
                },
                "selected_sessions": [
                    item.isoformat() for item in signal.selected_sessions
                ],
                "response_body_sha256": signal.response_body_sha256,
                "response_body_byte_length": signal.response_body_byte_length,
                "request_id_digest": signal.request_id_digest,
                "completed_signal_inputs_digest": None
                if signal.inputs is None
                else signal.inputs.digest,
                "fast_average": _decimal_text(signal.fast_average),
                "slow_average": _decimal_text(signal.slow_average),
                "flat_signal": None
                if signal.flat_signal is None
                else signal.flat_signal.value,
                "invested_signal": None
                if signal.invested_signal is None
                else signal.invested_signal.value,
                "provider_call_count": signal.provider_call_count,
                "credential_read_count": signal.credential_read_count,
            }
        )
    path = output_dir / "evidence.json"
    if path.exists() or path.is_symlink():
        raise ValueError("D33 evidence output already exists")
    path.write_text(
        json.dumps(body, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _safe_timestamp(value: datetime) -> str | None:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        return None
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _decimal_text(value: object) -> str | None:
    if type(value) is not Decimal:
        return None
    return format(value, "f")


__all__ = [
    "D33ObservationResult",
    "D33_FEATURE_BRANCH",
    "D33_SOURCE_ADMISSION_FAILURE",
    "SourceAdmission",
    "admit_current_source",
    "run_d33_read_only_observation",
]
