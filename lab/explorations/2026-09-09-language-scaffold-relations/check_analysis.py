"""Nontrivial observer checks: role direction, crossed truth and missing channels."""
import copy
from analyze import family_scores, who_score


def check():
    names=['X','Y','Z','U','V','W']
    rows=[]
    for g,p,c,other,other_p in [('X','Y','Z','U','V'),('U','V','W','X','Y')]:
        rows += [
            {'cue':c+'的爷爷是谁？','net_endpoint':{g:1.,p:.2,other:.1,other_p:.1}},
            {'cue':c+'的父亲是谁？','net_endpoint':{g:.1,p:.9,other:.1,other_p:.1}},
            {'cue':c,'net_endpoint':{g:.05,p:0.,other:.05,other_p:0.}},
        ]
    case={'names':names,'arm':'full','measurements':{'family':{'rows':rows},'who':{'rows':[
        {'cue':'松子是谁？','net_endpoint':{'甲':.8,'乙':.1}},
        {'cue':'铃铛是谁？','net_endpoint':{'甲':.2,'乙':.9}},
    ]}}}
    score=family_scores(case)[0]
    assert abs(score['role']-1.6)<1e-12
    assert abs(score['query_vs_bare']-.9)<1e-12
    assert abs(score['target_margin']-.8)<1e-12
    assert abs(who_score(case)-.7)<1e-12
    crossed=copy.deepcopy(case)
    crossed['arm']='crossed_chain'
    # Reversing the chain changes the expected grandfather, never the observed activities.
    assert family_scores(crossed)[0]['expected_grandfather']=='U'
    assert family_scores(crossed)[0]['target_margin']<0
    missing=copy.deepcopy(case)
    missing['measurements']['family']['rows'][0]['net_endpoint']['X']=None
    assert family_scores(missing)[0]['role'] is None
    assert family_scores(missing)[0]['target_margin'] is None
    print('Observer direction, crossed-chain truth and missingness checks passed.')


if __name__=='__main__':
    check()
