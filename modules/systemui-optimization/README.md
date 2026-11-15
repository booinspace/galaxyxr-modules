# SystemUI Optimization for AZJ2

This is a standalone experimental port of
[4uva4ek's SystemUI Optimization v0.4.0](https://github.com/4uva4ek/galaxyxr-modules/releases/tag/systemui-optimization%2Fv0.4.0),
pinned to source commit `3ccf395bf12d0525c257d043568c7d7b4e4014a6`.
The module targets **SM-I610 / I610UES3AZJ2 / Android 14** and installs disabled.
Original work is by **4uva4ek**; the AZJ2 build, compatibility checks and
KernelSU GXR restart integration are by **booinspace**.

## What it changes

The helper patches private SystemUI memory in three places:

- Removes two outer swapchain waits after the inner acquire routine has already
  waited for the selected colour and depth images. The required waits remain.
- Releases and submits the depth swapchain selected for the current rendering
  mode, including the foveated case.
- Defers repeated enables of hidden system panels until their explicit owner
  decides visibility. New, stale, unknown or changed owners use stock behaviour.

This can reduce redundant rendering work and eliminate the observed duplicate-wait
errors. It does not change tracking algorithms, display resolution or refresh rate.
No original library, boot partition or kernel is rewritten.

## Upstream target and AZJ2 comparison

The comparison below uses the exact library hashes and patch signatures pinned
by upstream v0.4.0. It is not a comparison of complete AZF3 and AZJ2 firmware
images; the release does not identify every component's originating build.

| Component | Comparison with the upstream target | AZJ2 change |
| --- | --- | --- |
| Impress Vulkan library | Entire file is identical: SHA-256 `ab04d6da…` | Existing wait/depth functions and offsets retained |
| SpaceFlinger Vulkan library | Whole-file hash differs; both 32-byte hook signatures match at the original offsets | Exact AZJ2 hash gate and generated signatures |
| SystemUI Vulkan library | Whole-file hash differs; the panel-owner hook signature matches at its original offset | Exact AZJ2 hash gate and generated signatures |

The native helper still verifies live instructions, mapping permissions, owned
padding and process identity before applying or restoring patches. Finding matching
instructions alone does not prove a performance gain or correct behaviour in every
system dialog. Its existing rollback and same-boot failure guards remain active.

The port adds a native AZJ2 build check, a separate module ID
`gxr_systemui_optimization_azj2`, Linux/Fedora payload generation, and all four
coordinated GXR restart hooks. The upstream update URL is removed so an incompatible
package cannot silently replace this port. The original module must stay disabled.

The port also strengthens the frame hook: it saves all incoming general-purpose
registers and processor flags around the inserted C callback. Upstream saved only
`x0` and the return address there. The ARM64 regression deliberately clobbers
caller registers and flags, then verifies their restoration. This removes a
compiler-dependent preservation assumption; it is a correctness improvement,
not an additional measured CPU saving.

## Startup correction in AZJ2 revision 2

The first AZJ2 package could disable itself before patch activation when service
and restart-started launched workers together. Both entered the cold-boot guard;
the second interpreted the guard's busy result as a failure and wrote `disable`.
The exported headset log records that exact busy result. Revision 2 claims the
single-worker lock before entering the boot guard, so a duplicate request exits
without changing the checkbox. A genuine guard failure still disables startup.
Nine host scenarios cover this collision, cleanup and the existing failure paths.
The upstream native patch set remains v0.4.0. On the headset, revision 2 reported
ENABLED in the live AZJ2 SystemUI. Its supported Off action then reported DISABLED
and `GXR_UPDATE_STATE=STOCK` in the same process, while Window Controls remained
RUNNING. This checks activation and restoration in that session; it does not
establish a performance gain or cover every system dialog. Keep Optimization off
for the first passthrough-blend layout test.

## Install and use

1. Keep Window Controls on its known working version for the first optimization
   test. Disable any upstream SystemUI Optimization or standalone candidate.
2. Install `gxr-systemui-optimization-azj2-0.4.0-r2-disabled.zip` through KernelSU GXR.
   Installation leaves the checkbox off.
3. Enable it only for a deliberate test, then use one GXR Soft restart. Service
   startup waits for the coordinated restart to finish and for the checked native
   libraries to be mapped. **Action reports status; it does not enable the module.**
4. Check normal windows, Quick Settings, volume, notifications and system dialogs.
   Disable the module if anything behaves incorrectly.

Disabling asks the worker to restore and verify the original instructions.
`action.sh off` is also available through the module's installer/recovery contract.
An unexpected process exit or failed restoration blocks automatic retries in the
same kernel boot. If restoration cannot be confirmed, leave the module disabled
and fully reboot. Root remains temporary and must be restored separately.

## Build

Requires Python 3.10+, Git, Bash, Unicorn's Python package and **Android NDK
29.0.14206865**. Use private copies of these exact stock libraries from
`/system_ext/lib64/`:

| File | AZJ2 SHA-256 |
| --- | --- |
| `libImpress-jni-vulkan.so` | `ab04d6daf57800a42170febaf33cb128441339c06bd6d46f068c0109693fee42` |
| `libspaceflinger_jni_vulkan.so` | `8342a55dd62163af3653dcf2153a842e243377897ced3ca00703603d275a3d7f` |
| `libsysui_jni_soong_vulkan.so` | `f6e34cf42f704c5d3ced9cca18dd392abf4925cde9e30c3b752a34be4102a809` |

```sh
python3 -B scripts/build-systemui-optimization-azj2.py \
  --ndk "$HOME/Android/Sdk/ndk/29.0.14206865" \
  --libraries /path/to/private/AZJ2-libraries \
  --output .build/output/systemui-optimization
```

The builder fetches the pinned upstream source, applies the reviewed patch,
generates compatibility headers locally and runs lifecycle and ARM64 tests.
Generated vendor signatures and full stock libraries stay outside Git. The ZIP
contains the helper, its small compatibility signatures, notices and build receipt.

## Evaluation and further improvements

The upstream release reports 55.30% CPU before, 53.32% during and 59.64% after
one combined test, measured as a percentage of one core. This is limited evidence,
not a repeatable saving established for this AZJ2 port. CPU/GPU impact and broader
coexistence with the other modules still need device testing.

The useful next measurement is a matched before/during/after test with the same
workspace, headset wear state, frame rate and active apps. Check duplicate-wait
errors and real panel transitions alongside CPU and GPU frame timing. More
aggressive schema caching needs a reliable allocation-lifetime/invalidation
contract; caching vendor pointers without one is unsafe. It is not part of this
port. Removing additional validation or suppressing panels globally is not a
substitute for profiling the actual scene.

## Credits and source

- [4uva4ek's pinned module source](https://github.com/4uva4ek/galaxyxr-modules/tree/3ccf395bf12d0525c257d043568c7d7b4e4014a6/modules/systemui-optimization)
- [Upstream research and measurements](https://github.com/4uva4ek/galaxyxr-modules/blob/3ccf395bf12d0525c257d043568c7d7b4e4014a6/modules/systemui-optimization/RESEARCH.md)
- [Upstream native notice](https://github.com/4uva4ek/galaxyxr-modules/blob/3ccf395bf12d0525c257d043568c7d7b4e4014a6/modules/systemui-optimization/NATIVE-NOTICE.txt)

The pinned tag has no standalone LICENSE file. The build retains the upstream
notices and attribution; this repository's MIT license is not presented as a
license grant for that upstream code or the Samsung/Google libraries.
