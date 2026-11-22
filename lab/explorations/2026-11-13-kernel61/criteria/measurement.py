"""Historical cross-system measurements with an added teaching-only Core match audit."""
import rig as g
m = g.m

def save(folder, name, rig):
    p = folder/(name+'.json.gz')
    receipt = m.original(p, rig.save(), compressed=True)
    return {'path': p.name, 'time_us': rig.time, **receipt}



def x3(folder, origin, kind):
    seed=g.case_seed('X3',origin)
    history_tests=[]
    for history in (0,1):
        p=g.Rig(kind,seed); records=g.teaching(p,history)
        save(folder,f'h{history}-parent',p)
        selection=(g.rnn_selection(p,records) if kind=='fixed-rnn-reader' else
                   g.matching(p,records) if kind=='threemind' else None)
        m.original(folder/f'h{history}-selection.json',selection or {'kind':kind,'defined_by':'declared XY/ZW interfaces'})
        cells={}
        for arm in ('intact','sham','target','matched','restored','all'):
            c,receipt=g.intervene(p,arm,selection)
            m.original(folder/f'h{history}-{arm}-intervention.json',receipt)
            save(folder,f'h{history}-{arm}-initial',c)
            for cue in ('X',''):
                child=c.fork(cue or 'none')
                result=g.probe(child,cue)
                save(folder,f'h{history}-{arm}-{cue or "none"}-final',child)
                cells[arm+'-'+(cue or 'none')]=result
        temporal={}
        for arm in ('intact','all'):
            for first,second in (('',''),('X',''),('','Y'),('X','Y')):
                c,_=g.intervene(p,arm,selection)
                result=g.probe(c,first,second=second)
                name=arm+'-'+(first or '0')+(second or '0')
                temporal[name]=result
                save(folder,f'h{history}-temporal-{name}',c)
        history_tests.append({'history':history,'selection':selection,'cells':cells,'temporal':temporal})
    # Distinct continuous closed-loop lives. No diagnostic result is fed back into them.
    worlds={}
    for sequence in ('PPP','PQP','QQQ','QPQ'):
        r=g.Rig(kind,seed); r.tick(0,{'K':.2})
        save(folder,sequence+'-birth',r)
        stages=[]
        for index,env in enumerate(sequence):
            start=r.save()
            stage=g.ring_stage(r,env)
            save(folder,f'{sequence}-stage{index+1}',r)
            diagnostics={}
            for cue in ('X',''):
                c=r.fork('uniform-diagnostic-'+(cue or 'none'))
                c.body={'x':.3125,'v':0.,'gate':0}
                diagnostics[cue or 'none']=g.probe(c,cue)
                save(folder,f'{sequence}-stage{index+1}-diagnostic-{cue or "none"}',c)
            if index==1:
                replay=g.Rig.restore(start); replay_reverse=g.Rig.restore(start); closed_reverse=g.Rig.restore(start)
                replay_report=g.ring_stage(replay,env,replay=stage['input_frames'])
                replay_reverse_report=g.ring_stage(replay_reverse,env,sign=-1,replay=stage['input_frames'])
                reverse_report=g.ring_stage(closed_reverse,env,sign=-1)
                for name,child in (('replay',replay),('replay-reversed',replay_reverse),('closed-reversed',closed_reverse)):
                    save(folder,f'{sequence}-stage2-{name}',child)
                stage['loop_audit']={'replay_model_equal': replay.save()['model']==r.save()['model'],
                    'reversed_replay_model_equal': replay.save()['model']==replay_reverse.save()['model'],
                    'closed_reversal_inputs_differ': reverse_report['input_frames']!=stage['input_frames'],
                    'closed_reversal_model_differs':closed_reverse.save()['model']!=r.save()['model'],
                    'replay':replay_report,'reversed_replay':replay_reverse_report,'closed_reversed':reverse_report}
            stages.append({'world':stage,'diagnostics':diagnostics})
        worlds[sequence]=stages
    return {'package':'X3','origin':origin,'kind':kind,'valid':True,
            'histories':history_tests,'worlds':worlds}
