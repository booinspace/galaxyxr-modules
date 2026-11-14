# App audio mixer for AZJ2

Audio Mixer adds individual app sliders to the headset's native volume popup
and expanded volume panel. Open the normal volume control while an app is
playing media, then adjust its 0–100% slider. Zero mutes that app; 100% removes
the mixer's attenuation. The existing master volume still applies.

Audio Mixer is included in the experimental **Window Controls 0.1.68** build. It updates the existing
`gxr_window_curvature` module and shares its injector, patched ART bridge,
firmware checks, restart hooks and recovery. Do not install it as a second
SystemUI injector. Existing window features remain included.

## Install and use

1. Keep your working Window Controls ZIP available. Close pinned windows and
   switch Window Controls off before installing this ZIP as an update.
2. Enable Window Controls and use one KernelSU GXR Soft restart. If the current
   session is quarantined, follow [Window Controls recovery](../../docs/CURVATURE.md)
   first; another Soft restart cannot clear a crashed full boot.
3. Open the headset's normal volume popup or expanded volume panel. App mixer
   shows apps with active media/game playback. Extra apps scroll at normal size.
4. Adjust an app slider. Settings are saved by Android user and package names
   and applied when that app creates new players. Apps sharing an Android UID
   share one slider, which is labelled accordingly.
5. Turn App mixer off to bypass saved levels, or use Reset app volumes to remove
   all saved attenuation. The switch and reset are in the native volume panel.

No additional APK or network service is installed. The Action page explains where
to find the controls; the sliders themselves are native Android views.

## Scope and recovery

The first build supports Android **AudioTrack and MediaPlayer** output. AAudio,
SoundPool, OpenSL ES and external/hardware players are labelled unsupported.
An app with mixed supported and unsupported active players is also labelled
unsupported. App playback remains untouched until a supported slider is reduced.
An existing supported player keeps its saved level if that app later adds an
unsupported player; switch the mixer off to bypass all levels.

Use **Allow simultaneous media** in the native mixer panel to let multiple apps
keep audio focus. After enabling it, restart playback in both apps. This uses
AZJ2's native multi-audio API and explicitly saves its setting after the
firmware API was observed changing only the live state. The choice survives
reboots independently of the module. Switch it off here to restore normal
exclusive focus; Android may stop existing playback when doing so. Individual apps can still choose to pause.

The sliders provide attenuation, not amplification. They do not change master
or stream volume, calls, alarms, notifications, routing, microphone gain or
Android's system ducking envelopes. It uses one separate `VolumeShaper` envelope
per supported player, with ID `0x475852`, and replaces/removes only that envelope.
Player access uses APIs verified in the saved AZJ2 framework; no vendor code is
included. The underlying player command is asynchronous, so a successful Binder
send is not proof of an audible change.

Normal disable/update removes the mixer envelopes and restores the original
panel dimensions. If SystemUI is killed before cleanup, attenuation can remain
in an app that is still playing. Close and reopen that app's playback, restart
the mixer, or fully reboot to clear it. The next mixer start first removes its
old envelope ID from supported players. Saved levels live in SystemUI's private
`booinspace_audio_mixer` preferences. Use Reset before removal if you want those
preferences cleared.

Target: SM-I610, `UML2.260301.001.I610UES3AZJ2`. The headset owner confirmed
individual app volume controls and simultaneous Symphonium/YouTube playback.
The native API changed the live audio state without saving it reliably, so the
switch now saves and verifies the setting explicitly and refreshes on reopening.
The owner confirmed the combined 0.1.68 update. Other apps and player APIs still
need individual testing.

## Build on Linux or Fedora

Use the [shared build requirements](../../docs/BUILDING.md). Run this from the
repository inside your Linux/Fedora build environment:

```sh
.build/venv/bin/python -B scripts/build-quick-controls-azj2.py \
  --java /usr/bin/java \
  --ecj .build/tools/ecj-3.39.0.jar \
  --r8 "$HOME/Android/Sdk/cmdline-tools/latest/lib/r8.jar" \
  --android-jar "$HOME/Android/Sdk/platforms/android-37.0/android.jar" \
  --cache .build/cache --output .build/output
```

The builder reuses Window Controls and the shared `gxr_build` library. It runs
the mixer tests, existing combined-runtime tests, Java/DEX compilation and
package validation. Output:
`gxr-window-curvature-0.1.68-azj2-quick-controls-disabled.zip` and its SHA-256 sidecar.
Packages install disabled. No release feed is changed by building locally.

## Credits and sources

Audio Mixer is by [booinspace](https://github.com/booinspace). Its new source is
MIT licensed; that licence does not relicense the surrounding project.

- [Android VolumeShaper documentation](https://developer.android.com/media/platform/volumeshaper).
- [AOSP PlayerProxy](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/media/java/android/media/PlayerProxy.java).
- [AOSP system ducking implementation](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/services/core/java/com/android/server/audio/PlaybackActivityMonitor.java).
- [BlueScorpioVR's Window Curvature](https://github.com/BlueScorpioVR/galaxyxr-modules):
  the existing runtime this feature extends.
- [Shared runtime credits and dependency licences](../../docs/SOURCES.md),
  including Frida, pandasauce's ART/CMC patch and Kolektori's dispatch work.
