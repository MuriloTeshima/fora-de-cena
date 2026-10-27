import unittest

import cv2
import numpy as np

from teleport_cam.effects import Silhouette
from teleport_cam.effect_catalog import EFFECTS, LABELS


class CreativeEffectTests(unittest.TestCase):
    def setUp(self):
        self.mask=np.zeros((180,320),np.float32)
        cv2.circle(self.mask,(160,45),22,1,-1)
        cv2.ellipse(self.mask,(160,125),(40,65),0,0,360,1,-1)
        self.background=np.full((180,320,3),40,np.uint8)
        self.live=self.background.copy()
        self.live[self.mask>0]=(80,140,210)
        self.subject=Silhouette(10,self.live,self.mask)

    def test_all_modes_have_exact_endpoints_in_both_directions(self):
        for name,kind in EFFECTS.items():
            for hidden in (True,False):
                with self.subTest(effect=name,hidden=hidden):
                    effect=kind(self.subject,hidden,10)
                    np.testing.assert_array_equal(effect.render(self.live,self.background,10),self.live if hidden else self.background)
                    np.testing.assert_array_equal(effect.render(self.live,self.background,10+effect.duration+.001),self.background if hidden else self.live)
                    self.assertTrue(effect.finished(10+effect.duration+.001))

    def test_effects_are_distinct_time_based_and_do_not_mutate_inputs(self):
        outputs=[]
        for name in ('puff','digital','dust','cartoon','portal'):
            with self.subTest(effect=name):
                kind=EFFECTS[name]; effect=kind(self.subject,True,10)
                before=self.live.copy(); bg=self.background.copy(); mask=self.mask.copy()
                effect.render(self.live,self.background,10+.1*effect.duration)
                result=effect.render(self.live,self.background,10+.45*effect.duration)
                other=kind(self.subject,True,10).render(self.live,self.background,10+.45*effect.duration)
                np.testing.assert_array_equal(result,other)
                np.testing.assert_array_equal(self.live,before)
                np.testing.assert_array_equal(self.background,bg)
                np.testing.assert_array_equal(self.mask,mask)
                left,top,right,bottom=effect.box
                protected=np.ones(self.mask.shape,bool); protected[top:bottom,left:right]=False
                np.testing.assert_array_equal(result[protected],bg[protected])
                self.assertEqual(result.dtype,np.uint8)
                self.assertTrue(np.any(result!=bg))
                outputs.append(result)
        for i in range(len(outputs)):
            for j in range(i): self.assertFalse(np.array_equal(outputs[i],outputs[j]))

    def test_bad_masks_and_changed_resolution_are_rejected(self):
        for name in ('puff','digital','dust','cartoon','portal'):
            with self.subTest(effect=name):
                for mask in (np.zeros_like(self.mask),np.full_like(self.mask,np.nan)):
                    with self.assertRaises(ValueError): EFFECTS[name](Silhouette(10,self.live,mask),True,10)
                effect=EFFECTS[name](self.subject,True,10)
                with self.assertRaises(ValueError): effect.render(self.live[:10],self.background,10.2)

    def test_catalog_has_only_supported_identifiers(self):
        self.assertEqual(set(LABELS.values()),set(EFFECTS)|{'instant'})

    def test_smoke_opaque_peak_covers_subject_before_it_disappears(self):
        effect=EFFECTS['puff'](self.subject,True,10)
        patch=np.full((effect.h,effect.w,3),40,np.uint8)
        image,coverage=effect._puff(patch,.32)
        core=effect.alpha>.95
        self.assertGreater(float(np.mean(coverage[core])),.96)
        # Smoke contains shaded volume, not one flat paint color.
        self.assertGreater(float(image[core].std()),3)


if __name__=='__main__': unittest.main()
