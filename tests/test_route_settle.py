"""After a routing command the matrix refuses new connections for a moment.

Measured on the tested unit (2026-11-06): the status poll sent right after a command
was refused, and so was its immediate retry, which made every matrix entity
unavailable until the next regular poll. A command sent in that time was then
skipped by Home Assistant. The client now waits a refusal out, and a short settling
window covers a refusal that lasts longer.
"""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.nohassle_av.coordinator import (
    POWER_SETTLE_SECONDS,
    ROUTE_SETTLE_SECONDS,
    MatrixCoordinator,
)
from custom_components.nohassle_av.matrix import MatrixClient
from custom_components.nohassle_av.select import MatrixAllOutputs, MatrixOutput

from .conftest import STATUS_PAYLOAD, FakeSession
from .test_setup import setup_matrix

REFUSED = aiohttp.ClientConnectorError(
    SimpleNamespace(host="example.invalid", port=80, ssl=True, is_ssl=False),
    ConnectionRefusedError(111, "Connection refused"),
)


def test_noting_a_route_command_opens_a_short_window():
    state = SimpleNamespace(settling_until=0.0)
    before = time.monotonic()
    MatrixCoordinator.note_route_command(state)
    assert (
        before + ROUTE_SETTLE_SECONDS
        <= state.settling_until
        <= time.monotonic() + ROUTE_SETTLE_SECONDS
    )
    assert ROUTE_SETTLE_SECONDS == 5.0


def test_a_route_command_never_shortens_a_power_window():
    state = SimpleNamespace(settling_until=time.monotonic() + POWER_SETTLE_SECONDS)
    power_window = state.settling_until
    MatrixCoordinator.note_route_command(state)
    assert state.settling_until == power_window


def wired_select(status=200):
    session = FakeSession()
    session.status = status
    client = MatrixClient(session, "example.invalid", 80)
    order = []
    client.coordinator = SimpleNamespace(
        data=None,
        note_route_command=Mock(side_effect=lambda: order.append("note")),
        async_poll_for_report=AsyncMock(side_effect=lambda: order.append("poll")),
    )
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Matrix",
        runtime_data=client,
        data={"input_names": [f"Input {i}" for i in range(1, 9)]},
    )
    return entry, order


@pytest.mark.parametrize("entity", [lambda e: MatrixOutput(e, 3), MatrixAllOutputs])
async def test_the_window_opens_after_the_matrix_accepts_the_command(entity):
    entry, order = wired_select()
    await entity(entry).async_select_option("Input 4")
    assert order == ["note", "poll"]


@pytest.mark.parametrize("entity", [lambda e: MatrixOutput(e, 3), MatrixAllOutputs])
async def test_a_refused_command_opens_no_window(entity):
    entry, order = wired_select(status=500)
    with pytest.raises(HomeAssistantError):
        await entity(entry).async_select_option("Input 4")
    assert order == []


async def test_selecting_an_input_does_not_make_the_entities_unavailable(
    hass, session, caplog
):
    entry = await setup_matrix(hass)
    registry = er.async_get(hass)
    entities = {
        e.unique_id.removeprefix(f"{entry.entry_id}_"): e.entity_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    output = entities["matrix_output_1"]
    power = entities["matrix_power_status"]
    coordinator = entry.runtime_data.coordinator

    def states():
        return [hass.states.get(e).state for e in (output, power)]

    def loud():
        return [
            r
            for r in caplog.records
            if r.name.startswith("custom_components.nohassle_av")
            and r.levelno >= logging.WARNING
        ]

    assert states() == ["Input 1", "unknown"]
    caplog.clear()
    # Every poll after the command is refused, for longer than the client waits.
    session.get.side_effect = REFUSED
    session.get.reset_mock()
    with (
        patch("custom_components.nohassle_av.matrix.REFUSED_RETRY_DELAYS", (0, 0)),
        patch("custom_components.nohassle_av.coordinator.REPORT_POLL_DELAYS", (0, 0)),
    ):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": output, "option": "Input 3"},
            blocking=True,
        )
        await hass.async_block_till_done()
    assert session.post.call_count == 1
    # It kept polling through the refusals instead of giving up at the first one.
    assert session.get.call_count == 2 * 3
    assert states() == ["Input 1", "unknown"]
    assert loud() == []

    # A second command in the window is sent, not skipped as unavailable.
    with (
        patch("custom_components.nohassle_av.matrix.REFUSED_RETRY_DELAYS", (0, 0)),
        patch("custom_components.nohassle_av.coordinator.REPORT_POLL_DELAYS", (0,)),
    ):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": output, "option": "Input 4"},
            blocking=True,
        )
    assert session.post.call_count == 2

    # Once the window has passed, the same failure is reported as it always was.
    coordinator.settling_until = 0.0
    with patch("custom_components.nohassle_av.matrix.REFUSED_RETRY_DELAYS", (0,)):
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert states() == ["unavailable", "unavailable"]
    assert [r.levelno for r in loud()] == [logging.ERROR]

    # And the matrix answering again clears it.
    session.get.side_effect = lambda *a, **k: session._context()
    session.body = STATUS_PAYLOAD.encode("ascii")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert states() == ["Input 1", "unknown"]
