from pathlib import Path
import plistlib
import struct
import tempfile
import unittest
from importlib.util import find_spec

from tools.macos_bundle import inspect_macho, minimum_macos, audit_bundle


@unittest.skipUnless(find_spec('macholib'), 'Mach-O audit dependency is macOS-specific')
class MacBundleTests(unittest.TestCase):
    def fixture(self, path, minimum=(15, 0, 0), cpu=0x0100000C):
        encoded = (minimum[0] << 16) | (minimum[1] << 8) | minimum[2]
        header = struct.pack('<IiiIIIII', 0xFEEDFACF, cpu, 0, 6, 1, 24, 0, 0)
        command = struct.pack('<IIIIII', 0x32, 24, 1, encoded, encoded, 0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(header + command)
        return path

    def test_actual_library_target_overrides_the_proposed_macos_13(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            a = self.fixture(base / 'Python', (15, 0, 0))
            b = self.fixture(base / 'mediapipe.dylib', (14, 0, 0))
            self.assertEqual(minimum_macos([a, b]), '15.0')
            self.assertEqual(inspect_macho(b)['minimum'], (14, 0, 0))

    def test_intel_only_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.fixture(Path(folder) / 'intel.dylib', cpu=0x01000007)
            with self.assertRaisesRegex(ValueError, 'ARM64'):
                inspect_macho(path)

    def test_intel_audit_requires_intel_in_every_library(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            intel = self.fixture(root / 'intel.dylib', cpu=0x01000007)
            arm = self.fixture(root / 'arm.dylib')
            self.assertEqual(inspect_macho(intel, 'x86_64')['minimum'], (15, 0, 0))
            self.assertEqual(minimum_macos([intel], 'x86_64'), '15.0')
            with self.assertRaisesRegex(ValueError, 'X86_64'):
                minimum_macos([intel, arm], 'x86_64')

    def test_bundle_with_false_minimum_or_missing_camera_notice_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            self.fixture(base / 'Contents/Frameworks/Python')
            path = base / 'Contents/Info.plist'
            path.write_bytes(plistlib.dumps({'LSMinimumSystemVersion': '13.0',
                                            'NSCameraUsageDescription': 'Local effects'}))
            with self.assertRaisesRegex(ValueError, 'inferior'):
                audit_bundle(base)
            path.write_bytes(plistlib.dumps({'LSMinimumSystemVersion': '15.0'}))
            with self.assertRaisesRegex(ValueError, 'NSCameraUsageDescription'):
                audit_bundle(base)
            path.write_bytes(plistlib.dumps({'LSMinimumSystemVersion': '15.0',
                                            'NSCameraUsageDescription': 'Local effects'}))
            self.assertEqual(audit_bundle(base)['minimum_macos'], '15.0')

    def test_absolute_build_rpath_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            path=self.fixture(base/'Contents/Frameworks/native.so')
            raw=path.read_bytes()
            value=b'/opt/build-machine/lib\x00'
            size=(12+len(value)+7)//8*8
            command=struct.pack('<III',0x8000001c,size,12)+value
            command+=b'\x00'*(size-len(command))
            header=bytearray(raw[:32])
            struct.pack_into('<II',header,16,2,24+size)
            path.write_bytes(header+raw[32:]+command)
            (base/'Contents/Info.plist').write_bytes(plistlib.dumps({
                'LSMinimumSystemVersion':'15.0','NSCameraUsageDescription':'Effects'}))
            self.assertEqual(inspect_macho(path)['rpaths'],['/opt/build-machine/lib'])
            with self.assertRaisesRegex(ValueError,'RPATH externo'):
                audit_bundle(base)

    def test_non_native_assets_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'asset.txt'
            p.write_text('resource')
            self.assertIsNone(inspect_macho(p))
