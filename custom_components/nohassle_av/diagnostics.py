"""Diagnostics for the No Hassle AV HDMI matrix."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NoHassleConfigEntry
from .const import CONF_HOST

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NoHassleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with the matrix address removed."""
    coordinator = entry.runtime_data.coordinator
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "status": coordinator.data,
    }
