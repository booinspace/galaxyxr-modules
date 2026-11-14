"""Package pinned upstream Wi-Fi ADB unchanged for the AZJ2 module collection."""
import argparse
import hashlib
import io
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://github.com/4uva4ek/galaxyxr-modules.git'
COMMIT = '9f096dfc79e72f180410bcfa5ba32b566734f62b'
VERSION = '1.0.2'


def validate(archive, source):
    """Check the GXR installer contract and byte-identical upstream runtime."""
    forbidden = runpy.run_path(str(ROOT / 'scripts/port-package.py'))['FORBIDDEN']
    with ZipFile(archive) as package:
        names = package.namelist()
        expected = {p.relative_to(source).as_posix(): p.read_bytes()
                    for p in source.rglob('*') if p.is_file()}
        assert len(names) == len(set(names)) and package.testzip() is None
        assert set(names) == set(expected) | {'disable', 'SHA256SUMS'}
        assert not forbidden.intersection(names)
        assert package.read('disable') == package.read('skip_mount') == b''
        for name, data in expected.items():
            assert package.read(name) == data, 'Modified upstream payload: ' + name
            if name.endswith('.sh'):
                assert (package.getinfo(name).external_attr >> 16) & 0o111
        props = dict(line.split('=', 1) for line in package.read('module.prop').decode().splitlines()
                     if '=' in line)
        assert (props['id'], props['version'], props['author']) == ('gxr_wifi_adb', VERSION, '4uva4ek')
        sums = dict((name, digest) for digest, name in
                    (line.split('  ', 1) for line in package.read('SHA256SUMS').decode().splitlines()))
        assert set(sums) == set(names) - {'disable', 'SHA256SUMS'}
        for name, digest in sums.items():
            assert hashlib.sha256(package.read(name)).hexdigest() == digest, name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, help='Existing repository containing the pinned commit')
    parser.add_argument('--output', type=Path, default=ROOT / 'releases')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='gxr-wifi-adb-') as temporary:
        work = Path(temporary)
        checkout = args.upstream.resolve() if args.upstream else work / 'upstream'
        if not args.upstream:
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
            subprocess.run(['git', '-C', str(checkout), 'fetch', '--depth=1', UPSTREAM, COMMIT], check=True)
        actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', COMMIT + '^{commit}'],
                                         text=True).strip()
        if actual != COMMIT:
            parser.error('Pinned upstream commit is required')
        data = subprocess.check_output(['git', '-C', str(checkout), 'archive', '--format=zip',
                                        COMMIT, 'modules/wifi-adb'])
        # Export committed files so local edits and untracked helpers cannot enter the build.
        with ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(work / 'source')
        module = work / 'source/modules/wifi-adb'
        subprocess.run([sys.executable, str(module / 'test_lifecycle.py')], check=True)
        subprocess.run([sys.executable, str(module / 'build.py')], check=True)
        built = work / f'source/dist/wifi-adb/gxr-wifi-adb-{VERSION}-auto.zip'
        validate(built, module / 'module')
        args.output.mkdir(parents=True, exist_ok=True)
        result = args.output / f'gxr-wifi-adb-azj2-{VERSION}-disabled.zip'
        shutil.copyfile(built, result)
        digest = hashlib.sha256(result.read_bytes()).hexdigest()
        result.with_suffix('.zip.sha256').write_text(f'{digest}  {result.name}\n')
        print(f'{result}: {result.stat().st_size} bytes SHA256 {digest}')
        print('Upstream runtime and ZIP bytes unchanged; AZJ2 headset behavior untested.')


if __name__ == '__main__':
    main()
