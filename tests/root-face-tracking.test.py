"""Offline checks for the AZJ2 relay's trace ownership, payload and package."""
import hashlib
import json
from pathlib import Path
import runpy
import socket
import struct
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'modules/root-face-tracking'
build = runpy.run_path(str(ROOT / 'scripts/build-root-face-tracking-azj2.py'))

with tempfile.TemporaryDirectory(prefix='gxr-ft-check-') as temporary:
    work = Path(temporary)
    source = work / 'source'
    build['prepare'](source)
    patched = (source / 'headset/gxr_alvr.c').read_text()
    assert 'O_TRUNC' not in patched
    assert 'TRACE "/uprobe_events"' not in patched
    assert 'p:" TRACE_GROUP "/pten' in patched
    assert 'rc_dir != 0 || rc_face != 0 || rc_jaw != 0 || rc_tongue != 0' in patched
    for test in ('gaze_math_selftest', 'relay_selftest'):
        binary = work / test
        subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror', str(source / 'tools' / (test+'.c')), '-lm', '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
        assert 'FAIL' not in result.stdout
        print(test + ': ' + str(sum(line.startswith('ok ') for line in result.stdout.splitlines())) + ' checks passed')

    trace = work / 'tracefs'
    instance = trace / 'instances/gxr_ft_azj2'
    names = ('pten','dir','bs','jaw','tongue')
    for name in names:
        path = instance / 'events/gxr_ft_azj2' / name / 'enable'
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text('1\n')
    (instance / 'tracing_on').write_text('1\n')
    (trace / 'tracing_on').write_text('1\n')
    (trace / 'buffer_size_kb').write_text('12345\n')
    foreign = trace / 'events/foreign/keep/enable'
    foreign.parent.mkdir(parents=True); foreign.write_text('1\n')
    events = trace / 'uprobe_events'
    events.write_text('p:foreign/keep /example:0x20\n')
    harness = work / 'trace_scope.c'
    harness.write_text('#define main gxr_sender_main\n#include '+json.dumps(str(source/'headset/gxr_alvr.c'))+'''
#undef main
int main(void) { tracefs_cleanup(); return 0; }
''')
    binary = work / 'trace_scope'
    subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-DTRACE_ROOT='+json.dumps(str(trace)),str(harness),'-lm','-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
    assert events.read_text() == 'p:foreign/keep /example:0x20\n'+''.join('-:gxr_ft_azj2/'+n+'\n' for n in names)
    assert foreign.read_text() == (trace/'tracing_on').read_text() == '1\n'
    assert (trace/'buffer_size_kb').read_text() == '12345\n'
    assert (instance/'tracing_on').read_text() == '0\n'
    assert all((instance/'events/gxr_ft_azj2'/n/'enable').read_text() == '0\n' for n in names)
    print('Trace cleanup leaves foreign probes, global tracing and global buffer size untouched')

    sender = work / 'sender'
    subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror',str(source/'headset/gxr_alvr.c'),'-lm','-o',str(sender)],check=True)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
        receiver.bind(('127.0.0.1',41463)); receiver.settimeout(3)
        subprocess.run([str(sender),'--selftest','--pc','127.0.0.1'],check=True,capture_output=True)
        data,_ = receiver.recvfrom(4096)
    assert len(data)==404 and data[:8]==b'UniExpr\0'
    values=struct.unpack('<99f',data[8:])
    assert abs(values[22]-.22)<1e-6 and values[88]==1.0
    assert abs(values[89]-.9)<1e-6 and abs(values[98]-.22)<1e-6
    assert subprocess.run([str(sender),'--selftest','--pc','127.0.0.1','--jaw-offset','0x1234'],capture_output=True).returncode==2
    assert subprocess.run([str(sender),'--selftest'],capture_output=True).returncode==2
    print('UniExpr packet matches the 404-byte receiver format; unverified offsets and implicit broadcast rejected')

    # Exercise the real shell validator and its trust boundary without writing module state.
    controller=(MODULE/'control.sh').read_text()
    validator=controller[controller.index('valid_pc() {'):controller.index('\nstock()')]
    for address,expected in [('192.168.10.13',0),('10.0.0.2',0),('1.2.3.4',0),('',1),('256.1.1.1',1),('127.0.0.1',1),('224.0.0.1',1),('1.2.3.255',1),('01.2.3.4',1),('1.2.3.4;id',1),('1.2.3.4\n10.0.0.2',1)]:
        result=subprocess.run(['sh','-c',validator+'\nvalid_pc "$1"','test',address])
        assert result.returncode==expected,address
    print('PC address validator rejects shell syntax, multicast, loopback and malformed destinations')

    membership=work/'cgroup'
    mounts=work/'mountinfo'; mounts.write_text('')
    helper=(MODULE/'cgroup.sh').read_text().replace('/proc/self/cgroup',str(membership)).replace('/proc/self/mountinfo',str(mounts))
    for group,expected in [('/',0),('/gxr-root-ft-azj2',0),('/uid_10263/pid_6101',1),('/uid_bad/pid_6101',1)]:
        membership.write_text('5:memory:/\n0::'+group+'\n')
        result=subprocess.run(['sh','-c',helper+'\nLOG="$1"; escape_manager_cgroup','test',str(work/'cgroup.log')])
        assert result.returncode==expected,group
    membership.write_text('5:memory:/\n')
    assert subprocess.run(['sh','-c',helper+'\nLOG="$1"; escape_manager_cgroup','test',str(work/'cgroup.log')]).returncode==1
    print('Cgroup starts permit boot-owned contexts and refuse unverified app/freezer contexts')

package=ROOT/'releases/gxr-root-face-tracking-azj2-0.1.1-disabled.zip'
if package.exists():
    with ZipFile(package) as archive:
        names=archive.namelist()
        forbidden=runpy.run_path(str(ROOT/'scripts/port-package.py'))['FORBIDDEN']
        assert not (set(names) & forbidden)
        assert all('/' not in n or n.startswith(('bin/','webroot/')) for n in names)
        assert len(names)==len(set(names))
        assert archive.read('disable')==archive.read('skip_mount')==b''
        for phase in ('prepare','stopped','started','abort'): assert 'restart-'+phase+'.sh' in names
        binary=archive.read('bin/gxr_alvr')
        assert binary[:6]==b'\x7fELF\x02\x01' and binary[18:20]==b'\xb7\x00'
        assert (archive.getinfo('bin/gxr_alvr').external_attr>>16)&0o111
        assert not any(n.endswith('.so') for n in names)
        for line in archive.read('SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1)
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest,name
        assert b'I610UES3AZJ2' in archive.read('guard.sh')
        assert b'--cleanup' in archive.read('control.sh')
        assert b'$MODDIR/bin/gxr_alvr' in archive.read('control.sh')
        assert 'gxr_alvr' not in names  # GXR installs root-level non-shell files with mode 0600.
        assert b'compdoge' in archive.read('LICENSE.upstream')
    print('Disabled arm64 ZIP, checksums, provenance and GXR restart hooks verified')
else:
    print('Source checks passed; ZIP checks run after the NDK build')
