# Mic gain boost for Galaxy XR AZJ2

Experimental KernelSU GXR port of
[BreadDoesStuff's mic gain module](https://github.com/BreadDoesStuff/galaxy-xr-modules/tree/93dcf733068d0f57d53b21b79f37b1f38f573e6f/modules/gxr-mic-gain-boost).
Targets SM-I610 on `I610UES3AZJ2`. Installs disabled. Audio behavior on this
firmware has not been tested.

The daemon listens for recording callbacks. It boosts `TX_DEC0 Volume` by 15
steps while `virtualdesktop.android` records with `VOICE_PERFORMANCE` (source
10). This port checks both package name and source; upstream checked source
alone. Upstream describes the codec steps as 1 dB each. The default path value
84 appears in AZJ2's mixer XML; root mixer access, actual gain and clipping
still need a device test.

Install the ZIP with **KernelSU GXR → Modules → Install from storage**, enable
its checkbox, then tap **Action**. No Soft restart is needed. `RUNNING` means
the callback was registered, not that audio quality has been validated. Start
Virtual Desktop's microphone and compare a recording at the same app settings.
Do not enable passthrough or rotation during this first check.

After the first start, edit
`/data/adb/modules/gxr_mic_gain_azj2/config.conf` if needed:

| Key | Default | Behavior |
| --- | --- | --- |
| `MODE` | `1` | Boost during eligible VD capture; concurrent recorders sharing that input path also receive the hardware gain |
| `MODE=2` | — | Boost only when VD is the sole ordinary mic recorder |
| `GAIN_DB` | `15` | Mixer step increment; accepted range 0–40, final control value capped at 124 |

Higher gain can clip. Bluetooth/USB mic routes are not established by this
port. Stop and restart the module through its checkbox and Action to reload
configuration. The stock `config.default.conf` stays checksummed; the mutable
`config.conf` is retained during updates.

Turning the checkbox off asks the daemon to restore the value it wrote. It
does not overwrite a different value subsequently set by the audio HAL or
another actor. Writes are checked by reading the mixer back, and ownership is
journaled before each write. An unexpected stop disables the module; Action
exports `/data/local/tmp/gxr_mic_gain_azj2-daemon.log` and any failure file.

Uninstall through KernelSU after restoration. GXR checks
`GXR_UPDATE_STATE=STOCK`. If restoration cannot be verified, leave it disabled
and fully reboot with DirtyFrag Autorun off; regain root manually before
removal. A full reboot resets the hardware path and invalidates the old boot's
journal. Module files can persist after temporary root ends.

Source, MIT license and build provenance are included in the ZIP. See
`THIRD_PARTY.md` and the repository's `docs/BREAD-AZJ2.md` for build steps and
the test sequence.
