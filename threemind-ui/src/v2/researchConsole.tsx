import { t, locale } from "./i18n";
import { lazy, Suspense, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import {
  ChevronRight,
  Download,
  GitFork,
  Pause,
  Play,
  RefreshCw,
} from "lucide-react";
import { api, post, timeLabel, type Run, ApiError } from "./api";
import {
  Badge,
  Button,
  ErrorBox,
  Field,
  Loading,
  Modal,
  useWorkspace,
} from "./ui";
import { InputComposer } from "./inputs";
import { InterventionFields } from "./configuration";

const Graph = lazy(() => import("./Graph"));
const ResearchPlans = lazy(() => import("./researchPlans"));
const ProbeCalibration = lazy(() => import("./probeCalibration"));
const names: Record<string, string> = {
  "runtime.advance": "逐步推进",
  "observe.summary": "状态摘要",
  "observe.graph": "图谱观察",
  "observe.output": "输出观察",
  "experiment.note": "实验注记",
};
const resultNames: Record<string, string> = {
  pending: "等待执行",
  completed: "已完成",
  interrupted: "已中断",
  failed: "失败",
};

export default function ResearchWorkspace({
  base,
  run,
}: {
  base: string;
  run: Run;
}) {
  const [query, setQuery] = useSearchParams();
  const tool = ["plans", "calibration"].includes(query.get("tool") ?? "")
    ? query.get("tool")!
    : "manual";
  return (
    <>
      <div
        className="tabs research-tool-tabs"
        role="tablist"
        aria-label={t("人工研究工具")}
      >
        {[
          ["manual", "人工操作"],
          ["plans", "受控实验计划"],
          ["calibration", "感官与探针校准"],
        ].map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tool === key}
            className={tool === key ? "active" : ""}
            onClick={() => {
              const next = new URLSearchParams(query);
              next.set("tool", key);
              setQuery(next);
            }}
          >
            {t(label)}
          </button>
        ))}
      </div>
      {tool === "calibration" ? (
        <Suspense fallback={<Loading />}>
          <ProbeCalibration key={run.id} base={base} />
        </Suspense>
      ) : tool === "plans" ? (
        <Suspense fallback={<Loading />}>
          <ResearchPlans base={base} run={run} />
        </Suspense>
      ) : (
        <ResearchConsole base={base} run={run} />
      )}
    </>
  );
}

