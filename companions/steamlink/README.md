# One-click Steam Link VR builder for Galaxy XR

Double-click **Build-SteamLink.cmd** on Windows. Keep `build_steamlink.py` in the
same folder. The batch file runs the build in your default WSL distribution and
leaves the signed APK under **output/<UTC timestamp>/** beside the batch file.

The script downloads the latest stable
[AngelDark92 XR Porting Hub](https://github.com/AngelDark92/xr-porting-hub)
patch bundle and [Morphe Desktop](https://github.com/MorpheApp/morphe-desktop).
It finds the newest downloadable original APK that matches the released
patch catalog's exact **version name and ARM64 build code**, applies the
recommended patches for that build, includes the Galaxy XR face/tongue bridge
and signs the result. Selection uses the complete catalog from that stable
release, including default-on support components such as Codecs Support.
This is the rooted-headset profile: controller APK patches are excluded to avoid overlapping KernelSU controller fixes.

## What gets downloaded

1. Valve's current **public and beta SteamVR APKs**, directly from its Steam
   content depot, using anonymous login. Only
   `drivers/vrlink/resources/android-steamlinkvr-release.apk` is fetched, into
   a separate cache. Your installed SteamVR is not modified.
2. Original Steam Link APK links published in the selected upstream release's
   README. These provide a fallback when the latest Valve APK is not yet ported.
3. The latest stable Morphe JAR and XR Porting Hub `.mpp`, with SHA-256 checks
   from GitHub's release metadata. DepotDownloader 3.4.0 is hash-pinned.

The upstream 2.0.20 original is unsigned. It is accepted only when its SHA-256
matches the pinned base used for the first build. Other inputs require a valid
APK signature or the official Steam depot integrity check. The final patched
APK must always pass Android signature verification.

The candidate with the highest supported build code wins. Unsupported builds
are skipped; the script never uses Morphe's `--force` or `--continue-on-error`.
If there is no downloadable compatible original, it stops with an error.
"Newest available compatible" can therefore be older than Valve's latest APK.
The console and build receipt name the actual selected version and source.
Compatibility metadata and a successful build do not establish headset stability.

## Requirements

- Windows with an **x86-64 Linux WSL distribution**, Python **3.11+** and Java **21+**.
- Linux **Android SDK Build Tools**, providing `aapt2` and `apksigner`.
- Internet access to GitHub, Steam and the upstream original-APK links.

The script finds SDK tools through `ANDROID_HOME` / `ANDROID_SDK_ROOT`,
`~/Android/Sdk`, or the existing `~/galaxy-xr-azj2/android-sdk` workspace.
The existing build PC already has these tools. Downloads and scratch files
live under `~/.cache/galaxyxr-steamlink` inside WSL.
Set `XR_WSL_DISTRO` in Windows to choose a distribution other than your WSL default.

## Signing and future updates

On the existing build PC, the script automatically reuses:

```text
~/galaxy-xr-azj2/steamlink-install/morphe-data/morphe.keystore
```

It verifies the output's signing certificate matches the previous locally
built Steam Link APK when that build is present. It refuses to silently replace
a missing key from that previous installation. Otherwise, a new installation
uses a persistent Morphe profile under
`~/.local/share/galaxyxr-steamlink/morphe-data`.
Privately back up the signing profile and credentials; do not commit them.
The same signing key is required for an in-place update of an installed app.

The build output includes the APK, `.sha256`, `patch-result.json` and
`build-info.json` with exact inputs, versions, patch choices and public signer
fingerprint. All requested patches, the final APK identity/signature and the
embedded face bridge are checked before the APK is copied to output. Each run
gets a new output folder, keeping earlier builds.

This command only builds. To install the chosen output separately:

```sh
adb install -r "SteamLink-<version>-<build>-GalaxyXR-patches-<patch-version>.apk"
```

## Optional inputs

Supply an original APK downloaded through the upstream Meta/DownQ instructions:

```bat
Build-SteamLink.cmd --apk "C:\Downloads\steamlink-original.apk"
```

Use another existing Morphe signing profile:

```bat
Build-SteamLink.cmd --morphe-data "C:\Private\morphe-data"
```

That profile must already contain `morphe.keystore` using Morphe's default
signing credentials. For unattended callers, set `XR_STEAMLINK_NO_PAUSE=1`
before invoking the batch file. No credentials are needed for the anonymous
Steam download.

## Validation

On 12 November 2026, the actual Windows batch launcher completed an end-to-end
build through WSL: Steam Link 2.0.20/5001712, XR Porting Hub 2.8.0 and Morphe
Desktop 2.1.1. All 19 patches from the previous build applied. APK identity,
face-bridge payloads and final signature were verified, and the signer matched
the previously installed build. Eight helper checks cover exact-build rejection,
root patch selection, download integrity, archive paths and certificate formats.
The generated APK was not installed or tested in a headset streaming session.

## Credits and licenses

- **Valve**: Steam Link VR and the official SteamVR content depot.
- **[AngelDark92](https://github.com/AngelDark92/xr-porting-hub)**: XR Porting Hub
  patches and exact-build catalogs; controller work credits **4uva4ek** upstream.
- **[compdoge](https://github.com/compdoge/gxr-face-bridge)**: the face/tongue
  bridge bundled by XR Porting Hub. Use the dedicated
  [Galaxy XR LinkFT receiver](https://github.com/compdoge/LinkFT) for this route.
- **[MorpheApp](https://github.com/MorpheApp/morphe-desktop)**: patching,
  rebuilding and signing CLI.
- **[SteamRE/DepotDownloader](https://github.com/SteamRE/DepotDownloader)**:
  selective anonymous Steam depot downloads.
- **[booinspace](https://github.com/booinspace)**: Windows launcher, download
  selection, signing-profile reuse and build checks.

This source folder contains scripts and instructions. APKs, keys and downloaded
tools are not vendored; downloaded components retain their upstream licenses.
