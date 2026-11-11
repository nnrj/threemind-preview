"""Supplement the full-habitat catalog with a synchronized causal comparison."""
from experiment import WORK
from media import clip
from lab.tools.ocean_cli import read_json,write_json


def build():
    catalog_path=WORK/'media/final/catalog.json'
    old=read_json(catalog_path)
    backup=WORK/'media/final/catalog-before-causal.json'
    if not backup.exists():write_json(backup,old)
    additions=[]
    for op,title in (('core','原意识'),('target','目标通路静默'),('matched','匹配通路静默')):
        offset=0 if op=='core' else 60
        additions.append(clip('causal-'+op,'g0-'+op,'E32 0号原位对照 · '+title,0,102-offset,115-offset,
            '同一绝对时间102–115模拟秒，完整环境保持。原意识和匹配静默摄入营养50；目标静默改变轨迹，未取得这次摄入。'
            '这是同源世界的三个反事实分支，不是三个独立群体。影片来自100毫秒采样的真实状态。'))
    ids={item['id'] for item in additions}
    old['clips']=[item for item in old['clips'] if item['id'] not in ids]+additions
    old['supplement']='Three same-time focal pathway comparisons; main environment retained'
    import json
    temporary=catalog_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(catalog_path)


if __name__=='__main__':build()
