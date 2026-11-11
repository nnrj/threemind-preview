import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, post } from "./api";
import { messageKeys, t } from "./i18n";
import { Button, CodeEditor, ErrorBox, Field } from "./ui";

const roles = messageKeys({
  input: "刺激输入",
  actuator: "执行器输出",
  observer: "被动观察",
  filter: "载体过滤",
  control: "显式控制",
  resource: "资源端口",
});
const transports = messageKeys({
  in_process: "进程内函数",
  http: "HTTP",
  websocket: "WebSocket",
  browser_media: "浏览器媒体",
  device_driver: "设备驱动",
  shared_memory: "共享内存",
});
const mappings = messageKeys({
  uniform_codec: "统一匿名编码",
  recorded_channels: "原始通道与记录重放",
  explicit_source_policy: "显式来源策略",
  fixed_engineering_projection: "固定工程投影",
  read_only: "只读观察",
  explicit_control: "显式科研控制",
  resource_accounting: "外部资源记账",
});
const recovery = messageKeys({
  state_and_inputs: "需完整适配器状态与待递送输入",
  recorded_inputs: "依赖已记录载体或输入",
  external_state_required: "需外部设备或会话状态",
  stateless: "无状态派生投影",
});
const issues = messageKeys({
  clock_unavailable: "未声明所需时钟域",
  signal_unavailable: "未声明所需数据端口",
  signal_units_mismatch: "数据端口的单位声明不一致",
  protocol_mismatch: "协议版本不匹配",
  roles_unavailable: "未声明所需端口角色",
  transport_unavailable: "未声明所需传输方式",
  restorable_state_not_declared: "未声明完整状态恢复能力",
});

function download(value: any) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], {
      type: "application/json;charset=utf-8",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "threemind-adapter-contract.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ContractDetails({ contract }: { contract: any }) {
  if (!contract) return null;
  return (
    <div className="adapter-contract-details">
      <p>
        <strong>{t("端口角色：")}</strong>
        {contract.roles
          .map((key: keyof typeof roles) => t(roles[key]))
          .join(" · ")}
      </p>
      <p>
        <strong>{t("传输方式：")}</strong>
        {contract.transports
          .map((key: keyof typeof transports) => t(transports[key]))
          .join(" · ")}
      </p>
      <p>
        <strong>{t("映射方式：")}</strong>
        {t(mappings[contract.mapping as keyof typeof mappings])}
      </p>
      {contract.mapping === "fixed_engineering_projection" && (
        <p className="notice">
          {t(
            "当前是固定投影的工程对照，不代表训练涌现的器官分工；不手工指定内部节点的语义。",
          )}
        </p>
      )}
      <p>
        <strong>{t("恢复条件：")}</strong>
        {t(recovery[contract.recovery as keyof typeof recovery])}
      </p>
      <p>
        <strong>{t("时钟域：")}</strong>
        <code>{contract.clocks.join(" · ")}</code>
      </p>
      <p>
        <strong>{t("接线身份依据：")}</strong>
        <code>{contract.identity_fields.join(" · ") || "—"}</code>
      </p>
      <p className="footnote">
        {t(
          "这里声明身份字段和协议，不包含实际部署接线、凭据或模型。不同数据端口使用各自的单位、载体和恢复协议。",
        )}
      </p>
    </div>
  );
}

