import { t } from "./i18n";
import { lazy, useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, Settings2 } from "lucide-react";
import { api, post, type Run } from "./api";
import { Button, Empty, ErrorBox, Field, Loading, Metric } from "./ui";
const Chart = lazy(() => import("./Chart"));

type Effective = {
  gain: number;
  budget_multiplier: number;
  competition_enabled: boolean;
  effective_budget: number | null;
  sources: string[];
};
type Ledger = {
  since_us: string;
  evaluated_frames: string;
  considered_channels: string;
  passed_channels: string;
  suppressed_channels: string;
  counter_overflowed: boolean;
  effective: Effective;
  modulators: {
    source: string;
    gain: number;
    budget_multiplier: number;
    competition_enabled: boolean;
    updated_us: string;
    expires_us: string;
  }[];
};
type Evidence = {
  latest: Ledger | null;
  revision: number;
  latest_time_us: string;
  more: boolean;
  next: string;
  rows: { time_us: string; attention: Ledger }[];
};
type Journal = {
  more: boolean;
  next: number;
  rows: {
    id: number;
    time_us: string;
    kind: string;
    payload: Record<string, unknown>;
    commit_revision: number;
  }[];
};
const stages: Record<string, string> = {
  input_modulation: "命令已处理",
  input_modulation_scheduled: "排队结果",
  input_modulation_delivered: "实际递送",
};

