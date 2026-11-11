import { lazy, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Button, ErrorBox, Field, Loading } from "./ui";
import { t } from "./i18n";
import TargetObservation from "./TargetObservation";

const Chart = lazy(() => import("./Chart"));
const number = (v: any) =>
  typeof v === "number" ? Number(v.toPrecision(5)).toString() : "—";

export function ProcessSummary({ value }: { value: any }) {
  const p = value?.process;
  if (!p) return null;
  if (p.status !== "recorded")
    return (
      <p className="notice">
        {t("过程未完整测量")}: {p.reason ?? p.status}
      </p>
    );
  return (
    <div className="process-summary">
      <strong>
        {t(p.raw_activity_seen ? "过程内测到活动" : "采样中未测到活动")}
      </strong>
      <dl className="readout-facts">
        {[
          ["active_node_count", "活动节点"],
          ["increased_node_count", "增强节点"],
          ["decreased_node_count", "减弱节点"],
          ["ended_node_count", "窗末前消退节点"],
          ["reactivated_node_count", "再次激活节点"],
          ["total_activation_variation", "累计活动变化"],
        ].map(([key, label]) => (
          <div key={key}>
            <dt>{t(label)}</dt>
            <dd>{number(p[key])}</dd>
          </div>
        ))}
      </dl>
      <p className="footnote">
        {t(
          "过程活动与收敛结果分别呈现；增强、减弱相对于刺激前基线，不单独证明因果。",
        )}{" "}
        {t("最大采样间隔")}{" "}
        {p.maximum_sample_gap_us == null
          ? "—"
          : `${Number(p.maximum_sample_gap_us) / 1000} ms`}
        .{p.sampling_gap_detected && <strong> {t("存在采样缺口")}</strong>}
        {p.baseline_status !== "measured" && (
          <strong>
            {" "}
            {t("基线未完整测得或配置为零参考；增减需结合基线条件解释。")}
          </strong>
        )}
      </p>
    </div>
  );
}

