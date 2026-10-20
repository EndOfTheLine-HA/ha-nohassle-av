"""Explicit power commands for the HDMI matrix, without inferred power state."""

from aiohttp import ClientError
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MatrixPower(entry, on=True), MatrixPower(entry, on=False)])


class MatrixPower(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:power"

    def __init__(self, entry, *, on: bool):
        self.client = entry.runtime_data
        self.on = on
        self._attr_name = "Power on" if on else "Power off"
        self._attr_unique_id = f"{entry.entry_id}_matrix_power_{'on' if on else 'off'}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"matrix_{entry.entry_id}")},
            manufacturer="No Hassle AV",
            model="8×8 HDMI Matrix",
            name=entry.title,
        )

    async def async_press(self):
        try:
            await self.client.power(self.on)
        except (ClientError, OSError, TimeoutError) as err:
            raise HomeAssistantError("Matrix power command failed") from err
