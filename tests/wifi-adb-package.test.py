"""Check the unmodified upstream Wi-Fi ADB package against GXR's installer rules."""
import hashlib
from pathlib import Path
import runpy
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class WifiAdbPackageTest(unittest.TestCase):
    def test_original_identity_and_complete_manifest(self):
        path = ROOT / 'releases/gxr-wifi-adb-azj2-1.0.2-disabled.zip'
        forbidden = runpy.run_path(str(ROOT / 'scripts/port-package.py'))['FORBIDDEN']
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            self.assertEqual(len(names), len(archive.namelist()))
            self.assertIsNone(archive.testzip())
            self.assertFalse(forbidden.intersection(names))
            self.assertEqual(archive.read('disable'), b'')
            self.assertEqual(archive.read('skip_mount'), b'')
            props = archive.read('module.prop').decode().splitlines()
            self.assertIn('id=gxr_wifi_adb', props)
            self.assertIn('author=4uva4ek', props)
            self.assertIn('version=1.0.2', props)
            for name in names:
                if name.endswith('.sh'):
                    self.assertTrue((archive.getinfo(name).external_attr >> 16) & 0o111, name)
            sums = dict((name, digest) for digest, name in
                        (line.split('  ', 1) for line in archive.read('SHA256SUMS').decode().splitlines()))
            self.assertEqual(set(sums), names - {'disable', 'SHA256SUMS'})
            for name, digest in sums.items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest, name)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         path.with_suffix('.zip.sha256').read_text().split()[0])


if __name__ == '__main__':
    unittest.main()
