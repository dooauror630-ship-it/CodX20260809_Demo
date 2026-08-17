<script setup lang="ts">
import { EditPen, Plus, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { errorMessage } from "@/api/client";
import { createBarn, createPlot, getBarns, getPlots, updateBarn, updatePlot } from "@/api/farms";
import { createWarehouse, getWarehouses, updateWarehouse } from "@/api/inventory";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { Barn, BarnType, Plot } from "@/types/farm";
import type { Warehouse } from "@/types/inventory";


const props = defineProps<{ resourceKind: "barn" | "plot" | "warehouse" }>();
const router = useRouter();
const auth = useAuthStore();
const farmContext = useFarmStore();
const loading = ref(false);
const compactTable = ref(false);
const resources = ref<Array<Barn | Plot | Warehouse>>([]);
const filters = reactive<{
  keyword: string;
  status: "all" | "active" | "disabled";
}>({ keyword: "", status: "all" });
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });

const dialogVisible = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);
const resourceForm = reactive<{
  code: string;
  name: string;
  barnType: BarnType;
  capacity: number | undefined;
  areaMu: number | undefined;
  soilType: string;
  location: string;
  isActive: boolean;
}>({
  code: "",
  name: "",
  barnType: "pig",
  capacity: undefined,
  areaMu: undefined,
  soilType: "",
  location: "",
  isActive: true,
});

const barnTypes: Array<{ value: BarnType; label: string }> = [
  { value: "pig", label: "猪舍" },
  { value: "chicken", label: "鸡舍" },
  { value: "isolation", label: "隔离舍" },
  { value: "other", label: "其他" },
];

const pageConfig = computed(() => ({
  barn: {
    eyebrow: "BARN PROFILE",
    title: "圈舍管理",
    singular: "圈舍",
    empty: "当前农场暂无圈舍",
    search: "搜索圈舍编号或名称",
  },
  plot: {
    eyebrow: "PLOT PROFILE",
    title: "地块管理",
    singular: "地块",
    empty: "当前农场暂无地块",
    search: "搜索地块编号、名称或土壤",
  },
  warehouse: {
    eyebrow: "WAREHOUSE PROFILE",
    title: "仓库管理",
    singular: "仓库",
    empty: "当前农场暂无仓库",
    search: "搜索仓库编号、名称或位置",
  },
})[props.resourceKind]);
const dialogTitle = computed(() => `${editingId.value ? "编辑" : "新建"}${pageConfig.value.singular}`);

function barnTypeName(value: string) {
  return barnTypes.find((item) => item.value === value)?.label ?? value;
}

