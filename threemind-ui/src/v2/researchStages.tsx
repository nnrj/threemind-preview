import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { post } from "./api";
import { Button, ErrorBox, Field } from "./ui";
import JsonEditor, { parseJson } from "./JsonEditor";
import { t } from "./i18n";

type Step = { command: string; parameters: Record<string, any> };
type Stage = { name: string; repeat: number; steps: Step[] };
export type StageProtocol = {
  schema_version: string;
  mode: string;
  limits: Record<string, number>;
  stages: Stage[];
};
const initialStage = (): Stage => ({
  name: t("重复刺激"),
  repeat: 20,
  steps: [
    {
      command: "stimulus.send",
      parameters: { text: "甲是松子", intensity: 1 },
    },
    { command: "runtime.wait", parameters: { duration_us: 10000000 } },
  ],
});
const choices = [
  "stimulus.send",
  "stimulus.frames",
  "runtime.wait",
  "observe.summary",
  "observe.output",
  "snapshot.capture",
  "experiment.note",
];
const defaults: Record<string, Record<string, any>> = {
  "stimulus.send": { text: "", intensity: 1 },
  "stimulus.frames": {
    frames: [{ time_us: "0", channels: [[1, 0.8]], intensity: 1 }],
  },
  "runtime.wait": { duration_us: 10000000 },
  "observe.summary": {},
  "observe.output": {},
  "snapshot.capture": { label: "研究状态" },
  "experiment.note": { text: "" },
};
const names: Record<string, string> = {
  "stimulus.send": "发送文本刺激",
  "stimulus.frames": "发送匿名刺激帧",
  "runtime.wait": "推进模拟时间",
  "observe.summary": "状态摘要",
  "observe.output": "输出引用",
  "snapshot.capture": "命名状态引用",
  "experiment.note": "实验注记",
};

