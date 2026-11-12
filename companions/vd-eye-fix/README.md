# Virtual Desktop eye-gaze fix (Windows companion)

This is a Windows VRCFaceTracking plugin, **not a headset KernelSU module**.
It applies [SinonVT's direction-based gaze fix](https://github.com/SinonVT/GalaxyXR-EyeTracking-Fix-Virtual-Desktop)
to the [Virtual Desktop VRCFaceTracking plugin](https://github.com/guygodin/VirtualDesktop.VRCFaceTracking).
It avoids head-roll leaking into the avatar's gaze. It does not change the
Galaxy XR runtime or the headset's own tracking. No AZJ2 firmware offsets are used.

The booinspace integration retains the upstream `net7.0-windows` x64 plugin
interface and filename. It also fixes the upstream conversion's non-unit
quaternion handling: all direction terms now scale together, double
intermediates avoid float overflow, and invalid/zero input returns neutral gaze.
The new maths still needs a live VRCFaceTracking test on the user's headset.

## Install on the PC

1. Install the official Virtual Desktop module through VRCFaceTracking once,
   then close VRCFaceTracking completely.
2. Back up its existing `VirtualDesktop.FaceTracking.dll` from
   `%AppData%\VRCFaceTracking\CustomLibs\91a90618-b020-4064-8832-809b2ca2b3bc\`.
3. Copy the built DLL into that folder. Keep the exact filename
   **VirtualDesktop.FaceTracking.dll**. Do not install the ZIP in KernelSU.
4. If Windows blocks the downloaded DLL, unblock it in file Properties.
   Start VRCFaceTracking and Virtual Desktop (Streamer 1.30+ per upstream).
5. Test level, left-roll and right-roll head positions while looking up,
   down, left and right. Check both eyes and facial-expression tracking.

To roll back, close VRCFaceTracking and restore your backed-up DLL, or
reinstall its official Virtual Desktop module. Registry updates can replace
the fixed DLL, so keep a backup of this build too.

## Build

On Windows with .NET SDK 8 or later:

```powershell
powershell -NoProfile -File scripts/build-vd-eye-fix.ps1
```

The script downloads only the pinned, hash-verified compile-time Core DLL
from the SinonVT revision recorded in `UPSTREAM.json`. It builds the plugin
and runs gaze/roll/scaling and invalid-input tests against that reference.
The reference DLL is not included in the release. Output is
`releases/gxr-vd-eye-fix-0.1.0-windows.zip` and a SHA-256 sidecar.

Upstream code: Virtual Desktop, Inc./guygodin (MIT); gaze fix: SinonVT;
OpenXR expression conversion is credited upstream to regzo2's QuestProOpenXR
module. AZJ2 repository integration and numeric robustness changes:
[booinspace](https://github.com/booinspace). The MIT license is retained.
