<script setup lang="ts">
import { CircleClose, EditPen, Finished, Plus, Refresh, Search, Tickets, View } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { getCatalogs } from "@/api/catalogs";
import { errorMessage } from "@/api/client";
import { getBarns } from "@/api/farms";
import { getItems, getWarehouses } from "@/api/inventory";
import {
  cancelLivestockCostEntry,
  createLivestockBatch,
  createLivestockCostEntry,
  createLivestockHealthRecord,
  createLivestockMovement,
  createLivestockWeightRecord,
  getLivestockAnalysis,
  getLivestockBatch,
  getLivestockBatches,
} from "@/api/livestock";
import { createProductionStockOperation } from "@/api/purchases";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { LivestockSpecies } from "@/types/catalog";
import type { Barn } from "@/types/farm";
import type { Item, Warehouse } from "@/types/inventory";
import type {
  LivestockAnalysis,
  LivestockBatch,
  LivestockBatchStatus,
  LivestockCostEntry,
  LivestockCostType,
  LivestockHealthType,
  LivestockMovement,
  LivestockSummary,
  WritableLivestockMovementType,
} from "@/types/livestock";
import { localDateInputValue } from "@/utils/date";
import LivestockFarmTrendChart from "./components/LivestockFarmTrendChart.vue";
import LivestockProductionTrendChart from "./components/LivestockProductionTrendChart.vue";


const router = useRouter();
const auth = useAuthStore();
const farmContext = useFarmStore();
const loading = ref(false);
const compactTable = ref(false);
const referencesLoading = ref(false);
const batches = ref<LivestockBatch[]>([]);
const barns = ref<Barn[]>([]);
const warehouses = ref<Warehouse[]>([]);
const productionItems = ref<Item[]>([]);
const pigSpecies = ref<LivestockSpecies | null>(null);
const filters = reactive({
  keyword: "",
  status: "all" as "all" | LivestockBatchStatus,
});
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });
const summary = reactive<LivestockSummary>({
  activeBatchCount: 0,
  currentHeadCount: 0,
  deathCount: 0,
  exitedCount: 0,
});
const analysisLoading = ref(false);
const analysis = ref<LivestockAnalysis | null>(null);
const analysisFilters = reactive({ trendDays: 30 });

const entryDialogVisible = ref(false);
const entrySaving = ref(false);
const entryForm = reactive({
  batchNo: "",
  name: "",
  entryNo: "",
  entryDate: "",
  barnId: null as number | null,
  initialCount: 1,
  source: "",
  notes: "",
});

const movementDialogVisible = ref(false);
const movementSaving = ref(false);
const movementBatch = ref<LivestockBatch | null>(null);
const movementForm = reactive({
  movementNo: "",
  movementType: "TRANSFER" as WritableLivestockMovementType,
  occurredOn: "",
  fromBarnId: null as number | null,
  toBarnId: null as number | null,
  quantity: 1,
  reason: "",
  notes: "",
});

const detailDialogVisible = ref(false);
const detailLoading = ref(false);
const detailBatch = ref<LivestockBatch | null>(null);
const productionDialogVisible = ref(false);
const productionSaving = ref(false);
const productionType = ref<"feeding" | "health" | "weight" | "cost">("feeding");
const productionForm = reactive({
  recordNo: "",
  occurredOn: "",
  warehouseId: null as number | null,
  itemId: null as number | null,
  quantity: 1,
  lotNo: "",
  healthType: "VACCINATION" as LivestockHealthType,
  description: "",
  medicineName: "",
  dosage: "",
  sampleCount: 10,
  averageWeight: 1,
  costType: "ENTRY" as LivestockCostType,
  amount: 0.01,
  notes: "",
});

const canOperate = computed(() => {
  const role = farmContext.currentFarm?.accessRole;
  return auth.isAdmin || role === "manager" || role === "operator";
});
const activePigBarns = computed(() => barns.value.filter(
  (barn) => barn.isActive && (barn.barnType === "pig" || barn.barnType === "isolation"),
));
const sourceBarns = computed(() => movementBatch.value?.barnBalances.filter((item) => item.headCount > 0) ?? []);
const destinationBarns = computed(() => activePigBarns.value.filter((barn) => barn.id !== movementForm.fromBarnId));
const movementTypeOptions: Array<{ label: string; value: WritableLivestockMovementType }> = [
  { label: "转舍", value: "TRANSFER" },
  { label: "死亡", value: "DEATH" },
  { label: "淘汰", value: "CULL" },
  { label: "出栏", value: "EXIT" },
];
const healthTypeNames: Record<LivestockHealthType, string> = {
  VACCINATION: "防疫",
  MEDICATION: "用药",
  DISEASE: "病情",
  OTHER: "其他",
};
const costCategoryNames: Record<string, string> = {
  feed: "饲料",
  veterinary_drug: "兽药",
  supply: "生产物资",
  other: "其他物料",
};
const costTypeNames: Record<LivestockCostType, string> = {
  ENTRY: "入栏成本",
  LABOR: "人工成本",
  OVERHEAD: "公共费用分摊",
  OTHER: "其他成本",
};

function suggestedNo(prefix: string) {
  return `${prefix}-${Date.now().toString(36).toUpperCase()}`;
}

function batchStatusName(status: LivestockBatchStatus) {
  return status === "ACTIVE" ? "在养" : "已结束";
}

function movementTypeName(type: LivestockMovement["movementType"]) {
  return {
    ENTRY: "入栏",
    TRANSFER: "转舍",
    DEATH: "死亡",
    CULL: "淘汰",
    EXIT: "出栏",
  }[type];
}

function movementTag(type: LivestockMovement["movementType"]) {
  if (type === "ENTRY") return "success";
  if (type === "TRANSFER") return "primary";
  if (type === "DEATH") return "danger";
  return "warning";
}

function costCategoryName(value: string) {
  return costCategoryNames[value] ?? "其他物料";
}

function barnBalanceText(batch: LivestockBatch) {
  return batch.barnBalances.length
    ? batch.barnBalances.map((item) => `${item.barnName} ${item.headCount}`).join("、")
    : "无在栏圈舍";
}

function movementDirection(movement: LivestockMovement) {
  if (movement.movementType === "ENTRY") return movement.toBarnName ?? "-";
  if (movement.movementType === "TRANSFER") {
    return `${movement.fromBarnName ?? "-"} → ${movement.toBarnName ?? "-"}`;
  }
  return movement.fromBarnName ?? "-";
}

function updateTableLayout() {
  compactTable.value = window.innerWidth < 760;
}

