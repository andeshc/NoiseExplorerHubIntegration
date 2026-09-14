# Validation record

Environment: Windows, Python 3.14, Home Assistant 2026.2.3, aiohttp 3.13.3, cryptography 46.0.5.

- 57 automated tests passed.
- All seven HA entity platforms instantiated using real Home Assistant classes.
- Simulated-server tests exercised the actual aiohttp WebSocket client, login, discovery, reads, write envelopes, timeouts, negative responses, push/reply correlation, reconnects and session replacement.
- AES ciphertext matched an independently generated OpenSSL vector.
- Parsing tests covered null/zero values, invalid numbers, source times, invalid/stale location fixes, Wi-Fi bit flags and alarm structures.
- Coordinator tests covered optional-entity discovery, multiple watches, removal, authentication failure, cloud readback and diagnostics redaction.
- Static checks passed with Ruff; all Python sources compiled.
- English translations matched the config-flow strings; 10 action descriptions parsed as YAML.
- Release ZIP integrity and allowlisted contents checked.
- A normal certificate-verified TLS 1.2 handshake succeeded to the configured Noise endpoint on port 8555. No credentials were sent.

One upstream Home Assistant/aiohttp deprecation warning appeared during tests. No test failed because of it.

These results do not establish live account authentication, physical watch command execution, or firmware support. No running user HA instance was modified. See LIVE_TEST.md for those remaining checks.
