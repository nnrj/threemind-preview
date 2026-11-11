"""Bounded, new-project-only teaching study using the existing Lab services."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import shutil
import time
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / '.work' / 'language-scaffold-relations-20260909'
META = HERE / 'platform.json'
BASE = HERE.parent / '2026-09-09-calibrated-generalization' / 'run.py'
loader = importlib.util.spec_from_file_location('scaffold_base', BASE)
base = importlib.util.module_from_spec(loader)
loader.loader.exec_module(base)
for key, value in dict(HERE=HERE, ROOT=ROOT, WORK=WORK, META=META,
                       OLD='8c69053a-125e-4fbd-80a8-5a028abb8a9c',
                       WORKER='language-scaffold-owned-jobs').items():
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
FAMILIES = [
    ('A B C D E F', 'X Y Z U V W'),
    ('青岳 白川 赤岩 玄舟 苍木 紫原', '冬岚 春汀 夏岑 秋洵 雪澄 露屿'),
]
CAL = [('A B C D E F', 'I J K L M N'),
       ('青岳 白川 赤岩 玄舟 苍木 紫原', '岚岳 汀川 岑岩 洵舟 澄木 屿原')]
ARMS = ['full', 'rule_scrambled', 'teaching_scrambled', 'crossed_chain', 'learning_off']
DIALOGUE = [
    '甲是松子。', '乙是铃铛。',
    '丙问甲，谁是铃铛？甲说：乙是铃铛。',
    '丙问乙，谁是松子？乙说：甲是松子。',
    '甲对乙说：我是松子，你是铃铛。',
    '乙对甲说：我是铃铛，你是松子。',
    '谁是松子？甲是松子。', '谁是铃铛？乙是铃铛。',
    '松子是谁？松子是甲。', '铃铛是谁？铃铛是乙。',
]
EXTRA_PAIRS = [('甲', '松子', '乙', '铃铛'), ('丁', '陶杯', '戊', '柳叶'), ('己', '木舟', '庚', '星河')]
OLD_PROJECTS = ['900840b0-d00d-450c-9669-72600cea7c40', base.OLD]


def shuffle_text(text, key):
    chars = list(text)
    random.Random(key).shuffle(chars)
    result = ''.join(chars)
    if result == text:
        result = text[1:] + text[:1]
    assert Counter(text) == Counter(result)
    return result


def curriculum(seed, family, rounds, arm, *, calibration=False):
    source, held = (CAL if calibration else FAMILIES)[family]
    a, b, c, d, e, f = source.split()
    x, y, z, u, v, w = held.split()
    facts = [f'{a}是{b}的父亲', f'{b}是{c}的父亲', f'{a}是{c}的爷爷',
             f'{d}是{e}的父亲', f'{e}是{f}的父亲', f'{d}是{f}的爷爷']
    lessons = [('rule', '父亲的父亲是爷爷')] * 2 + [
        ('language', f'{c}的爷爷是谁？{c}的爷爷是{a}。'),
        ('language', f'{f}的爷爷是谁？{f}的爷爷是{d}。'),
    ]
    sentences = []
    for cycle in range(rounds):
        rng = random.Random(seed * 1000 + cycle)
        person, object_, other, object2 = EXTRA_PAIRS[cycle % len(EXTRA_PAIRS)]
        dialogue = [text.replace('甲', person).replace('乙', other).replace('松子', object_).replace('铃铛', object2)
                    for text in DIALOGUE]
        extra = list(lessons) + [('language', text) for text in dialogue]
        rng.shuffle(extra)
        ordered = facts if cycle % 2 == 0 else facts[3:] + facts[:3]
        # Every condition has the same slots, carrier lengths and simulation duration.
        block = list(ordered)
        for j, (kind, text) in enumerate(extra):
            if arm == 'teaching_scrambled' or arm == 'rule_scrambled' and kind == 'rule':
                text = shuffle_text(text, seed * 100000 + cycle * 100 + j)
            block.insert(min(1 + 2 * j, len(block)), text)
        sentences.extend(block)
    chain = [f'{x}是{y}的父亲', f'{y}是{z}的父亲', f'{u}是{v}的父亲', f'{v}是{w}的父亲']
    if arm == 'crossed_chain':
        chain = [f'{u}是{y}的父亲', f'{y}是{z}的父亲', f'{x}是{v}的父亲', f'{v}是{w}的父亲']
    for cycle in range(8):
        order = chain.copy()
        random.Random(seed * 1000 + 500 + cycle).shuffle(order)
        sentences.extend(order)
    assert all(f'{z}的爷爷是' not in s and f'{w}的爷爷是' not in s for s in sentences)
    return sentences, held.split()


def protocols(names, doses, route='birth'):
    a, b, c, d, e, f = names
    return {
        'family': CalibrationProtocol(
            cues=[n + suffix for n in [c, f] for suffix in ['的爷爷是谁？', '的父亲是谁？', '']],
            terms=[a, b, d, e], intensities=doses, route=route, blank_us=200000),
        'who': CalibrationProtocol(cues=['松子是谁？', '铃铛是谁？'], terms=['甲', '乙'],
                                   intensities=doses, route=route, blank_us=200000),
    }


def old_inventory(db):
    inventory = {}
    for project in OLD_PROJECTS:
        with db.tx(project) as c:
            docs = c.execute('SELECT d.id,d.revision,v.content_hash FROM research_documents d '
                             'JOIN research_document_versions v ON v.document_id=d.id AND v.revision=d.revision '
                             'WHERE d.project_id=%s ORDER BY d.id',
                             (project,)).fetchall()
            notes = c.execute('SELECT n.id,n.revision,v.content_hash FROM notes n '
                              'JOIN note_versions v ON v.note_id=n.id AND v.revision=n.revision '
                              'WHERE n.project_id=%s ORDER BY n.id', (project,)).fetchall()
            # Model metadata and document heads only; historical payloads are not scanned.
        inventory[project] = {'runs': base.heads(db, project), 'documents': docs, 'notes': notes}
    return json.loads(encoded(inventory))


def preflight():
    rows = []
    for seed in range(41501, 41505):
        for family in range(2):
            _, names = curriculum(seed, family, 8, 'full', calibration=True)
            for key, protocol in protocols(names, [2.0]).items():
                sensor = TextSensor(seed, TextSensorConfig())
                mapping = transduction(sensor, protocol)
                rows.append({'seed': seed, 'family': family, 'group': key, 'coverage': mapping['coverage']})
    value = {'channel_count': 192, 'rows': rows,
             'note': 'physical coverage only; no Core training or answer selection'}
    (HERE / 'preflight.json').write_bytes(encoded(value))
    print(encoded({'groups': len(rows), 'covered_terms': sum(v['scorable'] for r in rows for v in r['coverage'].values()),
                   'terms': sum(len(r['coverage']) for r in rows)}).decode())


def init():
    if META.exists():
        raise RuntimeError('project already exists; never overwrite')
    db = Database(Settings.from_env().database_url)
    try:
        before = old_inventory(db)
        project = db.create_project({'id': LOCAL_USER}, '教学探索：父亲的父亲与问答迁移 · 2026-09-09')
        book = notebooks.ensure_default(db, project['id'], LOCAL_USER)
        ident = uuid4()
        notebooks.save_note(db, project['id'], LOCAL_USER, ident, {
            'operation_id': str(uuid4()), 'expected_revision': 0, 'title': '预先方案：教学句与祖父关系迁移',
            'kind': 'note', 'collection_id': str(book['id']),
            'body': {'format': 'markdown', 'text': (HERE / 'protocol.md').read_text(encoding='utf-8')}})
        with db.tx() as c:
            size = c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        meta = {'project_id': str(project['id']), 'notebook_id': str(book['id']), 'protocol_note_id': str(ident),
                'protocol_sha256': hashlib.sha256((HERE / 'protocol.md').read_bytes()).hexdigest(),
                'base_harness_sha256': hashlib.sha256(BASE.read_bytes()).hexdigest(),
                'old_heads_before': base.heads(db, base.OLD), 'old_inventory_before': before,
                'database_bytes_before': size, 'quota_baseline_percent': 63, 'quota_stop_percent': 81}
        META.write_bytes(encoded(meta))
        print(encoded({'project_id': meta['project_id'], 'database_bytes_before': size}).decode())
    finally:
        db.close()


class Study(base.Study):
    def __init__(self, phase):
        super().__init__(phase)
        assert hashlib.sha256(BASE.read_bytes()).hexdigest() == self.meta['base_harness_sha256']
        self.impl['base_harness_sha256'] = self.meta['base_harness_sha256']
        self.impl['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def guard(self, engine=None):
        self.peak = max(self.peak, psutil.Process().memory_info().rss)
        if self.peak > 2 * 1024**3 or psutil.virtual_memory().available < 3 * 1024**3:
            raise RuntimeError('memory budget')
        if min(shutil.disk_usage('D:/').free, shutil.disk_usage(WORK).free) < 15 * 1024**3:
            raise RuntimeError('disk reserve')
        local = sum(p.stat().st_size for p in WORK.glob('*') if p.is_file())
        if self.estimated + local > 3 * 1024**3:
            raise RuntimeError('training storage limit; 1 GiB reserved for publication')
        if time.monotonic() - self.started + self.previous > 1200:
            raise RuntimeError('20 minute experiment limit')
        if engine and (engine.metrics()['nodes'] > 2000 or engine.metrics()['edges'] > 100000):
            raise RuntimeError('network limit')

    def train(self, seed, sentences, tag, learn=True):
        # Use the unchanged previous training path, including input bus audit and checkpoint persistence.
        return super().train(seed, 'anonymous-distributed', sentences, 800000, tag, learn)

    def execute(self):
        if self.phase == 'calibration':
            cases = [(s, f, 8, 'full') for s in [41501, 41502] for f in range(2)]
        else:
            n = 24 if self.phase == 'main' else 8
            arms = ARMS if self.phase == 'main' else ['full', 'rule_scrambled']
            cases = [(s, f, n, a) for s in range(41601, 41613) for f in range(2) for a in arms]
        journal = WORK / f'{self.phase}-cases.jsonl'
        if journal.exists():
            raise RuntimeError('case journal already exists')
        for seed, family, n, arm in cases:
            self.refresh_budget()
            sentences, names = curriculum(seed, family, n, arm, calibration=self.phase == 'calibration')
            run, cp = self.train(seed, sentences, f'{self.phase}/{seed}/f{family}/n{n}/{arm}', arm != 'learning_off')
            doses = [1.0, 2.0, 4.0] if self.phase == 'calibration' else [self.dose]
            measurements = {k: self.probe(run, cp, p) for k, p in protocols(names, doses).items()}
            if self.phase == 'main' and arm == 'full':
                measurements['continuous_family'] = self.probe(run, cp, protocols(names, doses, 'continuation')['family'])
            row = {'seed': seed, 'family': family, 'n': n, 'arm': arm, 'names': names,
                   'sentence_count': len(sentences), 'corpus_sha256': hashlib.sha256(encoded(sentences)).hexdigest(),
                   'measurements': measurements}
            self.rows.append(row)
            with journal.open('ab') as stream:
                stream.write(json.dumps(row, ensure_ascii=False, default=str).encode() + b'\n')
            if len(self.rows) % 4 == 0 or self.phase == 'calibration':
                print(f'{self.phase} {len(self.rows)}/{len(cases)}; {time.monotonic()-self.started:.1f}s; '
                      f'estimated {self.estimated/1024**2:.1f} MiB', flush=True)


def decide():
    meta = json.loads(META.read_bytes())
    data = json.loads((WORK / meta['completed_phases']['calibration']).read_bytes())
    checks = []
    for dose in [1, 2, 4]:
        eligible = []
        for case in data['rows']:
            for m in case['measurements'].values():
                cover = all(v['scorable'] for v in m['mapping']['coverage'].values())
                for r in m['rows']:
                    if r['cue'] and r['intensity'] == dose:
                        eligible.append(cover and r['available'] and r['transport']['sent'] > 0
                                        and r['delivered_signal_amount'] > 0 and r['max_saturated_fraction'] < .2)
        checks.append({'dose': dose, 'eligible': sum(eligible), 'total': len(eligible),
                       'fraction': sum(eligible)/len(eligible)})
    selected = next((r['dose'] for r in checks if r['fraction'] >= .8), None)
    decision = {'selected_dose': selected, 'calibration_passed': selected is not None, 'summary': checks,
                'rule': 'lowest dose with >=80% physical observability; target scores never used',
                'calibration_sha256': hashlib.sha256((WORK / meta['completed_phases']['calibration']).read_bytes()).hexdigest()}
    with (HERE / 'calibration-decision.json').open('xb') as stream:
        stream.write(encoded(decision))
    print(encoded(decision).decode())
    if selected is None:
        raise SystemExit('calibration did not qualify: stop formal validation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['preflight', 'init', 'calibration', 'decide', 'main', 'dose'])
    args = parser.parse_args()
    if args.phase in ['preflight', 'init', 'decide']:
        globals()[args.phase]()
    else:
        study, error = Study(args.phase), None
        try:
            study.execute()
        except Exception as ex:
            error = f'{type(ex).__name__}: {ex}'
            raise
        finally:
            study.close(error)
