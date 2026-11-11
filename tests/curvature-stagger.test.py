"""Check that curvature waits for the borderless supervisor before attach."""

import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/curvature-stagger-service.sh"


class CurvatureStaggerTest(unittest.TestCase):
    def test_waits_for_borderless_running_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = root / "curvature"
            borderless = root / "borderless"
            status = root / "borderless-status"
            commands = root / "commands"
            for path in (module, borderless, commands):
                path.mkdir()
            marker = root / "ran"
            (module / "control.sh").write_text(f"#!/bin/sh\necho \"$1\" > {marker}\n")
            service = module / "service.sh"
            service.write_text(
                SOURCE.read_text()
                .replace("/data/adb/modules/gxr_borderless_azj2", str(borderless))
                .replace("/dev/gxr-borderless-azj2/status", str(status))
            )
            sleep = commands / "sleep"
            sleep.write_text("#!/bin/sh\n/bin/sleep 0.03\n")
            sleep.chmod(0o755)
            environment = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}"}
            process = subprocess.Popen(["/bin/sh", str(service)], env=environment,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            process.wait(timeout=2)
            time.sleep(0.12)
            self.assertFalse(marker.exists())
            status.write_text("RUNNING - borderless ready\n")
            deadline = time.monotonic() + 2
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.03)
            self.assertEqual(marker.read_text().strip(), "run")

    def test_stops_if_borderless_disappears_during_settle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = root / "curvature"
            borderless = root / "borderless"
            status = root / "borderless-status"
            commands = root / "commands"
            for path in (module, borderless, commands):
                path.mkdir()
            marker = root / "ran"
            (module / "control.sh").write_text(f"#!/bin/sh\ntouch {marker}\n")
            service = module / "service.sh"
            service.write_text(
                SOURCE.read_text()
                .replace("/data/adb/modules/gxr_borderless_azj2", str(borderless))
                .replace("/dev/gxr-borderless-azj2/status", str(status))
            )
            status.write_text("RUNNING - borderless ready\n")
            sleep_started = root / "sleep-started"
            sleep = commands / "sleep"
            sleep.write_text(f"#!/bin/sh\ntouch {sleep_started}\n/bin/sleep 0.2\n")
            sleep.chmod(0o755)
            environment = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}"}
            process = subprocess.Popen(["/bin/sh", str(service)], env=environment,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            process.wait(timeout=2)
            deadline = time.monotonic() + 2
            while not sleep_started.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(sleep_started.exists())
            status.unlink()
            while not (module / "failure").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((module / "disable").exists())
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
