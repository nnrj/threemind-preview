"""Publish measured E51 evidence without advancing Core or rewriting history."""
import shutil,re
from urllib.parse import quote
from experiment import *
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import artifact_once,archive_once
from threemind_lab import research_documents


def main():
    s=ArchivedStudy(WORK);s.name=s.settings.name;p=Publication(s)
    try:
        files={'results':(HERE/'results.json','application/json'),'outputs':(WORK/'outputs.html','text/html')}
        artifacts={k:artifact_once(p,k,file,'E51 '+k,mime) for k,(file,mime) in files.items()}
        for lang in ('zh','en'):
            def render(file):
                def link(m):
                    label,url=m.group(1),m.group(2)
                    for k,(f,_) in files.items():
                        if (file.parent/url).resolve()==f.resolve():return f"[{label}](/api/v2/projects/{s.project}/artifacts/{artifacts[k]['artifact_id']})"
                    if url.endswith('.md') and not url.startswith(('http','/','#')):
                        url='/docs?doc='+quote((file.parent/url).resolve().relative_to(ROOT).as_posix(),safe='')
                    return f'[{label}]({url})'
                return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,file.read_text(encoding='utf-8'))
            p.document('report:'+lang,'report','E51 时钟教学、现在与刚刚 / Clock and retelling '+lang,render(HERE/f'report.{lang}.md'))
            p.note('registration-final:'+lang,'E51 执行细节与工具纠错 / Details and correction '+lang,render(HERE/f'design.{lang}.md'))
        p.document('record:words','record','E51 原样回答 / Original answers',
            f"[查看每道题原话 / Every original answer](/api/v2/projects/{s.project}/artifacts/{artifacts['outputs']['artifact_id']})")
        final=WORK/'final-report';final.mkdir(exist_ok=True)
        for file in HERE.iterdir():
            if file.is_file() and file.suffix in ('.json','.md','.py') and not (final/file.name).exists():shutil.copy2(file,final/file.name)
        archive=archive_once(p,'E51 clock teaching and recollection evidence.zip',historical_scope=(
            'E48 frozen language input and recorded physical telemetry are read-only dependencies',
            'First single-frame probe admission failed before delivery; empty failure directory retained',
            'No Core or input encoder changes; external clock and20ms language frame presentation recorded'))
        p.document('record:evidence','record','E51 输入、过程与模型 / Inputs, processes and models',
            f"[证据及检查点 / Evidence and checkpoints](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})")
        for key in ('report:zh','report:en'):
            row=p.state[key];actual=research_documents.get(s.db,s.project,row['id'],revision=row['revision'])
            if actual['content_hash']!=row['content_hash']:raise RuntimeError('report publication mismatch')
        with s.db.tx() as tx:dbbytes=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        resources={'local_bytes':sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file()),
                   'database_growth':max(0,dbbytes-s.meta['database_bytes_before']),'usage':read_json(WORK/'usage.json'),
                   'free_bytes':{d:shutil.disk_usage(d+':/').free for d in ('C','D','E')}}
        new_json(HERE/'delivery.json',{'project':s.project,'archive':archive,'artifacts':artifacts,
            'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},'resources':resources})
        print({'project':s.project,'storage_MiB':round((resources['local_bytes']+resources['database_growth'])/2**20,1)},flush=True)
    finally:s.db.close()


if __name__=='__main__':main()
