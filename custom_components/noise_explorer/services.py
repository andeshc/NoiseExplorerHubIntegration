"""Device-targeted, validated Home Assistant actions."""

import json

import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .client.api import NoiseError
from .client.model import unpack
from .client.validation import update_alarm_state, validate_alarms
from .const import BUTTONS, DOMAIN, NUMBERS, READ_KEYS, SELECTS, SWITCHES


def validate_setting(key, value):
    value = str(value)
    if key in SWITCHES and value in {"0", "1"}:
        return value
    if key in SELECTS and value in SELECTS[key][1].values():
        return value
    if key in NUMBERS:
        _, low, high, step = NUMBERS[key]
        if value.isdigit() and low <= int(value) <= high and (int(value) - low) % step == 0:
            return value
    raise ServiceValidationError("Unsupported setting or value; see the integration README")


def async_register_services(hass):
    def resolve(device_id):
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise ServiceValidationError("Unknown device")
        eids = {identifier for domain, identifier in device.identifiers if domain == DOMAIN}
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id in device.config_entries and hasattr(entry, "runtime_data"):
                coordinator = entry.runtime_data
                if coordinator:
                    for eid in eids:
                        if eid in coordinator.watches:
                            return coordinator, eid
        raise ServiceValidationError("Noise watch is not loaded or no longer paired")

    async def handle(call):
        coordinator, eid = resolve(call.data["device_id"])
        action = call.service
        if action in BUTTONS:
            code = BUTTONS[action][1]
            if code is None:
                await coordinator.async_request_refresh()
            else:
                await coordinator.async_command(eid, code, {"Key": "1"} if code == 158 else None)
        elif action == "set_setting":
            key = call.data["key"]
            value = validate_setting(key, call.data["value"])
            if key not in coordinator.get_watch(eid).settings:
                raise ServiceValidationError("This watch has not reported support for that setting")
            await coordinator.async_set_setting(eid, key, value)
        elif action == "get_settings":
            try:
                await coordinator.client.connect()
                settings = await coordinator.client.read_settings(eid, READ_KEYS)
            except NoiseError as err:
                raise HomeAssistantError(str(err)) from err
            return {
                "settings": {
                    key: unpack(value) for key, value in settings.items() if key in READ_KEYS
                }
            }
        elif action == "set_alarms":
            try:
                alarms = validate_alarms(call.data["alarms"])
            except ValueError as err:
                raise ServiceValidationError(str(err)) from err
            await coordinator.async_set_setting(
                eid, "AlarmClockList", json.dumps(alarms, separators=(",", ":"))
            )
        elif action == "set_alarm_enabled":
            # Hold the same lock across read-modify-write to avoid lost changes
            # between simultaneous automations inside this integration.
            async with coordinator._action_lock:
                try:
                    await coordinator.client.connect()
                    settings = await coordinator.client.read_settings(eid, ["AlarmClockList"])
                    alarms = update_alarm_state(
                        settings.get("AlarmClockList"), call.data["alarm_id"], call.data["enabled"]
                    )
                    watch = coordinator.get_watch(eid)
                    await coordinator.client.set_setting(
                        eid,
                        watch.info["GID"],
                        "AlarmClockList",
                        json.dumps(alarms, separators=(",", ":")),
                    )
                    result = await coordinator.client.read_settings(eid, ["AlarmClockList"])
                    watch.merge_settings(result)
                    coordinator.async_update_listeners()
                except ValueError as err:
                    raise ServiceValidationError(str(err)) from err
                except NoiseError as err:
                    raise HomeAssistantError(str(err)) from err

    base = {vol.Required("device_id"): str}
    for name in BUTTONS:
        hass.services.async_register(DOMAIN, name, handle, schema=vol.Schema(base))
    hass.services.async_register(
        DOMAIN,
        "set_setting",
        handle,
        schema=vol.Schema(
            {
                **base,
                vol.Required("key"): vol.In([*SWITCHES, *SELECTS, *NUMBERS]),
                vol.Required("value"): vol.Coerce(str),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "get_settings",
        handle,
        schema=vol.Schema(base),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "set_alarms", handle, schema=vol.Schema({**base, vol.Required("alarms"): list})
    )
    hass.services.async_register(
        DOMAIN,
        "set_alarm_enabled",
        handle,
        schema=vol.Schema(
            {
                **base,
                vol.Required("alarm_id"): str,
                vol.Required("enabled"): bool,
            }
        ),
    )