async function loadReferences() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    barns.value = [];
    pigSpecies.value = null;
    return;
  }
  referencesLoading.value = true;
  try {
    const [catalogs, barnData, warehouseData, itemData] = await Promise.all([
      getCatalogs(),
      getBarns({ farmId, page: 1, pageSize: 100, status: "active" }),
      getWarehouses({ farmId, page: 1, pageSize: 100, status: "active" }),
      getItems({ farmId, page: 1, pageSize: 100, status: "active" }),
    ]);
    pigSpecies.value = catalogs.livestockSpecies.find((item) => item.code === "PIG" && item.isActive) ?? null;
    barns.value = barnData.items;
    warehouses.value = warehouseData.items;
    productionItems.value = itemData.items.filter((item) =>
      ["feed", "veterinary_drug", "supply", "other"].includes(item.itemType),
    );
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    referencesLoading.value = false;
  }
}

async function loadBatches() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    batches.value = [];
    pagination.total = 0;
    Object.assign(summary, { activeBatchCount: 0, currentHeadCount: 0, deathCount: 0, exitedCount: 0 });
    return;
  }
  loading.value = true;
  try {
    const data = await getLivestockBatches({
      farmId,
      page: pagination.page,
      pageSize: pagination.pageSize,
      keyword: filters.keyword || undefined,
      status: filters.status,
    });
    batches.value = data.items;
    pagination.total = data.pagination.total;
    Object.assign(summary, data.summary);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function loadAnalysis() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    analysis.value = null;
    return;
  }
  analysisLoading.value = true;
  try {
    analysis.value = await getLivestockAnalysis({ farmId, trendDays: analysisFilters.trendDays });
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    analysisLoading.value = false;
  }
}

function searchBatches() {
  pagination.page = 1;
  void loadBatches();
}

function resetFilters() {
  filters.keyword = "";
  filters.status = "all";
  searchBatches();
}

function changePage(page: number) {
  pagination.page = page;
  void loadBatches();
}

function changePageSize(pageSize: number) {
  pagination.page = 1;
  pagination.pageSize = pageSize;
  void loadBatches();
}

function openEntry() {
  if (!pigSpecies.value) return ElMessage.warning("猪养殖品类尚未启用");
  if (!activePigBarns.value.length) return ElMessage.warning("请先准备可用的猪舍或隔离舍");
  entryForm.batchNo = suggestedNo("PIG");
  entryForm.name = "";
  entryForm.entryNo = suggestedNo("EN");
  entryForm.entryDate = localDateInputValue();
  entryForm.barnId = activePigBarns.value[0]?.id ?? null;
  entryForm.initialCount = 1;
  entryForm.source = "";
  entryForm.notes = "";
  entryDialogVisible.value = true;
}

async function saveEntry() {
  const farmId = farmContext.currentFarmId;
  if (!farmId || !pigSpecies.value) return ElMessage.error("当前农场或猪养殖品类不可用");
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(entryForm.batchNo.trim())) {
    return ElMessage.error("批次编号须为 3-40 位字母、数字、下划线或短横线");
  }
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(entryForm.entryNo.trim())) {
    return ElMessage.error("入栏单号须为 3-40 位字母、数字、下划线或短横线");
  }
  if (entryForm.name.trim().length < 2 || entryForm.name.trim().length > 80) {
    return ElMessage.error("批次名称须为 2-80 个字符");
  }
  if (!entryForm.entryDate || entryForm.entryDate > localDateInputValue()) {
    return ElMessage.error("请选择不晚于今天的入栏日期");
  }
  if (!entryForm.barnId) return ElMessage.error("请选择入栏圈舍");
  if (!Number.isInteger(entryForm.initialCount) || entryForm.initialCount <= 0) {
    return ElMessage.error("初始头数须为正整数");
  }

  entrySaving.value = true;
  try {
    await createLivestockBatch({
      farmId,
      speciesId: pigSpecies.value.id,
      batchNo: entryForm.batchNo.trim(),
      name: entryForm.name.trim(),
      entryNo: entryForm.entryNo.trim(),
      entryDate: entryForm.entryDate,
      barnId: entryForm.barnId,
      initialCount: entryForm.initialCount,
      source: entryForm.source.trim() || null,
      notes: entryForm.notes.trim() || null,
    });
    ElMessage.success("生猪批次已入栏");
    entryDialogVisible.value = false;
    await Promise.all([loadBatches(), loadAnalysis()]);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    entrySaving.value = false;
  }
}

function openMovement(batch: LivestockBatch) {
  movementBatch.value = batch;
  movementForm.movementType = "TRANSFER";
  movementForm.movementNo = suggestedNo("TF");
  movementForm.occurredOn = localDateInputValue();
  movementForm.fromBarnId = batch.barnBalances[0]?.barnId ?? null;
  movementForm.toBarnId = activePigBarns.value.find((barn) => barn.id !== movementForm.fromBarnId)?.id ?? null;
  movementForm.quantity = 1;
  movementForm.reason = "";
  movementForm.notes = "";
  movementDialogVisible.value = true;
}

function changeMovementType(type: WritableLivestockMovementType) {
  movementForm.movementType = type;
  const prefix = { TRANSFER: "TF", DEATH: "DT", CULL: "CL", EXIT: "EX" }[type];
  movementForm.movementNo = suggestedNo(prefix);
  movementForm.toBarnId = type === "TRANSFER" ? destinationBarns.value[0]?.id ?? null : null;
  if (type !== "DEATH" && type !== "CULL") movementForm.reason = "";
}

function changeSourceBarn() {
  if (movementForm.movementType === "TRANSFER" && movementForm.toBarnId === movementForm.fromBarnId) {
    movementForm.toBarnId = destinationBarns.value[0]?.id ?? null;
  }
}

async function saveMovement() {
  const farmId = farmContext.currentFarmId;
  const batch = movementBatch.value;
  if (!farmId || !batch) return;
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(movementForm.movementNo.trim())) {
    return ElMessage.error("变动单号须为 3-40 位字母、数字、下划线或短横线");
  }
  if (!movementForm.occurredOn || movementForm.occurredOn > localDateInputValue()) {
    return ElMessage.error("请选择不晚于今天的变动日期");
  }
  if (!movementForm.fromBarnId) return ElMessage.error("请选择来源圈舍");
  if (movementForm.movementType === "TRANSFER" && !movementForm.toBarnId) {
    return ElMessage.error("请选择目标圈舍");
  }
  if (!Number.isInteger(movementForm.quantity) || movementForm.quantity <= 0) {
    return ElMessage.error("变动头数须为正整数");
  }
  if (["DEATH", "CULL"].includes(movementForm.movementType) && !movementForm.reason.trim()) {
    return ElMessage.error("死亡或淘汰必须填写原因");
  }

  movementSaving.value = true;
  try {
    await createLivestockMovement({
      farmId,
      batchId: batch.id,
      movementNo: movementForm.movementNo.trim(),
      movementType: movementForm.movementType,
      occurredOn: movementForm.occurredOn,
      fromBarnId: movementForm.fromBarnId,
      toBarnId: movementForm.movementType === "TRANSFER" ? movementForm.toBarnId : null,
      quantity: movementForm.quantity,
      reason: movementForm.reason.trim() || null,
      notes: movementForm.notes.trim() || null,
    });
    ElMessage.success("存栏变动已登记");
    movementDialogVisible.value = false;
    await Promise.all([loadBatches(), loadAnalysis()]);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    movementSaving.value = false;
  }
}

