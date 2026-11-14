"""Normalize public station data without Home Assistant dependencies."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .const import SIZES


class PackstationError(Exception):
    """A request could not provide usable station data."""

    code = "cannot_connect"


class StationNotFound(PackstationError):
    """No matching Packstation was found."""

    code = "station_not_found"


class InvalidResponse(PackstationError):
    """The service returned an unexpected payload."""

    code = "invalid_response"


class RateLimited(PackstationError):
    """DHL requested a pause."""

    code = "rate_limited"

    def __init__(self, seconds: float) -> None:
        self.retry_after = max(900, seconds)
        super().__init__(self.code)


def normalize_location(postal_code: str, number: str) -> tuple[str, str]:
    """Validate direct lookup input without synthesizing DHL identifiers."""
    postal_code, number = postal_code.strip(), number.strip()
    if not re.fullmatch(r"[0-9]{5}", postal_code) or not re.fullmatch(r"[0-9]{1,4}", number):
        raise ValueError("invalid_location")
    if int(number) == 0:
        raise ValueError("invalid_location")
    return postal_code, str(int(number))


def text(value: Any) -> str:
    """Keep only bounded strings from external data."""
    return value[:300].strip() if isinstance(value, str) else ""


@dataclass(frozen=True, slots=True)
class Station:
    """A verified public location, independent of a user's search address."""

    primary_key: str
    postal_code: str
    number: str
    city: str
    street: str
    house_number: str
    location_name: str = ""
    distance_m: float | None = None

    @property
    def address(self) -> str:
        return ", ".join(
            (
                f"{self.street} {self.house_number}".strip(),
                f"{self.postal_code} {self.city}".strip(),
            )
        )

    @property
    def title(self) -> str:
        return f"Packstation {self.number} · {self.postal_code} {self.city}".strip()

    @property
    def label(self) -> str:
        distance = f" · {self.distance_m:.0f} m" if self.distance_m is not None else ""
        return f"Packstation {self.number} · {self.address}{distance}"

    def to_data(self) -> dict[str, str]:
        """Persist public metadata only; omit search-relative distance."""
        return {
            key: getattr(self, key)
            for key in (
                "primary_key",
                "postal_code",
                "number",
                "city",
                "street",
                "house_number",
                "location_name",
            )
        }

    @classmethod
    def from_data(cls, data: dict) -> Station:
        return cls(**data)


def parse_station(payload: object, expected_key: str | None = None) -> Station:
    """Reject other location types and identity mismatches."""
    if not isinstance(payload, dict):
        raise InvalidResponse()
    if payload.get("locationType") != "PACKSTATION":
        raise StationNotFound()
    key = text(payload.get("primaryKeyPF"))
    if not re.fullmatch(r"[0-9]{1,2}-[0-9]{1,12}", key):
        raise InvalidResponse()
    if expected_key is not None and key != expected_key:
        raise InvalidResponse()
    try:
        postal_code, number = normalize_location(
            text(payload.get("zipCode")), text(payload.get("primaryKeyZipRegion"))
        )
    except ValueError as err:
        raise InvalidResponse() from err
    geo = payload.get("geoPosition")
    distance = geo.get("distance") if isinstance(geo, dict) else None
    if type(distance) not in (int, float) or not 0 <= distance < float("inf"):
        distance = None
    return Station(
        key,
        postal_code,
        number,
        text(payload.get("city")),
        text(payload.get("street")),
        text(payload.get("houseNo")),
        text(payload.get("locationName")),
        distance,
    )


def parse_search(payload: object) -> list[Station]:
    if not isinstance(payload, dict) or not isinstance(payload.get("pfLocations"), list):
        raise InvalidResponse()
    stations = {}
    for item in payload["pfLocations"]:
        try:
            station = parse_station(item)
        except PackstationError:
            continue
        stations.setdefault(station.primary_key, station)
    return sorted(
        stations.values(),
        key=lambda station: (
            station.distance_m if station.distance_m is not None else float("inf"),
            station.title,
        ),
    )


@dataclass(frozen=True, slots=True)
class Observation:
    station: Station
    counts: dict[str, int | None]
    source_timestamp: datetime | None

    def fresh(self, now: datetime, max_age: timedelta) -> bool:
        return self.source_timestamp is not None and (
            -timedelta(minutes=5) <= now - self.source_timestamp < max_age
        )

    def problem(self, now: datetime, max_age: timedelta) -> str | None:
        if self.source_timestamp is None:
            return "missing_timestamp"
        if self.source_timestamp > now + timedelta(minutes=5):
            return "future_timestamp"
        if not self.fresh(now, max_age):
            return "stale_data"
        if any(value is None for value in self.counts.values()):
            return "missing_compartments"
        return None

    def summary(self, usable: bool) -> str:
        return " · ".join(
            f"{size.upper()} {value if usable and value is not None else '—'}"
            for size, value in self.counts.items()
        )


def parse_observation(payload: object, expected_key: str) -> Observation:
    station = parse_station(payload, expected_key)
    live = payload.get("liveStatus")
    if live is None:
        live = {}
    if not isinstance(live, dict):
        raise InvalidResponse()
    counts = {
        size: value if type(value := live.get(field)) is int and value >= 0 else None
        for size, field in SIZES.items()
    }
    timestamp = None
    raw = live.get("sourceTimestamp")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is not None:
                timestamp = parsed.astimezone(UTC)
        except ValueError, OverflowError:
            pass
    return Observation(station, counts, timestamp)
