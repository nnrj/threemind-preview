"""Operational continuation checks; no formal subject is advanced."""
from pathlib import Path
import json,shutil,tempfile
import pytest
import assay_resume as resume
import assay_study as e


def test_complete_prefix_keeps_next_unadvanced_birth():
    cases=e.load(e.WORK/'cases.json')[:2]
    with tempfile.TemporaryDirectory(prefix='r46-resume-test-',dir=Path('.work')) as folder:
        work=Path(folder)
        for i,c in enumerate(cases):
            dst=work/'subjects'/c['key'];dst.mkdir(parents=True)
            src=e.WORK/'subjects'/c['key']
            shutil.copy2(src/'birth.json.gz',dst/'birth.json.gz')
            if i==0:
                for phase in ('teaching','probe'):shutil.copytree(src/phase,dst/phase)
        e.save(work/'cases.json',cases)
        row=e.load(work/'subjects'/cases[0]['key']/'probe/complete.json')
        e.save(work/'current.json',dict(unit='subjects/'+cases[0]['key']+'/probe',
            state_file=row['state_file'],sha256=row['sha256'],time_us=row['end_us']))
        e.save(work/'status.json',dict(state='running',sequences_completed=1))
        verified=resume.complete_prefix(work)
        assert verified['sequences']==1 and verified['boundaries']==2 and verified['next_birth_preserved']
        bad=work/'subjects'/cases[0]['key']/'probe/result.json.gz'
        with bad.open('ab') as f:f.write(b'corrupt engineering copy')
        with pytest.raises(AssertionError):resume.complete_prefix(work)


def test_boundary_failure_precedes_any_new_inflight(monkeypatch):
    with tempfile.TemporaryDirectory(prefix='r46-resume-stop-',dir=Path('.work')) as folder:
        work=Path(folder)
        def refuse(_):raise InterruptedError('complete stop')
        monkeypatch.setattr(e,'boundary',refuse)
        with pytest.raises(InterruptedError):resume.unit(work,'unused',None,lambda:None)
        assert not (work/'in-flight.json').exists() and not list(work.iterdir())
