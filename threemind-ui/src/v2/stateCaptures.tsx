import { t } from "./i18n";
import { useRef, useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bookmark, RefreshCw } from "lucide-react";
import { api, post, timeLabel, type Run } from "./api";
import { Button, Field, Modal, ErrorBox, useWorkspace } from "./ui";
import { usePreferences, updatePreferences } from "./preferences";

export function CapturePreferences() {
  const p = usePreferences();
  return (
    <>
      <label className="check">
        <input
          type="checkbox"
          checked={p.promptCaptureName}
          onChange={(e) =>
            updatePreferences({ promptCaptureName: e.target.checked })
          }
        />
        {t("捕获状态前询问名称")}
      </label>
      <Field
        label={t("自动命名方式")}
        hint={t(
          "以服务端实际保存的修订号为准。时间为恢复点的 UTC 创建时间；名称过长时仅缩短意识名称前缀。",
        )}
      >
        <select
          aria-label={t("自动命名方式")}
          value={p.captureNameStyle}
          onChange={(e) =>
            updatePreferences({
              captureNameStyle: e.target.value as "revision" | "timestamp",
            })
          }
        >
          <option value="timestamp">{t("意识名称 · 修订号 · UTC 时间")}</option>
          <option value="revision">{t("意识名称 · 修订号")}</option>
        </select>
      </Field>
      <p className="footnote">
        {t(
          "偏好仅保存在当前设备。自动检查点不会弹窗或批量命名，科学参数与模型状态不受命名影响。",
        )}
      </p>
    </>
  );
}

type RequestBody = {
  request_id: string;
  label: string;
  auto_name: "revision" | "timestamp";
  pinned: boolean;
};
type Receipt = {
  id: string;
  request_id: string;
  ordinal: number;
  status: string;
  error: string | null;
  checkpoint_id: string | null;
  parameters: RequestBody;
  result: {
    label?: string;
    revision?: number;
    time_us?: string;
    state_hash?: string;
  };
};

