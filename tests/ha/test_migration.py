"""Migrate the old default once, preserving station identities and custom limits."""

from datetime import timedelta

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.dhl_packstation_monitor import async_migrate_entry
from custom_components.dhl_packstation_monitor.const import (
    CONF_INTERVAL,
    CONF_MAX_AGE,
    DOMAIN,
)


@pytest.mark.parametrize("age", [None, 60, 75, 90])
async def test_age_migration_preserves_other_options(hass, entry_factory, age):
    options = {CONF_INTERVAL: 30, "unrelated": "preserve"}
    if age is not None:
        options[CONF_MAX_AGE] = age
    entry = entry_factory(options=options, minor_version=1)
    assert await async_migrate_entry(hass, entry)
    assert entry.version == 1
    assert entry.minor_version == 2
    expected = dict(options)
    if age == 60:
        expected.pop(CONF_MAX_AGE)
    assert entry.options == expected


@pytest.mark.parametrize("version,minor", [(1, 2), (1, 3), (2, 1)])
async def test_current_and_future_entries_are_not_rewritten(
    hass, entry_factory, version, minor
):
    options = {CONF_INTERVAL: 15, CONF_MAX_AGE: 60}
    entry = entry_factory(options=options, version=version, minor_version=minor)
    assert await async_migrate_entry(hass, entry) is (version == 1)
    assert entry.version == version
    assert entry.minor_version == minor
    assert entry.options == options


async def test_setup_migrates_once_without_replacing_stations_or_entities(
    hass, api, entry_factory
):
    entry = entry_factory(
        2, options={CONF_INTERVAL: 15, CONF_MAX_AGE: 60}, minor_version=1
    )
    subentries = dict(entry.subentries)
    registry = er.async_get(hass)
    total = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "1-10117407_free_total",
        suggested_object_id="my_station_total",
        config_entry=entry,
        config_subentry_id="station_407",
    )
    registry.async_update_entity(total.entity_id, name="My count")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.minor_version == 2
    assert entry.options == {CONF_INTERVAL: 15}
    assert all(
        coordinator.max_age == timedelta(minutes=75)
        for coordinator in entry.runtime_data.coordinators.values()
    )
    assert entry.subentries == subentries
    assert hass.states.get(total.entity_id).state == "6"
    assert registry.async_get(total.entity_id).name == "My count"
    identities = {
        item.unique_id: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert len(identities) == 18
    # An explicit 60 saved after migration is a custom choice, never migrated again.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_INTERVAL: 15, CONF_MAX_AGE: 60}
    )
    await hass.async_block_till_done()
    assert all(
        coordinator.max_age == timedelta(minutes=60)
        for coordinator in entry.runtime_data.coordinators.values()
    )
    assert {
        item.unique_id: item.entity_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    } == identities
