"""Check firmware identity gates and GXR lifecycle packaging of Lighthouse."""
import hashlib
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'releases/gxr-questlhsync-azj2-0.1.1-disabled.zip'
with ZipFile(p) as z:
    names=z.namelist()
    assert len(names)==len(set(names))
    assert z.read('disable')==z.read('skip_mount')==b''
    assert 'id=gxr_questlhsync' in z.read('module.prop').decode().splitlines()
    assert b'/data/adb/modules/gxr_questlhsync/settings.sh ' in z.read('webroot/app.js')
    assert b'"$MODDIR/bin/lhsyncd" "$MODDIR/bin"' in z.read('run.sh')
    for binary in ('gxr-head-origin','gxr-prepare'):
        assert ('"$MODDIR/bin/'+binary+'"').encode() in z.read('prepare.sh')
    assert b'I610UES3AZJ2' in z.read('guard.sh') and b'I610UEU2AZF3' not in z.read('guard.sh')
    for phase in ('prepare','stopped','started','abort'): assert 'restart-'+phase+'.sh' in names
    for binary in ('lhsyncd','gxr-lhsight','gxr-prepare','gxr-head-origin'):
        assert binary not in names
        assert z.read('bin/'+binary)[:6]==b'\x7fELF\x02\x01'
        assert (z.getinfo('bin/'+binary).external_attr>>16)&0o111
    assert all(len(Path(n).parts)<8 for n in names)
    manifest=z.read('SHA256SUMS').decode().splitlines()
    assert len(manifest)+2==len(names)
    for line in manifest:
        expected,name=line.split('  ',1)
        assert hashlib.sha256(z.read(name)).hexdigest()==expected,name
    assert not any(n.endswith('.so') or 'device_profile' in n for n in names)
print('PASS: Lighthouse ZIP, firmware gate, native architecture, lifecycle hooks and no firmware payloads')
