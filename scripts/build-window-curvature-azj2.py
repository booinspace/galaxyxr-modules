"""Build a disabled AZJ2 port from a pinned BlueScorpioVR window-curvature commit."""

import argparse
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "https://github.com/BlueScorpioVR/galaxyxr-modules.git"
COMMIT = "dd1a8915e3bbb8ea44f99033c8bc0dc8fdc22bd2"
SYSTEMUI = "dc664a17617b97d2aafebac9690c4235f530cd24399fbe16b6634d5df2a6a6dc"
RENDERER = "8342a55dd62163af3653dcf2153a842e243377897ced3ca00703603d275a3d7f"
UI_RENDERER = "f6e34cf42f704c5d3ced9cca18dd392abf4925cde9e30c3b752a34be4102a809"
IMPRESS = "ab04d6daf57800a42170febaf33cb128441339c06bd6d46f068c0109693fee42"
FRAMEWORK = "6ec625a07d94e3e50d82eea14bcec05425de303a62a512e6b82ae57881c46ad7"
ART = "afc9dde61f50e1e2b085c886e2bad7df98c433b28e0f01041221e1d138c321c5"
CMC_PATCH_SHA = "354bec3059c53cf9f83d3d8f3dcc81417654c0a2620bfac188c52e0092ba84bd"
QUICK_PATCH_SHA = "bb32f1de5a6d30bf82977c29af9c673a3550f8d0289b519b5bc0fd33fd0a56ca"
DISPATCH_PATCH_SHA = "441a84e4b7fb5462eafd5e8b712fb6fbbe43603515cd6dd6ff98b8e458803cde"
SUPERVISOR_LEASE_MS = 5000


def replace(path: Path, old: str, new: str) -> None:
    data = path.read_text()
    if data.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r} in {path}")
    path.write_text(data.replace(old, new))


def check_gxr_installer_payload(package: Path) -> None:
    """Apply this manager's startup/state restrictions after upstream ZIP checks."""
    forbidden = runpy.run_path(str(ROOT / "scripts/port-package.py"))["FORBIDDEN"]
    with ZipFile(package) as archive:
        unsupported = forbidden.intersection(archive.namelist())
    if unsupported:
        raise ValueError("Unsupported GXR startup/state payload: " + ", ".join(sorted(unsupported)))


