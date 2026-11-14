"""Shared build-time helpers; module policy and firmware pins stay in each builder."""
import hashlib
import io
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

# Keep these payload restrictions aligned with KernelSU GXR's gxr_update.rs.
FORBIDDEN = frozenset(('post-fs-data.sh', 'post-mount.sh', 'system.prop',
    'sepolicy.rule', 'boot-completed.sh', 'remove', 'update', 'guard-boot-id',
    'auto.pending', 'failure'))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_checksum(path):
    path = Path(path)
    digest = sha256(path.read_bytes())
    path.with_suffix(path.suffix + '.sha256').write_text(f'{digest}  {path.name}\n')
    return digest


def replace_exact(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError('Pinned source pattern mismatch: ' + str(path))
    path.write_text(text.replace(old, new))


def check_installer_entries(names):
    invalid = FORBIDDEN.intersection(names)
    if invalid:
        raise ValueError('Unsupported GXR startup/state payload: ' + ', '.join(sorted(invalid)))


def validate_payload(payload, executables=()):
    for name in payload:
        path = PurePosixPath(name)
        if not path.parts or path.is_absolute() or '..' in path.parts or len(path.parts) >= 8 or str(path) != name:
            raise ValueError('Unsafe/deep package path: ' + name)
        if not all(re.fullmatch(r'[A-Za-z0-9._-]+', part) for part in path.parts):
            raise ValueError('Unsafe package path: ' + name)
        if '/' in name and not name.startswith(('bin/', 'webroot/')):
            raise ValueError('Unexpected payload directory: ' + name)
    check_installer_entries(payload)
    for name in ('action.sh', 'auto.sh', 'module.prop', 'service.sh', 'disable', 'skip_mount'):
        if name not in payload:
            raise ValueError('Missing GXR entry: ' + name)
    if payload['disable'] or payload['skip_mount']:
        raise ValueError('Release must install disabled with skip_mount')
    identities = [line[3:] for line in payload['module.prop'].decode().splitlines() if line.startswith('id=')]
    # Other IDs select the legacy installer, which removes README.md and executable modes.
    if len(identities) != 1 or not re.fullmatch(r'gxr_[A-Za-z0-9._-]+', identities[0]):
        raise ValueError('GXR package ID must start with gxr_ and contain only safe filename characters')
    if any(name not in payload or not (name.startswith('bin/') or name.endswith('.sh')) for name in executables):
        raise ValueError('GXR native executables must be packaged under bin/')
    hooks = {f'restart-{phase}.sh' for phase in ('prepare', 'stopped', 'started', 'abort')}
    if 'restart-prepare.sh' in payload and not hooks.issubset(payload):
        raise ValueError('Incomplete GXR coordinated-restart hooks')
    if len(payload) > 128 or sum(map(len, payload.values())) > 64 * 1024 * 1024:
        raise ValueError('GXR package exceeds installer limits')


def validate_package(path, executables=()):
    """Validate paths, installer layout, permissions and the complete manifest."""
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError('Invalid ZIP')
        payload = {name: archive.read(name) for name in names}
        validate_payload(payload, executables)
        if 'SHA256SUMS' not in payload:
            raise ValueError('Missing checksum manifest')
        rows = [line.split('  ', 1) for line in payload['SHA256SUMS'].decode().splitlines()]
        if any(len(row) != 2 or not re.fullmatch('[0-9a-f]{64}', row[0]) for row in rows):
            raise ValueError('Invalid checksum manifest')
        sums = {name: digest for digest, name in rows}
        if len(sums) != len(rows) or set(sums) != set(names) - {'disable', 'SHA256SUMS'}:
            raise ValueError('Incomplete manifest')
        for name, expected in sums.items():
            if sha256(payload[name]) != expected:
                raise ValueError('Payload checksum mismatch: ' + name)
        for entry in archive.infolist():
            mode = entry.external_attr >> 16
            if (mode & 0o170000) not in (0, 0o100000):
                raise ValueError('Non-regular ZIP entry: ' + entry.filename)
            if (entry.filename.endswith('.sh') or entry.filename in executables) and not mode & 0o111:
                raise ValueError('Executable permission missing: ' + entry.filename)
    return payload


def package(output, payload, executables=(), timestamp=(2026, 11, 12, 0, 0, 0)):
    """Write a deterministic, disabled GXR ZIP and its checksum sidecar."""
    payload = dict(payload)
    payload['disable'] = b''
    payload['skip_mount'] = b''
    payload['SHA256SUMS'] = ''.join(f'{sha256(data)}  {name}\n'
        for name, data in sorted(payload.items()) if name not in ('disable', 'SHA256SUMS')).encode()
    validate_payload(payload, executables)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            entry = ZipInfo(name, timestamp)
            entry.create_system = 3
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = (0o100755 if name.endswith('.sh') or name in executables else 0o100644) << 16
            archive.writestr(entry, data)
    if validate_package(output, executables) != payload:
        raise ValueError('Package payload mismatch')
    digest = write_checksum(output)
    print(f'{output}: {output.stat().st_size} bytes SHA256 {digest}')
    return output


def resolve_tools(parser, args, names):
    for name in names:
        path = getattr(args, name).resolve()
        if not path.is_file():
            parser.error(f'Missing {name}: {path}')
        setattr(args, name, path)


def class_archive(directory, target):
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for source in sorted(directory.rglob('*.class')):
            archive.write(source, source.relative_to(directory).as_posix())


def dex(args, jar, stubs, destination):
    destination.mkdir()
    command = [str(args.java), '-cp', str(args.r8), 'com.android.tools.r8.D8',
               '--release', '--min-api', '34', '--lib', str(args.android_jar), '--output', str(destination)]
    if stubs is not None:
        command += ['--classpath', str(stubs)]
    subprocess.run(command + [str(jar)], check=True)
    result = (destination / 'classes.dex').read_bytes()
    if not result.startswith(b'dex\n') or len(list(destination.glob('*.dex'))) != 1:
        raise ValueError('Expected one helper DEX')
    return result


def validate_arm64(blob):
    if blob[:6] != b'\x7fELF\x02\x01' or blob[18:20] != b'\xb7\x00':
        raise ValueError('Expected Android ARM64 ELF')


def ndk_compiler(ndk, revision, api):
    ndk = ndk.resolve()
    if f'Pkg.Revision = {revision}' not in (ndk / 'source.properties').read_text().splitlines():
        raise ValueError('Android NDK ' + revision + ' required')
    host = {'Linux': 'linux-x86_64', 'Darwin': 'darwin-x86_64'}[platform.system()]
    return ndk / 'toolchains/llvm/prebuilt' / host / f'bin/aarch64-linux-android{api}-clang'


def export_source(destination, url, commit, paths=(), checkout=None):
    """Export pinned Git objects, excluding all working-tree and untracked edits."""
    if checkout is None:
        checkout = destination.parent / 'checkout'
        subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
        subprocess.run(['git', '-C', str(checkout), 'fetch', '--depth=1', url, commit], check=True)
    actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', commit + '^{commit}'], text=True).strip()
    if actual != commit:
        raise ValueError('Pinned upstream commit is required')
    data = subprocess.check_output(['git', '-C', str(checkout), 'archive', '--format=zip', commit, *paths])
    with ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(destination)
