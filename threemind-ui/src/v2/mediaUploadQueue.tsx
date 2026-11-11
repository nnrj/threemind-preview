import { t, locale } from "./i18n";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { MediaUpload } from "./mediaTransfer";
import { Button, Empty, ErrorBox, Loading, useWorkspace } from "./ui";

export const uploadStages: Record<string, string> = {
  uploading: "传输中／等待续传",
  verifying: "校验已存分块",
  processing: "服务器处理中",
  hashing: "校验完整原件",
  decoding: "解码与感官转换",
  admitting: "校验输入预算并提交",
  accepted: "已进入输入账本",
  failed: "处理失败，可重试",
  cancel_requested: "正在取消",
  cancelling: "正在取消",
  cancelled: "已取消",
  expired: "暂存已过期",
};
export const mediaSize = (value: string | number) => {
  const bytes = Number(value),
    unit = bytes >= 1024 ** 2 ? "MiB" : bytes >= 1024 ? "KiB" : "字节";
  return `${(bytes / (unit === "MiB" ? 1024 ** 2 : unit === "KiB" ? 1024 : 1)).toLocaleString(locale(), { maximumFractionDigits: 2 })} ${unit}`;
};

export default function MediaUploadQueue({
  base,
  busy,
  eligible,
  onResume,
}: {
  base: string;
  busy: boolean;
  eligible: boolean;
  onResume: (row: MediaUpload) => void;
}) {
  const client = useQueryClient();
  const { project } = useWorkspace();
  const [pages, setPages] = useState<string[]>([""]),
    [all, setAll] = useState(false);
  const uploads = useQuery<{
    rows: MediaUpload[];
    next: string | null;
    limits: any;
  }>({
    queryKey: ["media-uploads", base, pages.at(-1), all],
    queryFn: () =>
      api(
        `${base}/media-uploads?state=${all ? "all" : "unfinished"}${pages.at(-1) ? `&before=${pages.at(-1)}` : ""}`,
      ),
    refetchInterval: (q) =>
      busy ||
      q.state.data?.rows.some((r) =>
        ["processing", "cancel_requested"].includes(r.status),
      )
        ? 2000
        : false,
  });
  const cancel = useMutation({
    mutationFn: (id: string) =>
      api(`${base}/media-uploads/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["media-uploads", base] });
      client.invalidateQueries({ queryKey: ["media-upload-status", base] });
    },
  });
  return (
    <section
      className="media-upload-queue"
      role="region"
      aria-label={t("媒体传输与暂存")}
    >
      <div className="panel-heading">
        <div>
          <h3>{t("媒体传输与暂存")}</h3>
          <p>
            {t(
              "分块保留 24 小时，可重新选择原文件继续。处理失败的原件可重试或取消。",
            )}
          </p>
        </div>
        <Button onClick={() => uploads.refetch()}>{t("刷新上传记录")}</Button>
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={all}
          onChange={(e) => {
            setAll(e.target.checked);
            setPages([""]);
          }}
        />
        {t("显示已完成与已取消")}
      </label>
      <ErrorBox error={uploads.error ?? cancel.error} />
      {uploads.isPending ? (
        <Loading />
      ) : !uploads.data?.rows.length ? (
        <Empty
          title={t("没有待处理的媒体上传")}
          detail={t("已接收原件和逐帧证据仍在输入记录中。")}
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("原件")}</th>
                <th>{t("传输／处理")}</th>
                <th>{t("暂存期限")}</th>
                <th>{t("操作")}</th>
              </tr>
            </thead>
            <tbody>
              {uploads.data.rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.metadata.filename}
                    <small>
                      {mediaSize(r.byte_length)} ·{" "}
                      {r.metadata.kind === "audio"
                        ? t("声音")
                        : r.metadata.kind === "image"
                          ? t("图片")
                          : t("视频")}
                    </small>
                  </td>
                  <td>
                    {t(uploadStages[r.stage] ?? uploadStages[r.status])}
                    <small>
                      {mediaSize(r.received_bytes)} / {mediaSize(r.byte_length)}
                    </small>
                    {r.status === "processing" && (
                      <small>
                        {t("已形成 ")}
                        {r.progress_frames}
                        {t(" 个感官帧")}
                      </small>
                    )}
                    {r.error && <small className="error-text">{r.error}</small>}
                  </td>
                  <td>
                    {["accepted", "cancelled", "expired"].includes(r.status)
                      ? t("暂存分块已清理")
                      : new Date(r.expires_at).toLocaleString(locale(), {
                          hour12: false,
                        })}
                  </td>
                  <td>
                    <div className="button-row">
                      {["uploading", "failed", "processing"].includes(
                        r.status,
                      ) && (
                        <Button
                          disabled={busy || !eligible}
                          onClick={() => onResume(r)}
                        >
                          {t("继续／重试")}
                        </Button>
                      )}
                      {[
                        "uploading",
                        "failed",
                        "processing",
                        "cancel_requested",
                      ].includes(r.status) && (
                        <Button
                          disabled={
                            cancel.isPending || project?.role === "viewer"
                          }
                          onClick={() => cancel.mutate(r.id)}
                        >
                          {t("取消暂存")}
                        </Button>
                      )}
                      {r.status === "accepted" && (
                        <a
                          className="text-link"
                          href={`/api/v2${base}/media/${r.id}/original`}
                        >
                          {t("下载原件")}
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pager">
        <Button
          disabled={pages.length === 1}
          onClick={() => setPages((p) => p.slice(0, -1))}
        >
          {t("上一页")}
        </Button>
        <span>{t("第 {page} 页", { page: pages.length })}</span>
        <Button
          disabled={!uploads.data?.next}
          onClick={() => setPages((p) => [...p, uploads.data!.next!])}
        >
          {t("下一页")}
        </Button>
      </div>
      {uploads.data && (
        <p className="footnote">
          {t("每块 1 MiB；每个项目最多 ")}
          {uploads.data.limits.project_active_uploads}{" "}
          {t("个未完成上传，暂存预约总额")}{" "}
          {mediaSize(uploads.data.limits.project_staged_bytes)}
          {t(
            "。解码按感官与输入总线预算整条校验；取消不会删除已接收的研究证据。",
          )}
        </p>
      )}
      <Link
        className="text-link"
        to="/docs?doc=docs%2Fzh%2Fv2-media-uploads.md"
      >
        {t("续传、校验、取消与接收边界")}
      </Link>
    </section>
  );
}
