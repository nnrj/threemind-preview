import { useState } from "react";
import { Field, Button } from "./ui";
import JsonEditor, { parseJson } from "./JsonEditor";
import { t } from "./i18n";

export default function LanguageEditor({
  value,
  onChange,
  models = [],
  onValidityChange,
}: {
  value: any;
  onChange: (v: any) => void;
  models?: any[];
  onValidityChange?: (valid: boolean) => void;
}) {
  const [json, setJson] = useState(false),
    [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const p = value.protocol;
  function parsed(text: string) {
    const result = parseJson(text);
    if (
      !result?.protocol ||
      !result?.compute ||
      typeof result.protocol !== "object"
    )
      throw Error(t("请保留 protocol 与 compute 配置对象"));
    return result;
  }
  const patch = (key: string, v: any) =>
    onChange({ ...value, protocol: { ...p, [key]: v } });
  const selectModel = (role: string, id: string) => {
    const item = models.find((m) => m.id === id);
    const source = item?.metadata.protocol;
    onChange({
      ...value,
      assets: { ...value.assets, [role]: id || null },
      protocol: {
        ...p,
        ...(source
          ? Object.fromEntries(
              [
                "scratch_width",
                "scratch_heads",
                "scratch_layers",
                "scratch_context",
                "seed",
              ].map((k) => [k, source[k]]),
            )
          : {}),
        [role + "_checkpoint_sha256"]: item?.sha256 ?? null,
      },
    });
  };
  function toggle() {
    try {
      if (json) onChange(parsed(draft));
      else setDraft(JSON.stringify(value, null, 2));
      setJson(!json);
      setError("");
      onValidityChange?.(true);
    } catch (e) {
      setError(String(e));
      onValidityChange?.(false);
    }
  }
  return (
    <section className="language-editor">
      <div className="language-editor-heading">
        <strong>{t("语言感官与输出")}</strong>
        <Button type="button" onClick={toggle}>
          {t(json ? "图形配置" : "JSON 编辑")}
        </Button>
      </div>
      {error && <p role="alert">{error}</p>}
      {json ? (
        <>
          <Button
            type="button"
            onClick={() => {
              try {
                const v = parsed(draft);
                setDraft(JSON.stringify(v, null, 2));
                onChange(v);
                setError("");
                onValidityChange?.(true);
              } catch (e) {
                setError(String(e));
                onValidityChange?.(false);
              }
            }}
          >
            {t("格式化 JSON")}
          </Button>
          <JsonEditor
            value={draft}
            onChange={(v) => {
              setDraft(v);
              try {
                onChange(parsed(v));
                setError("");
                onValidityChange?.(true);
              } catch {
                setError(t("JSON 尚未通过语法校验"));
                onValidityChange?.(false);
              }
            }}
            label={t("语言适配协议")}
          />
          <small>
            {t("编辑时检查 JSON 语法，创建时校验完整协议及模型版本。")}
          </small>
        </>
      ) : (
        <>
          <div className="language-field-grid">
            <Field label={t("输入路径")}>
              <select
                value={p.input_model}
                onChange={(e) =>
                  onChange({
                    ...value,
                    assets: { ...value.assets, input: null },
                    protocol: {
                      ...p,
                      input_model: e.target.value,
                      input_checkpoint_sha256: null,
                    },
                  })
                }
              >
                <option value="text">{t("现有文本感官")}</option>
                <option value="scratch">{t("从零开始的 Transformer")}</option>
                <option value="qwen">Qwen3 Embedding 0.6B</option>
              </select>
            </Field>
            <Field label={t("输出路径")}>
              <select
                value={p.output_model}
                onChange={(e) =>
                  onChange({
                    ...value,
                    assets: { ...value.assets, head: null, output: null },
                    protocol: {
                      ...p,
                      output_model: e.target.value,
                      output_checkpoint_sha256: null,
                      mode: e.target.value === "raw" ? "core" : "strict",
                    },
                  })
                }
              >
                <option value="raw">{t("原始活动读出")}</option>
                <option value="scratch">{t("从零开始的 Transformer")}</option>
                <option value="qwen">Qwen3 0.6B</option>
              </select>
            </Field>
            {p.input_model === "text" && (
              <Field label={t("节点标记／感官模式")}>
                <select
                  value={value.text_sensor?.encoding ?? "anonymous-distributed"}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      text_sensor: {
                        ...value.text_sensor,
                        encoding: e.target.value,
                      },
                    })
                  }
                >
                  <option value="anonymous-distributed">
                    {t("匿名分布式")}
                  </option>
                  <option value="labeled-observation">
                    {t("外部标签观察")}
                  </option>
                  <option value="literal-character">{t("明文字符对照")}</option>
                </select>
              </Field>
            )}
            {p.output_model !== "raw" && (
              <Field label={t("转换方式")}>
                <select
                  value={p.mode}
                  onChange={(e) => patch("mode", e.target.value)}
                >
                  <option value="strict">
                    {t("严格转换：只看 Core 活动")}
                  </option>
                  <option value="assisted">
                    {t("知识辅助：同时看到原问题")}
                  </option>
                </select>
              </Field>
            )}
            <Field label={t("响应观察长度（模拟毫秒）")}>
              <input
                type="number"
                min={10}
                max={10000}
                step={10}
                value={p.response_us / 1000}
                onChange={(e) =>
                  patch("response_us", Number(e.target.value) * 1000)
                }
              />
            </Field>
            <Field label={t("活动转换特征")}>
              <select
                aria-label={t("活动转换特征")}
                value={p.feature_layout ?? "signed-average"}
                onChange={(e) => {
                  const peak = e.target.value === "unsigned-peak";
                  onChange({
                    ...value,
                    assets: { ...value.assets, head: null },
                    protocol: {
                      ...p,
                      schema_id: `threemind.language-adapter/${peak ? 2 : 1}`,
                      feature_layout: peak ? "unsigned-peak" : undefined,
                    },
                  });
                }}
              >
                <option value="signed-average">
                  {t("有符号平均 · 原协议")}
                </option>
                <option value="unsigned-peak">
                  {t("无符号峰值 · 新观察协议")}
                </option>
              </select>
              <small>
                {t(
                  "只改变外部活动投影；切换后需要重新校准转换头，已有意识保持原协议。",
                )}
              </small>
            </Field>
          </div>
          {["input", "output"]
            .filter((role) => p[role + "_model"] === "scratch")
            .map((role) => (
              <Field
                key={role}
                label={t(
                  role === "input"
                    ? "输入 Transformer 权重"
                    : "输出 Transformer 权重",
                )}
              >
                <select
                  value={value.assets?.[role] ?? ""}
                  onChange={(e) => selectModel(role, e.target.value)}
                >
                  <option value="">{t("未经训练 · 按种子随机初始化")}</option>
                  {models
                    .filter((m) => m.metadata.kind === "language-scratch")
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} · {m.sha256.slice(0, 10)}
                      </option>
                    ))}
                </select>
              </Field>
            ))}
          {p.output_model !== "raw" && (
            <Field label={t("活动到语言的映射")}>
              <select
                value={value.assets?.head ?? ""}
                onChange={(e) => {
                  const item = models.find((m) => m.id === e.target.value);
                  onChange({
                    ...value,
                    assets: { ...value.assets, head: e.target.value || null },
                    protocol: item?.metadata.protocol ?? p,
                  });
                }}
              >
                <option value="">{t("未校准：保留原始读出")}</option>
                {models
                  .filter((m) => m.metadata.kind === "language-head")
                  .map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} · {m.sha256.slice(0, 10)}
                    </option>
                  ))}
              </select>
            </Field>
          )}
          <p className="muted">
            {t(
              "随机权重模型没有预先学过语言。原始读出始终保留，语言转换的结果需要通过对照实验检验。",
            )}
          </p>
          <details>
            <summary>{t("高级参数")}</summary>
            <div className="language-field-grid">
              {[
                ["seed", "随机种子"],
                ["embedding_dimensions", "感官维数"],
                ["sample_us", "活动采样间隔（微秒）"],
                ["feature_buckets", "活动投影维数"],
                ["feature_bins", "时间分段数"],
                ["prefix_tokens", "活动前缀长度"],
                ["maximum_tokens", "输出长度上限"],
                ["scratch_width", "随机模型宽度"],
                ["scratch_heads", "注意力头数"],
                ["scratch_layers", "Transformer 层数"],
                ["scratch_context", "字节上下文长度"],
              ].map(([key, label]) => (
                <Field key={key} label={t(label)}>
                  <input
                    type="number"
                    value={p[key]}
                    onChange={(e) => patch(key, Number(e.target.value))}
                  />
                </Field>
              ))}
              <Field label={t("计算设备")}>
                <select
                  value={value.compute.compute_device}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      compute: {
                        ...value.compute,
                        compute_device: e.target.value,
                      },
                    })
                  }
                >
                  <option value="cpu">CPU</option>
                  <option value="cuda">GPU · CUDA</option>
                  <option value="auto">{t("自动选择")}</option>
                </select>
              </Field>
            </div>
            <p className="muted">
              {t(
                "模型结构、感官映射和权重在意识创建时绑定。使用训练后的新版本时，从原意识检查点建立新的对照意识。",
              )}
            </p>
          </details>
        </>
      )}
    </section>
  );
}
