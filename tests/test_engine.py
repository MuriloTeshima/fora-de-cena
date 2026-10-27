import unittest
from threading import Event
from unittest.mock import Mock, patch
import numpy as np
from teleport_cam.engine import Engine, Settings
from teleport_cam.scene import Scene
from teleport_cam.effects import Silhouette
from time import monotonic
import cv2

class EngineTests(unittest.TestCase):
    def test_meet_completion_waits_for_output_confirmation_and_uses_delivery_time(self):
        ready, sending, accepted = Event(), Event(), Event()
        capture, virtual = Mock(), Mock()
        scene = Scene()
        scene.background = np.zeros((12, 16, 3), np.uint8)
        scene.hidden = True
        def read():
            ready.wait(3)
            return True, np.ones((12, 16, 3), np.uint8)
        def send(frame):
            sending.set()
            accepted.wait(3)
        capture.read.side_effect = read
        virtual.send.side_effect = send
        with patch('teleport_cam.engine.Scene', return_value=scene), \
             patch.object(Engine, '_open_capture', return_value=capture), \
             patch.object(Engine, '_open_virtual', return_value=virtual), \
             patch.object(Engine, '_inference', return_value=None):
            engine = Engine(Settings(effect='instant', dynamic_background=False))
            try:
                ready.set()
                self.assertTrue(sending.wait(3))
                self.assertTrue(engine.disappearances.empty())
                confirmed_at = monotonic()
                engine.stop.set()
                accepted.set()
                engine.thread.join(4)
                delivered_at, sent = engine.disappearances.get_nowait()
                self.assertTrue(sent)
                self.assertGreaterEqual(delivered_at, confirmed_at)
                self.assertFalse(engine.thread.is_alive())
            finally:
                engine.stop.set()
                accepted.set()
                engine.thread.join(4)

    def test_motion_pulse_triggers_without_hold_but_foreign_effect_observation_does_not(self):
        for observed_mode,expected_hidden in (('dust',True),('anime',False)):
            with self.subTest(observed_mode=observed_mode):
                ready=Event(); capture=Mock(); scene=Scene(); calls=0
                scene.background=np.full((180,320,3),40,np.uint8)
                mask=np.zeros((180,320),np.float32); mask[25:175,115:205]=1
                live=scene.background.copy(); live[mask>0]=180
                def read():
                    nonlocal calls
                    ready.wait(3); calls+=1
                    with engine.lock:
                        stamp=monotonic()
                        engine.silhouette=Silhouette(stamp,live.copy(),mask.copy())
                        engine.observation=(stamp,calls==2,1)
                        engine.observation_effect=observed_mode
                    if calls>=5: engine.stop.set()
                    return True,live.copy()
                capture.read.side_effect=read
                with patch('teleport_cam.engine.Scene',return_value=scene), \
                     patch.object(Engine,'_open_capture',return_value=capture), \
                     patch.object(Engine,'_open_virtual',return_value=None), \
                     patch.object(Engine,'_inference',return_value=None):
                    engine=Engine(Settings(effect='dust',hold=2,dynamic_background=False))
                    ready.set(); engine.thread.join(5)
                self.assertFalse(engine.thread.is_alive())
                self.assertEqual(scene.hidden,expected_hidden)

    def test_effect_selection_changes_without_reopening_capture(self):
        ready=Event(); capture=Mock(); calls=0
        def read():
            nonlocal calls
            ready.wait(3); calls+=1
            if calls==2: engine.commands.put('effect:puff')
            if calls==3: engine.commands.put('effect:portal')
            if calls>=4: engine.stop.set()
            return True,np.full((12,16,3),180,np.uint8)
        capture.read.side_effect=read
        with patch.object(Engine,'_open_capture',return_value=capture) as opened, \
             patch.object(Engine,'_open_virtual',return_value=None), \
             patch.object(Engine,'_inference',return_value=None):
            engine=Engine(Settings(effect='instant',dynamic_background=False))
            ready.set(); engine.thread.join(5)
        self.assertFalse(engine.thread.is_alive())
        self.assertEqual(engine.effect_mode,'portal')
        opened.assert_called_once()
        capture.release.assert_called_once()

    def test_manual_effect_is_sent_clean_and_resources_close(self):
        self.exercise(False)
    def test_virtual_failure_keeps_local_preview_and_closes_devices(self):
        self.exercise(True)
    def exercise(self, send_error):
        ready=Event(); frames=[]; capture=Mock(); virtual=Mock()
        scene=Scene(); scene.background=np.full((12,16,3),30,np.uint8)
        calls=0
        def read():
            nonlocal calls
            ready.wait(3); calls+=1
            if calls==2: engine.commands.put('toggle')
            if calls==3: engine.commands.put('restore')
            if calls>=4: engine.stop.set()
            return True,np.full((12,16,3),180,np.uint8)
        def send(frame):
            frames.append(frame.copy())
            if send_error: raise RuntimeError('simulated disconnect')
        capture.read.side_effect=read
        virtual.send.side_effect=send
        with patch('teleport_cam.engine.Scene',return_value=scene), \
             patch.object(Engine,'_open_capture',return_value=capture), \
             patch.object(Engine,'_open_virtual',return_value=virtual), \
             patch.object(Engine,'_inference',return_value=None):
            engine=Engine(Settings(effect='instant',dynamic_background=False))
            ready.set(); engine.thread.join(5)
        self.assertFalse(engine.thread.is_alive())
        self.assertFalse(engine.running)
        capture.release.assert_called_once()
        virtual.close.assert_called_once()
        self.assertFalse(scene.hidden)
        self.assertIsNotNone(engine.preview)
        if send_error:
            self.assertIn('simulated disconnect',engine.virtual_status)
        else:
            self.assertEqual(len(frames),4)
            self.assertTrue(np.all(frames[0]==180))
            self.assertTrue(np.all(frames[1]==30))
            self.assertTrue(np.all(frames[2]==180))

