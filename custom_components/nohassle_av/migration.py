"""Move HDMI matrix entries from the old `monoprice` domain to `nohassle_av`.

Before version 0.3.0 this integration shipped as `custom_components/monoprice`
and kept the matrix as a second device type in that domain. The new entry is
created by the import (or user) config flow; this module then moves the old
entry's device and entities across and removes the old entry, so entity IDs,
history, custom names, areas and disabled flags all carry over.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_HOST,
    CONF_HTTP_PORT,
    CONF_INPUT_NAMES,
    CONF_MIGRATED_FROM,
    DOMAIN,
    LEGACY_DEVICE_TYPE,
    LEGACY_DOMAIN,
)
from .entity import matrix_device_identifier

_LOGGER = logging.getLogger(__name__)


@callback
def legacy_matrix_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Old matrix entries that have not been migrated yet."""
    return [
        entry
        for entry in hass.config_entries.async_entries(LEGACY_DOMAIN)
        if entry.data.get("device_type") == LEGACY_DEVICE_TYPE
    ]


def legacy_entry_data(entry: ConfigEntry) -> dict:
    """Data for the new entry, taken from an old matrix entry."""
    return {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_HTTP_PORT: entry.data[CONF_HTTP_PORT],
        CONF_INPUT_NAMES: list(entry.data[CONF_INPUT_NAMES]),
        CONF_MIGRATED_FROM: entry.entry_id,
    }


async def async_finish_migration(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Take over the old entry's device and entities, then remove the old entry.

    Safe to run again: if the old entry is already gone, only the marker is
    cleared.
    """
    legacy_id = entry.data[CONF_MIGRATED_FROM]
    legacy = hass.config_entries.async_get_entry(legacy_id)

    if legacy is not None:
        # Entities can only change integration while they are not loaded. The
        # old override would have loaded them; HA's built-in Monoprice and the
        # tone-controls stopgap refuse matrix entries, so they are not.
        if legacy.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(legacy_id)

        # Order matters: entities first, then the device. Moving a device to
        # another config entry removes any of its entities still registered to
        # the old one.
        moved = _move_entities(hass, legacy_id, entry)
        _move_device(hass, legacy_id, entry)
        try:
            await hass.config_entries.async_remove(legacy_id)
        except Exception:  # noqa: BLE001 - the move above must not be undone by this
            # Removing the old entry loads the old integration's code. If that
            # fails, the entities and device have already moved; leave an empty
            # old entry for the user to delete rather than failing this setup.
            _LOGGER.warning(
                "Moved HDMI matrix %s, but could not remove its old %s entry; "
                "delete it from Settings > Devices & services",
                entry.title,
                LEGACY_DOMAIN,
                exc_info=True,
            )
        _LOGGER.info(
            "Moved HDMI matrix %s (%d entities) from %s to %s",
            entry.title,
            moved,
            LEGACY_DOMAIN,
            DOMAIN,
        )

    data = {
        key: value for key, value in entry.data.items() if key != CONF_MIGRATED_FROM
    }
    hass.config_entries.async_update_entry(entry, data=data)


def _move_device(hass: HomeAssistant, legacy_id: str, entry: ConfigEntry) -> None:
    """Re-home the old device so its ID, area and user-given name are kept."""
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        (LEGACY_DOMAIN, f"matrix_{legacy_id}"), legacy_id
    )
    if device is None:
        return
    # One call: a device belongs to a single config entry. The older
    # add_config_entry_id / remove_config_entry_id pair is deprecated, and
    # remove_config_entry_id on its own deletes the device.
    registry.async_update_device(
        device.id,
        new_config_entry_id=entry.entry_id,
        new_identifiers={matrix_device_identifier(entry.entry_id)},
    )


def _move_entities(hass: HomeAssistant, legacy_id: str, entry: ConfigEntry) -> int:
    """Move every entity of the old entry, rewriting its unique ID prefix."""
    registry = er.async_get(hass)
    prefix = f"{legacy_id}_"
    moved = 0
    for entity in er.async_entries_for_config_entry(registry, legacy_id):
        unique_id = entity.unique_id
        if unique_id.startswith(prefix):
            unique_id = f"{entry.entry_id}_{unique_id.removeprefix(prefix)}"
        registry.async_update_entity_platform(
            entity.entity_id,
            DOMAIN,
            new_config_entry_id=entry.entry_id,
            new_unique_id=unique_id,
        )
        moved += 1
    return moved
