"""Matrix power from its verified standby/route status responses."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MatrixPowerStatus(entry)])


class MatrixPowerStatus(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, entry):
        super().__init__(entry.runtime_data.coordinator)
        self._attr_unique_id = f"{entry.entry_id}_matrix_power_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"matrix_{entry.entry_id}")},
            manufacturer="No Hassle AV",
            model="8×8 HDMI Matrix",
            name=entry.title,
        )

    @property
    def is_on(self):
        return (self.coordinator.data or {}).get("power")
