"""Validation shared by services and standalone protocol tests."""

import re

from .model import unpack


def validate_alarms(value):
    """Exact AlarmTime fields; preserve IDs when editing existing alarms."""
    if not isinstance(value, list) or len(value) > 10:
        raise ValueError("alarms must be a list of at most 10 items")
    result, ids = [], set()
    for alarm in value:
        if not isinstance(alarm, dict) or set(alarm) != {
            "hour",
            "min",
            "days",
            "onoff",
            "timeid",
            "bell",
        }:
            raise ValueError("Each alarm requires hour, min, days, onoff, timeid and bell")
        row = {key: str(val) for key, val in alarm.items()}
        if not re.fullmatch(r"\d{1,2}", row["hour"]) or not 0 <= int(row["hour"]) <= 23:
            raise ValueError("Invalid alarm hour")
        if not re.fullmatch(r"\d{1,2}", row["min"]) or not 0 <= int(row["min"]) <= 59:
            raise ValueError("Invalid alarm minute")
        if not re.fullmatch(r"[01](,[01]){7}", row["days"]):
            raise ValueError(
                "days must contain repeat flag followed by Monday through Sunday flags"
            )
        if row["onoff"] not in {"0", "1"} or not re.fullmatch(r"\d{1,3}", row["bell"]):
            raise ValueError("Invalid alarm state or bell")
        if not re.fullmatch(r"\d{17}", row["timeid"]) or row["timeid"] in ids:
            raise ValueError("Alarm IDs must be unique 17-digit timestamps")
        ids.add(row["timeid"])
        row["hour"], row["min"] = row["hour"].zfill(2), row["min"].zfill(2)
        result.append(row)
    return result


def update_alarm_state(value, timeid, enabled):
    alarms = unpack(value)
    if not isinstance(alarms, list):
        raise ValueError("No readable alarm list")
    result = [dict(row) for row in alarms]
    matched = False
    for row in result:
        if row.get("timeid") == timeid:
            row["onoff"] = "1" if enabled else "0"
            matched = True
    if not matched:
        raise ValueError("Alarm ID not found")
    return result
