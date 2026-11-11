"""Freeze analysis before inspecting outcome files; no change to registered criteria."""
import hashlib
from common import HERE,WORK,Study,encoded,new_json
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER

BODY='''分析聚合说明 / Analysis aggregation clarification

此说明在内部通路阶段执行完、尚未读取数值结果时登记，保持阶段正在执行；未修改阈值或实验。
Each parent's sequential score is the mean absolute communication effect across P/Q histories. The environmental score is the mean absolute history effect across the two counterbalanced route pairs (PQP versus PPP and QPQ versus QQQ). Absolute effects are combined because motor signs depend on fixed wiring; both signed components remain in the report. At least three of four parents covering both wiring seeds must pass the registered 0.0001 threshold. This does not count related lineages as independent populations.

每个父本的连续互动得分为 P/Q 两种历史的通信作用绝对值的平均；环境得分为两种反向顺序对照的行为差异绝对值的平均。固定运动接线可产生相反方向，故聚合大小而非抵消；报告保留全部有符号结果。此处是登记判据的计算展开，不按结果选取历史或方向。

用户补充原文：补充：在巩固记忆的时候，重复可以是不均匀的，初期重复频繁点，慢慢重复变稀疏，类似人类学习一项技能那样
该要求已包含在登记的 0、1、2、4、8、16、32、64、96、128 秒方案中。
'''

if __name__=='__main__':
    s=Study()
    try:
        target=WORK/'analysis-registration.json'
        if target.exists(): raise RuntimeError('analysis already frozen')
        raw=(HERE/'analyze.py').read_bytes()
        (WORK/'analysis-frozen.py').write_bytes(raw)
        note=notebooks.save_note(s.db,s.project,LOCAL_USER,s.identity('analysis-registration'),{
            'operation_id':s.identity('analysis-registration:write'),'expected_revision':0,'kind':'note',
            'collection_id':s.meta['notebook_id'],'title':'分析聚合与递疏复习补充登记',
            'body':{'format':'markdown','text':BODY}})
        new_json(target,{'analysis_sha256':hashlib.sha256(raw).hexdigest(),'note':str(note['id']),'body':BODY})
    finally:s.db.close()