def patch_art_cmc(work: Path, module: Path) -> None:
    """Apply the exact ART bridge guards and validate their cleanup transaction."""
    shutil.copyfile(ROOT / "scripts/curvature/frida-java-bridge-cmc.patch",
                    module / "agent/frida-java-bridge-cmc.patch")
    shutil.copyfile(ROOT / "scripts/curvature/frida-java-bridge-quick-code.patch",
                    module / "agent/frida-java-bridge-quick-code.patch")
    shutil.copyfile(ROOT / "tests/bridge-quick-code.test.mjs", module / "agent/check-quick-code.mjs")
    shutil.copyfile(ROOT / "scripts/curvature/frida-java-bridge-dispatch.patch",
                    module / "agent/frida-java-bridge-dispatch.patch")
    shutil.copyfile(ROOT / "tests/bridge-dispatch.test.py", module / "agent/check-dispatch.py")
    builder = work / "tools/build_window_curvature.py"
    replace(builder, "        diagnostics = []",
            "        patch = MODULE / 'agent/frida-java-bridge-cmc.patch'\n"
            f"        if hashlib.sha256(patch.read_bytes()).hexdigest() != {CMC_PATCH_SHA!r}:\n"
            "            raise ValueError('CMC bridge patch integrity mismatch')\n"
            "        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=bridge_dir, check=True)\n"
            "        subprocess.run(['git', 'apply', str(patch)], cwd=bridge_dir, check=True)\n"
            "        patch = MODULE / 'agent/frida-java-bridge-quick-code.patch'\n"
            f"        if hashlib.sha256(patch.read_bytes()).hexdigest() != {QUICK_PATCH_SHA!r}:\n"
            "            raise ValueError('Quick-code bridge patch integrity mismatch')\n"
            "        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=bridge_dir, check=True)\n"
            "        subprocess.run(['git', 'apply', str(patch)], cwd=bridge_dir, check=True)\n"
            "        subprocess.run(['node', str(agent / 'check-quick-code.mjs'),\n"
            "                        str(bridge_dir / 'lib/android.js'),\n"
            "                        str(bridge_dir / 'lib/class-factory.js')], check=True)\n"
            "        patch = MODULE / 'agent/frida-java-bridge-dispatch.patch'\n"
            f"        if hashlib.sha256(patch.read_bytes()).hexdigest() != {DISPATCH_PATCH_SHA!r}:\n"
            "            raise ValueError('Dispatch bridge patch integrity mismatch')\n"
            "        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=bridge_dir, check=True)\n"
            "        subprocess.run(['git', 'apply', str(patch)], cwd=bridge_dir, check=True)\n"
            "        subprocess.run([sys.executable, str(agent / 'check-dispatch.py'),\n"
            "                        str(bridge_dir / 'lib/android.js')], check=True)\n"
            "        diagnostics = []")
    replace(builder, "        'bridgeVersion': '7.0.13', 'bridgeSha512': BRIDGE_SHA512,",
            "        'bridgeVersion': '7.0.13', 'bridgeSha512': BRIDGE_SHA512,\n"
            "        'bridgeCmcPatch': {\n"
            "            'url': 'https://github.com/frida-packages/frida-java-bridge/pull/410',\n"
            "            'commit': 'fcdd7186467e8c6dfdcef888208807c9fc0424db',\n"
            f"            'sha256': {CMC_PATCH_SHA!r},\n"
            "            'localChange': 'Fail before cloning if the CMC allocator is unavailable',\n"
            "        },\n"
            "        'bridgeQuickCodePatch': {\n"
            "            'author': 'booinspace',\n"
            f"            'sha256': {QUICK_PATCH_SHA!r},\n"
            "            'change': 'Suspend ART quick-code writes and retain retired Java callbacks through agent cleanup',\n"
            "        },\n"
            "        'bridgeDispatchPatch': {\n"
            "            'author': 'Kolektori; atomic publication corrections by booinspace',\n"
            "            'url': 'https://github.com/frida-packages/frida-java-bridge/pull/401',\n"
            "            'commit': 'dde975ddd6cc8ea8e8667d9a6f5629b22ff16a1c',\n"
            f"            'sha256': {DISPATCH_PATCH_SHA!r},\n"
            "            'localChange': 'Atomic head publication; complete deletion snapshots before publication',\n"
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
        notices.write(
            "\nART quick-code patch transaction by booinspace.\n"
            "Suspends ART threads while entry-point instructions are written or restored.\n"
            "Retains retired JNI callbacks through script teardown for callers still in flight.\n"
            "Race background: https://github.com/frida-packages/frida-java-bridge/pull/401\n"
            "Complete patch: bin/source/agent/frida-java-bridge-quick-code.patch.\n")
        notices.write(
            "\nLock-free ART dispatch by Kolektori:\n"
            "https://github.com/frida-packages/frida-java-bridge/pull/401\n"
            "Upstream commit: dde975ddd6cc8ea8e8667d9a6f5629b22ff16a1c.\n"
            "Local corrections by booinspace: atomically publish completed snapshots, including deletion.\n"
            "Complete patch: bin/source/agent/frida-java-bridge-dispatch.patch.\n")


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
    ticket = module / "android/local/gxr/curvature/MenuAttachmentTicket.java"
    replace(ticket, 'if (root.getWindowToken() == null) throw new IllegalStateException("Menu closed before attachment");',
            'if (root.getWindowToken() == null) { closed = true; return; }')
    replace(ticket, '|| "restore-pending".equals(session.getStatus())) return;',
            '|| "restore-pending".equals(session.getStatus())) { closed = true; return; }')

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
            "fail 'SystemUI changed during the planned restart handoff'\n"
            '  sh "$MODDIR/restart.sh" startup "$target_identity" || {\n'
            '    echo "STARTUP_DEFERRED - no attachment performed; keep Home awake and retry Action."\n'
            '    exit 1\n'
            '  }\n')
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
    replace(control,
            '    elif [ "$graceful" -eq 1 ] && [ "$failed" -eq 0 ]; then',
            '    elif [ "$graceful" -eq 1 ] && [ "$failed" -eq 0 ] &&\n'
            '        printf "%s\\n" "$target_identity" > "$MODDIR/clean-stop.new" &&\n'
            '        mv "$MODDIR/clean-stop.new" "$MODDIR/clean-stop"; then')
    replace(control,
            '  [ "$(cat "$MODDIR/injected-identity" 2>/dev/null || true)" != "$target_identity" ] || fail \'Already attached to this SystemUI incarnation; reboot before re-enabling\'',
            '  if [ "$(cat "$MODDIR/injected-identity" 2>/dev/null || true)" = "$target_identity" ]; then\n'
            '    if sh "$MODDIR/restart.sh" needs-restart; then\n'
            '      echo "WAITING - use one GXR Soft restart to load the updated runtime."; exit 0\n'
            '    fi\n'
            '    fail "Already attached to this SystemUI incarnation; reboot before re-enabling"\n'
            '  fi\n'
            '  rm -f "$MODDIR/clean-stop"')
    replace(control,
            '  else echo \'Runtime not running.\'; fi',
            '  elif sh "$MODDIR/restart.sh" needs-restart; then\n'
            '    echo "WAITING - use one GXR Soft restart to load the updated runtime."\n'
            '  else echo \'Runtime not running.\'; fi')
    replace(control,
            '  while owns_state && [ "$n" -lt 18 ]; do',
            '  while { owns_state || [ -d "$LAUNCH_LOCK" ]; } && [ "$n" -lt 18 ]; do')
    replace(control,
            '  if owns_state; then echo \'Stop remains pending; inspect runtime.log. Do not reattach.\'; exit 1; fi',
            '  if owns_state || [ -d "$LAUNCH_LOCK" ]; then echo \'Stop remains pending; inspect runtime.log. Do not reattach.\'; exit 1; fi')
    replace(control,
            '  if ! owns_state && [ ! -f "$MODDIR/session-open" ] && [ ! -f "$MODDIR/failure" ]; then',
            '  if [ ! -d "$STATE" ] && [ ! -d "$LAUNCH_LOCK" ] && [ ! -f "$MODDIR/session-open" ] && [ ! -f "$MODDIR/failure" ]; then')


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


