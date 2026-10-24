"""Moving an HDMI matrix from the old `monoprice` domain, on real HA registries."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.nohassle_av.const import CONF_MIGRATED_FROM, DOMAIN
from custom_components.nohassle_av.diagnostics import (
    async_get_config_entry_diagnostics,
)

HOST = "192.0.2.10"  # documentation address, never a real device
SLUG = "no_hassle_av_matrix_192_0_2_10"
INPUTS = [f"Input {i}" for i in range(1, 9)]


def add_entry(hass, domain, data, *, unique_id=None, title="Matrix"):
    entry = ConfigEntry(
        domain=domain,
        title=title,
        data=data,
        options={},
        source=SOURCE_USER,
        unique_id=unique_id,
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    hass.config_entries._entries[entry.entry_id] = entry
    return entry


def legacy_keys():
    """(domain, unique-ID suffix, object ID) for every pre-0.3.0 matrix entity."""
    keys = [("select", f"matrix_output_{n}", f"{SLUG}_output_{n}") for n in range(1, 9)]
    keys += [
        ("select", "matrix_output_all", f"server_{SLUG}_outputs_all"),
        ("button", "matrix_power_on", f"server_{SLUG}_power_on"),
        ("button", "matrix_power_off", f"server_{SLUG}_power_off"),
        ("binary_sensor", "matrix_power_status", f"server_{SLUG}_power"),
    ]
    return keys


@pytest.fixture
def legacy(hass):
    """An old matrix entry, its device in an area, and its 12 registry entities."""
    entry = add_entry(
        hass,
        "monoprice",
        {
            "device_type": "matrix",
            "host": HOST,
            "http_port": 80,
            "input_names": INPUTS,
        },
        unique_id=f"matrix:{HOST}:80",
        title=f"No Hassle AV Matrix ({HOST})",
    )
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("monoprice", f"matrix_{entry.entry_id}")},
        manufacturer="No Hassle AV",
        name=entry.title,
    )
    devices.async_update_device(device.id, area_id="server", name_by_user="AV rack")
    entities = er.async_get(hass)
    for domain, suffix, object_id in legacy_keys():
        entities.async_get_or_create(
            domain,
            "monoprice",
            f"{entry.entry_id}_{suffix}",
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=object_id,
        )
    entities.async_update_entity(f"select.{SLUG}_output_3", name="Living room TV")
    entities.async_update_entity(
        f"select.{SLUG}_output_8", disabled_by=er.RegistryEntryDisabler.USER
    )
    return entry, device


async def import_legacy(hass, legacy_entry):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={"legacy_entry_id": legacy_entry.entry_id},
    )
    await hass.async_block_till_done()
    return result


async def test_import_moves_entities_device_and_removes_old_entry(
    hass, session, legacy
):
    legacy_entry, device = legacy
    result = await import_legacy(hass, legacy_entry)
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert CONF_MIGRATED_FROM not in entry.data
    assert entry.title == legacy_entry.title
    assert entry.unique_id == f"matrix:{HOST}:80"
    assert hass.config_entries.async_get_entry(legacy_entry.entry_id) is None

    registry = er.async_get(hass)
    moved = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(moved) == 12
    for domain, suffix, object_id in legacy_keys():
        entity = registry.async_get(f"{domain}.{object_id}")
        assert entity is not None, f"{domain}.{object_id} lost its entity ID"
        assert entity.platform == DOMAIN
        assert entity.config_entry_id == entry.entry_id
        assert entity.unique_id == f"{entry.entry_id}_{suffix}"
        assert entity.device_id == device.id
    assert registry.async_get(f"select.{SLUG}_output_3").name == "Living room TV"
    assert registry.async_get(f"select.{SLUG}_output_8").disabled_by is not None

    kept = dr.async_get(hass).async_get(device.id)
    assert kept is not None
    assert kept.identifiers == {(DOMAIN, f"matrix_{entry.entry_id}")}
    assert kept.config_entry_id == entry.entry_id
    assert (kept.area_id, kept.name_by_user) == ("server", "AV rack")

    # The moved entities are live under the new integration.
    assert hass.states.get(f"select.{SLUG}_output_1").state == "Input 1"
    assert hass.states.get(f"select.{SLUG}_output_3").name == "Living room TV"


async def test_failed_old_entry_removal_does_not_break_the_new_entry(
    hass, session, legacy
):
    legacy_entry, _ = legacy
    with patch.object(
        hass.config_entries, "async_remove", side_effect=ImportError("pymonoprice")
    ):
        result = await import_legacy(hass, legacy_entry)
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert CONF_MIGRATED_FROM not in entry.data
    # The move stands; only the empty old entry is left for the user to delete.
    assert (
        len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)) == 12
    )
    assert hass.states.get(f"select.{SLUG}_output_1").state == "Input 1"


async def test_second_import_is_a_no_op(hass, session, legacy):
    legacy_entry, _ = legacy
    await import_legacy(hass, legacy_entry)
    again = await import_legacy(hass, legacy_entry)
    assert again["type"] == "abort" and again["reason"] == "legacy_not_found"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_loaded_old_entry_is_unloaded_before_its_entities_move(
    hass, session, legacy
):
    legacy_entry, _ = legacy
    legacy_entry._async_set_state(hass, ConfigEntryState.LOADED, None)
    calls = []

    async def unload(entry_id):
        calls.append(entry_id)
        legacy_entry._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
        return True

    with patch.object(hass.config_entries, "async_unload", side_effect=unload):
        result = await import_legacy(hass, legacy_entry)
    assert result["type"] == "create_entry"
    assert calls == [legacy_entry.entry_id]


async def test_user_flow_offers_the_import_when_an_old_matrix_exists(
    hass, session, legacy
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "menu"
    assert result["menu_options"] == ["migrate", "manual"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "migrate"}
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert (
        len(
            er.async_entries_for_config_entry(
                er.async_get(hass), result["result"].entry_id
            )
        )
        == 12
    )


async def test_existing_entry_for_the_same_matrix_blocks_the_import(
    hass, session, legacy
):
    legacy_entry, _ = legacy
    add_entry(
        hass,
        DOMAIN,
        {"host": HOST, "http_port": 80, "input_names": INPUTS},
        unique_id=f"matrix:{HOST}:80",
    )
    result = await import_legacy(hass, legacy_entry)
    assert result["type"] == "abort" and result["reason"] == "already_configured"
    # Nothing was moved: the old entry and its entities are untouched.
    assert hass.config_entries.async_get_entry(legacy_entry.entry_id) is not None
    assert (
        len(
            er.async_entries_for_config_entry(er.async_get(hass), legacy_entry.entry_id)
        )
        == 12
    )


async def test_manual_setup_and_validation(hass, session):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "manual"  # no old matrix, no menu
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


async def test_diagnostics_redact_the_matrix_address(hass, session, legacy):
    legacy_entry, _ = legacy
    entry = (await import_legacy(hass, legacy_entry))["result"]
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert HOST not in str(diagnostics)
    assert diagnostics["status"]["routes"][1] == 1


async def test_setup_survives_an_offline_matrix(hass, session):
    session.status = 500
    entry = add_entry(
        hass,
        DOMAIN,
        {"host": HOST, "http_port": 80, "input_names": INPUTS},
        unique_id=f"matrix:{HOST}:80",
    )
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
