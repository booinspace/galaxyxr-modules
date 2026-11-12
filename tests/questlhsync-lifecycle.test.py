"""Run the real Lighthouse supervisor around a disposable process group on Linux."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(Path('/proc/self/stat').exists(),'Linux /proc required')
class LighthouseLifecycleTest(unittest.TestCase):
    def test_stop_restart_failure_and_previous_boot_recovery(self):
        with tempfile.TemporaryDirectory(prefix='gxr-lighthouse-test-') as directory:
            root=Path(directory); module=root/'module'; module.mkdir()
            run=root/'runtime'; boot=root/'boot'; boot.write_text('first-boot\n')
            tools=root/'tools'; tools.mkdir()
            for name,body in {'id':'echo 0','getprop':'echo 1','sha256sum':'exit 0'}.items():
                p=tools/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
            env={**os.environ,'PATH':str(tools)+':'+os.environ['PATH']}
            source=(ROOT/'modules/questlhsync/control.sh').read_text()
            source=source.replace('/dev/questlhsync-gxr',str(run)).replace('/data/adb/questlhsync-gxr',str(root/'settings'))
            source=source.replace('/proc/sys/kernel/random/boot_id',str(boot))
            source=source.replace('/dev/ksu-restart-stage',str(root/'restart'))
            source=source.replace('/data/local/tmp/questlhsync-gxr-',str(root/'export-'))
            (module/'control.sh').write_text(source)
            (module/'guard.sh').write_text('gxr_guard() { return 0; }\ngxr_calibration_guard() { return 0; }\n')
            (module/'run.sh').write_text('''#!/usr/bin/env python3
import ctypes,pathlib,signal,subprocess,time
root=pathlib.Path(__file__).parent
alive=True
def stop(*args):
 global alive
 alive=False
signal.signal(signal.SIGTERM,stop)
child=subprocess.Popen(['python3','-c',"import pathlib,signal,time; p=pathlib.Path("+repr(str(root/'camera-open'))+"); p.touch(); signal.signal(signal.SIGTERM,lambda *_:(p.unlink(missing_ok=True),exit(0))); time.sleep(120)"],preexec_fn=lambda:ctypes.CDLL(None).prctl(1,signal.SIGTERM))
print('lhsyncd fixture up: serial fake',flush=True)
while alive: time.sleep(.02)
child.wait(timeout=5)
''')
            # The production launcher runs sh run.sh; this isolated fixture launches Python.
            control=module/'control.sh'; control.write_text(control.read_text().replace('setsid sh "$MODDIR/run.sh"','setsid python3 "$MODDIR/run.sh"'))

            def command(verb,ok=True):
                result=subprocess.run(['sh',str(control),verb],env=env,text=True,capture_output=True,timeout=25)
                self.assertEqual(result.returncode==0,ok,result.stdout+result.stderr)
                return result.stdout
            def wait_for(predicate,timeout=15):
                until=time.monotonic()+timeout
                while not predicate() and time.monotonic()<until: time.sleep(.05)
                self.assertTrue(predicate())
            workers=[]
            def start():
                p=subprocess.Popen(['sh',str(control),'run'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                workers.append(p)
                wait_for(lambda:(run/'ready').exists() and (module/'camera-open').exists())
                self.assertIn('RUNNING',command('status'))
                return p
            try:
                p=start(); first=(run/'daemon.pid').read_text()
                command('run'); self.assertEqual((run/'daemon.pid').read_text(),first)
                command('prepare'); p.wait(timeout=15)
                self.assertFalse(run.exists()); self.assertFalse((module/'camera-open').exists())
                self.assertFalse((module/'disable').exists(),'planned stop must preserve checkbox')
                self.assertIn('GXR_UPDATE_STATE=STOCK',command('status'))
                p=start(); os.kill(int((run/'daemon.pid').read_text()),signal.SIGKILL)
                p.wait(timeout=15)
                self.assertTrue((module/'failure').exists()); self.assertTrue((module/'disable').exists())
                self.assertFalse((module/'camera-open').exists())
                (module/'disable').unlink()
                command('start',ok=False)
                boot.write_text('second-boot\n')
                p=start()
                self.assertTrue((module/'failure.previous-boot').exists())
                self.assertFalse((module/'failure').exists())
                command('off'); p.wait(timeout=15)
                self.assertIn('GXR_UPDATE_STATE=STOCK',command('status'))
            finally:
                if run.exists(): (run/'stop').touch()
                for p in workers:
                    if p.poll() is None: p.wait(timeout=20)


if __name__=='__main__':unittest.main()
