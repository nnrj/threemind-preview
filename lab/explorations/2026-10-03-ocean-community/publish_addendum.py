"""Append the dated lineage clarification; do not replace a sealed report/archive."""
from psycopg.conninfo import conninfo_to_dict
from threemind_lab.config import Settings
from experiment import HERE,study
from lab.tools.study_publication import Publication

if __name__=='__main__':
    target=conninfo_to_dict(Settings.from_env().database_url)
    if (target.get('host'),target.get('port'),target.get('dbname'))!=('127.0.0.1','5433','threemind'):
        raise RuntimeError('verified local destination required')
    s=study()
    try:
        p=Publication(s)
        for name,title in (('lineage-addendum','谱系补记 / Lineage addendum'),
            ('capture-composition-addendum','捕获事件组成 / Capture composition')):
            body=(HERE/(name+'.md')).read_text(encoding='utf-8')
            result=p.document('record:'+name,'record','E32 '+title,body)
            p.note(name,'E32 '+title,body)
            print(result['id'])
    finally:s.db.close()
