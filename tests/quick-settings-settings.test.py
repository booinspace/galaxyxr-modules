"""Exercise the shortcut's persistent root settings without touching a device."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='gxr-quick-settings-') as directory:
    work = Path(directory)
    shutil.copyfile(ROOT / 'modules/quick-settings-gesture/settings.sh', work / 'quick-settings-gesture.sh')
    tools = work / 'tools'
    tools.mkdir()
    identity = tools / 'id'
    identity.write_text('#!/bin/sh\nprintf "0\\n"\n')
    identity.chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'])
    def run(*args, ok=True):
        result = subprocess.run(['sh', str(work / 'quick-settings-gesture.sh'), *args],
                                env=env, text=True, capture_output=True)
        assert (result.returncode == 0) == ok, (args, result.stdout, result.stderr)
        return result.stdout
    assert json.loads(run()) == {'enabled': 0, 'holdMs': 500}
    assert run('wire') == 'quick-settings 0 500\n'
    assert json.loads(run('set', '1', '500')) == {'enabled': 1, 'holdMs': 500}
    path = work / 'quick-settings-gesture.conf'
    saved = path.read_bytes()
    for invalid in [('2', '500'), ('1', '100'), ('1;touch injected', '0'), ('1', '$(id)')]:
        run('set', *invalid, ok=False)
        assert path.read_bytes() == saved
    assert path.stat().st_mode & 0o777 == 0o600
    for invalid in ['ENABLED=1\n', saved.decode() + 'ENABLED=0\n',
                    'ENABLED=$(touch injected)\nHOLD_MS=500\n', 'ENABLED=1\nHOLD_MS=5\n']:
        path.write_text(invalid)
        run('wire', ok=False)
    assert not (work / 'injected').exists()
    assert json.loads(run('set', '1', '0'))['holdMs'] == 0
    identity.write_text('#!/bin/sh\nprintf "2000\\n"\n')
    run('set', '0', '500', ok=False)
print('PASS: root gate, defaults, persistence, atomic writes and strict shortcut settings')
