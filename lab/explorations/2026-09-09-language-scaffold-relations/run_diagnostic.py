"""Execute the amendment exactly; no condition selection based on name scores."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from run import HERE, WORK, META, ARMS, Study, curriculum, protocols, encoded


def execute(long=False):
    phase = 'long' if long else 'main'
    study = Study(phase)
    error = None
    try:
        assert hashlib.sha256((HERE/'amendment.md').read_bytes()).hexdigest() == study.meta['amendment_sha256']
        study.impl['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        study.impl['curriculum_harness_sha256'] = hashlib.sha256((HERE/'run.py').read_bytes()).hexdigest()
        if long and study.previous > 1000:
            raise RuntimeError('not enough reserved time for the optional long course')
        cases = [(41601,24,'full')] if long else [(s,8,a) for s in range(41601,41605) for a in ARMS]
        journal = WORK/f'{phase}-cases.jsonl'
        if journal.exists():
            raise RuntimeError('diagnostic journal already exists')
        for seed, rounds, arm in cases:
            study.refresh_budget()
            sentences, names = curriculum(seed,0,rounds,arm)
            run, cp = study.train(seed,sentences,f'diagnostic/{seed}/n{rounds}/{arm}',arm!='learning_off')
            measurements = {k:study.probe(run,cp,p) for k,p in protocols(names,[1.0]).items()}
            if arm=='full':
                measurements['continuous_family'] = study.probe(run,cp,protocols(names,[1.0],'continuation')['family'])
            row = {'seed':seed,'family':0,'n':rounds,'arm':arm,'names':names,'sentence_count':len(sentences),
                   'corpus_sha256':hashlib.sha256(encoded(sentences)).hexdigest(),'measurements':measurements,
                   'uncalibrated_diagnostic':True}
            study.rows.append(row)
            with journal.open('ab') as stream:
                stream.write(json.dumps(row,ensure_ascii=False,default=str).encode()+b'\n')
            print(f'{phase} {len(study.rows)}/{len(cases)}; {time.monotonic()-study.started:.1f}s; '
                  f'{study.estimated/1024**2:.1f} MiB',flush=True)
    except Exception as ex:
        error = f'{type(ex).__name__}: {ex}'
        raise
    finally:
        study.close(error)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--long',action='store_true')
    execute(parser.parse_args().long)
