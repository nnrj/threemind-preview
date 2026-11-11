import { t } from "./i18n";
import { lazy, useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, Settings2 } from "lucide-react";
import { api, post, numberLabel, type Run } from "./api";
import { Button, Empty, ErrorBox, Field, Loading, Metric } from "./ui";
const Chart = lazy(() => import("./Chart"));

type Ledger = {
  since_us: string;
  reserve: number;
  initial_total: number;
  supplied_total: number;
  offered_total: number;
  consumed_direct: number;
  consumed_associative: number;
  consumed_inhibition: number;
  consumed_maintenance: number;
  unserved_total: number;
  discarded_total: number;
  counter_overflowed: boolean;
  starved_since_us: string | null;
  death_us: string | null;
  settled_state_time_us: string;
  last_maintenance_deficit: number;
  parameters: {
    energy_capacity: number;
    energy_simulation_enabled: boolean;
    energy_starvation_damage_enabled: boolean;
    energy_model?: "local-field" | "global-ledger";
    irreversible_energy_death_enabled?: boolean;
  };
};
type Evidence = {
  latest: Ledger | null;
  revision: number;
  latest_time_us: string;
  more: boolean;
  next: string;
  rows: { time_us: string; energy: Ledger; quality: string }[];
  provider: {
    accepted_total: number;
    offered_total: number;
    pending: { time_us: string } | null;
  } | null;
};
const consumed = (e: Ledger) =>
  e.consumed_direct +
  e.consumed_associative +
  e.consumed_inhibition +
  e.consumed_maintenance;
const value = (n: number) => numberLabel(n, 6);

