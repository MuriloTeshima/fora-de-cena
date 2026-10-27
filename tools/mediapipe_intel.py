"""Construct and validate an explicitly selected, experimental Intel MediaPipe wheel."""
from __future__ import annotations

import base64
import csv
import hashlib
from importlib import metadata
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'packaging/mediapipe-intel-profile.json'


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_profile() -> dict:
    profile = json.loads(PROFILE.read_text(encoding='utf-8'))
    if profile['distribution_ready'] or profile['architecture'] != 'x86_64':
        raise ValueError('Expected experimental Intel profile')
    return profile


def make_wheel(template: Path, native: Path, destination: Path, profile: dict) -> Path:
    """Retain upstream Python/license files; never retain any ARM native member."""
    if digest(template) != profile['python_template']['sha256']:
        raise ValueError('Unverified upstream Python template')
    from tools.macos_bundle import inspect_macho
    record = inspect_macho(native, 'x86_64')
    if record is None:
        raise ValueError('Expected a native Intel Mach-O library')
    if record['minimum'] > (15, 0, 0):
        raise ValueError('Native library requires a newer macOS than the wheel tag')
    data = native.read_bytes()
    if b'/Users/' in data or b'C:\\Users\\' in data:
        raise ValueError('Private build paths embedded in native library')
    with zipfile.ZipFile(template) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError('Duplicate upstream wheel entries')
        if any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names):
            raise ValueError('Unsafe wheel member')
        native_names = [n for n in names if n.endswith(('.dylib', '.so', '.pyd', '.dll', '.a'))]
        if native_names != [profile['native_member']]:
            raise ValueError('Unexpected native members in Python template')
        files = {n: archive.read(n) for n in names if not n.endswith('/')}
    info = f"mediapipe-{profile['version']}.dist-info"
    record_name = info + '/RECORD'
    if not any(n.startswith(info + '/') and ('LICENSE' in n or 'NOTICE' in n) for n in files):
        raise ValueError('Upstream license/notice missing')
    files[profile['native_member']] = data
    files[info + '/WHEEL'] = (b'Wheel-Version: 1.0\nGenerator: fora-de-cena-experimental-intel\n'
                              b'Root-Is-Purelib: false\nBuild: 1fdcintel\n'
                              b'Tag: py3-none-macosx_15_0_x86_64\n')
    files[info + '/FDC-CUSTOM-BUILD.json'] = json.dumps({
        'experimental': True, 'distribution_ready': False, 'official_intel_wheel': False,
        'source_commit': profile['source_commit'], 'native_architecture': 'x86_64',
        'native_sha256': digest(native), 'python_template_sha256': digest(template),
    }, indent=2).encode('utf-8')
    files.pop(record_name, None)
    rows = []
    for name, content in sorted(files.items()):
        checksum = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode('ascii')
        rows.append((name, 'sha256=' + checksum, str(len(content))))
    rows.append((record_name, '', ''))
    buffer = io.StringIO(newline='')
    csv.writer(buffer, lineterminator='\n').writerows(rows)
    files[record_name] = buffer.getvalue().encode('utf-8')
    destination.mkdir(parents=True, exist_ok=True)
    wheel = destination / profile['wheel_filename']
    if wheel.exists():
        raise ValueError('Refusing to overwrite an existing custom wheel')
    with zipfile.ZipFile(wheel, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, content)
    return wheel


def validate_artifact(wheel: Path, provenance: Path) -> dict:
    """Bind build inputs, selected wheel and installed native bytes before packaging."""
    profile = load_profile()
    record = json.loads(provenance.read_text(encoding='utf-8'))
    if (not record.get('custom_build') or record.get('distribution_ready') is not False
            or record.get('architecture') != 'x86_64'
            or record.get('profile_sha256') != digest(PROFILE)
            or record.get('source_commit') != profile['source_commit']
            or record.get('source_patch_sha256') != profile['source_patch_sha256']
            or record.get('source_patch_sha256') != digest(ROOT / 'packaging/mediapipe-intel-source.patch')
            or record.get('bazel_sha256') != profile['bazel']['sha256']
            or record.get('build_driver_sha256') != digest(ROOT / 'tools/build_mediapipe_intel.py')
            or record.get('python_template_sha256') != profile['python_template']['sha256']):
        raise ValueError('Intel MediaPipe provenance differs from reviewed profile')
    checksum = digest(wheel)
    if (wheel.name != profile['wheel_filename'] or record.get('wheel', {}).get('sha256') != checksum
            or record.get('wheel', {}).get('filename') != wheel.name):
        raise ValueError('Intel MediaPipe wheel differs from provenance')
    distribution = metadata.distribution('mediapipe')
    direct = json.loads(distribution.read_text('direct_url.json') or '{}')
    if (distribution.version != profile['version'] or
            direct.get('archive_info', {}).get('hashes', {}).get('sha256') != checksum):
        raise ValueError('Install the explicitly selected Intel wheel before packaging')
    installed = Path(distribution.locate_file(profile['native_member']))
    if record.get('native_sha256') != digest(installed):
        raise ValueError('Installed Intel native library differs from provenance')
    with zipfile.ZipFile(wheel) as archive:
        if hashlib.sha256(archive.read(profile['native_member'])).hexdigest() != digest(installed):
            raise ValueError('Installed native MediaPipe differs from selected wheel')
    from tools.macos_bundle import inspect_macho
    if inspect_macho(installed, 'x86_64') is None:
        raise ValueError('Installed MediaPipe has no Intel Mach-O library')
    return record
