# No low-light toast for Galaxy XR AZJ2

Experimental KernelSU GXR port inspired by
[BreadDoesStuff's low-light module](https://github.com/BreadDoesStuff/galaxy-xr-modules/tree/93dcf733068d0f57d53b21b79f37b1f38f573e6f/modules/gxr-no-lowlight-toast).
Targets SM-I610 on `I610UES3AZJ2`. Installs disabled. The warning's behavior
still needs a dark-room test on the headset.

Upstream disables the ambient light sensor pipeline. This AZJ2 port instead
sets `ix.sysui.light_sensor.low_light_threshold=-Infinity` before SystemUI
initializes. AZJ2 parses this as a float and compares the filtered lux against
it. Ordinary nonnegative lux readings cannot enter the low-light condition.
The light sensor listener and separate dim-light threshold remain unchanged
in this implementation. Any other consumer of the low-light signal also stops
receiving normal low-light transitions; this is not a targeted hook into only
the Toast call. It does not improve tracking in darkness or change perception's
separate tracking-loss dialogs.

Install using **KernelSU GXR → Modules → Install from storage**. Leave the
other experimental window modules disabled for the first test. Enable this
module and tap **Action** to check that it is armed. Then use **one GXR Soft
restart**. Its coordinated `stopped` phase sets the nonpersistent property
before SystemUI starts; the `started` phase checks read-back. The package has
no `system.prop` or `post-fs-data.sh`, which this GXR manager rejects.

Check the property with:

```sh
adb shell getprop ix.sysui.light_sensor.low_light_threshold
```

Expected after the coordinated restart: `-Infinity`. Then test a dim/dark
environment and confirm the unwanted toast is absent. Keep testing the normal
dim-light inactivity behavior; it is preserved in the source but not yet
validated on the device. A plain Action does not change a running SystemUI's
cached threshold.

Turning the checkbox off restores the original property, but a SystemUI that
already read the modified value needs another restart to reload it. For the
simplest recovery, leave this module disabled and fully reboot with DirtyFrag
Autorun off. Regain temporary root if you want to uninstall it. GXR requires
`GXR_UPDATE_STATE=STOCK` before removal; the script will not claim restoration
while the same SystemUI process could still hold the modified threshold.
The property is nonpersistent, so a full reboot also restores the firmware
default. This module never restarts SystemUI itself.

See `THIRD_PARTY.md` and the repository's `docs/BREAD-AZJ2.md` for source,
license, build steps and compatibility evidence.
