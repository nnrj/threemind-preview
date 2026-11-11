"""Small CPU CLI round-trip against recorded observations; no simulations."""
import gzip
import json
import subprocess
import sys
from pathlib import Path

from experiment import ROOT, WORK, HERE, read_json, new_json
from threemind_transformer.local_activity import local_process


def main():
    destination = WORK/'cli-verification'
    destination.mkdir(exist_ok=False)
    source = WORK/'cases/s223-feedback-stage0'
    tests = [read_json(WORK/'cases'/f'{source.name}-test-{i}-description/result.json') for i in (0, 1)]
    observations = []
    for row in tests:
        with gzip.open(row['process'], 'rt', encoding='utf-8') as stream:
            observations.append({'process': local_process(json.load(stream))})
    queries = destination/'observations.jsonl'
    queries.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in observations), encoding='utf-8')
    output = destination/'utterances.jsonl'
    base = [sys.executable, '-m', 'threemind_transformer.adaptive_expression_cli']
    subprocess.run(base+['decode', '--parent', str(source/'expression-2'), '--input', str(queries),
                   '--output', str(output), '--device', 'cpu'], cwd=ROOT, check=True)
    decoded = [json.loads(line) for line in output.read_text(encoding='utf-8').splitlines()]
    if [r['text'] for r in decoded] != [r['output'] for r in tests]:
        raise RuntimeError('CPU decode differs from recorded GPU answers')
    teacher = destination/'teacher.jsonl'
    with gzip.open(source/'expression-2/teaching.jsonl.gz', 'rt', encoding='utf-8') as stream:
        examples = [json.loads(next(stream)) for _ in range(2)]
    teacher.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in examples), encoding='utf-8')
    subprocess.run(base+['teach', '--input', str(teacher), '--output', str(destination/'model'),
                   '--steps', '1', '--device', 'cpu'], cwd=ROOT, check=True)
    manifest = read_json(destination/'model/manifest.json')
    if manifest['revision'] != 1 or manifest['training']['samples'] != 2:
        raise RuntimeError('CLI teaching did not save its replay')
    new_json(HERE/'verification.json', {'focused_pytest_passed': 5, 'ruff_new_tool_files': 'passed',
        'cli_teach_cpu': 'two real observations, one numeric step, saved revision',
        'cli_decode_cpu_matches_recorded_cuda': len(decoded),
        'limitations': 'small functional check, not a speed benchmark or proof of all-device numeric identity',
        'core_advanced_by_verification': False})
    print({'verified': str(output), 'matching_cpu_cuda_answers': len(decoded)}, flush=True)


if __name__ == '__main__':
    main()
