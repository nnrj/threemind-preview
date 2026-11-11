import { t } from "./i18n";

export default function EcologyInterpretation({ value }: { value: any }) {
  if (!value) return null;
  const groups: [string, any[]][] = [
    [t("分析摘要"), [value.summary]],
    [t("观察说明"), value.observations],
    [t("待验证假设"), value.hypotheses],
    [t("后续研究建议"), value.suggestions],
  ];
  return (
    <section className="ecology-ai-text">
      {groups.map(
        ([label, items]) =>
          items.length > 0 && (
            <div key={label}>
              <h4>{label}</h4>
              {items.map((item: any, i: number) => (
                <div key={i}>
                  <p>{item.text}</p>
                  <small className="hash-value">
                    {item.source_refs.join(" · ")}
                  </small>
                </div>
              ))}
            </div>
          ),
      )}
      <h4>{t("证据局限")}</h4>
      <ul>
        {value.limitations.map((text: string, i: number) => (
          <li key={i}>{text}</li>
        ))}
      </ul>
    </section>
  );
}
