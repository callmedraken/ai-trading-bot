"""Shared validation helpers for domain values."""

from datetime import UTC, datetime
from decimal import Decimal


def require_decimal(value: Decimal, field_name: str) -> Decimal:
    """Return a Decimal or reject values that could introduce float error."""
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal")
    return value


def require_positive_decimal(value: Decimal, field_name: str) -> Decimal:
    """Return a strictly positive Decimal."""
    require_decimal(value, field_name)
    if value <= Decimal("0"):
        raise ValueError(f"{field_name} must be greater than zero")
    return value


def normalize_utc(value: datetime, field_name: str) -> datetime:
    """Require an aware datetime and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
