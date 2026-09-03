<script setup lang="ts">
import { Box, Coin, DocumentChecked, Goods, Refresh, Right, Search, Timer, Warning } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { errorMessage } from "@/api/client";
import { getBarns, getPlots } from "@/api/farms";
import { getItems, getWarehouses } from "@/api/inventory";
import { getCropCycles } from "@/api/crop";
import {
  cancelInventoryCount,
  createInventoryCount,
  createProductionStockOperation,
  createStockTransfer,
  getInventoryCount,
  getInventoryCounts,
  getInventoryAnalysis,
  getStockLedger,
  getStocks,
  postInventoryCount,
  updateInventoryCount,
} from "@/api/purchases";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { Barn, Plot } from "@/types/farm";
import type { Item, Warehouse } from "@/types/inventory";
import type { CropCycle } from "@/types/crop";
import type {
  InventoryAnalysis,
  InventoryCount,
  InventoryCountLine,
  InventoryCountStatus,
  InventoryExpiryLot,
  ProductionCostObjectType,
  ProductionStockOperationType,
  StockBalance,
  StockLedgerEntry,
  StockSummary,
} from "@/types/purchase";
import { localDateInputValue } from "@/utils/date";
import InventoryTrendChart from "./components/InventoryTrendChart.vue";


interface InventoryCountLineDraft extends Omit<InventoryCountLine, "actualQuantity" | "reason"> {
  actualQuantity: number;
  reason: string;
}

const router = useRouter();
const auth = useAuthStore();
const farmContext = useFarmStore();
const activeTab = ref("stocks");
const loading = ref(false);
const stocks = ref<StockBalance[]>([]);
const ledger = ref<StockLedgerEntry[]>([]);
const inventoryCounts = ref<InventoryCount[]>([]);
const inventoryAnalysis = ref<InventoryAnalysis | null>(null);
const warehouses = ref<Warehouse[]>([]);
const items = ref<Item[]>([]);
const barns = ref<Barn[]>([]);
const plots = ref<Plot[]>([]);
const cropCycles = ref<CropCycle[]>([]);
const summary = reactive<StockSummary>({ itemCount: 0, totalValue: "0.00", lowStockCount: 0 });
const stockFilters = reactive({ keyword: "", warehouseId: null as number | null, lowStock: false });
const ledgerFilters = reactive({
  keyword: "",
  warehouseId: null as number | null,
  itemId: null as number | null,
  dateRange: [] as [string, string] | [],
});
const stockPagination = reactive({ page: 1, pageSize: 10, total: 0 });
const ledgerPagination = reactive({ page: 1, pageSize: 10, total: 0 });
const countFilters = reactive({
  keyword: "",
  status: "all" as "all" | InventoryCountStatus,
  dateRange: [] as [string, string] | [],
});
const countPagination = reactive({ page: 1, pageSize: 10, total: 0 });
const analysisLoading = ref(false);
const analysisFilters = reactive({
  warehouseId: null as number | null,
  expiryDays: 30,
  trendDays: 30,
});
const transferDialogVisible = ref(false);
const transferSaving = ref(false);
const transferForm = reactive({
  documentNo: "",
  transferDate: "",
  fromWarehouseId: null as number | null,
  toWarehouseId: null as number | null,
  itemId: null as number | null,
  quantity: 1,
  lotNo: "",
});
const productionDialogVisible = ref(false);
const productionSaving = ref(false);
const productionOperationOptions = [
  { label: "生产领料", value: "issue" },
  { label: "生产退料", value: "return" },
];
const productionCostObjectOptions = [
  { label: "农场通用", value: "farm" },
  { label: "圈舍", value: "barn" },
  { label: "地块", value: "plot" },
  { label: "种植周期", value: "crop_cycle" },
];
const productionForm = reactive({
  documentNo: "",
  operationType: "issue" as ProductionStockOperationType,
  operationDate: "",
  warehouseId: null as number | null,
  itemId: null as number | null,
  quantity: 1,
  lotNo: "",
  costObjectType: "farm" as ProductionCostObjectType,
  costObjectId: null as number | null,
});
const countDialogVisible = ref(false);
const countSaving = ref(false);
const countForm = reactive({
  id: null as number | null,
  countNo: "",
  warehouseId: null as number | null,
  warehouseName: "",
  countDate: "",
  notes: "",
  status: "DRAFT" as InventoryCountStatus,
  version: 1,
  lines: [] as InventoryCountLineDraft[],
});
const canOperateStock = computed(() => {
  const role = farmContext.currentFarm?.accessRole;
  return auth.isAdmin || role === "manager" || role === "operator";
});
const selectedTransferItem = computed(() => items.value.find((item) => item.id === transferForm.itemId));
const selectedProductionItem = computed(() => items.value.find((item) => item.id === productionForm.itemId));
const productionActionLabel = computed(() => productionForm.operationType === "issue" ? "确认领料" : "确认退料");
const countReadOnly = computed(() => countForm.status !== "DRAFT" || !canOperateStock.value);
const countDifferenceLineCount = computed(() => countForm.lines.filter((line) => countDifference(line) !== 0).length);
const countDialogTitle = computed(() => {
  if (!countForm.id) return "新建库存盘点";
  return countReadOnly.value ? "盘点单详情" : "盘点录入";
});
const selectableCostObjects = computed(() => {
  if (productionForm.costObjectType === "barn") {
    return barns.value.map((item) => ({ id: item.id, label: `${item.name} (${item.code})` }));
  }
  if (productionForm.costObjectType === "plot") {
    return plots.value.map((item) => ({ id: item.id, label: `${item.name} (${item.code})` }));
  }
  if (productionForm.costObjectType === "crop_cycle") {
    return cropCycles.value
      .filter((cycle) => cycle.status === "ACTIVE" || cycle.status === "HARVESTING")
      .map((cycle) => ({
        id: cycle.id,
        label: `${cycle.cycleCode} (${cycle.cropTypeName ?? "种植周期"})`,
      }));
  }
  return [];
});

function suggestedTransferNo() {
  const now = new Date();
  const compactDate = localDateInputValue().replaceAll("-", "");
  const compactTime = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map((value) => String(value).padStart(2, "0"))
    .join("");
  return `TR-${compactDate}-${compactTime}`;
}

function suggestedProductionNo(operationType: ProductionStockOperationType) {
  const now = new Date();
  const compactDate = localDateInputValue().replaceAll("-", "");
  const compactTime = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map((value) => String(value).padStart(2, "0"))
    .join("");
  return `${operationType === "issue" ? "PI" : "PR"}-${compactDate}-${compactTime}`;
}

