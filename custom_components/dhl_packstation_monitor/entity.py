"""Stable station identity shared by seven entities."""

from urllib.parse import urlencode

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DISPLAY_CAPACITIES, DOMAIN
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

    def summary_attributes(self):
        observation = self.coordinator.snapshot
        usable = self.coordinator.usable
        capacities = dict(
            self.coordinator.subentry.data.get(CONF_DISPLAY_CAPACITIES, {})
        )
        return {
            "compartment_summary": observation.summary(usable),
            "compartment_total_summary": observation.total_summary(usable),
            "compartment_capacity_summary": observation.capacity_summary(
                usable, capacities
            ),
            "reported_total_capacity": observation.total_capacity,
            "display_capacities": capacities,
            "display_capacity_issues": observation.capacity_issues(usable, capacities),
        }
