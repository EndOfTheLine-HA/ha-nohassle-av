"""Config flow for the No Hassle AV HDMI matrix."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_HOST,
    CONF_HTTP_PORT,
    CONF_INPUT_NAMES,
    DEFAULT_HTTP_PORT,
    DOMAIN,
    INPUT_COUNT,
)
from .matrix import normalize_host


def matrix_unique_id(host: str, port: int) -> str:
    return f"matrix:{host}:{port}"


class NoHassleAVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an HDMI matrix by address."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            step_id="user", data_schema=vol.Schema(schema), errors=errors
        )
