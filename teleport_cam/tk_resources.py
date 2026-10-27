"""Validate packaged Tk scripts, including Tcl/Tk 9 DLL-embedded ZIP resources."""
from pathlib import Path
import re
import zipfile


def _containment_root(base: Path) -> Path:
    # A macOS .app keeps the real Tk data under Contents/Resources and symlinks it
    # into Contents/Frameworks (the _MEIPASS dir). Allow resolved targets to stay
    # anywhere inside the surrounding Contents tree, but never escape the bundle.
    if base.name == 'Frameworks' and base.parent.name == 'Contents':
        return base.parent
    return base


def verify_tk_data(root: Path) -> str:
    base = root.resolve()
    boundary = _containment_root(base)
    script = base / '_tk_data/tk.tcl'
    if script.is_file() and script.resolve().is_relative_to(boundary):
        return 'external-scripts'
    for path in base.rglob('tk.tcl'):
        if ('Tk.framework' in path.parts and path.resolve().is_relative_to(boundary)
                and path.is_file()):
            return 'framework-scripts'
    native_name = re.compile(r'^(?:lib)?(?:tcl\d+tk|tk)[0-9.a-z_-]*\.(?:dll|dylib|so(?:\.\d+)*)$')
    for path in base.rglob('*'):
        if not path.is_file() or not (native_name.fullmatch(path.name.lower()) or path.name == 'Tk'):
            continue
        if not path.resolve().is_relative_to(boundary) or not zipfile.is_zipfile(path):
            continue
        with zipfile.ZipFile(path) as archive:
            if 'tk_library/tk.tcl' in archive.namelist():
                archive.read('tk_library/tk.tcl')  # Verify this script's CRC, not just the filename.
                return 'embedded-library-zip'
    raise FileNotFoundError('Dados Tk da interface: scripts externos, framework ou ZIP da biblioteca ausentes.')
