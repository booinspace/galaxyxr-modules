"""Validate all new port archives against the KernelSU GXR package contract."""
import hashlib
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
for name, identity in (
    ('questlhsync', 'questlhsync_gxr'),
    ('framebuffer10', 'gxr_framebuffer10'),
    ('mvhevc-eye-fix', 'gxr_mvhevc_eye_fix'),
):
    path = ROOT / f'releases/gxr-{name}-azj2-0.1.0-disabled.zip'
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        assert len(names) == len(archive.namelist())
        assert archive.testzip() is None
        assert archive.read('disable') == archive.read('skip_mount') == b''
        assert 'id=' + identity in archive.read('module.prop').decode().splitlines()
        assert 'booinspace' in archive.read('module.prop').decode()
        assert {'action.sh', 'auto.sh', 'service.sh', 'uninstall.sh', 'README.md',
                'restart-prepare.sh', 'restart-stopped.sh', 'restart-started.sh', 'restart-abort.sh'} <= names
        assert 'customize.sh' not in names
        assert not any(n.endswith(('.so', '.apk')) or 'device_profile' in n for n in names)
        for entry in names:
            p = PurePosixPath(entry)
            assert not p.is_absolute() and '..' not in p.parts and len(p.parts) < 8, entry
            if entry.endswith('.sh'):
                assert (archive.getinfo(entry).external_attr >> 16) & 0o111, entry
        manifest = dict((n, h) for h, n in (line.split('  ', 1) for line in archive.read('SHA256SUMS').decode().splitlines()))
        assert set(manifest) == names - {'disable', 'SHA256SUMS'}
        for entry, expected in manifest.items():
            assert hashlib.sha256(archive.read(entry)).hexdigest() == expected, entry
        if name == 'framebuffer10':
            native = archive.read('bin/gxr-fb10-gate')
            assert native[:6] == b'\x7fELF\x02\x01' and native[18:20] == b'\xb7\x00'
            assert b'I610UES3AZJ2' in native
            assert (archive.getinfo('bin/gxr-fb10-gate').external_attr >> 16) & 0o111
    expected = path.with_suffix('.zip.sha256').read_text().split()[0]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    print('PASS:', path.name, 'disabled, firmware-specific, complete lifecycle, verified manifest, no firmware libraries')

path = ROOT / 'releases/gxr-vd-eye-fix-0.1.0-windows.zip'
with ZipFile(path) as archive:
    assert set(archive.namelist()) == {'VirtualDesktop.FaceTracking.dll', 'module.json', 'LICENSE', 'README.md', 'UPSTREAM.json', 'SHA256SUMS'}
    assert archive.read('VirtualDesktop.FaceTracking.dll')[:2] == b'MZ'
    expected, name = archive.read('SHA256SUMS').decode().strip().split('  ', 1)
    assert hashlib.sha256(archive.read(name)).hexdigest() == expected
assert hashlib.sha256(path.read_bytes()).hexdigest() == path.with_suffix('.zip.sha256').read_text().split()[0]
print('PASS:', path.name, 'Windows DLL only; no Core reference dependency included')
