import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t } from "./i18n";
import { Button, ErrorBox, Field } from "./ui";

export default function EvolutionSource({
  base,
  value,
  change,
  available,
}: any) {
  const [q, setQ] = useState(""),
    [offset, setOffset] = useState(0);
  const list = useQuery({
    queryKey: ["report-evolution-list", base, q, offset],
    queryFn: () =>
      api<any>(
        `${base}/evolutions?q=${encodeURIComponent(q)}&offset=${offset}`,
      ),
  });
  const current = useQuery({
    queryKey: ["report-evolution-protocol", base, value.id],
    queryFn: () => api<any>(`${base}/evolutions/${value.id}/protocol`),
    enabled: !!value.id,
    staleTime: Infinity,
  });
  useEffect(() => {
    available(current.data?.protocol.criteria.map((c: any) => c.metric) ?? []);
  }, [current.data, available]);
  return (
    <>
      <Field label={t("搜索多代实验")}>
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
        />
      </Field>
      <Field label={t("多代实验")}>
        <select
          value={value.id}
          onChange={(e) =>
            change({ ...value, id: e.target.value, generation: 0 })
          }
        >
          <option value="">{t("请选择")}</option>
          {value.id && !list.data?.rows.some((r: any) => r.id === value.id) && (
            <option value={value.id}>
              {t("当前选择")}: {value.id}
            </option>
          )}
          {list.data?.rows.map((r: any) => (
            <option key={r.id} value={r.id}>
              {r.name}
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
      <Field label={t("查看代次")}>
        <select
          value={value.generation}
          onChange={(e) =>
            change({ ...value, generation: Number(e.target.value) })
          }
        >
          {Array.from(
            { length: current.data?.protocol.generations ?? 1 },
            (_, i) => (
              <option key={i} value={i}>
                {i + 1}
              </option>
            ),
          )}
        </select>
      </Field>
      <Field label={t("多代结果阶段")}>
        <select
          value={value.stage}
          onChange={(e) => change({ ...value, stage: e.target.value })}
        >
          <option value="selection">{t("所有候选的筛选汇总")}</option>
          <option value="evaluation">{t("逐候选、逐筛选环境结果")}</option>
          <option value="verification">{t("最终独立验证结果")}</option>
        </select>
      </Field>
      <p className="hint">
        {t(
          "仅采集完整固定的代次与阶段，包含未入选候选。共用祖先和重复环境不算独立演化实验。",
        )}
      </p>
      <ErrorBox error={list.error || current.error} />
    </>
  );
}
