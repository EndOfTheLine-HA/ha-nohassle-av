"""HTTP routing protocol audited against the existing No Hassle AV scripts."""

import asyncio
import ipaddress
import re

from yarl import URL

# These are literal protocol codes, not sequential output indices.
OUTPUT_CODES = ("00", "01", "02", "03", "11", "12", "13", "14")


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
        command = route_command(output, source)
        async with self.lock:
            async with asyncio.timeout(5):
                async with self.session.post(
                    self.url, data=command, allow_redirects=False
                ) as response:
                    if response.status != 200:
                        raise OSError(f"Matrix returned HTTP {response.status}")
                    await response.read()
