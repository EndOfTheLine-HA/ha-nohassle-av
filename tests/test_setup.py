"""Setup, the config flow and diagnostics, on real Home Assistant registries."""

from __future__ import annotations

import logging
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntry, ConfigEntryState
from homeassistant.helpers import entity_registry as er

from custom_components.nohassle_av.const import DOMAIN
from custom_components.nohassle_av.diagnostics import (
    async_get_config_entry_diagnostics,
)

HOST = "192.0.2.10"  # documentation address, never a real device
INPUTS = [f"Input {i}" for i in range(1, 9)]

# Unique-ID suffixes since 0.3.0. They must not change: they are what keeps a
# user's entity IDs, history and names across updates.
UNIQUE_ID_SUFFIXES = {
    *(f"matrix_output_{n}" for n in range(1, 9)),
    "matrix_output_all",
    "matrix_power_on",
    "matrix_power_off",
    "matrix_power_status",
}


def add_entry(hass, host=HOST, **extra):
    entry = ConfigEntry(
        domain=DOMAIN,
        title="Matrix",
        data={"host": host, "http_port": 80, "input_names": INPUTS, **extra},
        options={},
        source=SOURCE_USER,
        unique_id=f"matrix:{host}:80",
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    hass.config_entries._entries[entry.entry_id] = entry
    return entry


async def setup_matrix(hass):
    entry = add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_setup_form_and_validation(hass, session):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form" and result["step_id"] == "user"
    form = {"host": "http://bad/", "http_port": 80} | {
        f"input_{i}": f"Input {i}" for i in range(1, 9)
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
    assert result["errors"] == {"base": "invalid_host"}
    form["host"] = HOST
    form["input_2"] = form["input_1"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
    assert result["errors"] == {"base": "invalid_sources"}
    form["input_2"] = "Input 2"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["data"] == {"host": HOST, "http_port": 80, "input_names": INPUTS}
    assert result["result"].state is ConfigEntryState.LOADED


async def test_the_same_matrix_cannot_be_added_twice(hass, session):
    await setup_matrix(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    form = {"host": HOST, "http_port": 80} | {
        f"input_{i}": f"Input {i}" for i in range(1, 9)
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
    assert result["type"] == "abort" and result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_entities_keep_their_unique_ids(hass, session):
    entry = await setup_matrix(hass)
    found = {
        e.unique_id.removeprefix(f"{entry.entry_id}_")
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }
    assert found == UNIQUE_ID_SUFFIXES
    assert hass.states.get("select.matrix_output_1").state == "Input 1"


def import_warnings(caplog):
    return [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "may not have finished" in r.getMessage()
    ]


async def test_an_entry_with_an_unfinished_import_marker_is_warned_about(
    hass, session, caplog
):
    """0.3.x removes the marker when its import finishes. 0.4.0 cannot finish one."""
    entry = add_entry(hass, migrated_from="an-old-entry-id")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED  # it still works
    assert len(import_warnings(caplog)) == 1
    assert "install version 0.3.2" in import_warnings(caplog)[0].getMessage()


async def test_a_normal_entry_gets_no_import_warning(hass, session, caplog):
    await setup_matrix(hass)
    assert import_warnings(caplog) == []


async def test_diagnostics_redact_the_matrix_address(hass, session):
    entry = await setup_matrix(hass)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert HOST not in str(diagnostics)
    assert diagnostics["status"]["routes"][1] == 1


async def test_setup_survives_an_offline_matrix(hass, session):
    session.status = 500
    entry = add_entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    power_on = next(
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.unique_id.endswith("matrix_power_on")
    )
    # Power buttons stay usable even while routing feedback is unavailable.
    assert hass.states.get(power_on.entity_id).state != "unavailable"
    with patch(
        "custom_components.nohassle_av.matrix.MatrixClient.power", new=AsyncMock()
    ) as power:
        await hass.services.async_call(
            "button", "press", {"entity_id": power_on.entity_id}, blocking=True
        )
    power.assert_awaited_once_with(True)
