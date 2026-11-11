import { t } from "./i18n";
import { lazy, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, RefreshCw, Settings2 } from "lucide-react";
import { api, numberLabel, type Run } from "./api";
import { Button, Empty, ErrorBox, Field, Loading, Metric } from "./ui";
const Graph = lazy(() => import("./Graph"));

type Checkpoint = {
  id: string;
  revision: number;
  time_us: string;
  state_hash: string;
};
type History = { rows: Checkpoint[]; more: boolean; next: number | null };
type Geometry = {
  checkpoint_id: string;
  revision: number;
  time_us: string;
  state_time_us: string;
  state_hash: string;
  dynamics: string;
  supported: boolean;
  total_nodes: number;
  total_edges: number;
  summary: null | {
    seed: number;
    coordinate_rule: string;
    parameters: {
      spatial_embedding: boolean;
      spatial_dimensions: number;
      neighborhood_enabled: boolean;
      spatial_radius: number;
      spatial_competition_rate: number;
    };
    neighbor_edges: number | null;
    clusters: number | null;
    isolated_nodes: number | null;
  };
  nodes: {
    id: number;
    position: number[];
    cluster: number;
    activation: number;
  }[];
  edges: {
    source: number;
    target: number;
    distance: number;
    within_radius: boolean;
    weight: number;
  }[];
  nodes_more: boolean;
  nodes_next: number;
  edges_more: boolean;
  edges_next: number;
};

