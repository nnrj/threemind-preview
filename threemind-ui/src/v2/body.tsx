import { t } from "./i18n";
import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type Run } from "./api";
import { Button, Empty, ErrorBox, Field, Loading, Metric } from "./ui";
const Chart = lazy(() => import("./Chart"));
const WorldObservation = lazy(() => import("./WorldObservation"));
const sources: Record<string, string> = {
  mujoco: "模拟物理环境",
  "ambient-fixture": "合成环境基底",
  "ambient-disturbance": "合成环境扰动",
  "simulated-interoception": "模拟内感受",
};
const reasons: Record<string, string> = {
  body_passed: "躯体已编码",
  body_sampling: "未到躯体采样时间",
  body_threshold: "未达到感知阈值",
  bypass: "躯体过滤关闭",
  phase_input_disabled: "实验阶段关闭输入",
  sources_closed: "全部来源已关闭",
};

export default function BodyPanel({
  base,
  run,
  configure,
  inspect,
}: {
  base: string;
  run: Run;
  configure: () => void;
  inspect: (id: string) => void;
}) {
  const [checkpoint, setCheckpoint] = useState("");
  const [historyPages, setHistoryPages] = useState<(number | null)[]>([null]);
  const [pages, setPages] = useState<(number | null)[]>([null]);
  const [source, setSource] = useState("");
  const [start, setStart] = useState("0"),
    [until, setUntil] = useState("");
  const [range, setRange] = useState({ start: "0", until: "" }),
    [error, setError] = useState("");
  const history = useQuery({
    queryKey: ["body-checkpoints", base, historyPages.at(-1)],
    queryFn: () =>
      api<any>(
        `${base}/checkpoint-history${historyPages.at(-1) ? `?before=${historyPages.at(-1)}` : ""}`,
      ),
    enabled: !!run.revision,
    refetchOnWindowFocus: false,
  });
  const selectedCheckpoint = checkpoint || history.data?.rows[0]?.id || "";
  const params = new URLSearchParams({ source, after_us: range.start });
  if (range.until) params.set("until_us", range.until);
  if (selectedCheckpoint) params.set("checkpoint_id", selectedCheckpoint);
  if (pages.at(-1)) params.set("before", String(pages.at(-1)));
  const evidence = useQuery({
    queryKey: ["body-tools", base, params.toString()],
    queryFn: () => api<any>(`${base}/body-tools?${params}`),
    enabled: !!run.revision && !!selectedCheckpoint,
    refetchOnWindowFocus: false,
    gcTime: 0,
  });
  const data = evidence.data;
  const rows: any[] = data?.rows ?? [];
  const status = data?.status;
  const download = new URLSearchParams(params);
  download.delete("before");
  if (data) download.set("checkpoint_id", data.checkpoint_id);
  const timeline = new Map<
    string,
    { time_us: string; raw: number; sensed: number }
  >();
  for (const row of rows) {
    const v = timeline.get(row.scheduled_time_us) ?? {
      time_us: row.scheduled_time_us,
      raw: 0,
      sensed: 0,
    };
    v.raw += row.raw.channels.length;
    v.sensed +=
      row.transduction?.passed_channels ?? row.stimulus.channels.length;
    timeline.set(v.time_us, v);
  }
  const chart = [...timeline.values()].sort((a, b) =>
    BigInt(a.time_us) < BigInt(b.time_us) ? -1 : 1,
  );
  return (
    <section
      className="panel resource-panel body-panel"
      role="region"
      aria-label={t("环境与躯体")}
    >
      <div className="panel-heading">
        <div>
          <h2>{t("环境与躯体")}</h2>
          <p>{t("查看外部载体如何经过躯体的采样、阈值、适应与测量噪声。")}</p>
        </div>
        <Button onClick={configure}>{t("配置环境与躯体")}</Button>
      </div>
      {data?.has_world && (
        <Suspense fallback={<Loading />}>
          <WorldObservation base={base} checkpoint={data.checkpoint_id} />
        </Suspense>
      )}
      <p className="notice">
        {t(
          "合成环境场与模拟内感受是显式实验工具。它们不代表真实生理测量，也不是模型的自发活动。默认物理环境保持独立；全部来源关闭后，这些工具停止产生新刺激。",
        )}
      </p>
      <form
        className="resource-filters"
        onSubmit={(e) => {
          e.preventDefault();
          if (
            !/^\d+$/.test(start) ||
            (until && (!/^\d+$/.test(until) || BigInt(until) < BigInt(start)))
          ) {
            setError(t("请输入非负整数时间，结束时间不能早于起始时间。"));
            return;
          }
          setError("");
          setRange({ start, until });
          setPages([null]);
        }}
      >
        <Field label={t("环境载体来源")}>
          <select
            aria-label={t("环境载体来源")}
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setPages([null]);
            }}
          >
            <option value="">{t("全部来源")}</option>
            {Object.entries(sources).map(([v, label]) => (
              <option key={v} value={v}>
                {t(label)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("载体起始时间（μs）")}>
          <input
            value={start}
            onChange={(e) => setStart(e.target.value)}
            inputMode="numeric"
          />
        </Field>
        <Field label={t("载体结束时间（μs）")}>
          <input
            value={until}
            onChange={(e) => setUntil(e.target.value)}
            inputMode="numeric"
            placeholder={t("不限")}
          />
        </Field>
        <Button type="submit">{t("筛选载体")}</Button>
      </form>
      <div className="query-controls">
        <Field label={t("环境证据检查点")}>
          <select
            aria-label={t("环境证据检查点")}
            value={selectedCheckpoint}
            onChange={(e) => {
              setCheckpoint(e.target.value);
              setPages([null]);
            }}
          >
            <option value="" disabled>
              {t("选择检查点")}
            </option>
            {history.data?.rows.map((c: any) => (
              <option value={c.id} key={c.id}>
                r{c.revision} · {c.time_us} μs
              </option>
            ))}
          </select>
        </Field>
        <Button
          onClick={async () => {
            const refreshed = await history.refetch();
            setCheckpoint(refreshed.data?.rows[0]?.id ?? "");
            setPages([null]);
            await evidence.refetch();
          }}
        >
          {t("刷新证据")}
        </Button>
      </div>
      <p className="footnote">
        {t(
          "检查点每组 50 个；可翻组查看更早版本。每页 30 个载体，图表只汇总当前页。导出包含该检查点内符合筛选条件的全部载体。",
        )}
      </p>
      <div className="pagination">
        <Button
          disabled={historyPages.length === 1}
          onClick={() => {
            setHistoryPages((p) => p.slice(0, -1));
            setCheckpoint("");
            setPages([null]);
          }}
        >
          {t("较新检查点")}
        </Button>
        <span>{t("第 {page} 组", { page: historyPages.length })}</span>
        <Button
          disabled={!history.data?.more}
          onClick={() => {
            setHistoryPages((p) => [...p, history.data.next]);
            setCheckpoint("");
            setPages([null]);
          }}
        >
          {t("较旧检查点")}
        </Button>
      </div>
      <ErrorBox error={error || history.error || evidence.error} />
      {evidence.isLoading && <Loading />}
      {!run.revision && (
        <Empty
          title={t("尚无检查点")}
          detail={t("运行提交后会在这里显示环境和躯体证据。")}
        />
      )}
      {data && (
        <>
          <p className="mono spatial-hash">
            r{data.revision} · {data.time_us} μs · {data.state_hash}
          </p>
          {status && (
            <div className="metrics-grid">
              <Metric
                label={t("环境载体")}
                value={status.environment_samples}
                detail={t("包含未被躯体感知的载体")}
              />
              <Metric
                label={t("模拟内感受载体")}
                value={status.interoceptive_samples}
                detail={t("独立的显式模拟信号")}
              />
              <Metric
                label={t("未到采样时间")}
                value={status.body_filter.counters.sampling_filtered}
                detail={t("保留原始载体，未送入内核")}
              />
              <Metric
                label={t("已保存基线通道")}
                value={status.body_filter.baseline_channels}
                detail={t("累计淘汰 {value0}", {
                  value0: String(status.body_filter.counters.baseline_evicted),
                })}
              />
            </div>
          )}
          <details className="readout-provenance">
            <summary>{t("该检查点的外部工具参数与状态")}</summary>
            <pre>
              {JSON.stringify(
                { configuration: data.configuration, status },
                null,
                2,
              )}
            </pre>
          </details>
          {rows.length ? (
            <>
              <Chart
                rows={[]}
                metric="count"
                title={t("当前页载体通道条目数")}
                topPadding={24}
                series={[
                  {
                    name: t("原始载体"),
                    rows: chart.map((r) => ({
                      time_us: r.time_us,
                      count: r.raw,
                    })),
                  },
                  {
                    name: t("感官编码"),
                    rows: chart.map((r) => ({
                      time_us: r.time_us,
                      count: r.sensed,
                    })),
                  },
                ]}
              />
              <p className="footnote">
                {t(
                  "感官编码位于输入总线与内核注意选择之前，不代表通道已经激活模型。相同时间的载体条目在此相加，原始独立帧边界仍然保留。",
                )}
              </p>
              <div className="table-scroll attention-history">
                <table>
                  <thead>
                    <tr>
                      <th>{t("时间（μs）／来源")}</th>
                      <th>{t("原始／感知通道")}</th>
                      <th>{t("躯体／递送状态")}</th>
                      <th>{t("原始与编码值")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.frame_id}>
                        <td>
                          {row.scheduled_time_us}
                          <small>
                            {t(sources[row.source] ?? row.source ?? "")}
                          </small>
                        </td>
                        <td>
                          {row.raw.channels.length} /{" "}
                          {row.transduction?.passed_channels ??
                            row.stimulus.channels.length}
                        </td>
                        <td>
                          {t(
                            reasons[row.transduction?.reason] ??
                              row.transduction?.reason ??
                              "未使用躯体过滤",
                          )}
                          <small>
                            {row.status === "delivered"
                              ? t("已递送 {value0} μs", {
                                  value0: String(row.delivered_time_us),
                                })
                              : row.status === "filtered"
                                ? t(reasons[row.reason] ?? row.reason ?? "")
                                : t("等待递送")}
                          </small>
                        </td>
                        <td>
                          <details>
                            <summary>{t("查看数值")}</summary>
                            <pre>
                              {JSON.stringify(
                                {
                                  raw: row.raw,
                                  encoded: row.stimulus,
                                  transduction: row.transduction,
                                  input_gate: row.input_gate,
                                },
                                null,
                                2,
                              )}
                            </pre>
                          </details>
                        </td>
                        <td>
                          <Button onClick={() => inspect(row.envelope_id)}>
                            {t("载体详情")}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <Empty
              title={t("没有匹配的环境载体")}
              detail={t("扩大时间范围，或在参数中配置相应环境与躯体工具。")}
            />
          )}
          <div className="pagination">
            <Button
              disabled={pages.length === 1}
              onClick={() => setPages((p) => p.slice(0, -1))}
            >
              {t("较新载体")}
            </Button>
            <span>{t("第 {page} 页", { page: pages.length })}</span>
            <Button
              disabled={!data.more}
              onClick={() => setPages((p) => [...p, data.next])}
            >
              {t("较旧载体")}
            </Button>
          </div>
          <div className="readout-downloads">
            {["csv", "jsonl"].map((format) => (
              <a
                key={format}
                className="text-link"
                href={`/api/v2${base}/body-tools/export?${download}&format=${format}`}
                download
              >
                {t("完整载体 ")}
                {format.toUpperCase()}
              </a>
            ))}
          </div>
        </>
      )}
      <Link className="text-link" to="/docs?doc=docs%2Fzh%2Fv2-body-tools.md">
        {t("环境与躯体的规则、公式和恢复边界")}
      </Link>
    </section>
  );
}