export function ProcessTools({
  base,
  recordId,
  hasSummary = false,
}: {
  base: string;
  recordId: number;
  hasSummary?: boolean;
}) {
  const [enabled, setEnabled] = useState(false),
    [offset, setOffset] = useState(0);
  const [right, setRight] = useState(""),
    [rightRun, setRightRun] = useState("");
  const [relative, setRelative] = useState(false),
    [comparison, setComparison] = useState<any>(null);
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const data = useQuery({
    queryKey: ["process-tool", base, recordId, offset],
    queryFn: () =>
      api(`${base}/readouts/${recordId}/process?offset=${offset}&limit=100`),
    enabled,
    gcTime: 0,
  });
  const p = data.data?.process;
  const chartRows = (key: string) =>
    (p?.timeline ?? []).map((r: any) => ({
      time_us: r.time_us,
      value: r[key],
    }));
  return (
    <section className="process-tools">
      <h3>{t("过程检测工具")}</h3>
      <p>
        {t(
          "查看短暂活动、先后转移与减弱；也可重新分析旧的完整轨迹，原记录保持不变。",
        )}
      </p>
      <Button onClick={() => setEnabled(!enabled)}>
        {t(enabled ? "收起过程分析" : "展开过程分析")}
      </Button>
      <TargetObservation
        key={`${base}:${recordId}`}
        base={base}
        recordId={recordId}
      />
      {enabled && (
        <>
          <ErrorBox error={data.error} />
          {data.isLoading ? (
            <Loading />
          ) : (
            p && (
              <>
                {!hasSummary && <ProcessSummary value={data.data} />}
                <Chart
                  rows={[]}
                  metric="value"
                  title={t("活动随时间变化")}
                  step
                  series={[
                    { name: t("总激活"), rows: chartRows("activation_total") },
                    {
                      name: t("相对基线增强"),
                      rows: chartRows("increase_over_baseline"),
                    },
                    {
                      name: t("相对基线减弱"),
                      rows: chartRows("decrease_below_baseline"),
                    },
                  ]}
                />
                <Chart
                  rows={chartRows("pattern_distance")}
                  metric="value"
                  title={t("相邻采样的活动分布变化")}
                  step
                />
                <p className="footnote">
                  {t(
                    "各节点峰值并非同一时刻；没有活动时分布距离留空。曲线只显示当前页采样。",
                  )}
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        {[
                          "节点",
                          "峰值",
                          "峰值时刻（秒）",
                          "增强幅度",
                          "减弱幅度",
                          "激活次数",
                          "累计活动变化",
                        ].map((h) => (
                          <th key={h}>{t(h)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.data.nodes.map((n: any) => (
                        <tr key={n.node_id}>
                          <td>
                            {n.node_id} {n.annotations?.join("、")}
                          </td>
                          <td>{number(n.process_peak_activation)}</td>
                          <td>
                            {n.process_peak_time_us == null
                              ? "—"
                              : number(Number(n.process_peak_time_us) / 1e6)}
                          </td>
                          <td>{number(n.positive_change_peak)}</td>
                          <td>{number(n.negative_change_peak)}</td>
                          <td>{n.activity_episode_count}</td>
                          <td>{number(n.total_activation_variation)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="readout-pagination">
                  <span>
                    {t("数据页（节点与采样各 100 条）")} {offset / 100 + 1}
                  </span>
                  <Button
                    disabled={!offset}
                    onClick={() => setOffset(offset - 100)}
                  >
                    {t("上一页")}
                  </Button>
                  <Button
                    disabled={
                      offset + 100 >=
                      Math.max(data.data.node_count, p.sample_count)
                    }
                    onClick={() => setOffset(offset + 100)}
                  >
                    {t("下一页")}
                  </Button>
                </div>
              </>
            )
          )}
        </>
      )}
      <details className="readout-provenance">
        <summary>{t("对照另一条完整轨迹")}</summary>
        <p>
          {t(
            "用于同源副本或节点身份对应的记录。比较全部已采样节点，不使用词语模板；对齐不到的时刻不会补零。",
          )}
        </p>
        <div className="query-controls">
          <Field label={t("对照证据编号")}>
            <input
              type="number"
              min="1"
              value={right}
              onChange={(e) => setRight(e.target.value)}
            />
          </Field>
          <Field label={t("对照意识 ID（留空为当前意识）")}>
            <input
              value={rightRun}
              onChange={(e) => setRightRun(e.target.value)}
            />
          </Field>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={relative}
              onChange={(e) => setRelative(e.target.checked)}
            />
            {t("按各自首个采样对齐")}
          </label>
          <Button
            disabled={busy || !right}
            onClick={async () => {
              setBusy(true);
              setError(null);
              setComparison(null);
              try {
                const q = new URLSearchParams({
                  left_id: String(recordId),
                  right_id: right,
                  relative: String(relative),
                  limit: "100",
                });
                if (rightRun) q.set("right_run", rightRun.trim());
                setComparison(await api(`${base}/readouts/compare?${q}`));
              } catch (e) {
                setError(e);
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("比较过程")}
          </Button>
        </div>
        <ErrorBox error={error} />
        {comparison && (
          <>
            {comparison.status !== "compared" && (
              <p className="notice">
                {t("没有可对齐的采样，无法判定轨迹相同或不同。")}
              </p>
            )}
            <p>
              {t("匹配采样")} {comparison.matched_samples} · {t("变化节点")}{" "}
              {comparison.changed_node_count} · {t("最大总差异")}{" "}
              {number(comparison.maximum_l1_difference)}
            </p>
            <p>
              {t("未匹配采样（左／右）")} {comparison.left_unmatched_samples} /{" "}
              {comparison.right_unmatched_samples}
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("节点")}</th>
                    <th>{t("最大差异")}</th>
                    <th>{t("对应时刻（秒）")}</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.nodes.map((n: any) => (
                    <tr key={n.node_id}>
                      <td>{n.node_id}</td>
                      <td>{number(n.difference_at_maximum)}</td>
                      <td>
                        {n.peak_time_us == null
                          ? "—"
                          : number(Number(n.peak_time_us) / 1e6)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="footnote">
              {t(
                "显示差异最大的前 100 个节点；完整比较可通过 Python／命令行导出。因果解释还需受控实验。",
              )}
            </p>
          </>
        )}
      </details>
    </section>
  );
}
