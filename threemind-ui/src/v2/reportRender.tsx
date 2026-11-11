import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t, messageKeys, locale } from "./i18n";
import { metricLabel } from "./reportLabels";
import { Button, ErrorBox, Loading } from "./ui";
import EventTable from "./ReportEventTable";
import AssessmentSummary from "./AssessmentSummary";
import { projectResourceHref } from "./reportLinks";
const ReportChart = lazy(() => import("./ReportChart"));

export const kindNames = messageKeys({
  trajectory: "时间序列",
  nodes: "节点分布",
  edges: "连接分布",
  analysis: "统计分析",
  events: "输入、干预与事件",
  evolution: "多代训练结果",
  ecology_trajectory: "生态种群轨迹",
  ecology_members: "生态全体个体",
  assessment: "独立评估结果",
  temporal_windows: "时序读出：窗口汇总",
  temporal_nodes: "时序读出：节点与排名",
  temporal_series: "时序读出：变化曲线",
});
export const blockNames = messageKeys({
  commentary: "研究说明",
  chart: "图表",
  table: "数据表格",
  fact: "数值摘要",
  record_block: "引用实验记录",
  assessment_summary: "固定规则判定",
});
export const sectionNames = messageKeys({
  purpose: "研究目的",
  methods: "方法与过程",
  results: "观测结果",
  discussion: "讨论",
  limitations: "限制与缺失",
  hypothesis: "研究假说",
  other: "其他说明",
});
export const chartNames = messageKeys({
  line: "折线图",
  scatter: "散点图",
  histogram: "直方图",
  bar: "柱状图",
});
export const statisticNames = messageKeys({
  first: "首个样本",
  last: "末个样本",
  minimum: "最小值",
  maximum: "最大值",
  mean: "样本算术均值",
  count: "有效值数量",
  missing: "缺失值数量",
});
export function displayValue(value: any) {
  return value === null || value === undefined
    ? t("缺失")
    : typeof value === "number"
      ? new Intl.NumberFormat(locale(), {
          maximumSignificantDigits: 7,
          notation:
            Math.abs(value) >= 1e7 ||
            (Math.abs(value) > 0 && Math.abs(value) < 1e-4)
              ? "scientific"
              : "standard",
        }).format(value)
      : String(value);
}

