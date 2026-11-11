"""Final tables for human interpretation of all registered E34 encounters."""
from experiment import HERE,WORK,ARMS
from lab.tools.ocean_cli import read_json


def build():
    f=read_json(WORK/'findings.json');sources=f['sources'];rows=[];dynamics=[]
    if any(set(s['arms'])!=set(ARMS) for s in sources.values()):raise RuntimeError('unfinished encounter')
    for key,s in sources.items():
        for op,a in s['arms'].items():
            contact='—' if a['first_contact_s'] is None else f"{a['first_contact_s']:.3f}"
            capture='—' if a['target_capture_s'] is None else f"{a['target_captured_by']} @ {a['target_capture_s']:.3f}"
            rows.append(f"| {key}: {s['focal']}→{s['target']} | {op} | {contact} | {capture} | {a['captured']} | {a['food']} | {a['physical']} |")
        c=s['comparisons'];target=c['uncued intact vs target'];matched=c['uncued intact vs matched']
        decrease=lambda v:100*(1-v['other_activation_seconds']/v['intact_activation_seconds']) if v['intact_activation_seconds'] else None
        values=[key,str(s['selected_edges']),f"{decrease(target):.2f}%",f"{decrease(matched):.2f}%"]
        for name in ('intact vs target','intact vs matched','experienced vs blank','experienced vs graft','experienced vs graft-matched'):
            x=c[name]['20'];values.append(f"{x['mae']:.6f} ({x['common_alive_s']:.2f}s)" if x['mae'] is not None else 'NA')
        dynamics.append('| '+' | '.join(values)+' |')
    body='''# E34 measured tables / 实测表

Every row retains the complete habitat. Time is seconds after the declared whole-world fork.

| 来源 / focal→counterpart | 操作 / operation | First contact s | Counterpart captured by @ s | Other+target captures | New food | Focal body alive |
| --- | --- | ---: | --- | ---: | ---: | --- |
'''+ '\n'.join(rows)+'''

Activity reduction uses1–10s samples where the target channels have no direct input in the preceding second in either branch. Action MAE uses only common living periods; duration in parentheses.

| Source | Edges | Target activity reduction | Matched activity reduction | Target action difference | Matched action difference | Experienced vs blank | Experienced vs graft | Experienced vs matched graft |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
'''+ '\n'.join(dynamics)+'\n'
    with (HERE/'measured-tables.md').open('x',encoding='utf-8') as out:out.write(body)


if __name__=='__main__':build()
