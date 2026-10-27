"""Small desktop adapters; never install drivers or change system security settings."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
import sys


def output_choices() -> dict[str, str]:
    choices = {'Só prévia': 'off'}
    if sys.platform == 'win32':
        choices.update({'OBS Virtual Camera': 'obs', 'Unity Capture': 'unitycapture'})
    elif sys.platform == 'darwin':
        choices['OBS Virtual Camera'] = 'obs'
    elif sys.platform.startswith('linux'):
        choices['Câmera virtual Linux'] = 'v4l2loopback'
    return choices


def default_output_label() -> str:
    return next((label for label, backend in output_choices().items() if backend != 'off'), 'Só prévia')


def font_family() -> str:
    return {'win32': 'Segoe UI', 'darwin': 'Helvetica Neue'}.get(sys.platform, 'DejaVu Sans')


def valid_linux_video_device(value: str) -> bool:
    return re.fullmatch(r'/dev/video[0-9]{1,5}', value) is not None


def system_environment() -> dict[str, str]:
    """Restore the system loader search path before starting a system application."""
    environment = dict(os.environ)
    for name in ('LD_LIBRARY_PATH', 'LIBPATH'):
        original = environment.pop(name + '_ORIG', None)
        if original is None:
            environment.pop(name, None)
        else:
            environment[name] = original
    # Do not propagate Python/loader injection into the file manager or browser.
    for name in tuple(environment):
        if name in ('PYTHONHOME', 'PYTHONPATH') or name.startswith('DYLD_'):
            environment.pop(name)
    return environment


def open_local_path(path: Path) -> None:
    target = path.resolve(strict=True)
    if sys.platform == 'win32':
        os.startfile(str(target))
        return
    executable = Path('/usr/bin/open' if sys.platform == 'darwin' else '/usr/bin/xdg-open')
    if not executable.is_file():
        raise OSError('O sistema não disponibiliza um aplicativo para abrir esta pasta ou arquivo.')
    subprocess.Popen([str(executable), str(target)], env=system_environment(),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