def integrate_boundary(module: Path) -> None:
    """Align the stock boundary and corner selection with the rotated window."""
    shutil.copyfile(ROOT / "scripts/curvature-boundary-agent.mjs", module / "agent/curvature-boundary-agent.mjs")
    replace(module / "module.prop", "version=0.1.19-azj2-experimental", "version=0.1.30-azj2")
    replace(module / "module.prop", "versionCode=120", "versionCode=131")
    replace(module / "module.prop", "name=Galaxy XR Curvature + Borderless + Rotation",
            "name=Galaxy XR Window Controls")
    replace(module / "module.prop", "description=Experimental AZJ2 window controls with Action settings",
            "description=AZJ2 window controls with 10x movement distance, aligned grab and resize boundaries, Action settings")
    replace(module.parents[1] / "tools/build_window_curvature.py",
            "'kind': 'disabled-experimental-kernelsu-module'", "'kind': 'disabled-kernelsu-module'")
    pins = module / "firmware.sha256"
    previous = dict((line.split('  ', 1)[1], line.split('  ', 1)[0]) for line in pins.read_text().splitlines())
    expected = {**previous, "/system_ext/lib64/libsysui_jni_soong_vulkan.so": UI_RENDERER}
    pins.write_text(pins.read_text() + f"{UI_RENDERER}  /system_ext/lib64/libsysui_jni_soong_vulkan.so\n")
    replace(module.parents[1] / "tools/check_window_curvature_package.py",
            f"assert pins == {previous!r}", f"assert pins == {expected!r}")
    agent = module / "agent/main.js"
    replace(agent, "import {installGrabRotation} from './curvature-grab-agent.mjs';",
            "import {installGrabRotation} from './curvature-grab-agent.mjs';\n"
            "import {installBoundaryAlignment} from './curvature-boundary-agent.mjs';")
    replace(agent, "let grab = null;", "let grab = null;\nlet boundary = null;\n"
            "let boundaryTasks = new Set();\nlet boundaryDeadline = -Infinity;")
    replace(agent, "    try { if (grab !== null) grab.stop(); }",
            "    try { if (boundary !== null) boundary.stop(); }\n"
            "    catch (error) { log('BOUNDARY_RESTORE_ERROR', {error: String(error)}); }\n"
            "    try { if (grab !== null) grab.stop(); }")
    replace(agent, "                            grab = installGrabRotation(Java, rotation, permitted, nowMs);",
            "                            grab = installGrabRotation(Java, rotation, permitted, nowMs);\n"
            "                            boundary = installBoundaryAlignment(id => !stopped && featureValues[2]\n"
            "                                && boundaryTasks.has(id) && nowMs() < boundaryDeadline, fail,\n"
            "                                id => !stopped && boundaryTasks.has(id) && nowMs() < boundaryDeadline);")
    replace(agent, "                rotation.pulse(home);",
            "                rotation.pulse(home);\n"
            "                boundaryTasks = new Set(Array.from(rotation.getBoundTaskIds(), Number));\n"
            "                boundaryDeadline = nowMs() + 2000;")
    replace(agent, "                (rotation === null || rotation.isRestored())) {",
            "                (rotation === null || rotation.isRestored()) &&\n"
            "                (boundary === null || boundary.isRestored())) {")
    replace(agent, "                clearInterval(timer);",
            "                if (boundary !== null) boundary.dispose();\n"
            "                clearInterval(timer);")
    replace(agent, "log('STATE', {rotation:",
            "log('STATE', {boundary: boundary === null ? null : boundary.getDiagnostics(), rotation:")


def integrate_home_pins(module: Path) -> None:
    """Extend the Home pin cap and scroll its existing five-column panel."""
    shutil.copyfile(ROOT / "scripts/curvature-home-pins-agent.mjs",
                    module / "agent/curvature-home-pins-agent.mjs")
    replace(module / "module.prop", "with 10x movement distance,",
            "with 50 Home pins, 10x movement distance,")
    agent = module / "agent/main.js"
    replace(agent, "import {installBoundaryAlignment} from './curvature-boundary-agent.mjs';",
            "import {installBoundaryAlignment} from './curvature-boundary-agent.mjs';\n"
            "import {installHomePins} from './curvature-home-pins-agent.mjs';")
    replace(agent, "let boundary = null;", "let boundary = null;\nlet homePins = null;")
    replace(agent, "    try { if (boundary !== null) boundary.stop(); }",
            "    try { if (homePins !== null) homePins.stop(); }\n"
            "    catch (error) { log('HOME_PINS_RESTORE_ERROR', {error: String(error)}); }\n"
            "    try { if (boundary !== null) boundary.stop(); }")
    replace(agent, "                            refreshFeatures();",
            "                            try { homePins = installHomePins(Java,\n"
            "                                () => !stopped && nowMs() - lastSupervisor < 2500); }\n"
            "                            catch (error) { log('HOME_PINS_UNAVAILABLE', {error: String(error)}); }\n"
            "                            refreshFeatures();")
    replace(agent, "                (boundary === null || boundary.isRestored())) {",
            "                (boundary === null || boundary.isRestored()) &&\n"
            "                (homePins === null || homePins.isRestored())) {")
    replace(agent, "                if (boundary !== null) boundary.dispose();",
            "                if (homePins !== null) homePins.dispose();\n"
            "                if (boundary !== null) boundary.dispose();")
    replace(agent, "log('STATE', {boundary:",
            "log('STATE', {homePins: homePins === null ? null : homePins.getDiagnostics(), boundary:")


