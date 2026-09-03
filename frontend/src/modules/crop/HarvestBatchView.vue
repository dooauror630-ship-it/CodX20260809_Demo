<script setup lang="ts">
import { Plus, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";

import { errorMessage } from "@/api/client";
import { getCatalogs } from "@/api/catalogs";
import { createHarvestBatch, getCropCycles, getHarvestBatches } from "@/api/crop";
import { getWarehouses } from "@/api/inventory";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { Unit } from "@/types/catalog";
import type { CropCycle, HarvestBatch } from "@/types/crop";
import type { Warehouse } from "@/types/inventory";

const auth = useAuthStore();
const farms = useFarmStore();
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const cycles = ref<CropCycle[]>([]);
const batches = ref<HarvestBatch[]>([]);
const warehouses = ref<Warehouse[]>([]);
const units = ref<Unit[]>([]);
const selectedCycleId = ref<number | null>(null);
const form = reactive({ harvestNo: "", harvestDate: new Date().toISOString().slice(0, 10), grossWeight: undefined as number | undefined, netWeight: undefined as number | undefined, unitId: null as number | null, warehouseId: null as number | null, notes: "" });
const writable = computed(() => auth.isAdmin || ["manager", "operator"].includes(farms.currentFarm?.accessRole ?? ""));
const totalNetWeight = computed(() => batches.value.reduce((sum, item) => sum + Number(item.netWeight), 0));

async function loadReferences() {
  const farmId = farms.currentFarmId;
  if (!farmId) return;
  try {
    const [cycleData, warehouseData, catalogs] = await Promise.all([
      getCropCycles({ farmId, page: 1, pageSize: 100, status: "HARVESTING" }),
      getWarehouses({ farmId, page: 1, pageSize: 100, status: "active" }),
      getCatalogs(),
    ]);
    cycles.value = cycleData.items;
    warehouses.value = warehouseData.items;
    units.value = catalogs.units.filter((item) => item.isActive);
    if (!cycles.value.some((item) => item.id === selectedCycleId.value)) selectedCycleId.value = cycles.value[0]?.id ?? null;
  } catch (error) { ElMessage.error(errorMessage(error)); }
}

async function loadBatches() {
  const farmId = farms.currentFarmId;
  if (!farmId || !selectedCycleId.value) { batches.value = []; return; }
  loading.value = true;
  try { batches.value = (await getHarvestBatches({ farmId, cropCycleId: selectedCycleId.value })).items; }
  catch (error) { ElMessage.error(errorMessage(error)); }
  finally { loading.value = false; }
}

function openCreate() {
  Object.assign(form, { harvestNo: `HC-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}`, harvestDate: new Date().toISOString().slice(0, 10), grossWeight: undefined, netWeight: undefined, unitId: units.value.find((item) => item.code === "KG")?.id ?? units.value[0]?.id ?? null, warehouseId: warehouses.value[0]?.id ?? null, notes: "" });
  dialogVisible.value = true;
}

async function save() {
  const farmId = farms.currentFarmId;
  if (!farmId || !selectedCycleId.value || !form.harvestNo || !form.harvestDate || !form.grossWeight || !form.netWeight || !form.unitId || !form.warehouseId) return ElMessage.error("请完整填写采收信息");
  saving.value = true;
  try {
    await createHarvestBatch({ farmId, cropCycleId: selectedCycleId.value, harvestNo: form.harvestNo, harvestDate: form.harvestDate, grossWeight: form.grossWeight, netWeight: form.netWeight, unitId: form.unitId, warehouseId: form.warehouseId, notes: form.notes.trim() || null });
    ElMessage.success("采收批次已登记"); dialogVisible.value = false; await loadBatches();
  } catch (error) { ElMessage.error(errorMessage(error)); }
  finally { saving.value = false; }
}

watch(() => farms.currentFarmId, async () => { selectedCycleId.value = null; await loadReferences(); await loadBatches(); }, { immediate: true });
watch(selectedCycleId, () => void loadBatches());
</script>

<template>
  <section class="admin-page">
    <header class="admin-page-header"><div><p class="admin-eyebrow">种植生产</p><h1>采收批次</h1><p>按采收中周期登记毛重、净重和暂存仓库。</p></div><div class="admin-header-actions"><el-button :icon="Refresh" @click="loadBatches">刷新</el-button><el-button v-if="writable" type="primary" :icon="Plus" :disabled="!selectedCycleId" @click="openCreate">登记采收</el-button></div></header>
    <div class="admin-toolbar"><el-select v-model="selectedCycleId" placeholder="请选择采收中周期" filterable><el-option v-for="cycle in cycles" :key="cycle.id" :label="`${cycle.cycleCode} · ${cycle.cropTypeName ?? ''}`" :value="cycle.id" /></el-select><span>累计净重 {{ totalNetWeight }} {{ batches[0]?.unitName ?? '' }}</span></div>
    <div class="admin-table-panel"><el-table v-loading="loading" :data="batches" row-key="id" empty-text="暂无采收批次"><el-table-column prop="harvestNo" label="采收批号" min-width="150" /><el-table-column prop="harvestDate" label="采收日期" width="120" /><el-table-column label="毛重 / 净重" min-width="180"><template #default="scope">{{ scope.row.grossWeight }} / {{ scope.row.netWeight }} {{ scope.row.unitName }}</template></el-table-column><el-table-column prop="warehouseName" label="暂存仓库" min-width="150" /><el-table-column prop="notes" label="备注" min-width="180" show-overflow-tooltip /></el-table></div>
    <el-dialog v-model="dialogVisible" title="登记采收批次" width="min(92vw, 620px)"><el-form label-position="top"><div class="farm-form-grid"><el-form-item label="采收批号" required><el-input v-model="form.harvestNo" maxlength="40" /></el-form-item><el-form-item label="采收日期" required><el-date-picker v-model="form.harvestDate" type="date" value-format="YYYY-MM-DD" class="full-width-control" /></el-form-item><el-form-item label="毛重" required><el-input-number v-model="form.grossWeight" :min="0.001" :precision="3" class="full-width-control" /></el-form-item><el-form-item label="净重" required><el-input-number v-model="form.netWeight" :min="0.001" :max="form.grossWeight" :precision="3" class="full-width-control" /></el-form-item><el-form-item label="计量单位" required><el-select v-model="form.unitId" class="full-width-control"><el-option v-for="unit in units" :key="unit.id" :label="unit.name" :value="unit.id" /></el-select></el-form-item><el-form-item label="暂存仓库" required><el-select v-model="form.warehouseId" class="full-width-control"><el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" /></el-select></el-form-item></div><el-form-item label="备注"><el-input v-model="form.notes" type="textarea" maxlength="500" /></el-form-item><div class="dialog-footer"><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">登记采收</el-button></div></el-form></el-dialog>
  </section>
</template>
