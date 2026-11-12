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
ART = "afc9dde61f50e1e2b085c886e2bad7df98c433b28e0f01041221e1d138c321c5"
CMC_PATCH_SHA = "354bec3059c53cf9f83d3d8f3dcc81417654c0a2620bfac188c52e0092ba84bd"


def replace(path: Path, old: str, new: str) -> None:
    data = path.read_text()
    if data.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r} in {path}")
    path.write_text(data.replace(old, new))


def patch_art_cmc(work: Path, module: Path) -> None:
    """Keep Frida's cloned methods visible to this firmware's moving GC."""
    shutil.copyfile(ROOT / "scripts/curvature/frida-java-bridge-cmc.patch",
                    module / "agent/frida-java-bridge-cmc.patch")
    builder = work / "tools/build_window_curvature.py"
    replace(builder, "        diagnostics = []",
            "        patch = MODULE / 'agent/frida-java-bridge-cmc.patch'\n"
            f"        if hashlib.sha256(patch.read_bytes()).hexdigest() != {CMC_PATCH_SHA!r}:\n"
            "            raise ValueError('CMC bridge patch integrity mismatch')\n"
            "        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=bridge_dir, check=True)\n"
            "        subprocess.run(['git', 'apply', str(patch)], cwd=bridge_dir, check=True)\n"
            "        diagnostics = []")
    replace(builder, "        'bridgeVersion': '7.0.13', 'bridgeSha512': BRIDGE_SHA512,",
            "        'bridgeVersion': '7.0.13', 'bridgeSha512': BRIDGE_SHA512,\n"
            "        'bridgeCmcPatch': {\n"
            "            'url': 'https://github.com/frida-packages/frida-java-bridge/pull/410',\n"
            "            'commit': 'fcdd7186467e8c6dfdcef888208807c9fc0424db',\n"
            f"            'sha256': {CMC_PATCH_SHA!r},\n"
            "            'localChange': 'Fail before cloning if the CMC allocator is unavailable',\n"
            "        },")
    replace(module / "THIRD_PARTY.md", "bundled unmodified source through Frida Compiler.",
            "bundled through Frida Compiler with the CMC allocation patch below.")
    with (module / "THIRD_PARTY.md").open("a") as notices:
        notices.write(
            "\nCMC method-allocation patch by pandasauce:\n"
            "https://github.com/frida-packages/frida-java-bridge/pull/410\n"
            "Upstream commit: fcdd7186467e8c6dfdcef888208807c9fc0424db.\n"
            "Local addition: refuse CMC cloning if its allocator is unavailable.\n"
            "The original npm source and complete local patch are included;\n"
            "the patch is bin/source/agent/frida-java-bridge-cmc.patch.\n")


