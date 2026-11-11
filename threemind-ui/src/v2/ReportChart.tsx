import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, ScatterChart, BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { t, useLocale } from "./i18n";
import { usePreferences } from "./preferences";
import { eventPhases } from "./ReportEventTable";

echarts.use([
  LineChart,
  ScatterChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  SVGRenderer,
]);

export default function ReportChart({ block }: { block: any }) {
  const host = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.ECharts | null>(null);
  const locale = useLocale(),
    theme = usePreferences().theme;
  const histogramRows = block.chart === "histogram" ? block.data.rows : [];
  const low = histogramRows[0]?.lower ?? 0;
  const span = (histogramRows.at(-1)?.upper ?? low) - low;
  // An explicit offset keeps narrow distributions legible without rounding
  // different bins into the same label. Tooltips retain original boundaries.
  const histogramOffset = span > 0 && Math.abs(low) > span * 1000 ? low : 0;
  useEffect(() => {
    if (!host.current) return;
    const chart = echarts.init(host.current, undefined, { renderer: "svg" });
    instance.current = chart;
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(host.current);
    return () => {
      resize.disconnect();
      chart.dispose();
      instance.current = null;
    };
  }, []);
  useEffect(() => {
    if (!instance.current) return;
    const { rows, method } = block.data;
    const histogram = block.chart === "histogram",
      categorical = histogram || block.chart === "bar";
    const binned = method === "ordinal-bin-sample-mean-min-max/1";
    const events = method === "all-events-by-kind-and-phase/1";
    const first = rows[0]?.time_us ?? rows[0]?.from_us ?? "0";
    const seconds = (time: string) =>
      Number(BigInt(time) - BigInt(first)) / 1e6;
    const xs = rows.map((row: any) =>
      binned
        ? seconds(row.from_us) +
          Number(BigInt(row.through_us) - BigInt(row.from_us)) / 2e6
        : seconds(row.time_us ?? first),
    );
    const values = rows.map((row: any, i: number) =>
      categorical ? (histogram ? row.count : row.value) : [xs[i], row.value],
    );
    const series: any[] = [
      {
        name: histogram ? t("计数") : binned ? t("样本算术均值") : block.metric,
        type: categorical ? "bar" : block.chart,
        data: values,
        showSymbol: rows.length < 100,
        symbolSize: 5,
        connectNulls: false,
        barMaxWidth: 55,
        itemStyle: { color: "#368e7c" },
        lineStyle: { width: 2 },
      },
    ];
    if (binned) {
      for (const [key, title] of [
        ["minimum", t("最小值")],
        ["maximum", t("最大值")],
      ]) {
        series.push({
          name: title,
          type: "line",
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 1, type: "dashed", color: "#a78055" },
          data: rows.map((r: any, i: number) => [xs[i], r[key]]),
        });
      }
      series.push({
        name: t("含缺失值的显示分组"),
        type: "scatter",
        symbol: "triangle",
        symbolSize: 9,
        itemStyle: { color: "#b45f50" },
        data: rows.flatMap((r: any, i: number) =>
          r.total > r.count && r.value !== null ? [[xs[i], r.value]] : [],
        ),
      });
    }
    const zoom = (
      instance.current.getOption()?.dataZoom as
        { start?: number; end?: number }[] | undefined
    )?.map(({ start, end }) => ({ start, end }));
    const ink =
      getComputedStyle(host.current!).getPropertyValue("--text").trim() ||
      (theme === "dark" ? "#ddd" : "#34433c");
    instance.current.setOption(
      {
        animation: false,
        textStyle: { color: ink },
        grid: {
          top: binned ? 55 : 30,
          left: events ? 155 : 65,
          right: histogram ? 55 : 24,
          bottom: 90,
        },
        tooltip: {
          trigger: categorical ? "item" : "axis",
          renderMode: "richText",
          ...(histogram
            ? {
                formatter: (item: any) => {
                  const row = rows[item.dataIndex];
                  return `${block.metric}\n${String(row.lower)} – ${String(row.upper)}\n${t("计数")}: ${row.count}`;
                },
              }
            : {}),
        },
        legend: { show: binned, type: "scroll", textStyle: { color: ink } },
        xAxis: events
          ? {
              type: "value",
              name: t("已记录事件数"),
              nameLocation: "middle",
              nameGap: 35,
              minInterval: 1,
              axisLabel: { color: ink },
            }
          : {
              type: categorical ? "category" : "value",
              name: categorical
                ? ""
                : `${t("相对首个样本的时间（s）")} · ${first} μs`,
              nameLocation: "middle",
              nameGap: 35,
              data: categorical
                ? rows.map((r: any) =>
                    histogram
                      ? `${Number((r.lower - histogramOffset).toPrecision(6))}\n– ${Number((r.upper - histogramOffset).toPrecision(6))}`
                      : r.label,
                  )
                : undefined,
              axisLabel: { color: ink, hideOverlap: true },
              axisLine: { lineStyle: { color: ink } },
            },
        yAxis: events
          ? {
              type: "category",
              inverse: true,
              data: rows.map(
                (r: any) =>
                  `${r.label}\n${t(eventPhases[r.phase as keyof typeof eventPhases] ?? r.phase)}`,
              ),
              axisLabel: {
                color: ink,
                width: 140,
                overflow: "truncate",
                interval: 0,
              },
            }
          : {
              type: "value",
              name: histogram ? t("计数") : block.data.unit,
              axisLabel: { color: ink },
              splitLine: { lineStyle: { opacity: 0.15 } },
            },
        dataZoom:
          events && rows.length <= 12
            ? []
            : [
                { type: "inside", ...(events ? { yAxisIndex: 0 } : {}) },
                {
                  type: "slider",
                  height: 14,
                  bottom: 8,
                  ...(events ? { yAxisIndex: 0, orient: "horizontal" } : {}),
                },
              ],
        series,
      },
      true,
    );
    if (zoom?.length) instance.current.setOption({ dataZoom: zoom });
  }, [block, locale, theme, histogramOffset]);
  return (
    <>
      <div
        className="report-chart"
        style={
          block.data.method === "all-events-by-kind-and-phase/1"
            ? { height: Math.max(360, block.data.rows.length * 42 + 100) }
            : undefined
        }
        ref={host}
        role="img"
        aria-label={block.title || `${block.metric} · ${block.chart}`}
      />
      {!!histogramOffset && (
        <p className="hint report-histogram-offset">
          {t("横轴为相对 {origin} 的偏移量；悬停或点选可查看原始分组边界。", {
            origin: String(histogramOffset),
          })}
        </p>
      )}
    </>
  );
}
