"""Read-only packaged resources and per-user writable state."""
from __future__ import annotations
import os
from pathlib import Path
import sys


def resource_root() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


def data_root() -> Path:
    # Preserve the existing development installation and its extension pairing.
    if not getattr(sys, 'frozen', False):
        return Path(__file__).resolve().parents[1]
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'ForaDeCena'
    if sys.platform.startswith('linux'):
        configured = Path(os.environ.get('XDG_DATA_HOME', ''))
        base = configured if configured.is_absolute() else Path.home() / '.local' / 'share'
        return base / 'fora-de-cena'
    local = os.environ.get('LOCALAPPDATA')
    return (Path(local) if local else Path.home() / 'AppData' / 'Local') / 'ForaDeCena'


def data_file(name: str) -> Path:
    folder = data_root()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder / name


def extension_folder() -> Path:
    """Export only on request; Chrome must never depend on onefile's temp folder."""
    source = resource_root() / 'meet_extension'
    if not getattr(sys, 'frozen', False):
        return source
    from . import __version__
    destination = data_root() / 'extensions' / __version__ / 'meet_extension'
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('manifest.json', 'package.json', 'background.js', 'heartbeat.js',
                 'protocol.js', 'popup.js', 'popup.html', 'popup.css'):
        target = destination / name
        content = (source / name).read_bytes()
        if target.is_file() and target.read_bytes() == content:
            continue
        temporary = target.with_suffix(target.suffix + '.tmp')
        temporary.write_bytes(content)
        temporary.replace(target)
    return destination
