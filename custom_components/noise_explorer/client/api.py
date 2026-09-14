"""Asynchronous encrypted cloud connection with correlated replies and push data."""

import asyncio
import secrets
from collections.abc import Callable
from contextlib import suppress
from urllib.parse import urlparse

import aiohttp

from .protocol import DEFAULT_URL, Codec, login_payload


class NoiseError(Exception):
    """Base error; messages must never contain account or watch data."""


class AuthenticationError(NoiseError):
    """Session expired, credentials rejected, or another session replaced this one."""

    def __init__(self, message: str, rc: int | None = None):
        self.rc = rc
        super().__init__(message)


class ConnectionError(NoiseError):
    """Transport unavailable or response timed out."""


class CommandError(NoiseError):
    def __init__(self, cid: int, rc: int):
        self.cid, self.rc = cid, rc
        super().__init__(f"Cloud command {cid} returned code {rc}")


class NoiseClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        client_id: str,
        *,
        url: str = DEFAULT_URL,
        timezone: str = "UTC+05:30",
        on_push: Callable[[dict], None] | None = None,
        on_disconnect: Callable[[NoiseError], None] | None = None,
    ):
        parsed = urlparse(url)
        if parsed.scheme != "wss" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("A secure WebSocket URL is required")
        self.session, self.email, self.password = session, email, password
        self.client_id, self.url, self.timezone = client_id, url, timezone
        self.on_push, self.on_disconnect = on_push, on_disconnect
        self.sid: str | None = None
        self.eid: str | None = None
        self.codec = Codec()
        self.ws = None
        self._reader = None
        self._pending: dict[int, tuple[int, asyncio.Future]] = {}
        self._location_requests: set[int] = set()
        self._connect_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._sn = secrets.randbelow(1_000_000_000)
        self.auth_blocked = False
        self._closing = False

    @property
    def connected(self) -> bool:
        return bool(self.sid and self.ws is not None and not self.ws.closed)

    async def connect(self) -> None:
        async with self._connect_lock:
            if self.connected:
                return
            if self.auth_blocked:
                raise AuthenticationError("Reauthentication required")
            await self.close()
            self._closing = False
            self.codec = Codec()
            try:
                async with asyncio.timeout(30):
                    self.ws = await self.session.ws_connect(
                        self.url, heartbeat=45, max_msg_size=4 * 1024 * 1024
                    )
                self._reader = asyncio.create_task(self._read_loop(), name="noise_explorer_reader")
                response = await self.request(
                    10011,
                    login_payload(self.email, self.password, self.client_id, self.timezone),
                    handshake=True,
                )
                if not response.get("SID"):
                    raise ConnectionError("Login response missing session identifier")
                pl = response.get("PL")
                if not isinstance(pl, dict) or not pl.get("EID"):
                    raise ConnectionError("Login response missing account identifier")
                self.sid, self.eid = response["SID"], pl["EID"]
            except BaseException:
                await self.close()
                raise

    async def close(self) -> None:
        self._closing = True
        self.sid = None
        if self.ws is not None:
            await self.ws.close()
        reader, self._reader = self._reader, None
        if reader and reader is not asyncio.current_task():
            reader.cancel()
            with suppress(asyncio.CancelledError):
                await reader
        self._fail_pending(ConnectionError("Connection closed"))

    def _fail_pending(self, error: NoiseError) -> None:
        for _, future in self._pending.values():
            if not future.done():
                future.set_exception(error)

    async def request(
        self,
        cid: int,
        payload=None,
        *,
        handshake=False,
        top: dict | None = None,
        response_timeout: float = 30,
    ) -> dict:
        if self.ws is None or self.ws.closed:
            raise ConnectionError("Cloud connection unavailable")
        self._sn = (self._sn + 1) % 2_147_483_647
        sn = self._sn
        # NetService.sendNetMsg adds this to every app request. Omitting it
        # makes the live server reject even a new login with RC -14.
        message = {"CID": cid, "SN": sn, "Version": "00140000"}
        if self.sid:
            message["SID"] = self.sid
        if payload is not None:
            message["PL"] = payload
        if top:
            message.update(top)
        future = asyncio.get_running_loop().create_future()
        self._pending[sn] = (cid, future)
        if cid == 30011 and isinstance(payload, dict) and payload.get("sub_action") == 100:
            self._location_requests.add(sn)
        try:
            async with asyncio.timeout(response_timeout):
                async with self._write_lock:
                    if handshake:
                        await self.ws.send_str(self.codec.handshake(message))
                    else:
                        await self.ws.send_bytes(self.codec.encrypt(message))
                return await future
        except TimeoutError as err:
            raise ConnectionError(f"Cloud command {cid} timed out; outcome unknown") from err
        except aiohttp.ClientError as err:
            raise ConnectionError("Cloud transport failed") from err
        finally:
            self._pending.pop(sn, None)
            self._location_requests.discard(sn)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Consume an error if sending itself failed.

    async def _read_loop(self) -> None:
        error: NoiseError = ConnectionError("Cloud connection closed")
        try:
            async for frame in self.ws:
                if frame.type not in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                    continue
                message = self.codec.decode(frame.data)
                cid, sn, rc = message.get("CID"), message.get("SN"), message.get("RC")
                if cid == 79002 or rc == -14:
                    self.auth_blocked = True
                    raise AuthenticationError(
                        "Cloud session replaced or invalid; sign in again", rc=rc
                    )
                pending = self._pending.get(sn)
                matched = pending is not None and (
                    cid == pending[0] + 1
                    or (sn in self._location_requests and cid in (50112, 50122))
                )
                if matched:
                    request_cid, future = pending
                    if not future.done():
                        if request_cid == 10011 and rc != 1:
                            if rc in (-200, -201, -202):
                                future.set_exception(
                                    ConnectionError("Login service temporarily unavailable")
                                )
                            elif isinstance(rc, int) and rc < 0:
                                self.auth_blocked = True
                                future.set_exception(
                                    AuthenticationError(f"Login rejected (code {rc})", rc=rc)
                                )
                            else:
                                future.set_exception(ConnectionError("Invalid login response status"))
                        elif isinstance(rc, int) and rc < 0:
                            future.set_exception(CommandError(request_cid, rc))
                        elif (
                            rc != 1
                            and request_cid != 1
                            and not (request_cid == 30011 and rc in (0, None))
                        ):
                            future.set_exception(
                                ConnectionError("Unrecognized cloud response status")
                            )
                        else:
                            future.set_result(message)
                # Correlated responses are handled by their caller. Unsolicited watch
                # messages must never satisfy an unrelated request with the same SN.
                if not matched and self.on_push and (rc is None or rc == 1):
                    self.on_push(message)
        except asyncio.CancelledError:
            raise
        except AuthenticationError as err:
            error = err
        except (aiohttp.ClientError, ValueError, TypeError, KeyError):
            error = ConnectionError("Cloud transport or frame decoding failed")
        finally:
            self.sid = None
            self._fail_pending(error)
            if self.ws is not None:
                await self.ws.close()
            if not self._closing and self.on_disconnect:
                self.on_disconnect(error)

    async def discover(self) -> list[dict]:
        response = await self.request(20091, top={"PARAM": {}})
        groups = response.get("PL")
        if not isinstance(groups, list):
            raise ConnectionError("Invalid watch discovery response")
        watches = {}
        for group in groups:
            if not isinstance(group, dict):
                continue
            for endpoint in group.get("Endpoints", []):
                if (
                    isinstance(endpoint, dict)
                    and str(endpoint.get("Type")) == "200"
                    and endpoint.get("EID")
                ):
                    watches[endpoint["EID"]] = {**endpoint, "GID": group.get("GID")}
        return list(watches.values())

    async def read_settings(self, eid: str, keys: list[str]) -> dict:
        response = await self.request(60051, {"EID": eid, "Keys": keys})
        payload = response.get("PL")
        if not isinstance(payload, dict):
            raise ConnectionError("Invalid settings response")
        return payload

    async def read_offline(self, eid: str):
        response = await self.request(60071, {"EID": eid})
        payload = response.get("PL")
        return payload.get("offline") if isinstance(payload, dict) else None

    async def set_setting(self, eid: str, gid: str, key: str, value: str) -> dict:
        # Do not retry writes: a lost response does not mean the watch rejected it.
        return await self.request(
            60031,
            {
                key: value,
                "TEID": eid,
                "TGID": gid,
                "settype": "true",
                "SMS": f"<{(self._sn + 1) % 2_147_483_647},{self.eid},E501>",
            },
        )

    async def command(self, eid: str, action: int, data: dict | None = None) -> dict:
        payload = {**(data or {}), "sub_action": action}
        if action in (158, 502, 503, 504):
            sn = (self._sn + 1) % 2_147_483_647
            argument = str(payload.get("Key", "1")) if action == 158 else ""
            payload["SMS"] = f"<{sn},{self.eid},E{action},{argument}>"
        return await self.request(
            30011, payload, top={"TEID": [eid]}, response_timeout=120
        )
