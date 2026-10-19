import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
echarts.use([
  BarChart,
  LineChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);
export function Chart({
  labels,
  values,
  type = "bar",
  color = "#4c82eb",
}: {
  labels: string[];
  values: (number | null)[];
  type?: "bar" | "line";
  color?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const chart = echarts.init(ref.current!);
    chart.setOption({
      tooltip: { trigger: "axis" },
      grid: { left: 55, right: 20, top: 20, bottom: 65 },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: {
          color: "#8897ac",
          rotate: labels.length > 6 ? 25 : 0,
          fontSize: 10,
        },
        axisLine: { lineStyle: { color: "#e5ebf4" } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#8897ac", fontSize: 10 },
        splitLine: { lineStyle: { color: "#eff3f8" } },
      },
      series: [
        {
          type,
          data: values,
          itemStyle: {
            color,
            borderRadius: type === "bar" ? [4, 4, 0, 0] : undefined,
          },
          smooth: true,
          areaStyle: type === "line" ? { opacity: 0.08 } : undefined,
          barMaxWidth: 36,
        },
      ],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current!);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [labels, values, type, color]);
  return (
    <div
      ref={ref}
      className="chart"
      role="img"
      aria-label={`Biểu đồ ${labels.join(", ")}`}
    />
  );
}
export function Scatter({ points }: { points: number[][] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const chart = echarts.init(ref.current!);
    chart.setOption({
      tooltip: { trigger: "item" },
      grid: { left: 60, right: 25, top: 25, bottom: 50 },
      xAxis: {
        type: "value",
        name: "Actual (triệu)",
        nameLocation: "middle",
        nameGap: 30,
      },
      yAxis: { type: "value", name: "Predicted (triệu)" },
      series: [
        {
          type: "scatter",
          data: points,
          symbolSize: 6,
          itemStyle: { color: "#4c82eb", opacity: 0.65 },
        },
      ],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current!);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [points]);
  return (
    <div
      className="chart"
      ref={ref}
      role="img"
      aria-label="Actual versus predicted salary on holdout test"
    />
  );
}
