"""Five compartment counts and the source timestamp."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.entity import EntityCategory

from .const import SIZES
from .entity import StationEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        async_add_entities(
            [
                *(CompartmentSensor(coordinator, size) for size in (*SIZES, "total")),
                SourceTimestampSensor(coordinator),
            ],
            config_subentry_id=subentry_id,
        )


class CompartmentSensor(StationEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, size):
        super().__init__(coordinator, f"free_{size}")
        self.size = size

    @property
    def native_value(self):
        counts = self.coordinator.snapshot.counts
        if self.size == "total":
            return sum(counts.values()) if all(v is not None for v in counts.values()) else None
        return counts[self.size]

    @property
    def available(self):
        return self.coordinator.usable and self.native_value is not None

    @property
    def extra_state_attributes(self):
        attributes = super().extra_state_attributes
        if self.size == "total":
            attributes.update(self.summary_attributes())
        return attributes


class SourceTimestampSensor(StationEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "source_timestamp")

    @property
    def available(self):
        return self.coordinator.last_source_timestamp is not None

    @property
    def native_value(self):
        return self.coordinator.last_source_timestamp
