"""Stable station identity shared by seven entities."""

from urllib.parse import urlencode

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StationCoordinator


class StationEntity(CoordinatorEntity[StationCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        station = coordinator.snapshot.station
        self._attr_unique_id = f"{station.primary_key}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station.primary_key)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="DHL",
            model="Packstation",
            name=coordinator.subentry.title,
            configuration_url="https://www.dhl.de/de/privatkunden/dhl-standorte-finden.html?"
            + urlencode(
                {
                    "address": f"{station.postal_code}:{station.number}",
                    "locationType": "packstationen",
                }
            ),
        )

    @property
    def extra_state_attributes(self):
        station = self.coordinator.snapshot.station
        return {
            "station_id": station.primary_key,
            "station_number": station.number,
            "postal_code": station.postal_code,
            "address": station.address,
        }
