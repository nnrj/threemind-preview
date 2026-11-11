import { t, messageKeys } from "./i18n";
import { numberLabel } from "./api";

export const assessmentStates = messageKeys({
  satisfied: "符合",
  not_satisfied: "不符合",
  undetermined: "未判定",
});
export const assessmentOperators: Record<string, string> = {
  gt: ">",
  gte: "≥",
  lt: "<",
  lte: "≤",
  eq: "=",
};

export default function AssessmentSummary({
  value,
  metrics = [],
}: {
  value: any;
  metrics?: any[];
}) {
  return (
    <section className="assessment-summary" aria-label={t("固定规则判定")}>
      <p className="footnote">
        {t(
          "所有已声明试验均计入分母。比例上下界包含未判定结果的可能性，不是置信区间，也不预测未知环境。",
        )}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t("规则与目标")}</th>
              <th>{t("判定")}</th>
              <th>{t("符合 / 不符合 / 未判定")}</th>
              <th>{t("比例上下界")}</th>
            </tr>
          </thead>
          <tbody>
            {value.criteria.map((item: any) => (
              <tr key={item.criterion.id}>
                <td>
                  <strong>{item.criterion.id}</strong>
                  <div>
                    {t(
                      metrics.find((m) => m.id === item.criterion.metric)
                        ?.label ?? item.criterion.metric,
                    )}{" "}
                    {assessmentOperators[item.criterion.operator]}{" "}
                    {numberLabel(item.criterion.threshold, 6)}
                  </div>
                  <small>
                    {t("要求比例")}{" "}
                    {numberLabel(item.criterion.required_fraction * 100)}%
                  </small>
                </td>
                <td>
                  {t(
                    assessmentStates[
                      item.status as keyof typeof assessmentStates
                    ],
                  )}
                </td>
                <td>
                  {item.satisfied} / {item.not_satisfied} / {item.undetermined}
                  <div>
                    <small>
                      {t("共 {count} 个试验", { count: item.total })}
                    </small>
                  </div>
                </td>
                <td>
                  {numberLabel(
                    item.fraction_lower_bound == null
                      ? null
                      : item.fraction_lower_bound * 100,
                  )}
                  % —{" "}
                  {numberLabel(
                    item.fraction_upper_bound == null
                      ? null
                      : item.fraction_upper_bound * 100,
                  )}
                  %
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
