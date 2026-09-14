# Noise Explorer for Home Assistant

An **experimental custom integration for the Noise Explorer Junior 2**, reverse engineered from the supplied Noise Explorer Hub Android app. It signs in with your existing **email/password** and discovers watches already paired to that account.

**Status:** live email/password login, paired-watch discovery, cached settings and online-status reads passed on 2026-09-14. The live data instantiated 44 entities using real Home Assistant 2026.2.3 classes. Fresh location and firmware requests also passed, and the owner confirmed Find watch rang. Setting changes and other commands still need verification. The app contains code for multiple watch models; returned settings and firmware determine which features work on your Junior 2.

## Install

If you cloned this repository, run `python scripts/package_release.py` first to generate the installable ZIP. This packaging step needs only Python's standard library. Alternatively, copy the integration folder directly as described in step 2.

1. Extract `dist/noise_explorer-0.1.1.zip`.
2. Copy `custom_components/noise_explorer` into your Home Assistant configuration directory, so it contains `/config/custom_components/noise_explorer/manifest.json`.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Noise Explorer**.
5. Enter the same email and password as Noise Explorer Hub. Do not paste credentials into a chat or issue report.
6. Open the discovered watch device. Press **Request location** to obtain a fresh position.

Tested with Home Assistant 2026.2.3. Other versions have not been verified. This is a manually installed integration, not a HACS-listed repository. The ZIP includes all integration files; it does not include the original APK, decompiled app, or analysis tools.

To update an existing installation, replace `custom_components/noise_explorer` with the folder from the new ZIP and restart Home Assistant. Version 0.1.1 fixes the missing protocol-version field that caused valid credentials to be rejected in 0.1.0.

## Entities

Up to **51 entities per watch**: 22 sensors, 7 binary sensors, one tracker, six buttons, nine switches, five selects, and one number. Optional controls are created only when the watch's cloud settings return a recognized value. Unsupported/missing readings remain unknown; no values are fabricated.

| Type | Exposed features |
|---|---|
| Device tracker | Watch coordinates, accuracy, original location time and source metadata |
| Telemetry sensors | Battery %, reported steps, raw cellular signal, Wi-Fi network, watch status code, network status, firmware |
| Time sensors | Battery report time, step report date/time, location report time, last successful cloud read |
| Location/event sensors | Location accuracy, source code, last received watch event |
| Configuration summaries | Alarm count, quiet schedule count, sleep schedule count, focus/offline configuration presence, operating mode code, SMS filter code, raw power-on timestamp |
| Binary sensors | Watch online, Wi-Fi connected, cloud connection, charging, low battery, location reporting enabled, super power saving |
| Buttons | Refresh cloud data, request location, find/ring watch, request steps, request signal, request firmware version |
| Switches | Step counting, step-goal notifications, contacts-only calls, cloud photos, anti-addiction, fault reporting, keep Wi-Fi connected, automatic Wi-Fi connection, firmware downloads over Wi-Fi only |
| Selects | Volume, screen brightness, sound/vibration mode, automatic call answering, operating mode |
| Number | Daily step goal, 1,000–30,000 in increments of 1,000 |

Some raw configuration sensors are disabled by default; enable them on the watch's entity page. A raw code is deliberately left as a code when its interpretation is model-dependent. Signal is a vendor level, **not dBm**. Low battery is derived from the returned battery percentage using a 20% threshold. Cloud connection and watch online are separate: the cloud can be reachable while the watch is offline.

Steps are the **last reported count**, with a separate report date/time. They are not marked as a lifetime total or used for HA long-term total statistics. Old reports are not reset to a fabricated zero at midnight. Alarm and schedule sensors report counts rather than recording the full personal schedules.

## Updates and location

The integration maintains one encrypted WebSocket session per account and consumes push updates. It also reads cached cloud settings every **300 seconds** by default. **Configure** offers a cloud interval of 60–3,600 seconds.