async function openDetail(batch: Pick<LivestockBatch, "id">) {
  detailDialogVisible.value = true;
  detailLoading.value = true;
  detailBatch.value = null;
  try {
    detailBatch.value = await getLivestockBatch(batch.id);
  } catch (error) {
    detailDialogVisible.value = false;
    ElMessage.error(errorMessage(error));
  } finally {
    detailLoading.value = false;
  }
}

function openProduction(type: "feeding" | "health" | "weight" | "cost") {
  productionType.value = type;
  const prefix = { feeding: "FD", health: "HL", weight: "WT", cost: "CT" }[type];
  productionForm.recordNo = suggestedNo(prefix);
  productionForm.occurredOn = detailBatch.value?.closedAt?.slice(0, 10) ?? localDateInputValue();
  productionForm.warehouseId = warehouses.value[0]?.id ?? null;
  productionForm.itemId = productionItems.value[0]?.id ?? null;
  productionForm.quantity = 1;
  productionForm.lotNo = "";
  productionForm.healthType = "VACCINATION";
  productionForm.description = "";
  productionForm.medicineName = "";
  productionForm.dosage = "";
  productionForm.sampleCount = 10;
  productionForm.averageWeight = 1;
  productionForm.costType = "ENTRY";
  productionForm.amount = 0.01;
  productionForm.notes = "";
  productionDialogVisible.value = true;
}

async function saveProductionRecord() {
  const farmId = farmContext.currentFarmId;
  const batch = detailBatch.value;
  if (!farmId || !batch) return;
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(productionForm.recordNo.trim())) {
    return ElMessage.error("记录单号须为 3-40 位字母、数字、下划线或短横线");
  }
  const lastBusinessDate = batch.closedAt?.slice(0, 10) ?? localDateInputValue();
  if (!productionForm.occurredOn || productionForm.occurredOn < batch.entryDate || productionForm.occurredOn > lastBusinessDate) {
    return ElMessage.error(`记录日期须在入栏日期至${batch.closedAt ? "批次结束日期" : "今天"}之间`);
  }
  productionSaving.value = true;
  try {
    if (productionType.value === "feeding") {
      if (!productionForm.warehouseId || !productionForm.itemId || productionForm.quantity <= 0) {
        return ElMessage.error("请选择仓库和领用物料，并填写正确数量");
      }
      await createProductionStockOperation({
        farmId,
        documentNo: productionForm.recordNo.trim(),
        operationType: "issue",
        operationDate: productionForm.occurredOn,
        warehouseId: productionForm.warehouseId,
        itemId: productionForm.itemId,
        quantity: productionForm.quantity,
        lotNo: productionForm.lotNo.trim() || null,
        costObjectType: "livestock_batch",
        costObjectId: batch.id,
      });
    } else if (productionType.value === "health") {
      if (productionForm.description.trim().length < 2) return ElMessage.error("请填写健康事项");
      await createLivestockHealthRecord({
        farmId,
        batchId: batch.id,
        recordNo: productionForm.recordNo.trim(),
        recordType: productionForm.healthType,
        occurredOn: productionForm.occurredOn,
        description: productionForm.description.trim(),
        medicineName: productionForm.medicineName.trim() || null,
        dosage: productionForm.dosage.trim() || null,
        notes: productionForm.notes.trim() || null,
      });
    } else if (productionType.value === "weight") {
      if (!Number.isInteger(productionForm.sampleCount) || productionForm.sampleCount <= 0 || productionForm.averageWeight <= 0) {
        return ElMessage.error("抽样头数和平均体重必须大于零");
      }
      await createLivestockWeightRecord({
        farmId,
        batchId: batch.id,
        recordNo: productionForm.recordNo.trim(),
        occurredOn: productionForm.occurredOn,
        sampleCount: productionForm.sampleCount,
        averageWeight: productionForm.averageWeight,
        notes: productionForm.notes.trim() || null,
      });
    } else {
      if (productionForm.description.trim().length < 2 || productionForm.amount <= 0) {
        return ElMessage.error("请填写成本说明和大于零的金额");
      }
      await createLivestockCostEntry({
        farmId,
        batchId: batch.id,
        entryNo: productionForm.recordNo.trim(),
        businessDate: productionForm.occurredOn,
        costType: productionForm.costType,
        amount: productionForm.amount,
        description: productionForm.description.trim(),
        notes: productionForm.notes.trim() || null,
      });
    }
    ElMessage.success(productionType.value === "cost" ? "批次成本已登记" : "生产记录已登记");
    productionDialogVisible.value = false;
    detailBatch.value = await getLivestockBatch(batch.id);
    await loadAnalysis();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    productionSaving.value = false;
  }
}

async function cancelCostEntry(entry: LivestockCostEntry) {
  const batch = detailBatch.value;
  if (!batch) return;
  try {
    await ElMessageBox.confirm(`撤销成本记录“${entry.description}”（¥ ${entry.amount}）？`, "撤销批次成本", {
      confirmButtonText: "确认撤销",
      cancelButtonText: "取消",
      type: "warning",
    });
    await cancelLivestockCostEntry(entry.id);
    ElMessage.success("批次成本已撤销");
    detailBatch.value = await getLivestockBatch(batch.id);
    await loadAnalysis();
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(errorMessage(error));
  }
}

watch(
  () => farmContext.currentFarmId,
  async () => {
    pagination.page = 1;
    filters.keyword = "";
    filters.status = "all";
    entryDialogVisible.value = false;
    movementDialogVisible.value = false;
    detailDialogVisible.value = false;
    productionDialogVisible.value = false;
    await Promise.all([loadReferences(), loadBatches(), loadAnalysis()]);
  },
  { immediate: true },
);

onMounted(() => {
  updateTableLayout();
  window.addEventListener("resize", updateTableLayout);
});

