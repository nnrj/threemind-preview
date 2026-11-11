"""Short synthetic whole-system witnesses, separate from scientific teaching."""
from pathlib import Path
import tempfile
import pytest
from full_subject import Student,old


@pytest.mark.parametrize('curve',['exponential','inverse-logarithmic','power-law'])
@pytest.mark.parametrize('relaxation',[True,False])
def test_full_subject_preserves_personal_adapters_and_next_window(curve,relaxation):
    old.deterministic()
    with tempfile.TemporaryDirectory(prefix='r46-engineering-',dir=Path('.work')) as folder:
        work=Path(folder)
        assert work.resolve().is_relative_to(Path('.work').resolve())
        s=Student(26110940,'engineering-only',curve,relaxation)
        lesson=s.lesson(('Z0',),0)
        assert lesson['teacher_control'] and s.core.time_us==1500000
        s.window({'Z0':.7},observed=True)
        s.checkpoint(work,'current.json.gz');saved=s.state()
        restored=Student.restore(work,saved)
        assert restored.state()==saved
        expected=s.window({'Z1':.8},observed=True)
        actual=restored.window({'Z1':.8},observed=True)
        assert expected==actual
        assert s.state()==restored.state()
        assert set(s.adapters)=={'sound','vision','action'}
        assert len(actual['raw'])==20 and len(actual['indices'])==8
        assert all(set(r)=={'activation','inhibition','direct','associative'} for frame in actual['raw'] for r in frame.values())
