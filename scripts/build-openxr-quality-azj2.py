"""Build pinned OpenXR QUALITY with the reviewed AZJ2 policy identity."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://github.com/4uva4ek/galaxyxr-modules.git'
COMMIT = '9f096dfc79e72f180410bcfa5ba32b566734f62b'
BUILD = 'UML2.260301.001.I610UES3AZJ2'
SERVICES = 'ca2d7cdb6a549b7bdbef2c0ef1cab025b2b058f724fc4710911aedb7b9e71555'
OLD_SERVICES = '1e6f0e8e85020b0ed25bcb387bf7604c9d38c73519ad85df04e15968290b1018'


def validate(archive):
    """Reject mismatched native identities, unsafe layout and altered payloads."""
    forbidden = runpy.run_path(str(ROOT / 'scripts/port-package.py'))['FORBIDDEN']
    with ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or z.testzip() is not None:
            raise ValueError('Invalid ZIP')
        if forbidden.intersection(names) or z.read('disable') != b'' or z.read('skip_mount') != b'':
            raise ValueError('Invalid GXR startup layout')
        props = dict(line.split('=', 1) for line in z.read('module.prop').decode().splitlines() if '=' in line)
        if (props['id'], props['version'], props['versionCode']) != ('gxr_openxr_quality', '0.1.2-azj2', '3'):
            raise ValueError('Incorrect update identity')
        if 'updateJson' in props:
            raise ValueError('The AZF3 update feed must not replace this port')
        native = z.read('bin/gxr-quality')
        required = (BUILD, SERVICES,
                    '562d027ff604a428b4004882589910be5a21dc1ee7972556929784abd8f44ac5',
                    '1da138baee18d16352938d7d33598ed715be8ba31d2bdea23940537001c9f24c',
                    '43392c7b1e812d52578a8bdffe03a08420c877fde922bdfcfdbe537afde72bf2')
        if native[:6] != b'\x7fELF\x02\x01' or native[18:20] != b'\xb7\x00':
            raise ValueError('Expected Android ARM64 ELF')
        if any(value.encode() not in native for value in required) or OLD_SERVICES.encode() in native:
            raise ValueError('Native firmware guards do not target AZJ2')
        if not (z.getinfo('bin/gxr-quality').external_attr >> 16) & 0o111:
            raise ValueError('Native executable permission missing')
        sums = dict((name, digest) for digest, name in
                    (line.split('  ', 1) for line in z.read('SHA256SUMS').decode().splitlines()))
        if set(sums) != set(names) - {'disable', 'SHA256SUMS'}:
            raise ValueError('Incomplete manifest')
        for name, expected in sums.items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise ValueError('Payload checksum mismatch: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, default=os.environ.get('ANDROID_NDK_HOME'), required=not os.environ.get('ANDROID_NDK_HOME'))
    parser.add_argument('--upstream', type=Path, help='Existing repository containing the pinned commit')
    parser.add_argument('--output', type=Path, default=ROOT / 'releases')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='gxr-quality-azj2-') as temporary:
        work = Path(temporary)
        checkout = args.upstream.resolve() if args.upstream else work / 'upstream'
        if not args.upstream:
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
            subprocess.run(['git', '-C', str(checkout), 'fetch', '--depth=1', UPSTREAM, COMMIT], check=True)
        actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', COMMIT + '^{commit}'], text=True).strip()
        if actual != COMMIT:
            parser.error('Pinned upstream commit is required')
        data = subprocess.check_output(['git', '-C', str(checkout), 'archive', '--format=zip',
                                        COMMIT, 'modules/openxr-quality', 'tools/build.py'])
        source = work / 'source'
        with ZipFile(io.BytesIO(data)) as z:
            z.extractall(source)
        patch = ROOT / 'modules/openxr-quality/azj2.patch'
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=source, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=source, check=True)
        module = source / 'modules/openxr-quality'
        for name in ('test_gate.py', 'test_update_contract.py'):
            subprocess.run([sys.executable, str(module / 'tests' / name)], check=True)
        fixtures = work / 'fixtures'
        fixtures.mkdir()
        paths = []
        for name, package, client in [('idle', 'com.android.systemui', 1),
                                      ('vr', 'com.valvesoftware.steamlinkvr', 7),
                                      ('paused', 'com.samsung.gallery', -1)]:
            path = fixtures / (name + '.txt')
            path.write_text(f'XR Clients state:\n{package}: id={max(client, 1)}, state=running\n'
                            f'Current Visible XR ClientId={client}\nCurrent Visible Managed FSM XR ClientId=-1\nStats since reset:\n')
            paths.append(str(path))
        policy = work / 'policy-test'
        subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        str(module / 'tests/policy_test.cpp'), '-o', str(policy)], check=True)
        print('Running upstream policy assertions with synthetic CPM fixtures.', flush=True)
        subprocess.run([str(policy), *paths], check=True)
        subprocess.run([sys.executable, str(module / 'build.py'), '--ndk', str(args.ndk.resolve())], check=True)
        built = source / 'dist/openxr-quality/gxr-openxr-quality-0.1.2-azj2-auto.zip'
        with ZipFile(built) as z:
            payload = {name: z.read(name) for name in z.namelist() if name not in ('disable', 'SHA256SUMS')}
        receipt = {'upstream': UPSTREAM, 'commit': COMMIT, 'targetBuild': BUILD, 'servicesSha256': SERVICES,
                   'patchSha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
                   'nativeSha256': hashlib.sha256(payload['bin/gxr-quality']).hexdigest(),
                   'ndk': '28.2.13676358', 'deviceActivationTested': False}
        payload['bin/source/build-receipt.json'] = (json.dumps(receipt, indent=2) + '\n').encode()
        payload['bin/source/azj2.patch'] = patch.read_bytes()
        payload['bin/source/build-openxr-quality-azj2.py'] = Path(__file__).read_bytes()
        payload['bin/source/port-package.py'] = (ROOT / 'scripts/port-package.py').read_bytes()
        payload['bin/source/README.md'] = (ROOT / 'modules/openxr-quality/README.md').read_bytes()
        args.output.mkdir(parents=True, exist_ok=True)
        result = args.output / 'gxr-openxr-quality-azj2-0.1.2-disabled.zip'
        runpy.run_path(str(ROOT / 'scripts/port-package.py'))['package'](result, payload, executables=('bin/gxr-quality',))
        validate(result)
        print('AZJ2 build and host policy/lifecycle checks passed; device activation remains untested.')


if __name__ == '__main__':
    main()
