# Steam Link beta 2.0.25 / 5002532

This is booinspace's experimental port of
[AngelDark92's XR Porting Hub 2.8.0](https://github.com/AngelDark92/xr-porting-hub/tree/42bef4a55bf76268c602665f03fd880e1f98d65f)
to Valve's exact **2.0.25 / 5002532** beta APK. It is separate from the
one-click builder, which follows upstream's released compatibility catalog.
It does not make the public 2.0.24 / 5002389 APK compatible.

The rooted-headset profile applies seven patches: Blue-noise dithering,
Codecs Support, GXR face and tongue bridge, Microphone input preset,
OLED color calibration, Unrestricted battery usage and Visual Delay Fix.
Controller APK patches remain excluded so they do not overlap the headset's
KernelSU controller modules. Older build scopes and their codec payload bytes
are preserved.

The beta already implements native Android XR face tracking. The face/tongue
patch adds tongue-direction transport for
[compdoge's Galaxy XR LinkFT receiver](https://github.com/compdoge/LinkFT).
It does not insert the legacy `libgxr_face_bridge.so` layer or replace Valve's
OpenXR loader. This APK is an Android application, not a KernelSU module.

## Install this build

The built APK is **41,899,823 bytes** (41.90 MB):

```text
Download/booinspace-modules/SteamLink-2.0.25-5002532-GalaxyXR-BETA.apk
```

Open it in Files to update the previous locally signed Steam Link installation.
The signing certificate matches that installation. Keep the working 2.0.20 APK
and the private Morphe signing profile. Android may reject an in-place downgrade
to 2.0.20; uninstalling an app to downgrade removes its local app data.

The APK was copied over ADB and its SHA-256 checked on the headset. It was not
installed automatically. Launch, streaming, eye/face tracking and LinkFT have
**not been runtime-tested on AZJ2 with this beta**.

## Exact inputs and evidence

- Upstream source: `42bef4a55bf76268c602665f03fd880e1f98d65f` (v2.8.0).
- Valve SteamVR beta depot: app `250820`, depot `250824`, manifest
  `5025230052748003982`; only `drivers/vrlink/resources/android-steamlinkvr-release.apk`.
- Original APK SHA-256: `3b0508ca8bac9b3f8f7aac64ddee83c40ed33226360ec67fdda23f4ea20d7bc0`.
- Original scene library: 2,333,584 bytes,
  `fcac719a50d11ba4fd76e92cd9ce25366d901c924340c91041ecffae89fd1bf5`.
- Morphe Desktop 2.1.1, Java 21, Android Build Tools 37.0.0, NDK 29.0.14206865.
- Public-source Gradle bootstrap: Morphe plugin v1.3.4
  (`a230c33f7eca1e18b07bf1114ca850421520f98d`), patcher v1.13.0
  (`70f20fcb1bc4cdaed639674d8757f57674d5764a`).
- OpenXR headers: release-1.1.49,
  `977f6675bc0057d5a54ed290cb5c71c699b1c0ab`.

The source patch adds independently inspected beta layouts, byte preconditions,
region hashes, codec GOT slots and seven tests. Native sites include microphone
preset `0xf906c`, tongue mapping `0x144004`, head-pose timestamp `0x102bb8`,
swapchain formats `0x10d658` / `0x10d6d0`, and draw return addresses
`0xf6698` / `0xf6778`. The beta codec helper is a separate resource so the
existing helper used by older builds remains byte-for-byte unchanged.

Validation: **255 passed, 52 skipped, zero failed** in `:patches:test`.
The skips require absent older decoded APK fixtures. All seven new beta tests
ran, including checks using this exact APK and library. The normal
`:patches:buildAndroid :patches:generatePatchesList` graph passed; Morphe applied
all seven selected patches. APK identity, native edits, payload hashes and
signing continuity were checked separately. See [build-info.json](build-info.json)
and [patch-result.json](patch-result.json).

## Rebuild the port

Use a fresh Linux/WSL workspace with the tool versions above. Install the SDK
tools using Google's official SDK manager, and keep signing data outside source.
Download the original APK through the existing builder's pinned DepotDownloader,
specifying the exact manifest above with `-manifest`. Verify its SHA-256 before
patching. No Valve APK or private signing key is included here.

Clone the following sources into sibling directories:

```sh
git clone --branch v2.8.0 https://github.com/AngelDark92/xr-porting-hub.git upstream
git clone --branch v1.3.4 https://github.com/MorpheApp/morphe-patches-gradle-plugin.git
git clone --branch v1.13.0 https://github.com/MorpheApp/morphe-patcher.git
git clone --branch release-1.1.49 https://github.com/KhronosGroup/OpenXR-SDK.git openxr-sdk
cd upstream
git apply /path/to/steamlink-beta-5002532-source.patch
```

Check the cloned revisions against the pins above. Compile the added codec
profile before building the patch bundle. From `upstream`, with `ANDROID_HOME`
pointing to the SDK:

```sh
llvm="$ANDROID_HOME/ndk/29.0.14206865/toolchains/llvm/prebuilt/linux-x86_64/bin"
out=../builds/steamlink-patches/build/beta-native
mkdir -p "$out"
"$llvm/aarch64-linux-android29-clang++" -std=c++17 -O2 -fPIC -shared \
  -fvisibility=hidden -static-libstdc++ -Wall -Wextra -Werror \
  -Wno-missing-field-initializers -DXR_USE_PLATFORM_ANDROID -I../openxr-sdk/include \
  extensions/codecs-support-layer/src/codecs_support_layer.cpp \
  -o "$out/libgxr_codecs_support.so" -Wl,-soname,libgxr_codecs_support.so \
  -Wl,-z,max-page-size=16384 -Wl,--exclude-libs,ALL -llog -ldl
"$llvm/llvm-strip" --strip-unneeded "$out/libgxr_codecs_support.so"
sha256sum "$out/libgxr_codecs_support.so"
cp "$out/libgxr_codecs_support.so" \
  patches/src/main/resources/steamlink/androidxr/libgxr_codecs_support_beta5002532.so
```

The helper must hash to
`5732a80c062e96559bc57bb21b52713221bd3f66ff6c0d4fae0abb787a6b6b05`.
Do not remove the pinned hash check to accept a different toolchain output.
Extract the original scene library and export these paths for the tests:

```sh
export STEAMLINK_BETA_APK=/path/to/original-5002532.apk
export STEAMLINK_BETA_SCENE=/path/to/original-libvrlink_scene.so
./gradlew :patches:test -Pgpr.user=public-source -Pgpr.key=unused
./gradlew :patches:buildAndroid :patches:generatePatchesList \
  -PreleaseChannel=stable -Pgpr.user=public-source -Pgpr.key=unused
```

The patch includes a Gradle composite-build bootstrap for the two public Morphe
source checkouts. The placeholder properties are not account credentials; no
GitHub package token is required for this build path. The bundle is generated at
`../builds/steamlink-patches/gradle/patches/libs/patches-2.8.0.mpp`.
Its embedded upstream version remains 2.8.0; identify it as this local beta port.

Use Morphe Desktop 2.1.1 and the same private `MORPHE_DATA_DIR` as the existing
installation:

```sh
java -jar /path/to/morphe-desktop-2.1.1-all.jar patch --exclusive \
  -p ../builds/steamlink-patches/gradle/patches/libs/patches-2.8.0.mpp \
  --enable='Blue-noise dithering' --enable='Codecs Support' \
  --enable='GXR face and tongue bridge' --enable='Microphone input preset' \
  --enable='OLED color calibration' --enable='Unrestricted battery usage' \
  --enable='Visual Delay Fix' -o /path/to/new-beta.apk \
  -r /path/to/patch-result.json "$STEAMLINK_BETA_APK"
```

Require a successful report with exactly those seven patches, verify the output
version is still 2.0.25 / 5002532 and run `apksigner verify --print-certs` before
installing. Never use `--force`, change the input's version to impersonate a
supported build, or continue after a failed patch.

## Credits and license

- **[AngelDark92](https://github.com/AngelDark92/xr-porting-hub)**: upstream patch
  implementations, native helpers, tests and catalogs. This adaptation is a
  local port, not an upstream release.
- **[compdoge](https://github.com/compdoge/gxr-face-bridge)**: face/tongue bridge
  work credited upstream; **[LinkFT](https://github.com/compdoge/LinkFT)** receives
  the tongue transport on the PC.
- **[MorpheApp](https://github.com/MorpheApp)**: patcher, Gradle plugin and CLI.
- **[KhronosGroup](https://github.com/KhronosGroup/OpenXR-SDK)**: OpenXR headers.
- **[SteamRE](https://github.com/SteamRE/DepotDownloader)**: official-depot APK
  downloading; **Valve** owns Steam Link VR and SteamVR.
- **[booinspace](https://github.com/booinspace)**: exact 5002532 layouts,
  isolated codec payload, build adaptation and verification.

The port source is covered by upstream's [GPLv3 license](LICENSE). Downloaded
tools and Valve's APK retain their own licenses. This directory contains the
source diff and evidence, not the APK, signing profile or downloaded dependencies.
