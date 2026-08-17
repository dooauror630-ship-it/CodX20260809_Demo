<script setup lang="ts">
import { EditPen, Plus, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { getCatalogs } from "@/api/catalogs";
import { errorMessage } from "@/api/client";
import {
  createItem,
  createItemCategory,
  getItemCategories,
  getItems,
  updateItem,
  updateItemCategory,
} from "@/api/inventory";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { Unit } from "@/types/catalog";
import type { Item, ItemCategory, ItemType } from "@/types/inventory";


const router = useRouter();
const auth = useAuthStore();
const farmContext = useFarmStore();
const activeTab = ref("items");
const loadingItems = ref(false);
const loadingCategories = ref(false);
const items = ref<Item[]>([]);
const categories = ref<ItemCategory[]>([]);
const units = ref<Unit[]>([]);
const itemFilters = reactive<{
  keyword: string;
  status: "all" | "active" | "disabled";
  categoryId: number | null;
}>({ keyword: "", status: "all", categoryId: null });
const categoryFilters = reactive<{
  keyword: string;
  status: "all" | "active" | "disabled";
}>({ keyword: "", status: "all" });
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });

const itemDialogVisible = ref(false);
const itemSaving = ref(false);
const editingItemId = ref<number | null>(null);
const itemForm = reactive<{
  code: string;
  name: string;
  categoryId: number | undefined;
  unitId: number | undefined;
  itemType: ItemType;
  safetyStock: number;
  lotTracking: boolean;
  isActive: boolean;
}>({
  code: "",
  name: "",
  categoryId: undefined,
  unitId: undefined,
  itemType: "feed",
  safetyStock: 0,
  lotTracking: false,
  isActive: true,
});

const categoryDialogVisible = ref(false);
const categorySaving = ref(false);
const editingCategoryId = ref<number | null>(null);
const categoryForm = reactive<{
  code: string;
  name: string;
  parentId: number | null;
  isActive: boolean;
}>({ code: "", name: "", parentId: null, isActive: true });

const itemTypes: Array<{ value: ItemType; label: string }> = [
  { value: "feed", label: "饲料" },
  { value: "veterinary_drug", label: "兽药" },
  { value: "seed", label: "种子/种苗" },
  { value: "fertilizer", label: "肥料" },
  { value: "pesticide", label: "农药" },
  { value: "product", label: "农牧产品" },
  { value: "supply", label: "生产物资" },
  { value: "other", label: "其他" },
];
const activeCategories = computed(() => categories.value.filter((item) => item.isActive));
const rootCategoryOptions = computed(() => categories.value.filter(
  (item) => item.parentId === null && item.isActive && item.id !== editingCategoryId.value,
));

function itemTypeName(value: ItemType) {
  return itemTypes.find((item) => item.value === value)?.label ?? value;
}

async function loadCatalogData() {
  try {
    units.value = (await getCatalogs()).units.filter((item) => item.isActive);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

async function loadCategories() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    categories.value = [];
    return;
  }
  loadingCategories.value = true;
  try {
    categories.value = await getItemCategories({
      farmId,
      keyword: categoryFilters.keyword || undefined,
      status: auth.isAdmin ? categoryFilters.status : "active",
    });
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loadingCategories.value = false;
  }
}

async function loadItems() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    items.value = [];
    pagination.total = 0;
    return;
  }
  loadingItems.value = true;
  try {
    const data = await getItems({
      farmId,
      page: pagination.page,
      pageSize: pagination.pageSize,
      keyword: itemFilters.keyword || undefined,
      status: auth.isAdmin ? itemFilters.status : "active",
      categoryId: itemFilters.categoryId || undefined,
    });
    items.value = data.items;
    pagination.total = data.pagination.total;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loadingItems.value = false;
  }
}

function searchItems() {
  pagination.page = 1;
  void loadItems();
}

function resetItemFilters() {
  itemFilters.keyword = "";
  itemFilters.status = "all";
  itemFilters.categoryId = null;
  searchItems();
}

function searchCategories() {
  void loadCategories();
}

function resetCategoryFilters() {
  categoryFilters.keyword = "";
  categoryFilters.status = "all";
  searchCategories();
}

