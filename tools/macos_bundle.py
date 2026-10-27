"""Inspect actual Mach-O deployment targets without consulting user settings."""
from pathlib import Path

MACHO_MAGICS = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
                b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}
CPU_TYPES = {'arm64': 0x0100000C, 'x86_64': 0x01000007}


def inspect_macho(path: Path, architecture: str = 'arm64') -> dict | None:
    expected_cpu = CPU_TYPES[architecture]
    with path.open('rb') as stream:
        if stream.read(4) not in MACHO_MAGICS:
            return None
    from macholib.MachO import MachO
    from macholib import mach_o
    versions = []
    architectures = []
    dependencies = set()
    rpaths = set()
    for header in MachO(str(path)).headers:
        architectures.append(header.header.cputype)
        if header.header.cputype != expected_cpu:
            continue
        for load, command, data in header.commands:
            if load.cmd == mach_o.LC_RPATH:
                rpaths.add(data.rstrip(b"\x00").decode("utf-8"))
            version = None
            if load.cmd == mach_o.LC_BUILD_VERSION and command.platform == 1:
                version = command.minos
            elif load.cmd == mach_o.LC_VERSION_MIN_MACOSX:
                version = command.version
            if version is not None:
                versions.append((version >> 16, (version >> 8) & 255, version & 255))
        dependencies.update(name for _, _, name in header.walkRelocatables())
    if expected_cpu not in architectures:
        raise ValueError('Mach-O sem ' + architecture.upper() + ': ' + path.name)
    return {'minimum': max(versions, default=(0, 0, 0)), 'dependencies': sorted(dependencies), 'rpaths': sorted(rpaths)}


def minimum_macos(paths, architecture: str = 'arm64') -> str:
    minimum = (13, 0, 0)
    for path in paths:
        record = inspect_macho(Path(path), architecture)
        if record:
            minimum = max(minimum, record['minimum'])
    return '.'.join(map(str, minimum[:2] if minimum[2] == 0 else minimum))


def audit_bundle(payload: Path, architecture: str = 'arm64') -> dict:
    import plistlib
    files = sorted(p for p in payload.rglob('*') if p.is_file() and not p.is_symlink())
    minimum = minimum_macos(files, architecture)
    plist = plistlib.loads((payload / 'Contents/Info.plist').read_bytes())
    declared = plist.get('LSMinimumSystemVersion', '')
    if tuple(map(int, declared.split('.'))) < tuple(map(int, minimum.split('.'))):
        raise ValueError('LSMinimumSystemVersion inferior às bibliotecas incluídas: ' + minimum)
    if not plist.get('NSCameraUsageDescription'):
        raise ValueError('Falta NSCameraUsageDescription')
    rows = []
    for path in files:
        record = inspect_macho(path, architecture)
        if not record:
            continue
        for name in record['dependencies']:
            if not name.startswith(('@loader_path/', '@rpath/', '@executable_path/', '/usr/lib/', '/System/Library/')):
                raise ValueError('Dependência externa ao macOS/bundle: ' + name)
        for name in record['rpaths']:
            if not name.startswith(('@loader_path', '@executable_path', '/usr/lib', '/System/Library/')):
                raise ValueError('RPATH externo ao macOS/bundle: ' + name)
        resolved = {}
        def expand(value):
            return Path(value.replace('@loader_path', str(path.parent)).replace(
                '@executable_path', str(payload / 'Contents/MacOS')))
        for name in record['dependencies']:
            if name.startswith('@rpath/'):
                candidates = [expand(r) / name[len('@rpath/'):] for r in record['rpaths']]
            elif name.startswith(('@loader_path/', '@executable_path/')):
                candidates = [expand(name)]
            else:
                continue  # macOS libraries may live in the dyld shared cache.
            matches = [p.resolve() for p in candidates
                       if p.exists() and p.resolve().is_relative_to(payload.resolve())]
            if not matches:
                raise ValueError('Dependência não resolvida dentro do bundle: ' + name)
            resolved[name] = matches[0].relative_to(payload.resolve()).as_posix()
        rows.append({'path': path.relative_to(payload).as_posix(),
                     'minimum_macos': '.'.join(map(str, record['minimum'])),
                     'dependencies': record['dependencies'], 'rpaths': record['rpaths'], 'resolved_dependencies': resolved})
    return {'minimum_macos': minimum, 'declared_minimum': declared, 'architecture': architecture,
            'camera_usage_description': plist['NSCameraUsageDescription'], 'binaries': rows}
