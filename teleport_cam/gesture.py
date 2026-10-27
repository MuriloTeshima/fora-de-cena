from __future__ import annotations
from dataclasses import dataclass
from math import dist, isfinite
from typing import Sequence

@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float = 0.0

@dataclass(frozen=True)
class Face:
    x: float
    y: float
    width: float
    height: float


def goku_pose(hand: Sequence[Point], face: Face | None) -> bool:
    """Pixel coordinates; geometry stays independent of MediaPipe and video APIs."""
    if len(hand) != 21 or face is None:
        return False
    if not all(isfinite(v) for p in hand for v in (p.x, p.y, p.z)):
        return False
    if not all(isfinite(v) for v in (face.x, face.y, face.width, face.height)):
        return False
    if min(face.width, face.height) < 20:
        return False
    def distance(a: int, b: int) -> float:
        return dist((hand[a].x, hand[a].y), (hand[b].x, hand[b].y))
    palm = distance(0, 9)
    if palm < 12 or not 0.15 < palm / face.height < 1.3:
        return False
    def extended(base: int) -> bool:
        length = sum(distance(i, i + 1) for i in range(base, base + 3))
        return (length > 1 and distance(base, base + 3) / length > 0.88
                and distance(0, base + 3) > distance(0, base + 1) * 1.18)
    if not extended(5) or not extended(9) or extended(13) or extended(17):
        return False
    if not 0.03 * palm < distance(8, 12) < 0.48 * palm:
        return False
    for tip in (8, 12):
        p = hand[tip]
        if not (face.x + face.width * 0.08 <= p.x <= face.x + face.width * 0.92
                and face.y - face.height * 0.18 <= p.y <= face.y + face.height * 0.28):
            return False
    return True


class HoldGate:
    """Require release, then continuous fresh observations before one trigger."""
    def __init__(self, hold_seconds: float = 1.0) -> None:
        if not 0.6 <= hold_seconds <= 3.0:
            raise ValueError('Tempo do gesto deve ficar entre 0,6 e 3 segundos.')
        self.hold_seconds = hold_seconds
        self.reset()

    def reset(self) -> None:
        self.armed = False
        self.started: float | None = None
        self.released: float | None = None
        self.last: float | None = None
        self.progress = 0.0

    def update(self, matched: bool, now: float) -> bool:
        if not isfinite(now):
            self.reset()
            return False
        if self.last is not None and (now <= self.last or now - self.last > 0.3):
            self.reset()
        self.last = now
        if not matched:
            self.started = None
            self.progress = 0.0
            if self.released is None:
                self.released = now
            if now - self.released >= 0.35:
                self.armed = True
            return False
        self.released = None
        if not self.armed:
            return False
        if self.started is None:
            self.started = now
        self.progress = min(1.0, (now - self.started) / self.hold_seconds)
        if self.progress < 1.0:
            return False
        self.reset()
        return True
