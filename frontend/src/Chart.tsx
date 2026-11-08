import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useTheme } from './theme';

function chartPalette(theme: string) {
  return theme === 'light'
    ? { text: '#425d7c', axis: '#526a85', line: '#b9ccdf', grid: '#e0e8f2', background: '#fff' }
    : { text: '#b3c6df', axis: '#8897ac', line: '#34445b', grid: '#26364d', background: '#142137' };
}
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
  const theme = useTheme();
  const datasetKey = JSON.stringify([labels, values, type, color]);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current!);
    const palette = chartPalette(theme);
    chart.setOption({
      animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      textStyle: { color: palette.text },
      tooltip: { trigger: "axis", backgroundColor: palette.background, borderColor: palette.line, textStyle: { color: palette.text } },
      grid: { left: 55, right: 20, top: 20, bottom: 65 },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: {
          color: palette.axis,
          rotate: labels.length > 6 ? 25 : 0,
          fontSize: 10,
        },
        axisLine: { lineStyle: { color: palette.line } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: palette.axis, fontSize: 10 },
        splitLine: { lineStyle: { color: palette.grid } },
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
  }, [datasetKey, theme]);
  return (
    labels.length === 0 ? <div className="empty" role="status">Chưa có dữ liệu cho biểu đồ này.</div> :
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
  const theme = useTheme();
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current!);
    const palette = chartPalette(theme);
    chart.setOption({
      animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      textStyle: { color: palette.text },
      tooltip: { trigger: "item", backgroundColor: palette.background, borderColor: palette.line, textStyle: { color: palette.text } },
      grid: { left: 60, right: 25, top: 25, bottom: 50 },
      xAxis: {
        type: "value",
        name: "Actual (triệu)",
        nameLocation: "middle",
        nameGap: 30,
        nameTextStyle: { color: palette.axis },
        axisLabel: { color: palette.axis },
        axisLine: { lineStyle: { color: palette.line } },
        splitLine: { lineStyle: { color: palette.grid } },
      },
      yAxis: { type: "value", name: "Predicted (triệu)", nameTextStyle: { color: palette.axis }, axisLabel: { color: palette.axis }, axisLine: { lineStyle: { color: palette.line } }, splitLine: { lineStyle: { color: palette.grid } } },
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
  }, [points, theme]);
  return (
    <div
      className="chart"
      ref={ref}
      role="img"
      aria-label="Actual versus predicted salary on holdout test"
    />
  );
}
