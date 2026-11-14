"""Package pinned upstream Wi-Fi ADB unchanged for the AZJ2 module collection."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from gxr_build import export_source, validate_package, write_checksum

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://github.com/4uva4ek/galaxyxr-modules.git'
COMMIT = '9f096dfc79e72f180410bcfa5ba32b566734f62b'
VERSION = '1.0.2'


def validate(archive, source):
    """Check the GXR installer contract and byte-identical upstream runtime."""
    payload = validate_package(archive)
    expected = {p.relative_to(source).as_posix(): p.read_bytes()
                for p in source.rglob('*') if p.is_file()}
    if set(payload) != set(expected) | {'disable', 'SHA256SUMS'}:
        raise ValueError('Unexpected upstream payload')
    for name, data in expected.items():
        if payload[name] != data:
            raise ValueError('Modified upstream payload: ' + name)
    props = dict(line.split('=', 1) for line in payload['module.prop'].decode().splitlines() if '=' in line)
    if (props['id'], props['version'], props['author']) != ('gxr_wifi_adb', VERSION, '4uva4ek'):
        raise ValueError('Incorrect upstream identity')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, help='Existing repository containing the pinned commit')
    parser.add_argument('--output', type=Path, default=ROOT / 'releases')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='gxr-wifi-adb-') as temporary:
        work = Path(temporary)
        export_source(work / 'source', UPSTREAM, COMMIT, ('modules/wifi-adb',), args.upstream)
        module = work / 'source/modules/wifi-adb'
        subprocess.run([sys.executable, str(module / 'test_lifecycle.py')], check=True)
        subprocess.run([sys.executable, str(module / 'build.py')], check=True)
        built = work / f'source/dist/wifi-adb/gxr-wifi-adb-{VERSION}-auto.zip'
        validate(built, module / 'module')
        args.output.mkdir(parents=True, exist_ok=True)
        result = args.output / f'gxr-wifi-adb-azj2-{VERSION}-disabled.zip'
        shutil.copyfile(built, result)
        digest = write_checksum(result)
        print(f'{result}: {result.stat().st_size} bytes SHA256 {digest}')
        print('Upstream runtime and ZIP bytes unchanged; AZJ2 headset behavior untested.')


if __name__ == '__main__':
    main()
