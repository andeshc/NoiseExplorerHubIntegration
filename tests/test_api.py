"""Exercise the real aiohttp WebSocket client against a local simulated server.

The session adapter changes only the URL to localhost; production validation
continues to require TLS. Test payloads are synthetic, never user captures.
"""

import asyncio
import json

import aiohttp
import pytest
from aiohttp import web
from client.api import AuthenticationError, CommandError, ConnectionError, NoiseClient


class Server:
    def __init__(self):
        self.messages = []
        self.login_rc = 1
        self.reply_rc = 1
        self.drop_cid = None
        self.ws = None
        self.codec = None

    async def handle(self, request):
        self.ws = web.WebSocketResponse()
        await self.ws.prepare(request)
        async for frame in self.ws:
            if frame.type == aiohttp.WSMsgType.TEXT:
                packet = json.loads(frame.data)
                message = self.codec.decode(packet["PT2"])
            else:
                message = self.codec.decode(frame.data)
            self.messages.append(message)
            cid = message["CID"]
            if self.drop_cid == cid:
                continue
            response = {"CID": cid + 1, "SN": message["SN"], "RC": self.reply_rc, "PL": {}}
            if cid == 10011:
                response.update(RC=self.login_rc, SID="synthetic-session", PL={"EID": "account1"})
                if message.get("Version") != "00140000":
                    response.update(RC=-14)
            elif cid == 20091:
                response["PL"] = [
                    {
                        "GID": "group1",
                        "Endpoints": [
                            {"Type": 100, "EID": "parent"},
                            {"Type": 200, "EID": "watch1", "NickName": "Test Watch"},
                        ],
                    }
                ]
            elif cid == 60051:
                response["PL"] = {
                    "battery_level": "20260914120000000_84",
                    "cur_steps": "20260914_1234",
                }
            elif cid == 60071:
                response["PL"] = {"offline": 1}
            await self.ws.send_bytes(self.codec.encrypt(response))
        return self.ws


