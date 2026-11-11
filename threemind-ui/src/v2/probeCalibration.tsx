import { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, post } from "./api";
import { Button, ErrorBox, Field, Loading, useWorkspace } from "./ui";
import JsonEditor, { parseJson } from "./JsonEditor";
import { t } from "./i18n";
import "./probeCalibration.css";
import TemporalProbe from "./TemporalProbe";

export default function ProbeCalibration({ base }: { base: string }) {
  const [mode, setMode] = useState("temporal");
  return (
    <>
      <div className="tabs" aria-label={t("观察方式")}>
        <button
          className={mode === "temporal" ? "active" : ""}
          onClick={() => setMode("temporal")}
        >
          {t("时序观察实验")}
        </button>
        <button
          className={mode === "fixed" ? "active" : ""}
          onClick={() => setMode("fixed")}
        >
          {t("固定窗口探针与感官校准")}
        </button>
      </div>
      {mode === "temporal" ? (
        <TemporalProbe base={base} />
      ) : (
        <FixedProbeCalibration base={base} />
      )}
    </>
  );
}

const defaults = {
  cues: ["甲", "乙"],
  terms: ["松子", "铃铛"],
  intensities: [1, 2, 4],
  route: "birth",
  blank_us: 800000,
  window_us: 1000000,
  sample_us: 20000,
  score_from_us: 200000,
  learning_during_probe: false,
};
const value = (x: any) =>
  x == null ? t("无法评分") : Number(x).toPrecision(5);
const colors = [
  "#237969",
  "#ad6538",
  "#566fac",
  "#a35792",
  "#658838",
  "#a14d4a",
  "#3b879d",
  "#877444",
];

function Curves({ result, row }: { result: any; row: any }) {
  const [index, setIndex] = useState(0);
  const terms = result.protocol.terms as string[];
  const top = result.rows.reduce(
    (max: number, r: any) =>
      r.curve.reduce(
        (m: number, p: any) =>
          terms.reduce((v, w) => Math.max(v, p.terms[w] ?? 0), m),
        max,
      ),
    0.000001,
  );
  const point = row.curve[Math.min(index, row.curve.length - 1)];
  return (
    <section className="panel">
      <h3>{t("观察词的激活曲线")}</h3>
      <p>{t("各强度使用相同纵轴；筛选仅用于评分，完整节点活动在证据包中。")}</p>
      <svg
        viewBox="0 0 760 280"
        role="img"
        aria-label={t("探针激活曲线")}
        style={{ width: "100%", maxHeight: 300 }}
      >
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line
              x1="76"
              x2="740"
              y1={235 - f * 210}
              y2={235 - f * 210}
              stroke="currentColor"
              opacity=".15"
            />
            <text x="2" y={239 - f * 210} fill="currentColor" fontSize="12">
              {(f * top).toPrecision(3)}
            </text>
          </g>
        ))}
        {terms.map((word, k) => {
          let next = true;
          const path = row.curve
            .map((p: any, i: number) => {
              if (p.terms[word] == null) {
                next = true;
                return "";
              }
              const cmd = next ? "M" : "L";
              next = false;
              return `${cmd}${76 + (i / (row.curve.length - 1)) * 664},${235 - (p.terms[word] / top) * 210}`;
            })
            .join(" ");
          return (
            <path
              key={word}
              d={path}
              fill="none"
              stroke={colors[k]}
              strokeWidth="2"
            >
              <title>{word}</title>
            </path>
          );
        })}
        <text x="76" y="264" fill="currentColor">
          0 s
        </text>
        <text x="690" y="264" fill="currentColor">
          {result.protocol.window_us / 1e6} s
        </text>
      </svg>
      <div className="probe-legend">
        {terms.map((w, k) => (
          <span key={w} style={{ color: colors[k] }}>
            {w}: {value(point.terms[w])}
          </span>
        ))}
      </div>
      <label>
        {t("查看采样点")} · {point.offset_us / 1e6} s
        <input
          aria-label={t("查看采样点")}
          type="range"
          min="0"
          max={row.curve.length - 1}
          value={Math.min(index, row.curve.length - 1)}
          onChange={(e) => setIndex(Number(e.target.value))}
          style={{ width: "100%" }}
        />
      </label>
    </section>
  );
}

