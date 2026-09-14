"""Watch location, with a separately exposed source timestamp."""

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from .entity import NoiseEntity, discover_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    discover_entities(
        entry, async_add_entities, lambda c, e, w: [NoiseTracker(c, e, "location", "Location")]
    )


class NoiseTracker(NoiseEntity, TrackerEntity):
    @property
    def source_type(self):
        return SourceType.GPS

    @property
    def available(self):
        return super().available and bool(self.watch.location.get("wgs84"))

    @property
    def latitude(self):
        return self.watch.location.get("latitude") if self.watch else None

    @property
    def longitude(self):
        return self.watch.location.get("longitude") if self.watch else None

    @property
    def location_accuracy(self):
        value = self.watch.location.get("accuracy") if self.watch else None
        return int(value) if value is not None else 0

    @property
    def extra_state_attributes(self):
        if not self.watch:
            return None
        return {
            k: v
            for k, v in self.watch.location.items()
            if k
            in {
                "timestamp",
                "type",
                "map_type",
                "region",
            }
        }
