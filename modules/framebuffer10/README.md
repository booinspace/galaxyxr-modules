# Framebuffer10 for AZJ2

This is an AZJ2 build of [4uva4ek's Framebuffer10](https://github.com/4uva4ek/galaxyxr-modules/tree/9f096dfc79e72f180410bcfa5ba32b566734f62b/modules/framebuffer10).
It requests 10-bit **SDR** output and corrects the compositor's output encoding
to reduce gradient banding. Brightness, gamut and HDR-to-SDR tone mapping stay
unchanged. It does not add HDR or improve tracking.

The port targets only SM-I610 `I610UES3AZJ2`. Its Vulkan compositor differs
from AZF3, but regenerating all 553 shader changes on the exact AZJ2 library
produced the same project edit script. The new stock and result hashes are
pinned. No Samsung library is shipped: the module generates its private copy
from the installed original and verifies the result before use.

**Status:** native build and host lifecycle checks; all 553 modified shader
slots validated offline, with unflagged shaders, reflection and alpha tests
passing. 10-bit output and colour appearance still need a headset test.
The output can differ at translucent edges because separate layers blend
in encoded colour space. Start with a familiar scene and video.

## Install and use

1. Confirm AZJ2, regain temporary root, keep DirtyFrag Autorun off and check
   KernelSU GXR says **Working**.
2. Install `gxr-framebuffer10-azj2-0.1.0-disabled.zip`. Leave it disabled for
   the first preflight. The Action screen reports status; it does not start
   Android or enable the checkbox.
3. For a root-shell preflight, run
   `sh /data/adb/modules/gxr_framebuffer10/action.sh preflight` while Home
   Space is awake. This creates and validates the private colour library
   and checks the 8-bit baseline; it does not switch output.
4. Enable Framebuffer10 and use **one KernelSU GXR Soft restart**. The
   coordinator prepares the library while Android is stopped and starts
   Android once. Leave the headset awake through verification.
5. Check Action for `ENABLED`. Existing Window Controls still uses its own
   startup delay. Test camera passthrough, gradients, ordinary windows,
   video, curved windows, transparency and any SteamVR quad-view inset.

The package includes all four restart hooks. Its port prevents independent
recovery restarts while KernelSU owns a restart and handles the disabled
module's handoff through that coordinator. Same-boot failed sessions stay
quarantined; a changed full-boot ID permits previous-boot cleanup without
changing the checkbox.

## Remove or recover

Uncheck Framebuffer10 and use **one GXR Soft restart** to restore stock
output. Verify Action reports `GXR_UPDATE_STATE=STOCK`, then uninstall or
update. An immediate `off` request while a session exists deliberately
refuses replacement until that coordinated restart has finished. This avoids
an independent compositor restart interrupting the other window modules.

If a crash interrupts recovery, leave it off and fully reboot. A full boot
clears the live renderer, selectors and mounts. Temporary root must be
regained manually. A failed coordinated transaction may require that full
reboot rather than repeated Soft restarts.

## Build

Requirements: Python 3, Git and Android NDK **28.2.13676358**. The build
fetches the exact upstream commit if `--upstream` is omitted, or accepts a
clean local checkout at that commit:

```sh
python3 scripts/build-framebuffer10-azj2.py --ndk /path/to/android-ndk
```

For the Linux host checks, keep a clean checkout of the pinned upstream
revision and run `python3 tests/framebuffer10-port.test.py --upstream /path/to/checkout`.
This runs the upstream native and lifecycle simulations plus the AZJ2 restart
regression checks against the built ZIP. `--cxx` selects a host C++ compiler;
the build host uses GCC 14 because GCC 15 diagnoses the upstream command
wrapper's temporary vectors with `-Wfree-nonheap-object` under `-O2 -Werror`.
The Android binary is built with the pinned NDK Clang toolchain.

The reviewed upstream edit script SHA-256 is
`f9aef5110e1ea6acad72bfb20b36aab5668491d0666d3d3111d8b511c418668a`.
AZJ2 stock library SHA-256:
`bd51da246ce12452b0069f3fc35a24389b7705c33819e37ab1916c5a6b3e8cd7`.
Generated private library SHA-256:
`3869de4f1b2d46f607089486a3b35997b15ebff0be7b9082d6af6d2a2eb64caf`.

To repeat shader regeneration/validation, use the pinned upstream recipe
with these AZJ2 hashes and SPIRV-Tools **v2026.4** at
`ef96ed763b43b59b33b31b362f09a02b729fa1c9`, with SPIRV-Headers
`496543121ce6419f23d6fa5d7194ba66c36212d2`. The older SPIR-V tools bundled
in NDK 28/29 reject a shader capability in this library. This regeneration
is not needed for normal builds because the verified edit script is unchanged.
Keep both the stock and generated libraries private; do not commit them.

Original controller and colour recipe: **4uva4ek**. AZJ2 identity, packaging,
restart integration and build recipe: **booinspace**. Upstream's native and
NDK notices are retained. The pinned source has no explicit repository-wide
license; review upstream terms before redistributing its compiled controller.
