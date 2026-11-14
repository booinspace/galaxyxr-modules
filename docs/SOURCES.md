# Sources, credits and licensing

## Quick Settings pinch

[booinspace](https://github.com/booinspace) wrote the left-pinch recognizer,
native UI-thread dispatch helper and settings integration. It invokes AZJ2's
existing taskbar Quick Settings action and reuses Window Controls' hand input
reader. Source under `modules/quick-settings-gesture/` is MIT licensed. No vendor
implementation is distributed. See the [shortcut guide](../modules/quick-settings-gesture/README.md).

## App audio mixer

[booinspace](https://github.com/booinspace) wrote the native volume-panel extension,
per-player attenuation ownership and host tests. New source under
`modules/audio-mixer/` is MIT licensed. It uses Android's playback callback and
`VolumeShaper` APIs; no Samsung or Google implementation source is copied or
packaged. It shares Window Controls' injector and dependency notices below.
See the [mixer guide](../modules/audio-mixer/README.md) for player limitations.

## OpenXR QUALITY

[4uva4ek](https://github.com/4uva4ek) authored the
[OpenXR QUALITY controller and Binder adapter](https://github.com/4uva4ek/galaxyxr-modules/tree/9f096dfc79e72f180410bcfa5ba32b566734f62b/modules/openxr-quality).
The AZJ2 recipe fetches that exact commit and applies a narrow policy-identity,
build-guard and metadata patch by [booinspace](https://github.com/booinspace).
Thermal policy, vendor ABI pins, guardian, cleanup and failure handling remain
upstream's implementation. No proprietary firmware or decompiled implementation
is published. The built ZIP retains upstream and Android NDK notices, plus the
port patch and build recipe. Upstream has no explicit repository-wide license;
its code is not relicensed by this collection.

## Wi-Fi ADB

[4uva4ek](https://github.com/4uva4ek) authored the
[Wi-Fi ADB module](https://github.com/4uva4ek/galaxyxr-modules/tree/9f096dfc79e72f180410bcfa5ba32b566734f62b/modules/wifi-adb).
The local recipe fetches commit `9f096dfc79e72f180410bcfa5ba32b566734f62b`,
runs its lifecycle tests and original builder, and copies the resulting 1.0.2
ZIP without modifying its bytes. The original module ID, author and update feed
remain intact. The recipe, collection docs and package checks are by
[booinspace](https://github.com/booinspace). No upstream runtime source is
vendored or rewritten for AZJ2. The owner confirmed that the packaged module
works on their AZJ2 headset; no other firmware was tested.
The pinned upstream has no explicit repository-wide license; its code is not
relicensed by this collection. Review upstream terms before redistributing
its generated ZIP.

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
- ART quick-code and JNI callback-lifetime guards by
  [booinspace](https://github.com/booinspace): suspend ART threads during
  entry-point writes/restoration and retain retired callbacks until script
  teardown. The exact local patch and original bridge archive are included.
  [Upstream race discussion](https://github.com/frida-packages/frida-java-bridge/pull/401)
  informed the investigation; this does not incorporate that entire proposal.
- The experimental candidate adapts
  [Kolektori's lock-free ART dispatch proposal](https://github.com/frida-packages/frida-java-bridge/pull/401),
  commit `dde975ddd6cc8ea8e8667d9a6f5629b22ff16a1c`. Local corrections by
  booinspace use atomic head publication and finish deletion snapshots before
  publishing them. The original bridge archive and complete modified patch are
  included under the bridge's existing license; this is an open upstream
  proposal, not an official released fix.
- [ECJ 3.39.0](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.39.0/)
  and [Android D8/R8](https://developer.android.com/tools/d8): host Java/DEX
  build tools. They are not installed on the headset.

## Window settings and wrist rotation

The opt-in [immersive app pins](IMMERSIVE-PINS.md) launcher, caption integration
and eye-fade helper are also by [booinspace](https://github.com/booinspace), as
are its gaze-coordinate conversion and scoped compositor brightness hook.
Their framework contracts and native eye-pose layout come from private inspection
of the exact AZJ2 firmware. No vendor implementation or firmware binary is included.
They share BlueScorpioVR's runtime and the dependency notices above.

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

## Root face tracking and Steam Link receivers

[compdoge/gxr-root-ft](https://github.com/compdoge/gxr-root-ft/tree/4d4dea8f7deacafc6859ab3d7cb98f513550402e),
commit `4d4dea8f7deacafc6859ab3d7cb98f513550402e` (1.4.0), supplies the MIT
root perception sender, gaze/pupil processing and tongue model. Pinned source,
MIT notice and original offline tests are retained under
`modules/root-face-tracking/upstream`. The separate AZJ2 patch isolates trace
buffers/events and rejects unverified offsets. The GXR lifecycle, exact library
gates, unicast-only settings, build and port checks are by **booinspace**.
The cgroup helper is adapted from compdoge's supervisor. No Samsung perception
library or captured biometric data is redistributed. See the
[port and validation limits](../modules/root-face-tracking/README.md).

[compdoge/VRCFT-ALVR-UE](https://github.com/compdoge/VRCFT-ALVR-UE/tree/4ef63fb3582edd261238fb9dab60da5aabbdbc84)
provides the 1.4.0 PC root receiver, derived from
[alvr-org/VRCFT-ALVR](https://github.com/alvr-org/VRCFT-ALVR), whose contributors
include zmerp and curoviyxru. [compdoge/LinkFT](https://github.com/compdoge/LinkFT/tree/36d8ae6979a16a593dac60140d108b7e55891e3f)
provides the dedicated Galaxy XR Steam Link receiver 1.0.1, based on
[Ykeara/LinkFT](https://github.com/Ykeara/LinkFT). The Windows installer downloads
their official release assets with pinned SHA-256 checks; receiver binaries
are not vendored in the companion source directory. Both keep upstream credit.

[compdoge/gxr-face-bridge](https://github.com/compdoge/gxr-face-bridge/tree/bce6c5ba89ac4fd892fd42dc30df2c1f23a246d4)
is the APK's OpenXR face/tongue bridge. The APK route and root relay are separate
tracking paths; the root module does not require the bridge to capture data.
[AngelDark92/GalaxyXR-Forge](https://github.com/AngelDark92/GalaxyXR-Forge)
indexes these projects. The
[PC companion guide](../companions/face-tracking/README.md) explains selection
and the difference between the two paths.

## Steam Link APK builder

[AngelDark92/xr-porting-hub](https://github.com/AngelDark92/xr-porting-hub)
supplies the patches, build catalogs and original-APK fallback links.
[compdoge/gxr-face-bridge](https://github.com/compdoge/gxr-face-bridge)
supplies the face/tongue layer embedded by those patches.
[MorpheApp/morphe-desktop](https://github.com/MorpheApp/morphe-desktop) supplies
the patch/rebuild/sign CLI; [SteamRE/DepotDownloader](https://github.com/SteamRE/DepotDownloader)
fetches Valve's original APK from the SteamVR content depot. The Windows/WSL
launcher, compatible-input selection, source/signature checks and signing-key
reuse are by **booinspace**. See the
[builder guide](../companions/steamlink/README.md) for requirements and evidence.

The script fetches official tool/patch releases and upstream-published APK
sources at run time. Downloaded code keeps its upstream license. This repository
ships no Steam Link APK, signing key or bundled copy of those tools in the
builder package. Each local build records the exact versions and hashes.