if __name__=='__main__': unittest.main()


class GokuPipelineTests(unittest.TestCase):
    effect_name='goku'
    def test_animation_reaches_virtual_camera_and_restore_cancels_it(self):
        ready=Event(); capture=Mock(); virtual=Mock(); frames=[]
        scene=Scene(); scene.background=np.full((180,320,3),40,np.uint8)
        live=scene.background.copy()
        mask=np.zeros((180,320),np.float32)
        cv2.circle(mask,(160,45),22,1,-1)
        cv2.ellipse(mask,(160,125),(40,65),0,0,360,1,-1)
        live[mask>0]=(80,140,210)
        calls=0
        def read():
            nonlocal calls
            ready.wait(3); calls+=1
            with engine.lock: engine.silhouette=Silhouette(monotonic(),live.copy(),mask.copy())
            if calls==2: engine.commands.put('toggle')
            if calls==6: engine.commands.put('restore')
            if calls>=8: engine.stop.set()
            return True,live.copy()
        capture.read.side_effect=read
        virtual.send.side_effect=lambda frame: frames.append(frame.copy())
        with patch('teleport_cam.engine.Scene',return_value=scene), \
             patch.object(Engine,'_open_capture',return_value=capture), \
             patch.object(Engine,'_open_virtual',return_value=virtual), \
             patch.object(Engine,'_inference',return_value=None):
            engine=Engine(Settings(effect=self.effect_name,dynamic_background=False))
            ready.set(); engine.thread.join(5)
        self.assertFalse(engine.thread.is_alive())
        self.assertEqual(len(frames),8)
        self.assertTrue(any(np.any(frame!=live) and np.any(frame!=scene.background) for frame in frames[2:5]))
        for frame in frames[5:]: np.testing.assert_array_equal(frame,live)
        self.assertFalse(scene.hidden)
        capture.release.assert_called_once()
        virtual.close.assert_called_once()

class DynamicPipelineTests(unittest.TestCase):
    def test_live_background_reaches_virtual_output_and_emits_single_completion(self):
        ready=Event(); capture=Mock(); virtual=Mock(); frames=[]
        scene=Scene(); scene.background=np.full((100,160,3),40,np.uint8)
        mask=np.zeros((100,160),np.float32); mask[20:85,65:100]=1
        calls=0
        def read():
            nonlocal calls
            ready.wait(3); calls+=1
            frame=scene.background.copy(); frame[mask>0]=220
            frame[5:15,5:15]=100+calls
            with engine.lock: engine.silhouette=Silhouette(monotonic(),frame.copy(),mask.copy())
            if calls==2: engine.commands.put('toggle')
            if calls==5: engine.commands.put('restore')
            if calls>=6: engine.stop.set()
            return True,frame
        capture.read.side_effect=read
        virtual.send.side_effect=lambda frame: frames.append(frame.copy())
        with patch('teleport_cam.engine.Scene',return_value=scene), \
             patch.object(Engine,'_open_capture',return_value=capture), \
             patch.object(Engine,'_open_virtual',return_value=virtual), \
             patch.object(Engine,'_inference',return_value=None):
            engine=Engine(Settings(effect='instant',dynamic_background=True))
            ready.set(); engine.thread.join(5)
        self.assertFalse(engine.thread.is_alive())
        for i in range(1,4):
            self.assertEqual(int(frames[i][50,80,0]),40)
            self.assertEqual(int(frames[i][8,8,0]),101+i)
        self.assertEqual(int(frames[4][50,80,0]),220)
        _,sent=engine.disappearances.get_nowait()
        self.assertTrue(sent)
        self.assertTrue(engine.disappearances.empty())


class AnimePipelineTests(GokuPipelineTests):
    effect_name='anime'

class PuffPipelineTests(GokuPipelineTests):
    effect_name='puff'

class DigitalPipelineTests(GokuPipelineTests):
    effect_name='digital'

class DustPipelineTests(GokuPipelineTests):
    effect_name='dust'

class CartoonPipelineTests(GokuPipelineTests):
    effect_name='cartoon'

class PortalPipelineTests(GokuPipelineTests):
    effect_name='portal'
