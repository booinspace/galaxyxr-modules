"""Exercise allowlist restoration using isolated fake Android commands, never the headset."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "persist.xr.wm.allowlisted_overlay_activity.package"
CLASS = "persist.xr.wm.allowlisted_overlay_activity.class_name"
APP = "app.symfonik.music.player"


class PropertiesTest(unittest.TestCase):
    def run_pin(self, *, fail=False, external=False, argument=APP, menu=False,
                request_line=None, close_fail=False, duplicate=False, launch_sleep=0, preflight_fail=False):
        with tempfile.TemporaryDirectory(prefix="gxr-pins-test-") as directory:
            work = Path(directory).resolve()
            module, commands, state = work / "module", work / "commands", work / "state"
            module.mkdir()
            commands.mkdir()
            state.mkdir()
            properties = work / "props.json"
            initial = {PACKAGE: "original.owner", CLASS: "original.owner.Panel",
                       "ro.build.version.incremental": "I610UES3AZJ2"}
            properties.write_text(json.dumps(initial))
            (module / "runtime.log").write_text("GXR_PINS_READY - fixture\n")
            (module / "firmware.sha256").write_text("fixture")
            (state / "module-path").write_text(str(module) + "\n")
            (state / "status").write_text("RUNNING - fixture\n")
            token = "a" * 32
            (state / "pin-menu-token").write_text(token + "\n")
            if menu:
                line = request_line if request_line is not None else f"GXR_PILL_PIN_REQUEST {token} 1000 42 {argument}"
                with (module / "runtime.log").open("a") as log:
                    log.write(line + "\n")
            trace, reply = work / "trace.jsonl", work / "reply.txt"
            fake = commands / "android-command.py"
            fake.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys, time
store = pathlib.Path(os.environ['PIN_TEST_PROPERTIES'])
p = json.loads(store.read_text())
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if name == 'id': print('0')
elif name == 'getprop': print(p.get(args[0], ''))
elif name == 'sha256sum': pass
elif name == 'ksud':
    assert args[:2] == ['resetprop', '-n'], 'Persistent property operation forbidden'
    p[args[2]] = args[3]
    store.write_text(json.dumps(p))
elif name == 'app_process':
    args = args[args.index('local.gxr.pins.PinCli') + 1:]
    with pathlib.Path(os.environ['PIN_TEST_TRACE']).open('a') as trace: trace.write(json.dumps(args) + '\\n')
    action = args[0]
    if action == 'resolve': print(args[-1] + '/' + args[-1] + '.Main')
    elif action == 'preflight':
        if os.environ['PIN_TEST_PREFLIGHT_FAIL'] == '1': sys.exit(8)
    elif action == 'close-for-pin':
        assert args == ['close-for-pin', '42', 'app.symfonik.music.player', '1000']
        if os.environ['PIN_TEST_CLOSE_FAIL'] == '1': sys.exit(9)
    elif action == 'launch':
        assert p['persist.xr.wm.allowlisted_overlay_activity.package'] == args[-1]
        time.sleep(float(os.environ['PIN_TEST_LAUNCH_SLEEP']))
        if os.environ['PIN_TEST_EXTERNAL'] == '1':
            p['persist.xr.wm.allowlisted_overlay_activity.package'] = 'another.owner'
            p['persist.xr.wm.allowlisted_overlay_activity.class_name'] = 'another.owner.Panel'
            store.write_text(json.dumps(p))
        if os.environ['PIN_TEST_FAIL'] == '1': sys.exit(7)
        print('PINNED - fixture')
    else: print('{}')
else: raise AssertionError(name)
""")
            fake.chmod(0o755)
            for name in ("id", "getprop", "sha256sum", "ksud", "app_process"):
                (commands / name).symlink_to(fake)
            source = (ROOT / "scripts/curvature-pins.sh").read_text()
            source = source.replace("/dev/gxr-window-curvature", str(state))
            source = source.replace("/dev/gxr-window-pins-launch", str(work / "launch-lock"))
            source = source.replace("/system/bin/app_process", str(commands / "app_process"))
            source = source.replace("KSUD=/data/adb/ksud", "KSUD=" + str(commands / "ksud"))
            script = module / "pins.sh"
            script.write_text(source)
            env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"],
                       PIN_TEST_PROPERTIES=str(properties), PIN_TEST_FAIL=str(int(fail)),
                       PIN_TEST_EXTERNAL=str(int(external)), PIN_TEST_TRACE=str(trace),
                       PIN_TEST_CLOSE_FAIL=str(int(close_fail)), PIN_TEST_LAUNCH_SLEEP=str(launch_sleep),
                       PIN_TEST_PREFLIGHT_FAIL=str(int(preflight_fail)))
            command = ["sh", str(script), "pin", argument]
            if menu:
                command = ["sh", "-c", 'exec 3>>"$1"; shift; exec sh "$@"', "fixture", str(reply), str(script), "menu-poll"]
            started = time.monotonic()
            result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=12)
            result.dispatch_seconds = time.monotonic() - started
            if menu and (state / "last-pin-menu-request").exists():
                deadline = time.monotonic() + 5
                while not reply.exists() or not reply.read_text().endswith("\n"):
                    if time.monotonic() > deadline: raise AssertionError((module / "service.log").read_text())
                    time.sleep(.02)
                if duplicate:
                    subprocess.run(command, env=env, text=True, capture_output=True, timeout=5, check=True)
            calls = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
            return result, initial, json.loads(properties.read_text()), \
                (work / "launch-lock").exists(), calls, reply.read_text() if reply.exists() else ""

    def test_success_restores_previous_owner(self):
        result, original, current, locked, _, _ = self.run_pin()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(current, original)
        self.assertFalse(locked)

    def test_failed_launch_restores_previous_owner(self):
        result, original, current, locked, _, _ = self.run_pin(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(current, original)
        self.assertFalse(locked)

    def test_existing_ordinary_window_is_rejected_before_property_changes_or_launch(self):
        result, original, current, locked, calls, _ = self.run_pin(preflight_fail=True)
        self.assertEqual(result.returncode, 8)
        self.assertEqual(current, original)
        self.assertEqual([call[0] for call in calls], ["resolve", "preflight"])
        self.assertFalse(locked)

    def test_external_owner_is_preserved_and_reported(self):
        result, original, current, locked, _, _ = self.run_pin(external=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(current[PACKAGE], "another.owner")
        self.assertEqual(current[CLASS], "another.owner.Panel")
        self.assertIn("changed externally", result.stderr)
        self.assertFalse(locked)

    def test_shell_payload_is_rejected_before_any_property_write(self):
        result, original, current, locked, _, _ = self.run_pin(argument=APP + "; id")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(current, original)
        self.assertFalse(locked)

    def test_menu_request_reopens_only_the_selected_task_and_acknowledges(self):
        result, original, current, locked, calls, reply = self.run_pin(menu=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call[0] for call in calls], ["resolve", "close-for-pin", "launch"])
        self.assertEqual(calls[1], ["close-for-pin", "42", APP, "1000"])
        self.assertEqual(reply, "pin-result 1000 0\n")
        self.assertEqual(current, original)
        self.assertFalse(locked)

    def test_menu_launch_does_not_block_supervisor_pulses_and_is_not_replayed(self):
        result, _, _, _, calls, reply = self.run_pin(menu=True, duplicate=True, launch_sleep=1.5)
        self.assertLess(result.dispatch_seconds, .8)
        self.assertEqual(sum(call[0] == "launch" for call in calls), 1)
        self.assertEqual(reply, "pin-result 1000 0\n")

    def test_changed_task_is_not_closed_or_launched_and_properties_restore(self):
        _, original, current, locked, calls, reply = self.run_pin(menu=True, close_fail=True)
        self.assertEqual([call[0] for call in calls], ["resolve", "close-for-pin"])
        self.assertEqual(reply, "pin-result 1000 9\n")
        self.assertEqual(current, original)
        self.assertFalse(locked)

    def test_menu_launch_failure_restores_allowlist_and_reports_failure(self):
        _, original, current, locked, _, reply = self.run_pin(menu=True, fail=True)
        self.assertEqual(reply, "pin-result 1000 7\n")
        self.assertEqual(current, original)
        self.assertFalse(locked)

    def test_forged_and_malformed_menu_requests_never_reach_root_launcher(self):
        for line in [f"GXR_PILL_PIN_REQUEST {'b' * 32} 1000 42 {APP}",
                     f"GXR_PILL_PIN_REQUEST {'a' * 32} 1000 -42 {APP}",
                     f"GXR_PILL_PIN_REQUEST {'a' * 32} 1:2 42 {APP}",
                     f"GXR_PILL_PIN_REQUEST {'a' * 32} 1000 4:2 {APP}",
                     f"GXR_PILL_PIN_REQUEST {'a' * 32} 1000 42 {APP}; id",
                     f"GXR_PILL_PIN_REQUEST {'a' * 32} 1000 42 $(id)",
                     f"GXR_PILL_PIN_REQUEST {'a' * 32} {'9' * 17} 42 {APP}"]:
            with self.subTest(line=line):
                result, original, current, locked, calls, reply = self.run_pin(menu=True, request_line=line)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(current, original)
                self.assertEqual(calls, [])
                self.assertEqual(reply, "")
                self.assertFalse(locked)


if __name__ == "__main__":
    unittest.main()
