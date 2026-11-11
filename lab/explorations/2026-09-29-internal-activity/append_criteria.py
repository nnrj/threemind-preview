"""Append interpretation corrections through versioned Lab services; never reseal old evidence."""
import copy
import json
from pathlib import Path
from uuid import UUID, uuid5

from threemind_lab import research_documents
from threemind_lab.config import Settings
from threemind_lab.database import Database, LOCAL_USER

HERE = Path(__file__).resolve().parent
PROJECT = 'df63c577-3b39-4642-87c5-2e9e1b05f165'
REPORTS = {'zh': 'c1c35176-a565-59fb-a280-219a70360d92', 'en': '876f6820-11a0-5548-8ff7-9b4f6a5502db'}

def main():
    zh = (HERE / 'autonomy-criteria.zh.md').read_text(encoding='utf-8')
    quote = zh.split('### 研究者原话备忘\n', 1)[1]
    database = Database(Settings.from_env().database_url)
    try:
        for lang, report in REPORTS.items():
            addition = (HERE / f'autonomy-criteria.{lang}.md').read_text(encoding='utf-8')
            if lang == 'en':
                addition += '\n\n### Original Chinese memo\n\n' + quote
            path = HERE / f'report.{lang}.md'
            existing = path.read_text(encoding='utf-8')
            if addition.splitlines()[0] not in existing:
                with path.open('a', encoding='utf-8', newline='\n') as f:
                    f.write('\n\n' + addition)
            current = research_documents.get(database, PROJECT, report)
            spec = copy.deepcopy(current['spec'])
            block_id = 'discussion-20260929-fixed-autonomy-criteria'
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