def integrate_autostart(module: Path) -> None:
    """Launch after verified restart even if the global service stage is skipped."""
    shutil.copyfile(ROOT / "scripts/curvature-service.sh", module / "service.sh")
    replace(module / "control.sh",
            "After a full reboot, enable and tap Action to start. Action also exports logs.",
            "Enabled modules start after GXR Soft restart. Action opens settings and exports logs.")
    ready = "      printf '%s\\n' 'RUNNING - supervised, independent Home Space windows' > \"$STATE/status\""
    replace(module / "control.sh", "    if grep -q '^GXR_CURVATURE_READY ' \"$LOG\"; then",
            "    if [ \"$ready\" -eq 0 ] && grep -q '^GXR_CURVATURE_READY ' \"$LOG\"; then")
    replace(module / "control.sh", ready, ready + '\n'
            '      if [ "${GXR_WINDOW_AUTOSTART:-0}" = 1 ]; then\n'
            '        (exec 3>&-\n'
            '         umask 077\n'
            '         report=$(mktemp /data/local/tmp/gxr-window-autostart.XXXXXX) || exit 1\n'
            '         trap \'rm -f "$report"\' EXIT\n'
            '         printf "AUTO_START_RUNNING\\nversion=%s\\ntarget=%s\\n" '
            '"$(sed -n \'s/^version=//p\' "$MODDIR/module.prop")" "$target_identity" > "$report" &&\n'
            '         chown 2000:2000 "$report" && chmod 600 "$report" &&\n'
            '         allowed && owns_state && kill -0 "$injector_pid" 2>/dev/null &&\n'
            '         [ "$(identity "$target")" = "$target_identity" ] &&\n'
            '         mv -f "$report" /data/local/tmp/gxr-window-autostart.txt ||\n'
            '           echo "AUTO_START_REPORT_FAILED - runtime remains active."\n'
            '        ) &\n'
            '      fi')
    replace(module / "control.sh",
            "start_time() { sed 's/.*) //' \"/proc/$1/stat\" 2>/dev/null | awk '{print $20}'; }",
            'start_time() {\n'
            '  local stat_line=\n'
            '  IFS= read -r stat_line < "/proc/$1/stat" 2>/dev/null || [ -n "$stat_line" ] || return 1\n'
            '  set -- ${stat_line##*) }\n'
            '  [ "$#" -ge 20 ] || return 1\n'
            '  shift 19\n'
            '  case "$1" in \'\'|*[!0-9]*) return 1 ;; esac\n'
            '  printf \'%s\' "$1"\n'
            '}')
    replace(module / "control.sh",
            'identity() { printf \'%s:%s:%s\' "$(cat /proc/sys/kernel/random/boot_id)" "$1" "$(start_time "$1")"; }',
            'identity() {\n'
            '  local boot=\n'
            '  IFS= read -r boot < /proc/sys/kernel/random/boot_id || [ -n "$boot" ] || return 1\n'
            '  printf \'%s:%s:%s\' "$boot" "$1" "$(start_time "$1")"\n'
            '}')


