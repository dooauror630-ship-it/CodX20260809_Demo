<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { AriaComponent, GraphicComponent, GridComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import { buildRegistrationTrendOption } from "../chartOptions";
import type { RegistrationTrendPoint } from "@/types/analytics";


use([BarChart, GridComponent, TooltipComponent, GraphicComponent, AriaComponent, CanvasRenderer]);

const props = defineProps<{ data: RegistrationTrendPoint[] }>();
const chartElement = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;

function renderChart() {
  chart?.setOption(buildRegistrationTrendOption(props.data), true);
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
  <div ref="chartElement" class="registration-chart" />
</template>
