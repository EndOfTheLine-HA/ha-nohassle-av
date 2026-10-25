"""No Hassle AV: 8×8 HDMI matrix control over the matrix's HTTP interface."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HOST, CONF_HTTP_PORT, CONF_IMPORT_MARKER, PLATFORMS
from .coordinator import MatrixCoordinator
from .matrix import MatrixClient

_LOGGER = logging.getLogger(__name__)

type NoHassleConfigEntry = ConfigEntry[MatrixClient]


async def async_setup_entry(hass: HomeAssistant, entry: NoHassleConfigEntry) -> bool:
    """Set up one HDMI matrix."""
    if entry.data.get(CONF_IMPORT_MARKER):
        _LOGGER.warning(
            "%s was created by an import from an earlier version that may not have "
            "finished, and this version cannot finish it. If its entities show as "
            "no longer provided, install version 0.3.2, restart Home Assistant, then "
            "update again",
            entry.title,
        )
    client = MatrixClient(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_HTTP_PORT]
    )
    client.coordinator = MatrixCoordinator(hass, entry, client)
    entry.runtime_data = client
    # Keep power controls available even when status feedback is offline.
    await client.coordinator.async_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NoHassleConfigEntry) -> bool:
    """Unload a matrix."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
