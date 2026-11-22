"""Original X1 teaching, research copies and seven-arm measurement on 6.1."""
import copy
import transfer_rig as g
m = g.m
ARMS = ('intact', 'sham', 'target-bundle', 'matched-bundle', 'persistent', 'fast', 'restored')
CUES = ('X', 'Y', 'XY', 'Z', 'W', 'ZW')

def save(folder, name, rig):
    p = folder/(name+'.json.gz')
    receipt = m.original(p, rig.save(), compressed=True)
    return {'path': p.name, 'time_us': rig.time, **receipt}


def x1(folder, origin):
    seed = g.case_seed('X1',origin)
    parents, matches = {}, {}
    for history in (0,1):
        p = g.Rig('threemind',seed)
        records = g.teaching(p,history,(.36,.40,.44,.48)[origin//2])
        save(folder,f'parent-h{history}-before-settlement',p)
        g.settle(p)
        save(folder,f'parent-h{history}',p)
        parents[history] = p
        matches[history] = g.matching(p,records)
        m.original(folder/f'teaching-observation-h{history}.json',records)
    m.original(folder/'matching.json',matches)
    if not all(v['passed'] for v in matches.values()):
        return {'package':'X1','origin':origin,'valid':False,'matching':matches,'trials':[]}
    trials = []
    for history in (0,1):
        parent, donor = parents[history], parents[1-history]
        for arm in ARMS:
            if arm == 'intact': child, receipt = parent.fork(arm), {'arm':arm}
            elif arm == 'sham': child,receipt = g.transfer(parent,parent)
            elif arm == 'matched-bundle': child,receipt = g.transfer(parent,donor,'ZW')
            else:
                child,receipt = g.transfer(parent,donor,mode=arm if arm in ('persistent','fast') else 'bundle')
                if arm == 'restored': child,_ = g.transfer(child,parent)
            initial = child.save()
            comparable = copy.deepcopy(initial); comparable['branch'] = parent.branch
            if arm in ('intact','sham','restored') and comparable != parent.save():
                raise RuntimeError('sham/reversal differs from intact whole state')
            m.original(folder/f'h{history}-{arm}-intervention.json',receipt)
            save(folder,f'h{history}-{arm}-initial',child)
            for cue in CUES:
                c = child.fork(cue)
                result = g.probe(c,cue,gate=True)
                checkpoint = save(folder,f'h{history}-{arm}-{cue}-final',c)
                goal = (-1 if history == 0 else 1) # donor X and recipient Z have the same output sign
                trials.append({'history':history,'arm':arm,'cue':cue,'goal':goal,
                               'success': result['choice'] == goal,'result':result,'checkpoint':checkpoint})
    return {'package':'X1','origin':origin,'valid':True,'matching':matches,'trials':trials}
