"""Exercise the root settings boundary without a connected headset."""
import json
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="gxr-mic-settings-") as directory:
    work = Path(directory)
    module = ROOT / "modules/mic-gain-boost"
    for name in ("settings.sh", "config.default.conf"):
        shutil.copyfile(module / name, work / name)
    (work / "control.sh").write_text("#!/bin/sh\nprintf 'KernelSU checkbox: ON\\nRUNNING\\n'\n")
    tools = work / "tools"
    tools.mkdir()
    (tools / "id").write_text("#!/bin/sh\necho 0\n")
    (tools / "id").chmod(0o755)
    for name, body in {
        'getprop': "echo samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys",
        'sha256sum': 'exit 0',
        'timeout': 'shift 3; exec "$@"',
    }.items():
        path = tools / name
        path.write_text('#!/bin/sh\nset -e\n' + body + '\n')
        path.chmod(0o755)
    (tools / 'flock').write_text('''#!/usr/bin/env python3
import fcntl,sys
try: fcntl.flock(int(sys.argv[-1]),fcntl.LOCK_EX|fcntl.LOCK_NB)
except OSError: sys.exit(1)
''')
    (tools / 'flock').chmod(0o755)
    (tools / 'recorder').write_text('''#!/usr/bin/env python3
import os,sys,wave
from pathlib import Path
command=sys.argv[3];directory=Path(sys.argv[4])/'webroot/recordings'
directory.mkdir(parents=True,exist_ok=True)
clip=directory/'mic-test.wav'
if command=='capture':
 if os.environ.get('MIC_TEST_FAIL')=='1':sys.exit(3)
 with wave.open(str(clip),'w') as w:w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(bytes(96000))
elif command in ('validate','play'):
 try:
  with wave.open(str(clip)) as w:assert w.getnframes()>0
 except Exception:sys.exit(1)
else:sys.exit(2)
''')
    (tools / 'recorder').chmod(0o755)
    script = work / 'settings.sh'
    script.write_text(script.read_text().replace('/system/bin/app_process', str(tools / 'recorder')))
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])

    def run(*args, ok=True):
        result = subprocess.run(["sh", str(work / "settings.sh"), *args], env=env,
                                text=True, capture_output=True)
        assert (result.returncode == 0) == ok, (args, result.stdout, result.stderr)
        return result.stdout

    assert json.loads(run("json")) == dict(gain=15, vdOnly=1, running=True, recording=False)
    run('record', ok=False)
    assert json.loads(run("set", "25", "0")) == dict(gain=25, vdOnly=0, running=True, recording=False)
    assert json.loads(run('record'))['recording']
    clip = work / 'webroot/recordings/mic-test.wav'
    old_clip = clip.read_bytes()
    run('play')
    run('stop-playback')
    assert (clip.parent / 'stop-playback').exists()
    env['MIC_TEST_FAIL'] = '1'
    run('record', ok=False)
    assert clip.read_bytes() == old_clip
    env.pop('MIC_TEST_FAIL')
    with (work / '.mic-test.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run('delete-recording', ok=False)
        assert clip.read_bytes() == old_clip
    assert not json.loads(run('delete-recording'))['recording']
    assert not clip.exists()
    clip.write_text('invalid clip')
    assert not json.loads(run('json'))['recording']
    clip.unlink()
    saved = (work / "config.conf").read_bytes()
    for gain, scope in (("41", "1"), ("-1", "1"), ("1.5", "1"),
                        ("15;touch injected", "1"), ("15", "$(id)")):
        run("set", gain, scope, ok=False)
        assert (work / "config.conf").read_bytes() == saved
    assert (work / "config.conf").stat().st_mode & 0o777 == 0o600
    (work / "config.conf").write_text("MODE=2\nGAIN_DB=7\n")
    assert json.loads(run("set", "0", "1"))["gain"] == 0
    assert "MODE=2\n" in (work / "config.conf").read_text()
    for bad in ("MODE=$(touch injected)\n", "MODE=1\nMODE=0\n", "OTHER=1\n", "GAIN_DB=99\n"):
        (work / "config.conf").write_text(bad)
        run("json", ok=False)
    assert not (work / "injected").exists()
    (work / "config.conf").unlink()
    (tools / "id").write_text("#!/bin/sh\necho 2000\n")
    run("set", "15", "1", ok=False)
print("PASS: mic settings, root/scope gates, explicit recording, failed capture preservation and deletion lock")