export default function EnergyPanel({
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
  const [error, setError] = useState(""),
    [amount, setAmount] = useState("0.1"),
    [notice, setNotice] = useState("");
  const request = useRef(crypto.randomUUID());
  const selection = new URLSearchParams({ after: filter.after });
  if (filter.until) selection.set("until", filter.until);
  const current = new URLSearchParams(selection);
  current.set("after", pages.at(-1)!);
  const evidence = useQuery({
    queryKey: ["energy", base, current.toString()],
    queryFn: () => api<Evidence>(`${base}/energy?${current}`),
    refetchInterval: run.status === "running" ? 3000 : false,
  });
  useEffect(() => {
    void evidence.refetch();
  }, [run.revision, evidence.refetch]);
  useEffect(() => {
    setNotice("");
  }, [run.status, run.revision]);
  const supply = useMutation({
    mutationFn: () =>
      post(`${base}/energy/supply`, {
        request_id: request.current,
        amount: Number(amount),
      }),
    onSuccess: () => {
      request.current = crypto.randomUUID();
      setNotice(
        run.status === "paused"
          ? t("供给已排队，继续运行后递送。")
          : t("供给已排队；实际接受量在提交后的账本与递送记录中查看。"),
      );
      void evidence.refetch();
    },
  });
  const latest = evidence.data?.latest,
    provider = evidence.data?.provider;
  const enabled = !!run.spec.config?.energy_simulation_enabled;
  const localEnergy =
    (latest?.parameters?.energy_model ?? run.spec.config?.energy_model) ===
    "local-field";
  const historicalEnergyDeath = !!(
    latest?.parameters.irreversible_energy_death_enabled ??
    run.spec.config?.irreversible_energy_death_enabled
  );
  const canSupply =
    enabled &&
    !run.spec.study_id &&
    ["running", "queued", "paused", "blocked"].includes(run.status);
  const rows = evidence.data?.rows ?? [];
  const chartRows = rows.map((row) => ({
    time_us: row.time_us,
    reserve:
      row.energy.parameters.energy_simulation_enabled &&
      !row.energy.counter_overflowed
        ? row.energy.reserve
        : null,
    consumed:
      row.energy.parameters.energy_simulation_enabled &&
      !row.energy.counter_overflowed
        ? consumed(row.energy)
        : null,
  }));
  return (
    <div className="energy-page" aria-label={t("能量与供给")} role="region">
      <section className="panel resource-panel">
        <div className="panel-heading">
          <div>
            <h2>{t("能量记账与外部供给")}</h2>
            <p>
              {t(
                "可选的实验资源模型。计量不代表焦耳，显示性能档位不会启用或修改此实验。",
              )}
            </p>
          </div>
          <Button onClick={configure}>
            <Settings2 size={15} />
            {t("配置能量与供给")}
          </Button>
        </div>
        <p className="notice">
          {t("能量记账：")}
          {enabled ? t("已启用") : t("未启用")}
          {historicalEnergyDeath
            ? t(" · 历史独立饥饿判死：")
            : t(" · 缺能结构损伤：")}
          {historicalEnergyDeath ||
          run.spec.config?.energy_starvation_damage_enabled
            ? t("已启用对照")
            : t("未启用")}
          {t(
            "。已有账本的暂停、恢复及开关不会补发初始储备；供给自身不会产生激活。",
          )}
        </p>
        <p className="footnote">
          {localEnergy
            ? t(
                "局部能量：总储备为各区域与节点的储备之和；单区域容量不是总容量。",
              )
            : t("全局能量：储备与容量属于同一个全局账本。")}
        </p>
        {latest ? (
          <>
            <div className="metrics-grid">
              <Metric
                label={
                  localEnergy
                    ? enabled
                      ? t("当前总储备")
                      : t("未参与演化的总储备")
                    : enabled
                      ? t("当前储备")
                      : t("未参与演化的储备")
                }
                value={value(latest.reserve)}
                detail={t(
                  localEnergy
                    ? "单区域容量 {value0} · 实验单位"
                    : "容量 {value0} · 实验单位",
                  { value0: String(value(latest.parameters.energy_capacity)) },
                )}
              />
              <Metric
                label={t("累计接受供给")}
                value={value(latest.supplied_total)}
                detail={t("实验单位")}
              />
              <Metric
                label={t("累计消耗")}
                value={value(consumed(latest))}
                detail={t("直接、联想、抑制与维护")}
              />
              <Metric
                label={t("累计未满足需求")}
                value={value(latest.unserved_total)}
                detail={t("储备不足的请求量 · 实验单位")}
              />
            </div>
            <p className="footnote">
              r{evidence.data!.revision}
              {t(" · 统计起点 ")}
              {latest.since_us}
              {t(" μs · 最近因果结算 ")}
              {latest.settled_state_time_us}
              {t(" μs。初始记账")} {value(latest.initial_total)}
              {t("，容量舍弃")} {value(latest.discarded_total)}
              {t("；开关不清空历史累计值。")}
            </p>
            {latest.starved_since_us !== null && (
              <p className="notice">
                {t("零储备记录始于 ")}
                {latest.starved_since_us}
                {t(" μs 开始。")}
                {latest.death_us !== null
                  ? t(
                      historicalEnergyDeath
                        ? "历史机制于 {value0} μs 强制判死；此记录只读，不改写原因。"
                        : "已于 {value0} μs 连续无激活达到宽限期，供给不能复活此意识。",
                      {
                        value0: String(latest.death_us),
                      },
                    )
                  : historicalEnergyDeath
                    ? t("历史饥饿机制记录；旧意识只读，不按新规则续跑。")
                    : t("缺能不会直接清空激活或判死；已排队供给按时间戳处理。")}
              </p>
            )}
            {latest.counter_overflowed && (
              <p className="notice">
                {t("累计浮点量已饱和，不能将饱和值用于精确守恒或效应估计。")}
              </p>
            )}
          </>
        ) : (
          <p className="footnote">
            {t(
              "尚无能量账本；旧模型不会被补造历史。启用此机制后会记录明确的版本升级与统计起点。",
            )}
          </p>
        )}
        <div className="energy-sources">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              supply.mutate();
            }}
          >
            <h3>{t("人工资源端口")}</h3>
            <p className="footnote">
              {t(
                "按命令处理后的正因果延迟递送；响应丢失后重试相同请求不会供给两次。",
              )}
            </p>
            <div className="resource-filters">
              <Field label={t("供给数量（实验单位）")}>
                <input
                  type="number"
                  min="0"
                  max="1000000000000"
                  step="any"
                  required
                  value={amount}
                  onChange={(e) => {
                    setAmount(e.target.value);
                    request.current = crypto.randomUUID();
                    setNotice("");
                  }}
                  disabled={supply.isPending}
                />
              </Field>
              <Button
                variant="primary"
                disabled={!canSupply || supply.isPending}
              >
                {t("排队供给")}
              </Button>
            </div>
            <ErrorBox error={supply.error} />
            {notice && <p role="status">{notice}</p>}
          </form>
          <div>
            <h3>{t("模拟外部储库")}</h3>
            <p className="footnote">
              {run.spec.energy_supply?.enabled
                ? enabled
                  ? t("供给已启用")
                  : t("等待内核启用能量记账")
                : t("供给未启用")}{" "}
              · {value(run.spec.energy_supply?.rate_per_s ?? 0.04)}
              {t(" 单位／模拟秒 · 总额度")}{" "}
              {run.spec.energy_supply?.total_supply_limit == null
                ? t("不限制")
                : value(run.spec.energy_supply.total_supply_limit)}
            </p>
            {provider && (
              <p>
                {t("已接受 ")}
                {value(provider.accepted_total)}
                {t("，已提出")} {value(provider.offered_total)}。
                {provider.pending
                  ? t("下一已排队供给：{value0} μs。", {
                      value0: String(provider.pending.time_us),
                    })
                  : t("当前没有待递送的储库供给。")}
              </p>
            )}
            <p className="footnote">
              {t(
                "停用和改参不撤销已排队供给；已接受的总额度保留。模型文件不会自动安装这项外部供应源。",
              )}
            </p>
          </div>
        </div>
        <Link className="text-link" to="/docs?doc=docs%2Fzh%2Fv2-energy.md">
          {t("查看资源方程、供给规则和版本边界")}
        </Link>
      </section>
      <section className="panel resource-panel">
        <div className="panel-heading">
          <div>
            <h2>{t("能量观测与证据")}</h2>
            <p>
              {t("曲线显示所选区间的当前页，完整筛选结果及供给日志可导出。")}
            </p>
          </div>
        </div>
        <form
          className="resource-filters"
          onSubmit={(e) => {
            e.preventDefault();
            const valid = (s: string) =>
              /^(0|[1-9][0-9]*)$/.test(s) && BigInt(s) <= (1n << 128n) - 1n;
            if (
              !valid(start) ||
              (end && (!valid(end) || BigInt(end) < BigInt(start)))
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
          <Field label={t("能量起始时间（微秒）")}>
            <input
              inputMode="numeric"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </Field>
          <Field label={t("能量结束时间（微秒）")}>
            <input
              inputMode="numeric"
              placeholder={t("不限制")}
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </Field>
          <Button>{t("应用筛选")}</Button>
        </form>
        <ErrorBox error={error || evidence.error} />
        {evidence.isPending ? (
          <Loading />
        ) : rows.length ? (
          <>
            <div className="chart-grid">
              <Chart
                rows={chartRows}
                metric="reserve"
                title={t("储备（实验单位） · 本页观测")}
              />
              <Chart
                rows={chartRows}
                metric="consumed"
                title={t("累计消耗（实验单位） · 本页观测")}
              />
            </div>
            <div className="table-scroll resource-history">
              <table>
                <thead>
                  <tr>
                    <th>{t("模拟时间（μs）")}</th>
                    <th>{t("能量记账")}</th>
                    <th>{t("储备")}</th>
                    <th>{t("累计直接消耗")}</th>
                    <th>{t("累计联想消耗")}</th>
                    <th>{t("累计抑制消耗")}</th>
                    <th>{t("累计维护消耗")}</th>
                    <th>{t("累计未满足需求")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.time_us}>
                      <td className="mono">{row.time_us}</td>
                      <td>
                        {row.energy.parameters.energy_simulation_enabled
                          ? t("启用")
                          : t("关闭")}
                      </td>
                      {[
                        "reserve",
                        "consumed_direct",
                        "consumed_associative",
                        "consumed_inhibition",
                        "consumed_maintenance",
                        "unserved_total",
                      ].map((key) => (
                        <td key={key}>
                          {value(row.energy[key as keyof Ledger] as number)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <Empty
            title={t("所选区间暂无能量观测")}
            detail={t(
              "采集后的结果会在此显示。关闭能量记账时保留账本，曲线不把它当作正在发生的能量演化。",
            )}
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
                className="button"
                key={format}
                href={`/api/v2${base}/energy/export?${selection}&format=${format}`}
              >
                <Download size={15} />
                {t("能量 ")}
                {format.toUpperCase()}
              </a>
            ))}
            <a
              className="button"
              href={`/api/v2${base}/energy/events/export?${selection}`}
            >
              <Download size={15} />
              {t("供给日志 JSONL")}
            </a>
          </div>
        </div>
        <p className="footnote">
          {t(
            "页面数值作适量舍入，下载保留存储的浮点值及原始模拟时间。曲线连接是采样间的示意，不代表完整连续轨迹；JSONL 带数据版本和状态校验。",
          )}
        </p>
      </section>
    </div>
  );
}
