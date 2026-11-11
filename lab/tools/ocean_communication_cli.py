"""CLI for complete-habitat signalling; Python callers use the same classes."""
import argparse
import gzip
import json
from pathlib import Path

from lab.tools.ocean_cli import read_json
from lab.tools.ocean_communication import CommunicationOcean, CommunicationProtocol, JointCommunicationOcean, JointCommunicationProtocol, load
from lab.tools.ocean_contact_cli import run, save


def run_recorded(world, folder, seconds, **options):
    """Ordinary ocean advancement plus a read-only, replayable acoustic journal."""
    process = None
    advance = world.step

    def step(record=None):
        def observed(row):
            nonlocal process
            if record:
                record(row)
            if not (row['communication']['emitted'] or row['communication']['received']):
                return
            if process is None:
                process = gzip.open(folder / 'communication.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1)
            members = []
            for identity, body in world.bodies.items():
                if not body.physical:
                    continue
                engine = world.engines[identity]
                nodes, hearing = engine.observation_nodes(), world.hearing_channels(identity)
                members.append({'id': identity, 'cohort': world.cohorts[identity], 'position': body.position,
                                'action': world.action(identity), 'grains': body.grains, 'captured': body.captured,
                                'active_nodes': sum(n['activation'] > 0 for n in nodes),
                                'hearing_activation': sum(n['activation'] for n in nodes if n['channel'] in hearing)})
            process.write(json.dumps({'time_us': row['time_us'], 'members': members,
                                      **row['communication']}, separators=(',', ':')) + '\n')
        return advance(observed)

    world.step = step
    try:
        return run(world, folder, seconds, **options)
    finally:
        world.step = advance
        if process:
            process.close()
        elif folder.exists() and not (folder / 'communication.jsonl.gz').exists():
            # A silent world is a valid, empty observation, not a missing file.
            with gzip.open(folder / 'communication.jsonl.gz', 'wt', encoding='utf-8'):
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    template = sub.add_parser('template')
    template.add_argument('--joint-body-sample', action='store_true')
    init = sub.add_parser('init')
    init.add_argument('protocol', type=Path)
    init.add_argument('output', type=Path)
    go = sub.add_parser('run')
    go.add_argument('snapshot', type=Path)
    go.add_argument('output', type=Path)
    go.add_argument('--seconds', type=float, required=True)
    go.add_argument('--wall-seconds', type=int, default=7200)
    go.add_argument('--hearing', choices=['live', 'muted', 'scrambled'])
    args = parser.parse_args()
    if args.command == 'template':
        model = JointCommunicationProtocol if args.joint_body_sample else CommunicationProtocol
        print(model().model_dump_json(by_alias=True, indent=2))
    elif args.command == 'init':
        protocol = read_json(args.protocol)
        model = JointCommunicationOcean if protocol.get('schema') == 'threemind.ocean-communication/2' else CommunicationOcean
        world = model(protocol)
        world.configure({i: str(i % 3) for i in world.bodies}, {str(k): 'core' for k in range(min(3, len(world.bodies)))}, cross_only=True)
        save(world, args.output)
    else:
        if args.seconds <= 0 or args.wall_seconds <= 0:
            parser.error('positive durations required')
        world = load(args.snapshot)
        if args.hearing:
            world.research['hearing_control'] = {'time_us': world.time_us, 'from': world.p.hearing_mode,
                                                'to': args.hearing, 'scope': 'other individuals only'}
            world.p = world.protocol_model.model_validate(world.p.model_dump(by_alias=True) | {'hearing_mode': args.hearing})
        result = run_recorded(world, args.output, args.seconds, wall_seconds=args.wall_seconds,
                              trajectory_interval_us=200000, activity_interval_us=1000000)
        print({k: result[k] for k in ('status', 'error', 'observed_us', 'wall_seconds', 'communication')})


if __name__ == '__main__':
    main()
