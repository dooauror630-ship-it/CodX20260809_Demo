<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import { buildInventoryTrendOption } from "../inventoryChartOptions";
import type { InventoryTrendPoint } from "@/types/purchase";


use([BarChart, GridComponent, LegendComponent, TooltipComponent, AriaComponent, CanvasRenderer]);

const props = defineProps<{ data: InventoryTrendPoint[] }>();
const chartElement = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

function renderChart() {
  chart?.setOption(buildInventoryTrendOption(props.data), true);
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
  <div ref="chartElement" class="inventory-trend-chart" aria-label="库存流动金额趋势图" />
</template>
