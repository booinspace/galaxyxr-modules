"""Check the GXR-specific startup contract missing from the upstream ZIP checker."""
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
check = runpy.run_path(str(ROOT / "scripts/build-window-curvature-azj2.py"))["check_gxr_installer_payload"]
forbidden = runpy.run_path(str(ROOT / "scripts/port-package.py"))["FORBIDDEN"]


class InstallerContractTest(unittest.TestCase):
    def test_service_and_coordinated_restart_hooks_are_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "module.zip"
            with ZipFile(path, "w") as archive:
                for name in ("service.sh", "action.sh", "auto.sh", "restart-started.sh",
                             "restart-prepare.sh", "restart-stopped.sh", "restart-abort.sh"):
                    archive.writestr(name, b"exit 0\n")
            check(path)

    def test_all_disallowed_startup_and_state_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in forbidden:
                with self.subTest(name=name):
                    path = Path(directory) / "rejected.zip"
                    with ZipFile(path, "w") as archive:
                        archive.writestr("service.sh", b"exit 0\n")
                        archive.writestr(name, b"")
                    with self.assertRaisesRegex(ValueError, "Unsupported GXR startup/state payload"):
                        check(path)


if __name__ == "__main__":
    unittest.main()