function suggestedCountNo() {
  const now = new Date();
  const compactDate = localDateInputValue().replaceAll("-", "");
  const compactTime = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map((value) => String(value).padStart(2, "0"))
    .join("");
  return `IC-${compactDate}-${compactTime}`;
}

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "-";
}

function documentTypeLabel(entry: StockLedgerEntry) {
  if (entry.documentType === "PURCHASE_RECEIPT") return "采购入库";
  if (entry.documentType === "PURCHASE_RETURN") return "采购退货";
  if (entry.documentType === "WAREHOUSE_TRANSFER") {
    return Number(entry.quantityDelta) < 0 ? "调拨出库" : "调拨入库";
  }
  if (entry.documentType === "PRODUCTION_ISSUE") return "生产领料";
  if (entry.documentType === "PRODUCTION_RETURN") return "生产退料";
  if (entry.documentType === "INVENTORY_ADJUSTMENT") {
    return Number(entry.quantityDelta) < 0 ? "盘亏调整" : "盘盈调整";
  }
  return entry.documentType;
}

function costObjectLabel(entry: StockLedgerEntry) {
  if (entry.costObjectType === "FARM") return `${farmContext.currentFarm?.name ?? "当前农场"}（通用）`;
  if (entry.costObjectType === "CROP_CYCLE") {
    const cycle = cropCycles.value.find((item) => item.id === entry.costObjectId);
    return cycle ? `${cycle.cycleCode} (${cycle.cropTypeName ?? "种植周期"})` : `种植周期 #${entry.costObjectId}`;
  }
  const resources = entry.costObjectType === "BARN" ? barns.value : entry.costObjectType === "PLOT" ? plots.value : [];
  const resource = resources.find((item) => item.id === entry.costObjectId);
  if (resource) return `${resource.name} (${resource.code})`;
  if (entry.costObjectType === "BARN") return `圈舍 #${entry.costObjectId}`;
  if (entry.costObjectType === "PLOT") return `地块 #${entry.costObjectId}`;
  if (entry.costObjectType === "LIVESTOCK_BATCH") return `养殖批次 #${entry.costObjectId}`;
  return "-";
}

function signedQuantity(value: string) {
  return Number(value) > 0 ? `+${value}` : value;
}

function quantityClass(value: string) {
  return Number(value) < 0 ? "quantity-out" : "quantity-in";
}

function countStatusName(status: InventoryCountStatus) {
  return status === "POSTED" ? "已过账" : status === "CANCELLED" ? "已取消" : "草稿";
}

function countStatusTag(status: InventoryCountStatus) {
  return status === "POSTED" ? "success" : status === "CANCELLED" ? "info" : "warning";
}

function countDifference(line: InventoryCountLineDraft) {
  return Number((line.actualQuantity - Number(line.bookQuantity)).toFixed(3));
}

function countQuantityText(value: number) {
  return value.toFixed(3).replace(/\.?(?:0+)$/, "");
}

function countDifferenceText(line: InventoryCountLineDraft) {
  const difference = countDifference(line);
  return `${difference > 0 ? "+" : ""}${countQuantityText(difference)}`;
}

function expiryStatusName(lot: InventoryExpiryLot) {
  if (lot.daysRemaining < 0) return `已过期 ${Math.abs(lot.daysRemaining)} 天`;
  if (lot.daysRemaining === 0) return "今天到期";
  return `${lot.daysRemaining} 天后到期`;
}

function expiryStatusTag(lot: InventoryExpiryLot) {
  return lot.status === "EXPIRED" ? "danger" : "warning";
}

function expiryLotKey(lot: InventoryExpiryLot) {
  return `${lot.warehouseId}-${lot.itemId}-${lot.lotNo ?? ""}`;
}

function setCountForm(inventoryCount: InventoryCount) {
  countForm.id = inventoryCount.id;
  countForm.countNo = inventoryCount.countNo;
  countForm.warehouseId = inventoryCount.warehouseId;
  countForm.warehouseName = inventoryCount.warehouseName;
  countForm.countDate = inventoryCount.countDate;
  countForm.notes = inventoryCount.notes ?? "";
  countForm.status = inventoryCount.status;
  countForm.version = inventoryCount.version;
  countForm.lines = (inventoryCount.lines ?? []).map((line) => ({
    ...line,
    actualQuantity: Number(line.actualQuantity),
    reason: line.reason ?? "",
  }));
}

function openCountDialog() {
  if (!warehouses.value.length) return ElMessage.error("请先建立可用仓库");
  countForm.id = null;
  countForm.countNo = suggestedCountNo();
  countForm.warehouseId = warehouses.value[0]?.id ?? null;
  countForm.warehouseName = warehouses.value[0]?.name ?? "";
  countForm.countDate = localDateInputValue();
  countForm.notes = "";
  countForm.status = "DRAFT";
  countForm.version = 1;
  countForm.lines = [];
  countDialogVisible.value = true;
}

async function openInventoryCount(row: InventoryCount) {
  countSaving.value = true;
  try {
    setCountForm(await getInventoryCount(row.id));
    countDialogVisible.value = true;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    countSaving.value = false;
  }
}

async function generateInventoryCount() {
  const farmId = farmContext.currentFarmId;
  const countNo = countForm.countNo.trim();
  if (!farmId) return ElMessage.error("请先选择农场");
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(countNo)) {
    return ElMessage.error("盘点单号须为 3-40 位字母、数字、下划线或短横线");
  }
  if (!countForm.countDate) return ElMessage.error("请选择盘点日期");
  if (!countForm.warehouseId) return ElMessage.error("请选择盘点仓库");
  countSaving.value = true;
  try {
    const inventoryCount = await createInventoryCount({
      farmId,
      countNo,
      warehouseId: countForm.warehouseId,
      countDate: countForm.countDate,
      notes: countForm.notes.trim() || null,
    });
    setCountForm(inventoryCount);
    await loadCounts();
    ElMessage.success("盘点单已生成，请录入实盘数量");
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    countSaving.value = false;
  }
}