def integrate_rotation(module: Path) -> None:
    """Share Curvature's bridge, menu owner and supervisor with Rotation."""
    destination = module / "android/local/gxr/rotation"
    destination.mkdir(parents=True)
    for source in sorted((ROOT / "modules/window-rotation/android/local/gxr/rotation").glob("*.java")):
        shutil.copyfile(source, destination / source.name)
    props = module / "module.prop"
    replace(props, "version=0.1.7-azj2-experimental", "version=0.1.19-azj2-experimental")
    replace(props, "versionCode=108", "versionCode=120")
    replace(props, "name=Galaxy XR Curvature + Borderless Windows",
            "name=Galaxy XR Curvature + Borderless + Rotation")
    replace(props,
            "description=Experimental AZJ2 curvature with original rim hiding and hover caption after 45 seconds. One injector; installs disabled. Keep separate Borderless off.",
            "description=Experimental AZJ2 window controls with Action settings, curvature, borderless, rotation sliders and opt-in wrist-grab rotation. Built-in recovery and coordinated restart resume. Keep separate window modules off. Installs disabled.")
    pins = module / "firmware.sha256"
    pins.write_text(pins.read_text() + f"{FRAMEWORK}  /system/framework/framework.jar\n"
                    f"{ART}  /apex/com.android.art/lib64/libart.so\n")
    checker = module.parents[1] / "tools/check_window_curvature_package.py"
    expected_pins = {
        "/system_ext/priv-app/XrSystemUI/XrSystemUI.apk": SYSTEMUI,
        "/system_ext/lib64/libspaceflinger_jni_vulkan.so": RENDERER,
        "/system_ext/lib64/libImpress-jni-vulkan.so": IMPRESS,
        "/system/framework/framework.jar": FRAMEWORK,
        "/apex/com.android.art/lib64/libart.so": ART,
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


def integrate_recovery(work: Path, module: Path) -> None:
    """Recover a previous full boot before attaching; keep same-boot quarantine."""
    shutil.copyfile(ROOT / "scripts/curvature-recovery.sh", module / "recovery.sh")
    shutil.copyfile(ROOT / "scripts/curvature-boot-recovery.sh", module / "boot-recovery.sh")
    shutil.copyfile(ROOT / "scripts/curvature-action.sh", module / "action.sh")
    replace(work / "tools/build_window_curvature.py",
            "'action.sh', 'auto.sh', 'uninstall.sh', 'control.sh', 'firmware.sha256',",
            "'action.sh', 'auto.sh', 'uninstall.sh', 'control.sh', 'firmware.sha256',\n"
            "        'recovery.sh', 'boot-recovery.sh',")
    replace(module / "customize.sh", "for script in service.sh action.sh auto.sh control.sh uninstall.sh; do",
            "for script in service.sh action.sh auto.sh control.sh uninstall.sh recovery.sh boot-recovery.sh; do")
    control = module / "control.sh"
    replace(control, "STATE=/dev/gxr-window-curvature\n",
            "STATE=/dev/gxr-window-curvature\nLAUNCH_LOCK=/dev/gxr-window-curvature-launch\n")
    replace(control, "  else echo 'Runtime not running.'; fi",
            "  elif [ -d \"$LAUNCH_LOCK\" ]; then\n"
            "    echo 'STARTING - validating or waiting for SystemUI startup.'\n"
            "  else echo 'Runtime not running.'; fi")
    replace(control, 'case "${1:-status}" in',
            '. "$MODDIR/boot-recovery.sh"\ncase "${1:-status}" in')
    replace(control, "  echo 'Enable/re-enable: turn checkbox on and reboot. No app curvature is saved across reboot.'",
            "  echo 'After a full reboot, enable and tap Action to start. Action also exports logs.'")
    old_reset = control.read_text().split("\nreset)\n", 1)[1].split("\nrun)\n", 1)[0]
    replace(control, "\nreset)\n" + old_reset + "\nrun)\n",
            "\nreset)\n"
            "  [ -f \"$MODDIR/disable\" ] || { echo 'Disable the module first.'; exit 1; }\n"
            "  [ ! -d \"$STATE\" ] || { echo 'Runtime state remains; fully reboot first.'; exit 1; }\n"
            "  [ ! -d \"$LAUNCH_LOCK\" ] || { echo 'Controller remains; fully reboot first.'; exit 1; }\n"
            "  clear_after_reboot || exit 1\n"
            "  echo 'Recovery complete. Module remains disabled.'\n"
            "  ;;\nrun)\n")
    prefix = ('run)\n  [ "$(id -u)" = 0 ] || { echo \'Root required.\'; exit 1; }\n'
              '  allowed || exit 0\n')
    replace(control, prefix, prefix +
            "  mkdir \"$LAUNCH_LOCK\" 2>/dev/null || { echo 'Controller already starting or active.'; exit 0; }\n"
            "  trap 'rmdir \"$LAUNCH_LOCK\" 2>/dev/null || true' EXIT\n")
    checked = "  sha256sum -c \"$MODDIR/firmware.sha256\" >/dev/null 2>&1 || fail 'Firmware APK/native hash mismatch'\n"
    replace(control, checked, checked +
            "  clear_after_reboot || fail 'Previous quarantine requires a full reboot or manual review'\n"
            "  allowed || exit 0\n")
    replace(control, "    fi\n  }\n  trap finish EXIT\n",
            "    fi\n    rmdir \"$LAUNCH_LOCK\" 2>/dev/null || true\n  }\n  trap finish EXIT\n")


def integrate_restart(work: Path, module: Path) -> None:
    """Resume only after clean hook removal and verified SystemUI replacement."""
    shutil.copyfile(ROOT / "scripts/curvature-restart.sh", module / "restart.sh")
    hooks = [f"restart-{phase}.sh" for phase in ("prepare", "stopped", "started", "abort")]
    for name in hooks:
        shutil.copyfile(ROOT / "scripts/curvature-restart-hook.sh", module / name)
    replace(work / "tools/build_window_curvature.py",
            "        'recovery.sh', 'boot-recovery.sh',",
            "        'recovery.sh', 'boot-recovery.sh', 'restart.sh',\n"
            "        " + ", ".join(repr(name) for name in hooks) + ",")
    installer = module / "customize.sh"
    replace(installer, "uninstall.sh recovery.sh boot-recovery.sh; do",
            "uninstall.sh recovery.sh boot-recovery.sh restart.sh " + " ".join(hooks) + "; do")
    control = module / "control.sh"
    replace(control, '  mkdir "$LAUNCH_LOCK" 2>/dev/null ||',
            '  [ ! -f /dev/ksu-restart-stage/busy ] || { echo "KernelSU restart in progress; startup deferred."; exit 0; }\n'
            '  mkdir "$LAUNCH_LOCK" 2>/dev/null ||')
    replace(control, "  target_identity=$(identity \"$target\")\n",
            "  target_identity=$(identity \"$target\")\n"
            "  [ -z \"${restart_target:-}\" ] || [ \"$target_identity\" = \"$restart_target\" ] || "
            "fail 'SystemUI changed during the planned restart handoff'\n")
    replace(control, "  failed=0\n", "  failed=0\n  planned=0\n")
    replace(control, "    trap - EXIT INT TERM HUP\n",
            "    trap - EXIT INT TERM HUP\n    planned_restored=0\n")
    replace(control, '    if [ "$graceful" -eq 1 ] && [ "$failed" -eq 0 ]; then',
            '    if [ "$planned" -eq 1 ] && [ "$graceful" -eq 1 ] && [ "$failed" -eq 0 ] && allowed; then\n'
            '      planned_restored=1\n'
            '    elif [ "$graceful" -eq 1 ] && [ "$failed" -eq 0 ]; then')
    replace(control, '    rmdir "$LAUNCH_LOCK" 2>/dev/null || true\n  }',
            '    rmdir "$LAUNCH_LOCK" 2>/dev/null || true\n'
            '    if [ "$planned_restored" -eq 1 ]; then\n'
            '      if sh "$MODDIR/restart.sh" complete "$target_identity"; then\n'
            "        echo 'PREPARED - hooks removed and injector detached; checkbox retained'\n"
            '      else\n'
            '        : > "$MODDIR/disable"\n'
            "        echo 'Planned restart cleanup was not verified; fully reboot before retrying.' > \"$MODDIR/failure\"\n"
            '      fi\n    fi\n  }')
    replace(control, "    printf 'pulse\\n' >&3 || { failed=1; break; }",
            "    if [ -f /dev/gxr-window-curvature-restart/request ] &&\n"
            '        sh "$MODDIR/restart.sh" requested "$target_identity"; then planned=1; break; fi\n'
            "    printf 'pulse\\n' >&3 || { failed=1; break; }")
    replace(control, '  if owns_state; then echo \'Stop remains pending; inspect runtime.log. Do not reattach.\'; exit 1; fi\n',
            '  if owns_state; then echo \'Stop remains pending; inspect runtime.log. Do not reattach.\'; exit 1; fi\n'
            '  clear_after_reboot || exit 1\n')


def integrate_features(work: Path, module: Path) -> None:
    """Use the existing root supervisor and Manager WebUI for persistent flags."""
    shutil.copyfile(ROOT / "scripts/curvature-features.sh", module / "features.sh")
    shutil.copytree(ROOT / "modules/window-controls/webroot", module / "webroot")
    for name in ("curvature-features-agent", "curvature-grab-agent"):
        shutil.copyfile(ROOT / f"scripts/{name}.mjs", module / "agent" / f"{name}.mjs")
    builder = work / "tools/build_window_curvature.py"
    replace(builder, "        'recovery.sh', 'boot-recovery.sh', 'restart.sh',",
            "        'recovery.sh', 'boot-recovery.sh', 'restart.sh', 'features.sh',")
    replace(builder, "    assert payload['disable'] == payload['skip_mount'] == b''",
            "    for path in sorted((MODULE / 'webroot').iterdir()):\n"
            "        if path.is_file(): payload['webroot/' + path.name] = path.read_bytes()\n"
            "    assert payload['disable'] == payload['skip_mount'] == b''")
    installer = module / "customize.sh"
    replace(installer, "set_perm_recursive",
            "previous_features=/data/adb/modules/gxr_window_curvature/features.conf\n"
            'if [ -f "$previous_features" ] && [ "$MODPATH" != /data/adb/modules/gxr_window_curvature ]; then\n'
            '  cp "$previous_features" "$MODPATH/features.conf" || abort "Cannot retain feature settings"\n'
            "fi\n"
            'sh "$MODPATH/features.sh" wire >/dev/null || abort "Invalid saved feature settings"\n'
            "set_perm_recursive")
    replace(installer, "uninstall.sh recovery.sh", "uninstall.sh features.sh recovery.sh")
    with installer.open("a") as script:
        script.write('\n[ ! -f "$MODPATH/features.conf" ] || set_perm "$MODPATH/features.conf" 0 0 0600\n')
    control = module / "control.sh"
    replace(control, "    printf 'pulse\\n' >&3 || { failed=1; break; }",
            '    selected=$(sh "$MODDIR/features.sh" wire) || { failed=1; break; }\n'
            '    printf "%s\\n" "$selected" >&3 || { failed=1; break; }\n'
            "    printf 'pulse\\n' >&3 || { failed=1; break; }")

    menu = module / "android/local/gxr/curvature/MenuAttachment.java"
    text = menu.read_text().replace("controls.getRequiredHeight()", "curvatureHeight")
    text = text.replace("        try {\n            parent.addView(controls",
                        "        int curvatureHeight = local.gxr.rotation.WindowFeatures.curvature ? controls.getRequiredHeight() : 0;\n"
                        "        if (curvatureHeight == 0) controls.setVisibility(View.GONE);\n"
                        "        try {\n            parent.addView(controls")
    menu.write_text(text)
    controls = module / "android/local/gxr/curvature/CurvatureControls.java"
    replace(controls, "            try { session.toggle(); update(); }",
            "            if (!local.gxr.rotation.WindowFeatures.curvature) return;\n"
            "            try { session.toggle(); update(); }")
    replace(controls, "if (!fromUser || stopped) return;",
            "if (!fromUser || stopped || !local.gxr.rotation.WindowFeatures.curvature) return;")
    replace(controls, "if (!stopped) applyStrength(bar.getProgress());",
            "if (!stopped && local.gxr.rotation.WindowFeatures.curvature) applyStrength(bar.getProgress());")

    agent = module / "agent/main.js"
    replace(agent, "import {installBorderless} from './borderless.mjs';",
            "import {installBorderless} from './borderless.mjs';\n"
            "import {installGrabRotation} from './curvature-grab-agent.mjs';\n"
            "import {parseFeatureCommand, applyFeatureSettings} from './curvature-features-agent.mjs';")
    replace(agent, "let rotation = null;",
            "let rotation = null;\nlet grab = null;\nlet Features = null;\n"
            "let featureValues = [true, true, true, false];\nlet appliedFeatures = '';\n"
            "function refreshFeatures() {\n"
            "    if (Features === null || grab === null || appliedFeatures === featureValues.join('')) return;\n"
            "    applyFeatureSettings(featureValues, {Features, rotation, grab, borderless, tasks});\n"
            "    appliedFeatures = featureValues.join('');\n"
            "    log('SETTINGS', {curvature: featureValues[0], borderless: featureValues[1],\n"
            "        rotation: featureValues[2], grab: featureValues[3]});\n}\n")
    replace(agent, "    try { if (rotation !== null) rotation.shutdown(); }",
            "    try { if (grab !== null) grab.stop(); }\n"
            "    catch (error) { log('GRAB_RESTORE_ERROR', {error: String(error)}); }\n"
            "    try { if (rotation !== null) rotation.shutdown(); }")
    replace(agent, "                Attachment.setRotationController(rotation);",
            "                Attachment.setRotationController(rotation);\n"
            "                Features = factory.use('local.gxr.rotation.WindowFeatures');")
    replace(agent, "                            installNative();",
            "                            grab = installGrabRotation(Java, rotation, permitted, nowMs);\n"
            "                            refreshFeatures();\n                            installNative();")
    replace(agent, "factory.use('local.gxr.curvature.CaptionVisibility'));",
            "factory.use('local.gxr.curvature.CaptionVisibility'), featureValues[1], rotation);")
    replace(agent, "                if (!entry.session.heartbeat())",
            "                if (!featureValues[0] && entry.session.getValue() > 0) entry.session.set(0);\n"
            "                if (!entry.session.heartbeat())")
    replace(agent, "                rotation.pulse(home);",
            "                rotation.pulse(home);\n"
            "                if (grab !== null) grab.pulse(home);")
    replace(agent, "        const command = line.trim();",
            "        const command = line.trim();\n"
            "        const values = parseFeatureCommand(command);\n"
            "        if (values !== null && !stopped) {\n"
            "            featureValues = values;\n"
            "            Java.perform(() => { try { refreshFeatures(); } catch (error) { fail(error); } });\n"
            "            return;\n        }")


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
        replace(props, "author=BlueScorpioVR", "author=BlueScorpioVR; AZJ2 port by booinspace")
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
            shutil.copyfile(ROOT / "scripts/curvature/CaptionVisibility.java",
                            module / "android/local/gxr/curvature/CaptionVisibility.java")
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
                    "                                try { borderless = installBorderless(Java, fail,\n"
                    "                                    factory.use('local.gxr.curvature.CaptionVisibility')); }\n"
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
            patch_art_cmc(work, module)
            integrate_recovery(work, module)
            integrate_restart(work, module)
            integrate_features(work, module)
            subprocess.run(["node", "--test", str(ROOT / "tests/window-grab-features.test.mjs"),
                            str(ROOT / "tests/window-settings-ui.test.mjs")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/window-feature-settings.test.py")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/curvature-boot-recovery.test.py"),
                            str(module)], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/curvature-restart.test.py"),
                            str(module)], check=True)
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
        version = "0.1.19" if args.integrated_rotation else "0.1.7" if args.integrated_borderless else "0.1.4" if args.stagger_borderless else "0.1.6"
        package = args.output / f"gxr-window-curvature-{version}-azj2-experimental-disabled.zip"
        subprocess.run([sys.executable, "tools/check_window_curvature_package.py", str(package)],
                       cwd=work, check=True)
        print(package)


if __name__ == "__main__":
    main()
