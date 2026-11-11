"""Explicitly recorded resource amendment, preserving the initial registration."""
import time
from experiment import WORK,read_json,new_json,encoded


def main():
    if len([p for p in (WORK/'cases').glob('s*-dt*/result.json') if read_json(p).get('kind')=='source'])!=12:
        raise RuntimeError('finish the original timing stage before applying this revision')
    path=WORK/'platform.json';meta=read_json(path)
    revision=WORK/'resource-revision-1.json'
    if revision.exists():
        if meta['settings']['storage_soft']!=4*2**30:raise RuntimeError('partial budget revision')
        print('budget revision already recorded');return
    new_json(WORK/'platform-initial.json',meta)
    updated=read_json(path)
    updated['settings']['storage_soft']=4*2**30
    updated['settings']['storage_hard']=12*2**30
    new_json(revision,{'date':'2026-10-05','recorded_at_epoch':time.time(),'reason':'resource-amendment.zh.md',
        'original':meta['settings'],'revised':updated['settings'],'experiment_criteria_changed':False})
    staging=WORK/'platform-revised.tmp';staging.write_bytes(encoded(updated));staging.replace(path)
    print('working4GiB / total12GiB, original registration preserved')


if __name__=='__main__':main()
