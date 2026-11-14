"""Check the AZJ2 package and reject corrupted or incorrectly targeted binaries."""
import hashlib
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
BUILDER = runpy.run_path(str(ROOT / 'scripts/build-openxr-quality-azj2.py'))
PACKAGE = ROOT / 'releases/gxr-openxr-quality-azj2-0.1.2-disabled.zip'


class PackageTest(unittest.TestCase):
    def altered(self, target, firmware=False):
        with ZipFile(PACKAGE) as source:
            payload = {entry.filename: source.read(entry.filename) for entry in source.infolist()}
            if firmware:
                payload['bin/gxr-quality'] = payload['bin/gxr-quality'].replace(
                    BUILDER['SERVICES'].encode(), BUILDER['OLD_SERVICES'].encode())
                payload['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                    for name, data in sorted(payload.items()) if name not in ('disable', 'SHA256SUMS')).encode()
            else:
                payload['NOTICE.txt'] += b'changed'
            with ZipFile(target, 'w') as output:
                for entry in source.infolist():
                    output.writestr(entry, payload[entry.filename])

    def test_built_package(self):
        BUILDER['validate'](PACKAGE)

    def test_corrupted_payload_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'changed.zip'
            self.altered(target)
            with self.assertRaisesRegex(ValueError, 'Payload checksum mismatch'):
                BUILDER['validate'](target)

    def test_azf3_guard_rejected_even_with_valid_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'wrong-firmware.zip'
            self.altered(target, firmware=True)
            with self.assertRaisesRegex(ValueError, 'firmware guards'):
                BUILDER['validate'](target)


if __name__ == '__main__':
    unittest.main()