function FramesField({
  value,
  onChange,
}: {
  value: any[];
  onChange: (value: any[]) => void;
}) {
  const [page, setPage] = useState(0);
  const [channelPages, setChannelPages] = useState<Record<number, number>>({});
  const update = (index: number, frame: any) =>
    onChange(value.map((f, i) => (i === index ? frame : f)));
  return (
    <div>
      <p>{t("匿名帧（原始通道与相对时间）")}</p>
      {value.slice(page * 5, page * 5 + 5).map((frame, offset) => {
        const index = page * 5 + offset;
        const channelPage = Math.min(
          channelPages[index] ?? 0,
          Math.max(0, Math.ceil(frame.channels.length / 50) - 1),
        );
        return (
          <details open key={index}>
            <summary>
              {t("帧")} {index + 1}
            </summary>
            <div className="form-grid">
              <Field label={t("相对时间（微秒）")}>
                <input
                  value={frame.time_us}
                  onChange={(e) =>
                    update(index, { ...frame, time_us: e.target.value })
                  }
                />
              </Field>
              <Field label={t("刺激强度")}>
                <input
                  type="number"
                  step="any"
                  value={frame.intensity ?? 1}
                  onChange={(e) =>
                    update(index, {
                      ...frame,
                      intensity: Number(e.target.value),
                    })
                  }
                />
              </Field>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("通道")}</th>
                    <th>{t("幅值")}</th>
                    <th>{t("操作")}</th>
                  </tr>
                </thead>
                <tbody>
                  {frame.channels
                    .slice(channelPage * 50, (channelPage + 1) * 50)
                    .map((channel: number[], offset: number) => {
                      const j = channelPage * 50 + offset;
                      return (
                        <tr key={j}>
                          {[0, 1].map((k) => (
                            <td key={k}>
                              <input
                                aria-label={t(k ? "幅值" : "通道")}
                                type="number"
                                step={k ? "any" : "1"}
                                value={channel[k]}
                                onChange={(e) =>
                                  update(index, {
                                    ...frame,
                                    channels: frame.channels.map(
                                      (c: number[], pos: number) =>
                                        pos === j
                                          ? c.map((v, part) =>
                                              part === k
                                                ? Number(e.target.value)
                                                : v,
                                            )
                                          : c,
                                    ),
                                  })
                                }
                              />
                            </td>
                          ))}
                          <td>
                            <Button
                              disabled={frame.channels.length === 1}
                              aria-label={t("删除通道")}
                              onClick={() =>
                                update(index, {
                                  ...frame,
                                  channels: frame.channels.filter(
                                    (_: unknown, pos: number) => pos !== j,
                                  ),
                                })
                              }
                            >
                              <Trash2 size={14} />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
            <div className="json-actions">
              <Button
                disabled={channelPage === 0}
                onClick={() =>
                  setChannelPages({ ...channelPages, [index]: channelPage - 1 })
                }
              >
                {t("上一页")}
              </Button>
              <span>
                {t("通道")} {channelPage + 1}/
                {Math.max(1, Math.ceil(frame.channels.length / 50))}
              </span>
              <Button
                disabled={(channelPage + 1) * 50 >= frame.channels.length}
                onClick={() =>
                  setChannelPages({ ...channelPages, [index]: channelPage + 1 })
                }
              >
                {t("下一页")}
              </Button>
              <Button
                onClick={() =>
                  update(index, {
                    ...frame,
                    channels: [
                      ...frame.channels,
                      [
                        frame.channels.reduce(
                          (max: number, c: number[]) => Math.max(max, c[0]),
                          0,
                        ) + 1,
                        0.5,
                      ],
                    ],
                  })
                }
              >
                {t("添加通道")}
              </Button>
              <Button
                disabled={value.length === 1}
                onClick={() => {
                  onChange(value.filter((_, i) => i !== index));
                  setPage(0);
                }}
              >
                {t("删除帧")}
              </Button>
            </div>
          </details>
        );
      })}
      <div className="json-actions">
        <Button disabled={page === 0} onClick={() => setPage(page - 1)}>
          {t("上一页")}
        </Button>
        <span>
          {page + 1}/{Math.max(1, Math.ceil(value.length / 5))}
        </span>
        <Button
          disabled={(page + 1) * 5 >= value.length}
          onClick={() => setPage(page + 1)}
        >
          {t("下一页")}
        </Button>
        <Button
          disabled={value.length >= 4096}
          onClick={() => {
            onChange([
              ...value,
              {
                time_us: String(Number(value.at(-1)?.time_us ?? 0) + 1000),
                channels: [[1, 0.5]],
                intensity: 1,
              },
            ]);
            setPage(Math.floor(value.length / 5));
          }}
        >
          {t("添加帧")}
        </Button>
      </div>
    </div>
  );
}

export default function StageEditor({
  base,
  revision,
  limits,
  initial,
  derivedFrom,
  onDone,
}: {
  base: string;
  revision: number;
  limits: Record<string, number>;
  initial?: StageProtocol;
  derivedFrom?: string;
  onDone: (id: string) => void;
}) {
  const [name, setName] = useState(t("阶段重复实验"));
  const [protocol, setProtocol] = useState<StageProtocol>(
    initial ?? {
      schema_version: "threemind.research-plan/3",
      mode: "confirm",
      limits,
      stages: [
        initialStage(),
        {
          name: t("结果观察"),
          repeat: 1,
          steps: [{ command: "observe.output", parameters: {} }],
        },
      ],
    },
  );
  const [json, setJson] = useState(false),
    [raw, setRaw] = useState(""),
    [notice, setNotice] = useState("");
  const request = useRef<{ content: string; id: string } | undefined>(
    undefined,
  );
  const working = () => (json ? parseJson(raw) : protocol);
  const validation = useMutation({
    mutationFn: async (switchBack: boolean) => {
      const result = await post(`${base}/research/plans/validate`, working());
      if (result.protocol.schema_version !== "threemind.research-plan/3")
        throw new Error(t("阶段编辑器需要 research-plan/3 协议。"));
      setProtocol(result.protocol);
      if (switchBack) setJson(false);
      setNotice(
        `${t("校验通过")} · ${result.totals.steps} ${t("步")} · ${result.totals.stimuli} ${t("次刺激")} · ${result.totals.wait_us / 1e6} s`,
      );
      return result;
    },
  });
  const save = useMutation({
    mutationFn: async () => {
      const checked = await post(`${base}/research/plans/validate`, working());
      const body = {
        name,
        expected_revision: revision,
        protocol: checked.protocol,
        ...(derivedFrom ? { derived_from: derivedFrom } : {}),
      };
      const content = JSON.stringify(body);
      if (request.current?.content !== content)
        request.current = { content, id: crypto.randomUUID() };
      return post(`${base}/research/plans`, {
        ...body,
        request_id: request.current.id,
      });
    },
    onSuccess: (value) => onDone(value.id),
  });
  const stageChange = (i: number, stage: Stage) =>
    setProtocol({
      ...protocol,
      stages: protocol.stages.map((s, j) => (j === i ? stage : s)),
    });
  const count = protocol.stages.reduce(
    (n, s) => n + s.repeat * s.steps.length,
    0,
  );
  return (
    <div className="plan-editor">
      <Field label={t("实验计划名称")}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
        />
      </Field>
      <div className="panel-heading">
        <h3>{t("阶段与重复")}</h3>
        <button
          className="text-link"
          onClick={() => {
            if (json) validation.mutate(true);
            else {
              setRaw(JSON.stringify(protocol, null, 2));
              setJson(true);
            }
          }}
        >
          {t(json ? "切换为图形配置" : "切换为 JSON 编辑")}
        </button>
      </div>
      <p>
        {t(
          "每个阶段按顺序执行其中步骤，再按重复次数完整循环；完成后进入下一阶段。重复游标与推进目标会保存，暂停恢复不重新教学。",
        )}
      </p>
      <ErrorBox error={validation.error ?? save.error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {json ? (
        <>
          <div className="json-actions">
            <Button
              onClick={() => {
                try {
                  setRaw(JSON.stringify(parseJson(raw), null, 2));
                } catch (e) {
                  setNotice(String(e));
                }
              }}
            >
              {t("格式化 JSON")}
            </Button>
          </div>
          <JsonEditor
            label={t("阶段协议 JSON")}
            value={raw}
            onChange={setRaw}
            rows={22}
          />
        </>
      ) : (
        <>
          <Field label={t("执行模式")}>
            <select
              value={protocol.mode}
              onChange={(e) =>
                setProtocol({ ...protocol, mode: e.target.value })
              }
            >
              <option value="confirm">{t("确认后执行完整计划")}</option>
              <option value="manual">{t("人工逐步（每次只执行一步）")}</option>
              <option value="automatic">{t("受限自动（仅同源沙箱）")}</option>
            </select>
          </Field>
          {protocol.stages.map((stage, i) => (
            <article className="panel kernel-help" key={i}>
              <div className="form-grid">
                <Field label={`${t("阶段")} ${i + 1}`}>
                  <input
                    value={stage.name}
                    onChange={(e) =>
                      stageChange(i, { ...stage, name: e.target.value })
                    }
                  />
                </Field>
                <Field label={t("完整重复次数")}>
                  <input
                    type="number"
                    min={1}
                    max={1000}
                    value={stage.repeat}
                    onChange={(e) =>
                      stageChange(i, {
                        ...stage,
                        repeat: Number(e.target.value),
                      })
                    }
                  />
                </Field>
              </div>
              {stage.steps.map((step, j) => (
                <div className="plan-stage-step" key={j}>
                  <div className="panel-heading">
                    <Field label={`${t("步骤")} ${j + 1}`}>
                      <select
                        value={step.command}
                        onChange={(e) =>
                          stageChange(i, {
                            ...stage,
                            steps: stage.steps.map((s, k) =>
                              k === j
                                ? {
                                    command: e.target.value,
                                    parameters: structuredClone(
                                      defaults[e.target.value],
                                    ),
                                  }
                                : s,
                            ),
                          })
                        }
                      >
                        {choices.map((c) => (
                          <option value={c} key={c}>
                            {t(names[c])}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Button
                      disabled={stage.steps.length === 1}
                      aria-label={t("删除步骤")}
                      onClick={() =>
                        stageChange(i, {
                          ...stage,
                          steps: stage.steps.filter((_, k) => k !== j),
                        })
                      }
                    >
                      <Trash2 size={15} />
                    </Button>
                  </div>
                  {Object.entries(step.parameters).map(([key, value]) => {
                    const update = (v: unknown) =>
                      stageChange(i, {
                        ...stage,
                        steps: stage.steps.map((s, k) =>
                          k === j
                            ? {
                                ...s,
                                parameters: { ...s.parameters, [key]: v },
                              }
                            : s,
                        ),
                      });
                    if (key === "frames")
                      return (
                        <FramesField
                          key={key}
                          value={value}
                          onChange={update}
                        />
                      );
                    return (
                      <Field
                        key={key}
                        label={t(
                          (
                            {
                              text: "文本",
                              intensity: "刺激强度",
                              duration_us: "推进微秒数",
                              label: "状态名称",
                            } as Record<string, string>
                          )[key] ?? key,
                        )}
                      >
                        {typeof value === "number" ? (
                          <input
                            type="number"
                            step="any"
                            value={value}
                            onChange={(e) => update(Number(e.target.value))}
                          />
                        ) : (
                          <textarea
                            rows={2}
                            value={value}
                            onChange={(e) => update(e.target.value)}
                          />
                        )}
                      </Field>
                    );
                  })}
                </div>
              ))}
              <div className="json-actions">
                <Button
                  disabled={stage.steps.length >= 200}
                  onClick={() =>
                    stageChange(i, {
                      ...stage,
                      steps: [
                        ...stage.steps,
                        { command: "observe.output", parameters: {} },
                      ],
                    })
                  }
                >
                  <Plus size={15} />
                  {t("添加步骤")}
                </Button>
                {[
                  [-1, ArrowUp],
                  [1, ArrowDown],
                ].map(([direction, Icon]: any) => (
                  <Button
                    key={direction}
                    disabled={
                      i + direction < 0 ||
                      i + direction >= protocol.stages.length
                    }
                    aria-label={t(direction < 0 ? "上移阶段" : "下移阶段")}
                    onClick={() => {
                      const stages = [...protocol.stages];
                      [stages[i], stages[i + direction]] = [
                        stages[i + direction],
                        stages[i],
                      ];
                      setProtocol({ ...protocol, stages });
                    }}
                  >
                    <Icon size={15} />
                  </Button>
                ))}
                <Button
                  disabled={protocol.stages.length === 1}
                  onClick={() =>
                    setProtocol({
                      ...protocol,
                      stages: protocol.stages.filter((_, j) => j !== i),
                    })
                  }
                >
                  {t("删除阶段")}
                </Button>
              </div>
            </article>
          ))}
          <Button
            disabled={protocol.stages.length >= 200}
            onClick={() =>
              setProtocol({
                ...protocol,
                stages: [...protocol.stages, initialStage()],
              })
            }
          >
            <Plus size={15} />
            {t("添加阶段")}
          </Button>
          <details>
            <summary>{t("资源与执行上限")}</summary>
            <div className="form-grid">
              {Object.entries(protocol.limits).map(([key, value]) => (
                <Field label={key} key={key}>
                  <input
                    type="number"
                    value={value}
                    onChange={(e) =>
                      setProtocol({
                        ...protocol,
                        limits: {
                          ...protocol.limits,
                          [key]: Number(e.target.value),
                        },
                      })
                    }
                  />
                </Field>
              ))}
            </div>
          </details>
          <p>
            {t("展开后步骤数")}: {count}
          </p>
        </>
      )}
      <div className="json-actions">
        <Button
          disabled={validation.isPending}
          onClick={() => validation.mutate(false)}
        >
          {t("校验计划")}
        </Button>
        <Button
          variant="primary"
          disabled={save.isPending || !name.trim()}
          onClick={() => save.mutate()}
        >
          {t("冻结并保存计划")}
        </Button>
      </div>
    </div>
  );
}
