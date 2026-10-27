from io import BytesIO
from pathlib import Path
import tempfile
import unittest
import zipfile

from teleport_cam.tk_resources import verify_tk_data


class PackagedTkTests(unittest.TestCase):
    def test_external_scripts_are_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '_tk_data').mkdir()
            (root / '_tk_data/tk.tcl').write_text('# Tk resource')
            self.assertEqual(verify_tk_data(root), 'external-scripts')

    def test_embedded_tk9_scripts_do_not_require_a_fake_external_directory(self):
        for name in ('tcl9tk90.dll', 'libtcl9tk9.0.dylib', 'libtcl9tk9.0.so'):
            with self.subTest(library=name), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                payload = BytesIO()
                with zipfile.ZipFile(payload, 'w') as archive:
                    archive.writestr('tk_library/tk.tcl', '# Tk resource')
                (root / name).write_bytes(b'fixture native prefix' + payload.getvalue())
                self.assertEqual(verify_tk_data(root), 'embedded-library-zip')
                self.assertFalse((root / '_tk_data').exists())

    def test_framework_scripts_are_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / 'Tk.framework/Versions/9.1/Resources/Scripts/tk.tcl'
            script.parent.mkdir(parents=True)
            script.write_text('# Tk resource')
            self.assertEqual(verify_tk_data(root), 'framework-scripts')

    def test_missing_tk_scripts_or_an_unrelated_zip_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with zipfile.ZipFile(root / 'unrelated.zip', 'w') as archive:
                archive.writestr('tk_library/tk.tcl', '# unrelated')
            with zipfile.ZipFile(root / 'tcl9tk90.dll', 'w') as archive:
                archive.writestr('other-file.txt', '# no Tk resource')
            with self.assertRaises(FileNotFoundError):
                verify_tk_data(root)

    def test_macos_bundle_scripts_symlinked_into_resources_are_supported(self):
        # In a .app, PyInstaller stores the scripts under Contents/Resources and
        # links them into Contents/Frameworks (the _MEIPASS dir passed in here).
        with tempfile.TemporaryDirectory() as folder:
            contents = Path(folder) / 'Contents'
            frameworks = contents / 'Frameworks'
            resources = contents / 'Resources' / '_tk_data'
            frameworks.mkdir(parents=True)
            resources.mkdir(parents=True)
            (resources / 'tk.tcl').write_text('# Tk resource')
            (frameworks / '_tk_data').symlink_to(Path('..') / 'Resources' / '_tk_data')
            self.assertEqual(verify_tk_data(frameworks), 'external-scripts')

    def test_symlink_escaping_the_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as folder:
            external = Path(outside) / '_tk_data'
            external.mkdir()
            (external / 'tk.tcl').write_text('# outside the bundle')
            frameworks = Path(folder) / 'Contents' / 'Frameworks'
            frameworks.mkdir(parents=True)
            (frameworks / '_tk_data').symlink_to(external)
            with self.assertRaises(FileNotFoundError):
                verify_tk_data(frameworks)
