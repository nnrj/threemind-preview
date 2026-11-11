"""Check generated links and sizes without rereading large experiment evidence."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / '.work/eye-hand-learning-20261007'


def main():
    manifest = json.loads((WORK / 'replay-manifest.json').read_text(encoding='utf-8'))
    index = (WORK / 'eye-hand-learning.html').read_text(encoding='utf-8')
    for chapter in manifest['chapters']:
        path = (WORK / chapter['path']).resolve()
        if not path.is_relative_to(WORK.resolve()) or path.stat().st_size != chapter['bytes']:
            raise ValueError('chapter path or size mismatch')
        if f'href="{chapter["path"]}"' not in index: raise ValueError('missing chapter link')
    if sum(c['frames'] for c in manifest['chapters']) != manifest['frames']:
        raise ValueError('frame accounting')
    template = (ROOT / 'lab/tools/active_vision_replay.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', template, re.S).group(1).replace('__DATA__', '{}')
    (WORK / 'replay-syntax.js').write_text(script, encoding='utf-8')
    result = {'chapters': len(manifest['chapters']), 'clips': manifest['clips'], 'frames': manifest['frames'],
              'html_bytes': manifest['file_bytes'],
              'largest_chapter_bytes': max(c['bytes'] for c in manifest['chapters']),
              'paths_and_sizes_checked': True, 'browser_visual_validation': False,
              'scope': 'generated metadata and static source only; no repeated evidence hashing'}
    with (WORK / 'assets-check.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result))


if __name__ == '__main__': main()