function ResearchConsole({ base, run }: { base: string; run: Run }) {
  const { project } = useWorkspace(),
    client = useQueryClient(),
    navigate = useNavigate();
  const write = ["owner", "researcher"].includes(project?.role ?? "");
  const [seconds, setSeconds] = useState("0.01"),
    [checkpoint, setCheckpoint] = useState("");
  const [before, setBefore] = useState<string>(),
    [ceiling, setCeiling] = useState<string>();
  const [pages, setPages] = useState<(string | undefined)[]>([]),
    [note, setNote] = useState("");
  const [retry, setRetry] = useState<any>(),
    [notice, setNotice] = useState("");
  const [graph, setGraph] = useState<any>(),
    [forkOpen, setForkOpen] = useState(false),
    [forkName, setForkName] = useState(`${run.name} · 实验沙箱`);
  const [background, setBackground] = useState("preserve");
  const [intervention, setIntervention] = useState<any>({
    nodes: [],
    edges: [],
    lesion: false,
  });
  const history = useQuery<any>({
    queryKey: ["research-actions", base, before, ceiling],
    queryFn: () =>
      api(
        `${base}/research/actions?limit=30${before ? `&before=${before}` : ""}${ceiling ? `&ceiling=${ceiling}` : ""}`,
      ),
    refetchInterval: 2000,
  });
  const versions = useQuery<any[]>({
    queryKey: ["research-checkpoints", base, run.revision],
    queryFn: () => api(`${base}/checkpoints`),
    gcTime: 0,
  });
  function refresh() {
    setBefore(undefined);
    setCeiling(undefined);
    setPages([]);
    for (const key of [
      "run",
      "runs",
      "research-actions",
      "research-checkpoints",
      "checkpoints",
      "versions",
    ])
      client.invalidateQueries({ queryKey: [key] });
  }
  const action = useMutation({
    mutationFn: (body: any) => post<any>(base + "/research/actions", body),
    onSuccess: (row) => {
      setRetry(undefined);
      refresh();
      setNotice(
        row.status === "pending"
          ? t("操作已入库，工作进程将推进到指定时刻后暂停。")
          : t("已保存对真实恢复点的观察记录。"),
      );
      if (row.kind === "observe.graph") setGraph(row.result);
      if (row.kind === "experiment.note") setNote("");
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status < 500) setRetry(undefined);
    },
  });
  const control = useMutation({
    mutationFn: (body: any) => post(base + "/commands", body),
    onSuccess: () => {
      refresh();
      setNotice(
        t(
          "命令已入队，执行情况见因果事件。暂停时，排队的干预将在下一次推进开始时应用。",
        ),
      );
    },
  });
  const fork = useMutation({
    mutationFn: () =>
      post<any>(base + "/forks", {
        name: forkName,
        checkpoint_id: checkpoint || null,
        paused: true,
        background,
      }),
    onSuccess: (row) => {
      refresh();
      navigate(`/runs/${row.id}?view=research`);
    },
  });
  const pending = history.data?.rows.some((r: any) => r.status === "pending"),
    paused = ["paused", "blocked"].includes(run.status);
  const canAdvance =
    write && paused && !run.spec.study_id && run.life !== "dead" && !pending;
  function send(kind: string, parameters: any = {}) {
    const body = { request_id: crypto.randomUUID(), kind, ...parameters };
    setRetry(body);
    setNotice("");
    action.mutate(body);
  }
  function advance(duration_us?: number) {
    const duration = duration_us ?? Math.round(Number(seconds) * 1e6);
    if (
      !seconds.trim() ||
      !Number.isSafeInteger(duration) ||
      duration <= 0 ||
      duration > 86400000000
    ) {
      setNotice(t("请输入 0.000001～86400 秒的推进时长。"));
      return;
    }
    send("runtime.advance", {
      duration_us: duration,
      expected_revision: run.revision,
    });
  }
  return (
    <section className="research-console" aria-label={t("人工实验控制台")}>
      <div className="panel-heading">
        <div>
          <h2>{t("人工实验控制台")}</h2>
          <p>
            {t(
              "先选择真实恢复点，再观察、注记或从暂停状态逐步推进。所有操作保存编号与结果。",
            )}
          </p>
        </div>
        <Button onClick={refresh}>
          <RefreshCw size={14} />
          {t("刷新")}
        </Button>
      </div>
      <ErrorBox
        error={
          action.error ??
          control.error ??
          fork.error ??
          history.error ??
          versions.error
        }
      />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {retry && action.isError && (
        <div className="notice">
          {t("上次请求的结果未确认。重试复用编号 ")}
          {retry.request_id}
          {t("，不会额外推进一次。")}
          <Button
            disabled={action.isPending}
            onClick={() => action.mutate(retry)}
          >
            {t("重试同一操作")}
          </Button>
        </div>
      )}
      <div className="research-console-grid">
        <section className="panel research-control-panel">
          <h3>{t("推进与控制")}</h3>
          <p className="muted">
            {t("当前 ")}
            {timeLabel(run.time_us)} · r{run.revision}
            {t(
              "。推进遵守本意识的模拟时间、物理采样和速度设置；设备性能档位不改变实验时间。",
            )}
          </p>
          {!paused && (
            <p>{t("先使用页面顶部的暂停命令，等待状态保存完成。")}</p>
          )}
          {run.spec.study_id && (
            <p className="notice">
              {t("这是冻结的配对条件。请创建同源沙箱进行独立手动操作。")}
            </p>
          )}
          <Field label={t("推进时长（模拟秒）")}>
            <input
              aria-label={t("推进时长（模拟秒）")}
              type="number"
              step="any"
              min={0.000001}
              max={86400}
              value={seconds}
              onChange={(e) => setSeconds(e.target.value)}
            />
          </Field>
          <div className="json-actions">
            <Button
              variant="primary"
              disabled={!canAdvance || action.isPending || !!retry}
              onClick={() => advance()}
            >
              <Play size={14} />
              {t("推进并暂停")}
            </Button>
            <Button
              disabled={!canAdvance || action.isPending || !!retry}
              onClick={() => advance(run.spec.config.step_us)}
            >
              <ChevronRight size={14} />
              {t("一个数值步长")}
            </Button>
            <Button
              disabled={
                !write ||
                !["queued", "running"].includes(run.status) ||
                control.isPending
              }
              onClick={() => control.mutate({ kind: "pause" })}
            >
              <Pause size={14} />
              {t("中断推进")}
            </Button>
          </div>
          <details>
            <summary>{t("已有结构干预与输入关闭")}</summary>
            <p>
              {t(
                "这些操作影响模型。干预只作用于已有节点／边，暂停期间先排队，再由下一次推进执行。",
              )}
            </p>
            <InterventionFields
              value={intervention}
              readOnly={!write}
              onChange={setIntervention}
            />
            <div className="json-actions">
              <Button
                disabled={!canAdvance || control.isPending}
                onClick={() =>
                  control.mutate({
                    kind: "intervention",
                    payload: intervention,
                  })
                }
              >
                {t("将结构干预排队")}
              </Button>
              <Button
                disabled={!canAdvance || control.isPending}
                onClick={() => control.mutate({ kind: "close_inputs" })}
              >
                {t("将永久关闭输入排队")}
              </Button>
            </div>
          </details>
          <Link className="text-link" to={`?view=events`}>
            {t("查看命令实际执行的因果事件")}
          </Link>
        </section>
        <section className="panel research-control-panel">
          <h3>{t("恢复点与被动观察")}</h3>
          <Field label={t("研究恢复点")}>
            <select
              aria-label={t("研究恢复点")}
              value={checkpoint}
              onChange={(e) => setCheckpoint(e.target.value)}
            >
              <option value="">{t("最新已提交恢复点")}</option>
              {checkpoint &&
                !versions.data?.some((cp) => cp.id === checkpoint) && (
                  <option value={checkpoint}>{t("指定历史恢复点")}</option>
                )}
              {versions.data?.map((cp) => (
                <option key={cp.id} value={cp.id}>
                  r{cp.revision} · {timeLabel(cp.time_us)}
                  {cp.label ? ` · ${cp.label}` : ""}
                </option>
              ))}
            </select>
          </Field>
          <p className="muted">
            {t(
              "观察不会推进时间或改变连接。进行中的意识只引用已提交版本。记录操作需要项目研究权限；只读成员可查看既有记录。",
            )}
          </p>
          <div className="json-actions">
            {[
              ["observe.summary", "记录状态摘要"],
              ["observe.graph", "查看并记录图谱"],
              ["observe.output", "记录读出与器官引用"],
            ].map(([kind, label]) => (
              <Button
                key={kind}
                disabled={
                  !write || !run.revision || action.isPending || !!retry
                }
                onClick={() =>
                  send(kind, { checkpoint_id: checkpoint || null })
                }
              >
                {t(label)}
              </Button>
            ))}
          </div>
          <Button
            disabled={!write || !run.revision}
            onClick={() => setForkOpen(true)}
          >
            <GitFork size={15} />
            {t("从此恢复点创建暂停沙箱")}
          </Button>
          <p className="footnote">
            {t(
              "复制精确模型和可恢复外部状态，保留来源；不删除原意识、不自动推进。真实物理设备会话不能复制。",
            )}
          </p>
        </section>
        <section className="panel research-control-panel">
          <h3>{t("向普通输入总线提交刺激")}</h3>
          {write ? (
            <InputComposer base={base} run={run} />
          ) : (
            <p>{t("只读成员可查询已记录的刺激。")}</p>
          )}
          <Link className="text-link" to="?view=inputs">
            {t("媒体、设备与原始输入证据")}
          </Link>
        </section>
        <section className="panel research-control-panel">
          <h3>{t("在恢复点添加实验注记")}</h3>
          <Field label={t("实验注记")}>
            <textarea
              aria-label={t("实验注记")}
              rows={6}
              value={note}
              maxLength={20000}
              onChange={(e) => setNote(e.target.value)}
              readOnly={!write}
            />
          </Field>
          <Button
            disabled={
              !write ||
              !note.trim() ||
              !run.revision ||
              action.isPending ||
              !!retry
            }
            onClick={() =>
              send("experiment.note", {
                checkpoint_id: checkpoint || null,
                text: note,
              })
            }
          >
            {t("保存恢复点注记")}
          </Button>
          <p className="footnote">
            {t(
              "这里记录短过程注记。完整笔记本、写作和结构化报告将使用独立模块。",
            )}
          </p>
        </section>
      </div>
      <section className="panel research-history">
        <div className="panel-heading">
          <h3>{t("操作与结果")}</h3>
          <a className="text-link" href={`/api/v2${base}/research/export`}>
            <Download size={14} />
            {t("导出完整操作记录 JSONL")}
          </a>
        </div>
        {history.isPending ? (
          <Loading />
        ) : !history.data?.rows.length ? (
          <p>{t("尚无操作记录。第一条观察也会保留精确恢复点与操作者。")}</p>
        ) : (
          history.data.rows.map((row: any) => (
            <article key={row.id}>
              <div className="panel-heading">
                <strong>{t(names[row.kind] ?? row.kind)}</strong>
                <span>
                  {t(resultNames[row.status] ?? row.status)} ·{" "}
                  {new Date(row.created_at).toLocaleString(locale())}
                </span>
              </div>
              {row.kind === "runtime.advance" && (
                <p>
                  {t("计划 ")}
                  {timeLabel(row.parameters.start_us)} →{" "}
                  {timeLabel(row.parameters.target_us)}
                  {t("；实际")}{" "}
                  {row.result.actual_time_us
                    ? timeLabel(row.result.actual_time_us)
                    : t("尚未提交终点")}{" "}
                  {row.result.status && <Badge status={row.result.status} />}
                </p>
              )}
              {row.kind === "experiment.note" && (
                <p className="research-note">{row.parameters.text}</p>
              )}
              {row.error && <ErrorBox error={row.error} />}
              <div className="json-actions">
                <button
                  className="text-link"
                  onClick={() =>
                    setCheckpoint(row.result_checkpoint_id || row.checkpoint_id)
                  }
                >
                  {t("选用此恢复点")}
                </button>
                <button
                  className="text-link"
                  onClick={() =>
                    setGraph({
                      checkpoint_id:
                        row.result_checkpoint_id || row.checkpoint_id,
                      revision: row.result.revision,
                    })
                  }
                >
                  {t("查看该点图谱")}
                </button>
                <Link
                  className="text-link"
                  to={`/data?run=${run.id}&checkpoint=${row.result_checkpoint_id || row.checkpoint_id}`}
                >
                  {t("查询该点节点与连接")}
                </Link>
              </div>
              {row.result.events?.map((event: any) => (
                <p key={event.channel}>
                  {event.channel} · {timeLabel(event.time_us)} ·{" "}
                  <code>event {event.event_id}</code>
                  <a
                    className="text-link"
                    href={`/api/v2${base}/research/evidence/${event.event_id}`}
                  >
                    {t("查看原始读出")}
                  </a>
                </p>
              ))}
              <details>
                <summary>{t("查看命令、结果与可复核编号")}</summary>
                <pre>{JSON.stringify(row, null, 2)}</pre>
              </details>
            </article>
          ))
        )}
        <div className="json-actions">
          <Button
            disabled={!pages.length}
            onClick={() => {
              setBefore(pages.at(-1));
              setPages(pages.slice(0, -1));
            }}
          >
            {t("上一页操作")}
          </Button>
          <span>{t("第 {page} 页", { page: pages.length + 1 })}</span>
          <Button
            disabled={!history.data?.more}
            onClick={() => {
              setPages([...pages, before]);
              setBefore(history.data.next);
              setCeiling(history.data.ceiling);
            }}
          >
            {t("下一页操作")}
          </Button>
        </div>
      </section>
      {graph && (
        <Modal
          open
          wide
          onOpenChange={() => setGraph(undefined)}
          title={t("固定恢复点的意识图谱")}
          description={t("这是 {value0} 的历史状态；观察布局不参与核心执行。", {
            value0: String(graph.checkpoint_id),
          })}
        >
          <Suspense fallback={<Loading />}>
            <Graph
              project={project!.id}
              run={run.id}
              polling={false}
              endpoint={`/api/v2${base}/graph?checkpoint_id=${graph.checkpoint_id}`}
            />
          </Suspense>
          <p>
            {t(
              "图谱按当前设备显示额度呈现，完整节点与连接可在数据查询中导出。",
            )}
          </p>
        </Modal>
      )}
      <Modal
        open={forkOpen}
        onOpenChange={setForkOpen}
        title={t("创建同源实验沙箱")}
        description={t(
          "从选中的数据库恢复点创建独立、暂停的意识。后续操作保留在新意识中。",
        )}
      >
        <Field label={t("沙箱名称")}>
          <input
            aria-label={t("沙箱名称")}
            value={forkName}
            maxLength={120}
            onChange={(e) => setForkName(e.target.value)}
          />
        </Field>
        <Field label={t("背景刺激")}>
          <select
            aria-label={t("背景刺激")}
            value={background}
            onChange={(e) => setBackground(e.target.value)}
          >
            <option value="preserve">{t("保留来源配置与背景刺激")}</option>
            <option value="suspend">
              {t("暂停新背景载体（用于受控输入实验）")}
            </option>
          </select>
        </Field>
        <p className="footnote">
          {t("该选择写入沙箱的来源配置；已经进入内核的在途事件保持原样。")}
        </p>
        <ErrorBox error={fork.error} />
        <div className="form-actions">
          <Button onClick={() => setForkOpen(false)}>{t("取消")}</Button>
          <Button
            variant="primary"
            disabled={!forkName.trim() || fork.isPending}
            onClick={() => fork.mutate()}
          >
            {t("创建暂停沙箱")}
          </Button>
        </div>
      </Modal>
    </section>
  );
}