@pytest.fixture
async def connection():
    server = Server()
    app = web.Application()
    app.router.add_get("/svc/pipe", server.handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    async with aiohttp.ClientSession() as session:

        class LocalSession:
            async def ws_connect(self, url, **kwargs):
                server.codec = client.codec
                return await session.ws_connect(f"http://127.0.0.1:{port}/svc/pipe", **kwargs)

        client = NoiseClient(LocalSession(), "parent@example.test", "test-password", "client01")
        yield client, server
        await client.close()
    await runner.cleanup()


async def test_full_login_discovery_poll_and_write(connection):
    client, server = connection
    await client.connect()
    assert client.connected and client.eid == "account1"
    watches = await client.discover()
    assert [w["EID"] for w in watches] == ["watch1"]
    assert watches[0]["GID"] == "group1"
    settings = await client.read_settings("watch1", ["battery_level"])
    assert settings["battery_level"].endswith("_84")
    assert await client.read_offline("watch1") == 1
    await client.set_setting("watch1", "group1", "volume_level", "2")
    sent = server.messages[-1]
    assert sent["PL"]["TEID"] == "watch1"
    assert sent["PL"]["SMS"] == f"<{sent['SN']},account1,E501>"
    assert sent["SID"] == "synthetic-session"
    await client.command("watch1", 158, {"Key": "1"})
    assert server.messages[-1]["TEID"] == ["watch1"]
    sent = server.messages[-1]
    assert sent["PL"] == {
        "sub_action": 158, "Key": "1", "SMS": f"<{sent['SN']},account1,E158,1>"
    }
    assert all(message["Version"] == "00140000" for message in server.messages)


async def test_rejected_login_does_not_reconnect_loop(connection):
    client, server = connection
    server.login_rc = -127
    with pytest.raises(AuthenticationError) as caught:
        await client.connect()
    assert caught.value.rc == -127
    assert not client.connected
    with pytest.raises(AuthenticationError):
        await client.connect()
    assert len(server.messages) == 1


async def test_transient_login_can_retry(connection):
    client, server = connection
    server.login_rc = -201
    with pytest.raises(ConnectionError):
        await client.connect()
    server.login_rc = 1
    await client.connect()
    assert client.connected


@pytest.mark.parametrize("rc", [-101, -103, -123, -127, -400, -14])
async def test_login_error_preserves_safe_server_code(connection, rc):
    client, server = connection
    server.login_rc = rc
    with pytest.raises(AuthenticationError) as caught:
        await client.connect()
    assert caught.value.rc == rc
    assert not client.connected


@pytest.mark.parametrize("action", [502, 503, 504])
async def test_telemetry_request_includes_app_sms_envelope(connection, action):
    client, server = connection
    await client.connect()
    await client.command("watch1", action)
    sent = server.messages[-1]
    assert sent["PL"] == {
        "sub_action": action, "SMS": f"<{sent['SN']},account1,E{action},>"
    }


@pytest.mark.parametrize("rc", [None, "unexpected", 0])
async def test_malformed_login_does_not_blame_credentials(connection, rc):
    client, server = connection
    server.login_rc = rc
    with pytest.raises(ConnectionError):
        await client.connect()
    assert not client.auth_blocked


async def test_timeout_cleanup_and_no_write_retry(connection):
    client, server = connection
    await client.connect()
    server.drop_cid = 60031
    with pytest.raises(ConnectionError, match="outcome unknown"):
        await client.request(60031, {"volume_level": "2"}, response_timeout=0.02)
    assert not client._pending
    assert sum(m["CID"] == 60031 for m in server.messages) == 1


async def test_negative_response_is_not_success(connection):
    client, server = connection
    await client.connect()
    server.reply_rc = -160
    with pytest.raises(CommandError) as caught:
        await client.command("watch1", 158)
    assert caught.value.rc == -160


async def test_unsolicited_push_cannot_satisfy_wrong_cid(connection):
    client, server = connection
    pushes = []
    client.on_push = pushes.append
    await client.connect()
    server.drop_cid = 60051
    request = asyncio.create_task(client.read_settings("watch1", ["battery_level"]))
    for _ in range(100):
        if server.messages[-1]["CID"] == 60051:
            break
        await asyncio.sleep(0)
    sn = server.messages[-1]["SN"]
    await server.ws.send_bytes(
        client.codec.encrypt({"CID": 50112, "SN": sn, "RC": 1, "PL": {"EID": "watch1"}})
    )
    await asyncio.sleep(0.01)
    assert not request.done()
    assert pushes[0]["CID"] == 50112
    await server.ws.send_bytes(
        client.codec.encrypt({"CID": 60052, "SN": sn, "RC": 1, "PL": {"battery_level": "0"}})
    )
    assert (await request)["battery_level"] == "0"


@pytest.mark.parametrize("cid", [50112, 50122])
async def test_location_notification_completes_matching_request(connection, cid):
    client, server = connection
    await client.connect()
    server.drop_cid = 30011
    request = asyncio.create_task(client.command("watch1", 100))
    for _ in range(100):
        if server.messages[-1]["CID"] == 30011:
            break
        await asyncio.sleep(0)
    sn = server.messages[-1]["SN"]
    await server.ws.send_bytes(client.codec.encrypt({
        "CID": cid, "SN": sn, "RC": 1,
        "PL": {"EID": "watch1", "result": {"type": "1", "location": "72,19"}},
    }))
    assert (await asyncio.wait_for(request, 1))["CID"] == cid
    assert not client._location_requests


async def test_session_kick_fails_pending_and_blocks_reconnect(connection):
    client, server = connection
    disconnected = asyncio.Event()
    client.on_disconnect = lambda error: disconnected.set()
    await client.connect()
    await server.ws.send_bytes(client.codec.encrypt({"CID": 79002, "RC": 1}))
    await asyncio.wait_for(disconnected.wait(), 1)
    assert not client.connected and client.auth_blocked
    with pytest.raises(AuthenticationError):
        await client.connect()


async def test_reconnect_generates_new_key_and_sid(connection):
    client, server = connection
    await client.connect()
    key = client.codec.key
    await client.close()
    await client.connect()
    assert client.connected and client.codec.key != key


def test_tls_is_required():
    with pytest.raises(ValueError):
        NoiseClient(None, "test", "test", "client", url="ws://example.test")
