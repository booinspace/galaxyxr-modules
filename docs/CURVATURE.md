# Window controls for Galaxy XR AZJ2

The combined module adds curvature, borderless app windows, a hover-only
caption pill, hand positional rotation and pitch/yaw/roll sliders to ordinary
Home Space Android windows. Stock dragging moves the window; turning the
grabbing hand rotates it in all three axes. The movement outline and resize
corners follow that orientation. Resize motion is projected into the tilted
window's frame, so outward motion grows the window and inward motion shrinks
it. The module uses one supervised Frida injector and one Java-owned menu.

The stock maximum movement distance is extended tenfold. The stock 5 m fallback
becomes 50 m; an explicitly configured maximum is multiplied by ten. The near limit,
movement sensitivity and ordinary app input are unchanged. The user confirmed
movement beyond the old limit and correct outward/inward tilted resizing on
AZJ2. This confirms the reported behavior, not a measured 50 m placement.
The user confirmed in-place installation and automatic reload of 0.1.30 after
one GXR Soft restart, with Home and window features working before Action.

Planned GXR Soft restart resume has been verified on the headset. The 90-second
startup gate is a workaround for a native startup crash whose cause remains
undetermined. Extended idle/wake stability remains unverified.

This is a **KernelSU GXR module ZIP**. It requires an active temporary root
session; it is not an APK or a kernel LKM. Keep DirtyFrag **Autorun off**.

The opt-in [immersive app pins candidate](IMMERSIVE-PINS.md) adds a native
overlay launcher, a pill-menu **Pin app** action and eye-driven fading. Overlay
visibility and dragging were confirmed in an earlier trial; the complete pin
behaviour remains experimental. The confirmed baseline remains 0.1.30.

Version **0.1.30** adds [up to 50 Home pins](HOME-PINS.md), with the same
five-column tiles and panel size. Scroll vertically above 10 pinned apps.
The user confirmed automatic startup and working Home/window features. ADB
matched the automatic RUNNING report to the installed version and live
SystemUI full-boot/PID/start-time identity.
This build waits for a 90-second SystemUI process age before every attachment,
including ordinary starts after a full reboot. Earlier builds applied that
age gate only to planned restart resume. A 0.1.26 ART crash occurred at 33
seconds of SystemUI uptime; applying the existing delay is a precaution, not
proof of the underlying native cause or a complete crash fix.

## Install

1. Confirm KernelSU GXR reports **Working**. Keep separate Borderless and
   Rotation modules off. Updating from 0.1.24 or earlier can require one final
   full reboot and regaining temporary root: that installed version's guard
   runs before the new files can replace it. The combined package handles
   previous-boot quarantine through its built-in recovery checks.
2. In **Modules → Install from storage**, choose the combined ZIP. It installs
   disabled. Use an in-place update; if the existing module is pending
   deletion, tap **Undo**, leave it off, then retry installation.
3. Enable **Galaxy XR Window Controls** and use one GXR **Soft restart**.
   The verified restart hook queues startup directly, even when the manager's
   service stage has already been dispatched. Future GXR Soft restarts use
   the coordinated handoff described below.
4. Keep Home Space awake and allow up to **150 seconds**, then fully close an
   ordinary app window and launch it again. Action settings can report
   **App window setup: ready**, but opening Action is not required to start.
   A window restored before the Borderless delay can keep its decorations.
   Reopening only its top menu does not recreate the window.

The current package is `gxr-window-curvature-0.1.30-azj2-disabled.zip`.
Verify its checksum against the builder's `.sha256` sidecar before copying.
Boundary alignment is included in the combined build. The tested 0.1.23
artifact remains available in the repository as a checkpoint.

## Updating without a full reboot

Starting with 0.1.25, a normal stop reports stock state only after curvature,
rims, caption visibility, rotation and boundary transforms are restored, all
native move computations have returned, and the injector has detached.
KernelSU GXR can then replace the installed package with a higher version
without a cold boot. It retains a disabled backup and installs the update
disabled. Enable it afterward. If that SystemUI process previously hosted the
old runtime, Action reports **WAITING**: use one GXR **Soft restart** to load
the update, keeping temporary root. The existing 90-second startup guard still
applies. If the current process has never hosted this module, Action can start
it directly. Uninstalling first is unnecessary.