def integrate_immersive_pins(work: Path, module: Path) -> None:
    """Add opt-in native overlay launches and eye-only panel fading to one injector."""
    sources = ROOT / "modules/window-controls/android/local/gxr/pins"
    destination = module / "android/local/gxr/pins"
    destination.mkdir(parents=True)
    for source in sorted(sources.glob("*.java")):
        shutil.copyfile(source, destination / source.name)
    shutil.copyfile(ROOT / "scripts/curvature-pins-agent.mjs",
                    module / "agent/curvature-pins-agent.mjs")
    shutil.copyfile(ROOT / "scripts/curvature-pins-scrim.mjs",
                    module / "agent/curvature-pins-scrim.mjs")
    shutil.copyfile(ROOT / "scripts/curvature-pins.sh", module / "pins.sh")
    replace(module / "module.prop", "version=0.1.30-azj2", "version=0.1.55-azj2-experimental")
    replace(module / "module.prop", "versionCode=131", "versionCode=156")
    replace(module / "module.prop", "description=AZJ2 window controls with",
            "description=Experimental AZJ2 window controls with opt-in immersive app pins,")
    pins = module / "firmware.sha256"
    previous = dict((line.split("  ", 1)[1], line.split("  ", 1)[0])
                    for line in pins.read_text().splitlines())
    services = "ca2d7cdb6a549b7bdbef2c0ef1cab025b2b058f724fc4710911aedb7b9e71555"
    expected = {**previous, "/system/framework/services.jar": services}
    pins.write_text(pins.read_text() + f"{services}  /system/framework/services.jar\n")
    replace(work / "tools/check_window_curvature_package.py",
            f"assert pins == {previous!r}", f"assert pins == {expected!r}")
    replace(work / "tools/build_window_curvature.py",
            "'boot-recovery.sh', 'restart.sh', 'features.sh',",
            "'boot-recovery.sh', 'restart.sh', 'features.sh', 'pins.sh',")
    installer = module / "customize.sh"
    replace(installer, "uninstall.sh features.sh recovery.sh", "uninstall.sh features.sh pins.sh recovery.sh")
    with installer.open("a") as script:
        script.write('\nprevious_pin=/data/adb/modules/gxr_window_curvature/pin-app.conf\n'
                     'if [ -f "$previous_pin" ] && [ "$MODPATH" != /data/adb/modules/gxr_window_curvature ]; then\n'
                     '  cp "$previous_pin" "$MODPATH/pin-app.conf" || abort "Cannot retain pinned app selection"\n'
                     '  set_perm "$MODPATH/pin-app.conf" 0 0 0600\nfi\n')
    replace(module / "control.sh", "off)\n",
            'off)\n'
            '  if [ -f "$MODDIR/pin-app.conf" ]; then\n'
            '    sh "$MODDIR/pins.sh" close-all || { echo "Pinned app cleanup failed; stop pending."; exit 1; }\n'
            '  fi\n')
    replace(module / "control.sh", '  printf \'%s\\n\' "$$" > "$STATE/supervisor-pid"',
            '  printf \'%s\\n\' "$$" > "$STATE/supervisor-pid"\n'
            '  echo "SUPERVISOR_CGROUP=$(sed -n \'s/^0:://p\' /proc/$$/cgroup)"')
    agent = module / "agent/main.js"
    for old, new in [
        ("        return new Promise((resolve, reject) => Java.perform(() => {",
         "        log('INIT_PHASE', {stage: 'enter-java'});\n        return new Promise((resolve, reject) => Java.perform(() => {"),
        ("                const bytes = Java.use('android.util.Base64').decode(DEX_BASE64, 0);",
         "                log('INIT_PHASE', {stage: 'java-attached'});\n                const bytes = Java.use('android.util.Base64').decode(DEX_BASE64, 0);"),
        ("                Session = factory.use('local.gxr.curvature.CurvatureSession');",
         "                log('INIT_PHASE', {stage: 'helper-loaded'});\n                Session = factory.use('local.gxr.curvature.CurvatureSession');"),
        ("                Java.choose('com.android.systemui.xr.wm.shell.mixedreality.MixedRealityStateObserver', {",
         "                log('INIT_PHASE', {stage: 'find-observer'});\n                Java.choose('com.android.systemui.xr.wm.shell.mixedreality.MixedRealityStateObserver', {"),
        ("                        Java.choose('com.android.systemui.xr.wm.shell.subspace.TaskSubspaceRepositoryImpl', {",
         "                        log('INIT_PHASE', {stage: 'find-repository'});\n                        Java.choose('com.android.systemui.xr.wm.shell.subspace.TaskSubspaceRepositoryImpl', {"),
        ("                            try { homePins = installHomePins(Java,",
         "                            log('INIT_PHASE', {stage: 'install-home-hooks'});\n                            try { homePins = installHomePins(Java,"),
        ("                            installNative();",
         "                            log('INIT_PHASE', {stage: 'install-window-hooks'});\n                            installNative();"),
    ]:
        replace(agent, old, new)
    replace(agent, "import {installHomePins} from './curvature-home-pins-agent.mjs';",
            "import {installHomePins} from './curvature-home-pins-agent.mjs';\n"
            "import {installImmersivePins} from './curvature-pins-agent.mjs';")
    replace(agent, "let homePins = null;",
            "let homePins = null;\nlet immersivePins = null;\n"
            "let pinsRequested = false;\nlet pinFactory = null;")
    replace(agent, "                            grab = installGrabRotation(Java, rotation, permitted, nowMs);",
            "                            grab = installGrabRotation(Java, rotation,\n"
            "                                () => !stopped && nowMs() - lastSupervisor < 2500\n"
            "                                    && (homeSpace() || (immersivePins !== null && immersivePins.canGrab())), nowMs);")
    replace(agent, "                rotation.pulse(home);",
            "                rotation.pulse(home, Java.array('int', immersivePins === null ? [] : immersivePins.getRotationTaskIds()));")
    replace(agent, "                if (grab !== null) grab.pulse(home);",
            "                if (grab !== null) grab.pulse(home || (immersivePins !== null && immersivePins.canGrab()));")
    replace(agent, "let lastSupervisor = -Infinity;",
            "let lastSupervisor = -Infinity;\nlet supervisorPulses = 0;")
    replace(agent, "if (command === 'pulse' && !stopped) lastSupervisor = nowMs();",
            "if (command === 'pulse' && !stopped) { lastSupervisor = nowMs(); supervisorPulses++; }")
    replace(agent, "log('STOPPING', {reason});",
            "log('STOPPING', {reason, pulseAgeMs: nowMs() - lastSupervisor, supervisorPulses});")
    replace(agent, "    try { if (homePins !== null) homePins.stop(); }",
            "    try { if (immersivePins !== null) immersivePins.stop(); }\n"
            "    catch (error) { log('PINS_RESTORE_ERROR', {error: String(error)}); }\n"
            "    try { if (homePins !== null) homePins.stop(); }")
    replace(agent, "                            refreshFeatures();",
            "                            pinFactory = factory;\n"
            "                            refreshFeatures();")
    replace(agent, "        const values = parseFeatureCommand(command);",
            "        if (command === 'pins-on') {\n"
            "            if (!stopped && !pinsRequested && pinFactory !== null) {\n"
            "                pinsRequested = true;\n"
            "                Java.perform(() => {\n"
            "                    try { immersivePins = installImmersivePins(Java, pinFactory,\n"
            "                        () => !stopped && nowMs() - lastSupervisor < 2500, nowMs); }\n"
            "                    catch (error) { console.log('GXR_PINS_ERROR ' + String(error)); }\n"
            "                });\n"
            "            }\n            return;\n        }\n"
            "        const values = parseFeatureCommand(command);")
    replace(module / "control.sh", "    printf 'pulse\\n' >&3 || { failed=1; break; }",
            "    printf 'pulse\\n' >&3 || { failed=1; break; }\n"
            '    if [ "$((count % 10))" -eq 0 ] && read -r pulse_uptime unused < /proc/uptime; then\n'
            '      echo "SUPERVISOR_PULSE count=$count uptime=$pulse_uptime"\n'
            '    fi')
    replace(agent, "            if (!stopped && borderless !== null) borderless.pulse();",
            "            if (!stopped && borderless !== null) borderless.pulse();\n"
            "            if (!stopped && immersivePins !== null) immersivePins.pulse();")
    replace(agent, "                (homePins === null || homePins.isRestored())) {",
            "                (homePins === null || homePins.isRestored()) &&\n"
            "                (immersivePins === null || immersivePins.isRestored())) {")
    replace(agent, "                if (homePins !== null) homePins.dispose();",
            "                if (immersivePins !== null) immersivePins.dispose();\n"
            "                if (homePins !== null) homePins.dispose();")
    replace(agent, "log('STATE', {homePins:",
            "log('STATE', {immersivePins: immersivePins === null ? null : immersivePins.getDiagnostics(), homePins:")


