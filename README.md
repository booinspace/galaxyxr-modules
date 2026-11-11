# Galaxy XR modules for AZJ2

KernelSU GXR modules for Samsung Galaxy XR SM-I610 running
`UML2.260301.001.I610UES3AZJ2` (Android 14). Maintained by
[booinspace](https://github.com/booinspace).

These are module ZIPs installed after temporary root is active. The separate
[Galaxy XR root project](https://git.puppy.boo/nathalie/galaxyxr-root) supplies
DirtyFrag, KernelSU GXR and root instructions.

| Module | What it does | Creator and source | Guide |
| --- | --- | --- | --- |
| Window controls | Curvature, white-rim removal, pill auto-hide, and pitch/yaw/roll controls in one runtime | Curvature by [BlueScorpioVR](https://github.com/BlueScorpioVR/galaxyxr-modules); AZJ2 integration, borderless and rotation by [booinspace](https://github.com/booinspace) | [Install, use, build and recover](docs/CURVATURE.md) |
| Recovery | Exports window logs and acknowledges quarantine after a full reboot | [booinspace](https://github.com/booinspace) | [Recovery](docs/CURVATURE.md#recovery-and-logs) |
| Mic gain boost | Adjusts microphone gain for selected recording modes | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Mic guide](modules/mic-gain-boost/README.md) |
| Passthrough anywhere | Toggles camera passthrough in an immersive app with a double-tap | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Passthrough guide](modules/passthrough-anywhere/README.md) |
| No low-light toast | Suppresses the low-light signal while retaining the dim-light pipeline | [BreadDoesStuff](https://github.com/BreadDoesStuff/galaxy-xr-modules); AZJ2 port by [booinspace](https://github.com/booinspace) | [Low-light guide](modules/no-lowlight-toast/README.md) |

Window controls are confirmed working on the user's AZJ2 headset. The three
BreadDoesStuff ports have passed build and host checks; their individual
feature behavior still needs device validation.

## Window controls

Install the combined Window Controls ZIP through **KernelSU GXR → Modules →
Install from storage**. Keep separate Borderless and Rotation modules off.
The combined module owns all window features through one injector, Java
bridge, menu layout and rollback supervisor.

After enabling it, use one GXR **Soft restart**. Wait **45 seconds**, then
fully close and reopen an app window. The delay does not retrofit an already
restored window. The rim and resting pill hide; pointing at the top reveals
the pill and retains dragging. The app's top menu contains Curve/Flatten,
curvature strength, Pitch, Yaw, Roll and Reset rotation.

The tested package is `Combined-0.1.9-ROTATION.zip`, 25,439,558 bytes (25.44 MB),
SHA-256 `889e8fdae4977889092a459cc78adef0e39fb0f3186a8d8f3e514cbe17baf916`.
See the [window guide](docs/CURVATURE.md) for setup, limits and recovery.

## Build and source

- [Combined window build](scripts/build-window-curvature-azj2.py)
- [Shared borderless agent](scripts/curvature-borderless-agent.mjs)
- [Rotation helper source](modules/window-rotation/android/local/gxr/rotation/)
- [Recovery builder](scripts/build-curvature-recovery.py)
- [Bread ports and host checks](docs/BREAD-AZJ2.md)
- [Sources, credits and licensing](docs/SOURCES.md)

The repository includes component sources and build inputs. Use the combined
window package for the supported curvature/borderless/rotation setup. Module
ZIPs install disabled and verify their payload and firmware before attaching.
A full reboot clears live in-process hooks; installed module files can remain.
