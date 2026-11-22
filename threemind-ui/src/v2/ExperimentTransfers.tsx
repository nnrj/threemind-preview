import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Directory } from "./ExperimentStorage";
import { t } from "./i18n";
import { Button, ErrorBox, Field } from "./ui";

const base = "/storage/experiment-pool/transfers";
const actions = {
  sync: "单向同步",
  backup: "版本备份",
  migrate: "迁移",
  archive: "归档到移动存储",
  unarchive: "从归档放回运行目录",
  restore: "从备份恢复",
};
type Action = keyof typeof actions;
type Job = {
  id: string;
  name: string;
  operation: Action;
  destination: string;
  status: string;
  created: number;
  source_parts?: { directory: string; relative_path: string }[];
  error?: string;
  bytes?: number;
  copied_bytes?: number;
  release_pending?: boolean;
  release_parts?: Record<string, string>;
};
type Catalog = {
  studies: {
    name: string;
    residency: string;
    status: string;
    directories: string[];
  }[];
  jobs: Job[];
};
type Estimate = {
  files: number;
  bytes: number;
  source_allocated_bytes: number;
  source_bytes_on_other_volumes: number;
  available_bytes: number;
  online: boolean;
};
const bytes = (n: number) =>
  (n / 1024 ** 3).toLocaleString(undefined, { maximumFractionDigits: 3 }) +
  " GiB";
const states: Record<string, string> = {
  ready: "等待执行",
  running: "正在传输",
  paused: "已暂停",
  complete: "已完成",
  released: "旧副本已释放",
  cancelled: "已取消",
};

function post<T>(path: string, body: unknown) {
  return api<T>(base + path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "X-ThreeMind-Request-ID": crypto.randomUUID() },
  });
}

