"""No Hassle AV: 8×8 HDMI matrix control over the matrix's HTTP interface."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HOST, CONF_HTTP_PORT, CONF_MIGRATED_FROM, PLATFORMS
from .coordinator import MatrixCoordinator
from .matrix import MatrixClient
from .migration import async_finish_migration

type NoHassleConfigEntry = ConfigEntry[MatrixClient]


async def async_setup_entry(hass: HomeAssistant, entry: NoHassleConfigEntry) -> bool:
    """Set up one HDMI matrix."""
    # A matrix imported from the old `monoprice` domain takes over its entities
    # and device here, before any platform loads, so entity IDs and history
    # carry over.
    if entry.data.get(CONF_MIGRATED_FROM):
        await async_finish_migration(hass, entry)

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