def integrate_pill_pin(module: Path) -> None:
    """Reuse the existing caption host and supervised root launcher for its Pin row."""
    menu = module / "android/local/gxr/curvature/MenuAttachment.java"
    replace(menu, "    private RotationMenu rotationControls;",
            "    private RotationMenu rotationControls;\n    private local.gxr.pins.PinMenu pinControls;")
    replace(menu, "            if (rotationController != null) rotationControls = rotationController.attachMenu(menu, root);",
            "            if (rotationController != null) rotationControls = rotationController.attachMenu(menu, root);\n"
            "            pinControls = local.gxr.pins.PinMenu.attach(root, task);")
    replace(menu, "int expanded = oldHeight + curvatureHeight",
            "int expanded = oldHeight + curvatureHeight + (pinControls == null ? 0 : pinControls.getRequiredHeight())")
    replace(menu, "        if (rotationControls != null) rotationControls.close();",
            "        if (pinControls != null) pinControls.close();\n"
            "        if (rotationControls != null) rotationControls.close();")
    agent = module / "agent/main.js"
    replace(agent, "let pinsRequested = false;\nlet pinFactory = null;",
            "let pinsRequested = false;\nlet pinFactory = null;\nlet PinMenu = null;\nlet pinMenuToken = '';")
    replace(agent, "                            pinFactory = factory;",
            "                            pinFactory = factory;\n"
            "                            PinMenu = factory.use('local.gxr.pins.PinMenu');")
    replace(agent, "            if (!stopped && immersivePins !== null) immersivePins.pulse();",
            "            if (!stopped && immersivePins !== null) immersivePins.pulse();\n"
            "            if (!stopped && PinMenu !== null && pinMenuToken) {\n"
            "                PinMenu.setToken(pinMenuToken);\n"
            "                PinMenu.pulse();\n"
            "                const request = String(PinMenu.pollRequest());\n"
            "                if (request) console.log('GXR_PILL_PIN_REQUEST ' + request);\n"
            "            }")
    replace(agent, "    try { if (immersivePins !== null) immersivePins.stop(); }",
            "    try { if (PinMenu !== null) PinMenu.shutdown(); }\n"
            "    catch (error) { log('PIN_MENU_RESTORE_ERROR', {error: String(error)}); }\n"
            "    try { if (immersivePins !== null) immersivePins.stop(); }")
    replace(agent, "        if (command === 'pins-on') {",
            "        const pinToken = /^pin-token ([0-9a-f]{32})$/.exec(command);\n"
            "        if (pinToken && !stopped) { pinMenuToken = pinToken[1]; return; }\n"
            "        const pinResult = /^pin-result ([0-9]{1,16}) ([0-9]{1,3})$/.exec(command);\n"
            "        if (pinResult && !stopped && PinMenu !== null) {\n"
            "            Java.perform(() => PinMenu.complete(Number(pinResult[1]), Number(pinResult[2]) === 0));\n"
            "            return;\n"
            "        }\n"
            "        if (command === 'pins-on') {")
    control = module / "control.sh"
    replace(control, "  count=0\n  ready=0\n  while allowed; do",
            "  pin_menu_token=$(od -An -N16 -tx1 /dev/urandom | tr -d ' \\n')\n"
            "  [ \"${#pin_menu_token}\" -eq 32 ] || fail 'Cannot initialise pin menu channel'\n"
            "  printf '%s\\n' \"$pin_menu_token\" > \"$STATE/pin-menu-token\"\n"
            "  count=0\n  ready=0\n  while allowed; do")
    replace(control, '    selected=$(sh "$MODDIR/features.sh" wire) || { failed=1; break; }',
            '    printf "pin-token %s\\n" "$pin_menu_token" >&3 || { failed=1; break; }\n'
            '    if [ -z "$pin_menu_pid" ] || ! kill -0 "$pin_menu_pid" 2>/dev/null; then\n'
            '      [ -z "$pin_menu_pid" ] || wait "$pin_menu_pid" || { failed=1; break; }\n'
            '      # Settings and menu reads must not delay the supervisor lease.\n'
            '      (selected=$(sh "$MODDIR/features.sh" wire 3>&-) || exit 1\n'
            '       printf "%s\\n" "$selected" >&3 || exit 1\n'
            '       [ ! -f "$MODDIR/pin-app.conf" ] || printf "pins-on\\n" >&3 || exit 1\n'
            '       exec sh "$MODDIR/pins.sh" menu-poll 3>&3) &\n'
            '      pin_menu_pid=$!\n'
            '    fi')
    replace(control, '    printf "%s\\n" "$selected" >&3 || { failed=1; break; }\n', '')
    replace(control, '  injector_pid=\n', '  pin_menu_pid=\n  injector_pid=\n')
    replace(control, '    planned_restored=0\n',
            '    planned_restored=0\n'
            '    rm -f "$STATE/pin-menu-token"\n'
            '    if [ -n "$pin_menu_pid" ]; then\n'
            '      kill -TERM "$pin_menu_pid" 2>/dev/null || true\n'
            '      wait "$pin_menu_pid" 2>/dev/null || true\n'
            '      pin_menu_pid=\n'
            '    fi\n')
    replace(control,
            'rm -f "$STATE/control" "$STATE/status" "$STATE/supervisor-pid" "$STATE/injector-pid" "$STATE/module-path" "$STATE/target"',
            'rm -f "$STATE/control" "$STATE/status" "$STATE/supervisor-pid" "$STATE/injector-pid" "$STATE/module-path" "$STATE/target" '
            '"$STATE/pin-menu-token" "$STATE/last-pin-menu-request"')


