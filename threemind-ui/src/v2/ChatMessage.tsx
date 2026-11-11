import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, timeLabel } from "./api";
import { t } from "./i18n";
import { ActivitySummary, classes } from "./readouts";
import { sources, statuses } from "./inputs";
import { ErrorBox } from "./ui";
import { usePreferences } from "./preferences";

export type ChatEntry = {
  id: string;
  kind: string;
  input_id: string | null;
  event_id: string | null;
  source: string;
  source_class: string;
  reconstructed: boolean;
  linked_input_id: string | null;
  stimulus: any;
  readout: any;
};

function ReadoutBody({ row, base }: { row: ChatEntry; base: string }) {
  const p = usePreferences();
  const temporal = row.kind === "temporal_readout";
  const [expanded, setExpanded] = useState(false);
  const [offset, setOffset] = useState(0);
  const cached = row.readout?.display;
  const modern = cached?.schema === "threemind.chat-readout/2";
  const changed = temporal ? p.temporalChatItems !== 7 : !p.chatActivationOrder;
  const query = new URLSearchParams({
    order: p.chatActivationOrder ? "activation" : "id",
    scope: temporal ? "candidates" : "active",
    limit: String(temporal ? p.temporalChatItems || 2000 : 128),
  });
  const preview = useQuery({
    queryKey: ["chat-presentation", base, row.id, query.toString()],
    queryFn: () => api(`${base}/conversation/${row.id}/presentation?${query}`),
    enabled: modern && changed,
    gcTime: 0,
  });
  const display =
    changed && preview.data?.display ? preview.data.display : cached;
  const full = useQuery({
    queryKey: ["chat-nodes", base, row.id, offset],
    queryFn: () =>
      api(
        `${base}/readouts/${row.event_id}?section=${temporal ? "nodes" : row.readout.node_scope === "all-source-nodes" ? "raw_nodes" : "activity_nodes"}&order=id&offset=${offset}&limit=50`,
      ),
    enabled: expanded,
    gcTime: 0,
  });
  const text =
    display?.text ??
    display?.nodes
      ?.map((n: any) => n.labels?.join(" · ") || `#${n.id}`)
      .join(" · ");
  const [moreLabels, setMoreLabels] = useState(false);
  const [labelOffset, setLabelOffset] = useState(0);
  const remainder = useQuery({
    queryKey: [
      "chat-labels",
      base,
      row.id,
      labelOffset,
      p.chatActivationOrder,
      temporal,
    ],
    queryFn: () =>
      api(
        `${base}/conversation/${row.id}/presentation?scope=${temporal ? "candidates" : "active"}&order=${p.chatActivationOrder ? "activation" : "id"}&offset=${labelOffset}&limit=128`,
      ),
    enabled: modern && moreLabels,
    gcTime: 0,
  });
  return (
    <>
      <p className="readout-plain">{text || t("此记录没有可显示的正文。")}</p>
      {display?.anonymous_text && display?.anonymous_text !== text && (
        <small className="anonymous-readout">
          {display.anonymous_text} ·{" "}
          {display.node_ids
            ?.slice(0, 7)
            .map((id: number) => `#${id}`)
            .join(" · ")}
          {(display.item_count ?? 0) > 7 && ` … (${display.item_count})`}
        </small>
      )}
      {temporal && (
        <small className="temporal-message-summary">
          {t(
            classes[row.readout.classification] ??
              row.readout.classification ??
              "",
          )}
          {display?.node_ids?.length > 0 && (
            <>
              {" "}
              · {t("主要节点")}{" "}
              {display.node_ids
                .slice(0, 5)
                .map((id: number) => `#${id}`)
                .join(" · ")}
            </>
          )}
        </small>
      )}
      {temporal && row.readout.analysis_schema && (
        <ActivitySummary value={row.readout} />
      )}
      {display?.truncated && modern && (
        <button
          type="button"
          className="text-link"
          onClick={() => {
            setMoreLabels((v) => !v);
            setLabelOffset(0);
          }}
        >
          {moreLabels ? t("收起完整读出文字") : t("查看完整读出文字")} (
          {display.item_count})
        </button>
      )}
      {moreLabels && (
        <div className="chat-expanded-labels">
          <p>{remainder.data?.display?.text}</p>
          <ErrorBox error={remainder.error} />
          <button
            type="button"
            className="text-link"
            disabled={!labelOffset}
            onClick={() => setLabelOffset((v) => Math.max(0, v - 128))}
          >
            {t("上一段")}
          </button>
          <button
            type="button"
            className="text-link"
            disabled={remainder.data?.display?.next == null}
            onClick={() => setLabelOffset(remainder.data.display.next)}
          >
            {t("下一段")}
          </button>
        </div>
      )}
      <details
        className="chat-evidence"
        onToggle={(e) => setExpanded(e.currentTarget.open)}
      >
        <summary>{t("完整节点与记录详情")}</summary>
        <small>
          {t("记录")} #{row.event_id} · {t("来源")}{" "}
          {t(sources[row.source] ?? row.source ?? "—")}
        </small>
        <small>
          {t("原始节点")} {row.readout.node_count ?? "—"} · {t("候选节点")}{" "}
          {row.readout.candidate_count ?? "—"}
        </small>
        {row.readout.overlapping_count > 0 && (
          <small>{t("观察期间有重叠输入；完整活动均保留。")}</small>
        )}
        {!row.linked_input_id && <small>{t("未关联特定输入。")}</small>}
        {expanded && (
          <>
            <ErrorBox error={full.error} />
            <div className="chat-node-table">
              <table>
                <thead>
                  <tr>
                    <th>{t("节点")}</th>
                    <th>{t(temporal ? "窗末激活" : "激活")}</th>
                    {row.readout.analysis_schema && <th>{t("判定时激活")}</th>}
                    {temporal && (
                      <>
                        <th>{t("窗内峰值")}</th>
                        <th>{t("综合得分")}</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {full.data?.rows?.map(({ item: n }: any) => (
                    <tr key={n.node_id ?? n.id}>
                      <td>#{n.node_id ?? n.id}</td>
                      <td>
                        {n[
                          temporal ? "last_activation" : "activation"
                        ]?.toPrecision(5) ?? "—"}
                      </td>
                      {row.readout.analysis_schema && (
                        <td>{n.decision_activation?.toPrecision(5) ?? "—"}</td>
                      )}
                      {temporal && (
                        <>
                          <td>{n.peak_activation?.toPrecision(5) ?? "—"}</td>
                          <td>{n.score?.toPrecision(5) ?? "—"}</td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button
              type="button"
              className="text-link"
              disabled={!offset}
              onClick={() => setOffset((v) => Math.max(0, v - 50))}
            >
              {t("上一页")}
            </button>
            <button
              type="button"
              className="text-link"
              disabled={!full.data?.more}
              onClick={() => setOffset((v) => v + 50)}
            >
              {t("下一页")}
            </button>
          </>
        )}
        <Link
          className="text-link"
          to={`?view=readouts&record=${row.event_id}`}
        >
          {t("图表与导出")}
        </Link>
        {row.linked_input_id && (
          <Link
            className="text-link"
            to={`?view=inputs&input=${row.linked_input_id}`}
          >
            {t("原始刺激")}
          </Link>
        )}
      </details>
    </>
  );
}

export default function ChatMessage({
  row,
  base,
}: {
  row: ChatEntry;
  base: string;
}) {
  const input = row.kind === "input",
    temporal = row.kind === "temporal_readout";
  const environment = input && row.source_class !== "manual";
  const label = input
    ? environment
      ? "环境"
      : "我"
    : temporal
      ? "时序读出"
      : row.kind === "external_interpretation"
        ? "外部意识解读"
        : "被动读出";
  const at = input ? row.stimulus?.last_delivery_us : row.readout?.time_us;
  return (
    <article
      className={`conversation-message chat-message ${input ? (environment ? "environment" : "user stimulus-message") : "interpreter readout-message"}`}
      data-message-id={row.id}
    >
      <header>
        <strong>{t(label)}</strong>
        <span>
          {temporal
            ? `${timeLabel(row.readout?.start_us)} – ${timeLabel(row.readout?.end_us)}`
            : at != null
              ? timeLabel(at)
              : t("待递送")}
        </span>
      </header>
      {input ? (
        <>
          <p className="carrier-preview">
            {row.stimulus?.text ??
              row.stimulus?.name ??
              t(sources[row.source] ?? row.source)}
          </p>
          <small>
            {t(statuses[row.stimulus?.status] ?? row.stimulus?.status ?? "")} ·{" "}
            {row.stimulus?.delivered_count ?? 0}/
            {row.stimulus?.frame_count ?? 0}
          </small>
          <details className="chat-evidence">
            <summary>{t("刺激详情")}</summary>
            <small>
              {t(sources[row.source] ?? row.source)} · #{row.id}
            </small>
            <Link
              className="text-link"
              to={`?view=inputs&input=${row.input_id}`}
            >
              {t("原始刺激与递送记录")}
            </Link>
          </details>
        </>
      ) : row.kind === "external_interpretation" ? (
        <p>{row.readout?.text}</p>
      ) : (
        <ReadoutBody row={row} base={base} />
      )}
    </article>
  );
}
