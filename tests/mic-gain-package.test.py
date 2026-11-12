"""Verify the GXR installer and live settings payload in the built mic ZIP."""
import hashlib
from pathlib import Path
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class MicGainPackageTest(unittest.TestCase):
    def test_installable_tree_and_settings_manifest(self):
        path = ROOT / "releases/gxr-mic-gain-boost-azj2-0.2.3-disabled.zip"
        with ZipFile(path) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(all(len(Path(name).parts) < 8 for name in names))
            self.assertEqual(archive.read("disable"), b"")
            self.assertEqual(archive.read("skip_mount"), b"")
            for name in ("settings.sh", "webroot/index.html", "webroot/settings.js", "webroot/style.css"):
                self.assertIn(name, names)
            self.assertIn(b"ksu://webui?id=gxr_mic_gain_azj2", archive.read("action.sh"))
            self.assertTrue(archive.read("bin/helper.dex").startswith(b"dex\n"))
            self.assertIn('bin/source/src/com/gxr/mic/MicTest.java', names)
            self.assertFalse(any('/recordings/' in name or name.endswith(('.wav', '.part')) for name in names))
            self.assertIn(b'media-src \'self\'', archive.read('webroot/index.html'))
            for button in (b'id="play-recording"', b'id="stop-playback"', b'id="test-status"'):
                self.assertIn(button, archive.read('webroot/index.html'))
            self.assertNotIn(b'<audio', archive.read('webroot/index.html'))
            manifest = archive.read("SHA256SUMS").decode().splitlines()
            self.assertEqual(len(manifest) + 2, len(names))
            for line in manifest:
                expected, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)


if __name__ == "__main__": unittest.main()
