"""Check shipped station labels through HA's translation loader, including fallback."""

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from custom_components.dhl_packstation_monitor.const import DOMAIN


@pytest.mark.parametrize("language", ["en", "de", "fr"])
async def test_station_attribute_labels_load_for_every_entity(
    hass, api, entry_factory, language
):
    entry = entry_factory()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    translations = await async_get_translations(hass, language, "entity", {DOMAIN})
    labels = (
        {
            "station_id": "Stations-ID",
            "station_number": "Packstationsnummer",
            "postal_code": "Postleitzahl",
            "address": "Adresse",
        }
        if language == "de"
        else {
            "station_id": "Station ID",
            "station_number": "Packstation number",
            "postal_code": "Postal code",
            "address": "Address",
        }
    )
    registered = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(registered) == 9
    for entity in registered:
        state = hass.states.get(entity.entity_id)
        for attribute, expected in labels.items():
            assert attribute in state.attributes
            key = (
                f"component.{DOMAIN}.entity.{entity.domain}.{entity.translation_key}"
                f".state_attributes.{attribute}.name"
            )
            assert translations[key] == expected