export default function StateCaptures({
  base,
  run,
  onFork,
}: {
  base: string;
  run: Run;
  onFork: (id: string) => void;
}) {
  const { project } = useWorkspace(),
    p = usePreferences(),
    client = useQueryClient();
  const [open, setOpen] = useState(false),
    [label, setLabel] = useState(""),
    [pinned, setPinned] = useState(false);
  const [pages, setPages] = useState<(number | null)[]>([null]);
  const request = useRef<RequestBody | null>(null);
  const canWrite = ["owner", "researcher"].includes(project?.role ?? "");
  const active = ["queued", "running"].includes(run.status);
  const before = pages.at(-1);
  const history = useQuery({
    queryKey: ["state-captures", project?.id, run.id, before],
    queryFn: () =>
      api<{ rows: Receipt[]; next: number | null }>(
        `${base}/state-captures?limit=5${before ? `&before=${before}` : ""}`,
      ),
    refetchInterval: (query) =>
      active || query.state.data?.rows.some((row) => row.status === "pending")
        ? 1000
        : false,
    refetchIntervalInBackground: false,
  });
  const mutation = useMutation({
    mutationFn: (body: RequestBody) =>
      post<Receipt>(`${base}/state-captures`, body),
    onSuccess: () => {
      request.current = null;
      setOpen(false);
      setPages([null]);
      client.invalidateQueries({ queryKey: ["state-captures"] });
    },
  });
  const completed = history.data?.rows.find((r) => r.status === "completed");
  const acknowledged = history.data?.rows.find(
    (r) => r.request_id === mutation.variables?.request_id,
  );
  useEffect(() => {
    if (acknowledged && request.current) {
      request.current = null;
      setOpen(false);
      mutation.reset();
    }
  }, [acknowledged?.id]);
  useEffect(() => {
    if (completed)
      for (const key of ["versions", "metadata-history", "run", "checkpoints"])
        client.invalidateQueries({ queryKey: [key] });
  }, [completed?.id, client]);
  function send() {
    const body = request.current ?? {
      request_id: crypto.randomUUID(),
      label,
      auto_name: p.captureNameStyle,
      pinned,
    };
    request.current = body;
    mutation.mutate(body);
  }
  const waiting = history.data?.rows.some((r) => r.status === "pending");
  return (
    <section className="panel state-captures" aria-label={t("状态捕获")}>
      <div className="panel-heading">
        <div>
          <h2>{t("捕获并命名状态")}</h2>
          <p>
            {t(
              "名称、保留标记与实际恢复点同时提交。等待明确回执后再进行下一次捕获。",
            )}
          </p>
        </div>
        <Link
          className="text-link"
          to="/settings?section=display#capture-preferences"
        >
          {t("命名设置")}
        </Link>
      </div>
      <div className="capture-controls">
        <Button
          disabled={!canWrite || !active || !!waiting || mutation.isPending}
          onClick={() => {
            if (request.current) send();
            else if (p.promptCaptureName) {
              setLabel("");
              setPinned(false);
              mutation.reset();
              setOpen(true);
            } else {
              setLabel("");
              setPinned(false);
              request.current = {
                request_id: crypto.randomUUID(),
                label: "",
                auto_name: p.captureNameStyle,
                pinned: false,
              };
              send();
            }
          }}
        >
          <Bookmark size={16} />
          {mutation.error && request.current
            ? t("重试捕获请求")
            : t("捕获最新状态")}
        </Button>
        <button
          className="icon-button"
          aria-label={t("刷新捕获回执")}
          onClick={() => history.refetch()}
        >
          <RefreshCw size={16} />
        </button>
        {!active && (
          <span className="muted">
            {t("已停止的意识可在下方直接编辑已有恢复点名称。")}
          </span>
        )}
      </div>
      <ErrorBox error={history.error} />
      {!open && <ErrorBox error={mutation.error} />}
      {!!history.data?.rows.length && (
        <div className="capture-receipts">
          {history.data.rows.map((row) => (
            <article key={row.id} className={`capture-receipt ${row.status}`}>
              <div>
                <strong>
                  {row.result.label ||
                    row.parameters.label ||
                    t("按实际恢复点自动命名")}
                </strong>
                <p>
                  {row.status === "pending" ? (
                    t("等待因果边界提交")
                  ) : row.status === "failed" ? (
                    row.error
                  ) : (
                    <>
                      {t("已保存 · r")}
                      {row.result.revision} · {timeLabel(row.result.time_us)}
                    </>
                  )}
                </p>
                {row.result.state_hash && (
                  <small className="mono" title={row.result.state_hash}>
                    {row.result.state_hash.slice(0, 20)}…
                  </small>
                )}
              </div>
              {row.checkpoint_id && (
                <div className="capture-links">
                  <Link
                    className="text-link"
                    to={`/data?run=${run.id}&checkpoint=${row.checkpoint_id}`}
                  >
                    {t("查询此状态")}
                  </Link>
                  {canWrite && (
                    <button
                      className="text-link"
                      onClick={() => onFork(row.checkpoint_id!)}
                    >
                      {t("从此状态分支")}
                    </button>
                  )}
                </div>
              )}
            </article>
          ))}
          <div className="pagination">
            <Button
              disabled={pages.length === 1}
              onClick={() => setPages(pages.slice(0, -1))}
            >
              {t("上一页")}
            </Button>
            <span>{t("第 {page} 页", { page: pages.length })}</span>
            <Button
              disabled={!history.data.next}
              onClick={() => setPages([...pages, history.data!.next])}
            >
              {t("下一页")}
            </Button>
          </div>
        </div>
      )}
      <Modal
        open={open}
        onOpenChange={(value) => {
          if (!mutation.isPending) setOpen(value);
        }}
        title={t("命名本次捕获")}
        description={t(
          "留空时按实际保存的修订号自动命名。取消不会提交捕获请求。",
        )}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <Field
            label={t("恢复点名称")}
            hint={t("最多 120 字符；不填写则使用自动命名。")}
          >
            <input
              aria-label={t("恢复点名称")}
              autoFocus
              maxLength={120}
              value={label}
              readOnly={mutation.isPending || !!request.current}
              onChange={(e) => setLabel(e.target.value)}
            />
          </Field>
          <label className="check">
            <input
              type="checkbox"
              checked={pinned}
              disabled={mutation.isPending || !!request.current}
              onChange={(e) => setPinned(e.target.checked)}
            />
            {t("保留此恢复点，阻止整份档案被清理")}
          </label>
          <ErrorBox error={mutation.error} />
          {mutation.error && (
            <p className="footnote">
              {t(
                "可以重试同一请求。回执未知时不会用新编号重复提交；若要改名，先取消并查看捕获记录。",
              )}
            </p>
          )}
          <div className="form-actions">
            <Button
              type="button"
              disabled={mutation.isPending}
              onClick={() => {
                setOpen(false);
                request.current = null;
              }}
            >
              {t("取消")}
            </Button>
            <Button variant="primary" disabled={mutation.isPending}>
              {mutation.error ? t("重试原请求") : t("确认捕获")}
            </Button>
          </div>
        </form>
      </Modal>
    </section>
  );
}