A clean stop records the exact full-boot/PID/start-time identity. The restart
coordinator uses that proof to retire the old process and authorize one
replacement. Reinjecting into the same SystemUI process is still refused.

Failed cleanup, an unexpected stop or an existing quarantine still blocks
replacement and requires recovery. Pending removal/update markers and same
or lower version codes remain rejected. The user confirmed the 0.1.30 update
and automatic startup after one GXR Soft restart in the same full boot. The
automatic RUNNING report matched the new version and live process identity.

## After a cold boot

Leave the combined module enabled across normal shutdowns. Regain temporary
root with DirtyFrag Autorun off, then use one GXR Soft restart. This late-load
setup does not dispatch ordinary module services immediately when root is
loaded. The module checks its payload and firmware, preserves the previous
boot's diagnostics and acknowledges that old quarantine before attachment.

If services have not started it, tap the combined module's **Action**. Action
starts it when enabled and not already starting/running, waits up to 30 seconds
for status, then exports logs. This start does not require a Soft restart.
Action starts the runtime and opens settings. Startup first waits until the
SystemUI process is 90 seconds old, followed by the usual 45-second Borderless
delay. Recreate an app window afterward.

A crash still disables the module. After a full reboot, regain root, enable
it and tap **Action**. The module never turns its own checkbox on. A Soft
restart cannot clear an unexpected crash's quarantine.
Missing/malformed identities, conflicting session records, a live runtime,
another injector or failed firmware/payload checks prevent automatic recovery.

## Planned Soft restarts

KernelSU GXR's four restart phases stop the running agent before Android is
stopped. The agent must acknowledge flat curvature, restored orientation and
caption cleanup; its injector must detach and its supervisor must exit. The
module keeps its checkbox enabled during this planned stop.

The stopped phase checks that the old SystemUI process has exited. The started
phase records the new process identity after Android has booted and queues
the module's startup worker. That worker returns control to the coordinator
immediately and waits in the background for the matching restart generation.
The normal service stage provides a fallback launch; the
existing controller lock prevents duplicate attachment. Once the
coordinator marks that restart ready, the service waits until that exact
replacement process is at least 90 seconds old before consuming its one-use
authorization and attaching again. The wait does not change the selected
process or accept a later generation. Action can report STARTING during this
wait. Allow up to 150 seconds after Home Space returns, then recreate an app
window; Borderless still attaches 45 seconds after the agent starts.

Automatic startup writes `/data/local/tmp/gxr-window-autostart.txt` after the
runtime reaches RUNNING. It records the module version and full-boot/PID/start-
time identity. Pull it over ADB before opening Action to verify activation
independently; an older version or process identity is a stale report.
Do not request another restart while startup is pending. Individual curve/rotation
choices are not preserved when Android recreates the windows.

An incomplete cleanup, cancelled restart, changed target, stale generation,
manual disable or unexpected crash does not receive that authorization. The
module does not restart Android itself or turn its checkbox back on. A failed
handoff can require a full reboot. Uncoordinated `stop`/`start` commands are not
supported. Temporary root still has to be regained after a full power-off.

Device validation on 12 November 2026 covered two consecutive Soft restarts in
one full boot. Exported diagnostics and live process checks confirmed successful
restart hooks, distinct replacement SystemUI identities, consumed one-use
handoffs and no current disable/failure markers. After the second restart, the
user confirmed curve/tilt menus, rim/pill hiding, dragging and app input before
pressing Action. Later checks confirmed boundary alignment and rotated resizing
with the current window runtime.

## Use

- Open the window's top menu for **Curve/Flatten** and its strength slider.
- Use **Pitch**, **Yaw** and **Roll** sliders to change local orientation;
  the angle applies when released. **Reset rotation** restores the window's
  stock local orientation. Start with a small angle before trying side-lying
  roll angles.
- Point at the top caption area to reveal the pill. Moving away hides it after
  half a second. The caption parent and touch handler remain available for
  stock window dragging.
- Enable **Rotate while grabbing** in Action settings to turn the window with
  your grabbing hand while stock dragging positions it. Turn it off to use
  only the sliders.

