"""Exercise flow-manager success, recovery, duplicate and abort paths."""

from types import MappingProxyType
from unittest.mock import patch

import probatio
import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.data_entry_flow import FlowResultType

from custom_components.dhl_packstation_monitor.const import (
    CONF_DISPLAY_CAPACITIES,
    CONF_INTERVAL,
    CONF_MAX_AGE,
    DOMAIN,
)
from custom_components.dhl_packstation_monitor.models import (
    InvalidResponse,
    PackstationError,
    RateLimited,
    StationNotFound,
)


async def start(hass, path="search"):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": path})


async def test_initial_multi_station(hass, api):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "Georgenstr. 31, Berlin"}
    )
    assert result["step_id"] == "select"
    selected = ["1-10117407", "1-10117408"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"stations": selected}
    )
    assert result["step_id"] == "confirm"
    assert hass.config_entries.async_entries(DOMAIN) == []
    with patch("custom_components.dhl_packstation_monitor.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"stations": selected}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert len(entry.subentries) == 2
    assert entry.data == {}
    assert all("Georgenstr. 31, Berlin" not in str(sub.data) for sub in entry.subentries.values())
    duplicate = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert duplicate["reason"] == "single_instance_allowed"


async def test_cancel_before_confirmation_leaves_no_entry(hass, api):
    result = await start(hass, "direct")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"postal_code": "10117", "station_number": "407"}
    )
    hass.config_entries.flow.async_abort(result["flow_id"])
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    "error", [PackstationError(), StationNotFound(), InvalidResponse(), RateLimited(900)]
)
async def test_search_error_recovery(hass, api, error):
    result = await start(hass)
    api.search.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "Berlin"}
    )
    assert result["errors"] == {"base": error.code}
    api.search.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "Berlin"}
    )
    assert result["step_id"] == "select"


@pytest.mark.parametrize("address", [" ", "a" * 301])
async def test_invalid_search(hass, api, address):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"address": address})
    assert result["errors"] == {"base": "invalid_address"}
    api.search.assert_not_called()


async def test_empty_search(hass, api):
    api.search.return_value = []
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "Berlin"}
    )
    assert result["errors"] == {"base": "no_stations"}


@pytest.mark.parametrize(
    "error",
    [ValueError(), PackstationError(), StationNotFound(), InvalidResponse(), RateLimited(900)],
)
async def test_direct_errors(hass, api, error):
    api.resolve.side_effect = error
    result = await start(hass, "direct")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"postal_code": "10117", "station_number": "407"}
    )
    assert result["errors"] == {
        "base": "invalid_location" if isinstance(error, ValueError) else error.code
    }


async def test_preview_failure_retry_and_deselect(hass, api, observations):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "Berlin"}
    )
    observations["1-10117408"] = PackstationError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"stations": ["1-10117407", "1-10117408"]}
    )
    assert result["errors"] == {"base": "validation_failed"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"stations": ["1-10117407", "1-10117408"]}
    )
    assert result["errors"] == {"base": "validation_failed"}
    with patch("custom_components.dhl_packstation_monitor.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"stations": ["1-10117407"]}
        )
        await hass.async_block_till_done()
    assert len(result["result"].subentries) == 1


async def test_empty_selection_and_confirmation(hass, api):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "Berlin"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"stations": []})
    assert result["errors"] == {"base": "no_selection"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"stations": ["1-10117407"]}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"stations": []})
    assert result["errors"] == {"base": "no_selection"}


async def test_subentry_search_add_and_duplicate(hass, api, entry_factory):
    entry = entry_factory()
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"address": "Berlin"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"stations": "1-10117408"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"stations": "1-10117408"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(entry.subentries) == 2
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "direct"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"postal_code": "10117", "station_number": "407"}
    )
    assert result["errors"] == {"base": "already_configured"}


async def test_subentry_duplicate_appearing_during_preview(hass, api, entry_factory, observations):
    entry = entry_factory()
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "direct"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"postal_code": "10117", "station_number": "408"}
    )
    station = observations["1-10117408"].station
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType({"station": station.to_data()}),
            subentry_type="station",
            title=station.title,
            unique_id=station.primary_key,
        ),
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"stations": "1-10117408"}
    )
    assert result["errors"] == {"base": "already_configured"}


