<script setup lang="ts">
import { Link, Plus, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";

import { errorMessage } from "@/api/client";
import {
  createFieldOperation,
  createFieldOperationInput,
  getAvailableFieldOperationInputs,
  getCropCycleCostSummary,
  getCropCycles,
  getCropOperationSuggestions,
  getFieldOperationInputs,
  getFieldOperations,
} from "@/api/crop";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type {
  AvailableFieldOperationInput,
  CropCycle,
  CropCycleCostSummary,
  CropOperationSuggestion,
  FieldOperation,
  FieldOperationInput,
  FieldOperationType,
} from "@/types/crop";

const auth = useAuthStore();
const farmStore = useFarmStore();
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const inputDialogVisible = ref(false);
const inputLoading = ref(false);
const bindingDocumentId = ref<number | null>(null);
const cycles = ref<CropCycle[]>([]);
const operations = ref<FieldOperation[]>([]);
const costSummary = ref<CropCycleCostSummary | null>(null);
const suggestions = ref<CropOperationSuggestion[]>([]);
const operationInputs = ref<FieldOperationInput[]>([]);
const availableInputs = ref<AvailableFieldOperationInput[]>([]);
const inputOperation = ref<FieldOperation | null>(null);
const selectedCycleId = ref<number | null>(null);
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });
const form = reactive({
  operationType: "LAND_PREPARATION" as FieldOperationType,
  operationDate: new Date().toISOString().slice(0, 10),
  areaMu: undefined as number | undefined,
  laborHours: 0,
  machineHours: 0,
  laborCost: 0,
  serviceCost: 0,
  notes: "",
});
const operationTypes: Array<{ value: FieldOperationType; label: string }> = [
  { value: "LAND_PREPARATION", label: "整地" },
  { value: "SOWING", label: "播种" },
  { value: "TRANSPLANTING", label: "移栽" },
  { value: "IRRIGATION", label: "灌溉" },
  { value: "FERTILIZATION", label: "施肥" },
  { value: "PEST_CONTROL", label: "用药" },
  { value: "WEEDING", label: "除草" },
  { value: "OTHER", label: "其他" },
];
const writable = computed(
  () =>
    auth.isAdmin ||
    ["manager", "operator"].includes(farmStore.currentFarm?.accessRole ?? ""),
);
const selectedCycle = computed(
  () =>
    cycles.value.find((cycle) => cycle.id === selectedCycleId.value) ?? null,
);
const totalInputCost = computed(() =>
  operationInputs.value
    .reduce((total, item) => total + Number(item.amount), 0)
    .toFixed(2),
);

