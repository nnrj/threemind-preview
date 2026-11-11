"""Append readable experiment notes through the Lab service, not direct SQL."""
import re
from urllib.parse import quote
from experiment import ROOT,HERE,WORK
from lab.tools.study_publication import ArchivedStudy,Publication


def render(path):
    def link(match):
        label,url=match.group(1),match.group(2)
        if url.startswith(('/','#')) or '://' in url:return match.group(0)
        if url.endswith('.md'):
            target=(path.parent/url).resolve()
            if target.is_relative_to(ROOT) and target.is_file():
                return f'[{label}](/docs?doc='+quote(target.relative_to(ROOT).as_posix(),safe='')+')'
        return f'{label} (`{url}`)'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,path.read_text(encoding='utf-8'))


def main():
    s=ArchivedStudy(WORK);p=Publication(s)
    try:
        for name in ('stage-a','events-registration','resource-amendment','decoder-fit-registration',
                     'trajectory-registration','timing-followup-registration','scoring-correction'):
            for language in ('zh','en'):
                path=HERE/f'{name}.{language}.md'
                p.note(name+':'+language,'E48 '+name+' '+language,render(path))
        print('E48 progress notes published')
    finally:s.db.close()


if __name__=='__main__':main()
