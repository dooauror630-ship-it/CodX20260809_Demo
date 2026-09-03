<script setup lang="ts">
import { LineChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { LivestockProductionTrendPoint } from "@/types/livestock";


use([LineChart, GridComponent, LegendComponent, TooltipComponent, AriaComponent, CanvasRenderer]);

const props = defineProps<{ data: LivestockProductionTrendPoint[] }>();
const chartElement = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

function option(): EChartsCoreOption {
  return {
    aria: { enabled: true, description: "生猪批次存栏与抽样均重趋势图" },
    animationDuration: 350,
    grid: { left: 18, right: 22, top: 46, bottom: 14, containLabel: true },
    legend: { top: 4, right: 4, itemWidth: 14, itemHeight: 8, textStyle: { color: "#65716b" } },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: props.data.map((point) => point.date.slice(5)),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#d7ddd9" } },
      axisLabel: { color: "#65716b", hideOverlap: true },
    },
    yAxis: [
      {
        type: "value",
        name: "头",
        min: 0,
        axisLabel: { color: "#65716b" },
        splitLine: { lineStyle: { color: "#edf0ee" } },
      },
      {
        type: "value",
        name: "kg",
        min: 0,
        axisLabel: { color: "#65716b" },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        type: "line",
        name: "存栏头数",
        data: props.data.map((point) => point.headCount),
        symbolSize: 7,
        itemStyle: { color: "#287b50" },
        lineStyle: { width: 2, color: "#287b50" },
      },
      {
        type: "line",
        name: "抽样均重",
        yAxisIndex: 1,
        data: props.data.map((point) => point.averageWeight === null ? null : Number(point.averageWeight)),
        connectNulls: true,
        symbolSize: 7,
        itemStyle: { color: "#c58428" },
        lineStyle: { width: 2, color: "#c58428" },
      },
    ],
  };
}

function renderChart() {
  chart?.setOption(option(), true);
}

onMounted(() => {
  if (!chartElement.value) return;
  chart = init(chartElement.value);
  renderChart();
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(chartElement.value);
});

watch(() => props.data, renderChart, { deep: true });

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <div ref="chartElement" class="livestock-production-trend-chart" aria-label="生猪批次存栏与抽样均重趋势图" />
</template>
