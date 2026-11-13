"""Exercise the generated heartbeat and slow helpers without Android or an injector."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

source = Path(sys.argv.pop(1)).read_text()
start = source.index("  pin_menu_token=$(od")
loop = source[start:source.index("\n  ;;\n*)", start)]
cleanup_start = source.index('    rm -f "$STATE/pin-menu-token"')
cleanup = source[cleanup_start:source.index('    if [ -n "$injector_pid" ]; then', cleanup_start)]


class SupervisorTest(unittest.TestCase):
    def run_loop(self, *, features_delay=0, menu_delay=4, report_delay=0, invalid=False, stop=None):
        with tempfile.TemporaryDirectory(prefix="gxr-pin-supervisor-") as directory:
            work = Path(directory)
            commands = work / "commands"
            commands.mkdir()
            (work / "runtime.log").write_text("GXR_CURVATURE_READY {}\n")
            (work / "module.prop").write_text("version=fixture\n")
            (work / "active").touch()
            (work / "identity").write_text("fixture\n")
            (work / "features.sh").write_text(
                f'sleep {features_delay}\n' + ('exit 7\n' if invalid else "printf 'features 1 1 1 0\\n'\n"))
            (work / "pins.sh").write_text(
                'printf "%s\\n" "$$" >> "$MODDIR/poll-pids"\n'
                'printf "pin-result 1000 0\\n" >&3\n' + f'exec sleep {menu_delay}\n')
            (commands / "mktemp").write_text(
                '#!/bin/sh\nprintf "report\\n" >> "$MODDIR/reports"\n' +
                f'sleep {report_delay}\nexec /usr/bin/mktemp "$@"\n')
            (commands / "chown").write_text('#!/bin/sh\nexit 0\n')
            for command in commands.iterdir():
                command.chmod(0o755)
            fifo = work / "control.pipe"
            os.mkfifo(fifo)
            pulses, received = [], []

            def receive():
                with fifo.open() as reader:
                    for line in reader:
                        received.append(line.strip())
                        if line != "pulse\n":
                            continue
                        pulses.append(time.monotonic())
                        if len(pulses) == 2:
                            if stop == "disable":
                                (work / "disable").touch()
                            elif stop == "identity":
                                (work / "identity").write_text("reused-pid\n")

            reader = threading.Thread(target=receive, daemon=True)
            reader.start()
            script = work / "check.sh"
            script.write_text('''set -u
MODDIR=$1; export MODDIR
STATE=$MODDIR
LOG=$MODDIR/runtime.log
injector_pid=$$
target=$$
target_identity=fixture
maximum=5
pin_menu_pid=
failed=0
GXR_WINDOW_AUTOSTART=1
allowed() { [ ! -f "$MODDIR/disable" ]; }
owns_state() { [ -f "$MODDIR/active" ]; }
identity() { cat "$MODDIR/identity"; }
finish() {
  rm -f "$MODDIR/active"
''' + cleanup + '''
}
trap finish EXIT
exec 3> "$MODDIR/control.pipe"
''' + loop.replace("/data/local/tmp/gxr-window-autostart", str(work / "autostart")) + '''
[ "$failed" -eq 0 ]
''')
            env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["sh", str(script), str(work)], env=env,
                                    capture_output=True, text=True, timeout=15)
            reader.join(timeout=2)
            self.assertFalse(reader.is_alive(), "Helper retained the supervisor pipe after stop")
            self.assertEqual(result.returncode, int(invalid or stop == "identity"), result.stdout + result.stderr)
            if stop or invalid:
                self.assertLessEqual(len(pulses), 3)
            else:
                self.assertEqual(len(pulses), 5)
                self.assertIn("features 1 1 1 0", received)
                self.assertIn("pin-result 1000 0", received)
                self.assertEqual((work / "reports").read_text().splitlines(), ["report"])
                self.assertIn("target=fixture", (work / "autostart.txt").read_text())
            if len(pulses) > 1:
                gap = max(b - a for a, b in zip(pulses, pulses[1:]))
                self.assertLess(gap, 2, f"Slow helper stalled the 2500 ms lease: {gap:.3f}s")
                print(f"Heartbeat max gap={gap:.3f}s ({features_delay=}, {menu_delay=}, {report_delay=}, {stop=})")
            if (work / "poll-pids").exists():
                pids = (work / "poll-pids").read_text().splitlines()
                self.assertLessEqual(len(pids), 2, "Blocked workers accumulated")
                for pid in pids:
                    with self.assertRaises(ProcessLookupError, msg="Menu worker survived cleanup"):
                        os.kill(int(pid), 0)
            self.assertFalse((work / "pin-menu-token").exists(), "Old launcher token survived stop")

    def test_blocked_menu_does_not_delay_pulses(self):
        self.run_loop()

    def test_slow_settings_and_startup_report_do_not_delay_pulses(self):
        self.run_loop(features_delay=3, menu_delay=0, report_delay=3.2)

    def test_invalid_settings_stop_the_runtime(self):
        self.run_loop(invalid=True)

    def test_disable_is_observed_while_settings_are_blocked(self):
        self.run_loop(features_delay=3, stop="disable")

    def test_pid_identity_change_stops_pulses(self):
        self.run_loop(stop="identity")

    def test_start_time_parses_comm_with_spaces_and_parentheses(self):
        with tempfile.TemporaryDirectory(prefix="gxr-stat-") as directory:
            root = Path(directory)
            (root / "99").mkdir()
            fields = ["S"] + ["0"] * 18 + ["12345", "0"]
            (root / "99/stat").write_text("99 (worker ) with spaces) " + " ".join(fields) + "\n")
            (root / "boot").write_text("fixture-boot\n")
            functions = source[source.index("start_time() {"):source.index("\nfail() {")]
            functions = functions.replace('/proc/$1/stat', str(root) + '/$1/stat')
            functions = functions.replace('/proc/sys/kernel/random/boot_id', str(root / "boot"))
            result = subprocess.run(["sh", "-c", functions + "\nidentity 99"], capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, "fixture-boot:99:12345")
            result = subprocess.run(["sh", "-c", functions + "\nstart_time 100"], capture_output=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
