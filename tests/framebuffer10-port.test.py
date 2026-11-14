"""Run pinned upstream lifecycle checks against the AZJ2 source transform."""
import argparse
import os
from pathlib import Path
import runpy
import sys
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--upstream', type=Path, required=True)
parser.add_argument('--cxx', default=shutil.which('g++-14') or shutil.which('g++'))
args = parser.parse_args()
builder = runpy.run_path(str(ROOT / 'scripts/build-framebuffer10-azj2.py'))
head = subprocess.check_output(['git', '-C', str(args.upstream), 'rev-parse', 'HEAD'], text=True).strip()
assert head == builder['COMMIT'], 'Pinned upstream commit required'
subprocess.run(['git', '-C', str(args.upstream), 'diff', '--quiet', 'HEAD'], check=True)
assert args.cxx, 'A host C++ compiler is required'

with tempfile.TemporaryDirectory(prefix='gxr-framebuffer-port-test-') as temporary:
    source = Path(temporary) / 'source'
    shutil.copytree(args.upstream, source, ignore=shutil.ignore_patterns('.git', 'dist', '__pycache__'))
    builder['port'](source)
    tests = source / 'modules/framebuffer10/tests'
    native = tests / 'test_native_coordinated.py'
    text = native.read_text().replace("['g++',", '[' + repr(args.cxx) + ',')
    text = text.replace("[('normal',0),", "[('coordinator-busy-recovery',3),('normal',0),")
    text = text.replace(" if scenario=='normal':", """ if scenario=='coordinator-busy-recovery':
  assert 'KernelSU restart owns Android' in r.stdout,r.stdout
  assert all('COMMAND ctl.'+verb+' ' not in r.stdout for verb in ('start','stop','restart')),r.stdout
 if scenario=='normal':""")
    native.write_text(text)
    subprocess.run(['python3', str(native)], check=True)

    hooks = tests / 'test_hooks.py'
    text = hooks.read_text().replace('date() {', '''awk() {
 if [ "$2" = /proc/uptime ] && [ -n "${FAKE_CLOCK:-}" ]; then date +%s; else command awk "$@"; fi
}
date() {''')
    hooks.write_text(text)
    subprocess.run(['python3', str(hooks)], check=True)

    archive = ROOT / 'releases/gxr-framebuffer10-azj2-0.1.0-disabled.zip'
    dist = source / 'dist/framebuffer10'
    dist.mkdir(parents=True)
    shutil.copyfile(archive, dist / 'gxr-framebuffer10-0.1.0-azj2-experimental-auto.zip')
    subprocess.run(['python3', str(tests / 'test_lifecycle.py')], check=True)

    # The checkbox applies at the next coordinated restart, never an independent stop.
    module = source / 'modules/framebuffer10/module'
    for name in ('cold-boot-reset.sh',):
        (module / name).write_text('exit 0\n')
    (module / 'bin').mkdir()
    (module / 'bin/gxr-fb10-gate').write_text('#!/bin/sh\nexit 99\n')
    (module / 'bin/gxr-fb10-gate').chmod(0o755)
    (module / 'session-lease').mkdir()
    result = subprocess.run(['sh', str(module / 'auto.sh'), 'disable'], capture_output=True, text=True)
    assert result.returncode == 1 and (module / 'disable').exists(), result
    assert 'Soft restart' in result.stdout, result.stdout
print('PASS: AZJ2 native coordination, bounded hooks and disabled-session removal gate')
