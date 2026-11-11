# Passthrough anywhere for Galaxy XR AZJ2

Experimental KernelSU GXR port of
[BreadDoesStuff's passthrough module](https://github.com/BreadDoesStuff/galaxy-xr-modules/tree/93dcf733068d0f57d53b21b79f37b1f38f573e6f/modules/gxr-passthrough-anywhere).
Targets SM-I610 on `I610UES3AZJ2`. Installs disabled. Live passthrough behavior
has not been tested on this firmware.

The root daemon observes SystemUI's physical double-tap rejection in an
immersive app, then temporarily places the global CPM passthrough layer above
that app. The app should keep running. A second double-tap returns control to
the last state SystemUI requested. This uses the same API and log strings
present in AZJ2; it does not inject code into SystemUI.

Install through **KernelSU GXR → Modules → Install from storage**, enable the
checkbox, then tap **Action** once to start. No Soft restart is needed. Open an
immersive/OpenXR app such as Virtual Desktop, then double-tap. A later Action
while running requests the same toggle. The headset's recenter and normal
click gestures are handled by the stock input detector.

The port refuses to force the camera layer until it has both immersive focus
and an observed SystemUI passthrough baseline. If its log says `WAITING`, return
to Home, use the normal passthrough toggle, then open the immersive app again.
It will never substitute a guessed initial alpha/z for missing baseline data.

Runtime configuration is created at
`/data/adb/modules/gxr_passthrough_azj2/config.conf`:

| Key | Default | Behavior |
| --- | --- | --- |
| `ALPHA` | `1.0` | Camera opacity, 0–1 |
| `Z` | `9999` | Compositor order; accepted range -10000–10000 |
| `DEBOUNCE_MS` | `600` | Double-tap debounce, 100–5000 ms |
| `ENABLED` | `1` | Listen for physical double-tap rejections |
| `MUTE_SYSUI_TOAST` | `0` | Optional: `1` hides **all** SystemUI toasts while immersive focus is active, then restores the prior app-op |

Toast suppression is off by default, unlike upstream, because it suppresses
more than the rejection message. If enabled, the original app-op is saved and
restored rather than forcing `allow`. The passthrough cameras and their normal
privacy indicator are expected to activate. Performance, focus transitions,
camera visibility and input still need testing on the headset.

Turn the checkbox off to restore the owned camera state and optional toast
setting. SystemUI's own later state request takes priority. Journals are tied
to boot and SystemUI identity; stale state is not replayed into a new process.
GXR's coordinated restart first stops this daemon. Avoid an unrelated
SystemUI restart while passthrough is forced.

Action exports logs to `/data/local/tmp/gxr_passthrough_azj2-daemon.log` and any
failure file. GXR verifies `GXR_UPDATE_STATE=STOCK` before uninstall. If the
owner changes or restoration fails, leave disabled and fully reboot with
DirtyFrag Autorun off before reacquiring root and removing it.

See `THIRD_PARTY.md` and the repository's `docs/BREAD-AZJ2.md` for credits,
builds and the first test sequence.
