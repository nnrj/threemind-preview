"""Explicit /2 common-body sampling pilot after the /1 structural diagnosis."""
from experiment import WORK, execute, load, save
from lab.tools.ocean_communication import JointCommunicationOcean


def source(seed):
    folder = WORK / 'joint-sources' / str(seed)
    if folder.exists():
        return folder
    old = load(WORK / 'sources' / str(seed))
    if old.time_us != 0 or old.packets:
        raise ValueError('this pilot must begin at the saved pre-exposure source')
    protocol = old.p.model_dump(by_alias=True) | {'schema': 'threemind.ocean-communication/2'}
    state = old.capture()
    state['schema'] = JointCommunicationOcean.state_schema
    state['coverage']['material']['enclosure']['group']['community']['world']['protocol'] = protocol
    new = JointCommunicationOcean(protocol, state=state, images={i: e.capture_state() for i, e in old.engines.items()})
    new.research['common_sample_pilot'] = {
        'source': str(WORK / 'sources' / str(seed)), 'time_us': 0,
        'change': 'explicit common-body observation; original channel values and mapping retained',
        'scope': 'new independent world, not an in-place upgrade'}
    save(new, folder)
    return folder


def main():
    from batch import stage
    for seed in (0, 1):
        name = f's{seed}-joint-development'
        if not (WORK / 'cases' / name / 'result.json').exists():
            execute(source(seed), name, 30, checkpoint_seconds=20)
    for seed in (0, 1):
        stage(WORK / f'cases/s{seed}-joint-development/checkpoints/20000000', f's{seed}-joint-muted', 10, 'muted')


if __name__ == '__main__':
    main()
