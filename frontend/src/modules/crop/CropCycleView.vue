<script setup lang="ts">
import { Plus, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";

import { errorMessage } from "@/api/client";
import { getCatalogs } from "@/api/catalogs";
import { createCropCycle, getCropCycles, updateCropCycleStatus } from "@/api/crop";
import { getPlots } from "@/api/farms";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { CatalogData, CropType } from "@/types/catalog";
import type { Plot } from "@/types/farm";
import type { CropCycle, CropCycleStatus } from "@/types/crop";

const auth = useAuthStore();
const farmStore = useFarmStore();
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const cycles = ref<CropCycle[]>([]);
const plots = ref<Plot[]>([]);
const catalog = ref<CatalogData>({ units: [], livestockSpecies: [], cropTypes: [] });
const filters = reactive({ keyword: "", status: "all" as CropCycleStatus | "all" });
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });
const form = reactive({ cycleCode: "", plotId: null as number | null, cropTypeId: null as number | null, varietyId: null as number | null, areaMu: undefined as number | undefined, plannedStartDate: "", plannedEndDate: "", notes: "" });
const statusLabels: Record<CropCycleStatus, string> = { PLANNED: "计划中", ACTIVE: "种植中", HARVESTING: "采收中", CLOSED: "已关闭", CANCELLED: "已取消" };
const writable = computed(() => auth.isAdmin || ["manager", "operator"].includes(farmStore.currentFarm?.accessRole ?? ""));
const selectedType = computed<CropType | null>(() => catalog.value.cropTypes.find((item) => item.id === form.cropTypeId) ?? null);

async function load() {
  const farmId = farmStore.currentFarmId;
  if (!farmId) { cycles.value = []; pagination.total = 0; return; }
  loading.value = true;
  try {
    const data = await getCropCycles({ farmId, page: pagination.page, pageSize: pagination.pageSize, keyword: filters.keyword || undefined, status: filters.status });
    cycles.value = data.items; pagination.total = data.pagination.total;
  } catch (error) { ElMessage.error(errorMessage(error)); } finally { loading.value = false; }
}

async function loadReferences() {
  const farmId = farmStore.currentFarmId;
  if (!farmId) return;
  try {
    const [catalogs, plotData] = await Promise.all([getCatalogs(), getPlots({ farmId, page: 1, pageSize: 100, status: "active" })]);
    catalog.value = catalogs; plots.value = plotData.items;
  } catch (error) { ElMessage.error(errorMessage(error)); }
}

function openCreate() {
  Object.assign(form, { cycleCode: "", plotId: plots.value[0]?.id ?? null, cropTypeId: catalog.value.cropTypes[0]?.id ?? null, varietyId: null, areaMu: undefined, plannedStartDate: new Date().toISOString().slice(0, 10), plannedEndDate: "", notes: "" });
  form.varietyId = selectedType.value?.varieties[0]?.id ?? null;
  dialogVisible.value = true;
}

async function save() {
  const farmId = farmStore.currentFarmId;
  if (!farmId || !form.plotId || !form.cropTypeId || !form.varietyId || !form.areaMu || !form.cycleCode || !form.plannedStartDate || !form.plannedEndDate) { ElMessage.error("请完整填写周期信息"); return; }
  saving.value = true;
  try { await createCropCycle({ farmId, cycleCode: form.cycleCode.trim(), plotId: form.plotId, cropTypeId: form.cropTypeId, varietyId: form.varietyId, areaMu: form.areaMu, plannedStartDate: form.plannedStartDate, plannedEndDate: form.plannedEndDate, notes: form.notes.trim() || null }); ElMessage.success("种植周期已创建"); dialogVisible.value = false; await load(); }
  catch (error) { ElMessage.error(errorMessage(error)); } finally { saving.value = false; }
}

async function changeStatus(cycle: CropCycle, status: CropCycleStatus) {
  try { const updated = await updateCropCycleStatus(cycle.id, status); Object.assign(cycle, updated); ElMessage.success("周期状态已更新"); }
  catch (error) { ElMessage.error(errorMessage(error)); }
}

function statusType(status: CropCycleStatus) { return status === "CLOSED" ? "success" : status === "CANCELLED" ? "info" : status === "HARVESTING" ? "warning" : status === "ACTIVE" ? "primary" : ""; }
function statusLabel(status: string) { return statusLabels[status as CropCycleStatus] ?? status; }
watch(() => form.cropTypeId, () => { form.varietyId = selectedType.value?.varieties[0]?.id ?? null; });
watch(() => farmStore.currentFarmId, () => { pagination.page = 1; void loadReferences(); void load(); }, { immediate: true });
</script>

