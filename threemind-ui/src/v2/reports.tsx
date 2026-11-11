import { can } from "./access";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import {
  ArrowLeft,
  ArrowDown,
  ArrowUp,
  Plus,
  Save,
  History,
  Archive,
  Trash2,
  Database,
  Eye,
} from "lucide-react";
import { api, post, ApiError } from "./api";
import { t, useLocale, dateLabel, messageKeys } from "./i18n";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  useWorkspace,
} from "./ui";
import JsonEditor, { parseJson } from "./JsonEditor";
import ReportRender, {
  kindNames,
  blockNames,
  sectionNames,
  chartNames,
  statisticNames,
} from "./reportRender";
import "./reports.css";
import { openReportDraft, reportDraftKey } from "./reportDraft";
import { metricOption } from "./reportLabels";
import ReportExport from "./ReportExport";
import ReportShare from "./ReportShare";
import ResearchAI from "./ResearchAI";
import { AICallDetail } from "./aiProviders";
import { eventGroups } from "./ReportEventTable";
import EvolutionSource from "./EvolutionSource";
import EcologySource from "./EcologySource";
import AssessmentSource from "./AssessmentSource";
import TemporalSource, { type TemporalSelection } from "./TemporalSource";

type Kind = "record" | "report";
const reportMessages = messageKeys({
  validated: "校验通过；所有数据块均引用已固定的真实来源。",
  restored: "已恢复浏览器中的未保存草案；保存时仍会检查数据库修订。",
  saved: "已保存修订 {revision}",
});
type Source = any;
type Spec = {
  schema_version?: string;
  kind: Kind;
  title: string;
  sources: string[];
  blocks: any[];
};
const availableCharts: Record<string, string[]> = {
  trajectory: ["line", "scatter", "histogram"],
  nodes: ["histogram"],
  edges: ["histogram"],
  analysis: ["bar"],
  events: ["bar"],
  evolution: ["histogram"],
  ecology_trajectory: ["line", "scatter", "histogram"],
  ecology_members: ["histogram"],
  assessment: ["histogram"],
  temporal_windows: ["histogram", "bar"],
  temporal_nodes: ["histogram", "bar"],
  temporal_series: ["line", "scatter"],
};
const blank = (kind: Kind): Spec => ({
  schema_version: "threemind.research-document/1",
  kind,
  title: kind === "record" ? t("新的实验记录") : t("新的实验报告"),
  sources: [],
  blocks: [
    {
      id: crypto.randomUUID(),
      type: "commentary",
      section: "purpose",
      markdown: "",
    },
  ],
});

function Pagination({
  offset,
  more,
  onChange,
  step = 50,
}: {
  offset: number;
  more: boolean;
  onChange: (n: number) => void;
  step?: number;
}) {
  return (
    <div className="report-inline">
      <Button
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - step))}
      >
        {t("上一页")}
      </Button>
      <span>{Math.floor(offset / step) + 1}</span>
      <Button disabled={!more} onClick={() => onChange(offset + step)}>
        {t("下一页")}
      </Button>
    </div>
  );
}

