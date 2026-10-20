"""HTTP routing protocol audited against the existing No Hassle AV scripts."""

import asyncio
import ipaddress
import re

from yarl import URL

# These are literal protocol codes, not sequential output indices.
OUTPUT_CODES = ("00", "01", "02", "03", "11", "12", "13", "14")


def parse_routes(payload: str) -> dict[int, int]:
    """Read routes by protocol output code, ignoring the accompanying EDID frames."""
    routes = {}
    for frame in payload.split("!"):
        match = re.fullmatch(r"\s*@T\s+([0-9a-f]{2})\s+([0-9a-f]{2})\s*", frame, re.I)
        if not match:
            continue
        code, value = (item.upper() for item in match.groups())
        if code in OUTPUT_CODES:
            source = int(value, 16) + 1
            output = OUTPUT_CODES.index(code) + 1
            if not 1 <= source <= 8 or output in routes:
                raise ValueError("Invalid matrix routing status")
            routes[output] = source
    if len(routes) != 8:
        raise ValueError("Incomplete matrix routing status")
    return routes


def parse_status(payload: str) -> dict:
    # "none" also occurs while the front panel is ON: it is not power feedback.
    if payload.strip() == "none":
        return {"power": None, "routes": {}}
    return {"power": None, "routes": parse_routes(payload)}


def normalize_host(host: str) -> str:
    host = host.strip().lower()
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        if len(host) > 253 or not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        ):
            raise ValueError(
                "Enter an IP address or hostname without a URL or path"
            ) from None
        return host


def route_command(output: int, source: int) -> bytes:
    if (
        type(output) is not int
        or type(source) is not int
        or not (1 <= output <= 8 and 1 <= source <= 8)
    ):
        raise ValueError("Output and input must be integers from 1 to 8")
    return f"@T {OUTPUT_CODES[output - 1]} {source - 1:02X} !".encode("ascii")


class MatrixClient:
    def __init__(self, session, host: str, port: int):
        self.session = session
        self.url = URL.build(
            scheme="http", host=normalize_host(host), port=port, path="/video.set"
        )
        self.lock = asyncio.Lock()

    async def route(self, output: int, source: int):
        await self._send(route_command(output, source))

    async def route_all(self, source: int):
        if type(source) is not int or not 1 <= source <= 8:
            raise ValueError("Input must be an integer from 1 to 8")
        await self._send(f"@T 04 {source - 1:02X} !".encode("ascii"))

    async def power(self, on: bool):
        if type(on) is not bool:
            raise ValueError("Power state must be a boolean")
        await self._send(b"@T 0F 01 !" if on else b"@T 0F 00 !")

    async def status(self):
        async with self.lock:
            async with asyncio.timeout(5):
                async with self.session.get(
                    self.url.with_path("/all_dat.get"),
                    allow_redirects=False,
                    headers={"Cache-Control": "no-cache"},
                ) as response:
                    if response.status != 200:
                        raise OSError(f"Matrix status returned HTTP {response.status}")
                    return parse_status(await response.text())

    async def _send(self, command: bytes):
        async with self.lock:
            async with asyncio.timeout(5):
                async with self.session.post(
                    self.url,
                    data=command,
                    allow_redirects=False,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                ) as response:
                    if response.status != 200:
                        raise OSError(f"Matrix returned HTTP {response.status}")
                    await response.read()
