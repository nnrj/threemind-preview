"""Literal sentences, contiguous repetitions, isolated evidence, unchanged Core."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import statistics
import time
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / '.work' / 'blocked-sentence-teaching-20260909'
META = HERE / 'platform.json'
BASE = HERE.parent / '2026-09-09-calibrated-generalization' / 'run.py'
loader = importlib.util.spec_from_file_location('blocked_base', BASE)
base = importlib.util.module_from_spec(loader)
loader.loader.exec_module(base)
OLD_PROJECTS = ['900840b0-d00d-450c-9669-72600cea7c40',
                '8c69053a-125e-4fbd-80a8-5a028abb8a9c',
                '7c4fb6f2-ca29-4cd8-9a4c-f112ddbff1dd']
for key, value in dict(HERE=HERE, ROOT=ROOT, WORK=WORK, META=META,
                       OLD=OLD_PROJECTS[-1], WORKER='blocked-sentence-owned-jobs').items():
    setattr(base, key, value)

from threemind_core import Config
from threemind_lab import notebooks
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.inputs import envelope_record
from threemind_lab.protocols import RunSpec
from threemind_runtime import create_engine
from threemind_runtime.calibration import CalibrationProtocol, transduction
from threemind_runtime.sensory import TEXT_VERSION, TextSensor, TextSensorConfig

encoded = base.encoded
SEEDS = [41701, 41702, 41703, 41704]
GAP = 800_000
SENSOR = TextSensorConfig(normalization='none')
DIALOGUE = [
    '甲是松子。',
    '乙是铃铛。',
    '丙问甲，谁是铃铛？甲说：乙是铃铛。',
    '丙问乙，谁是松子？乙说：甲是松子。',
    '甲对乙说：我是松子，你是铃铛。',
    '乙对甲说：我是铃铛，你是松子。',
    '谁是松子？甲是松子。',
    '谁是铃铛？乙是铃铛。',
    '松子是谁？松子是甲。',
    '铃铛是谁？铃铛是乙。',
]
USER_FAMILY = ['C的父亲是B', 'B的父亲是A', 'C的爷爷是A', '父亲的父亲是爷爷']
FAMILY = USER_FAMILY + ['F的父亲是E', 'E的父亲是D', 'F的爷爷是D']
HELD = ['Z的父亲是Y', 'Y的父亲是X', 'W的父亲是V', 'V的父亲是U']
CROSSED = ['Z的父亲是Y', 'Y的父亲是U', 'W的父亲是V', 'V的父亲是X']


def curriculum():
    blocks = []
    def add(stage, sentences, rounds, repeats):
        for sweep in range(1, rounds + 1):
            for sentence in sentences:
                blocks.append(dict(stage=stage, sweep=sweep, text=sentence, repetitions=repeats))
    add('dialogue', DIALOGUE, 3, 20)
    add('family', FAMILY, 3, 20)
    add('review', DIALOGUE, 1, 5)
    common = list(blocks)
    add('held', HELD, 3, 20)
    normal = list(blocks)
    blocks = list(common)
    add('crossed', CROSSED, 3, 20)
    return common, normal, blocks


def expand(blocks):
    return [b['text'] for b in blocks for _ in range(b['repetitions'])]


def protocols(group, route):
    if group == 'pair':
        cues, terms = ['甲', '乙'], ['松子', '铃铛']
    elif group == 'who':
        cues = ['谁是松子？', '谁是铃铛？', '松子是谁？', '铃铛是谁？']
        terms = ['甲', '乙']
    else:
        names = ['C', 'F'] if group == 'seen_family' else ['Z', 'W']
        terms = ['A', 'B', 'D', 'E'] if group == 'seen_family' else ['X', 'Y', 'U', 'V']
        cues = [child + suffix for child in names for suffix in ['的爷爷是谁？', '的父亲是谁？', '']]
    return CalibrationProtocol(cues=cues, terms=terms, intensities=[1.0], route=route,
                               blank_us=0, learning_during_probe=True)


def inventory(db):
    result = {}
    for project in OLD_PROJECTS:
        with db.tx(project) as c:
            docs = c.execute('SELECT d.id,d.revision,v.content_hash FROM research_documents d '
                             'JOIN research_document_versions v ON v.document_id=d.id AND v.revision=d.revision '
                             'WHERE d.project_id=%s ORDER BY d.id', (project,)).fetchall()
            notes = c.execute('SELECT n.id,n.revision,v.content_hash FROM notes n '
                              'JOIN note_versions v ON v.note_id=n.id AND v.revision=n.revision '
                              'WHERE n.project_id=%s ORDER BY n.id', (project,)).fetchall()
        result[project] = dict(runs=base.heads(db, project), documents=docs, notes=notes)
    return json.loads(encoded(result))


def preflight():
    common, normal, crossed = curriculum()
    assert len(expand(common)) == 1070
    assert len(expand(normal)) == len(expand(crossed)) == 1310
    for course in [normal, crossed]:
        seen = Counter()
        for b in course:
            assert '【' not in b['text'] and '】' not in b['text']
            assert b['repetitions'] >= 10 or seen[b['text']] >= 60
            seen[b['text']] += b['repetitions']
        assert all(seen[s] == 65 for s in DIALOGUE)
        assert all(seen[s] == 60 for s in FAMILY)
        assert all('Z的爷爷是' not in b['text'] and 'W的爷爷是' not in b['text'] for b in course)
    assert Counter(''.join(expand(normal))) == Counter(''.join(expand(crossed)))
    carriers = sorted(set(expand(normal) + expand(crossed)))
    maps = []
    for seed in SEEDS:
        sensor = TextSensor(seed, SENSOR)
        for text in carriers:
            assert sensor.normalize(text) == text
            assert len(list(sensor.frames(text))) == 1, 'Never split a complete training sentence'
        for group in ['pair', 'who', 'seen_family', 'family']:
            p = protocols(group, 'continuation')
            maps.append(dict(seed=seed, group=group, coverage=transduction(sensor, p)['coverage']))
    manifest = dict(seeds=SEEDS, gap_us=GAP, sensor=asdict(SENSOR), core=Config().to_dict(),
                    common=common, normal=normal, crossed=crossed,
                    normal_sentences=expand(normal), crossed_sentences=expand(crossed),
                    sentence_count_per_full_course=1310, simulated_seconds=1048,
                    original_sentences=DIALOGUE + USER_FAMILY,
                    tests={g: {r: protocols(g, r).model_dump() for r in ['continuation', 'birth']}
                           for g in ['pair', 'who', 'seen_family', 'family']})
    (HERE / 'curriculum.json').write_bytes(encoded(manifest))
    result = dict(exact_original_strings=True, punctuation_preserved=True, all_carriers_single_frame=True,
                  first_exposure_repetitions=20, first_three_sweeps_repetitions=20,
                  same_character_counts_in_crossed_control=True, max_sentence_characters=max(map(len, carriers)),
                  coverage=maps, seed_selection='four fixed consecutive seeds; no replacement for poor coverage')
    (HERE / 'preflight.json').write_bytes(encoded(result))
    print(encoded({k: v for k, v in result.items() if k != 'coverage'}).decode())
    print('Unscorable term masks:', [(m['seed'], m['group'], k) for m in maps
                                     for k, v in m['coverage'].items() if not v['scorable']])


def init():
    if META.exists():
        raise RuntimeError('new study already initialized; never overwrite')
    preflight()
    db = Database(Settings.from_env().database_url)
    try:
        old = inventory(db)
        project = db.create_project({'id': LOCAL_USER}, '逐句重复教学：完整说话人与祖父关系 · 2026-09-09')
        book = notebooks.ensure_default(db, project['id'], LOCAL_USER)
        note = uuid4()
        notebooks.save_note(db, project['id'], LOCAL_USER, note, {
            'operation_id': str(uuid4()), 'expected_revision': 0, 'kind': 'note',
            'collection_id': str(book['id']), 'title': '预先方案：每句连续20次，原文、说话人与标点完整保留',
            'body': {'format': 'markdown', 'text': (HERE / 'protocol.md').read_text(encoding='utf-8')}})
        with db.tx() as c:
            size = c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        meta = dict(project_id=str(project['id']), notebook_id=str(book['id']), protocol_note_id=str(note),
                    old_heads_before=base.heads(db, OLD_PROJECTS[-1]), old_inventory_before=old,
                    database_bytes_before=size, quota_baseline_percent=65, quota_stop_percent=83,
                    frozen_sha256={name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                   for name in ['protocol.md', 'curriculum.json', 'run.py', 'preflight.json']},
                    protocol_sha256=hashlib.sha256((HERE / 'protocol.md').read_bytes()).hexdigest(),
                    base_harness_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest())
        META.write_bytes(encoded(meta))
        print(encoded(dict(project_id=meta['project_id'], database_bytes_before=size)).decode())
    finally:
        db.close()


def average(values):
    return statistics.mean(values) if values else None


class Study(base.Study):
    def __init__(self, seed):
        # Reuse only owned-job persistence/probe machinery; there is no calibration gate.
        super().__init__('calibration', attempt=seed)
        self.phase, self.path = f'seed-{seed}', WORK / f'seed-{seed}-results.json'
        if self.path.exists() or (WORK / f'seed-{seed}-trace.jsonl').exists():
            raise RuntimeError('seed evidence already exists; never rerun or overwrite silently')
        for name, sha in self.meta['frozen_sha256'].items():
            assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == sha
        assert hashlib.sha256(BASE.read_bytes()).hexdigest() == self.meta['base_harness_sha256']
        self.seed, self.dose = seed, 1.0
        self.impl['base_harness_sha256'] = self.meta['base_harness_sha256']
        self.impl['study_harness_sha256'] = self.meta['frozen_sha256']['run.py']
        self.impl['curriculum_sha256'] = self.meta['frozen_sha256']['curriculum.json']
        self.anchor_edges = set()
        self.trace = WORK / f'seed-{seed}-trace.jsonl'

    def guard(self, engine=None):
        self.peak = max(self.peak, psutil.Process().memory_info().rss)
        if self.peak > 2 * 1024**3 or psutil.virtual_memory().available < 3 * 1024**3:
            raise RuntimeError('memory reserve reached')
        if min(shutil.disk_usage('D:/').free, shutil.disk_usage(WORK).free) < 15 * 1024**3:
            raise RuntimeError('disk reserve reached')
        local = sum(p.stat().st_size for p in WORK.iterdir() if p.is_file())
        if self.estimated + local > 3 * 1024**3:
            raise RuntimeError('3 GiB training stop; 1 GiB publication reserve')
        if self.previous + time.monotonic() - self.started > 1800:
            raise RuntimeError('30 minute cumulative experiment limit')
        if engine and (engine.metrics()['nodes'] > 2000 or engine.metrics()['edges'] > 100000):
            raise RuntimeError('network trace budget')
        quota = HERE / 'quota-monitor.json'
        if quota.exists() and json.loads(quota.read_bytes())['used_percent'] >= 83:
            raise RuntimeError('account quota stop at 18 percentage points; reserve below 20')

    def start(self, arm, image=None, origin=None):
        e = create_engine(state=image) if image else create_engine(Config())
        spec = RunSpec(environment='manual', clock='unbounded', duration_s=None, seed=self.seed,
                       config=e.config.to_dict(), text_sensor=SENSOR,
                       structural_readout={'enabled': False}, temporal_readout={'enabled': False})
        run = self.db.create_run(self.project, f'逐句20次/{self.seed}/{arm}', spec.model_dump())
        context = dict(initialized=True, start_us=str(e.time_us), origin=origin)
        inputs = RuntimeInputs(self.db, self.project, run['id'], e, spec, context, e.time_us,
                               initial_image=image.to_dict() if image else None)
        return dict(e=e, spec=spec, run=run, inputs=inputs, revision=0, arm=arm, origin=origin,
                    presented=[], start_us=e.time_us, count=1070 if image else 0, previous=None)

    def log_state(self, runtime, block, repetition):
        e = runtime['e']
        state = e.capture_state().to_dict()
        edge_map = {(v['source'], v['target']): v for v in state['edges']}
        if runtime['count'] == 20 and not self.anchor_edges:
            self.anchor_edges = set(edge_map)
        retained = [edge_map[k] for k in self.anchor_edges if k in edge_map]
        row = dict(seed=self.seed, arm=runtime['arm'], count=runtime['count'], block=block,
                   repetition_in_block=repetition, metrics=e.metrics(),
                   mean_edge_stability=average([v['stability'] for v in state['edges']]),
                   mean_node_stability=average([v['stability'] for v in state['nodes']]),
                   mean_local_plasticity=average([v['local_plasticity'] for v in state['nodes']]),
                   first_sentence_edges=len(self.anchor_edges), retained_first_sentence_edges=len(retained),
                   anchor_mean_weight=average([v['weight'] for v in retained]),
                   anchor_mean_stability=average([v['stability'] for v in retained]))
        with self.trace.open('ab') as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False).encode() + b'\n')

    def save(self, runtime, label, groups):
        e, inputs, run = runtime['e'], runtime['inputs'], runtime['run']
        image = e.capture_state()
        cp = self.db.save_checkpoint(self.project, run['id'], image,
            expected_revision=runtime['revision'], status='completed', observations=[e.metrics()],
            previous=runtime['previous'], input_changes=inputs.take_changes(),
            context=dict(initialized=True, protocol=runtime['spec'].model_dump(),
                         start_us=str(runtime['start_us']), end_us=str(e.time_us),
                         input_bus=inputs.bus.capture(), input_bus_run_id=str(run['id']),
                         implementation=self.impl, source_enabled=True,
                         exploration=dict(stage=label, seed=self.seed, arm=runtime['arm'],
                                          count=runtime['count'], sentences=runtime['presented'],
                                          gap_us=GAP, origin=runtime['origin'])))
        runtime['revision'] += 1
        # Full checkpoints are intentionally used for a small number of stage anchors.
        self.refresh_budget()
        measurements = {}
        for group in groups:
            for route in ['continuation', 'birth']:
                self.guard()
                measurements[group + '/' + route] = self.probe(run, cp, protocols(group, route))
        assert e.capture_state().digest == image.digest, 'measurement must not advance or edit the training source'
        row = dict(seed=self.seed, arm=runtime['arm'], stage=label, count=runtime['count'],
                   run_id=str(run['id']), checkpoint_id=str(cp['id']), source_hash=image.digest,
                   simulated_time_us=str(e.time_us), metrics=e.metrics(), measurements=measurements,
                   presented_sha256=hashlib.sha256(encoded(runtime['presented'])).hexdigest())
        self.rows.append(row)
        with (WORK / f'seed-{self.seed}-stages.jsonl').open('ab') as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False).encode() + b'\n')
        print(f"seed {self.seed} {runtime['arm']} {label}: {runtime['count']} inputs; "
              f"{time.monotonic()-self.started:.1f}s; {self.estimated/1024**2:.1f} MiB", flush=True)
        return image, cp

    def teach(self, runtime, blocks, milestones):
        sensor, e, inputs = TextSensor(self.seed, SENSOR), runtime['e'], runtime['inputs']
        last_saved = None
        for block in blocks:
            for rep in range(1, block['repetitions'] + 1):
                self.guard(e)
                if e.life == 'dead':
                    raise RuntimeError('training reached model death; retain evidence and do not resurrect')
                text, at = block['text'], e.time_us
                frames = [dict(f, stimulus=replace(f['stimulus'], time_us=at + f['stimulus'].time_us))
                          for f in sensor.frames(text)]
                assert sensor.normalize(text) == text and len(frames) == 1
                env = envelope_record(uuid4(), 'text-sensor', 'manual-cli-text',
                       {'text': text, 'intensity': 1},
                       {'seed': self.seed, 'adapter': asdict(SENSOR), 'transduction': sensor.describe(text)},
                       1, len(frames[0]['stimulus'].channels), version=TEXT_VERSION)
                inputs.changes['envelopes'].append(env)
                inputs.schedule(env, frames)
                e.advance_to(at + GAP, inputs.observe, inputs_only=True)
                runtime['presented'].append(text)
                runtime['count'] += 1
                if rep == block['repetitions'] or runtime['count'] in [1, 5, 10]:
                    self.log_state(runtime, block, rep)
                if runtime['count'] in milestones:
                    label, groups = milestones[runtime['count']]
                    last_saved = self.save(runtime, label, groups)
            if runtime['count'] % 100 == 0:
                self.refresh_budget()
                print(f"seed {self.seed} {runtime['arm']} training {runtime['count']} inputs", flush=True)
        return last_saved

    def execute(self):
        common, normal, crossed = curriculum()
        primary = self.start('normal')
        milestones = {
            20: ('single_20', []), 40: ('pair_20_each', ['pair']),
            200: ('dialogue_1', ['pair', 'who']), 600: ('dialogue_3', ['pair', 'who']),
            1020: ('family_3', ['seen_family']), 1070: ('review', ['pair', 'who'])}
        image, cp = self.teach(primary, common, milestones)
        source = dict(run_id=str(primary['run']['id']), checkpoint_id=str(cp['id']), source_hash=image.digest,
                      inheritance='exact continuation clone; no activity reset', common_count=1070)
        self.teach(primary, normal[len(common):], {1310: ('final', ['pair', 'who', 'family'])})
        control = self.start('crossed', image, source)
        self.teach(control, crossed[len(common):], {1310: ('final', ['family'])})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['preflight', 'init', 'seed'])
    parser.add_argument('--seed', type=int, choices=SEEDS)
    args = parser.parse_args()
    if args.phase in ['preflight', 'init']:
        globals()[args.phase]()
    else:
        if args.seed is None:
            parser.error('--seed is required')
        study, error = Study(args.seed), None
        try:
            study.execute()
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            study.close(error)
