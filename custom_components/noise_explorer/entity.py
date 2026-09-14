"""Shared identity and dynamic discovery."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class NoiseEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, eid, key, name):
        super().__init__(coordinator, context=eid)
        self.eid, self.key = eid, key
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{eid}_{key}"
        self._attr_name = name

    @property
    def watch(self):
        return self.coordinator.watches.get(self.eid)

    @property
    def available(self):
        return super().available and self.watch is not None and self.watch.settings_ok

    @property
    def device_info(self):
        watch = self.watch
        return DeviceInfo(
            identifiers={(DOMAIN, self.eid)},
            manufacturer="Noise",
            name=watch.name if watch else "Noise Explorer watch",
            model=watch.info.get("deviceType", "Explorer Junior 2") if watch else None,
            sw_version=watch.info.get("VersionCur") if watch else None,
        )


def discover_entities(entry, async_add_entities, factory):
    coordinator = entry.runtime_data
    known = set()

    def discover():
        entities = []
        for eid, watch in coordinator.watches.items():
            for entity in factory(coordinator, eid, watch):
                if entity.unique_id not in known:
                    known.add(entity.unique_id)
                    entities.append(entity)
        if entities:
            async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
