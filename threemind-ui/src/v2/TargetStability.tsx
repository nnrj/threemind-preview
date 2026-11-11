import { lazy, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Button, ErrorBox, Field, Loading } from "./ui";
import { t } from "./i18n";
import { classes, localStates } from "./readoutLabels";

const Chart = lazy(() => import("./Chart"));
const number = (v: any) =>
  typeof v === "number" ? Number(v.toPrecision(6)).toString() : "—";

export default function TargetStability({
  base,
  recordId,
}: {
  base: string;
  recordId: number;
}) {
  const [ids, setIds] = useState("");
  const [settle, setSettle] = useState("800");
  const [pattern, setPattern] = useState("0.08");
  const [amplitude, setAmplitude] = useState("0.12");
  const [floor, setFloor] = useState("0.00000001");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const result = useQuery({
    queryKey: ["target-observation", base, recordId, query, offset],
    queryFn: () =>
      api(`${base}/readouts/${recordId}/target?${query}&offset=${offset}`),
    enabled: !!query,
    gcTime: 0,
  });
  const value = result.data;
  return (
    <section className="target-stability">
      <h4>{t("持续稳定（旧版）")}</h4>
      <p className="notice">
        {t(
          "持续稳定是单独的分析条件；不满足它，不表示没有响应。旧判据与默认 800 毫秒保持不变。",
        )}
      </p>
      <p>
        {t(
          "指定节点分析完整过程；目标响应、局部稳定与全局收敛分别呈现。原始活动不会被删改。",
        )}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          setQuery(
            new URLSearchParams({
              node_ids: ids
                .trim()
                .split(/[，,\s]+/)
                .join(","),
              settle_us: String(Number(settle) * 1000),
              pattern_drift_max: pattern,
              amplitude_drift_max: amplitude,
              response_floor: floor,
            }).toString(),
          );
        }}
      >
        <div className="query-controls">
          <Field label={t("目标节点 ID（逗号分隔）")}>
            <input
              required
              value={ids}
              onChange={(e) => setIds(e.target.value)}
            />
          </Field>
          <Button type="submit" disabled={!ids.trim() || result.isFetching}>
            {t("分析目标响应")}
          </Button>
        </div>
        <details>
          <summary>{t("局部判定参数")}</summary>
          <div className="query-controls">
            <Field label={t("稳定观察长度（毫秒）")}>
              <input
                type="number"
                min="0.001"
                max="60000"
                step="any"
                required
                value={settle}
                onChange={(e) => setSettle(e.target.value)}
              />
            </Field>
            <Field label={t("模式最大分布距离")}>
              <input
                type="number"
                min="0"
                max="1"
                step="any"
                required
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
              />
            </Field>
            <Field label={t("最大总幅度相对变化")}>
              <input
                type="number"
                min="0"
                max="1"
                step="any"
                required
                value={amplitude}
                onChange={(e) => setAmplitude(e.target.value)}
              />
            </Field>
            <Field label={t("响应总量下限")}>
              <input
                type="number"
                min="0"
                max="1"
                step="any"
                required
                value={floor}
                onChange={(e) => setFloor(e.target.value)}
              />
            </Field>
          </div>
        </details>
      </form>
      <p className="footnote">
        {t(
          "确认性实验应事先确定目标和参数；事后选取只作探索。局部模式稳定仍可能伴随整体衰减。",
        )}
      </p>
      <ErrorBox error={result.error} />
      {result.isFetching && <Loading />}
      {value && (
        <>
          <dl className="readout-facts">
            <div>
              <dt>{t("原全局判定")}</dt>
              <dd>
                {t(
                  classes[value.original_classification] ??
                    value.original_classification,
                )}
              </dd>
            </div>
            <div>
              <dt>{t("目标活动")}</dt>
              <dd>
                {t(
                  value.process.status !== "recorded"
                    ? "未观察"
                    : value.process.raw_activity_seen
                      ? "过程内测到活动"
                      : "采样中未测到活动",
                )}
              </dd>
            </div>
            <div>
              <dt>{t("首次局部模式收敛（秒）")}</dt>
              <dd>
                {value.first_pattern_convergence
                  ? number(
                      Number(value.first_pattern_convergence.time_us) / 1e6,
                    )
                  : "—"}
              </dd>
            </div>
            <div>
              <dt>{t("首次局部稳态（秒）")}</dt>
              <dd>
                {value.first_steady_convergence
                  ? number(Number(value.first_steady_convergence.time_us) / 1e6)
                  : "—"}
              </dd>
            </div>
            <div>
              <dt>{t("窗末局部状态")}</dt>
              <dd>
                {t(
                  localStates[value.terminal_local_state.status] ??
                    value.terminal_local_state.status,
                )}
              </dd>
            </div>
          </dl>
          {(value.original_censored || value.process.sampling_gap_detected) && (
            <p className="notice">
              {t("记录有删失或采样缺口；已测活动保留，缺失期间不能判定稳定。")}
            </p>
          )}
          {value.process.baseline_status !== "measured" && (
            <p className="footnote">
              {t("基线未完整测得或配置为零参考；增减需结合基线条件解释。")}
            </p>
          )}
          <Chart
            rows={value.process.timeline ?? []}
            metric="activation_total"
            title={t("目标总激活随时间变化")}
            step
            fitTimeRange
          />
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "节点",
                    "峰值",
                    "激活积分",
                    "窗末激活",
                    "激活次数",
                    "累计活动变化",
                  ].map((h) => (
                    <th key={h}>{t(h)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {value.nodes.map((n: any) => (
                  <tr key={n.node_id}>
                    <td>
                      {n.node_id} {n.annotations?.join("、")}
                    </td>
                    <td>{number(n.process_peak_activation)}</td>
                    <td>{number(n.sampled_activation_integral)}</td>
                    <td>{number(n.terminal_activation)}</td>
                    <td>{n.activity_episode_count}</td>
                    <td>{number(n.total_activation_variation)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="readout-pagination">
            <span>
              {t("曲线采样页")} {offset / 100 + 1}
            </span>
            <Button disabled={!offset} onClick={() => setOffset(offset - 100)}>
              {t("上一页")}
            </Button>
            <Button
              disabled={offset + 100 >= value.process.sample_count}
              onClick={() => setOffset(offset + 100)}
            >
              {t("下一页")}
            </Button>
            <a
              href={`/api/v2${base}/readouts/${recordId}/target?${query}&download=true`}
            >
              {t("导出完整目标分析 JSON")}
            </a>
          </div>
        </>
      )}
    </section>
  );
}
