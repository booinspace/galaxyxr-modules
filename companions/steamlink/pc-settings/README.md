# Steam Link PC settings helper

This is the owner-supplied copy of AngelDark92's SteamVR settings helper,
imported on 15 November 2026. It edits the PC's `steamvr.vrsettings`; it is
separate from the APK builder and is never run by `Build-SteamLink.cmd`.

Close SteamVR, keep the BAT and PS1 together, then double-click
**Apply-SteamLink-GalaxyXR-PC-Settings.bat** and choose a profile. It requires
Windows PowerShell 5.1 or later. For an explicit profile or settings path:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Apply-SteamLink-GalaxyXR-PC-Settings.ps1 -Mode Highest -SettingsPath "C:\Path\To\Steam\config\steamvr.vrsettings" -NoPause
```

| Profile | Encode width | Transport tile width | Requested bitrate |
| --- | ---: | ---: | ---: |
| Default | VRLink default | VRLink default | VRLink default |
| Stable | 2048 | 1536 | 250 Mbps |
| Quality | 2560 | 1536 | 300 Mbps |
| High | 3072 | 1536 | 300 Mbps |
| Highest | 3072 | 1536 | **600 Mbps** |
| Ultra | 4032 | 1536 | **1000 Mbps** |

The two upper bitrates are the owner's overrides. A requested target does not
establish sustained network throughput, encoder acceptance or decoder stability.
Ultra also uses a larger source image, so it changes more than bitrate alone.

## Settings and recovery

The helper refuses to write while SteamVR processes are running. It creates a
`steamvr.vrsettings.gxr-backup-<timestamp>` copy, validates a temporary file,
then replaces the selected settings file. To recover the exact previous values,
close SteamVR and restore that backup.

**Review before applying:** non-Reset profiles remove saved overrides including
`enableHandTracking` and `shareEyeTrackingData`. Those options can return to their
Steam Link defaults. The helper predates the current native Galaxy XR profile
and edits global `driver_vrlink` settings, which can overlap Galaxy XR Companion's
configuration. It does not update the Companion's own encoder budget.

**Reset removes entire sections**, including `driver_vrlink`, along with
`steamvr.preferredRefreshRate`. Values in those sections may have been written by
other tools. Reset is not an ownership-aware undo; use the backup for that.
No active SteamVR settings were changed when importing or validating this copy.

## Source and changes

Original scripts: **[AngelDark92/xr-porting-hub](https://github.com/AngelDark92/xr-porting-hub/tree/b4ac8aa4701559c30a06280a1ef9292e8071cd5a/Install)**,
reference commit `b4ac8aa4701559c30a06280a1ef9292e8071cd5a`.
The local copy already included JsonCpp infinity-token parsing, a JSON-object
check, a 600 Mbps Highest profile and no forced `asyncSend` write. This import
retains those changes, sets Ultra to 1000 Mbps and corrects both menu labels.
The BAT is retained from the owner's copy; use the PowerShell command above
when passing arguments.

The original PC snapshot SHA-256 values were:

- PS1: `8b0d02106082df4178a91b1827e2ae080d37da6dde2839917bd9787a91ed70c2`
- BAT: `0b39872ddea7d81baa755cc9e9017a4d9eed25f4e340e006d8ca7a2db60b75e7`

Upstream's GPLv3 [license](LICENSE.upstream) and [notice](NOTICE.upstream) are
retained. This folder does not relicense those scripts under the collection's
MIT license. Import, profile adjustments and checks are by **booinspace**.

## Validation

Run the source checks from the repository root:

```powershell
powershell.exe -NoProfile -File .\tests\steamlink-pc-settings.test.ps1
```

The checks parse the script and exercise its JSON parser, property updates,
profile selection and process guard in memory. They never invoke the settings
write path, stop SteamVR, or establish streaming performance.
