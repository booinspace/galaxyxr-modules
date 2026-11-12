"""Small shared packager for disabled GXR ports; no vendor firmware payloads."""
import hashlib
from pathlib import Path, PurePosixPath
import re
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

# Keep these payload restrictions aligned with KernelSU GXR's gxr_update.rs.
FORBIDDEN = frozenset(('post-fs-data.sh', 'post-mount.sh', 'system.prop',
    'sepolicy.rule', 'boot-completed.sh', 'remove', 'update', 'guard-boot-id',
    'auto.pending', 'failure'))


def package(output, payload, executables=()):
    payload = dict(payload)
    payload['disable'] = b''
    payload['skip_mount'] = b''
    for name in payload:
        path = PurePosixPath(name)
        if not path.parts or path.is_absolute() or '..' in path.parts or len(path.parts) >= 8 or str(path) != name:
            raise ValueError('Unsafe/deep package path: ' + name)
        if not all(re.fullmatch(r'[A-Za-z0-9._-]+', part) for part in path.parts):
            raise ValueError('Unsafe package path: ' + name)
        if name in FORBIDDEN:
            raise ValueError('Unexpected startup/state payload: ' + name)
        if '/' in name and not name.startswith(('bin/', 'webroot/')):
            raise ValueError('Unexpected payload directory: ' + name)
    for name in ('action.sh', 'auto.sh', 'module.prop', 'service.sh'):
        if name not in payload: raise ValueError('Missing GXR entry: ' + name)
    identities = [line[3:] for line in payload['module.prop'].decode().splitlines() if line.startswith('id=')]
    # Other IDs select the legacy installer, which removes README.md and executable modes.
    if len(identities) != 1 or not re.fullmatch(r'gxr_[A-Za-z0-9._-]+', identities[0]):
        raise ValueError('GXR package ID must start with gxr_ and contain only safe filename characters')
    if any(name not in payload or not (name.startswith('bin/') or name.endswith('.sh')) for name in executables):
        raise ValueError('GXR native executables must be packaged under bin/')
    payload['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
        for name,data in sorted(payload.items()) if name not in ('disable','SHA256SUMS')).encode()
    if len(payload) > 128 or sum(map(len, payload.values())) > 64 * 1024 * 1024:
        raise ValueError('GXR package exceeds installer limits')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for name,data in sorted(payload.items()):
            info=ZipInfo(name,(2026,11,12,0,0,0)); info.create_system=3; info.compress_type=ZIP_DEFLATED
            info.external_attr=(0o100755 if name.endswith('.sh') or name in executables else 0o100644)<<16
            archive.writestr(info,data)
    with ZipFile(output) as archive:
        if archive.testzip() is not None: raise ValueError('ZIP integrity failure')
        for name,data in payload.items():
            if archive.read(name)!=data: raise ValueError('Payload mismatch: '+name)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n')
    print(f'{output}: {output.stat().st_size} bytes SHA256 {digest}')
    return output
