"""Recovered boolean settings."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory

from .client.model import flag
from .const import SWITCHES
from .entity import NoiseEntity, discover_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    discover_entities(
        entry,
        async_add_entities,
        lambda c, e, w: (
            NoiseSwitch(c, e, key, name)
            for key, name in SWITCHES.items()
            if flag(w.settings.get(key)) is not None
        ),
    )


class NoiseSwitch(NoiseEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self):
        return super().available and self.is_on is not None

    @property
    def is_on(self):
        return flag(self.watch.settings.get(self.key)) if self.watch else None

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_setting(self.eid, self.key, "1")

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_setting(self.eid, self.key, "0")
