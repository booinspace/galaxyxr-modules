"""Run the packaged boot/restart launchers without Action or Android services."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(sys.argv.pop(1))
GEN = "44444444-4444-4444-8444-444444444444"
NEXT = "55555555-5555-4555-8555-555555555555"


class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.module = self.root / "module"
        self.module.mkdir()
        self.coord = self.root / "coordinator"
        self.coord.mkdir()
        self.calls = self.root / "calls"
        for name in ("service.sh", "restart-started.sh", "restart-prepare.sh"):
            text = (SOURCE / name).read_text().replace("/dev/ksu-restart-stage", str(self.coord))
            (self.module / name).write_text(text)
        (self.module / "control.sh").write_text(
            '#!/bin/sh\n'
            f'printf "%s\\n" "$1" >> "{self.calls}"\n')
        (self.module / "restart.sh").write_text(
            '#!/bin/sh\n'
            f'echo "$1" >> "{self.root}/phases"\n'
            f'[ ! -f "{self.root}/reject" ]\n')
        self.addCleanup(lambda: self.module.joinpath("disable").touch())

    def dispatch(self, name, **extra):
        return subprocess.run(["sh", str(self.module / name)],
                              env={**os.environ, **extra}, capture_output=True,
                              text=True, timeout=3)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        self.fail(self.module.joinpath("service.log").read_text()
                  if self.module.joinpath("service.log").exists() else "No startup log")

    def begin(self):
        self.coord.joinpath("generation").write_text(GEN)
        self.coord.joinpath("busy").touch()

    def ready(self):
        self.coord.joinpath("ready").touch()
        self.coord.joinpath("busy").unlink(missing_ok=True)

    def waiting(self):
        self.wait_for(lambda: self.module.joinpath("service.log").exists() and
                      "startup requested" in self.module.joinpath("service.log").read_text())
        self.assertFalse(self.calls.exists())

    def test_service_launches_without_action(self):
        result = self.dispatch("service.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.wait_for(self.calls.exists)
        self.assertEqual(self.calls.read_text(), "run\n")

    def test_started_hook_returns_before_ready_then_starts_automatically(self):
        self.begin()
        result = self.dispatch("restart-started.sh", KSU_RESTART_GENERATION=GEN)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.root.joinpath("phases").read_text(), "started\n")
        self.waiting()
        self.ready()
        self.wait_for(self.calls.exists)
        self.assertEqual(self.calls.read_text(), "run\n")

    def test_prepare_and_failed_started_hook_do_not_launch(self):
        self.assertEqual(self.dispatch("restart-prepare.sh").returncode, 0)
        self.assertFalse(self.module.joinpath("service.log").exists())
        self.root.joinpath("reject").touch()
        self.assertNotEqual(self.dispatch("restart-started.sh").returncode, 0)
        self.assertFalse(self.module.joinpath("service.log").exists())

    def test_disabled_or_removed_modules_do_not_launch(self):
        for marker in ("disable", "remove"):
            self.module.joinpath(marker).touch()
            for name in ("service.sh", "restart-started.sh"):
                self.assertEqual(self.dispatch(name).returncode, 0)
            self.assertFalse(self.calls.exists())
            self.assertFalse(self.module.joinpath("service.log").exists())
            self.module.joinpath(marker).unlink()

    def test_pending_launch_is_cancelled_when_generation_changes(self):
        self.begin()
        self.assertEqual(self.dispatch("service.sh").returncode, 0)
        self.waiting()
        self.coord.joinpath("generation").write_text(NEXT)
        self.ready()
        time.sleep(1.2)
        self.assertFalse(self.calls.exists())

    def test_disable_or_restart_error_cancels_pending_launch(self):
        for directory, marker in ((self.module, "disable"), (self.coord, "error")):
            with self.subTest(marker=marker):
                self.module.joinpath("service.log").unlink(missing_ok=True)
                self.begin()
                self.assertEqual(self.dispatch("service.sh").returncode, 0)
                self.waiting()
                directory.joinpath(marker).touch()
                self.ready()
                time.sleep(1.2)
                self.assertFalse(self.calls.exists())
                directory.joinpath(marker).unlink()

    def test_malformed_generation_never_reaches_the_controller(self):
        result = subprocess.run(["sh", str(self.module / "service.sh"), "worker", "invalid"],
                                capture_output=True, text=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()
