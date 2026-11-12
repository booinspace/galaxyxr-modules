"""Exercise the real generated shell controller with disposable processes and a fake injector."""
import os
import select
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(sys.argv.pop(1))
BOOT = "33333333-3333-4333-8333-333333333333"
GEN = "44444444-4444-4444-8444-444444444444"
NEXT_GEN = "55555555-5555-4555-8555-555555555555"


@unittest.skipUnless(sys.platform.startswith("linux"), "Requires Linux /proc process identities")
class RestartTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.module = self.root / "modules/gxr_window_curvature"
        self.module.mkdir(parents=True)
        (self.root / "localtmp").mkdir()
        (self.root / "dev").mkdir()
        (self.root / "boot").write_text(BOOT)
        self.coord = self.root / "dev/restart"
        self.coord.mkdir()
        self.handoff = self.root / "dev/gxr-window-curvature-restart"
        self.state = self.root / "dev/gxr-window-curvature"
        self.controllers = []
        self.targets = []
        self.addCleanup(self.stop_processes)
        self.target = self.new_target()
        commands = self.root / "commands"
        commands.mkdir()
        for name, body in {
            "id": "echo 0",
            "chown": "exit 0",
            "sha256sum": "exit 0",
            "pidof": f'case "$1" in com.android.systemui) cat "{self.root}/target";; frida-inject) cat "{self.root}/injector" 2>/dev/null || true;; esac',
            "getprop": 'case "$1" in sys.boot_completed) echo 1;; ro.product.model) echo SM-I610;; *) echo samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys;; esac',
        }.items():
            path = commands / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}"}
        for name in ("control.sh", "boot-recovery.sh", "restart.sh", "recovery.sh", "features.sh",
                     "restart-prepare.sh", "restart-stopped.sh", "restart-started.sh", "restart-abort.sh"):
            text = (SOURCE / name).read_text()
            for before, after in {
                "/data/adb/modules": str(self.root / "modules"),
                "/data/local/tmp": str(self.root / "localtmp"),
                "/dev/gxr-": str(self.root / "dev/gxr-"),
                "/dev/ksu-restart-stage": str(self.coord),
                "/proc/sys/kernel/random/boot_id": str(self.root / "boot"),
                "/proc/uptime": str(self.root / "uptime"),
            }.items():
                text = text.replace(before, after)
            (self.module / name).write_text(text)
        (self.module / "bin").mkdir()
        injector = self.module / "bin/frida-inject"
        injector.write_text(
            '#!/bin/sh\n'
            f'echo $$ > "{self.root}/injector"\n'
            f'trap \'rm -f "{self.root}/injector"\' EXIT\n'
            'echo \'GXR_CURVATURE_READY {"test":true}\'\n'
            'while IFS= read -r command; do\n'
            '  if [ "$command" = stop ]; then\n'
            f'    if [ ! -f "{self.root}/no-ack" ]; then echo \'GXR_CURVATURE_STOPPED {{"test":true}}\'; fi\n'
            '    exit 0\n  fi\ndone\n')
        injector.chmod(0o755)
        self.coord.joinpath("generation").write_text(GEN)
        self.coord.joinpath("ready").touch()
        (self.root / "uptime").write_text("999999999 0\n")

    def new_target(self):
        target = subprocess.Popen(["sleep", "120"])
        self.targets.append(target)
        (self.root / "target").write_text(str(target.pid))
        return target

    def stop_processes(self):
        (self.module / "disable").touch()
        for process in self.controllers + self.targets:
            if process.poll() is None:
                if process in self.controllers:
                    try:
                        process.wait(timeout=5)
                        continue
                    except subprocess.TimeoutExpired:
                        pass
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        self.fail((self.module / "service.log").read_text() if (self.module / "service.log").exists() else "Timed out")

    def launch(self):
        with (self.module / "service.log").open("a") as log:
            controller = subprocess.Popen(["sh", str(self.module / "control.sh"), "run"], env=self.env,
                                          stdout=log, stderr=subprocess.STDOUT)
        self.controllers.append(controller)
        self.wait_for(lambda: self.state.joinpath("status").exists() and
                      self.state.joinpath("status").read_text().startswith("RUNNING"))
        return controller

    def hook(self, phase, success=True):
        env = {**self.env, "KSU_RESTART_GENERATION": self.coord.joinpath("generation").read_text()}
        result = subprocess.run(["sh", str(self.module / f"restart-{phase}.sh")], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def helper(self, phase, *args):
        return subprocess.run(["sh", str(self.module / "restart.sh"), phase, *args], env=self.env,
                              capture_output=True, text=True, timeout=5)

    def begin(self, generation=GEN):
        self.coord.joinpath("generation").write_text(generation)
        self.coord.joinpath("busy").touch()
        self.coord.joinpath("ready").unlink(missing_ok=True)

    def ready(self):
        self.coord.joinpath("busy").unlink()
        self.coord.joinpath("ready").touch()

    def test_two_planned_restarts_keep_enabled_then_crash_cannot_replay(self):
        controller = self.launch()
        for generation in (GEN, NEXT_GEN):
            self.begin(generation)
            old = self.module.joinpath("session-open").read_text().strip()
            self.hook("prepare")
            controller.wait(timeout=5)
            self.assertFalse(self.module.joinpath("disable").exists())
            self.assertFalse(self.module.joinpath("failure").exists())
            self.assertEqual(self.handoff.joinpath("phase").read_text().strip(), "quiesced")
            self.target.terminate()
            self.target.wait(timeout=2)
            self.hook("stopped")
            self.target = self.new_target()
            self.hook("started")
            self.assertNotEqual(self.helper("authorize", old).returncode, 0)
            self.ready()
            expected = self.handoff.joinpath("new-target").read_text()
            self.handoff.joinpath("new-target").write_text(BOOT + ":1:1")
            self.assertNotEqual(self.helper("authorize", old).returncode, 0)
            self.handoff.joinpath("new-target").write_text(expected)
            controller = self.launch()
            self.assertFalse(self.module.joinpath("disable").exists())
            self.assertEqual(self.handoff.joinpath("phase").read_text().strip(), "consumed")
            self.assertNotEqual(self.module.joinpath("session-open").read_text().strip(), old)
            self.assertNotEqual(self.helper("authorize", old).returncode, 0)
        self.target.terminate()
        self.target.wait(timeout=2)
        controller.wait(timeout=8)
        self.assertTrue(self.module.joinpath("disable").exists())
        self.module.joinpath("disable").unlink()
        result = subprocess.run(["sh", str(self.module / "control.sh"), "run"], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("startup gate failed", result.stdout)

    def make_gate(self):
        def target_id(process):
            start = Path(f"/proc/{process.pid}/stat").read_text().rsplit(") ", 1)[1].split()[19]
            return f"{BOOT}:{process.pid}:{start}"
        old = target_id(self.target)
        self.target.terminate()
        self.target.wait(timeout=2)
        self.target = self.new_target()
        current = target_id(self.target)
        self.handoff.mkdir()
        for name, value in {"generation": GEN, "phase": "verified", "old-target": old,
                            "new-target": current}.items():
            self.handoff.joinpath(name).write_text(value)
        self.module.joinpath("session-open").write_text(old)
        self.module.joinpath("injected-identity").write_text(old)
        ticks = int(subprocess.check_output(["getconf", "CLK_TCK"], text=True))
        self.start_seconds = int(current.rsplit(":", 1)[1]) / ticks
        (self.root / "uptime").write_text(f"{self.start_seconds + 10:.2f} 0\n")
        process = subprocess.Popen(["sh", str(self.module / "restart.sh"), "await", old], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.controllers.append(process)
        self.assertTrue(select.select([process.stderr], [], [], 5)[0])
        self.assertIn("STARTUP_WAIT", process.stderr.readline())
        return process, old, current

    def test_gate_waits_without_consuming_the_handoff(self):
        process, old, current = self.make_gate()
        self.assertIsNone(process.poll())
        self.assertNotEqual(self.helper("authorize", old).returncode, 0)
        self.assertEqual(self.handoff.joinpath("phase").read_text().strip(), "verified")
        (self.root / "uptime").write_text(f"{self.start_seconds + 91:.2f} 0\n")
        out, err = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, out + err)
        self.assertIn("STARTUP_AGE_PASSED", err)
        self.assertEqual(self.handoff.joinpath("phase").read_text().strip(), "verified")
        result = self.helper("authorize", old)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), current)

    def test_gate_rejects_changed_process_generation_and_bad_clock(self):
        process, old, current = self.make_gate()
        # A later restart generation must not spend the earlier authorization.
        self.coord.joinpath("generation").write_text(NEXT_GEN)
        process.communicate(timeout=5)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(self.handoff.joinpath("phase").read_text().strip(), "verified")
        self.coord.joinpath("generation").write_text(GEN)
        (self.root / "uptime").write_text("invalid kernel time\n")
        self.assertNotEqual(self.helper("await", old).returncode, 0)
        self.assertEqual(self.handoff.joinpath("phase").read_text().strip(), "verified")
        (self.root / "uptime").write_text("999999999 0\n")
        self.target.terminate()
        self.target.wait(timeout=2)
        self.target = self.new_target()
        self.assertNotEqual(self.helper("authorize", old).returncode, 0)
        self.assertEqual(self.handoff.joinpath("new-target").read_text().strip(), current)

    def test_missing_cleanup_ack_aborts_before_android_stop(self):
        controller = self.launch()
        (self.root / "no-ack").touch()
        self.begin()
        self.hook("prepare", success=False)
        self.hook("abort")
        controller.wait(timeout=5)
        self.assertIsNone(self.target.poll())
        self.assertTrue(self.module.joinpath("disable").exists())
        self.assertEqual(self.handoff.joinpath("phase").read_text().strip(), "aborted")

    def test_idle_restart_has_no_resume_permission_and_preserves_disabled_switch(self):
        self.begin()
        self.hook("prepare")
        self.hook("stopped")
        self.hook("started")
        self.ready()
        self.assertEqual(self.handoff.joinpath("phase").read_text().strip(), "idle-complete")
        self.assertNotEqual(self.helper("authorize", BOOT + ":1:1").returncode, 0)
        self.module.joinpath("disable").touch()
        self.begin(NEXT_GEN)
        self.hook("prepare", success=False)
        self.assertTrue(self.module.joinpath("disable").exists())

    def test_busy_generation_and_unplanned_quarantine_block_start(self):
        self.begin()
        result = subprocess.run(["sh", str(self.module / "control.sh"), "run"], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.module.joinpath("disable").exists())
        env = {**self.env, "KSU_RESTART_GENERATION": NEXT_GEN}
        result = subprocess.run(["sh", str(self.module / "restart-prepare.sh")], env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.handoff.exists())
        self.module.joinpath("injected-identity").write_text(BOOT + ":1:1")
        self.module.joinpath("session-open").write_text(BOOT + ":1:1")
        self.hook("prepare", success=False)
        self.assertFalse(self.handoff.exists())


if __name__ == "__main__":
    unittest.main()