def integrate_supervisor_lease(module: Path) -> None:
    """Give busy app launches bounded headroom without widening tracking freshness."""
    agent = module / "agent/main.js"
    source = agent.read_text()
    old = "nowMs() - lastSupervisor < 2500"
    if source.count(old) != 4:
        raise ValueError("Unexpected combined supervisor predicates")
    agent.write_text(source.replace(old, "nowMs() - lastSupervisor < SUPERVISOR_LEASE_MS"))
    replace(agent, "now - lastSupervisor >= 2500", "now - lastSupervisor >= SUPERVISOR_LEASE_MS")
    replace(agent, "let supervisorPulses = 0;",
            f"const SUPERVISOR_LEASE_MS = {SUPERVISOR_LEASE_MS};\n"
            "let supervisorPulses = 0;\nlet maxSupervisorGapMs = 0;")
    replace(agent, "if (command === 'pulse' && !stopped) { lastSupervisor = nowMs(); supervisorPulses++; }",
            "if (command === 'pulse' && !stopped) {\n"
            "            const stamp = nowMs(), gap = stamp - lastSupervisor;\n"
            "            if (Number.isFinite(gap) && gap >= 0) maxSupervisorGapMs = Math.max(maxSupervisorGapMs, gap);\n"
            "            lastSupervisor = stamp; supervisorPulses++;\n        }")
    replace(agent, "pulseAgeMs: nowMs() - lastSupervisor, supervisorPulses}",
            "pulseAgeMs: nowMs() - lastSupervisor, supervisorPulses, maxSupervisorGapMs}")
    replace(agent, "log('STATE', {immersivePins:",
            "log('STATE', {supervisor: {leaseMs: SUPERVISOR_LEASE_MS, pulses: supervisorPulses,\n"
            "                    ageMs: nowMs() - lastSupervisor, maxGapMs: maxSupervisorGapMs}, immersivePins:")
    session = module / "java/local/gxr/curvature/CurvatureSession.java"
    replace(session, "new CurvatureSession(taskId, node, 3000, true)",
            f"new CurvatureSession(taskId, node, {SUPERVISOR_LEASE_MS}, true)")
    replace(session, "CurvatureLease.supervised(range, clock, 3000)",
            f"CurvatureLease.supervised(range, clock, {SUPERVISOR_LEASE_MS})")
    work = module.parents[1]
    shutil.copyfile(ROOT / "tests/WindowSupervisorLeaseTest.java", work / "tests/WindowSupervisorLeaseTest.java")
    checker = work / "tools/check_window_curvature.py"
    replace(checker, '    sources.append(ROOT / "tests/WindowCurvatureLeaseTest.java")',
            '    sources.append(ROOT / "tests/WindowCurvatureLeaseTest.java")\n'
            '    sources.append(ROOT / "tests/WindowSupervisorLeaseTest.java")')
    replace(checker, '        subprocess.run([str(args.java), "-cp", output, "WindowCurvatureLeaseTest"], check=True)',
            '        subprocess.run([str(args.java), "-cp", output, "WindowCurvatureLeaseTest"], check=True)\n'
            f'        subprocess.run([str(args.java), "-cp", output, "WindowSupervisorLeaseTest", "{SUPERVISOR_LEASE_MS}"], check=True)')
    replace(module / "control.sh",
            'if [ "$((count % 10))" -eq 0 ] && read -r pulse_uptime unused < /proc/uptime; then',
            'if read -r pulse_uptime unused < /proc/uptime; then')


