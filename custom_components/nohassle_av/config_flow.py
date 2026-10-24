"""Config flow for the No Hassle AV HDMI matrix."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_HOST,
    CONF_HTTP_PORT,
    CONF_INPUT_NAMES,
    CONF_LEGACY_ENTRY_ID,
    DEFAULT_HTTP_PORT,
    DOMAIN,
    INPUT_COUNT,
)
from .matrix import normalize_host
from .migration import legacy_entry_data, legacy_matrix_entries


def matrix_unique_id(host: str, port: int) -> str:
    return f"matrix:{host}:{port}"


class NoHassleAVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an HDMI matrix, or import one set up before the rename."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if legacy_matrix_entries(self.hass):
            return self.async_show_menu(
                step_id="user", menu_options=["migrate", "manual"]
            )
        return await self.async_step_manual()

    async def async_step_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Import a matrix that was set up under the old `monoprice` domain."""
        legacy = legacy_matrix_entries(self.hass)
        if not legacy:
            return self.async_abort(reason="legacy_not_found")
        if len(legacy) == 1:
            return await self._async_import(legacy[0])
        if user_input is not None:
            chosen = self.hass.config_entries.async_get_entry(
                user_input[CONF_LEGACY_ENTRY_ID]
            )
            if chosen is None:
                return self.async_abort(reason="legacy_not_found")
            return await self._async_import(chosen)
        return self.async_show_form(
            step_id="migrate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LEGACY_ENTRY_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=entry.entry_id, label=entry.title
                                )
                                for entry in legacy
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Started by the tone-controls stopgap when it meets a matrix entry."""
        legacy = self.hass.config_entries.async_get_entry(
            import_data.get(CONF_LEGACY_ENTRY_ID, "")
        )
        if legacy is None or legacy not in legacy_matrix_entries(self.hass):
            return self.async_abort(reason="legacy_not_found")
        return await self._async_import(legacy)

    async def _async_import(self, legacy: ConfigEntry) -> ConfigFlowResult:
        data = legacy_entry_data(legacy)
        await self.async_set_unique_id(
            matrix_unique_id(data[CONF_HOST], data[CONF_HTTP_PORT])
        )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=legacy.title, data=data)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a matrix by address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = normalize_host(user_input[CONF_HOST])
            except ValueError:
                errors["base"] = "invalid_host"
            else:
                port = int(user_input[CONF_HTTP_PORT])
                await self.async_set_unique_id(matrix_unique_id(host, port))
                self._abort_if_unique_id_configured()
                names = [
                    str(user_input[f"input_{i}"]).strip()
                    for i in range(1, INPUT_COUNT + 1)
                ]
                if not all(names) or len(set(names)) != INPUT_COUNT:
                    errors["base"] = "invalid_sources"
                else:
                    return self.async_create_entry(
                        title=f"No Hassle AV Matrix ({host})",
                        data={
                            CONF_HOST: host,
                            CONF_HTTP_PORT: port,
                            CONF_INPUT_NAMES: names,
                        },
                    )
        schema: dict = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_HTTP_PORT, default=DEFAULT_HTTP_PORT): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
        }
        schema.update(
            {
                vol.Required(f"input_{i}", default=f"Input {i}"): str
                for i in range(1, INPUT_COUNT + 1)
            }
        )
        return self.async_show_form(
            step_id="manual", data_schema=vol.Schema(schema), errors=errors
        )
