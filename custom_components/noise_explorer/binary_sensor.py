"""Boolean flags with unknown preserved."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .client.model import flag, numeric
from .entity import NoiseEntity, discover_entities

PARALLEL_UPDATES = 0
FLAGS = [
    ("watch_online", "Watch online", "connectivity"),
    ("wifi_connected", "Wi-Fi connected", "connectivity"),
    ("status", "Charging", "battery_charging"),
    ("low_battery", "Low battery", "battery"),
    ("loc_onoff", "Location reporting enabled", None),
    ("super_power_onoff", "Super power saving", None),
    ("cloud_connection", "Cloud connection", "connectivity"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    discover_entities(
        entry, async_add_entities, lambda c, e, w: (NoiseBinarySensor(c, e, row) for row in FLAGS)
    )


class NoiseBinarySensor(NoiseEntity, BinarySensorEntity):
    def __init__(self, coordinator, eid, row):
        super().__init__(coordinator, eid, row[0], row[1])
        self._attr_device_class = row[2]

    @property
    def available(self):
        if self.key == "cloud_connection":
            return self.watch is not None
        return super().available

    @property
    def is_on(self):
        if not self.watch:
            return None
        if self.key == "cloud_connection":
            return self.coordinator.client.connected
        if self.key == "watch_online":
            offline = flag(self.watch.settings.get("_offline"))
            return not offline if offline is not None else None
        if self.key == "wifi_connected":
            return self.watch.wifi_connected
        if self.key == "low_battery":
            value = numeric(self.watch.settings.get("battery_level"), 0, 100)
            return value <= 20 if value is not None else None
        return flag(self.watch.settings.get(self.key))