@pytest.mark.parametrize("name", ["Nearby station", " "])
async def test_reconfigure_same_identity_and_error_recovery(hass, api, entry_factory, name):
    entry = entry_factory()
    subentry = next(iter(entry.subentries.values()))
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"),
        context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
    )
    api.station.side_effect = PackstationError()
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"name": name})
    assert result["errors"] == {"base": "cannot_connect"}
    api.station.side_effect = None
    from custom_components.dhl_packstation_monitor.models import Observation, Station

    api.station.return_value = Observation(
        Station.from_data(dict(subentry.data["station"])), {}, None
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"name": name})
    assert result["reason"] == "reconfigure_successful"
    assert subentry.unique_id == "1-10117407"
    assert subentry.title == (name.strip() or "Packstation 407 · 10117 Berlin")


async def test_options_defaults_validation_and_save(hass, entry_factory):
    entry = entry_factory()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_INTERVAL: 60, CONF_MAX_AGE: 30}
    )
    assert result["errors"] == {"base": "invalid_options"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_INTERVAL: 30, CONF_MAX_AGE: 90}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_INTERVAL: 30, CONF_MAX_AGE: 90}


@pytest.mark.parametrize(
    "language,label",
    [("en", "Home location (Home Assistant)"), ("de", "Heimstandort (Home Assistant)")],
)
async def test_home_location_suggested_clearable_and_only_sent_on_submit(
    hass, api, language, label
):
    hass.config.language = language
    hass.config.latitude, hass.config.longitude = 52.52, 13.39
    result = await start(hass)
    field = next(iter(result["data_schema"].schema))
    assert field.description["suggested_value"] == label
    assert isinstance(field, probatio.Optional)
    selector = result["data_schema"].schema[field]
    assert selector.config["custom_value"]
    api.search.assert_not_called()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"address": label})
    api.search.assert_awaited_once_with("52.520000,13.390000")
    assert result["step_id"] == "select"


@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (0, 0),
        (None, 13),
        (52, None),
        (True, 13),
        (float("nan"), 13),
        (52, float("inf")),
        (91, 13),
        (52, 181),
    ],
)
async def test_missing_or_invalid_home_location_is_not_suggested(hass, api, latitude, longitude):
    hass.config.latitude, hass.config.longitude = latitude, longitude
    result = await start(hass)
    field = next(iter(result["data_schema"].schema))
    assert not field.description
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "Home location (Home Assistant)"}
    )
    assert result["errors"] == {"base": "invalid_address"}
    api.search.assert_not_called()


async def test_cleared_home_stays_empty_then_accepts_another_address(hass, api):
    hass.config.latitude, hass.config.longitude = 52.52, 13.39
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "invalid_address"}
    field = next(iter(result["data_schema"].schema))
    assert not field.description
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": "Hamburg"}
    )
    api.search.assert_awaited_once_with("Hamburg")
    assert result["step_id"] == "select"


async def test_optional_capacities_can_be_added_changed_and_cleared(hass, api, entry_factory):
    entry = entry_factory()
    subentry = next(iter(entry.subentries.values()))

    async def edit(values):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "station"),
            context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
        )
        return await hass.config_entries.subentries.async_configure(result["flow_id"], values)

    result = await edit({"name": "Near home", CONF_DISPLAY_CAPACITIES: {"s": 12, "m": 0}})
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data[CONF_DISPLAY_CAPACITIES] == {"s": 12, "m": 0}
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"),
        context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
    )
    # Suggested values do not become schema defaults, so clearing removes them.
    capacity_field = next(
        key for key in result["data_schema"].schema if key.schema == CONF_DISPLAY_CAPACITIES
    )
    section_schema = result["data_schema"].schema[capacity_field]
    assert section_schema.options["collapsed"]
    suggested = {
        field.schema: field.description["suggested_value"]
        for field in section_schema.schema.schema
        if field.description
    }
    assert suggested == {"s": 12, "m": 0}
    assert section_schema({}) == {}
    await hass.config_entries.subentries.async_configure(result["flow_id"], {"name": "Near home"})
    assert subentry.data[CONF_DISPLAY_CAPACITIES] == {}


async def test_fractional_manual_capacity_reports_validation_error(hass, api, entry_factory):
    entry = entry_factory()
    subentry = next(iter(entry.subentries.values()))
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"),
        context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Near home", CONF_DISPLAY_CAPACITIES: {"s": 1.5}}
    )
    assert result["errors"] == {"base": "invalid_capacities"}
