# Wear-aware display blanking for AZJ2

This KernelSU GXR module turns the headset's physical display off after
**60 seconds without detected eyes while still worn**. Android stays awake
and the module continues observing eye input. When eyes return, it restores
display output. It polls every **16 ms while blanked**, and every 250 ms
otherwise. These are polling intervals, not a measured wake-up latency.

Version **0.2.0** replaces the earlier 20% brightness behavior. It uses the
same module ID, so install it as an update to eye dimming. The saved user
brightness is unchanged. An explicit unknown eye status releases blanking
immediately. CPM reports changes, so a poll without a new snapshot retains
the last confirmed eye state.

Stock proximity removal sleep, manual sleep, ordinary inactivity, thermal
protection and low-battery shutdown remain active. The helper takes no wake
lock and never calls `wakeUp()`. A physically blanked panel can still leave
apps and audio running; this is not a battery-saving system sleep mode.

## Install and use

1. Confirm SM-I610 firmware `I610UES3AZJ2`, regain temporary root and check
   KernelSU GXR says **Working**. Keep DirtyFrag Autorun off.
2. Switch the installed eye-dimming module off and wait about 15 seconds for
   its cleanup. Install `gxr-wear-dim-azj2-0.2.0-disabled.zip` as an update.
3. Enable **Galaxy XR wear-aware display blanking (AZJ2)** and tap **Action**.
   Expect `RUNNING` and `PORT_READY`. No Soft restart is needed; keep the
   working Window Controls module installed.
4. Remove the headset for three seconds, then put it back on to clear any
   stock eye-loss countdown started before activation.
5. Test a full minute without detectable eyes while the wear sensor remains
   covered. Check panel blanking, restoration when eyes return, app/audio
   continuity and normal removal sleep. Leave tracking cameras unobstructed.
   If wake-up fails, use the stock Power button, disable this module and fully reboot.

The user confirmed a guarded three-second panel-off/restore test on AZJ2:
the display went fully black and returned to the same Home Space and apps.
Android remained interactive. The complete minute timer and eye-triggered
restoration still need a module test, and actual latency is unmeasured. CPM service
death requests supervised cleanup; a silent tracking stall cannot be inferred
from an unchanged snapshot. Use the Power button and reboot if it fails to restore.

## Stop and recover

Switch the module off to restore its panel override and the previous
eye-monitor property. Wait about 15 seconds before uninstalling or updating.
Restoration only turns output back on while Android remains interactive;
it does not wake a headset that has entered stock sleep. If cleanup fails,
leave the module off and fully reboot with DirtyFrag Autorun off. A full boot
clears live effects; installed module files and settings can remain.

**Action** exports `gxr_wear_dim_azj2-daemon.log` and any failure file to
`/data/local/tmp/`. Ownership is journaled before blanking. The shared
supervisor requests cleanup after a crash, disable, update or uninstall.
The four GXR restart hooks stop the helper before a planned Soft restart.

## Implementation

AZJ2's stock `EyesMonitor` normally warns at 60 seconds and requests sleep at
90 seconds when mounted, in a dim room and without eyes. While running, this
module sets its nonpersistent `debug.ix.sysui.eyes_monitor.enabled` property
to `false` and replaces that policy with the worn/no-eyes minute timer.
The module applies in bright rooms too.

A standalone root `app_process` observes the stock type-34 off-body sensor
and reads `CPM.SystemInputInfo.eyesStatus`. Confirmed status 1 (eyes absent)
can sustain the timer. Eyes present, unknown input, removal or Android sleep
reset it. Eye-return handling uses the helper's own looper, independently of
the supervisor's 250 ms cleanup watchdog.

The helper obtains the sole physical panel token through the
[Android 14 compositor's read-only AIDL getters](https://android.googlesource.com/platform/frameworks/native/+/android-14.0.0_r1/libs/gui/aidl/android/gui/ISurfaceComposer.aidl)
(transactions 6 and 7, verified on AZJ2), then uses the stock
`SurfaceControl.setDisplayPowerMode` API: OFF (0) and NORMAL (2). It loads no
server native library and patches no native code. Firmware and payload pins
are checked before activation. It also releases a journaled temporary
brightness override left by an older dimming build.

## Build

Use a JDK, Android SDK platform JAR and D8/R8:

```sh
python3 scripts/build-wear-dim.py \
  --java /path/to/java --javac /path/to/javac \
  --r8 /path/to/r8.jar --android-jar /path/to/android.jar
python3 tests/bread-daemon-lifecycle.test.py  # Linux/WSL
python3 tests/wear-dim-package.test.py
```

The builder also produces `wear-display-api-probe.dex`. This read-only probe
resolves the actual display getters and counts eye-state snapshots for about
two seconds, without blanking the panel:

```sh
adb push releases/wear-display-api-probe.dex /data/local/tmp/
adb shell 'CLASSPATH=/data/local/tmp/wear-display-api-probe.dex app_process /system/bin WearDisplayApiProbe'
```

An awake-headset probe returned a single eyes-present snapshot across 125
polls, confirming that unchanged polls must retain the last observation.

The builder runs wear/eye timing policy tests, compiles the helper and
packages its source with the existing supervisor. Package checks cover
disabled installation, checksums, directory depth and all four restart hooks.

Implementation by [booinspace](https://github.com/booinspace), based on the
user's stock AZJ2 firmware and Android's display API. The investigation also
compared [scrcpy's Android 14 display access](https://github.com/Genymobile/scrcpy/tree/master/server/src/main/java/com/genymobile/scrcpy/wrappers);
its server-library loader is not used here. No proprietary firmware binaries
are included.
