"""Build 4uva4ek's pinned SystemUI Optimization v0.4.0 for the inspected AZJ2 libraries."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from gxr_build import export_source, package, validate_arm64, validate_package

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://github.com/4uva4ek/galaxyxr-modules.git'
COMMIT = '3ccf395bf12d0525c257d043568c7d7b4e4014a6'
BUILD = 'UML2.260301.001.I610UES3AZJ2'
PINS = {
    'libImpress-jni-vulkan.so': 'ab04d6daf57800a42170febaf33cb128441339c06bd6d46f068c0109693fee42',
    'libspaceflinger_jni_vulkan.so': '8342a55dd62163af3653dcf2153a842e243377897ced3ca00703603d275a3d7f',
    'libsysui_jni_soong_vulkan.so': 'f6e34cf42f704c5d3ced9cca18dd392abf4925cde9e30c3b752a34be4102a809',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, required=True, help='Android NDK 29.0.14206865')
    parser.add_argument('--libraries', type=Path, required=True, help='Private stock AZJ2 copies of the three pinned libraries')
    parser.add_argument('--upstream', type=Path, help='Existing checkout containing the pinned upstream commit')
    parser.add_argument('--output', type=Path, default=ROOT / 'releases')
    args = parser.parse_args()
    for name, expected in PINS.items():
        if hashlib.sha256((args.libraries / name).read_bytes()).hexdigest() != expected:
            parser.error('Exact AZJ2 library required: ' + name)
    if 'Pkg.Revision = 29.0.14206865' not in (args.ndk / 'source.properties').read_text().splitlines():
        parser.error('Android NDK 29.0.14206865 required')
    with tempfile.TemporaryDirectory(prefix='gxr-systemui-azj2-') as temporary:
        work = Path(temporary)
        source = work / 'upstream'
        export_source(source, UPSTREAM, COMMIT,
                      ('modules/systemui-optimization', 'modules/controller-whitening/native/freeze.inc',
                       'tools/build.py', 'tools/cold-boot-reset.sh'), args.upstream)
        local = ROOT / 'modules/systemui-optimization'
        patch = local / 'azj2.patch'
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=source, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=source, check=True)
        module = source / 'modules/systemui-optimization'
        subprocess.run([sys.executable, str(module / 'tests/test_lifecycle.py')], check=True)
        subprocess.run([sys.executable, str(module / 'prepare_compatibility.py'),
                        '--library', str((args.libraries / 'libImpress-jni-vulkan.so').resolve())], check=True)
        subprocess.run([sys.executable, str(module / 'prepare_panels.py'),
                        '--libraries', str(args.libraries.resolve()), '--ndk', str(args.ndk.resolve())], check=True)
        for test in ('test_depth_patch.py', 'test_wait_fix.py'):
            subprocess.run([sys.executable, str(module / 'tests' / test),
                            str((args.libraries / 'libImpress-jni-vulkan.so').resolve())], check=True)
        subprocess.run([sys.executable, str(module / 'tests/test_panel_payload.py'),
                        str(source / 'dist/systemui-optimization/panels')], check=True)
        subprocess.run([sys.executable, str(source / 'tools/build.py'), 'systemui-optimization',
                        '--ndk', str(args.ndk.resolve())], check=True)
        built = source / 'dist/systemui-optimization/gxr-systemui-optimization-0.4.0-azj2.1-experimental-auto.zip'
        with ZipFile(built) as archive:
            payload = {name: archive.read(name) for name in archive.namelist() if name not in ('disable', 'SHA256SUMS')}
        for path in local.glob('*.sh'):
            subprocess.run(['sh', '-n', str(path)], check=True)
            payload[path.name] = path.read_bytes()
        # Reuse the existing generation/ready gate before this separate native worker starts.
        service = (ROOT / 'scripts/curvature-service.sh').read_text()
        entry = 'export GXR_WINDOW_AUTOSTART=1\nexec sh "$MODDIR/control.sh" run'
        if service.count(entry) != 1:
            raise ValueError('Coordinated service entry changed; review the startup adapter')
        service = service.replace(entry,
                                  'rm -f /dev/gxr_systemui_optimization_azj2/coordinated-restart\nexec sh "$MODDIR/auto.sh" resume')
        payload['service.sh'] = service.encode()
        payload['README.md'] = (local / 'README.md').read_bytes()
        payload['bin/source/azj2.patch'] = patch.read_bytes()
        payload['bin/source/build-systemui-optimization-azj2.py'] = Path(__file__).read_bytes()
        payload['bin/source/gxr_build.py'] = (ROOT / 'scripts/gxr_build.py').read_bytes()
        receipt = {'upstream': UPSTREAM, 'commit': COMMIT, 'targetBuild': BUILD, 'libraries': PINS,
                   'ndk': '29.0.14206865', 'deviceActivationTested': False,
                   'patchSha256': hashlib.sha256(patch.read_bytes()).hexdigest()}
        payload['bin/source/build-receipt.json'] = (json.dumps(receipt, indent=2) + '\n').encode()
        validate_arm64(payload['bin/gxr-systemui'])
        if BUILD.encode() not in payload['bin/gxr-systemui']:
            raise ValueError('Native firmware guard missing')
        props = dict(line.split('=', 1) for line in payload['module.prop'].decode().splitlines() if '=' in line)
        if (props['id'], props['versionCode']) != ('gxr_systemui_optimization_azj2', '402') or 'updateJson' in props:
            raise ValueError('Incorrect AZJ2 module identity/update feed')
        for digest in PINS.values():
            if digest.encode() not in payload['auto.sh']:
                raise ValueError('Runtime library hash gate missing')
        args.output.mkdir(parents=True, exist_ok=True)
        output = args.output / 'gxr-systemui-optimization-azj2-0.4.0-r2-disabled.zip'
        package(output, payload, executables=('bin/gxr-systemui',))
        validate_package(output, executables=('bin/gxr-systemui',))
        print('AZJ2 package and ARM64/lifecycle checks passed; live activation and performance are untested.')


if __name__ == '__main__':
    main()
