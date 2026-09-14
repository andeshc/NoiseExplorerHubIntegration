# Reverse-engineering evidence

## Artifact

- Supplied file: `noise.xapk`, 332,341,851 bytes.
- XAPK SHA-256: `c059709d37d3ebef335efb655f8da26dd75737109d7a25d95d1663353cbf872a`.
- Base APK: `com.noise.explorer.apk`.
- APK SHA-256: `1eab7eaaf2e3cbbb2cdb4ddb78794289085aee39ff20722041cdb9ffc51201fe`.
- App: Noise Explorer Hub, package `com.noise.explorer`, version `1.0.7.052119`, code 11.
- Six DEX files. Java decompilation with JADX 1.5.6 completed with 196 method errors among 17,707 classes. Relevant protocol call sites were readable; shared/native/media functionality was not exhaustively recovered.

The large ABI split contains native/media components. This implementation uses the Java cloud protocol in the base APK. Decompiled files and downloaded tooling stay under ignored `analysis/`; they are not redistributed in the integration ZIP.

## Evidence map

Paths below are relative to the local, untracked `analysis/decompiled/sources` directory. They are evidence references, not links to files distributed in this repository. Line numbers refer to the local JADX output.

| Behavior | App evidence |
|---|---|
| Noise-specific India endpoint and `HI` region | `com/xiaoxun/xun/region/AppRegionModel.java:49`, `LOCAL_WATCH_LIST` |
| `wss://host/svc/pipe` | `com/xiaoxun/xun/services/NetService.java:2685` |
| Email/password login payload | `com/xiaoxun/xun/activitys/NewLoginActivity.java:1973`, `sendEmailLogin` |
| Required `Version="00140000"` on outgoing requests | `NetService.java:6545`, `sendNetMsg`; `CloudBridgeUtil.SW_PROTOCOL_NUM` |
| Uppercase, zero-padded MD5 | `com/xiaoxun/xun/utils/StrUtil.java:183`, `getMD5` |
| `region=global` | `com/xiaoxun/xun/utils/XimalayaUtil.java:26` |
| Login time zone `UTC+05:30` style | `com/xiaoxun/xunoversea/utils/Utils.java:51` |
| RSA public key and PT1/PT2 handshake | `NetService.java:141`, `NetService.java:3842` |
| RSA/PKCS1 v1.5 | `com/xiaoxun/xun/utils/RSACoder.java:25` |
| AES-CBC/PKCS5 padding with key also used as IV | `ib/a.java`, `h`, `c` |
| Binary encrypted frames, JSON/base64 text replies | `NetService.java:270`, `NetService.java:300`, `NetService.java:3890` |
| WebSocket transport without extra binary framing; protocol ping | `dx/client/api/EndpointFactory.java`, endpoint type 6; `lb/a.java` and `lb/d.java` |
| Login success `RC=1`, root `SID`, `PL.EID` | `NetService.java:4152` |
| Family discovery request | `NetService.java:6206`, `sendQueryAllGroups` |
| `PL[]`, `GID`, `Endpoints[]`, device `Type=200` | `com/xiaoxun/xun/ImibabyApp.java:4394`, `CloudBridgeUtil.WATCH_TYPE` |
| Multi-key read | `NetService.java:6150`, `sendMapMGetMsg` |
| Settings write envelope/SMS hint | `NetService.java:6166`, `sendMapSetMsg` |
| Online/offline read | `NetService.java:5183`, `getDeviceOfflineState`; response at 1314; key `offline` |
| Watch commands and routing | `NetService.java:6605`, `CloudBridgeUtil.CloudE2eMsgContent` |
| Find watch action 158, `Key="1"` | `com/xiaoxun/xun/utils/WatchFunctionUtils.java:76` |
| Location action 100 | `com/xiaoxun/xun/testdemand/GoogleMapTestViewModel.java:144` |
| Location notifications | `NetService.java:4971`, CIDs 50112 and 50122 |
| Position string ordering and map formats | `com/xiaoxun/xun/beans/LocationData.java:51` |
| Battery `timestamp_value` | `NetService.java:2104`, `NetService.java:5350` |
| Steps `date_count` | `com/xiaoxun/xun/activitys/StepsActivity.java:649` and 677 |
| Main telemetry fields | `com/xiaoxun/xun/activitys/NewMainActivity.java:412`; `NetService.java:4544` |
| WLAN JSON array | `NetService.java:4064`, `updateWlanStateData` |
| WLAN connected bit 4 | `com/xiaoxun/xun/activitys/WatchWifiActivity.java:1000` |
| Volume, brightness, sound/vibration values | `com/xiaoxun/xun/activitys/VolumeActivity.java`, `mapSetData`, listeners a/b/c |
| Automatic answering values | `com/xiaoxun/xun/activitys/DeviceAutoAnswerActivity.java`, `getModeFromPosition` |
| Modes 4/3/5 = saving/normal/performance | `com/xiaoxun/xun/activitys/OperationSelectActivity.java`, listeners b/g/h |
| Watch switches | `com/xiaoxun/xun/activitys/WatchManagerActivity.java:368` and click handlers |
| Wi-Fi switches | `com/xiaoxun/xun/activitys/WatchWifiSettingActivity.java:42` and 59 |
| Alarm object fields and repeat string | `com/xiaoxun/xun/beans/AlarmTime.java`; `AlarmClockActivity.java:361` |
| Local time interpretation | `com/xiaoxun/xun/utils/TimeUtil.java:553`, `getMillisByTime` |
| Session invalid/kicked codes | `NetService.java:3471`, RC -14 and CID 79002 |
| Reply matching | `NetService.java:1850`, `checkMsgQueueResp`: SN equality and response CID=request CID+1 |

