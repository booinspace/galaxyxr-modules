"""Check rotation quarantine and conflict guards without a device or root."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RotationControlTest(unittest.TestCase):
    def test_reboot_recovery_and_other_module_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = root / "module"
            module.mkdir()
            (root / "dev").mkdir()
            commands = root / "commands"
            commands.mkdir()
            (commands / "id").write_text("#!/bin/sh\necho 0\n")
            (commands / "chown").write_text("#!/bin/sh\nexit 0\n")
            for command in commands.iterdir():
                command.chmod(0o755)
            source = (ROOT / "modules/window-rotation/control.sh").read_text()
            script = module / "control.sh"
            script.write_text(source.replace("/dev/gxr-", str(root / "dev/gxr-"))
                              .replace("/data/adb/", str(root / "data") + "/")
                              .replace("/proc/sys/kernel/random/boot_id", str(root / "boot")))
            environment = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}"}

            def run(command, success=True):
                result = subprocess.run(["/bin/sh", str(script), command], env=environment,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                return result.stdout

            (module / "disable").touch()
            (root / "boot").write_text("first\n")
            self.assertIn("GXR_UPDATE_STATE=STOCK", run("status"))
            (module / "session-open").write_text("first:123:456\n")
            (module / "injected-identity").write_text("first:123:456\n")
            (module / "failure").write_text("Restoration unverified\n")
            (module / "runtime.log").write_text("partial log\n")
            self.assertNotIn("GXR_UPDATE_STATE=STOCK", run("status"))
            run("reset", success=False)
            self.assertTrue((module / "session-open").exists())
            (root / "boot").write_text("second\n")
            self.assertIn("GXR_UPDATE_STATE=STOCK", run("reset"))
            self.assertFalse((module / "session-open").exists())

            self.assertEqual(len(list(module.glob("runtime.log.before-*"))), 1)
            self.assertEqual(len(list(module.glob("failure.before-*"))), 1)
            self.assertIn("GXR_UPDATE_STATE=STOCK", run("off"))

            (module / "disable").unlink()
            conflict = root / "data/modules/gxr_borderless_azj2"
            conflict.mkdir(parents=True)
            self.assertIn("Disable gxr_borderless_azj2", run("run", success=False))
            self.assertTrue((module / "disable").exists())
            self.assertFalse((module / "session-open").exists())

            (conflict / "disable").touch()
            (module / "disable").unlink()
            (root / "data/modules/gxr_window_curvature").mkdir()
            self.assertIn("Disable gxr_window_curvature", run("run", success=False))
            self.assertTrue((module / "disable").exists())
            self.assertFalse((module / "session-open").exists())


if __name__ == "__main__":
    unittest.main()