export default function SpatialPanel({
  project,
  base,
  run,
  configure,
}: {
  project: string;
  base: string;
  run: Run;
  configure: () => void;
}) {
  const [before, setBefore] = useState<(number | null)[]>([null]);
  const [checkpoint, setCheckpoint] = useState("");
  const [nodePages, setNodePages] = useState([-1]),
    [edgePages, setEdgePages] = useState([0]);
  const [start, setStart] = useState("0"),
    [until, setUntil] = useState("");
  const [filter, setFilter] = useState({ start: "0", until: "" }),
    [error, setError] = useState("");
  const [axes, setAxes] = useState<string[] | null>(null);
  const query = new URLSearchParams({ after_us: filter.start });
  if (filter.until) query.set("until_us", filter.until);
  if (before.at(-1) !== null) query.set("before", String(before.at(-1)));
  const history = useQuery({
    queryKey: ["spatial-checkpoints", base, query.toString()],
    queryFn: () => api<History>(`${base}/checkpoint-history?${query}`),
    refetchOnWindowFocus: false,
    gcTime: 0,
  });
  useEffect(() => {
    if (!checkpoint && history.data?.rows[0])
      setCheckpoint(history.data.rows[0].id);
  }, [checkpoint, history.data]);
  const evidence = useQuery({
    queryKey: ["spatial", base, checkpoint, nodePages.at(-1), edgePages.at(-1)],
    queryFn: () =>
      api<Geometry>(
        `${base}/spatial?checkpoint_id=${checkpoint}&node_after=${nodePages.at(-1)}&edge_after=${edgePages.at(-1)}`,
      ),
    enabled: !!checkpoint,
    placeholderData: (previous) =>
      previous?.checkpoint_id === checkpoint ? previous : undefined,
    refetchOnWindowFocus: false,
    gcTime: 0,
  });
  const result = evidence.data,
    summary = result?.summary;
  const dimensions = summary?.parameters.spatial_dimensions ?? 3;
  const projection =
    axes ?? [0, 1, 2].map((n) => (n < dimensions ? String(n) : "-1"));
  const select = (value: string) => {
    setCheckpoint(value);
    setNodePages([-1]);
    setEdgePages([0]);
    setAxes(null);
  };
  return (
    <div className="spatial-page" role="region" aria-label={t("因果空间基底")}>
      <section className="panel resource-panel">
        <div className="panel-heading">
          <div>
            <h2>{t("因果空间实验")}</h2>
            <p>{t("检查实际模型使用的发育几何、已有连接的距离与空间邻域。")}</p>
          </div>
          <Button onClick={configure}>
            <Settings2 size={15} />
            {t("配置空间参数")}
          </Button>
        </div>
        <p className="notice">
          {t(
            "因果空间默认关闭。开启后，它会参与模型演化；此处的坐标来自明确的种子先验，不代表网络自发形成了空间。图形旋转、2D／3D 切换与投影轴选择只改变观察。",
          )}
        </p>
        <form
          className="resource-filters"
          onSubmit={(e) => {
            e.preventDefault();
            if (
              !/^\d+$/.test(start) ||
              (until && (!/^\d+$/.test(until) || BigInt(until) < BigInt(start)))
            ) {
              setError(t("请输入非负整数模拟时间，结束时间不能早于起始时间。"));
              return;
            }
            setError("");
            setFilter({ start, until });
            setBefore([null]);
            select("");
          }}
        >
          <Field label={t("检查点起始时间（μs）")}>
            <input
              value={start}
              inputMode="numeric"
              onChange={(e) => setStart(e.target.value)}
            />
          </Field>
          <Field label={t("检查点结束时间（μs）")}>
            <input
              value={until}
              inputMode="numeric"
              onChange={(e) => setUntil(e.target.value)}
              placeholder={t("不限")}
            />
          </Field>
          <Button type="submit">{t("筛选检查点")}</Button>
          <Button
            onClick={async () => {
              const data = await history.refetch();
              select(data.data?.rows[0]?.id ?? "");
            }}
          >
            <RefreshCw size={15} />
            {t("刷新当前组")}
          </Button>
        </form>
        <Field label={t("空间检查点")}>
          <select
            aria-label={t("空间检查点")}
            value={checkpoint}
            onChange={(e) => select(e.target.value)}
            disabled={!history.data?.rows.length}
          >
            <option value="" disabled>
              {t("选择已提交的检查点")}
            </option>
            {history.data?.rows.map((c) => (
              <option key={c.id} value={c.id}>
                r{c.revision} · {c.time_us} μs · {c.state_hash.slice(0, 10)}
              </option>
            ))}
          </select>
        </Field>
        <div className="pagination">
          <Button
            disabled={before.length === 1}
            onClick={() => {
              setBefore((p) => p.slice(0, -1));
              select("");
            }}
          >
            {t("较新检查点")}
          </Button>
          <span>
            {t("第 {page} 组，每组最多 50 个", { page: before.length })}
          </span>
          <Button
            disabled={!history.data?.more}
            onClick={() => {
              setBefore((p) => [...p, history.data!.next]);
              select("");
            }}
          >
            {t("较旧检查点")}
          </Button>
        </div>
        <p className="footnote">
          {t(
            "固定检查点后，表格、图像与导出都使用同一份模型和参数。当前检查点列表不会自动跟随后台运行；可刷新当前组或按时间查找旧版本。",
          )}
        </p>
        <ErrorBox error={error || history.error || evidence.error} />
        {(history.isPending || (!!checkpoint && evidence.isPending)) && (
          <Loading />
        )}
        {!history.isPending && !history.data?.rows.length && (
          <Empty
            title={t("没有匹配的检查点")}
            detail={t("运行产生检查点后可在此查看，或扩大时间筛选范围。")}
          />
        )}
        {result && !result.supported && (
          <Empty
            title={t("此旧版本尚无因果空间机制")}
            detail={t(
              "可在普通网络观察页查看投影；需要空间实验时，暂停配置并显式启用空间基底。",
            )}
          />
        )}
        {summary && (
          <>
            <div className="metrics-grid">
              <Metric
                label={t("基底维数")}
                value={
                  summary.parameters.spatial_embedding
                    ? String(dimensions)
                    : "未启用"
                }
                detail={t("固定种子 {value0}", {
                  value0: String(summary.seed),
                })}
              />
              <Metric
                label={t("半径内有向连接")}
                value={String(summary.neighbor_edges ?? "—")}
                detail={t("全部已有连接 {value0}", {
                  value0: String(result!.total_edges),
                })}
              />
              <Metric
                label={t("邻域连通分组")}
                value={String(summary.clusters ?? "—")}
                detail={t("弱连通，含孤立节点")}
              />
              <Metric
                label={t("邻域孤立节点")}
                value={String(summary.isolated_nodes ?? "—")}
                detail={t("全部节点 {value0}", {
                  value0: String(result!.total_nodes),
                })}
              />
            </div>
            <p className="footnote">
              {t("邻域约束")}
              {summary.parameters.neighborhood_enabled ? t("开启") : t("关闭")}
              {t(" · 半径")} {summary.parameters.spatial_radius}
              {t(" 个基底坐标单位 · 竞争速率")}{" "}
              {summary.parameters.spatial_competition_rate}
              {t("／模拟秒。缩小半径不会自动删除已有连接。")}
            </p>
          </>
        )}
        {result && (
          <p className="footnote mono">
            r{result.revision}
            {t(" · 模拟时间 ")}
            {result.time_us}
            {t(" μs · 状态结算")} {result.state_time_us} μs
            <br />
            {result.state_hash}
          </p>
        )}
        <Link className="text-link" to="/docs?doc=docs%2Fzh%2Fv2-spatial.md">
          {t("坐标规则、距离传播、竞争公式与版本边界")}
        </Link>
      </section>
      {summary?.parameters.spatial_embedding && result && (
        <>
          <section className="panel resource-panel">
            <div className="panel-heading">
              <div>
                <h2>{t("因果坐标的观察投影")}</h2>
                <p>
                  {t("显示当前选定的坐标轴；距离与邻域判断始终使用全部 ")}
                  {dimensions} {t("维。连线都是模型已经形成的连接。")}
                </p>
              </div>
            </div>
            <div className="resource-filters">
              {["X", "Y", "Z"].map((label, index) => (
                <Field
                  key={t(label)}
                  label={t("{value0} 投影轴", { value0: String(label) })}
                >
                  <select
                    aria-label={t("{value0} 投影轴", { value0: String(label) })}
                    value={projection[index]}
                    onChange={(e) =>
                      setAxes(
                        projection.map((v, i) =>
                          i === index ? e.target.value : v,
                        ),
                      )
                    }
                  >
                    <option value="-1">{t("隐藏此轴")}</option>
                    {Array.from({ length: dimensions }, (_, i) => (
                      <option key={i} value={String(i)}>
                        {t("第 {axis} 维", { axis: i + 1 })}
                      </option>
                    ))}
                  </select>
                </Field>
              ))}
            </div>
            <Graph
              project={project}
              run={run.id}
              polling={false}
              revision={result.revision}
              endpoint={`/api/v2${base}/spatial/graph?checkpoint_id=${checkpoint}&axes=${projection.join(",")}`}
            />
            <p className="footnote">
              {t(
                "显示数量与形状使用本设备的显示设置；完整坐标与连接距离可在下面导出。画面颜色对应所选检查点的已结算数值状态。",
              )}
            </p>
          </section>
          <section className="panel resource-panel">
            <div className="panel-heading">
              <div>
                <h2>{t("坐标、分组与连接距离")}</h2>
                <p>
                  {t(
                    "按节点身份或连接身份分页；导出包含所选检查点的全部记录。",
                  )}
                </p>
              </div>
              <div className="actions">
                {[
                  ["nodes", "csv", "节点坐标 CSV"],
                  ["edges", "csv", "连接距离 CSV"],
                  ["all", "jsonl", "完整几何 JSONL"],
                ].map(([records, format, label]) => (
                  <a
                    key={records}
                    className="button"
                    href={`/api/v2${base}/spatial/export?checkpoint_id=${checkpoint}&records=${records}&format=${format}`}
                  >
                    <Download size={14} />
                    {t(label)}
                  </a>
                ))}
              </div>
            </div>
            <div className="table-scroll spatial-history">
              <table>
                <thead>
                  <tr>
                    <th>{t("节点")}</th>
                    <th>{t("坐标")}</th>
                    <th>{t("邻域分组")}</th>
                    <th>{t("激活")}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.nodes.map((n) => (
                    <tr key={n.id}>
                      <td>{n.id}</td>
                      <td>
                        <details>
                          <summary>
                            {n.position
                              .slice(0, 3)
                              .map((v) => numberLabel(v, 4))
                              .join(", ")}
                            {dimensions > 3
                              ? t(" … 共 {value0} 维", {
                                  value0: String(dimensions),
                                })
                              : ""}
                          </summary>
                          <pre>{JSON.stringify(n.position, null, 2)}</pre>
                        </details>
                      </td>
                      <td>{n.cluster}</td>
                      <td>{numberLabel(n.activation, 5)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <Button
                disabled={nodePages.length === 1}
                onClick={() => setNodePages((p) => p.slice(0, -1))}
              >
                {t("上一组节点")}
              </Button>
              <span>{t("第 {page} 页", { page: nodePages.length })}</span>
              <Button
                disabled={!result.nodes_more}
                onClick={() => setNodePages((p) => [...p, result.nodes_next])}
              >
                {t("下一组节点")}
              </Button>
            </div>
            <div className="table-scroll spatial-history">
              <table>
                <thead>
                  <tr>
                    <th>{t("源 → 目标")}</th>
                    <th>{t("完整维度距离")}</th>
                    <th>{t("位于半径内")}</th>
                    <th>{t("权重")}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.edges.map((e) => (
                    <tr key={`${e.source}:${e.target}`}>
                      <td>
                        {e.source} → {e.target}
                      </td>
                      <td>{numberLabel(e.distance, 6)}</td>
                      <td>{e.within_radius ? t("是") : t("否")}</td>
                      <td>{numberLabel(e.weight, 5)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <Button
                disabled={edgePages.length === 1}
                onClick={() => setEdgePages((p) => p.slice(0, -1))}
              >
                {t("上一组连接")}
              </Button>
              <span>{t("第 {page} 页", { page: edgePages.length })}</span>
              <Button
                disabled={!result.edges_more}
                onClick={() => setEdgePages((p) => [...p, result.edges_next])}
              >
                {t("下一组连接")}
              </Button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
