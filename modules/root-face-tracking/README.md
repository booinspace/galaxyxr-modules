# Galaxy XR root face tracking for AZJ2

This is **compdoge's [gxr-root-ft](https://github.com/compdoge/gxr-root-ft)**
1.4.0 sender, with an AZJ2 build and KernelSU GXR lifecycle by
[booinspace](https://github.com/booinspace). It is a **headset KernelSU module**,
not an APK. Root acquisition remains in the separate
[galaxyxr-root project](https://github.com/booinspace/galaxyxr-root).

The sender reads the vendor perception pipeline through uprobes and sends
face/tongue expressions, independent eye gaze and pupil measurements to
**compdoge's [VRCFT-ALVR-UE](https://github.com/compdoge/VRCFT-ALVR-UE)** receiver
on Windows. It uses the ALVR UniExpr packet format; **an ALVR streamer is not
required**. Steam Link or Virtual Desktop can carry the VR session separately.

## Compatibility and validation

Target: SM-I610, Android 14, `UML2.260301.001.I610UES3AZJ2`.
Installation is disabled by default. Startup checks the exact fingerprint,
payload checksums and both stock plugin SHA-256 identities:

| Stock vendor library | SHA-256 |
| --- | --- |
| `libperception_eye_tracking_host_plugin.so` | `b621f85c50059fcd4b4f0cb3ba9aebbeb0cee6298d6572ab64fa5ad13afb6882` |
| `libperception_face_parameter_tracking_host_plugin.so` | `b02d127f5a1ab8ac0c08c4adf6bd0f7b04a36032b110b31911af5dcf26da1a58` |

The eye library matches the AZF3 identity documented upstream. Offline ARM64
inspection of the exported AZJ2 libraries found the expected sites:

| Probe | File offset | Register/data contract inspected |
| --- | --- | --- |
| Pupil | eye `0x4bef60` | Float load from `x10`; detection index in `w20` |
| Eye direction | eye `0x4be378` | Vector address in `x0` immediately before the call |
| Face blendshapes | face `0x3589f8` | `memcpy` source in `x1`, byte count in `x2` |
| Jaw/tongue | face `0xf09aa4` | Unclamped jaw at `x21+0x60`, tongue at `+0xfc`/`+0x108`/`+0x10c` |
| Tongue model | face `0x358a34` | Second vector's `memcpy` source in `x1` |

The upstream offsets are retained. These checks support an experimental build;
they do not establish live data quality or prove every vector length/semantic
assumption. Host checks cover gaze maths, relay bookkeeping, private trace
cleanup and the receiver packet format. **The AZJ2 probes and avatar output
have not yet been tested live.** No stock vendor binaries are redistributed.

## Install and use

1. Have working temporary root in KernelSU GXR. Keep DirtyFrag Autorun off
   during the first test.
2. Install `gxr-root-face-tracking-azj2-0.1.1-disabled.zip` through
   **KernelSU GXR → Modules → Install from storage**. This is separate from
   Window Controls; do not install the unported upstream ZIP alongside it.
3. On Windows, install the official root receiver using the
   [PC companion instructions](../../companions/face-tracking/README.md).
   Run **Use-RootRelay.cmd** to select it. Keep the other face/eye providers
   inactive to avoid competing output.
4. Enable this module and tap **Action**. Enter the receiving PC's LAN IPv4
   address, then **Save PC**. No destination is preconfigured and broadcast
   discovery is disabled in this port.
5. Tap **Start relay**, wait a few seconds, then **Refresh**. `RUNNING` means
   the process is alive and all five probe registrations succeeded; it does
   not mean a calibrated avatar has received valid measurements.
6. Wear the headset and test gaze, blinks, jaw and tongue in VRCFT's preview
   before using an avatar. Complete the headset's stock eye/face calibration.
   The root relay does not need the patched Steam Link face bridge enabled.

No Soft restart is needed. A checked module can resume after temporary root
starts or a coordinated GXR Soft restart. Action **Stop relay** stops the
current session; turn the KernelSU switch off to prevent automatic resume.
For the simpler APK path, keep this root module off and select **SteamLink**
on the PC instead.

## Changes for this port

- A private tracefs instance, `/sys/kernel/tracing/instances/gxr_ft_azj2`, owns
  its buffer and reader. Only its five `gxr_ft_azj2/*` events are removed.
  Upstream's device-wide uprobe truncation is not used.
- Root starts require all five probes. The launcher checks the exact AZJ2
  libraries and the native binary rejects offset/plugin overrides.
- The upstream single-instance lock is retained for compatibility with the
  original sender, but a lock-open failure now refuses to start.
- The supervisor tracks boot/PID/start time and stops only its own child.
  It has four GXR restart hooks, bounded stop waits and same-boot quarantine
  after an unexpected exit. It does not use global `pkill` or restart loops.
- The upstream cgroup escape is retained with membership verification. An
  Action launch refuses to start if it cannot leave the Manager's app leaf;
  `setsid` alone would not prevent Android's cached-app freezer from pausing it.
- Settings and learned dilation state persist under
  `/data/adb/gxr-root-ft-azj2`. The WebUI exposes only destination, start/stop,
  status and log export. Upstream's gaze/tongue calibration remains unchanged.

This port ships no extra SELinux policy file and changes no enforcement setting.
It uses the existing KernelSU root domain for tracing access. KernelSU GXR's
reviewed installer rejects `sepolicy.rule`; packaging checks enforce that
restriction before a ZIP is produced. The executable is installed under
`bin/gxr_alvr`, where the GXR installer grants execute permission.

## Stop, diagnose and remove

Turn the KernelSU switch off and wait up to 20 seconds for owned probes to be
removed. Action **Export logs** copies bounded health/status output to
`/data/local/tmp/gxr-root-ft-runtime.log`; ordinary launch does not enable raw
verbose face logging. Unexpected exits disable the module for that boot.
After a full reboot, regain temporary root and explicitly re-enable it when
ready. A full reboot clears live trace probes; installed module files and
saved settings remain.

Keep the module off before updating/removing it. If cleanup cannot be
verified, leave it off and fully reboot rather than repeatedly Soft restarting.
KernelSU can then remove the package. To erase saved settings as well, remove
`/data/adb/gxr-root-ft-azj2` with root after the runtime has stopped.

UDP **41463** carries unencrypted biometric measurements. Send only to your
own PC on a trusted LAN, use a private-network firewall rule and do not forward
this port from the Internet. This module observes a vendor process with
uprobes: hook or kernel faults can still destabilize tracking or the headset.

## Build

Linux x86-64/WSL, Python 3, a C compiler, `patch`, and Android NDK
**29.0.14206865** are required. No Kotlin, Gradle, APK signing or full kernel
build is involved.

```sh
python3 tests/port-package.test.py
python3 tests/root-face-tracking.test.py
python3 scripts/build-root-face-tracking-azj2.py \
  --ndk "$ANDROID_NDK_HOME" --output releases
python3 tests/root-face-tracking.test.py
```

The offline packet check briefly binds localhost UDP 41463; stop any receiver
on the build host first. The builder applies `azj2.patch` to the pinned MIT
source, emits an Android/bionic arm64 ELF with 16 KB segment alignment and
packages all source/build inputs, license, build receipt and checksums.

## Credits

- **[compdoge](https://github.com/compdoge)**: original root relay, expression
  mapping, gaze/pupil processing, tongue model and cgroup investigation.
  Pinned source: `4d4dea8f7deacafc6859ab3d7cb98f513550402e` (1.4.0), MIT.
- **[alvr-org/VRCFT-ALVR](https://github.com/alvr-org/VRCFT-ALVR)** and its
  contributors, including zmerp and curoviyxru: receiver and packet conventions.
- **[booinspace](https://github.com/booinspace)**: AZJ2 inspection, trace
  isolation, lifecycle integration, settings and build/test packaging.

MIT notice is retained under `upstream/LICENSE` and in the built ZIP.
