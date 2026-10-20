"""Source selectors backed by the matrix's live routing feedback."""

from aiohttp import ClientError
from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([MatrixOutput(entry, output) for output in range(1, 9)])


class MatrixOutput(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:video-input-hdmi"

    def __init__(self, entry, output):
        self.client = entry.runtime_data
        super().__init__(self.client.coordinator)
        self.output = output
        self._attr_name = f"Output {output}"
        self._attr_unique_id = f"{entry.entry_id}_matrix_output_{output}"
        self._attr_options = list(entry.data["input_names"])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"matrix_{entry.entry_id}")},
            manufacturer="No Hassle AV",
            model="8×8 HDMI Matrix",
            name=entry.title,
        )
        self._attr_extra_state_attributes = {"state_source": "device"}

    @property
    def current_option(self):
        source = (self.coordinator.data or {}).get("routes", {}).get(self.output)
        return self.options[source - 1] if source is not None else None

    @property
    def available(self):
        return super().available and bool((self.coordinator.data or {}).get("power"))

    async def async_select_option(self, option):
        if option not in self.options:
            raise HomeAssistantError("Unknown matrix input")
        try:
            await self.client.route(self.output, self.options.index(option) + 1)
        except (ClientError, OSError, TimeoutError) as err:
            raise HomeAssistantError("Matrix routing failed") from err
        await self.coordinator.async_request_refresh()