export function EvidenceTable({
  rows,
  metrics,
}: {
  rows: any[];
  metrics: string[];
}) {
  return (
    <div className="table-wrap report-data-table">
      <table>
        <thead>
          <tr>
            <th>{t("样本或对象")}</th>
            <th>{t("质量")}</th>
            {metrics.map((m) => (
              <th key={m} title={m}>
                {metricLabel(m)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.ordinal ?? i}>
              <td>{r.label}</td>
              <td>{r.quality}</td>
              {metrics.map((m) => (
                <td key={m} title={String(r.values[m] ?? "")}>
                  {displayValue(r.values[m])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CompleteTable({ base, block }: { base: string; block: any }) {
  const [after, setAfter] = useState(-1),
    [opened, setOpened] = useState(false);
  const page = useQuery({
    queryKey: ["report-rows", base, block.source, after],
    queryFn: () =>
      api(`${base}/report-sources/${block.source}/rows?after=${after}`),
    enabled: opened,
  });
  return (
    <>
      {block.source_kind === "events" ? (
        <EventTable
          rows={opened ? (page.data?.rows ?? []) : block.rows}
          base={base}
          source={block.source}
        />
      ) : (
        <EvidenceTable
          rows={opened ? (page.data?.rows ?? []) : block.rows}
          metrics={block.metrics}
        />
      )}
      <div className="report-inline">
        <span>
          {t("共 {count} 行；每页显示 100 行。", { count: block.row_count })}
        </span>
        {!opened && block.row_count > 100 && (
          <Button onClick={() => setOpened(true)}>{t("浏览全部数据")}</Button>
        )}
        {opened && (
          <>
            <Button
              disabled={after < 0}
              onClick={() => setAfter(Math.max(-1, after - 100))}
            >
              {t("上一页")}
            </Button>
            <Button
              disabled={!page.data?.more}
              onClick={() => setAfter(page.data.rows.at(-1).ordinal)}
            >
              {t("下一页")}
            </Button>
          </>
        )}
      </div>
      <ErrorBox error={page.error} />
    </>
  );
}

export function RenderBlock({ block, base }: { block: any; base?: string }) {
  if (block.type === "assessment_summary")
    return (
      <section>
        <h3>{t("固定规则判定")}</h3>
        <AssessmentSummary value={block.assessment} />
        <small>
          {t("固定来源")} · {block.source_hash}
        </small>
      </section>
    );
  if (block.type === "record_block")
    return (
      <section className="report-reference">
        <small>
          {t("引用固定记录修订")} · {block.record_id} · r{block.revision}
        </small>
        <RenderBlock block={block.content} base={base} />
      </section>
    );
  if (block.type === "commentary")
    return (
      <section className="report-text markdown">
        <h3>{t(sectionNames[block.section as keyof typeof sectionNames])}</h3>
        <small>{t("作者说明与解释")}</small>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[
            [rehypeKatex, { trust: false, strict: "ignore", maxExpand: 1000 }],
          ]}
          components={{
            img: ({ src, alt }) => {
              const local = projectResourceHref(
                typeof src === "string" ? src : undefined,
                base,
                true,
              );
              return local ? (
                <a href={local} target="_blank" rel="noreferrer">
                  <img src={local} alt={alt || ""} loading="lazy" />
                </a>
              ) : (
                <span>{alt}</span>
              );
            },
            a: ({ href, children }) => (
              <a
                href={
                  /^https?:\/\//.test(href ?? "")
                    ? href
                    : projectResourceHref(href, base)
                }
                target="_blank"
                rel="noreferrer"
              >
                {children}
              </a>
            ),
          }}
        >
          {block.markdown || t("尚未填写说明。")}
        </ReactMarkdown>
      </section>
    );
  if (block.type === "fact")
    return (
      <section className="report-fact">
        <span>
          {block.label || metricLabel(block.metric)} ·{" "}
          {t(statisticNames[block.statistic as keyof typeof statisticNames])}
        </span>
        <strong>{displayValue(block.value)}</strong>
        <small>
          {block.unit} ·{" "}
          {t("有效 {valid} / 缺失 {missing}", {
            valid: block.statistics.count,
            missing: block.statistics.missing,
          })}
        </small>
        {block.statistic === "mean" && (
          <small>
            {t("这是样本算术均值，不是时间加权均值或独立重复的统计推断。")}
          </small>
        )}
      </section>
    );
  return (
    <section className="report-figure">
      <h3>
        {block.title ||
          (block.metric ? metricLabel(block.metric) : t("数据表格"))}
      </h3>
      {block.type === "table" ? (
        base ? (
          <CompleteTable base={base} block={block} />
        ) : block.source_kind === "events" ? (
          <EventTable rows={block.rows} />
        ) : (
          <EvidenceTable rows={block.rows} metrics={block.metrics} />
        )
      ) : (
        <>
          <Suspense fallback={<Loading />}>
            <ReportChart block={block} />
          </Suspense>
          <p className="hint">
            {t("有效 {valid} / 缺失 {missing}", {
              valid: block.data.statistics.count,
              missing: block.data.statistics.missing,
            })}{" "}
            ·{" "}
            {block.data.method === "ordinal-bin-sample-mean-min-max/1"
              ? t("图中展示分组均值与极值范围；极值范围不是置信区间。")
              : t("使用全部已采集的选定数据。")}
          </p>
          {block.analysis_metric && (
            <EvidenceTable
              rows={block.data.rows}
              metrics={Object.keys(block.data.rows[0]?.values ?? {})}
            />
          )}
        </>
      )}
      <small className="report-source-id">
        {t("数据来源")} · {block.source}
      </small>
    </section>
  );
}

export default function ReportRender({
  data,
  base,
}: {
  data: any;
  base?: string;
}) {
  return (
    <article className="report-paper">
      <header>
        <span className="eyebrow">
          {data.spec.kind === "record"
            ? "EXPERIMENT RECORD"
            : "RESEARCH REPORT"}
        </span>
        <h2>{data.spec.title}</h2>
        <p>
          {data.content_hash
            ? `r${data.revision} · ${data.content_hash}`
            : t("当前未保存预览")}
        </p>
        <small>
          {data.review === "reviewed" ? t("作者已标记复核") : t("待复核草案")}
        </small>
        {data.ai_call_id && (
          <p className="footnote">
            {t("含 AI 辅助生成内容；复核状态以上述修订为准。")}
          </p>
        )}
      </header>
      {data.blocks.map((b: any) => (
        <RenderBlock key={b.id} block={b} base={base} />
      ))}
      <section className="report-provenance">
        <h3>{t("数据来源与适用范围")}</h3>
        {Object.entries(data.sources).map(([id, source]: [string, any]) => (
          <details key={id}>
            <summary>
              {t(kindNames[source.manifest.kind as keyof typeof kindNames])} ·{" "}
              {source.manifest.provenance.run_name || id} ·{" "}
              {source.manifest.coverage.row_count} {t("行")}
            </summary>
            <p>
              {t(
                "恢复点、协议、数据摘要和缺失情况随此记录固定。说明文字不等于已验证的测量结论。",
              )}
            </p>
            <dl>
              <dt>{t("内容哈希")}</dt>
              <dd>{source.content_hash}</dd>
              <dt>{t("最长样本间隔（μs）")}</dt>
              <dd>{source.manifest.coverage.max_gap_us}</dd>
            </dl>
            <pre>{JSON.stringify(source.manifest, null, 2)}</pre>
          </details>
        ))}
      </section>
    </article>
  );
}
