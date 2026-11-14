# OpenXR QUALITY for AZJ2

Experimental AZJ2 port of [4uva4ek's OpenXR QUALITY](https://github.com/4uva4ek/galaxyxr-modules/tree/9f096dfc79e72f180410bcfa5ba32b566734f62b/modules/openxr-quality),
by [booinspace](https://github.com/booinspace). Target: **Samsung SM-I610**,
`UML2.260301.001.I610UES3AZJ2`, Android 14. Port version **0.1.2-azj2**.

The module holds the vendor HEAD_TRACKING QUALITY request while an OpenXR app
is visible and the headset is awake. Controllers are not required. QUALITY
requests camera minimum/maximum 60/60 FPS; EFFICIENCY requests 30/60. Requested
rates do not establish actual camera rate, tracking accuracy or display FPS.
This does not add prediction or specifically change hand/finger tracking.

App exit, minimization and sleep release the override. Thermal severity 4
releases it; resumption requires severity 2 or lower. The stock reduction at
severity 3 is deliberately overridden while active. CPU/GPU thermal controls
remain active. Power use and heat may increase. Upstream's controller, guardian,
cleanup, process identity, failure guards and verified late-load gate are retained.

## What changed for AZJ2

The original build installs on AZJ2 but rejects its framework policy hash at
activation. This port changes the accepted `services.jar` SHA-256 to
`ca2d7cdb6a549b7bdbef2c0ef1cab025b2b058f724fc4710911aedb7b9e71555`
and adds the exact build check above. Model, perception-host, Binder-library,
thermal-overlay and vendor-command checks remain intact. No identity check is
removed or weakened. The [patch](azj2.patch) shows the complete source change.

Private inspection of AZJ2's `PerceptionPerformanceService` confirmed HEAD_TRACKING
service `(1,1)`, QUALITY/EFFICIENCY modes 1/2, thermal trigger/release policy and
battery-saver policy. The saved perception host and live Binder hashes match
upstream. The controller also checks the expected 3/2/true overlays at runtime.
No Samsung framework, native library or decompiled source is distributed.

The module keeps `gxr_openxr_quality` so it updates the existing installation.
Its version code is 3, above upstream 0.1.1's 2. The AZF3 update feed is removed
from this local port so it cannot replace the AZJ2 binary automatically.

## Install and test

The ZIP is `gxr-openxr-quality-azj2-0.1.2-disabled.zip`. It installs disabled.

1. Keep the failed upstream QUALITY module off. Since it failed in this kernel
   boot, fully reboot the headset before testing the replacement. A Soft restart
   alone cannot clear its same-boot failure guard.
2. Regain temporary root with DirtyFrag Autorun off. Install this ZIP as an
   update in KernelSU GXR; leave it disabled until installation completes.
3. Enable QUALITY, then use one KernelSU GXR Soft restart. The retained startup
   gate requires verified late-load root and a completed restart generation.
4. Keep the headset awake and enter immersive Steam Link or another OpenXR app.
   Open QUALITY's Action report. Expect `QUALITY held for <package>` when active;
   a waiting report means ordinary policy is active. Home Space alone does not qualify.
5. Minimize/exit the app and check that it releases the override. A status report
   confirms the controller's own state, not an independent measurement of camera FPS.

Action reports only; it does not start the module. Existing failure markers are
preserved during an update. The next full-boot startup handles previous-boot
guards using upstream's existing logic. Do not delete guards to retry in place.

If a check fails, leave the module off and save the Action output. The upstream
root-terminal stop command is `sh /data/adb/modules/gxr_openxr_quality/action.sh off`.
If cleanup cannot be verified, keep it off and fully power-cycle the headset.

## Build and checks

Use Linux/WSL with Python 3, Git, a host C++17 compiler and Android NDK
**28.2.13676358**. No Samsung kernel build or Java SDK is needed:

```sh
python3 scripts/build-openxr-quality-azj2.py --ndk /path/to/ndk/28.2.13676358
python3 tests/openxr-quality-port.test.py
```

The builder fetches upstream commit `9f096dfc79e72f180410bcfa5ba32b566734f62b`,
exports committed files, checks/applies the patch and runs upstream's gate,
restoration/update and native policy tests. The native policy tests use synthetic
CPM fixtures. `--upstream /path/to/cached/repo` avoids another fetch of the same
commit. `--output` selects a different local output directory.

The original upstream builder compiles ARM64 API 30 code with the NDK and retains
its notices. Local packaging adds the exact patch, build recipe, receipt and this
guide under `bin/source/`, then verifies executable permissions, firmware guards
and every payload checksum. ZIPs and checksum sidecars go to ignored `releases/`.
Only source, patches and documentation belong in Git; published binaries belong
in GitHub Releases.

Host tests and package checks establish build integrity. Live acquire/release,
restart behaviour, camera rates and any tracking improvement still need device
validation. Copying the ZIP to the headset does not activate it.

## Credits

Original controller, Binder adapter and lifecycle: **4uva4ek**. AZJ2 policy review,
target guard, build recipe and package checks: **booinspace**. Upstream has no
explicit repository-wide license; this collection does not relicense its code.
Upstream and Android NDK notices remain in the built package.