Settings belong to each live window and are not saved across SystemUI restart
or window recreation. The module does not remove an app's own letterboxing.
Pitch and yaw can make a panel edge-on or turn it away from you.

## Feature settings and wrist grabs

The module's **Action** starts the enabled runtime, exports logs and
opens a small settings page inside KernelSU GXR. No companion APK is needed.
The page has switches for curvature, borderless windows, rotation controls and
rotation while grabbing. **Apply settings** saves those choices across reboots
and the running supervisor applies them on its next pulse. Reopen the window
menu after applying. Disabling curvature flattens its windows; disabling
borderless restores the last stock rim request and shows the pill. Disabling
rotation restores its local orientation. Turning only grab rotation off keeps
the current orientation and the Pitch, Yaw and Roll sliders.

Grab rotation is **off by default**. It observes AZJ2's stock
hand input events and uses the active hand-grip quaternion during stock move
events. This follows the full hand orientation, including roll. The tracking
frame is the hand grip/palm frame; it is not a raw wrist-joint measurement.
The caption's owning view performs the node update; stock
translation and event delivery continue. Each grab starts from the window's
current orientation, so enabling it does not immediately turn the window.
The math removes the parent's changing orientation before applying the hand
delta. Roll is taken from the full hand quaternion.

New windows bind to their caption when the delayed caption hook runs. A window
created earlier can receive hand samples without creating a rotation session.
Opening its top menu also binds the existing caption, so grab
rotation can work without recreating that window. The menu can close afterward;
updates use the caption's view owner. This does not retrofit Borderless's rim
and pill hooks onto an older window.

The native reader checks the exact AZJ2 function addresses and code for
HandDevice.updateState and AxrifInputManager.populateHandsSourceState. It
reads the same InputActionEvent consumed by the stock handlers, bounds the
action table, verifies the grip/pinch variant types and requires active grip
data, a finite normalized quaternion and a sample age below 100 ms. It requires
one hand with stock pinch-gesture strength at least 0.8. Two pinching hands, stale tracking or
tracking loss cancel grab rotation until the next grab. The existing sliders
remain available. Wrist data stays in process memory and is not logged.

Device checks covered pitch, yaw and roll, retained orientation after release
and aligned app input. The user also confirmed that the movement outline
follows the rotated window and that tilted resize corners respond with 0.1.23.
The later direction report is addressed by the 0.1.25 solver-frame correction.
See [boundary alignment](BOUNDARY-ALIGNMENT.md) for its implementation and
checks. Extended idle/wake behavior and tracking under difficult conditions
remain unverified. Host tests establish parsing, quaternion math and cleanup
behavior; they do not replace headset checks.
The page reports hand tracking as waiting, tracking or unavailable. Waiting
means no fresh accepted sample; the window runtime can still be running.
The log records input callback/sample counts, grab counts and rejection reasons every
10 seconds, without positions or quaternions. Export logs after a hand test
to distinguish an idle native path from rejected samples. Startup reports
STARTING during the 90-second Soft restart guard; that guard and the subsequent
45-second Borderless delay remain unchanged.

For the first check, keep grab rotation off and confirm the existing window
features. Then enable it, wait for tracking, recreate one ordinary app window
after the usual startup delay, and use a small wrist movement in each axis.
Check release, dragging and app input before trying large angles. Turn grab
rotation off and check the sliders again. Use the existing full reboot
recovery procedure if SystemUI crashes.

## Compatibility and runtime

Target fingerprint:
`samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys`.
The runtime checks SM-I610 and these exact stock SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `/system_ext/priv-app/XrSystemUI/XrSystemUI.apk` | `dc664a17617b97d2aafebac9690c4235f530cd24399fbe16b6634d5df2a6a6dc` |
| `/system_ext/lib64/libspaceflinger_jni_vulkan.so` | `8342a55dd62163af3653dcf2153a842e243377897ced3ca00703603d275a3d7f` |
| `/system_ext/lib64/libImpress-jni-vulkan.so` | `ab04d6daf57800a42170febaf33cb128441339c06bd6d46f068c0109693fee42` |
| `/system/framework/framework.jar` | `6ec625a07d94e3e50d82eea14bcec05425de303a62a512e6b82ae57881c46ad7` |
| `/apex/com.android.art/lib64/libart.so` | `afc9dde61f50e1e2b085c886e2bad7df98c433b28e0f01041221e1d138c321c5` |
| `/system_ext/lib64/libsysui_jni_soong_vulkan.so` | `f6e34cf42f704c5d3ced9cca18dd392abf4925cde9e30c3b752a34be4102a809` |

