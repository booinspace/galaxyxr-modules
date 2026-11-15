"""Build the standalone disabled AZJ2 Saved Workspaces module; no vendor binaries are bundled."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from gxr_build import class_archive, dex, package, resolve_tools, sha256

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('java', 'javac', 'r8', 'android-jar'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'releases')
    args = parser.parse_args()
    resolve_tools(parser, args, ('java', 'javac', 'r8', 'android_jar'))
    module = ROOT / 'modules/saved-workspaces'
    with tempfile.TemporaryDirectory(prefix='gxr-workspaces-') as temporary:
        work = Path(temporary)
        tests = work / 'tests'
        tests.mkdir()
        core = ('Workspace', 'WorkspaceMath', 'WorkspacePlan', 'WorkspaceStore', 'WorkspaceEngine', 'WorkspaceWait', 'WorkspaceFollowMotion')
        sources = module / 'java/local/gxr/workspaces'
        subprocess.run([str(args.javac), '--release', '8', '-d', str(tests),
                        *(str(sources / (name + '.java')) for name in core),
                        str(ROOT / 'tests/WorkspaceTest.java')], check=True)
        subprocess.run([str(args.java), '-cp', str(tests), 'WorkspaceTest'], check=True)
        subprocess.run(['node', '--test', str(ROOT / 'tests/workspaces-agent.test.mjs')], check=True)
        classes = work / 'classes'
        classes.mkdir()
        runtime = ROOT / 'scripts/bread-port/PortRuntime.java'
        java_sources = sorted(sources.glob('*.java')) + [runtime]
        subprocess.run([str(args.javac), '--release', '8', '-nowarn', '-classpath', str(args.android_jar),
                        '-d', str(classes), *(str(path) for path in java_sources)], check=True)
        jar = work / 'helper.jar'
        class_archive(classes, jar)
        payload = {path.name: path.read_bytes() for path in module.iterdir() if path.is_file()}
        payload['bin/helper.dex'] = dex(args, jar, None, work / 'dex')
        if len(payload['bin/helper.dex']) > 512 * 1024:
            raise ValueError('Workspace transport limit exceeded')
        runtime_script = (ROOT / 'scripts/bread-port/daemon-control.sh').read_text()
        # Action delegates startup to service.sh so it does not inherit the manager's frozen cgroup.
        payload['bin/runtime.sh'] = runtime_script.encode()
        for source in java_sources:
            payload['bin/source/' + source.name] = source.read_bytes()
        for name in ('build-saved-workspaces-azj2.py', 'gxr_build.py', 'curvature-workspaces-agent.mjs'):
            payload['bin/source/' + name] = (ROOT / 'scripts' / name).read_bytes()
        payload['bin/build-info.json'] = (json.dumps({
            'target': 'Samsung SM-I610 I610UES3AZJ2 Android 14',
            'dependency': 'Window Controls 0.1.70+ (versionCode 171+)',
            'status': 'experimental; full workspace behavior requires headset testing',
            'tools': {name: sha256(getattr(args, name).read_bytes()) for name in ('java', 'javac', 'r8', 'android_jar')},
            'sources': {name: sha256(data) for name, data in sorted(payload.items()) if name.startswith('bin/source/')},
        }, indent=2, sort_keys=True) + '\n').encode()
        for path in module.glob('*.sh'):
            subprocess.run(['sh', '-n', str(path)], check=True)
        package(args.output / 'gxr-saved-workspaces-azj2-0.1.5-disabled.zip', payload)


if __name__ == '__main__':
    main()