async function loadCycles() {
  const farmId = farmStore.currentFarmId;
  if (!farmId) {
    cycles.value = [];
    selectedCycleId.value = null;
    return;
  }
  try {
    const data = await getCropCycles({
      farmId,
      page: 1,
      pageSize: 100,
      status: "all",
    });
    cycles.value = data.items.filter((cycle) =>
      ["ACTIVE", "HARVESTING"].includes(cycle.status),
    );
    if (
      !selectedCycleId.value ||
      !cycles.value.some((cycle) => cycle.id === selectedCycleId.value)
    )
      selectedCycleId.value = cycles.value[0]?.id ?? null;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

async function loadOperations() {
  const farmId = farmStore.currentFarmId;
  if (!farmId || !selectedCycleId.value) {
    operations.value = [];
    suggestions.value = [];
    costSummary.value = null;
    pagination.total = 0;
    return;
  }
  loading.value = true;
  try {
    const [data, summary, suggestionData] = await Promise.all([
      getFieldOperations({
        farmId,
        cropCycleId: selectedCycleId.value,
        page: pagination.page,
        pageSize: pagination.pageSize,
      }),
      getCropCycleCostSummary(selectedCycleId.value),
      getCropOperationSuggestions(selectedCycleId.value),
    ]);
    operations.value = data.items;
    pagination.total = data.pagination.total;
    costSummary.value = summary;
    suggestions.value = suggestionData.items;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function loadReferences() {
  try {
    await loadCycles();
    await loadOperations();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

function openCreate(suggestion?: CropOperationSuggestion) {
  Object.assign(form, {
    operationType: suggestion?.operationType ?? "LAND_PREPARATION",
    operationDate: suggestion?.suggestedDate ?? new Date().toISOString().slice(0, 10),
    areaMu: selectedCycle.value
      ? Number(selectedCycle.value.areaMu)
      : undefined,
    laborHours: 0,
    machineHours: 0,
    laborCost: 0,
    serviceCost: 0,
    notes: suggestion?.defaultNotes ?? "",
  });
  dialogVisible.value = true;
}
async function save() {
  const farmId = farmStore.currentFarmId;
  if (
    !farmId ||
    !selectedCycleId.value ||
    !form.areaMu ||
    !form.operationDate
  ) {
    ElMessage.error("请选择周期并完整填写操作信息");
    return;
  }
  saving.value = true;
  try {
    await createFieldOperation({
      farmId,
      cropCycleId: selectedCycleId.value,
      operationType: form.operationType,
      operationDate: form.operationDate,
      areaMu: form.areaMu,
      laborHours: form.laborHours,
      machineHours: form.machineHours,
      laborCost: form.laborCost,
      serviceCost: form.serviceCost,
      notes: form.notes.trim() || null,
    });
    ElMessage.success("农事操作已登记");
    dialogVisible.value = false;
    await loadOperations();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    saving.value = false;
  }
}
async function loadOperationInputs() {
  const farmId = farmStore.currentFarmId;
  if (!farmId || !inputOperation.value) return;
  inputLoading.value = true;
  try {
    const [bound, available] = await Promise.all([
      getFieldOperationInputs({
        farmId,
        fieldOperationId: inputOperation.value.id,
      }),
      getAvailableFieldOperationInputs({
        farmId,
        fieldOperationId: inputOperation.value.id,
      }),
    ]);
    operationInputs.value = bound.items;
    availableInputs.value = available.items;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    inputLoading.value = false;
  }
}
async function openInputs(operation: FieldOperation) {
  inputOperation.value = operation;
  operationInputs.value = [];
  availableInputs.value = [];
  inputDialogVisible.value = true;
  await loadOperationInputs();
}
async function bindInput(stockDocumentId: number) {
  const farmId = farmStore.currentFarmId;
  if (!farmId || !inputOperation.value) return;
  bindingDocumentId.value = stockDocumentId;
  try {
    await createFieldOperationInput({
      farmId,
      fieldOperationId: inputOperation.value.id,
      stockDocumentId,
    });
    ElMessage.success("投入品已绑定");
    await Promise.all([loadOperationInputs(), loadOperations()]);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    bindingDocumentId.value = null;
  }
}
function typeLabel(value: string) {
  return operationTypes.find((item) => item.value === value)?.label ?? value;
}
watch(
  () => farmStore.currentFarmId,
  () => {
    pagination.page = 1;
    void loadReferences();
  },
  { immediate: true },
);
watch(selectedCycleId, () => {
  pagination.page = 1;
  void loadOperations();
});
</script>

<template>
  <section class="farm-page resource-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">FIELD OPERATIONS</p>
        <h1>农事操作</h1>
        <p>
          {{ farmStore.currentFarm?.name ?? "尚未选择农场" }} ·
          记录整地、播种、灌溉等作业
        </p>
      </div>
      <el-button
        v-if="writable && selectedCycle"
        type="primary"
        :icon="Plus"
        @click="openCreate()"
        >登记操作</el-button
      >
    </header>
    <el-empty v-if="!farmStore.currentFarm" description="暂无可用农场" />
    <template v-else>
      <div class="farm-toolbar" role="search" aria-label="筛选农事操作">
        <el-select
          v-model="selectedCycleId"
          class="cycle-select"
          aria-label="选择种植周期"
          placeholder="选择活动周期"
          ><el-option
            v-for="cycle in cycles"
            :key="cycle.id"
            :label="`${cycle.cycleCode} · ${cycle.plotName}`"
            :value="cycle.id" /></el-select
        ><el-button type="primary" :icon="Search" @click="loadOperations"
          >查询</el-button
        ><el-button :icon="Refresh" @click="loadReferences">刷新</el-button>
      </div>
      <el-alert
        v-if="!selectedCycle"
        title="暂无可登记农事操作的活动周期"
        type="info"
        :closable="false"
      />
      <el-descriptions
        v-if="selectedCycle && costSummary"
        :column="4"
        border
        direction="vertical"
        aria-label="种植周期成本汇总"
      >
        <el-descriptions-item label="周期总成本"
          >¥ {{ costSummary.totalCost }}</el-descriptions-item
        >
        <el-descriptions-item label="亩均成本"
          >¥ {{ costSummary.costPerMu }}</el-descriptions-item
        >
        <el-descriptions-item label="材料成本"
          >¥ {{ costSummary.materialCost }}</el-descriptions-item
        >
        <el-descriptions-item label="人工 / 服务"
          >¥ {{ costSummary.laborCost }} / ¥
          {{ costSummary.serviceCost }}</el-descriptions-item
        >
        <el-descriptions-item label="烘烤能源"
          >¥ {{ costSummary.curingCost }}</el-descriptions-item
        >
      </el-descriptions>
      <div v-if="selectedCycle" class="farm-table-shell suggestion-table">
        <div class="section-heading">
          <h2>周期作业建议</h2>
          <span>以实际开始日期优先计算</span>
        </div>
        <el-table :data="suggestions" row-key="templateId" empty-text="该作物暂无作业模板">
          <el-table-column label="作业" min-width="130">
            <template #default="scope">{{ typeLabel(scope.row.operationType) }}</template>
          </el-table-column>
          <el-table-column prop="suggestedDate" label="建议日期" min-width="130" />
          <el-table-column label="要求" width="90">
            <template #default="scope">
              <el-tag :type="scope.row.required ? 'danger' : 'info'" effect="plain">
                {{ scope.row.required ? "必做" : "建议" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.recorded ? 'success' : scope.row.overdue ? 'danger' : 'warning'">
                {{ scope.row.recorded ? "已记录" : scope.row.overdue ? "逾期" : "待处理" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="defaultNotes" label="建议内容" min-width="220" />
          <el-table-column v-if="writable" label="操作" width="90" fixed="right">
            <template #default="scope">
              <el-button link type="primary" :disabled="scope.row.recorded" @click="openCreate(scope.row)">
                登记
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div v-if="selectedCycle" class="farm-table-shell">
        <el-table
          v-loading="loading"
          :data="operations"
          row-key="id"
          empty-text="当前周期暂无农事操作"
          ><el-table-column label="日期 / 类型" min-width="180"
            ><template #default="scope"
              ><strong>{{ scope.row.operationDate }}</strong
              ><br /><span class="table-secondary">{{
                typeLabel(String(scope.row.operationType))
              }}</span></template
            ></el-table-column
          ><el-table-column label="作业面积" width="120" align="right"
            ><template #default="scope"
              >{{ scope.row.areaMu }} 亩</template
            ></el-table-column
          ><el-table-column label="工时" min-width="150"
            ><template #default="scope"
              >人工 {{ scope.row.laborHours }} h<br /><span
                class="table-secondary"
                >机械 {{ scope.row.machineHours }} h</span
              ></template
            ></el-table-column
          ><el-table-column label="费用" min-width="150" align="right"
            ><template #default="scope"
              >¥ {{ scope.row.laborCost }}<br /><span class="table-secondary"
                >服务 ¥ {{ scope.row.serviceCost }}</span
              ></template
            ></el-table-column
          ><el-table-column
            prop="notes"
            label="备注"
            min-width="150"
          /><el-table-column label="投入品" width="110" fixed="right"
            ><template #default="scope"
              ><el-button
                link
                type="primary"
                :icon="Link"
                @click="openInputs(scope.row)"
                >查看</el-button
              ></template
            ></el-table-column
          ></el-table
        >
        <footer class="admin-pagination">
          <span>共 {{ pagination.total }} 条记录</span
          ><el-pagination
            v-model:current-page="pagination.page"
            :page-size="pagination.pageSize"
            layout="prev, pager, next"
            :total="pagination.total"
            @current-change="loadOperations"
          />
        </footer>
      </div>
    </template>
    <el-dialog
      v-model="inputDialogVisible"
      :title="
        inputOperation
          ? `投入品 · ${inputOperation.operationDate} ${typeLabel(inputOperation.operationType)}`
          : '农事投入品'
      "
      width="min(94vw, 760px)"
      destroy-on-close
    >
      <el-tabs>
        <el-tab-pane :label="`已绑定 (${operationInputs.length})`">
          <el-table
            v-loading="inputLoading"
            :data="operationInputs"
            row-key="id"
            empty-text="该农事操作尚未绑定投入品"
          >
            <el-table-column label="领料单 / 日期" min-width="170"
              ><template #default="scope"
                ><strong>{{ scope.row.documentNo }}</strong
                ><br /><span class="table-secondary">{{
                  scope.row.operationDate
                }}</span></template
              ></el-table-column
            >
            <el-table-column label="物料" min-width="170"
              ><template #default="scope"
                >{{ scope.row.itemName }}<br /><span class="table-secondary">{{
                  scope.row.itemCode
                }}</span></template
              ></el-table-column
            >
            <el-table-column label="数量" width="120" align="right"
              ><template #default="scope"
                >{{ scope.row.quantity }} {{ scope.row.unitName }}</template
              ></el-table-column
            >
            <el-table-column label="成本" width="120" align="right"
              ><template #default="scope"
                >¥ {{ scope.row.amount }}</template
              ></el-table-column
            >
          </el-table>
          <div class="dialog-footer">
            <strong>投入品成本合计：¥ {{ totalInputCost }}</strong>
          </div>
        </el-tab-pane>
        <el-tab-pane
          v-if="writable"
          :label="`可绑定 (${availableInputs.length})`"
        >
          <el-table
            v-loading="inputLoading"
            :data="availableInputs"
            row-key="stockDocumentId"
            empty-text="暂无符合当前周期和日期的未绑定领料单"
          >
            <el-table-column label="领料单 / 日期" min-width="170"
              ><template #default="scope"
                ><strong>{{ scope.row.documentNo }}</strong
                ><br /><span class="table-secondary">{{
                  scope.row.operationDate
                }}</span></template
              ></el-table-column
            >
            <el-table-column label="物料" min-width="170"
              ><template #default="scope"
                >{{ scope.row.itemName }}<br /><span class="table-secondary">{{
                  scope.row.itemCode
                }}</span></template
              ></el-table-column
            >
            <el-table-column label="数量 / 成本" width="150" align="right"
              ><template #default="scope"
                >{{ scope.row.quantity }} {{ scope.row.unitName }}<br /><span
                  class="table-secondary"
                  >¥ {{ scope.row.amount }}</span
                ></template
              ></el-table-column
            >
            <el-table-column label="操作" width="90" align="right"
              ><template #default="scope"
                ><el-button
                  link
                  type="primary"
                  :loading="bindingDocumentId === scope.row.stockDocumentId"
                  @click="bindInput(scope.row.stockDocumentId)"
                  >绑定</el-button
                ></template
              ></el-table-column
            >
          </el-table>
        </el-tab-pane>
      </el-tabs>
      <template #footer
        ><el-button @click="inputDialogVisible = false"
          >关闭</el-button
        ></template
      >
    </el-dialog>
    <el-dialog
      v-model="dialogVisible"
      title="登记农事操作"
      width="min(92vw, 620px)"
      ><el-form label-position="top" @submit.prevent="save"
        ><div class="farm-form-grid">
          <el-form-item label="操作类型" required
            ><el-select v-model="form.operationType" class="full-width-control"
              ><el-option
                v-for="item in operationTypes"
                :key="item.value"
                :label="item.label"
                :value="item.value" /></el-select></el-form-item
          ><el-form-item label="操作日期" required
            ><el-date-picker
              v-model="form.operationDate"
              type="date"
              value-format="YYYY-MM-DD"
              class="full-width-control" /></el-form-item
          ><el-form-item label="作业面积（亩）" required
            ><el-input-number
              v-model="form.areaMu"
              :min="0.001"
              :precision="3"
              controls-position="right"
              class="full-width-control" /></el-form-item
          ><el-form-item label="人工工时（小时）"
            ><el-input-number
              v-model="form.laborHours"
              :min="0"
              :precision="2"
              controls-position="right"
              class="full-width-control" /></el-form-item
          ><el-form-item label="机械工时（小时）"
            ><el-input-number
              v-model="form.machineHours"
              :min="0"
              :precision="2"
              controls-position="right"
              class="full-width-control" /></el-form-item
          ><el-form-item label="人工费用（元）"
            ><el-input-number
              v-model="form.laborCost"
              :min="0"
              :precision="2"
              controls-position="right"
              class="full-width-control" /></el-form-item
          ><el-form-item label="服务费用（元）"
            ><el-input-number
              v-model="form.serviceCost"
              :min="0"
              :precision="2"
              controls-position="right"
              class="full-width-control"
          /></el-form-item>
        </div>
        <el-form-item label="备注"
          ><el-input v-model="form.notes" type="textarea" maxlength="500"
        /></el-form-item>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button
          ><el-button type="primary" :loading="saving" @click="save"
            >登记操作</el-button
          >
        </div></el-form
      ></el-dialog
    >
  </section>
</template>

<style scoped>
.suggestion-table { margin-top: 20px; }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; padding: 18px 20px 0; }
.section-heading h2 { margin: 0 0 12px; font-size: 16px; }
.section-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
</style>