export default function AttentionPanel({
  base,
  run,
  configure,
}: {
  base: string;
  run: Run;
  configure: () => void;
}) {
  const [start, setStart] = useState("0"),
    [end, setEnd] = useState("");
  const [filter, setFilter] = useState({ after: "0", until: "" }),
    [pages, setPages] = useState(["0"]);
  const [journalPages, setJournalPages] = useState([0]);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [gain, setGain] = useState("1"),
    [budget, setBudget] = useState("1"),
    [ttl, setTtl] = useState("30"),
    [competition, setCompetition] = useState(false);
  const attempt = useRef({ fingerprint: "", id: "" });
  const selection = new URLSearchParams({ after: filter.after });
  if (filter.until) selection.set("until", filter.until);
  const current = new URLSearchParams(selection);
  current.set("after", pages.at(-1)!);
  const refresh = run.status === "running" ? 3000 : false;
  const evidence = useQuery({
    queryKey: ["attention", base, current.toString()],
    queryFn: () => api<Evidence>(`${base}/attention?${current}`),
    refetchInterval: refresh,
    gcTime: 0,
  });
  const journal = useQuery({
    queryKey: ["attention-journal", base, journalPages.at(-1)],
    queryFn: () =>
      api<Journal>(`${base}/attention/events?after=${journalPages.at(-1)}`),
    refetchInterval: refresh,
    gcTime: 0,
  });
  useEffect(() => {
    void evidence.refetch();
    void journal.refetch();
    setNotice("");
  }, [run.revision, run.status, evidence.refetch, journal.refetch]);
  const modulate = useMutation({
    mutationFn: () => {
      const payload = {
        gain: Number(gain),
        budget_multiplier: Number(budget),
        competition_enabled: competition,
        ttl_us: Math.round(Number(ttl) * 1e6),
      };
      const fingerprint = JSON.stringify(payload);
      if (attempt.current.fingerprint !== fingerprint)
        attempt.current = { fingerprint, id: crypto.randomUUID() };
      return post(`${base}/attention/modulate`, {
        ...payload,
        request_id: attempt.current.id,
      });
    },
    onSuccess: () => {
      attempt.current = { fingerprint: "", id: "" };
      setNotice(
        run.status === "paused"
          ? t("调制已排队，继续运行后递送。")
          : t("调制已排队；实际生效或拒绝结果会出现在递送记录中。"),
      );
      void journal.refetch();
    },
  });
  const latest = evidence.data?.latest,
    rows = evidence.data?.rows ?? [];
  const allowed =
    !run.spec.study_id &&
    run.life !== "dead" &&
    ["queued", "running", "paused", "blocked"].includes(run.status);
  return (
    <div
      className="attention-page"
      role="region"
      aria-label={t("输入注意与调制")}
    >
      <section className="panel resource-panel">
        <div className="panel-heading">
          <div>
            <h2>{t("输入注意与环境竞争")}</h2>
            <p>
              {t(
                "每个带时间戳的感官帧独立选择通道；默认透明传递，不作语义优先排序。",
              )}
            </p>
          </div>
          <Button onClick={configure}>
            <Settings2 size={15} />
            {t("配置注意参数")}
          </Button>
        </div>
        <p className="notice">
          {t("固定竞争：")}
          {run.spec.config?.attention_competition_enabled
            ? t("已启用")
            : t("未启用")}
          {t(
            "。临时调制可显式请求竞争；仅改变增益或容量倍率不会自动开启竞争。原始刺激与实际通过结果分开保存。",
          )}
        </p>
        {latest ? (
          <>
            <div className="metrics-grid">
              <Metric
                label={t("统计帧数")}
                value={latest.evaluated_frames}
                detail={t("仅计门控参与的帧")}
              />
              <Metric
                label={t("考虑通道数")}
                value={latest.considered_channels}
                detail={t("各帧通道累计")}
              />
              <Metric
                label={t("通过通道数")}
                value={latest.passed_channels}
                detail={t("通过不保证产生激活")}
              />
              <Metric
                label={t("抑制通道数")}
                value={latest.suppressed_channels}
                detail={t("未送入核心响应")}
              />
            </div>
            <p className="footnote">
              {t("最近检查点 r")}
              {evidence.data!.revision} · {evidence.data!.latest_time_us}
              {t(" μs · 统计起点 ")}
              {latest.since_us} {t("μs。当前总增益 ")}
              {latest.effective.gain}
              {t("，容量倍率")} {latest.effective.budget_multiplier}
              {t("，竞争")}
              {latest.effective.competition_enabled
                ? t("开启，每帧容量 {value0}", {
                    value0: String(latest.effective.effective_budget),
                  })
                : t("关闭，通道不限")}
              。
            </p>
            {latest.counter_overflowed && (
              <p className="notice">
                {t("累计计数已饱和，仅可视为下界，不用于精确比例或差值。")}
              </p>
            )}
          </>
        ) : (
          <p className="footnote">
            {t("尚无注意账本。旧版本的历史不会补造为零。")}
          </p>
        )}
        <Link className="text-link" to="/docs?doc=docs%2Fzh%2Fv2-attention.md">
          {t("选择规则、模拟时间期限与证据边界")}
        </Link>
      </section>
      <section className="panel resource-panel">
        <h2>{t("临时标量调制")}</h2>
        <p className="footnote">
          {t(
            "这是显式外部输入端口。命令处理后至少经过内核传播延迟才生效；更早到达的刺激使用原参数。当前表单使用同一个来源，新递送覆盖该来源的旧值；多个来源共同作用，过期按模拟时间判定。调制自身不会产生节点或激活。",
          )}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setNotice("");
            modulate.mutate();
          }}
        >
          <div className="resource-filters">
            <Field label={t("刺激增益")}>
              <input
                type="number"
                min="0"
                max="2"
                step="any"
                required
                value={gain}
                onChange={(e) => setGain(e.target.value)}
                disabled={!allowed || modulate.isPending}
              />
            </Field>
            <Field label={t("注意容量倍率")}>
              <input
                type="number"
                min="0"
                max="2"
                step="any"
                required
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                disabled={!allowed || modulate.isPending}
              />
            </Field>
            <Field label={t("有效时长（模拟秒）")}>
              <input
                type="number"
                min="0.000001"
                max="1000000"
                step="0.000001"
                required
                value={ttl}
                onChange={(e) => setTtl(e.target.value)}
                disabled={!allowed || modulate.isPending}
              />
            </Field>
            <label className="check">
              <input
                type="checkbox"
                checked={competition}
                onChange={(e) => setCompetition(e.target.checked)}
                disabled={!allowed || modulate.isPending}
              />
              {t("临时请求通道竞争")}
            </label>
            <Button type="submit" disabled={!allowed || modulate.isPending}>
              {t("递送调制")}
            </Button>
          </div>
          {!allowed && (
            <p className="footnote">
              {t("冻结实验或已结束的意识不接受人工插入调制。")}
            </p>
          )}
          {notice && (
            <p className="notice" role="status">
              {notice}
            </p>
          )}
          <ErrorBox error={modulate.error} />
        </form>
        {latest && latest.modulators.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("来源")}</th>
                  <th>{t("增益 / 容量倍率")}</th>
                  <th>{t("请求竞争")}</th>
                  <th>{t("到期模拟时间（μs）")}</th>
                  <th>{t("最近检查点状态")}</th>
                </tr>
              </thead>
              <tbody>
                {latest.modulators.map((m) => (
                  <tr key={m.source}>
                    <td>{m.source}</td>
                    <td>
                      {m.gain} / {m.budget_multiplier}
                    </td>
                    <td>{m.competition_enabled ? t("是") : t("否")}</td>
                    <td>{m.expires_us}</td>
                    <td>
                      {BigInt(m.expires_us) >
                      BigInt(evidence.data!.latest_time_us)
                        ? t("有效")
                        : t("已过期")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className="panel resource-panel">
        <div className="panel-heading">
          <div>
            <h2>{t("注意账本历史")}</h2>
            <p>
              {t(
                "采样计数保持十进制整数。图表仅显示当前页可精确表示的计数，完整筛选范围可导出。",
              )}
            </p>
          </div>
        </div>
        <form
          className="resource-filters"
          onSubmit={(e) => {
            e.preventDefault();
            if (
              !/^\d+$/.test(start) ||
              (end && (!/^\d+$/.test(end) || BigInt(end) < BigInt(start)))
            ) {
              setError(t("请输入非负整数模拟时间，结束时间不能早于起始时间。"));
              return;
            }
            setError("");
            setFilter({ after: start, until: end });
            setPages([start]);
          }}
        >
          <Field label={t("起始模拟时间（μs）")}>
            <input
              inputMode="numeric"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </Field>
          <Field label={t("结束模拟时间（μs）")}>
            <input
              inputMode="numeric"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              placeholder={t("不限")}
            />
          </Field>
          <Button type="submit">{t("应用时间筛选")}</Button>
          {(["csv", "jsonl"] as const).map((format) => (
            <a
              key={format}
              className="button"
              href={`/api/v2${base}/attention/export?${selection}&format=${format}`}
            >
              <Download size={14} />
              {format.toUpperCase()}
            </a>
          ))}
        </form>
        <ErrorBox error={error || evidence.error} />
        {evidence.isPending && <Loading />}
        {rows.length > 0 ? (
          <>
            <Chart
              rows={[]}
              metric="channels"
              title={t("累计通道数")}
              topPadding={24}
              step
              series={(
                [
                  ["passed_channels", "通过"],
                  ["suppressed_channels", "抑制"],
                ] as const
              ).map(([key, name]) => ({
                name: t(name),
                rows: rows.map((r) => ({
                  time_us: r.time_us,
                  channels:
                    !r.attention.counter_overflowed &&
                    BigInt(r.attention[key]) <= BigInt(Number.MAX_SAFE_INTEGER)
                      ? Number(r.attention[key])
                      : null,
                })),
              }))}
            />
            <div className="table-scroll attention-history">
              <table>
                <thead>
                  <tr>
                    <th>{t("模拟时间（μs）")}</th>
                    <th>{t("统计帧")}</th>
                    <th>{t("考虑")}</th>
                    <th>{t("通过")}</th>
                    <th>{t("抑制")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.time_us}>
                      <td>{r.time_us}</td>
                      <td>{r.attention.evaluated_frames}</td>
                      <td>{r.attention.considered_channels}</td>
                      <td>{r.attention.passed_channels}</td>
                      <td>{r.attention.suppressed_channels}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          !evidence.isPending && (
            <Empty
              title={t("没有账本采样")}
              detail={t("当前筛选范围没有已提交的注意账本采样。")}
            />
          )
        )}
        <div className="pagination">
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
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>{t("调制递送记录")}</h2>
            <p>
              {t(
                "命令被接收不代表已经生效；以实际递送记录为准，拒绝原因也会保留。",
              )}
            </p>
          </div>
          <a className="button" href={`/api/v2${base}/attention/events/export`}>
            <Download size={14} />
            {t("导出全部调制记录")}
          </a>
        </div>
        <ErrorBox error={journal.error} />
        <div className="table-scroll attention-history">
          <table>
            <thead>
              <tr>
                <th>{t("模拟时间（μs）")}</th>
                <th>{t("阶段")}</th>
                <th>{t("来源 / 结果")}</th>
                <th>{t("详情")}</th>
              </tr>
            </thead>
            <tbody>
              {journal.data?.rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.time_us}</td>
                  <td>{t(stages[row.kind] ?? row.kind)}</td>
                  <td>
                    {String(row.payload.source ?? "")} /{" "}
                    {t(
                      (
                        {
                          applied: "已生效",
                          rejected: "已拒绝",
                          scheduled: "已排队",
                        } as Record<string, string>
                      )[String(row.payload.status)] ?? "已处理",
                    )}
                  </td>
                  <td>
                    <details>
                      <summary>{t("查看记录")}</summary>
                      <pre>{JSON.stringify(row.payload, null, 2)}</pre>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!journal.isPending && !journal.data?.rows.length && (
          <Empty
            title={t("没有调制记录")}
            detail={t("调制实际处理后会在此保留记录。")}
          />
        )}
        <div className="pagination">
          <Button
            disabled={journalPages.length === 1}
            onClick={() => setJournalPages((p) => p.slice(0, -1))}
          >
            {t("上一组记录")}
          </Button>
          <span>{t("第 {page} 页", { page: journalPages.length })}</span>
          <Button
            disabled={!journal.data?.more}
            onClick={() => setJournalPages((p) => [...p, journal.data!.next])}
          >
            {t("下一组记录")}
          </Button>
        </div>
      </section>
    </div>
  );
}