export default function ExperimentTransfers({
  directories,
  writable,
  reload,
}: {
  directories: Directory[];
  writable: boolean;
  reload: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<Action>("sync");
  const [study, setStudy] = useState("");
  const [destination, setDestination] = useState("");
  const [restoreName, setRestoreName] = useState("");
  const [version, setVersion] = useState("");
  const [discover, setDiscover] = useState("");
  const [legacy, setLegacy] = useState("");
  const [confirm, setConfirm] = useState("");
  const [backupDirectory, setBackupDirectory] = useState("");
  const [backupName, setBackupName] = useState("");
  const [backupID, setBackupID] = useState("");
  const [estimate, setEstimate] = useState<{ key: string; data: Estimate }>();
  const q = useQuery({
    queryKey: ["experiment-transfers"],
    queryFn: () => api<Catalog>(base),
    enabled: open,
    refetchInterval: (q) =>
      q.state.data?.jobs?.some(
        (j) => ["ready", "running"].includes(j.status) || j.release_pending,
      )
        ? 2500
        : false,
  });
  const historical = useQuery({
    queryKey: ["historical-experiments", discover],
    queryFn: () =>
      api<{ names: string[] }>(
        base + "/discover?directory=" + encodeURIComponent(discover),
      ),
    enabled: open && !!discover,
  });
  const studies = q.data?.studies ?? [],
    jobs = q.data?.jobs ?? [];
  const backups = jobs.filter(
    (j) => j.operation === "backup" && j.status === "complete",
  );
  const names =
    action === "restore"
      ? Array.from(new Set(backups.map((j) => j.name)))
      : studies
          .filter((s) =>
            action === "unarchive"
              ? s.residency === "archived"
              : !["archive", "migrate"].includes(action) ||
                (s.residency === "active" && s.status === "complete"),
          )
          .map((s) => s.name);
  const sourceIds = studies.find((s) => s.name === study)?.directories ?? [];
  const sources = directories.filter((d) => sourceIds.includes(d.id));
  const separateDisk = (d: Directory) =>
    !!d.physical_disks?.length &&
    !!sources.length &&
    sources.length === sourceIds.length &&
    sources.every(
      (s) =>
        !!s.physical_disks?.length &&
        !s.physical_disks.some((id) => d.physical_disks!.includes(id)),
    );
  const eligible = directories.filter((d) => {
    if (!d.enabled || !d.online) return false;
    const role = d.role ?? "run";
    if (action === "archive") return role === "archive";
    if (action === "backup") return role !== "run";
    if (action === "sync") return true;
    return (
      role === "run" &&
      !(action === "migrate" && sourceIds.length === 1 && sourceIds[0] === d.id)
    );
  });
  if (action === "archive")
    eligible.sort(
      (a, b) =>
        Number(separateDisk(b)) - Number(separateDisk(a)) ||
        a.priority - b.priority,
    );
  const recommendation =
    action === "archive" ? eligible.find(separateDisk) : undefined;
  const selected = destination
    ? eligible.find((d) => d.id === destination)
    : recommendation;
  const body = {
    operation: action,
    name: study,
    destination: selected?.id ?? "",
    backup: action === "restore" ? version : null,
    restore_as: action === "restore" ? restoreName : null,
  };
  const key = JSON.stringify(body);
  const valid =
    names.includes(study) &&
    !!selected &&
    (action !== "restore" ||
      (!!restoreName &&
        backups.some((j) => j.id === version && j.name === study)));
  const change = useMutation({
    mutationFn: ({ path, payload }: { path: string; payload: unknown }) =>
      post(path, payload),
    onSuccess: () => {
      setConfirm("");
      setEstimate(undefined);
      q.refetch();
      reload();
      if (discover) historical.refetch();
    },
  });
  const preview = useMutation({
    mutationFn: async () => ({
      key,
      data: await post<Estimate>("/preview", body),
    }),
    onSuccess: setEstimate,
  });
  const write = (path: string, payload: unknown = {}) =>
    change.mutate({ path, payload });
  return (
    <details
      className="data-evidence"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>{t("实验同步、迁移与归档")}</summary>
      {open && (
        <>
          <details>
            <summary>{t("登记已完成的历史实验")}</summary>
            <Field label={t("运行目录")}>
              <select
                value={discover}
                onChange={(e) => {
                  setDiscover(e.target.value);
                  setLegacy("");
                }}
              >
                <option value="">{t("选择目录")}</option>
                {directories
                  .filter((d) => (d.role ?? "run") === "run" && d.online)
                  .map((d) => (
                    <option key={d.id}>{d.id}</option>
                  ))}
              </select>
            </Field>
            <Field label={t("历史实验")}>
              <select
                value={legacy}
                onChange={(e) => setLegacy(e.target.value)}
              >
                <option value="">{t("选择实验")}</option>
                {historical.data?.names.map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </Field>
            <Button
              disabled={!writable || !legacy || change.isPending}
              onClick={() =>
                write("/adopt", { name: legacy, directory: discover })
              }
            >
              {t("将此实验登记为已完成")}
            </Button>
            <ErrorBox error={historical.error} />
          </details>
          <div className="data-form-grid">
            <Field label={t("操作")}>
              <select
                value={action}
                onChange={(e) => {
                  setAction(e.target.value as Action);
                  setDestination("");
                }}
              >
                {Object.entries(actions).map(([k, v]) => (
                  <option key={k} value={k}>
                    {t(v)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("实验名称")}>
              <select
                value={study}
                onChange={(e) => {
                  setStudy(e.target.value);
                  setVersion("");
                  setDestination("");
                }}
              >
                <option value="">{t("选择实验")}</option>
                {names.map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </Field>
            <Field label={t("目标目录")}>
              <select
                value={selected?.id ?? ""}
                onChange={(e) => setDestination(e.target.value)}
              >
                <option value="">{t("选择目录")}</option>
                {eligible.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.id} · {d.path}
                    {d.id === recommendation?.id
                      ? " · " + t("推荐：其他物理磁盘")
                      : ""}
                  </option>
                ))}
              </select>
            </Field>
            {action === "archive" &&
              selected?.volume &&
              sources.length > 0 &&
              (sources.every((s) => s.volume === selected.volume) ? (
                <p>
                  {t(
                    "归档目录与源数据在同一卷。要给这个卷腾空间，可以选择另一块盘。",
                  )}
                </p>
              ) : sources.some((s) => s.volume === selected.volume) ? (
                <p>
                  {t(
                    "部分实验数据与目标目录在同一卷。预览可查看其他源卷上的数据占用。",
                  )}
                </p>
              ) : null)}
            {action === "restore" && (
              <>
                <Field label={t("备份版本")}>
                  <select
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                  >
                    <option value="">{t("选择备份版本")}</option>
                    {backups
                      .filter((j) => j.name === study)
                      .map((j) => (
                        <option key={j.id} value={j.id}>
                          {new Date(j.created * 1000).toLocaleString()} · {j.id}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label={t("恢复后的新实验名称")}>
                  <input
                    value={restoreName}
                    onChange={(e) => setRestoreName(e.target.value)}
                  />
                </Field>
              </>
            )}
          </div>
          <div className="data-actions">
            <Button
              disabled={!valid || preview.isPending}
              onClick={() => preview.mutate()}
            >
              {t("预览传输")}
            </Button>
            <Button
              disabled={
                !writable || !valid || estimate?.key !== key || change.isPending
              }
              onClick={() => write("/jobs", body)}
            >
              {t("开始传输")}
            </Button>
          </div>
          {estimate?.key === key && (
            <p>
              {t("文件数")} {estimate.data.files} · {t("源数据")}{" "}
              {bytes(estimate.data.bytes)} · {t("目标可用空间")}{" "}
              {bytes(estimate.data.available_bytes)}
              {action === "archive" &&
                estimate.data.source_bytes_on_other_volumes != null && (
                  <>
                    {" "}
                    · {t("其他源卷上的占用")}{" "}
                    {bytes(estimate.data.source_bytes_on_other_volumes)}
                  </>
                )}
              {estimate.data.source_allocated_bytes != null && (
                <>
                  {" "}
                  · {t("源盘实际占用")}{" "}
                  {bytes(estimate.data.source_allocated_bytes)}
                </>
              )}
            </p>
          )}
          {studies
            .filter((s) => s.residency === "archived")
            .map((s) => (
              <p key={s.name}>
                {s.name} · {t("已归档")} ·{" "}
                {s.directories
                  .map(
                    (id) =>
                      id +
                      (directories.find((d) => d.id === id)?.online
                        ? ""
                        : " (" + t("磁盘离线") + ")"),
                  )
                  .join(", ")}
              </p>
            ))}
          <Button
            onClick={() => {
              q.refetch();
              reload();
            }}
          >
            {t("刷新传输记录")}
          </Button>
          {[...jobs].reverse().map((j) => (
            <div key={j.id} className="data-evidence">
              <strong>
                {j.name} · {t(actions[j.operation])} → {j.destination}
              </strong>{" "}
              {t(states[j.status] ?? j.status)}
              <small> · {j.id}</small>
              {j.error && <p role="alert">{j.error}</p>}
              {["ready", "running", "paused"].includes(j.status) && (
                <>
                  <Button
                    disabled={!writable || change.isPending}
                    onClick={() => write("/jobs/" + j.id + "/resume")}
                  >
                    {t("继续传输")}
                  </Button>
                  <Button
                    disabled={
                      !writable || change.isPending || j.status === "running"
                    }
                    onClick={() => write("/jobs/" + j.id + "/cancel")}
                  >
                    {t("取消传输")}
                  </Button>
                </>
              )}
              {j.status === "complete" &&
                ["archive", "unarchive", "migrate"].includes(j.operation) &&
                (confirm === j.id ? (
                  <>
                    <p>
                      {t("将重新校验当前副本，然后删除该次迁移留下的旧副本。")}
                    </p>
                    {j.source_parts?.map((p) => (
                      <div key={p.directory + "/" + p.relative_path}>
                        <code>
                          {directories.find((d) => d.id === p.directory)
                            ?.path ?? p.directory}
                          /{p.relative_path}
                        </code>
                      </div>
                    ))}
                    <Button
                      disabled={!writable || change.isPending}
                      onClick={() => write("/jobs/" + j.id + "/release")}
                    >
                      {t("确认释放旧副本")}
                    </Button>
                    <Button onClick={() => setConfirm("")}>
                      {t("保留旧副本")}
                    </Button>
                  </>
                ) : (
                  <Button
                    disabled={
                      !writable || change.isPending || j.release_pending
                    }
                    onClick={() => setConfirm(j.id)}
                  >
                    {t("释放旧副本")}
                  </Button>
                ))}
            </div>
          ))}
          <details>
            <summary>{t("从磁盘登记已有备份")}</summary>
            <Field label={t("备份目录")}>
              <select
                value={backupDirectory}
                onChange={(e) => setBackupDirectory(e.target.value)}
              >
                <option value="">{t("选择目录")}</option>
                {directories
                  .filter((d) => d.online)
                  .map((d) => (
                    <option key={d.id}>{d.id}</option>
                  ))}
              </select>
            </Field>
            <Field label={t("原实验名称")}>
              <input
                value={backupName}
                onChange={(e) => setBackupName(e.target.value)}
              />
            </Field>
            <Field label={t("备份版本编号")}>
              <input
                value={backupID}
                onChange={(e) => setBackupID(e.target.value)}
              />
            </Field>
            <Button
              disabled={
                !writable ||
                change.isPending ||
                !backupDirectory ||
                !backupName ||
                !backupID
              }
              onClick={() =>
                write("/import-backup", {
                  directory: backupDirectory,
                  name: backupName,
                  backup: backupID,
                })
              }
            >
              {t("登记备份版本")}
            </Button>
          </details>
          <ErrorBox error={q.error ?? preview.error ?? change.error} />
        </>
      )}
    </details>
  );
}
