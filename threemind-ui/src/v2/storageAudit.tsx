import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "./api";
import { Button, ErrorBox, useWorkspace } from "./ui";
import { t } from "./i18n";
import "./probeCalibration.css";

const bytes = (v: number) => `${(v / 1024 ** 2).toFixed(2)} MiB`;
export default function StorageAudit() {
  const { project } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const audit = useMutation({
    mutationFn: (start: number) =>
      api<any>(`/projects/${project!.id}/storage-audit?offset=${start}`),
    onSuccess: (_, start) => setOffset(start),
  });
  const data = audit.data;
  const labels: Record<string, string> = {
    keep: t("建议保留"),
    risk: t("清理有风险"),
    candidate: t("空记录清理候选"),
  };
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `storage-audit-${project!.id}-${offset}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <section className="panel settings-panel storage-audit">
      <h2>{t("实验存储检查")}</h2>
      <p>
        {t(
          "只读扫描当前项目的记录和引用元数据，不展开大模型、媒体或笔记正文，也不删除任何数据。",
        )}
      </p>
      <Button
        variant="primary"
        disabled={!project || audit.isPending}
        onClick={() => audit.mutate(0)}
      >
        {audit.isPending ? t("正在检查") : t("扫描当前项目")}
      </Button>
      <ErrorBox error={audit.error} />
      {data && (
        <>
          <p>
            {t("检查时间")}: {data.checked_at} · {data.totals.runs}{" "}
            {t("个意识")}
          </p>
          <p>
            {t("恢复点与证据载荷")}: {bytes(data.stored_payload_bytes)} ·{" "}
            {t("网络查询投影预算估计")}:{" "}
            {bytes(data.network_projection_estimate_bytes)}
          </p>
          {data.database_physical_bytes != null && (
            <p>
              {t("整个数据库物理大小（所有项目）")}:{" "}
              {bytes(data.database_physical_bytes)}
            </p>
          )}
          {data.bundle_uploads && (
            <p>
              {t("实验包上传载荷")}: {bytes(data.bundle_uploads.stored_bytes)} ·{" "}
              {t("上传记录需结合实验包引用人工核对；此处不执行删除。")}
            </p>
          )}
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {["意识", "建议", "依据", "恢复点载荷"].map((x) => (
                    <th key={x}>{t(x)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r: any) => (
                  <tr key={r.id}>
                    <td>
                      <Link to={`/runs/${r.id}`}>{r.name}</Link>
                      <br />
                      <small>{r.id}</small>
                    </td>
                    <td>{labels[r.classification]}</td>
                    <td>
                      {r.reasons.map((s: string) => (
                        <p key={s}>{t(s)}</p>
                      ))}
                    </td>
                    <td>{bytes(r.metadata.checkpoints?.bytes ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="form-actions">
            <Button
              disabled={offset === 0 || audit.isPending}
              onClick={() => audit.mutate(Math.max(0, offset - 50))}
            >
              {t("上一页")}
            </Button>
            {Math.floor(offset / 50) + 1}
            <Button
              disabled={!data.more || audit.isPending}
              onClick={() => audit.mutate(offset + 50)}
            >
              {t("下一页")}
            </Button>
            <Button onClick={download}>{t("下载本页检查结果")}</Button>
          </div>
          {data.limitations.map((s: string) => (
            <p className="muted" key={s}>
              {t(s)}
            </p>
          ))}
          <p>
            {t(
              "空记录候选也需要在模型档案中检查完整清理预览，由你决定是否清理。此页面没有删除操作。",
            )}
          </p>
        </>
      )}
    </section>
  );
}
