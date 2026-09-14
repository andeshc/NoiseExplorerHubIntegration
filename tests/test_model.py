from datetime import UTC, datetime, timedelta, timezone

import pytest
from client.model import Watch, flag, numeric, scalar, timestamp
from client.validation import update_alarm_state, validate_alarms


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("20260914123000123_84", 84),
        ("0", 0),
        (None, None),
        ("null", None),
        ("NaN", None),
        ("inf", None),
        ({}, None),
        (True, None),
    ],
)
def test_numeric(value, expected):
    assert numeric(value, 0, 100) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("null", None),
        ("1", True),
        ("0", False),
        ("9", None),
        ("20260914120000000_1", True),
    ],
)
def test_flags(value, expected):
    assert flag(value) is expected


def test_timestamp_uses_app_local_zone():
    zone = timezone(timedelta(hours=5, minutes=30))
    assert timestamp("20260914123000123_84", zone) == datetime(
        2026, 9, 14, 7, 0, 0, 123000, tzinfo=UTC
    )
    assert timestamp("20260914_1234", zone).day == 14
    assert timestamp("20269999123000123") is None
    assert scalar("not_a_timestamp") == "not_a_timestamp"


def fix(stamp="20260914120000000", coords="77.5,12.9", **extra):
    return {
        "timestamp": stamp,
        "result": {"type": "1", "location": coords, "radius": "25", "region": 404, **extra},
    }


def test_location_lon_lat_order_stale_and_zero_fixes():
    watch = Watch("watch1", {})
    watch.merge_location(fix())
    assert watch.location["latitude"] == 12.9
    assert watch.location["longitude"] == 77.5
    assert watch.location["accuracy"] == 25
    original = watch.location.copy()
    watch.merge_location(fix(stamp="20260913120000000", coords="1,2"))
    assert watch.location == original
    for coords in ("0,0", "181,91", "nan,10", "invalid", "", "12,inf"):
        watch.merge_location(fix(coords=coords))
        assert watch.location == original
    watch.merge_location(fix(type="0"))
    assert watch.location == original


def test_china_offset_coordinates_not_claimed_wgs84():
    watch = Watch("watch1", {})
    watch.merge_location(fix(region=460, mapType="1"))
    assert watch.location["wgs84"] is False


def test_push_does_not_invent_missing_data():
    watch = Watch("watch1", {})
    watch.apply_push(
        {"CID": 30012, "PL": {"sub_action": 501, "battery_level": "20260914120000000_0"}}
    )
    assert numeric(watch.settings["battery_level"]) == 0
    assert "cur_steps" not in watch.settings
    watch.apply_push({"CID": 30012, "PL": {"sub_action": 161}})
    assert watch.last_event["kind"] == "sos"


def alarm():
    return {
        "hour": "7",
        "min": "30",
        "days": "1,1,1,1,1,1,0,0",
        "timeid": "20260914120000000",
        "bell": "1",
        "onoff": "1",
    }


def test_alarm_validation_and_update_preserves_unknown_fields():
    row = alarm()
    assert validate_alarms([row])[0]["hour"] == "07"
    row["vendor_extra"] = "preserve me"
    updated = update_alarm_state([row], row["timeid"], False)
    assert updated[0]["onoff"] == "0"
    assert updated[0]["vendor_extra"] == "preserve me"
    assert row["onoff"] == "1"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("hour", "24"),
        ("min", "60"),
        ("days", "Mon"),
        ("timeid", "x"),
        ("bell", "-1"),
        ("onoff", "3"),
    ],
)
def test_bad_alarms_rejected(key, value):
    with pytest.raises(ValueError):
        validate_alarms([{**alarm(), key: value}])


def test_duplicate_alarm_ids_rejected():
    with pytest.raises(ValueError):
        validate_alarms([alarm(), alarm()])
    with pytest.raises(ValueError):
        update_alarm_state([alarm()], "unknown", True)


@pytest.mark.parametrize(
    ("status", "expected"),
    [("4", True), ("5", True), ("0", False), ("3", False), (None, None), ("null", None)],
)
def test_wifi_connected_uses_bit_four(status, expected):
    watch = Watch("watch1", {})
    watch.merge_settings({"wlan": [{"wlan_status": status, "wlan_ssid": "synthetic-network"}]})
    assert watch.wifi_connected is expected


def test_malformed_wifi_is_unknown():
    watch = Watch("watch1", {})
    for value in (None, "null", "garbage", "[]", "{}", [None]):
        watch.merge_settings({"wlan": value})
        assert watch.wifi_connected is None
