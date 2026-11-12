# Galaxy XR modules for AZJ2

KernelSU GXR modules for Samsung Galaxy XR SM-I610 running
`UML2.260301.001.I610UES3AZJ2` (Android 14). Maintained by
[booinspace](https://github.com/booinspace).

These are module ZIPs installed after temporary root is active. The separate
[Galaxy XR root project](https://github.com/booinspace/galaxyxr-root) supplies
DirtyFrag, KernelSU GXR and root instructions.

Download [Window Controls 0.1.26](https://github.com/booinspace/galaxyxr-modules/raw/refs/heads/main/releases/gxr-window-curvature-0.1.26-azj2-disabled.zip)
and its [checksum](releases/gxr-window-curvature-0.1.26-azj2-disabled.zip.sha256).
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
Enable the new version, tap Action and use one GXR Soft restart when requested.
The 0.1.25 → 0.1.26 installation completed without a full reboot; validation
of the replacement runtime after that restart is pending.
Updating from 0.1.24 or earlier can still require one final full reboot because
the old package's shutdown guard runs before replacement.

The combined build includes [boundary alignment](docs/BOUNDARY-ALIGNMENT.md)
by default. It uses the window's actual transform and keeps stock move events
and resize input intact.

| Module | What it does | Creator and source | Guide |
| --- | --- | --- | --- |
| Window controls | Curvature, white-rim removal, pill auto-hide, hand positional rotation in pitch/yaw/roll, aligned movement/resize boundaries, 10× movement distance, sliders, built-in recovery and planned Soft restart resume | Curvature by [BlueScorpioVR](https://github.com/BlueScorpioVR/galaxyxr-modules); AZJ2 integration, borderless, rotation, boundary alignment and recovery by [booinspace](https://github.com/booinspace); ART/CMC patch by [pandasauce](https://github.com/frida-packages/frida-java-bridge/pull/410) | [Install, use, build and recover](docs/CURVATURE.md) |
| Wear-aware display blanking | Development 0.2.0: panel off after 60 seconds without eyes while worn; 16 ms eye polling while blanked; keeps removal sleep | [booinspace](https://github.com/booinspace), using the stock AZJ2 wear, eye and display APIs | [Wear/display guide](modules/wear-dim/README.md) |
| Mic gain boost | Action UI with live 0–40 step gain control, global or Virtual Desktop-only scope, and a local 10-second recording/playback test | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port and Action UI by [booinspace](https://github.com/booinspace) | [Mic guide](modules/mic-gain-boost/README.md) |
| Passthrough anywhere | Toggles camera passthrough in an immersive app with a double-tap | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Passthrough guide](modules/passthrough-anywhere/README.md) |
| No low-light toast | Suppresses the low-light signal while retaining the dim-light pipeline | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Low-light guide](modules/no-lowlight-toast/README.md) |
| QuestLHSync alignment (experimental) | Aligns PC SteamVR Lighthouse devices with Galaxy XR over Virtual Desktop; does not inject native Home Space controllers | [stearnsbq](https://github.com/stearnsbq/questlhsync-galaxy-xr) and [CreoleVR](https://github.com/CreoleVR/QuestLHSync); AZJ2 build/lifecycle by [booinspace](https://github.com/booinspace) | [Lighthouse guide](modules/questlhsync/README.md) |
| Framebuffer10 (experimental) | Requests 10-bit SDR output with locally generated compositor shader corrections | [4uva4ek](https://github.com/4uva4ek/galaxyxr-modules/tree/main/modules/framebuffer10); AZJ2 port by [booinspace](https://github.com/booinspace) | [Colour output guide](modules/framebuffer10/README.md) |
| MV-HEVC eye fix (experimental) | Corrects left-primary spatial-video eye order in Gallery XR; does not change gaze tracking | [AngelDark92](https://github.com/AngelDark92), via [4uva4ek's repository](https://github.com/4uva4ek/galaxyxr-modules/tree/main/modules/mvhevc-eye-fix); AZJ2 lifecycle by [booinspace](https://github.com/booinspace) | [Video guide](modules/mvhevc-eye-fix/README.md) |
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

Install the combined Window Controls ZIP through **KernelSU GXR → Modules →
Install from storage**. Keep separate Borderless and Rotation modules off.
The combined module owns all window features through one injector, Java
bridge, menu layout and rollback supervisor.

After enabling it, tap the combined module's **Action** to start it. Planned
GXR Soft restarts use cleanup hooks and a single-use handoff to resume in the
new SystemUI process while keeping the module enabled. Automatic resume now
waits for a **90-second SystemUI process age**, then the usual **45-second**
Borderless delay. Allow up to **150 seconds** after Home Space returns, then
fully close and reopen an app window. The delay does not retrofit an already
restored window. The rim and resting pill hide; pointing at the top reveals
the pill and retains dragging. The app's top menu contains Curve/Flatten,
curvature strength, Pitch, Yaw, Roll and Reset rotation.

The current package is `gxr-window-curvature-0.1.26-azj2-disabled.zip`. The build
includes an ART/CMC bridge patch and checks the exact ART library hash before
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
- [Virtual Desktop Windows companion build](scripts/build-vd-eye-fix.ps1)
- [Sources, credits and licensing](docs/SOURCES.md)

The repository includes component sources and build inputs. Use the combined
window package for the supported curvature/borderless/rotation setup. Module
ZIPs install disabled and verify their payload and firmware before attaching.
A full reboot clears live in-process hooks; installed module files can remain.
