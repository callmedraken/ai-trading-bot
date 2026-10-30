"""Current desktop-only verification projections over frozen 146-A contracts."""

from __future__ import annotations

from hashlib import sha256

from trading_bot.experiments.historical_research_custody import (
    HistoricalResearchCustodyError,
    HistoricalSessionAuthority,
    historical_research_normalized_csv,
)
from trading_bot.experiments.historical_research_dataset import (
    HistoricalResearchDatasetError,
    HistoricalResearchDatasetSnapshot,
    HistoricalResearchDatasetVerification,
    HistoricalResearchPartitionManifest,
    HistoricalResearchPartitionMaterial,
    HistoricalResearchPartitionRole,
    _complete_historical_research_dataset_verification,
    _membership,
    _verify_historical_research_partition_physical,
    parse_historical_research_csv,
)
from trading_bot.experiments.research_strategy_backtest import (
    historical_data_fingerprint,
)
from trading_bot.market_data.models import HistoricalDataResult


def verify_desktop_open_bytes(
    normalized_open_bytes: bytes,
    snapshot: HistoricalResearchDatasetSnapshot,
    open_manifest: HistoricalResearchPartitionManifest,
    holdout_commitment: HistoricalResearchPartitionManifest,
) -> HistoricalDataResult:
    """Verify the OPEN projection without reading holdout or raw bytes."""
    if (
        type(snapshot) is not HistoricalResearchDatasetSnapshot
        or type(open_manifest) is not HistoricalResearchPartitionManifest
        or type(holdout_commitment) is not HistoricalResearchPartitionManifest
    ):
        raise HistoricalResearchDatasetError("exact OPEN contract types required")
    _membership(snapshot, open_manifest, holdout_commitment)
    if type(normalized_open_bytes) is not bytes or not normalized_open_bytes:
        raise HistoricalResearchDatasetError("nonempty OPEN bytes required")
    if (
        sha256(normalized_open_bytes).hexdigest()
        != open_manifest.normalized_file_sha256
        or len(normalized_open_bytes) != open_manifest.normalized_byte_size
    ):
        raise HistoricalResearchDatasetError("OPEN bytes/digest/size mismatch")
    data = parse_historical_research_csv(
        normalized_open_bytes, HistoricalResearchPartitionRole.OPEN
    )
    try:
        canonical = historical_research_normalized_csv(data.bars)
    except HistoricalResearchCustodyError as error:
        raise HistoricalResearchDatasetError("invalid canonical OPEN CSV") from error
    if canonical != normalized_open_bytes:
        raise HistoricalResearchDatasetError("noncanonical OPEN CSV bytes")
    if (
        len(data.bars),
        data.bars[0].timestamp,
        data.bars[-1].timestamp,
        historical_data_fingerprint(data),
    ) != (
        open_manifest.row_count,
        open_manifest.first_bar_timestamp,
        open_manifest.last_bar_timestamp,
        open_manifest.historical_data_fingerprint,
    ):
        raise HistoricalResearchDatasetError("OPEN physical metadata mismatch")
    return data


def verify_desktop_published_dataset(
    snapshot: HistoricalResearchDatasetSnapshot,
    open_material: HistoricalResearchPartitionMaterial,
    holdout_material: HistoricalResearchPartitionMaterial,
    authority: HistoricalSessionAuthority,
) -> HistoricalResearchDatasetVerification:
    """Verify both desktop partitions against accepted published sessions."""
    if type(authority) is not HistoricalSessionAuthority:
        raise HistoricalResearchDatasetError("published session authority required")
    if any(
        type(item) is not HistoricalResearchPartitionMaterial
        for item in (open_material, holdout_material)
    ):
        raise HistoricalResearchDatasetError(
            "both physical partition materials required"
        )
    _membership(snapshot, open_material.manifest, holdout_material.manifest)
    opened = _verify_historical_research_partition_physical(open_material)
    holdout = _verify_historical_research_partition_physical(holdout_material)
    authority.verify(opened)
    authority.verify(holdout)
    return _complete_historical_research_dataset_verification(
        snapshot, open_material, holdout_material, opened, holdout
    )


__all__ = ["verify_desktop_open_bytes", "verify_desktop_published_dataset"]
