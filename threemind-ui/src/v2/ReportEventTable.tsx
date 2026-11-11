import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t, messageKeys } from "./i18n";
import { Button, ErrorBox, Loading, Modal } from "./ui";

export const eventGroups = messageKeys({
  all: "全部已记录事件",
  inputs: "输入接收、调度与递送",
  interventions: "人工干预与参数变更",
  lifecycle: "阶段与运行控制",
  readouts: "结构、时序与器官读出",
});
export const eventPhases = messageKeys({
  processed_command: "命令已处理",
  configuration_commit: "参数变更已提交",
  scheduled_input: "输入已排队",
  delivered_input: "已记录输入递送",
  rejected_input: "输入已拒绝",
  recorded_event: "已记录事件",
});

function EventDetail({
  base,
  source,
  ordinal,
  close,
}: {
  base: string;
  source: string;
  ordinal: number;
  close: () => void;
}) {
  const detail = useQuery({
    queryKey: ["report-event-detail", base, source, ordinal],
    queryFn: () => api(`${base}/report-sources/${source}/rows/${ordinal}`),
  });
  return (
    <Modal
      title={t("固定事件原始内容")}
      open
      onOpenChange={(value) => {
        if (!value) close();
      }}
    >
      <p className="hint">
        {t("内容来自已固定的事件来源，包含当时记录的载体、参数与关联信息。")}
      </p>
      <ErrorBox error={detail.error} />
      {detail.isPending ? (
        <Loading />
      ) : (
        <pre className="report-event-json">
          {JSON.stringify(detail.data, null, 2)}
        </pre>
      )}
    </Modal>
  );
}

export default function EventTable({
  rows,
  base,
  source,
}: {
  rows: any[];
  base?: string;
  source?: string;
}) {
  const [opened, setOpened] = useState<number | null>(null);
  return (
    <>
      <p className="hint">
        {t(
          "模拟时间与受理时间 UTC 使用不同的时钟。日志条目数不等于独立输入数或实验次数。",
        )}
      </p>
      <p className="hint report-event-scroll-hint">
        {t("可横向滚动表格查看全部字段。")}
      </p>
      <div className="table-wrap report-data-table">
        <table>
          <thead>
            <tr>
              <th>{t("模拟时间（μs）")}</th>
              <th>{t("事件类型与阶段")}</th>
              <th>{t("提交版本与事件 ID")}</th>
              <th>{t("命令受理时间（UTC）")}</th>
              <th>{t("原始内容")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.ordinal}>
                <td>{row.time_us}</td>
                <td>
                  {row.label}
                  <small className="report-event-meta">
                    {t(
                      eventPhases[row.quality as keyof typeof eventPhases] ??
                        row.quality,
                    )}
                  </small>
                </td>
                <td>
                  r{row.provenance.commit_revision} · {row.provenance.event_id}
                  <small className="report-event-meta">
                    {row.provenance.event_key}
                  </small>
                </td>
                <td>
                  {row.provenance.admitted_at ?? "—"}
                  <small className="report-event-meta">
                    {row.provenance.command_id
                      ? `#${row.provenance.command_id}`
                      : ""}
                  </small>
                </td>
                <td>
                  {base && source ? (
                    <Button
                      onClick={() => setOpened(row.ordinal)}
                      aria-label={t("查看事件 {id}", {
                        id: row.provenance.event_id,
                      })}
                    >
                      {t("查看原始内容")}
                    </Button>
                  ) : (
                    <span title={row.provenance.payload_hash}>
                      {row.provenance.payload_hash.slice(0, 12)}…
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {opened !== null && base && source && (
        <EventDetail
          base={base}
          source={source}
          ordinal={opened}
          close={() => setOpened(null)}
        />
      )}
    </>
  );
}
