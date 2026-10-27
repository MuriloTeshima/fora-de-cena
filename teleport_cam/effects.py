from __future__ import annotations
from dataclasses import dataclass
import sys
import cv2
import numpy as np
from numpy.typing import NDArray
from .scene import Frame

Mask = NDArray[np.float32]

@dataclass(frozen=True)
class Silhouette:
    captured_at: float
    frame: Frame
    mask: Mask


def smooth(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)

class TeleportEffect:
    """One captured silhouette; all animation uses elapsed time, never frame count."""
    duration = 0.48

    def __init__(self, subject: Silhouette, hidden_target: bool, started: float,
                 *, max_resolution: int | None = None) -> None:
        if subject.mask.shape != subject.frame.shape[:2] or not np.isfinite(subject.mask).all():
            raise ValueError('Recorte de pessoa inválido.')
        self.subject = subject
        self.hidden_target = hidden_target
        self.started = started
        mask = np.clip(subject.mask, 0, 1)
        points = cv2.findNonZero((mask > 0.4).astype(np.uint8))
        if points is None or len(points) < 100:
            raise ValueError('Não encontrei uma silhueta. Entre no enquadramento.')
        x, y, w, h = cv2.boundingRect(points)
        pad = max(12, round(w * 0.06))
        ih, iw = mask.shape
        self.box = (max(0, x-pad), max(0, y-pad), min(iw, x+w+pad), min(ih, y+h+pad))
        left, top, right, bottom = self.box
        self.person = subject.frame[top:bottom,left:right].copy()
        alpha = mask[top:bottom,left:right]
        if max_resolution is not None and max(alpha.shape) > max_resolution:
            scale = max_resolution / max(alpha.shape)
            size = (max(1,round(alpha.shape[1]*scale)),max(1,round(alpha.shape[0]*scale)))
            self.person = cv2.resize(self.person,size,interpolation=cv2.INTER_AREA)
            alpha = cv2.resize(alpha,size,interpolation=cv2.INTER_AREA)
        self.alpha = cv2.GaussianBlur(alpha, (0,0), 1.1)
        rh, rw = self.alpha.shape
        self.yy, self.xx = np.indices((rh,rw),dtype=np.float32)
        rng = np.random.default_rng(47)
        strips = rng.uniform(0,1,(1,max(2,rw//4))).astype(np.float32)
        self.strips = cv2.resize(strips,(rw,rh),interpolation=cv2.INTER_NEAREST)
        self.halo = cv2.dilate(self.alpha,np.ones((9,9),np.uint8))
        # Position streaks using actual occupied columns, avoiding a rectangular effect.
        columns = np.flatnonzero(self.alpha.max(axis=0) > 0.5)
        self.streaks: list[tuple[int,int,int,float,int]] = []
        for col in rng.choice(columns, size=min(30,len(columns)), replace=False):
            rows = np.flatnonzero(self.alpha[:,col] > 0.4)
            if rows.size:
                self.streaks.append((int(col),int(rows[0]),int(rows[-1]),float(rng.uniform(0.7,1.3)),int(rng.integers(1,3))))

    def finished(self, now: float) -> bool:
        return now-self.started >= self.duration

    def render(self, live: Frame, background: Frame, now: float) -> Frame:
        if live.shape != background.shape or live.shape != self.subject.frame.shape:
            raise ValueError('Resolução mudou durante o efeito.')
        p = min(1.0,max(0.0,(now-self.started)/self.duration))
        if p >= 1:
            return background.copy() if self.hidden_target else live.copy()
        if p <= 0:
            return live.copy() if self.hidden_target else background.copy()
        # Disappearance and return share the same timeline in opposite directions.
        u = p if self.hidden_target else 1-p
        left,top,right,bottom=self.box
        base=background.copy()
        roi=base[top:bottom,left:right].astype(np.float32)
        energy = max(0.0,float(np.sin(np.pi*u)))
        warp = np.sin(self.yy*0.075+u*32)*energy*min(7,self.alpha.shape[1]*0.025)
        warped=cv2.remap(self.person,self.xx+warp,self.yy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
        survival=np.clip((self.strips-u*1.45+0.30)*5,0,1)
        opacity=self.alpha*survival*(1-smooth((u-0.10)/0.65))
        # A pale, vertically stretched remnant persists after the body disappears.
        trail=cv2.GaussianBlur(self.alpha,(1,31),0)*energy*0.16*(1-smooth((u-0.75)/0.25))
        tint=np.array((235,211,179),np.float32)
        roi=roi*(1-trail[:,:,None])+tint*trail[:,:,None]
        roi=roi*(1-opacity[:,:,None])+warped.astype(np.float32)*opacity[:,:,None]
        lines=np.zeros(self.alpha.shape,np.float32)
        rh,rw=self.alpha.shape
        for col,y0,y1,speed,thickness in self.streaks:
            length=max(10,round((y1-y0)*0.5))
            center=round(y1-(u*1.65*speed)*(y1-y0+length))
            cv2.line(lines,(col,max(-length,center-length)),(col,min(rh+length,center)),1.0,thickness,cv2.LINE_AA)
        lines*=self.halo*energy*0.85
        glow=cv2.GaussianBlur(lines,(0,0),2.5)*0.4
        luminous=np.clip(lines+glow,0,0.9)[:,:,None]
        roi=roi*(1-luminous)+np.array((255,239,213),np.float32)*luminous
        base[top:bottom,left:right]=np.clip(roi,0,255).astype(np.uint8)
        # Keep unaffected background bit-exact outside the silhouette and glow.
        return base

class AnimeTeleportEffect(TeleportEffect):
    """Cel-like colors, ink contour and a fast cut, followed by a short speed-line echo."""
    duration=0.42

    def __init__(self,subject:Silhouette,hidden_target:bool,started:float) -> None:
        # Bound procedural work on Apple Silicon while retaining full-resolution
        # capture, output and background. Other platforms retain their detail.
        super().__init__(subject,hidden_target,started,max_resolution=480 if sys.platform=='darwin' else None)
        # Only the brief captured subject is stylized; the camera feed remains natural.
        softened=cv2.bilateralFilter(self.person,5,35,35)
        self.person=np.clip((softened.astype(np.uint16)//40)*40+20,0,255).astype(np.uint8)
        grey=cv2.cvtColor(softened,cv2.COLOR_BGR2GRAY)
        self.ink=(cv2.Canny(grey,55,130).astype(np.float32)/255)*self.alpha
        self.contour=cv2.morphologyEx((self.alpha>0.45).astype(np.uint8),cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8)).astype(np.float32)
        self.trail=cv2.GaussianBlur(self.alpha,(1,41),0)
        self._phase=self.yy[:,:1]*.045
        self._ink_factor=1-self.ink[:,:,None]*.6

    def render(self,live:Frame,background:Frame,now:float) -> Frame:
        if live.shape!=background.shape or live.shape!=self.subject.frame.shape:
            raise ValueError('Resolução mudou durante o teletransporte.')
        p=min(1.,max(0.,(now-self.started)/self.duration))
        if p<=0: return live.copy() if self.hidden_target else background.copy()
        if p>=1: return background.copy() if self.hidden_target else live.copy()
        u=p if self.hidden_target else 1-p
        energy=max(0.,float(np.sin(np.pi*u)))
        left,top,right,bottom=self.box
        result=background.copy()
        # Compose foreground and transmission separately. Upscaling these layers
        # avoids resizing/blurring the full-resolution background inside the box.
        foreground=np.zeros((*self.alpha.shape,3),np.float32)
        transmission=np.ones(self.alpha.shape,np.float32)
        def over(color,alpha):
            attenuation=1-alpha
            foreground[:]*=attenuation[:,:,None]
            foreground[:]+=color*alpha[:,:,None]
            transmission[:]*=attenuation
        # A brief anticipation, a decisive disappearance, then only the echo.
        body=1-smooth((u-0.14)/0.28)
        drift=np.sin(self._phase+u*30)*energy*min(9,self.alpha.shape[1]*.03)
        stretched=cv2.remap(self.person,self.xx+drift,self.yy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
        cel=stretched.astype(np.float32)*self._ink_factor
        alpha=self.alpha*body
        over(cel,alpha)
        outline=self.contour*body*.85
        over(np.array((28,25,24),np.float32),outline)
        echo=self.trail*max(0.,1-abs(u-.43)/.4)*.20
        over(np.array((250,211,150),np.float32),echo)
        lines=np.zeros(self.alpha.shape,np.float32)
        rh,rw=lines.shape
        for col,y0,y1,speed,width in self.streaks:
            length=max(18,round((y1-y0)*.7))
            end=round(y1+(0.20-u)*speed*(y1-y0+length)*1.8)
            cv2.line(lines,(col,end-length),(col,end),1.,width,cv2.LINE_AA)
        lines*=self.halo*energy
        dark=np.clip(cv2.GaussianBlur(lines,(3,1),0)*.45,0,.5)
        foreground*=1-dark[:,:,None]
        transmission*=1-dark
        bright=np.clip(lines*.95,0,.95)
        over(np.array((255,244,220),np.float32),bright)
        size=(right-left,bottom-top)
        if self.alpha.shape != (size[1],size[0]):
            foreground=cv2.resize(foreground,size,interpolation=cv2.INTER_LINEAR)
            transmission=cv2.resize(transmission,size,interpolation=cv2.INTER_LINEAR)
        roi=result[top:bottom,left:right].astype(np.float32)
        roi*=transmission[:,:,None]
        roi+=foreground
        np.clip(roi,0,255,out=roi)
        result[top:bottom,left:right]=roi.astype(np.uint8)
        return result
