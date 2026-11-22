"""Read-only verification using the same canonical hash as saved StateImage IDs."""
import gzip
import json
import statistics

from threemind_core import StateImage
from bench import HERE, WORK, numerical, sha


def main():
    directory=WORK/'diagnostic'
    assert not (directory/'in-flight.json').exists()
    manifest=json.loads((directory/'manifest.json').read_text('utf8'))
    for name,expected in manifest.items():assert sha((HERE/name).read_bytes())==expected,name
    rows=[json.loads(line) for line in (directory/'rows.jsonl').read_text('utf8').splitlines()]
    assert len(rows)==40
    for row in rows:
        data=gzip.decompress((directory/row['state_file']).read_bytes())
        assert StateImage(data).digest==row['state_sha256']
        assert numerical(json.loads(data))==row['numerical_sha256']
    summaries={}
    profiles={}
    for case in ('native-weak128','python-weak32'):
        summaries[case]={}
        for expiry,retain in ((False,False),(True,False),(False,True),(True,True)):
            sample=[r for r in rows if r['case']==case and r['trial']>0 and r['expiry']==expiry and r['retain']==retain]
            assert len(sample)==4 and len({r['numerical_sha256'] for r in sample})==1
            name=f'{int(expiry)}{int(retain)}'
            summaries[case][name]={'expiry':expiry,'retain':retain,
                'median_seconds':statistics.median(r['advance_seconds'] for r in sample),
                'nodes':sample[0]['nodes'],'audit':sample[0]['audit']}
            if 'profile' in sample[-1]:
                profiles[name]=[p for p in sample[-1]['profile'] if p['function'] in (
                    '_node_timers','_expiry','_base_expiry','_delete_node','_settle_node','_project_node',
                    '_ensure_node','set','discard','_receive')]
    result={'cases':summaries,'verified_states':len(rows),'profiles':profiles,
            'rows_sha256':sha((directory/'rows.jsonl').read_bytes()),
            'verification_note':'StateImage IDs use canonical hashes. The frozen runner compared raw bytes at its final read-only audit; this verifier corrects that audit without rerunning measurements.'}
    (HERE/'diagnostic-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(summaries))


if __name__=='__main__':main()
