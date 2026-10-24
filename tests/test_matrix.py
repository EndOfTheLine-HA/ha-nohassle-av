"""Matrix protocol, client and entities, ported from the pre-0.3.0 verify script."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.nohassle_av.binary_sensor import MatrixPowerStatus
from custom_components.nohassle_av.button import MatrixPower
from custom_components.nohassle_av.coordinator import MatrixCoordinator
from custom_components.nohassle_av.matrix import (
    MAX_RESPONSE_BYTES,
    MatrixClient,
    normalize_host,
    parse_routes,
    parse_status,
    route_command,
)
from custom_components.nohassle_av.select import MatrixAllOutputs, MatrixOutput

from .conftest import OUTPUT_CODES, STATUS_PAYLOAD, FakeSession

ALL_ONE = {i: i for i in range(1, 9)}


def test_parse_routes_and_status():
    assert parse_routes(STATUS_PAYLOAD + "@T 05 00 00 !") == ALL_ONE
    assert parse_status("none\r\n") == {"power": None, "routes": {}}
    assert parse_status(STATUS_PAYLOAD)["power"] is None


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "<html>error</html>",
        STATUS_PAYLOAD.replace("@T 00 00 !", ""),
        STATUS_PAYLOAD + "@T 00 00 !",
        STATUS_PAYLOAD.replace("@T 00 00 !", "@T 00 FF !"),
    ],
)
def test_malformed_status_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_status(bad)


def test_route_commands_cover_all_64_routes():
    for output, code in enumerate(OUTPUT_CODES, 1):
        for source in range(1, 9):
            assert (
                route_command(output, source)
                == f"@T {code} {source - 1:02X} !".encode()
            )


@pytest.mark.parametrize(
    "output,source", [(0, 1), (9, 1), (1, 0), (1, 9), (True, 1), (1, "2")]
)
def test_invalid_routes_are_rejected(output, source):
    with pytest.raises(ValueError):
        route_command(output, source)


@pytest.mark.parametrize(
    "bad", ["http://example.invalid", "example.invalid/path", "foo:80", "", "a b"]
)
def test_invalid_hosts_are_rejected(bad):
    with pytest.raises(ValueError):
        normalize_host(bad)


def test_host_is_normalized():
    assert normalize_host("EXAMPLE.invalid") == "example.invalid"


async def test_none_report_keeps_the_last_routes():
    coordinator = SimpleNamespace(
        client=SimpleNamespace(status=AsyncMock(return_value=parse_status("none"))),
        data={"power": None, "routes": dict(ALL_ONE)},
    )
    assert await MatrixCoordinator._async_update_data(coordinator) == coordinator.data


async def test_client_reads_status_and_sends_routes():
    session = FakeSession()
    client = MatrixClient(session, "example.invalid", 80)
    assert await client.status() == {"power": None, "routes": ALL_ONE}
    assert str(session.get.call_args.args[0]).endswith("/all_dat.get")
    await client.route(5, 8)
    assert session.post.call_args.kwargs["data"] == b"@T 11 07 !"
    assert session.post.call_args.kwargs["allow_redirects"] is False
    assert (
        session.post.call_args.kwargs["headers"]["Content-Type"]
        == "application/x-www-form-urlencoded"
    )


async def test_oversized_reply_fails_like_an_unreachable_device():
    session = FakeSession()
    session.body = STATUS_PAYLOAD.encode("ascii") + b" " * (MAX_RESPONSE_BYTES + 1)
    client = MatrixClient(session, "example.invalid", 80)
    for call in (client.status, lambda: client.route(1, 1)):
        with pytest.raises(OSError, match="larger than expected"):
            await call()


async def test_corrupted_byte_fails_the_poll():
    session = FakeSession()
    session.body = STATUS_PAYLOAD.encode("ascii") + b"\xff"
    with pytest.raises(ValueError):
        await MatrixClient(session, "example.invalid", 80).status()


def _entry(client):
    return SimpleNamespace(
        entry_id="entry-1",
        title="Matrix",
        data={
            "host": "example.invalid",
            "http_port": 80,
            "input_names": [f"Input {i}" for i in range(1, 9)],
        },
        runtime_data=client,
    )


@pytest.fixture
def wired():
    session = FakeSession()
    client = MatrixClient(session, "example.invalid", 80)
    client.coordinator = SimpleNamespace(
        data={"power": True, "routes": {i: 1 for i in range(1, 9)}},
        last_update_success=True,
        async_request_refresh=AsyncMock(),
        async_poll_for_report=AsyncMock(),
        async_refresh=AsyncMock(),
    )
    return session, client, _entry(client)


async def test_output_selects_and_all_outputs(wired):
    session, client, entry = wired
    entity = MatrixOutput(entry, 5)
    all_outputs = MatrixAllOutputs(entry)
    assert all_outputs.unique_id == "entry-1_matrix_output_all"
    assert all_outputs.device_info["identifiers"] == entity.device_info["identifiers"]
    assert all_outputs.current_option == "Input 1"
    for source in range(1, 9):
        await all_outputs.async_select_option(f"Input {source}")
        assert (
            session.post.call_args.kwargs["data"]
            == f"@T 04 {source - 1:02X} !".encode()
        )
    assert all_outputs.current_option == "Input 1"  # Commands do not invent feedback.
    client.coordinator.data["routes"][5] = 2
    assert all_outputs.current_option is None
    client.coordinator.data["routes"][5] = 1
    for invalid in (0, 9, True, "2"):
        with pytest.raises(ValueError):
            await client.route_all(invalid)
    entity.async_write_ha_state = Mock()
    await entity.async_select_option("Input 8")
    assert entity.current_option == "Input 1"  # A sent command is not device feedback.
    client.coordinator.data["routes"][5] = 8  # Next poll observed the new route.
    assert entity.current_option == "Input 8"
    client.coordinator.last_update_success = False
    assert not entity.available


async def test_selecting_an_input_waits_for_the_matrix_to_report(wired):
    session, client, entry = wired
    await MatrixOutput(entry, 3).async_select_option("Input 4")
    await MatrixAllOutputs(entry).async_select_option("Input 2")
    assert client.coordinator.async_poll_for_report.await_count == 2


async def test_power_entities(wired):
    session, client, entry = wired
    entity = MatrixOutput(entry, 5)
    power = MatrixPowerStatus(entry)
    assert power.is_on is True  # Mocked explicit state; the parser never infers it.
    assert power.device_info["identifiers"] == entity.device_info["identifiers"]
    client.coordinator.data = parse_status("none")
    assert power.is_on is None and power.available and entity.current_option is None
    client.coordinator.last_update_success = False
    assert not power.available  # A failed request must not look like powered off.
    client.coordinator.last_update_success = True
    for on, expected in ((True, b"@T 0F 01 !"), (False, b"@T 0F 00 !")):
        button = MatrixPower(entry, on=on)
        assert button.device_info["identifiers"] == entity.device_info["identifiers"]
        assert button.unique_id == f"entry-1_matrix_power_{'on' if on else 'off'}"
        await button.async_press()
        assert session.post.call_args.kwargs["data"] == expected


async def test_failures_raise_home_assistant_errors(wired):
    session, client, entry = wired
    session.status = 500
    with pytest.raises(HomeAssistantError):
        await MatrixAllOutputs(entry).async_select_option("Input 2")
    with pytest.raises(HomeAssistantError):
        await MatrixOutput(entry, 1).async_select_option("Input 1")
    for on in (True, False):
        with pytest.raises(HomeAssistantError):
            await MatrixPower(entry, on=on).async_press()
    session.status = 200
    with (
        patch.object(client, "_send", new=AsyncMock(side_effect=TimeoutError)),
        pytest.raises(HomeAssistantError),
    ):
        await MatrixPower(entry, on=True).async_press()
