import copy
import unittest
import numpy as np
from lab.tools.raw_state_expression import RawStateProjection,RawGraphStateProjection,RawGraphBasis,ridge_fit,ridge_predict
from threemind_transformer.development import TrajectoryBasis


class RawProcessTests(unittest.TestCase):
    def process(self):
        return {'start_us':'0','end_us':'20','trajectory':[
            {'time_us':str(t),'nodes':[{'channel':7,'activation':a,'inhibition':i}]}
            for t,a,i in ((0,2,3),(10,4,6),(20,8,12))]}

    def test_preserves_amplitude_and_does_not_mutate(self):
        p=self.process();original=copy.deepcopy(p)
        out=RawStateProjection((7,),samples=3).project(p)
        self.assertEqual(out['values'],[[1,2,3],[1,4,6],[1,8,12]])
        self.assertEqual(p,original)
        self.assertEqual(out['sample_times_us'],['0','10','20'])

    def test_missing_and_unknown_are_not_silently_zeroed(self):
        with self.assertRaises(ValueError):RawStateProjection((8,),samples=3).project(self.process())
        with self.assertRaises(KeyError):RawStateProjection((7,),('trace',),samples=3).project(self.process())

    def test_raw_ridge_and_split_boundary(self):
        rows=[{'values':[[x]],'target':str(x>0),'split':'train'} for x in (-2,-1,1,2)]
        model=ridge_fit(rows)
        self.assertEqual(ridge_predict(model,[[[-1.5]],[[1.5]]]),['False','True'])
        with self.assertRaises(ValueError):ridge_fit([dict(rows[0],split='test')])

    def test_new_layout_keeps_legacy_bounds(self):
        with self.assertRaises(ValueError):TrajectoryBasis(tuple(range(4097)))
        basis=RawGraphBasis(4098)
        self.assertEqual(basis.width,4098)
        with self.assertRaises(ValueError):RawGraphBasis(262145)

    def test_graph_excludes_external_queue_and_keeps_real_weights(self):
        p=RawGraphStateProjection((7,8))
        nodes=[dict.fromkeys(p.NODE_FIELDS,0.)|{'id':i+1,'channel':7+i,'birth_us':'0','last_touch_us':'0'} for i in range(2)]
        state={'time_us':'10','nodes':nodes,'edges':[{'source':1,'target':2,'weight':.75,'stability':.2,'eligibility':.1,'touches':3,'birth_us':'0','last_touch_us':'0'}],
               'operator_state':{'short_term':[],'fast':[]},'queue':[{'answer':'secret'}]}
        values=p.project({'states':[state]*5})
        changed=copy.deepcopy(state);changed['queue']=[{'answer':'different'}]
        self.assertTrue(np.array_equal(values,p.project({'states':[changed]*5})))
        self.assertAlmostEqual(values[0,2*14+15+1],.75)


if __name__=='__main__':unittest.main()