<template>
  <section class="farm-page resource-page">
    <header class="page-header farm-page-header"><div><p class="eyebrow">CROP CYCLES</p><h1>种植周期</h1><p>{{ farmStore.currentFarm?.name ?? "尚未选择农场" }} · 共 {{ pagination.total }} 个周期</p></div><el-button v-if="writable && farmStore.currentFarm" type="primary" :icon="Plus" @click="openCreate">新建周期</el-button></header>
    <el-empty v-if="!farmStore.currentFarm" description="暂无可用农场" />
    <template v-else>
      <div class="farm-toolbar" role="search" aria-label="筛选种植周期"><el-input v-model="filters.keyword" clearable :prefix-icon="Search" placeholder="搜索周期编号、地块或作物" @keyup.enter="pagination.page = 1; load()" /><el-select v-model="filters.status" aria-label="周期状态"><el-option label="全部状态" value="all" /><el-option v-for="(label, value) in statusLabels" :key="value" :label="label" :value="value" /></el-select><el-button type="primary" :icon="Search" @click="pagination.page = 1; load()">查询</el-button><el-button :icon="Refresh" @click="filters.keyword = ''; filters.status = 'all'; pagination.page = 1; load()">重置</el-button></div>
      <div class="farm-table-shell"><el-table v-loading="loading" :data="cycles" row-key="id" empty-text="当前农场暂无种植周期"><el-table-column label="周期" min-width="180"><template #default="scope"><strong>{{ scope.row.cycleCode }}</strong><br /><span class="table-secondary">{{ scope.row.cropTypeName }} · {{ scope.row.varietyName }}</span></template></el-table-column><el-table-column label="地块" min-width="130"><template #default="scope">{{ scope.row.plotName }}<br /><span class="table-secondary">{{ scope.row.areaMu }} 亩</span></template></el-table-column><el-table-column label="计划区间" min-width="210"><template #default="scope">{{ scope.row.plannedStartDate }} 至 {{ scope.row.plannedEndDate }}</template></el-table-column><el-table-column label="状态" width="100"><template #default="scope"><el-tag :type="statusType(scope.row.status)" effect="plain">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column><el-table-column v-if="writable" label="操作" width="150"><template #default="scope"><el-button v-if="scope.row.status === 'PLANNED'" link type="primary" @click="changeStatus(scope.row, 'ACTIVE')">开始种植</el-button><el-button v-else-if="scope.row.status === 'ACTIVE'" link type="warning" @click="changeStatus(scope.row, 'HARVESTING')">开始采收</el-button><el-button v-else-if="scope.row.status === 'HARVESTING'" link type="success" @click="changeStatus(scope.row, 'CLOSED')">关闭周期</el-button></template></el-table-column></el-table><footer class="admin-pagination"><span>共 {{ pagination.total }} 个周期</span><el-pagination v-model:current-page="pagination.page" :page-size="pagination.pageSize" layout="prev, pager, next" :total="pagination.total" @current-change="load" /></footer></div>
    </template>
    <el-dialog v-model="dialogVisible" title="新建种植周期" width="min(92vw, 620px)"><el-form label-position="top" @submit.prevent="save"><div class="farm-form-grid"><el-form-item label="周期编号" required><el-input v-model="form.cycleCode" maxlength="40" /></el-form-item><el-form-item label="地块" required><el-select v-model="form.plotId" class="full-width-control"><el-option v-for="plot in plots" :key="plot.id" :label="`${plot.name}（${plot.areaMu}亩）`" :value="plot.id" /></el-select></el-form-item><el-form-item label="作物类型" required><el-select v-model="form.cropTypeId" class="full-width-control"><el-option v-for="type in catalog.cropTypes" :key="type.id" :label="type.name" :value="type.id" /></el-select></el-form-item><el-form-item label="品种" required><el-select v-model="form.varietyId" class="full-width-control"><el-option v-for="variety in selectedType?.varieties ?? []" :key="variety.id" :label="variety.name" :value="variety.id" /></el-select></el-form-item><el-form-item label="占用面积（亩）" required><el-input-number v-model="form.areaMu" :min="0.001" :precision="3" controls-position="right" class="full-width-control" /></el-form-item><el-form-item label="计划开始" required><el-date-picker v-model="form.plannedStartDate" type="date" value-format="YYYY-MM-DD" class="full-width-control" /></el-form-item><el-form-item label="计划结束" required><el-date-picker v-model="form.plannedEndDate" type="date" value-format="YYYY-MM-DD" class="full-width-control" /></el-form-item></div><el-form-item label="备注"><el-input v-model="form.notes" type="textarea" maxlength="500" /></el-form-item><div class="dialog-footer"><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">创建周期</el-button></div></el-form></el-dialog>
  </section>
</template>
