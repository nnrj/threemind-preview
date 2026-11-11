import { useState } from "react";
import { Button, Field, ErrorBox } from "./ui";
import { post } from "./api";
import { t } from "./i18n";

export default function RobotControls({
  root,
  run,
  notify,
}: {
  root: string;
  run: any;
  notify: (text: string) => void;
}) {
  const task = run.spec.robot_protocol;
  const motors = [...task.world.motors].sort((a, b) =>
    a.id < b.id ? -1 : a.id > b.id ? 1 : 0,
  );
  const [kind, setKind] = useState("force"),
    [body, setBody] = useState(task.endpoint_body);
  const [force, setForce] = useState([0, 0, 0]),
    [torque, setTorque] = useState([0, 0, 0]);
  const [commands, setCommands] = useState(motors.map(() => 0)),
    [duration, setDuration] = useState(100000);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  async function send(action: string) {
    setBusy(true);
    setError(null);
    try {
      const receipt = await post(
        `${root}/runs/${run.id}/commands`,
        action === "checkpoint"
          ? { kind: "checkpoint" }
          : {
              kind: "robot_control",
              payload: {
                action,
                duration_us: duration,
                ...(action === "force"
                  ? { body_id: body, force, torque }
                  : action === "actuators"
                    ? { commands }
                    : {}),
              },
            },
      );
      notify(
        `${t("已提交操作，工作进程处理后写入事件记录。收据：")}${receipt.id ?? JSON.stringify(receipt)}`,
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const vector = (
    label: string,
    value: number[],
    change: (v: number[]) => void,
  ) => (
    <div className="form-grid">
      {value.map((v, i) => (
        <Field key={i} label={t(`${label} ${["X", "Y", "Z"][i]}`)}>
          <input
            type="number"
            step="any"
            value={v}
            onChange={(e) =>
              change(
                value.map((x, j) => (i === j ? e.target.valueAsNumber : x)),
              )
            }
          />
        </Field>
      ))}
    </div>
  );
  return (
    <details className="robot-interventions">
      <summary>{t("人工干预与快照")}</summary>
      <p className="footnote">
        {t(
          "干预会影响机器人并留下记录。力采用世界坐标；执行器指令为 -1～1。暂停时先排队，随后单步或继续；持续时间按模拟时间计算。",
        )}
      </p>
      <ErrorBox error={error} />
      <Field label={t("干预方式")}>
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="force">{t("施加外力与力矩")}</option>
          <option value="actuators">{t("临时接管执行器")}</option>
        </select>
      </Field>
      {kind === "force" ? (
        <>
          <Field label={t("施力部件")}>
            <select value={body} onChange={(e) => setBody(e.target.value)}>
              {task.world.bodies.map((b: any) => (
                <option key={b.id} value={b.id}>
                  {b.label || b.id}
                </option>
              ))}
            </select>
          </Field>
          {vector("力（N）", force, setForce)}
          {vector("力矩（Nm）", torque, setTorque)}
        </>
      ) : (
        <div className="form-grid">
          {motors.map((m: any, i: number) => (
            <Field key={m.id} label={`${m.label || m.id} · ${m.id}`}>
              <input
                type="number"
                min="-1"
                max="1"
                step="0.05"
                value={commands[i]}
                onChange={(e) =>
                  setCommands(
                    commands.map((v, j) =>
                      i === j ? e.target.valueAsNumber : v,
                    ),
                  )
                }
              />
            </Field>
          ))}
        </div>
      )}
      <Field label={t("持续时间（μs）")}>
        <input
          type="number"
          min={task.world.physics.sample_us}
          step={task.world.physics.sample_us}
          value={duration}
          onChange={(e) => setDuration(e.target.valueAsNumber)}
        />
      </Field>
      <div className="form-actions">
        <Button disabled={busy} onClick={() => void send(kind)}>
          {t("提交干预")}
        </Button>
        <Button disabled={busy} onClick={() => void send("release")}>
          {t("解除人工干预")}
        </Button>
        <Button disabled={busy} onClick={() => void send("checkpoint")}>
          {t("保存完整快照")}
        </Button>
        <Button disabled={busy} onClick={() => void send("reset_world")}>
          {t("仅复位世界")}
        </Button>
      </div>
      <p className="footnote">
        {t(
          "复位保留意识及已递送和在途输入，仅重建外部物理状态；快照可在研究操作中分叉恢复。",
        )}
      </p>
    </details>
  );
}
