"""Exercise the recovery Action against isolated module directories."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "modules/curvature-recovery/action.sh"


class CurvatureRecoveryTest(unittest.TestCase):
    def test_archives_diagnostic_and_waits_for_new_boot_before_reset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "modules").mkdir()
            (root / "localtmp").mkdir()
            commands = root / "commands"
            commands.mkdir()
            (commands / "id").write_text("#!/bin/sh\necho 0\n")
            (commands / "chown").write_text("#!/bin/sh\nexit 0\n")
            for command in commands.iterdir():
                command.chmod(0o755)
            action = root / "action.sh"
            action.write_text(
                SOURCE.read_text()
                .replace("/data/adb/modules", str(root / "modules"))
                .replace("/data/adb/gxr-", str(root / "gxr-"))
                .replace("/data/local/tmp", str(root / "localtmp"))
                .replace("/dev/gxr-borderless-azj2", str(root / "borderless-state"))
                .replace("/proc/sys/kernel/random/boot_id", str(root / "boot_id"))
                .replace("/system/bin/sh", "/bin/sh")
            )
            environment = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}"}

            diagnostic = root / "modules/gxr_curvature_diagnostics"
            diagnostic.mkdir()
            contents = {
                "module.prop": b"id=gxr_curvature_diagnostics\nversionCode=1\n",
                "action.sh": b"#!/bin/sh\nexit 0\n",
            }
            for name, data in contents.items():
                (diagnostic / name).write_bytes(data)
            (diagnostic / "disable").touch()
            (diagnostic / "SHA256SUMS").write_text("".join(
                f"{hashlib.sha256(data).hexdigest()}  {name}\n"
                for name, data in contents.items()
            ))

            curvature = root / "modules/gxr_window_curvature"
            curvature.mkdir()
            (curvature / "disable").touch()
            (curvature / "failure").write_text("quarantined\n")
            (curvature / "session-open").write_text("old:123:456\n")
            (curvature / "runtime.log").write_text("READY\n")
            (curvature / "injected-identity").write_text("old:123:456\n")
            (curvature / "control.sh").write_text(
                "#!/bin/sh\n[ \"$1\" = reset ] || exit 1\n"
                f"rm -f {curvature / 'failure'} {curvature / 'session-open'}\n"
            )
            borderless = root / "modules/gxr_borderless_azj2"
            borderless.mkdir()
            (borderless / "runtime.log").write_text("GXR_BORDERLESS_FATAL TypeError\n")
            (borderless / "failure").write_text("quarantined\n")
            (borderless / "disable").touch()
            (borderless / "injected-identity").write_text("old:99:100\n")
            (root / "boot_id").write_text("old\n")

            def run(*args):
                return subprocess.run(["/bin/sh", str(action), *args], env=environment,
                                      text=True, capture_output=True, check=True).stdout

            self.assertEqual(run("status").strip(), "GXR_UPDATE_STATE=STOCK")
            self.assertEqual(run("off").strip(), "GXR_UPDATE_STATE=STOCK")
            self.assertIn("Full reboot required", run())
            self.assertFalse(diagnostic.exists())
            self.assertTrue((root / "gxr-curvature-diagnostics-0.1.0-backup").exists())
            self.assertTrue((curvature / "failure").exists())
            self.assertEqual((root / "localtmp/gxr-curvature-runtime.log").read_text(), "READY\n")
            self.assertEqual((root / "localtmp/gxr-borderless-runtime.log").read_text(),
                             "GXR_BORDERLESS_FATAL TypeError\n")
            self.assertTrue((borderless / "failure").exists())

            (root / "boot_id").write_text("new\n")
            run()
            self.assertFalse((curvature / "failure").exists())
            self.assertFalse((curvature / "session-open").exists())
            self.assertFalse((borderless / "failure").exists())
            self.assertFalse((borderless / "runtime.log").exists())
            self.assertEqual(len(list(borderless.glob("runtime.pre-reset.*.log"))), 1)


if __name__ == "__main__":
    unittest.main()
