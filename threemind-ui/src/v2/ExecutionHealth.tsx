import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t, useLocale, messageKeys, locale } from "./i18n";
import { Button, ErrorBox, Field } from "./ui";

const states = messageKeys({
  inactive: "暂无执行对象",
  pending: "累计采样时长中",
  active: "条件成立",
  missing: "证据不足",
  clear: "未命中",
});
export function ExecutionHealthFields({
  base,
  value,
  onChange,
}: {
  base: string;
  value: any;
  onChange: (value: any) => void;
}) {
  const names = useLocale() === "en" ? "en" : "zh";
  const metadata = useQuery({
    queryKey: ["execution-health", base],
    queryFn: () => api<any>(base + "/execution-health"),
  });
  const config = value ?? metadata.data?.defaults;
  if (!config) return <ErrorBox error={metadata.error} />;
  const update = (index: number, key: string, v: any) =>
    onChange({
      ...config,
      rules: config.rules.map((r: any, i: number) =>
        i === index ? { ...r, [key]: v } : r,
      ),
    });
  return (
    <section className="observer-rule">
      <h3>{t("执行资源与进度预警")}</h3>
      <label className="check">
        <input
          type="checkbox"
          checked={config.enabled}
          onChange={(e) => onChange({ ...config, enabled: e.target.checked })}
        />
        {t("启用可配置执行预警")}
      </label>
      <p className="footnote">
        {t(
          "需同时启用项目通知及执行预警事件。阈值只产生提示，不暂停任务、不修改意识。历史未知时间、过期数据和无执行对象分别标示。",
        )}
      </p>
      <details>
        <summary>{t("高级：编辑执行预警规则")}</summary>
        <p className="footnote">
          {t(
            "等待与租约按数据库宿主 UTC 时间观察；资源规则不会靠重复读取同一缓存样本累计时长。CPU 的 100% 表示一个逻辑核心。",
          )}
        </p>
        {config.rules.map((rule: any, index: number) => (
          <fieldset className="observer-rule" key={index}>
            <legend>{t("预警规则 {number}", { number: index + 1 })}</legend>
            <div className="observer-fields">
              <Field label={t("规则编号")}>
                <input
                  aria-label={t("规则编号")}
                  required
                  pattern="[a-z][a-z0-9_-]{0,47}"
                  value={rule.id}
                  onChange={(e) => update(index, "id", e.target.value)}
                />
              </Field>
              <Field label={t("规则名称")}>
                <input
                  aria-label={t("规则名称")}
                  maxLength={120}
                  value={rule.label}
                  onChange={(e) => update(index, "label", e.target.value)}
                />
              </Field>
              <Field label={t("观察指标")}>
                <select
                  aria-label={t("观察指标")}
                  value={rule.metric}
                  onChange={(e) => update(index, "metric", e.target.value)}
                >
                  {Object.entries(metadata.data?.metrics ?? {}).map(
                    ([key, m]: any) => (
                      <option key={key} value={key}>
                        {m[names]} · {m.unit}
                      </option>
                    ),
                  )}
                </select>
              </Field>
              <Field label={t("比较条件")}>
                <select
                  aria-label={t("比较条件")}
                  value={rule.comparison}
                  onChange={(e) => update(index, "comparison", e.target.value)}
                >
                  {[
                    ["gte", "≥"],
                    ["gt", ">"],
                    ["lte", "≤"],
                    ["lt", "<"],
                    ["eq", "="],
                  ].map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("触发阈值")}>
                <input
                  aria-label={t("触发阈值")}
                  type="number"
                  required
                  min={0}
                  max={1e12}
                  step="any"
                  value={rule.threshold ?? ""}
                  onChange={(e) =>
                    update(
                      index,
                      "threshold",
                      e.target.value === "" ? null : Number(e.target.value),
                    )
                  }
                />
              </Field>
              {(
                [
                  ["hold_us", t("持续采样时长（秒）"), 0],
                  ["cooldown_us", t("重复提醒间隔（秒）"), 0],
                  ["maximum_gap_us", t("最大采样间隔（秒）"), 0.001],
                ] as const
              ).map(([key, label, min]) => (
                <Field key={key} label={label}>
                  <input
                    aria-label={label}
                    type="number"
                    required
                    min={min}
                    max={1e6}
                    step="0.001"
                    value={rule[key] == null ? "" : rule[key] / 1e6}
                    onChange={(e) =>
                      update(
                        index,
                        key,
                        e.target.value === ""
                          ? null
                          : Math.round(Number(e.target.value) * 1e6),
                      )
                    }
                  />
                </Field>
              ))}
            </div>
            <div className="query-controls">
              <label className="check">
                <input
                  type="checkbox"
                  checked={rule.enabled}
                  onChange={(e) => update(index, "enabled", e.target.checked)}
                />
                {t("启用此规则")}
              </label>
              <Button
                type="button"
                onClick={() =>
                  onChange({
                    ...config,
                    rules: config.rules.filter(
                      (_: any, i: number) => i !== index,
                    ),
                  })
                }
              >
                {t("移除规则")}
              </Button>
            </div>
          </fieldset>
        ))}
        <Button
          type="button"
          disabled={config.rules.length >= 16 || !metadata.data}
          onClick={() =>
            onChange({
              ...config,
              rules: [
                ...config.rules,
                {
                  ...metadata.data.defaults.rules[0],
                  id: "rule_" + crypto.randomUUID().slice(0, 8),
                },
              ],
            })
          }
        >
          {t("添加执行预警规则")}
        </Button>
      </details>
      <ErrorBox error={metadata.error} />
    </section>
  );
}

