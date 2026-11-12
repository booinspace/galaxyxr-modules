"""Check the built archive against GXR's installed-tree and restart contracts."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "releases/gxr-wear-dim-azj2-0.1.2-disabled.zip"


class WearDimPackageTest(unittest.TestCase):
    def test_installed_tree_and_manifest(self):
        with ZipFile(PACKAGE) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(all(len(Path(name).parts) < 8 for name in names))
            self.assertEqual(archive.read("disable"), b"")
            self.assertEqual(archive.read("skip_mount"), b"")
            manifest = archive.read("SHA256SUMS").decode().splitlines()
            self.assertEqual(len(manifest) + 2, len(names))
            for line in manifest:
                expected, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected)

    def test_coordinated_restart_is_complete_and_prepares_cleanup(self):
        with ZipFile(PACKAGE) as archive, tempfile.TemporaryDirectory() as directory:
            module = Path(directory)
            for phase in ("prepare", "stopped", "started", "abort"):
                name = f"restart-{phase}.sh"
                target = module / name
                target.write_bytes(archive.read(name))
                subprocess.run(["/bin/sh", "-n", str(target)], check=True)
                if phase != "prepare":
                    subprocess.run(["/bin/sh", str(target)], check=True)
            (module / "control.sh").write_text('#!/bin/sh\nprintf "%s" "$1"\n')
            result = subprocess.check_output(["/bin/sh", str(module / "restart-prepare.sh")], text=True)
            self.assertEqual(result, "prepare")
            (module / "control.sh").write_text('#!/bin/sh\nexit 9\n')
            result = subprocess.run(["/bin/sh", str(module / "restart-prepare.sh")])
            self.assertEqual(result.returncode, 9, 'restart must stop when cleanup fails')


if __name__ == "__main__":
    unittest.main()
