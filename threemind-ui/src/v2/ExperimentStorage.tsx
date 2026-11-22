import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t } from "./i18n";
import { Button, ErrorBox, Field, Loading } from "./ui";
import ExperimentTransfers from "./ExperimentTransfers";

const GIB = 1024 ** 3;
export type Directory = {
  id: string;
  path: string;
  priority: number;
  limit_bytes: number | null;
  reserve_bytes: number;
  enabled: boolean;
  role?: "run" | "archive" | "backup";
  volume?: string;
  physical_disks?: string[];
  online?: boolean;
  available_bytes?: number;
};
type Study = { name: string; status: string };
type Status = { revision: number; directories: Directory[]; studies: Study[] };
type Part = {
  name: string;
  bytes: number;
  kind: string;
  directory?: string;
  relative_path?: string;
};
type Plan = {
  name: string;
  parts: Part[];
  fits?: boolean;
  split_would_fit?: boolean;
  shortage_single_bytes?: number;
  status?: string;
};
type Manifest = { volumes: { part: string; bytes: number; sha256: string }[] };
const base = "/storage/experiment-pool";
const size = (n: number) =>
  (n / GIB).toLocaleString(undefined, { maximumFractionDigits: 3 }) + " GiB";
function change<T>(url: string, body: unknown, method = "POST") {
  return api<T>(url, {
    method,
    body: JSON.stringify(body),
    headers: { "X-ThreeMind-Request-ID": crypto.randomUUID() },
  });
}

function Directories({
  status,
  reload,
  writable,
}: {
  status: Status;
  reload: () => void;
  writable: boolean;
}) {
  const [dirs, setDirs] = useState(status.directories);
  const modify = (i: number, fields: Partial<Directory>) =>
    setDirs(dirs.map((d, j) => (i === j ? { ...d, ...fields } : d)));
  const save = useMutation({
    mutationFn: () =>
      change(
        base,
        {
          expected_revision: status.revision,
          directories: dirs.map(
            ({
              id,
              path,
              priority,
              limit_bytes,
              reserve_bytes,
              enabled,
              role,
            }) => ({
              id,
              path,
              priority,
              limit_bytes,
              reserve_bytes,
              enabled,
              role: role ?? "run",
            }),
          ),
        },
        "PUT",
      ),
    onSuccess: reload,
  });
  return (
    <fieldset disabled={!writable || save.isPending}>
      <legend>{t("存储目录")}</legend>
      {dirs.map((d, i) => (
        <div className="data-form-grid" key={i}>
          <Field label={t("目录标识")}>
            <input
              value={d.id}
              onChange={(e) => modify(i, { id: e.target.value })}
            />
          </Field>
          <Field label={t("宿主机目录")}>
            <input
              value={d.path}
              onChange={(e) => modify(i, { path: e.target.value })}
            />
          </Field>
          <Field label={t("目录用途")}>
            <select
              value={d.role ?? "run"}
              onChange={(e) =>
                modify(i, { role: e.target.value as Directory["role"] })
              }
            >
              <option value="run">{t("运行目录")}</option>
              <option value="archive">{t("归档目录")}</option>
              <option value="backup">{t("备份目录")}</option>
            </select>
          </Field>
          <Field label={t("优先级（小数值优先）")}>
            <input
              type="number"
              min="0"
              value={d.priority}
              onChange={(e) => modify(i, { priority: Number(e.target.value) })}
            />
          </Field>
          <Field label={t("目录上限（GiB，留空不限）")}>
            <input
              type="number"
              min="0"
              step="any"
              value={d.limit_bytes == null ? "" : d.limit_bytes / GIB}
              onChange={(e) =>
                modify(i, {
                  limit_bytes:
                    e.target.value === ""
                      ? null
                      : Math.round(Number(e.target.value) * GIB),
                })
              }
            />
          </Field>
          <Field label={t("磁盘最低剩余（GiB）")}>
            <input
              type="number"
              min="0"
              step="any"
              value={d.reserve_bytes / GIB}
              onChange={(e) =>
                modify(i, {
                  reserve_bytes: Math.round(Number(e.target.value) * GIB),
                })
              }
            />
          </Field>
          <label>
            <input
              type="checkbox"
              checked={d.enabled}
              onChange={(e) => modify(i, { enabled: e.target.checked })}
            />{" "}
            {t("启用目录")}
          </label>
          {d.online != null && (
            <span>
              {d.online
                ? t("可分配空间") + " " + size(d.available_bytes ?? 0)
                : t("磁盘离线")}
            </span>
          )}
          <Button onClick={() => setDirs(dirs.filter((_, j) => i !== j))}>
            {t("移除此目录")}
          </Button>
        </div>
      ))}
      <div className="data-actions">
        <Button
          onClick={() =>
            setDirs([
              ...dirs,
              {
                id: "",
                path: "",
                priority: dirs.length + 1,
                limit_bytes: null,
                reserve_bytes: 0,
                enabled: true,
              },
            ])
          }
        >
          {t("添加数据目录")}
        </Button>
        <Button
          disabled={dirs.some((d) => !d.id.trim() || !d.path.trim())}
          onClick={() => save.mutate()}
        >
          {t("保存目录设置")}
        </Button>
      </div>
      <ErrorBox error={save.error} />
    </fieldset>
  );
}

