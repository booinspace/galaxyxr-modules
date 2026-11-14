# Wi-Fi ADB

Wi-Fi ADB is by [4uva4ek](https://github.com/4uva4ek/galaxyxr-modules/tree/9f096dfc79e72f180410bcfa5ba32b566734f62b/modules/wifi-adb).
This collection builds upstream **1.0.2** at commit
`9f096dfc79e72f180410bcfa5ba32b566734f62b` without changing its runtime,
metadata, author or update feed. The local build recipe and documentation are
by [booinspace](https://github.com/booinspace).

The AZJ2 filename identifies this collection's build. It is not an AZJ2-specific
fork. No firmware offsets, private XR APIs, kernel modules, native compiler or
Samsung source are used. The owner tested the module on an
`SM-I610 / I610UES3AZJ2` headset and confirmed Wi-Fi ADB works.

## Install and connect

1. Have working temporary root in KernelSU GXR and enable USB debugging on the headset.
2. Install `gxr-wifi-adb-azj2-1.0.2-disabled.zip` through KernelSU GXR's module installer.
   Installation leaves it disabled. It has the original `gxr_wifi_adb` identity;
   an upstream copy is the same module, not a second installation.
3. Enable it and use the supported KernelSU GXR module startup workflow. The
   current temporary-root setup normally dispatches services during a GXR Soft restart.
4. Keep Wi-Fi connected. Action reports the waiting prerequisite or the address
   to use. On the computer, run `adb connect HEADSET_IP:5555` and approve its
   RSA authorization prompt on the headset if requested.

This is classic authenticated ADB TCP, not Android's pairing-code wireless
debugging interface. It may listen on interfaces other than Wi-Fi; use it on
a trusted network. Activation and restoration restart adbd and briefly drop
both USB and network ADB connections. It does not turn Wi-Fi on, create root,
disable authentication, or forward the headset address to a PC.

The worker waits for boot completion, a wlan0 IPv4 address and adbd. It checks
the listener and can make up to three recovery restarts per kernel boot after
a settling period. Offline waiting does not consume those attempts.

## Disable and recover

Turn the module off to stop its worker and restore the TCP port value recorded
at activation. To request and wait for restoration explicitly from a root shell:

```sh
su -c 'sh /data/adb/modules/gxr_wifi_adb/action.sh off'
```

Action reports restoration errors. If restoration cannot be confirmed, leave
the module disabled and fully reboot. The changed TCP property is volatile;
an existing network-ADB configuration is preserved when its baseline is restored.
After a full reboot, temporary root must be regained before the module can start.

## Build and checks

From this repository's root, with Python 3, Git, Bash and network access:

```sh
python3 scripts/build-wifi-adb-azj2.py
python3 tests/wifi-adb-package.test.py
```

The builder fetches the pinned commit, exports only its committed Wi-Fi ADB
files, runs upstream's ten simulated lifecycle scenarios and its original
packager, then checks the GXR payload, checksums, executable permissions and
unchanged source bytes. It copies the ZIP to `releases/` with the AZJ2 collection
filename and writes its SHA-256 sidecar. The ZIP itself is byte-identical to
the upstream builder's output. `--upstream /path/to/repository` reuses a local
Git object database containing that commit; working-tree edits are not used.

These host checks do not verify AZJ2 SELinux policy, actual RSA authorization,
network reachability or cold-boot timing. No headset is contacted by the build;
the owner separately confirmed operation on the AZJ2 headset.

The pinned upstream has no explicit repository-wide license. The recipe links
and fetches that source without relicensing it; the original author remains
in the package. Consult upstream terms before redistributing its ZIP.
