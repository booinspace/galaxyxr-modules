"""Linux host test of the real supervisor with a fake, reversible helper process."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(Path('/proc/self/stat').exists(), 'Linux /proc required; run on WSL')
class DaemonLifecycleTest(unittest.TestCase):
    def test_one_child_and_cooperative_off_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = root / 'module'
            module.mkdir()
            (module / 'config.default.conf').write_text('MODE=1\nGAIN_DB=15\n')
            commands = root / 'commands'
            commands.mkdir()
            fixed = {'id': 'echo 0', 'sha256sum': 'exit 0', 'pidof': f'echo {os.getpid()}',
                     'getprop': '''case "$1" in
ro.product.model) echo SM-I610 ;;
ro.build.fingerprint) echo samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys ;;
sys.boot_completed) echo 1 ;;
esac'''}
            for name, body in fixed.items():
                file = commands / name
                file.write_text('#!/bin/sh\n' + body + '\n')
                file.chmod(0o755)
            helper = root / 'app_process'
            helper.write_text('''#!/usr/bin/env python3
import os,sys,time
from pathlib import Path
module=Path(sys.argv[-1])
state=Path(os.environ['GXR_PORT_STATE'])
if 'restore' in sys.argv:
    (module/'owned-test-value').unlink(missing_ok=True)
    print('PORT_STOCK')
else:
    count=module/'daemon-starts'
    count.write_text(str(int(count.read_text())+1 if count.exists() else 1))
    (module/'owned-test-value').write_text('changed')
    (state/'ready').touch()
    while not (state/'stop').exists() and not (module/'disable').exists(): time.sleep(.02)
    (module/'owned-test-value').unlink(missing_ok=True)
    (state/'restored').touch()
''')
            helper.chmod(0o755)
            (root / 'boot').write_text('test-boot\n')
            control = module / 'control.sh'
            source = (ROOT / 'modules/mic-gain-boost/control.sh').read_text()
            source = source.replace('. "$MODDIR/bin/runtime.sh"',
                                    (ROOT / 'scripts/bread-port/daemon-control.sh').read_text())
            source = source.replace('STATE="/dev/$ID"', 'STATE="' + str(root) + '/$ID"')
            source = source.replace('/proc/sys/kernel/random/boot_id', str(root / 'boot'))
            source = source.replace('/system/bin/app_process', str(helper))
            control.write_text(source)
            env = {**os.environ, 'PATH': f"{commands}:{os.environ['PATH']}"}
            child = subprocess.Popen(['/bin/sh', str(control), 'run'], env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                state = root / 'gxr_mic_gain_azj2'
                end = time.monotonic() + 5
                while not (state / 'ready').exists() and time.monotonic() < end:
                    if child.poll() is not None: self.fail(child.stdout.read())
                    time.sleep(.02)
                self.assertTrue((state / 'ready').exists())
                self.assertTrue((module / 'owned-test-value').exists())
                subprocess.run(['/bin/sh', str(control), 'run'], env=env, check=True, timeout=3)
                self.assertEqual((module / 'daemon-starts').read_text(), '1')
                status = subprocess.check_output(['/bin/sh', str(control), 'status'], env=env, text=True)
                self.assertIn('RUNNING', status)
                self.assertNotIn('GXR_UPDATE_STATE=STOCK', status)
                subprocess.run(['/bin/sh', str(control), 'prepare'], env=env, check=True, timeout=25)
                child.communicate(timeout=5)
                self.assertFalse((module / 'owned-test-value').exists())
                self.assertFalse((module / 'session-open').exists())
                self.assertFalse(state.exists())
                self.assertFalse((module / 'failure').exists())
                self.assertFalse((module / 'disable').exists(), 'restart preparation must preserve activation')
                child = subprocess.Popen(['/bin/sh', str(control), 'run'], env=env,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                end = time.monotonic() + 5
                while not (state / 'ready').exists() and time.monotonic() < end:
                    if child.poll() is not None: self.fail(child.stdout.read())
                    time.sleep(.02)
                self.assertTrue((state / 'ready').exists())
                self.assertEqual((module / 'daemon-starts').read_text(), '2')
                stopped = subprocess.check_output(['/bin/sh', str(control), 'off'], env=env, text=True, timeout=25)
                self.assertIn('GXR_UPDATE_STATE=STOCK', stopped)
                child.communicate(timeout=5)
                self.assertFalse((module / 'owned-test-value').exists())
                self.assertFalse((module / 'session-open').exists())
                self.assertFalse(state.exists())
                self.assertFalse((module / 'failure').exists())
            finally:
                if child.poll() is None:
                    (module / 'disable').touch()
                    child.communicate(timeout=20)


if __name__ == '__main__': unittest.main()
