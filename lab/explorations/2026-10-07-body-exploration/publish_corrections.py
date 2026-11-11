"""Append E61 continuity scope notices to historical projects, without replacing reports."""
import json
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.study_publication import ArchivedStudy, Publication
from lab.tools.service_study import new_json
from threemind_lab import research_documents
from threemind_lab.config import Settings

HERE = Path(__file__).resolve().parent
STUDIES = (
    ('E52', 'coadaptive-language-20261005', '2026-10-05-coadaptive-language'),
    ('E54', 'shape-color-20261006', '2026-10-06-shape-color-pointing'),
    ('E55', 'grounded-reviews-20261006', '2026-10-06-grounded-reviews'),
    ('E56', 'vision-correction-20261006', '2026-10-06-vision-correction'),
    ('E57', 'choice-attribution-20261006', '2026-10-06-choice-attribution'),
    ('E58', 'embodied-memory-20261007', '2026-10-07-embodied-memory'),
    ('E59', 'active-vision-20261007', '2026-10-07-active-vision'),
    ('E60', 'eye-hand-learning-20261007', '2026-10-07-eye-hand-learning'),
)


def main():
    endpoint = urlsplit(Settings.from_env().database_url)
    if (endpoint.scheme, endpoint.hostname, endpoint.port, endpoint.path) != ('postgresql', '127.0.0.1', 5433, '/threemind'):
        raise ValueError('corrections are authorized only for the local ThreeMind database')
    # Resolve every source before any database write; no evidence directories scanned.
    for _, work, folder in STUDIES:
        if not (ROOT/'.work'/work/'platform.json').is_file():
            raise FileNotFoundError(work)
        for language in ('zh', 'en'):
            if not (ROOT/'lab/explorations'/folder/f'continuity-note.{language}.md').is_file():
                raise FileNotFoundError(folder)
    records = []
    for code, work, folder in STUDIES:
        study = ArchivedStudy(ROOT/'.work'/work)
        pub = Publication(study)
        try:
            for language in ('zh', 'en'):
                body = (ROOT/'lab/explorations'/folder/f'continuity-note.{language}.md').read_text(encoding='utf-8')
                doc = f'docs/{language}/plans/system-continuity-audit.md'
                body = body.replace(f'../../../{doc}', '/docs?doc='+quote(doc, safe=''))
                saved = pub.document('record:continuity-review-20261007:'+language, 'record',
                    f'{code} 连续性核查补注 / Continuity scope correction {language}', body)
                got = research_documents.get(study.db, study.project, saved['id'])
                if got['spec']['blocks'][0]['markdown'] != body:
                    raise ValueError('stored correction differs; existing records not overwritten')
                records.append({'study':code, 'project_id':study.project, 'language':language,
                                'document_id':saved['id'], 'body_matches':True})
            print(json.dumps({'study':code,'new_correction_records':2,'old_reports_preserved':True}), flush=True)
        finally:
            study.db.close()
    target = HERE/'historical-corrections.json'
    if not target.exists():
        new_json(target, {'date':'2026-10-07','records':records,'original_reports_unchanged':True})


if __name__ == '__main__':
    main()
