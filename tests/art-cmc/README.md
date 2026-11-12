# Disposable ART/CMC bridge test

This test runs in its own shell-owned `app_process`, with no APK installation,
root access, SystemUI attachment, display changes or network listener. Frida
Gadget loads a local script through its documented
[Script interaction](https://frida.re/docs/gadget/#script).

The Java program calls a hooked method 20,000 times while another thread
requests GC. The original method briefly sleeps every eighth call, allowing
collection while the cloned method is on the stack. It checks every return
value, the hook count and overlap with at least ten GC requests.

Build after the combined module has populated the dependency cache. Use a
JDK with `javac`, the same Frida 17.23.3 Python environment and SDK paths as
the main build:

```sh
.build/venv/bin/python tests/art-cmc/build.py \
  --r8 "$GXR_R8" --android-jar "$GXR_ANDROID_JAR" \
  --bridge .build/cache/frida-java-bridge-7.0.13.tgz \
  --output .build/art-cmc
curl -fL https://github.com/frida/frida/releases/download/17.23.3/frida-gadget-17.23.3-android-arm64.so.xz \
  -o .build/art-cmc/gadget.xz
printf '%s  %s\n' aeb3109844d69f5745438597667841a9141e8701a174341999e1479a4c97925f \
  .build/art-cmc/gadget.xz | shasum -a 256 -c -
xz -dc .build/art-cmc/gadget.xz > .build/art-cmc/libgadget.so
adb shell mkdir -p /data/local/tmp/gxr-art-cmc-probe
adb push .build/art-cmc/classes.dex .build/art-cmc/unpatched.js \
  .build/art-cmc/patched.js .build/art-cmc/libgadget.so \
  tests/art-cmc/run.sh /data/local/tmp/gxr-art-cmc-probe/
adb shell sh /data/local/tmp/gxr-art-cmc-probe/run.sh unpatched 1
adb shell sh /data/local/tmp/gxr-art-cmc-probe/run.sh patched 1
```

The control run can crash its disposable process. It must not crash SystemUI.
`PROBE_ART` must report `cmc:1` and `allocator:true`. The script records logs
under `unpatched-1` and `patched-1`; a second numeric argument selects a fresh
run directory without overwriting evidence. Collect native tombstones through
`adb logcat -b crash -d` when needed.

On SM-I610 AZJ2 with ART SHA-256
`afc9dde61f50e1e2b085c886e2bad7df98c433b28e0f01041221e1d138c321c5`,
the original bridge crashed in `ReferenceMapVisitor::VisitFrame` during CMC
thread flipping. The patched bridge completed all 20,000 calls. A leaf-method
test passed with both bridges; keeping the original method on the stack was
necessary to reproduce the failure.

This supports the upstream fix; it does not prove the cause of every SystemUI
crash or establish long-term window-module stability. The patch is credited
in [Sources](../../docs/SOURCES.md).

After pulling the logs, remove only the test's temporary directory:

```sh
adb pull /data/local/tmp/gxr-art-cmc-probe .build/art-cmc-evidence
adb shell rm -r /data/local/tmp/gxr-art-cmc-probe
```
