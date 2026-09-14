"""UI login, reauthentication, and polling options."""

import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .client.api import AuthenticationError, NoiseClient, NoiseError
from .const import DEFAULT_POLL, DOMAIN


class NoiseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        placeholders = {}
        if user_input is not None:
            offset = int(
                datetime.now(ZoneInfo(self.hass.config.time_zone)).utcoffset().total_seconds() / 60
            )
            timezone = (
                f"UTC{'+' if offset >= 0 else '-'}{abs(offset) // 60:02}:{abs(offset) % 60:02}"
            )
            data = {**user_input, "client_id": secrets.token_hex(8), "timezone": timezone}
            client = NoiseClient(
                async_get_clientsession(self.hass),
                data["email"],
                data["password"],
                data["client_id"],
                timezone=timezone,
            )
            try:
                await client.connect()
                await self.async_set_unique_id(client.eid)
                if self.source == config_entries.SOURCE_REAUTH:
                    entry = self._get_reauth_entry()
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(entry, data_updates=data)
                self._abort_if_unique_id_configured()
                watches = await client.discover()
                if not watches:
                    return self.async_abort(reason="no_watches")
                return self.async_create_entry(title="Noise Explorer", data=data)
            except AuthenticationError as err:
                errors["base"] = {
                    -101: "wrong_password",
                    -103: "unknown_email",
                    -123: "login_throttled",
                    -127: "account_locked",
                    -14: "invalid_session",
                    -400: "server_redirect",
                }.get(err.rc, "invalid_auth")
                placeholders["error_code"] = str(err.rc) if err.rc is not None else "unknown"
            except (NoiseError, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            finally:
                await client.close()
        schema = vol.Schema(
            {
                vol.Required("email"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.EMAIL)
                ),
                vol.Required("password"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NoiseOptionsFlow()


class NoiseOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "poll_interval",
                        default=self.config_entry.options.get("poll_interval", DEFAULT_POLL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                    vol.Required(
                        "location_interval",
                        default=self.config_entry.options.get("location_interval", 0),
                    ): vol.Any(0, vol.All(vol.Coerce(int), vol.Range(min=300, max=86400))),
                }
            ),
        )
