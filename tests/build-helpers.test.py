"""Exercise the shared build trust boundaries without Android or network access."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from gxr_build import export_source, package, replace_exact, validate_arm64, validate_package


class BuildHelpersTest(unittest.TestCase):
    def payload(self):
        return {'module.prop': b'id=gxr_fixture\nversionCode=1\n',
                **{name: b'#!/system/bin/sh\nexit 0\n' for name in ('action.sh', 'auto.sh', 'service.sh')},
                'bin/native': b'fixture'}

    def alter(self, path, change):
        with ZipFile(path) as source:
            entries = [(entry, source.read(entry.filename)) for entry in source.infolist()]
        with ZipFile(path, 'w') as target:
            change(target, entries)

    def test_deterministic_package_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'module.zip'
            package(path, self.payload(), executables=('bin/native',))
            original = path.read_bytes()
            package(path, dict(reversed(list(self.payload().items()))), executables=('bin/native',))
            self.assertEqual(original, path.read_bytes())
            self.assertEqual(path.with_suffix('.zip.sha256').read_text(),
                             f'{hashlib.sha256(original).hexdigest()}  module.zip\n')
            self.assertEqual(validate_package(path, ('bin/native',))['disable'], b'')

    def test_reject_altered_archive(self):
        for case in ('duplicate', 'checksum', 'manifest', 'missing-manifest', 'duplicate-manifest', 'script-mode', 'native-mode', 'symlink'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'module.zip'
                package(path, self.payload(), executables=('bin/native',))

                def change(target, entries):
                    for entry, data in entries:
                        if case == 'checksum' and entry.filename == 'bin/native':
                            data += b'changed'
                        if entry.filename == 'SHA256SUMS':
                            if case == 'missing-manifest':
                                continue
                            if case == 'manifest':
                                data = b''
                            if case == 'duplicate-manifest':
                                data += data.splitlines(keepends=True)[0]
                        if ((case == 'script-mode' and entry.filename == 'service.sh') or
                                (case == 'native-mode' and entry.filename == 'bin/native')):
                            entry.external_attr = 0o100644 << 16
                        if case == 'symlink' and entry.filename == 'bin/native':
                            entry.external_attr = 0o120777 << 16
                        target.writestr(entry, data)
                    if case == 'duplicate':
                        target.writestr(entries[0][0], entries[0][1])

                if case == 'duplicate':
                    with self.assertWarns(UserWarning):
                        self.alter(path, change)
                else:
                    self.alter(path, change)
                with self.assertRaises(ValueError):
                    validate_package(path, ('bin/native',))

    def test_partial_restart_hooks_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'module.zip'
            with self.assertRaisesRegex(ValueError, 'Incomplete GXR'):
                package(path, {**self.payload(), 'restart-prepare.sh': b'exit 0\n'})
            self.assertFalse(path.exists())

    def test_exact_patch_does_not_modify_ambiguous_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            for text in ('missing', 'anchor anchor'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    replace_exact(path, 'anchor', 'replacement')
                self.assertEqual(path.read_text(), text)
            path.write_text('one anchor')
            replace_exact(path, 'anchor', 'replacement')
            self.assertEqual(path.read_text(), 'one replacement')

    def test_export_uses_pinned_objects_and_ignores_local_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / 'repo'
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (repo / 'source').write_text('committed')
            subprocess.run(['git', '-C', str(repo), 'add', 'source'], check=True)
            subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture'], check=True)
            commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            (repo / 'source').write_text('local edit')
            (repo / 'untracked').write_text('must not ship')
            export_source(root / 'export', 'unused', commit, checkout=repo)
            self.assertEqual((root / 'export/source').read_text(), 'committed')
            self.assertFalse((root / 'export/untracked').exists())

    def test_non_arm64_and_truncated_elf_rejected(self):
        for blob in (b'', b'\x7fELF', b'\x7fELF\x01\x01' + bytes(64)):
            with self.subTest(blob=blob), self.assertRaises(ValueError):
                validate_arm64(blob)


if __name__ == '__main__':
    unittest.main()
