import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Upload } from 'lucide-react';
import { api, projectPath } from './api';
import { useWorkspace, ErrorBox, Loading, Empty } from './ui';
import { t } from './i18n';
import './species.css';

export default function SpeciesLibrary() {
  const { project } = useWorkspace();
  const base = `${projectPath(project!.id)}/species`;
  const cache = useQueryClient();
  const [q, setQ] = useState('');
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const records = useQuery({ queryKey: ['species', project!.id, q, offset],
    queryFn: () => api<any[]>(`${base}?q=${encodeURIComponent(q)}&offset=${offset}&limit=30`) });
  async function upload(file: File) {
    setBusy(true); setError(undefined);
    try {
      const form = new FormData(); form.append('file', file);
      await api(base, { method: 'POST', body: form });
      setOffset(0); setQ(''); await cache.invalidateQueries({ queryKey: ['species', project!.id] });
    } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return <section className="panel species-library">
    <div className="panel-heading"><div><h2>{t('物种库')}</h2>
      <p className="muted">{t('一起保存躯体、意识、谱系与能力证据，供后续实验复用。候选不等于已证明的生物学物种。')}</p></div>
      <label className={`button primary ${busy ? 'disabled' : ''}`}><Upload size={16}/>{busy ? t('正在校验…') : t('导入物种包')}
        <input hidden type="file" accept=".tmspecies,.zip" disabled={busy} onChange={e => {
          const file = e.target.files?.[0]; if(file) void upload(file); e.target.value = '';
        }}/></label></div>
    <label>{t('搜索物种名称')}<input value={q} onChange={e=>{setQ(e.target.value);setOffset(0);}} placeholder={t('名称')}/></label>
    <ErrorBox error={error || records.error}/>
    {records.isLoading ? <Loading/> : !records.data?.length ? <Empty title={t('暂无物种候选')} detail={t('从实验快照保存有价值的个体，再导入 .tmspecies 包。原实验和原意识保持不变。')}/> :
      <div className="species-grid">{records.data.map(row => {
        const m = row.manifest;
        return <article className="species-card" key={row.id}>
          <div className="panel-heading"><h3>{row.name}</h3><span className="badge">{m.qualification === 'replicated' ? t('附重复验证记录') : t('待复验候选')}</span></div>
          <p>{m.description}</p>
          <dl><dt>{t('来源个体 / 代次')}</dt><dd>#{m.source.individual} / G{m.body.generation}</dd>
            <dt>{t('保存时刻')}</dt><dd>{Number(m.source.world_time_us)/1e6} s</dd>
            <dt>{t('体型 / 外壳')}</dt><dd>{(m.traits.radius*1000).toFixed(2)} mm / {m.traits.shell.toFixed(3)}</dd>
            {m.body.body_material_energy != null && <><dt>{t('可消化躯体能量')}</dt><dd>{Number(m.body.body_material_energy).toFixed(2)}</dd></>}
            <dt>{t('内核')}</dt><dd>{m.kernel_id}</dd></dl>
          <h4>{t('能力证据')}</h4>
          {m.evidence.map((e:any,i:number)=><p key={i}>{e.summary || e.kind || JSON.stringify(e)}</p>)}
          <details><summary>{t('谱系、躯体与复用说明')}</summary>
            <p>{t('默认作为新个体继承结构和躯体，清空活动，明确配置初始能量；不是自动继续原意识。完整快照另供恢复核对。')}</p>
            <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify({lineage:m.lineage,traits:m.traits,body:m.body,evidence:m.evidence,environment_protocol:m.environment_protocol,reuse:m.reuse,source:m.source},null,2)}</pre>
          </details>
          <a className="button" href={`/api/v2${base}/${row.id}/download`}><Download size={16}/>{t('导出物种包')}</a>
        </article>;
      })}</div>}
    <div className="button-row"><button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-30))}>{t('上一页')}</button>
      <button disabled={records.data?.length!==30} onClick={()=>setOffset(offset+30)}>{t('下一页')}</button></div>
    <p className="muted">{t('导出的物种包可用于后续海洋实验；配置、谱系与快照保持原始版本。')}</p>
  </section>;
}