async function saveCountDraft(showSuccess = true): Promise<InventoryCount | null> {
  if (!countForm.id) return null;
  const invalidLine = countForm.lines.find((line) => (
    !Number.isFinite(line.actualQuantity) || line.actualQuantity < 0
  ));
  if (invalidLine) {
    ElMessage.error(`“${invalidLine.itemName}”的实盘数量不能小于 0`);
    return null;
  }
  const missingReason = countForm.lines.find((line) => countDifference(line) !== 0 && !line.reason.trim());
  if (missingReason) {
    ElMessage.error(`“${missingReason.itemName}”存在盘点差异，请填写原因`);
    return null;
  }
  countSaving.value = true;
  try {
    const inventoryCount = await updateInventoryCount(countForm.id, {
      version: countForm.version,
      notes: countForm.notes.trim() || null,
      lines: countForm.lines.map((line) => ({
        id: line.id,
        actualQuantity: line.actualQuantity,
        reason: line.reason.trim() || null,
      })),
    });
    setCountForm(inventoryCount);
    await loadCounts();
    if (showSuccess) ElMessage.success("盘点草稿已保存");
    return inventoryCount;
  } catch (error) {
    ElMessage.error(errorMessage(error));
    return null;
  } finally {
    countSaving.value = false;
  }
}

async function postCountDraft() {
  const saved = await saveCountDraft(false);
  if (!saved) return;
  try {
    await ElMessageBox.confirm(
      `确认过账 ${saved.countNo}？系统将按 ${saved.differenceLineCount} 条差异调整库存，过账后不能修改。`,
      "确认盘点过账",
      { type: "warning", confirmButtonText: "确认过账", cancelButtonText: "取消" },
    );
    countSaving.value = true;
    const posted = await postInventoryCount(saved.id, saved.version);
    setCountForm(posted);
    await Promise.all([loadCounts(), loadStocks(), loadLedger(), loadAnalysis()]);
    ElMessage.success("盘点单已过账，库存余额和流水已同步更新");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error));
  } finally {
    countSaving.value = false;
  }
}

async function cancelCount(row: InventoryCount) {
  try {
    await ElMessageBox.confirm(`确认取消盘点单 ${row.countNo}？`, "取消盘点单", {
      type: "warning",
      confirmButtonText: "确认取消",
      cancelButtonText: "返回",
    });
    const cancelled = await cancelInventoryCount(row.id, row.version);
    if (countForm.id === row.id) setCountForm(cancelled);
    await loadCounts();
    ElMessage.success("盘点单已取消");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error));
  }
}

function openTransferDialog() {
  if (warehouses.value.length < 2) return ElMessage.error("库存调拨至少需要两个启用仓库");
  if (!items.value.length) return ElMessage.error("请先建立可用物料");
  transferForm.documentNo = suggestedTransferNo();
  transferForm.transferDate = localDateInputValue();
  transferForm.fromWarehouseId = warehouses.value[0]?.id ?? null;
  transferForm.toWarehouseId = warehouses.value.find(
    (warehouse) => warehouse.id !== transferForm.fromWarehouseId,
  )?.id ?? null;
  transferForm.itemId = items.value[0]?.id ?? null;
  transferForm.quantity = 1;
  transferForm.lotNo = "";
  transferDialogVisible.value = true;
}

function selectDefaultProductionCostObject() {
  if (productionForm.costObjectType === "barn") {
    productionForm.costObjectId = barns.value[0]?.id ?? null;
  } else if (productionForm.costObjectType === "plot") {
    productionForm.costObjectId = plots.value[0]?.id ?? null;
  } else if (productionForm.costObjectType === "crop_cycle") {
    productionForm.costObjectId = selectableCostObjects.value[0]?.id ?? null;
  } else {
    productionForm.costObjectId = null;
  }
}

function updateProductionOperationType() {
  productionForm.documentNo = suggestedProductionNo(productionForm.operationType);
}

function openProductionDialog() {
  if (!warehouses.value.length) return ElMessage.error("请先建立可用仓库");
  if (!items.value.length) return ElMessage.error("请先建立可用物料");
  productionForm.operationType = "issue";
  productionForm.documentNo = suggestedProductionNo("issue");
  productionForm.operationDate = localDateInputValue();
  productionForm.warehouseId = warehouses.value[0]?.id ?? null;
  productionForm.itemId = items.value[0]?.id ?? null;
  productionForm.quantity = 1;
  productionForm.lotNo = "";
  productionForm.costObjectType = "farm";
  productionForm.costObjectId = null;
  productionDialogVisible.value = true;
}

function selectedCostObjectLabel() {
  if (productionForm.costObjectType === "farm") return `${farmContext.currentFarm?.name ?? "当前农场"}（通用）`;
  const resource = selectableCostObjects.value.find((item) => item.id === productionForm.costObjectId);
  return resource?.label ?? "未选择使用对象";
}

async function saveProductionOperation() {
  const farmId = farmContext.currentFarmId;
  const documentNo = productionForm.documentNo.trim();
  const operationLabel = productionForm.operationType === "issue" ? "领料" : "退料";
  if (!farmId) return ElMessage.error("请先选择农场");
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(documentNo)) {
    return ElMessage.error("领退料单号须为 3-40 位字母、数字、下划线或短横线");
  }
  if (!productionForm.operationDate) return ElMessage.error("请选择业务日期");
  if (!productionForm.warehouseId) return ElMessage.error("请选择领退仓库");
  if (!productionForm.itemId) return ElMessage.error("请选择生产物料");
  if (!productionForm.quantity || productionForm.quantity <= 0) return ElMessage.error("领退数量必须大于 0");
  if (selectedProductionItem.value?.lotTracking && !productionForm.lotNo.trim()) {
    return ElMessage.error(`物料“${selectedProductionItem.value.name}”必须填写批号`);
  }
  if (productionForm.costObjectType !== "farm" && !productionForm.costObjectId) {
    const labels: Record<Exclude<ProductionCostObjectType, "farm">, string> = {
      barn: "圈舍",
      plot: "地块",
      livestock_batch: "养殖批次",
      crop_cycle: "种植周期",
    };
    return ElMessage.error(`请选择${labels[productionForm.costObjectType]}`);
  }
  try {
    await ElMessageBox.confirm(
      `确认${operationLabel} ${productionForm.quantity} ${selectedProductionItem.value?.unitName ?? ""} ${selectedProductionItem.value?.name ?? "物料"}，使用对象为${selectedCostObjectLabel()}？`,
      `确认生产${operationLabel}`,
      { type: "warning", confirmButtonText: `确认${operationLabel}`, cancelButtonText: "取消" },
    );
    productionSaving.value = true;
    const operation = await createProductionStockOperation({
      farmId,
      documentNo,
      operationType: productionForm.operationType,
      operationDate: productionForm.operationDate,
      warehouseId: productionForm.warehouseId,
      itemId: productionForm.itemId,
      quantity: productionForm.quantity,
      lotNo: productionForm.lotNo.trim() || null,
      costObjectType: productionForm.costObjectType,
      costObjectId: productionForm.costObjectType === "farm" ? null : productionForm.costObjectId,
    });
    productionDialogVisible.value = false;
    activeTab.value = "ledger";
    ledgerFilters.keyword = operation.documentNo;
    ledgerPagination.page = 1;
    await Promise.all([loadStocks(), loadLedger(), loadAnalysis()]);
    ElMessage.success(`生产${operationLabel}已过账，库存余额已同步更新`);
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error));
  } finally {
    productionSaving.value = false;
  }
}

