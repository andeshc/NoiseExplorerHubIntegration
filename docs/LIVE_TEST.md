# First test with your watch

These are the remaining tests requiring your account and Junior 2. No password needs to be sent to the developer.

1. Install the ZIP and sign in through HA. Confirm it discovers the already-paired watch without rebinding.
2. Compare battery, reported steps, charging, network, watch online, and Wi-Fi readings against the app. Check report timestamps, especially the local-time assumption.
3. Press Request location. Compare the HA map pin, accuracy, and location report time to the app. Confirm the location changes after moving the watch.
4. Press Find watch and confirm it rings. A cloud acknowledgement alone is insufficient.
5. Test one reversible setting, such as volume. Confirm the watch applies it, then restore the original value.
6. Read settings and inspect the returned alarm IDs. Test enabling/disabling an existing alarm and restore it. Test complete alarm-list replacement only after saving the original list.
7. Open the phone app while HA is connected, and vice versa. If a session is kicked, confirm HA offers reauthentication without repeatedly displacing the app.
8. Temporarily take the watch offline. Confirm Watch online differs from Cloud connection. Restore connectivity and confirm telemetry resumes.
9. Restart HA and confirm discovery and cached sensors recover. Request a fresh location; location is not persisted across restarts.

For troubleshooting, download the integration's **Diagnostics** from HA and report the failing action and returned numeric error code. Diagnostics contain reported field names and status booleans only, not payload values, watch IDs, coordinates, account identifiers, passwords, or tokens.

Optional: run `scripts/probe.py` locally for a read-only sign-in/discovery check before installation. It prints a watch count and field names with all values hidden.
