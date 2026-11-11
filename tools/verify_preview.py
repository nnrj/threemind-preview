"""Verify preserved source bytes in this independently packaged repository."""
import argparse,hashlib,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();root=a.root.resolve()
    m=json.loads((root/'SOURCE_MANIFEST.json').read_text(encoding='utf8'))
    for x in m['source_files']:
        f=(root/x['path']).resolve();assert f.is_relative_to(root)
        assert f.is_file() and f.stat().st_size==x['bytes'],x['path']
        assert hashlib.sha256(f.read_bytes()).hexdigest()==x['sha256'],x['path']
    print(json.dumps({'source_commit':m['source_commit'],'preserved_files_verified':len(m['source_files'])}))
if __name__=='__main__':main()