async function loadResources() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    resources.value = [];
    pagination.total = 0;
    return;
  }

  loading.value = true;
  try {
    const query = {
      farmId,
      page: pagination.page,
      pageSize: pagination.pageSize,
      keyword: filters.keyword || undefined,
      status: auth.isAdmin ? filters.status : "active" as const,
    };
    const data = props.resourceKind === "barn"
      ? await getBarns(query)
      : props.resourceKind === "plot"
        ? await getPlots(query)
        : await getWarehouses(query);
    resources.value = data.items;
    pagination.total = data.pagination.total;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

function searchResources() {
  pagination.page = 1;
  void loadResources();
}

function resetFilters() {
  filters.keyword = "";
  filters.status = "all";
  searchResources();
}

function changePage(page: number) {
  pagination.page = page;
  void loadResources();
}

function changePageSize(pageSize: number) {
  pagination.page = 1;
  pagination.pageSize = pageSize;
  void loadResources();
}

function resetForm() {
  editingId.value = null;
  resourceForm.code = "";
  resourceForm.name = "";
  resourceForm.barnType = "pig";
  resourceForm.capacity = undefined;
  resourceForm.areaMu = undefined;
  resourceForm.soilType = "";
  resourceForm.location = "";
  resourceForm.isActive = true;
}

function openCreate() {
  resetForm();
  dialogVisible.value = true;
}

function openEdit(resource: Barn | Plot | Warehouse) {
  editingId.value = resource.id;
  resourceForm.code = resource.code;
  resourceForm.name = resource.name;
  resourceForm.isActive = resource.isActive;
  if (props.resourceKind === "barn") {
    const barn = resource as Barn;
    resourceForm.barnType = barn.barnType;
    resourceForm.capacity = barn.capacity;
  } else if (props.resourceKind === "plot") {
    const plot = resource as Plot;
    resourceForm.areaMu = Number(plot.areaMu);
    resourceForm.soilType = plot.soilType ?? "";
  } else {
    resourceForm.location = (resource as Warehouse).location ?? "";
  }
  dialogVisible.value = true;
}

function validateResource() {
  const code = resourceForm.code.trim();
  const name = resourceForm.name.trim();
  if (!/^[A-Za-z0-9_-]{2,20}$/.test(code)) return `${pageConfig.value.singular}编号须为 2-20 位字母、数字、下划线或短横线`;
  if (name.length < 2 || name.length > 80) return `${pageConfig.value.singular}名称须为 2-80 个字符`;
  if (props.resourceKind === "barn") {
    if (!Number.isInteger(resourceForm.capacity) || Number(resourceForm.capacity) < 0) return "设计容量须为非负整数";
  } else if (props.resourceKind === "plot") {
    if (!resourceForm.areaMu || resourceForm.areaMu <= 0) return "地块面积必须大于 0 亩";
    if (resourceForm.soilType.trim().length > 40) return "土壤说明不能超过 40 个字符";
  } else if (resourceForm.location.trim().length > 255) {
    return "仓库位置不能超过 255 个字符";
  }
  return "";
}

async function saveResource() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    ElMessage.error("请先选择农场");
    return;
  }
  const validationError = validateResource();
  if (validationError) {
    ElMessage.error(validationError);
    return;
  }

  saving.value = true;
  try {
    if (props.resourceKind === "barn") {
      const input = {
        code: resourceForm.code.trim(),
        name: resourceForm.name.trim(),
        barnType: resourceForm.barnType,
        capacity: Number(resourceForm.capacity),
      };
      if (editingId.value) await updateBarn(editingId.value, { ...input, isActive: resourceForm.isActive });
      else await createBarn({ farmId, ...input });
    } else if (props.resourceKind === "plot") {
      const input = {
        code: resourceForm.code.trim(),
        name: resourceForm.name.trim(),
        areaMu: Number(resourceForm.areaMu),
        soilType: resourceForm.soilType.trim() || null,
      };
      if (editingId.value) await updatePlot(editingId.value, { ...input, isActive: resourceForm.isActive });
      else await createPlot({ farmId, ...input });
    } else {
      const input = {
        code: resourceForm.code.trim(),
        name: resourceForm.name.trim(),
        location: resourceForm.location.trim() || null,
      };
      if (editingId.value) await updateWarehouse(editingId.value, { ...input, isActive: resourceForm.isActive });
      else await createWarehouse({ farmId, ...input });
    }
    ElMessage.success(`${pageConfig.value.singular}已${editingId.value ? "更新" : "创建"}`);
    dialogVisible.value = false;
    await loadResources();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    saving.value = false;
  }
}

function updateTableLayout() {
  compactTable.value = window.innerWidth < 760;
}

