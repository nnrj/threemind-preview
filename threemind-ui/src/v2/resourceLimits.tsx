import { t } from "./i18n";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, RefreshCw } from "lucide-react";
import { api, type Run } from "./api";
import { Button, Empty, ErrorBox, Field, Loading, Metric } from "./ui";

const counters = [
  ["node_capacity_rejections", "节点出生受限"],
  ["edge_capacity_rejections", "连接出生受限"],
  ["adaptation_budget_skips", "连接适应跳过"],
  ["propagation_budget_skips", "兴奋传播跳过"],
] as const;
const limits = [
  ["max_nodes", "节点容量"],
  ["max_edges", "连接容量"],
  ["edge_adaptation_limit", "每周期适应预算"],
  ["propagation_limit", "每步传播预算"],
] as const;
type Resources = {
  since_us: string;
  adaptation_period_us: string;
  adaptations_used: number;
  counter_overflowed: boolean;
  step_us: number;
  limits: Record<(typeof limits)[number][0], number | null>;
} & Record<(typeof counters)[number][0], string>;
type Evidence = {
  latest: Resources | null;
  latest_time_us: string;
  revision: number;
  rows: { time_us: string; resources: Resources; quality: string }[];
  more: boolean;
  next: string;
};

export default function ResourcePanel({
  base,
  run,
}: {
  base: string;
  run: Run;
}) {
  const [start, setStart] = useState("0"),
    [end, setEnd] = useState("");
  const [filter, setFilter] = useState({ after: "0", until: "" });
  const [pages, setPages] = useState(["0"]),
    [error, setError] = useState("");
  const selection = new URLSearchParams({ after: filter.after });
  if (filter.until) selection.set("until", filter.until);
  const current = new URLSearchParams(selection);
  current.set("after", pages[pages.length - 1]);
  const evidence = useQuery({
    queryKey: ["resources", base, current.toString()],
    queryFn: () => api<Evidence>(`${base}/resources?${current}`),
    refetchInterval: run.status === "running" ? 3000 : false,
  });
  useEffect(() => {
    void evidence.refetch();
  }, [run.revision, evidence.refetch]);
  const latest = evidence.data?.latest;
  return (
    <section className="panel resource-panel" aria-label={t("容量与预算记录")}>
      <div className="panel-heading">
        <div>
          <h2>{t("容量与计算预算")}</h2>
          <p>{t("限额改变模型的演化条件。显示性能档位不会修改这些参数。")}</p>
        </div>
        <Link
          className="text-link"
          to="/docs?doc=docs%2Fzh%2Fv2-resource-limits.md"
        >
          {t("计数口径与公式")}
        </Link>
      </div>
      {latest && (
        <>
          <div className="resource-limit-summary">
            {limits.map(([key, label]) => (
              <span key={key}>
                {t(label)} <strong>{latest.limits[key] ?? t("不限制")}</strong>
              </span>
            ))}
          </div>
          <div className="metrics-grid">
            {counters.map(([key, label]) => (
              <Metric
                key={key}
                label={t(label)}
                value={<span className="resource-count">{latest[key]}</span>}
                detail={t("累计次数")}
              />
            ))}
          </div>
          <p className="footnote">
            {t("统计起点 ")}
            {latest.since_us}
            {t(" μs · 最新恢复点")} {evidence.data!.latest_time_us} μs · r
            {evidence.data!.revision}
            {t("。适应账本记录周期 ")}
            {latest.adaptation_period_us}
            {t(" μs，已用")} {latest.adaptations_used}
            {t(" 次；周期宽度 ")}
            {latest.step_us}{" "}
            {t("μs。账本在实际使用预算时推进，查看页面不会重置它。")}
          </p>
          {latest.counter_overflowed && (
            <p className="notice">
              {t(
                "累计计数已达到 128 位上限；达到上限的值是下界，不能继续解释为精确次数。",
              )}
            </p>
          )}
        </>
      )}
      {!latest && !evidence.isPending && (
        <p className="notice">
          {t(
            "此运行尚无容量与预算账本。旧版模型不会被补记为零；启用限额后，从明确的升级时间开始记录。",
          )}
        </p>
      )}
      <details className="resource-history" open>
        <summary>{t("已提交的观测记录")}</summary>
        <p className="footnote">
          {t(
            "按模拟时间筛选，保留原始整数计数。观测点之间可能发生多次操作，不能把计数变化当作操作的精确发生时间。",
          )}
        </p>
        <form
          className="resource-filters"
          onSubmit={(e) => {
            e.preventDefault();
            const valid = (s: string) =>
              /^(0|[1-9][0-9]*)$/.test(s) && BigInt(s) <= (1n << 128n) - 1n;
            if (
              !valid(start) ||
              (end !== "" && (!valid(end) || BigInt(end) < BigInt(start)))
            ) {
              setError(
                t("请输入有效的非负整数微秒，结束时间不能小于起始时间。"),
              );
              return;
            }
            setError("");
            setFilter({ after: start, until: end });
            setPages([start]);
          }}
        >
          <Field label={t("起始时间（微秒）")}>
            <input
              inputMode="numeric"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </Field>
          <Field label={t("结束时间（微秒）")}>
            <input
              inputMode="numeric"
              placeholder={t("不限制")}
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </Field>
          <Button>{t("应用筛选")}</Button>
          <Button
            type="button"
            onClick={() => evidence.refetch()}
            disabled={evidence.isFetching}
          >
            <RefreshCw size={15} />
            {t("刷新")}
          </Button>
        </form>
        <ErrorBox error={error || evidence.error} />
        {evidence.isPending ? (
          <Loading />
        ) : evidence.data?.rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("模拟时间（μs）")}</th>
                  {counters.map(([key, label]) => (
                    <th key={key}>{t(label)}</th>
                  ))}
                  <th>{t("计数状态")}</th>
                </tr>
              </thead>
              <tbody>
                {evidence.data.rows.map((row) => (
                  <tr key={row.time_us}>
                    <td className="mono">{row.time_us}</td>
                    {counters.map(([key]) => (
                      <td className="mono" key={key}>
                        {row.resources[key]}
                      </td>
                    ))}
                    <td>
                      {row.resources.counter_overflowed
                        ? t("已饱和／下界")
                        : t("精确累计")}{" "}
                      · {row.quality}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={t("所选区间暂无预算观测")}
            detail={t("运行采集后会显示已提交的数据；调整筛选不会改变模型。")}
          />
        )}
        <div className="resource-actions">
          <div className="page-actions">
            <Button
              disabled={pages.length === 1}
              onClick={() => setPages((p) => p.slice(0, -1))}
            >
              {t("上一页")}
            </Button>
            <span>{t("第 {page} 页", { page: pages.length })}</span>
            <Button
              disabled={!evidence.data?.more}
              onClick={() => setPages((p) => [...p, evidence.data!.next])}
            >
              {t("下一页")}
            </Button>
          </div>
          <div className="page-actions">
            {["csv", "jsonl"].map((format) => (
              <a
                key={format}
                className="button"
                href={`/api/v2${base}/resources/export?${selection}&format=${format}`}
              >
                <Download size={15} />
                {t("导出筛选 ")}
                {format.toUpperCase()}
              </a>
            ))}
          </div>
        </div>
        <p className="footnote">
          {t(
            "导出包含筛选区间内的全部已提交观测，不受当前分页限制。JSONL 附带筛选范围、导出时的数据版本与状态校验值。",
          )}
        </p>
      </details>
    </section>
  );
}
