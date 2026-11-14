"""Check release-only catalogue selection and download integrity."""
from pathlib import Path
import runpy
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from gxr_build import package, sha256

build = runpy.run_path(str(ROOT / 'scripts/update-module-catalogue.py'))['build_catalogue']


class CatalogueTest(unittest.TestCase):
    def fixture(self, code=1, identity='gxr_fixture'):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'module.zip'
            payload = {name: b'#!/system/bin/sh\nexit 0\n' for name in ('auto.sh', 'action.sh', 'service.sh')}
            payload['module.prop'] = f'id={identity}\nname=Fixture\nauthor=Creator\nversion=0.{code}\nversionCode={code}\n'.encode()
            package(path, payload)
            blob = path.read_bytes()
        asset = {'name': 'gxr-fixture.zip', 'size': len(blob), 'digest': 'sha256:' + sha256(blob),
                 'browser_download_url': 'https://github.com/booinspace/galaxyxr-modules/releases/download/test/gxr-fixture.zip'}
        return {'draft': False, 'prerelease': True, 'assets': [asset]}, blob

    def test_published_prerelease_has_explicit_identity_hash_and_label(self):
        release, blob = self.fixture()
        catalogue, feeds = build([release], lambda _: blob)
        item, = catalogue['modules']
        self.assertEqual('gxr_fixture', item['id'])
        self.assertTrue(item['experimental'])
        self.assertEqual('Creator', item['author'])
        self.assertEqual(sha256(blob), feeds[item['id']]['sha256'])

    def test_reject_draft_corruption_missing_hash_and_foreign_url(self):
        for case in ('draft', 'corrupt', 'missing-hash', 'url'):
            release, blob = self.fixture()
            if case == 'draft': release['draft'] = True
            if case == 'corrupt': blob += b'changed'
            if case == 'missing-hash': release['assets'][0]['digest'] = ''
            if case == 'url': release['assets'][0]['browser_download_url'] = 'https://other.test/module.zip'
            with self.subTest(case=case), self.assertRaises(ValueError):
                build([release], lambda _: blob)

    def test_highest_version_wins_and_conflicting_same_version_is_rejected(self):
        older, first = self.fixture()
        newer, second = self.fixture(2)
        older['assets'][0]['name'] = 'gxr-old.zip'
        _, feeds = build([older, newer], lambda a: first if a['name'] == 'gxr-old.zip' else second)
        self.assertEqual(2, feeds['gxr_fixture']['versionCode'])
        newer['assets'][0]['digest'] = 'sha256:' + sha256(first + b'different')
        newer['assets'][0]['size'] = len(first + b'different')
        # A valid ZIP can carry trailing bytes, so version identity must still reject this.
        with self.assertRaisesRegex(ValueError, 'Different payloads'):
            build([older, newer], lambda a: first if a['name'] == 'gxr-old.zip' else first + b'different')

    def test_pc_companion_and_removed_rotation_are_not_offered(self):
        release, blob = self.fixture(identity='gxr_window_rotation')
        release['assets'].append({'name': 'gxr-vd-eye-fix-0.1.0-windows.zip'})
        with self.assertRaisesRegex(ValueError, 'No installable'):
            build([release], lambda _: blob)


if __name__ == '__main__':
    unittest.main()
