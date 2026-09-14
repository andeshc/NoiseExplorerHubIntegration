"""One session per account; shared cloud reads plus unsolicited updates."""

import asyncio
import logging
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client.api import AuthenticationError, NoiseError
from .client.model import Watch
from .const import DEFAULT_POLL, DOMAIN, READ_KEYS

_LOGGER = logging.getLogger(__name__)


class NoiseCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=entry.options.get("poll_interval", DEFAULT_POLL)),
        )
        self.client = client
        self.watches: dict[str, Watch] = {}
        self.client.on_push = self._push
        self.client.on_disconnect = self._disconnected
        self._last_location: dict[str, float] = {}
        self._location_tasks: dict[str, asyncio.Task] = {}
        self._action_lock = asyncio.Lock()
        self.location_interval = entry.options.get("location_interval", 0)
        self.entry = entry

    async def _async_update_data(self):
        try:
            await self.client.connect()
            discovered = await self.client.discover()
            current = {info["EID"] for info in discovered}
            for eid in set(self.watches) - current:
                del self.watches[eid]
            for info in discovered:
                eid = info["EID"]
                if eid not in self.watches:
                    self.watches[eid] = Watch(eid, info, zone=ZoneInfo(self.hass.config.time_zone))
                self.watches[eid].info = info
                watch = self.watches[eid]
                try:
                    values = await self.client.read_settings(eid, READ_KEYS)
                    watch.merge_settings(values)
                    watch.settings_ok = True
                    try:
                        watch.settings["_offline"] = await self.client.read_offline(eid)
                    except AuthenticationError:
                        raise
                    except NoiseError:
                        watch.settings["_offline"] = None
                except AuthenticationError:
                    raise
                except NoiseError:
                    watch.settings_ok = False
                if (
                    self.location_interval
                    and eid not in self._location_tasks
                    and time.monotonic() - self._last_location.get(eid, 0) >= self.location_interval
                ):
                    self._last_location[eid] = time.monotonic()
                    self._location_tasks[eid] = self.entry.async_create_background_task(
                        self.hass, self._locate(eid), f"Noise location {eid}"
                    )
            if self.watches and not any(w.settings_ok for w in self.watches.values()):
                raise UpdateFailed("Watch settings could not be read")
            return self.watches
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (NoiseError, aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed("Cannot communicate with Noise Explorer cloud") from err

    async def _locate(self, eid):
        try:
            await self.async_command(eid, 100)
        except HomeAssistantError:
            _LOGGER.debug("Scheduled location request did not complete")
        finally:
            self._location_tasks.pop(eid, None)

    def _disconnected(self, error):
        self.async_set_update_error(UpdateFailed(str(error)))
        if isinstance(error, AuthenticationError):
            # Avoid a reconnect contest with the phone app if the server allows
            # only one session. Resume only through the user's reauth flow.
            self.entry.async_start_reauth(self.hass)

    def _push(self, message):
        pl = message.get("PL", {})
        if not isinstance(pl, dict):
            return
        eid = pl.get("EID") or pl.get("Eid") or message.get("SEID")
        watch = self.watches.get(eid)
        if watch is None:
            return
        event = watch.apply_push(message)
        if event:
            self.hass.bus.async_fire(
                f"{DOMAIN}_watch_event",
                {
                    "watch_id": eid,
                    "config_entry_id": self.entry.entry_id,
                    **watch.last_event,
                },
            )
        # Push traffic must not postpone polling forever or hide another watch's
        # failed refresh. Notify listeners without resetting the polling timer.
        self.async_update_listeners()

    def get_watch(self, eid):
        if eid not in self.watches:
            raise HomeAssistantError("Watch is no longer paired to this account")
        return self.watches[eid]

    async def async_command(self, eid, action, data=None):
        self.get_watch(eid)
        async with self._action_lock:
            try:
                await self.client.connect()
                response = await self.client.command(eid, action, data)
                watch = self.get_watch(eid)
                watch.apply_push(
                    {**response, "PL": {"sub_action": action, **response.get("PL", {})}}
                )
                self.async_update_listeners()
                return response
            except (NoiseError, aiohttp.ClientError, TimeoutError) as err:
                raise HomeAssistantError(
                    str(err) if isinstance(err, NoiseError) else "Noise cloud unavailable"
                ) from err

    async def async_set_setting(self, eid, key, value):
        watch = self.get_watch(eid)
        if not watch.info.get("GID"):
            raise HomeAssistantError("Watch has no family identifier")
        async with self._action_lock:
            try:
                await self.client.connect()
                await self.client.set_setting(eid, watch.info["GID"], key, value)
                # Read back: successful cloud storage does not prove the watch
                # applied the setting. Never optimistically claim device state.
                result = await self.client.read_settings(eid, [key])
                watch.merge_settings(result)
                self.async_update_listeners()
            except (NoiseError, aiohttp.ClientError, TimeoutError) as err:
                raise HomeAssistantError(
                    str(err) if isinstance(err, NoiseError) else "Noise cloud unavailable"
                ) from err
