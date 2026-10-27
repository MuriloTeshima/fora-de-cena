"""Original, deterministic webcam exits. No downloaded art or character assets."""
from __future__ import annotations

import cv2
import numpy as np

from .effects import Silhouette, TeleportEffect, smooth
from .scene import Frame


class CreativeEffect(TeleportEffect):
    """Animate a bounded cutout at <= 360px, then composite onto the live background."""
    duration = 0.9
    kind = 'puff'

    def __init__(self, subject: Silhouette, hidden_target: bool, started: float) -> None:
        super().__init__(subject, hidden_target, started)
        # Leave room for smoke, flight and the portal without touching the whole image.
        left, top, right, bottom = self.box
        height, width = subject.mask.shape
        pad = max(24, (right-left)//2)
        self.box = (max(0, left-pad), max(0, top-pad//2), min(width, right+pad), min(height, bottom+pad//2))
        left, top, right, bottom = self.box
        self.size = (right-left, bottom-top)
        # Smoke is deliberately soft; a smaller working canvas keeps its extra volume layers cheap.
        limit = 240 if self.kind == 'puff' else 360
        scale = min(1.0, limit/max(self.size))
        size = (max(2, round(self.size[0]*scale)), max(2, round(self.size[1]*scale)))
        self.person = cv2.resize(subject.frame[top:bottom, left:right], size)
        self.alpha = cv2.resize(np.clip(subject.mask[top:bottom, left:right], 0, 1), size)
        self.alpha = cv2.GaussianBlur(self.alpha, (0, 0), .8)
        self.h, self.w = self.alpha.shape
        self.yy, self.xx = np.mgrid[:self.h, :self.w].astype(np.float32)
        occupied = cv2.findNonZero((self.alpha > .4).astype(np.uint8))
        x, y, w, h = cv2.boundingRect(occupied)
        self.center = (x+w/2, y+h/2)
        self.body_size = (w, h)
        rng = np.random.default_rng(291)
        noise = rng.random((max(2, self.h//9), max(2, self.w//9))).astype(np.float32)
        self.noise = cv2.resize(noise, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        self.blocks = cv2.resize(noise, (self.w, self.h), interpolation=cv2.INTER_NEAREST)
        ys, xs = np.nonzero(self.alpha > .6)
        selected = rng.choice(len(xs), min(230, len(xs)), replace=False)
        self.particles = [(int(xs[i]), int(ys[i]), float(rng.uniform(.5, 1.5)), float(rng.uniform(-1, 1))) for i in selected]
        self.clouds = [(float(rng.uniform(-.5, .5)), float(rng.uniform(-.5, .5)), float(rng.uniform(.12, .25))) for _ in range(13)]
        if self.kind == 'puff':
            coarse=rng.random((18,18)).astype(np.float32)
            fine=rng.random((55,55)).astype(np.float32)
            self.smoke_noise=cv2.resize(coarse,(self.w,self.h),interpolation=cv2.INTER_CUBIC)*.7+cv2.resize(fine,(self.w,self.h),interpolation=cv2.INTER_LINEAR)*.3
            self.smoke_noise=cv2.GaussianBlur(self.smoke_noise,(0,0),1.1)
            self.smoke_core=cv2.dilate(self.alpha,np.ones((13,13),np.uint8))
            # Staggered lobes cover the actual torso/head, rather than a few disconnected discs.
            self.plumes=[(float(dx+rng.uniform(-.08,.08)),float(dy+rng.uniform(-.05,.05)),float(rng.uniform(.30,.42)),float(rng.uniform(.17,.24)),float(rng.uniform(.7,1.3)))
                         for dy in (-.44,-.22,0,.22,.44) for dx in (-.30,.30)]

    @staticmethod
    def over(base: Frame, color: Frame, alpha: np.ndarray) -> Frame:
        a = np.clip(alpha, 0, 1)[:, :, None]
        return np.clip(base.astype(np.float32)*(1-a)+color.astype(np.float32)*a, 0, 255).astype(np.uint8)

    def render(self, live: Frame, background: Frame, now: float) -> Frame:
        if live.shape != background.shape or live.shape != self.subject.frame.shape:
            raise ValueError('Resolução mudou durante o efeito.')
        p = min(1.0, max(0.0, (now-self.started)/self.duration))
        if p <= 0:
            return live.copy() if self.hidden_target else background.copy()
        if p >= 1:
            return background.copy() if self.hidden_target else live.copy()
        u = p if self.hidden_target else 1-p
        left, top, right, bottom = self.box
        patch = cv2.resize(background[top:bottom, left:right], (self.w, self.h))
        image, coverage = self._layers(patch, u)
        # Composite the effect delta, so unaffected background stays bit exact.
        full = cv2.resize(image, self.size, interpolation=cv2.INTER_LINEAR)
        alpha = cv2.resize(coverage, self.size, interpolation=cv2.INTER_LINEAR)
        result = background.copy()
        original = result[top:bottom, left:right]
        active = alpha > .002
        original[active] = full[active]
        return result

    def _layers(self, patch: Frame, u: float) -> tuple[Frame, np.ndarray]:
        if self.kind == 'puff':
            return self._puff(patch, u)
        if self.kind in ('digital', 'dust'):
            return self._dissolve(patch, u)
        return self._motion(patch, u)

    def _puff(self, patch: Frame, u: float) -> tuple[Frame, np.ndarray]:
        body = self.alpha*(1-smooth((u-.18)/.19))
        result = self.over(patch, self.person, body)
        density = np.zeros_like(self.alpha)
        volume = np.zeros_like(self.alpha)
        cx, cy = self.center
        bw, bh = self.body_size
        growth = .22+1.12*smooth(u/.40)
        drift = smooth((u-.35)/.65)
        flow_x=self.xx+np.sin(self.yy*.035+u*9)*4
        flow_y=self.yy+u*22
        noise=cv2.remap(self.smoke_noise,flow_x.astype(np.float32),flow_y.astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
        for index,(dx,dy,rx,ry,speed) in enumerate(self.plumes):
            x=cx+dx*bw*growth+np.sin(u*6+index)*bw*.04*drift
            y=cy+dy*bh*growth-drift*bh*.20*speed
            q=((self.xx-x)/max(2,bw*rx*growth))**2+((self.yy-y)/max(2,bh*ry*growth))**2
            depth=np.clip(1-q,0,1)
            density=np.maximum(density,np.clip((1-q+(noise-.5)*.35)*7,0,1))
            volume=np.maximum(volume,depth)
        # The thick core hides the cut at the peak, even on a broad silhouette.
        core=self.smoke_core*smooth(u/.20)*(1-smooth((u-.40)/.25))
        density=np.maximum(density,core)
        envelope=smooth(u/.16)*(1-smooth((u-.50)/.50))
        clouds=cv2.GaussianBlur(density,(0,0),.85)*envelope
        shade=np.where(volume>.55,1.,np.where(volume>.16,.94,.84)).astype(np.float32)
        shade=np.clip(shade+(noise-.5)*.06,.78,1)
        smoke=(np.array((238,241,247),np.float32)*shade[:,:,None]).astype(np.uint8)
        shadow=cv2.GaussianBlur(clouds,(0,0),4)*.15
        result=self.over(result,np.full_like(patch,(118,112,111)),shadow)
        result = self.over(result, smoke, clouds)
        rim=cv2.morphologyEx(clouds,cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8))*.18
        result=self.over(result,np.full_like(patch,(137,133,137)),rim)
        return result, np.maximum(body, np.maximum(clouds,shadow))

    def _dissolve(self, patch: Frame, u: float) -> tuple[Frame, np.ndarray]:
        digital = self.kind == 'digital'
        field = self.blocks if digital else self.noise
        sweep = (self.xx/self.w)*.65+field*.35
        threshold = smooth((u-.04)/.80)
        survival = np.clip((sweep-threshold)*18, 0, 1)
        body = self.alpha*survival
        person = self.person
        if digital:
            small = cv2.resize(person, (max(2, self.w//10), max(2, self.h//10)), interpolation=cv2.INTER_AREA)
            person = cv2.resize(small, (self.w, self.h), interpolation=cv2.INTER_NEAREST)
            shift = np.sin(self.yy*.13+u*36)*smooth(u/.2)*5
            person = cv2.remap(person, self.xx+shift.astype(np.float32), self.yy, cv2.INTER_NEAREST)
        result = self.over(patch, person, body)
        flecks = np.zeros_like(self.alpha)
        colors = np.zeros_like(patch)
        for x, y, speed, drift in self.particles:
            activation = float(sweep[y, x])
            age = (threshold-activation)/.38
            if 0 < age < 1:
                px = round(x+age*self.w*.32*speed)
                py = round(y-age*self.h*.18+drift*age*25)
                radius = max(1, round((4 if digital else 2)*(1-age)))
                opacity = (1-age)*.9
                color = tuple(int(v) for v in self.person[y, x])
                if digital:
                    cv2.rectangle(flecks, (px, py), (px+radius, py+radius), opacity, -1)
                    cv2.rectangle(colors, (px, py), (px+radius, py+radius), color, -1)
                else:
                    cv2.circle(flecks, (px, py), radius, opacity, -1, cv2.LINE_AA)
                    cv2.circle(colors, (px, py), radius, color, -1, cv2.LINE_AA)
        return self.over(result, colors, flecks), np.maximum(body, flecks)

    def _motion(self, patch: Frame, u: float) -> tuple[Frame, np.ndarray]:
        cx, cy = self.center
        portal = self.kind == 'portal'
        travel = smooth((u-.12)/.70)
        sx = max(.01, 1-travel*.98) if portal else 1+.35*np.sin(np.pi*travel)
        sy = max(.01, 1-travel*.98) if portal else max(.5, 1-.35*np.sin(np.pi*travel))
        dx = travel*self.body_size[0]*.45 if portal else travel*self.w*1.45
        matrix = np.float32([[sx, 0, cx*(1-sx)+dx], [0, sy, cy*(1-sy)]])
        person = cv2.warpAffine(self.person, matrix, (self.w, self.h))
        alpha = cv2.warpAffine(self.alpha, matrix, (self.w, self.h))*(1-smooth((u-.75)/.20))
        result = patch.copy()
        coverage = alpha.copy()
        if portal:
            portal_mask = np.zeros_like(alpha)
            envelope = smooth(u/.16)*(1-smooth((u-.76)/.24))
            center = (round(cx+self.body_size[0]*.45), round(cy))
            axes = (max(2, round(self.body_size[0]*.30*envelope)), max(2, round(self.body_size[1]*.52*envelope)))
            cv2.ellipse(portal_mask, center, axes, 0, 0, 360, .7*envelope, -1, cv2.LINE_AA)
            result = self.over(result, np.full_like(patch, (59, 30, 42)), portal_mask)
            rim = np.zeros_like(alpha)
            cv2.ellipse(rim, center, axes, 0, 0, 360, envelope, 3, cv2.LINE_AA)
            result = self.over(result, np.full_like(patch, (255, 170, 105)), cv2.GaussianBlur(rim, (0, 0), 3)*.6)
            result = self.over(result, np.full_like(patch, (255, 227, 189)), rim)
            coverage = np.maximum(coverage, np.maximum(portal_mask, cv2.GaussianBlur(rim, (0, 0), 3)))
        else:
            # A stretched, translucent silhouette sells acceleration without a full-screen wipe.
            trail = cv2.GaussianBlur(alpha, (31, 1), 0)*np.sin(np.pi*travel)*.35
            result = self.over(result, np.full_like(patch, (220, 209, 192)), trail)
            coverage = np.maximum(coverage, trail)
        return self.over(result, person, alpha), coverage


class PuffEffect(CreativeEffect):
    kind = 'puff'
    duration = 1.05


class DigitalEffect(CreativeEffect):
    kind = 'digital'
    duration = .85


class DustEffect(CreativeEffect):
    kind = 'dust'
    duration = 1.15


class CartoonExitEffect(CreativeEffect):
    kind = 'cartoon'
    duration = .65


class PortalEffect(CreativeEffect):
    kind = 'portal'
    duration = 1.0
