import type { EChartsCoreOption } from "echarts/core";

import type { InventoryTrendPoint } from "@/types/purchase";


export function buildInventoryTrendOption(data: InventoryTrendPoint[]): EChartsCoreOption {
  const empty = data.every((point) => Number(point.inboundAmount) === 0 && Number(point.outboundAmount) === 0);
  return {
    aria: {
      enabled: true,
      description: "库存入库与出库金额趋势图",
    },
    animationDuration: 350,
    grid: {
      left: 18,
      right: 18,
      top: 42,
      bottom: 14,
      containLabel: true,
    },
    legend: {
      top: 4,
      right: 4,
      itemWidth: 12,
      itemHeight: 8,
      textStyle: { color: "#65716b" },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: number) => `¥ ${Number(value).toFixed(2)}`,
    },
    xAxis: {
      type: "category",
      data: data.map((point) => point.date.slice(5)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#d7ddd9" } },
      axisLabel: { color: "#65716b", hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#65716b", formatter: (value: number) => `¥${value}` },
      splitLine: { lineStyle: { color: "#edf0ee" } },
    },
    series: [
      {
        type: "bar",
        name: "入库金额",
        data: data.map((point) => Number(point.inboundAmount)),
        barMaxWidth: 20,
        itemStyle: { color: "#287b50", borderRadius: [3, 3, 0, 0] },
      },
      {
        type: "bar",
        name: "出库金额",
        data: data.map((point) => Number(point.outboundAmount)),
        barMaxWidth: 20,
        itemStyle: { color: "#c58428", borderRadius: [3, 3, 0, 0] },
      },
    ],
    graphic: empty
      ? [{
          type: "text",
          left: "center",
          top: "middle",
          style: { text: "当前周期暂无库存流动", fill: "#8b9690", fontSize: 14 },
        }]
      : [],
  };
}
