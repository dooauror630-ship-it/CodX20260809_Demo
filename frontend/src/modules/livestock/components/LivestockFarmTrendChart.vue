<script setup lang="ts">
import { BarChart, LineChart } from "echarts/charts";
import { AriaComponent, GraphicComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { LivestockFarmTrendPoint } from "@/types/livestock";


use([LineChart, BarChart, GridComponent, LegendComponent, TooltipComponent, GraphicComponent, AriaComponent, CanvasRenderer]);

const props = defineProps<{ data: LivestockFarmTrendPoint[] }>();
const chartElement = ref<HTMLElement | null>(null);
let chart: ECharts | undefined;

function option(): EChartsCoreOption {
  if (!props.data.length) {
    return {
      graphic: { type: "text", left: "center", top: "middle", style: { text: "当前周期暂无养殖数据", fill: "#7b8680", fontSize: 13 } },
    };
  }
  return {
    aria: { enabled: true, description: "农场生猪存栏和每日死亡趋势图" },
    color: ["#28754b", "#c84b4b"],
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: ["当前存栏", "每日死亡"] },
    grid: { left: 18, right: 18, top: 44, bottom: 10, containLabel: true },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: props.data.map((item) => item.date.slice(5)),
      axisLabel: { color: "#6f7974", hideOverlap: true },
      axisLine: { lineStyle: { color: "#dce2de" } },
    },
    yAxis: [
      { type: "value", minInterval: 1, name: "头", axisLabel: { color: "#6f7974" }, splitLine: { lineStyle: { color: "#edf0ee" } } },
      { type: "value", minInterval: 1, name: "死亡", axisLabel: { color: "#6f7974" }, splitLine: { show: false } },
    ],
    series: [
      {
        name: "当前存栏",
        type: "line",
        smooth: true,
        symbol: "none",
        lineStyle: { width: 3 },
        areaStyle: { color: "rgba(40, 117, 75, 0.10)" },
        data: props.data.map((item) => item.currentHeadCount),
      },
      {
        name: "每日死亡",
        type: "bar",
        yAxisIndex: 1,
        barMaxWidth: 14,
        data: props.data.map((item) => item.deathCount),
      },
    ],
  };
}

function render() {
  if (!chartElement.value) return;
  chart ??= init(chartElement.value);
  chart.setOption(option(), true);
}

function resize() {
  chart?.resize();
}

watch(() => props.data, () => nextTick(render), { deep: true });
onMounted(() => {
  render();
  window.addEventListener("resize", resize);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", resize);
  chart?.dispose();
});
</script>

<template>
  <div ref="chartElement" class="livestock-farm-trend-chart" aria-label="农场生猪存栏和每日死亡趋势图" />
</template>
