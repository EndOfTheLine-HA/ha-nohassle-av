"""One shared status request for all eight matrix outputs."""

import asyncio
import logging
import time
from datetime import timedelta

from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

# Seconds to wait before each poll after a command. The matrix reports its routing
# once per change, usually within a fraction of a second, and answers "none" at every
# other time, so a few quick polls are the only way to catch the new routes.
REPORT_POLL_DELAYS = (0.0, 0.4, 1.0)

# After a power command the matrix answers one status request with something that is
# not a routing report, and a power on restarts its web server for 8 to 45 seconds
# (measured on the tested unit). A failed poll in this window is expected, so it keeps
# the previous data instead of marking every entity unavailable.
POWER_SETTLE_SECONDS = 60.0


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
        # time.monotonic() value until which a failed poll is expected.
        self.settling_until = 0.0

    def note_power_command(self):
        """Call after the matrix accepted a power command."""
        self.settling_until = time.monotonic() + POWER_SETTLE_SECONDS

    async def _async_update_data(self):
        try:
            status = await self.client.status()
            self.reported = bool(status["routes"])
            # The firmware can return "none" between routing reports.
            if not status["routes"] and self.data:
                status["routes"] = self.data.get("routes", {})
            return status
        except (ClientError, OSError, TimeoutError, ValueError) as err:
            # Only while the matrix was reachable before: a device that was already
            # failing must keep showing as unavailable.
            if (
                self.data
                and self.last_update_success
                and time.monotonic() < self.settling_until
            ):
                _LOGGER.debug("Matrix status failed while it settles: %r", err)
                self.reported = False
                return self.data
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