function FixedProbeCalibration({ base }: { base: string }) {
  const { project } = useWorkspace();
  const pending = useRef<{ signature: string; operation_id: string } | null>(
    null,
  );
  const [doseText, setDoseText] = useState("1,2,4");
  const [historyPage, setHistoryPage] = useState(0);
  const [protocol, setProtocol] = useState<any>(defaults),
    [json, setJson] = useState<string | null>(null);
  const [checkpoint, setCheckpoint] = useState(""),
    [selected, setSelected] = useState(""),
    [rowIndex, setRowIndex] = useState(1);
  const [error, setError] = useState<unknown>(),
    [page, setPage] = useState(0);
  const root = `/projects/${project!.id}`;
  const history = useQuery<any>({
    queryKey: ["calibrations", base, historyPage],
    queryFn: () =>
      api(`${base}/calibrations?mode=fixed-window&offset=${historyPage * 20}`),
    refetchInterval: (q) =>
      q.state.data?.rows?.some((r: any) =>
        ["pending", "leased"].includes(r.status),
      )
        ? 2000
        : false,
  });
  const detail = useQuery<any>({
    queryKey: ["calibration", root, selected],
    enabled: !!selected,
    queryFn: () => api(`${root}/calibrations/${selected}`),
    refetchInterval: (q) =>
      q.state.data && ["pending", "leased"].includes(q.state.data.status)
        ? 1500
        : false,
  });
  const result = useQuery<any>({
    queryKey: ["calibration-result", root, selected],
    enabled: detail.data?.status === "done",
    queryFn: () => api(`${root}/calibrations/${selected}/result`),
  });
  const formProtocol = () => ({
    ...protocol,
    cues: protocol.cues.filter((s: string) => s.trim()),
    terms: protocol.terms.filter((s: string) => s.trim()),
    intensities: doseText.split(",").map((s) => {
      if (!s.trim() || !Number.isFinite(Number(s)))
        throw new Error(t("请输入有效的探针强度"));
      return Number(s);
    }),
  });
  const create = useMutation({
    mutationFn: () => {
      const body = {
        checkpoint_id: checkpoint || null,
        protocol: json === null ? formProtocol() : parseJson(json),
      };
      const signature = JSON.stringify(body);
      if (pending.current?.signature !== signature)
        pending.current = { signature, operation_id: crypto.randomUUID() };
      return post<any>(`${base}/calibrations`, {
        ...body,
        operation_id: pending.current.operation_id,
      });
    },
    onSuccess: (r) => {
      pending.current = null;
      setSelected(r.id);
      setRowIndex(1);
      setPage(0);
      setHistoryPage(0);
      void history.refetch();
    },
    onError: setError,
  });
  const patch = (key: string, val: any) =>
    setProtocol({ ...protocol, [key]: val });
  const data = result.data,
    row = data?.rows[Math.min(rowIndex, data.rows.length - 1)];
  const channels =
    row?.input_frames.flatMap((f: any) =>
      f.stimulus.channels.map(([c, a]: any[]) => ({
        channel: c,
        amplitude: a,
        intensity: f.stimulus.intensity,
        time_us: f.stimulus.time_us,
      })),
    ) ?? [];
  return (
    <div className="research-workspace probe-calibration">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>{t("感官与探针校准")}</h2>
            <p>{t("从固定恢复点创建独立测量副本；不推进、不改写原意识。")}</p>
          </div>
          <Button
            onClick={() => {
              try {
                if (json === null)
                  setJson(JSON.stringify(formProtocol(), null, 2));
                else {
                  const parsed = parseJson(json) as any;
                  if (
                    !parsed ||
                    typeof parsed !== "object" ||
                    Object.keys(defaults).some((k) => !(k in parsed)) ||
                    Object.keys(parsed).some((k) => !(k in defaults)) ||
                    ![parsed.cues, parsed.terms].every(
                      (a) =>
                        Array.isArray(a) &&
                        a.every((v) => typeof v === "string"),
                    ) ||
                    !Array.isArray(parsed.intensities) ||
                    !parsed.intensities.every(
                      (v: any) => typeof v === "number",
                    ) ||
                    !["birth", "continuation"].includes(parsed.route) ||
                    typeof parsed.learning_during_probe !== "boolean" ||
                    [
                      "blank_us",
                      "window_us",
                      "sample_us",
                      "score_from_us",
                    ].some((k) => typeof parsed[k] !== "number")
                  )
                    throw new Error(t("JSON 结构无法转换为图形配置"));
                  setProtocol(parsed);
                  setDoseText(parsed.intensities.join(","));
                  setJson(null);
                }
                setError(undefined);
              } catch (e) {
                setError(e);
              }
            }}
          >
            {json === null ? t("JSON 编辑") : t("图形配置")}
          </Button>
        </div>
        <Field label={t("恢复点编号（留空固定到最新已保存点）")}>
          <input
            value={checkpoint}
            onChange={(e) => setCheckpoint(e.target.value)}
          />
        </Field>
        {json !== null ? (
          <JsonEditor
            value={json}
            onChange={setJson}
            label={t("校准协议 JSON")}
            rows={18}
          />
        ) : (
          <>
            <div className="form-grid">
              <Field label={t("探针文本（每行一个）")}>
                <textarea
                  rows={3}
                  value={protocol.cues.join("\n")}
                  onChange={(e) => patch("cues", e.target.value.split("\n"))}
                />
              </Field>
              <Field label={t("观察词与对照词（每行一个）")}>
                <textarea
                  rows={3}
                  value={protocol.terms.join("\n")}
                  onChange={(e) => patch("terms", e.target.value.split("\n"))}
                />
              </Field>
              <Field label={t("探针强度（逗号分隔）")}>
                <input
                  value={doseText}
                  onChange={(e) => setDoseText(e.target.value)}
                />
              </Field>
              <Field label={t("副本起点")}>
                <select
                  value={protocol.route}
                  onChange={(e) => patch("route", e.target.value)}
                >
                  <option value="birth">{t("继承结构，清空活动")}</option>
                  <option value="continuation">
                    {t("保持恢复点活动与在途事件")}
                  </option>
                </select>
              </Field>
            </div>
            <details>
              <summary>{t("高级测量参数")}</summary>
              <div className="form-grid">
                {[
                  ["blank_us", "延续副本的空白等待（微秒）"],
                  ["window_us", "观察时长（微秒）"],
                  ["sample_us", "采样间隔（微秒）"],
                  ["score_from_us", "评分起点（微秒）"],
                ].map(([k, label]) => (
                  <Field key={k} label={t(label)}>
                    <input
                      type="number"
                      value={protocol[k]}
                      onChange={(e) => patch(k, Number(e.target.value))}
                    />
                  </Field>
                ))}
              </div>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={protocol.learning_during_probe}
                  onChange={(e) =>
                    patch("learning_during_probe", e.target.checked)
                  }
                />
                {t("探针期间继续学习（默认关闭）")}
              </label>
            </details>
          </>
        )}
        <p className="muted">
          {t(
            "感官编码和种子继承所选恢复点；总线映射、传播门槛与内核参数保持原值。每组含无探针对照。",
          )}
        </p>
        <ErrorBox error={error} />
        <Button
          variant="primary"
          disabled={create.isPending || project?.role === "viewer"}
          onClick={() => {
            setError(undefined);
            create.mutate();
          }}
        >
          {t("使用独立副本校准")}
        </Button>
      </section>
      <section className="panel">
        <h3>{t("已保存的校准")}</h3>
        <ErrorBox error={history.error} />
        <select
          aria-label={t("选择校准结果")}
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setRowIndex(1);
            setPage(0);
          }}
        >
          <option value="">{t("选择校准结果")}</option>
          {history.data?.rows.map((r: any) => (
            <option key={r.id} value={r.id}>
              {new Date(r.created_at).toLocaleString()} · {t(r.status)}
            </option>
          ))}
        </select>
        <div className="probe-pagination">
          <Button
            disabled={!historyPage}
            onClick={() => setHistoryPage(historyPage - 1)}
          >
            {t("上一页")}
          </Button>
          {historyPage + 1}
          <Button
            disabled={!history.data?.more}
            onClick={() => setHistoryPage(historyPage + 1)}
          >
            {t("下一页")}
          </Button>
        </div>
        {detail.data && (
          <p>
            {t("状态")}: {t(detail.data.status)} · {t("来源哈希")}:{" "}
            <code>{detail.data.source_hash}</code>
          </p>
        )}
        {detail.data?.status === "pending" && (
          <p>{t("等待支持校准的新版 worker；无需让原意识继续运行。")}</p>
        )}
        <ErrorBox
          error={
            detail.error ||
            result.error ||
            (detail.data?.error ? new Error(detail.data.error) : undefined)
          }
        />
        {result.isFetching && <Loading />}
      </section>
      {data && (
        <>
          <section className="panel">
            <h3>{t("可观测性与编码覆盖")}</h3>
            <p>
              {t("逐边门槛")}: {data.activation_floor} · {t("传播节律")}:{" "}
              {data.propagation_interval_us} μs
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("观察词")}</th>
                    <th>{t("编码通道")}</th>
                    <th>{t("专属评分通道")}</th>
                    <th>{t("保留幅值比例")}</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.mapping.coverage).map(
                    ([w, c]: [string, any]) => (
                      <tr key={w}>
                        <td>{w}</td>
                        <td>{c.channels}</td>
                        <td>{c.exclusive_channels || t("无法评分")}</td>
                        <td>{value(c.retained_weight_fraction)}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
            <p>
              {t(
                "共享通道和探针直接触达通道只从评分中排除；无专属通道显示无法评分，不记成零。",
              )}
            </p>
            <a
              className="button"
              href={`/api/v2${root}/artifacts/${detail.data.result.bundle_artifact_id}`}
            >
              {t("下载完整校准证据")}
            </a>{" "}
            <a
              className="button"
              href={`/api/v2${root}/artifacts/${detail.data.result.artifact_id}`}
            >
              {t("下载校准 JSON")}
            </a>
          </section>
          <section className="panel">
            <h3>{t("探针与无探针对照")}</h3>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    {[
                      "探针",
                      "强度",
                      "发出量",
                      "接收触达量",
                      "实际激活增量",
                      "已递送联想量",
                      ...data.protocol.terms,
                    ].map((x: string) => (
                      <th key={x}>{t(x)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r: any, i: number) => (
                    <tr key={r.id}>
                      <td>
                        <button
                          onClick={() => {
                            setRowIndex(i);
                            setPage(0);
                          }}
                          aria-pressed={i === rowIndex}
                        >
                          {r.cue ?? t("无探针对照")}
                        </button>
                      </td>
                      <td>{r.intensity}</td>
                      {[
                        r.transport.sent,
                        r.transport.received,
                        r.transport.activated,
                        r.delivered_signal_amount,
                      ].map((v, k) => (
                        <td key={k}>{value(v)}</td>
                      ))}
                      {data.protocol.terms.map((w: string) => (
                        <td key={w}>
                          {value(
                            r.cue === null
                              ? r.endpoint[w]
                              : r.net_endpoint?.[w],
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              {t(
                "探针评分减去无探针对照；传输量列是实际计数。到达信号可能汇合多条已过门槛的边，不能由此推断逐边拒绝次数。",
              )}
            </p>
          </section>
          {row && (
            <>
              <Curves key={`${selected}:${row.id}`} result={data} row={row} />
              <section className="panel">
                <h3>{t("实际输入帧与通道幅值")}</h3>
                <p>
                  {row.cue ?? t("无探针对照")} · {row.intensity}
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        {["模拟时间（微秒）", "通道", "原始幅值", "帧强度"].map(
                          (x) => (
                            <th key={x}>{t(x)}</th>
                          ),
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {channels
                        .slice(page * 40, page * 40 + 40)
                        .map((c: any, i: number) => (
                          <tr key={i}>
                            <td>{c.time_us}</td>
                            <td>{c.channel}</td>
                            <td>{value(c.amplitude)}</td>
                            <td>{c.intensity}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                <Button disabled={!page} onClick={() => setPage(page - 1)}>
                  {t("上一页")}
                </Button>{" "}
                {page + 1}{" "}
                <Button
                  disabled={(page + 1) * 40 >= channels.length}
                  onClick={() => setPage(page + 1)}
                >
                  {t("下一页")}
                </Button>
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
