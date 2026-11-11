import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { api, post } from "./api";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  PageTitle,
  useWorkspace,
} from "./ui";
import RobotEditor, { controlNames } from "./RobotEditor";
import RobotControls from "./RobotControls";
import WorldScene from "./WorldScene";
import { NewRun } from "./research";
import { t } from "./i18n";
import { can } from "./access";
import "./robots.css";

export default function Robots() {
  const { project, user } = useWorkspace(),
    client = useQueryClient();
  const [search, setSearch] = useSearchParams();
  const [task, setTask] = useState<any>(),
    [preview, setPreview] = useState<any>();
  const [saved, setSaved] = useState<any>(),
    [create, setCreate] = useState(false),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [tab, setTab] = useState("scene"),
    [offset, setOffset] = useState(0);
  const nonce = useRef(crypto.randomUUID());
  const root = `/projects/${project?.id}`,
    runId = search.get("run");
  const writable =
    can(user, "worlds.write") &&
    ["owner", "researcher"].includes(project?.role ?? "");
  useEffect(() => {
    setTask(undefined);
    setPreview(undefined);
    setSaved(undefined);
    setNotice("");
    setOffset(0);
  }, [project?.id]);
  const linkedWorld = search.get("world");
  useEffect(() => {
    if (!linkedWorld || !project) return;
    let current = true;
    api(`${root}/worlds/${linkedWorld}`)
      .then((r) => {
        if (current) {
          setSaved(r);
          change(r.protocol);
        }
      })
      .catch((e) => {
        if (current) setError(e);
      });
    return () => {
      current = false;
    };
  }, [linkedWorld, project?.id]);
  const library = useQuery({
    queryKey: ["robot-library", project?.id, offset],
    queryFn: () => api<any>(`${root}/worlds?kind=robot&offset=${offset}`),
    enabled: !!project,
  });
  const runs = useQuery({
    queryKey: ["robot-runs", project?.id],
    queryFn: () => api<any[]>(`${root}/runs?limit=200`),
    enabled: !!project,
    refetchInterval: 4000,
  });
  const run = useQuery({
    queryKey: ["robot-run", project?.id, runId],
    queryFn: () => api<any>(`${root}/runs/${runId}`),
    enabled: !!project && !!runId,
    refetchInterval: 1000,
  });
  const observed = useQuery({
    queryKey: ["robot-observe", project?.id, runId, run.data?.revision],
    queryFn: () => api<any>(`${root}/runs/${runId}/world/observation`),
    enabled: !!runId && !!run.data?.revision,
    gcTime: 0,
  });
  const scene = useQuery({
    queryKey: ["robot-scene", project?.id, runId],
    queryFn: () => api<any>(`${root}/runs/${runId}/world/protocol`),
    enabled: !!runId && !!run.data?.revision,
    staleTime: Infinity,
    gcTime: 60000,
  });
  const change = (v: any) => {
    setTask(v);
    setPreview(undefined);
    nonce.current = crypto.randomUUID();
  };
  async function attempt(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function check() {
    const checked = await post(`${root}/robots/validate`, { protocol: task });
    setPreview(checked);
    return checked;
  }
  const chooseRun = (id: string) =>
    setSearch(id ? { view: "robots", run: id } : { view: "robots" });
  const current = run.data?.spec.environment === "robot" ? run.data : undefined;
  const layout = runId ? observed.data?.observation : preview?.layout;
  const rendered = runId ? scene.data?.protocol : preview?.scene_protocol;
  const metrics = current?.metrics ?? preview?.layout?.task_metrics;
  if (!project)
    return (
      <Empty
        title={t("请选择项目")}
        detail={t("机器人任务和证据按项目保存。")}
      />
    );
  return (
    <>
      <PageTitle
        eyebrow="ROBOT EXPERIMENTS"
        title={t("机器人任务")}
        description={t(
          "从原始力矩开始，观察感觉如何变成动作。任务成绩由环境评价。",
        )}
        actions={
          <Link
            className="text-link"
            to="/docs?doc=docs/zh/plans/robotics-and-language.md"
          >
            {t("方案与验收边界")}
          </Link>
        }
      />
      <ErrorBox
        error={
          error ?? run.error ?? observed.error ?? scene.error ?? library.error
        }
      />
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <div className="robot-toolbar">
        <Field label={t("观察机器人意识")}>
          <select
            value={runId ?? ""}
            onChange={(e) => chooseRun(e.target.value)}
          >
            <option value="">{t("配置新任务与预览")}</option>
            {runs.data
              ?.filter((r) => r.spec.environment === "robot")
              .map((r) => (
                <option value={r.id} key={r.id}>
                  {r.name}
                </option>
              ))}
          </select>
        </Field>
        {current && (
          <>
            <span>
              {current.name} · {t(current.status)} ·{" "}
              {(Number(current.time_us) / 1e6).toFixed(2)} s ·{" "}
              {t(controlNames[current.spec.robot_protocol.control.mode])}
            </span>
            {writable && (
              <Button
                disabled={
                  busy || ["completed", "cancelled"].includes(current.status)
                }
                onClick={() =>
                  void attempt(async () => {
                    await post(`${root}/runs/${runId}/commands`, {
                      kind: current.status === "paused" ? "resume" : "pause",
                    });
                    await client.invalidateQueries({ queryKey: ["robot-run"] });
                  })
                }
              >
                {t(current.status === "paused" ? "继续" : "暂停")}
              </Button>
            )}
            {writable && (
              <Button
                disabled={
                  busy || current.status !== "paused" || current.life === "dead"
                }
                onClick={() =>
                  void attempt(async () => {
                    await post(`${root}/runs/${runId}/research/actions`, {
                      kind: "runtime.advance",
                      request_id: crypto.randomUUID(),
                      expected_revision: current.revision,
                      duration_us:
                        current.spec.robot_protocol.world.physics.sample_us,
                    });
                    setNotice(t("已提交一个感官周期的步进，完成后自动暂停。"));
                  })
                }
              >
                {t("单步")}
              </Button>
            )}
            <Link className="text-link" to={`/runs/${runId}?tab=research`}>
              {t("意识、快照与研究操作")}
            </Link>
          </>
        )}
      </div>
      <div
        className="robot-mobile-tabs tabs"
        role="tablist"
        aria-label={t("机器人工作区")}
      >
        {[
          ["scene", "三维观察"],
          ["configure", "配置"],
          ["signals", "感官与动作"],
        ].map(([id, name]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? "active" : ""}
            onClick={() => setTab(id)}
          >
            {t(name)}
          </button>
        ))}
      </div>
      <div className={`robot-workspace robot-tab-${tab}`}>
        <section className="panel robot-scene-panel">
          <div className="panel-heading">
            <h2>{t("三维观察")}</h2>
            <span>
              {layout
                ? `${Number(layout.physical_time_us) / 1e6} s`
                : t("尚未步进")}
            </span>
          </div>
          {rendered && layout ? (
            <WorldScene protocol={rendered} observation={layout} />
          ) : (
            <Empty
              title={t(
                runId
                  ? "等待工作进程提交物理状态"
                  : preview?.valid
                    ? "配置已校验，等待任务开始"
                    : "先校验与预览任务",
              )}
              detail={t(
                preview?.valid && !layout
                  ? "创建意识并接入后，Linux worker 将计算并保存场景，随后可在此观察。"
                  : "转动观察相机不会向意识或机器人施加刺激。",
              )}
            />
          )}
          {metrics && (
            <div className="robot-metrics">
              {metrics.task_reward !== undefined && (
                <>
                  <span>
                    {t("官方任务末步评分")}{" "}
                    <strong>{Number(metrics.task_reward).toFixed(3)}</strong>
                  </span>
                  <span>
                    {t("官方任务累计评分")}{" "}
                    <strong>
                      {Number(metrics.task_reward_total).toFixed(3)}
                    </strong>
                  </span>
                </>
              )}
              <span>
                {t("目标距离")}{" "}
                <strong>{Number(metrics.task_distance).toFixed(3)} m</strong>
              </span>
              <span>
                {t("距离改善")}{" "}
                <strong>
                  {Number(metrics.task_distance_improvement).toFixed(3)} m
                </strong>
              </span>
              <span>
                {t("任务完成")}{" "}
                <strong>
                  {metrics.task_success_observed === false
                    ? "—"
                    : metrics.task_success
                      ? t("是")
                      : t("否")}
                </strong>
              </span>
            </div>
          )}
          {current &&
            writable &&
            !["completed", "cancelled", "failed"].includes(current.status) && (
              <RobotControls
                key={current.id}
                root={root}
                run={current}
                notify={setNotice}
              />
            )}
        </section>
        <section className="panel robot-config-panel">
          {!runId && (
            <>
              <Field label={t("已保存的机器人任务")}>
                <select
                  value={saved?.document_id ?? ""}
                  onChange={(e) => {
                    const id = e.target.value;
                    if (!id) {
                      setSaved(undefined);
                      return;
                    }
                    void attempt(async () => {
                      const r = await api(`${root}/worlds/${id}`);
                      setSaved(r);
                      change(r.protocol);
                    });
                  }}
                >
                  <option value="">{t("新任务")}</option>
                  {library.data?.rows.map((r: any) => (
                    <option value={r.id} key={r.id}>
                      {r.title} · r{r.revision}
                    </option>
                  ))}
                </select>
              </Field>
              {(offset > 0 || library.data?.more) && (
                <div className="form-actions">
                  <Button
                    disabled={!offset}
                    onClick={() => setOffset(offset - 30)}
                  >
                    {t("上一页")}
                  </Button>
                  <Button
                    disabled={!library.data?.more}
                    onClick={() => setOffset(offset + 30)}
                  >
                    {t("下一页")}
                  </Button>
                </div>
              )}
            </>
          )}
          <RobotEditor
            key={runId ?? project.id}
            project={project.id}
            value={runId ? current?.spec.robot_protocol : task}
            onChange={change}
            readOnly={!!runId || !writable}
          />
          {!runId && (
            <div className="form-actions robot-sticky-actions">
              <Button
                disabled={busy || !task}
                onClick={() =>
                  void attempt(async () => {
                    await check();
                    setTab("scene");
                  })
                }
              >
                {t("校验与预览")}
              </Button>
              {writable && (
                <>
                  <Button
                    disabled={busy || !task}
                    onClick={() =>
                      void attempt(async () => {
                        const checked = await check();
                        const row = await post(`${root}/worlds`, {
                          operation_id: nonce.current,
                          document_id: saved?.document_id ?? null,
                          expected_revision: saved?.revision ?? 0,
                          protocol: checked.protocol,
                        });
                        setSaved(row);
                        nonce.current = crypto.randomUUID();
                        await client.invalidateQueries({
                          queryKey: ["robot-library"],
                        });
                        setNotice(t("任务版本已保存。"));
                      })
                    }
                  >
                    {t("保存任务版本")}
                  </Button>
                  <Button
                    variant="primary"
                    disabled={busy || !task}
                    onClick={() =>
                      void attempt(async () => {
                        await check();
                        setCreate(true);
                      })
                    }
                  >
                    {t("创建意识并接入")}
                  </Button>
                </>
              )}
            </div>
          )}
        </section>
        <section className="panel robot-signals-panel">
          <h2>{t("感官与动作")}</h2>
          <p className="footnote">
            {t("这里展示实际采样和执行记录。任务评分不作为内核奖励输入。")}
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("感官")}</th>
                  <th>{t("物理值")}</th>
                  <th>{t("单位")}</th>
                </tr>
              </thead>
              <tbody>
                {(
                  observed.data?.measurements ??
                  layout?.measurements ??
                  []
                ).map((m: any) => (
                  <tr key={m.id}>
                    <td>{m.id}</td>
                    <td>
                      {m.values
                        .slice(0, 6)
                        .map((v: number) => Number(v).toPrecision(4))
                        .join(", ")}
                    </td>
                    <td>{m.unit ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("执行器")}</th>
                  <th>{t("指令")}</th>
                  <th>{t("实际施力")}</th>
                </tr>
              </thead>
              <tbody>
                {(observed.data?.controls ?? layout?.controls ?? []).map(
                  (m: any) => (
                    <tr key={m.id}>
                      <td>{m.id}</td>
                      <td>{Number(m.command).toFixed(3)}</td>
                      <td>
                        {Number(m.joint_force).toFixed(4)} {m.unit}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
      <NewRun
        open={create}
        onOpenChange={setCreate}
        robotProtocol={task}
        onCreated={(r) => {
          chooseRun(r.id);
          setTab("scene");
          void client.invalidateQueries({ queryKey: ["robot-runs"] });
        }}
      />
    </>
  );
}
