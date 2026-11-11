import { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, post, projectPath } from "./api";
import { Button, ErrorBox, Loading, Modal, useWorkspace } from "./ui";
import { can } from "./access";
import { t } from "./i18n";

type Running = {
  id: string;
  name: string;
  project_id: string;
  project_name?: string;
  status: string;
  can_pause: boolean;
  reason?: string;
  pause_payload?: { kind: string; payload?: unknown };
};

export default function LogoutDialog({
  close,
  logout,
}: {
  close: () => void;
  logout: () => Promise<void>;
}) {
  const { user } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const [previous, setPrevious] = useState<Running[]>([]);
  const [selected, setSelected] = useState<Record<string, Running>>({});
  const [paused, setPaused] = useState<string[]>([]);
  const accepted = useRef(new Set<string>());
  const [acceptedIds, setAcceptedIds] = useState<string[]>([]);
  const running = useQuery<{ items: Running[]; next: number | null }>({
    queryKey: ["logout-running", offset],
    queryFn: () => api(`/session/running-instances?limit=200&offset=${offset}`),
    retry: false,
  });
  const rows = [...previous, ...(running.data?.items || [])].filter(
    (row, index, list) =>
      list.findIndex((other) => other.id === row.id) === index,
  );
  const remaining = Object.values(selected).filter(
    (row) => !paused.includes(row.id),
  );
  const finish = useMutation({
    mutationFn: async () => {
      for (const row of remaining) {
        const base = `${projectPath(row.project_id)}/runs/${encodeURIComponent(row.id)}`;
        if (!accepted.current.has(row.id)) {
          await post(
            `${base}/commands`,
            row.pause_payload ?? { kind: "pause", payload: {} },
          );
          accepted.current.add(row.id);
          setAcceptedIds((old) => [...old, row.id]);
        }
        // Acceptance is not completion: keep the session until the causal boundary
        // has actually paused this independently controlled instance.
        let settled = false;
        for (let attempt = 0; attempt < 30; attempt++) {
          const state = await api<{ status: string }>(base);
          if (
            ["paused", "completed", "cancelled", "dead", "failed"].includes(
              state.status,
            )
          ) {
            settled = true;
            break;
          }
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
        if (!settled)
          throw new Error(
            t(
              "实例 {name} 尚未确认暂停，账号保持登录。请查看实例状态后重试。",
              { name: row.name },
            ),
          );
        setPaused((old) => [...old, row.id]);
      }
      await logout();
    },
  });
  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open && !finish.isPending) close();
      }}
      title={t("退出登录")}
      description={t(
        "默认退出后意识继续运行。账号过期、断网或关闭页面也不会自动暂停；只有明确选中的实例才会请求暂停。",
      )}
    >
      <h3>{t("可选：暂停这些实例后退出")}</h3>
      {running.isPending ? (
        <Loading />
      ) : rows.length ? (
        <div className="logout-instances">
          {rows.map((row) => (
            <label key={row.id} className="logout-instance">
              <input
                type="checkbox"
                checked={!!selected[row.id]}
                disabled={
                  finish.isPending ||
                  paused.includes(row.id) ||
                  acceptedIds.includes(row.id) ||
                  !row.can_pause ||
                  !can(user, "runs.pause")
                }
                onChange={(event) =>
                  setSelected((old) => {
                    const next = { ...old };
                    if (event.target.checked) next[row.id] = row;
                    else delete next[row.id];
                    return next;
                  })
                }
              />
              <span>
                <strong>{row.name}</strong>
                <small>
                  {paused.includes(row.id)
                    ? t("已确认暂停")
                    : acceptedIds.includes(row.id)
                      ? t("暂停已提交，等待确认")
                      : !row.can_pause
                        ? row.reason === "no-pause-permission"
                          ? t("没有此实例的暂停权限。")
                          : t("此实例由实验管理，不能独立暂停。")
                        : row.project_name || row.project_id}
                </small>
              </span>
            </label>
          ))}
        </div>
      ) : (
        <p>{t("没有正在运行且可访问的实例。")}</p>
      )}
      {running.data?.next && (
        <Button
          type="button"
          disabled={finish.isPending}
          onClick={() => {
            setPrevious(rows);
            setOffset(running.data!.next!);
          }}
        >
          {t("查看更多实例")}
        </Button>
      )}
      <ErrorBox error={running.error} />
      <ErrorBox error={finish.error} />
      {acceptedIds.some((identity) => !paused.includes(identity)) && (
        <p className="notice">
          {t(
            "已受理的暂停不会撤销；重试只查询这些实例的暂停结果，不重复发送命令。",
          )}
        </p>
      )}
      {finish.isPending && (
        <p role="status">{t("正在确认所选实例已暂停，请保持此窗口。")}</p>
      )}
      <div className="form-actions">
        <Button type="button" disabled={finish.isPending} onClick={close}>
          {acceptedIds.some((identity) => !paused.includes(identity))
            ? t("关闭（已提交的暂停仍有效）")
            : t("取消")}
        </Button>
        <Button
          variant="primary"
          disabled={finish.isPending}
          onClick={() => finish.mutate()}
        >
          {remaining.length
            ? t("暂停 {count} 个实例后退出", { count: remaining.length })
            : t("退出，意识继续运行")}
        </Button>
      </div>
    </Modal>
  );
}