export default function AdapterContracts() {
  const catalogue = useQuery({
    queryKey: ["adapter-contract-catalogue"],
    queryFn: () => api<any>("/adapters"),
    refetchOnWindowFocus: false,
  });
  const [selection, setSelection] = useState("remote-anonymous"),
    [value, setValue] = useState<any>(null),
    [protocol, setProtocol] = useState(""),
    [transport, setTransport] = useState("websocket"),
    [requiredRoles, setRequiredRoles] = useState<string[]>(["input"]),
    [restore, setRestore] = useState(false),
    [clock, setClock] = useState(""),
    [checkUnits, setCheckUnits] = useState(false),
    [units, setUnits] = useState<string[]>([]),
    [result, setResult] = useState<any>(null),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const accept = (manifest: any) => {
    setValue(manifest);
    setProtocol(manifest.contract.protocol);
    setTransport(manifest.contract.transports[0]);
    setRequiredRoles([]);
    setRestore(false);
    setClock("");
    setCheckUnits(false);
    setUnits(manifest.contract.signals.map((s: any) => s.units));
    setResult(null);
  };
  useEffect(() => {
    if (!selection) return;
    let cancelled = false;
    setBusy(true);
    setError(null);
    setValue(null);
    api<any>("/adapters/" + encodeURIComponent(selection) + "/manifest")
      .then((manifest) => {
        if (!cancelled) accept(manifest);
      })
      .catch((error) => {
        if (!cancelled) setError(error);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selection]);
  const changed = () => {
    setResult(null);
    setError(null);
  };
  return (
    <section
      className="adapter-contract-tools"
      aria-label={t("适配器接入验收")}
    >
      <h2>{t("适配器接入验收")}</h2>
      <p>
        {t(
          "先核对公共契约和所需能力，再在设备所在环境运行 SDK 验收。声明通过不会创建绑定、安装代码或启动意识。",
        )}
      </p>
      <ErrorBox error={error || catalogue.error} />
      <fieldset disabled={busy}>
        <div className="form-grid">
          <Field label={t("已实现的契约")}>
            <select
              aria-label={t("已实现的契约")}
              value={selection}
              onChange={(e) => {
                setSelection(e.target.value);
                changed();
              }}
            >
              <option value="" disabled>
                {t("导入的第三方声明")}
              </option>
              {catalogue.data?.adapters.map((row: any) => (
                <option key={row.id} value={row.id}>
                  {t(row.name)} · {row.version}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("导入契约声明 JSON")}>
            <input
              aria-label={t("导入契约声明 JSON")}
              type="file"
              accept=".json,application/json"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (!file) return;
                setBusy(true);
                changed();
                try {
                  if (file.size > 131072)
                    throw new Error(t("契约声明不能超过 128 KiB。"));
                  const checked = await post("/adapters/validate", {
                    manifest_json: await file.text(),
                  });
                  setSelection("");
                  accept(checked.manifest);
                  setResult(checked);
                } catch (error) {
                  setError(error);
                } finally {
                  setBusy(false);
                }
              }}
            />
          </Field>
        </div>
        {value && (
          <>
            <ContractDetails contract={value.contract} />
            <div className="form-grid">
              <Field label={t("所需协议版本")}>
                <input
                  aria-label={t("所需协议版本")}
                  value={protocol}
                  maxLength={128}
                  onChange={(e) => {
                    setProtocol(e.target.value);
                    changed();
                  }}
                />
              </Field>
              <Field label={t("所需传输方式")}>
                <select
                  aria-label={t("所需传输方式")}
                  value={transport}
                  onChange={(e) => {
                    setTransport(e.target.value);
                    changed();
                  }}
                >
                  {Object.entries(transports).map(([key, label]) => (
                    <option key={key} value={key}>
                      {t(label)}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <details>
              <summary>{t("高级：校验时钟与端口单位")}</summary>
              <Field label={t("所需时钟域")}>
                <select
                  aria-label={t("所需时钟域")}
                  value={clock}
                  onChange={(e) => {
                    setClock(e.target.value);
                    changed();
                  }}
                >
                  <option value="">{t("不限定")}</option>
                  {[
                    "model_us",
                    "physical_us",
                    "host_capture",
                    "host_monotonic",
                  ].map((key) => (
                    <option key={key} value={key}>
                      {key}
                    </option>
                  ))}
                </select>
              </Field>
              <label className="check">
                <input
                  type="checkbox"
                  checked={checkUnits}
                  onChange={(e) => {
                    setCheckUnits(e.target.checked);
                    changed();
                  }}
                />
                {t("逐项校验端口单位声明")}
              </label>
              {checkUnits &&
                value.contract.signals.map((signal: any, index: number) => (
                  <Field
                    key={index}
                    label={t("期望单位（{port}）", {
                      port: signal.direction + ":" + signal.payload,
                    })}
                  >
                    <input
                      aria-label={t("期望单位（{port}）", {
                        port: signal.direction + ":" + signal.payload,
                      })}
                      maxLength={1200}
                      value={units[index]}
                      onChange={(e) => {
                        setUnits((old) =>
                          old.map((v, i) => (i === index ? e.target.value : v)),
                        );
                        changed();
                      }}
                    />
                  </Field>
                ))}
              <p className="footnote">
                {t(
                  "这里只比较声明，单位必须明确一致；实际量纲换算、采样标定和时钟对齐由对应适配器验证。",
                )}
              </p>
            </details>
            <div className="query-controls">
              {Object.entries(roles).map(([key, label]) => (
                <label className="check" key={key}>
                  <input
                    type="checkbox"
                    checked={requiredRoles.includes(key)}
                    onChange={(e) => {
                      setRequiredRoles((old) =>
                        e.target.checked
                          ? [...old, key]
                          : old.filter((k) => k !== key),
                      );
                      changed();
                    }}
                  />
                  {t(label)}
                </label>
              ))}
            </div>
            <label className="check">
              <input
                type="checkbox"
                checked={restore}
                onChange={(e) => {
                  setRestore(e.target.checked);
                  changed();
                }}
              />
              {t("要求完整状态恢复声明")}
            </label>
            <div className="query-controls">
              <Button
                onClick={async () => {
                  setBusy(true);
                  changed();
                  try {
                    setResult(
                      await post("/adapters/validate", {
                        manifest_json: JSON.stringify(value),
                        negotiation: {
                          protocol,
                          roles: requiredRoles,
                          transports: [transport],
                          require_restorable_state: restore,
                          clocks: clock ? [clock] : [],
                          signals: checkUnits
                            ? value.contract.signals.map(
                                (s: any, i: number) => ({
                                  ...s,
                                  units: units[i],
                                }),
                              )
                            : [],
                        },
                      }),
                    );
                  } catch (error) {
                    setError(error);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {t("校验所需能力")}
              </Button>
              <Button onClick={() => download(value)}>
                {t("下载契约声明")}
              </Button>
            </div>
            <details>
              <summary>{t("高级：查看契约 JSON")}</summary>
              <CodeEditor
                label={t("适配器契约 JSON")}
                readOnly
                value={JSON.stringify(value, null, 2)}
                onChange={() => {}}
                rows={18}
              />
            </details>
          </>
        )}
      </fieldset>
      {result && (
        <div className="notice adapter-contract-result" role="status">
          <p>{t("声明结构与校验和通过；尚未执行或授权设备。")}</p>
          <p>
            {result.matches_installed_declaration
              ? t("与当前安装版本的声明一致。")
              : t("与当前安装声明不一致或未安装；不能据此确认第三方实现可用。")}
          </p>
          {result.negotiation &&
            (result.negotiation.declared_compatible ? (
              <strong>{t("声明具备所需协议和能力。")}</strong>
            ) : (
              <ul>
                {result.negotiation.issues.map((key: keyof typeof issues) => (
                  <li key={key}>{t(issues[key])}</li>
                ))}
              </ul>
            ))}
        </div>
      )}
      <details>
        <summary>{t("SDK 可执行验收与接入示例")}</summary>
        <p>
          {t(
            "在开发设备上显式运行这些命令。内置小样例检查编码、待递送恢复、观察隔离和背压；不证明真实硬件、任意代码或自主控制能力。",
          )}
        </p>
        <pre>
          {
            "python -m threemind_runtime.adapter_cli describe remote-anonymous\npython -m threemind_runtime.adapter_cli validate adapter.json --transport websocket\npython -m threemind_runtime.adapter_cli probe remote-anonymous --backend native"
          }
        </pre>
      </details>
      <Link className="text-link" to="/docs?doc=docs%2Fzh%2Fv2-adapter-sdk.md">
        {t("公共契约、SDK 与机器人接入边界")}
      </Link>
    </section>
  );
}
