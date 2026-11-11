import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { t } from "./i18n";
import { Button, ErrorBox, Field } from "./ui";

export default function AssessmentSource({
  base,
  value,
  change,
}: {
  base: string;
  value: string;
  change: (id: string) => void;
}) {
  const [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0);
  const rows = useQuery({
    queryKey: ["report-assessments", base, query, offset],
    queryFn: () =>
      api(
        `${base}/assessments?q=${encodeURIComponent(query)}&offset=${offset}`,
      ),
  });
  return (
    <>
      <Field label={t("检索独立评估")}>
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOffset(0);
            change("");
          }}
        />
      </Field>
      <Field label={t("独立评估批次")}>
        <select
          aria-label={t("独立评估批次")}
          value={value}
          onChange={(e) => change(e.target.value)}
        >
          <option value="">{t("请选择")}</option>
          {rows.data?.rows.map((r: any) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </Field>
      <div className="query-controls">
        <Button
          type="button"
          disabled={!offset}
          onClick={() => {
            setOffset(offset - 30);
            change("");
          }}
        >
          {t("上一页")}
        </Button>
        <Button
          type="button"
          disabled={!rows.data?.more}
          onClick={() => {
            setOffset(offset + 30);
            change("");
          }}
        >
          {t("下一页")}
        </Button>
      </div>
      <p className="footnote">
        {t(
          "评估来源包含全部已声明试验。当前未完成或失败的试验保留未判定，不会只采集成功个体。",
        )}
      </p>
      <ErrorBox error={rows.error} />
    </>
  );
}
