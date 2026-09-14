"""Interactive, read-only account probe. Credentials never enter command arguments."""

import asyncio
import secrets
import sys
from getpass import getpass
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "noise_explorer"))
from client.api import NoiseClient, NoiseError  # noqa: E402
from const import READ_KEYS  # noqa: E402


async def probe(email, password):
    async with aiohttp.ClientSession() as session:
        client = NoiseClient(session, email, password, secrets.token_hex(8))
        try:
            await client.connect()
            watches = await client.discover()
            print(f"Sign-in succeeded. Paired watches: {len(watches)}")
            for index, watch in enumerate(watches, 1):
                settings = await client.read_settings(watch["EID"], READ_KEYS)
                print(f"Watch {index}: returned setting names (values hidden):")
                print(", ".join(sorted(k for k in settings if k in READ_KEYS)))
        except (NoiseError, aiohttp.ClientError, TimeoutError) as error:
            print(
                f"Probe failed: {error if isinstance(error, NoiseError) else type(error).__name__}"
            )
            return 1
        finally:
            await client.close()
    return 0


if __name__ == "__main__":
    print("Noise cloud sign-in may replace the phone app's current session.")
    print("This probe only discovers paired watches and reads cached settings.")
    email = input("Noise account email: ")
    password = getpass("Password (hidden): ")
    raise SystemExit(asyncio.run(probe(email, password)))
