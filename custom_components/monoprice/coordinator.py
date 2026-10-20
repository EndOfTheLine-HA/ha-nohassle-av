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
            return await self.client.status()
        except (ClientError, OSError, TimeoutError, ValueError) as err:
            raise UpdateFailed("Cannot read matrix routing status") from err
