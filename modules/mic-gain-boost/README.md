# Mic gain boost for Galaxy XR AZJ2

KernelSU GXR port of
[BreadDoesStuff's mic gain module](https://github.com/BreadDoesStuff/galaxy-xr-modules/tree/93dcf733068d0f57d53b21b79f37b1f38f573e6f/modules/gxr-mic-gain-boost),
with an Action settings page by [booinspace](https://github.com/booinspace).
Targets SM-I610 on `I610UES3AZJ2`; installs disabled.

Version **0.2.0** adds a **0–40 step gain slider** and a **Virtual Desktop
only** switch. Changes persist across reboots and are loaded within the
running helper's next 250 ms settings check, plus mixer command time. No
Soft restart is needed. Zero removes this module's extra gain.

## Install and use

1. Regain temporary root; confirm KernelSU GXR says **Working**. Keep
   DirtyFrag Autorun off.
2. If an older mic module is running, switch it off and wait about 15 seconds
   for restoration. Install `gxr-mic-gain-boost-azj2-0.2.0-disabled.zip`.
3. Enable **Galaxy XR mic gain boost (AZJ2)** and tap **Action**. This starts
   the helper and opens its settings page.
4. Adjust **Gain boost**, choose the recording scope and tap **Apply settings**.
   Compare a short recording at identical app settings before increasing gain.

**Virtual Desktop only** is on by default, preserving the previous behavior:
boost while `virtualdesktop.android` uses `VOICE_PERFORMANCE` (source 10).
Turn it off for boost during ordinary, unsilenced mic recording in any app.
The runtime only changes `TX_DEC0 Volume`, the built-in hardware input path.
It does not control USB/Bluetooth microphone gain. Simultaneous apps sharing
that path share the hardware gain, even with the VD switch on.

Higher gain can clip. The default is +15 mixer steps. Upstream describes one
step as 1 dB; acoustic gain has not been measured, so the slider uses steps.
AZJ2's mixer XML contains a route baseline of 84; writes are capped at 124.
The helper observes the current baseline instead of assuming 84.

The original VD boost was user-tested on AZJ2. **The new settings page, live
adjustments and global scope still need a headset recording test.** `RUNNING`
means the callback is registered, not that recording quality was validated.

## Settings and cleanup

The root-only page writes `config.conf` atomically and accepts bounded numeric
values. It never evaluates config as shell code. Settings can also be edited
at `/data/adb/modules/gxr_mic_gain_azj2/config.conf`:

| Key | Default | Behavior |
| --- | --- | --- |
| `GAIN_DB` | `15` | Legacy key name for added mixer steps, 0–40 |
| `MODE` | `1` | Require VD voice capture; apps sharing its path receive the same hardware gain |
| `MODE=0` | — | Any ordinary mic recording can trigger boost |
| `MODE=2` | — | Retained legacy mode: require VD to be the sole ordinary mic recorder |

The page preserves mode 2 if VD-only stays on. Configuration is retained
during updates; `config.default.conf` remains checksummed.

Repeated slider adjustments use the original owned baseline rather than
stacking gain. If the audio HAL writes a different value, the helper respects
it and starts a later boost from that value. Mixer writes are read back,
and ownership is journaled before writing. Turning the module off restores
only the value this session owns. Wait about 15 seconds before updating or
uninstalling. If restoration is unverified, leave it disabled and fully reboot
with DirtyFrag Autorun off before retrying.

The page's **Export logs** button copies the current log and any failure to
`/data/local/tmp/gxr_mic_gain_azj2-*` without starting a stopped runtime.
Temporary root must be regained after a full boot to reapply the effect.

## Build and credits

See [the port guide](../../docs/BREAD-AZJ2.md) for JDK/SDK build requirements.
The builder includes source, MIT notices, firmware/payload pins and provenance.
Run `python3 tests/mic-settings.test.py`, `node --test tests/mic-settings-ui.test.mjs`
and the shared daemon lifecycle test as well as the builder's Java policy
checks. Host tests cover global/VD eligibility, live gain baseline handling,
restoration, validation and the UI's bounded root commands.

The original module is by **BreadDoesStuff**, under MIT; see
`LICENSE.upstream` and `THIRD_PARTY.md`. The AZJ2 port and live Action UI are by
**booinspace**. No firmware binary is bundled.
