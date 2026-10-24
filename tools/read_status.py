"""Read matrix feedback without changing any device setting. Run using HA Python."""

import asyncio
import sys
from pathlib import Path

from aiohttp import ClientSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.nohassle_av.matrix import MatrixClient


async def main():
    async with ClientSession() as session:
        print(await MatrixClient(session, sys.argv[1], 80).status())


asyncio.run(main())
