<script setup lang="ts">
import { CircleCheck, Delete, EditPen, Plus, Refresh, RefreshLeft, Search, View } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { errorMessage } from "@/api/client";
import { getItems, getWarehouses } from "@/api/inventory";
import {
  cancelPurchase,
  createPurchase,
  createPurchaseReturn,
  createSupplier,
  getPurchase,
  getPurchases,
  getSuppliers,
  postPurchase,
  updatePurchase,
  updateSupplier,
} from "@/api/purchases";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { Item, Warehouse } from "@/types/inventory";
import type { PurchaseOrder, PurchaseStatus, Supplier } from "@/types/purchase";
import { localDateInputValue } from "@/utils/date";


interface PurchaseLineDraft {
  key: number;
  itemId: number | undefined;
  quantity: number | undefined;
  unitPrice: number | undefined;
  lotNo: string;
  expiresOn: string;
  returnedQuantity: string;
  returnableQuantity: string;
}

const router = useRouter();
const auth = useAuthStore();
const farmContext = useFarmStore();
const activeTab = ref("purchases");
const loading = ref(false);
const referencesLoading = ref(false);
const purchases = ref<PurchaseOrder[]>([]);
const suppliers = ref<Supplier[]>([]);
const supplierOptions = ref<Supplier[]>([]);
const warehouses = ref<Warehouse[]>([]);
const items = ref<Item[]>([]);
const filters = reactive<{
  keyword: string;
  status: "all" | PurchaseStatus;
  dateRange: [string, string] | [];
}>({ keyword: "", status: "all", dateRange: [] });
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });
const supplierFilters = reactive<{
  keyword: string;
  status: "all" | "active" | "disabled";
}>({ keyword: "", status: "all" });
const supplierPagination = reactive({ page: 1, pageSize: 10, total: 0 });

const purchaseDialogVisible = ref(false);
const purchaseSaving = ref(false);
const purchaseReadOnly = ref(false);
const editingPurchaseId = ref<number | null>(null);
const purchaseForm = reactive<{
  orderNo: string;
  supplierId: number | undefined;
  warehouseId: number | undefined;
  orderDate: string;
  notes: string;
  version: number;
  status: PurchaseStatus;
  lines: PurchaseLineDraft[];
}>({
  orderNo: "",
  supplierId: undefined,
  warehouseId: undefined,
  orderDate: "",
  notes: "",
  version: 1,
  status: "DRAFT",
  lines: [],
});
let lineKey = 0;

const purchaseReturnDialogVisible = ref(false);
const purchaseReturnSaving = ref(false);
const returnPurchase = ref<PurchaseOrder | null>(null);
const purchaseReturnForm = reactive({
  documentNo: "",
  returnDate: "",
  warehouseId: undefined as number | undefined,
  purchaseLineId: undefined as number | undefined,
  quantity: 1,
});

const supplierDialogVisible = ref(false);
const supplierSaving = ref(false);
const editingSupplierId = ref<number | null>(null);
const supplierForm = reactive({
  code: "",
  name: "",
  contact: "",
  phone: "",
  address: "",
  isActive: true,
});

const canOperatePurchases = computed(() => {
  const role = farmContext.currentFarm?.accessRole;
  return auth.isAdmin || role === "manager" || role === "operator";
});
const canManageSuppliers = computed(() => auth.isAdmin || farmContext.currentFarm?.accessRole === "manager");
const activeSuppliers = computed(() => supplierOptions.value.filter((item) => item.isActive));
const activeWarehouses = computed(() => warehouses.value.filter((item) => item.isActive));
const activeItems = computed(() => items.value.filter((item) => item.isActive));
const purchaseSupplierOptions = computed(() => purchaseReadOnly.value ? supplierOptions.value : activeSuppliers.value);
const purchaseWarehouseOptions = computed(() => purchaseReadOnly.value ? warehouses.value : activeWarehouses.value);
const purchaseItemOptions = computed(() => purchaseReadOnly.value ? items.value : activeItems.value);
const purchaseTotal = computed(() => purchaseForm.lines.reduce(
  (total, line) => total + Number(line.quantity || 0) * Number(line.unitPrice || 0),
  0,
));
const purchaseDialogTitle = computed(() => purchaseReadOnly.value
  ? "采购单详情"
  : `${editingPurchaseId.value ? "编辑" : "新建"}采购单`);
