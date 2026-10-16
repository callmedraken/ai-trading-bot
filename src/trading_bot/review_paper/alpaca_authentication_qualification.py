"""D1R4 fixed Alpaca authentication probe; no session or trading authority."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5

from trading_bot.domain import Bar, Symbol
from trading_bot.market_calendar import NYSEMarketCalendar
from trading_bot.market_data.alpaca_daily_snapshot import (
    ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
    build_alpaca_historical_bars_request,
    parse_alpaca_historical_bars_response,
)
from trading_bot.market_data.alpaca_http import (
    MAX_ALPACA_RESPONSE_BYTES,
    AlpacaHistoricalBarsRequest,
    AlpacaHttpResponse,
    StdlibAlpacaHistoricalBarsTransport,
)
from trading_bot.market_data.daily_snapshot_models import (
    XNYS_CALENDAR_DESCRIPTOR,
    DailySnapshotCaptureRequest,
)
from trading_bot.market_data.daily_snapshot_provider import (
    BoundMarketCalendar,
    build_daily_provider_request,
)
from trading_bot.market_data.exceptions import (
    AlpacaHttpStatusError,
)
from trading_bot.review_paper.alpaca_windows_credentials import (
    ScopedAlpacaSecrets,
    read_current_product_alpaca_secrets,
)

QUALIFY_AUTH_INTERLOCK = "AUTHORIZE_ARCH134_D1R4_ONE_ALPACA_AUTH_QUALIFICATION"
MAX_AUTH_QUALIFICATION_BYTES = 4096
PROBE_SESSION = date(2026, 10, 7)
PROBE_TIMESTAMP = datetime(2026, 10, 7, 4, tzinfo=UTC)


class AuthQualificationReason(StrEnum):
    PASS = "PASS"
    CREDENTIAL_READ_FAILED = "CREDENTIAL_READ_FAILED"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    HTTP_REJECTED = "HTTP_REJECTED"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    SOURCE_DRIFT = "SOURCE_DRIFT"


def build_authentication_probe() -> AlpacaHistoricalBarsRequest:
    """Freeze the same SPY/SIP/raw/USD daily request as D1's October-7 read."""
    request = DailySnapshotCaptureRequest(
        uuid5(NAMESPACE_URL, "alpaca-authentication-probe/v1:SPY:XNYS:2026-10-07"),
        (Symbol("SPY"),),
        datetime(2026, 10, 8, 4, tzinfo=UTC),
        XNYS_CALENDAR_DESCRIPTOR,
    )
    frozen = build_daily_provider_request(
        request,
        ALPACA_DAILY_SNAPSHOT_DESCRIPTOR,
        BoundMarketCalendar(XNYS_CALENDAR_DESCRIPTOR, NYSEMarketCalendar()),
    )
    if frozen.target_session.session_date != PROBE_SESSION:
        raise ValueError("fixed probe calendar mismatch")
    return build_alpaca_historical_bars_request(frozen)


