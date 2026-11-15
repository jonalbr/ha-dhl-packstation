"""Check the real entity, device, coordinator and entry lifecycle."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

try:
    from pytest_homeassistant.common import async_fire_time_changed
except ModuleNotFoundError:
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.dhl_packstation_monitor.const import (
    CONF_INTERVAL,
    CONF_MAX_AGE,
    DOMAIN,
)
from custom_components.dhl_packstation_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.dhl_packstation_monitor.models import (
    PackstationError,
    RateLimited,
)


def states(hass, entry):
    return {
        item.unique_id: hass.states.get(item.entity_id)
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


async def test_nine_entities_each_with_stable_registry_links(hass, api, entry_factory):
    entry = entry_factory(2)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registered = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(registered) == 18
    assert {item.config_subentry_id for item in registered} == set(entry.subentries)
    assert (
        len(dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)) == 2
    )
    values = states(hass, entry)
    assert values["1-10117407_free_s"].state == "3"
    assert values["1-10117407_free_m"].state == "0"
    assert values["1-10117407_free_total"].state == "6"
    assert values["1-10117407_free_total"].attributes["state_class"] == "measurement"
    assert (
        values["1-10117407_free_total"].attributes["compartment_summary"]
        == "S 3 · M 0 · L 2 · XL 1"
    )
    assert values["1-10117407_data_problem"].state == "off"
    coordinator = entry.runtime_data.coordinators["station_407"]
    assert coordinator._cancel_expiry is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert coordinator._cancel_expiry is None
    assert not list(coordinator.async_contexts())


async def test_partial_counts_and_failure_isolation(
    hass, api, entry_factory, observations
):
    entry = entry_factory(2)
    original = observations["1-10117407"]
    observations["1-10117407"] = replace(
        original, counts={**original.counts, "s": None}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    values = states(hass, entry)
    assert values["1-10117407_free_s"].state == "unavailable"
    assert values["1-10117407_free_total"].state == "unavailable"
    assert values["1-10117407_free_m"].state == "0"
    assert (
        values["1-10117407_data_problem"].attributes["reason"] == "missing_compartments"
    )
    coordinator = entry.runtime_data.coordinators["station_407"]
    timestamp = values["1-10117407_source_timestamp"].state
    observations["1-10117407"] = PackstationError()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    values = states(hass, entry)
    assert values["1-10117407_free_m"].state == "unavailable"
    assert (
        values["1-10117407_data_problem"].attributes["compartment_summary"]
        == "S — · M — · L — · XL —"
    )
    assert values["1-10117407_source_timestamp"].state == timestamp
    assert values["1-10117407_data_problem"].state == "on"
    assert values["1-10117408_free_s"].state == "3"
    observations["1-10117407"] = original
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert states(hass, entry)["1-10117407_data_problem"].state == "off"


async def test_missing_data_and_all_station_failures_do_not_block_setup(
    hass, api, entry_factory, observations
):
    entry = entry_factory(2)
    observations["1-10117407"] = PackstationError()
    observations["1-10117408"] = RateLimited(1800)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    values = states(hass, entry)
    assert len(values) == 18
    assert values["1-10117407_source_timestamp"].state == "unavailable"
    assert values["1-10117407_last_successful_poll"].state == "unavailable"
    assert values["1-10117407_last_poll_attempt"].state != "unavailable"
    assert values["1-10117408_data_problem"].attributes["reason"] == "rate_limited"


async def test_source_and_poll_timestamps_are_distinct(
    hass, api, entry_factory, observations, freezer
):
    freezer.move_to(dt_util.utcnow().replace(microsecond=0))
    entry = entry_factory()
    source_time = dt_util.utcnow() - timedelta(minutes=10)
    original = replace(observations["1-10117407"], source_timestamp=source_time)
    observations["1-10117407"] = original
    attempted = dt_util.utcnow()

    async def delayed_response(key):
        freezer.move_to(dt_util.utcnow() + timedelta(seconds=2))
        return original

    api.station.side_effect = delayed_response
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinators["station_407"]
    successful = dt_util.utcnow()
    values = states(hass, entry)
    assert values["1-10117407_source_timestamp"].state == source_time.isoformat()
    assert values["1-10117407_last_poll_attempt"].state == attempted.isoformat()
    assert values["1-10117407_last_successful_poll"].state == successful.isoformat()

    # A later failed request advances only the attempt, retaining the source and success.
    freezer.move_to(successful + timedelta(minutes=1))
    api.station.side_effect = PackstationError()
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    values = states(hass, entry)
    assert values["1-10117407_last_poll_attempt"].state == dt_util.utcnow().isoformat()
    assert values["1-10117407_last_successful_poll"].state == successful.isoformat()
    assert values["1-10117407_source_timestamp"].state == source_time.isoformat()
    assert values["1-10117407_data_problem"].state == "on"

    # A valid response can still contain stale data: polling success is not freshness.
    freezer.move_to(dt_util.utcnow() + timedelta(minutes=1))
    stale_time = dt_util.utcnow() - timedelta(hours=2)
    api.station.side_effect = None
    api.station.return_value = replace(original, source_timestamp=stale_time)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    values = states(hass, entry)
    assert (
        values["1-10117407_last_successful_poll"].state == dt_util.utcnow().isoformat()
    )
    assert values["1-10117407_source_timestamp"].state == stale_time.isoformat()
    assert values["1-10117407_data_problem"].attributes["reason"] == "stale_data"
    assert values["1-10117407_free_s"].state == "unavailable"


async def test_display_name_changes_preserve_existing_entity_ids_and_user_names(
    hass, api, entry_factory
):
    entry = entry_factory()
    registry = er.async_get(hass)
    existing = [
        registry.async_get_or_create(
            domain,
            DOMAIN,
            f"1-10117407_{key}",
            suggested_object_id=f"existing_dhl_{key}",
            config_entry=entry,
            config_subentry_id="station_407",
        )
        for domain, key in (
            ("sensor", "source_timestamp"),
            ("binary_sensor", "data_problem"),
        )
    ]
    for item in existing:
        registry.async_update_entity(item.entity_id, name="My custom name")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for item in existing:
        registered = registry.async_get(item.entity_id)
        assert registered.unique_id == item.unique_id
        assert registered.name == "My custom name"
        assert hass.states.get(item.entity_id) is not None


async def test_expiry_without_http_and_invalid_future_source(
    hass, api, entry_factory, observations, freezer
):
    entry = entry_factory()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinators["station_407"]
    # The source expires in five minutes; polling is still fifteen minutes away.
    observation = observations["1-10117407"]
    observations["1-10117407"] = replace(
        observation, source_timestamp=dt_util.utcnow() - timedelta(minutes=55)
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    before = api.station.await_count
    freezer.move_to(dt_util.utcnow() + timedelta(minutes=6))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert api.station.await_count == before
    assert states(hass, entry)["1-10117407_free_s"].state == "unavailable"
    assert coordinator.problem == "stale_data"
    observations["1-10117407"] = replace(
        observation, source_timestamp=dt_util.utcnow() + timedelta(minutes=6)
    )
    previous_timestamp = coordinator.last_source_timestamp
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.problem == "future_timestamp"
    assert coordinator.last_source_timestamp == previous_timestamp


async def test_options_reload_once_and_preserve_ids(hass, api, entry_factory):
    entry = entry_factory()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry_before = {
        item.unique_id: item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload_entry:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_INTERVAL: 30, CONF_MAX_AGE: 90}
        )
        await hass.async_block_till_done()
        assert reload_entry.await_count == 1
    assert entry.runtime_data.coordinators["station_407"].max_age == timedelta(
        minutes=90
    )
    assert {
        item.unique_id: item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    } == registry_before


async def test_station_remove_and_add_runtime(hass, api, entry_factory):
    entry = entry_factory(2)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    removed = entry.runtime_data.coordinators["station_407"]
    hass.config_entries.async_remove_subentry(entry, "station_407")
    await hass.async_block_till_done()
    assert removed._cancel_expiry is None
    assert set(entry.runtime_data.coordinators) == {"station_408"}
    registered = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(registered) == 9
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "direct"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"postal_code": "10117", "station_number": "407"}
    )
    await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"stations": "1-10117407"}
    )
    await hass.async_block_till_done()
    assert (
        len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)) == 18
    )


async def test_reconfigure_respects_device_override(hass, api, entry_factory):
    entry = entry_factory()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    dr.async_get(hass).async_update_device(
        device.id, name_by_user="My custom device name"
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "station"),
        context={"source": "reconfigure", "subentry_id": "station_407"},
    )
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload_entry:
        await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"name": "New station display name"}
        )
        await hass.async_block_till_done()
        assert reload_entry.await_count == 1
    device = dr.async_get(hass).async_get(device.id)
    assert device.name == "New station display name"
    assert device.name_by_user == "My custom device name"


async def test_diagnostics_allowlist(hass, api, entry_factory):
    entry = entry_factory()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    diagnostic = await async_get_config_entry_diagnostics(hass, entry)
    assert "Georgenstr" not in str(diagnostic)
    assert "postal_code" not in str(diagnostic)
    assert diagnostic["stations"][0]["counts"]["s"] == 3
    coordinator = entry.runtime_data.coordinators["station_407"]
    coordinator.last_update_success = False
    diagnostic = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostic["stations"][0]["counts"] is None
