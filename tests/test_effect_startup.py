from pathlib import Path
from threading import Event
import unittest
from unittest.mock import Mock, patch
import cv2
import numpy as np

from teleport_cam.effects import AnimeTeleportEffect, Silhouette
from teleport_cam.engine import Engine, Settings
from teleport_cam.scene import Scene


class EffectStartupTests(unittest.TestCase):
    def pipeline(self, *, error='', fresh=False, slow_setup=False):
        ready=Event()
        scene=Scene()
        scene.background=np.full((180,320,3),40,np.uint8)
        mask=np.zeros((180,320),np.float32)
        mask[20:175,110:210]=1
        live=scene.background.copy()
        live[mask>0]=(80,140,210)
        capture,virtual=Mock(),Mock()
        frames=[]
        clock=[10.0]
        calls=0
        rendered=[]
        class SlowEffect(AnimeTeleportEffect):
            def __init__(self,*args):
                super().__init__(*args)
                clock[0]+=1.0  # Simulate first-use work longer than the animation.
            def render(self,live,background,now):
                rendered.append((now,self.started))
                return super().render(live,background,now)
        def read():
            nonlocal calls
            ready.wait(3)
            calls+=1
            clock[0]+=.2
            if fresh:
                engine.silhouette=Silhouette(clock[0],live,mask)
            if calls==2:
                engine.effect_error=error
                engine.commands.put('toggle')
            if calls>=9:
                engine.stop.set()
            return True,live.copy()
        capture.read.side_effect=read
        virtual.send.side_effect=lambda frame:frames.append(frame.copy())
        effects={'anime':SlowEffect if slow_setup else AnimeTeleportEffect}
        with patch('teleport_cam.engine.Scene',return_value=scene), \
             patch('teleport_cam.engine.monotonic',side_effect=lambda:clock[0]), \
             patch('teleport_cam.engine.EFFECTS',effects), \
             patch.object(Engine,'_open_capture',return_value=capture), \
             patch.object(Engine,'_open_virtual',return_value=virtual), \
             patch.object(Engine,'_inference',return_value=None):
            engine=Engine(Settings(effect='anime',fps=1000,dynamic_background=False))
            ready.set()
            engine.thread.join(4)
            if engine.thread.is_alive():
                engine.stop.set()
                engine.thread.join(2)
                self.fail('Pipeline did not terminate')
        return engine,scene,frames,live,rendered

    def test_slow_or_missing_mask_never_silently_hides_the_person(self):
        engine,scene,frames,live,_=self.pipeline()
        self.assertFalse(scene.hidden)
        self.assertIn('preservada',engine.message)
        self.assertTrue(engine.disappearances.empty())
        for frame in frames:
            np.testing.assert_array_equal(frame,live)

    def test_mask_failure_does_not_turn_an_animated_effect_into_an_instant_cut(self):
        engine,scene,frames,live,_=self.pipeline(error='synthetic model failure',fresh=True)
        self.assertFalse(scene.hidden)
        self.assertTrue(engine.disappearances.empty())
        self.assertIn('não aplicado',engine.message)
        for frame in frames:
            np.testing.assert_array_equal(frame,live)

    def test_expensive_setup_does_not_use_up_the_animation_timeline(self):
        engine,scene,frames,live,rendered=self.pipeline(fresh=True,slow_setup=True)
        self.assertEqual(rendered[0][0],rendered[0][1])
        self.assertTrue(any(np.any(f!=live) and np.any(f!=scene.background) for f in frames[2:5]))
        self.assertTrue(scene.hidden)

    def test_warmup_is_synthetic_and_does_not_publish_a_person_mask(self):
        engine=Engine.__new__(Engine)
        engine.settings=Settings(width=320,height=180)
        engine.effect_mode='anime'
        engine.silhouette=None
        segmenter=Mock()
        with patch('teleport_cam.engine.Segmenter',return_value=segmenter):
            self.assertIs(engine._prepare_segmenter(Path('models')),segmenter)
        frame,stamp=segmenter.capture.call_args.args
        self.assertEqual(stamp,0.0)
        self.assertEqual(frame.shape,(180,320,3))
        self.assertFalse(frame.any())
        self.assertIsNone(engine.silhouette)

    def test_failed_warmup_closes_native_model_resources(self):
        engine=Engine.__new__(Engine)
        engine.settings=Settings(width=320,height=180)
        engine.effect_mode='anime'
        segmenter=Mock()
        segmenter.capture.side_effect=RuntimeError('initial inference failed')
        with patch('teleport_cam.engine.Segmenter',return_value=segmenter):
            with self.assertRaises(RuntimeError):
                engine._prepare_segmenter(Path('models'))
        segmenter.close.assert_called_once()


class BoundedTeleportTests(unittest.TestCase):
    def test_mac_compositor_keeps_output_size_and_background_detail(self):
        rng=np.random.default_rng(20)
        background=rng.integers(0,256,(720,1280,3),dtype=np.uint8)
        mask=np.zeros((720,1280),np.float32)
        cv2.ellipse(mask,(640,360),(400,345),0,0,360,1,-1)
        live=background.copy()
        live[mask>0]=(80,140,210)
        with patch('teleport_cam.effects.sys.platform','darwin'):
            effect=AnimeTeleportEffect(Silhouette(10,live,mask),True,10)
        self.assertLessEqual(max(effect.alpha.shape),480)
        result=effect.render(live,background,10.15)
        self.assertEqual(result.shape,background.shape)
        left,top,right,bottom=effect.box
        protected=np.ones(mask.shape,bool)
        protected[top:bottom,left:right]=False
        np.testing.assert_array_equal(result[protected],background[protected])
        # No rectangular low-resolution background patch at the ROI's corner.
        np.testing.assert_array_equal(result[top:top+4,left:left+4],background[top:top+4,left:left+4])
        np.testing.assert_array_equal(effect.render(live,background,10),live)
        np.testing.assert_array_equal(effect.render(live,background,10.5),background)

    def test_other_platforms_keep_full_compositor_detail(self):
        frame=np.zeros((720,1280,3),np.uint8)
        mask=np.zeros((720,1280),np.float32)
        mask[15:705,250:1030]=1
        for system in ('win32','linux'):
            with self.subTest(system=system),patch('teleport_cam.effects.sys.platform',system):
                effect=AnimeTeleportEffect(Silhouette(10,frame,mask),True,10)
            self.assertGreater(max(effect.alpha.shape),480)