export default function ExecutionHealth({ base }: { base: string }) {
  const names = useLocale() === "en" ? "en" : "zh";
  const data = useQuery({
    queryKey: ["execution-health", base],
    queryFn: () => api<any>(base + "/execution-health"),
    refetchInterval: 5000,
  });
  const current = data.data?.monitor;
  return (
    <section
      className="panel notification-policy"
      aria-label={t("执行资源与进度监测")}
    >
      <h2>{t("执行资源与进度监测")}</h2>
      <p className="footnote">
        {t(
          "只显示本项目任务及其执行节点的观测。宿主内存包含其他程序，进程内存不含子进程；这些数据不会作为刺激进入内核。",
        )}
      </p>
      <ErrorBox error={data.error} />
      <ErrorBox error={current?.error} />
      {!current?.enabled ? (
        <p>{t("执行预警当前关闭；项目所有者可在通知规则中开启。")}</p>
      ) : (
        <>
          <p>
            {t("每 5 秒检查到期监测；当前规则 v{version}。", {
              version: current.policy_revision,
            })}
          </p>
          {current.snapshot?.observed_at ? (
            <p className="footnote">
              {t("最近宿主观测：")}
              {new Date(current.snapshot.observed_at).toLocaleString(locale())}
            </p>
          ) : (
            <p>{t("等待通知 worker 采集首次观测。")}</p>
          )}
          <dl className="execution-health-metrics">
            {Object.entries(current.snapshot?.metrics ?? {}).map(
              ([key, v]: any) => (
                <div key={key}>
                  <dt>{data.data.metrics[key]?.[names] ?? key}</dt>
                  <dd>
                    {!v.applicable
                      ? t("暂无执行对象")
                      : v.value == null
                        ? t("证据不足")
                        : Number(v.value).toLocaleString(locale(), {
                            maximumFractionDigits: 2,
                          })}
                  </dd>
                  <small>{data.data.metrics[key]?.unit}</small>
                </div>
              ),
            )}
          </dl>
          <div className="query-controls">
            {Object.entries(current.state ?? {}).map(([key, v]: any) => (
              <span className="badge" key={key}>
                {key} ·{" "}
                {t(states[v.status as keyof typeof states] ?? "证据不足")}
              </span>
            ))}
          </div>
          <details>
            <summary>{t("查看监测范围与缺失依据")}</summary>
            <pre>{JSON.stringify(current.snapshot, null, 2)}</pre>
          </details>
          <Button
            type="button"
            disabled={!current.snapshot?.observed_at}
            onClick={() => {
              const url = URL.createObjectURL(
                new Blob(
                  [
                    JSON.stringify(
                      {
                        version: "threemind.execution-health-export/1",
                        monitor: current,
                        metrics: data.data.metrics,
                      },
                      null,
                      2,
                    ),
                  ],
                  { type: "application/json;charset=utf-8" },
                ),
              );
              const link = document.createElement("a");
              link.href = url;
              link.download = "threemind-execution-health.json";
              link.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            }}
          >
            {t("导出本次执行观测")}
          </Button>
        </>
      )}
    </section>
  );
}