def remove_borderless_delay(module: Path) -> None:
    """Build the timing-only experiment while retaining normal cancellation cleanup."""
    agent = module / "agent/main.js"
    replace(agent, "log('BORDERLESS_PENDING', {delaySeconds: 45});",
            "log('BORDERLESS_PENDING', {delaySeconds: 0});")
    replace(agent, "                            }), 45000);", "                            }), 0);")
    replace(module / "control.sh", "Borderless: pending 45-second startup delay.",
            "Borderless: waiting for queued initialization.")
    replace(module / "webroot/index.html",
            "Controls wait until SystemUI is 90 seconds old; borderless attaches 45 seconds later. Reopen app windows afterward.",
            "Startup test: controls wait until SystemUI is 90 seconds old; borderless attaches after initialization. Reopen app windows afterward.")
    replace(module / "webroot/settings.js",
            "App window setup: waiting up to 45 seconds after runtime start. Then close and reopen the app.",
            "App window setup: waiting for initialization. Then close and reopen the app.")
    replace(module / "module.prop", "version=0.1.55-azj2-experimental",
            "version=0.1.56-azj2-startup-test")
    replace(module / "module.prop", "versionCode=156", "versionCode=157")
    replace(module / "module.prop", "description=Experimental AZJ2 window controls with",
            "description=AZJ2 startup test: no extra 45-second Borderless wait; 90-second SystemUI age guard retained. Window controls with")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default=UPSTREAM, help="Pinned upstream URL or local clone")
    parser.add_argument("--stagger-borderless", action="store_true",
                        help="Coordinate startup with a separate Borderless runtime")
    parser.add_argument("--integrated-borderless", action="store_true",
                        help="Include rim hiding and hover caption in the shared runtime")
    parser.add_argument("--integrated-rotation", action="store_true",
                        help="Include pitch, yaw and roll in the shared runtime (requires --integrated-borderless)")
    parser.add_argument("--no-borderless-delay", action="store_true",
                        help="Build the separate 0.1.56 timing test, retaining the 90-second SystemUI age guard")
    # Keep old build commands working; boundary alignment is now part of the combined build.
    parser.add_argument("--experimental-boundary", action="store_true", help=argparse.SUPPRESS)
    for name in ("java", "ecj", "r8", "android-jar", "cache", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.stagger_borderless and args.integrated_borderless:
        parser.error("Choose only one combined-window build mode")
    if args.integrated_rotation and not args.integrated_borderless:
        parser.error("--integrated-rotation requires --integrated-borderless")
    if args.no_borderless_delay and not args.integrated_rotation:
        parser.error("--no-borderless-delay requires the combined --integrated-rotation build")
    if args.experimental_boundary and not args.integrated_rotation:
        parser.error("--experimental-boundary requires --integrated-rotation")
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
            if not args.integrated_rotation:
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
            integrate_boundary(module)
            integrate_home_pins(module)
            integrate_autostart(module)
            integrate_immersive_pins(work, module)
            integrate_pill_pin(module)
            integrate_supervisor_lease(module)
            if args.no_borderless_delay:
                remove_borderless_delay(module)
            subprocess.run([sys.executable, str(ROOT / "tests/pin-supervisor.test.py"),
                            str(module / "control.sh")], check=True)
            subprocess.run(["node", "--test", str(ROOT / "tests/window-boundary.test.mjs")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/window-boundary-abi.test.py")], check=True)
            subprocess.run(["node", "--test", str(ROOT / "tests/borderless-caption-discovery.test.mjs")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/menu-ticket-host.test.py"),
                            str(module / "android/local/gxr/curvature/MenuAttachmentTicket.java"),
                            "--java", str(args.java), "--ecj", str(args.ecj)], check=True)
            subprocess.run(["node", "--test", str(ROOT / "tests/window-grab-features.test.mjs"),
                            str(ROOT / "tests/window-settings-ui.test.mjs"),
                            str(ROOT / "tests/immersive-pins.test.mjs"),
                            str(ROOT / "tests/pin-scrim.test.mjs"),
                            str(ROOT / "tests/home-pins.test.mjs")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/pins-properties.test.py")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/pin-menu-task.test.py"),
                            "--java", str(args.java), "--ecj", str(args.ecj),
                            "--android-jar", str(args.android_jar)], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/window-feature-settings.test.py")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/curvature-boot-recovery.test.py"),
                            str(module)], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/curvature-restart.test.py"),
                            str(module)], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/curvature-autostart.test.py"),
                            str(module)], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/window-installer-contract.test.py")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/window-controls-conflicts.test.py"),
                            str(module / "control.sh")], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/rotation-controller-host.test.py"),
                            "--java", str(args.java), "--ecj", str(args.ecj)], check=True)
            subprocess.run([sys.executable, str(ROOT / "tests/pinned-panels-host.test.py"),
                            "--java", str(args.java), "--ecj", str(args.ecj),
                            "--sdk-tools-lib", str(args.r8.parent)], check=True)
            subprocess.run(["node", str(ROOT / "tests/curvature-combined-lifecycle.mjs"),
                            str(module / "agent/main.js"), "--rotation", "--boundary", "--home-pins",
                            *(["--no-borderless-delay"] if args.no_borderless_delay else [])], check=True)
            math_classes = Path(temporary) / "rotation-tests"
            subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
                            "-proc:none", "-failOnWarning", "-d", str(math_classes),
                            str(module / "android/local/gxr/rotation/RotationMath.java"),
                            str(ROOT / "tests/RotationMathTest.java")], check=True)
            subprocess.run([str(args.java), "-cp", str(math_classes),
                            "local.gxr.rotation.RotationMathTest"], check=True)
            subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
                            "-proc:none", "-failOnWarning", "-d", str(math_classes),
                            str(module / "android/local/gxr/pins/FadePolicy.java"),
                            str(module / "android/local/gxr/pins/BackdropPolicy.java"),
                            str(module / "android/local/gxr/pins/PanelRay.java"),
                            str(ROOT / "tests/FadePolicyTest.java"),
                            str(ROOT / "tests/PanelRayTest.java"),
                            str(ROOT / "tests/BackdropPolicyTest.java")], check=True)
            subprocess.run([str(args.java), "-cp", str(math_classes),
                            "local.gxr.pins.FadePolicyTest"], check=True)
            subprocess.run([str(args.java), "-cp", str(math_classes),
                            "local.gxr.pins.BackdropPolicyTest"], check=True)
            subprocess.run([str(args.java), "-cp", str(math_classes),
                            "local.gxr.pins.PanelRayTest"], check=True)
            subprocess.run([str(args.java), "-jar", str(args.ecj), "-source", "1.8", "-target", "1.8",
                            "-proc:none", "-failOnWarning", "-d", str(math_classes),
                            str(module / "android/local/gxr/pins/PinRequest.java"),
                            str(ROOT / "tests/PinRequestTest.java")], check=True)
            subprocess.run([str(args.java), "-cp", str(math_classes),
                            "local.gxr.pins.PinRequestTest"], check=True)
        (module / "install-info.txt").write_text(
            "AZJ2 port of BlueScorpioVR's window-curvature module. Installs DISABLED.\n"
            "Firmware I610UES3AZJ2 only; APK and native hashes are checked before attach.\n" +
            ("Window Controls combines curvature, borderless and hand rotation in one runtime.\n"
             if args.integrated_rotation else
             "One-injector borderless/curvature build is experimental; see README.md.\n"
             if args.integrated_borderless else
             "Staggered startup with borderless is experimental; see README.md.\n"
             if args.stagger_borderless else
             "Standalone curvature source worked on the headset; see README.md.\n")
        )
        (module / "README.md").write_bytes((ROOT / "docs/CURVATURE.md").read_bytes())
        if args.no_borderless_delay:
            readme = module / "README.md"
            readme.write_text(
                "# Window Controls 0.1.56 immersive brightness candidate\n\n"
                "Suppresses the separate fullscreen scrim while only owned pins are visible over an immersive app; native diagnostics report the mean requested alpha and suppressed frames. Visual brightness verification is pending. Retains the device-confirmed menu cancellation, restored-caption binding, scoped pin rotation/resizing, VR focus/input routing and tracking leases. Removes only the extra 45-second Borderless wait; "
                "the 90-second SystemUI process-age guard, firmware checks and quarantine remain. "
                "Borderless is queued immediately after agent initialization and can still be cancelled on stop.\n\n"
                "Install this ZIP as an update to the existing Window Controls module. It installs disabled. "
                "The guide below describes the normal delayed build; its extra 45-second wait does not apply to this test.\n\n"
                + readme.read_text())
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
        version = ("0.1.56-azj2-startup-test" if args.no_borderless_delay else
                   "0.1.55-azj2-experimental" if args.integrated_rotation else
                   ("0.1.7" if args.integrated_borderless else "0.1.4" if args.stagger_borderless else "0.1.6") + "-azj2-experimental")
        package = args.output / f"gxr-window-curvature-{version}-disabled.zip"
        subprocess.run([sys.executable, "tools/check_window_curvature_package.py", str(package)],
                       cwd=work, check=True)
        check_gxr_installer_payload(package)
        print(package)


if __name__ == "__main__":
    main()
