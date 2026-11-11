"""Synthetic arithmetic checks. No individual, training or scientific data."""
import copy
import unittest

from diagnose_assay import contrast,coordinate_range,numeric_outcome,variation


class SecondaryDiagnosticsTests(unittest.TestCase):
    def test_temporal_inhibition_position_survives_history_and_omission_subtraction(self):
        lookup={}
        for h in (0,1):
            for cue in (True,False):
                lookup[0,'exponential',True,'ordinary',h,300,cue]={'response_vector':[float(h)]*160}
        position=19*8+1*4+1  # last frame, output 1, inhibition
        lookup[0,'exponential',True,'ordinary',1,300,True]['response_vector'][position]+=.5
        vector=contrast(lookup,0,'exponential',True,'ordinary',300)
        self.assertEqual(vector[position],.5)
        self.assertEqual(sum(x!=0 for x in vector),1)
        self.assertEqual(vector[1::4][-1],.5)

    def test_node_ids_are_not_numeric_variation(self):
        row=dict(formed=True,surviving=1,forecast_30days=[.002],response_vector=[0.,.1],
            initial_connections=[dict(source=17,target=28,source_symbol='cue',target_symbol='out0',weight=.5,half_life=31.)],
            current_connections=[])
        remapped=copy.deepcopy(row)
        remapped['initial_connections'][0].update(source=937,target=652)
        self.assertEqual(numeric_outcome(row),numeric_outcome(remapped))
        result=variation([dict(numeric=numeric_outcome(r)) for r in (row,remapped)])
        self.assertEqual(result['response'],0.)
        self.assertEqual(result['initial_weight'],0.)
        self.assertEqual(result['current_weight'],0.)

    def test_small_numeric_difference_and_changed_structure_are_reported(self):
        a=dict(formed=True,surviving=1,initial=[('cue','out0',.5,31.)],current=[('cue','out0',.1,30.)],
               forecast=[.002],response=[0.,.1])
        b=copy.deepcopy(a);b['response'][1]+=1e-14;b['current']=[]
        result=variation([dict(numeric=x) for x in (a,b)])
        self.assertGreater(result['response'],0.)
        self.assertLess(result['response'],2e-14)
        self.assertEqual(result['current_structures'],2)
        self.assertIsNone(result['current_weight'])
        self.assertIsNone(coordinate_range([[1.],[1.,2.]]))


if __name__=='__main__':unittest.main()
