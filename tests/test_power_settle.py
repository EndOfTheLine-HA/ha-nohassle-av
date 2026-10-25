"""After a power command the matrix answers oddly and restarts its web server.

Measured on the tested unit (2026-10-24): every power press made the next status
read fail, and a power on took the web server down for 8 to 45 seconds. That must
not make the source selectors and the Power sensor unavailable, or log an error,
for something expected. The power buttons never depended on the status poll.
"""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ServerDisconnectedError
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.nohassle_av.button import MatrixPower
from custom_components.nohassle_av.coordinator import (
    POWER_SETTLE_SECONDS,
    MatrixCoordinator,
)
from custom_components.nohassle_av.matrix import MatrixClient

from .conftest import STATUS_PAYLOAD, FakeSession
from .test_setup import setup_matrix

COORDINATOR_LOGGER = "custom_components.nohassle_av.coordinator"
ROUTES = {"power": None, "routes": {i: 1 for i in range(1, 9)}}
FAILURES = [
    ValueError("Incomplete matrix routing status"),
    ServerDisconnectedError(),
    TimeoutError(),
    OSError("Connection refused"),
]


def coordinator(*, error, window, data=ROUTES, last_ok=True):
    return SimpleNamespace(
        client=SimpleNamespace(status=AsyncMock(side_effect=error)),
        data=data,
        last_update_success=last_ok,
        settling_until=time.monotonic() + window,
        reported=True,
    )


@pytest.mark.parametrize("error", FAILURES, ids=lambda e: type(e).__name__)
async def test_a_failed_poll_inside_the_window_keeps_the_last_data(error, caplog):
    caplog.set_level(logging.DEBUG, logger=COORDINATOR_LOGGER)
    state = coordinator(error=error, window=30)
    assert await MatrixCoordinator._async_update_data(state) is ROUTES
    assert state.reported is False
    ours = [r for r in caplog.records if r.name == COORDINATOR_LOGGER]
    assert [r.levelno for r in ours] == [logging.DEBUG]  # logged, and only at debug


@pytest.mark.parametrize("error", FAILURES, ids=lambda e: type(e).__name__)
async def test_a_failed_poll_outside_the_window_is_a_failure(error):
    with pytest.raises(UpdateFailed, match="Cannot read matrix routing status"):
        await MatrixCoordinator._async_update_data(coordinator(error=error, window=-1))


async def test_the_window_never_hides_a_matrix_that_was_already_failing():
    for kwargs in ({"data": None}, {"last_ok": False}):
        with pytest.raises(UpdateFailed):
            await MatrixCoordinator._async_update_data(
                coordinator(error=OSError(), window=30, **kwargs)
            )


def test_noting_a_power_command_opens_a_bounded_window():
    state = SimpleNamespace(settling_until=0.0)
    before = time.monotonic()
    MatrixCoordinator.note_power_command(state)
    assert (
        before + POWER_SETTLE_SECONDS
        <= state.settling_until
        <= time.monotonic() + POWER_SETTLE_SECONDS
    )
    # The README, AUDIT and release notes all say 60 seconds.
    assert POWER_SETTLE_SECONDS == 60.0


def wired_button(status=200):
    session = FakeSession()
    session.status = status
    client = MatrixClient(session, "example.invalid", 80)
    order = []
    client.coordinator = SimpleNamespace(
        note_power_command=Mock(side_effect=lambda: order.append("note")),
        async_request_refresh=AsyncMock(side_effect=lambda: order.append("refresh")),
    )
    entry = SimpleNamespace(
        entry_id="entry-1", title="Matrix", runtime_data=client, data={}
    )
    return session, client, entry, order


@pytest.mark.parametrize("on", [True, False])
async def test_the_window_opens_after_the_matrix_accepts_the_command(on):
    session, client, entry, order = wired_button()
    await MatrixPower(entry, on=on).async_press()
    assert order == ["note", "refresh"]  # window first, then the refresh it covers


@pytest.mark.parametrize("on", [True, False])
async def test_a_refused_command_opens_no_window(on):
    session, client, entry, order = wired_button(status=500)
    with pytest.raises(HomeAssistantError):
        await MatrixPower(entry, on=on).async_press()
    assert order == []


@pytest.mark.parametrize("on", [True, False])
async def test_a_command_that_times_out_opens_no_window(on):
    """A known limit: the matrix may have received it, but a timeout cannot say."""
    session, client, entry, order = wired_button()
    with (
        patch.object(client, "_send", new=AsyncMock(side_effect=TimeoutError)),
        pytest.raises(HomeAssistantError),
    ):
        await MatrixPower(entry, on=on).async_press()
    assert order == []


async def test_a_power_press_does_not_make_the_entities_unavailable(
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
    button = entities["matrix_power_off"]
    assert hass.states.get(output).state == "Input 1"
    assert hass.states.get(power).state == "unknown"

    def states():
        return [hass.states.get(e).state for e in (output, power, button)]

    def loud():
        return [
            r
            for r in caplog.records
            if r.name.startswith("custom_components.nohassle_av")
            and r.levelno >= logging.WARNING
        ]

    # The next status read after the command is not a routing report.
    caplog.clear()
    session.body = b"@T 0F 00 !"
    session.get.reset_mock()
    await hass.services.async_call(
        "button", "press", {"entity_id": button}, blocking=True
    )
    await hass.async_block_till_done()
    assert session.get.call_count == 1  # the refresh did run, and failed
    # Still shown, not unavailable, and nothing louder than debug was logged.
    assert states()[:2] == ["Input 1", "unknown"]
    assert "unavailable" not in states()
    assert loud() == []

    # Once the window has passed, the same failure is reported as it always was.
    entry.runtime_data.coordinator.settling_until = 0.0
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert states()[:2] == ["unavailable", "unavailable"]
    assert (
        hass.states.get(button).state != "unavailable"
    )  # buttons never depended on it
    assert [r.levelno for r in loud()] == [logging.ERROR]

    # And the matrix coming back clears it.
    session.body = STATUS_PAYLOAD.encode("ascii")
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert states()[:2] == ["Input 1", "unknown"]
