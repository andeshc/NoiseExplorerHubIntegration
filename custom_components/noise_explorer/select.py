"""Discrete values copied from app UI call sites."""

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory

from .const import SELECTS
from .entity import NoiseEntity, discover_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    discover_entities(
        entry,
        async_add_entities,
        lambda c, e, w: (
            NoiseSelect(c, e, key, name, options)
            for key, (name, options) in SELECTS.items()
            if str(w.settings.get(key)) in options.values()
        ),
    )


class NoiseSelect(NoiseEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, eid, key, name, options):
        super().__init__(coordinator, eid, key, name)
        self.values = options
        self._attr_options = list(options)

    @property
    def current_option(self):
        value = str(self.watch.settings.get(self.key)) if self.watch else None
        return next((name for name, wire in self.values.items() if wire == value), None)

    @property
    def available(self):
        return super().available and self.current_option is not None

    async def async_select_option(self, option):
        await self.coordinator.async_set_setting(self.eid, self.key, self.values[option])
