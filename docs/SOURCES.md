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

The Action settings page and wrist-grab integration in development build
0.1.19 are by [booinspace](https://github.com/booinspace). The native reader
observes the stock hand input event's full grip orientation and pinch state.
See the [OpenXR standard grip pose](https://registry.khronos.org/OpenXR/specs/1.1/html/xrspec.html)
for the hand-relative orientation convention. Its AZJ2 entry points and input
layout checks come from inspection of the exact pinned compositor image.
No compositor binary is included.

## BreadDoesStuff modules

The [mic gain](../modules/mic-gain-boost/),
[passthrough](../modules/passthrough-anywhere/) and
[low-light](../modules/no-lowlight-toast/) ports derive from
[BreadDoesStuff/galaxy-xr-modules](https://github.com/BreadDoesStuff/galaxy-xr-modules/tree/93dcf733068d0f57d53b21b79f37b1f38f573e6f),
commit `93dcf733068d0f57d53b21b79f37b1f38f573e6f`, copyright (c) 2026
BreadDoesStuff, under MIT. Each module retains its `LICENSE.upstream` and
`THIRD_PARTY.md`. The [port guide](BREAD-AZJ2.md) describes behavior,
compatibility checks and builds.

## Root tools

The separate [Galaxy XR root project](https://git.puppy.boo/nathalie/galaxyxr-root)
credits DirtyFrag, KernelSU GXR and Samsung kernel sources. Root acquisition
is not bundled into these modules.

## Wear-aware dimming and firmware hold

[Wear-aware dimming](../modules/wear-dim/) is by
[booinspace](https://github.com/booinspace), using the existing local port
supervisor and inspection of stock AZJ2 `EyesMonitor`,
`ProximitySensorManager`, `CPM.SystemInputInfo` and DisplayManager APIs.
It adds no SystemUI injector and includes no proprietary firmware binaries.
The [firmware hold](FIRMWARE-HOLD.md) uses the device's existing package-manager
controls for the two verified Samsung OTA agents.