The module refuses mismatches. A firmware update requires inspection and a
new build. No stock APK or native library is replaced.

The shared Java bridge includes pandasauce's
[ART/CMC allocation fix](https://github.com/frida-packages/frida-java-bridge/pull/410)
at commit `fcdd7186467e8c6dfdcef888208807c9fc0424db`, with a local guard
that refuses CMC method cloning if its allocator is unavailable. The upstream
PR is open. Samsung's exact ART image was inspected to confirm that this
allocator uses tracked LinearAlloc storage. The patch, original npm source,
credits and hashes are included in the ZIP.

The [disposable GC test](../tests/art-cmc/README.md) reproduced a native
`ReferenceMapVisitor::VisitFrame` crash with the original bridge while a hooked
method remained on the stack during CMC collection. The patched bridge passed
20,000 calls with the same test. This supports the fix; it does not establish
long-term SystemUI stability.

The immersive-pins candidate also includes local quick-code restoration and
JNI callback-lifetime guards. Its five disposable-process cleanup trials passed
on AZJ2, and 0.1.36's later module shutdown did not crash SystemUI. The current
candidate also corrects pin-launch I/O and isolates manual startup from the
KernelSU UI's freezer group. Version 0.1.37 subsequently hung during startup;
0.1.38 started and launched pinned windows, but lost its supervisor heartbeat
and quarantined without killing SystemUI. Candidate 0.1.39 isolates menu polling,
corrects gaze/focus handling and addresses the compositor's separate brightness
factor. Versions 0.1.39 and 0.1.40 then exposed a native-helper lifetime bug on
pinning and must stay disabled. Corrected 0.1.41 retains native code/storage and
keeps cleanup running after a disarm error; 0.1.42 additionally removes the extra
45-second Borderless wait. The user confirmed 0.1.48's pin fading, interaction,
normal Steam Link brightness and uninterrupted VRChat joystick input while looking
at the pin. Its export matches the live process identity and contains no module
error or shutdown. The user confirmed 0.1.52's scoped wrist rotation and resizing
for immersive pins; its watchdogs use five seconds after 0.1.50's guarded
heartbeat shutdown. A later menu-dismissal race stopped that session. Candidate
0.1.54 treats that race as cancellation and discovers pre-existing captions for
ordinary wrist rotation. The user confirmed both fixes and the return-from-Steam-Link
second-pin test. A small constant immersive-view dim remains while pins are open,
despite the live CPM layers reporting full opacity and a zero-alpha background
scrim. Candidate 0.1.56 suppresses the separate native fullscreen scrim under the
same owned-pin/immersive-only lease; gaze fading and VR input routing are unchanged.
The user confirmed normal immersive brightness, pin fading and joystick input
with 0.1.56. Its matching export records 3,784 suppressed scrim frames and no
fatal error or shutdown. Extended idle/wake remains unverified. See the
[pin investigation and limits](IMMERSIVE-PINS.md#build-and-attribution).

Curvature uses the pinned BlueScorpioVR native hooks and helper. Borderless
suppresses task window rims through `CPM.NodeUpdates` and keeps the caption's
layout and input target. Rotation changes the same task node's orientation
through the stock quaternion API. Owned node references use scene-node
identity, so stock wrapper closure does not invalidate rollback.

Curvature owns the combined menu's size, surface crop and dismissal. The
common heartbeat supplies Home Space eligibility and waits for curvature,
orientation and caption cleanup before detaching. Separate window runtimes
and competing injectors are rejected before attachment.
Caption changes run on each view's owning thread. Borderless uses the common
monotonic heartbeat rather than a separate wall-clock deadline that expires
while the headset sleeps.

The intended scope is ordinary 2D Home Space windows. Other firmware,
immersive/system window behavior, extended stability and every app's input
alignment have not been established. The outline follows rotation but remains
rectangular when the content is curved.

## Recovery and logs

Switch the window module off to request cleanup. The supervisor reports its
state through **Action** and keeps quarantine markers when restoration is
unverified. Clean shutdown in 0.1.25 restores the recorded stock rim request;
it no longer creates a reboot requirement after success. After a failed or
unverified stop, fully reboot with DirtyFrag Autorun off before resetting or
replacing the runtime.

Recovery and diagnostic export are bundled. Use the combined module's
**Action** to see its status and export logs while running. Export does not
reset a live session. Startup archives previous-boot `runtime.log`, `failure`
and `session-open` files before acknowledging them, and keeps the checkbox as
you set it. The exported files can be collected over ADB:

```sh
adb pull /data/local/tmp/gxr-curvature-runtime.log
adb pull /data/local/tmp/gxr-curvature-failure
adb pull /data/local/tmp/gxr-curvature-session-open
adb pull /data/local/tmp/gxr-window-diagnostics.txt
```

An absent failure file is normal. Check export timestamps before interpreting
saved copies. Logs can contain app/task identifiers. Use KernelSU GXR's planned
Soft restart for normal restarts. After an unexpected failure, switch the
module off and fully reboot before resetting its quarantine.

## Build

Requirements: Python with `frida==17.23.3`, Node 22, Java, ECJ 3.39.0,
Android SDK D8/R8 and an Android platform JAR. The validated host used WSL
and Android SDK 37. Set the tool paths for your machine:

```sh
python3 -m venv .build/venv
.build/venv/bin/pip install frida==17.23.3
GXR_ECJ=/path/to/ecj-3.39.0.jar
GXR_R8=/path/to/android-sdk/cmdline-tools/latest/lib/r8.jar
GXR_ANDROID_JAR=/path/to/android-sdk/platforms/android-37.0/android.jar
.build/venv/bin/python scripts/build-window-curvature-azj2.py \
  --integrated-borderless --integrated-rotation \
  --java /usr/bin/java --ecj "$GXR_ECJ" --r8 "$GXR_R8" \
  --android-jar "$GXR_ANDROID_JAR" \
  --cache .build/cache --output .build/output
```

The output is `gxr-window-curvature-0.1.30-azj2-disabled.zip`
and its `.sha256` sidecar. ECJ SHA-256:
`01f5a92ac19bb2b3bf85e295a68f2c73c264369109158b566ce9b490af982948`.
The builder fetches upstream commit
`dd1a8915e3bbb8ea44f99033c8bc0dc8fdc22bd2`, verifies Frida downloads, compiles
one helper DEX, and packages source, dependency receipts and runtime notices.
Bundled documentation and source receipts contribute to the ZIP checksum.
The experimental dispatch regression check also requires a host C compiler
(`cc`) with C11/GNU atomics and pthread support, available in the existing Linux
build toolchain and macOS command-line tools.

The build runs upstream policy/mesh and Java safety tests plus local checks
for node ownership, wrapper replacement, cleanup retry, heartbeat expiry,
rotation math, shared failure handling and competing-window-runtime guards.
The feature checks also exercise strict configuration parsing, persistent
flags, live rim/pill restoration, wrist quaternion composition, unique-hand
selection, invalid/stale OpenXR data and return to slider controls.
Recovery checks cover previous-boot archival, same-boot refusal, identity
validation, active runtimes, both integrity gates, disabled/removal markers,
duplicate starts and Action's start/export behavior.
The Linux restart test uses disposable processes and a fake injector to check
two complete handoffs, unchanged enabled state, replay rejection, changed
targets, missing cleanup acknowledgement and aborted/idle restarts. These
tests do not simulate the Android renderer or establish device compatibility.
Age-gate tests use a controlled uptime input to verify the wait, preserve the
unused authorization, and reject changed processes, generations and invalid
clock data before attachment.
The disabled-package verifier checks checksums, executable modes, ARM64/Dex
layout and all six firmware pins. The CMC patch is checked before applying
it and its exact hash is recorded in `build.json`.
