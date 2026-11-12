# Sources, credits and licensing

## Window controls

[BlueScorpioVR/galaxyxr-modules](https://github.com/BlueScorpioVR/galaxyxr-modules/tree/dd1a8915e3bbb8ea44f99033c8bc0dc8fdc22bd2/modules/window-curvature)
provides the curvature engine, native mesh hooks, supervised injector and
menu helper at commit `dd1a8915e3bbb8ea44f99033c8bc0dc8fdc22bd2`.
BlueScorpioVR designed and wrote that implementation.

The local integration supplies the AZJ2 firmware gate, shared borderless and
hover-caption hooks, pitch/yaw/roll helper, combined menu ownership and
coordinated cleanup, built-in previous-boot recovery, diagnostic export and
the module-side planned-restart handoff for KernelSU GXR's restart phases.
The borderless and rotation APIs were inspected in the
stock AZJ2 SystemUI and framework from the user's SM-I610. Proprietary
firmware binaries are not distributed in this repository.

The pinned upstream checkout has no top-level license. This repository
provides its build recipe and attribution; review upstream terms before
redistributing the compiled curvature package.

Runtime and build components:

- [Frida 17.23.3](https://github.com/frida/frida/releases/tag/17.23.3): the
  unmodified Android arm64 injector. Archive SHA-256:
  `fa27b0478fbe1909978388d606236008c40e19ffddcea3bca69a6ed54fde02dc`;
  ELF SHA-256:
  `bc4e1a0c7ede20af387e9e002a535cb3ff0072f523c460692820473b3f07e122`.
  Packages include its COPYING notice and LGPL 2.0-or-later text.
- [frida-java-bridge 7.0.13](https://www.npmjs.com/package/frida-java-bridge/v/7.0.13):
  bundled once in the shared agent, with its original archive and pinned
  SHA-512 recorded by the builder.
- [pandasauce's ART/CMC allocation patch](https://github.com/frida-packages/frida-java-bridge/pull/410),
  commit `fcdd7186467e8c6dfdcef888208807c9fc0424db`: keeps copied ArtMethods
  in ART's tracked LinearAlloc storage so CMC can update their class pointers.
  The combined build includes this open upstream patch with a local guard
  against a missing allocator. Patch SHA-256:
  `354bec3059c53cf9f83d3d8f3dcc81417654c0a2620bfac188c52e0092ba84bd`.
  Both the patch and original npm archive are included for source availability;
  the bridge's existing license remains applicable.
- [ECJ 3.39.0](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.39.0/)
  and [Android D8/R8](https://developer.android.com/tools/d8): host Java/DEX
  build tools. They are not installed on the headset.

## Window settings and wrist rotation

The Action settings page, wrist-grab integration and aligned movement/resize
boundaries are by [booinspace](https://github.com/booinspace). The native reader
observes the stock hand input event's full grip orientation and pinch state.
See the [OpenXR standard grip pose](https://registry.khronos.org/OpenXR/specs/1.1/html/xrspec.html)
for the hand-relative orientation convention. Its AZJ2 entry points and input
layout checks come from inspection of the exact pinned compositor image.
The [boundary implementation](BOUNDARY-ALIGNMENT.md) uses the exact AZJ2
UI renderer and point-conversion entry points. No compositor binary is included.

## BreadDoesStuff modules

The [mic gain](../modules/mic-gain-boost/),
[passthrough](../modules/passthrough-anywhere/) and
[low-light](../modules/no-lowlight-toast/) ports derive from
[BreadDoesStuff/galaxy-xr-modules](https://github.com/BreadDoesStuff/galaxy-xr-modules/tree/93dcf733068d0f57d53b21b79f37b1f38f573e6f),
commit `93dcf733068d0f57d53b21b79f37b1f38f573e6f`, copyright (c) 2026
BreadDoesStuff, under MIT. Each module retains its `LICENSE.upstream` and
`THIRD_PARTY.md`. The [port guide](BREAD-AZJ2.md) describes behavior,
compatibility checks and builds.

The mic Action UI, live settings and global recording scope in 0.2.0 are by
[booinspace](https://github.com/booinspace). The upstream MIT notices remain
included. The slider controls codec steps; acoustic dB gain is not calibrated.
The 0.2.1 user-initiated recording helper and local playback controls are also
by booinspace, using Android's public `AudioRecord` API. No audio is bundled
or uploaded, and no KernelSU Manager microphone permission is added.

## Lighthouse alignment and video ports

[stearnsbq/questlhsync-galaxy-xr](https://github.com/stearnsbq/questlhsync-galaxy-xr/tree/e0f476e00169744a201ea8656aef4dc266ca63fd),
commit `e0f476e00169744a201ea8656aef4dc266ca63fd`, supplies the Galaxy XR QVR
capture, factory calibration, exposure filter and settings page. It embeds
the observation server from [CreoleVR/QuestLHSync](https://github.com/CreoleVR/QuestLHSync).
Both MIT notices are retained, with the upstream source in the repository and
package. The AZJ2 port uses Android NDK 28.2/bionic, exact firmware/library
checks and a process-identity supervisor with coordinated restart hooks.
Those integration changes are by **booinspace**. No factory maps or headset
camera images are redistributed. This is PC alignment, not native Android
controller injection.

[4uva4ek/galaxyxr-modules](https://github.com/4uva4ek/galaxyxr-modules/tree/9f096dfc79e72f180410bcfa5ba32b566734f62b),
commit `9f096dfc79e72f180410bcfa5ba32b566734f62b`, supplies **4uva4ek's
Framebuffer10** controller/colour recipe and documents **AngelDark92's
MV-HEVC eye-order patches**. The build recipe fetches the pinned Framebuffer10
source and applies the AZJ2 identity and restart changes. It retains upstream
native/NDK notices. The MV-HEVC package uses a locally authored lifecycle
controller and the documented three patch sites. No proprietary stock or
modified Samsung library is shipped in either package. Both generate private
copies on the user's device and check the full result hashes.

The pinned 4uva4ek source has no explicit repository-wide license. Attribution
does not supply redistribution permission; review upstream terms before
redistributing its compiled Framebuffer10 controller. The repository keeps
the pinned fetch/build recipe rather than bulk-vendoring that source.
The OpenXR QUALITY investigation also references that pinned source; no
QUALITY binary is included.

Offline shader review used official
[SPIRV-Tools v2026.4](https://github.com/KhronosGroup/SPIRV-Tools/releases/tag/v2026.4),
commit `ef96ed763b43b59b33b31b362f09a02b729fa1c9`, and SPIRV-Headers
`496543121ce6419f23d6fa5d7194ba66c36212d2`. These are host validation tools,
not headset runtime dependencies.

## Virtual Desktop VRCFaceTracking companion

[SinonVT/GalaxyXR-EyeTracking-Fix-Virtual-Desktop](https://github.com/SinonVT/GalaxyXR-EyeTracking-Fix-Virtual-Desktop/tree/51a482cc2ce903fc51d238d55f561dbedcae767a),
commit `51a482cc2ce903fc51d238d55f561dbedcae767a`, supplies the direction-based
eye fix on top of **guygodin / Virtual Desktop, Inc.'s** MIT-licensed
VRCFaceTracking plugin. The original expression conversion credits regzo2's
QuestProOpenXR module. Sources and MIT license are retained under
`companions/vd-eye-fix`. **booinspace** added the build/test integration and
homogeneous quaternion maths for non-unit/invalid input. The hash-pinned Core
reference DLL is downloaded only for compilation and is not redistributed.
This companion runs on Windows; it has no Android firmware hooks.

## Root tools

The separate [Galaxy XR root project](https://git.puppy.boo/nathalie/galaxyxr-root)
credits DirtyFrag, KernelSU GXR and Samsung kernel sources. Root acquisition
is not bundled into these modules.

## Wear-aware display blanking and firmware hold

[Wear-aware display blanking](../modules/wear-dim/) is by
[booinspace](https://github.com/booinspace), using the existing local port
supervisor and inspection of stock AZJ2 `EyesMonitor`,
`ProximitySensorManager`, `CPM.SystemInputInfo` and Android display APIs.
The 0.2.0 helper uses Android 14's
[ISurfaceComposer display getters](https://android.googlesource.com/platform/frameworks/native/+/android-14.0.0_r1/libs/gui/aidl/android/gui/ISurfaceComposer.aidl)
and the stock `SurfaceControl.setDisplayPowerMode` method. The getters were
verified read-only on AZJ2. [scrcpy](https://github.com/Genymobile/scrcpy) was
also consulted for Android 14 display API access; its server-library loader
is not used here.
It adds no SystemUI injector and includes no proprietary firmware binaries.
The [firmware hold](FIRMWARE-HOLD.md) uses the device's existing package-manager
controls for the two verified Samsung OTA agents.
