"""The matrix closes the connection after every reply, and answers with its routing
report only once per change. These tests use a real aiohttp session against a fake
matrix that behaves the same way, because a mocked session cannot show either."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from custom_components.nohassle_av.coordinator import (
    REPORT_POLL_DELAYS,
    MatrixCoordinator,
)
from custom_components.nohassle_av.matrix import MatrixClient

from .conftest import STATUS_PAYLOAD


@pytest.fixture
async def closing_matrix():
    """A server like the matrix: HTTP/1.1, no Connection header, socket closed."""
    requests = []

    async def handle(reader, writer):
        head = await reader.readuntil(b"\r\n\r\n")
        length = 0
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":")[1])
        body_in = await reader.readexactly(length) if length else b""
        requests.append((head.split(b" ")[0].decode(), body_in))
        body = b"" if head.startswith(b"POST") else STATUS_PAYLOAD.encode()
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
            b"Content-Length:%d\r\n\r\n%s" % (len(body), body)
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield port, requests
    server.close()
    await server.wait_closed()


async def test_commands_and_polls_survive_a_matrix_that_closes_every_connection(
    closing_matrix,
):
    port, requests = closing_matrix
    async with aiohttp.ClientSession() as session:
        client = MatrixClient(session, "127.0.0.1", port)
        for _ in range(20):
            await client.route(1, 2)
            status = await client.status()
            assert len(status["routes"]) == 8
    methods = [method for method, _ in requests]
    assert methods.count("POST") >= 20 and methods.count("GET") >= 20


class _Session:
    """Raises the given errors for the first calls, then answers normally."""

    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    def _request(self):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        response = SimpleNamespace(
            status=200,
            content=SimpleNamespace(iter_chunked=_chunks(STATUS_PAYLOAD.encode())),
        )
        context = AsyncMock()
        context.__aenter__.return_value = response
        return context

    def get(self, *args, **kwargs):
        return self._request()

    post = get


def _chunks(body):
    def iter_chunked(size):
        async def chunks():
            yield body

        return chunks()

    return iter_chunked


DISCONNECT = aiohttp.ServerDisconnectedError("Server disconnected")


@pytest.mark.parametrize(
    "error",
    [DISCONNECT, aiohttp.ClientOSError(104, "Connection reset by peer")],
    ids=["disconnected", "reset"],
)
async def test_a_connection_the_matrix_already_closed_is_retried_once(error):
    session = _Session([error])
    client = MatrixClient(session, "example.invalid", 80)
    assert len((await client.status())["routes"]) == 8
    assert session.calls == 2


async def test_a_second_disconnect_is_reported_not_retried_forever():
    session = _Session([DISCONNECT, DISCONNECT, DISCONNECT])
    with pytest.raises(aiohttp.ServerDisconnectedError):
        await MatrixClient(session, "example.invalid", 80).route(1, 1)
    assert session.calls == 2


async def test_other_errors_are_not_retried():
    session = _Session([OSError("boom")])
    with pytest.raises(OSError, match="boom"):
        await MatrixClient(session, "example.invalid", 80).status()
    assert session.calls == 1


def _coordinator(results):
    """results: per refresh, True = the matrix reported routes, False = none,
    None = the poll failed."""
    results = list(results)
    coordinator = SimpleNamespace(reported=False, last_update_success=True)

    async def refresh():
        outcome = results.pop(0)
        coordinator.last_update_success = outcome is not None
        coordinator.reported = bool(outcome)

    coordinator.async_refresh = AsyncMock(side_effect=refresh)
    return coordinator


async def _poll(coordinator):
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    with patch("custom_components.nohassle_av.coordinator.asyncio.sleep", fake_sleep):
        await MatrixCoordinator.async_poll_for_report(coordinator)
    return delays


async def test_polling_stops_as_soon_as_the_matrix_reports():
    coordinator = _coordinator([False, True])
    delays = await _poll(coordinator)
    assert coordinator.async_refresh.await_count == 2
    assert delays == list(REPORT_POLL_DELAYS[:2])


async def test_polling_is_bounded_when_the_matrix_never_reports():
    """Re-selecting the current input produces no report at all."""
    coordinator = _coordinator([False] * 10)
    await _poll(coordinator)
    assert coordinator.async_refresh.await_count == len(REPORT_POLL_DELAYS)
    assert sum(REPORT_POLL_DELAYS) <= 2


async def test_polling_gives_up_when_the_matrix_cannot_be_reached():
    coordinator = _coordinator([None, True, True])
    await _poll(coordinator)
    assert coordinator.async_refresh.await_count == 1


async def test_a_carried_over_none_report_is_not_a_fresh_report():
    coordinator = SimpleNamespace(
        client=SimpleNamespace(
            status=AsyncMock(return_value={"power": None, "routes": {}})
        ),
        data={"power": None, "routes": {i: 1 for i in range(1, 9)}},
    )
    data = await MatrixCoordinator._async_update_data(coordinator)
    assert (
        data["routes"] == coordinator.data["routes"] and coordinator.reported is False
    )
    coordinator.client.status.return_value = {
        "power": None,
        "routes": {i: 2 for i in range(1, 9)},
    }
    await MatrixCoordinator._async_update_data(coordinator)
    assert coordinator.reported is True
