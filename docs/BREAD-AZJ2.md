# BreadDoesStuff modules ported to AZJ2

These experimental AZJ2 modules are ports of
[BreadDoesStuff/galaxy-xr-modules](https://github.com/BreadDoesStuff/galaxy-xr-modules)
at commit `93dcf733068d0f57d53b21b79f37b1f38f573e6f`, under its MIT license.
BreadDoesStuff's upstream device testing was on AZF3. These builds target only
Samsung Galaxy XR SM-I610, Android 14,
`UML2.260301.001.I610UES3AZJ2`.

| Port | Activation | Behavior |
| --- | --- | --- |
| [Mic gain boost](../modules/mic-gain-boost/README.md) | Enable, then Action | Checks the VD package and recording source; verifies writes and journals mixer ownership |
| [Passthrough anywhere](../modules/passthrough-anywhere/README.md) | Enable, then Action; double-tap in immersive app | Requires an observed baseline; closes CPM resources; journals restoration; broad toast muting defaults off |
| [No low-light toast](../modules/no-lowlight-toast/README.md) | Enable, Action, then one coordinated GXR Soft restart | Sets only the low-light threshold; keeps the sensor pipeline and dim-light threshold enabled |

All ZIPs install **disabled**. They do not acquire root. They have GXR
`action.sh off/status` restoration reports, payload and firmware checksums,
`auto.sh`, `skip_mount`, and the four coordinated restart hooks. Ordinary app
daemons run as separate root `app_process` processes; there is no Frida
injector in these ports. The prohibited upstream `system.prop` and
`post-fs-data.sh` are not included.

## Compatibility evidence

The port was checked against stock files read from the user's AZJ2 headset:

- SystemUI APK: `dc664a17617b97d2aafebac9690c4235f530cd24399fbe16b6634d5df2a6a6dc`.
- Framework JAR: `6ec625a07d94e3e50d82eea14bcec05425de303a62a512e6b82ae57881c46ad7`.
- Mixer XML: `79526e6e79d03bf55ff6363a68db8f723460bbe47d76367e8ca259dc7df1f870`.
- `tinymix`: `d20da6b80c64f0bbe322fe75b4a89dde72389bfc7c7e5395b5cbb57d2dba0b0f`.

AZJ2 contains the required CPM methods, recording callback interfaces,
client-package/source accessors, focused XR mode and task-stack listener API.
Its SystemUI retains the same double-tap rejection and passthrough-state log
strings. Its mic XML has `TX_DEC0 Volume` and a handset-mic route value of 84.
Its `LightSensorManager` reads the low-light threshold once at class startup
and compares the filtered lux against it; the dim-light threshold is separate.
The low-light port therefore needs a restart phase before SystemUI starts.

The live AZJ2 read-only signature probe passed. It is built as `bread-azj2-api-probe.dex`. It looks up method
signatures and invokes no mixer writes, callbacks, CPM node updates or
property setters. Signature checks do not establish permissions or runtime
behavior. CPM restoration submits the last observed baseline transaction; it
has no alpha/z read-back in this API, so visual restoration still needs checking. Ordinary ADB shell could not open the mixer, so the mic helper also
checks root access and read-back before claiming a successful write.

## Build and host checks

Use a JDK with `java` and `javac`, an Android platform JAR, and the SDK's R8 JAR.
No new injector or native binary download is needed. On the configured WSL PC:

```sh
python3 scripts/build-bread-azj2.py \
  --java /usr/bin/java --javac /usr/bin/javac \
  --r8 /home/nathalie/galaxy-xr-azj2/android-sdk/cmdline-tools/latest/lib/r8.jar \
  --android-jar /home/nathalie/galaxy-xr-azj2/android-sdk/platforms/android-37.0/android.jar
python3 tests/bread-port-control.test.py
python3 tests/bread-daemon-lifecycle.test.py  # Linux/WSL
shellcheck modules/mic-gain-boost/*.sh modules/passthrough-anywhere/*.sh modules/no-lowlight-toast/*.sh
```

The build checks the mic policy, shared recording modes, non-stacking gain,
owned-value restoration, passthrough log parsing and threshold representation.
It compiles hidden Android API stubs separately and excludes them from the
helper DEX. The package checks disabled markers, payload checksums, GXR startup
requirements and source/DEX integrity. A receipt in each ZIP records upstream,
source and tool hashes. The shell test exercises the ordered low-light restart
and prevents an early stock report while SystemUI still caches a changed value.

To run only the read-only probe:

```sh
adb push releases/bread-azj2-api-probe.dex /data/local/tmp/
adb shell 'CLASSPATH=/data/local/tmp/bread-azj2-api-probe.dex /system/bin/app_process /system/bin PortApiProbe'
```

## First device tests

Feature behavior is not yet validated on the headset. Keep DirtyFrag Autorun
off, and test one port at a time with the window injectors disabled.

1. **Mic:** enable and start with Action, record in VD, then stop its capture.
   Compare audio at identical app settings. Test a second recorder separately
   and, if needed, MODE 2 with concurrent capture. Turn the port off and check
   that its Action/exported log records restoration.
2. **Passthrough:** enable and start with Action, open an immersive app, then
   double-tap twice. Confirm camera view, return to the app, continued app/input
   operation, and restoration when leaving the app. If the baseline is missing,
   use the normal Home passthrough toggle first. Test with toast muting off.
3. **Low light:** enable and use the GXR Soft restart after arming. Check the
   threshold is `-Infinity`, the unwanted dim-room toast is absent, and normal
   dim-light inactivity behavior still works.

Turning a port off requests restoration; GXR verifies stock state before an
update or uninstall. The mic's hardware gain may affect other simultaneous
recorders and can clip. Optional passthrough toast muting hides all SystemUI
toasts while immersive focus is active. Low-light suppression changes the
low-light signal, and cannot improve tracking conditions.

If any restoration is unverified, leave the port disabled, fully reboot with
Autorun off, then regain root manually if removal is needed. Installed module
files can persist after temporary root ends. A low-light property's original
value can be restored immediately, but its cached SystemUI value needs a new
process before GXR reports stock. The ports never initiate a SystemUI restart.

The upstream MIT notice and each module's `THIRD_PARTY.md` are included in the
built packages. No firmware binaries or root exploit are bundled.

## Built releases

The current port ZIPs are version **0.1.1**, credited to BreadDoesStuff with the
AZJ2 port by **booinspace**. Their runtime files match the previous release.

| Module | ZIP SHA-256 |
| --- | --- |
| mic-gain-boost | `6e654a12c87f453d5c716463658d2285386adbd72083099ea22386771f6be71b` |
| passthrough-anywhere | `3dd1a8b9056f9fade118fc50ea8dcc8adf7901d76216dee08bb62493b5aa2b22` |
| no-lowlight-toast | `626c663c326d55705454bbaada07fe31d12db7909b8c5fdb6fc80ef35d561322` |

Use one branch/version for each feature; do not enable duplicate variants.
