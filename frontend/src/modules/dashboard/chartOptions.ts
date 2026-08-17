import type { EChartsCoreOption } from "echarts/core";

import type { RegistrationTrendPoint } from "@/types/analytics";


export function buildRegistrationTrendOption(data: RegistrationTrendPoint[]): EChartsCoreOption {
  const empty = data.every((point) => point.count === 0);
  return {
    aria: {
      enabled: true,
      description: "最近六个月账户创建数量柱状图",
    },
    animationDuration: 350,
    grid: {
      left: 20,
      right: 18,
      top: 24,
      bottom: 12,
      containLabel: true,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: number) => `${value} 个`,
    },
    xAxis: {
      type: "category",
      data: data.map((point) => point.month),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#d7ddd9" } },
      axisLabel: { color: "#65716b" },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      axisLabel: { color: "#65716b" },
      splitLine: { lineStyle: { color: "#edf0ee" } },
    },
    series: [
      {
        type: "bar",
        name: "新增账户",
        data: data.map((point) => point.count),
        barMaxWidth: 36,
        itemStyle: {
          color: "#287b50",
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
    graphic: empty
      ? [
          {
            type: "text",
            left: "center",
            top: "middle",
            style: {
              text: "暂无新增账户",
              fill: "#8b9690",
              fontSize: 14,
            },
          },
        ]
      : [],
  };
}
