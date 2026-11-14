# Left-pinch Quick Settings for AZJ2

This experimental Window Controls addition opens the headset's native Quick
Settings panel when you hold your left thumb and index finger together for half
a second. Release fully, then repeat to close it. An immediate-pinch option is
also available. Right-hand pinches do not trigger the shortcut.

The shortcut is **off by default**. In KernelSU GXR, open Window Controls' settings
page, find Quick Settings pinch, enable it and press Apply pinch shortcut. It
works independently of wrist-grab rotation. Settings persist in the module's
private `quick-settings-gesture.conf` file. The headset owner confirmed the left
pinch shortcut working on AZJ2.

## Behaviour in immersive apps

The implementation calls the same native action as the taskbar's Quick Settings
button. The inspected AZJ2 path shows a system panel in 3D space and does not
request Home Space or launch another app. It retains the native lockscreen check,
panel visibility state, controls and close behaviour. The native panel can dim
or temporarily take input focus from an immersive app while it is open.

**Immersive behaviour is not headset-verified.** We still need to check that
Quick Settings remains visible over Steam Link and that input returns after
closing it. This does not bypass provisioning, lockscreen or tracking-safety UI.

The shortcut observes the normal hand input; it does not consume or rewrite it.
A left pinch may still click or reach the app underneath. Use the half-second
hold to reduce accidental toggles and short pinches to operate Quick Settings.
Holding continuously toggles only once. Tracking loss requires a new tracked
release before rearming, and queued requests expire after 250 ms. Android must
report the display interactive before the native action is dispatched.

## Package and build

The source lives under `modules/quick-settings-gesture/` and
`scripts/curvature-quick-settings-agent.mjs`. It shares Window Controls' one
SystemUI injector, patched ART bridge, exact AZJ2 firmware pins and lifecycle.
It does not install another APK or a second injector. Disabling the shortcut
unsubscribes its hand reader and cancels queued requests. Wrist rotation keeps
its own subscription to the shared native hooks, and an already-open native panel
remains under normal system control.

The combined candidate is **0.1.68-azj2-quick-controls**, containing Audio Mixer
and this shortcut alongside the existing window features. Build it inside the
Linux/Fedora environment using the [shared requirements](../../docs/BUILDING.md):

```sh
.build/venv/bin/python -B scripts/build-quick-controls-azj2.py \
  --java /usr/bin/java \
  --ecj .build/tools/ecj-3.39.0.jar \
  --r8 "$HOME/Android/Sdk/cmdline-tools/latest/lib/r8.jar" \
  --android-jar "$HOME/Android/Sdk/platforms/android-37.0/android.jar" \
  --cache .build/cache --output .build/output
```

Output is `gxr-window-curvature-0.1.68-azj2-quick-controls-disabled.zip` with a
SHA-256 sidecar. It updates the existing `gxr_window_curvature` module and installs
disabled. Follow [Window Controls installation and recovery](../../docs/CURVATURE.md)
when testing an update. Local builds do not publish or alter the release feeds.

Local Node tests cover gesture timing, release/rearm, tracking loss, the shared
hand observer, settings UI and shutdown. Shell tests cover the root settings
boundary. The builder also runs a Java host test for UI-thread dispatch,
screen-off handling, stale requests and cancellation before compiling the DEX.
These checks do not replace testing the gesture and native panel on the headset.

## Credits

Gesture recognition, the shared hand reader, native dispatch helper and settings
are by [booinspace](https://github.com/booinspace). New source in this module is
MIT licensed. AZJ2 API names and layouts were checked against privately saved
firmware; no vendor implementation is copied or distributed.

This extends [BlueScorpioVR's Window Curvature runtime](https://github.com/BlueScorpioVR/galaxyxr-modules)
with the existing Frida/ART fixes. See [shared credits and licences](../../docs/SOURCES.md).
