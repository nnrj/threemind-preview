import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, post } from "./api";
import { t, useLocale, dateLabel, messageKeys } from "./i18n";
import { Button, ErrorBox, Field, Modal } from "./ui";

const statuses = messageKeys({
  pending: "等待执行",
  leased: "正在导出",
  done: "导出完成",
  failed: "导出失败",
  cancelled: "已取消",
});

export default function ReportExport({
  base,
  document,
  revision,
  dirty = false,
  writable = true,
}: {
  base: string;
  document: string;
  revision: number;
  dirty?: boolean;
  writable?: boolean;
}) {
  const language = useLocale();
  const [open, setOpen] = useState(false),
    [format, setFormat] = useState("pdf"),
    [includeData, setIncludeData] = useState(false),
    [tableRows, setTableRows] = useState(100),
    [chartPoints, setChartPoints] = useState(500),
    [offset, setOffset] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const retry = useRef<any>(null);
  const path = `${base}/research-documents/${document}/exports`;
  const history = useQuery({
    queryKey: ["report-exports", path, offset],
    queryFn: () => api(`${path}?offset=${offset}`),
    enabled: open,
    refetchInterval: (query) =>
      open &&
      query.state.data?.rows.some(
        (r: any) => r.status === "pending" || r.status === "leased",
      )
        ? 2500
        : false,
  });
  async function submit() {
    setBusy(true);
    setError(undefined);
    const options = {
      revision,
      format,
      language,
      include_data: includeData,
      table_rows: tableRows,
      chart_points: chartPoints,
    };
    const fingerprint = JSON.stringify(options);
    if (retry.current?.fingerprint !== fingerprint)
      retry.current = {
        fingerprint,
        body: { ...options, operation_id: crypto.randomUUID() },
      };
    try {
      await post(path, retry.current.body);
      retry.current = null;
      setOffset(0);
      await history.refetch();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button disabled={!revision} onClick={() => setOpen(true)}>
        <Download size={15} />
        {t("导出")}
      </Button>
      <Modal
        open={open}
        onOpenChange={setOpen}
        title={t("导出记录与报告")}
        wide
      >
        <p>
          {t("固定导出修订 {revision}；后续编辑不会改变已生成的文件。", {
            revision,
          })}
        </p>
        {dirty && (
          <p role="status" className="hint">
            {t("当前有未保存修改。请先保存，再生成包含这些修改的导出。")}
          </p>
        )}
        <div className="report-field-grid">
          <Field label={t("正文格式")}>
            <select value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="pdf">PDF</option>
              <option value="docx">Word (.docx)</option>
              <option value="markdown">Markdown</option>
              <option value="html">HTML</option>
            </select>
          </Field>
          <Field
            label={t("每张正文表格最多行数")}
            hint={t(
              "按原始顺序取前若干行，正文会明确标注范围。完整数据可另附。",
            )}
          >
            <input
              type="number"
              min={1}
              aria-label={t("每张正文表格最多行数")}
              max={5000}
              value={tableRows}
              onChange={(e) => setTableRows(Number(e.target.value))}
            />
          </Field>
          <Field
            label={t("图表最多显示点数")}
            hint={t("超过时显示分组均值及最小值、最大值；完整数据不被删改。")}
          >
            <input
              type="number"
              min={10}
              aria-label={t("图表最多显示点数")}
              max={1000}
              value={chartPoints}
              onChange={(e) => setChartPoints(Number(e.target.value))}
            />
          </Field>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={includeData}
            onChange={(e) => setIncludeData(e.target.checked)}
          />
          {t("证据包附带全部固定来源数据行（可能较大）")}
        </label>
        <p className="hint">
          {t(
            "可分别下载正文与证据 ZIP。证据包保留文档、来源清单、校验值及 SVG／PNG 图表；Markdown 配图请使用证据 ZIP。",
          )}
        </p>
        <p className="hint">
          {t(
            "正文表格最多 100000 单元格，证据包最多 2 GiB；超限时会提示拆分，不会悄悄丢弃数据。",
          )}
        </p>
        {writable && (
          <Button
            variant="primary"
            disabled={
              busy ||
              dirty ||
              !Number.isInteger(tableRows) ||
              tableRows < 1 ||
              tableRows > 5000 ||
              !Number.isInteger(chartPoints) ||
              chartPoints < 10 ||
              chartPoints > 1000
            }
            onClick={() => void submit()}
          >
            {busy ? t("提交中…") : t("生成导出文件")}
          </Button>
        )}
        <ErrorBox error={error || history.error} />
        <h3>{t("导出历史")}</h3>
        {history.data?.rows.map((row: any) => (
          <article className="report-export-row" key={row.id}>
            <div>
              <strong>
                r{row.revision} · {row.options.format.toUpperCase()}
              </strong>
              <small>
                {dateLabel(row.created_at)} ·{" "}
                {t(statuses[row.status as keyof typeof statuses] || row.status)}
              </small>
            </div>
            {row.status === "done" && (
              <div className="report-inline">
                <a
                  className="report-download"
                  href={`/api/v2${base}/artifacts/${row.result.artifact_id}`}
                  download
                >
                  {t("下载正文")}
                </a>
                <a
                  className="report-download"
                  href={`/api/v2${base}/artifacts/${row.result.bundle_artifact_id}`}
                  download
                >
                  {t("下载证据 ZIP")}
                </a>
              </div>
            )}
            {row.status === "pending" && (
              <small>
                {t(
                  "任务会由具备导出组件和字体的工作节点执行，可在任务队列查看调度状态。",
                )}
              </small>
            )}
            {row.error && <ErrorBox error={row.error} />}
            {!!row.result?.warnings?.length && (
              <small>
                {t("部分正文表格仅包含选定行数；详见正文范围说明。")}
              </small>
            )}
          </article>
        ))}
        <div className="report-inline">
          <Button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            {t("上一页")}
          </Button>
          <Button
            disabled={!history.data?.more}
            onClick={() => setOffset(offset + 20)}
          >
            {t("下一页")}
          </Button>
        </div>
      </Modal>
    </>
  );
}
