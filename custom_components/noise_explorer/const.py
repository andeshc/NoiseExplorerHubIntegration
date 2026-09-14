"""Entity capabilities supported by recovered app call sites."""

DOMAIN = "noise_explorer"
PLATFORMS = ["sensor", "binary_sensor", "device_tracker", "button", "switch", "select", "number"]
DEFAULT_POLL = 300

# Friendly name, values on the wire. Only create optional controls when the
# server actually returns the corresponding setting for this watch.
SWITCHES = {
    "setps_setting": "Step counting",
    "setps_notification": "Step goal notifications",
    "white_list_on": "Allow calls from contacts only",
    "CloudPhotos": "Cloud photos",
    "fcm_onoff": "Anti addiction",
    "report_fault_onoff": "Fault reporting",
    "keep_wifi_connect": "Keep Wi-Fi connected",
    "auto_connect_wifi": "Automatically connect Wi-Fi",
    "fota_wifi_only": "Firmware download over Wi-Fi only",
}
SELECTS = {
    "operation_mode_value": (
        "Operating mode",
        {"Power saving": "4", "Normal": "3", "Performance": "5"},
    ),
    "volume_level": ("Volume", {"Silent": "0", "Low": "2", "Medium": "4", "High": "6"}),
    "led_level": ("Screen brightness", {"Dim": "1", "Medium": "4", "Bright": "10"}),
    "volumevibrate": (
        "Notification mode",
        {"Sound": "1", "Vibrate": "2", "Sound and vibrate": "3"},
    ),
    "auto_answer": ("Auto answer", {"Off": "0", "Immediately": "2", "After delay": "1"}),
}
NUMBERS = {"steps_target_level": ("Daily step goal", 1000, 30000, 1000)}
BUTTONS = {
    "refresh": ("Refresh cloud data", None),
    "locate": ("Request location", 100),
    "find_watch": ("Find watch", 158),
    "request_steps": ("Request step update", 502),
    "request_signal": ("Request signal update", 503),
    "request_version": ("Request firmware version", 504),
}
READ_KEYS = list(
    dict.fromkeys(
        [
            "wlan",
            "battery_level",
            "watch_status",
            "status",
            "signal_level",
            "net_stat",
            "cur_steps",
            "operation_mode_value",
            "device_power_on_time",
            "SilenceList",
            "SleepList",
            "AlarmClockList",
            "silence_list_new",
            "offlinemode",
            "super_power_onoff",
            "sms_filter",
            "sos_sms",
            "loc_onoff",
            *SWITCHES,
            *SELECTS,
            *NUMBERS,
        ]
    )
)
