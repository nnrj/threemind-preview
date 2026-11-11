import { Field } from "./ui";
import { t } from "./i18n";

export default function PlaygroundEditor({
  value,
  onChange,
  readOnly,
}: {
  value: any;
  onChange: (v: any) => void;
  readOnly: boolean;
}) {
  const cfg = value.playground;
  const patch = (key: string, next: any) =>
    onChange({ ...value, playground: { ...cfg, [key]: next } });
  return (
    <section aria-label={t("官方 Playground 任务")}>
      <p className="notice">
        {t(
          "保留官方 PandaPickCube 物理与位置伺服。物理步长 5 ms，动作周期 20 ms；150 步后暂停，意识与快照保留。",
        )}
      </p>
      <div className="form-grid">
        <Field label={t("任务名称")}>
          <input
            value={value.name}
            disabled={readOnly}
            onChange={(e) => onChange({ ...value, name: e.target.value })}
          />
        </Field>
        <Field
          label={t("计算后端")}
          hint={t(
            "由具备相应能力的 Linux worker 执行。改变后端需新建任务，不静默替换旧快照。",
          )}
        >
          <select
            disabled={readOnly}
            value={`${cfg.implementation}/${cfg.device}`}
            onChange={(e) => {
              const [implementation, device] = e.target.value.split("/");
              onChange({
                ...value,
                playground: { ...cfg, implementation, device },
              });
            }}
          >
            <option value="jax/cpu">JAX / CPU</option>
            <option value="jax/cuda">JAX / CUDA</option>
            <option value="warp/cuda">Warp / CUDA</option>
          </select>
        </Field>
        <Field
          label={t("感官来源")}
          hint={t(
            "官方状态含全局位置等特权信息；两种模式均不把奖励或任务答案送入内核。",
          )}
        >
          <select
            disabled={readOnly}
            value={cfg.observation}
            onChange={(e) => patch("observation", e.target.value)}
          >
            <option value="physical-senses">{t("关节、接触与局部信标")}</option>
            <option value="official-state">
              {t("官方状态向量（特权观测）")}
            </option>
          </select>
        </Field>
        <Field label={t("目标可观测信标")}>
          <input
            type="checkbox"
            disabled={readOnly || cfg.observation === "official-state"}
            checked={value.beacon_enabled}
            onChange={(e) =>
              onChange({ ...value, beacon_enabled: e.target.checked })
            }
          />
        </Field>
        <Field label={t("感官输入强度")}>
          <input
            type="number"
            min="0"
            max="100"
            step="any"
            disabled={readOnly}
            value={cfg.input_intensity}
            onChange={(e) => patch("input_intensity", e.target.valueAsNumber)}
          />
        </Field>
        <Field label={t("输出映射增益")}>
          <input
            type="number"
            min="0"
            max="100"
            step="any"
            disabled={readOnly}
            value={cfg.projection_gain}
            onChange={(e) => patch("projection_gain", e.target.valueAsNumber)}
          />
        </Field>
      </div>
      <p className="footnote">
        {t("官方任务源码版本")} <code>{cfg.revision}</code>
      </p>
      <p className="footnote">
        {t(
          "校验配置后可保存或创建意识；首次执行的编译需要时间，worker 保存检查点后即可查看三维场景。",
        )}
      </p>
    </section>
  );
}
