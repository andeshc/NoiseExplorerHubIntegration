"""Defensive parsing of observed watch fields. Missing data stays unknown."""

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, tzinfo


def unpack(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            pass
    return value


def scalar(value):
    if isinstance(value, str) and "_" in value:
        prefix, suffix = value.split("_", 1)
        if prefix.isdigit() and len(prefix) in (8, 14, 17):
            return suffix
    return value


def numeric(value, minimum=None, maximum=None):
    try:
        if isinstance(value, bool):
            return None
        number = float(scalar(value))
        if (
            not math.isfinite(number)
            or (minimum is not None and number < minimum)
            or (maximum is not None and number > maximum)
        ):
            return None
        return int(number) if number.is_integer() else number
    except (ValueError, TypeError):
        return None


def flag(value):
    value = scalar(value)
    if value in (1, "1", True):
        return True
    if value in (0, "0", False):
        return False
    return None


def timestamp(value, zone=UTC):
    """App TimeUtil.getMillisByTime uses local time, with no offset on the wire."""
    if not isinstance(value, str):
        return None
    value = value.split("_", 1)[0]
    for length, fmt in (
        (17, "%Y%m%d%H%M%S%f"),
        (14, "%Y%m%d%H%M%S"),
        (12, "%Y%m%d%H%M"),
        (8, "%Y%m%d"),
    ):
        if len(value) == length:
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=zone)
            except ValueError:
                return None
    return None


@dataclass
class Watch:
    eid: str
    info: dict
    settings: dict = field(default_factory=dict)
    location: dict = field(default_factory=dict)
    last_event: dict = field(default_factory=dict)
    last_sync: datetime | None = None
    settings_ok: bool = False
    zone: tzinfo = UTC

    @property
    def name(self):
        return self.info.get("NickName") or "Noise Explorer watch"

    def merge_settings(self, values: dict):
        self.settings.update({key: value for key, value in values.items() if key != "EID"})
        self.last_sync = datetime.now(UTC)

    @property
    def wifi(self):
        rows = unpack(self.settings.get("wlan"))
        return rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}

    @property
    def wifi_connected(self):
        status = numeric(self.wifi.get("wlan_status"), 0)
        return bool(int(status) & 4) if status is not None else None

    def merge_location(self, payload: dict):
        # LocationData.parseLocation takes the PL's result object; Location is used
        # by SOS and geofence envelopes. Coordinates are longitude,latitude.
        outer = payload.get("Location", payload)
        outer = unpack(outer)
        if not isinstance(outer, dict):
            return
        result = unpack(outer.get("result", outer))
        if not isinstance(result, dict) or str(result.get("type", "0")) == "0":
            return
        coords = result.get("location")
        if not isinstance(coords, str):
            return
        parts = coords.split(",")
        if len(parts) < 2:
            return
        lon, lat = numeric(parts[0], -180, 180), numeric(parts[1], -90, 90)
        if lon is None or lat is None or (lon == 0 and lat == 0):
            return
        stamp = timestamp(outer.get("timestamp", payload.get("timestamp")), self.zone)
        previous = self.location.get("timestamp")
        if previous and stamp and stamp < previous:
            return
        # Indian fixes are WGS84. Do not silently put Chinese offset coordinates
        # on the HA map; expose their source metadata until conversion is added.
        region = str(result.get("region", "404"))
        map_type = str(result.get("mapType", "0"))
        wgs84 = region not in {"460", "461", "454", "455"} or map_type == "0"
        self.location = {
            "latitude": lat,
            "longitude": lon,
            "accuracy": numeric(result.get("radius"), 0),
            "timestamp": stamp,
            "type": str(result.get("type")),
            "description": result.get("desc"),
            "city": result.get("city"),
            "map_type": map_type,
            "region": region,
            "wgs84": wgs84,
        }

    def apply_push(self, message: dict) -> bool:
        payload = message.get("PL", {})
        if not isinstance(payload, dict):
            return False
        cid, action = message.get("CID"), payload.get("sub_action")
        if action == 504 and isinstance(payload.get("watch_version"), str):
            self.info["VersionCur"] = payload["watch_version"]
        if cid in (50112, 50122) or action == 100:
            self.merge_location(payload)
        if action == 501:
            self.merge_settings(payload)
        # Only field names observed in the app are consumed; no inferred values.
        if action in (160, 165, 166, 400, 502, 503, 504):
            self.merge_settings(
                {
                    k: v
                    for k, v in payload.items()
                    if k
                    in {
                        "battery_level",
                        "cur_steps",
                        "signal_level",
                        "net_stat",
                        "status",
                        "watch_status",
                    }
                }
            )
        kind = {
            161: "sos",
            162: "city_change",
            163: "safe_area",
            164: "guard",
            165: "battery",
            168: "danger_area",
        }.get(action)
        if cid in (50112, 50122) and str(payload.get("SOS")) == "1":
            kind = "sos"
        if kind:
            self.last_event = {"kind": kind, "received_at": datetime.now(UTC).isoformat()}
        return kind is not None
