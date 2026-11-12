# Wear-aware dimming for AZJ2

This KernelSU GXR module replaces the dim-room eye-loss sleep countdown with
dimming. With the headset worn and awake, 60 seconds of confirmed missing eyes
dims display 0 to 20% of its current brightness. Detecting eyes again, removing
the headset, or stopping the module releases the temporary override. A display
already at minimum brightness stays there.

The stock proximity sensor still controls removal sleep. Manual sleep,
low-battery shutdown, thermal protection and the ordinary inactivity timeout
remain in place. There is no wake lock. A power-off caused by anything other
than the stock eye-loss monitor needs separate diagnosis.

## Install and use

1. Regain temporary root and confirm KernelSU GXR says **Working**. Keep
   DirtyFrag Autorun off.
2. Install `gxr-wear-dim-azj2-0.1.2-disabled.zip`. It installs disabled.
3. Enable **Galaxy XR wear-aware eye-loss dimming (AZJ2)**, then tap **Action**.
   Expect `RUNNING` and `PORT_READY`. No Soft restart is required. The existing
   combined Window Controls module can stay enabled.
4. Remove the headset for at least three seconds, then put it back on. This
   clears any stock eye-loss countdown that had already started before the
   module was enabled.
5. With brightness above minimum, test a minute without detectable eyes while
   the wear sensor remains covered. Confirm dimming, brightness restoration
   when eyes return, and normal sleep after removal. Do not cover tracking
   cameras or use a test that disables the wear sensor.

Before rooting, stop if the device is not the expected firmware. The module
also gates activation on the exact AZJ2 fingerprint and SHA-256 of SystemUI
and framework.jar.

Switching the module off requests cooperative cleanup of the brightness
override and restores the eye-monitor property's previous value. Wait about
15 seconds before uninstalling. If restoration fails, keep it off and fully
reboot; both changes are nonpersistent. Regain temporary root manually if
needed to remove installed module files.

After a full reboot, root and the live effects are gone. Regain temporary root
and use Action to reapply; the ZIP and module files remain installed. The
runtime does not restart SystemUI or change the window module's hooks.

## Implementation and checks

AZJ2's `EyesMonitor` starts its countdown when the headset is mounted, the room
is dim and eyes are absent. It shows a warning at 60 seconds and calls
`goToSleep(..., 14, 1)` at 90 seconds. Its
`debug.ix.sysui.eyes_monitor.enabled` flag prevents new countdowns. The module
sets that nonpersistent flag to `false` only while its supervised helper runs.

A separate `app_process` helper observes the same type-34 off-body sensor as
stock `ProximitySensorManager` and reads `CPM.SystemInputInfo.eyesStatus`.
As in the stock eye-monitor flow, an unsuccessful retrieval leaves the last
observation intact; unknown status before the first valid observation does
not start dimming. CPM service death requests cleanup. Only status 1 (eyes
absent), continuous wear and an interactive display start the minute timer.
Unknown status, eye presence, removal and sleep reset it.

The helper uses `DisplayManager.setTemporaryBrightness(0, value)` and releases
its override with `Float.NaN`. It never writes `screen_brightness` or changes
the brightness mode. A same-boot journal and the existing port supervisor
provide cleanup after crashes, disable, update and uninstall.

The delay applies whenever eyes are absent while worn, including a bright
room. It is intentionally broader than stock's dim-room-only countdown.

Host policy tests cover the minute boundary, eye return, removal, sleep,
unknown input and brightness bounds. A read-only ADB probe on the AZJ2 device
confirmed type-34 sensing, the temporary-brightness API and eyes-present input
without root. The user tested the installed dimming module on the AZJ2 headset
and reports it working. Restoration across every state and extended stability
have not been independently verified.

## Build

Use the existing Java 8-compatible compiler, Android SDK jar and D8/R8:

```sh
python3 scripts/build-wear-dim.py \
  --java /path/to/java --javac /path/to/javac \
  --r8 /path/to/r8.jar --android-jar /path/to/android.jar
python3 tests/bread-daemon-lifecycle.test.py
python3 tests/wear-dim-package.test.py
```

The builder runs `WearDimPolicyTest`, packages a DEX and the shared supervisor,
includes the helper/build source, and verifies ZIP checksums and the installer's maximum directory depth and complete coordinated-restart hook set. It needs
no Frida injector or new native library.

Implementation by [booinspace](https://github.com/booinspace), based on
inspection of the user's stock AZJ2 firmware. It reuses this repository's
port lifecycle code. No proprietary firmware binaries are included.
