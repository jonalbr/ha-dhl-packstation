"""The bundled card is served locally and loaded without dashboard edits."""

from unittest.mock import MagicMock

from homeassistant.components import frontend
from homeassistant.setup import async_setup_component

from custom_components.dhl_packstation_monitor import async_setup
from custom_components.dhl_packstation_monitor.const import CARD_URL, VERSION


async def test_bundled_card_served_and_registered(hass, hass_client):
    assert await async_setup_component(hass, "http", {})
    modules = MagicMock()
    hass.config.components.add("frontend")
    hass.data[frontend.DATA_EXTRA_MODULE_URL] = modules
    assert await async_setup(hass, {})
    modules.add.assert_called_once_with(f"{CARD_URL}?v={VERSION}")
    client = await hass_client()
    response = await client.get(CARD_URL)
    assert response.status == 200
    assert response.content_type in ("text/javascript", "application/javascript")
    content = await response.text()
    assert 'const CARD_TYPE = "dhl-packstation-card"' in content
    assert "getConfigElement" in content
    assert "window.customCards.push" in content
    assert "public" in response.headers["Cache-Control"]
