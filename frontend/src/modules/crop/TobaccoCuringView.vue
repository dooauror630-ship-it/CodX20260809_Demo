<script setup lang="ts">
import { Check, Plus, Refresh } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";

import { errorMessage } from "@/api/client";
import { getCatalogs } from "@/api/catalogs";
import { completeTobaccoCuringBatch, createTobaccoCuringBatch, getCropCycles, getTobaccoCuringBatches } from "@/api/crop";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { Unit } from "@/types/catalog";
import type { CropCycle, TobaccoCuringBatch } from "@/types/crop";

const auth = useAuthStore();
const farms = useFarmStore();
const loading = ref(false);
const saving = ref(false);
const createVisible = ref(false);
const completeVisible = ref(false);
const cycles = ref<CropCycle[]>([]);
const units = ref<Unit[]>([]);
const batches = ref<TobaccoCuringBatch[]>([]);
const selectedCycleId = ref<number | null>(null);
const completingBatch = ref<TobaccoCuringBatch | null>(null);
const localDateTime = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 19);
const createForm = reactive({ curingNo: "", startAt: localDateTime(), inputWeight: undefined as number | undefined, unitId: null as number | null, notes: "" });
const completeForm = reactive({ endAt: localDateTime(), outputWeight: undefined as number | undefined, fuelCost: 0, electricityCost: 0 });
const writable = computed(() => auth.isAdmin || ["manager", "operator"].includes(farms.currentFarm?.accessRole ?? ""));
const completed = computed(() => batches.value.filter((item) => item.status === "COMPLETED"));
const averageEfficiency = computed(() => completed.value.length ? (completed.value.reduce((sum, item) => sum + Number(item.curingEfficiency), 0) / completed.value.length).toFixed(2) : "--");

async function loadReferences() {
  const farmId = farms.currentFarmId;
  if (!farmId) return;
  try {
    const [cycleData, catalogs] = await Promise.all([
      getCropCycles({ farmId, page: 1, pageSize: 100, status: "HARVESTING" }), getCatalogs(),
    ]);
    cycles.value = cycleData.items.filter((item) => item.cropTypeName === "烟草");
    units.value = catalogs.units.filter((item) => item.isActive);
    if (!cycles.value.some((item) => item.id === selectedCycleId.value)) selectedCycleId.value = cycles.value[0]?.id ?? null;
  } catch (error) { ElMessage.error(errorMessage(error)); }
}

async function loadBatches() {
  const farmId = farms.currentFarmId;
  if (!farmId || !selectedCycleId.value) { batches.value = []; return; }
  loading.value = true;
  try { batches.value = (await getTobaccoCuringBatches({ farmId, cropCycleId: selectedCycleId.value })).items; }
  catch (error) { ElMessage.error(errorMessage(error)); }
  finally { loading.value = false; }
}

function openCreate() {
  Object.assign(createForm, { curingNo: `HK-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}`, startAt: localDateTime(), inputWeight: undefined, unitId: units.value.find((item) => item.code === "KG")?.id ?? units.value[0]?.id ?? null, notes: "" });
  createVisible.value = true;
}

async function saveCreate() {
  const farmId = farms.currentFarmId;
  if (!farmId || !selectedCycleId.value || !createForm.curingNo || !createForm.startAt || !createForm.inputWeight || !createForm.unitId) return ElMessage.error("请完整填写入炉信息");
  saving.value = true;
  try {
    await createTobaccoCuringBatch({ farmId, cropCycleId: selectedCycleId.value, curingNo: createForm.curingNo, startAt: createForm.startAt, inputWeight: createForm.inputWeight, unitId: createForm.unitId, notes: createForm.notes.trim() || null });
    ElMessage.success("烘烤批次已开始"); createVisible.value = false; await loadBatches();
  } catch (error) { ElMessage.error(errorMessage(error)); }
  finally { saving.value = false; }
}

function openComplete(batch: TobaccoCuringBatch) {
  completingBatch.value = batch;
  Object.assign(completeForm, { endAt: localDateTime(), outputWeight: undefined, fuelCost: 0, electricityCost: 0 });
  completeVisible.value = true;
}

async function saveComplete() {
  if (!completingBatch.value || !completeForm.endAt || !completeForm.outputWeight) return ElMessage.error("请完整填写出炉信息");
  saving.value = true;
  try {
    await completeTobaccoCuringBatch(completingBatch.value.id, { ...completeForm, outputWeight: completeForm.outputWeight });
    ElMessage.success("烘烤批次已完成"); completeVisible.value = false; await loadBatches();
  } catch (error) { ElMessage.error(errorMessage(error)); }
  finally { saving.value = false; }
}

