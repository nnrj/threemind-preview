"""Read selected events from closed ocean Arrow chunks, including live studies.

Only time/event columns are decoded. Partial chunks and all Core states are left
alone. A caller-owned cursor avoids repeatedly reading growing evidence files.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from pyarrow import ipc


def read_events(folder, *, kinds=(), after=None):
    folder=Path(folder).resolve();found=[];last=after;through=None;count=0
    for path in sorted((folder/'inputs').glob('*.arrow')):
        if after is not None and path.name<=after:continue
        with ipc.open_file(path,options=ipc.IpcReadOptions(included_fields=[0,2])) as reader:
            table=reader.read_all()
        for text in table.column('events').to_pylist():
            found.extend(e for e in json.loads(text) if not kinds or e['kind'] in kinds)
        if table.num_rows:through=table.column('time_us')[-1].as_py()
        last=path.name;count+=1
    return {'folder':str(folder),'last_chunk':last,'through_us':through,
            'new_chunks':count,'events':found}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording',type=Path)
    parser.add_argument('--kind',action='append',default=[])
    parser.add_argument('--cursor',type=Path,help='Optional separate caller-owned JSON cursor')
    args=parser.parse_args();prior=None
    if args.cursor and args.cursor.exists():
        prior=json.loads(args.cursor.read_bytes())
        if prior['folder']!=str(args.recording.resolve()) or prior['kinds']!=sorted(args.kind):
            raise ValueError('cursor belongs to a different recording or event filter')
    result=read_events(args.recording,kinds=args.kind,after=prior['last_chunk'] if prior else None)
    if args.cursor:
        state={k:v for k,v in result.items() if k!='events'}
        state['kinds']=sorted(args.kind)
        if state['through_us'] is None and prior:state['through_us']=prior['through_us']
        args.cursor.parent.mkdir(parents=True,exist_ok=True)
        staging=args.cursor.with_suffix('.tmp')
        staging.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
        staging.replace(args.cursor)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