function SourceDialog({
  base,
  onClose,
  onChoose,
  initialEcology,
  initialTemporal,
}: {
  base: string;
  onClose: () => void;
  onChoose: (id: string) => void;
  initialEcology?: { id: string; checkpoint: string };
  initialTemporal?: TemporalSelection & { run: string };
}) {
  const [kind, setKind] = useState(
      initialTemporal
        ? "temporal_windows"
        : initialEcology
          ? "ecology_trajectory"
          : "trajectory",
    ),
    [run, setRun] = useState(initialTemporal?.run ?? ""),
    [checkpoint, setCheckpoint] = useState("");
  const [study, setStudy] = useState(""),
    [studySearch, setStudySearch] = useState(""),
    [studyOffset, setStudyOffset] = useState(0);
  const [runOffset, setRunOffset] = useState(0),
    [offset, setOffset] = useState(0),
    [analysisOffset, setAnalysisOffset] = useState(0),
    [analysis, setAnalysis] = useState("");
  const [from, setFrom] = useState(""),
    [through, setThrough] = useState(""),
    [metrics, setMetrics] = useState<string[]>([]);
  const [eventGroup, setEventGroup] = useState("all"),
    [eventKinds, setEventKinds] = useState("");
  const [evolution, setEvolution] = useState({
    id: "",
    generation: 0,
    stage: "selection",
  });
  const [evolutionMetrics, setEvolutionMetrics] = useState<string[]>([]);
  const [assessment, setAssessment] = useState("");
  const [temporal, setTemporal] = useState<TemporalSelection>(
    initialTemporal ?? { calibration_id: "", window_ids: [] },
  );
  const isTemporal = kind.startsWith("temporal_");
  const [ecology, setEcology] = useState(
    initialEcology ?? { id: "", checkpoint: "" },
  );
  const ecological =
    kind === "ecology_trajectory" || kind === "ecology_members";
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [requested, setRequested] = useState("");
  const retry = useRef<any>(null);
  const catalog = useQuery({
    queryKey: ["report-catalog", base],
    queryFn: () => api(`${base}/report-catalog`),
  });
  const studies = useQuery({
    queryKey: ["report-studies", base, studySearch, studyOffset],
    queryFn: () =>
      api(
        `${base}/study-library?q=${encodeURIComponent(studySearch)}&offset=${studyOffset}&limit=30`,
      ),
  });
  const runs = useQuery({
    queryKey: ["report-runs", base, study, runOffset],
    queryFn: () =>
      api<any[]>(
        `${base}/runs?summary=true&include_archived=true&offset=${runOffset}&limit=100${study ? `&study_id=${study}` : ""}`,
      ),
  });
  const checkpoints = useQuery({
    queryKey: ["report-checkpoints", base, run],
    queryFn: () => api<any[]>(`${base}/runs/${run}/checkpoints`),
    enabled: !!run,
  });
  const analyses = useQuery({
    queryKey: ["report-analyses", base, study, analysisOffset],
    queryFn: () =>
      api(
        `${base}/report-analyses?offset=${analysisOffset}${study ? `&study=${study}` : ""}`,
      ),
    enabled: kind === "analysis",
  });
  const sources = useQuery({
    queryKey: ["report-sources", base, offset],
    queryFn: () => api(`${base}/report-sources?offset=${offset}`),
    refetchInterval: (q) =>
      q.state.data?.rows.some((s: any) =>
        ["pending", "leased"].includes(s.status),
      )
        ? 1500
        : false,
  });
  async function capture() {
    setBusy(true);
    setError(undefined);
    const selection = {
      kind,
      ...(ecological
        ? {
            ecology_id: ecology.id,
            ecology_checkpoint_id: ecology.checkpoint || null,
          }
        : kind === "evolution"
          ? {
              evolution_id: evolution.id,
              evolution_generation: evolution.generation,
              evolution_stage: evolution.stage,
            }
          : kind === "assessment"
            ? { assessment_id: assessment }
            : kind === "analysis"
              ? { analysis_artifact_id: analysis }
              : isTemporal && temporal.calibration_id
                ? { calibration_id: temporal.calibration_id }
                : { run_id: run, checkpoint_id: checkpoint || null }),
      ...(isTemporal ? { window_ids: temporal.window_ids } : {}),
      metrics,
      ...(kind === "trajectory" ||
      kind === "events" ||
      kind === "ecology_trajectory" ||
      (isTemporal && !temporal.calibration_id)
        ? { from_us: from || null, through_us: through || null }
        : {}),
      ...(kind === "events"
        ? {
            event_group: eventGroup,
            event_kinds: eventKinds.split(/[,，\s]+/).filter(Boolean),
          }
        : {}),
    };
    const fingerprint = JSON.stringify(selection);
    if (retry.current?.fingerprint !== fingerprint)
      retry.current = {
        fingerprint,
        body: { ...selection, operation_id: crypto.randomUUID() },
      };
    try {
      const row = await post(`${base}/report-sources`, retry.current.body);
      setRequested(row.id);
      retry.current = null;
      setOffset(0);
      await sources.refetch();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      onOpenChange={(open) => !open && !busy && onClose()}
      title={t("选择或采集数据来源")}
      description={t(
        "固定恢复点和选定区间。采集在后台完成，不改变意识。已有来源可以反复使用。",
      )}
      wide
    >
      <details className="report-capture" open>
        <summary>{t("采集新的数据来源")}</summary>
        <fieldset disabled={busy} className="report-capture-fields">
          <div className="form-grid">
            <Field label={t("来源类型")}>
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setMetrics([]);
                }}
              >
                {Object.entries(kindNames).map(([key, name]) => (
                  <option key={key} value={key}>
                    {t(name)}
                  </option>
                ))}
              </select>
            </Field>
            {kind !== "evolution" && kind !== "assessment" && !ecological && (
              <>
                <Field label={t("搜索实验")}>
                  <input
                    value={studySearch}
                    onChange={(e) => {
                      setStudySearch(e.target.value);
                      setStudyOffset(0);
                    }}
                  />
                </Field>
                <Field label={t("所属实验（可选）")}>
                  <select
                    value={study}
                    onChange={(e) => {
                      setStudy(e.target.value);
                      setRun("");
                      setCheckpoint("");
                      setRunOffset(0);
                      setAnalysis("");
                      setAnalysisOffset(0);
                    }}
                  >
                    <option value="">{t("所有实验与独立意识")}</option>
                    {studies.data?.rows.map((s: any) => (
                      <option value={s.id} key={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Pagination
                  offset={studyOffset}
                  more={studies.data?.more ?? false}
                  step={30}
                  onChange={setStudyOffset}
                />
              </>
            )}
            {ecological ? (
              <>
                <EcologySource
                  base={base}
                  value={ecology}
                  change={setEcology}
                />
                {kind === "ecology_trajectory" && (
                  <>
                    <Field label={t("起始时间（μs，可留空）")}>
                      <input
                        inputMode="numeric"
                        value={from}
                        onChange={(event) => setFrom(event.target.value)}
                      />
                    </Field>
                    <Field label={t("截止时间（μs，可留空）")}>
                      <input
                        inputMode="numeric"
                        value={through}
                        onChange={(event) => setThrough(event.target.value)}
                      />
                    </Field>
                  </>
                )}
              </>
            ) : kind === "evolution" ? (
              <EvolutionSource
                base={base}
                value={evolution}
                change={(value: any) => {
                  setEvolution(value);
                  setMetrics([]);
                }}
                available={setEvolutionMetrics}
              />
            ) : kind === "assessment" ? (
              <AssessmentSource
                base={base}
                value={assessment}
                change={setAssessment}
              />
            ) : kind === "analysis" ? (
              <>
                <Field label={t("已完成的统计分析")}>
                  <select
                    value={analysis}
                    onChange={(e) => setAnalysis(e.target.value)}
                  >
                    <option value="">{t("请选择")}</option>
                    {analyses.data?.rows.map((a: any) => (
                      <option value={a.id} key={a.id}>
                        {a.study_name} · {a.params.control} →{" "}
                        {a.params.treatment} · {dateLabel(a.created_at)}
                      </option>
                    ))}
                  </select>
                </Field>
                <Pagination
                  offset={analysisOffset}
                  more={analyses.data?.more ?? false}
                  onChange={setAnalysisOffset}
                />
              </>
            ) : (
              <>
                <Field label={t("意识")}>
                  <select
                    value={run}
                    onChange={(e) => {
                      setRun(e.target.value);
                      setCheckpoint("");
                      setTemporal({ calibration_id: "", window_ids: [] });
                    }}
                  >
                    <option value="">{t("请选择")}</option>
                    {runs.data?.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} · {r.id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label={t("固定恢复点")}>
                  <select
                    value={checkpoint}
                    onChange={(e) => setCheckpoint(e.target.value)}
                  >
                    <option value="">{t("提交采集时的最新恢复点")}</option>
                    {checkpoints.data?.map((cp) => (
                      <option key={cp.id} value={cp.id}>
                        r{cp.revision} · {cp.time_us} μs
                      </option>
                    ))}
                  </select>
                </Field>
                <Pagination
                  offset={runOffset}
                  more={runs.data?.length === 100}
                  step={100}
                  onChange={setRunOffset}
                />
                {isTemporal && (
                  <TemporalSource
                    key={run}
                    base={base}
                    run={run}
                    kind={kind}
                    value={temporal}
                    onChange={setTemporal}
                  />
                )}
                {(kind === "trajectory" || kind === "events") && (
                  <>
                    <Field label={t("起始时间（μs，可留空）")}>
                      <input
                        inputMode="numeric"
                        value={from}
                        onChange={(e) => setFrom(e.target.value)}
                      />
                    </Field>
                    <Field label={t("截止时间（μs，可留空）")}>
                      <input
                        inputMode="numeric"
                        value={through}
                        onChange={(e) => setThrough(e.target.value)}
                      />
                    </Field>
                  </>
                )}
              </>
            )}
          </div>
          {kind === "events" && (
            <div className="form-grid">
              <Field label={t("事件范围")}>
                <select
                  aria-label={t("事件范围")}
                  value={eventGroup}
                  onChange={(e) => setEventGroup(e.target.value)}
                >
                  {Object.entries(eventGroups).map(([key, label]) => (
                    <option key={key} value={key}>
                      {t(label)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field
                label={t("指定事件类型（可选）")}
                hint={t(
                  "使用事件类型键，以逗号分隔；与所选事件范围同时生效。留空包含该范围全部类型。",
                )}
              >
                <input
                  aria-label={t("指定事件类型（可选）")}
                  value={eventKinds}
                  onChange={(e) => setEventKinds(e.target.value)}
                  placeholder="input_delivered, input_rejected"
                />
              </Field>
              <p className="hint">
                {t(
                  "仅采集恢复点内已提交的事件。待处理命令、未记录的内部传播不会被当作已发生的事件。",
                )}
              </p>
            </div>
          )}
          <details>
            <summary>{t("选择指标（默认全部）")}</summary>
            <div className="report-metric-choices">
              {(kind === "evolution"
                ? evolutionMetrics
                : Object.keys(catalog.data?.metrics[kind] ?? {})
              ).map((m) => (
                <label key={m}>
                  <input
                    type="checkbox"
                    checked={metrics.length === 0 || metrics.includes(m)}
                    disabled={metrics.length === 1 && metrics[0] === m}
                    onChange={(e) => {
                      const current = metrics.length
                        ? metrics
                        : kind === "evolution"
                          ? evolutionMetrics
                          : Object.keys(catalog.data.metrics[kind]);
                      setMetrics(
                        e.target.checked
                          ? [...new Set([...current, m])]
                          : current.filter((k) => k !== m),
                      );
                    }}
                  />
                  {metricOption(m)}
                </label>
              ))}
            </div>
          </details>
          <Button
            variant="primary"
            disabled={
              busy ||
              (isTemporal &&
                temporal.mode === "probe" &&
                !temporal.calibration_id) ||
              (kind === "temporal_series" &&
                temporal.window_ids.length !== 1) ||
              (ecological
                ? !ecology.id
                : kind === "evolution"
                  ? !evolution.id || !evolutionMetrics.length
                  : kind === "assessment"
                    ? !assessment
                    : kind === "analysis"
                      ? !analysis
                      : !run)
            }
            onClick={capture}
          >
            {t("开始采集")}
          </Button>
        </fieldset>
      </details>
      <ErrorBox
        error={
          error ||
          catalog.error ||
          sources.error ||
          studies.error ||
          runs.error ||
          checkpoints.error ||
          analyses.error
        }
      />
      <h3>{t("复用已有数据来源")}</h3>
      <div className="report-source-list">
        {sources.data?.rows.map((s: any) => (
          <div key={s.id} className={requested === s.id ? "selected" : ""}>
            <div>
              <strong>
                {s.run_name || t(kindNames[s.kind as keyof typeof kindNames])}
              </strong>
              <small>
                {t(kindNames[s.kind as keyof typeof kindNames])} ·{" "}
                {s.row_count ?? "…"} {t("行")} · {dateLabel(s.created_at)} ·{" "}
                {s.id.slice(0, 8)}
              </small>
              {s.error && <ErrorBox error={s.error} />}
            </div>
            <div className="report-inline">
              <Button
                disabled={busy || !s.content_hash}
                onClick={() => onChoose(s.id)}
              >
                {s.content_hash
                  ? t("使用此来源")
                  : s.status === "failed"
                    ? t("采集失败")
                    : t("采集中…")}
              </Button>
              <Button
                disabled={busy || ["pending", "leased"].includes(s.status)}
                onClick={async () => {
                  if (
                    !window.confirm(
                      t(
                        "释放未被文档引用的采集数据？已保存修订引用的来源会保留。",
                      ),
                    )
                  )
                    return;
                  setBusy(true);
                  setError(undefined);
                  try {
                    await api(`${base}/report-sources/${s.id}`, {
                      method: "DELETE",
                    });
                    await sources.refetch();
                  } catch (e) {
                    setError(e);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {t("释放未引用来源")}
              </Button>
            </div>
          </div>
        ))}
      </div>
      <Pagination
        offset={offset}
        more={sources.data?.more ?? false}
        onChange={setOffset}
      />
    </Modal>
  );
}

function RecordPicker({
  base,
  onSelect,
  onClose,
}: {
  base: string;
  onSelect: (block: any) => void;
  onClose: () => void;
}) {
  const [offset, setOffset] = useState(0),
    [query, setQuery] = useState(""),
    [id, setId] = useState(""),
    [revision, setRevision] = useState(0),
    [before, setBefore] = useState<number | undefined>();
  const rows = useQuery({
    queryKey: ["reference-records", base, query, offset],
    queryFn: () =>
      api(
        `${base}/research-documents?kind=record&query=${encodeURIComponent(query)}&offset=${offset}`,
      ),
  });
  const versions = useQuery({
    queryKey: ["record-versions", base, id, before],
    queryFn: () =>
      api(
        `${base}/research-documents/${id}/versions${before ? `?before=${before}` : ""}`,
      ),
    enabled: !!id,
  });
  const selected = useQuery({
    queryKey: ["record-reference", base, id, revision],
    queryFn: () => api(`${base}/research-documents/${id}?revision=${revision}`),
    enabled: !!id && revision > 0,
  });
  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={t("引用实验记录")}
      description={t(
        "选择固定修订中的图表、表格或说明；以后修改原记录不会改变此引用。",
      )}
    >
      {" "}
      <Field label={t("搜索记录")}>
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOffset(0);
          }}
        />
      </Field>
      <Field label={t("实验记录")}>
        <select
          aria-label={t("实验记录")}
          value={id}
          onChange={(e) => {
            setId(e.target.value);
            setBefore(undefined);
            setRevision(
              rows.data.rows.find((r: any) => r.id === e.target.value)
                ?.revision ?? 0,
            );
          }}
        >
          <option value="">{t("请选择")}</option>
          {rows.data?.rows.map((r: any) => (
            <option key={r.id} value={r.id}>
              {r.title}
            </option>
          ))}
        </select>
      </Field>
      <Pagination
        offset={offset}
        more={rows.data?.more ?? false}
        onChange={setOffset}
      />
      {id && (
        <>
          <Field label={t("修订")}>
            <select
              aria-label={t("修订")}
              value={revision}
              onChange={(e) => setRevision(Number(e.target.value))}
            >
              {versions.data?.rows.map((v: any) => (
                <option key={v.revision} value={v.revision}>
                  r{v.revision} · {v.title}
                </option>
              ))}
            </select>
          </Field>
          {versions.data?.more && (
            <Button
              onClick={() => setBefore(versions.data.rows.at(-1).revision)}
            >
              {t("更早修订")}
            </Button>
          )}
          <div className="report-source-list">
            {selected.data?.spec.blocks.map((block: any) => (
              <div key={block.id}>
                <span>
                  {block.title ||
                    block.metric ||
                    t(blockNames[block.type as keyof typeof blockNames])}
                </span>
                <Button
                  onClick={() =>
                    onSelect({
                      id: crypto.randomUUID(),
                      type: "record_block",
                      record_id: id,
                      revision,
                      block_id: block.id,
                    })
                  }
                >
                  {t("添加引用")}
                </Button>
              </div>
            ))}
          </div>
        </>
      )}
      <ErrorBox error={rows.error || versions.error || selected.error} />
    </Modal>
  );
}

function BlockEditor({
  block,
  sourceRows,
  disabled,
  onChange,
}: {
  block: any;
  sourceRows: Record<string, Source>;
  disabled: boolean;
  onChange: (value: any) => void;
}) {
  const patch = (value: any) => onChange({ ...block, ...value });
  const selected = sourceRows[block.source],
    metrics = Object.keys(selected?.manifest?.metrics ?? {});
  if (block.type === "assessment_summary")
    return (
      <Field label={t("固定评估来源")}>
        <select
          aria-label={t("固定评估来源")}
          disabled={disabled}
          value={block.source}
          onChange={(event) => patch({ source: event.target.value })}
        >
          {Object.values(sourceRows)
            .filter((s) => s.kind === "assessment")
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.provenance.batch_name} · {s.id.slice(0, 10)}
              </option>
            ))}
        </select>
        <small>
          {t("判定直接读取固定来源，不能在文档 JSON 中填写或改写结果。")}
        </small>
      </Field>
    );
  if (block.type === "record_block")
    return (
      <p>
        {t("引用固定记录修订")} · {block.record_id} · r{block.revision} ·{" "}
        {block.block_id}
      </p>
    );
  if (block.type === "commentary")
    return (
      <>
        <Field label={t("说明分类")}>
          <select
            disabled={disabled}
            value={block.section}
            onChange={(e) => patch({ section: e.target.value })}
          >
            {Object.entries(sectionNames).map(([key, name]) => (
              <option key={key} value={key}>
                {t(name)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("Markdown 说明")}>
          <textarea
            disabled={disabled}
            rows={6}
            value={block.markdown}
            onChange={(e) => patch({ markdown: e.target.value })}
          />
        </Field>
        <small>{t("支持 Markdown 和 LaTeX 公式；文字属于作者解释。")}</small>
      </>
    );
  return (
    <fieldset disabled={disabled}>
      <div className="form-grid">
        <Field label={t("数据来源")}>
          <select
            value={block.source}
            onChange={(e) => {
              const source = sourceRows[e.target.value],
                metric = Object.keys(source.manifest.metrics)[0];
              onChange({
                ...block,
                source: source.id,
                ...(block.type === "table"
                  ? {
                      metrics: Object.keys(source.manifest.metrics).slice(0, 8),
                    }
                  : { metric }),
                ...(block.type === "chart"
                  ? {
                      chart: availableCharts[source.kind][0],
                      analysis_metric:
                        source.kind === "analysis"
                          ? source.manifest.analysis.metrics[0]?.metric
                          : null,
                    }
                  : {}),
                ...(block.type === "fact"
                  ? { statistic: source.kind === "events" ? "count" : "last" }
                  : {}),
              });
            }}
          >
            {Object.values(sourceRows)
              .filter((s) => block.type !== "fact" || s.kind !== "analysis")
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.provenance.run_name ||
                    t(kindNames[s.kind as keyof typeof kindNames])}{" "}
                  · {s.id.slice(0, 8)}
                </option>
              ))}
          </select>
        </Field>
        <Field
          label={block.type === "fact" ? t("摘要标题") : t("图表或表格标题")}
        >
          <input
            value={block.title ?? block.label ?? ""}
            onChange={(e) =>
              patch(
                block.type === "fact"
                  ? { label: e.target.value }
                  : { title: e.target.value },
              )
            }
          />
        </Field>
        {block.type === "table" ? (
          <div className="report-metric-choices">
            {metrics.map((m) => (
              <label key={m}>
                <input
                  type="checkbox"
                  checked={block.metrics.includes(m)}
                  onChange={(e) =>
                    patch({
                      metrics: e.target.checked
                        ? [...block.metrics, m]
                        : block.metrics.filter((v: string) => v !== m),
                    })
                  }
                />
                {metricOption(m)}
              </label>
            ))}
          </div>
        ) : (
          <Field label={t("指标")}>
            <select
              value={block.metric}
              onChange={(e) => patch({ metric: e.target.value })}
            >
              {metrics.map((m) => (
                <option key={m} value={m}>
                  {metricOption(m)}
                </option>
              ))}
            </select>
          </Field>
        )}
        {block.type === "chart" && (
          <>
            <Field label={t("图表类型")}>
              <select
                value={block.chart}
                onChange={(e) => patch({ chart: e.target.value })}
              >
                {(availableCharts[selected?.kind] ?? []).map((key) => (
                  <option key={key} value={key}>
                    {t(chartNames[key as keyof typeof chartNames])}
                  </option>
                ))}
              </select>
            </Field>
            {block.chart === "histogram" && (
              <Field label={t("直方图分组数")}>
                <input
                  type="number"
                  min="5"
                  max="100"
                  value={block.bins ?? 30}
                  onChange={(e) => patch({ bins: Number(e.target.value) })}
                />
              </Field>
            )}
            {selected?.kind === "analysis" && (
              <Field label={t("统计终点")}>
                <select
                  value={block.analysis_metric ?? ""}
                  onChange={(e) => patch({ analysis_metric: e.target.value })}
                >
                  {selected.manifest.analysis.metrics.map((r: any) => (
                    <option key={r.metric}>{r.metric}</option>
                  ))}
                </select>
              </Field>
            )}
          </>
        )}
        {block.type === "fact" && (
          <Field label={t("摘要方式")}>
            <select
              value={block.statistic}
              onChange={(e) => patch({ statistic: e.target.value })}
            >
              {Object.entries(statisticNames)
                .filter(
                  ([key]) => selected?.kind !== "events" || key === "count",
                )
                .map(([key, name]) => (
                  <option key={key} value={key}>
                    {t(name)}
                  </option>
                ))}
            </select>
          </Field>
        )}
      </div>
    </fieldset>
  );
}

function DocumentEditor({
  base,
  initial,
  kind,
  actor,
  onBack,
  onSaved,
}: {
  base: string;
  initial: any;
  kind: Kind;
  actor: string;
  onBack: () => void;
  onSaved: () => void;
}) {
  const [opening] = useState(() =>
    openReportDraft(
      actor,
      reportDraftKey(actor, base, initial?.id ?? `new:${kind}`),
    ),
  );
  const cache = useRef(opening),
    recovered = opening.data;
  const documentId = useRef(
    recovered?.id ?? initial?.id ?? crypto.randomUUID(),
  );
  const [spec, setSpec] = useState<Spec>(
    () => recovered?.spec ?? initial?.spec ?? blank(kind),
  );
  const [revision, setRevision] = useState(
      recovered?.revision ?? initial?.revision ?? 0,
    ),
    [review, setReview] = useState(
      recovered?.review ?? initial?.review ?? "draft",
    );
  const [sourceRows, setSourceRows] = useState<Record<string, Source>>({});
  const [sourceOpen, setSourceOpen] = useState(false),
    [recordOpen, setRecordOpen] = useState(false),
    [historyOpen, setHistoryOpen] = useState(false),
    [historyBefore, setHistoryBefore] = useState<number | undefined>();
  const [jsonMode, setJsonMode] = useState(recovered?.jsonMode ?? false),
    [jsonText, setJsonText] = useState(recovered?.jsonText ?? ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [message, setMessage] = useState(recovered ? reportMessages.restored : "");
  const [rendered, setRendered] = useState<any>(),
    [previewOpen, setPreviewOpen] = useState(false);
  const [originOpen, setOriginOpen] = useState(false);
  const savedText = useRef(
    recovered?.saved ??
      JSON.stringify({
        spec: initial?.spec ?? spec,
        review: initial?.review ?? review,
      }),
  );
  const retry = useRef<any>(recovered?.pending ?? null),
    mounted = useRef(true);
  const dirty =
    JSON.stringify({ spec, review }) !== savedText.current ||
    (jsonMode && jsonText !== JSON.stringify(spec, null, 2));
  const recovery = useRef<any>(null);
  recovery.current = {
    id: documentId.current,
    revision,
    spec,
    review,
    jsonMode,
    jsonText,
    saved: savedText.current,
    pending: retry.current,
    dirty,
  };
  useEffect(() => {
    mounted.current = true;
    cache.current.activate();
    return () => {
      mounted.current = false;
      if (recovery.current.dirty || recovery.current.pending)
        cache.current.write(recovery.current);
      cache.current.close();
    };
  }, []);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty || busy) event.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty, busy]);
  useEffect(() => {
    if (!dirty) return;
    const timer = window.setTimeout(
      () => cache.current.write(recovery.current),
      300,
    );
    return () => clearTimeout(timer);
  }, [spec, review, revision, dirty, jsonMode, jsonText]);
  useEffect(() => {
    let active = true;
    Promise.all(spec.sources.map((id) => api(`${base}/report-sources/${id}`)))
      .then((rows) => {
        if (active)
          setSourceRows(Object.fromEntries(rows.map((r) => [r.id, r])));
      })
      .catch((e) => {
        if (active) setError(e);
      });
    return () => {
      active = false;
    };
  }, [base, JSON.stringify(spec.sources)]);
  const versions = useQuery({
    queryKey: [
      "document-versions",
      base,
      documentId.current,
      historyBefore,
      revision,
    ],
    queryFn: () =>
      api(
        `${base}/research-documents/${documentId.current}/versions${historyBefore ? `?before=${historyBefore}` : ""}`,
      ),
    enabled: historyOpen && revision > 0,
  });
  function change(value: Spec) {
    setSpec(value);
    setMessage("");
  }
  function current() {
    const value = jsonMode ? parseJson(jsonText) : spec;
    if (
      !value ||
      !Array.isArray(value.sources) ||
      !Array.isArray(value.blocks) ||
      value.kind !== kind
    )
      throw new Error(t("文档类型、来源和内容块结构无效。"));
    return value as Spec;
  }
  async function validate(show = true) {
    setBusy(true);
    setError(undefined);
    try {
      const value = current(),
        output = await post(`${base}/research-documents/preview`, value);
      if (!mounted.current) return;
      if (jsonMode) setSpec(output.spec);
      setRendered(output);
      setPreviewOpen(show);
      setMessage(reportMessages.validated);
      return output.spec as Spec;
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function save(copy = false) {
    setBusy(true);
    setError(undefined);
    setMessage("");
    try {
      const value = current(),
        id = copy
          ? retry.current?.copy
            ? retry.current.id
            : crypto.randomUUID()
          : documentId.current;
      const data = {
        spec: value,
        expected_revision: copy ? 0 : revision,
        review,
        ai_call_id: initial?.ai_call_id ?? null,
      };
      const fingerprint = JSON.stringify({ id, data });
      if (retry.current?.fingerprint !== fingerprint)
        retry.current = {
          fingerprint,
          id,
          copy,
          body: { ...data, operation_id: crypto.randomUUID() },
        };
      recovery.current = {
        ...recovery.current,
        spec: value,
        pending: retry.current,
      };
      cache.current.write(recovery.current);
      const result = await api(
        `${base}/research-documents/${retry.current.id}`,
        { method: "PUT", body: JSON.stringify(retry.current.body) },
      );
      cache.current.clear();
      retry.current = null;
      if (!mounted.current) return;
      cache.current.close();
      cache.current = openReportDraft(actor, reportDraftKey(actor, base, id));
      recovery.current = { ...recovery.current, dirty: false, pending: null };
      documentId.current = id;
      setRevision(result.revision);
      setSpec(value);
      savedText.current = JSON.stringify({ spec: value, review });
      setJsonText(JSON.stringify(value, null, 2));
      setMessage(reportMessages.saved);
      onSaved();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function chooseSource(id: string) {
    setSourceOpen(false);
    setBusy(true);
    setError(undefined);
    try {
      const [source, template] = await Promise.all([
        api(`${base}/report-sources/${id}`),
        api(`${base}/report-sources/${id}/template?kind=${kind}`),
      ]);
      setSourceRows((rows) => ({ ...rows, [id]: source }));
      const isEmpty =
        !spec.sources.length &&
        spec.blocks.every((b) => b.type === "commentary" && !b.markdown);
      change(
        isEmpty
          ? { ...template, title: spec.title }
          : { ...spec, sources: [...new Set([...spec.sources, id])] },
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  function add(type: string) {
    const id = crypto.randomUUID();
    if (type === "record_block") {
      setRecordOpen(true);
      return;
    }
    if (type === "commentary") {
      change({
        ...spec,
        blocks: [
          ...spec.blocks,
          { id, type, section: "discussion", markdown: "" },
        ],
      });
      return;
    }
    const source = Object.values(sourceRows).find((s) =>
      type === "assessment_summary"
        ? s.kind === "assessment"
        : type !== "fact" || s.kind !== "analysis",
    );
    if (!source) {
      setSourceOpen(true);
      return;
    }
    const metric = Object.keys(source.manifest.metrics)[0];
    const block = {
      id,
      type,
      source: source.id,
      ...(type === "assessment_summary"
        ? {}
        : type === "table"
          ? { metrics: Object.keys(source.manifest.metrics).slice(0, 8) }
          : { metric }),
      ...(type === "chart"
        ? {
            chart: availableCharts[source.kind][0],
            analysis_metric:
              source.kind === "analysis"
                ? source.manifest.analysis.metrics[0]?.metric
                : null,
          }
        : type === "fact"
          ? { statistic: source.kind === "events" ? "count" : "last" }
          : {}),
    };
    change({ ...spec, blocks: [...spec.blocks, block] });
  }
  function back() {
    if (busy) return;
    if (
      dirty &&
      !window.confirm(t("尚有未保存修改，离开编辑页面？浏览器会暂存当前草案。"))
    )
      return;
    onBack();
  }
  return (
    <div className="report-editor">
      {originOpen && initial?.ai_call_id && (
        <AICallDetail
          callId={initial.ai_call_id}
          onClose={() => setOriginOpen(false)}
        />
      )}
      <div className="report-inline">
        <Button onClick={back} disabled={busy}>
          <ArrowLeft size={16} />
          {t("返回列表")}
        </Button>
        <span>{revision ? `r${revision}` : t("尚未保存")}</span>
        {initial?.ai_call_id && (
          <Button onClick={() => setOriginOpen(true)}>
            {t("AI 生成来源")}
          </Button>
        )}
        {initial?.import_ai_generated && (
          <small>{t("导入记录保留的AI来源；未重建原生成调用")}</small>
        )}
        {dirty && <small>{t("有未保存修改")}</small>}
        <div className="report-spacer" />
        <ReportExport
          base={base}
          document={documentId.current}
          revision={revision}
          dirty={dirty}
        />
        <ReportShare
          base={base}
          document={documentId.current}
          revision={revision}
          dirty={dirty}
        />
        <Button
          disabled={busy || revision === 0}
          onClick={() => setHistoryOpen(true)}
        >
          <History size={16} />
          {t("修订历史")}
        </Button>
        <Button disabled={busy} onClick={() => void validate()}>
          <Eye size={16} />
          {t("预览与校验")}
        </Button>
        <Button disabled={busy} variant="primary" onClick={() => void save()}>
          <Save size={16} />
          {t("保存")}
        </Button>
      </div>
      <ErrorBox error={error} />
      {error instanceof ApiError && error.status === 409 && (
        <Button disabled={busy} onClick={() => void save(true)}>
          {t("另存为副本")}
        </Button>
      )}
      {message && (
        <p role="status" className="hint">
          {t(message, { revision })}
        </p>
      )}
      <fieldset disabled={busy}>
        <div className="report-inline">
          <Field label={t("文档标题")}>
            <input
              value={spec.title}
              onChange={(e) => change({ ...spec, title: e.target.value })}
              disabled={jsonMode}
            />
          </Field>
          <Field label={t("复核状态")}>
            <select
              aria-label={t("复核状态")}
              value={review}
              onChange={(e) => setReview(e.target.value)}
            >
              <option value="draft">{t("待复核草案")}</option>
              <option value="reviewed">{t("作者已标记复核")}</option>
            </select>
          </Field>
        </div>
      </fieldset>
      <div className="report-inline">
        <h3>{t("内容配置")}</h3>
        <div className="report-spacer" />
        <button
          className="text-button"
          disabled={busy}
          onClick={async () => {
            if (jsonMode) {
              const value = await validate(false);
              if (value) setJsonMode(false);
            } else {
              setJsonText(JSON.stringify(spec, null, 2));
              setJsonMode(true);
            }
          }}
        >
          {jsonMode ? t("切换到图形配置") : t("切换到 JSON 编辑")}
        </button>
      </div>
      {jsonMode ? (
        <>
          <div className="report-inline">
            <Button
              disabled={busy}
              onClick={() => {
                try {
                  setJsonText(JSON.stringify(parseJson(jsonText), null, 2));
                  setError(undefined);
                } catch (e) {
                  setError(e);
                }
              }}
            >
              {t("格式化")}
            </Button>
            <Button disabled={busy} onClick={() => void validate(false)}>
              {t("校验")}
            </Button>
          </div>
          <JsonEditor
            value={jsonText}
            onChange={setJsonText}
            readOnly={busy}
            label={t("记录与报告 JSON")}
            rows={28}
          />
        </>
      ) : (
        <div className="report-compose">
          <aside className="report-composer-sources">
            <h3>{t("数据来源")}</h3>
            <Button disabled={busy} onClick={() => setSourceOpen(true)}>
              <Database size={16} />
              {t("添加数据来源")}
            </Button>
            {spec.sources.map((id) => (
              <div key={id}>
                <strong>
                  {sourceRows[id]?.provenance?.run_name || id.slice(0, 8)}
                </strong>
                <small>
                  {sourceRows[id] &&
                    t(kindNames[sourceRows[id].kind as keyof typeof kindNames])}
                </small>
                <code>{id.slice(0, 8)}</code>
                <button
                  className="text-button"
                  disabled={busy || spec.blocks.some((b) => b.source === id)}
                  onClick={() =>
                    change({
                      ...spec,
                      sources: spec.sources.filter((s) => s !== id),
                    })
                  }
                >
                  {t("移除此引用")}
                </button>
              </div>
            ))}
            <p className="hint">
              {t(
                "图表和表格的数值由数据库提供。删除内容块只改变文档，不改变来源数据。",
              )}
            </p>
          </aside>
          <div className="report-blocks">
            {spec.blocks.map((block, index) => (
              <section className="report-block-editor" key={block.id}>
                <header>
                  <span>{index + 1}</span>
                  <h3>
                    {t(blockNames[block.type as keyof typeof blockNames])}
                  </h3>
                  <div className="report-spacer" />
                  {[-1, 1].map((delta) => (
                    <Button
                      key={delta}
                      disabled={
                        busy ||
                        index + delta < 0 ||
                        index + delta >= spec.blocks.length
                      }
                      aria-label={delta < 0 ? t("上移内容块") : t("下移内容块")}
                      onClick={() => {
                        const blocks = [...spec.blocks];
                        [blocks[index], blocks[index + delta]] = [
                          blocks[index + delta],
                          blocks[index],
                        ];
                        change({ ...spec, blocks });
                      }}
                    >
                      {delta < 0 ? (
                        <ArrowUp size={15} />
                      ) : (
                        <ArrowDown size={15} />
                      )}
                    </Button>
                  ))}
                  <Button
                    disabled={busy}
                    aria-label={t("删除内容块")}
                    onClick={() =>
                      change({
                        ...spec,
                        blocks: spec.blocks.filter((b) => b.id !== block.id),
                      })
                    }
                  >
                    <Trash2 size={15} />
                  </Button>
                </header>
                <BlockEditor
                  block={block}
                  sourceRows={sourceRows}
                  disabled={busy}
                  onChange={(value) =>
                    change({
                      ...spec,
                      blocks: spec.blocks.map((b) =>
                        b.id === block.id ? value : b,
                      ),
                    })
                  }
                />
              </section>
            ))}
            <div className="report-add-blocks">
              {Object.entries(blockNames)
                .filter(([key]) => kind === "report" || key !== "record_block")
                .map(([key, name]) => (
                  <Button
                    key={key}
                    disabled={busy || spec.blocks.length >= 100}
                    onClick={() => add(key)}
                  >
                    <Plus size={15} />
                    {t(name)}
                  </Button>
                ))}
            </div>
          </div>
        </div>
      )}
      {sourceOpen && (
        <SourceDialog
          base={base}
          onClose={() => setSourceOpen(false)}
          onChoose={(id) => void chooseSource(id)}
        />
      )}
      {recordOpen && (
        <RecordPicker
          base={base}
          onClose={() => setRecordOpen(false)}
          onSelect={(b) => {
            change({ ...spec, blocks: [...spec.blocks, b] });
            setRecordOpen(false);
          }}
        />
      )}
      <Modal
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        title={t("记录预览")}
        description={t("所有图表由固定来源计算；完整数据可在表格中分页查看。")}
        wide
      >
        {rendered && <ReportRender data={rendered} base={base} />}
      </Modal>
      <Modal
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        title={t("修订历史")}
        description={t("载入旧修订后保存，会生成新的修订并保留原历史。")}
      >
        <ErrorBox error={versions.error} />
        {versions.data?.rows.map((v: any) => (
          <div className="report-history-row" key={v.revision}>
            <div>
              <strong>
                r{v.revision} · {v.title}
              </strong>
              <small>{dateLabel(v.created_at)}</small>
            </div>
            <Button
              disabled={busy}
              onClick={async () => {
                if (
                  dirty &&
                  !window.confirm(t("载入此修订将替换当前未保存的编辑，继续？"))
                )
                  return;
                try {
                  const row = await api(
                    `${base}/research-documents/${documentId.current}?revision=${v.revision}`,
                  );
                  change(row.spec);
                  setReview("draft");
                  setJsonMode(false);
                  setHistoryOpen(false);
                } catch (e) {
                  setError(e);
                }
              }}
            >
              {t("载入此修订")}
            </Button>
          </div>
        ))}
        {versions.data?.more && (
          <Button
            onClick={() => setHistoryBefore(versions.data.rows.at(-1).revision)}
          >
            {t("更早修订")}
          </Button>
        )}
      </Modal>
    </div>
  );
}

export default function Reports() {
  const { project, user } = useWorkspace(),
    client = useQueryClient();
  useLocale();
  const base = `/projects/${project!.id}`,
    write = project?.role !== "viewer" && can(user,"reports.write");
  const [params, setParams] = useSearchParams(),
    kind: Kind = params.get("tab") === "report" ? "report" : "record";
  const [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0),
    [archived, setArchived] = useState(false),
    [editing, setEditing] = useState<any>(undefined),
    [preview, setPreview] = useState<any>(),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const [aiCall, setAiCall] = useState<string>();
  const documentParam = params.get("document");
  const ecologyParam = params.get("ecology");
  const temporalRun = params.get("temporal_run");
  const sourceParam = params.get("source");
  useEffect(() => {
    if (!sourceParam || !write) return;
    let active = true;
    api(
      `${base}/report-sources/${encodeURIComponent(sourceParam)}/template?kind=${kind}`,
    )
      .then((spec) => {
        if (active) {
          setEditing({ id: crypto.randomUUID(), revision: 0, spec });
          setParams({ tab: kind });
        }
      })
      .catch((cause) => {
        if (active) setError(cause);
      });
    return () => {
      active = false;
    };
  }, [base, sourceParam, write, kind]);
  const documents = useQuery({
    queryKey: ["research-documents", base, kind, query, offset, archived],
    queryFn: () =>
      api(
        `${base}/research-documents?kind=${kind}&query=${encodeURIComponent(query)}&offset=${offset}&archived=${archived}`,
      ),
  });
  useEffect(() => {
    setEditing(undefined);
    setPreview(undefined);
    setError(undefined);
    setOffset(0);
  }, [base]);
  useEffect(() => {
    if (!documentParam) return;
    let active = true;
    api(`${base}/research-documents/${encodeURIComponent(documentParam)}`)
      .then((row) => {
        if (active) {
          if (write) setEditing(row);
          else void open(row, false);
        }
      })
      .catch((e) => {
        if (active) setError(e);
      });
    return () => {
      active = false;
    };
  }, [base, documentParam, write]);
  async function open(row: any, edit: boolean) {
    setBusy(true);
    setError(undefined);
    try {
      const result = await api(
        `${base}/research-documents/${row.id}${edit ? "" : "/render"}`,
      );
      if (edit) setEditing(result);
      else setPreview(result);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function archive(row: any) {
    setBusy(true);
    setError(undefined);
    try {
      await post(`${base}/research-documents/${row.id}/archive`, {
        expected_revision: row.revision,
        archived: !archived,
      });
      await documents.refetch();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  if (editing !== undefined)
    return (
      <DocumentEditor
        key={`${base}:${editing?.id ?? "new"}`}
        base={base}
        actor={user.id}
        initial={editing}
        kind={kind}
        onBack={() => setEditing(undefined)}
        onSaved={() => {
          client.invalidateQueries({ queryKey: ["research-documents", base] });
        }}
      />
    );
  return (
    <>
      {write && (ecologyParam || temporalRun) && (
        <SourceDialog
          key={`${base}:${ecologyParam}`}
          base={base}
          initialEcology={
            ecologyParam
              ? {
                  id: ecologyParam,
                  checkpoint: params.get("checkpoint") ?? "",
                }
              : undefined
          }
          initialTemporal={
            temporalRun
              ? {
                  run: temporalRun,
                  mode: params.get("calibration") ? "probe" : "run",
                  calibration_id: params.get("calibration") ?? "",
                  window_ids: params.get("window")
                    ? [params.get("window")!]
                    : [],
                }
              : undefined
          }
          onClose={() => setParams({ tab: kind })}
          onChoose={async (id) => {
            setParams({ tab: kind });
            try {
              const spec = await api(
                `${base}/report-sources/${id}/template?kind=${kind}`,
              );
              setEditing({ id: crypto.randomUUID(), revision: 0, spec });
            } catch (error) {
              setError(error);
            }
          }}
        />
      )}
      <PageTitle
        eyebrow="RESEARCH EVIDENCE"
        title={t("记录与报告")}
        description={t(
          "用固定的实验数据组织图表、观测与解释。每份记录可以有不同的研究视角，每次修改保留独立修订。",
        )}
        actions={
          write && (
            <div className="report-inline">
              <ResearchAI
                key={`${base}:${kind}`}
                base={base}
                kind={kind}
                onGenerated={(id) => void open({ id }, true)}
                sourcePicker={(choose, close) => (
                  <SourceDialog base={base} onChoose={choose} onClose={close} />
                )}
                recordPicker={(choose, close) => (
                  <RecordPicker base={base} onSelect={choose} onClose={close} />
                )}
              />
              <Button variant="primary" onClick={() => setEditing(null)}>
                <Plus size={16} />
                {kind === "record" ? t("新建实验记录") : t("新建实验报告")}
              </Button>
            </div>
          )
        }
      />
      <p className="record-scope">
        {t("此工作区显示所属项目的记录与报告。")}{" "}
        <a href="/research-records">{t("查看全部实验")}</a>
      </p>
      <div className="tabs" role="tablist" aria-label={t("记录与报告")}>
        <button
          role="tab"
          aria-selected={kind === "record"}
          className={kind === "record" ? "active" : ""}
          onClick={() => {
            setParams({ tab: "record" });
            setOffset(0);
          }}
        >
          {t("实验记录")}
        </button>
        <button
          role="tab"
          aria-selected={kind === "report"}
          className={kind === "report" ? "active" : ""}
          onClick={() => {
            setParams({ tab: "report" });
            setOffset(0);
          }}
        >
          {t("实验报告")}
        </button>
      </div>
      <div className="report-inline report-filters">
        <Field label={t("搜索标题")}>
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
          />
        </Field>
        <label>
          <input
            type="checkbox"
            checked={archived}
            onChange={(e) => {
              setArchived(e.target.checked);
              setOffset(0);
            }}
          />
          {t("已归档")}
        </label>
      </div>
      <ErrorBox error={error || documents.error} />
      {documents.isLoading && <Loading />}
      {documents.data?.rows.length === 0 && (
        <Empty
          title={t("还没有研究记录")}
          detail={t(
            "选择意识或已完成的实验，采集固定数据来源，再从默认图表开始整理。",
          )}
        />
      )}
      <div className="report-document-list">
        {documents.data?.rows.map((row: any) => (
          <article key={row.id}>
            <div>
              <span className="eyebrow">
                {kind === "record" ? "RECORD" : "REPORT"} · r{row.revision}
              </span>
              <h3>
                <button
                  className="text-button"
                  onClick={() => void open(row, false)}
                >
                  {row.title}
                </button>
              </h3>
              <small>
                {dateLabel(row.updated_at)} ·{" "}
                {row.review === "reviewed"
                  ? t("作者已标记复核")
                  : t("待复核草案")}
              </small>
              {row.ai_call_id && (
                <button
                  className="text-button"
                  onClick={() => setAiCall(row.ai_call_id)}
                >
                  {t("AI 生成来源")}
                </button>
              )}
              {row.import_ai_generated && (
                <small>{t("导入记录保留的AI来源；未重建原生成调用")}</small>
              )}
            </div>
            <div className="report-inline">
              <Button disabled={busy} onClick={() => void open(row, false)}>
                {t("查看")}
              </Button>
              <ReportExport
                base={base}
                document={row.id}
                revision={row.revision}
                writable={write}
              />
              <ReportShare
                base={base}
                document={row.id}
                revision={row.revision}
              />
              {write && !archived && (
                <Button disabled={busy} onClick={() => void open(row, true)}>
                  {t("编辑")}
                </Button>
              )}
              {write && (
                <Button disabled={busy} onClick={() => void archive(row)}>
                  <Archive size={15} />
                  {archived ? t("恢复") : t("归档")}
                </Button>
              )}
            </div>
          </article>
        ))}
      </div>
      <Pagination
        offset={offset}
        more={documents.data?.more ?? false}
        onChange={setOffset}
      />
      <Modal
        open={!!preview}
        onOpenChange={(open) => !open && setPreview(undefined)}
        title={t("记录预览")}
        description={t("此视图来自已保存的固定修订。")}
        wide
      >
        {preview && <ReportRender data={preview} base={base} />}
      </Modal>
      {aiCall && (
        <AICallDetail callId={aiCall} onClose={() => setAiCall(undefined)} />
      )}
    </>
  );
}
