"""DHL Packstation Monitor lifecycle."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .api import PackstationClient

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import StationCoordinator


@dataclass
class MonitorRuntime:
    client: PackstationClient
    coordinators: dict[str, StationCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[MonitorRuntime]
) -> bool:
    """Set up each station independently, including temporarily unavailable ones."""
    from homeassistant.const import Platform
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from .coordinator import StationCoordinator

    runtime = MonitorRuntime(PackstationClient(async_get_clientsession(hass)), {})
    entry.runtime_data = runtime
    for subentry in entry.get_subentries_of_type("station"):
        coordinator = StationCoordinator(hass, entry, subentry, runtime.client)
        runtime.coordinators[subentry.subentry_id] = coordinator
        entry.async_on_unload(coordinator.cancel_expiry)
        await coordinator.async_refresh()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )
    return True


async def _async_reload(
    hass: HomeAssistant, entry: ConfigEntry[MonitorRuntime]
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[MonitorRuntime]
) -> bool:
    from homeassistant.const import Platform

    return await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )
