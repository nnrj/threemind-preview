"""Capture pre-edit engineering witnesses; never run against formal subjects."""
import hashlib
import json
from pathlib import Path

from threemind_core import Stimulus
from threemind_kernels.local63 import Local63Config
from threemind_kernels.registry import resolve_kernel

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / '.work/kernel63-default-alignment/witnesses'


def main():
    # These are pre-edit witnesses, not fixtures to regenerate with later defaults.
    expected = dict(resource_precheck_enabled=True, subthreshold_expiry_enabled=True,
                    inhibition_updates_usage=False, inhibition_bypasses_resources=True)
    assert all(Local63Config().to_dict()[k] == v for k, v in expected.items()), (
        'Run only on the pre-edit ae252c3e implementation; preserve existing witnesses.'
    )
    OUT.mkdir(exist_ok=False)
    descriptor = resolve_kernel('threemind.continuous-memory/6.3')
    patches = {
        'old-default': {},
        'old-stability': {'consolidation_mode': 'stability', 'novelty_mode': 'immediate'},
        'old-independent': {'separate_inhibition_resources': True, 'inhibition_bypasses_resources': False},
        'old-proportional': {'inhibition_distribution': 'weight-proportional'},
        'old-weak': {},
    }
    for name, patch in patches.items():
        engine = descriptor.create(Local63Config(**patch), backend='native')
        if name == 'old-weak':
            engine.inject(Stimulus(0, ((1, .0001),)))
        else:
            for when, channels in [(0, ((101, .4), (202, .3))), (100000, ((101, .5),)),
                                   (200000, ((202, .2), (303, .6)))]:
                engine.inject(Stimulus(when, channels))
        engine.advance_to(0 if name == 'old-weak' else 900000)
        (OUT / (name+'-before.json')).write_bytes(engine.capture_state().payload)
        engine.advance_to(300000000 if name == 'old-weak' else 2100000)
        (OUT / (name+'-after.json')).write_bytes(engine.capture_state().payload)
    paths = []
    for version in ('60', '61', '62'):
        paths += [ROOT / f'src/threemind_kernels/{name}{version}.py' for name in ('local',)]
        paths += [ROOT / f'src/threemind_kernels/local{version}{suffix}.py' for suffix in ('_config', '_native')]
        paths += [ROOT / f'crates/threemind-core/src/local{version}{suffix}'
                  for suffix in ('.rs', '_transitions.rs', '-defaults.json')]
    paths += [ROOT / 'src/threemind_kernels/decay61.py']
    manifest = {'historical_sources': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in paths if p.exists()},
                'witnesses': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.json')}}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), 'utf8')
    print(json.dumps({'witnesses': len(manifest['witnesses']), 'historical_sources': len(manifest['historical_sources'])}))


if __name__ == '__main__': main()