Unqualified `NetService.java` and `CloudBridgeUtil` above refer to `com/xiaoxun/xun/services/NetService.java` and `com/xiaoxun/xun/utils/CloudBridgeUtil.java`.

## Wire protocol

The default Noise region endpoint is **`wss://noise-cmibro.xunkids.com:8555/svc/pipe`**. The generic `m.java` Singapore default is overridden by `AppRegionModel`; using it for Noise India would be a mistake. Other services in the same region config are under `https://india-api.xunkids.com/` (`noise`, `fileServer`, `stepserver`, `hsdataserver`, `xun-cloudalbum`, etc.). They are not needed by this integration.

Requests carry uppercase envelope fields: `CID`, `SN`, `Version="00140000"`, optional `SID`, and `PL`. `NetService.sendNetMsg` inserts the version before encryption. A live login without it returned RC -14; adding it returned RC 1 with the same credentials.

1. Generate a fresh 16-byte ASCII session key.
2. Build CID **10011** with `Name=MD5(email).upper()`, `Uuid=MD5(email).upper()`, `Password=MD5(password).upper()`, `loginType=0`, `Type=102`, `countryCode=HI`, `region=global`, `domainCheck=1`, `timezone=UTC±HH:MM`, `ads`, empty `ect`/`ectr`.
3. Send a WebSocket text object: `PT1=base64(RSA-PKCS1v1.5(public_key, AES_key))`, `PT2=base64(AES-CBC(key, IV=key, padded_JSON))`.
4. Read response CID **10012**; a successful login has root `RC=1`, root `SID`, and `PL.EID`.
5. Send subsequent envelopes as binary AES-CBC frames. The app also accepts JSON or base64 text responses. Session keys/SIDs remain memory-only in this implementation.

`ads` follows the app's device string structure, with a persistent random installation ID and a HomeAssistant brand suffix. Live login accepted this suffix on 2026-09-14.

| Request | Response | Payload / routing |
|---|---|---|
| 20091 | 20092 | No PL, `PARAM={}`; response `PL` is a list of family groups |
| 60051 | 60052 | `PL={EID, Keys:[...]}`; response PL directly maps setting names to values |
| 60071 | 60072 | `PL={EID}`; response `PL.offline`, 1 means offline |
| 60031 | 60032 | `PL={setting:value, TEID:watch_eid, TGID:family_gid, settype:"true", SMS:"<SN,user_eid,E501>"}` |
| 30011 | 30012; 50112/50122 for location | Root `TEID=[watch_eid]`; `PL={sub_action:code,...}`. Location notifications may complete the request when their SN matches. |
| — | 50112 / 50122 | New/track location notifications with `PL.EID` and `PL.result` |
| — | 79002 | Session kicked; stop automatic authentication attempts |

The app includes `PL.SMS="<SN,account_eid,Eaction,argument>"` for find-watch and telemetry requests (DevOptActivity.requestSteps, SystemUpdateActivity.requestWatchVersion, WatchManagerActivity.deviceFindWatch). Find-watch uses argument `1`; telemetry requests leave it empty. The integration includes these fields.

Recovered button actions: 100 locate, 158 find (Key `"1"`), 502 step update, 503 signal update, 504 version update. The app may return a cloud acknowledgement separately from the watch result. A non-negative acknowledgement is not a guarantee of physical completion. Negative return codes are surfaced. A timeout does not trigger an automatic write retry.

Incoming `sub_action=501` reports contain fields such as `battery_level`, `cur_steps`, `watch_status`, `status`, `signal_level`, `net_stat`, and `wlan`. Other event paths are partially implemented using only recognized field names. The shared app code's action 164 is ambiguous across generations and is exposed as **guard**, not confidently classified as low battery.

## Scope and uncertainty

**Verified statically:** the endpoints, request builders, encryption algorithms, selected parameter values, and parsers above exist in the supplied app.

**Verified with tests:** client transport logic against a local simulated server, an independent OpenSSL AES ciphertext vector, malformed-value handling, per-watch HA state, discovery of optional controls, settings readback, and redaction.

**Live endpoint check:** on 2026-09-14, the Noise host on port 8555 completed a TLS 1.2 handshake with normal certificate and hostname verification. No account login or watch request was sent for this check. The app's WebSocket library has a trust-all default; this integration deliberately retains normal TLS verification, which passed for the tested endpoint.

**Live account validation:** email/password login, one paired-watch discovery, cached settings and offline-status reads succeeded on 2026-09-14. The live settings instantiated 44 HA entities. Firmware returned `PL.watch_version`; location arrived as CID 50112 with a matching SN and a valid fix. The owner confirmed Find watch rang, but it did not return an acknowledgement within 35 seconds. Step and signal refreshes did not return a reply in the same test window. Credentials and personal payloads were excluded from logs, tests and version control.

**Not verified on hardware:** setting and alarm writes, remaining Junior 2 features and firmware response variants, session coexistence, and local timestamp interpretation for the actual account.

The integration does not attempt account creation, rebinding, device takeover, certificate bypass, raw command injection, firmware changes, or automatic writes during setup. The lack of a feature means its protocol or model support has not been sufficiently established for this implementation.

## Home Assistant references

Implementation follows the official [config-flow documentation](https://developers.home-assistant.io/docs/core/integration/config_flow/), [coordinated data fetching](https://developers.home-assistant.io/docs/integration_fetching_data/), [service-action registration](https://developers.home-assistant.io/docs/dev_101_services/), and [device-tracker entity interface](https://developers.home-assistant.io/docs/core/entity/device-tracker/). These explain the HA interfaces; the supplied APK is the protocol source.
