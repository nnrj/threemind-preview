"""Append interpretation corrections through versioned Lab services; never reseal old evidence."""
import copy
import json
from pathlib import Path
from uuid import UUID, uuid5

from threemind_lab import research_documents
from threemind_lab.config import Settings
from threemind_lab.database import Database, LOCAL_USER

HERE = Path(__file__).resolve().parent
PROJECT = '59aee7a1-5248-417f-a03b-b56f858a04d9'
REPORTS = {'zh': 'c767c0eb-d03d-55fd-8dad-31b9389a574b', 'en': '3d861c62-168d-5f21-b125-926942e938d9'}

def main():
    zh = (HERE / 'discussion-addendum.zh.md').read_text(encoding='utf-8')
    quote = zh.split('### 研究者原话备忘\n', 1)[1]
    database = Database(Settings.from_env().database_url)
    try:
        for lang, report in REPORTS.items():
            addition = (HERE / f'discussion-addendum.{lang}.md').read_text(encoding='utf-8')
            if lang == 'en':
                addition += '\n\n### Original Chinese memo\n\n' + quote
            path = HERE / f'report.{lang}.md'
            existing = path.read_text(encoding='utf-8')
            if addition.splitlines()[0] not in existing:
                with path.open('a', encoding='utf-8', newline='\n') as f:
                    f.write('\n\n' + addition)
            current = research_documents.get(database, PROJECT, report)
            spec = copy.deepcopy(current['spec'])
            block_id = 'discussion-20260929-causal-boundaries'
            if not any(b['id'] == block_id for b in spec['blocks']):
                spec['blocks'].append({'id': block_id, 'type': 'commentary', 'section': 'discussion', 'markdown': addition})
                saved = research_documents.save(database, PROJECT, LOCAL_USER, report, {
                    'operation_id': str(uuid5(UUID(report), block_id)),
                    'expected_revision': current['revision'], 'spec': spec,
                })
            else:
                saved = {'revision': current['revision'], 'already_appended': True}
            verify = research_documents.get(database, PROJECT, report)
            assert next(b for b in verify['spec']['blocks'] if b['id'] == block_id)['markdown'] == addition
            print(json.dumps({'lang': lang, 'report': report, 'saved': saved}, default=str))
    finally:
        database.close()

if __name__ == '__main__':
    main()
