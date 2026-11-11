"""One N0 fixture: exact mask scope, whole restoration and subsequent action."""
import json,unittest
from uuid import uuid4
from m4_instrument import ROOT
from m4_instrument_driver import InstrumentGuard
import m4_balanced_rig as rig
import pilot_m2 as m


class RigTests(unittest.TestCase):
    def test_complete_parent_and_mask_restoration(self):
        folder=(ROOT/'.work'/('m4-balanced-fixture-'+uuid4().hex)).resolve();folder.mkdir()
        with InstrumentGuard(folder) as guard:
            self.assertTrue(guard.thread.is_alive())
            result=rig.instrument(folder,1123004)
            m.original(folder/'result.json',result)
            self.assertTrue(result['passed'])
        self.assertFalse((folder/'STOP').exists())
        print(json.dumps({'fixture':str(folder),'result':result}))


if __name__=='__main__':unittest.main()
