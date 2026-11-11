import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, projectPath, statuses } from "./api";
import { t, dateLabel, messageKeys } from "./i18n";
import { Button, ErrorBox, Loading } from "./ui";

const reasons: Record<string, string> = messageKeys({
  running: "执行中，租约有效",
  awaiting_recovery: "租约过期，等待节点接管",
  waiting_checkpoint: "等待来源恢复点完成",
  waiting_evidence: "等待新的已提交证据",
  waiting_schedule: "等待下一次调度时间",
  admission_paused: "执行额度为 0，已暂停领取",
  no_eligible_worker: "没有在线且具备所需能力的执行节点",
  capacity: "执行额度已占满，等待已有任务释放",
  waiting_turn: "具备执行条件，等待节点领取",
  finished: "任务已结束",
});
const features: Record<string, string> = messageKeys({
  "worker.core": "意识内核",
  "worker.mujoco": "MuJoCo 物理环境",
  "worker.world_v1": "可配置世界与躯体",
  "worker.world_rgb_v1": "世界离屏 RGB 感官",
  "worker.world_authoring_v1": "世界与躯体草案",
  "worker.telemetry_host": "宿主机遥测",
  "worker.telemetry_process": "进程遥测",
  "worker.telemetry_runtime": "运行时遥测",
  "worker.ai": "AI 文本请求",
  "worker.notifications": "邮件通知",
});
const kinds: Record<string, string> = messageKeys({
  run: "意识运行",
  study: "实验准备",
  research_plan: "受控计划",
  analysis: "统计分析",
  export: "模型导出",
  data_export: "数据导出",
  ai: "AI 请求",
  notification: "通知邮件",
});

function Receipt({ base, job }: { base: string; job: string }) {
  const data = useQuery({
    queryKey: ["execution", "assignments", base, job],
    queryFn: () => api(`${base}/${job}/assignments`),
    refetchInterval: 5000,
  });
  return (
    <div className="assignment-receipts">
      <a
        className="text-link"
        href={`/api/v2${base}/${job}/assignments`}
        download={`execution-assignments-${job}.json`}
      >
        {t("导出执行回执")}
      </a>
      <ErrorBox error={data.error} />
      {data.isPending && <Loading />}
      {data.data?.length === 0 && (
        <p>{t("尚无执行回执；早期版本的历史任务不补造节点记录。")}</p>
      )}
      {data.data?.map((receipt: any) => (
        <article key={receipt.generation}>
          <strong>
            {t("第 {attempt} 次领取", { attempt: receipt.generation })}
          </strong>
          <span>
            {receipt.worker_id} · {dateLabel(receipt.assigned_at)}
          </span>
          <p>
            {t("实际内核后端")}: {receipt.capabilities.backend ?? t("不适用")}
          </p>
          <details>
            <summary>{t("领取时的能力快照")}</summary>
            <pre>{JSON.stringify(receipt, null, 2)}</pre>
          </details>
        </article>
      ))}
    </div>
  );
}

export default function SchedulingPanel({
  projectId,
  manage = false,
  runId,
}: {
  projectId: string;
  manage?: boolean;
  runId?: string;
}) {
  // Parent keys this panel by project/run so a cursor never crosses project boundaries.
  const [history, setHistory] = useState(!!runId);
  const [cursors, setCursors] = useState<
    Array<{ before_time: string; before_id: string } | null>
  >([null]);
  const [expanded, setExpanded] = useState("");
  const cursor = cursors[cursors.length - 1];
  const base = manage
    ? `/admin/execution/projects/${projectId}/jobs`
    : `${projectPath(projectId)}/execution/jobs`;
  const params = new URLSearchParams({ history: String(history) });
  if (runId) params.set("run_id", runId);
  if (cursor)
    Object.entries(cursor).forEach(([key, value]) => params.set(key, value));
  const data = useQuery({
    queryKey: ["execution", "jobs", base, runId, history, cursor],
    queryFn: () => api(`${base}?${params}`),
    refetchInterval: 3000,
  });
  return (
    <section className="scheduling-panel" aria-label={t("任务调度与执行记录")}>
      <div className="panel-heading">
        <div>
          <h3>{t("任务调度与执行记录")}</h3>
          <p>{t("显示当前等待原因及每次实际领取的节点；状态会随队列变化。")}</p>
        </div>
        {!runId && (
          <label className="check">
            <input
              type="checkbox"
              checked={history}
              onChange={(e) => {
                setHistory(e.target.checked);
                setCursors([null]);
                setExpanded("");
              }}
            />
            {t("包含已结束任务")}
          </label>
        )}
      </div>
      <ErrorBox error={data.error} />
      {data.isPending && <Loading />}
      {data.data?.rows.length === 0 && (
        <p className="muted">{t("当前筛选下没有任务。")}</p>
      )}
      <div className="scheduling-jobs">
        {data.data?.rows.map((job: any) => (
          <article key={job.id} className="scheduling-job">
            <div className="scheduling-job-heading">
              <strong>{t(kinds[job.kind] ?? job.kind)}</strong>
              <span>{t(statuses[job.status] ?? job.status)}</span>
            </div>
            <p className="scheduling-reason">
              {t(reasons[job.reason] ?? job.reason)}
            </p>
            {!manage && !runId && job.run_id && (
              <Link className="text-link" to={`/runs/${job.run_id}`}>
                {t("查看意识")}
              </Link>
            )}
            <dl>
              <div>
                <dt>{t("任务编号")}</dt>
                <dd>
                  <code>{job.id}</code>
                </dd>
              </div>
              <div>
                <dt>{t("创建时间")}</dt>
                <dd>{dateLabel(job.created_at)}</dd>
              </div>
              <div>
                <dt>{t("所需能力")}</dt>
                <dd>
                  {job.required_features.length
                    ? job.required_features
                        .map((key: string) => t(features[key] ?? key))
                        .join(" · ")
                    : t("历史记录未知")}
                </dd>
              </div>
              <div>
                <dt>{t("执行节点")}</dt>
                <dd>{job.worker_id ?? t("尚未分配")}</dd>
              </div>
              <div>
                <dt>{t("实际内核后端")}</dt>
                <dd>{job.backend ?? (job.assigned_at ? t("不适用") : "—")}</dd>
              </div>
            </dl>
            <button
              className="text-link"
              type="button"
              aria-expanded={expanded === job.id}
              onClick={() => setExpanded(expanded === job.id ? "" : job.id)}
            >
              {t(expanded === job.id ? "收起执行回执" : "查看执行回执")} (
              {job.attempts})
            </button>
            {expanded === job.id && <Receipt base={base} job={job.id} />}
          </article>
        ))}
      </div>
      {(cursors.length > 1 || data.data?.next) && (
        <div className="pagination">
          <Button
            disabled={cursors.length === 1 || data.isFetching}
            onClick={() => {
              setCursors(cursors.slice(0, -1));
              setExpanded("");
            }}
          >
            {t("上一页")}
          </Button>
          <span>{t("第 {page} 页", { page: cursors.length })}</span>
          <Button
            disabled={!data.data?.next || data.isFetching}
            onClick={() => {
              setCursors([...cursors, data.data.next]);
              setExpanded("");
            }}
          >
            {t("下一页")}
          </Button>
        </div>
      )}
      <p className="footnote">
        {t("能力匹配不保证数值后端等价，也不替代设备授权和资源隔离。")}
      </p>
    </section>
  );
}
