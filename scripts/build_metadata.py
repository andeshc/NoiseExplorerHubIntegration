"""Rebuild UI translations and action descriptions from the capability catalog."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "noise_explorer"
sys.path.insert(0, str(COMPONENT))
from const import BUTTONS, DOMAIN, NUMBERS, SELECTS, SWITCHES  # noqa: E402

strings = {
    "title": "Noise Explorer",
    "config": {
        "step": {
            "user": {
                "title": "Connect Noise Explorer Hub",
                "description": "Sign in with the email and password used in Noise Explorer Hub. Pair the watch in the app first. This uses Noise's cloud service. The service may replace an existing app session.",
                "data": {"email": "Email", "password": "Password"},
            }
        },
        "error": {
            "invalid_auth": "Sign-in was rejected. Check your credentials and account status.",
            "cannot_connect": "Cannot connect to Noise cloud. Check connectivity and try again.",
        },
        "abort": {
            "already_configured": "This Noise account is already configured.",
            "no_watches": "No paired watches found. Pair your watch in Noise Explorer Hub first.",
            "reauth_successful": "Sign-in updated successfully.",
            "wrong_account": "Sign in with the same Noise account as this integration.",
        },
    },
    "options": {
        "step": {
            "init": {
                "title": "Noise Explorer updates",
                "description": "Cloud reads do not force a GPS fix. Automatic location requests wake the watch and use battery. Use 0 to disable them, or at least 300 seconds. The Request location button works at any time.",
                "data": {
                    "poll_interval": "Cloud refresh interval (seconds)",
                    "location_interval": "Automatic location request interval (seconds, 0 disables)",
                },
            }
        }
    },
}
for file in (COMPONENT / "strings.json", COMPONENT / "translations" / "en.json"):
    file.parent.mkdir(exist_ok=True)
    file.write_text(json.dumps(strings, indent=2) + "\n", encoding="utf-8")

device = {"name": "Watch", "required": True, "selector": {"device": {"integration": DOMAIN}}}
services = {}
for key, (name, action) in BUTTONS.items():
    services[key] = {
        "name": name,
        "description": (
            "Refresh cached cloud values for the account."
            if action is None
            else "Send this command to the selected watch. A cloud acknowledgement does not guarantee physical execution; the watch may be offline."
        ),
        "fields": {"device_id": device},
    }
services["set_setting"] = {
    "name": "Set watch setting",
    "description": "Set a supported setting using its documented wire value; see README. Prefer switch/select/number entities for normal use.",
    "fields": {
        "device_id": device,
        "key": {
            "name": "Setting",
            "required": True,
            "selector": {"select": {"options": [*SWITCHES, *SELECTS, *NUMBERS]}},
        },
        "value": {"name": "Value", "required": True, "selector": {"text": {}}},
    },
}
services["get_settings"] = {
    "name": "Read watch settings",
    "description": "Return supported settings, including alarm IDs and schedules. This response may contain personal schedule information.",
    "fields": {"device_id": device},
}
services["set_alarms"] = {
    "name": "Replace watch alarms",
    "description": "Replace the complete alarm list, up to 10 alarms. An empty list deletes all alarms. Read the existing list first and preserve IDs when editing.",
    "fields": {
        "device_id": device,
        "alarms": {"name": "Alarm list", "required": True, "selector": {"object": {}}},
    },
}
services["set_alarm_enabled"] = {
    "name": "Enable or disable an alarm",
    "description": "Change one existing alarm, preserving the others. Obtain its ID using Read watch settings.",
    "fields": {
        "device_id": device,
        "alarm_id": {"name": "Alarm ID", "required": True, "selector": {"text": {}}},
        "enabled": {"name": "Enabled", "required": True, "selector": {"boolean": {}}},
    },
}
# JSON is a YAML subset; this keeps the builder free of third-party dependencies.
(COMPONENT / "services.yaml").write_text(json.dumps(services, indent=2) + "\n", encoding="utf-8")
print(f"Wrote English UI metadata and {len(services)} action descriptions")
