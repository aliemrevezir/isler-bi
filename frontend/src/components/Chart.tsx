import ReactECharts from "echarts-for-react";
import { useMemo } from "react";
import type { ChartSpec } from "../lib/api";
import { useTheme } from "../lib/theme";

const PALETTE = [
  "#6366f1",
  "#22d3ee",
  "#f59e0b",
  "#10b981",
  "#ef4444",
  "#a855f7",
  "#ec4899",
  "#84cc16",
];

export default function Chart({ spec }: { spec: ChartSpec }) {
  const { theme } = useTheme();

  const option = useMemo(() => {
    const dark = theme === "dark";
    const axisColor = dark ? "#94a3b8" : "#64748b";
    const lineColor = dark ? "#1e293b" : "#e2e8f0";
    const textColor = dark ? "#f1f5f9" : "#1e293b";

    const hasDualAxis = spec.series.some(
      (s) => s.yAxisIndex === 1 || s.type === "line"
    );
    const needsDual = spec.series.some((s) => s.yAxisIndex === 1);

    const rotate = spec.x.length > 8 ? 35 : 0;

    return {
      color: PALETTE,
      backgroundColor: "transparent",
      title: {
        text: spec.title,
        left: 0,
        top: 0,
        textStyle: { fontSize: 14, fontWeight: 600, color: textColor },
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: dark ? "#0f172a" : "#ffffff",
        borderColor: lineColor,
        textStyle: { color: textColor },
      },
      legend: {
        top: 0,
        right: 0,
        textStyle: { color: axisColor },
        icon: "roundRect",
      },
      grid: {
        left: 8,
        right: needsDual ? 24 : 12,
        bottom: rotate ? 36 : 12,
        top: 48,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: spec.x,
        axisLine: { lineStyle: { color: lineColor } },
        axisLabel: { color: axisColor, rotate, interval: "auto" },
        axisTick: { show: false },
      },
      yAxis: needsDual
        ? [
            {
              type: "value",
              axisLabel: { color: axisColor },
              splitLine: { lineStyle: { color: lineColor } },
            },
            {
              type: "value",
              axisLabel: { color: axisColor },
              splitLine: { show: false },
            },
          ]
        : {
            type: "value",
            axisLabel: { color: axisColor },
            splitLine: { lineStyle: { color: lineColor } },
          },
      series: spec.series.map((s) => {
        const type = s.type || spec.type || "bar";
        return {
          name: s.name,
          type,
          data: s.data,
          yAxisIndex: s.yAxisIndex ?? 0,
          smooth: type === "line",
          showSymbol: type === "line" ? spec.x.length <= 30 : undefined,
          itemStyle: { borderRadius: type === "bar" ? [3, 3, 0, 0] : 0 },
          barMaxWidth: 40,
        };
      }),
      _dual: hasDualAxis,
    };
  }, [spec, theme]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <ReactECharts
        option={option}
        style={{ height: 360, width: "100%" }}
        notMerge
        opts={{ renderer: "canvas" }}
      />
    </div>
  );
}
