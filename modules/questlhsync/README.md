# QuestLHSync Lighthouse alignment for AZJ2

This ports [stearnsbq's Galaxy XR camera bridge](https://github.com/stearnsbq/questlhsync-galaxy-xr)
to SM-I610 `I610UES3AZJ2`. It supplies tracking-camera observations to
[CreoleVR's QuestLHSync](https://github.com/CreoleVR/QuestLHSync) on the PC so
SteamVR can align Lighthouse devices with the headset over Virtual Desktop.
Index controllers, Tundra trackers and Vive Tracker 3.0 remain connected to
the PC through their USB dongles. Their existing SteamVR drivers do the tracking.

**This does not add native Home Space controller input.** There is no incoming
controller pose/button path in this module. See the
[native-input investigation](../../docs/LIGHTHOUSE-AND-QUALITY.md).

Status: the exact AZJ2 camera, camera-service, calibration-plugin and perception
host hashes match the upstream-supported build. The port compiles for arm64;
exposure, supervisor and package checks pass on the build host. Live camera
capture, alignment accuracy and simultaneous use with the other headset
modules still need testing. `RUNNING` means the service is ready, not that
SteamVR has acquired an alignment lock.

## Install

Use **0.1.1** or later. Version 0.1.0 kept the upstream module ID
`questlhsync_gxr`, which selected KernelSU's legacy installer. That removed
the README required by the checksum manifest and cleared the native helpers'
executable permissions. The resulting `Payload checksum mismatch` happens
before factory calibration or camera capture, so rebooting cannot repair it.
The corrected ID is `gxr_questlhsync`; its WebUI uses the same corrected path.
Native helpers now live under `bin/`, where the GXR installer grants executable
permissions. The pinned upstream native sources remain unchanged.

1. Install the PC driver from the official
   [QuestLHSync v1.28 release](https://github.com/CreoleVR/QuestLHSync/releases/tag/v1.28),
   which includes Galaxy XR support. Restart SteamVR as its guide requests.
   Disable other simultaneous alignment tools such as SpaceCalibrator or
   OpenVR-SpaceSync. Keep the Index and tracker dongles on the PC.
2. On AZJ2, regain temporary root with DirtyFrag Autorun off. Check KernelSU
   GXR says **Working**. If 0.1.0 is installed, switch it off and uninstall it;
   keep it off if removal is pending. Install
   `gxr-questlhsync-azj2-0.1.1-disabled.zip`. This is a new module identity,
   rather than an update to 0.1.0, and it arrives disabled. Keep only the
   corrected module enabled. Do not enable the original AZF3 module alongside it.
3. Enable this module and tap **Action**. Factory calibration is generated
   privately on the headset; no manual map or calibration download is needed.
   Action reports service status and exports its log. A full Android restart
   is not required for this first start.
4. Connect Virtual Desktop to SteamVR on the same trusted LAN. Follow the PC
   driver's alignment instructions with the Lighthouse devices visible to
   their base stations. Test one controller first, then the remaining devices.
   Check the PC driver's lock indication and alignment while moving.

KernelSU's WebUI opens the upstream exposure-cutoff settings. The default
10 ms cutoff **filters** incoming frames; it does not set camera exposure.
Lower cutoffs can reduce motion blur but can also reject every frame. Start
with the default. `exposure_rejected` increasing without observations points
to this filter; `empty_frames` increasing instead calls for checking lighting,
visibility and detection. Neither counter proves an alignment lock.

The upstream [camera discussion](https://github.com/stearnsbq/questlhsync-galaxy-xr/issues/2)
reports short-exposure frame-pattern work in a separate port. This build
retains stearnsbq's camera behavior and does not enable that unverified setter.
Hands-only operation with Index controllers may therefore need exposure and
motion testing even though the firmware identities match.

## Stop and recover

Uncheck the module. Its supervisor stops its own daemon/camera process group
and verifies cleanup. A root shell can also run:

```sh
sh /data/adb/modules/gxr_questlhsync/action.sh off
sh /data/adb/modules/gxr_questlhsync/action.sh status
```

Wait for `GXR_UPDATE_STATE=STOCK` before updating or uninstalling. If cleanup
or process ownership cannot be verified, leave it off and fully reboot rather
than repeatedly restarting it. An unexpected stop disables the module and
blocks another attempt in the same full boot. After a full reboot, regain
temporary root, review the log, then enable it manually. Planned GXR Soft
restarts use all four cleanup/resume hooks and preserve the checkbox.

Action exports service logs to `/data/local/tmp/questlhsync-gxr-service.log`.
Factory maps stay in `/dev/questlhsync-gxr/calibration`; persistent numeric
settings and a random discovery ID stay in `/data/adb/questlhsync-gxr`.
No factory calibration or camera images are included in this repository.

The service uses **unauthenticated TCP 47280 and UDP 47281**. Use a trusted
LAN and do not forward those ports to the internet. It sends observations
and calibration, rather than camera images.

## Build and credits

With Python 3 and Android NDK **28.2.13676358**:

```sh
python3 scripts/build-questlhsync-azj2.py --ndk /path/to/android-ndk
python3 tests/port-package.test.py
python3 tests/questlhsync-package.test.py
python3 tests/questlhsync-lifecycle.test.py
```

The Linux lifecycle test uses fake native children and camera effects; it
does not access a headset. The build uses Android bionic for the daemon and
retains the separate QVR capture child. It needs no Zig installation.

Galaxy XR camera/calibration port and settings: **stearnsbq**. Lighthouse
observation server and PC alignment: **CreoleVR / QuestLHSync**. Sources are
pinned in `UPSTREAM.json`, retained under `upstream/`, and bundled in the ZIP
with their MIT licenses. AZJ2 firmware validation, NDK build and coordinated
lifecycle integration: **[booinspace](https://github.com/booinspace)**.