def _source_identity(value: object) -> None:
    if (
        type(value) is not str
        or len(value) != 40
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("invalid authentication qualification source")


@dataclass(frozen=True, slots=True)
class AlpacaAuthenticationQualification:
    schema: str
    source_head: str
    source_tree: str
    probe_session: str
    probe_method: str
    probe_host: str
    probe_target: str
    status: str
    reason: AuthQualificationReason
    credential_pair_read_attempts: int
    credential_pair_read_succeeded: bool
    alpaca_request_attempts: int
    http_status: int | None
    provider_code: int | None
    source_readmitted: bool

    def __post_init__(self) -> None:
        _source_identity(self.source_head)
        _source_identity(self.source_tree)
        probe = build_authentication_probe()
        fixed = {
            "schema": "alpaca-authentication-qualification/v1",
            "probe_session": PROBE_SESSION.isoformat(),
            "probe_method": probe.method,
            "probe_host": probe.host,
            "probe_target": probe.target,
        }
        if any(
            type(getattr(self, k)) is not str or getattr(self, k) != v
            for k, v in fixed.items()
        ):
            raise ValueError("invalid fixed authentication probe")
        if type(self.reason) is not AuthQualificationReason:
            raise ValueError("invalid authentication qualification reason")
        if type(self.status) is not str or self.status != (
            "PASS" if self.reason is AuthQualificationReason.PASS else "BLOCKED"
        ):
            raise ValueError("invalid authentication qualification status")
        for count in (self.credential_pair_read_attempts, self.alpaca_request_attempts):
            if type(count) is not int or count not in (0, 1):
                raise ValueError("invalid authentication qualification budget")
        if (
            type(self.credential_pair_read_succeeded) is not bool
            or type(self.source_readmitted) is not bool
        ):
            raise ValueError("invalid authentication qualification observation")
        if (
            self.credential_pair_read_succeeded
            and self.credential_pair_read_attempts != 1
        ):
            raise ValueError("credential pair was not read")
        if self.alpaca_request_attempts and not self.credential_pair_read_succeeded:
            raise ValueError("request without credential readiness")
        if self.http_status is not None and (
            type(self.http_status) is not int
            or not 100 <= self.http_status <= 599
            or self.alpaca_request_attempts != 1
        ):
            raise ValueError("invalid authentication qualification HTTP status")
        if self.provider_code is not None and (
            type(self.provider_code) is not int
            or not 0 <= self.provider_code <= (1 << 63) - 1
            or self.http_status in (None, 200)
        ):
            raise ValueError("invalid authentication qualification provider code")
        if self.reason is AuthQualificationReason.PASS and (
            not self.credential_pair_read_succeeded
            or self.alpaca_request_attempts != 1
            or self.http_status != 200
            or not self.source_readmitted
        ):
            raise ValueError("incomplete authentication qualification PASS")
        if self.reason is not AuthQualificationReason.SOURCE_DRIFT:
            if not self.source_readmitted:
                raise ValueError("missing final source admission")
            if self.reason is AuthQualificationReason.CREDENTIAL_READ_FAILED:
                if self.credential_pair_read_attempts != 1 or (
                    self.credential_pair_read_succeeded
                    or self.alpaca_request_attempts
                    or self.http_status is not None
                ):
                    raise ValueError("invalid credential failure")
            elif self.alpaca_request_attempts != 1:
                raise ValueError("missing qualification request")
            if self.reason is AuthQualificationReason.HTTP_REJECTED and (
                self.http_status is None or self.http_status == 200
            ):
                raise ValueError("invalid HTTP rejection")
            if self.reason is AuthQualificationReason.TRANSPORT_FAILED and (
                self.http_status is not None
            ):
                raise ValueError("invalid transport failure")
            if self.reason is AuthQualificationReason.RESPONSE_INVALID and (
                self.http_status != 200
            ):
                raise ValueError("invalid response failure")
        elif self.source_readmitted:
            raise ValueError("source drift cannot be admitted")


def serialize_authentication_qualification(
    value: AlpacaAuthenticationQualification,
) -> bytes:
    if type(value) is not AlpacaAuthenticationQualification:
        raise ValueError("exact authentication qualification required")
    value.__post_init__()
    payload = (
        json.dumps(asdict(value), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(payload) > MAX_AUTH_QUALIFICATION_BYTES:
        raise ValueError("authentication qualification exceeds bound")
    return payload


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate authentication qualification field")
        result[key] = value
    return result


def _constant(_value: str) -> object:
    raise ValueError("invalid authentication qualification constant")


def parse_authentication_qualification(
    payload: bytes,
) -> AlpacaAuthenticationQualification:
    value = None
    try:
        if (
            type(payload) is not bytes
            or not 0 < len(payload) <= MAX_AUTH_QUALIFICATION_BYTES
        ):
            raise ValueError
        material = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        if type(material) is not dict or set(material) != {
            f.name for f in fields(AlpacaAuthenticationQualification)
        }:
            raise ValueError
        if type(material["reason"]) is not str:
            raise ValueError
        material["reason"] = AuthQualificationReason(material["reason"])
        candidate = AlpacaAuthenticationQualification(**material)
        if serialize_authentication_qualification(candidate) != payload:
            raise ValueError
        value = candidate
    except Exception:
        pass
    if value is None:
        # Outside the handler: discard even the raw JSON exception context.
        raise ValueError("invalid canonical authentication qualification") from None
    return value


def _compatible_response(response: AlpacaHttpResponse) -> None:
    if type(response) is not AlpacaHttpResponse:
        raise ValueError("invalid response type")
    response.__post_init__()
    if not 0 < len(response.body) <= MAX_ALPACA_RESPONSE_BYTES:
        raise ValueError("invalid response bound")
    candidates, complete = parse_alpaca_historical_bars_response(response.body)
    if not complete or len(candidates) != 1:
        raise ValueError("incomplete fixed probe")
    # The strict parser validates values/duplicates first. Preserve exact symbol
    # membership too: empty unexpected symbol arrays otherwise vanish in candidates.
    symbols = tuple(json.loads(response.body, parse_float=str, parse_int=str)["bars"])
    if symbols != ("SPY",):
        raise ValueError("unexpected probe symbol map")
    candidate = candidates[0]
    if (
        candidate.symbol != Symbol("SPY")
        or candidate.response_ordinal != 0
        or candidate.session.session_date != PROBE_SESSION
        or candidate.timestamp != PROBE_TIMESTAMP
    ):
        raise ValueError("wrong fixed probe")
    # Reuse the domain OHLCV invariant; retain neither bars nor response evidence.
    Bar(
        candidate.symbol,
        candidate.timestamp,
        candidate.open,
        candidate.high,
        candidate.low,
        candidate.close,
        candidate.volume,
    )


def qualify_alpaca_authentication(
    *,
    expected_head: str,
    expected_tree: str,
    qualify_auth: str,
    admit_source: Callable[[], object],
    transport: StdlibAlpacaHistoricalBarsTransport,
    credential_reader: Callable[
        [], ScopedAlpacaSecrets
    ] = read_current_product_alpaca_secrets,
) -> AlpacaAuthenticationQualification:
    """One fixed pair read and at most one transport attempt; never retry."""
    _source_identity(expected_head)
    _source_identity(expected_tree)
    if type(qualify_auth) is not str or qualify_auth != QUALIFY_AUTH_INTERLOCK:
        raise ValueError("authentication qualification interlock required")
    if type(transport) is not StdlibAlpacaHistoricalBarsTransport:
        raise ValueError("exact accepted Alpaca transport required")
    if not callable(admit_source) or not callable(credential_reader):
        raise ValueError("qualification boundaries required")
    probe = build_authentication_probe()
    attempts = pair_attempts = 0
    pair_ok = False
    status = code = None
    reason = AuthQualificationReason.SOURCE_DRIFT
    source_ok = False
    try:
        admit_source()
        reason = AuthQualificationReason.CREDENTIAL_READ_FAILED
        pair_attempts = 1
        with credential_reader() as secrets:
            if type(secrets) is not ScopedAlpacaSecrets:
                raise ValueError("exact credential scope required")
            pair_ok = True
            # Re-admit immediately before transport, including after credential read.
            reason = AuthQualificationReason.SOURCE_DRIFT
            admit_source()

            def attempt(key: str, secret: str) -> None:
                nonlocal attempts, reason, status, code
                if attempts:
                    raise ValueError("authentication request budget exhausted")
                attempts = 1
                reason = AuthQualificationReason.TRANSPORT_FAILED
                try:
                    response = transport.execute(
                        probe, api_key_id=key, api_secret_key=secret
                    )
                except AlpacaHttpStatusError as error:
                    if (
                        type(error) is AlpacaHttpStatusError
                        and type(error.status) is int
                        and 100 <= error.status <= 599
                        and error.status != 200
                    ):
                        status = error.status
                        reason = AuthQualificationReason.HTTP_REJECTED
                        if (
                            type(error.provider_code) is int
                            and 0 <= error.provider_code <= (1 << 63) - 1
                        ):
                            code = error.provider_code
                except Exception:
                    pass
                else:
                    status = 200
                    reason = AuthQualificationReason.RESPONSE_INVALID
                    try:
                        _compatible_response(response)
                    except Exception:
                        pass
                    else:
                        reason = AuthQualificationReason.PASS

            secrets.use(attempt)
    except Exception:
        if reason is AuthQualificationReason.PASS:
            # Unexpected scope cleanup failure cannot manufacture PASS.
            reason = AuthQualificationReason.TRANSPORT_FAILED
            status = code = None
    try:
        admit_source()
        source_ok = reason is not AuthQualificationReason.SOURCE_DRIFT
    except Exception:
        reason = AuthQualificationReason.SOURCE_DRIFT
    return AlpacaAuthenticationQualification(
        "alpaca-authentication-qualification/v1",
        expected_head,
        expected_tree,
        PROBE_SESSION.isoformat(),
        probe.method,
        probe.host,
        probe.target,
        "PASS" if reason is AuthQualificationReason.PASS else "BLOCKED",
        reason,
        pair_attempts,
        pair_ok,
        attempts,
        status,
        code,
        source_ok,
    )