watch(
  [() => props.resourceKind, () => farmContext.currentFarmId],
  () => {
    pagination.page = 1;
    filters.keyword = "";
    filters.status = "all";
    void loadResources();
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
  <section class="farm-page resource-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">{{ pageConfig.eyebrow }}</p>
        <h1>{{ pageConfig.title }}</h1>
        <p v-if="farmContext.currentFarm">{{ farmContext.currentFarm.name }} · 共 {{ pagination.total }} 个{{ pageConfig.singular }}</p>
        <p v-else>尚未选择农场</p>
      </div>
      <el-button v-if="auth.isAdmin && farmContext.currentFarm" type="primary" :icon="Plus" @click="openCreate">
        新建{{ pageConfig.singular }}
      </el-button>
    </header>

    <el-empty v-if="!farmContext.currentFarm" class="resource-empty" description="暂无可用农场">
      <el-button v-if="auth.isAdmin" type="primary" @click="router.push('/base/farms')">前往农场档案</el-button>
    </el-empty>

    <template v-else>
      <div class="farm-toolbar" :class="{ 'is-user-view': !auth.isAdmin }" role="search" :aria-label="`筛选${pageConfig.singular}`">
        <el-input
          v-model="filters.keyword"
          clearable
          :prefix-icon="Search"
          :placeholder="pageConfig.search"
          :aria-label="pageConfig.search"
          @clear="searchResources"
          @keyup.enter="searchResources"
        />
        <el-select v-if="auth.isAdmin" v-model="filters.status" :aria-label="`筛选${pageConfig.singular}状态`">
          <el-option label="全部状态" value="all" />
          <el-option label="正常使用" value="active" />
          <el-option label="已停用" value="disabled" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="searchResources">查询</el-button>
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>

      <div class="farm-table-shell">
        <el-table v-loading="loading" :data="resources" row-key="id" :empty-text="pageConfig.empty">
          <el-table-column :label="`${pageConfig.singular}名称`" min-width="165">
            <template #default="scope">
              <div class="farm-name-cell">
                <strong>{{ scope.row.name }}</strong>
                <span v-if="compactTable && resourceKind === 'barn'">{{ scope.row.code }} · {{ scope.row.capacity }} 头/只</span>
                <span v-else-if="compactTable && resourceKind === 'plot'">{{ scope.row.code }} · {{ scope.row.areaMu }} 亩</span>
                <span v-else-if="compactTable">{{ scope.row.code }} · {{ scope.row.location || "未填写位置" }}</span>
                <span v-else>{{ scope.row.code }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-if="resourceKind === 'barn' && !compactTable" label="圈舍类型" width="120">
            <template #default="scope">{{ barnTypeName(scope.row.barnType) }}</template>
          </el-table-column>
          <el-table-column v-if="resourceKind === 'barn' && !compactTable" prop="capacity" label="设计容量" width="110" align="right">
            <template #default="scope">{{ scope.row.capacity }} 头/只</template>
          </el-table-column>
          <el-table-column v-if="resourceKind === 'plot' && !compactTable" prop="areaMu" label="面积" width="110" align="right">
            <template #default="scope">{{ scope.row.areaMu }} 亩</template>
          </el-table-column>
          <el-table-column v-if="resourceKind === 'plot' && !compactTable" label="土壤" min-width="140">
            <template #default="scope">{{ scope.row.soilType || "-" }}</template>
          </el-table-column>
          <el-table-column v-if="resourceKind === 'warehouse' && !compactTable" label="仓库位置" min-width="220">
            <template #default="scope">{{ scope.row.location || "-" }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="scope">
              <el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">
                {{ scope.row.isActive ? "正常" : "停用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="auth.isAdmin" label="操作" :width="compactTable ? 72 : 100" fixed="right">
            <template #default="scope">
              <div class="farm-actions">
                <el-tooltip v-if="compactTable" :content="`编辑${pageConfig.singular}`">
                  <el-button circle :icon="EditPen" :aria-label="`编辑${pageConfig.singular}`" @click="openEdit(scope.row)" />
                </el-tooltip>
                <el-button v-else link type="primary" :icon="EditPen" @click="openEdit(scope.row)">编辑</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <footer class="admin-pagination">
          <span>共 {{ pagination.total }} 个{{ pageConfig.singular }}</span>
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

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="min(92vw, 560px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveResource">
        <div class="farm-form-grid">
          <el-form-item :label="`${pageConfig.singular}编号`" required>
            <el-input v-model="resourceForm.code" maxlength="20" placeholder="例如 001" :aria-label="`${pageConfig.singular}编号`" />
          </el-form-item>
          <el-form-item :label="`${pageConfig.singular}名称`" required>
            <el-input v-model="resourceForm.name" maxlength="80" :placeholder="`请输入${pageConfig.singular}名称`" :aria-label="`${pageConfig.singular}名称`" />
          </el-form-item>
          <template v-if="resourceKind === 'barn'">
            <el-form-item label="圈舍类型" required>
              <el-select v-model="resourceForm.barnType" class="full-width-control" aria-label="圈舍类型">
                <el-option v-for="item in barnTypes" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="设计容量（头/只）" required>
              <el-input-number
                v-model="resourceForm.capacity"
                class="full-width-control"
                :min="0"
                :max="2000000000"
                :precision="0"
                controls-position="right"
                aria-label="设计容量"
              />
            </el-form-item>
          </template>
          <template v-else-if="resourceKind === 'plot'">
            <el-form-item label="面积（亩）" required>
              <el-input-number
                v-model="resourceForm.areaMu"
                class="full-width-control"
                :min="0.001"
                :max="99999999999.999"
                :precision="3"
                controls-position="right"
                aria-label="地块面积"
              />
            </el-form-item>
            <el-form-item label="土壤说明">
              <el-input v-model="resourceForm.soilType" maxlength="40" placeholder="例如 红壤、黏壤土" aria-label="土壤说明" />
            </el-form-item>
          </template>
          <el-form-item v-else label="仓库位置" class="farm-form-span">
            <el-input
              v-model="resourceForm.location"
              maxlength="255"
              placeholder="例如 主院北侧一号库"
              aria-label="仓库位置"
            />
          </el-form-item>
          <el-form-item v-if="editingId" label="使用状态">
            <el-switch v-model="resourceForm.isActive" active-text="正常" inactive-text="停用" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveResource">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
