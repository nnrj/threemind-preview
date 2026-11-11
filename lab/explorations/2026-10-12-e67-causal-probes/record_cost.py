"""Separate adjunct DB reference overhead from the four-arm main experiment.

The frozen r4 publisher classifies file members by arm. This later read-only
audit also checks resource identity so causal-probe rows cannot be counted as
main-course per-arm overhead. Prior snapshots are retained, never overwritten.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from probe import load_env, ResearchStorage, OperationsClient, read, write, RESOURCE, KEY, HERE


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();load_env();storage=ResearchStorage()
    main_work=storage.workspace_path('2026-10-11-shape-color-kernels')
    project=read(main_work/'platform.json')['project_id']
    experiment=read(main_work/'.research-records/identity.json')['experiment']
    groups={k:dict(entries=0,evidence=0,json_bytes=0) for k in ('2','3.1','4-adaptive','4-legacy','shared','causal-adjunct')}
    def owner(row):
        locator=row.get('locator') or {};key=str(row.get('original_key',''))
        if locator.get('resource_id')==RESOURCE or key.startswith(KEY):return 'causal-adjunct'
        member=str(locator.get('member',''))
        for arm in ('2','3.1','4-adaptive','4-legacy'):
            if key.startswith('arms/'+arm+'/') or key in ('subject:'+arm,'condition:'+arm) or member.startswith(('arms/'+arm+'/', 'replays/'+arm+'/')):
                return arm
        return 'shared'
    with OperationsClient.from_environment(source='ai') as client:
        for kind in ('entries','evidence'):
            offset=0
            while True:
                page=client.call('records.'+kind,{'path':{'project':project,'experiment':experiment},'query':{'offset':offset,'limit':200}})
                for row in page['rows']:
                    group=groups[owner(row)];group[kind]+=1
                    group['json_bytes']+=len(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode('utf-8'))
                if not page['more']:break
                offset+=len(page['rows'])
    output=args.output.resolve();work=storage.workspace_path(HERE.name)
    if not output.is_relative_to(work):raise ValueError('save adjunct audit in its own managed resource')
    value=dict(schema='threemind.e67-record-size/2',time=datetime.now(timezone.utc).isoformat(),groups=groups,
        interpretation='Logical UTF-8 JSON entry/evidence bytes only. Excludes text revisions, receipts, PostgreSQL disk pages/indexes/WAL. Causal adjunct is not main-course cost. This appended audit supersedes resource-blind allocation, without rewriting the old snapshot.')
    with storage.writer(RESOURCE):write(output,value)
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
