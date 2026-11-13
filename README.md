# Galaxy XR modules for AZJ2

KernelSU GXR modules for Samsung Galaxy XR SM-I610 running
`UML2.260301.001.I610UES3AZJ2` (Android 14). Maintained by
[booinspace](https://github.com/booinspace).

These are module ZIPs installed after temporary root is active. The separate
[Galaxy XR root project](https://github.com/booinspace/galaxyxr-root) supplies
DirtyFrag, KernelSU GXR and root instructions.

Download [Window Controls 0.1.60](releases/gxr-window-curvature-0.1.60-azj2-no-age-test-disabled.zip)
and its [checksum](releases/gxr-window-curvature-0.1.60-azj2-no-age-test-disabled.zip.sha256).
Other published module ZIPs are on the
[AZJ2 modules release](https://github.com/booinspace/galaxyxr-modules/releases/tag/azj2-modules-2026.11.12).

Window Controls now includes **hand positional rotation**: grab a window to
move it and turn your hand to rotate it in pitch, yaw and roll. Action opens
settings for curvature, borderless windows, rotation and rotation while
grabbing. Grab rotation is off by default; the sliders remain available.
The movement outline, resize corners and resize motion follow the rotated
window. The maximum movement distance is ten times the stock limit; the
near limit stays unchanged. The user confirmed extended reach and correct
outward/inward resizing while tilted on AZJ2. See
[feature settings and wrist grabs](docs/CURVATURE.md#feature-settings-and-wrist-grabs).

Updates stop the existing runtime cleanly before replacing the package.
Enable the new version and use one GXR Soft restart. The user confirmed the
0.1.30 update and automatic activation with Home and window features working
before opening Action. ADB verified the automatic-start version and live
process identity.
Updating from 0.1.24 or earlier can still require one final full reboot because
the old package's shutdown guard runs before replacement.

The combined build includes [boundary alignment](docs/BOUNDARY-ALIGNMENT.md)
by default. It uses the window's actual transform and keeps stock move events
and resize input intact.

Version **0.1.30** also raises Home's pin limit to 50. It keeps the
five-column tiles and panel size, adding vertical scrolling above 10 apps.
See the [Home pins guide](docs/HOME-PINS.md).
The 90-second startup-age check now covers ordinary starts as well as planned
restarts. A 0.1.26 crash occurred before that age; the native cause is unresolved.
The verified restart hook now queues startup directly, with the normal service
entry point as a fallback, so activation does not depend on opening Action.

| Module | What it does | Creator and source | Guide |
| --- | --- | --- | --- |
| Window controls | Curvature, white-rim removal, pill auto-hide, wrist rotation, aligned move/resize boundaries, 10× movement distance, sliders, 50 Home pins, and movable/resizable app pins over immersive apps with gaze fading and continued VR input | Curvature by [BlueScorpioVR](https://github.com/BlueScorpioVR/galaxyxr-modules); AZJ2 integration, borderless, rotation, app pins, Home pins and recovery by [booinspace](https://github.com/booinspace); ART/CMC patch by [pandasauce](https://github.com/frida-packages/frida-java-bridge/pull/410); dispatch patch based on [Kolektori's work](https://github.com/frida-packages/frida-java-bridge/pull/401) | [Install, use, build and recover](docs/CURVATURE.md) |
| Wear-aware display blanking | Development 0.2.0: panel off after 60 seconds without eyes while worn; 16 ms eye polling while blanked; keeps removal sleep | [booinspace](https://github.com/booinspace), using the stock AZJ2 wear, eye and display APIs | [Wear/display guide](modules/wear-dim/README.md) |
| Mic gain boost | Action UI with live 0–40 step gain control, global or Virtual Desktop-only scope, and a local 10-second recording/playback test | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port and Action UI by [booinspace](https://github.com/booinspace) | [Mic guide](modules/mic-gain-boost/README.md) |
| Passthrough anywhere | Toggles camera passthrough in an immersive app with a double-tap | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Passthrough guide](modules/passthrough-anywhere/README.md) |
| No low-light toast | Suppresses the low-light signal while retaining the dim-light pipeline | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Low-light guide](modules/no-lowlight-toast/README.md) |
| QuestLHSync alignment (experimental) | Aligns PC SteamVR Lighthouse devices with Galaxy XR over Virtual Desktop; does not inject native Home Space controllers | [stearnsbq](https://github.com/stearnsbq/questlhsync-galaxy-xr) and [CreoleVR](https://github.com/CreoleVR/QuestLHSync); AZJ2 build/lifecycle by [booinspace](https://github.com/booinspace) | [Lighthouse guide](modules/questlhsync/README.md) |
| Framebuffer10 (experimental) | Requests 10-bit SDR output with locally generated compositor shader corrections | [4uva4ek](https://github.com/4uva4ek/galaxyxr-modules/tree/main/modules/framebuffer10); AZJ2 port by [booinspace](https://github.com/booinspace) | [Colour output guide](modules/framebuffer10/README.md) |
| MV-HEVC eye fix (experimental) | Corrects left-primary spatial-video eye order in Gallery XR; does not change gaze tracking | [AngelDark92](https://github.com/AngelDark92), via [4uva4ek's repository](https://github.com/4uva4ek/galaxyxr-modules/tree/main/modules/mvhevc-eye-fix); AZJ2 lifecycle by [booinspace](https://github.com/booinspace) | [Video guide](modules/mvhevc-eye-fix/README.md) |
| Root face tracking (experimental) | Vendor perception relay for per-eye gaze, pupils, face and tongue; separate Windows receiver | [compdoge](https://github.com/compdoge/gxr-root-ft); AZJ2 trace isolation and lifecycle by [booinspace](https://github.com/booinspace) | [Headset guide](modules/root-face-tracking/README.md), [PC receivers](companions/face-tracking/README.md) |
| Virtual Desktop gaze fix (Windows companion) | VRCFaceTracking DLL correcting avatar gaze when the head rolls; install on the PC | [SinonVT](https://github.com/SinonVT/GalaxyXR-EyeTracking-Fix-Virtual-Desktop) and [guygodin](https://github.com/guygodin/VirtualDesktop.VRCFaceTracking); numeric fix/build by [booinspace](https://github.com/booinspace) | [PC install guide](companions/vd-eye-fix/README.md) |

The three new experimental headset ports have AZJ2 identity and host checks,
but have not been activated or tested on the headset. Install and test one at
a time; their guides distinguish build evidence from live behavior. The
Windows gaze fix passes 1,050 direction/roll/scale checks and invalid-input
checks, but still needs a live VRCFaceTracking test. These builds are separate
from the previously published release linked above.

The [OpenXR QUALITY investigation](docs/LIGHTHOUSE-AND-QUALITY.md#openxr-quality)
explains its conditional 60 FPS camera request and the changed AZJ2 policy
identity that blocks a direct install. No QUALITY build or native Home Space
Lighthouse bridge is included.

The Window Controls runtime stayed enabled and resumed automatically after two
consecutive GXR Soft restarts on the AZJ2 headset. The second device test
confirmed curvature, rotation, rim/pill hiding, dragging and app input. The
90-second startup gate is a workaround; the native startup crash that prompted
it has not been fully diagnosed. Extended idle/wake stability remains
unverified. The user has also tested all three BreadDoesStuff ports and
the earlier wear-aware dimming on AZJ2 and reports them working. The new
0.2.0 panel-blanking behavior and live/global mic controls require device
validation. The 16 ms eye-poll interval is not a measured display wake latency.

The experimental [wear-aware display module](modules/wear-dim/README.md) is a
standalone process. The [firmware hold guide](docs/FIRMWARE-HOLD.md)
records the reversible OTA-agent block applied to keep the headset on AZJ2.

## Window controls

Opt-in [immersive app pins](docs/IMMERSIVE-PINS.md), by booinspace,
adds a native overlay launcher and eye-driven fading to the combined runtime.
The user confirmed that 0.1.54 supports wrist rotation on ordinary windows before
opening their menus, rapid menu dismissal, and returning from Steam Link to pin
another app. Pinned apps support gaze fading, dragging, rotation and resizing,
with VRChat joystick forwarding while looking at the pin. Exported logs match
the live SystemUI identity and contain no fatal error or quarantine. The user
also confirmed that 0.1.56 removes the remaining immersive-view dimming while
retaining pin fading and joystick input.
Versions 0.1.39 and 0.1.40 contain a native brightness-helper lifetime bug and
must stay disabled. The current candidate retains native code/storage through
teardown and keeps VR focus separate from pin-pointer input. Version 0.1.56
also suppresses the renderer's separate fullscreen scrim while only owned pins
are visible over an immersive app. It keeps pin gaze fading and input routing
unchanged and reports the scrim's original alpha in diagnostics. The matching
device export records 3,784 suppressed positive-alpha scrim frames and no fatal
error. Extended idle/wake remains unverified.

Install the combined Window Controls ZIP through **KernelSU GXR → Modules →
Install from storage**. Keep separate Borderless and Rotation modules off.
The combined module owns all window features through one injector, Java
bridge, menu layout and rollback supervisor.

After enabling it, use one **KernelSU GXR Soft restart**. The module starts
automatically after cleanup hooks and a single-use handoff authorize the new
SystemUI process. Keep the module enabled for later Soft restarts. Startup
waits for a **90-second SystemUI process age** in the confirmed 0.1.56 build;
that ZIP has no additional Borderless delay. After it reaches RUNNING,
fully close and reopen an app window. The delay does not retrofit an already
restored window. The rim and resting pill hide; pointing at the top reveals
the pill and retains dragging. The app's top menu contains Curve/Flatten,
curvature strength, Pitch, Yaw, Roll and Reset rotation.

The confirmed package is `gxr-window-curvature-0.1.56-azj2-startup-test-disabled.zip`.
The separate 0.1.57 experiment removes the fixed age delay while retaining
readiness, firmware, identity and quarantine checks. Its automatic RUNNING report
matched the new live SystemUI before Action, at approximately 43 seconds of
process age, and the user confirmed working window controls. Cold-boot and
repeated early-start stability remain unverified; see the
[startup experiment](docs/CURVATURE.md#zero-age-startup-experiment).

Version 0.1.60 retains that startup path and addresses Android focus staying
on a pin after interaction. It returns focus to the unique visible immersive
task while retaining the pin's pointer path. It also hides system hand outlines
in immersive view until a pin needs interaction. The user confirmed both fixes
working on AZJ2. See [pin focus and hands](docs/IMMERSIVE-PINS.md#android-focus-and-hand-outlines).
The build includes an ART/CMC bridge patch and checks the exact ART library hash before
attachment.
Recovery is built in: after a cold boot, module startup preserves diagnostics
and acknowledges the previous boot's session automatically. **Action** starts
the enabled module if needed and exports logs. Same-boot quarantine stays
blocked unless a clean planned restart explicitly authorizes the replacement
SystemUI process. The module never enables its own checkbox.
See the [window guide](docs/CURVATURE.md) for setup, limits and recovery.

## Build and source

- [Combined window build](scripts/build-window-curvature-azj2.py)
- [Shared borderless agent](scripts/curvature-borderless-agent.mjs)
- [Rotation helper source](modules/window-rotation/android/local/gxr/rotation/)
- [Bread ports and host checks](docs/BREAD-AZJ2.md)
- [QuestLHSync AZJ2 build](scripts/build-questlhsync-azj2.py)
- [Framebuffer10 AZJ2 build](scripts/build-framebuffer10-azj2.py)
- [MV-HEVC AZJ2 packaging](scripts/build-mvhevc-azj2.py)
- [Root face tracking AZJ2 build](scripts/build-root-face-tracking-azj2.py)
- [Windows face tracking receiver installer](companions/face-tracking/README.md)
- [One-click Steam Link APK builder for Windows](companions/steamlink/README.md)
- [Virtual Desktop Windows companion build](scripts/build-vd-eye-fix.ps1)
- [Sources, credits and licensing](docs/SOURCES.md)

The repository includes component sources and build inputs. Use the combined
window package for the supported curvature/borderless/rotation setup. Module
ZIPs install disabled and verify their payload and firmware before attaching.
A full reboot clears live in-process hooks; installed module files can remain.
