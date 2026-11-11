"""Recompute four confirmation analyses from ZIP records without running a subject."""
from pathlib import Path
import argparse,hashlib,importlib,json,math,re,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'lab/explorations/2026-10-16-mechanism-discovery'))

def compare(a,b,path='result'):
    if isinstance(a,dict):
        assert set(a)==set(b),f'{path}: key mismatch'
        for k in a:compare(a[k],b[k],path+'.'+k)
    elif isinstance(a,list):
        assert len(a)==len(b),f'{path}: length mismatch'
        for i,(x,y) in enumerate(zip(a,b)):compare(x,y,f'{path}[{i}]')
    elif isinstance(a,(int,float)) and not isinstance(a,bool):
        assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12),f'{path}: numeric mismatch'
    else:assert a==b,f'{path}: value mismatch'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args()
    base=a.data.resolve();report={}
    specs=[('M1-confirmation','m1-confirmation-v1','m1_confirm_analyze'),('M3-confirmation','m3-confirmation-v2','m3_confirm_analyze'),('M5-confirmation','m5-confirmation-v1','m5_confirm_analyze'),('M2-confirmation','m2-gain-prediction-v1','m2_gain_analyze')]
    manifest={r['path']:r for r in (json.loads(line) for line in (base/'MANIFEST.jsonl').open(encoding='utf8'))}
    for study,directory,module in specs:
        work=base/'experiments/2026-10-16-mechanism-discovery'/directory;archive=work/'originals-v1.zip';recorded=json.loads((work/'analysis-v1.json').read_text(encoding='utf8'))
        with archive.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==manifest[archive.relative_to(base).as_posix()]['sha256']
        mod=importlib.import_module(module)
        with zipfile.ZipFile(archive) as z:
            names=sorted((n for n in z.namelist() if re.fullmatch(r'units/o\d+/result\.json',n)),key=lambda n:int(n.split('/')[1][1:]))
            raw=[z.read(n) for n in names];results=[json.loads(b) for b in raw]
            if study in ('M1-confirmation','M5-confirmation'):
                with tempfile.TemporaryDirectory(prefix='threemind-public-reanalysis-') as td:
                    t=Path(td);(t/'cases.json').write_bytes(z.read('cases.json'))
                    for n,b in zip(names,raw):dest=t/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
                    actual=mod.analyze(t)
            elif study=='M3-confirmation':
                actual=mod.evaluate([mod.source_scores(r) for r in results]);actual['result_manifest']=[{'path':n,'sha256':hashlib.sha256(b).hexdigest()} for n,b in zip(names,raw)]
            else:actual=mod.evaluate([mod.score(r) for r in results])
        compare(actual,recorded)
        report[study]={'matched_published_analysis':True,'independent_origins':actual['independent_origins'],'valid':actual['valid'],'decision':actual.get('verdict',actual.get('goal',actual.get('goals')))}
    if a.output:
        dest=a.output.resolve();assert not dest.is_relative_to(base),'Write analysis outside the published dataset'
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
