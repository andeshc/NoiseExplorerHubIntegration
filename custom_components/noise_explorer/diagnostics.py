"""Allowlisted diagnostics: no accounts, coordinates, tokens, or payloads."""

from .const import READ_KEYS


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        "integration_version": "0.1.0",
        "connected": coordinator.client.connected,
        "last_update_success": coordinator.last_update_success,
        "poll_interval": entry.options.get("poll_interval", 300),
        "location_interval": entry.options.get("location_interval", 0),
        "watches": [
            {
                "index": index,
                "settings_ok": watch.settings_ok,
                "reported_keys": sorted(key for key in watch.settings if key in READ_KEYS),
                "has_location": bool(watch.location),
            }
            for index, watch in enumerate(coordinator.watches.values(), 1)
        ],
    }
