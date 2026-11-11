"""Store post-archive delivery summaries with resolvable platform links.

Document revisions preserve earlier text; the evidence archive is untouched.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.study_publication import ArchivedStudy, Publication
from lab.tools.evidence_archive import artifact_once
from threemind_lab import research_documents
from threemind_lab.database import LOCAL_USER
from publish import links

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/vision-correction-20261006'


def main():
    s = ArchivedStudy(WORK)
    p = Publication(s)
    try:
        asset = artifact_once(p, 'artifact:delivery', HERE/'delivery.json',
                              'E56 publication identifiers and measured storage', 'application/json')
        url = f'/api/v2/projects/{s.project}/artifacts/{asset["artifact_id"]}'
        records = {}
        for lang in ('zh', 'en'):
            key = 'record:delivery:'+lang
            body = links((HERE/f'delivery.{lang}.md').read_text(encoding='utf-8'), p)
            body = body.replace('(delivery.json)', '('+url+')')
            if key not in p.state:
                value = p.document(key, 'record', 'E56 交付与预算 / Delivery and budget '+lang, body)
            else:
                old = research_documents.get(s.db, s.project, p.state[key]['id'])
                spec = dict(old['spec'])
                blocks = [dict(b) for b in spec['blocks']]
                narrative = next(b for b in blocks if b['id'] == 'narrative')
                if narrative['markdown'] == body:
                    value = p.state[key]
                else:
                    narrative['markdown'] = body
                    spec['blocks'] = blocks
                    value = research_documents.save(s.db, s.project, LOCAL_USER, old['id'], {
                        'operation_id': s.identity(key+':canonical-links-v1'),
                        'expected_revision': old['revision'], 'spec': spec})
                    p.remember(key, value)
            records[lang] = {'id': str(value['id']), 'revision': value['revision']}
        output = HERE/'delivery-records.json'
        if not output.exists():
            with output.open('x', encoding='utf-8') as out:
                json.dump({'project_id': s.project, 'records': records,
                           'delivery_artifact': asset['artifact_id']}, out, indent=2)
        print(json.dumps(records))
    finally:
        s.db.close()


if __name__ == '__main__':
    main()
