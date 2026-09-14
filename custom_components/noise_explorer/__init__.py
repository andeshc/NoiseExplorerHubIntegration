"""Noise Explorer Hub custom integration."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client.api import NoiseClient
from .const import PLATFORMS
from .coordinator import NoiseCoordinator
from .services import async_register_services


async def async_setup(hass, config):
    async_register_services(hass)
    return True


async def async_setup_entry(hass, entry):
    client = NoiseClient(
        async_get_clientsession(hass),
        entry.data["email"],
        entry.data["password"],
        entry.data["client_id"],
        timezone=entry.data.get("timezone", "UTC+05:30"),
    )
    coordinator = NoiseCoordinator(hass, entry, client)
    entry.runtime_data = coordinator
    try:
        await coordinator.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await client.close()
        raise
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    async def stop(event):
        await client.close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop))
    return True


async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.close()
        return True
    return False
