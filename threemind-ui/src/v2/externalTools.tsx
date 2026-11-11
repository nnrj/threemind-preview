import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "./api";
import { Button, ErrorBox, Field, Loading, useWorkspace } from "./ui";
import { t } from "./i18n";
import { usePreferences, updatePreferences } from "./preferences";
import "./bundles.css";

export default function ExternalTools() {
  const p = usePreferences(),
    { project } = useWorkspace();
  const [search, setSearch] = useState(""),
    [selected, setSelected] = useState(""),
    [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<unknown>();
  const catalog = useQuery({
    queryKey: ["operations-catalog"],
    queryFn: () => api<any>("/operations/catalog"),
    staleTime: 30000,
  });
  const capability = useQuery({
    queryKey: ["tool-capabilities"],
    queryFn: () => api<any>("/capabilities"),
    refetchInterval: 30000,
  });
  const rows = (catalog.data?.operations ?? []).filter((item: any) =>
    `${item.id} ${item.title}`.toLowerCase().includes(search.toLowerCase()),
  );
  const current = catalog.data?.operations.find(
    (item: any) => item.id === selected,
  );
  const schemas: Record<string, unknown> = {};
  const pending: unknown[] = current ? [current] : [];
  while (pending.length) {
    const item = pending.pop();
    if (!item || typeof item !== "object") continue;
    const ref = (item as { $ref?: string }).$ref;
    if (ref?.startsWith("#/components/schemas/")) {
      const key = ref.split("/").at(-1)!;
      if (!Object.hasOwn(schemas, key)) {
        schemas[key] = catalog.data.components.schemas[key];
        pending.push(schemas[key]);
      }
    }
    pending.push(...Object.values(item));
  }
  const config = {
    mcpServers: {
      threemind: {
        command: "threemind-mcp",
        env: { THREEMIND_API_URL: window.location.origin },
      },
    },
  };
  return (
    <div className="bundle-workspace">
      <section className="panel settings-panel">
        <h2>{t("计算工具默认值")}</h2>
        <p>
          {t(
            "只影响之后新建的 Transformer 任务；意识内核、已有任务和实验协议保持原配置。",
          )}
        </p>
        <div className="form-grid">
          <Field label={t("计算设备")}>
            <select
              aria-label={t("计算设备")}
              value={p.toolComputeDevice}
              onChange={(e) =>
                updatePreferences({
                  toolComputeDevice: e.target
                    .value as typeof p.toolComputeDevice,
                })
              }
            >
              <option value="auto">{t("自动（测量收益后选择）")}</option>
              <option value="cpu">CPU</option>
              <option value="cuda">{t("GPU 优先（失败回退 CPU）")}</option>
            </select>
          </Field>
          <Field label={t("显存预算（MiB）")}>
            <input
              type="number"
              min={128}
              max={131072}
              value={p.toolGpuMemory}
              onChange={(e) =>
                updatePreferences({ toolGpuMemory: Number(e.target.value) })
              }
            />
          </Field>
          <Field label={t("显存预留（MiB）")}>
            <input
              type="number"
              min={128}
              max={32768}
              value={p.toolGpuHeadroom}
              onChange={(e) =>
                updatePreferences({ toolGpuHeadroom: Number(e.target.value) })
              }
            />
          </Field>
        </div>
        <p>
          {t(
            "自动选择需要测得稳定至少 20% 加速。GPU 故障的 CPU 重试从同一初始条件开始，不拼接两次轨迹。",
          )}
        </p>
        <Link to="/kernels?view=transformer">{t("打开 Transformer 工具")}</Link>
        <h3>{t("工作进程报告的设备")}</h3>
        <ErrorBox error={capability.error} />
        {!capability.data?.workers?.length && (
          <p className="muted">
            {t("尚无可见工作进程报告；请启动 worker，实际设备以任务证据为准。")}
          </p>
        )}
        {capability.data?.workers?.map((worker: any) => {
          const compute =
            worker.capabilities?.features?.["worker.transformer_v1"]?.compute;
          return (
            <details key={worker.id}>
              <summary>
                {worker.name} · {compute?.torch_version ?? t("未安装可选依赖")}{" "}
                · {compute?.cuda_available ? "CUDA" : "CPU"}
              </summary>
              <pre className="bundle-preview">
                {JSON.stringify(compute ?? {}, null, 2)}
              </pre>
            </details>
          );
        })}
      </section>
      <section className="panel settings-panel">
        <h2>{t("AI 与命令行接入")}</h2>
        <p>
          {t(
            "页面、CLI 和 MCP 使用同一服务、权限和校验。先查看协议，再执行；响应不确定时，用原请求编号查询回执。",
          )}
        </p>
        <pre className="bundle-preview">{`threemind ops list\nthreemind ops show experiment.create\nthreemind ops receipt --project ${project?.id ?? "PROJECT_ID"} --request-id REQUEST_ID`}</pre>
        <details>
          <summary>{t("MCP 连接配置")}</summary>
          <p>
            {t(
              "将命令替换为已安装环境中的 threemind-mcp 绝对路径。服务端账号密码在本地环境变量中填写，不粘贴到聊天。",
            )}
          </p>
          <pre className="bundle-preview">
            {JSON.stringify(config, null, 2)}
          </pre>
          <Button
            onClick={() =>
              navigator.clipboard
                .writeText(JSON.stringify(config, null, 2))
                .then(() => setCopied(true))
                .catch(setCopyError)
            }
          >
            {t(copied ? "已复制" : "复制配置")}
          </Button>
          <ErrorBox error={copyError} />
          <p>
            {t(
              "文件传输可选：由宿主设置 THREEMIND_MCP_TRANSFER_DIR；Agent 只能在该目录内交换已校验的实验包。",
            )}
          </p>
        </details>
      </section>
      <section className="panel settings-panel">
        <h2>{t("可用操作与真实协议")}</h2>
        <input
          aria-label={t("搜索操作")}
          placeholder={t("搜索操作")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <ErrorBox error={catalog.error} />
        {catalog.isLoading ? (
          <Loading />
        ) : (
          <Field label={t("选择操作")}>
            <select
              aria-label={t("选择操作")}
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">{t("选择操作")}</option>
              {rows.slice(0, 200).map((item: any) => (
                <option key={item.id} value={item.id}>
                  {item.id} · {item.effect}
                </option>
              ))}
            </select>
          </Field>
        )}
        {current && (
          <>
            <p>
              <code>
                {current.method} {current.path}
              </code>
            </p>
            <p>
              {t(
                current.effect === "read"
                  ? "只读操作"
                  : "写入操作：执行时仍检查权限、修订号与资源限制。",
              )}
            </p>
            <pre className="bundle-preview">
              {JSON.stringify(
                { operation: current, components: { schemas } },
                null,
                2,
              )}
            </pre>
            <code>threemind ops show {current.id}</code>
          </>
        )}
      </section>
    </div>
  );
}