watch(() => farms.currentFarmId, async () => { selectedCycleId.value = null; await loadReferences(); await loadBatches(); }, { immediate: true });
watch(selectedCycleId, () => void loadBatches());
</script>

<template>
  <section class="admin-page">
    <header class="admin-page-header"><div><p class="admin-eyebrow">烟草生产</p><h1>烟草烘烤</h1><p>记录每炉入炉、出炉和能源成本。</p></div><div class="admin-header-actions"><el-button :icon="Refresh" @click="loadBatches">刷新</el-button><el-button v-if="writable" type="primary" :icon="Plus" :disabled="!selectedCycleId" @click="openCreate">开始烘烤</el-button></div></header>
    <div class="admin-toolbar"><el-select v-model="selectedCycleId" placeholder="请选择采收中烟草周期" filterable><el-option v-for="cycle in cycles" :key="cycle.id" :label="`${cycle.cycleCode} · ${cycle.varietyName ?? ''}`" :value="cycle.id" /></el-select><span>已完成 {{ completed.length }} 炉 · 平均得率 {{ averageEfficiency }}<template v-if="averageEfficiency !== '--'">%</template></span></div>
    <div class="admin-table-panel"><el-table v-loading="loading" :data="batches" row-key="id" empty-text="暂无烘烤批次"><el-table-column prop="curingNo" label="烘烤批号" min-width="140" /><el-table-column label="状态" width="100"><template #default="scope"><el-tag :type="scope.row.status === 'COMPLETED' ? 'success' : 'warning'">{{ scope.row.status === "COMPLETED" ? "已完成" : "烘烤中" }}</el-tag></template></el-table-column><el-table-column label="入炉 / 出炉" min-width="180"><template #default="scope">{{ scope.row.inputWeight }} / {{ scope.row.outputWeight ?? "--" }} {{ scope.row.unitName }}</template></el-table-column><el-table-column label="得率" width="100"><template #default="scope">{{ scope.row.curingEfficiency ? `${scope.row.curingEfficiency}%` : "--" }}</template></el-table-column><el-table-column label="燃料 / 电费" min-width="150"><template #default="scope">¥ {{ scope.row.fuelCost }} / {{ scope.row.electricityCost }}</template></el-table-column><el-table-column label="时间" min-width="180"><template #default="scope">{{ scope.row.startAt }}<br />{{ scope.row.endAt ?? "进行中" }}</template></el-table-column><el-table-column v-if="writable" label="操作" width="100" align="right"><template #default="scope"><el-button v-if="scope.row.status === 'IN_PROGRESS'" link type="primary" :icon="Check" @click="openComplete(scope.row)">完成</el-button></template></el-table-column></el-table></div>
    <el-dialog v-model="createVisible" title="开始烘烤" width="min(92vw, 560px)"><el-form label-position="top"><div class="farm-form-grid"><el-form-item label="烘烤批号" required><el-input v-model="createForm.curingNo" maxlength="40" /></el-form-item><el-form-item label="开始时间" required><el-date-picker v-model="createForm.startAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="full-width-control" /></el-form-item><el-form-item label="入炉重量" required><el-input-number v-model="createForm.inputWeight" :min="0.001" :precision="3" class="full-width-control" /></el-form-item><el-form-item label="计量单位" required><el-select v-model="createForm.unitId" class="full-width-control"><el-option v-for="unit in units" :key="unit.id" :label="unit.name" :value="unit.id" /></el-select></el-form-item></div><el-form-item label="备注"><el-input v-model="createForm.notes" type="textarea" maxlength="500" /></el-form-item><div class="dialog-footer"><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveCreate">开始烘烤</el-button></div></el-form></el-dialog>
    <el-dialog v-model="completeVisible" title="完成烘烤" width="min(92vw, 560px)"><el-form label-position="top"><div class="farm-form-grid"><el-form-item label="结束时间" required><el-date-picker v-model="completeForm.endAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" class="full-width-control" /></el-form-item><el-form-item label="出炉重量" required><el-input-number v-model="completeForm.outputWeight" :min="0.001" :max="Number(completingBatch?.inputWeight ?? 0)" :precision="3" class="full-width-control" /></el-form-item><el-form-item label="燃料成本（元）"><el-input-number v-model="completeForm.fuelCost" :min="0" :precision="2" class="full-width-control" /></el-form-item><el-form-item label="电费（元）"><el-input-number v-model="completeForm.electricityCost" :min="0" :precision="2" class="full-width-control" /></el-form-item></div><div class="dialog-footer"><el-button @click="completeVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveComplete">确认完成</el-button></div></el-form></el-dialog>
  </section>
</template>
