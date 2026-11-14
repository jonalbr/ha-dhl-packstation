"""Display metadata never changes availability, values or entity identity."""

from homeassistant.helpers import entity_registry as er

from custom_components.dhl_packstation_monitor.const import CONF_DISPLAY_CAPACITIES


async def test_manual_denominators_are_display_only_and_survive_reload(hass, api, entry_factory):
    entry = entry_factory()
    subentry = next(iter(entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        entry,
        subentry,
        data={
            **subentry.data,
            CONF_DISPLAY_CAPACITIES: {"s": 1, "m": 0, "l": 3, "xl": 5},
        },
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(registry) == 7
    entity_ids = {entity.unique_id: entity.entity_id for entity in registry}
    diagnostic = hass.states.get(entity_ids["1-10117407_data_problem"])
    assert diagnostic.state == "off"
    assert diagnostic.attributes["display_capacity_issues"] == ["s"]
    assert diagnostic.attributes["compartment_capacity_summary"] == "S 3/— · M 0/0 · L 2/3 · XL 1/5"
    assert diagnostic.attributes["compartment_total_summary"] == "Σ 6/12 · S 3 · M 0 · L 2 · XL 1"
    assert hass.states.get(entity_ids["1-10117407_free_s"]).state == "3"
    assert hass.states.get(entity_ids["1-10117407_free_total"]).state == "6"
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert {
        entity.unique_id: entity.entity_id
        for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    } == entity_ids
    assert (
        hass.states.get(entity_ids["1-10117407_data_problem"]).attributes["display_capacities"]["s"]
        == 1
    )
