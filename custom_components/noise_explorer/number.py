"""Daily step goal."""

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory

from .client.model import numeric
from .const import NUMBERS
from .entity import NoiseEntity, discover_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    discover_entities(
        entry,
        async_add_entities,
        lambda c, e, w: (
            NoiseNumber(c, e, key, row)
            for key, row in NUMBERS.items()
            if numeric(w.settings.get(key), 0) is not None
        ),
    )


class NoiseNumber(NoiseEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = "steps"

    def __init__(self, coordinator, eid, key, row):
        super().__init__(coordinator, eid, key, row[0])
        self._attr_native_min_value, self._attr_native_max_value, self._attr_native_step = row[1:]

    @property
    def native_value(self):
        return numeric(self.watch.settings.get(self.key), 0) if self.watch else None

    async def async_set_native_value(self, value):
        await self.coordinator.async_set_setting(self.eid, self.key, str(int(value)))