function openCreateItem() {
  if (!activeCategories.value.length) {
    ElMessage.warning("请先创建可用的物料分类");
    activeTab.value = "categories";
    return;
  }
  editingItemId.value = null;
  itemForm.code = "";
  itemForm.name = "";
  itemForm.categoryId = activeCategories.value[0]?.id;
  itemForm.unitId = units.value[0]?.id;
  itemForm.itemType = "feed";
  itemForm.safetyStock = 0;
  itemForm.lotTracking = false;
  itemForm.isActive = true;
  itemDialogVisible.value = true;
}

function openEditItem(item: Item) {
  editingItemId.value = item.id;
  itemForm.code = item.code;
  itemForm.name = item.name;
  itemForm.categoryId = item.categoryId;
  itemForm.unitId = item.unitId;
  itemForm.itemType = item.itemType;
  itemForm.safetyStock = Number(item.safetyStock);
  itemForm.lotTracking = item.lotTracking;
  itemForm.isActive = item.isActive;
  itemDialogVisible.value = true;
}

async function saveItem() {
  const farmId = farmContext.currentFarmId;
  const code = itemForm.code.trim();
  const name = itemForm.name.trim();
  if (!farmId) return ElMessage.error("请先选择农场");
  if (!/^[A-Za-z0-9_-]{2,30}$/.test(code)) return ElMessage.error("物料编号须为 2-30 位字母、数字、下划线或短横线");
  if (!name || name.length > 100) return ElMessage.error("物料名称须为 1-100 个字符");
  if (!itemForm.categoryId) return ElMessage.error("请选择物料分类");
  if (!itemForm.unitId) return ElMessage.error("请选择计量单位");
  if (itemForm.safetyStock < 0) return ElMessage.error("安全库存不能小于 0");

  itemSaving.value = true;
  try {
    const input = {
      code,
      name,
      categoryId: itemForm.categoryId,
      unitId: itemForm.unitId,
      itemType: itemForm.itemType,
      safetyStock: Number(itemForm.safetyStock),
      lotTracking: itemForm.lotTracking,
    };
    if (editingItemId.value) {
      await updateItem(editingItemId.value, { ...input, isActive: itemForm.isActive });
    } else {
      await createItem({ farmId, ...input });
    }
    ElMessage.success(`物料已${editingItemId.value ? "更新" : "创建"}`);
    itemDialogVisible.value = false;
    await loadItems();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    itemSaving.value = false;
  }
}

function openCreateCategory() {
  editingCategoryId.value = null;
  categoryForm.code = "";
  categoryForm.name = "";
  categoryForm.parentId = null;
  categoryForm.isActive = true;
  categoryDialogVisible.value = true;
}

function openEditCategory(category: ItemCategory) {
  editingCategoryId.value = category.id;
  categoryForm.code = category.code;
  categoryForm.name = category.name;
  categoryForm.parentId = category.parentId;
  categoryForm.isActive = category.isActive;
  categoryDialogVisible.value = true;
}

async function saveCategory() {
  const farmId = farmContext.currentFarmId;
  const code = categoryForm.code.trim();
  const name = categoryForm.name.trim();
  if (!farmId) return ElMessage.error("请先选择农场");
  if (!/^[A-Za-z0-9_-]{2,20}$/.test(code)) return ElMessage.error("分类编号须为 2-20 位字母、数字、下划线或短横线");
  if (!name || name.length > 80) return ElMessage.error("分类名称须为 1-80 个字符");

  categorySaving.value = true;
  try {
    const input = { code, name, parentId: categoryForm.parentId };
    if (editingCategoryId.value) {
      await updateItemCategory(editingCategoryId.value, { ...input, isActive: categoryForm.isActive });
    } else {
      await createItemCategory({ farmId, ...input });
    }
    ElMessage.success(`物料分类已${editingCategoryId.value ? "更新" : "创建"}`);
    categoryDialogVisible.value = false;
    await loadCategories();
    await loadItems();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    categorySaving.value = false;
  }
}

watch(
  () => farmContext.currentFarmId,
  async () => {
    pagination.page = 1;
    itemFilters.keyword = "";
    itemFilters.categoryId = null;
    categoryFilters.keyword = "";
    await loadCatalogData();
    await loadCategories();
    await loadItems();
  },
  { immediate: true },
);
</script>

