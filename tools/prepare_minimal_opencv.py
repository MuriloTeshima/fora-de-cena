"""Prepare the exact reviewed OpenCV source under work/. Never install or publish."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD = 200 * 1024 * 1024
MAX_EXTRACTED = 1024 * 1024 * 1024


def extract_verified(archive: Path, destination: Path, expected: str, top_folder: str) -> Path:
    with archive.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        raise ValueError('OpenCV source SHA256 mismatch')
    if destination.exists():
        raise ValueError('Use a new, empty extraction destination')
    with tarfile.open(archive, 'r:gz') as package:
        members = package.getmembers()
        if sum(member.size for member in members) > MAX_EXTRACTED:
            raise ValueError('OpenCV source exceeds extraction limit')
        for member in members:
            # The source distribution does not need links or special devices.
            parts = Path(member.name.replace('\\', '/')).parts
            if (not parts or parts[0] != top_folder or '..' in parts
                    or not (member.isfile() or member.isdir())
                    or not (destination / member.name).resolve().is_relative_to(destination.resolve())):
                raise ValueError('Unsafe source archive member')
        destination.mkdir(parents=True)
        package.extractall(destination, members=members, filter='data')
    return destination / top_folder


def main() -> None:
    profile = json.loads((ROOT / 'packaging/opencv-minimal-profile.json').read_text(encoding='utf-8'))
    info = profile['source_distribution']
    work = ROOT / 'work/opencv-minimal'
    if (not (ROOT / 'work').resolve().is_relative_to(ROOT.resolve())
            or not work.resolve().is_relative_to((ROOT / 'work').resolve())):
        raise ValueError('Redirected source destination')
    work.mkdir(parents=True, exist_ok=True)
    (ROOT / 'work/test-temp').mkdir(parents=True, exist_ok=True)
    archive = work / info['filename']
    if not info['url'].startswith('https://files.pythonhosted.org/'):
        raise ValueError('Unexpected source host')
    # Refuse an old partial download rather than silently reusing it.
    with urllib.request.urlopen(info['url'], timeout=60) as response, archive.open('xb') as output:
        if not response.url.startswith('https://files.pythonhosted.org/'):
            raise ValueError('Unexpected source redirect')
        count = 0
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > MAX_DOWNLOAD:
                raise ValueError('Source download exceeds limit')
            output.write(chunk)
    source = extract_verified(archive, work / 'source', info['sha256'], info['filename'].removesuffix('.tar.gz'))
    directory = '--directory=' + source.relative_to(ROOT).as_posix()
    patch = str(ROOT / 'packaging/opencv-minimal-source.patch')
    subprocess.run(['git', 'apply', directory, '--check', patch], cwd=ROOT, check=True)
    subprocess.run(['git', 'apply', directory, patch], cwd=ROOT, check=True)
    print('Verified source and reviewed patch prepared under work/opencv-minimal/.')


if __name__ == '__main__':
    main()
