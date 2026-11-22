"""Separately recalculate behavioral scores from saved positions, not result scores."""
import math
import apparatus as a
import study

def main():
    report=a.read(a.WORK/'analysis-v1/analysis.json')
    checked=0
    for row in report['behavior']:
        folder=a.WORK/'science'/row['material']/row['profile']/row['state']/row['motor']
        region=[];stationary=[];distances=[]
        for j in (0,1):
            trace=a.read(folder/f'start{j}/trajectory.json.gz')['rows']
            region.append(sum(.5<=t['body']['x']<1 for t in trace)/600)
            stationary.append(sum(abs(t['body']['v'])<1e-6 for t in trace)/600)
            # Reconstruct path from saved velocity and applied force using the
            # analytical damped-motion integral; no result.json values used.
            distances.append(sum(abs(.375*t['applied']*.1 +
                (t['body']['v']-.375*t['applied'])*(1-math.exp(-.08))/.8) for t in trace))
        mean=sum(region)/2
        assert abs(mean-row['region1'])<1e-12
        target=1-mean if row['history']==0 else mean
        assert abs(target-row['target'])<1e-12
        assert abs(sum(stationary)/2-row['mean_stationary'])<1e-12
        assert abs(sum(distances)/2-row['mean_travel'])<1e-12
        checked+=1
    assert checked==96
    # Read the source corpus again: alignment tables must not be invented from
    # final outcomes, and version input fixtures must remain exact.
    for seed in a.SEEDS:
        for idx in a.HISTORIES:
            source=a.material(seed,idx)
            assert source==a.read(a.WORK/'materials'/f's{seed}-c{idx}.json.gz')
    study.frozen_check()
    a.save(a.WORK/'analysis-v1/independent-check.json',{'passed':True,'behavior_rows':checked,
        'recomputed_from':'saved body positions, velocities and applied controls',
        'source_bindings_rechecked':True,'scope':'separate calculation by the same assistant; not external replication'})
    print('Verified 96 aggregate rows from 192 complete position/control traces and all source bindings.')

if __name__=='__main__':main()
