import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, post } from "./api";
import { useAccess } from "./access";
import { Button, Empty, ErrorBox, Loading } from "./ui";
import { t, dateLabel } from "./i18n";
export default function HostMaintenance() {
  const allowed = useAccess(),
    client = useQueryClient();
  const data = useQuery({
    queryKey: ["admin-host"],
    queryFn: () => api("/admin"),
    enabled: allowed("system.read"),
  });
  const change = useMutation({
    mutationFn: (worker: any) =>
      post(
        `/admin/workers/${encodeURIComponent(worker.id)}/enabled?enabled=${!worker.enabled}`,
        {},
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["admin-host"] }),
  });
  return (
    <>
      <section className="panel">
        <h2>{t("执行节点")}</h2>
        <p>{t("停止领取新任务不终止已有租约，也不改变意识动力学。")}</p>
        <ErrorBox error={data.error || change.error} />
        {data.isPending ? (
          <Loading />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Worker</th>
                  <th>{t("最近心跳")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {(data.data?.workers || []).map((worker: any) => (
                  <tr key={worker.id}>
                    <td>{worker.name}</td>
                    <td>
                      {worker.heartbeat ? dateLabel(worker.heartbeat) : "—"}
                    </td>
                    <td>{worker.enabled ? t("启用") : t("停用")}</td>
                    <td>
                      <Button
                        disabled={!allowed("system.write") || change.isPending}
                        onClick={() => change.mutate(worker)}
                      >
                        {worker.enabled ? t("停止领取新任务") : t("启用")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data.data && !data.data.workers?.length && (
          <Empty
            title={t("尚无执行节点")}
            detail={t(
              "工作站启动器会自动启动本地 worker，也可以单独启动执行进程。",
            )}
          />
        )}
      </section>
      <section className="panel">
        <h2>{t("关键操作审计")}</h2>
        <div className="event-list">
          {(data.data?.audit || []).map((entry: any) => (
            <div className="event-row" key={entry.id}>
              <span>{dateLabel(entry.occurred_at)}</span>
              <strong>{entry.action}</strong>
              <code>{entry.resource}</code>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
