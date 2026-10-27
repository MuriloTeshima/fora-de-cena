import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.opencv_artifact import ROOT, digest, validate_artifact, inspect_runtime, used_symbols


class OpenCVArtifactTests(unittest.TestCase):
    def test_symbol_inventory_reads_utf8_sources_on_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'teleport_cam').mkdir()
            (root / 'teleport_cam' / 'example.py').write_text(
                '# Áreas visíveis da câmera\nimport cv2\ncv2.resize(None, (1, 1))\n',
                encoding='utf-8')
            self.assertEqual(used_symbols(root), ['resize'])

    def test_same_version_wrong_wheel_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as folder:
            wheel=Path(folder)/"selected.whl"
            wheel.write_bytes(b"different build with the same version")
            provenance=Path(folder)/"provenance.json"
            provenance.write_text(json.dumps({"custom_build":True,"distribution_ready":False,
                "wheel":{"filename":wheel.name,"sha256":"0"*64}}))
            with self.assertRaisesRegex(ValueError,"differs from provenance"):
                validate_artifact(wheel,provenance)

    def test_parallel_cv2_providers_are_rejected(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            wheel=Path(folder)/"selected.whl"; wheel.write_bytes(b"selected")
            provenance=Path(folder)/"provenance.json"
            provenance.write_text(json.dumps({"custom_build":True,"distribution_ready":False,
                "wheel":{"filename":wheel.name,"sha256":digest(wheel)},
                "profile_sha256":digest(ROOT/"packaging/opencv-minimal-profile.json"),
                "source_patch_sha256":digest(ROOT/"packaging/opencv-minimal-source.patch"),
                "source":json.loads((ROOT/"packaging/opencv-minimal-profile.json").read_text())["source_distribution"]}))
            providers=[SimpleNamespace(metadata={"Name":name}) for name in
                       ("opencv-contrib-python","opencv-python-headless")]
            with patch("tools.opencv_artifact.metadata.distributions",return_value=providers):
                with self.assertRaisesRegex(ValueError,"exactly one cv2 provider"):
                    validate_artifact(wheel,provenance)

    def test_real_codec_roundtrip_without_camera(self):
        import cv2
        import numpy as np
        image=np.zeros((48,64,3),dtype=np.uint8); image[:]=[30,90,180]
        ok,encoded=cv2.imencode(".jpg",image)
        self.assertTrue(ok)
        decoded=cv2.imdecode(encoded,cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape,image.shape)
        self.assertLess(float(np.abs(decoded.astype(float)-image).mean()),3)

    def test_custom_runtime_when_requested(self):
        import os
        if not os.environ.get("FDC_TEST_MINIMAL_OPENCV"):
            self.skipTest("Only required for the explicit custom OpenCV candidate")
        import cv2
        report=inspect_runtime(cv2)
        self.assertTrue(report["avfoundation"])
        self.assertFalse(report["camera_opened"])
        self.assertFalse(hasattr(cv2,"imshow"))


class CompliancePackageTests(unittest.TestCase):
    def test_build_signature_has_portable_case_sensitive_path_order(self):
        import hashlib
        from tools.distribution_licenses import runtime_signature
        files = {
            'teleport_cam/example.py': b'pass\r\n',
            'main.py': b'entry\n',
            'camera_output/main.py': b'worker\n',
            'camera_output/worker.spec': b'worker recipe\n',
            'packaging/fora_de_cena.spec': b'app recipe\n',
            'requirements.lock.txt': b'locked\n',
            'packaging/notices/opencv-minimal/OpenCV.txt': b'notice A\r\n',
            'packaging/notices/opencv-minimal/libpng.txt': b'notice B\n',
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, content in files.items():
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            expected = hashlib.sha256()
            for name in sorted(files):
                expected.update(name.encode('utf-8'))
                expected.update(files[name].replace(b'\r\n', b'\n'))
            self.assertEqual(runtime_signature(root), expected.hexdigest())

    def test_independent_helper_source_package_can_be_created_without_app_build_inputs(self):
        import zipfile
        from tools.distribution_licenses import package_compliance
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);notices=base/"notices";notices.mkdir()
            (notices/"NOTICE.txt").write_text("test notice")
            with patch("tools.distribution_licenses.upstream_files",return_value=[]):
                sources,licenses=package_compliance(base/"output","test",notices)
            with zipfile.ZipFile(sources) as archive:
                self.assertIn("camera_output/main.py",archive.namelist())
                self.assertIn("camera_output/LICENSE",archive.namelist())
                self.assertNotIn("camera_output/requirements-opencv-build.txt",archive.namelist())
                self.assertIsNone(archive.testzip())
            with zipfile.ZipFile(licenses) as archive:
                self.assertIn("video-output/GPL-2.0.txt",archive.namelist())
