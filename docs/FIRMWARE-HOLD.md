# Hold the headset on AZJ2

On the SM-I610 running `I610UES3AZJ2`, the Samsung firmware updater is
`com.wssyncmldm` (`FotaAgent`, 4.2.25), with the companion agent
`com.sec.android.soagent` (`SOAgent_VST`, 1.0.20). Both were inspected over ADB
and disabled for user 0. The firmware remains AZJ2.

```sh
adb shell pm disable-user --user 0 com.wssyncmldm
adb shell pm disable-user --user 0 com.sec.android.soagent
```

This blocks those packages' automatic checks, boot receivers, update UI and
notifications. It uses package-manager state and survives a normal reboot
without temporary root. It does not uninstall their APKs, erase their data or
require an extra root module. After the change, both packages reported
`disabled-user`, with no running updater process or service. No active update
notifications from either package were found. Suppression of a future update
prompt still needs confirmation on the headset; no restart was performed.

Verify the state with:

```sh
adb shell pm list packages -d
adb shell getprop ro.build.fingerprint
```

Both updater package names should appear in the disabled list. The existing
`ota_disable_automatic_update=1` global setting was left unchanged.

## Restore firmware updates

Both packages originally used their manifest-default enabled state
(`enabled=0`). Restore that exact state with:

```sh
adb shell pm default-state --user 0 com.wssyncmldm
adb shell pm default-state --user 0 com.sec.android.soagent
```

Then open Settings → Software updates when ready to update. An update can
remove the vulnerability used for temporary root and invalidate the modules'
firmware checks. Inspect compatibility before accepting one.

This hold targets Samsung OTA firmware updates. It does not freeze Play Store
apps, Google Play system components, manual flashing or factory-reset state,
and cannot cancel a firmware installation that is already committed. No OTA
payload or recovery partitions were modified. Remaining on AZJ2 also means
remaining without newer firmware security fixes.
