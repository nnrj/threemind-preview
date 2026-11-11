"""Compact final inventory from existing screens and immutable receipts."""
from collections import defaultdict
from experiment import HERE, ROOT, WORK
from lab.tools.ocean_cli import read_json, write_json


def main():
    catalog=read_json(WORK/'turning-catalog-014.json')
    by_identity=defaultdict(list)
    for item in catalog['candidates']:
        by_identity[item['study'],item['individual']].append(item)
    identities=[]
    for (study,i),items in sorted(by_identity.items()):
        observations={}
        for item in items:
            for e in item['events']:
                key=(e['time_us'],e['turn_degrees'],e['alignment_after'])
                observations.setdefault(key,{'event':e,'cases':[]})['cases'].append(item['case'])
        identities.append({'study':study,'individual':i,'snapshots':len(items),
            'observations':list(observations.values()),
            'library_ids':[x['library_id'] for x in items if x['saved']]})
    # Include later capture events: an early turning snapshot is not the entire
    # lifetime. Any matching identity would still require a same-branch check.
    both=[]
    for study,base in [('E37',ROOT/'.work/ocean-enclosure-20261004'),('E38',WORK)]:
        for path in sorted((base/'cases').glob('*/events.json')):
            for event in read_json(path):
                if event['kind']!='body_engulfed':continue
                key=(study,event['predator'])
                if key in by_identity:
                    both.append({'study':study,'case':path.parent.name,'capture':event,
                        'turning_cases':[x['case'] for x in by_identity[key]],
                        'requires_same_branch_review':True})
    out={'schema':'threemind.turning-candidate-summary/1',
        'archive_count':sum(x['saved'] for x in catalog['candidates']),
        'source_identity_count':len(identities),
        'identity_scope':'study + source individual; matched branches share a source identity',
        'source_catalog':str(WORK/'turning-catalog-014.json'),
        'identities':identities,'cross_segment_capture_matches':both,
        'stable_foraging_causally_tested':False,'core_modified':False}
    write_json(HERE/'turning-results.json',out)
    print({'archives':out['archive_count'],'identities':len(identities),'capture_matches':len(both)})


if __name__=='__main__':main()
