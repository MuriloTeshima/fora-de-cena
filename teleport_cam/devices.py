from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sys
import cv2
from cv2_enumerate_cameras import enumerate_cameras
from .platform_support import valid_linux_video_device


def capture_backends() -> tuple[int, ...]:
    if sys.platform == 'win32':
        return (cv2.CAP_DSHOW, cv2.CAP_MSMF)
    if sys.platform == 'darwin':
        return (cv2.CAP_AVFOUNDATION,)
    if sys.platform.startswith('linux'):
        return (cv2.CAP_V4L2,)
    raise RuntimeError('Sistema sem suporte de captura de câmera.')


def linux_loopback_device(path: str) -> bool:
    if not sys.platform.startswith('linux') or not valid_linux_video_device(path):
        return False
    device = Path('/sys/class/video4linux') / Path(path).name
    return device.exists() and 'virtual' in device.resolve().parts

@dataclass(frozen=True)
class CameraDevice:
    index: int
    name: str
    path: str
    backend: int

    @property
    def label(self) -> str:
        return f'{self.name} · {self.index}'

    @property
    def virtual(self) -> bool:
        return (linux_loopback_device(self.path) or
                any(word in self.name.lower() for word in ('obs','virtual','unity','quest','loopback')))


def list_cameras() -> list[CameraDevice]:
    # Query device metadata only; never start streaming or read image frames.
    cameras = [CameraDevice(c.index,c.name,c.path or '',c.backend)
               for c in enumerate_cameras(capture_backends()[0])]
    # exclusive_caps loopbacks are OUTPUT-only before a producer attaches, so
    # capture-only enumeration cannot list them yet. Read their sysfs metadata.
    known = {camera.path for camera in cameras}
    cameras.extend(device for device in linux_output_devices() if device.path not in known)
    return cameras


def linux_output_devices() -> list[CameraDevice]:
    if not sys.platform.startswith('linux'):
        return []
    devices = []
    for entry in sorted(Path('/sys/class/video4linux').glob('video[0-9]*')):
        path = '/dev/' + entry.name
        if not linux_loopback_device(path):
            continue
        try:
            with (entry / 'name').open(encoding='utf-8', errors='replace') as source:
                name = source.readline(200).strip() or entry.name
        except OSError:
            name = entry.name
        devices.append(CameraDevice(int(entry.name[5:]), name, path, cv2.CAP_V4L2))
    return devices
