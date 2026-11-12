# Credits and provenance

These ports derive from
[BreadDoesStuff/galaxy-xr-modules](https://github.com/BreadDoesStuff/galaxy-xr-modules)
at commit `93dcf733068d0f57d53b21b79f37b1f38f573e6f`. Copyright (c) 2026
BreadDoesStuff. The upstream MIT license is included as `LICENSE.upstream`.
Upstream's README reports testing on AZF3; this branch targets AZJ2.

The original recording callback approach, codec control selection, passthrough
log observer, CPM calls, and task-focus listener came from BreadDoesStuff.
The AZJ2 port adds firmware guards, disabled installation, GXR lifecycle and
restart hooks, cooperative stop, rollback journals, validation and build tests.
Mic capture also checks the Virtual Desktop package. Passthrough requires an
observed SystemUI baseline and leaves broad toast suppression off by default.
The low-light port uses AZJ2's separate threshold instead of disabling the
whole sensor pipeline.

The 0.2.0 mic settings page, live gain changes and optional global recording
scope are by booinspace. The original callback/mixer approach remains credited
to BreadDoesStuff under the included MIT license.
The 0.2.1 recording helper and local playback controls are by booinspace,
using Android's public AudioRecord API. No recording is bundled or uploaded.

API verification used the user's stock AZJ2 framework/SystemUI and mixer XML.
Those proprietary binaries are not redistributed. Compile-only hidden API
stubs are included as source but excluded from the helper DEX. The Java/JDK,
Android platform JAR and D8/R8 are host build tools, not module payloads.
Each ZIP includes its sources, tool/source hashes, checksums and build receipt.
Compilation and signature checks do not certify runtime behavior or security.
