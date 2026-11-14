"""Read the DHL website service with bounded requests and shared backoff."""

import asyncio
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_BASE
from .models import (
    InvalidResponse,
    Observation,
    PackstationError,
    RateLimited,
    Station,
    StationNotFound,
    normalize_location,
    parse_observation,
    parse_search,
)


def retry_seconds(value: str, now: datetime) -> float:
    try:
        return max(900, int(value))
    except ValueError:
        try:
            return max(900, (parsedate_to_datetime(value) - now).total_seconds())
        except TypeError, ValueError, OverflowError:
            return 900


class PackstationClient:
    def __init__(self, session: ClientSession) -> None:
        self.session = session
        self._lock = asyncio.Lock()
        self._retry_at = 0.0

    async def _get(self, path: str, **params: str | int) -> dict:
        async with self._lock:
            remaining = self._retry_at - monotonic()
            if remaining > 0:
                raise RateLimited(remaining)
            try:
                async with self.session.get(
                    f"{API_BASE}/{path}",
                    params=params,
                    timeout=ClientTimeout(total=20),
                    allow_redirects=False,
                ) as response:
                    if response.status in (204, 404):
                        raise StationNotFound()
                    if response.status == 429:
                        seconds = retry_seconds(
                            response.headers.get("Retry-After", "900"), datetime.now(UTC)
                        )
                        self._retry_at = monotonic() + seconds
                        raise RateLimited(seconds)
                    if response.status != 200:
                        raise PackstationError()
                    try:
                        data = await response.json()
                    except (ValueError, UnicodeError) as err:
                        raise InvalidResponse() from err
            except (ClientError, TimeoutError) as err:
                raise PackstationError() from err
            if not isinstance(data, dict):
                raise InvalidResponse()
            return data

    async def search(self, address: str) -> list[Station]:
        return parse_search(await self._get("nearbySearch", address=address, maxResults=100))

    async def resolve(self, postal_code: str, number: str) -> Observation:
        postal_code, number = normalize_location(postal_code, number)
        candidates = await self.search(f"{postal_code}:{number}")
        for station in candidates:
            if station.postal_code == postal_code and station.number == number:
                result = await self.station(station.primary_key)
                if result.station.postal_code != postal_code or result.station.number != number:
                    raise StationNotFound()
                return result
        raise StationNotFound()

    async def station(self, primary_key: str) -> Observation:
        if not re.fullmatch(r"[0-9]{1,2}-[0-9]{1,12}", primary_key):
            raise InvalidResponse()
        return parse_observation(
            await self._get(f"locationByPrimaryKeyPF/{primary_key}"), primary_key
        )
