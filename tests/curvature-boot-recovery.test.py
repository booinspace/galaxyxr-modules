"""Exercise the generated combined module without root, Android services or injection."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(sys.argv.pop(1))
OLD_BOOT = "11111111-1111-4111-8111-111111111111"
NEW_BOOT = "22222222-2222-4222-8222-222222222222"
IDENTITY = OLD_BOOT + ":123:456"


class BootRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.module = self.root / "modules/gxr_window_curvature"
        self.module.mkdir(parents=True)
        (self.root / "localtmp").mkdir()
        (self.root / "dev").mkdir()
        self.state = self.root / "dev/gxr-window-curvature"
        self.launch = self.root / "dev/gxr-window-curvature-launch"
        commands = self.root / "commands"
        commands.mkdir()
        for name, body in {
            "id": "echo 0",
            "chown": "exit 0",
            "getprop": 'case "$1" in sys.boot_completed) echo 1;; ro.product.model) echo SM-I610;; *) echo samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys;; esac',
            "pidof": f'[ "$1" != frida-inject ] || test ! -f "{self.root}/injector" || echo 999',
            "sha256sum": f'echo "$*" >> "{self.root}/checks"; case "$*" in *firmware.sha256*) test ! -f "{self.root}/bad-firmware";; *) test ! -f "{self.root}/bad-payload";; esac',
        }.items():
            path = commands / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}"}
        for name in ("control.sh", "boot-recovery.sh", "recovery.sh", "action.sh", "restart.sh", "features.sh"):
            text = (SOURCE / name).read_text()
            for before, after in {
                "/data/adb/modules": str(self.root / "modules"),
                "/data/local/tmp": str(self.root / "localtmp"),
                "/dev/gxr-": str(self.root / "dev/gxr-"),
                "/dev/ksu-restart-stage": str(self.root / "dev/restart"),
                "/proc/sys/kernel/random/boot_id": str(self.root / "boot"),
            }.items():
                text = text.replace(before, after)
            (self.module / name).write_text(text)
        (self.root / "boot").write_text(NEW_BOOT)
        for name, value in {"injected-identity": IDENTITY, "session-open": IDENTITY,
                            "failure": "old failure", "runtime.log": "GXR_CURVATURE_FATAL old crash"}.items():
            (self.module / name).write_text(value)

    def run_control(self, command="run"):
        return subprocess.run(["sh", str(self.module / "control.sh"), command], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def assert_preserved(self):
        self.assertTrue((self.module / "session-open").exists())
        self.assertEqual((self.module / "runtime.log").read_text(), "GXR_CURVATURE_FATAL old crash")
        self.assertFalse(list(self.module.glob("*.pre-reset.*")))

    def test_new_boot_archives_and_exports_before_reaching_injection_gate(self):
        result = self.run_control()
        self.assertIn("Previous session acknowledged", result.stdout)
        # The fake device has no SystemUI PID: stop before any injector can run.
        self.assertIn("Expected one SystemUI process", result.stdout)
        self.assertFalse((self.module / "session-open").exists())
        self.assertEqual(len(list(self.module.glob("*.pre-reset.*"))), 3)
        self.assertEqual((self.root / "localtmp/gxr-curvature-failure").read_text(), "old failure")
        self.assertIn("firmware.sha256", (self.root / "checks").read_text())
        self.assertFalse(self.launch.exists())

    def test_same_boot_and_bad_identities_are_not_cleared(self):
        for boot, previous, session in (
            (OLD_BOOT, IDENTITY, IDENTITY),
            (NEW_BOOT, "", IDENTITY),
            (NEW_BOOT, "malformed:123:456", IDENTITY),
            (NEW_BOOT, IDENTITY, OLD_BOOT + ":124:456"),
            ("", IDENTITY, IDENTITY),
        ):
            with self.subTest(boot=boot, previous=previous, session=session):
                (self.module / "disable").unlink(missing_ok=True)
                (self.root / "boot").write_text(boot)
                (self.module / "injected-identity").write_text(previous)
                (self.module / "session-open").write_text(session)
                self.assertNotEqual(self.run_control().returncode, 0)
                self.assert_preserved()

    def test_live_runtime_hash_failure_and_other_injector_block_recovery(self):
        for marker in (self.state, self.root / "bad-payload", self.root / "bad-firmware", self.root / "injector"):
            with self.subTest(marker=marker):
                (self.module / "disable").unlink(missing_ok=True)
                marker.mkdir() if marker == self.state else marker.touch()
                self.assertNotEqual(self.run_control().returncode, 0)
                self.assert_preserved()
                marker.rmdir() if marker == self.state else marker.unlink()

    def test_disabled_removed_and_duplicate_start_do_not_change_markers(self):
        for marker in (self.module / "disable", self.module / "remove", self.launch):
            with self.subTest(marker=marker):
                marker.mkdir() if marker == self.launch else marker.touch()
                self.assertEqual(self.run_control().returncode, 0)
                self.assert_preserved()
                self.assertEqual((self.module / "failure").read_text(), "old failure")
                marker.rmdir() if marker == self.launch else marker.unlink()

    def test_manual_reset_stays_disabled_and_requires_new_boot(self):
        self.assertNotEqual(self.run_control("reset").returncode, 0)
        (self.module / "disable").touch()
        (self.root / "boot").write_text(OLD_BOOT)
        self.assertNotEqual(self.run_control("reset").returncode, 0)
        self.assert_preserved()
        (self.root / "boot").write_text(NEW_BOOT)
        self.assertEqual(self.run_control("reset").returncode, 0)
        self.assertTrue((self.module / "disable").exists())
        self.assertFalse((self.module / "session-open").exists())
        self.state.mkdir()
        self.assertNotEqual(self.run_control("reset").returncode, 0)

    def test_update_stop_acknowledges_a_previous_boot_crash_without_starting(self):
        result = self.run_control("off")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("GXR_UPDATE_STATE=STOCK", result.stdout)
        self.assertTrue((self.module / "disable").exists())
        self.assertFalse((self.module / "failure").exists())
        self.assertFalse((self.module / "session-open").exists())
        self.assertFalse(self.state.exists())
        self.assertFalse(self.launch.exists())
        self.assertEqual(len(list(self.module.glob("*.pre-reset.*"))), 3)

    def test_update_stop_cannot_clear_a_crash_from_the_same_boot(self):
        (self.root / "boot").write_text(OLD_BOOT)
        result = self.run_control("off")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("GXR_UPDATE_STATE=STOCK", result.stdout)
        self.assert_preserved()

    def test_action_starts_once_and_exports_without_resetting_live_session(self):
        (self.module / "control.sh").write_text(
            '#!/bin/sh\ncase "$1" in\nrun)\n'
            f'  echo run >> "{self.root}/calls"\n  mkdir "{self.state}"\n'
            f'  echo RUNNING > "{self.state}/status"\n  ;;\n'
            'status) echo status;;\nesac\n')
        for unused in range(2):
            result = subprocess.run(["sh", str(self.module / "action.sh")], env=self.env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Exported", result.stdout)
        self.assertEqual((self.root / "calls").read_text(), "run\n")
        self.assert_preserved()
        (self.state / "status").unlink()
        self.state.rmdir()
        (self.module / "disable").touch()
        result = subprocess.run(["sh", str(self.module / "action.sh")], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "calls").read_text(), "run\n")


if __name__ == "__main__":
    unittest.main()
