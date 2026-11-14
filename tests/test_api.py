"""Exercise actual request handling with deterministic HTTP doubles."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientConnectionError

from custom_components.dhl_packstation_monitor.api import (
    PackstationClient,
    retry_seconds,
)
from custom_components.dhl_packstation_monitor.models import (
    InvalidResponse,
    PackstationError,
    RateLimited,
    StationNotFound,
)


class Response:
    def __init__(self, body, status=200, headers=None):
        self.body, self.status, self.headers = body, status, headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def client_for(response):
    session = MagicMock()
    session.get.return_value = response
    return PackstationClient(session)


@pytest.mark.parametrize(
    "status,error",
    [
        (204, StationNotFound),
        (404, StationNotFound),
        (403, PackstationError),
        (500, PackstationError),
        (302, PackstationError),
    ],
)
async def test_http_errors(status, error):
    client = client_for(Response({}, status))
    with pytest.raises(error):
        await client.search("Berlin")
    assert client.session.get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize(
    "error", [TimeoutError(), ClientConnectionError("private request URL")]
)
async def test_network_errors_are_sanitized(error):
    client = client_for(None)
    client.session.get.side_effect = error
    with pytest.raises(PackstationError) as caught:
        await client.search("private search address")
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("body", [[], ValueError(), UnicodeError()])
async def test_invalid_json(body):
    with pytest.raises(InvalidResponse):
        await client_for(Response(body)).search("Berlin")


async def test_rate_limit_blocks_followup_requests():
    client = client_for(Response({}, 429, {"Retry-After": "1800"}))
    for _ in range(2):
        with pytest.raises(RateLimited) as caught:
            await client.search("Berlin")
        assert caught.value.retry_after > 1700
    assert client.session.get.call_count == 1


def test_retry_after_date_and_fallback():
    now = datetime.now(UTC).replace(microsecond=0)
    assert retry_seconds("1", now) == 900
    assert retry_seconds("1800", now) == 1800
    assert retry_seconds(format_datetime(now + timedelta(hours=1)), now) == 3600
    assert retry_seconds("invalid", now) == 900
    assert retry_seconds("Sat, 14 Nov 2026 12:00:00", now) == 900


async def test_resolve_exact_station(payload):
    client = client_for(None)
    client.session.get.side_effect = [
        Response({"pfLocations": [payload]}),
        Response(payload),
    ]
    assert (await client.resolve("10117", "407")).counts["s"] == 3


async def test_resolve_does_not_accept_nearby_station(payload):
    client = client_for(Response({"pfLocations": [payload]}))
    with pytest.raises(StationNotFound):
        await client.resolve("10117", "999")
    payload["zipCode"] = "99999"
    client.session.get.side_effect = [
        Response({"pfLocations": [{**payload, "zipCode": "10117"}]}),
        Response(payload),
    ]
    with pytest.raises(StationNotFound):
        await client.resolve("10117", "407")


async def test_invalid_key_is_not_requested():
    client = client_for(None)
    with pytest.raises(InvalidResponse):
        await client.station("../private")
    client.session.get.assert_not_called()
