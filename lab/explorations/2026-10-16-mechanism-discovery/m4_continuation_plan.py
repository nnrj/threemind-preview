"""Read-only M4 stage ordering; no tensor libraries, engines or state mutation."""
import pilot_m2 as m
ARMS=('sham','eye','hand','matched-eye','matched-hand','restored-eye','restored-hand')
ORDINARY=('birth','warmup','pre',*(f'teach-{i}-{j}' for i in range(2) for j in range(8)),
          'development','confirmation')
CAUSAL=tuple(f'{arm}-{part}' for arm in ARMS for part in ('initial','final'))


def decide(origin,done,selection=False,decision=None,result=False):
    """Pure, strict next-stage rule; result presence never authorizes replay."""
    done=list(done)
    if len(done)!=len(set(done)) or set(done)-set(ORDINARY+CAUSAL):raise ValueError('unknown or duplicate boundary')
    ordinary=[s for s in done if s in ORDINARY]
    if ordinary!=list(ORDINARY[:len(ordinary)]):raise ValueError('non-prefix ordinary boundaries')
    causal=[s for s in done if s in CAUSAL]
    if causal!=list(CAUSAL[:len(causal)]):raise ValueError('non-prefix causal boundaries')
    if causal and (len(ordinary)!=len(ORDINARY) or not selection or decision is None or not decision['eligible']):
        raise ValueError('causal branches without complete registered prerequisites')
    if decision is not None and len(ordinary)!=len(ORDINARY):raise ValueError('premature causal decision')
    if selection and 'development' not in ordinary:raise ValueError('selection before development')
    if result:
        if len(ordinary)!=len(ORDINARY) or decision is None or (decision['eligible'] and len(causal)!=len(CAUSAL)):
            raise ValueError('premature result')
        return None
    if len(ordinary)<len(ORDINARY):
        label=ORDINARY[len(ordinary)]
        if label=='confirmation' and not selection:return {'origin':origin,'stage':'selection','parent':'development'}
        return {'origin':origin,'stage':label,'parent':None if not ordinary else ordinary[-1]}
    if not selection:raise ValueError('confirmation without preregistered selection')
    if decision is None:return {'origin':origin,'stage':'causal-preparation','parent':'confirmation'}
    if decision['eligible'] and len(causal)<len(CAUSAL):
        label=CAUSAL[len(causal)];arm,part=label.rsplit('-',1)
        return {'origin':origin,'stage':label,'parent':'confirmation' if part=='initial' else arm+'-initial'}
    return {'origin':origin,'stage':'finish','parent':None}


def inspect_origin(work,origin):
    folder=work/'units'/f'o{origin}'
    if not folder.exists():return decide(origin,[])
    if m.read(folder/'cases.json')!=m.read(work/'cases.json')[origin]['bank']:raise ValueError('frozen cases differ')
    actual={p.stem for p in (folder/'boundaries').glob('*.json')}
    if actual-set(ORDINARY+CAUSAL):raise ValueError('unexpected boundary')
    done=[s for s in ORDINARY+CAUSAL if s in actual]
    for label in done:
        boundary=m.read(folder/'boundaries'/(label+'.json'))
        r=m.read(folder/'states'/label/'complete.json')
        if boundary['path']!=(folder/'states'/label).relative_to(work).as_posix() or boundary['origin']!=origin:
            raise ValueError('boundary path/identity')
        if (boundary['canonical_sha256'],boundary['time_us'])!=(r['canonical_sha256'],r['time_us']):
            raise ValueError('boundary/state mismatch')
    found=[(folder/n).exists() for n in ('group-selection.json','edge-selection.json','development-graph.json.gz')]
    if any(found) and not all(found):raise ValueError('incomplete read-only selection')
    decision=m.read(folder/'pre-causal-decision.json') if (folder/'pre-causal-decision.json').exists() else None
    return decide(origin,done,all(found),decision,(folder/'result.json').exists())


def next_stage(work):
    if (work/'in-flight.json').exists():raise RuntimeError('in-flight marker requires owner audit; never clear/replay')
    for origin in range(8):
        result=inspect_origin(work,origin)
        if result is not None:
            if any((work/'units'/f'o{i}').exists() for i in range(origin+1,8)):
                raise ValueError('later origin exists before current completion')
            return result
    return None
