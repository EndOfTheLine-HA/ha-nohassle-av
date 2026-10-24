"""Source selectors backed by the matrix's live routing feedback."""

from aiohttp import ClientError
from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .entity import matrix_device_info


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            *(MatrixOutput(entry, output) for output in range(1, 9)),
            MatrixAllOutputs(entry),
        ]
    )


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
        self._attr_device_info = matrix_device_info(entry)
        self._attr_extra_state_attributes = {"state_source": "device"}

    @property
    def current_option(self):
        source = (self.coordinator.data or {}).get("routes", {}).get(self.output)
        return self.options[source - 1] if source is not None else None

    async def async_select_option(self, option):
        if option not in self.options:
            raise HomeAssistantError("Unknown matrix input")
        try:
            await self.client.route(self.output, self.options.index(option) + 1)
        except (ClientError, OSError, TimeoutError) as err:
            raise HomeAssistantError("Matrix routing failed") from err
        await self.coordinator.async_request_refresh()


class MatrixAllOutputs(MatrixOutput):
    """Route one input to every output using the matrix's broadcast command."""

    def __init__(self, entry):
        super().__init__(entry, output=0)
        # Sorts after Output 8 in HA's device controls, before the power buttons.
        self._attr_name = "Outputs: All"
        self._attr_unique_id = f"{entry.entry_id}_matrix_output_all"

    @property
    def current_option(self):
        routes = (self.coordinator.data or {}).get("routes", {})
        if set(routes) != set(range(1, 9)) or len(set(routes.values())) != 1:
            return None
        return self.options[routes[1] - 1]

    async def async_select_option(self, option):
        if option not in self.options:
            raise HomeAssistantError("Unknown matrix input")
        try:
            await self.client.route_all(self.options.index(option) + 1)
        except (ClientError, OSError, TimeoutError) as err:
            raise HomeAssistantError("Matrix all-output routing failed") from err
        await self.coordinator.async_request_refresh()
