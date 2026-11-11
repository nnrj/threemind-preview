import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t } from "./i18n";
import { Button, ErrorBox, Field } from "./ui";

export type EcologySelection = { id: string; checkpoint: string };

export default function EcologySource({
  base,
  value,
  change,
}: {
  base: string;
  value: EcologySelection;
  change: (value: EcologySelection) => void;
}) {
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [before, setBefore] = useState<number | null>(null);
  const list = useQuery({
    queryKey: ["report-ecology-list", base, q, offset],
    queryFn: () =>
      api<any>(`${base}/ecologies?q=${encodeURIComponent(q)}&offset=${offset}`),
  });
  const snapshots = useQuery({
    queryKey: ["report-ecology-checkpoints", base, value.id, before],
    queryFn: () =>
      api<any>(
        `${base}/ecologies/${value.id}/checkpoints${before ? `?before=${before}` : ""}`,
      ),
    enabled: !!value.id,
  });
  return (
    <>
      <Field label={t("搜索生态训练")}>
        <input
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setOffset(0);
          }}
        />
      </Field>
      <Field label={t("生态训练")}>
        <select
          value={value.id}
          onChange={(event) => {
            change({ id: event.target.value, checkpoint: "" });
            setBefore(null);
          }}
        >
          <option value="">{t("请选择")}</option>
          {value.id &&
            !list.data?.rows.some((row: any) => row.id === value.id) && (
              <option value={value.id}>
                {t("当前选择")}: {value.id}
              </option>
            )}
          {list.data?.rows.map((row: any) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      </Field>
      <div className="report-inline">
        <Button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 30))}
        >
          {t("上一页")}
        </Button>
        <Button
          disabled={!list.data?.more}
          onClick={() => setOffset(offset + 30)}
        >
          {t("下一页")}
        </Button>
      </div>
      <Field label={t("固定种群恢复点")}>
        <select
          disabled={!value.id}
          value={value.checkpoint}
          onChange={(event) =>
            change({ ...value, checkpoint: event.target.value })
          }
        >
          <option value="">{t("提交采集时的最新恢复点")}</option>
          {value.checkpoint &&
            !snapshots.data?.rows.some(
              (row: any) => row.id === value.checkpoint,
            ) && (
              <option value={value.checkpoint}>
                {t("当前选择")}: {value.checkpoint}
              </option>
            )}
          {snapshots.data?.rows.map((row: any) => (
            <option key={row.id} value={row.id}>
              r{row.revision} · {row.time_us} μs
            </option>
          ))}
        </select>
      </Field>
      <div className="report-inline">
        <Button disabled={!before} onClick={() => setBefore(null)}>
          {t("最新恢复点")}
        </Button>
        <Button
          disabled={!snapshots.data?.more}
          onClick={() => setBefore(snapshots.data.rows.at(-1).revision)}
        >
          {t("更早恢复点")}
        </Button>
      </div>
      <p className="hint">
        {t(
          "采集完整种群，包含未繁殖和已死亡个体。身体数据属于物理结算时点，可能领先意识时间；共处环境和共用祖先不等于独立重复实验。",
        )}
      </p>
      <ErrorBox error={list.error || snapshots.error} />
    </>
  );
}
