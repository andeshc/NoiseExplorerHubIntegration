# Watch test checklist

Use this checklist to verify an installation with a paired Junior 2. Login, cloud reads, fresh location and firmware requests have passed live testing, and the owner confirmed Find watch rang. See the [validation record](VALIDATION.md) for the results and limitations. Repeat these checks on an installation; setting changes, alarm changes and concurrent phone sessions remain unverified. Enter credentials locally, never in an issue report.

1. Install the ZIP and sign in through HA. Confirm it discovers the already-paired watch without rebinding.
2. Compare battery, reported steps, charging, network, watch online, and Wi-Fi readings against the app. Check report timestamps, especially the local-time assumption.
3. Press Request location. Compare the HA map pin, accuracy, and location report time to the app. Confirm the location changes after moving the watch.
4. Press Find watch once and confirm it rings. The tested watch rang without returning a reply, so a timeout does not prove it failed. Do not retry automatically.
5. Test one reversible setting that appears for the watch, such as volume if available. Record its original value, confirm the watch applies the change, then restore the original value.
6. Read settings and inspect the returned alarm IDs. Test enabling/disabling an existing alarm and restore it. Test complete alarm-list replacement only after saving the original list.
7. Open the phone app while HA is connected, and vice versa. If a session is kicked, confirm HA offers reauthentication without repeatedly displacing the app.
8. Temporarily take the watch offline. Confirm Watch online differs from Cloud connection. Restore connectivity and confirm telemetry resumes.
9. Restart HA and confirm discovery and cached sensors recover. Request a fresh location; location is not persisted across restarts.

For troubleshooting, download the integration's **Diagnostics** from HA and report the failing action, the exact error shown, and the installed integration version. Include a numeric server code if one is shown. Diagnostics include field names, status flags, version and polling metadata; they omit watch payload values, watch IDs, coordinates, account identifiers, passwords and tokens.

Optional: follow the [probe instructions](../README.md#development-and-live-verification) for a local sign-in/discovery check before installation. The probe prints a watch count and field names with values hidden. Signing in may replace the phone app's session.
