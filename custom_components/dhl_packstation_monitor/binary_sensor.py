"""Report unusable or incomplete station data."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from .entity import StationEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        async_add_entities([DataProblemSensor(coordinator)], config_subentry_id=subentry_id)


class DataProblemSensor(StationEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "data_problem")

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.problem is not None

    @property
    def extra_state_attributes(self):
        return {
            **super().extra_state_attributes,
            "reason": self.coordinator.problem,
            "compartment_summary": self.coordinator.snapshot.summary(self.coordinator.usable),
        }
