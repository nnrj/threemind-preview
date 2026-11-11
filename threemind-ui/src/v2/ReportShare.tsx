import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, ExternalLink, Share2 } from "lucide-react";
import { api, post } from "./api";
import { dateLabel, messageKeys, t, useLocale } from "./i18n";
import { Button, ErrorBox, Field, Modal, useWorkspace } from "./ui";
import { verifiedHtml } from "./sharedPublication";

const statuses = messageKeys({
  active: "可访问",
  revoked: "已撤销",
  expired: "已过期",
  unavailable: "发布者权限已失效",
});

type Props = {
  base: string;
  document: string;
  revision: number;
  dirty?: boolean;
};

export default function ReportShare(props: Props) {
  const { project } = useWorkspace();
  return project?.role === "owner" ? <ShareControl {...props} /> : null;
}

function ShareControl({
  base,
  document: documentId,
  revision,
  dirty = false,
}: Props) {
  const language = useLocale();
  const [open, setOpen] = useState(false),
    [fixedRevision, setFixedRevision] = useState(revision),
    [includeBundle, setIncludeBundle] = useState(false),
    [days, setDays] = useState("7"),
    [selectedId, setSelectedId] = useState(""),
    [offset, setOffset] = useState(0),
    [exportOffset, setExportOffset] = useState(0),
    [preview, setPreview] = useState<{ html: string; hash: string }>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const exportRetry = useRef<any>(null),
    shareRetry = useRef<any>(null);
  const historyHeading = useRef<HTMLHeadingElement>(null);
  const path = `${base}/research-documents/${documentId}`;
  const exports = useQuery({
    queryKey: ["share-exports", path, exportOffset],
    queryFn: () => api(`${path}/exports?offset=${exportOffset}`),
    enabled: open,
    refetchInterval: open ? 2500 : false,
  });
  const shares = useQuery({
    queryKey: ["document-shares", path, offset],
    queryFn: () => api(`${path}/shares?offset=${offset}`),
    enabled: open,
    refetchInterval: open ? 5000 : false,
  });
  const candidates = (exports.data?.rows ?? []).filter(
    (row: any) =>
      row.revision === fixedRevision &&
      row.options.format === "html" &&
      (!includeBundle || row.options.include_data),
  );
  const selected = candidates.find((row: any) => row.id === selectedId);
  const artifactId =
    selected?.status === "done" ? selected.result.artifact_id : undefined;
  const artifactHash = selected?.result?.sha256;
  useEffect(() => {
    setPreview(undefined);
    if (!open || !artifactId || !artifactHash) return;
    const controller = new AbortController();
    void verifiedHtml(
      `/api/v2${base}/artifacts/${artifactId}`,
      artifactHash,
      controller.signal,
      "same-origin",
    )
      .then((html) => {
        if (!controller.signal.aborted)
          setPreview({ html, hash: artifactHash });
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e);
      });
    return () => controller.abort();
  }, [open, base, artifactId, artifactHash]);

  function openDialog(value: boolean) {
    if (busy) return;
    setOpen(value);
    if (value) {
      setFixedRevision(revision);
      setSelectedId("");
      setPreview(undefined);
      setError(undefined);
      setNotice("");
      setOffset(0);
      setExportOffset(0);
    }
  }
  async function prepare() {
    setBusy(true);
    setError(undefined);
    setNotice("");
    const options = {
      revision: fixedRevision,
      format: "html",
      language,
      include_data: includeBundle,
    };
    const fingerprint = JSON.stringify(options);
    if (exportRetry.current?.fingerprint !== fingerprint)
      exportRetry.current = {
        fingerprint,
        body: { ...options, operation_id: crypto.randomUUID() },
      };
    try {
      const row = await post(`${path}/exports`, exportRetry.current.body);
      exportRetry.current = null;
      setSelectedId(row.id);
      setExportOffset(0);
      await exports.refetch();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function publish() {
    if (
      !preview ||
      preview.hash !== artifactHash ||
      !selected ||
      selected.status !== "done"
    )
      return;
    setBusy(true);
    setError(undefined);
    setNotice("");
    const options = {
      export_id: selected.id,
      expected_body_hash: preview.hash,
      expires_days: days === "none" ? null : Number(days),
      include_bundle: includeBundle,
    };
    const fingerprint = JSON.stringify(options);
    if (shareRetry.current?.fingerprint !== fingerprint)
      shareRetry.current = {
        fingerprint,
        body: { ...options, operation_id: crypto.randomUUID() },
      };
    try {
      await post(`${path}/shares`, shareRetry.current.body);
      shareRetry.current = null;
      setOffset(0);
      await shares.refetch();
      setNotice(t("分享链接已创建，可在下方复制或撤销。"));
      historyHeading.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id: string) {
    setBusy(true);
    setError(undefined);
    try {
      await post(`${path}/shares/${id}/revoke`, {});
      await shares.refetch();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice(t("分享链接已复制。"));
    } catch {
      setNotice(t("请在链接输入框中手动复制。"));
    }
  }
  return (
    <>
      <Button disabled={!revision} onClick={() => openDialog(true)}>
        <Share2 size={15} />
        {t("分享")}
      </Button>
      <Modal
        open={open}
        onOpenChange={openDialog}
        title={t("分享固定版本")}
        wide
      >
        <p>
          {t(
            "当前选择修订 {revision}。先预览文件，再创建可供他人访问的链接。",
            { revision: fixedRevision },
          )}
        </p>
        <p className="hint">
          {t(
            "链接指向当前部署；本地工作站不会因此上传到云端。任何获得链接的人均可阅读和下载所选内容。",
          )}
        </p>
        {dirty && (
          <p role="status" className="hint">
            {t("当前有未保存修改。请先保存，再生成包含这些修改的导出。")}
          </p>
        )}
        {revision !== fixedRevision && (
          <p className="hint">
            {t(
              "文档已有新修订；此窗口仍处理打开时选中的版本。重新打开可选择新版本。",
            )}
          </p>
        )}
        <label className="check">
          <input
            type="checkbox"
            checked={includeBundle}
            disabled={busy}
            onChange={(e) => {
              setIncludeBundle(e.target.checked);
              setSelectedId("");
              setPreview(undefined);
            }}
          />
          {t("同时公开完整证据 ZIP")}
        </label>
        {includeBundle && (
          <p className="hint">
            {t(
              "证据 ZIP 包含全部固定来源数据、完整协议与重放内容、文档 JSON 和图表；请确认这些材料都适合公开。",
            )}
          </p>
        )}
        <div className="report-inline">
          <Button disabled={busy || dirty} onClick={() => void prepare()}>
            {t("生成分享预览")}
          </Button>
          <Field label={t("或选择已生成的 HTML 文件")}>
            <select
              disabled={busy}
              value={selectedId}
              onChange={(e) => {
                setSelectedId(e.target.value);
                setError(undefined);
              }}
            >
              <option value="">{t("请选择")}</option>
              {candidates.map((row: any) => (
                <option key={row.id} value={row.id}>
                  {dateLabel(row.created_at)} ·{" "}
                  {row.status === "done"
                    ? t("导出完成")
                    : row.status === "failed"
                      ? t("导出失败")
                      : t("正在导出")}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {(exportOffset > 0 || exports.data?.more) && (
          <div className="report-inline">
            <Button
              disabled={exportOffset === 0 || busy}
              onClick={() => setExportOffset(Math.max(0, exportOffset - 20))}
            >
              {t("上一页")}
            </Button>
            <Button
              disabled={!exports.data?.more || busy}
              onClick={() => setExportOffset(exportOffset + 20)}
            >
              {t("下一页")}
            </Button>
          </div>
        )}
        {selected?.status === "failed" && (
          <ErrorBox error={new Error(selected.error || t("导出失败"))} />
        )}
        {selected &&
          selected.status !== "done" &&
          selected.status !== "failed" && (
            <p role="status">{t("正在生成预览，请稍候…")}</p>
          )}
        {preview && (
          <>
            <p className="publication-hash">
              HTML SHA256 · <code>{preview.hash}</code>
            </p>
            <iframe
              className="publication-frame"
              title={t("分享正文预览")}
              sandbox=""
              referrerPolicy="no-referrer"
              srcDoc={preview.html}
            />
          </>
        )}
        <div className="report-inline">
          <Field label={t("链接有效期")}>
            <select
              value={days}
              disabled={busy}
              onChange={(e) => setDays(e.target.value)}
            >
              <option value="7">{t("7 天")}</option>
              <option value="30">{t("30 天")}</option>
              <option value="365">{t("365 天")}</option>
              <option value="none">{t("直至撤销")}</option>
            </select>
          </Field>
          <Button
            variant="primary"
            disabled={
              busy ||
              dirty ||
              !preview ||
              preview.hash !== artifactHash ||
              selected?.status !== "done"
            }
            onClick={() => void publish()}
          >
            {t("创建分享链接")}
          </Button>
        </div>
        <ErrorBox error={error || exports.error || shares.error} />
        {notice && <p role="status">{notice}</p>}
        <h3 ref={historyHeading}>{t("已创建的分享")}</h3>
        <p className="hint">
          {t(
            "撤销后链接无法再次访问；他人已经下载的文件无法收回。发布者停用或失去项目所有者权限时，链接也会停止提供内容。",
          )}
        </p>
        <div className="publication-list">
          {(shares.data?.rows ?? []).map((row: any) => {
            const url = new URL(`/shared/${row.id}`, window.location.origin)
              .href;
            return (
              <article key={row.id}>
                <div>
                  <strong>
                    r{row.revision} ·{" "}
                    {t(statuses[row.status as keyof typeof statuses])}
                  </strong>
                  <small>
                    {dateLabel(row.created_at)} ·{" "}
                    {row.expires_at
                      ? t("到期：{date}", { date: dateLabel(row.expires_at) })
                      : t("直至撤销")}{" "}
                    · {row.metadata.bundle ? t("正文与完整证据") : t("仅正文")}
                  </small>
                </div>
                <input
                  aria-label={t("分享链接")}
                  readOnly
                  value={url}
                  onFocus={(e) => e.target.select()}
                />
                <div className="report-inline">
                  <Button
                    disabled={row.status !== "active"}
                    onClick={() => void copy(url)}
                  >
                    <Copy size={14} />
                    {t("复制链接")}
                  </Button>
                  {row.status === "active" && (
                    <a href={url} target="_blank" rel="noreferrer">
                      <ExternalLink size={14} />
                      {t("打开分享页")}
                    </a>
                  )}
                  {!row.revoked_at && (
                    <Button disabled={busy} onClick={() => void revoke(row.id)}>
                      {t("撤销分享")}
                    </Button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
        {shares.data?.rows.length === 0 && (
          <p className="hint">{t("尚未创建分享链接。")}</p>
        )}
        {(offset > 0 || shares.data?.more) && (
          <div className="report-inline">
            <Button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              {t("上一页")}
            </Button>
            <Button
              disabled={!shares.data?.more}
              onClick={() => setOffset(offset + 20)}
            >
              {t("下一页")}
            </Button>
          </div>
        )}
      </Modal>
    </>
  );
}
