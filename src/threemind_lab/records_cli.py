"""The same research-record service used by UI and the operation/MCP catalog."""

import argparse
import json
import sys
from datetime import date
from uuid import UUID, uuid4

import httpx

from .data_cli import connect, connection, read_object


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('list', 'detail', 'register', 'append', 'attach', 'text', 'finalize', 'verify',
                                           'backfill-plan', 'backfill-apply', 'receipt', 'entries', 'evidence', 'preview'))
    connection(parser)
    parser.add_argument('--project', type=UUID)
    parser.add_argument('--experiment', type=UUID)
    parser.add_argument('--batch', type=UUID)
    parser.add_argument('--evidence', type=UUID)
    parser.add_argument('--json', help='Bounded JSON request file')
    parser.add_argument('--query', default='')
    parser.add_argument('--kernel', default='')
    parser.add_argument('--status', default='')
    parser.add_argument('--coverage', default='')
    parser.add_argument('--executor', default='')
    parser.add_argument('--classification', default='', choices=('formal', 'proposal', 'calibration', 'development'))
    parser.add_argument('--from-date', type=date.fromisoformat)
    parser.add_argument('--through-date', type=date.fromisoformat)
    parser.add_argument('--kind', help='Entry kind filter for entries')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--hashes', action='store_true')
    args = parser.parse_args(argv)
    reads = {'list', 'detail', 'verify', 'receipt', 'entries', 'evidence', 'preview'}
    body = read_object(args.json) if args.json else None
    request = args.request_id or (UUID(body['request_id']) if body and body.get('request_id') else uuid4())
    try:
        path = {}
        if args.action != 'list':
            if not args.project:
                raise ValueError('--project is required')
            path['project'] = str(args.project)
        if args.action in ('detail', 'append', 'attach', 'text', 'finalize', 'verify', 'entries', 'evidence'):
            if not args.experiment:
                raise ValueError('--experiment is required')
            path['experiment'] = str(args.experiment)
        if args.action == 'backfill-apply':
            if not args.batch:
                raise ValueError('--batch is required')
            path['batch'] = str(args.batch)
        if args.action == 'preview':
            if not args.evidence:
                raise ValueError('--evidence is required')
            path['evidence'] = str(args.evidence)
        if args.action == 'receipt':
            if not args.request_id:
                raise ValueError('--request-id is required for a receipt')
            path['request_id'] = str(args.request_id)
        arguments = {'path': path}
        if args.action == 'list':
            arguments['query'] = {k: v for k, v in {'project': str(args.project) if args.project else None,
                'query': args.query, 'kernel': args.kernel, 'status': args.status, 'coverage': args.coverage,
                'executor': args.executor, 'classification': args.classification,
                'from_date': args.from_date.isoformat() if args.from_date else None,
                'through_date': args.through_date.isoformat() if args.through_date else None,
                'offset': args.offset, 'limit': args.limit}.items() if v is not None}
        elif args.action == 'verify':
            arguments['query'] = {'hashes': args.hashes}
        elif args.action in ('entries', 'evidence', 'preview'):
            arguments['query'] = {'offset': args.offset, 'limit': args.limit}
            if args.action == 'entries' and args.kind:
                arguments['query']['kind'] = args.kind
        if args.action not in reads:
            if body is None:
                raise ValueError('--json request file is required')
            body = dict(body)
            body['request_id'] = str(request)
            arguments['body'] = body
            print(f'request_id={request}', file=sys.stderr, flush=True)
        with connect(args) as client:
            result = client.call('records.' + args.action.replace('-', '_'), arguments, request_id=request)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, httpx.HTTPError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
