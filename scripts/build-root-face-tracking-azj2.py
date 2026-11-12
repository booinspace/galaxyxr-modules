"""Build compdoge's MIT root face relay with isolated AZJ2 tracing and GXR lifecycle."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'modules/root-face-tracking'


def prepare(destination):
    """Copy pinned upstream source, then apply the auditable AZJ2 integration patch."""
    shutil.copytree(MODULE / 'upstream', destination)
    subprocess.run(['patch', '-p1', '--batch', '-i', str(MODULE / 'azj2.patch')], cwd=destination, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'releases')
    args = parser.parse_args()
    ndk = args.ndk.resolve()
    if 'Pkg.Revision = 29.0.14206865' not in (ndk / 'source.properties').read_text():
        parser.error('Android NDK 29.0.14206865 required')
    host = {'Linux': 'linux-x86_64', 'Darwin': 'darwin-x86_64'}[platform.system()]
    compiler = ndk / 'toolchains/llvm/prebuilt' / host / 'bin/aarch64-linux-android29-clang'
    package = runpy.run_path(str(ROOT / 'scripts/port-package.py'))['package']
    with tempfile.TemporaryDirectory(prefix='gxr-root-face-build-') as temporary:
        work = Path(temporary)
        source = work / 'source'
        prepare(source)
        binary = work / 'gxr_alvr'
        subprocess.run([str(compiler), '-O2', '-Wall', '-Wextra', '-Werror',
                        '-Wl,-z,max-page-size=16384', str(source / 'headset/gxr_alvr.c'), '-lm', '-o', str(binary)], check=True)
        blob = binary.read_bytes()
        if blob[:6] != b'\x7fELF\x02\x01' or blob[18:20] != b'\xb7\x00':
            raise ValueError('Expected Android arm64 ELF')
        payload = {p.relative_to(MODULE).as_posix(): p.read_bytes() for p in MODULE.rglob('*')
                   if p.is_file() and 'upstream' not in p.relative_to(MODULE).parts}
        payload['bin/gxr_alvr'] = blob
        payload['LICENSE.upstream'] = (MODULE / 'upstream/LICENSE').read_bytes()
        # Include all source and build inputs, with stable archive metadata.
        bundled = [p for p in MODULE.rglob('*') if p.is_file()]
        bundled += [Path(__file__), ROOT / 'scripts/port-package.py', ROOT / 'tests/root-face-tracking.test.py', ROOT / 'tests/port-package.test.py']
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode='w') as archive:
            for p in sorted(bundled):
                data = p.read_bytes()
                info = tarfile.TarInfo(p.relative_to(ROOT).as_posix())
                info.size = len(data); info.mode = 0o644
                archive.addfile(info, io.BytesIO(data))
        payload['bin/source/source.tar.gz'] = gzip.compress(archive_bytes.getvalue(), mtime=0)
        receipt = {
            'upstream': json.loads((MODULE / 'UPSTREAM.json').read_text()),
            'ndk': '29.0.14206865', 'android_api': 29,
            'status': 'AZJ2 libraries and probe instructions inspected; no live probe or avatar validation',
            'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(bundled)},
            'binary_sha256': hashlib.sha256(blob).hexdigest(),
        }
        payload['bin/build-info.json'] = (json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode()
        package(args.output / 'gxr-root-face-tracking-azj2-0.1.1-disabled.zip', payload, executables=('bin/gxr_alvr',))


if __name__ == '__main__':
    main()
