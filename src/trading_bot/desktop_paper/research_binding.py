"""Validated external research binding for the P5A paper-evaluation lane."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final
from uuid import UUID

from trading_bot.desktop_paper.configuration import (
    PaperEvaluationConfig,
    PaperStrategyBinding,
    create_paper_evaluation_config,
)
from trading_bot.desktop_paper.models import PaperRuntimePolicy
from trading_bot.domain import Symbol
from trading_bot.experiments.filtered_trend_bundle import ResearchBundle
from trading_bot.experiments.filtered_trend_data import UNIVERSE

ACCEPTED_FILTERED_TREND_BUNDLE_PATH: Final = Path(
    r"F:\AI\research-reports\filtered-trend-6203cbe8\bundle.json"
)
FILTERED_TREND_BUNDLE_SCHEMA: Final = "filtered-trend-bundle/v1"
FILTERED_TREND_CONTEXT_SCHEMA: Final = "filtered-trend-campaign/v1"
FILTERED_TREND_SOURCE_HEAD: Final = "6203cbe8729d585dd3a244448bfa81318c7dfc11"
FILTERED_TREND_SOURCE_TREE: Final = "9529749c33fb1dee3b1271e80e7c08f8be0d004d"
FILTERED_TREND_DATASET_ID: Final = "d5aa8ed7-b5cd-53a3-8671-5370f976e8e3"
FILTERED_TREND_CAMPAIGN_ID: Final = "48ae05d5-ede1-5461-9da9-b5d7744cefad"
FILTERED_TREND_BUNDLE_ID: Final = "3b86c5e0-6053-53af-a499-d297265f3cd8"
FILTERED_TREND_CANDIDATE_ID: Final = "31397ce5-5dc7-5887-b29a-efc5075c5ebf"
FILTERED_TREND_PRICE_BASIS: Final = "ALPACA_ALL_ADJUSTED_PRICE_V1"
FILTERED_TREND_STRATEGY_FAMILY: Final = "FILTERED_TREND_BASE_MA"
FILTERED_TREND_STRATEGY_VERSION: Final = "filtered-trend-base-ma/v1"


class PaperEvaluationBindingRejected(RuntimeError):
    """Raised when an external paper-evaluation bundle is not accepted."""

    code = "PAPER_EVALUATION_BINDING_REJECTED"

    def __init__(self, detail: str = "") -> None:
        super().__init__(self.code if not detail else f"{self.code}: {detail}")


def _reject(detail: str) -> None:
    raise PaperEvaluationBindingRejected(detail)


def _read_bundle_bytes(path: Path) -> bytes:
    if not isinstance(path, Path):
        _reject("bundle path must be a Path")
    if not path.exists():
        raise PaperEvaluationBindingRejected("PAPER_EVALUATION_SELECTION_REQUIRED")
    if path.is_symlink() or not path.is_file():
        _reject("bundle path is not a regular file")
    try:
        return path.read_bytes()
    except (OSError, ValueError) as error:
        raise PaperEvaluationBindingRejected("bundle cannot be read") from error


def _validate_outer_schema(body: bytes) -> None:
    try:
        raw = json.loads(body.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise PaperEvaluationBindingRejected("bundle JSON is malformed") from error
    if type(raw) is not dict or raw.get("schema") != FILTERED_TREND_BUNDLE_SCHEMA:
        _reject("bundle schema mismatch")


def _validate_bundle(
    bundle: ResearchBundle, provenance_digest: str
) -> PaperStrategyBinding:
    context = bundle.context
    if context.get("schema") != FILTERED_TREND_CONTEXT_SCHEMA:
        _reject("context schema mismatch")
    expected_context = {
        "source_head": FILTERED_TREND_SOURCE_HEAD,
        "source_tree": FILTERED_TREND_SOURCE_TREE,
        "dataset_id": FILTERED_TREND_DATASET_ID,
        "price_basis": FILTERED_TREND_PRICE_BASIS,
        "qualification_policy": None,
        "paper_binding": None,
        "live_eligible": False,
        "universe": list(UNIVERSE),
    }
    for name, expected in expected_context.items():
        if context.get(name) != expected:
            _reject(f"{name} mismatch")
    if bundle.campaign_id != FILTERED_TREND_CAMPAIGN_ID:
        _reject("campaign identity mismatch")
    if bundle.bundle_id != FILTERED_TREND_BUNDLE_ID:
        _reject("bundle identity mismatch")

    projection = bundle.to_dict()
    shortlist = projection.get("shortlist")
    if type(shortlist) is not list or len(shortlist) != 10:
        _reject("shortlist must contain exactly ten entries")
    if shortlist[0] != FILTERED_TREND_CANDIDATE_ID:
        _reject("selected candidate is not shortlist ordinal 1")
    if FILTERED_TREND_CANDIDATE_ID not in shortlist:
        _reject("selected candidate is absent from shortlist")

    selected = next(
        (
            summary
            for summary in bundle.summaries
            if summary.candidate_id == FILTERED_TREND_CANDIDATE_ID
        ),
        None,
    )
    if selected is None:
        _reject("selected candidate evidence is absent")
    config = selected.config
    if (
        config.family != "BASE_MA"
        or config.fast != 35
        or config.slow != 50
        or config.parameter != "none"
    ):
        _reject("selected candidate config mismatch")
    if context["universe"][0] != "SPY":
        _reject("frozen universe ordinal 1 is not SPY")

    return PaperStrategyBinding(
        strategy_family=FILTERED_TREND_STRATEGY_FAMILY,
        strategy_version=FILTERED_TREND_STRATEGY_VERSION,
        symbol=Symbol(context["universe"][0]),
        parameter_set=(("fast", 35), ("slow", 50)),
        research_campaign_id=UUID(FILTERED_TREND_CAMPAIGN_ID),
        research_bundle_id=UUID(FILTERED_TREND_BUNDLE_ID),
        research_candidate_id=UUID(FILTERED_TREND_CANDIDATE_ID),
        provenance_digest=provenance_digest,
    )


def load_accepted_paper_binding(
    path: Path = ACCEPTED_FILTERED_TREND_BUNDLE_PATH,
) -> PaperStrategyBinding:
    """Read exact bundle bytes, validate evidence, and derive one binding."""
    body = _read_bundle_bytes(path)
    digest = hashlib.sha256(body).hexdigest()
    _validate_outer_schema(body)
    try:
        bundle = ResearchBundle.from_bytes(body)
        binding = _validate_bundle(bundle, digest)
    except PaperEvaluationBindingRejected:
        raise
    except Exception as error:
        raise PaperEvaluationBindingRejected("bundle evidence is invalid") from error
    return binding


def load_accepted_paper_evaluation_config(
    path: Path = ACCEPTED_FILTERED_TREND_BUNDLE_PATH,
) -> PaperEvaluationConfig:
    """Build the production config only from a validated accepted bundle."""
    return create_paper_evaluation_config(
        load_accepted_paper_binding(path), PaperRuntimePolicy()
    )
