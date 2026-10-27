import unittest
from dataclasses import replace

from teleport_cam.gesture import Face, Point, HoldGate
from teleport_cam.gesture_guides import GUIDES
from teleport_cam.recognition import GestureRecognizer, ninja_pose, portal_pose, farewell_pose


FACE=Face(100,100,100,160)


def hand(opened=False, shift=0):
    points=[Point(150+shift,250) for _ in range(21)]
    points[0]=Point(150+shift,300)
    for base,x in ((5,120),(9,145),(13,170),(17,195)):
        for offset,y in enumerate((230,200,170,140) if opened else (230,210,225,255)):
            points[base+offset]=Point(x+shift,y)
    points[4]=Point(80+shift,215)
    return points


def pinched(tip):
    points=hand(True)
    points[4]=points[tip]
    return points


def snap_release():
    points=pinched(12)
    points[12]=Point(150,270)
    return points


class RecognitionTests(unittest.TestCase):
    def armed(self,mode):
        recognizer=GestureRecognizer()
        for i in range(5): recognizer.update([],FACE,i*.1,mode)
        return recognizer

    def test_ninja_accepts_one_hand_seal_and_mirror_but_rejects_open_palm(self):
        points=hand(False)
        for base,x in ((5,135),(9,150)):
            for offset,y in enumerate((230,200,170,140)): points[base+offset]=Point(x,y)
        self.assertTrue(ninja_pose([points],FACE))
        self.assertTrue(ninja_pose([[replace(point,x=300-point.x) for point in points]],FACE))
        self.assertFalse(ninja_pose([points,points],FACE))
        self.assertFalse(ninja_pose([hand(True)],FACE))
        self.assertFalse(ninja_pose([hand(False)],FACE))
        tilted=[replace(point,x=point.x+(300-point.y)*.3) for point in points]
        self.assertTrue(ninja_pose([tilted],FACE))

    def test_portal_requires_two_open_palms_straddling_face(self):
        self.assertTrue(portal_pose([hand(True,-100),hand(True,100)],FACE))
        self.assertFalse(portal_pose([hand(True,-100)],FACE))
        self.assertFalse(portal_pose([hand(False,-100),hand(True,100)],FACE))
        self.assertFalse(portal_pose([hand(True,100),hand(True,110)],FACE))

    def test_snap_requires_preparation_then_middle_finger_folding(self):
        recognizer=self.armed('dust')
        self.assertFalse(recognizer.update([pinched(12)],FACE,.5,'dust').matched)
        self.assertFalse(recognizer.update([pinched(12)],FACE,.6,'dust').matched)
        self.assertTrue(recognizer.update([snap_release()],FACE,.7,'dust').matched)
        self.assertFalse(recognizer.update([snap_release()],FACE,.8,'dust').matched)

    def test_opening_a_pinch_is_not_a_snap(self):
        recognizer=self.armed('dust')
        recognizer.update([pinched(12)],FACE,.5,'dust')
        recognizer.update([pinched(12)],FACE,.6,'dust')
        self.assertFalse(recognizer.update([hand(True)],FACE,.7,'dust').matched)

    def test_digital_pinch_opens_without_forehead_or_hold_countdown(self):
        recognizer=self.armed('digital')
        recognizer.update([pinched(8)],FACE,.5,'digital')
        recognizer.update([pinched(8)],FACE,.6,'digital')
        self.assertTrue(recognizer.update([hand(True)],FACE,.7,'digital').matched)

    def test_startup_held_pinch_and_single_frame_pinch_do_not_fire(self):
        recognizer=GestureRecognizer()
        for i in range(8): self.assertFalse(recognizer.update([pinched(12)],FACE,i*.1,'dust').matched)
        self.assertFalse(recognizer.update([snap_release()],FACE,.8,'dust').matched)
        recognizer=self.armed('dust')
        recognizer.update([pinched(12)],FACE,.5,'dust')
        self.assertFalse(recognizer.update([snap_release()],FACE,.52,'dust').matched)

    def test_stale_data_mode_change_and_hand_jump_clear_preparation(self):
        for case in ('stale','mode','jump'):
            with self.subTest(case=case):
                recognizer=self.armed('dust')
                recognizer.update([pinched(12)],FACE,.5,'dust')
                recognizer.update([pinched(12)],FACE,.6,'dust')
                points=snap_release()
                if case=='jump': points=[replace(point,x=point.x+80) for point in points]
                result=recognizer.update([points],FACE,1.2 if case=='stale' else .7,'digital' if case=='mode' else 'dust')
                self.assertFalse(result.matched)

    def test_static_single_palm_is_a_hold_pose_without_wave_requirement(self):
        recognizer=self.armed('cartoon')
        gate=HoldGate(.8)
        for i in range(5): gate.update(False,i*.1)
        events=[]
        for i in range(5,25):
            result=recognizer.update([hand(True)],FACE,i*.1,'cartoon')
            self.assertTrue(result.matched)
            events.append(gate.update(result.matched,i*.1))
        self.assertEqual(sum(events),1)
        self.assertFalse(GUIDES['cartoon'].motion)

    def test_farewell_tolerates_naturally_bent_pinky_and_mirroring(self):
        points=hand(True)
        for offset,y in enumerate((230,210,225,255)): points[17+offset]=Point(195,y)
        self.assertTrue(farewell_pose([points],FACE))
        self.assertTrue(farewell_pose([[replace(point,x=300-point.x) for point in points]],FACE))
        self.assertFalse(farewell_pose([hand(False)],FACE))
        self.assertFalse(farewell_pose([hand(True),hand(True)],FACE))

    def test_manual_mode_missing_face_and_bad_geometry_do_not_trigger(self):
        for mode in GUIDES:
            recognizer=self.armed(mode)
            self.assertFalse(recognizer.update([hand(True)],None,.5,mode).matched)
            self.assertFalse(recognizer.update([[Point(float('nan'),0)]*21],FACE,.6,mode).matched)
        recognizer=self.armed('instant')
        for i in range(10): self.assertFalse(recognizer.update([hand(True)],FACE,.5+i*.1,'instant').matched)


if __name__=='__main__': unittest.main()
