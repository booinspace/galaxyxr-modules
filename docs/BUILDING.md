# Building the modules

Each module keeps its existing build command, firmware pins and upstream source
revision. The Python builders share [gxr_build.py](../scripts/gxr_build.py) for
the repeated work: deterministic ZIPs, checksums, installer validation, Java/DEX
helpers, exact source replacements, NDK selection and pinned Git exports.
The library uses only Python's standard library. Run builders from a full clone;
copying a single builder without its shared library is no longer sufficient.

`port-package.py` remains a compatibility entry point for older recipes. New
builders import `gxr_build` directly. The unmodified Wi-Fi ADB ZIP is validated
and copied, rather than repackaged. Modules with bundled local build recipes
also include the shared library in their source payload.

Shared validation checks the GXR installer layout, disabled installation,
supported startup entries, path depth, executable permissions, complete restart
hooks and the full checksum manifest. Firmware hashes, vendor ABI checks,
thermal limits, cleanup and quarantine stay in their module-specific code.

Rotation now belongs to Window Controls. Its unchanged Java helpers live under
`modules/window-controls/android/local/gxr/rotation/`; the standalone builder,
agent and module scripts have been removed. Existing conflict checks remain so
an old installed Rotation module cannot run alongside the combined module.

## Fedora WSL container

The module builders can run directly on Fedora with the tools below installed.
For an isolated build environment, run this from the Fedora repository:

```sh
cd ~/Documents/repos/galaxyxr-modules
./scripts/build-fedora.sh --shell
```

The wrapper asks for sudo to use rootful Podman, builds the image and opens Bash
at `/repo`. It includes JDK 21, Python, Frida 17.23.3, Node.js 22, ECJ 3.39.0,
CMake and the host C/C++ tools. It mounts your existing `~/Android/Sdk` read-only;
that SDK must contain Android command-line tools (including their Kotlin
libraries), platform `android-37.0`, build-tools `37.0.0` and both NDKs listed
below. SDK packages and licenses stay in that existing installation.
No host JDK, Python, Node.js or Frida installation is needed for container builds.

Inside the container, the tool paths are already set:

```sh
python3 scripts/build-wear-dim.py \
  --java "$JAVA_HOME/bin/java" --javac "$JAVA_HOME/bin/javac" \
  --r8 "$GXR_R8" --android-jar "$GXR_ANDROID_JAR" --output "$GXR_OUTPUT"
python3 scripts/build-questlhsync-azj2.py --ndk "$GXR_NDK28" --output "$GXR_OUTPUT"
```

`GXR_ECJ`, `GXR_CACHE` and `GXR_NDK29` are also available for the other existing
build recipes. Pass `--output "$GXR_OUTPUT"` so artifacts go to the host's
`.build/output/`; `/repo` is read-only. `exit` leaves the container. To run one
command without an interactive shell, use `./scripts/build-fedora.sh -- COMMAND`.
The Windows PowerShell/.NET companion build still runs separately on Windows.

This wrapper uses host networking because the current WSL chroot cannot create
Podman's nftables bridge. Start Fedora through its normal `enter-fedora` launcher
so `/dev`, `/proc`, `/sys` and `/run` are mounted. A direct `chroot /mnt/fedora ...`
does not prepare those mounts. The wrapper checks all four mounts before
starting Podman; it does not change the host's mount setup.

## Requirements and commands

Use Linux or WSL for the complete headset build. Java builders need a JDK,
Android platform JAR and D8/R8. Window Controls and Borderless also need
`frida==17.23.3`; Window Controls uses Node.js and ECJ 3.39.0. Native ports use
the exact NDK revision listed below. Builds do not need ADB or root access.

Set these paths to your installed tools:

```sh
export GXR_SDK=/path/to/android-sdk
export GXR_ECJ=/path/to/ecj-3.39.0.jar
export GXR_R8="$GXR_SDK/cmdline-tools/latest/lib/r8.jar"
export GXR_ANDROID_JAR="$GXR_SDK/platforms/android-37.0/android.jar"
```

| Builder | Requirements and instructions |
| --- | --- |
| `build-window-curvature-azj2.py` | Frida, Node.js, JDK, ECJ and D8; [Window Controls](CURVATURE.md#build) |
| `build-audio-mixer-azj2.py` | Same Window Controls toolchain; builds native per-app volume controls in its shared runtime; [Audio Mixer](../modules/audio-mixer/README.md#build-on-linux-or-fedora) |
| `build-quick-controls-azj2.py` | Same Window Controls toolchain; builds Audio Mixer and the left-pinch native Quick Settings shortcut; [Quick Settings pinch](../modules/quick-settings-gesture/README.md#package-and-build) |
| `build-borderless.py` | Frida; [legacy Borderless](BORDERLESS.md) |
| `build-bread-azj2.py` | JDK, javac and D8; [mic, passthrough and low-light ports](BREAD-AZJ2.md) |
| `build-wear-dim.py` | JDK, javac and D8; [display blanking](../modules/wear-dim/README.md) |
| `build-questlhsync-azj2.py` | NDK 28.2.13676358; [QuestLHSync](../modules/questlhsync/README.md) |
| `build-framebuffer10-azj2.py` | NDK 28.2.13676358; [Framebuffer10](../modules/framebuffer10/README.md) |
| `build-openxr-quality-azj2.py` | NDK 28.2.13676358 and host C++17 compiler; [OpenXR QUALITY](../modules/openxr-quality/README.md) |
| `build-root-face-tracking-azj2.py` | NDK 29.0.14206865; [root face tracking](../modules/root-face-tracking/README.md) |
| `build-wifi-adb-azj2.py` | Python and Git; [Wi-Fi ADB](../modules/wifi-adb/README.md) |
| `build-mvhevc-azj2.py` | Python; [MV-HEVC eye fix](../modules/mvhevc-eye-fix/README.md) |
| `build-port-diagnostics.py` | Python; packages the read-only firmware exporter |
| `build-vd-eye-fix.ps1` | Windows PowerShell and .NET SDK; [VD gaze companion](../companions/vd-eye-fix/README.md) |

Generated ZIPs and checksums stay in ignored `releases/` or the builder's
`--output` directory. Publish binaries through GitHub Releases. These build
changes do not increase module versions or require reinstalling a working module.

## Checks

Run the shared helper tests without an Android toolchain:

```sh
python3 -B tests/build-helpers.test.py
python3 -B tests/port-package.test.py
python3 -B tests/window-installer-contract.test.py
```

The helper tests reject altered payloads, incomplete manifests, duplicate ZIP
entries, missing executable permissions, symlinks, partial restart hooks and
ambiguous source patches. A temporary Git fixture checks that pinned exports
exclude working-tree edits and untracked files.

Each module's guide lists its build and policy/lifecycle checks. After rebuilding,
run its package tests too. Build results establish compilation and archive
integrity; they do not establish behaviour on a headset. Keep device-confirmed
release ZIPs available when testing a newly compiled package.
