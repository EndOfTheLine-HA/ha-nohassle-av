"""Isolated Home Assistant with a simulated matrix. No test reaches a device."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

OUTPUT_CODES = ("00", "01", "02", "03", "11", "12", "13", "14")
# Output n routed to input n: a complete, valid routing report.
STATUS_PAYLOAD = "".join(f"@T {code} {i:02X} !" for i, code in enumerate(OUTPUT_CODES))


@pytest.fixture
async def hass(tmp_path):
    source = Path(__file__).parents[1] / "custom_components" / "nohassle_av"
    shutil.copytree(
        source,
        tmp_path / "custom_components" / "nohassle_av",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    loader.async_setup(instance)
    dr.async_setup(instance)
    await ar.async_load(instance, load_empty=True)
    await dr.async_load(instance, load_empty=True)
    await er.async_load(instance, load_empty=True)
    yield instance
    await instance.async_stop(force=True)


class FakeSession:
    """Stands in for aiohttp: answers every request with the current body."""

    def __init__(self) -> None:
        self.status = 200
        self.body = STATUS_PAYLOAD.encode("ascii")
        self.post = Mock(side_effect=lambda *a, **k: self._context())
        self.get = Mock(side_effect=lambda *a, **k: self._context())

    def _context(self):
        body = self.body

        def iter_chunked(size):
            async def chunks():
                for start in range(0, len(body), size):
                    yield body[start : start + size]

            return chunks()

        response = SimpleNamespace(
            status=self.status, content=SimpleNamespace(iter_chunked=iter_chunked)
        )
        context = AsyncMock()
        context.__aenter__.return_value = response
        return context


@pytest.fixture
def session():
    fake = FakeSession()
    with patch(
        "custom_components.nohassle_av.async_get_clientsession", return_value=fake
    ):
        yield fake
