"""Isolated apparatus and endpoint checks; fixtures excluded from scientific N."""
import copy
from pathlib import Path
import tempfile
import unittest
import m2_cue_rig as rig
import m2_cue_audit as audit
import m2_cue_analyze as analysis
import pilot_m2 as m


class Checks(unittest.TestCase):
    def test_real_whole_paths_and_all_interventions(self):
        path=Path(tempfile.mkdtemp(prefix='m2-cue-instrument-',dir=m.ROOT/'.work'))
        self.assertTrue(rig.instrument(path,rig.TEST_SEED)['passed'])

    def test_one_excluded_source_files_and_timeline(self):
        path=Path(tempfile.mkdtemp(prefix='m2-cue-unit-',dir=m.ROOT/'.work'))
        value=rig.unit(path,0,seed=rig.TEST_SEED)
        self.assertEqual(value['scientific_origins'],0)
        self.assertEqual(audit.unit_audit(path,value),{'diagnostics':24,'cultivation_probes':49,'whole_snapshots':102,'restorations':6})
        scores=analysis.scores(value,path)
        self.assertEqual(len(scores['histories']),2)
        self.assertEqual(scores['passed'],audit.independently_qualifies(value))

    def test_fixed_six_of_eight_and_no_temporal_rescue(self):
        rows=[{'origin':i,'passed':i<6,'histories':[{'temporal_class':'no-expression-in-window'}]*2} for i in range(8)]
        self.assertEqual(analysis.evaluate(rows)['verdict'],'PASS')
        rows[5]['passed']=False
        for r in rows:r['histories']=[{'temporal_class':'endpoint-missed-window-response'}]*2
        self.assertEqual(analysis.evaluate(rows)['verdict'],'FAIL')


if __name__=='__main__':unittest.main()
