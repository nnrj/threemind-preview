"""Publish E61 evidence, reports and replay through existing Lab services."""
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote, urlsplit
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from lab.tools.study_publication import ArchivedStudy, Publication
from lab.tools.evidence_archive import artifact_once
from lab.tools.streaming_evidence import archive_stream_once
from lab.tools.service_study import new_json
from threemind_lab import research_documents

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/body-exploration-20261007'


def links(body, project, artifacts):
    def replace(match):
        label, url = match.groups()
        artifact_key = url if url in artifacts else None
        if artifact_key is None and not url.startswith(('/', '#')) and '://' not in url:
            local = (HERE/url).resolve()
            artifact_key = next((name for name in artifacts if local in ((WORK/name).resolve(), (HERE/name).resolve())), None)
        if artifact_key is not None: url = f'/api/v2/projects/{project}/artifacts/{artifacts[artifact_key]["artifact_id"]}'
        elif url.endswith('.md') and not url.startswith(('/', '#')) and '://' not in url:
            path = (HERE/url).resolve()
            if path.is_relative_to(ROOT) and path.is_file(): url = '/docs?doc='+quote(path.relative_to(ROOT).as_posix(), safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace, body)


def main():
    from threemind_lab.config import Settings
    endpoint = urlsplit(Settings.from_env().database_url)
    if endpoint.scheme != 'postgresql' or endpoint.hostname != '127.0.0.1' or endpoint.port != 5433 or endpoint.path != '/threemind':
        raise ValueError('E61 publication is restricted to the authorized local ThreeMind database')
    study = ArchivedStudy(WORK); study.name = 'body-exploration/1'; pub = Publication(study)
    try:
        artifacts = {}
        replay = json.loads((WORK/'replay-manifest.json').read_text(encoding='utf-8'))
        index = (WORK/'body-exploration.html').read_text(encoding='utf-8')
        for chapter in replay['chapters']:
            name = chapter['path']
            artifact = artifact_once(pub, name, WORK/name, 'E61 '+chapter['title'], 'text/html')
            artifacts[name] = artifact
            index = index.replace(f'href="{name}"', f'href="/api/v2/projects/{study.project}/artifacts/{artifact["artifact_id"]}"')
            print(json.dumps({'published_chapters': len(artifacts), 'total': len(replay['chapters'])}), flush=True)
        platform_index = WORK/'body-exploration-platform.html'
        if not platform_index.exists(): platform_index.write_text(index, encoding='utf-8')
        elif platform_index.read_text(encoding='utf-8') != index: raise ValueError('published chapter links changed')
        chapter_references = WORK/'replay-artifacts.json'
        references = {'schema':'threemind.replay-artifact-references/1',
                      'project_id':study.project,
                      'chapters':{c['path']:artifacts[c['path']] for c in replay['chapters']},
                      'archive_policy':'HTML chapters are stored as independent artifacts; ZIP keeps original process, renderer and these references, avoiding a second database copy.'}
        if not chapter_references.exists(): new_json(chapter_references, references)
        elif json.loads(chapter_references.read_text(encoding='utf-8')) != references:
            raise ValueError('published replay references changed')
        for name, path, mime in [('results.json', HERE/'results.json', 'application/json'),
                                ('baseline-reference.json', HERE/'baseline-reference.json', 'application/json'),
                                ('gaze-events.json', WORK/'gaze-events.json', 'application/json'),
                                ('body-exploration-results.png', WORK/'body-exploration-results.png', 'image/png'),
                                ('caregiver-process.png', WORK/'caregiver-process.png', 'image/png'),
                                ('body-exploration.html', platform_index, 'text/html')]:
            artifacts[name] = artifact_once(pub, name, path, 'E61 '+name, mime)
        for name in ('execution-notes', 'tools', 'exploration-amendment', 'caregiver-amendment', 'budget-amendment', 'quota-amendment', 'posture-amendment', 'continuation-amendment', 'withdrawal-correction', 'main-results.zh', 'main-results.en', 'continuity-correction.zh', 'continuity-correction.en', 'verification'):
            pub.note('final:'+name, 'E61 '+name, links((HERE/f'{name}.md').read_text(encoding='utf-8'), study.project, artifacts))
        verified = []
        for language in ('zh', 'en'):
            body = links((HERE/f'report.{language}.md').read_text(encoding='utf-8'), study.project, artifacts)
            saved = pub.document('report:continuity-corrected:'+language, 'report', 'E61 分段流程与连续性更正 / Segmented pipeline and continuity correction '+language, body)
            record = research_documents.get(study.db, study.project, saved['id'])
            if record['spec']['blocks'][0]['markdown'] != body: raise ValueError('stored report mismatch')
            verified.append({'id': saved['id'], 'language': language, 'body_matches': True})
        for name in ('streaming_evidence.py', 'body_playground.py', 'continuous_motor.py', 'eye_hand_world.py', 'gaze_events.py', 'active_vision_replay.py', 'active_vision_replay.html',
                     'sensorimotor_session.py', 'active_eye.py', 'whole_scene_classroom.py', 'grounded_classroom.py',
                     'shape_color_world.py', 'activity_controller.py', 'choice_attribution.py', 'service_study.py'):
            source = ROOT/'lab/tools'/name; destination = WORK/'delivered-tools'/name
            destination.parent.mkdir(exist_ok=True)
            if not destination.exists(): shutil.copy2(source, destination)
        # The generic archiver copies source Markdown/Python separately. Keep
        # the small JSON summaries beside them inside the same archive.
        for name in ('results.json',):
            destination = WORK/'publication-sources'/name
            destination.parent.mkdir(exist_ok=True)
            if not destination.exists(): shutil.copy2(HERE/name, destination)
        print(json.dumps({'stage': 'archive and upload', 'reports_checked': len(verified)}), flush=True)
        archive = archive_stream_once(pub, 'E61 完整输入、活动、教学、失败、眼手轨迹及模型.zip',
            omit_derived_names=('features.npz', *(Path(c['path']).name for c in replay['chapters'])))
        pub.document('evidence', 'record', 'E61 全部证据与回放',
            f'[完整证据](/api/v2/projects/{study.project}/artifacts/{archive["artifact_id"]})\n\n'
            f'[回放](/api/v2/projects/{study.project}/artifacts/{artifacts["body-exploration.html"]["artifact_id"]})\n\n'
            '动作来源逐段说明，保留全部题目；旧Core和旧证据不改。 / Action provenance and every trial retained.')
        with study.db.tx() as tx:
            size = tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery = {'project_id': study.project, 'artifacts': artifacts, 'archive': archive, 'reports': verified,
                    'destination': {'kind': 'local PostgreSQL artifact_chunks', 'host': endpoint.hostname,
                                    'port': endpoint.port, 'database': endpoint.path.lstrip('/')},
                    'local_bytes': sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
                    'database_growth_bytes': max(0, size-study.meta['database_bytes_before'])}
        if not (HERE/'delivery.json').exists(): new_json(HERE/'delivery.json', delivery)
        print(json.dumps({'project_id': study.project, 'reports': verified,
                          'chapters': len(replay['chapters']), 'archive_bytes': archive['bytes'],
                          'local_bytes': delivery['local_bytes'], 'database_growth_bytes': delivery['database_growth_bytes']}))
    finally: study.db.close()


if __name__ == '__main__': main()
