# Galaxy XR modules for AZJ2

KernelSU GXR modules for Samsung Galaxy XR SM-I610 running
`UML2.260301.001.I610UES3AZJ2` (Android 14). Maintained by
[booinspace](https://github.com/booinspace).

These are module ZIPs installed after temporary root is active. The separate
[Galaxy XR root project](https://github.com/booinspace/galaxyxr-root) supplies
DirtyFrag, KernelSU GXR and root instructions.

Download the current ZIPs and checksum file from the
[AZJ2 modules release](https://github.com/booinspace/galaxyxr-modules/releases/tag/azj2-modules-2026.11.12).
The combined ZIP contains curvature, borderless windows and rotation.

Window Controls now includes **hand positional rotation**: grab a window to
move it and turn your hand to rotate it in pitch, yaw and roll. Action opens
settings for curvature, borderless windows, rotation and rotation while
grabbing. Grab rotation is off by default; the sliders remain available.
The user verified all three axes, retained orientation after release and
aligned app input on **0.1.18**. See
[feature settings and wrist grabs](docs/CURVATURE.md#feature-settings-and-wrist-grabs).

The local 0.1.19 development build also binds an existing window when its top
menu opens and adds grab diagnostics. That change still needs a device test;
it does not fix Samsung's untilted grab outline. Keep the working 0.1.18
installation while boundary alignment is investigated separately.

The separate [boundary experiment](docs/EXPERIMENTAL-BOUNDARY.md) makes
Samsung's movement outline follow the window transform. The user confirmed
that 0.1.22 aligns the outline and returns after a Soft restart, but resize
corners stop working when tilted and work again after Reset rotation.
The 0.1.23 candidate corrects the corner test's coordinate conversion. Its
host checks pass; rotated resizing still needs a headset test. The tested
0.1.18 package is preserved separately.

| Module | What it does | Creator and source | Guide |
| --- | --- | --- | --- |
| Window controls | Curvature, white-rim removal, pill auto-hide, hand positional rotation in pitch/yaw/roll, sliders, built-in recovery and planned Soft restart resume | Curvature by [BlueScorpioVR](https://github.com/BlueScorpioVR/galaxyxr-modules); AZJ2 integration, borderless, rotation and recovery by [booinspace](https://github.com/booinspace); ART/CMC patch by [pandasauce](https://github.com/frida-packages/frida-java-bridge/pull/410) | [Install, use, build and recover](docs/CURVATURE.md) |
| Wear-aware dimming | Dims after 60 seconds without detected eyes while worn; keeps proximity removal sleep | [booinspace](https://github.com/booinspace), using the stock AZJ2 wear and eye APIs | [Wear/dim guide](modules/wear-dim/README.md) |
| Mic gain boost | Adjusts microphone gain for selected recording modes | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Mic guide](modules/mic-gain-boost/README.md) |
| Passthrough anywhere | Toggles camera passthrough in an immersive app with a double-tap | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Passthrough guide](modules/passthrough-anywhere/README.md) |
| No low-light toast | Suppresses the low-light signal while retaining the dim-light pipeline | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Low-light guide](modules/no-lowlight-toast/README.md) |

The Window Controls runtime stayed enabled and resumed automatically after two
consecutive GXR Soft restarts on the AZJ2 headset. The second device test
confirmed curvature, rotation, rim/pill hiding, dragging and app input. The
90-second startup gate is a workaround; the native startup crash that prompted
it has not been fully diagnosed. Extended idle/wake stability remains
unverified. The user has also tested all three BreadDoesStuff ports and
wear-aware dimming on the AZJ2 headset and reports them working.

The experimental [wear-aware dimming module](modules/wear-dim/README.md) is a
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

The published baseline package is `Combined-0.1.15-booinspace.zip`. The build includes an
ART/CMC bridge patch and checks the exact ART library hash before attachment.
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
- [Sources, credits and licensing](docs/SOURCES.md)

The repository includes component sources and build inputs. Use the combined
window package for the supported curvature/borderless/rotation setup. Module
ZIPs install disabled and verify their payload and firmware before attaching.
A full reboot clears live in-process hooks; installed module files can remain.
