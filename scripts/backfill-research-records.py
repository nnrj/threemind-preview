"""Explicit inventory / preview / apply for preserved historical research.

Apply requires a verified complete backup and a completed isolated restore
witness. It never starts a worker, model or simulation.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lab.tools.historical_record_backfill import backfill_one
from lab.tools.historical_record_inventory import scan_sources
from threemind_lab.config import Settings
from threemind_lab.database import Database
from threemind_lab.research_records import digest
from threemind_lab.storage_backup import inspect
from threemind_lab.storage_files import atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inventory', 'preview', 'apply'))
    parser.add_argument('--directory', type=Path, default=Path('data/records-backfill-20261010'))
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--restore-witness', type=Path)
    parser.add_argument('--source', action='append', help='Only these explicitly named source keys; otherwise all')
    args = parser.parse_args()
    settings = Settings.from_env()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    database = Database(settings.database_url)
    try:
        if args.action == 'inventory':
            inventory = scan_sources(database)
            atomic_json(directory / 'inventory.json', inventory)
            print(json.dumps({'items': len(inventory['items']), 'hash': inventory['inventory_hash'],
                'projects': len(inventory['projects']), 'files': sum(len(i['files']) for i in inventory['items'])}))
            return
        inventory = json.loads((directory / 'inventory.json').read_bytes())
        expected = inventory['inventory_hash']
        if digest({k: v for k, v in inventory.items() if k != 'inventory_hash'}) != expected:
            raise ValueError('reviewed inventory hash differs; regenerate and review explicitly')
        if args.action == 'apply':
            if not args.backup or not args.restore_witness:
                raise ValueError('apply requires --backup and --restore-witness')
            backup = inspect(args.backup)
            witness = json.loads(args.restore_witness.read_bytes())
            if witness.get('backup_id') != backup['id'] or witness.get('state') != 'restoration-verified':
                raise ValueError('completed full backup recovery witness is required')
            database.require_current_schema()
        requested = set(args.source or ())
        known = {source['source_key'] for source in inventory['items']}
        if requested - known:
            raise ValueError('unknown reviewed source key: ' + ', '.join(sorted(requested - known)))
        priority = [
            'lab-exploration:2026-10-08-centered-restart',
            'lab-exploration:2026-10-08-centered-learning',
            'lab-exploration:2026-10-08-centered-correction-cycles',
            'lab-exploration:2026-10-08-retention-kernel',
            'lab-exploration:2026-10-08-retention-repair',
            'lab-exploration:2026-10-08-retention-telemetry-text',
            'lab-exploration:2026-10-09-local-events-v4',
        ]
        order = {key: i for i, key in enumerate(priority)}
        sources = sorted(inventory['items'], key=lambda source: (
            order.get(source['source_key'], len(order)), source.get('experiment_date') or '', source['source_key']))
        results = []
        for source in sources:
            if args.source and source['source_key'] not in args.source:
                continue
            result = backfill_one(database, source, expected, directory / args.action,
                                  preview_only=args.action == 'preview')
            results.append(result)
            atomic_json(directory / (args.action + '-results.json'), results)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        database.close()


if __name__ == '__main__':
    main()
