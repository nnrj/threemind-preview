import { lazy, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Button, ErrorBox, Field, Loading } from "./ui";
import { t } from "./i18n";
import { classes } from "./readoutLabels";

const Chart = lazy(() => import("./Chart"));
const number = (v: any) =>
  typeof v === "number" ? Number(v.toPrecision(7)).toString() : "—";
const seconds = (v: any) => (v == null ? "—" : number(Number(v) / 1e6));
const reasons: Record<string, string> = {
  already_active: "首个采样已有活动",
  response_entry: "响应出现",
  leader_change: "领先节点变化",
  observed_peak: "观测到先升后降",
  episode_maximum: "本段最大响应",
};

export default function ResponseObservation({
  base,
  recordId,
}: {
  base: string;
  recordId: number;
}) {
  const [ids, setIds] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [event, setEvent] = useState<number | null>(null);
  const [rankOffset, setRankOffset] = useState(0);
  const result = useQuery({
    queryKey: [
      "response-readout",
      base,
      recordId,
      query,
      offset,
      event,
      rankOffset,
    ],
    queryFn: () =>
      api(
        `${base}/readouts/${recordId}/response?${query}&offset=${offset}&rank_offset=${rankOffset}${event == null ? "" : `&event_index=${event}`}`,
      ),
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
  const value = result.data;
  const selected = value?.selected_event;
  return (
    <section className="response-observation">
      <h4>{t("响应收敛：读出短暂而明确的活动")}</h4>
      <p>
        {t(
          "不要求持续 800 毫秒。保留响应出现、峰值与领先节点变化；每次输出按同一采样时刻的激活强度排序。",
        )}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          setRankOffset(0);
          setEvent(null);
          setQuery(
            ids.trim()
              ? new URLSearchParams({
                  node_ids: ids
                    .trim()
                    .split(/[，,\s]+/)
                    .join(","),
                }).toString()
              : "",
          );
        }}
      >
        <div className="query-controls">
          <Field label={t("目标节点 ID（留空读取全部节点）")}>
            <input value={ids} onChange={(e) => setIds(e.target.value)} />
          </Field>
          <Button type="submit" disabled={result.isFetching}>
            {t("读取响应")}
          </Button>
        </div>
      </form>
      <ErrorBox error={result.error} />
      {result.isFetching && <Loading />}
      {value && (
        <>
          <dl className="readout-facts">
            <div>
              <dt>{t("响应")}</dt>
              <dd>
                {t(
                  value.status === "response_observed"
                    ? "检测到响应"
                    : value.status === "not_observed"
                      ? "未观察"
                      : value.raw_activity_seen
                        ? "检测到微弱活动（未超过数值容差）"
                        : "采样中未测到活动",
                )}
              </dd>
            </div>
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
              <dt>{t("响应段／读出时刻")}</dt>
              <dd>
                {value.episode_count} / {value.event_count}
              </dd>
            </div>
            <div>
              <dt>{t("采样间隔（毫秒）")}</dt>
              <dd>
                {number(
                  Number(value.configuration.expected_interval_us) / 1000,
                )}
              </dd>
            </div>
          </dl>
          {(value.original_censored || value.sampling_gap_count > 0) && (
            <p className="notice">
              {t("记录有边界截断或采样缺口；已测响应保留，缺失过程不补写。")}
            </p>
          )}
          {selected && (
            <div className="response-snapshot">
              <h5>{t("当前读出：同一时刻的激活排序")}</h5>
              <p>
                {seconds(selected.time_us)} {t("秒")} ·{" "}
                {selected.reasons.map((s: string) => t(reasons[s])).join(" · ")}
              </p>
              <p>
                {t("领先差值")} {number(selected.lead_margin)} ·{" "}
                {t("本段采样数")} {selected.episode_sample_count}
              </p>
              {selected.leader_ids.length > 1 && (
                <p>{t("领先节点并列，不强行选出唯一答案。")}</p>
              )}
              {selected.episode_sample_count === 1 && (
                <p className="notice">
                  {t("单点响应已保留；实际持续时间与点间过程未知。")}
                </p>
              )}
              {(selected.episode_left_censored ||
                selected.episode_right_censored) && (
                <p className="footnote">
                  {t(
                    "此段起点或终点超出已有采样，不能据此断定活动何时开始或结束。",
                  )}
                </p>
              )}
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("节点")}</th>
                      <th>{t("外部注释")}</th>
                      <th>{t("当前激活")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.ranking.map((n: any) => (
                      <tr key={n.node_id}>
                        <td>{n.node_id}</td>
                        <td>
                          {value.annotations[String(n.node_id)]?.join("、") ||
                            "—"}
                        </td>
                        <td>{number(n.activation)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="readout-pagination">
                <span>
                  {t("激活节点")} {selected.ranking_count}
                </span>
                <Button
                  disabled={!rankOffset}
                  onClick={() => setRankOffset(rankOffset - 100)}
                >
                  {t("上一页")}
                </Button>
                <Button
                  disabled={rankOffset + 100 >= selected.ranking_count}
                  onClick={() => setRankOffset(rankOffset + 100)}
                >
                  {t("下一页")}
                </Button>
                <Button
                  disabled={event == null}
                  onClick={() => {
                    setEvent(null);
                    setRankOffset(0);
                  }}
                >
                  {t("返回本窗最大响应")}
                </Button>
              </div>
              <p className="footnote">
                {t(
                  "默认展示本窗总激活最大的响应时刻（并列取最早）。这不等于答案最正确；可逐项查看其他响应。零激活节点省略，未拼接不同时刻的峰值。",
                )}
              </p>
            </div>
          )}
          <Chart
            rows={value.timeline}
            metric="activation_total"
            title={t("总激活随时间变化（当前页）")}
            step
            fitTimeRange
          />
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("时刻（秒）")}</th>
                  <th>{t("观测内容")}</th>
                  <th>{t("总激活")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {value.events.map((e: any) => (
                  <tr key={e.index}>
                    <td>{seconds(e.time_us)}</td>
                    <td>
                      {e.reasons.map((s: string) => t(reasons[s])).join(" · ")}
                    </td>
                    <td>{number(e.activation_total)}</td>
                    <td>
                      <Button
                        aria-pressed={selected?.index === e.index}
                        onClick={() => {
                          setEvent(e.index);
                          setRankOffset(0);
                        }}
                      >
                        {t("查看此刻")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="readout-pagination">
            <span>
              {t("数据页（响应与采样各 100 条）")} {offset / 100 + 1}
            </span>
            <Button disabled={!offset} onClick={() => setOffset(offset - 100)}>
              {t("上一页")}
            </Button>
            <Button
              disabled={
                offset + 100 >= Math.max(value.event_count, value.sample_count)
              }
              onClick={() => setOffset(offset + 100)}
            >
              {t("下一页")}
            </Button>
            <a
              href={`/api/v2${base}/readouts/${recordId}/response?${query}&download=true`}
            >
              {t("导出完整响应 JSON")}
            </a>
          </div>
          <p className="footnote">
            {t(
              "响应收敛是本项目对响应形成结果的称呼，不等同于持续稳态。检测器不判断词义、正确答案或意识；完整轨迹和原全局判定保留。",
            )}
          </p>
        </>
      )}
    </section>
  );
}
