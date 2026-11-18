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

## Passthrough blend

Window Controls 0.1.76 also exposes AZJ2's native dimmer slider in Quick Settings
for **Home Space camera/environment blending**. Move it to zero for the selected
Home environment, 100% for camera passthrough, or between them for a mixture.
With a black Home environment, an intermediate setting should darken the room
view while retaining the app windows. This rendering result still needs the
headset test; it has not been measured or visually confirmed.

The adapter updates the native Home passthrough alpha and keeps the Home
background active while both layers are needed. The corrected build supplies empty
update lists to the native transaction and reserves one full row in Quick Settings'
window, surface crop and XR visible bounds. Closing the panel and reopening it
does not add another row. Samsung's resource overlay anchors the media card
directly to brightness, so the adapter reconnects it below the blend slider
without a reverse constraint. Both original layout parameters and the original
panel size are restored when the module stops.
The blend row follows the native brightness row's visibility, so it stays hidden
while a detail or customization page is open. It leaves app-owned passthrough
and higher-priority safety or lockscreen states unchanged; the slider is disabled
there. Stopping Window Controls restores the original slider listener, visibility
and Home alpha. A five-second supervisor lease also releases the adapter after
a lost connection. There is no separate APK or additional injector.

Build this candidate with the normal tool arguments below and add
`--workspaces-host`. Its output is
`gxr-window-curvature-0.1.77-azj2-grab-sync-disabled.zip`. Test it before
enabling the separate SystemUI Optimization candidate, so the two changes can
be evaluated independently. The active Samsung overlay and the enlarged render
buffer were checked on the headset, and the owner confirmed that 0.1.76 installs.
The new media anchor, spacing and blend
rendering still need a headset check. Host tests cover copied layout parameters
and exact rollback, native widget reuse, user-only updates, Home-only composition,
critical/app-state isolation and cleanup.
They cannot establish camera compositing on the headset.

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
