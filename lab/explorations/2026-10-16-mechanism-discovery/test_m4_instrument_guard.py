"""Pressure detection on isolated directories; no Core or physical instance."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

import m4_instrument_driver as d


class GuardTests(unittest.TestCase):
    def run_fault(self, *, resource_error=None, private=0, elapsed=0):
        work = d.m.ROOT/'.work'/('m4-guard-fixture-'+uuid4().hex)
        work.mkdir(exist_ok=False)
        guard = d.InstrumentGuard(work)
        process = SimpleNamespace(memory_info=lambda: SimpleNamespace(private=private))
        with patch.object(d.m, 'resource_check', side_effect=resource_error,
                          return_value={'available_bytes': {'commit': 9*2**30}}), \
             patch.object(d.psutil, 'Process', return_value=process), \
             patch.object(d.time, 'monotonic', return_value=guard.started+elapsed):
            guard.watch()
        value = json.loads((work/'STOP').read_bytes())
        self.assertFalse((work/'in-flight.json').exists())
        self.assertEqual(set(x.name for x in work.iterdir()), {'STOP'})
        return value

    def test_host_pressure_requests_stop(self):
        self.assertIn('reserve fault', self.run_fault(resource_error=RuntimeError('reserve fault'))['reason'])

    def test_private_cap_requests_stop(self):
        self.assertIn('3 GiB', self.run_fault(private=3*2**30+1)['reason'])

    def test_wall_budget_requests_stop(self):
        self.assertIn('10 minute', self.run_fault(elapsed=601)['reason'])


if __name__ == '__main__':
    unittest.main()
