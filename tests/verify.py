"""Native HA tests. Uses simulated HTTP and amp clients; never contacts hardware."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.monoprice import async_setup_entry, async_unload_entry
from custom_components.monoprice.config_flow import MonoPriceConfigFlow
from custom_components.monoprice.matrix import (
    MatrixClient,
    normalize_host,
    route_command,
)
from custom_components.monoprice.media_player import MonopriceZone
from custom_components.monoprice.number import MonopriceZoneNumber, NUMBERS
from custom_components.monoprice.select import MatrixOutput
from custom_components.monoprice.button import MatrixPower
from homeassistant.exceptions import HomeAssistantError


async def main():
    for output, code in enumerate(("00", "01", "02", "03", "11", "12", "13", "14"), 1):
        for source in range(1, 9):
            assert (
                route_command(output, source)
                == f"@T {code} {source - 1:02X} !".encode()
            )
    for output, source in [(0, 1), (9, 1), (1, 0), (1, 9), (True, 1), (1, "2")]:
        try:
            route_command(output, source)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid route accepted")
    for bad in ("http://example.invalid", "example.invalid/path", "foo:80", "", "a b"):
        try:
            normalize_host(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid host accepted")
    assert normalize_host("EXAMPLE.invalid") == "example.invalid"
    response = SimpleNamespace(status=200, read=AsyncMock(return_value=b"OK"))
    context = AsyncMock()
    context.__aenter__.return_value = response
    session = SimpleNamespace(post=Mock(return_value=context))
    client = MatrixClient(session, "example.invalid", 80)
    await client.route(5, 8)
    assert session.post.call_args.kwargs["data"] == b"@T 11 07 !"
    assert session.post.call_args.kwargs["allow_redirects"] is False
    assert (
        session.post.call_args.kwargs["headers"]["Content-Type"]
        == "application/x-www-form-urlencoded"
    )
    entry = SimpleNamespace(
        entry_id="legacy-entry",
        title="Matrix",
        data={
            "device_type": "matrix",
            "host": "example.invalid",
            "http_port": 80,
            "input_names": [f"Input {i}" for i in range(1, 9)],
        },
        runtime_data=client,
    )
    entity = MatrixOutput(entry, 5)
    entity.async_write_ha_state = Mock()
    await entity.async_select_option("Input 8")
    assert entity.current_option == "Input 8"
    for on, expected in ((True, b"@T 0F 01 !"), (False, b"@T 0F 00 !")):
        button = MatrixPower(entry, on=on)
        assert button.device_info["identifiers"] == entity.device_info["identifiers"]
        assert button.unique_id == f"legacy-entry_matrix_power_{'on' if on else 'off'}"
        await button.async_press()
        assert session.post.call_args.kwargs["data"] == expected
    assert entity.current_option == "Input 8"
    response.status = 500
    for on in (True, False):
        try:
            await MatrixPower(entry, on=on).async_press()
        except HomeAssistantError:
            pass
        else:
            raise AssertionError("Failed power command accepted")
    response.status = 200
    with patch.object(client, "_send", new=AsyncMock(side_effect=TimeoutError)):
        try:
            await MatrixPower(entry, on=True).async_press()
        except HomeAssistantError:
            pass
        else:
            raise AssertionError("Power timeout accepted")
    response.status = 500
    try:
        await entity.async_select_option("Input 1")
    except HomeAssistantError:
        pass
    else:
        raise AssertionError("Failed route accepted")
    assert entity.current_option == "Input 8"
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(),
            async_unload_platforms=AsyncMock(return_value=True),
        )
    )
    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        await async_setup_entry(hass, entry)
    assert hass.config_entries.async_forward_entry_setups.call_args.args[1] == [
        "select",
        "button",
    ]
    await async_unload_entry(hass, entry)
    assert hass.config_entries.async_unload_platforms.call_args.args[1] == [
        "select",
        "button",
    ]
    # An existing config entry has no device_type. It must remain an amplifier.
    legacy = SimpleNamespace(
        entry_id="legacy-entry",
        data={"port": "same-port", "not_first_run": True},
        async_on_unload=Mock(),
        add_update_listener=Mock(),
    )
    hass.async_add_executor_job = AsyncMock(return_value=Mock())
    with patch("custom_components.monoprice.get_monoprice"):
        await async_setup_entry(hass, legacy)
    assert hass.config_entries.async_forward_entry_setups.call_args.args[1] == [
        "media_player",
        "number",
    ]
    assert legacy.data == {"port": "same-port", "not_first_run": True}
    assert legacy.runtime_data.first_run is False
    # Legacy namespace and EQ behavior remain exactly the same.
    amp = Mock()
    runtime = SimpleNamespace(client=amp, zone_status={})
    zone = MonopriceZone(
        amp, [{1: "Input 1"}, {"Input 1": 1}, ["Input 1"]], "legacy-entry", 11, runtime
    )
    assert zone.unique_id == "legacy-entry_11"
    zone.turn_on()
    amp.set_power.assert_called_with(11, True)
    for description in NUMBERS:
        number = MonopriceZoneNumber(runtime, "legacy-entry", 11, description)
        assert number.unique_id == f"legacy-entry_11_{description.key}"
        number.schedule_update_ha_state = Mock()
        number.set_native_value(0)
        getattr(amp, description.setter).assert_called_with(11, description.offset)
    flow = MonoPriceConfigFlow()
    flow.hass = SimpleNamespace()
    assert (await flow.async_step_user())["menu_options"] == ["amp", "matrix"]
    flow._async_current_entries = lambda: [SimpleNamespace(data={"port": "same-port"})]
    with patch(
        "custom_components.monoprice.config_flow.validate_input", new=AsyncMock()
    ) as connect:
        result = await flow.async_step_amp({"port": "same-port"})
        assert result["reason"] == "already_configured"
        connect.assert_not_called()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()
    data = {
        "host": "example.invalid",
        "http_port": 80,
        **{f"input_{i}": f"Input {i}" for i in range(1, 9)},
    }
    result = await flow.async_step_matrix(data)
    assert result["data"]["device_type"] == "matrix"
    data["input_2"] = data["input_1"]
    assert (await flow.async_step_matrix(data))["errors"]["base"] == "invalid_sources"
    print(
        "PASS: all 64 routes, power buttons, HTTP failures/timeouts, device identity, "
        "lifecycle isolation, setup choice, legacy amp IDs and EQ, duplicate amp prevention"
    )


asyncio.run(main())
