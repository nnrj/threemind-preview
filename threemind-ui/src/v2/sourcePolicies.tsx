import { t } from "./i18n";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RefreshCw, Settings2 } from "lucide-react";
import { api, type Run } from "./api";
import { Button, ErrorBox, Loading } from "./ui";

export default function SourcePolicyPanel({
  base,
  run,
  configure,
}: {
  base: string;
  run: Run;
  configure: () => void;
}) {
  const data = useQuery({
    queryKey: ["source-policies", run.id, run.spec.source_policies],
    queryFn: () => api(`${base}/source-policies`),
    gcTime: 0,
  });
  return (
    <section
      className="panel source-policy-panel"
      aria-label={t("输入来源与竞争策略")}
    >
      <div className="panel-heading">
        <div>
          <h2>{t("来源与竞争")}</h2>
          <p>
            {t(
              "类别开关与来源开关同时开启才准入。绕过只作用于这一来源的感官帧。",
            )}
          </p>
        </div>
        <Button onClick={configure}>
          <Settings2 size={15} />
          {t("调整来源策略")}
        </Button>
      </div>
      <div className="source-policy-intro">
        <p>
          {t(
            "策略变更会记录为配置版本。已排入内核的帧继续按其冻结的绕过标记递送；已接收但尚未排队的载体会重新检查来源开关。绕过竞争仍受外部增益、感官编码、实验阶段及模型资源约束。",
          )}
        </p>
        <div className="message-links">
          <Link className="text-link" to="?view=conversation">
            {t("消息显示偏好")}
          </Link>
          <Link
            className="text-link"
            to="/docs?doc=docs/zh/v2-source-policies.md"
          >
            {t("来源策略与恢复规则")}
          </Link>
          <Button onClick={() => data.refetch()}>
            <RefreshCw size={14} />
            {t("重新读取")}
          </Button>
        </div>
      </div>
      <ErrorBox error={data.error} />
      {data.isPending && <Loading />}
      {data.data?.categories.map((category: any) => (
        <div className="source-policy-category" key={category.id}>
          <header>
            <h3>{t(category.label)}</h3>
            <span>
              {t("类别准入：")}
              {data.data.configuration[`${category.id}_enabled`]
                ? t("开启")
                : t("关闭")}
            </span>
            <span>
              {t("类别绕过：")}
              {data.data.configuration[`${category.id}_bypass_attention`]
                ? t("开启")
                : t("关闭")}
            </span>
          </header>
          <div className="source-policy-grid">
            {data.data.rows
              .filter((row: any) => row.category === category.id)
              .map((row: any) => (
                <article key={row.key}>
                  <div>
                    <strong>{t(row.label)}</strong>
                    <span
                      className={`source-policy-state ${row.effective.enabled ? "source-open" : "source-closed"}`}
                    >
                      {row.effective.enabled
                        ? t("策略允许准入")
                        : t("策略关闭准入")}
                    </span>
                  </div>
                  <dl>
                    <div>
                      <dt>{t("来源开关")}</dt>
                      <dd>
                        {row.configuration.enabled ? t("开启") : t("关闭")}
                      </dd>
                    </div>
                    <div>
                      <dt>{t("有效竞争方式")}</dt>
                      <dd>
                        {row.effective.bypass_attention
                          ? t("绕过通道竞争")
                          : t("遵循内核竞争")}
                      </dd>
                    </div>
                  </dl>
                  {row.configuration.enabled && !row.effective.enabled && (
                    <small>
                      {t("所属类别已关闭，单独开启此来源仍不会递送。")}
                    </small>
                  )}
                  {row.aliases.length > 0 && (
                    <details>
                      <summary>{t("来源标识")}</summary>
                      <code>{row.aliases.join(" · ")}</code>
                    </details>
                  )}
                </article>
              ))}
          </div>
          {category.id === "ai" && (
            <p className="footnote">
              {t(
                "这里配置外部 AI 载体的准入策略。AI 供应商与调用工具会沿用这些策略，完成情况见功能恢复清单；模型自身的活动不归为 AI 外部来源。",
              )}
            </p>
          )}
        </div>
      ))}
      <p className="footnote">
        {t(
          "“允许准入”表示来源策略通过。实际递送还需要相应感官、设备权限和运行条件满足；关闭消息显示不会关闭输入。网络项只管感官刺激，设备读取及标量端口由各自权限管理。",
        )}
      </p>
    </section>
  );
}