onBeforeUnmount(() => window.removeEventListener("resize", updateTableLayout));
</script>

<template>
  <section class="farm-page livestock-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">PIG PRODUCTION</p>
        <h1>生猪管理</h1>
        <p v-if="farmContext.currentFarm">{{ farmContext.currentFarm.name }} · 共 {{ pagination.total }} 个批次</p>
        <p v-else>尚未选择农场</p>
      </div>
      <el-button
        v-if="canOperate && farmContext.currentFarm"
        type="primary"
        :icon="Plus"
        :loading="referencesLoading"
        :disabled="referencesLoading"
        @click="openEntry"
      >
        批次入栏
      </el-button>
    </header>

    <el-empty v-if="!farmContext.currentFarm" class="resource-empty" description="暂无可用农场">
      <el-button v-if="auth.isAdmin" type="primary" @click="router.push('/base/farms')">前往农场档案</el-button>
    </el-empty>

    <template v-else>
      <div class="summary-grid" aria-label="生猪存栏汇总">
        <article class="summary-card">
          <span class="summary-icon tone-green"><Tickets /></span>
          <div><p>当前存栏</p><strong>{{ summary.currentHeadCount }}<small>头</small></strong></div>
        </article>
        <article class="summary-card">
          <span class="summary-icon tone-blue"><Refresh /></span>
          <div><p>在养批次</p><strong>{{ summary.activeBatchCount }}<small>批</small></strong></div>
        </article>
        <article class="summary-card">
          <span class="summary-icon tone-red"><CircleClose /></span>
          <div><p>累计死亡率</p><strong>{{ analysis?.summary.mortalityRate ?? "0.00" }}<small>% · {{ summary.deathCount }} 头</small></strong></div>
        </article>
        <article class="summary-card">
          <span class="summary-icon tone-amber"><Finished /></span>
          <div><p>淘汰与出栏</p><strong>{{ summary.exitedCount }}<small>头</small></strong></div>
        </article>
      </div>

      <section class="livestock-analysis" aria-labelledby="livestockAnalysisTitle">
        <header class="analysis-section-header">
          <div>
            <h2 id="livestockAnalysisTitle">农场生产分析</h2>
            <span>{{ analysis?.period.dateFrom ?? "-" }} 至 {{ analysis?.period.dateTo ?? "-" }} · 死亡率按累计入栏口径</span>
          </div>
          <el-select v-model="analysisFilters.trendDays" class="livestock-analysis-period" aria-label="养殖趋势统计周期" @change="loadAnalysis">
            <el-option label="近 7 天" :value="7" />
            <el-option label="近 30 天" :value="30" />
            <el-option label="近 90 天" :value="90" />
          </el-select>
        </header>
        <div v-loading="analysisLoading" class="livestock-analysis-content">
          <div class="livestock-analysis-chart-shell">
            <livestock-farm-trend-chart :data="analysis?.trend ?? []" />
          </div>
          <header class="livestock-comparison-header">
            <div><h3>批次指标对比</h3><span>最近 10 个批次，支持查看原始记录</span></div>
          </header>
          <div class="farm-table-shell">
            <el-table :data="analysis?.batchComparisons ?? []" row-key="batchId" empty-text="当前农场暂无可对比批次">
              <el-table-column label="批次" :min-width="compactTable ? 225 : 180">
                <template #default="scope">
                  <div class="farm-name-cell">
                    <strong>{{ scope.row.name }}</strong>
                    <span>{{ scope.row.batchNo }} · {{ scope.row.entryDate }}</span>
                    <span v-if="compactTable">存栏 {{ scope.row.currentHeadCount }} 头 · 死亡率 {{ scope.row.mortalityRate }}% · 生产成本 ¥ {{ scope.row.productionCost }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column v-if="!compactTable" label="当前存栏" width="105" align="right"><template #default="scope">{{ scope.row.currentHeadCount }} 头</template></el-table-column>
              <el-table-column v-if="!compactTable" label="死亡率" width="100" align="right"><template #default="scope">{{ scope.row.mortalityRate }}%</template></el-table-column>
              <el-table-column v-if="!compactTable" label="最新均重" width="110" align="right"><template #default="scope">{{ scope.row.latestAverageWeight ? `${scope.row.latestAverageWeight} kg` : "-" }}</template></el-table-column>
              <el-table-column v-if="!compactTable" label="ADG" width="105" align="right"><template #default="scope">{{ scope.row.adg ? `${scope.row.adg} kg/天` : "-" }}</template></el-table-column>
              <el-table-column v-if="!compactTable" label="FCR" width="90" align="right"><template #default="scope">{{ scope.row.fcr ?? "-" }}<small v-if="scope.row.fcrEstimated"> 估</small></template></el-table-column>
              <el-table-column v-if="!compactTable" label="生产成本" width="125" align="right"><template #default="scope">¥ {{ scope.row.productionCost }}</template></el-table-column>
              <el-table-column label="操作" width="74" fixed="right">
                <template #default="scope"><el-tooltip content="查看批次"><el-button circle :icon="View" aria-label="查看对比批次" @click="openDetail({ id: scope.row.batchId })" /></el-tooltip></template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </section>

      <div class="farm-toolbar livestock-toolbar" role="search" aria-label="筛选生猪批次">
        <el-input
          v-model="filters.keyword"
          clearable
          :prefix-icon="Search"
          placeholder="搜索批次编号、名称或来源"
          aria-label="搜索生猪批次"
          @clear="searchBatches"
          @keyup.enter="searchBatches"
        />
        <el-select v-model="filters.status" aria-label="筛选批次状态">
          <el-option label="全部状态" value="all" />
          <el-option label="在养" value="ACTIVE" />
          <el-option label="已结束" value="CLOSED" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="searchBatches">查询</el-button>
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>

      <div class="farm-table-shell">
        <el-table v-loading="loading" :data="batches" row-key="id" empty-text="当前农场暂无生猪批次">
          <el-table-column label="批次" :min-width="compactTable ? 230 : 190">
            <template #default="scope">
              <div class="farm-name-cell">
                <strong>{{ scope.row.name }}</strong>
                <span>{{ scope.row.batchNo }}<template v-if="compactTable"> · {{ scope.row.entryDate }}</template></span>
                <span v-if="compactTable">{{ batchStatusName(scope.row.status) }} · 存栏 {{ scope.row.currentHeadCount }} 头 · {{ barnBalanceText(scope.row) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-if="!compactTable" prop="entryDate" label="入栏日期" width="120" />
          <el-table-column v-if="!compactTable" label="当前存栏" width="110" align="right">
            <template #default="scope"><strong>{{ scope.row.currentHeadCount }}</strong> 头</template>
          </el-table-column>
          <el-table-column v-if="!compactTable" label="圈舍分布" min-width="220">
            <template #default="scope">{{ barnBalanceText(scope.row) }}</template>
          </el-table-column>
          <el-table-column v-if="!compactTable" label="减员/出栏" min-width="150">
            <template #default="scope">死亡 {{ scope.row.deathCount }} · 淘汰 {{ scope.row.cullCount }} · 出栏 {{ scope.row.exitCount }}</template>
          </el-table-column>
          <el-table-column v-if="!compactTable" label="状态" width="90">
            <template #default="scope">
              <el-tag :type="scope.row.status === 'ACTIVE' ? 'success' : 'info'" effect="plain">
                {{ batchStatusName(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" :width="compactTable ? 96 : 112" fixed="right">
            <template #default="scope">
              <div class="farm-actions">
                <el-tooltip content="查看批次">
                  <el-button circle :icon="View" aria-label="查看批次" @click="openDetail(scope.row)" />
                </el-tooltip>
                <el-tooltip v-if="canOperate && scope.row.status === 'ACTIVE'" content="登记变动">
                  <el-button
                    circle
                    type="primary"
                    :icon="EditPen"
                    aria-label="登记变动"
                    @click="openMovement(scope.row)"
                  />
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
        </el-table>
        <footer class="admin-pagination">
          <span>共 {{ pagination.total }} 个批次</span>
          <el-pagination
            :current-page="pagination.page"
            :page-size="pagination.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="pagination.total"
            layout="sizes, prev, pager, next"
            @current-change="changePage"
            @size-change="changePageSize"
          />
        </footer>
      </div>
    </template>

    <el-dialog v-model="entryDialogVisible" title="生猪批次入栏" width="min(94vw, 680px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveEntry">
        <div class="farm-form-grid">
          <el-form-item label="批次编号" required>
            <el-input v-model="entryForm.batchNo" maxlength="40" aria-label="批次编号" />
          </el-form-item>
          <el-form-item label="批次名称" required>
            <el-input v-model="entryForm.name" maxlength="80" placeholder="例如 八月育肥猪一批" aria-label="批次名称" />
          </el-form-item>
          <el-form-item label="入栏单号" required>
            <el-input v-model="entryForm.entryNo" maxlength="40" aria-label="入栏单号" />
          </el-form-item>
          <el-form-item label="入栏日期" required>
            <el-date-picker
              v-model="entryForm.entryDate"
              type="date"
              value-format="YYYY-MM-DD"
              :disabled-date="(value: Date) => value.getTime() > Date.now()"
              class="full-width-control"
              aria-label="入栏日期"
            />
          </el-form-item>
          <el-form-item label="入栏圈舍" required>
            <el-select v-model="entryForm.barnId" class="full-width-control" aria-label="入栏圈舍">
              <el-option
                v-for="barn in activePigBarns"
                :key="barn.id"
                :label="`${barn.name} (${barn.code}) · 容量 ${barn.capacity}`"
                :value="barn.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="初始头数" required>
            <el-input-number
              v-model="entryForm.initialCount"
              class="full-width-control"
              :min="1"
              :max="2000000000"
              :precision="0"
              controls-position="right"
              aria-label="初始头数"
            />
          </el-form-item>
          <el-form-item label="来源">
            <el-input v-model="entryForm.source" maxlength="120" placeholder="例如 自繁或供应户" aria-label="生猪来源" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="entryForm.notes" maxlength="500" placeholder="可填写检疫或入栏情况" aria-label="入栏备注" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="entryDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="entrySaving" @click="saveEntry">确认入栏</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="movementDialogVisible" title="登记存栏变动" width="min(94vw, 680px)" destroy-on-close>
      <div v-if="movementBatch" class="dialog-context">
        <strong>{{ movementBatch.name }}</strong> · 当前 {{ movementBatch.currentHeadCount }} 头 · {{ barnBalanceText(movementBatch) }}
      </div>
      <el-form label-position="top" @submit.prevent="saveMovement">
        <el-form-item label="变动类型" required>
          <el-radio-group
            :model-value="movementForm.movementType"
            aria-label="变动类型"
            @update:model-value="changeMovementType"
          >
            <el-radio-button v-for="item in movementTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <div class="farm-form-grid">
          <el-form-item label="变动单号" required>
            <el-input v-model="movementForm.movementNo" maxlength="40" aria-label="变动单号" />
          </el-form-item>
          <el-form-item label="变动日期" required>
            <el-date-picker
              v-model="movementForm.occurredOn"
              type="date"
              value-format="YYYY-MM-DD"
              :disabled-date="(value: Date) => value.getTime() > Date.now()"
              class="full-width-control"
              aria-label="变动日期"
            />
          </el-form-item>
          <el-form-item label="来源圈舍" required>
            <el-select
              v-model="movementForm.fromBarnId"
              class="full-width-control"
              aria-label="来源圈舍"
              @change="changeSourceBarn"
            >
              <el-option
                v-for="barn in sourceBarns"
                :key="barn.barnId"
                :label="`${barn.barnName} (${barn.barnCode}) · ${barn.headCount} 头`"
                :value="barn.barnId"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="movementForm.movementType === 'TRANSFER'" label="目标圈舍" required>
            <el-select v-model="movementForm.toBarnId" class="full-width-control" aria-label="目标圈舍">
              <el-option
                v-for="barn in destinationBarns"
                :key="barn.id"
                :label="`${barn.name} (${barn.code}) · 容量 ${barn.capacity}`"
                :value="barn.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="变动头数" required>
            <el-input-number
              v-model="movementForm.quantity"
              class="full-width-control"
              :min="1"
              :max="2000000000"
              :precision="0"
              controls-position="right"
              aria-label="变动头数"
            />
          </el-form-item>
          <el-form-item v-if="movementForm.movementType === 'DEATH' || movementForm.movementType === 'CULL'" label="原因" required>
            <el-input v-model="movementForm.reason" maxlength="255" aria-label="变动原因" />
          </el-form-item>
          <el-form-item label="备注" class="farm-form-span">
            <el-input v-model="movementForm.notes" maxlength="500" aria-label="变动备注" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="movementDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="movementSaving" @click="saveMovement">确认登记</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="生猪批次详情" width="min(96vw, 960px)" destroy-on-close>
      <div v-loading="detailLoading" class="livestock-detail">
        <template v-if="detailBatch">
          <div class="livestock-detail-heading">
            <div class="farm-name-cell"><strong>{{ detailBatch.name }}</strong><span>{{ detailBatch.batchNo }} · {{ detailBatch.entryDate }} 入栏</span></div>
            <div class="farm-actions">
              <el-button v-if="canOperate" type="primary" :icon="Plus" @click="openProduction(detailBatch.status === 'ACTIVE' ? 'feeding' : 'cost')">{{ detailBatch.status === "ACTIVE" ? "生产记录" : "补录成本" }}</el-button>
              <el-tag :type="detailBatch.status === 'ACTIVE' ? 'success' : 'info'" effect="plain">{{ batchStatusName(detailBatch.status) }}</el-tag>
            </div>
          </div>
          <div class="livestock-detail-summary">
            <div><span>初始头数</span><strong>{{ detailBatch.initialCount }} 头</strong></div>
            <div><span>当前存栏</span><strong>{{ detailBatch.currentHeadCount }} 头</strong></div>
            <div><span>死亡 / 淘汰</span><strong>{{ detailBatch.deathCount }} / {{ detailBatch.cullCount }} 头</strong></div>
            <div><span>累计出栏</span><strong>{{ detailBatch.exitCount }} 头</strong></div>
            <div><span>最近均重</span><strong>{{ detailBatch.productionSummary?.latestAverageWeight ?? "-" }}<template v-if="detailBatch.productionSummary?.latestAverageWeight"> kg</template></strong></div>
            <div><span>日增重 ADG</span><strong>{{ detailBatch.productionSummary?.adg ?? "-" }}<template v-if="detailBatch.productionSummary?.adg"> kg/天</template></strong></div>
            <div><span>累计饲料</span><strong>{{ detailBatch.productionSummary?.feedWeightComplete ? detailBatch.productionSummary.totalFeedWeightKg : "单位待换算" }}<template v-if="detailBatch.productionSummary?.feedWeightComplete"> kg</template></strong></div>
            <div><span>料肉比 FCR</span><strong>{{ detailBatch.productionSummary?.fcr ?? "-" }}<template v-if="detailBatch.productionSummary?.fcrEstimated">（估算）</template></strong></div>
            <div><span>直接物料成本</span><strong>¥ {{ detailBatch.productionSummary?.totalDirectCost ?? "0.00" }}</strong></div>
            <div><span>其他生产成本</span><strong>¥ {{ detailBatch.productionSummary?.totalAdditionalCost ?? "0.00" }}</strong></div>
            <div><span>批次生产成本</span><strong>¥ {{ detailBatch.productionSummary?.totalProductionCost ?? "0.00" }}</strong></div>
            <div><span>头均生产成本</span><strong><template v-if="detailBatch.productionSummary?.productionCostPerHead">¥ {{ detailBatch.productionSummary.productionCostPerHead }}<small>{{ detailBatch.productionSummary.productionCostPerHeadBasis === "EXITED" ? " / 已出栏" : " / 在养估算" }}</small></template><template v-else>-</template></strong></div>
          </div>
          <section class="livestock-detail-section">
            <header><h2>生产趋势</h2><span>存栏来自数量流水，均重仅显示实际抽样记录</span></header>
            <LivestockProductionTrendChart :data="detailBatch.productionTrend ?? []" />
          </section>
          <section class="livestock-detail-section">
            <header>
              <h2>入栏、人工与公共费用</h2>
              <el-button v-if="canOperate" text type="primary" @click="openProduction('cost')">登记成本</el-button>
            </header>
            <div class="livestock-cost-breakdown" aria-label="批次其他生产成本结构">
              <div v-for="item in detailBatch.productionSummary?.additionalCostBreakdown ?? []" :key="item.costType">
                <span>{{ costTypeNames[item.costType as LivestockCostType] }}</span>
                <strong>¥ {{ item.amount }}</strong>
                <small>{{ item.recordCount }} 笔有效记录</small>
              </div>
              <p v-if="!detailBatch.productionSummary?.additionalCostBreakdown.length">暂无入栏、人工或公共费用</p>
            </div>
            <div class="farm-table-shell">
              <el-table :data="detailBatch.costEntries ?? []" row-key="id" empty-text="暂无其他生产成本记录">
                <el-table-column label="日期 / 单号" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.businessDate }}</strong><span>{{ scope.row.entryNo }}</span></div></template></el-table-column>
                <el-table-column label="类型" width="130"><template #default="scope">{{ costTypeNames[scope.row.costType as LivestockCostType] }}</template></el-table-column>
                <el-table-column label="说明" min-width="180"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.description }}</strong><span>{{ scope.row.notes || "无备注" }}</span></div></template></el-table-column>
                <el-table-column label="金额" width="120" align="right"><template #default="scope"><strong :class="{ 'cancelled-cost': scope.row.status === 'CANCELLED' }">¥ {{ scope.row.amount }}</strong></template></el-table-column>
                <el-table-column label="状态" width="90"><template #default="scope"><el-tag :type="scope.row.status === 'POSTED' ? 'success' : 'info'" effect="plain">{{ scope.row.status === "POSTED" ? "有效" : "已撤销" }}</el-tag></template></el-table-column>
                <el-table-column v-if="canOperate" label="操作" width="74" fixed="right"><template #default="scope"><el-button v-if="scope.row.status === 'POSTED'" link type="danger" @click="cancelCostEntry(scope.row)">撤销</el-button></template></el-table-column>
              </el-table>
            </div>
          </section>
          <section class="livestock-detail-section">
            <header><h2>当前圈舍分布</h2><span>{{ detailBatch.source || "未填写来源" }}</span></header>
            <div class="farm-table-shell">
              <el-table :data="detailBatch.barnBalances" row-key="barnId" empty-text="当前批次已无存栏">
                <el-table-column label="圈舍" min-width="180"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.barnName }}</strong><span>{{ scope.row.barnCode }}</span></div></template></el-table-column>
                <el-table-column prop="headCount" label="当前头数" width="120" align="right"><template #default="scope"><strong>{{ scope.row.headCount }}</strong> 头</template></el-table-column>
                <el-table-column prop="barnCapacity" label="设计容量" width="120" align="right"><template #default="scope">{{ scope.row.barnCapacity }} 头</template></el-table-column>
              </el-table>
            </div>
          </section>
          <section class="livestock-detail-section">
            <header>
              <h2>批次直接成本</h2>
              <el-button v-if="canOperate && detailBatch.status === 'ACTIVE'" text type="primary" @click="openProduction('feeding')">领用物料</el-button>
            </header>
            <div class="livestock-cost-breakdown" aria-label="批次直接成本结构">
              <div v-for="item in detailBatch.productionSummary?.costBreakdown ?? []" :key="item.category">
                <span>{{ costCategoryName(item.category) }}</span>
                <strong>¥ {{ item.amount }}</strong>
                <small>{{ item.recordCount }} 笔</small>
              </div>
              <p v-if="!detailBatch.productionSummary?.costBreakdown.length">暂无已归集成本</p>
            </div>
            <div class="farm-table-shell">
              <el-table :data="detailBatch.materialRecords ?? []" row-key="id" empty-text="暂无批次领退料记录">
                <el-table-column label="日期 / 单号" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.operationDate }}</strong><span>{{ scope.row.documentNo }}</span></div></template></el-table-column>
                <el-table-column label="物料" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.itemName }}</strong><span>{{ costCategoryName(scope.row.itemType) }} · {{ scope.row.itemCode }}</span></div></template></el-table-column>
                <el-table-column label="仓库" min-width="120" prop="warehouseName" />
                <el-table-column label="数量" width="110" align="right"><template #default="scope"><strong>{{ scope.row.operationType === 'return' ? '-' : '' }}{{ scope.row.quantity }}</strong> {{ scope.row.unitName }}</template></el-table-column>
                <el-table-column label="计入成本" width="120" align="right"><template #default="scope">{{ scope.row.operationType === 'return' ? '-' : '' }}¥ {{ scope.row.amount }}</template></el-table-column>
              </el-table>
            </div>
          </section>
          <section class="livestock-detail-section">
            <header>
              <h2>健康、防疫与用药</h2>
              <el-button v-if="canOperate && detailBatch.status === 'ACTIVE'" text type="primary" @click="openProduction('health')">登记健康</el-button>
            </header>
            <div class="farm-table-shell">
              <el-table :data="detailBatch.healthRecords ?? []" row-key="id" empty-text="暂无健康记录">
                <el-table-column label="日期 / 单号" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.occurredOn }}</strong><span>{{ scope.row.recordNo }}</span></div></template></el-table-column>
                <el-table-column label="类型" width="90"><template #default="scope">{{ healthTypeNames[scope.row.recordType as LivestockHealthType] }}</template></el-table-column>
                <el-table-column label="事项" min-width="180" prop="description" />
                <el-table-column label="药品 / 剂量" min-width="160"><template #default="scope">{{ scope.row.medicineName || '-' }}<template v-if="scope.row.dosage"> · {{ scope.row.dosage }}</template></template></el-table-column>
              </el-table>
            </div>
          </section>
          <section class="livestock-detail-section">
            <header>
              <h2>称重记录</h2>
              <el-button v-if="canOperate && detailBatch.status === 'ACTIVE'" text type="primary" @click="openProduction('weight')">登记称重</el-button>
            </header>
            <div class="farm-table-shell">
              <el-table :data="detailBatch.weightRecords ?? []" row-key="id" empty-text="暂无称重记录">
                <el-table-column label="日期 / 单号" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.occurredOn }}</strong><span>{{ scope.row.recordNo }}</span></div></template></el-table-column>
                <el-table-column label="抽样头数" width="110" align="right"><template #default="scope">{{ scope.row.sampleCount }} 头</template></el-table-column>
                <el-table-column label="平均体重" width="130" align="right"><template #default="scope"><strong>{{ scope.row.averageWeight }}</strong> kg</template></el-table-column>
                <el-table-column label="备注" min-width="180"><template #default="scope">{{ scope.row.notes || '-' }}</template></el-table-column>
              </el-table>
            </div>
          </section>
          <section class="livestock-detail-section">
            <header><h2>存栏变动流水</h2><span>共 {{ detailBatch.movementCount }} 条</span></header>
            <div class="farm-table-shell">
              <el-table :data="detailBatch.movements ?? []" row-key="id" empty-text="暂无存栏变动">
                <el-table-column label="日期 / 单号" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.occurredOn }}</strong><span>{{ scope.row.movementNo }}</span></div></template></el-table-column>
                <el-table-column label="类型" width="90"><template #default="scope"><el-tag :type="movementTag(scope.row.movementType)" effect="plain">{{ movementTypeName(scope.row.movementType) }}</el-tag></template></el-table-column>
                <el-table-column label="圈舍" min-width="190"><template #default="scope">{{ movementDirection(scope.row) }}</template></el-table-column>
                <el-table-column prop="quantity" label="头数" width="90" align="right"><template #default="scope"><strong>{{ scope.row.quantity }}</strong></template></el-table-column>
                <el-table-column label="原因 / 备注" min-width="180"><template #default="scope">{{ scope.row.reason || scope.row.notes || "-" }}</template></el-table-column>
              </el-table>
            </div>
          </section>
        </template>
      </div>
      <template #footer><el-button @click="detailDialogVisible = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="productionDialogVisible" title="登记生产记录" width="min(94vw, 680px)" destroy-on-close>
      <el-radio-group v-model="productionType" class="production-type" aria-label="生产记录类型">
        <el-radio-button value="feeding" :disabled="detailBatch?.status === 'CLOSED'">物料领用</el-radio-button>
        <el-radio-button value="health" :disabled="detailBatch?.status === 'CLOSED'">健康 / 用药</el-radio-button>
        <el-radio-button value="weight" :disabled="detailBatch?.status === 'CLOSED'">称重</el-radio-button>
        <el-radio-button value="cost">生产成本</el-radio-button>
      </el-radio-group>
      <el-form label-position="top" @submit.prevent="saveProductionRecord">
        <div class="farm-form-grid">
          <el-form-item label="记录单号" required><el-input v-model="productionForm.recordNo" maxlength="40" /></el-form-item>
          <el-form-item label="业务日期" required><el-date-picker v-model="productionForm.occurredOn" type="date" value-format="YYYY-MM-DD" class="full-width-control" :disabled-date="(value: Date) => value.getTime() > Date.now()" /></el-form-item>
          <template v-if="productionType === 'feeding'">
            <el-form-item label="领料仓库" required><el-select v-model="productionForm.warehouseId" class="full-width-control"><el-option v-for="item in warehouses" :key="item.id" :label="`${item.name} (${item.code})`" :value="item.id" /></el-select></el-form-item>
            <el-form-item label="领用物料" required><el-select v-model="productionForm.itemId" class="full-width-control"><el-option v-for="item in productionItems" :key="item.id" :label="`${item.name} · ${costCategoryName(item.itemType)} (${item.unitName})`" :value="item.id" /></el-select></el-form-item>
            <el-form-item label="领用数量" required><el-input-number v-model="productionForm.quantity" class="full-width-control" :min="0.001" :precision="3" controls-position="right" /></el-form-item>
            <el-form-item label="批号"><el-input v-model="productionForm.lotNo" maxlength="64" placeholder="启用批次管理的物料必填" /></el-form-item>
          </template>
          <template v-else-if="productionType === 'health'">
            <el-form-item label="记录类型" required><el-select v-model="productionForm.healthType" class="full-width-control"><el-option v-for="(label, value) in healthTypeNames" :key="value" :label="label" :value="value" /></el-select></el-form-item>
            <el-form-item label="健康事项" required><el-input v-model="productionForm.description" maxlength="255" placeholder="例如 猪瘟疫苗首免" /></el-form-item>
            <el-form-item label="药品 / 疫苗"><el-input v-model="productionForm.medicineName" maxlength="120" /></el-form-item>
            <el-form-item label="剂量"><el-input v-model="productionForm.dosage" maxlength="80" placeholder="例如 每头 1 头份" /></el-form-item>
          </template>
          <template v-else-if="productionType === 'weight'">
            <el-form-item label="抽样头数" required><el-input-number v-model="productionForm.sampleCount" class="full-width-control" :min="1" :precision="0" controls-position="right" /></el-form-item>
            <el-form-item label="平均体重（kg）" required><el-input-number v-model="productionForm.averageWeight" class="full-width-control" :min="0.001" :precision="3" controls-position="right" /></el-form-item>
          </template>
          <template v-else>
            <el-form-item label="成本类型" required><el-select v-model="productionForm.costType" class="full-width-control"><el-option v-for="(label, value) in costTypeNames" :key="value" :label="label" :value="value" /></el-select></el-form-item>
            <el-form-item label="金额（元）" required><el-input-number v-model="productionForm.amount" class="full-width-control" :min="0.01" :max="99999999999999.99" :precision="2" controls-position="right" /></el-form-item>
            <el-form-item label="成本说明" required class="farm-form-span"><el-input v-model="productionForm.description" maxlength="255" placeholder="例如 仔猪采购款或本月饲养人工" /></el-form-item>
          </template>
          <el-form-item v-if="productionType !== 'feeding'" label="备注" class="farm-form-span"><el-input v-model="productionForm.notes" maxlength="500" /></el-form-item>
        </div>
      </el-form>
      <el-alert v-if="productionType === 'feeding' && (!warehouses.length || !productionItems.length)" type="warning" :closable="false" title="请先在库存管理中建立可用仓库和生产物料，并完成采购入库。" />
      <template #footer>
        <el-button @click="productionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="productionSaving" @click="saveProductionRecord">确认登记</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.livestock-toolbar {
  grid-template-columns: minmax(240px, 1fr) 150px auto auto;
}

