"""Use real HA flows and registries, replacing only the external API."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.dhl_packstation_monitor.api import PackstationClient
from custom_components.dhl_packstation_monitor.const import CONF_INTERVAL, CONF_MAX_AGE, DOMAIN
from custom_components.dhl_packstation_monitor.models import (
    StationNotFound,
    normalize_location,
    parse_observation,
)


@pytest.fixture
def observations(payload):
    second = deepcopy(payload)
    second.update(primaryKeyPF="1-10117408", primaryKeyZipRegion="408", street="Other street")
    return {
        item["primaryKeyPF"]: parse_observation(item, item["primaryKeyPF"])
        for item in (payload, second)
    }


@pytest.fixture
def api(observations):
    client = AsyncMock(spec=PackstationClient)

    async def station(key):
        value = observations[key]
        if isinstance(value, Exception):
            raise value
        return value

    async def resolve(postal, number):
        postal, number = normalize_location(postal, number)
        for value in observations.values():
            if not isinstance(value, Exception) and (
                value.station.postal_code == postal and value.station.number == number
            ):
                return value
        raise StationNotFound()

    client.station.side_effect = station
    client.resolve.side_effect = resolve
    client.search.return_value = [value.station for value in observations.values()]
    with (
        patch(
            "custom_components.dhl_packstation_monitor.config_flow.PackstationClient",
            return_value=client,
        ),
        patch("custom_components.dhl_packstation_monitor.PackstationClient", return_value=client),
    ):
        yield client


@pytest.fixture
def entry_factory(hass, observations):
    def create(count=1, options=None):
        subentries = [
            {
                "subentry_id": f"station_{observation.station.number}",
                "subentry_type": "station",
                "unique_id": key,
                "title": observation.station.title,
                "data": {"station": observation.station.to_data()},
            }
            for key, observation in list(observations.items())[:count]
        ]
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DOMAIN,
            data={},
            title="DHL Packstation Monitor",
            subentries_data=subentries,
            options=options or {CONF_INTERVAL: 15, CONF_MAX_AGE: 60},
        )
        entry.add_to_hass(hass)
        return entry

    return create