<template>
  <section class="farm-page item-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">ITEM PROFILE</p>
        <h1>物料管理</h1>
        <p v-if="farmContext.currentFarm">{{ farmContext.currentFarm.name }} · {{ pagination.total }} 个物料</p>
        <p v-else>尚未选择农场</p>
      </div>
    </header>

    <el-empty v-if="!farmContext.currentFarm" class="resource-empty" description="暂无可用农场">
      <el-button v-if="auth.isAdmin" type="primary" @click="router.push('/base/farms')">前往农场档案</el-button>
    </el-empty>

    <el-tabs v-else v-model="activeTab" class="base-tabs">
      <el-tab-pane label="物料档案" name="items">
        <div class="tab-command-bar">
          <div class="farm-toolbar item-toolbar" :class="{ 'is-user-view': !auth.isAdmin }" role="search" aria-label="筛选物料">
            <el-input
              v-model="itemFilters.keyword"
              clearable
              :prefix-icon="Search"
              placeholder="搜索物料编号或名称"
              aria-label="搜索物料编号或名称"
              @clear="searchItems"
              @keyup.enter="searchItems"
            />
            <el-select v-model="itemFilters.categoryId" clearable placeholder="全部分类" aria-label="筛选物料分类" @change="searchItems">
              <el-option v-for="item in categories" :key="item.id" :label="item.parentName ? `${item.parentName} / ${item.name}` : item.name" :value="item.id" />
            </el-select>
            <el-select v-if="auth.isAdmin" v-model="itemFilters.status" aria-label="筛选物料状态">
              <el-option label="全部状态" value="all" />
              <el-option label="正常使用" value="active" />
              <el-option label="已停用" value="disabled" />
            </el-select>
            <el-button type="primary" :icon="Search" @click="searchItems">查询</el-button>
            <el-button :icon="Refresh" @click="resetItemFilters">重置</el-button>
          </div>
          <el-button v-if="auth.isAdmin" type="primary" :icon="Plus" @click="openCreateItem">新建物料</el-button>
        </div>

        <div class="farm-table-shell">
          <el-table v-loading="loadingItems" :data="items" row-key="id" empty-text="当前农场暂无物料">
            <el-table-column label="物料名称" min-width="170">
              <template #default="scope">
                <div class="farm-name-cell"><strong>{{ scope.row.name }}</strong><span>{{ scope.row.code }}</span></div>
              </template>
            </el-table-column>
            <el-table-column prop="categoryName" label="分类" min-width="120" />
            <el-table-column label="用途" min-width="110">
              <template #default="scope">{{ itemTypeName(scope.row.itemType) }}</template>
            </el-table-column>
            <el-table-column label="安全库存" min-width="120" align="right">
              <template #default="scope">{{ scope.row.safetyStock }} {{ scope.row.unitName }}</template>
            </el-table-column>
            <el-table-column label="批号" width="82" align="center">
              <template #default="scope">{{ scope.row.lotTracking ? "跟踪" : "不跟踪" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="82">
              <template #default="scope">
                <el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">{{ scope.row.isActive ? "正常" : "停用" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="auth.isAdmin" label="操作" width="90" fixed="right">
              <template #default="scope">
                <el-button link type="primary" :icon="EditPen" @click="openEditItem(scope.row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <footer class="admin-pagination">
            <span>共 {{ pagination.total }} 个物料</span>
            <el-pagination
              :current-page="pagination.page"
              :page-size="pagination.pageSize"
              :page-sizes="[10, 20, 50]"
              :total="pagination.total"
              layout="sizes, prev, pager, next"
              @current-change="(page: number) => { pagination.page = page; loadItems(); }"
              @size-change="(size: number) => { pagination.page = 1; pagination.pageSize = size; loadItems(); }"
            />
          </footer>
        </div>
      </el-tab-pane>

      <el-tab-pane label="物料分类" name="categories">
        <div class="tab-command-bar">
          <div class="farm-toolbar category-toolbar" :class="{ 'is-user-view': !auth.isAdmin }" role="search" aria-label="筛选物料分类">
            <el-input
              v-model="categoryFilters.keyword"
              clearable
              :prefix-icon="Search"
              placeholder="搜索分类编号或名称"
              aria-label="搜索分类编号或名称"
              @clear="searchCategories"
              @keyup.enter="searchCategories"
            />
            <el-select v-if="auth.isAdmin" v-model="categoryFilters.status" aria-label="筛选分类状态">
              <el-option label="全部状态" value="all" />
              <el-option label="正常使用" value="active" />
              <el-option label="已停用" value="disabled" />
            </el-select>
            <el-button type="primary" :icon="Search" @click="searchCategories">查询</el-button>
            <el-button :icon="Refresh" @click="resetCategoryFilters">重置</el-button>
          </div>
          <el-button v-if="auth.isAdmin" type="primary" :icon="Plus" @click="openCreateCategory">新建分类</el-button>
        </div>

        <div class="farm-table-shell">
          <el-table v-loading="loadingCategories" :data="categories" row-key="id" empty-text="当前农场暂无物料分类">
            <el-table-column label="分类名称" min-width="170">
              <template #default="scope">
                <div class="farm-name-cell"><strong>{{ scope.row.name }}</strong><span>{{ scope.row.code }}</span></div>
              </template>
            </el-table-column>
            <el-table-column label="上级分类" min-width="140">
              <template #default="scope">{{ scope.row.parentName || "一级分类" }}</template>
            </el-table-column>
            <el-table-column label="层级" width="90">
              <template #default="scope">{{ scope.row.parentId ? "二级" : "一级" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="82">
              <template #default="scope">
                <el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">{{ scope.row.isActive ? "正常" : "停用" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="auth.isAdmin" label="操作" width="90" fixed="right">
              <template #default="scope">
                <el-button link type="primary" :icon="EditPen" @click="openEditCategory(scope.row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="itemDialogVisible" :title="`${editingItemId ? '编辑' : '新建'}物料`" width="min(92vw, 680px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveItem">
        <div class="farm-form-grid">
          <el-form-item label="物料编号" required><el-input v-model="itemForm.code" maxlength="30" aria-label="物料编号" /></el-form-item>
          <el-form-item label="物料名称" required><el-input v-model="itemForm.name" maxlength="100" aria-label="物料名称" /></el-form-item>
          <el-form-item label="物料分类" required>
            <el-select v-model="itemForm.categoryId" class="full-width-control" filterable aria-label="物料分类">
              <el-option v-for="item in activeCategories" :key="item.id" :label="item.parentName ? `${item.parentName} / ${item.name}` : item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="计量单位" required>
            <el-select v-model="itemForm.unitId" class="full-width-control" filterable aria-label="计量单位">
              <el-option v-for="item in units" :key="item.id" :label="`${item.name} (${item.code})`" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="物料用途" required>
            <el-select v-model="itemForm.itemType" class="full-width-control" aria-label="物料用途">
              <el-option v-for="item in itemTypes" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="安全库存">
            <el-input-number v-model="itemForm.safetyStock" class="full-width-control" :min="0" :precision="3" controls-position="right" aria-label="安全库存" />
          </el-form-item>
          <el-form-item label="批号管理"><el-switch v-model="itemForm.lotTracking" active-text="跟踪" inactive-text="不跟踪" /></el-form-item>
          <el-form-item v-if="editingItemId" label="使用状态"><el-switch v-model="itemForm.isActive" active-text="正常" inactive-text="停用" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="itemDialogVisible = false">取消</el-button><el-button type="primary" :loading="itemSaving" @click="saveItem">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="categoryDialogVisible" :title="`${editingCategoryId ? '编辑' : '新建'}物料分类`" width="min(92vw, 560px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveCategory">
        <div class="farm-form-grid">
          <el-form-item label="分类编号" required><el-input v-model="categoryForm.code" maxlength="20" aria-label="分类编号" /></el-form-item>
          <el-form-item label="分类名称" required><el-input v-model="categoryForm.name" maxlength="80" aria-label="分类名称" /></el-form-item>
          <el-form-item label="上级分类">
            <el-select v-model="categoryForm.parentId" class="full-width-control" clearable placeholder="一级分类" aria-label="上级分类">
              <el-option v-for="item in rootCategoryOptions" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="editingCategoryId" label="使用状态"><el-switch v-model="categoryForm.isActive" active-text="正常" inactive-text="停用" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="categoryDialogVisible = false">取消</el-button><el-button type="primary" :loading="categorySaving" @click="saveCategory">保存</el-button></template>
    </el-dialog>
  </section>
</template>
