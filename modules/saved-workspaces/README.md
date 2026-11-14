# Saved Workspaces for Galaxy XR

Saved Workspaces adds a row of scene previews above the native Recent apps list.
Cinema, Desk and VRChat are separate layouts you can switch between. Layouts return
in front of where you are facing, rather than to fixed points in the room.

This is a standalone experimental KernelSU GXR module for **SM-I610 / I610UES3AZJ2**.
It requires **Window Controls 0.1.70 or later** for its native SystemUI adapter.
There is one SystemUI injector, owned by Window Controls. Disabling Saved
Workspaces removes its Recents strip and tracking without stopping Window Controls.

## Install and first test

1. Keep a copy of your working Window Controls ZIP. Close pinned windows and
   switch Window Controls off before updating it to the supplied 0.1.70 host build.
   Use the existing Window Controls update/recovery procedure; leave DirtyFrag
   Autorun off. Do not reset a crash quarantine in the same full boot.
2. Enable Window Controls and verify its ordinary window controls first.
3. Install `gxr-saved-workspaces-azj2-0.1.2-disabled.zip`. It installs disabled.
   Enable it and tap Action to start its root worker. No extra restart is needed.
4. Close and reopen Recent apps using the normal right-pinch gesture. Confirm
   the one-time setup message before switching layouts. Desk initially adopts
   your current windows; Cinema and VRChat start empty.
5. Start with disposable app windows. Open and position two apps, open Recents,
   then select Cinema. Open another app there and switch back to Desk. Check
   positions, sizes, rotation, curvature and pins before relying on saved scenes.

Tap a preview to select a workspace. **New** creates an empty workspace; select
its card to enter it. Hold a card to rename or delete it. Switch away from a
workspace before deleting its saved layout. **Save layout** saves the current
scene immediately; it also saves automatically every ten seconds and before a
switch. The current card is outlined and labelled.
The workspace controls use the native app-suggestions row’s centered width, with
extra workspace cards available by scrolling sideways.

## Switching behavior

The module saves the outgoing layout before changing any windows. It pauses media
from apps absent from the destination, closes their windows, reuses common apps
and opens missing apps. A change between an ordinary window and a pinned window
reopens that app. Normal windows are positioned before the destination immersive
app is brought forward. A shared immersive task is brought forward without
removing and relaunching its task.

Saved data includes launch activity, native window placement and size, custom
rotation, curvature, pin mode and user-minimized state. A new preview is captured
after a workspace opens, with Recents hidden. Protected content may be blank.
Previews are never uploaded and are not written to shared storage.

Closing a window can discard unsaved app work. Apps reopen through their normal
launcher: this does not restore a document, playback timestamp, login, network
session or Steam Link connection. Shared apps retain their existing app state.
Paused media is not automatically resumed when returning to a workspace.

Window readiness has no fixed launch deadline: slow apps keep opening, and an
immersive app’s 2D connection screen counts as a valid launch stage. Its SteamVR
or network connection continues inside the app. All normal destination launches
are submitted before waiting for their layouts. **Stop waiting** pauses a pending
switch without closing its apps; retry by selecting its card. Startup failures
never automatically switch back or reopen the previous scene. Missing/changed
launchers still fail preflight before any windows are closed.

The first version supports eight workspaces with up to sixteen windows each and
one launcher window per app. Duplicate app windows make saving fail with a message
instead of silently losing a window. A minimized window whose transform has never
been observed must be restored once before it can be saved. Layouts need Rotation
or Curvature enabled in Window Controls when their saved values use those features.

## Stop, recovery and data

Turn Saved Workspaces off to remove the strip. The current app windows stay open.
The root worker and native UI use independent heartbeat checks. Coordinated GXR
restart hooks stop the worker and reconnect it after Window Controls returns.
Root itself remains temporary and must be restored after a full reboot.

Saved layouts survive a module restart, but the module does not automatically
close or relaunch apps on startup. Select a workspace to restore it. Before that
first switch, it preserves the current Android scene as a recovery snapshot
without overwriting an existing saved preset.

An interrupted switch leaves a journal and the saved previous workspace. The
strip marks the destination as unfinished. Opened apps stay in place. Select
that card to retry, or choose another workspace; it never switches back
automatically. A checksum error stops
loading the affected data instead of resetting it. Logs appear in the module
Action and `GxrWorkspaces` logcat entries. Saved layouts, previews and the recovery
snapshot live in SystemUI's private `files/booinspace-workspaces` directory; they
are not included in the public build. Uninstalling the module deliberately leaves
this data intact. Clearing SystemUI's app data can erase it.

## Build and evidence

Build on Linux/Fedora with JDK, Android SDK, R8 and Node.js:

```sh
python3 -B scripts/build-saved-workspaces-azj2.py \
  --java "$(command -v java)" --javac "$(command -v javac)" \
  --r8 "$HOME/Android/Sdk/cmdline-tools/latest/lib/r8.jar" \
  --android-jar "$HOME/Android/Sdk/platforms/android-37.0/android.jar" \
  --output .build/output
```

Build its Window Controls adapter with the normal `build-quick-controls-azj2.py`
command plus `--workspaces-host`. Both builders retain firmware checks and produce
disabled ZIPs with checksum sidecars. No Samsung or Google source/APK is bundled.

Portable tests exercise layout math, persistence/corruption handling, preflight,
shared apps, media selection, slow startup, interrupted switches and manual retry. Transport tests
check size limits, session matching, expiry and isolation from the parent runtime.
Android compilation checks API use. A disposable invisible-node probe on AZJ2
confirmed facing-relative transform capture and explicit-matrix round-tripping;
it did not move or close apps. The native Recents strip, saved previews and Steam Link workspace switching have
been confirmed on AZJ2. The captured helper load completed in 93 ms, with both
modules running. **Stop waiting, manual retry and full multi-app geometry still
need further headset testing.**

## Credits

Workspace implementation by [booinspace](https://github.com/booinspace), under the
included MIT license. Its optional host uses the existing Window Controls port of
[BlueScorpioVR's window-curvature module](https://github.com/BlueScorpioVR/galaxyxr-modules),
with [Frida](https://github.com/frida/frida) and the bridge corrections credited in
this repository's [sources guide](https://github.com/booinspace/galaxyxr-modules/blob/main/docs/SOURCES.md).
The workspace worker reuses this repository's cooperative port runtime. Stock
Android XR behavior was inspected locally; proprietary decompiled code is not
included in this module.
