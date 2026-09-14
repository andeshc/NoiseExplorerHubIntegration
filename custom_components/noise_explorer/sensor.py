"""Watch telemetry, source timestamps, and configuration summaries."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from .client.model import numeric, scalar, timestamp, unpack
from .entity import NoiseEntity, discover_entities

PARALLEL_UPDATES = 0
# key, name, unit, device class, state class
SENSORS = [
    ("wifi_ssid", "Wi-Fi network", None, None, None),
    ("battery_level", "Battery", "%", "battery", "measurement"),
    ("cur_steps", "Reported steps", "steps", None, None),
    ("signal_level", "Cellular signal raw", None, None, "measurement"),
    ("watch_status", "Watch status code", None, None, None),
    ("net_stat", "Network status", None, None, None),
    ("operation_mode_value", "Operating mode code", None, None, None),
    ("sms_filter", "SMS filter mode code", None, None, None),
    ("device_power_on_time", "Power on timestamp raw", None, None, None),
    ("VersionCur", "Firmware", None, None, None),
    ("battery_updated", "Battery report time", None, "timestamp", None),
    ("steps_updated", "Step report time", None, "timestamp", None),
    ("last_sync", "Last cloud sync", None, "timestamp", None),
    ("location_time", "Location report time", None, "timestamp", None),
    ("location_accuracy", "Location accuracy", "m", "distance", "measurement"),
    ("location_type", "Location source code", None, None, None),
    ("last_event", "Last watch event", None, None, None),
    ("AlarmClockList", "Alarm count", None, None, None),
    ("SilenceList", "Quiet schedule count", None, None, None),
    ("SleepList", "Sleep schedule count", None, None, None),
    ("silence_list_new", "Focus schedule configuration", None, None, None),
    ("offlinemode", "Offline mode configuration", None, None, None),
]


async def async_setup_entry(hass, entry, async_add_entities):
    discover_entities(
        entry, async_add_entities, lambda c, e, w: (NoiseSensor(c, e, row) for row in SENSORS)
    )


class NoiseSensor(NoiseEntity, SensorEntity):
    def __init__(self, coordinator, eid, row):
        key, name, unit, device_class, state_class = row
        super().__init__(coordinator, eid, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        if key in {
            "watch_status",
            "net_stat",
            "operation_mode_value",
            "sms_filter",
            "device_power_on_time",
            "VersionCur",
            "last_sync",
            "silence_list_new",
            "offlinemode",
        }:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        if not self.watch:
            return None
        watch, key = self.watch, self.key
        value = watch.settings.get(key)
        if key == "wifi_ssid":
            return watch.wifi.get("wlan_ssid") if watch.wifi_connected else None
        if key == "battery_level":
            return numeric(value, 0, 100)
        if key in {"cur_steps", "signal_level"}:
            return numeric(value, 0)
        if key in {"battery_updated", "steps_updated"}:
            return timestamp(
                watch.settings.get("battery_level" if key == "battery_updated" else "cur_steps"),
                watch.zone,
            )
        if key == "last_sync":
            return watch.last_sync
        if key == "VersionCur":
            return watch.info.get(key)
        if key == "location_time":
            return watch.location.get("timestamp")
        if key == "location_accuracy":
            return watch.location.get("accuracy")
        if key == "location_type":
            return watch.location.get("type")
        if key == "last_event":
            return watch.last_event.get("kind")
        if key in {"AlarmClockList", "SilenceList", "SleepList"}:
            parsed = unpack(value)
            return len(parsed) if isinstance(parsed, list) else None
        if key in {"silence_list_new", "offlinemode"}:
            return "Configured" if isinstance(unpack(value), (list, dict)) else None
        value = scalar(value)
        return (
            str(value)[:255] if value is not None and not isinstance(value, (list, dict)) else None
        )

    @property
    def extra_state_attributes(self):
        if self.key == "last_event" and self.watch:
            return self.watch.last_event or None
        # Do not add contact, schedule, location or account payloads to recorder.
        return None
