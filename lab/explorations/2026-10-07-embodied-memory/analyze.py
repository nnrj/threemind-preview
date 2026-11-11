"""Small derived summaries only; never rewrites source cases or Core state."""
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from lab.tools.classroom_eye import DetailedClassroom
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/embodied-memory-20261007'


def read(path):return json.loads(path.read_bytes())


def state(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)


def main():
    cases={p.parent.name:read(p) for p in sorted((WORK/'cases').glob('*/result.json'))}
    previous=read(HERE/'results.json') if (HERE/'results.json').exists() else {}
    # Case folders cannot be overwritten by this runner. Reuse already derived
    # state comparisons rather than repeatedly reading large historical states.
    differences=previous.get('state_differences',{});world=DetailedClassroom(resolution=4);teacher=set(world.channels[264:270]);visual=set(world.channels[:256])
    for seed in (223,279):
        for plasticity in (0,1):
            for delay in (0,6,30):
                key=f's{seed}-p{plasticity}-d{delay}'
                if key in differences:continue
                paths=[WORK/f'cases/C-s{seed}-p{plasticity}-h{h}-d{delay}/checkpoint.json.gz' for h in (0,1)]
                if not all(p.exists() for p in paths):continue
                states=[state(p)['core'] for p in paths]
                nodes=[{int(n['channel']):n for n in s['nodes']} for s in states]
                row={}
                for group,channels in [('teacher',teacher),('visual',visual),('all',set(nodes[0])|set(nodes[1]))]:
                    row[group]={field:sum(abs(float(nodes[0].get(c,{}).get(field,0))-float(nodes[1].get(c,{}).get(field,0))) for c in channels)
                                for field in ('activation','inhibition')}
                row['edges']=[len(s['edges']) for s in states]
                differences[key]=row
    command_effects={}
    for key,value in cases.items():
        if not key.startswith('C-') or 'predictions' not in value:continue
        # Same eye/body input before the first selected movement; merely derive
        # the actual existing executor's first force, never a target label.
        from lab.tools.shape_color_world import POSITIONS,Pointer
        forces=[]
        for preds in value['predictions']:
            forces.append([Pointer(.1,-.15).teacher_action(POSITIONS[p]).tolist() for p in preds])
        command_effects[key]={'history_changed_first_commands':int(np.any(np.asarray(forces[0])!=forces[1],axis=1).sum()),
            'n_pairs':len(forces[0]),'forces_from_recorded_choices_at_common_body':forces,
            'scope':'executor command at explicit common pose, not a new closed-loop trajectory'}
    for seed in (223,279):
        baseline=command_effects.get(f'C-s{seed}-p1-d6-refit-saved-layout')
        if baseline:
            reference=np.asarray(baseline['forces_from_recorded_choices_at_common_body'])
            for mode in ('silence','rescue','teacher-swap','connections-swap'):
                row=command_effects.get(f'C-s{seed}-d6-{mode}-score')
                if row:
                    row['commands_changed_from_normal']=int(np.any(np.asarray(row['forces_from_recorded_choices_at_common_body'])!=reference,axis=2).sum())
    donor_following={}
    for seed in (223,279):
        normal=cases.get(f'C-s{seed}-p1-d6-refit-saved-layout')
        swapped=cases.get(f'C-s{seed}-d6-connections-swap-score')
        if normal and swapped:
            before=np.asarray(normal['predictions']);after=np.asarray(swapped['predictions'])
            donor=np.asarray(normal['targets'])[::-1];changed=before!=after
            donor_following[f's{seed}']={'n':int(before.size),'before_matches':int((before==donor).sum()),
                'after_matches':int((after==donor).sum()),'changed_choices':int(changed.sum()),
                'changed_toward_donor':int((changed & (after==donor)).sum()),
                'changed_away_from_donor':int((changed & (before==donor)).sum())}
    temporal_transfer=previous.get('frozen_six_second_reader_across_delays',{})
    from lab.tools.spatial_choice import SpatialChoice
    from lab.tools.choice_attribution import paired_scores
    import torch
    torch.set_num_threads(2)
    for seed in (223,279):
        folder=WORK/f'cases/C-s{seed}-p1-d6-refit-saved-layout/controller'
        if not folder.exists():continue
        head,_=SpatialChoice.restore(folder)
        for delay in (0,6,30):
            if f's{seed}-d{delay}' in temporal_transfer:continue
            paths=[WORK/f'cases/C-s{seed}-p1-h{h}-d{delay}-test-normal/features.npz' for h in (0,1)]
            if not all(p.exists() for p in paths):continue
            data=[np.load(p) for p in paths]
            preds=[head.predict(d['activity']).argmax(-1).tolist() for d in data]
            targets=[d['y'].tolist() for d in data]
            temporal_transfer[f's{seed}-d{delay}']=paired_scores(preds,targets)|{
                'reader':'frozen six-second calibration; no further fit','predictions':preds,'targets':targets}
    pointing={}
    for kind in ('activity','incoming'):
        path=WORK/f'cases/A-fit-{kind}/predictions.json'
        if path.exists():
            rows=read(path)
            pointing[kind]={cat:{'n':sum(r['category']==cat for r in rows),
                'nearest_object_correct':sum(r['category']==cat and r['correct'] for r in rows),
                'arrived_within_0_20m':sum(r['category']==cat and r['target_distance']<=.20 for r in rows)}
                for cat in ('color','shape','pair')}
    stopped={p.parent.name:read(p) for p in (WORK/'cases').glob('*/stopped.json')}
    completed_seconds=sum(c['wall_seconds'] for c in cases.values())
    failed_seconds=sum(c['wall_seconds'] for c in stopped.values())
    amendment=WORK/'compute-budget-amendment.json'
    result={'schema':'E58-results/1','cases':cases,'state_differences':differences,'derived_first_commands':command_effects,
        'connection_transfer_donor_following':donor_following,
        'physical_pointing':pointing,
        'frozen_six_second_reader_across_delays':temporal_transfer,
        'stopped':stopped,
        'completed_stages':len(cases),'compute_minutes':completed_seconds/60,
        'compute_including_failed_minutes':(completed_seconds+failed_seconds)/60,
        'compute_budget_amendment':read(amendment) if amendment.exists() else None,
        'created':read(WORK/'instances.json')['created'],
        'local_bytes':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file())}
    (HERE/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('completed_stages','compute_minutes','created','local_bytes')},ensure_ascii=False))
    for key,value in cases.items():
        if 'correct' in value or 'conditions' in value:print(key,json.dumps({k:value[k] for k in ('correct','n','paired_both_correct','frozen_new_correct','conditions') if k in value},ensure_ascii=False))


if __name__=='__main__':main()