function Placement({
  status,
  reload,
  writable,
}: {
  status: Status;
  reload: () => void;
  writable: boolean;
}) {
  const [name, setName] = useState("");
  const [split, setSplit] = useState(false);
  const [parts, setParts] = useState<Part[]>([
    { name: "main", bytes: GIB, kind: "data" },
  ]);
  const body = { name, allow_split: split, parts };
  const key = JSON.stringify(body);
  const [selection, select] = useState("");
  const [member, setMember] = useState("");
  const [readback, setReadback] = useState("");
  const url = base + "/studies/" + encodeURIComponent(selection);
  const saved = useQuery({
    queryKey: ["experiment-placement", selection],
    queryFn: () => api<Plan>(url),
    enabled: !!selection,
  });
  const preview = useMutation({
    mutationFn: async () => ({
      key,
      plan: await change<Plan>(base + "/preview", body),
    }),
  });
  const plan = preview.data?.key === key ? preview.data.plan : null;
  const reserve = useMutation({
    mutationFn: () => change<Plan>(base + "/reserve", body),
    onSuccess: (d) => {
      select(d.name);
      reload();
    },
  });
  const action = useMutation({
    mutationFn: (action: string) =>
      change<Plan | Manifest>(url + "/" + action, {}),
    onSuccess: (_d, action) => {
      if (action === "cancel") select("");
      else saved.refetch();
      reload();
    },
  });
  const extract = useMutation({
    mutationFn: () =>
      change<{ path: string }>(url + "/extract", { member, part: readback }),
  });
  const edit = (i: number, update: Partial<Part>) =>
    setParts(parts.map((p, j) => (j === i ? { ...p, ...update } : p)));
  const table = (p: Plan) => (
    <ul>
      {p.parts.map((v) => (
        <li key={v.name}>
          {v.name} · {size(v.bytes)} · {v.directory} / {v.relative_path}
        </li>
      ))}
    </ul>
  );
  return (
    <>
      <fieldset>
        <legend>{t("实验空间预估")}</legend>
        <Field label={t("实验目录名")}>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        {parts.map((p, i) => (
          <div className="data-form-grid" key={i}>
            <Field label={t("分项名称")}>
              <input
                value={p.name}
                onChange={(e) => edit(i, { name: e.target.value })}
              />
            </Field>
            <Field label={t("用途")}>
              <select
                value={p.kind}
                onChange={(e) => edit(i, { kind: e.target.value })}
              >
                <option value="data">{t("实验数据")}</option>
                <option value="archive">{t("归档分卷")}</option>
                <option value="readback">{t("回读副本")}</option>
              </select>
            </Field>
            <Field label={t("峰值空间（GiB）")}>
              <input
                type="number"
                min="0"
                step="any"
                value={p.bytes / GIB}
                onChange={(e) =>
                  edit(i, { bytes: Math.round(Number(e.target.value) * GIB) })
                }
              />
            </Field>
            <Button
              disabled={parts.length === 1}
              onClick={() => setParts(parts.filter((_, j) => j !== i))}
            >
              {t("删除分项")}
            </Button>
          </div>
        ))}
        <Button
          onClick={() =>
            setParts([...parts, { name: "", kind: "data", bytes: GIB }])
          }
        >
          {t("添加分项")}
        </Button>
        <label>
          <input
            type="checkbox"
            checked={split}
            onChange={(e) => setSplit(e.target.checked)}
          />{" "}
          {t("允许本次实验跨目录存储")}
        </label>
        <div className="data-actions">
          <Button
            disabled={
              !name.trim() ||
              parts.some((p) => !p.name.trim() || p.bytes <= 0) ||
              preview.isPending
            }
            onClick={() => preview.mutate()}
          >
            {t("预估空间")}
          </Button>
          <Button
            disabled={!writable || !plan?.fits || reserve.isPending}
            onClick={() => reserve.mutate()}
          >
            {t("确认预留")}
          </Button>
        </div>
        {plan &&
          (plan.fits ? (
            table(plan)
          ) : (
            <p role="status">
              {t("单个目录还差")} {size(plan.shortage_single_bytes ?? 0)}。
              {plan.split_would_fit
                ? t("允许拆分后可放下全部分项。")
                : t("现有目录无法容纳这份预算。")}
            </p>
          ))}
        <ErrorBox error={preview.error ?? reserve.error} />
      </fieldset>
      {status.studies.length > 0 && (
        <fieldset>
          <legend>{t("已分配的实验")}</legend>
          <select
            aria-label={t("已分配的实验")}
            value={selection}
            onChange={(e) => {
              select(e.target.value);
              action.reset();
              extract.reset();
              setReadback("");
              setMember("");
            }}
          >
            <option value="">—</option>
            {status.studies.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name} · {s.status === "complete" ? t("已完成") : t("已预留")}
              </option>
            ))}
          </select>
          {saved.data && (
            <>
              {table(saved.data)}
              <div className="data-actions">
                {(["archive", "verify", "finish", "cancel"] as const).map(
                  (v, i) => (
                    <Button
                      key={v}
                      disabled={
                        (!writable && v !== "verify") ||
                        action.isPending ||
                        (v !== "verify" && saved.data.status === "complete")
                      }
                      onClick={() => action.mutate(v)}
                    >
                      {
                        [
                          t("生成归档分卷"),
                          t("校验归档分卷"),
                          t("完成并释放预留"),
                          t("取消未使用的预留"),
                        ][i]
                      }
                    </Button>
                  ),
                )}
              </div>
            </>
          )}
          {action.data && "volumes" in action.data && (
            <ul>
              {action.data.volumes.map((v) => (
                <li key={v.part}>
                  <a
                    href={
                      "/api/v2" + url + "/volumes/" + encodeURIComponent(v.part)
                    }
                  >
                    {v.part}
                  </a>{" "}
                  · {size(v.bytes)}
                </li>
              ))}
            </ul>
          )}
          {saved.data?.parts.some((p) => p.kind === "archive") && (
            <div className="data-form-grid">
              <Field label={t("归档内文件路径")}>
                <input
                  value={member}
                  placeholder="world-1/trajectory.json"
                  onChange={(e) => {
                    setMember(e.target.value);
                    extract.reset();
                  }}
                />
              </Field>
              {member && (
                <a
                  href={
                    "/api/v2" +
                    url +
                    "/member?member=" +
                    encodeURIComponent(member)
                  }
                >
                  {t("下载归档中的文件")}
                </a>
              )}
              {saved.data.status === "reserved" &&
                saved.data.parts.some((p) => p.kind === "readback") && (
                  <>
                    <Field label={t("回读目录")}>
                      <select
                        value={readback}
                        onChange={(e) => {
                          setReadback(e.target.value);
                          extract.reset();
                        }}
                      >
                        <option value="">—</option>
                        {saved.data.parts
                          .filter((p) => p.kind === "readback")
                          .map((p) => (
                            <option key={p.name}>{p.name}</option>
                          ))}
                      </select>
                    </Field>
                    <Button
                      disabled={
                        !writable || !member || !readback || extract.isPending
                      }
                      onClick={() => extract.mutate()}
                    >
                      {t("从分卷还原文件")}
                    </Button>
                    {extract.data && <span>{extract.data.path}</span>}
                    <ErrorBox error={extract.error} />
                  </>
                )}
            </div>
          )}
          <ErrorBox error={saved.error ?? action.error} />
        </fieldset>
      )}
    </>
  );
}

export default function ExperimentStorage({ writable }: { writable: boolean }) {
  const [open, setOpen] = useState(false);
  const q = useQuery({
    queryKey: ["experiment-storage"],
    queryFn: () => api<Status>(base),
    enabled: open,
  });
  return (
    <details
      className="data-evidence"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>{t("实验数据目录与多盘分配")}</summary>
      {open &&
        (q.data ? (
          <>
            <p>{t("未配置时使用现有单目录。每项实验默认保存在同一个目录。")}</p>
            <Directories
              key={q.data.revision}
              status={q.data}
              writable={writable}
              reload={() => q.refetch()}
            />
            {q.data.directories.some((d) => (d.role ?? "run") === "run") && (
              <Placement
                status={q.data}
                writable={writable}
                reload={() => q.refetch()}
              />
            )}
            {q.data.directories.length > 0 && (
              <ExperimentTransfers
                directories={q.data.directories}
                writable={writable}
                reload={() => q.refetch()}
              />
            )}
          </>
        ) : q.error ? (
          <ErrorBox error={q.error} />
        ) : (
          <Loading />
        ))}
    </details>
  );
}
