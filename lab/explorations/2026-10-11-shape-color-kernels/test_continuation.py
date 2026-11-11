"""No simulation: continuation safety and whole-individual storage accounting."""
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import continue_four as c
import storage_measure as m


class ContinuationChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='e67-test-', dir=c.ROOT/'.work')
        self.work = Path(self.tmp.name)

    def tearDown(self):
        self.assertTrue(self.work.resolve().is_relative_to((c.ROOT/'.work').resolve()))
        self.tmp.cleanup()

    def write(self, name, value):
        path = self.work/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def test_failed_or_incomplete_predecessor_cannot_start(self):
        self.write('pipeline-status.json', {'phase': 'failed'})
        with self.assertRaises(c.HostPause):
            c.ready(self.work)
        self.write('pipeline-status.json', {'phase': 'awaiting-report-review'})
        self.write('computation-complete.json', {'arms': ['2', '3.1']})
        with self.assertRaisesRegex(ValueError, 'stage missing'):
            c.ready(self.work)
        for arm in c.FIRST:
            for stage in c.STAGES:
                self.write(f'arms/{arm}/{stage}/result.json', {})
        with self.assertRaisesRegex(ValueError, 'replay receipt'):
            c.ready(self.work)
        for arm in c.FIRST:
            self.write(f'replays/{arm}/export.json', {})
        self.assertTrue(c.ready(self.work))

    def test_low_disk_stops_four_before_any_subject_work(self):
        # Construct only the host guard, without a Lab client or an organism.
        s = object.__new__(c.FourStudy)
        s.work = self.work
        s.last_guard = 0
        s.last_auth_check = c.time.monotonic()
        disk = c.shutil._ntuple_diskusage(100*2**30, 75*2**30, 25*2**30)
        with patch.object(c.shutil, 'disk_usage', return_value=disk):
            with self.assertRaisesRegex(c.HostPause, 'pause /4 first'):
                s.guard()

    def test_resume_reuses_existing_courses_and_never_runs_first_arms(self):
        self.write('questions.json', {'initial': ['initial-question'],
                    'development': ['development-question'], 'final': ['holdout']})
        self.write('initial-curriculum.json', ['original-initial'])
        for r in range(1, 4):
            self.write(f'round-{r}-curriculum.json',
                       {'lessons': [f'original-course-{r}'], 'calibration': [f'cal-{r}']})
        calls = []
        class FakeStudy:
            work = self.work
            def amend(self): pass
            def guard(self): pass
        def save(s, arm, name, *args):
            calls.append((arm, name, args))
        with patch.object(c, 'teach', save), patch.object(c, 'collect', save), patch.object(c, 'fit', save):
            c.run_four(FakeStudy(), lambda *a, **kw: None)
        self.assertEqual({arm for arm, _, _ in calls}, set(c.LATER))
        self.assertEqual(len(calls), 2*len(c.STAGES))
        for arm in c.LATER:
            self.assertEqual([name for a, name, _ in calls if a == arm], c.STAGES)
        for arm, name, args in calls:
            if name.startswith('correction-'):
                self.assertEqual(args[1], ['original-course-'+name[-1]])
            if name == 'final':
                self.assertEqual(args[1], ['holdout'])

    def test_storage_includes_learning_state_and_counts_shared_once(self):
        self.write('arms/2/fit-3/system/complete.json', {'identity': 'fixture'})
        self.write('arms/2/fit-3/system/words/learning.json', {'optimizer': 'kept', 'rng': 1})
        source = self.work/'arms/2/fit-3/system/system.json.gz'
        source.write_bytes(gzip.compress(json.dumps({'identity': 'fixture', 'session':
            {'core': {'nodes': {'a': {}}, 'edges': []}}}).encode()))
        self.write('arms/2/old-stage/process.json', {'trajectory': 1})
        self.write('replays/2/replay.json', {'video': 1})
        self.write('questions.json', {'shared': 1})
        before = {p: m.digest(p) for p in m.files(self.work)}
        result = m.measure(self.work, ['2'], resident=False)
        row = result['arms']['2']
        self.assertIn('words/learning.json', row['checkpoint_manifest'])
        self.assertEqual(row['complete_individual']['files'], 3)
        self.assertEqual(row['all_files']['files'], 5)
        self.assertEqual(result['shared_or_other_files']['files'], 1)
        self.assertEqual(result['study_files']['bytes'], row['all_files']['bytes']+
                         result['shared_or_other_files']['bytes'])
        self.assertEqual(before, {p: m.digest(p) for p in m.files(self.work)})
        with self.assertRaisesRegex(ValueError, 'complete subject'):
            m.measure(self.work, ['4-legacy'], resident=False)
        if os.name == 'nt':
            # A nonresident uncompressed file has cluster-rounded allocation,
            # not the logical-byte count returned by GetCompressedFileSizeW.
            path = self.work/'allocation-check.bin'
            path.write_bytes(b'x'*5000)
            self.assertGreaterEqual(m.allocated(path), 5000)
            self.assertEqual(m.allocated(path) % 4096, 0)

    def test_auth_expiry_retains_pending_records_without_stopping_authorized_work(self):
        class Client:
            offline = True
            def call(self, *args, **kwargs):
                if self.offline:
                    raise c.AuthenticationRequired('test expired session')
                return {'id': 'test-acknowledgement'}
        client = Client()
        recorder = c.DurableRecorder(self.work, '00000000-0000-0000-0000-000000000001', client=client)
        recorder.register({'source_key': 'isolated-e67-host-test'})
        with patch.object(c, 'ROOT', self.work):
            with self.assertRaises(c.AuthenticationRequired):
                recorder.synchronize(strict=True)
            recorder.allow_deferred = True
            state = recorder.synchronize(strict=True)
            self.assertEqual(state['pending'], 1)
            self.assertEqual(len(list((recorder.control/'pending').glob('*.json'))), 1)
            client.offline = False
            self.assertEqual(recorder.synchronize(strict=True)['pending'], 0)
            self.assertEqual(len(list((recorder.control/'receipts').glob('*.json'))), 1)
            with patch.object(c.ResearchRecorder, 'synchronize', side_effect=ValueError('HTTP 409: conflicting scientific content')):
                with self.assertRaisesRegex(ValueError, '409'):
                    recorder.synchronize(strict=True)
            with patch.object(c.ResearchRecorder, 'synchronize', side_effect=OSError('original storage unavailable')):
                with self.assertRaises(OSError):
                    recorder.synchronize(strict=True)


if __name__ == '__main__':
    unittest.main()
