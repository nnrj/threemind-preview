import { t, useLocale } from "./i18n";
import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  ToolboxComponent,
  MarkAreaComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  ToolboxComponent,
  MarkAreaComponent,
  SVGRenderer,
]);

export default function Chart({
  rows,
  metric = "activation",
  height = 260,
  series,
  phases = [],
  title: titleOverride,
  step = false,
  topPadding = 0,
  fitTimeRange = false,
}: {
  rows: any[];
  metric?: string;
  height?: number;
  series?: { name: string; rows: any[] }[];
  phases?: { name: string; duration_s: number }[];
  title?: string;
  step?: boolean;
  topPadding?: number;
  fitTimeRange?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null),
    chart = useRef<echarts.ECharts | null>(null);
  const language = useLocale();
  const previousLanguage = useRef(language);
  useEffect(() => {
    if (!host.current) return;
    const instance = echarts.init(host.current, undefined, { renderer: "svg" });
    chart.current = instance;
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      instance.dispose();
      chart.current = null;
    };
  }, []);
  useEffect(() => {
    const extraTitles: Record<string, string> = {
      mean_activation: "节点平均激活（0–1）",
      saturated_fraction: "饱和节点比例（激活 ≥ 0.95）",
      active_fraction: "活动节点比例（高于内核阈值）",
      edge_density: "有向连接密度（0–1）",
      energy_reserve: "能量储备（实验单位）",
      energy_consumed: "累计能量消耗（实验单位）",
      energy_supplied: "累计接受供给（实验单位）",
      energy_unserved: "累计未满足需求（实验单位）",
    };
    const title =
      titleOverride ??
      t(
        extraTitles[metric] ??
          (metric === "activation"
            ? "总激活量（归一化单位）"
            : metric === "edges"
              ? "有向连接数"
              : metric === "inhibition"
                ? "总抑制势（归一化单位）"
                : "平均连接权重"),
      );
    // Changing UI language must not discard an in-progress inspection range.
    const zoom =
      previousLanguage.current !== language
        ? (
            chart.current?.getOption().dataZoom as
              { start?: number; end?: number }[] | undefined
          )?.map(({ start, end }) => ({ start, end }))
        : undefined;
    previousLanguage.current = language;
    let phaseEnd = 0;
    const areas = phases.map((p) => {
      const start = phaseEnd;
      phaseEnd += p.duration_s;
      return [{ name: p.name, xAxis: start }, { xAxis: phaseEnd }];
    });
    chart.current?.setOption(
      {
        animation: false,
        color: ["#3a9181", "#b27445", "#7274b4", "#bd637a"],
        legend: { show: !!series, top: 28, type: "scroll" },
        tooltip: { trigger: "axis" },
        grid: {
          left: 66,
          right: 20,
          top: (series ? 76 : 42) + topPadding,
          bottom: 74,
        },
        xAxis: {
          type: "value",
          min: fitTimeRange ? "dataMin" : undefined,
          max: fitTimeRange ? "dataMax" : undefined,
          name: t("模拟时间（s）"),
          nameLocation: "middle",
          nameGap: 32,
          axisLine: { lineStyle: { color: "#b4c3ba" } },
          splitLine: { show: false },
        },
        yAxis: {
          type: "value",
          name: title,
          nameTextStyle: {
            align: "left",
            padding: [0, 0, 8, -45],
            color: "#6c7d73",
          },
          splitLine: { lineStyle: { color: "#e9eee9" } },
        },
        dataZoom: [
          { type: "inside" },
          {
            type: "slider",
            height: 15,
            bottom: 0,
            borderColor: "transparent",
            fillerColor: "#3a918122",
          },
        ],
        series: (series ?? [{ name: title, rows }]).map((s, i) => ({
          name: s.name,
          type: "line",
          step: step ? "end" : false,
          showSymbol: false,
          lineStyle: { width: 2 },
          areaStyle: { opacity: series ? 0 : 0.055 },
          markArea:
            i === 0 && areas.length
              ? {
                  silent: true,
                  itemStyle: {
                    color: "#3a918108",
                    borderWidth: 1,
                    borderColor: "#8d9e9728",
                  },
                  label: { color: "#77847b", position: "insideTop" },
                  data: areas,
                }
              : undefined,
          connectNulls: false,
          data: s.rows.map((row) => [
            Number(row.time_us) / 1e6,
            row[metric] ?? null,
          ]),
        })),
      },
      true,
    );
    if (zoom?.length) chart.current?.setOption({ dataZoom: zoom });
  }, [
    rows,
    metric,
    series,
    phases,
    titleOverride,
    step,
    topPadding,
    fitTimeRange,
    language,
  ]);
  return (
    <div
      ref={host}
      style={{ height }}
      role="img"
      aria-label={t("{value0} 随模拟时间变化的曲线", {
        value0: String(titleOverride ?? metric),
      })}
    />
  );
}
