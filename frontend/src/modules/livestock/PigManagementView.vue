<script setup lang="ts">
import { CircleClose, EditPen, Finished, Plus, Refresh, Search, Tickets, View } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { getCatalogs } from "@/api/catalogs";
import { errorMessage } from "@/api/client";
import { getBarns } from "@/api/farms";
import {
  createLivestockBatch,
  createLivestockMovement,
  getLivestockBatch,
  getLivestockBatches,
} from "@/api/livestock";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { LivestockSpecies } from "@/types/catalog";
import type { Barn } from "@/types/farm";
import type {
  LivestockBatch,
  LivestockBatchStatus,
  LivestockMovement,
  LivestockSummary,
  WritableLivestockMovementType,
} from "@/types/livestock";
import { localDateInputValue } from "@/utils/date";


const router = useRouter();
const auth = useAuthStore();
const farmContext = useFarmStore();
const loading = ref(false);
const compactTable = ref(false);
const referencesLoading = ref(false);
const batches = ref<LivestockBatch[]>([]);
const barns = ref<Barn[]>([]);
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
    const [catalogs, barnData] = await Promise.all([
      getCatalogs(),
      getBarns({ farmId, page: 1, pageSize: 100, status: "active" }),
    ]);
    pigSpecies.value = catalogs.livestockSpecies.find((item) => item.code === "PIG" && item.isActive) ?? null;
    barns.value = barnData.items;
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
    await loadBatches();
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
    await loadBatches();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    movementSaving.value = false;
  }
}

async function openDetail(batch: LivestockBatch) {
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

watch(
  () => farmContext.currentFarmId,
  async () => {
    pagination.page = 1;
    filters.keyword = "";
    filters.status = "all";
    entryDialogVisible.value = false;
    movementDialogVisible.value = false;
    detailDialogVisible.value = false;
    await Promise.all([loadReferences(), loadBatches()]);
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
          <div><p>累计死亡</p><strong>{{ summary.deathCount }}<small>头</small></strong></div>
        </article>
        <article class="summary-card">
          <span class="summary-icon tone-amber"><Finished /></span>
          <div><p>淘汰与出栏</p><strong>{{ summary.exitedCount }}<small>头</small></strong></div>
        </article>
      </div>

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
            <el-tag :type="detailBatch.status === 'ACTIVE' ? 'success' : 'info'" effect="plain">
              {{ batchStatusName(detailBatch.status) }}
            </el-tag>
          </div>
          <div class="livestock-detail-summary">
            <div><span>初始头数</span><strong>{{ detailBatch.initialCount }} 头</strong></div>
            <div><span>当前存栏</span><strong>{{ detailBatch.currentHeadCount }} 头</strong></div>
            <div><span>死亡 / 淘汰</span><strong>{{ detailBatch.deathCount }} / {{ detailBatch.cullCount }} 头</strong></div>
            <div><span>累计出栏</span><strong>{{ detailBatch.exitCount }} 头</strong></div>
          </div>
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
  </section>
</template>

<style scoped>
.livestock-toolbar {
  grid-template-columns: minmax(240px, 1fr) 150px auto auto;
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
}
</style>
