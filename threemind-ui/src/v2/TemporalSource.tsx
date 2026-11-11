import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, timeLabel } from "./api";
import { t } from "./i18n";
import { Field, ErrorBox } from "./ui";
import { classes } from "./readouts";

export type TemporalSelection = {
  mode?: "run" | "probe";
  calibration_id: string;
  window_ids: string[];
};
export default function TemporalSource({
  base,
  run,
  kind,
  value,
  onChange,
}: {
  base: string;
  run: string;
  kind: string;
  value: TemporalSelection;
  onChange: (v: TemporalSelection) => void;
}) {
  const mode = value.mode ?? "run";
  const [offset, setOffset] = useState(0);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const probes = useQuery({
    queryKey: ["report-temporal-probes", base, run, offset],
    enabled: !!run && mode === "probe",
    queryFn: () =>
      api(`${base}/runs/${run}/calibrations?mode=temporal&offset=${offset}`),
    gcTime: 0,
  });
  const probe = useQuery({
    queryKey: ["report-temporal-probe", base, value.calibration_id],
    enabled: !!value.calibration_id,
    queryFn: () => api(`${base}/calibrations/${value.calibration_id}/result`),
    gcTime: 0,
  });
  const windows = useQuery({
    queryKey: ["report-temporal-windows", base, run, cursors.at(-1)],
    enabled: !!run && mode === "run",
    queryFn: () =>
      api(
        `${base}/runs/${run}/readouts?kind=temporal_readout&limit=30${cursors.at(-1) ? `&before_id=${cursors.at(-1)}` : ""}`,
      ),
    gcTime: 0,
  });
  const choices =
    mode === "probe"
      ? (probe.data?.rows ?? [])
          .filter((r: any) => r.temporal)
          .map((r: any) => ({ ...r.temporal, cue: r.cue }))
      : (windows.data?.rows ?? []).map((r: any) => r.payload);
  return (
    <div className="form-grid">
      <Field label={t("时序来源")}>
        <select
          value={mode}
          onChange={(e) => {
            onChange({
              mode: e.target.value as "run" | "probe",
              calibration_id: "",
              window_ids: [],
            });
          }}
        >
          <option value="run">{t("意识持续活动的读出")}</option>
          <option value="probe">{t("独立时序实验")}</option>
        </select>
      </Field>
      {mode === "probe" && (
        <>
          <Field label={t("已完成的时序实验")}>
            <select
              value={value.calibration_id}
              onChange={(e) =>
                onChange({
                  mode: "probe",
                  calibration_id: e.target.value,
                  window_ids: [],
                })
              }
            >
              <option value="">{t("请选择")}</option>
              {probes.data?.rows?.map((r: any) => (
                <option key={r.id} value={r.id} disabled={r.status !== "done"}>
                  {r.id.slice(0, 8)} · {t(r.status)}
                </option>
              ))}
            </select>
          </Field>
          <div>
            <button
              className="text-link"
              disabled={!offset}
              onClick={() => setOffset((v) => Math.max(0, v - 20))}
            >
              {t("上一页")}
            </button>
            <button
              className="text-link"
              disabled={!probes.data?.more}
              onClick={() => setOffset((v) => v + 20)}
            >
              {t("下一页")}
            </button>
          </div>
        </>
      )}
      <Field
        label={t(
          kind === "temporal_series"
            ? "观察窗口（曲线须选择一个）"
            : "观察窗口（可选择全部）",
        )}
      >
        <select
          value={value.window_ids[0] ?? ""}
          onChange={(e) =>
            onChange({
              ...value,
              window_ids: e.target.value ? [e.target.value] : [],
            })
          }
        >
          <option value="">
            {t(
              kind === "temporal_series"
                ? "请选择"
                : "全部窗口（包括未完成记录）",
            )}
          </option>
          {choices.map((r: any) => (
            <option key={r.window_id} value={r.window_id}>
              {r.cue || r.source} · {timeLabel(r.start_us)} ·{" "}
              {t(classes[r.classification] ?? r.classification)} ·{" "}
              {r.window_id.slice(0, 8)}
            </option>
          ))}
        </select>
      </Field>
      {mode === "run" && (
        <div>
          <button
            className="text-link"
            disabled={cursors.length <= 1}
            onClick={() => setCursors((v) => v.slice(0, -1))}
          >
            {t("较新窗口")}
          </button>
          <button
            className="text-link"
            disabled={!windows.data?.more}
            onClick={() => setCursors((v) => [...v, windows.data.next])}
          >
            {t("更早窗口")}
          </button>
        </div>
      )}
      <ErrorBox error={windows.error ?? probes.error ?? probe.error} />
    </div>
  );
}