const returnablePurchaseLines = computed(() => (
  returnPurchase.value?.lines ?? []
).filter((line) => Number(line.returnableQuantity) > 0));
const selectedPurchaseReturnLine = computed(() => (
  returnPurchase.value?.lines ?? []
).find((line) => line.id === purchaseReturnForm.purchaseLineId));
const purchaseReturnRefund = computed(() => (
  Number(purchaseReturnForm.quantity || 0) * Number(selectedPurchaseReturnLine.value?.unitPrice ?? 0)
));

const statusNames: Record<PurchaseStatus, string> = {
  DRAFT: "草稿",
  POSTED: "已过账",
  CANCELLED: "已取消",
};

function statusTag(status: PurchaseStatus) {
  return status === "POSTED" ? "success" : status === "CANCELLED" ? "info" : "warning";
}

function suggestedOrderNo() {
  return `PO-${Date.now().toString(36).toUpperCase()}`;
}

function suggestedPurchaseReturnNo() {
  return `RT-${Date.now().toString(36).toUpperCase()}`;
}

function addLine(source?: Partial<PurchaseLineDraft>) {
  purchaseForm.lines.push({
    key: ++lineKey,
    itemId: source?.itemId ?? activeItems.value[0]?.id,
    quantity: source?.quantity,
    unitPrice: source?.unitPrice,
    lotNo: source?.lotNo ?? "",
    expiresOn: source?.expiresOn ?? "",
    returnedQuantity: source?.returnedQuantity ?? "0",
    returnableQuantity: source?.returnableQuantity ?? "0",
  });
}

function removeLine(key: number) {
  if (purchaseForm.lines.length === 1) return;
  purchaseForm.lines = purchaseForm.lines.filter((line) => line.key !== key);
}

function itemFor(line: PurchaseLineDraft) {
  return items.value.find((item) => item.id === line.itemId);
}

async function loadReferences() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    supplierOptions.value = [];
    warehouses.value = [];
    items.value = [];
    return;
  }
  referencesLoading.value = true;
  try {
    const [supplierData, warehouseData, itemData] = await Promise.all([
      getSuppliers({ farmId, page: 1, pageSize: 100, status: "all" }),
      getWarehouses({ farmId, page: 1, pageSize: 100, status: "all" }),
      getItems({ farmId, page: 1, pageSize: 100, status: "all" }),
    ]);
    supplierOptions.value = supplierData.items;
    warehouses.value = warehouseData.items;
    items.value = itemData.items;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    referencesLoading.value = false;
  }
}

