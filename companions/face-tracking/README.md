# Galaxy XR VRCFaceTracking receivers

These scripts install the official **compdoge** Windows releases and preserve
existing receiver files/settings. They do not build or redistribute the
receiver DLLs in this source folder.

| Route | Headset component | PC receiver |
| --- | --- | --- |
| Steam Link APK bridge | [gxr-face-bridge](https://github.com/compdoge/gxr-face-bridge) embedded in a patched Steam Link APK | [compdoge/LinkFT](https://github.com/compdoge/LinkFT/releases/tag/gxr-facebridge-v1.0.1) 1.0.1 |
| Root perception relay | [gxr-root-ft AZJ2 KernelSU port](../../modules/root-face-tracking/README.md) | [compdoge/VRCFT-ALVR-UE](https://github.com/compdoge/VRCFT-ALVR-UE/releases/tag/v1.4.0) 1.4.0 |

The dedicated LinkFT maps Galaxy XR's repurposed tongue slots. Stock LinkFT
can interpret those slots differently. The root receiver uses the ALVR UniExpr
format without requiring an ALVR streamer. Use one face/eye route at a time.

## Install

Use the current Steam version of VRCFaceTracking. In PowerShell, from this
folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-GalaxyXR-Receivers.ps1
```

The installer downloads the two official ZIPs, checks pinned SHA-256 hashes,
backs up `CustomLibs` and settings, then installs LinkFT selected and the root
receiver in standby. It closes VRCFT during replacement; open it again from
Steam afterward. It places **Use-SteamLink.cmd** and **Use-RootRelay.cmd** on
the Desktop. Each shortcut selects one provider and reopens VRCFT. The script
assumes the default Steam install path; adjust it for a different Steam library.

The current VRCFT loader discovers a folder when `module.json` is present and
has no persisted provider-disable setting. The selectors rename only the four
known providers' metadata between `module.json` and `module.json.disabled`.
DLLs and provider settings stay in place. Do not use VRCFT's registry installer
to overwrite the locally installed forks. Unrelated providers are not modified;
disable them manually if they claim the same eye/face channels.

The provider scripts, original receiver files and timestamped backups live in:

```text
%APPDATA%\VRCFaceTracking\GalaxyXR-Providers
```

That folder also has **Use-VirtualDesktop.cmd** and **Use-StockSteamLink.cmd**
to restore the previous receiver selection when those modules were installed.
The native VRCFT eye/expression checkboxes still apply for a running session;
use the profile shortcuts for a persistent selection across app restarts.

## Steam Link path

Select **Use-SteamLink.cmd**. In Steam Link's advanced settings enable **OSC**,
**Share eye tracking** and **Share face tracking**, with output port **9015**.
The receiver binds `127.0.0.1:9015`; no LAN firewall opening is needed for it.
Do not change VRCFT's general OSC output ports for this receiver.

The Galaxy XR APK must already contain the face bridge and have eye/face
permissions. Complete Samsung's eye and face calibration. The existing patched
APK's bridge matches upstream 1.0.0; the PC module is the dedicated 1.0.1 release.
This route supplies the runtime's combined gaze and five tongue directions;
use the root route for the additional per-eye/pupil data.

## Root relay path

Select **Use-RootRelay.cmd**, then configure/start the headset module as its
[guide](../../modules/root-face-tracking/README.md) describes. Allow inbound
UDP **41463** for `VRCFaceTracking.ModuleProcess.exe` only on the trusted private
LAN. The source installer does not create firewall rules or change network
profiles. No router forwarding is needed. `Initialized` in VRCFT means the
receiver loaded, not that valid live tracking arrived.

## Sources and licensing

- [compdoge/gxr-face-bridge](https://github.com/compdoge/gxr-face-bridge):
  Android OpenXR layer embedded in the APK; not another PC plugin to install.
- [compdoge/LinkFT](https://github.com/compdoge/LinkFT), based on
  [Ykeara/LinkFT](https://github.com/Ykeara/LinkFT): dedicated Galaxy XR receiver.
- [compdoge/gxr-root-ft](https://github.com/compdoge/gxr-root-ft): MIT root sender.
- [compdoge/VRCFT-ALVR-UE](https://github.com/compdoge/VRCFT-ALVR-UE), based on
  [alvr-org/VRCFT-ALVR](https://github.com/alvr-org/VRCFT-ALVR): root receiver.
- [VRCFaceTracking](https://github.com/benaclejames/VRCFaceTracking): module
  host and loader behavior used for reversible profile selection.
- Installer/profile scripts and AZJ2 integration: **booinspace**.

The downloaded binaries remain governed by their upstream licenses; these
scripts do not relicense them. ZIP hashes are pinned in the installer. Neither
route has been validated end-to-end with the user's avatar during this port.