.livestock-analysis {
  min-width: 0;
}

.livestock-analysis-period {
  width: 130px;
  flex: 0 0 130px;
}

.livestock-analysis-content {
  min-height: 390px;
}

.livestock-analysis-chart-shell {
  padding: 18px;
  border: 1px solid var(--line);
  background: var(--surface);
}

.livestock-farm-trend-chart {
  width: 100%;
  height: 290px;
}

.livestock-comparison-header {
  display: flex;
  min-height: 66px;
  align-items: center;
}

.livestock-comparison-header h3 {
  margin: 0 0 4px;
  color: var(--ink);
  font-size: 15px;
  font-weight: 650;
}

.livestock-comparison-header span {
  color: var(--muted);
  font-size: 12px;
}

.summary-card small {
  margin-left: 4px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
}

.livestock-detail {
  min-height: 220px;
}

.production-type {
  margin-bottom: 18px;
}

.livestock-detail-heading,
.livestock-detail-section > header {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
}

.livestock-detail-heading {
  margin-bottom: 16px;
}

.livestock-detail-summary {
  display: grid;
  margin-bottom: 20px;
  border: 1px solid var(--line);
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.livestock-detail-summary > div {
  display: flex;
  min-width: 0;
  min-height: 72px;
  padding: 12px 14px;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
  border-right: 1px solid var(--line);
}

.livestock-detail-summary > div:last-child {
  border-right: 0;
}

.livestock-detail-summary span,
.livestock-detail-section > header span {
  color: var(--muted);
  font-size: 12px;
}

.livestock-detail-summary strong {
  overflow-wrap: anywhere;
  color: var(--ink);
  font-size: 18px;
}

.livestock-detail-summary strong small {
  color: var(--muted);
  font-size: 11px;
  font-weight: 500;
}

.livestock-detail-section {
  margin-top: 18px;
}

.livestock-detail-section > header {
  margin-bottom: 10px;
}

.livestock-detail-section h2 {
  margin: 0;
  color: var(--ink);
  font-size: 15px;
}

.livestock-production-trend-chart {
  width: 100%;
  height: 280px;
}

.livestock-cost-breakdown {
  display: grid;
  margin-bottom: 12px;
  border: 1px solid var(--line);
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.livestock-cost-breakdown > div {
  display: flex;
  min-width: 0;
  min-height: 64px;
  padding: 10px 12px;
  flex-direction: column;
  gap: 3px;
  border-right: 1px solid var(--line);
}

.livestock-cost-breakdown > div:last-child {
  border-right: 0;
}

.livestock-cost-breakdown span,
.livestock-cost-breakdown small,
.livestock-cost-breakdown > p {
  color: var(--muted);
  font-size: 12px;
}

.livestock-cost-breakdown strong {
  overflow-wrap: anywhere;
  color: var(--ink);
  font-size: 16px;
}

.livestock-cost-breakdown > p {
  margin: 0;
  padding: 16px;
  grid-column: 1 / -1;
}

.cancelled-cost {
  color: var(--muted);
  text-decoration: line-through;
}

@media (max-width: 900px) {
  .livestock-toolbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .livestock-toolbar .el-input {
    grid-column: 1 / -1;
  }
}

@media (max-width: 620px) {
  .livestock-toolbar {
    grid-template-columns: minmax(0, 1fr);
  }

  .livestock-toolbar .el-input {
    grid-column: auto;
  }

  .livestock-detail-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .livestock-detail-summary > div:nth-child(2) {
    border-right: 0;
  }

  .livestock-detail-summary > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--line);
  }

  .livestock-production-trend-chart {
    height: 240px;
  }

  .livestock-farm-trend-chart {
    height: 250px;
  }

  .livestock-analysis-chart-shell {
    padding: 12px;
  }

  .livestock-analysis .analysis-section-header {
    align-items: stretch;
    flex-direction: column;
  }

  .livestock-analysis-period {
    width: 100%;
    flex-basis: auto;
  }

  .livestock-cost-breakdown {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
