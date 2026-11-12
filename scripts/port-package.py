"""Small shared packager for disabled GXR ports; no vendor firmware payloads."""
import hashlib
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


def package(output, payload, executables=()):
    payload = dict(payload)
    payload['disable'] = b''
    payload['skip_mount'] = b''
    for name in payload:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or len(path.parts) >= 8 or str(path) != name:
            raise ValueError('Unsafe/deep package path: ' + name)
    for name in ('action.sh', 'auto.sh', 'module.prop', 'service.sh'):
        if name not in payload: raise ValueError('Missing GXR entry: ' + name)
    payload['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
        for name,data in sorted(payload.items()) if name not in ('disable','SHA256SUMS')).encode()
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
