<script setup lang="ts">
import { EditPen, Plus } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import { createCropVariety, getCatalogs, updateCropVariety } from "@/api/catalogs";
import { errorMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import type { CatalogData, CropVariety } from "@/types/catalog";


const auth = useAuthStore();
const loading = ref(false);
const catalog = ref<CatalogData>({ units: [], livestockSpecies: [], cropTypes: [] });
const varietyDialogVisible = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);
const varietyForm = reactive<{
  cropTypeId: number | undefined;
  code: string;
  name: string;
  isActive: boolean;
}>({ cropTypeId: undefined, code: "", name: "", isActive: true });

const varieties = computed(() => catalog.value.cropTypes.flatMap((cropType) =>
  cropType.varieties.map((variety) => ({ ...variety, cropTypeName: cropType.name })),
));
const dimensions: Record<string, string> = {
  WEIGHT: "重量",
  VOLUME: "体积",
  LIVESTOCK: "数量",
  AREA: "面积",
  PACKAGE: "包装",
};

async function loadCatalogs() {
  loading.value = true;
  try {
    catalog.value = await getCatalogs();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

function openCreateVariety() {
  editingId.value = null;
  varietyForm.cropTypeId = catalog.value.cropTypes.find((item) => item.isActive)?.id;
  varietyForm.code = "";
  varietyForm.name = "";
  varietyForm.isActive = true;
  varietyDialogVisible.value = true;
}

function openEditVariety(variety: CropVariety) {
  editingId.value = variety.id;
  varietyForm.cropTypeId = variety.cropTypeId;
  varietyForm.code = variety.code;
  varietyForm.name = variety.name;
  varietyForm.isActive = variety.isActive;
  varietyDialogVisible.value = true;
}

async function saveVariety() {
  const code = varietyForm.code.trim();
  const name = varietyForm.name.trim();
  if (!varietyForm.cropTypeId) return ElMessage.error("请选择作物类型");
  if (!/^[A-Za-z0-9_-]{2,20}$/.test(code)) return ElMessage.error("品种编号须为 2-20 位字母、数字、下划线或短横线");
  if (!name || name.length > 80) return ElMessage.error("品种名称须为 1-80 个字符");

  saving.value = true;
  try {
    const input = { cropTypeId: varietyForm.cropTypeId, code, name };
    if (editingId.value) {
      await updateCropVariety(editingId.value, { ...input, isActive: varietyForm.isActive });
    } else {
      await createCropVariety(input);
    }
    ElMessage.success(`作物品种已${editingId.value ? "更新" : "创建"}`);
    varietyDialogVisible.value = false;
    await loadCatalogs();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    saving.value = false;
  }
}

onMounted(() => void loadCatalogs());
</script>

<template>
  <section class="farm-page catalog-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">BUSINESS CATALOG</p>
        <h1>业务字典</h1>
        <p>{{ catalog.units.length }} 个计量单位 · {{ catalog.livestockSpecies.length }} 个养殖品类 · {{ catalog.cropTypes.length }} 个作物类型</p>
      </div>
    </header>

    <el-tabs class="base-tabs">
      <el-tab-pane label="计量单位">
        <div class="farm-table-shell">
          <el-table v-loading="loading" :data="catalog.units" row-key="id" empty-text="暂无计量单位">
            <el-table-column label="单位名称" min-width="150">
              <template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.name }}</strong><span>{{ scope.row.code }}</span></div></template>
            </el-table-column>
            <el-table-column label="量纲" min-width="110"><template #default="scope">{{ dimensions[scope.row.dimension] || scope.row.dimension }}</template></el-table-column>
            <el-table-column prop="baseFactor" label="基础换算系数" min-width="130" align="right" />
            <el-table-column prop="scale" label="小数位" width="90" align="right" />
            <el-table-column label="状态" width="82"><template #default="scope"><el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">{{ scope.row.isActive ? "正常" : "停用" }}</el-tag></template></el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="养殖品类">
        <div class="farm-table-shell">
          <el-table v-loading="loading" :data="catalog.livestockSpecies" row-key="id" empty-text="暂无养殖品类">
            <el-table-column label="品类名称" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.name }}</strong><span>{{ scope.row.code }}</span></div></template></el-table-column>
            <el-table-column label="管理方式" min-width="120"><template #default>按批次管理</template></el-table-column>
            <el-table-column label="状态" width="82"><template #default="scope"><el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">{{ scope.row.isActive ? "正常" : "停用" }}</el-tag></template></el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="作物与品种">
        <div class="catalog-section">
          <div class="catalog-section-header"><h2>作物类型</h2></div>
          <div class="farm-table-shell">
            <el-table v-loading="loading" :data="catalog.cropTypes" row-key="id" empty-text="暂无作物类型">
              <el-table-column label="作物名称" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.name }}</strong><span>{{ scope.row.code }}</span></div></template></el-table-column>
              <el-table-column label="品种数量" min-width="110" align="right"><template #default="scope">{{ scope.row.varieties.length }} 个</template></el-table-column>
              <el-table-column label="状态" width="82"><template #default="scope"><el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">{{ scope.row.isActive ? "正常" : "停用" }}</el-tag></template></el-table-column>
            </el-table>
          </div>
        </div>

        <div class="catalog-section">
          <div class="catalog-section-header"><h2>作物品种</h2><el-button v-if="auth.isAdmin" type="primary" :icon="Plus" @click="openCreateVariety">新建品种</el-button></div>
          <div class="farm-table-shell">
            <el-table v-loading="loading" :data="varieties" row-key="id" empty-text="暂无作物品种">
              <el-table-column label="品种名称" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.name }}</strong><span>{{ scope.row.code }}</span></div></template></el-table-column>
              <el-table-column prop="cropTypeName" label="所属作物" min-width="120" />
              <el-table-column label="状态" width="82"><template #default="scope"><el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">{{ scope.row.isActive ? "正常" : "停用" }}</el-tag></template></el-table-column>
              <el-table-column v-if="auth.isAdmin" label="操作" width="90" fixed="right"><template #default="scope"><el-button link type="primary" :icon="EditPen" @click="openEditVariety(scope.row)">编辑</el-button></template></el-table-column>
            </el-table>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="varietyDialogVisible" :title="`${editingId ? '编辑' : '新建'}作物品种`" width="min(92vw, 560px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveVariety">
        <div class="farm-form-grid">
          <el-form-item label="作物类型" required>
            <el-select v-model="varietyForm.cropTypeId" class="full-width-control" aria-label="作物类型">
              <el-option v-for="item in catalog.cropTypes.filter((crop) => crop.isActive)" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="品种编号" required><el-input v-model="varietyForm.code" maxlength="20" aria-label="品种编号" /></el-form-item>
          <el-form-item label="品种名称" required><el-input v-model="varietyForm.name" maxlength="80" aria-label="品种名称" /></el-form-item>
          <el-form-item v-if="editingId" label="使用状态"><el-switch v-model="varietyForm.isActive" active-text="正常" inactive-text="停用" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="varietyDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveVariety">保存</el-button></template>
    </el-dialog>
  </section>
</template>
