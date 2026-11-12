# MV-HEVC video eye fix for AZJ2

This ports the patch documented by **AngelDark92** in
[4uva4ek/galaxyxr-modules](https://github.com/4uva4ek/galaxyxr-modules/tree/9f096dfc79e72f180410bcfa5ba32b566734f62b/modules/mvhevc-eye-fix).
It corrects Samsung Gallery XR's inverted eye order for **left-primary
MV-HEVC spatial video**. It is unrelated to eye tracking, avatar gaze or
controller tracking. The separate [SinonVT Windows plugin](../../companions/vd-eye-fix/)
addresses avatar gaze.

The two stock media libraries on the inspected AZJ2 headset are byte-identical
to the upstream-reviewed files. The port generates private copies locally,
checks the complete resulting hashes and bind-mounts only those copies. No
Samsung binary is distributed and no partition is written.

Status: generation checked against the actual AZJ2 libraries; synthetic
runtime tests cover apply, disable, partial-apply rollback and refusal to
detach another module's mount. Gallery playback still needs a headset test.
The third patch forces left-primary output: **right-primary content is not
supported by this build**.

## Install and use

1. Confirm SM-I610 `I610UES3AZJ2`, regain temporary root with DirtyFrag
   Autorun off, and check KernelSU GXR says **Working**.
2. Install `gxr-mvhevc-eye-fix-azj2-0.1.0-disabled.zip`; it arrives disabled.
3. Enable it and tap **Action**. It verifies the package and firmware,
   generates both libraries, starts its cleanup watcher and applies both
   mounts. Gallery XR is closed so reopening it loads the new copies.
4. Reopen a known left-primary MV-HEVC video in Gallery XR. Check depth and
   eye order. Action should report `ENABLED`. Other apps which previously
   loaded these libraries need to be closed and reopened too.

No Soft restart is needed for initial activation. All four GXR restart
hooks are included: cleanup precedes a planned restart and the service stage
reapplies only when the checkbox remains enabled. A cold boot clears mounts;
temporary root must be regained before the module can run again.

## Disable and remove

Uncheck the module and allow a few seconds for its watcher to restore the
original paths. Or, from a root shell:

```sh
sh /data/adb/modules/gxr_mvhevc_eye_fix/action.sh off
sh /data/adb/modules/gxr_mvhevc_eye_fix/action.sh status
```

Wait for `GXR_UPDATE_STATE=STOCK` before replacing or uninstalling. This
verifies the library paths and mount table; it does not inspect every running
process's already loaded mappings. Reopen affected apps after rollback.
If restoration is unverified, leave it disabled and fully reboot. Do not
stack another patch or bind mount on these two paths.

## Build and provenance

Only Python 3 is required to package this shell-based module:

```sh
python3 scripts/build-mvhevc-azj2.py
python3 tests/mvhevc-runtime.test.py
```

The Linux test uses synthetic libraries and fake mounts, never the headset.
The fixed patch facts come from upstream commit
`9f096dfc79e72f180410bcfa5ba32b566734f62b`:

| Library | Byte offset | Replacement |
| --- | --- | --- |
| libstagefright.so | 1817377 | `15` |
| libaplayer.so | 2309657 | `15` |
| libaplayer.so | 1005196 | `23 00 80 52` |

Stock and generated hashes are pinned in `control.sh`. Only one byte in
stagefright and five in aplayer differ. The AZJ2 lifecycle controller is by
**[booinspace](https://github.com/booinspace)**. It adds transactional apply,
mount-inode ownership, a watcher armed before either mount, global namespace
entry and restart hooks. The pinned upstream repository has no explicit
repository-wide license; its code is not bulk-vendored here. See
[sources and credits](../../docs/SOURCES.md).
