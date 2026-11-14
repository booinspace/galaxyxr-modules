"""Reject package IDs that bypass KernelSU GXR's direct installer."""
import hashlib
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
api = runpy.run_path(str(ROOT / 'scripts/port-package.py'))
package = api['package']


class PortPackageTest(unittest.TestCase):
    def test_reject_unsupported_installer_entries(self):
        payload = {name: b'exit 0\n' for name in ('action.sh', 'auto.sh', 'service.sh')}
        payload['module.prop'] = b'id=gxr_fixture\nversionCode=1\n'
        invalid = list(api['FORBIDDEN']) + ['system/file', 'a/../file', 'bin/back\\slash',
                    'bin/sp ace', 'bin/é', './file', '.']
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'rejected.zip'
            for name in invalid:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    package(output, {**payload, name: b'forbidden'})
                self.assertFalse(output.exists())

    def test_gxr_install_route_and_payload(self):
        payload = {name: b'#!/system/bin/sh\nexit 0\n'
                   for name in ('action.sh', 'auto.sh', 'service.sh')}
        payload.update({'module.prop': b'id=gxr_fixture\nversionCode=1\n',
                        'README.md': b'Installation guide\n', 'bin/helper': b'native fixture'})
        with tempfile.TemporaryDirectory(prefix='gxr-port-package-test-') as directory:
            output = Path(directory) / 'module.zip'
            for identity in ('questlhsync_gxr', 'gxr_', 'gxr_unsafe/path'):
                with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, 'GXR package ID'):
                    package(output, {**payload, 'module.prop': ('id=' + identity + '\n').encode()})
                self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError, 'under bin/'):
                package(output, {**payload, 'native-helper': b'fixture'}, executables=('native-helper',))
            self.assertFalse(output.exists())
            package(output, payload, executables=('bin/helper',))
            with ZipFile(output) as archive:
                self.assertEqual(archive.read('README.md'), payload['README.md'])
                self.assertEqual((archive.getinfo('bin/helper').external_attr >> 16) & 0o777, 0o755)
                for line in archive.read('SHA256SUMS').decode().splitlines():
                    expected, name = line.split('  ', 1)
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