Automatic GPS requests are **off by default**. Set the automatic location interval to at least 300 seconds to enable them; 900 seconds is a reasonable starting point. These requests run on the next cloud refresh after their interval elapses. They wake the watch and can affect battery life. The Request location button works independently.

Location remains unavailable until a valid fix arrives; it is not restored from disk after restarting HA. Previously received fixes remain visible while connected, even if old: inspect **Location report time** before using a position in an automation. The app parses offset-free timestamps in the phone's local time; this integration uses HA's configured time zone. Set it to the same zone as your watch/app. This assumption still needs live verification.

Indian location fixes are treated as WGS84, matching the app. Offset coordinates identified as Chinese GCJ/BD map formats are withheld from the HA tracker; conversion is not implemented. These limitations matter if the watch is used outside India.

## Actions

All actions use an explicit **Watch** device selector (`device_id`), preventing ambiguous cross-account targeting.

| Action | Purpose |
|---|---|
| `noise_explorer.refresh` | Refresh cached cloud values for the account |
| `noise_explorer.locate` | Request a new position |
| `noise_explorer.find_watch` | Ring the watch |
| `noise_explorer.request_steps` | Ask the watch to update steps |
| `noise_explorer.request_signal` | Ask the watch to update cellular signal |
| `noise_explorer.request_version` | Request a firmware-version update |
| `noise_explorer.get_settings` | Return allowlisted settings, including alarm IDs and schedules |
| `noise_explorer.set_setting` | Write a validated setting from the table below |
| `noise_explorer.set_alarms` | Replace the entire alarm list; an empty list removes all alarms |
| `noise_explorer.set_alarm_enabled` | Enable/disable one alarm while preserving the rest |

Prefer the switch, select, and number entities for normal automations. Example:

```yaml
action: noise_explorer.find_watch
data:
  device_id: YOUR_HOME_ASSISTANT_WATCH_DEVICE_ID
```

Read settings with a response variable:

```yaml
action: noise_explorer.get_settings
data:
  device_id: YOUR_HOME_ASSISTANT_WATCH_DEVICE_ID
response_variable: watch_settings
```

`get_settings` returns `settings`, including a decoded `AlarmClockList`. Its response may contain personal schedules and Wi-Fi details; diagnostics intentionally do not include these values.

### Validated setting values

| Setting key | Accepted wire values |
|---|---|
| `volume_level` | `0` silent, `2` low, `4` medium, `6` high |
| `led_level` | `1` dim, `4` medium, `10` bright |
| `volumevibrate` | `1` sound, `2` vibration, `3` both |
| `auto_answer` | `0` off, `2` immediate, `1` delayed; delay depends on firmware |
| `operation_mode_value` | `4` power saving, `3` normal, `5` performance |
| `steps_target_level` | `1000` through `30000`, multiples of `1000` |
| `setps_setting`, `setps_notification` | `0` off / `1` on; misspellings are the actual protocol |
| `white_list_on`, `CloudPhotos`, `fcm_onoff`, `report_fault_onoff` | `0` off / `1` on |
| `keep_wifi_connect`, `auto_connect_wifi`, `fota_wifi_only` | `0` off / `1` on |

The step-goal range is an integration-side conservative limit. Settings are read back after writing. Readback proves cloud storage, not that an offline watch has applied the change. Timed-out writes are not retried automatically because their outcome may be unknown.

### Alarm management

Read the current list first. To enable one alarm:

```yaml
action: noise_explorer.set_alarm_enabled
data:
  device_id: YOUR_HOME_ASSISTANT_WATCH_DEVICE_ID
  alarm_id: "20260914120000000"
  enabled: true
```

To replace the complete list, pass up to ten objects with `hour`, `min`, `days`, `onoff`, `timeid`, and `bell`. Preserve existing IDs and bell values when editing. Each new `timeid` must be a unique 17-digit `yyyyMMddHHmmssSSS` timestamp. The IDs below are synthetic examples; replace them with the IDs read from the watch or a new timestamp as appropriate. Use a bell value known to work on your watch.

