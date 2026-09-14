# Validation record

Validation date: 2026-09-14. Integration version: 0.1.1.

Environment: Windows, Python 3.14, Home Assistant 2026.2.3, aiohttp 3.13.3, cryptography 46.0.5.

- 79 automated tests passed.
- All seven HA entity platforms instantiated using real Home Assistant classes.
- Simulated-server tests exercised the actual aiohttp WebSocket client, login, discovery, reads, write envelopes, timeouts, negative responses, push/reply correlation, reconnects and session replacement.
- AES ciphertext matched an independently generated OpenSSL vector.
- Parsing tests covered null/zero values, invalid numbers, source times, invalid/stale location fixes, Wi-Fi bit flags and alarm structures.
- Coordinator tests covered optional-entity discovery, multiple watches, removal, authentication failure, cloud readback and diagnostics redaction.
- Static checks passed with Ruff; all Python sources compiled.
- English translations matched the config-flow strings; 10 action descriptions parsed as YAML.
- Release ZIP integrity and allowlisted contents checked.
- An initial certificate-verified TLS 1.2 handshake succeeded to the configured Noise endpoint on port 8555 without sending credentials. The subsequent account tests are described below.

One upstream Home Assistant/aiohttp deprecation warning appeared during tests. No test failed because of it.

Live account testing on 2026-09-14 confirmed authentication, discovery of one paired watch, cached settings reads and online-status reads. Live data instantiated 44 entities across the seven platforms. Adding the missing protocol version changed login from RC -14 to RC 1 without changing credentials. Tests now enforce this field and check specific login error messages.

Fresh firmware requests returned RC 1 with `watch_version`; the sensor consumes that field. Fresh location returned RC 1 via CID 50112 with the original request SN; the location request now completes on that response. A valid location was parsed without printing coordinates. The owner confirmed the Find watch test rang, although no command reply arrived within 35 seconds. Step and signal requests also did not reply within that window (the initial step request was allowed the full 120-second timeout). Cached readings remained available.

Settings writes, alarm changes, concurrent phone sessions and complete firmware support remain unverified. No running user HA instance was modified. See the [watch test checklist](LIVE_TEST.md) for the remaining checks and installation verification.
