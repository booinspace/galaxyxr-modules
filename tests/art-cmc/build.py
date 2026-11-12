"""Build both disposable CMC probes with the combined module's exact bridge patch."""
import argparse
import base64
import io
import hashlib
from pathlib import Path
import subprocess
import tarfile
import tempfile
from zipfile import ZipFile
import frida

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
for name in ('r8', 'android-jar', 'bridge', 'output'):
    parser.add_argument('--' + name, type=Path, required=True)
parser.add_argument('--java', default='java')
parser.add_argument('--javac', default='javac')
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
patch = root.parents[1] / 'scripts/curvature/frida-java-bridge-cmc.patch'
assert hashlib.sha256(patch.read_bytes()).hexdigest() == '354bec3059c53cf9f83d3d8f3dcc81417654c0a2620bfac188c52e0092ba84bd'
subprocess.run([args.javac, '--release', '8', '-d', str(output / 'classes'),
                str(root / 'CmcProbe.java')], check=True)
with ZipFile(output / 'probe.jar', 'w') as jar:
    for source in sorted((output / 'classes').rglob('*.class')):
        jar.write(source, source.relative_to(output / 'classes').as_posix())
subprocess.run([args.java, '-cp', str(args.r8),
                'com.android.tools.r8.D8', '--min-api', '26',
                '--lib', str(args.android_jar),
                '--output', str(output), str(output / 'probe.jar')], check=True)
bridge = args.bridge.read_bytes()
assert base64.b64encode(hashlib.sha512(bridge).digest()).decode() == 'YSyKjxbxKnSi3KSUy9vciOvTOuq0RRh9dkxzkQVEdfIIZlw20zE8D3Cq9eL2FDqUVj4YKas6Wf09kCjL5zbffg=='
assert frida.__version__ == '17.23.3'
for variant in ('unpatched', 'patched'):
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        package = work / 'node_modules/frida-java-bridge'
        package.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(bridge)) as source:
            for entry in source.getmembers():
                if not entry.isfile(): continue
                relative = Path(entry.name).relative_to('package')
                assert '..' not in relative.parts
                target = package / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.extractfile(entry).read())
        if variant == 'patched':
            subprocess.run(['git', 'apply', '--check', str(patch)], cwd=package, check=True)
            subprocess.run(['git', 'apply', str(patch)], cwd=package, check=True)
        (work / 'main.js').write_text((root / 'agent.js').read_text().replace('VARIANT', variant))
        compiler = frida.Compiler()
        diagnostics = []
        compiler.on('diagnostics', diagnostics.append)
        bundle = compiler.build('main.js', project_root=str(work))
        assert not diagnostics, diagnostics
        (output / f'{variant}.js').write_text(bundle)
        print(variant, hashlib.sha256(bundle.encode()).hexdigest())
