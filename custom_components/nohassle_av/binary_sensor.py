"""Reserved power entity; actual power feedback has not been established."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entity import matrix_device_info


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MatrixPowerStatus(entry)])


class MatrixPowerStatus(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, entry):
        super().__init__(entry.runtime_data.coordinator)
        self._attr_unique_id = f"{entry.entry_id}_matrix_power_status"
        self._attr_device_info = matrix_device_info(entry)

    @property
    def is_on(self):
        return (self.coordinator.data or {}).get("power")
