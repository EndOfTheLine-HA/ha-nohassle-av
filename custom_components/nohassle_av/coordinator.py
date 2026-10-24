"""One shared status request for all eight matrix outputs."""

import asyncio
import logging
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

# Seconds to wait before each poll after a command. The matrix reports its routing
# once per change, usually within a fraction of a second, and answers "none" at every
# other time, so a few quick polls are the only way to catch the new routes.
REPORT_POLL_DELAYS = (0.0, 0.4, 1.0)


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
        # True when the last poll carried a routing report from the matrix, False
        # when it only said "none" and the previous routes were kept.
        self.reported = False

    async def _async_update_data(self):
        try:
            status = await self.client.status()
            self.reported = bool(status["routes"])
            # The firmware can return "none" between routing reports.
            if not status["routes"] and self.data:
                status["routes"] = self.data.get("routes", {})
            return status
        except (ClientError, OSError, TimeoutError, ValueError) as err:
            raise UpdateFailed("Cannot read matrix routing status") from err

    async def async_poll_for_report(self):
        """After a command, poll briefly until the matrix reports the new routes.

        Gives up at the first failed poll (the regular poll recovers) and after a
        bounded wait, since a command that changes nothing produces no report.
        """
        for delay in REPORT_POLL_DELAYS:
            await asyncio.sleep(delay)
            await self.async_refresh()
            if not self.last_update_success or self.reported:
                return
