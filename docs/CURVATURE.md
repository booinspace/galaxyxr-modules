# Window controls for Galaxy XR AZJ2

The combined module adds curvature, borderless app windows, a hover-only
caption pill, and pitch/yaw/roll controls to ordinary Home Space Android
windows. It uses one supervised Frida injector and one Java-owned menu.
The user confirmed the combined features work on the AZJ2 headset.

This is a **KernelSU GXR module ZIP**. It requires an active temporary root
session; it is not an APK or a kernel LKM. Keep DirtyFrag **Autorun off**.

## Install

1. Confirm KernelSU GXR reports **Working**. Keep separate Borderless and
   Rotation modules off. If updating an active window runtime, switch it off,
   fully reboot, regain temporary root and run Recovery to acknowledge any
   quarantine first.
2. In **Modules → Install from storage**, choose the combined ZIP. It installs
   disabled. Use an in-place update; if the existing module is pending
   deletion, tap **Undo**, leave it off, then retry installation.
3. Enable **Galaxy XR Curvature + Borderless + Rotation** and use one GXR
   **Soft restart** to dispatch services.
4. Wait **45 seconds**, fully close an ordinary app window and launch it again.
   A window restored before the Borderless delay can keep its decorations.
   Reopening only its top menu does not recreate the window.

The verified headset copy is `/sdcard/Download/Combined-0.1.9-ROTATION.zip`,
25,439,558 bytes (25.44 MB), SHA-256
`889e8fdae4977889092a459cc78adef0e39fb0f3186a8d8f3e514cbe17baf916`.

## Use

- Open the window's top menu for **Curve/Flatten** and its strength slider.
- Use **Pitch**, **Yaw** and **Roll** sliders to change local orientation;
  the angle applies when released. **Reset rotation** restores the window's
  stock local orientation. Start with a small angle before trying side-lying
  roll angles.
- Point at the top caption area to reveal the pill. Moving away hides it after
  half a second. The caption parent and touch handler remain available for
  stock window dragging.
- Stock hand dragging positions the window. Rotation uses the menu controls;
  direct hand-grab rotation is not implemented.

Settings belong to each live window and are not saved across SystemUI restart
or window recreation. The module does not remove an app's own letterboxing.
Pitch and yaw can make a panel edge-on or turn it away from you.

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

The module refuses mismatches. A firmware update requires inspection and a
new build. No stock APK or native library is replaced.

Curvature uses the pinned BlueScorpioVR native hooks and helper. Borderless
suppresses task window rims through `CPM.NodeUpdates` and keeps the caption's
layout and input target. Rotation changes the same task node's orientation
through the stock quaternion API. Owned node references use scene-node
identity, so stock wrapper closure does not invalidate rollback.

Curvature owns the combined menu's size, surface crop and dismissal. The
common heartbeat supplies Home Space eligibility and waits for curvature,
orientation and caption cleanup before detaching. Separate window runtimes
and competing injectors are rejected before attachment.

The intended scope is ordinary 2D Home Space windows. Other firmware,
immersive/system window behavior, extended stability and every app's input
alignment have not been established. The flat resize outline remains a
renderer limitation.

## Recovery and logs

Switch the window module off to request cleanup. The supervisor reports its
state through **Action** and keeps quarantine markers when restoration is
unverified. Because stock rim restoration requires process recreation, fully
reboot with DirtyFrag Autorun off before resetting or replacing the runtime.

Install `releases/gxr-curvature-recovery-0.1.2-disabled.zip` through KernelSU
GXR, then enable Recovery so its **Action** button is available. Recovery's
startup scripts do not attach to SystemUI. After a full reboot, regain root,
leave the window module off and run **Recovery → Action**. Quarantine can only
be acknowledged after the full boot ID changes; Soft restart does not change
that ID.

Recovery also exports logs. If used while the window module is running, it can
print **Disable curvature before reset** after copying them; that message
concerns resetting quarantine. The exported files can be collected over ADB:

```sh
adb pull /data/local/tmp/gxr-curvature-runtime.log
adb pull /data/local/tmp/gxr-curvature-failure
adb pull /data/local/tmp/gxr-curvature-session-open
```

An absent failure file is normal. Check export timestamps before interpreting
saved copies. Logs can contain app/task identifiers. Avoid another Soft
restart while the window runtime is attached; stop it and follow the full
reboot/reset procedure instead.

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

The output is `gxr-window-curvature-0.1.9-azj2-experimental-disabled.zip`
and its `.sha256` sidecar. ECJ SHA-256:
`01f5a92ac19bb2b3bf85e295a68f2c73c264369109158b566ce9b490af982948`.
The builder fetches upstream commit
`dd1a8915e3bbb8ea44f99033c8bc0dc8fdc22bd2`, verifies Frida downloads, compiles
one helper DEX, and packages source, dependency receipts and runtime notices.
Bundled documentation and source receipts contribute to the ZIP checksum.

The build runs upstream policy/mesh and Java safety tests plus local checks
for node ownership, wrapper replacement, cleanup retry, heartbeat expiry,
rotation math, shared failure handling and competing-window-runtime guards.
The disabled-package verifier checks checksums, executable modes, ARM64/Dex
layout and all four firmware pins.

Build Recovery with `python3 scripts/build-curvature-recovery.py` and run its
host check with `python3 tests/curvature-recovery.test.py`.
