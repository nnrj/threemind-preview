import unittest
from collections import defaultdict
import numpy as np
try:
    from lab.tools.visual_event_world import VisualEventWorld
except ImportError:
    VisualEventWorld=None


@unittest.skipIf(VisualEventWorld is None,'optional MuJoCo research dependency unavailable')
class VisualEventTests(unittest.TestCase):
    def test_same_physical_exposure_different_order_and_grouping(self):
        world=VisualEventWorld(71)
        forward,measurements=world.event(0,1)
        reverse,other=world.event(0,-1)
        split,_=world.event(0,1,split=True)
        def totals(frames):
            out=defaultdict(float)
            for row in frames:
                self.assertEqual(row['labels'],{})
                for channel,amount in row['stimulus'].channels:
                    out[channel]+=amount*row['stimulus'].intensity
            return out
        a,b,c=totals(forward),totals(reverse),totals(split)
        self.assertEqual(a.keys(),b.keys())
        self.assertEqual(a.keys(),c.keys())
        for key in a:
            self.assertAlmostEqual(a[key],b[key],places=12)
            self.assertAlmostEqual(a[key],c[key],places=12)
        self.assertEqual(forward[-1],reverse[-1])
        self.assertNotEqual(forward[1],reverse[1])
        self.assertEqual([r['stimulus'].time_us for r in forward],list(range(0,900000,100000)))
        self.assertEqual(len(measurements[0]['object_positions_m']),4)
        self.assertTrue(np.array_equal(measurements[0]['values'],other[0]['values']))


if __name__=='__main__':unittest.main()