```yaml
action: noise_explorer.set_alarms
data:
  device_id: YOUR_HOME_ASSISTANT_WATCH_DEVICE_ID
  alarms:
    - hour: "07"
      min: "30"
      days: "1,1,1,1,1,1,0,0"
      onoff: "1"
      timeid: "20260914120000000"
      bell: "1"
```

`days` contains the repeat flag followed by Monday–Sunday flags; this example repeats on weekdays. The 10-alarm limit is conservative, not a measured Junior 2 maximum. Whole-list replacement overwrites concurrent changes from the phone app. Editing one alarm is serialized against other writes inside this integration, but cannot lock out app changes.

## Events

`noise_explorer_watch_event` is fired for recognized live SOS, city-change, safe-area, guard, battery, and danger-area messages. It contains `watch_id`, `config_entry_id`, `kind`, and `received_at`. `watch_id` is the vendor EID, not HA's device ID. No raw location, contacts, or chat payload is included. Offline event-history synchronization is not implemented, so events missed while disconnected are not replayed.

## Validation and limitations

- The XAPK was decompiled locally and used as protocol evidence, not as executable instructions. Evidence and endpoints are in [docs/PROTOCOL.md](docs/PROTOCOL.md).
- Automated tests cover encrypted framing, login, discovery, settings, failure handling, reconnects, parsing, alarm validation, real HA entity classes, multi-watch behavior, and diagnostics redaction.
- Automated tests use synthetic responses. Live login, cloud reads, fresh location and firmware requests also passed; the owner confirmed Find watch rang. Concurrent app sessions and setting changes remain unverified.
- On the tested firmware, Find watch rang without returning a reply, so the action can time out despite physical execution. Step and signal refresh requests did not reply within the 35-second live test window; their cached readings remain available. Do not automatically retry a timed-out command.
- The app handles server session replacement. If HA is kicked out, it requests reauthentication instead of repeatedly logging in and kicking the app out. A separately invited family account may help, but concurrent-session behavior has not been tested.
- This is a **cloud integration**, not a local Bluetooth connection. It needs internet access to Noise's server on TLS port 8555, and the watch needs its normal network service.
- Heart rate, blood oxygen, sleep-health reports, geofence editing, contacts editing, text/audio messaging, photos, remote recording, and live video are not implemented. Their presence in shared app code does not establish Junior 2 support, and several require separate HTTP/media protocols. No fake sensors or arbitrary raw-command service are supplied for them.
- Passwords are stored in HA's config-entry storage for reconnects, as with other password-based integrations. Protect HA backups. Logs and diagnostics do not output credentials, tokens, children’s names, account IDs, coordinates, or raw payloads.

## Development and live verification

The recorded test environment uses Python 3.14. Run these commands from the repository root:

```text
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check custom_components tests scripts
```

The commands above are for Windows. On Linux replace `.venv\Scripts\python.exe` with `.venv/bin/python`.

An optional interactive probe performs login, discovery, and cached reads only:

```text
.venv\Scripts\python.exe scripts/probe.py
```

On Linux, use `.venv/bin/python scripts/probe.py`. It prompts for credentials locally, hides the password, and prints only watch counts and returned field names. It does not ring, locate, or change watch settings, but signing in may replace the phone app's session. Read the [validation record](docs/VALIDATION.md) for completed checks and the [watch test checklist](docs/LIVE_TEST.md) for checks to repeat on an installation.

Use the virtual environment's Python to run `scripts/build_metadata.py` when rebuilding UI metadata. Package the ZIP with `python scripts/package_release.py`; this script needs only the standard library. Project documentation is maintained in [this repository](https://github.com/andeshc/NoiseExplorerHubIntegration).
