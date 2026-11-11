import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, numberLabel } from "./api";
import { t, messageKeys } from "./i18n";
import { Button, CodeEditor, ErrorBox, Loading } from "./ui";

const expenses = messageKeys({
  maintenance_spent: "身体维持支出",
  effort_spent: "身体动作支出",
  reproduction_spent: "繁殖额外支出",
});
const totals = messageKeys({
  initial_external: "身体资源初始外部输入",
  regenerated: "身体资源累计再生",
  remaining: "身体资源账本剩余总量",
  spent: "身体资源累计支出",
});

export default function EcologyLedger({ root, checkpoint }: any) {
  const [open, setOpen] = useState(false);
  const [cursors, setCursors] = useState<string[]>([]);
  const after = cursors.at(-1) ?? "";
  const pools = useQuery({
    queryKey: ["ecology-resource-pools", root, checkpoint.id, after],
    queryFn: () =>
      api<any>(
        `${root}/resource-pools?checkpoint_id=${checkpoint.id}${after ? `&after=${encodeURIComponent(after)}` : ""}`,
      ),
    enabled: open,
  });
  const balance = checkpoint.observation.population.resource_balance;
  return (
    <details
      className="ecology-group"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>{t("资源收支账本")}</summary>
      <p className="hint">
        {t(
          "初始输入 + 再生 = 剩余 + 支出。单位是身体资源记账单位，不是内核能量或奖励。",
        )}
      </p>
      <div className="ecology-summary">
        {Object.entries(totals).map(([key, label]) => (
          <div key={key}>
            <span>{t(label)}</span>
            <strong title={String(balance[key])}>
              {numberLabel(balance[key])}
            </strong>
          </div>
        ))}
      </div>
      <div className="ecology-summary">
        {Object.entries(expenses).map(([key, label]) => (
          <div key={key}>
            <span>{t(label)}</span>
            <strong title={String(checkpoint.ledger[key])}>
              {numberLabel(checkpoint.ledger[key])}
            </strong>
          </div>
        ))}
      </div>
      <p>
        {t("共 {count} 个历史栖息地；每页最多 30 个，失效身体的库存仍保留。", {
          count: checkpoint.ledger.pool_count,
        })}
      </p>
      {pools.isLoading && open && <Loading />}
      {pools.data?.rows.map((row: any) => (
        <section className="ecology-group" key={row.habitat}>
          <h4>{row.habitat === "shared" ? t("共享世界") : row.habitat}</h4>
          {!Object.keys(row.resources).length && (
            <p className="hint">{t("此栖息地没有资源区域。")}</p>
          )}
          <div className="ecology-summary">
            {Object.entries(row.resources).map(([patch, amount]) => (
              <div key={patch}>
                <span>{patch}</span>
                <strong title={String(amount)}>
                  {numberLabel(amount as number)}
                </strong>
              </div>
            ))}
          </div>
        </section>
      ))}
      <div className="query-controls">
        <Button
          disabled={!cursors.length}
          onClick={() => setCursors(cursors.slice(0, -1))}
        >
          {t("上一页")}
        </Button>
        <Button
          disabled={!pools.data?.more || pools.isFetching}
          onClick={() =>
            setCursors([...cursors, pools.data.rows.at(-1).habitat])
          }
        >
          {t("下一页")}
        </Button>
      </div>
      <details>
        <summary>{t("查看账本摘要 JSON")}</summary>
        <CodeEditor
          readOnly
          value={JSON.stringify(checkpoint.ledger, null, 2)}
          onChange={() => {}}
          label={t("账本摘要 JSON")}
        />
      </details>
      <p className="footnote">
        {t("这里只分页显示库存；完整账本和所有个体保存在固定种群证据包中。")}
      </p>
      <ErrorBox error={pools.error} />
    </details>
  );
}
