"""Exercise the media controller with synthetic libraries and owned hard-link mounts."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
PINS={'SF_HASH':'8db37c90c458e92faad1f0a6160d53e769da9759c6db14fb2cfedbcec1727490',
      'AP_HASH':'a1d055498e9bc9b09850748944f0605c7fd9052eec2050f027fa4724b449b047',
      'SF_PATCHED':'4e51540d13f50d94f6c8deabae1137158af826cff29c56cd30ce4963a9ef1973',
      'AP_PATCHED':'017dc755311dfc9ff42d2501d4daa4c33ce92ec7d1d543c333a80c6f62d18ddd'}


class MediaRuntimeTest(unittest.TestCase):
    def test_generation_transactional_rollback_and_unrelated_mount(self):
        with tempfile.TemporaryDirectory(prefix='gxr-media-test-') as directory:
            root=Path(directory); module=root/'module';module.mkdir();tools=root/'tools';tools.mkdir()
            sf=root/'stage.so';ap=root/'player.so';mountinfo=root/'mountinfo';mountinfo.write_text('')
            blobs=[bytearray(1817400),bytearray(2309700)]
            originals=[bytes(b) for b in blobs]
            blobs[0][1817377]=0x15;blobs[1][2309657]=0x15;blobs[1][1005196:1005200]=bytes.fromhex('23008052')
            for path,data in zip((sf,ap),originals):path.write_bytes(data)
            fake_pins=[hashlib.sha256(b).hexdigest() for b in [*originals,*blobs]]
            source=(ROOT/'modules/mvhevc-eye-fix/control.sh').read_text()
            for old,new in zip(PINS.values(),fake_pins):source=source.replace(old,new)
            source=source.replace('/system/lib64/libstagefright.so',str(sf)).replace('/system/lib64/libaplayer.so',str(ap))
            source=source.replace('/dev/gxr-mvhevc-azj2',str(root/'runtime')).replace('/proc/self/mountinfo',str(mountinfo))
            control=module/'control.sh';control.write_text(source)
            (module/'SHA256SUMS').write_text(hashlib.sha256(control.read_bytes()).hexdigest()+'  control.sh\n')
            scripts={'id':'echo 0','readlink':'echo global-namespace','chown':'exit 0','chcon':'exit 0','am':'exit 0',
                     'getprop':'''case "$1" in
ro.build.fingerprint) echo samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys ;;
sys.boot_completed) echo 1 ;;
esac''',
                     'mount':'''[ "${FAIL_AP:-0}" != 1 ] || [ "$4" != "$AP_TEST" ] || exit 9
cp "$4" "$4.stock"
rm "$4"
ln "$3" "$4"
printf 'x x x x %s x\\n' "$4" >> "$MOUNTINFO_TEST"
''',
                     'umount':'''target=$1
[ "$1" != -l ] || target=$2
printf '%s\\n' "$target" >> "$UNMOUNT_TEST"
rm "$target"
mv "$target.stock" "$target"
grep -v " $target " "$MOUNTINFO_TEST" > "$MOUNTINFO_TEST.new" || true
mv "$MOUNTINFO_TEST.new" "$MOUNTINFO_TEST"
'''}
            for name,body in scripts.items():
                path=tools/name;path.write_text('#!/bin/sh\nset -e\n'+body+'\n');path.chmod(0o755)
            env={**os.environ,'PATH':str(tools)+':'+os.environ['PATH'],'AP_TEST':str(ap),
                 'MOUNTINFO_TEST':str(mountinfo),'UNMOUNT_TEST':str(root/'unmounts')}
            def run(verb,ok=True,**extra):
                result=subprocess.run(['sh',str(control),verb],env={**env,**extra},capture_output=True,text=True,timeout=8)
                self.assertEqual(result.returncode==0,ok,result.stdout+result.stderr)
                return result.stdout
            self.assertIn('GXR_UPDATE_STATE=STOCK',run('status'))
            self.assertIn('ENABLED',run('on'))
            self.assertEqual(sf.read_bytes(),blobs[0]);self.assertEqual(ap.read_bytes(),blobs[1])
            self.assertIn('GXR_UPDATE_STATE=STOCK',run('off'))
            self.assertEqual(sf.read_bytes(),originals[0]);self.assertEqual(ap.read_bytes(),originals[1])
            (module/'disable').unlink()
            run('on',ok=False,FAIL_AP='1')
            self.assertEqual(sf.read_bytes(),originals[0]);self.assertEqual(ap.read_bytes(),originals[1])
            self.assertIn('GXR_UPDATE_STATE=STOCK',run('status'))
            (module/'disable').unlink()
            foreign=root/'foreign.so';foreign.write_bytes(originals[0])
            sf.unlink();os.link(foreign,sf);mountinfo.write_text('x x x x '+str(sf)+' x\n')
            previous=(root/'unmounts').read_text()
            run('on',ok=False)
            self.assertTrue(os.path.samestat(foreign.stat(),sf.stat()))
            self.assertEqual((root/'unmounts').read_text(),previous,'foreign mount must never be detached')
            time.sleep(1.2)


if __name__=='__main__':unittest.main()