async function loadPurchases() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    purchases.value = [];
    pagination.total = 0;
    return;
  }
  loading.value = true;
  try {
    const data = await getPurchases({
      farmId,
      page: pagination.page,
      pageSize: pagination.pageSize,
      keyword: filters.keyword || undefined,
      status: filters.status,
      dateFrom: filters.dateRange[0] || undefined,
      dateTo: filters.dateRange[1] || undefined,
    });
    purchases.value = data.items;
    pagination.total = data.pagination.total;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function loadSuppliers() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    suppliers.value = [];
    supplierPagination.total = 0;
    return;
  }
  loading.value = true;
  try {
    const data = await getSuppliers({
      farmId,
      page: supplierPagination.page,
      pageSize: supplierPagination.pageSize,
      keyword: supplierFilters.keyword || undefined,
      status: supplierFilters.status,
    });
    suppliers.value = data.items;
    supplierPagination.total = data.pagination.total;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

function searchPurchases() {
  pagination.page = 1;
  void loadPurchases();
}

function resetPurchaseFilters() {
  filters.keyword = "";
  filters.status = "all";
  filters.dateRange = [];
  searchPurchases();
}

function searchSuppliers() {
  supplierPagination.page = 1;
  void loadSuppliers();
}

function resetSupplierFilters() {
  supplierFilters.keyword = "";
  supplierFilters.status = "all";
  searchSuppliers();
}

function openCreatePurchase() {
  if (!activeSuppliers.value.length || !activeWarehouses.value.length || !activeItems.value.length) {
    ElMessage.warning("请先准备可用的供应商、仓库和物料");
    return;
  }
  editingPurchaseId.value = null;
  purchaseReadOnly.value = false;
  purchaseForm.orderNo = suggestedOrderNo();
  purchaseForm.supplierId = activeSuppliers.value[0]?.id;
  purchaseForm.warehouseId = activeWarehouses.value[0]?.id;
  purchaseForm.orderDate = localDateInputValue();
  purchaseForm.notes = "";
  purchaseForm.version = 1;
  purchaseForm.status = "DRAFT";
  purchaseForm.lines = [];
  addLine();
  purchaseDialogVisible.value = true;
}

async function openPurchase(order: PurchaseOrder, readOnly = order.status !== "DRAFT") {
  try {
    const detail = await getPurchase(order.id);
    editingPurchaseId.value = detail.id;
    purchaseReadOnly.value = readOnly;
    purchaseForm.orderNo = detail.orderNo;
    purchaseForm.supplierId = detail.supplierId;
    purchaseForm.warehouseId = detail.warehouseId;
    purchaseForm.orderDate = detail.orderDate;
    purchaseForm.notes = detail.notes ?? "";
    purchaseForm.version = detail.version;
    purchaseForm.status = detail.status;
    purchaseForm.lines = [];
    for (const line of detail.lines ?? []) {
      addLine({
        itemId: line.itemId,
        quantity: Number(line.quantity),
        unitPrice: Number(line.unitPrice),
        lotNo: line.lotNo ?? "",
        expiresOn: line.expiresOn ?? "",
        returnedQuantity: line.returnedQuantity,
        returnableQuantity: line.returnableQuantity,
      });
    }
    purchaseDialogVisible.value = true;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

async function savePurchase() {
  const farmId = farmContext.currentFarmId;
  const orderNo = purchaseForm.orderNo.trim();
  if (!farmId) return ElMessage.error("请先选择农场");
  if (!/^[A-Za-z0-9_-]{3,30}$/.test(orderNo)) return ElMessage.error("采购单号须为 3-30 位字母、数字、下划线或短横线");
  if (!purchaseForm.supplierId) return ElMessage.error("请选择供应商");
  if (!purchaseForm.warehouseId) return ElMessage.error("请选择入库仓库");
  if (!purchaseForm.orderDate) return ElMessage.error("请选择采购日期");
  if (!purchaseForm.lines.length) return ElMessage.error("采购单至少需要一条明细");
  const duplicateKeys = new Set<string>();
  for (const line of purchaseForm.lines) {
    const item = itemFor(line);
    if (!item) return ElMessage.error("请选择采购物料");
    if (!line.quantity || line.quantity <= 0) return ElMessage.error(`物料“${item.name}”的数量必须大于 0`);
    if (line.unitPrice === undefined || line.unitPrice < 0) return ElMessage.error(`物料“${item.name}”的单价不能小于 0`);
    if (item.lotTracking && !line.lotNo.trim()) return ElMessage.error(`物料“${item.name}”必须填写批号`);
    if (line.expiresOn && !line.lotNo.trim()) return ElMessage.error("填写有效期时必须同时填写批号");
    if (line.expiresOn && line.expiresOn < purchaseForm.orderDate) return ElMessage.error("有效期不能早于采购日期");
    const key = `${item.id}:${line.lotNo.trim()}`;
    if (duplicateKeys.has(key)) return ElMessage.error("同一物料和批号不能重复填写");
    duplicateKeys.add(key);
  }

  const input = {
    farmId,
    orderNo,
    supplierId: purchaseForm.supplierId,
    warehouseId: purchaseForm.warehouseId,
    orderDate: purchaseForm.orderDate,
    notes: purchaseForm.notes.trim() || null,
    lines: purchaseForm.lines.map((line) => ({
      itemId: Number(line.itemId),
      quantity: Number(line.quantity),
      unitPrice: Number(line.unitPrice),
      lotNo: line.lotNo.trim() || null,
      expiresOn: line.expiresOn || null,
    })),
  };
  purchaseSaving.value = true;
  try {
    if (editingPurchaseId.value) {
      await updatePurchase(editingPurchaseId.value, { ...input, version: purchaseForm.version });
    } else {
      await createPurchase(input);
    }
    ElMessage.success(`采购草稿已${editingPurchaseId.value ? "更新" : "创建"}`);
    purchaseDialogVisible.value = false;
    await loadPurchases();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    purchaseSaving.value = false;
  }
}

async function handlePost(order: PurchaseOrder) {
  try {
    await ElMessageBox.confirm(
      `确认将采购单 ${order.orderNo} 过账入库？`,
      "确认过账",
      { type: "warning", confirmButtonText: "确认过账", cancelButtonText: "取消" },
    );
    await postPurchase(order.id, order.version);
    ElMessage.success("采购单已过账，库存已更新");
    await loadPurchases();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error));
  }
}

function resetPurchaseReturnQuantity() {
  const available = Number(selectedPurchaseReturnLine.value?.returnableQuantity ?? 0);
  purchaseReturnForm.quantity = Math.min(1, available);
}

async function openPurchaseReturn(order: PurchaseOrder) {
  try {
    const detail = await getPurchase(order.id);
    const availableLines = (detail.lines ?? []).filter((line) => Number(line.returnableQuantity) > 0);
    if (!availableLines.length) return ElMessage.warning("该采购单已无可退物料");
    if (!activeWarehouses.value.length) return ElMessage.warning("请先启用退货仓库");
    returnPurchase.value = detail;
    purchaseReturnForm.documentNo = suggestedPurchaseReturnNo();
    purchaseReturnForm.returnDate = localDateInputValue();
    purchaseReturnForm.warehouseId = activeWarehouses.value.some((item) => item.id === detail.warehouseId)
      ? detail.warehouseId
      : activeWarehouses.value[0]?.id;
    purchaseReturnForm.purchaseLineId = availableLines[0]?.id;
    resetPurchaseReturnQuantity();
    purchaseReturnDialogVisible.value = true;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

async function savePurchaseReturn() {
  const farmId = farmContext.currentFarmId;
  const purchase = returnPurchase.value;
  const line = selectedPurchaseReturnLine.value;
  const documentNo = purchaseReturnForm.documentNo.trim();
  if (!farmId || !purchase) return ElMessage.error("请先选择采购单");
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(documentNo)) {
    return ElMessage.error("退货单号须为 3-40 位字母、数字、下划线或短横线");
  }
  if (!purchaseReturnForm.returnDate) return ElMessage.error("请选择退货日期");
  if (!purchaseReturnForm.warehouseId) return ElMessage.error("请选择退货仓库");
  if (!line) return ElMessage.error("请选择退货物料");
  if (!purchaseReturnForm.quantity || purchaseReturnForm.quantity <= 0) {
    return ElMessage.error("退货数量必须大于 0");
  }
  if (purchaseReturnForm.quantity > Number(line.returnableQuantity)) {
    return ElMessage.error(`退货数量不能超过可退数量 ${line.returnableQuantity} ${line.unitName}`);
  }
  try {
    await ElMessageBox.confirm(
      `确认退回 ${purchaseReturnForm.quantity} ${line.unitName} ${line.itemName}，预计退款 ¥ ${purchaseReturnRefund.value.toFixed(2)}？`,
      "确认采购退货",
      { type: "warning", confirmButtonText: "确认退货", cancelButtonText: "取消" },
    );
    purchaseReturnSaving.value = true;
    const purchaseReturn = await createPurchaseReturn({
      farmId,
      documentNo,
      purchaseId: purchase.id,
      purchaseLineId: line.id,
      returnDate: purchaseReturnForm.returnDate,
      warehouseId: purchaseReturnForm.warehouseId,
      quantity: purchaseReturnForm.quantity,
    });
    purchaseReturnDialogVisible.value = false;
    ElMessage.success(`采购退货已过账，退款金额 ¥ ${purchaseReturn.refundAmount}`);
    await loadPurchases();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error));
  } finally {
    purchaseReturnSaving.value = false;
  }
}