async function saveTransfer() {
  const farmId = farmContext.currentFarmId;
  const documentNo = transferForm.documentNo.trim();
  if (!farmId) return ElMessage.error("请先选择农场");
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(documentNo)) {
    return ElMessage.error("调拨单号须为 3-40 位字母、数字、下划线或短横线");
  }
  if (!transferForm.transferDate) return ElMessage.error("请选择调拨日期");
  if (!transferForm.fromWarehouseId || !transferForm.toWarehouseId) return ElMessage.error("请选择调出和调入仓库");
  if (transferForm.fromWarehouseId === transferForm.toWarehouseId) return ElMessage.error("调出和调入仓库不能相同");
  if (!transferForm.itemId) return ElMessage.error("请选择调拨物料");
  if (!transferForm.quantity || transferForm.quantity <= 0) return ElMessage.error("调拨数量必须大于 0");
  if (selectedTransferItem.value?.lotTracking && !transferForm.lotNo.trim()) {
    return ElMessage.error(`物料“${selectedTransferItem.value.name}”必须填写批号`);
  }
  try {
    await ElMessageBox.confirm(
      `确认将 ${transferForm.quantity} ${selectedTransferItem.value?.unitName ?? ""} ${selectedTransferItem.value?.name ?? "物料"} 调拨到目标仓库？`,
      "确认库存调拨",
      { type: "warning", confirmButtonText: "确认调拨", cancelButtonText: "取消" },
    );
    transferSaving.value = true;
    const transfer = await createStockTransfer({
      farmId,
      documentNo,
      fromWarehouseId: transferForm.fromWarehouseId,
      toWarehouseId: transferForm.toWarehouseId,
      transferDate: transferForm.transferDate,
      itemId: transferForm.itemId,
      quantity: transferForm.quantity,
      lotNo: transferForm.lotNo.trim() || null,
    });
    transferDialogVisible.value = false;
    activeTab.value = "ledger";
    ledgerFilters.keyword = transfer.documentNo;
    ledgerPagination.page = 1;
    await Promise.all([loadStocks(), loadLedger(), loadAnalysis()]);
    ElMessage.success("库存调拨已过账，两个仓库的余额已同步更新");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(errorMessage(error));
  } finally {
    transferSaving.value = false;
  }
}

