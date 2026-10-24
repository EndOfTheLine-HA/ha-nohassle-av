"""One shared status request for all eight matrix outputs."""

import logging
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


class MatrixCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="No Hassle AV matrix",
            config_entry=entry,
            update_interval=timedelta(seconds=15),
        )
        self.client = client

    async def _async_update_data(self):
        try:
            status = await self.client.status()
            # The firmware can return "none" between routing reports.
            if not status["routes"] and self.data:
                status["routes"] = self.data.get("routes", {})
            return status
        except (ClientError, OSError, TimeoutError, ValueError) as err:
            raise UpdateFailed("Cannot read matrix routing status") from err