async function handleCancel(order: PurchaseOrder) {
  try {
    await ElMessageBox.confirm(
      `确认取消采购草稿 ${order.orderNo}？`,
      "取消采购单",
      { type: "warning", confirmButtonText: "确认取消", cancelButtonText: "返回" },
    );
    await cancelPurchase(order.id, order.version);
    ElMessage.success("采购单已取消");
    await loadPurchases();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error));
  }
}

function openCreateSupplier() {
  editingSupplierId.value = null;
  supplierForm.code = "";
  supplierForm.name = "";
  supplierForm.contact = "";
  supplierForm.phone = "";
  supplierForm.address = "";
  supplierForm.isActive = true;
  supplierDialogVisible.value = true;
}

function openEditSupplier(supplier: Supplier) {
  editingSupplierId.value = supplier.id;
  supplierForm.code = supplier.code;
  supplierForm.name = supplier.name;
  supplierForm.contact = supplier.contact ?? "";
  supplierForm.phone = supplier.phone ?? "";
  supplierForm.address = supplier.address ?? "";
  supplierForm.isActive = supplier.isActive;
  supplierDialogVisible.value = true;
}

async function saveSupplier() {
  const farmId = farmContext.currentFarmId;
  const code = supplierForm.code.trim();
  const name = supplierForm.name.trim();
  if (!farmId) return ElMessage.error("请先选择农场");
  if (!/^[A-Za-z0-9_-]{2,20}$/.test(code)) return ElMessage.error("供应商编号须为 2-20 位字母、数字、下划线或短横线");
  if (name.length < 2 || name.length > 100) return ElMessage.error("供应商名称须为 2-100 个字符");
  const input = {
    code,
    name,
    contact: supplierForm.contact.trim() || null,
    phone: supplierForm.phone.trim() || null,
    address: supplierForm.address.trim() || null,
  };
  supplierSaving.value = true;
  try {
    if (editingSupplierId.value) {
      await updateSupplier(editingSupplierId.value, { ...input, isActive: supplierForm.isActive });
    } else {
      await createSupplier({ farmId, ...input });
    }
    ElMessage.success(`供应商已${editingSupplierId.value ? "更新" : "创建"}`);
    supplierDialogVisible.value = false;
    await Promise.all([loadSuppliers(), loadReferences()]);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    supplierSaving.value = false;
  }
}