async function loadReferences() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    warehouses.value = [];
    items.value = [];
    barns.value = [];
    plots.value = [];
    cropCycles.value = [];
    return;
  }
  try {
    const [warehouseData, itemData, barnData, plotData, cropCycleData] = await Promise.all([
      getWarehouses({ farmId, page: 1, pageSize: 100, status: "active" }),
      getItems({ farmId, page: 1, pageSize: 100, status: "active" }),
      getBarns({ farmId, page: 1, pageSize: 100, status: "active" }),
      getPlots({ farmId, page: 1, pageSize: 100, status: "active" }),
      getCropCycles({ farmId, page: 1, pageSize: 100, status: "all" }),
    ]);
    warehouses.value = warehouseData.items;
    items.value = itemData.items;
    barns.value = barnData.items;
    plots.value = plotData.items;
    cropCycles.value = cropCycleData.items;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

async function loadStocks() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    stocks.value = [];
    stockPagination.total = 0;
    Object.assign(summary, { itemCount: 0, totalValue: "0.00", lowStockCount: 0 });
    return;
  }
  loading.value = true;
  try {
    const data = await getStocks({
      farmId,
      page: stockPagination.page,
      pageSize: stockPagination.pageSize,
      keyword: stockFilters.keyword || undefined,
      warehouseId: stockFilters.warehouseId || undefined,
      lowStock: stockFilters.lowStock || undefined,
    });
    stocks.value = data.items;
    stockPagination.total = data.pagination.total;
    Object.assign(summary, data.summary);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function loadLedger() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    ledger.value = [];
    ledgerPagination.total = 0;
    return;
  }
  loading.value = true;
  try {
    const data = await getStockLedger({
      farmId,
      page: ledgerPagination.page,
      pageSize: ledgerPagination.pageSize,
      keyword: ledgerFilters.keyword || undefined,
      warehouseId: ledgerFilters.warehouseId || undefined,
      itemId: ledgerFilters.itemId || undefined,
      dateFrom: ledgerFilters.dateRange[0] || undefined,
      dateTo: ledgerFilters.dateRange[1] || undefined,
    });
    ledger.value = data.items;
    ledgerPagination.total = data.pagination.total;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function loadCounts() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    inventoryCounts.value = [];
    countPagination.total = 0;
    return;
  }
  loading.value = true;
  try {
    const data = await getInventoryCounts({
      farmId,
      page: countPagination.page,
      pageSize: countPagination.pageSize,
      keyword: countFilters.keyword || undefined,
      status: countFilters.status,
      dateFrom: countFilters.dateRange[0] || undefined,
      dateTo: countFilters.dateRange[1] || undefined,
    });
    inventoryCounts.value = data.items;
    countPagination.total = data.pagination.total;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

async function loadAnalysis() {
  const farmId = farmContext.currentFarmId;
  if (!farmId) {
    inventoryAnalysis.value = null;
    return;
  }
  analysisLoading.value = true;
  try {
    inventoryAnalysis.value = await getInventoryAnalysis({
      farmId,
      warehouseId: analysisFilters.warehouseId || undefined,
      expiryDays: analysisFilters.expiryDays,
      trendDays: analysisFilters.trendDays,
    });
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    analysisLoading.value = false;
  }
}

function searchStocks() {
  stockPagination.page = 1;
  void loadStocks();
}

function resetStockFilters() {
  stockFilters.keyword = "";
  stockFilters.warehouseId = null;
  stockFilters.lowStock = false;
  searchStocks();
}

function searchLedger() {
  ledgerPagination.page = 1;
  void loadLedger();
}

function resetLedgerFilters() {
  ledgerFilters.keyword = "";
  ledgerFilters.warehouseId = null;
  ledgerFilters.itemId = null;
  ledgerFilters.dateRange = [];
  searchLedger();
}

function searchCounts() {
  countPagination.page = 1;
  void loadCounts();
}

function resetCountFilters() {
  countFilters.keyword = "";
  countFilters.status = "all";
  countFilters.dateRange = [];
  searchCounts();
}

watch(
  () => farmContext.currentFarmId,
  async () => {
    stockPagination.page = 1;
    ledgerPagination.page = 1;
    countPagination.page = 1;
    stockFilters.keyword = "";
    stockFilters.warehouseId = null;
    stockFilters.lowStock = false;
    ledgerFilters.keyword = "";
    ledgerFilters.warehouseId = null;
    ledgerFilters.itemId = null;
    ledgerFilters.dateRange = [];
    countFilters.keyword = "";
    countFilters.status = "all";
    countFilters.dateRange = [];
    analysisFilters.warehouseId = null;
    analysisFilters.expiryDays = 30;
    analysisFilters.trendDays = 30;
    transferDialogVisible.value = false;
    productionDialogVisible.value = false;
    countDialogVisible.value = false;
    await Promise.all([loadReferences(), loadStocks(), loadLedger(), loadCounts(), loadAnalysis()]);
  },
  { immediate: true },
);
</script>

<template>
  <section class="farm-page inventory-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">INVENTORY CONTROL</p>
        <h1>库存管理</h1>
        <p v-if="farmContext.currentFarm">{{ farmContext.currentFarm.name }} · {{ summary.itemCount }} 项库存</p>
        <p v-else>尚未选择农场</p>
      </div>
      <div v-if="farmContext.currentFarm && canOperateStock" class="inventory-page-actions">
        <el-button :icon="DocumentChecked" @click="openCountDialog">新建盘点</el-button>
        <el-button :icon="Right" @click="openTransferDialog">新建调拨</el-button>
        <el-button type="primary" :icon="Goods" @click="openProductionDialog">生产领退料</el-button>
      </div>
    </header>

    <el-empty v-if="!farmContext.currentFarm" class="resource-empty" description="暂无可用农场">
      <el-button v-if="auth.isAdmin" type="primary" @click="router.push('/base/farms')">前往农场档案</el-button>
    </el-empty>

    <template v-else>
      <div class="inventory-summary-grid" aria-label="库存汇总">
        <div class="inventory-summary-item"><span class="summary-icon tone-green"><el-icon><Box /></el-icon></span><div><p>库存物料</p><strong>{{ summary.itemCount }}<small>项</small></strong></div></div>
        <div class="inventory-summary-item"><span class="summary-icon tone-blue"><el-icon><Coin /></el-icon></span><div><p>库存金额</p><strong>¥ {{ summary.totalValue }}</strong></div></div>
        <div class="inventory-summary-item"><span class="summary-icon tone-amber"><el-icon><Warning /></el-icon></span><div><p>低库存</p><strong>{{ summary.lowStockCount }}<small>项</small></strong></div></div>
        <div class="inventory-summary-item"><span class="summary-icon tone-red"><el-icon><Timer /></el-icon></span><div><p>效期预警</p><strong>{{ inventoryAnalysis?.summary.warningLotCount ?? 0 }}<small>批</small></strong></div></div>
      </div>

      <el-tabs v-model="activeTab" class="base-tabs">
        <el-tab-pane label="库存现状" name="stocks">
          <div class="farm-toolbar stock-toolbar" role="search" aria-label="筛选库存">
            <el-input v-model="stockFilters.keyword" clearable :prefix-icon="Search" placeholder="搜索物料或仓库" aria-label="搜索库存" @clear="searchStocks" @keyup.enter="searchStocks" />
            <el-select v-model="stockFilters.warehouseId" clearable placeholder="全部仓库" aria-label="筛选库存仓库" @change="searchStocks"><el-option v-for="item in warehouses" :key="item.id" :label="item.name" :value="item.id" /></el-select>
            <el-checkbox v-model="stockFilters.lowStock" border @change="searchStocks">仅看低库存</el-checkbox>
            <el-button type="primary" :icon="Search" @click="searchStocks">查询</el-button><el-button :icon="Refresh" @click="resetStockFilters">重置</el-button>
          </div>
          <div class="farm-table-shell">
            <el-table v-loading="loading" :data="stocks" row-key="id" empty-text="当前筛选下暂无库存">
              <el-table-column label="物料" min-width="180"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.itemName }}</strong><span>{{ scope.row.itemCode }}</span></div></template></el-table-column>
              <el-table-column prop="warehouseName" label="仓库" min-width="130" />
              <el-table-column label="现存数量" min-width="120" align="right"><template #default="scope"><strong>{{ scope.row.quantity }}</strong> {{ scope.row.unitName }}</template></el-table-column>
              <el-table-column label="移动平均价" min-width="125" align="right"><template #default="scope">¥ {{ scope.row.averageCost }}</template></el-table-column>
              <el-table-column label="库存金额" min-width="125" align="right"><template #default="scope">¥ {{ scope.row.inventoryValue }}</template></el-table-column>
              <el-table-column label="安全库存" min-width="115" align="right"><template #default="scope">{{ scope.row.safetyStock }} {{ scope.row.unitName }}</template></el-table-column>
              <el-table-column label="预警" width="90"><template #default="scope"><el-tag v-if="scope.row.lowStock" type="warning" effect="plain">偏低</el-tag><span v-else>-</span></template></el-table-column>
            </el-table>
            <footer class="admin-pagination"><span>共 {{ stockPagination.total }} 项库存</span><el-pagination :current-page="stockPagination.page" :page-size="stockPagination.pageSize" :page-sizes="[10, 20, 50]" :total="stockPagination.total" layout="sizes, prev, pager, next" @current-change="(page: number) => { stockPagination.page = page; loadStocks(); }" @size-change="(size: number) => { stockPagination.page = 1; stockPagination.pageSize = size; loadStocks(); }" /></footer>
          </div>
        </el-tab-pane>

        <el-tab-pane label="库存流水" name="ledger">
          <div class="farm-toolbar ledger-toolbar" role="search" aria-label="筛选库存流水">
            <el-input v-model="ledgerFilters.keyword" clearable :prefix-icon="Search" placeholder="搜索单号或物料" aria-label="搜索库存流水" @clear="searchLedger" @keyup.enter="searchLedger" />
            <el-select v-model="ledgerFilters.warehouseId" clearable placeholder="全部仓库" aria-label="筛选流水仓库"><el-option v-for="item in warehouses" :key="item.id" :label="item.name" :value="item.id" /></el-select>
            <el-select v-model="ledgerFilters.itemId" clearable filterable placeholder="全部物料" aria-label="筛选流水物料"><el-option v-for="item in items" :key="item.id" :label="item.name" :value="item.id" /></el-select>
            <el-date-picker v-model="ledgerFilters.dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" aria-label="流水日期范围" />
            <el-button type="primary" :icon="Search" @click="searchLedger">查询</el-button><el-button :icon="Refresh" @click="resetLedgerFilters">重置</el-button>
          </div>
          <div class="farm-table-shell">
            <el-table v-loading="loading" :data="ledger" row-key="id" empty-text="当前筛选下暂无库存流水">
              <el-table-column label="库存单" min-width="180"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.documentNo }}</strong><span>{{ formatDateTime(scope.row.occurredAt) }}</span></div></template></el-table-column>
              <el-table-column label="业务类型" min-width="110"><template #default="scope">{{ documentTypeLabel(scope.row) }}</template></el-table-column>
              <el-table-column label="物料" min-width="160"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.itemName }}</strong><span>{{ scope.row.itemCode }}</span></div></template></el-table-column>
              <el-table-column prop="warehouseName" label="仓库" min-width="120" />
              <el-table-column label="使用对象" min-width="180"><template #default="scope">{{ costObjectLabel(scope.row) }}</template></el-table-column>
              <el-table-column label="数量变化" min-width="120" align="right"><template #default="scope"><strong :class="quantityClass(scope.row.quantityDelta)">{{ signedQuantity(scope.row.quantityDelta) }}</strong> {{ scope.row.unitName }}</template></el-table-column>
              <el-table-column label="单位成本" min-width="110" align="right"><template #default="scope">¥ {{ scope.row.unitCost }}</template></el-table-column>
              <el-table-column label="金额" min-width="110" align="right"><template #default="scope">¥ {{ scope.row.amount }}</template></el-table-column>
              <el-table-column label="批号/有效期" min-width="150"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.lotNo || "-" }}</strong><span>{{ scope.row.expiresOn || "无有效期" }}</span></div></template></el-table-column>
            </el-table>
            <footer class="admin-pagination"><span>共 {{ ledgerPagination.total }} 条流水</span><el-pagination :current-page="ledgerPagination.page" :page-size="ledgerPagination.pageSize" :page-sizes="[10, 20, 50]" :total="ledgerPagination.total" layout="sizes, prev, pager, next" @current-change="(page: number) => { ledgerPagination.page = page; loadLedger(); }" @size-change="(size: number) => { ledgerPagination.page = 1; ledgerPagination.pageSize = size; loadLedger(); }" /></footer>
          </div>
        </el-tab-pane>

        <el-tab-pane label="库存盘点" name="counts">
          <div class="farm-toolbar count-toolbar" role="search" aria-label="筛选库存盘点">
            <el-input v-model="countFilters.keyword" clearable :prefix-icon="Search" placeholder="搜索盘点单号或仓库" aria-label="搜索库存盘点" @clear="searchCounts" @keyup.enter="searchCounts" />
            <el-select v-model="countFilters.status" aria-label="筛选盘点状态" @change="searchCounts">
              <el-option label="全部状态" value="all" />
              <el-option label="草稿" value="DRAFT" />
              <el-option label="已过账" value="POSTED" />
              <el-option label="已取消" value="CANCELLED" />
            </el-select>
            <el-date-picker v-model="countFilters.dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" aria-label="盘点日期范围" />
            <el-button type="primary" :icon="Search" @click="searchCounts">查询</el-button><el-button :icon="Refresh" @click="resetCountFilters">重置</el-button>
          </div>
          <div class="farm-table-shell">
            <el-table v-loading="loading" :data="inventoryCounts" row-key="id" empty-text="当前筛选下暂无盘点单">
              <el-table-column label="盘点单" min-width="180"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.countNo }}</strong><span>{{ formatDateTime(scope.row.createdAt) }}</span></div></template></el-table-column>
              <el-table-column prop="warehouseName" label="盘点仓库" min-width="130" />
              <el-table-column prop="countDate" label="盘点日期" min-width="115" />
              <el-table-column label="状态" width="100"><template #default="scope"><el-tag :type="countStatusTag(scope.row.status)" effect="plain">{{ countStatusName(scope.row.status) }}</el-tag></template></el-table-column>
              <el-table-column label="库存批次" min-width="105" align="right"><template #default="scope">{{ scope.row.lineCount }} 条</template></el-table-column>
              <el-table-column label="差异" min-width="100" align="right"><template #default="scope"><strong :class="scope.row.differenceLineCount ? 'quantity-out' : ''">{{ scope.row.differenceLineCount }} 条</strong></template></el-table-column>
              <el-table-column label="调整单" min-width="150"><template #default="scope">{{ scope.row.adjustmentDocumentNo || "-" }}</template></el-table-column>
              <el-table-column label="操作" width="150" fixed="right"><template #default="scope"><div class="purchase-actions"><el-button link type="primary" @click="openInventoryCount(scope.row)">{{ scope.row.status === "DRAFT" && canOperateStock ? "盘点录入" : "查看" }}</el-button><el-button v-if="scope.row.status === 'DRAFT' && canOperateStock" link type="danger" @click="cancelCount(scope.row)">取消</el-button></div></template></el-table-column>
            </el-table>
            <footer class="admin-pagination"><span>共 {{ countPagination.total }} 张盘点单</span><el-pagination :current-page="countPagination.page" :page-size="countPagination.pageSize" :page-sizes="[10, 20, 50]" :total="countPagination.total" layout="sizes, prev, pager, next" @current-change="(page: number) => { countPagination.page = page; loadCounts(); }" @size-change="(size: number) => { countPagination.page = 1; countPagination.pageSize = size; loadCounts(); }" /></footer>
          </div>
        </el-tab-pane>

        <el-tab-pane label="库存分析" name="analysis">
          <div class="farm-toolbar analysis-toolbar" role="search" aria-label="筛选库存分析">
            <el-select v-model="analysisFilters.warehouseId" clearable placeholder="全部仓库" aria-label="筛选分析仓库" @change="loadAnalysis"><el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" /></el-select>
            <el-select v-model="analysisFilters.expiryDays" aria-label="效期预警范围" @change="loadAnalysis"><el-option label="7 天内到期" :value="7" /><el-option label="30 天内到期" :value="30" /><el-option label="90 天内到期" :value="90" /><el-option label="180 天内到期" :value="180" /></el-select>
            <el-select v-model="analysisFilters.trendDays" aria-label="趋势统计周期" @change="loadAnalysis"><el-option label="近 7 天" :value="7" /><el-option label="近 30 天" :value="30" /><el-option label="近 90 天" :value="90" /></el-select>
            <el-button type="primary" :icon="Refresh" :loading="analysisLoading" @click="loadAnalysis">刷新分析</el-button>
          </div>

          <div v-loading="analysisLoading" class="inventory-analysis-content">
            <div class="analysis-metrics" aria-label="库存分析汇总">
              <div><span>期间入库金额</span><strong class="quantity-in">¥ {{ inventoryAnalysis?.summary.periodInboundAmount ?? "0.00" }}</strong></div>
              <div><span>期间出库金额</span><strong class="quantity-out">¥ {{ inventoryAnalysis?.summary.periodOutboundAmount ?? "0.00" }}</strong></div>
              <div><span>临期批次</span><strong>{{ inventoryAnalysis?.summary.expiringLotCount ?? 0 }}<small>批</small></strong></div>
              <div><span>过期批次</span><strong class="quantity-out">{{ inventoryAnalysis?.summary.expiredLotCount ?? 0 }}<small>批</small></strong></div>
            </div>

            <div class="inventory-analysis-grid">
              <section class="inventory-analysis-panel" aria-labelledby="inventoryTrendTitle">
                <header class="analysis-panel-header"><div><h2 id="inventoryTrendTitle">库存流动金额</h2><span>{{ inventoryAnalysis?.period.dateFrom ?? "-" }} 至 {{ inventoryAnalysis?.period.dateTo ?? "-" }}</span></div></header>
                <inventory-trend-chart :data="inventoryAnalysis?.trend ?? []" />
              </section>
              <section class="inventory-analysis-panel" aria-labelledby="inventoryConsumptionTitle">
                <header class="analysis-panel-header"><div><h2 id="inventoryConsumptionTitle">生产净耗用排行</h2><span>领料扣除同期退料</span></div></header>
                <div v-if="inventoryAnalysis?.topConsumedItems.length" class="consumption-list">
                  <div v-for="(item, index) in inventoryAnalysis.topConsumedItems" :key="item.itemId" class="consumption-row">
                    <span class="consumption-rank">{{ index + 1 }}</span>
                    <div class="farm-name-cell"><strong>{{ item.itemName }}</strong><span>{{ item.itemCode }}</span></div>
                    <div class="consumption-value"><strong>{{ item.netQuantity }} {{ item.unitName }}</strong><span>¥ {{ item.netAmount }}</span></div>
                  </div>
                </div>
                <el-empty v-else :image-size="70" description="当前周期暂无生产耗用" />
              </section>
            </div>

            <div class="analysis-section-header"><div><h2>临期与过期批次</h2><span>{{ analysisFilters.expiryDays }} 天预警范围</span></div></div>
            <div class="farm-table-shell">
              <el-table :data="inventoryAnalysis?.expiryLots ?? []" :row-key="expiryLotKey" empty-text="当前范围内暂无效期预警">
                <el-table-column label="物料" min-width="180"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.itemName }}</strong><span>{{ scope.row.itemCode }}</span></div></template></el-table-column>
                <el-table-column prop="warehouseName" label="仓库" min-width="140" />
                <el-table-column label="批号" min-width="140"><template #default="scope">{{ scope.row.lotNo || "-" }}</template></el-table-column>
                <el-table-column label="当前数量" min-width="125" align="right"><template #default="scope"><strong>{{ scope.row.quantity }}</strong> {{ scope.row.unitName }}</template></el-table-column>
                <el-table-column prop="expiresOn" label="有效期" min-width="120" />
                <el-table-column label="状态" min-width="140"><template #default="scope"><el-tag :type="expiryStatusTag(scope.row)" effect="plain">{{ expiryStatusName(scope.row) }}</el-tag></template></el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-dialog v-model="countDialogVisible" :title="countDialogTitle" width="min(96vw, 1100px)" :close-on-click-modal="false" destroy-on-close>
      <el-form label-position="top" @submit.prevent="countForm.id ? saveCountDraft() : generateInventoryCount()">
        <div class="farm-form-grid count-header-form">
          <el-form-item label="盘点单号" required><el-input v-model="countForm.countNo" maxlength="40" :disabled="Boolean(countForm.id)" aria-label="盘点单号" /></el-form-item>
          <el-form-item label="盘点日期" required><el-date-picker v-model="countForm.countDate" class="full-width-control" type="date" value-format="YYYY-MM-DD" :disabled="Boolean(countForm.id)" aria-label="盘点日期" /></el-form-item>
          <el-form-item label="盘点仓库" required><el-select v-model="countForm.warehouseId" class="full-width-control" filterable :disabled="Boolean(countForm.id)" aria-label="盘点仓库"><el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" /></el-select></el-form-item>
          <el-form-item label="盘点状态"><el-input :model-value="countStatusName(countForm.status)" disabled aria-label="盘点状态" /></el-form-item>
          <el-form-item class="farm-form-span" label="备注"><el-input v-model="countForm.notes" type="textarea" :rows="2" maxlength="500" show-word-limit :disabled="countReadOnly" aria-label="盘点备注" /></el-form-item>
        </div>

        <template v-if="countForm.id">
          <div class="purchase-lines-header count-lines-header">
            <h3>盘点明细</h3>
            <span>共 {{ countForm.lines.length }} 个库存批次，{{ countDifferenceLineCount }} 条差异</span>
          </div>
          <div class="count-lines-table">
            <el-table :data="countForm.lines" row-key="id" empty-text="暂无盘点明细">
              <el-table-column label="物料" min-width="170"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.itemName }}</strong><span>{{ scope.row.itemCode }}</span></div></template></el-table-column>
              <el-table-column label="批号/有效期" min-width="145"><template #default="scope"><div class="farm-name-cell"><strong>{{ scope.row.lotNo || "无批号" }}</strong><span>{{ scope.row.expiresOn || "无有效期" }}</span></div></template></el-table-column>
              <el-table-column label="账面数量" min-width="115" align="right"><template #default="scope">{{ scope.row.bookQuantity }} {{ scope.row.unitName }}</template></el-table-column>
              <el-table-column label="实盘数量" min-width="160" align="right"><template #default="scope"><el-input-number v-if="!countReadOnly" v-model="scope.row.actualQuantity" class="count-quantity-input" :min="0" :precision="3" controls-position="right" :aria-label="`实盘数量-${scope.row.itemCode}-${scope.row.lotNo || '无批号'}`" /><span v-else>{{ countQuantityText(scope.row.actualQuantity) }} {{ scope.row.unitName }}</span></template></el-table-column>
              <el-table-column label="差异" min-width="105" align="right"><template #default="scope"><strong :class="countDifference(scope.row) < 0 ? 'quantity-out' : countDifference(scope.row) > 0 ? 'quantity-in' : ''">{{ countDifferenceText(scope.row) }} {{ scope.row.unitName }}</strong></template></el-table-column>
              <el-table-column label="差异原因" min-width="210"><template #default="scope"><el-input v-if="!countReadOnly" v-model="scope.row.reason" maxlength="255" :placeholder="countDifference(scope.row) ? '存在差异，必填' : '无差异可留空'" :aria-label="`差异原因-${scope.row.itemCode}-${scope.row.lotNo || '无批号'}`" /><span v-else>{{ scope.row.reason || "-" }}</span></template></el-table-column>
            </el-table>
          </div>
        </template>
        <el-alert v-else title="生成盘点单后，系统会按当前仓库的物料批次记录账面数量。盘点期间请暂停该仓库出入库。" type="info" :closable="false" show-icon />
      </el-form>
      <template #footer>
        <el-button @click="countDialogVisible = false">{{ countForm.id ? "关闭" : "取消" }}</el-button>
        <template v-if="!countForm.id"><el-button type="primary" :loading="countSaving" @click="generateInventoryCount">生成盘点单</el-button></template>
        <template v-else-if="!countReadOnly"><el-button :loading="countSaving" @click="saveCountDraft()">保存草稿</el-button><el-button type="primary" :loading="countSaving" @click="postCountDraft">确认过账</el-button></template>
      </template>
    </el-dialog>

    <el-dialog v-model="transferDialogVisible" title="新建库存调拨" width="min(92vw, 650px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveTransfer">
        <div class="farm-form-grid">
          <el-form-item label="调拨单号" required><el-input v-model="transferForm.documentNo" maxlength="40" aria-label="调拨单号" /></el-form-item>
          <el-form-item label="调拨日期" required><el-date-picker v-model="transferForm.transferDate" class="full-width-control" type="date" value-format="YYYY-MM-DD" aria-label="调拨日期" /></el-form-item>
          <el-form-item label="调出仓库" required><el-select v-model="transferForm.fromWarehouseId" class="full-width-control" aria-label="调出仓库"><el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" :disabled="warehouse.id === transferForm.toWarehouseId" /></el-select></el-form-item>
          <el-form-item label="调入仓库" required><el-select v-model="transferForm.toWarehouseId" class="full-width-control" aria-label="调入仓库"><el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" :disabled="warehouse.id === transferForm.fromWarehouseId" /></el-select></el-form-item>
          <el-form-item class="farm-form-span" label="调拨物料" required><el-select v-model="transferForm.itemId" class="full-width-control" filterable aria-label="调拨物料" @change="transferForm.lotNo = ''"><el-option v-for="item in items" :key="item.id" :label="`${item.name} (${item.code})`" :value="item.id" /></el-select></el-form-item>
          <el-form-item :label="`调拨数量${selectedTransferItem ? `（${selectedTransferItem.unitName}）` : ''}`" required><el-input-number v-model="transferForm.quantity" class="full-width-control" :min="0.001" :precision="3" controls-position="right" aria-label="调拨数量" /></el-form-item>
          <el-form-item :label="selectedTransferItem?.lotTracking ? '物料批号（必填）' : '物料批号'"><el-input v-model="transferForm.lotNo" maxlength="64" aria-label="调拨批号" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="transferDialogVisible = false">取消</el-button><el-button type="primary" :loading="transferSaving" @click="saveTransfer">确认调拨</el-button></template>
    </el-dialog>

    <el-dialog v-model="productionDialogVisible" title="生产领退料" width="min(92vw, 680px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveProductionOperation">
        <div class="farm-form-grid">
          <el-form-item class="farm-form-span" label="业务类型" required>
            <el-segmented v-model="productionForm.operationType" :options="productionOperationOptions" class="full-width-control" aria-label="业务类型" @change="updateProductionOperationType" />
          </el-form-item>
          <el-form-item label="领退料单号" required><el-input v-model="productionForm.documentNo" maxlength="40" aria-label="领退料单号" /></el-form-item>
          <el-form-item label="业务日期" required><el-date-picker v-model="productionForm.operationDate" class="full-width-control" type="date" value-format="YYYY-MM-DD" aria-label="业务日期" /></el-form-item>
          <el-form-item label="领退仓库" required><el-select v-model="productionForm.warehouseId" class="full-width-control" filterable aria-label="领退仓库"><el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" /></el-select></el-form-item>
          <el-form-item label="生产物料" required><el-select v-model="productionForm.itemId" class="full-width-control" filterable aria-label="生产物料" @change="productionForm.lotNo = ''"><el-option v-for="item in items" :key="item.id" :label="`${item.name} (${item.code})`" :value="item.id" /></el-select></el-form-item>
          <el-form-item :label="`领退数量${selectedProductionItem ? `（${selectedProductionItem.unitName}）` : ''}`" required><el-input-number v-model="productionForm.quantity" class="full-width-control" :min="0.001" :precision="3" controls-position="right" aria-label="领退数量" /></el-form-item>
          <el-form-item :label="selectedProductionItem?.lotTracking ? '物料批号（必填）' : '物料批号'"><el-input v-model="productionForm.lotNo" maxlength="64" aria-label="领退批号" /></el-form-item>
          <el-form-item class="farm-form-span" label="使用对象类型" required>
            <el-segmented v-model="productionForm.costObjectType" :options="productionCostObjectOptions" class="full-width-control" aria-label="使用对象类型" @change="selectDefaultProductionCostObject" />
          </el-form-item>
          <el-form-item class="farm-form-span" label="使用对象" required>
            <el-input v-if="productionForm.costObjectType === 'farm'" :model-value="`${farmContext.currentFarm?.name ?? '当前农场'}（通用）`" disabled aria-label="使用对象" />
            <el-select v-else v-model="productionForm.costObjectId" class="full-width-control" filterable :placeholder="`请选择${productionForm.costObjectType === 'barn' ? '圈舍' : productionForm.costObjectType === 'plot' ? '地块' : productionForm.costObjectType === 'crop_cycle' ? '种植周期' : '养殖批次'}`" aria-label="使用对象">
              <el-option v-for="item in selectableCostObjects" :key="item.id" :label="item.label" :value="item.id" />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="productionDialogVisible = false">取消</el-button><el-button type="primary" :loading="productionSaving" @click="saveProductionOperation">{{ productionActionLabel }}</el-button></template>
    </el-dialog>
  </section>
</template>
