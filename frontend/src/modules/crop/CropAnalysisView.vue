<script setup lang="ts">
import { Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { ref, watch } from "vue";

import { errorMessage } from "@/api/client";
import { getCropCycleAnalysis, getCropCycles, getCropFarmAnalysis } from "@/api/crop";
import { useFarmStore } from "@/stores/farm";
import type { CropAnalysisComparison, CropCycle, CropCycleAnalysis } from "@/types/crop";

const farmStore = useFarmStore();
const loading = ref(false);
const comparisonLoading = ref(false);
const cycles = ref<CropCycle[]>([]);
const selectedCycleId = ref<number | null>(null);
const analysis = ref<CropCycleAnalysis | null>(null);
const comparisons = ref<CropAnalysisComparison[]>([]);

async function loadCycles() {
  const farmId = farmStore.currentFarmId;
  if (!farmId) {
    cycles.value = [];
    selectedCycleId.value = null;
    analysis.value = null;
    return;
  }
  const data = await getCropCycles({ farmId, page: 1, pageSize: 100, status: "all" });
  cycles.value = data.items.filter((cycle) => ["HARVESTING", "CLOSED"].includes(cycle.status));
  if (!cycles.value.some((cycle) => cycle.id === selectedCycleId.value)) {
    selectedCycleId.value = cycles.value[0]?.id ?? null;
  }
}

async function loadAnalysis() {
  if (!selectedCycleId.value) {
    analysis.value = null;
    return;
  }
  loading.value = true;
  try {
    analysis.value = await getCropCycleAnalysis(selectedCycleId.value);
  } catch (error) {
    analysis.value = null;
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function loadComparison() {
  const farmId = farmStore.currentFarmId;
  if (!farmId) {
    comparisons.value = [];
    return;
  }
  comparisonLoading.value = true;
  try {
    comparisons.value = (await getCropFarmAnalysis(farmId)).items;
  } catch (error) {
    comparisons.value = [];
    ElMessage.error(errorMessage(error));
  } finally {
    comparisonLoading.value = false;
  }
}

async function load() {
  try {
    await loadCycles();
    await Promise.all([loadAnalysis(), loadComparison()]);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

watch(() => farmStore.currentFarmId, () => void load(), { immediate: true });
</script>

<template>
  <section class="farm-page resource-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">CROP ANALYSIS</p>
        <h1>种植分析</h1>
        <p>{{ farmStore.currentFarm?.name ?? "尚未选择农场" }} · 产量、成本、烘烤和分级汇总</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </header>

    <el-empty v-if="!farmStore.currentFarm" description="暂无可用农场" />
    <template v-else>
      <div class="farm-toolbar" role="search" aria-label="选择分析周期">
        <el-select v-model="selectedCycleId" class="cycle-select" filterable placeholder="选择采收中或已关闭周期">
          <el-option v-for="cycle in cycles" :key="cycle.id" :label="`${cycle.cycleCode} · ${cycle.cropTypeName ?? ''}`" :value="cycle.id" />
        </el-select>
        <el-button type="primary" :icon="Search" :disabled="!selectedCycleId" @click="loadAnalysis">查询</el-button>
      </div>
      <el-alert v-if="!selectedCycleId" title="暂无采收中或已关闭的种植周期" type="info" :closable="false" />

      <div v-else v-loading="loading" class="analysis-content">
        <el-descriptions v-if="analysis" :column="4" border direction="vertical" aria-label="种植分析汇总">
          <el-descriptions-item label="采收净重">{{ analysis.harvest.totalNetWeight }} {{ analysis.unitName ?? "" }}</el-descriptions-item>
          <el-descriptions-item label="亩产">{{ analysis.harvest.yieldPerMu }} {{ analysis.unitName ?? "" }}/亩</el-descriptions-item>
          <el-descriptions-item label="周期总成本">¥ {{ analysis.cost.totalCost }}</el-descriptions-item>
          <el-descriptions-item label="单位产量成本">¥ {{ analysis.cost.unitOutputCost }}/{{ analysis.unitName ?? "单位" }}</el-descriptions-item>
          <el-descriptions-item label="亩均成本">¥ {{ analysis.cost.costPerMu }}</el-descriptions-item>
          <el-descriptions-item label="烘烤得率">{{ analysis.curing.efficiency }}%</el-descriptions-item>
          <el-descriptions-item label="分级率">{{ analysis.grading.gradingRate }}%</el-descriptions-item>
          <el-descriptions-item label="等级参考价值">¥ {{ analysis.grading.referenceValue }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="analysis" class="analysis-grid">
          <section>
            <h2>生产构成</h2>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="采收批次">{{ analysis.harvest.batchCount }}</el-descriptions-item>
              <el-descriptions-item label="烘烤批次">{{ analysis.curing.completedBatchCount }} / {{ analysis.curing.batchCount }} 已完成</el-descriptions-item>
              <el-descriptions-item label="入炉 / 出炉">{{ analysis.curing.totalInputWeight }} / {{ analysis.curing.totalOutputWeight }} {{ analysis.unitName ?? "" }}</el-descriptions-item>
              <el-descriptions-item label="已分级 / 未分级">{{ analysis.grading.gradedQuantity }} / {{ analysis.grading.ungradedQuantity }} {{ analysis.unitName ?? "" }}</el-descriptions-item>
            </el-descriptions>
          </section>
          <section>
            <h2>成本构成</h2>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="材料">¥ {{ analysis.cost.materialCost }}</el-descriptions-item>
              <el-descriptions-item label="人工">¥ {{ analysis.cost.laborCost }}</el-descriptions-item>
              <el-descriptions-item label="服务">¥ {{ analysis.cost.serviceCost }}</el-descriptions-item>
              <el-descriptions-item label="烘烤能源">¥ {{ analysis.cost.curingCost }}</el-descriptions-item>
            </el-descriptions>
          </section>
        </div>

        <div v-if="analysis" class="farm-table-shell">
          <div class="analysis-heading"><h2>等级结构</h2><span>占已分级数量比例</span></div>
          <el-table :data="analysis.grading.gradeStructure" row-key="gradeCode" empty-text="当前周期暂无分级记录">
            <el-table-column prop="gradeCode" label="等级" min-width="120" />
            <el-table-column label="数量" min-width="150" align="right"><template #default="scope">{{ scope.row.quantity }} {{ analysis.unitName ?? "" }}</template></el-table-column>
            <el-table-column label="占比" min-width="220"><template #default="scope"><el-progress :percentage="Number(scope.row.percentage)" /></template></el-table-column>
            <el-table-column label="参考价值" min-width="140" align="right"><template #default="scope">¥ {{ scope.row.referenceValue }}</template></el-table-column>
          </el-table>
        </div>
      </div>
      <div class="farm-table-shell comparison-table">
        <div class="analysis-heading"><h2>多作物周期对比</h2><span>最近 20 个采收中或已关闭周期</span></div>
        <el-table v-loading="comparisonLoading" :data="comparisons" row-key="cycleId" empty-text="暂无可对比周期">
          <el-table-column label="周期 / 作物" min-width="180">
            <template #default="scope"><strong>{{ scope.row.cycleCode }}</strong><br /><span class="table-secondary">{{ scope.row.cropTypeName }} · {{ scope.row.plotName }}</span></template>
          </el-table-column>
          <el-table-column label="面积" width="100" align="right"><template #default="scope">{{ scope.row.areaMu }} 亩</template></el-table-column>
          <el-table-column label="净产量" min-width="130" align="right"><template #default="scope">{{ scope.row.totalNetWeight }} {{ scope.row.unitName ?? "" }}</template></el-table-column>
          <el-table-column label="亩产" min-width="140" align="right"><template #default="scope">{{ scope.row.yieldPerMu }} {{ scope.row.unitName ?? "" }}/亩</template></el-table-column>
          <el-table-column label="总成本" min-width="120" align="right"><template #default="scope">¥ {{ scope.row.totalCost }}</template></el-table-column>
          <el-table-column label="亩均成本" min-width="120" align="right"><template #default="scope">¥ {{ scope.row.costPerMu }}</template></el-table-column>
          <el-table-column label="单位成本" min-width="140" align="right"><template #default="scope">¥ {{ scope.row.unitOutputCost }}/{{ scope.row.unitName ?? "单位" }}</template></el-table-column>
          <el-table-column label="分级率" width="100" align="right"><template #default="scope">{{ scope.row.gradingRate }}%</template></el-table-column>
          <el-table-column label="参考价值" min-width="120" align="right"><template #default="scope">¥ {{ scope.row.referenceValue }}</template></el-table-column>
        </el-table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.analysis-content { min-height: 180px; display: grid; gap: 20px; }
.analysis-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.analysis-grid h2, .analysis-heading h2 { margin: 0 0 12px; font-size: 16px; }
.analysis-heading { display: flex; align-items: baseline; justify-content: space-between; padding: 18px 20px 0; }
.analysis-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
.comparison-table { margin-top: 20px; }
@media (max-width: 760px) { .analysis-grid { grid-template-columns: 1fr; } }
</style>