watch(
  () => farmContext.currentFarmId,
  async () => {
    pagination.page = 1;
    supplierPagination.page = 1;
    filters.keyword = "";
    filters.status = "all";
    filters.dateRange = [];
    supplierFilters.keyword = "";
    purchaseReturnDialogVisible.value = false;
    returnPurchase.value = null;
    await Promise.all([loadReferences(), loadPurchases(), loadSuppliers()]);
  },
  { immediate: true },
);
</script>

<template>
  <section class="farm-page purchase-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">PURCHASE RECEIPT</p>
        <h1>采购入库</h1>
        <p v-if="farmContext.currentFarm">{{ farmContext.currentFarm.name }} · {{ pagination.total }} 张采购单</p>
        <p v-else>尚未选择农场</p>
      </div>
    </header>

    <el-empty v-if="!farmContext.currentFarm" class="resource-empty" description="暂无可用农场">
      <el-button v-if="auth.isAdmin" type="primary" @click="router.push('/base/farms')">前往农场档案</el-button>
    </el-empty>

    <el-tabs v-else v-model="activeTab" class="base-tabs">
      <el-tab-pane label="采购单" name="purchases">
        <div class="tab-command-bar">
          <div class="farm-toolbar purchase-toolbar" role="search" aria-label="筛选采购单">
            <el-input v-model="filters.keyword" clearable :prefix-icon="Search" placeholder="搜索单号或供应商" aria-label="搜索采购单" @clear="searchPurchases" @keyup.enter="searchPurchases" />
            <el-select v-model="filters.status" aria-label="筛选采购单状态">
              <el-option label="全部状态" value="all" /><el-option label="草稿" value="DRAFT" /><el-option label="已过账" value="POSTED" /><el-option label="已取消" value="CANCELLED" />
            </el-select>
            <el-date-picker v-model="filters.dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" aria-label="采购日期范围" />
            <el-button type="primary" :icon="Search" @click="searchPurchases">查询</el-button>
            <el-button :icon="Refresh" @click="resetPurchaseFilters">重置</el-button>
          </div>
          <el-button
            v-if="canOperatePurchases"
            type="primary"
            :icon="Plus"
            :loading="referencesLoading"
            :disabled="referencesLoading"
            @click="openCreatePurchase"
          >
            新建采购单
          </el-button>
        </div>

        <div class="farm-table-shell">
          <el-table v-loading="loading" :data="purchases" row-key="id" empty-text="当前农场暂无采购单">
            <el-table-column label="采购单" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.orderNo }}</strong><span>{{ scope.row.orderDate }}</span></div></template></el-table-column>
            <el-table-column prop="supplierName" label="供应商" min-width="150" />
            <el-table-column prop="warehouseName" label="入库仓库" min-width="130" />
            <el-table-column label="金额" min-width="115" align="right"><template #default="scope">¥ {{ scope.row.totalAmount }}</template></el-table-column>
            <el-table-column label="状态" width="90"><template #default="scope"><el-tag :type="statusTag(scope.row.status)" effect="plain">{{ statusNames[scope.row.status as PurchaseStatus] }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="scope">
                <div class="purchase-actions">
                  <el-button v-if="scope.row.status === 'DRAFT' && canOperatePurchases" link type="primary" :icon="EditPen" @click="openPurchase(scope.row, false)">编辑</el-button>
                  <el-button v-else link type="primary" :icon="View" @click="openPurchase(scope.row, true)">查看</el-button>
                  <el-button v-if="scope.row.status === 'DRAFT' && canOperatePurchases" link type="success" :icon="CircleCheck" @click="handlePost(scope.row)">过账</el-button>
                  <el-button v-if="scope.row.status === 'POSTED' && canOperatePurchases" link type="warning" :icon="RefreshLeft" @click="openPurchaseReturn(scope.row)">退货</el-button>
                  <el-button v-if="scope.row.status === 'DRAFT' && canOperatePurchases" link type="danger" @click="handleCancel(scope.row)">取消</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <footer class="admin-pagination"><span>共 {{ pagination.total }} 张采购单</span><el-pagination :current-page="pagination.page" :page-size="pagination.pageSize" :page-sizes="[10, 20, 50]" :total="pagination.total" layout="sizes, prev, pager, next" @current-change="(page: number) => { pagination.page = page; loadPurchases(); }" @size-change="(size: number) => { pagination.page = 1; pagination.pageSize = size; loadPurchases(); }" /></footer>
        </div>
      </el-tab-pane>

      <el-tab-pane label="供应商" name="suppliers">
        <div class="tab-command-bar">
          <div class="farm-toolbar supplier-toolbar" role="search" aria-label="筛选供应商">
            <el-input v-model="supplierFilters.keyword" clearable :prefix-icon="Search" placeholder="搜索编号、名称或联系人" aria-label="搜索供应商" @clear="searchSuppliers" @keyup.enter="searchSuppliers" />
            <el-select v-model="supplierFilters.status" aria-label="筛选供应商状态"><el-option label="全部状态" value="all" /><el-option label="正常合作" value="active" /><el-option label="已停用" value="disabled" /></el-select>
            <el-button type="primary" :icon="Search" @click="searchSuppliers">查询</el-button><el-button :icon="Refresh" @click="resetSupplierFilters">重置</el-button>
          </div>
          <el-button v-if="canManageSuppliers" type="primary" :icon="Plus" @click="openCreateSupplier">新建供应商</el-button>
        </div>
        <div class="farm-table-shell">
          <el-table v-loading="loading" :data="suppliers" row-key="id" empty-text="当前农场暂无供应商">
            <el-table-column label="供应商" min-width="180"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.name }}</strong><span>{{ scope.row.code }}</span></div></template></el-table-column>
            <el-table-column prop="contact" label="联系人" min-width="110"><template #default="scope">{{ scope.row.contact || "-" }}</template></el-table-column>
            <el-table-column prop="phone" label="联系电话" min-width="140"><template #default="scope">{{ scope.row.phone || "-" }}</template></el-table-column>
            <el-table-column prop="address" label="地址" min-width="180"><template #default="scope">{{ scope.row.address || "-" }}</template></el-table-column>
            <el-table-column label="状态" width="90"><template #default="scope"><el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">{{ scope.row.isActive ? "正常" : "停用" }}</el-tag></template></el-table-column>
            <el-table-column v-if="canManageSuppliers" label="操作" width="90" fixed="right"><template #default="scope"><el-button link type="primary" :icon="EditPen" @click="openEditSupplier(scope.row)">编辑</el-button></template></el-table-column>
          </el-table>
          <footer class="admin-pagination"><span>共 {{ supplierPagination.total }} 个供应商</span><el-pagination :current-page="supplierPagination.page" :page-size="supplierPagination.pageSize" :page-sizes="[10, 20, 50]" :total="supplierPagination.total" layout="sizes, prev, pager, next" @current-change="(page: number) => { supplierPagination.page = page; loadSuppliers(); }" @size-change="(size: number) => { supplierPagination.page = 1; supplierPagination.pageSize = size; loadSuppliers(); }" /></footer>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="purchaseDialogVisible" :title="purchaseDialogTitle" width="min(96vw, 1060px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="savePurchase">
        <div class="purchase-header-form">
          <el-form-item label="采购单号" required><el-input v-model="purchaseForm.orderNo" :disabled="purchaseReadOnly" maxlength="30" aria-label="采购单号" /></el-form-item>
          <el-form-item label="采购日期" required><el-date-picker v-model="purchaseForm.orderDate" :disabled="purchaseReadOnly" class="full-width-control" type="date" value-format="YYYY-MM-DD" aria-label="采购日期" /></el-form-item>
          <el-form-item label="供应商" required><el-select v-model="purchaseForm.supplierId" :disabled="purchaseReadOnly" class="full-width-control" filterable aria-label="供应商"><el-option v-for="item in purchaseSupplierOptions" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="入库仓库" required><el-select v-model="purchaseForm.warehouseId" :disabled="purchaseReadOnly" class="full-width-control" filterable aria-label="入库仓库"><el-option v-for="item in purchaseWarehouseOptions" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="备注" class="purchase-notes"><el-input v-model="purchaseForm.notes" :disabled="purchaseReadOnly" maxlength="500" aria-label="采购备注" /></el-form-item>
        </div>
        <div class="purchase-lines-header"><h3>采购明细</h3><el-button v-if="!purchaseReadOnly" :icon="Plus" @click="addLine()">添加明细</el-button></div>
        <div class="purchase-lines">
          <div v-for="(line, index) in purchaseForm.lines" :key="line.key" class="purchase-line-row">
            <span class="purchase-line-index">{{ index + 1 }}</span>
            <el-form-item class="purchase-line-item" label="物料" required><el-select v-model="line.itemId" :disabled="purchaseReadOnly" filterable aria-label="采购物料"><el-option v-for="item in purchaseItemOptions" :key="item.id" :label="`${item.name} (${item.code})`" :value="item.id" /></el-select></el-form-item>
            <el-form-item class="purchase-line-quantity" :label="`数量${itemFor(line) ? `（${itemFor(line)?.unitName}）` : ''}`" required><el-input-number v-model="line.quantity" :disabled="purchaseReadOnly" :min="0.001" :precision="3" controls-position="right" aria-label="采购数量" /><span v-if="purchaseReadOnly && Number(line.returnedQuantity) > 0" class="form-note">已退 {{ line.returnedQuantity }}，可退 {{ line.returnableQuantity }}</span></el-form-item>
            <el-form-item class="purchase-line-price" label="含税单价" required><el-input-number v-model="line.unitPrice" :disabled="purchaseReadOnly" :min="0" :precision="4" controls-position="right" aria-label="采购单价" /></el-form-item>
            <el-form-item class="purchase-line-amount" label="金额"><strong class="line-amount">¥ {{ (Number(line.quantity || 0) * Number(line.unitPrice || 0)).toFixed(2) }}</strong></el-form-item>
            <el-form-item class="purchase-line-lot" :label="itemFor(line)?.lotTracking ? '批号（必填）' : '批号'"><el-input v-model="line.lotNo" :disabled="purchaseReadOnly" maxlength="64" aria-label="物料批号" /></el-form-item>
            <el-form-item class="purchase-line-expiry" label="有效期"><el-date-picker v-model="line.expiresOn" :disabled="purchaseReadOnly" type="date" value-format="YYYY-MM-DD" aria-label="物料有效期" /></el-form-item>
            <el-tooltip v-if="!purchaseReadOnly" content="删除明细"><el-button class="line-remove" circle :icon="Delete" :disabled="purchaseForm.lines.length === 1" aria-label="删除采购明细" @click="removeLine(line.key)" /></el-tooltip>
          </div>
        </div>
        <div class="purchase-total"><span>采购合计</span><strong>¥ {{ purchaseTotal.toFixed(2) }}</strong></div>
      </el-form>
      <template #footer><el-button @click="purchaseDialogVisible = false">{{ purchaseReadOnly ? "关闭" : "取消" }}</el-button><el-button v-if="!purchaseReadOnly" type="primary" :loading="purchaseSaving" @click="savePurchase">保存草稿</el-button></template>
    </el-dialog>

    <el-dialog v-model="purchaseReturnDialogVisible" title="采购退货" width="min(92vw, 720px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="savePurchaseReturn">
        <div class="farm-form-grid">
          <el-form-item label="原采购单"><el-input :model-value="returnPurchase?.orderNo ?? ''" disabled aria-label="原采购单" /></el-form-item>
          <el-form-item label="供应商"><el-input :model-value="returnPurchase?.supplierName ?? ''" disabled aria-label="退货供应商" /></el-form-item>
          <el-form-item label="退货单号" required><el-input v-model="purchaseReturnForm.documentNo" maxlength="40" aria-label="退货单号" /></el-form-item>
          <el-form-item label="退货日期" required><el-date-picker v-model="purchaseReturnForm.returnDate" class="full-width-control" type="date" value-format="YYYY-MM-DD" aria-label="退货日期" /></el-form-item>
          <el-form-item label="退货仓库" required><el-select v-model="purchaseReturnForm.warehouseId" class="full-width-control" filterable aria-label="退货仓库"><el-option v-for="warehouse in activeWarehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" /></el-select></el-form-item>
          <el-form-item label="退货物料" required><el-select v-model="purchaseReturnForm.purchaseLineId" class="full-width-control" filterable aria-label="退货物料" @change="resetPurchaseReturnQuantity"><el-option v-for="line in returnablePurchaseLines" :key="line.id" :label="`${line.itemName} · ${line.lotNo || '无批号'} · 可退 ${line.returnableQuantity} ${line.unitName}`" :value="line.id" /></el-select></el-form-item>
          <el-form-item :label="`退货数量${selectedPurchaseReturnLine ? `（${selectedPurchaseReturnLine.unitName}）` : ''}`" required><el-input-number v-model="purchaseReturnForm.quantity" class="full-width-control" :min="0.001" :max="Number(selectedPurchaseReturnLine?.returnableQuantity ?? 0)" :precision="3" controls-position="right" aria-label="退货数量" /></el-form-item>
          <el-form-item label="原采购单价"><el-input :model-value="selectedPurchaseReturnLine ? `¥ ${selectedPurchaseReturnLine.unitPrice}` : ''" disabled aria-label="原采购单价" /></el-form-item>
          <el-form-item class="farm-form-span" label="批号/有效期"><el-input :model-value="selectedPurchaseReturnLine ? `${selectedPurchaseReturnLine.lotNo || '无批号'} / ${selectedPurchaseReturnLine.expiresOn || '无有效期'}` : ''" disabled aria-label="退货批号和有效期" /></el-form-item>
        </div>
        <div class="purchase-total"><span>预计退款</span><strong>¥ {{ purchaseReturnRefund.toFixed(2) }}</strong></div>
      </el-form>
      <template #footer><el-button @click="purchaseReturnDialogVisible = false">取消</el-button><el-button type="primary" :loading="purchaseReturnSaving" @click="savePurchaseReturn">确认退货</el-button></template>
    </el-dialog>

    <el-dialog v-model="supplierDialogVisible" :title="`${editingSupplierId ? '编辑' : '新建'}供应商`" width="min(92vw, 650px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveSupplier"><div class="farm-form-grid">
        <el-form-item label="供应商编号" required><el-input v-model="supplierForm.code" maxlength="20" aria-label="供应商编号" /></el-form-item>
        <el-form-item label="供应商名称" required><el-input v-model="supplierForm.name" maxlength="100" aria-label="供应商名称" /></el-form-item>
        <el-form-item label="联系人"><el-input v-model="supplierForm.contact" maxlength="40" aria-label="供应商联系人" /></el-form-item>
        <el-form-item label="联系电话"><el-input v-model="supplierForm.phone" maxlength="30" aria-label="供应商联系电话" /></el-form-item>
        <el-form-item label="地址" class="farm-form-span"><el-input v-model="supplierForm.address" maxlength="255" aria-label="供应商地址" /></el-form-item>
        <el-form-item v-if="editingSupplierId" label="合作状态"><el-switch v-model="supplierForm.isActive" active-text="正常" inactive-text="停用" /></el-form-item>
      </div></el-form>
      <template #footer><el-button @click="supplierDialogVisible = false">取消</el-button><el-button type="primary" :loading="supplierSaving" @click="saveSupplier">保存</el-button></template>
    </el-dialog>
  </section>
</template>
