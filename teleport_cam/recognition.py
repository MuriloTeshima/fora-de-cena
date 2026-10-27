"""Pure geometry and temporal motion recognition; no camera or audio dependencies."""
from __future__ import annotations
from dataclasses import dataclass
from math import dist, isfinite
from typing import Sequence

from .gesture import Face, Point, goku_pose
from .gesture_guides import guide_for

Hand = Sequence[Point]


def distance(hand: Hand, a: int, b: int) -> float:
    return dist((hand[a].x, hand[a].y), (hand[b].x, hand[b].y))


def valid_hand(hand: Hand) -> bool:
    return len(hand) == 21 and all(isfinite(v) for point in hand for v in (point.x, point.y, point.z)) and distance(hand, 0, 9) >= 12


def extended(hand: Hand, base: int) -> bool:
    length = sum(distance(hand, i, i+1) for i in range(base, base+3))
    return length > 1 and distance(hand, base, base+3)/length > .85 and distance(hand, 0, base+3) > distance(hand, 0, base+1)*1.14


def open_palm(hand: Hand) -> bool:
    return valid_hand(hand) and all(extended(hand, base) for base in (5, 9, 13, 17))


def ninja_pose(hands: Sequence[Hand], face: Face) -> bool:
    if len(hands) != 1 or not near_face(hands[0],face):
        return False
    hand=hands[0]
    palm=distance(hand,0,9)
    return (extended(hand,5) and extended(hand,9)
            and not extended(hand,13) and not extended(hand,17)
            and distance(hand,8,12)<palm*.65
            and hand[8].y<hand[5].y-palm*.18
            and hand[12].y<hand[9].y-palm*.18)


def near_face(hand:Hand,face:Face) -> bool:
    return (valid_hand(hand) and face.height>=20 and face.width>=20
            and .12<distance(hand,0,9)/face.height<1.8
            and abs(hand[0].x-(face.x+face.width/2))<face.width*2.8
            and face.y-face.height*.9<hand[9].y<face.y+face.height*2.6)


def farewell_pose(hands:Sequence[Hand],face:Face) -> bool:
    if len(hands)!=1 or not near_face(hands[0],face):
        return False
    hand=hands[0]
    visible=0
    for base in (5,9,13,17):
        length=sum(distance(hand,i,i+1) for i in range(base,base+3))
        # Natural palms have curved fingers; accept three clearly unfolded fingers.
        if length>1 and distance(hand,base,base+3)/length>.78 and distance(hand,0,base+3)>distance(hand,0,base+1)*1.04:
            visible+=1
    return visible>=3


def portal_pose(hands: Sequence[Hand], face: Face) -> bool:
    if len(hands) != 2 or not all(open_palm(hand) for hand in hands):
        return False
    left, right = sorted(hands, key=lambda hand: hand[9].x)
    center = face.x+face.width/2
    span = right[9].x-left[9].x
    return (left[9].x < center-face.width*.3 and right[9].x > center+face.width*.3
            and face.width*.9 < span < face.width*3.5
            and all(face.y-face.height*.5 < hand[9].y < face.y+face.height*1.8 for hand in hands))


@dataclass(frozen=True)
class Recognition:
    matched: bool
    progress: float
    hint: str


class GestureRecognizer:
    """Hold poses use Engine's HoldGate; motion emits only one fresh, deliberate pulse."""
    def __init__(self) -> None:
        self.mode = ''
        self.reset()

    def reset(self) -> None:
        self.last: float | None = None
        self.neutral_since: float | None = None
        self.armed = False
        self.prepared: tuple[float, Point, float, float] | None = None

    def _neutral(self, now: float) -> None:
        self.prepared = None
        if self.neutral_since is None:
            self.neutral_since = now
        if now-self.neutral_since >= .35:
            self.armed = True

    def _pulse(self) -> Recognition:
        self.armed = False
        self.neutral_since = None
        self.prepared = None
        return Recognition(True, 1.0, 'Gesto reconhecido. Solte a mão antes de repetir.')

    def update(self, hands: Sequence[Hand], face: Face | None, now: float, effect: str) -> Recognition:
        guide = guide_for(effect)
        if effect != self.mode:
            self.reset()
            self.mode = effect
        if not isfinite(now):
            self.reset()
            return Recognition(False, 0, 'Aguardando uma observação válida.')
        if self.last is not None and (now <= self.last or now-self.last > .3):
            self.reset()
        self.last = now
        if face is None or not all(isfinite(v) for v in (face.x, face.y, face.width, face.height)) or min(face.width, face.height) < 20:
            self.reset()
            return Recognition(False, 0, 'Mostre somente seu rosto e mantenha a câmera estável.')
        if guide.kind == 'manual':
            return Recognition(False, 0, guide.instruction)
        if not guide.motion:
            matched = (len(hands) == 1 and goku_pose(hands[0], face) if guide.kind == 'forehead' else
                       ninja_pose(hands, face) if guide.kind == 'ninja' else
                       farewell_pose(hands, face) if guide.kind == 'palm' else portal_pose(hands, face))
            return Recognition(matched, 0, 'Mantenha a posição…' if matched else guide.instruction)
        if len(hands) != 1 or not valid_hand(hands[0]):
            if not hands:
                self._neutral(now)
            else:
                self.reset()
            return Recognition(False, 0, 'Mostre uma mão inteira, bem iluminada.')
        hand = hands[0]
        palm = distance(hand, 0, 9)
        # Motions must stay near this one face, not be a tiny/background hand.
        if not .15 < palm/face.height < 1.3 or abs(hand[0].x-(face.x+face.width/2)) > face.width*2.5:
            self.reset()
            return Recognition(False, 0, 'Aproxime a mão do rosto, sem cobri-lo.')
        tip = 12 if guide.kind == 'snap' else 8
        touching = distance(hand, 4, tip)/palm < .25
        if not self.armed:
            if not touching:
                self._neutral(now)
            else:
                self.neutral_since = None
            return Recognition(False, 0, 'Solte os dedos antes de preparar o próximo gesto.')
        if touching:
            self.neutral_since = None
            if self.prepared is None:
                self.prepared = (now, hand[0], distance(hand, 0, tip)/palm, palm)
            elapsed = now-self.prepared[0]
            if elapsed > 1:
                self.armed = False
                self.prepared = None
                return Recognition(False, 0, 'Preparação longa demais. Solte e tente novamente.')
            return Recognition(False, min(.8, elapsed/.12*.8), 'Agora estale os dedos.' if tip == 12 else 'Agora abra a pinça.')
        if self.prepared is not None:
            began, wrist, reach, old_palm = self.prepared
            elapsed = now-began
            stable = dist((wrist.x, wrist.y), (hand[0].x, hand[0].y)) < old_palm*.65 and .7 < palm/old_palm < 1.4
            separated = distance(hand, 4, tip)/palm > (.4 if tip == 12 else .6)
            # A snap's middle finger must fall toward the palm; opening a pinch is insufficient.
            folded = reach-distance(hand, 0, tip)/palm > .12
            if .07 <= elapsed <= (.8 if tip == 12 else .9) and stable and separated and (folded or tip == 8):
                return self._pulse()
            if elapsed > .9 or not stable:
                self.prepared = None
            else:
                return Recognition(False, .8, 'Complete o movimento mantendo a mão visível.')
        self._neutral(now)
        return Recognition(False, 0, guide.instruction)
