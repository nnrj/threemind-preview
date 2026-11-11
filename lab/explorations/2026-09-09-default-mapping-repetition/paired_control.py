"""Pair-swap control planned before any teaching; existing sensor and Core defaults."""
import argparse
import hashlib
import json
import re
from uuid import uuid4

from run import HERE, WORK, META, BASE, Study, base, curriculum, encoded
from threemind_lab import notebooks
from threemind_lab.config import Settings
from threemind_lab.database import Database, LOCAL_USER


def swapped(text):
    return re.sub('松子|铃铛', lambda m: {'松子':'铃铛','铃铛':'松子'}[m[0]], text)


def init():
    meta = json.loads(META.read_bytes())
    assert not meta.get('completed_phases'), 'Register all controls before starting any training'
    assert 'pair_control' not in meta
    plan = (HERE/'pair-control-plan.md').read_text(encoding='utf-8')
    db = Database(Settings.from_env().database_url)
    try:
        note = uuid4()
        notebooks.save_note(db, meta['project_id'], LOCAL_USER, note, {
            'operation_id':str(uuid4()), 'expected_revision':0, 'kind':'note',
            'collection_id':meta['notebook_id'], 'title':'预先对照方案：保持逐句20次的名词配对互换',
            'body':{'format':'markdown','text':plan}})
        meta['pair_control'] = dict(seeds=[41701,41702], note_id=str(note),
            frozen_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest()
                           for n in ['pair-control-plan.md','paired_control.py']})
        META.write_bytes(encoded(meta))
        print('Pair control plan saved before any main or control training.')
    finally:
        db.close()


class Control(Study):
    def __init__(self, seed):
        base.Study.__init__(self, 'calibration', attempt=seed+10000)
        self.phase, self.path = f'pair-swap-{seed}', WORK / f'pair-swap-{seed}-results.json'
        self.seed, self.dose = seed, 1.0
        self.trace = WORK / f'pair-swap-{seed}-trace.jsonl'
        if self.path.exists() or self.trace.exists():
            raise RuntimeError('supplement evidence already exists')
        for name, sha in (self.meta['frozen_sha256'] | self.meta['pair_control']['frozen_sha256']).items():
            assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha
        assert hashlib.sha256(BASE.read_bytes()).hexdigest()==self.meta['base_harness_sha256']
        expected_implementation=json.loads((HERE/'implementation.json').read_bytes())
        assert self.impl['source_sha256']==expected_implementation['source_sha256']
        assert self.impl['native_binary_sha256']==expected_implementation['native_binary_sha256']
        self.impl['study_harness_sha256']=self.meta['frozen_sha256']['run.py']
        self.impl['supplement_harness_sha256']=self.meta['pair_control']['frozen_sha256']['paired_control.py']
        self.anchor_edges=set()

    def execute(self):
        _, normal, _ = curriculum()
        blocks=[b | {'text':swapped(b['text'])} for b in normal]
        for before, after in zip(normal, blocks):
            assert len(before['text'])==len(after['text'])
            assert re.sub('松子|铃铛','物体',before['text'])==re.sub('松子|铃铛','物体',after['text'])
        runtime=self.start('pair_swap')
        self.teach(runtime, blocks, {
            20:('single_20',[]), 40:('pair_20_each',['pair']),
            200:('dialogue_1',['pair','who']), 600:('dialogue_3',['pair','who']),
            1070:('review',['pair','who']), 1310:('final',['pair','who'])})


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=['init','seed'])
    p.add_argument('--seed',type=int,choices=[41701,41702])
    args=p.parse_args()
    if args.phase=='init':
        init()
    else:
        if args.seed is None:
            p.error('--seed required')
        study,error=Control(args.seed),None
        try:
            study.execute()
        except Exception as exc:
            error=f'{type(exc).__name__}: {exc}'
            raise
        finally:
            study.close(error)
