"""Build a disabled AZJ2 port from a pinned BlueScorpioVR window-curvature commit."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "https://github.com/BlueScorpioVR/galaxyxr-modules.git"
COMMIT = "dd1a8915e3bbb8ea44f99033c8bc0dc8fdc22bd2"
SYSTEMUI = "dc664a17617b97d2aafebac9690c4235f530cd24399fbe16b6634d5df2a6a6dc"
RENDERER = "8342a55dd62163af3653dcf2153a842e243377897ced3ca00703603d275a3d7f"
IMPRESS = "ab04d6daf57800a42170febaf33cb128441339c06bd6d46f068c0109693fee42"
FRAMEWORK = "6ec625a07d94e3e50d82eea14bcec05425de303a62a512e6b82ae57881c46ad7"


def replace(path: Path, old: str, new: str) -> None:
    data = path.read_text()
    if data.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r} in {path}")
    path.write_text(data.replace(old, new))


def integrate_rotation(module: Path) -> None:
    """Share Curvature's bridge, menu owner and supervisor with Rotation."""
    destination = module / "android/local/gxr/rotation"
    destination.mkdir(parents=True)
    for source in sorted((ROOT / "modules/window-rotation/android/local/gxr/rotation").glob("*.java")):
        shutil.copyfile(source, destination / source.name)
    props = module / "module.prop"
    replace(props, "version=0.1.7-azj2-experimental", "version=0.1.9-azj2-experimental")
    replace(props, "versionCode=108", "versionCode=110")
    replace(props, "name=Galaxy XR Curvature + Borderless Windows",
            "name=Galaxy XR Curvature + Borderless + Rotation")
    replace(props,
            "description=Experimental AZJ2 curvature with original rim hiding and hover caption after 45 seconds. One injector; installs disabled. Keep separate Borderless off.",
            "description=Experimental AZJ2 curvature, rim and pill hiding, and pitch/yaw/roll controls. One injector and shared menu. Keep separate Rotation and Borderless off. Installs disabled.")
    pins = module / "firmware.sha256"
    pins.write_text(pins.read_text() + f"{FRAMEWORK}  /system/framework/framework.jar\n")
    checker = module.parents[1] / "tools/check_window_curvature_package.py"
    expected_pins = {
        "/system_ext/priv-app/XrSystemUI/XrSystemUI.apk": SYSTEMUI,
        "/system_ext/lib64/libspaceflinger_jni_vulkan.so": RENDERER,
        "/system_ext/lib64/libImpress-jni-vulkan.so": IMPRESS,
        "/system/framework/framework.jar": FRAMEWORK,
    }
    replace(checker, "        for line in archive.read('firmware.sha256').decode().splitlines():",
            "        pins = dict((line.split('  ', 1)[1], line.split('  ', 1)[0])\n"
            "                    for line in archive.read('firmware.sha256').decode().splitlines())\n"
            f"        assert pins == {expected_pins!r}\n"
            "        for line in archive.read('firmware.sha256').decode().splitlines():")
    replace(checker, "assert len(digest) == 64 and path.startswith('/system_ext/')",
            "assert len(digest) == 64 and path in pins")

    menu = module / "android/local/gxr/curvature/MenuAttachment.java"
    replace(menu, "import android.os.Handler;",
            "import android.os.Handler;\nimport local.gxr.rotation.RotationController;\n"
            "import local.gxr.rotation.RotationMenu;")
    replace(menu, "    private final Object menu;",
            "    private static RotationController rotationController;\n"
            "    private RotationMenu rotationControls;\n"
            "    public static void setRotationController(RotationController controller) {\n"
            "        rotationController = controller;\n    }\n"
            "    private final Object menu;")
    replace(menu, "            int expanded = oldHeight + controls.getRequiredHeight();",
            "            if (rotationController != null) rotationControls = rotationController.attachMenu(menu, root);\n"
            "            int expanded = oldHeight + controls.getRequiredHeight()\n"
            "                    + (rotationControls == null ? 0 : rotationControls.getRequiredHeight());")
    replace(menu, "        controls.close();",
            "        if (rotationControls != null) rotationControls.close();\n        controls.close();")

    agent = module / "agent/main.js"
    replace(agent, "let borderless = null;", "let borderless = null;\nlet rotation = null;")
    replace(agent, "    if (borderlessTimer !== null) clearTimeout(borderlessTimer);",
            "    if (borderlessTimer !== null) clearTimeout(borderlessTimer);\n"
            "    try { if (rotation !== null) rotation.shutdown(); }\n"
            "    catch (error) { log('ROTATION_RESTORE_ERROR', {error: String(error)}); }")
    replace(agent, "                const Attachment = factory.use('local.gxr.curvature.MenuAttachment');",
            "                const Attachment = factory.use('local.gxr.curvature.MenuAttachment');\n"
            "                rotation = Java.retain(factory.use('local.gxr.rotation.RotationController').$new());\n"
            "                Attachment.setRotationController(rotation);")
    replace(agent, "            if (!stopped && borderless !== null) borderless.pulse();",
            "            if (!stopped && borderless !== null) borderless.pulse();\n"
            "            if (!stopped && rotation !== null) {\n"
            "                rotation.pulse(home);\n"
            "                const error = String(rotation.getError());\n"
            "                if (error) throw new Error('Rotation: ' + error);\n            }")
    replace(agent, "                (borderless === null || borderless.isStopped())) {",
            "                (borderless === null || borderless.isStopped()) &&\n"
            "                (rotation === null || rotation.isRestored())) {")
    replace(agent, "log('STATE', {borderlessActive:",
            "log('STATE', {rotation: rotation === null ? null : String(rotation.getStatus()), borderlessActive:")

    control = module / "control.sh"
    replace(control, "  maximum=${2:-0}",
            "  rotation=/data/adb/modules/gxr_window_rotation\n"
            "  [ ! -d \"$rotation\" ] || [ -f \"$rotation/disable\" ] || "
            "[ -f \"$rotation/remove\" ] || fail 'Disable standalone Rotation; this build includes it'\n"
            "  [ ! -d /dev/gxr-window-rotation ] && [ ! -d /dev/gxr-borderless-azj2 ] || "
            "fail 'Another window runtime is still active; stop it and fully reboot'\n"
            "  [ -z \"$(pidof frida-inject)\" ] || fail 'Another injector is active; stop it before shared window controls'\n"
            "  maximum=${2:-0}")
    replace(control, "    else echo 'Borderless: pending 45-second startup delay.'; fi",
            "    else echo 'Borderless: pending 45-second startup delay.'; fi\n"
            "    echo 'Rotation: shared Curvature menu; standalone Rotation must stay off.'")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default=UPSTREAM, help="Pinned upstream URL or local clone")
    parser.add_argument("--stagger-borderless", action="store_true",
                        help="Coordinate startup with a separate Borderless runtime")
    parser.add_argument("--integrated-borderless", action="store_true",
                        help="Include rim hiding and hover caption in the shared runtime")
    parser.add_argument("--integrated-rotation", action="store_true",
                        help="Include pitch, yaw and roll in the shared runtime (requires --integrated-borderless)")
    for name in ("java", "ecj", "r8", "android-jar", "cache", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.stagger_borderless and args.integrated_borderless:
        parser.error("Choose only one combined-window build mode")
    if args.integrated_rotation and not args.integrated_borderless:
        parser.error("--integrated-rotation requires --integrated-borderless")
    for name in ("java", "ecj", "r8", "android_jar"):
        path = getattr(args, name).resolve()
        if not path.is_file():
            parser.error(f"Missing {name}: {path}")
        setattr(args, name, path)
    args.output = args.output.resolve()
    args.cache = args.cache.resolve()
    with tempfile.TemporaryDirectory(prefix="gxr-curvature-azj2-") as temporary:
        work = Path(temporary) / "upstream"
        subprocess.run(["git", "clone", "--quiet", args.upstream, str(work)], check=True)
        subprocess.run(["git", "-C", str(work), "checkout", "--quiet", COMMIT], check=True)
        if subprocess.check_output(["git", "-C", str(work), "rev-parse", "HEAD"], text=True).strip() != COMMIT:
            raise ValueError("Unexpected upstream commit")

        module = work / "modules/window-curvature"
        (module / "firmware.sha256").write_text(
            f"{SYSTEMUI}  /system_ext/priv-app/XrSystemUI/XrSystemUI.apk\n"
            f"{RENDERER}  /system_ext/lib64/libspaceflinger_jni_vulkan.so\n"
            f"{IMPRESS}  /system_ext/lib64/libImpress-jni-vulkan.so\n"
        )
        replace(module / "control.sh", "I610UEU2AZF3:user/release-keys", "I610UES3AZJ2:user/release-keys")
        props = module / "module.prop"
        replace(props, "version=0.1.3-experimental", "version=0.1.6-azj2-experimental")
        replace(props, "versionCode=103", "versionCode=107")
        replace(props, "author=BlueScorpioVR", "author=BlueScorpioVR; AZJ2 port by nathalie")
        replace(props,
                "updateJson=https://raw.githubusercontent.com/BlueScorpioVR/galaxyxr-modules/main/updates/window-curvature.json\n",
                "")
        if args.stagger_borderless:
            replace(props, "version=0.1.6-azj2-experimental", "version=0.1.4-azj2-experimental")
            replace(props, "versionCode=107", "versionCode=105")
            (module / "service.sh").write_bytes(
                (ROOT / "scripts/curvature-stagger-service.sh").read_bytes())
        if args.integrated_borderless:
            subprocess.run(["node", "--test", str(ROOT / "tests/curvature-borderless-agent.test.mjs")],
                           check=True)
            replace(props, "version=0.1.6-azj2-experimental", "version=0.1.7-azj2-experimental")
            replace(props, "versionCode=107", "versionCode=108")
            replace(props, "name=Galaxy XR Home Space Window Curvature",
                    "name=Galaxy XR Curvature + Borderless Windows")
            replace(props,
                    "description=Opt-in task-local Curve/Flatten button and strength slider for ordinary Galaxy XR Home Space app windows. Firmware-pinned, independently supervised rollback. Installs disabled. Flat resize outline remains a known limitation.",
                    "description=Experimental AZJ2 curvature with original rim hiding and hover caption after 45 seconds. One injector; installs disabled. Keep separate Borderless off.")
            (module / "agent/borderless.mjs").write_bytes(
                (ROOT / "scripts/curvature-borderless-agent.mjs").read_bytes())
            main_agent = module / "agent/main.js"
            replace(main_agent, "import {DEX_BASE64} from './helper-dex.js';",
                    "import {DEX_BASE64} from './helper-dex.js';\n"
                    "import {installBorderless} from './borderless.mjs';")
            replace(main_agent, "let stopReason = '';",
                    "let stopReason = '';\nlet borderless = null;\nlet borderlessTimer = null;")
            replace(main_agent, "    stopReason = reason;\n    log('STOPPING', {reason});",
                    "    stopReason = reason;\n"
                    "    if (borderlessTimer !== null) clearTimeout(borderlessTimer);\n"
                    "    try { if (borderless !== null) borderless.stop(); }\n"
                    "    catch (error) { log('BORDERLESS_RESTORE_ERROR', {error: String(error)}); }\n"
                    "    log('STOPPING', {reason});")
            replace(main_agent, "            const home = !stopped && homeSpace();",
                    "            const home = !stopped && homeSpace();\n"
                    "            if (!stopped && borderless !== null) borderless.pulse();")
            replace(main_agent, "            if (stopped && tasks.size === 0) {",
                    "            if (stopped && tasks.size === 0 &&\n"
                    "                (borderless === null || borderless.isStopped())) {")
            replace(main_agent, "log('STATE', {homeSpace: home,",
                    "log('STATE', {borderlessActive: borderless !== null && !stopped, homeSpace: home,")
            replace(main_agent, "                            resolve(true);",
                    "                            log('BORDERLESS_PENDING', {delaySeconds: 45});\n"
                    "                            borderlessTimer = setTimeout(() => Java.perform(() => {\n"
                    "                                if (stopped) return;\n"
                    "                                try { borderless = installBorderless(Java, fail); }\n"
                    "                                catch (error) { fail(error); }\n"
                    "                            }), 45000);\n"
                    "                            resolve(true);")
            control = module / "control.sh"
            replace(control,
                    "    echo 'Runtime supervisor state is present; see runtime.log for per-window values.'",
                    "    echo 'Runtime supervisor state is present; see runtime.log for per-window values.'\n"
                    "    if grep -Eq '^GXR_BORDERLESS_READY|\"borderlessActive\":true' \"$LOG\"; then\n"
                    "      echo 'Borderless: attached; reopen an app to test rim and hover pill.'\n"
                    "    else echo 'Borderless: pending 45-second startup delay.'; fi")
            replace(control,
                    "  allowed || exit 0\n  maximum=${2:-0}",
                    "  allowed || exit 0\n"
                    "  [ -f /data/adb/modules/gxr_borderless_azj2/disable ] || "
                    "[ ! -d /data/adb/modules/gxr_borderless_azj2 ] || "
                    "fail 'Disable separate Borderless and fully reboot before combined use'\n"
                    "  maximum=${2:-0}")
            replace(control,
                    "    if [ \"$graceful\" -eq 1 ] && [ \"$failed\" -eq 0 ]; then\n"
                    "      rm -f \"$MODDIR/session-open\"\n"
                    "      echo 'STOPPED - agent confirmed all owned tasks flat; injector detached'",
                    "    if [ \"$graceful\" -eq 1 ] && [ \"$failed\" -eq 0 ]; then\n"
                    "      : > \"$MODDIR/disable\"\n"
                    "      printf '%s\\n' 'Combined rim restoration needs a full reboot before reset.' > \"$MODDIR/failure\"\n"
                    "      echo 'DISABLED - curvature flattened; reboot to restore stock rims'")
            subprocess.run(["node", str(ROOT / "tests/curvature-combined-lifecycle.mjs"),
                            str(main_agent)], check=True)
        if args.integrated_rotation:
            integrate_rotation(module)
            subprocess.run([sys.executable, str(ROOT / "tests/window-controls-conflicts.test.py"),
                            str(module / "control.sh")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/rotation-controller-host.test.py"),
                            "--java", str(args.java), "--ecj", str(args.ecj)], check=True)
            subprocess.run(["node", str(ROOT / "tests/curvature-combined-lifecycle.mjs"),
                            str(module / "agent/main.js"), "--rotation"], check=True)
            math_classes = Path(temporary) / "rotation-tests"
            subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
                            "-proc:none", "-failOnWarning", "-d", str(math_classes),
                            str(module / "android/local/gxr/rotation/RotationMath.java"),
                            str(ROOT / "tests/RotationMathTest.java")], check=True)
            subprocess.run([str(args.java), "-cp", str(math_classes),
                            "local.gxr.rotation.RotationMathTest"], check=True)
        (module / "install-info.txt").write_text(
            "AZJ2 port of BlueScorpioVR's window-curvature module. Installs DISABLED.\n"
            "Firmware I610UES3AZJ2 only; APK and native hashes are checked before attach.\n" +
            ("One-injector borderless/curvature build is experimental; see README.md.\n"
             if args.integrated_borderless else
             "Staggered startup with borderless is experimental; see README.md.\n"
             if args.stagger_borderless else
             "Standalone curvature source worked on the headset; see README.md.\n")
        )
        (module / "README.md").write_bytes((ROOT / "docs/CURVATURE.md").read_bytes())
        replace(work / "tools/build_window_curvature.py",
                "temp_root = Path.home() / 'AppData/Local/Temp/opencode'", "temp_root = None")

        subprocess.run(["node", "--test", "tests/window-curvature-policy.test.mjs",
                        "tests/window-curvature-mesh.test.mjs"], cwd=work, check=True)
        subprocess.run([sys.executable, "tools/check_window_curvature.py", "--java", str(args.java),
                        "--ecj", str(args.ecj)], cwd=work, check=True)
        subprocess.run([sys.executable, "tools/build_window_curvature.py",
                        "--java", str(args.java), "--ecj", str(args.ecj), "--r8", str(args.r8),
                        "--android-jar", str(args.android_jar), "--cache", str(args.cache),
                        "--output", str(args.output), "--no-update-feed"], cwd=work, check=True)
        version = "0.1.9" if args.integrated_rotation else "0.1.7" if args.integrated_borderless else "0.1.4" if args.stagger_borderless else "0.1.6"
        package = args.output / f"gxr-window-curvature-{version}-azj2-experimental-disabled.zip"
        subprocess.run([sys.executable, "tools/check_window_curvature_package.py", str(package)],
                       cwd=work, check=True)
        print(package)


if __name__ == "__main__":
    main()
