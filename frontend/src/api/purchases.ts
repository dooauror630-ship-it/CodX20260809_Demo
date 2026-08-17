import { apiClient } from "./client";
import type { ResourceListData, ResourceListQuery } from "@/types/inventory";
import type {
  CreateInventoryCountInput,
  CreateProductionStockOperationInput,
  CreatePurchaseReturnInput,
  CreateStockTransferInput,
  CreatePurchaseInput,
  CreateSupplierInput,
  InventoryCount,
  InventoryCountListQuery,
  InventoryAnalysis,
  InventoryAnalysisQuery,
  PurchaseListQuery,
  PurchaseOrder,
  PurchaseReturn,
  StockBalance,
  StockLedgerEntry,
  StockSummary,
  StockTransfer,
  ProductionStockOperation,
  Supplier,
  SupplierListQuery,
  UpdatePurchaseInput,
  UpdateInventoryCountInput,
  UpdateSupplierInput,
} from "@/types/purchase";


interface DataResponse<T> {
  success: true;
  data: T;
  message?: string;
  requestId: string;
}

export async function getSuppliers(query: SupplierListQuery) {
  return (
    await apiClient.get<DataResponse<ResourceListData<Supplier>>>("/suppliers", { params: query })
  ).data.data;
}

export async function createSupplier(input: CreateSupplierInput) {
  return (
    await apiClient.post<DataResponse<{ supplier: Supplier }>>("/suppliers", input)
  ).data.data.supplier;
}

export async function updateSupplier(supplierId: number, input: UpdateSupplierInput) {
  return (
    await apiClient.patch<DataResponse<{ supplier: Supplier }>>(`/suppliers/${supplierId}`, input)
  ).data.data.supplier;
}

export async function getPurchases(query: PurchaseListQuery) {
  return (
    await apiClient.get<DataResponse<ResourceListData<PurchaseOrder>>>("/purchases", { params: query })
  ).data.data;
}

export async function getPurchase(purchaseId: number) {
  return (
    await apiClient.get<DataResponse<{ purchase: PurchaseOrder }>>(`/purchases/${purchaseId}`)
  ).data.data.purchase;
}

export async function createPurchase(input: CreatePurchaseInput) {
  return (
    await apiClient.post<DataResponse<{ purchase: PurchaseOrder }>>("/purchases", input)
  ).data.data.purchase;
}

export async function updatePurchase(purchaseId: number, input: UpdatePurchaseInput) {
  return (
    await apiClient.patch<DataResponse<{ purchase: PurchaseOrder }>>(`/purchases/${purchaseId}`, input)
  ).data.data.purchase;
}

export async function postPurchase(purchaseId: number, version: number) {
  return (
    await apiClient.post<DataResponse<{ purchase: PurchaseOrder }>>(`/purchases/${purchaseId}/post`, { version })
  ).data.data.purchase;
}

export async function cancelPurchase(purchaseId: number, version: number) {
  return (
    await apiClient.post<DataResponse<{ purchase: PurchaseOrder }>>(`/purchases/${purchaseId}/cancel`, { version })
  ).data.data.purchase;
}

export async function createPurchaseReturn(input: CreatePurchaseReturnInput) {
  return (
    await apiClient.post<DataResponse<{ purchaseReturn: PurchaseReturn }>>("/purchase-returns", input)
  ).data.data.purchaseReturn;
}

export async function getStocks(query: ResourceListQuery & { warehouseId?: number; lowStock?: boolean }) {
  return (
    await apiClient.get<DataResponse<ResourceListData<StockBalance> & { summary: StockSummary }>>("/stocks", {
      params: query,
    })
  ).data.data;
}

export async function getStockLedger(query: ResourceListQuery & {
  warehouseId?: number;
  itemId?: number;
  dateFrom?: string;
  dateTo?: string;
}) {
  return (
    await apiClient.get<DataResponse<ResourceListData<StockLedgerEntry>>>("/stock-ledger", { params: query })
  ).data.data;
}

export async function createStockTransfer(input: CreateStockTransferInput) {
  return (
    await apiClient.post<DataResponse<{ transfer: StockTransfer }>>("/stock-transfers", input)
  ).data.data.transfer;
}

export async function createProductionStockOperation(input: CreateProductionStockOperationInput) {
  return (
    await apiClient.post<DataResponse<{ operation: ProductionStockOperation }>>(
      "/production-stock-operations",
      input,
    )
  ).data.data.operation;
}

export async function getInventoryCounts(query: InventoryCountListQuery) {
  return (
    await apiClient.get<DataResponse<ResourceListData<InventoryCount>>>("/inventory-counts", { params: query })
  ).data.data;
}

export async function getInventoryAnalysis(query: InventoryAnalysisQuery) {
  return (
    await apiClient.get<DataResponse<InventoryAnalysis>>("/inventory-analysis", { params: query })
  ).data.data;
}

export async function getInventoryCount(countId: number) {
  return (
    await apiClient.get<DataResponse<{ inventoryCount: InventoryCount }>>(`/inventory-counts/${countId}`)
  ).data.data.inventoryCount;
}

export async function createInventoryCount(input: CreateInventoryCountInput) {
  return (
    await apiClient.post<DataResponse<{ inventoryCount: InventoryCount }>>("/inventory-counts", input)
  ).data.data.inventoryCount;
}

export async function updateInventoryCount(countId: number, input: UpdateInventoryCountInput) {
  return (
    await apiClient.patch<DataResponse<{ inventoryCount: InventoryCount }>>(`/inventory-counts/${countId}`, input)
  ).data.data.inventoryCount;
}

export async function postInventoryCount(countId: number, version: number) {
  return (
    await apiClient.post<DataResponse<{ inventoryCount: InventoryCount }>>(`/inventory-counts/${countId}/post`, {
      version,
    })
  ).data.data.inventoryCount;
}

export async function cancelInventoryCount(countId: number, version: number) {
  return (
    await apiClient.post<DataResponse<{ inventoryCount: InventoryCount }>>(`/inventory-counts/${countId}/cancel`, {
      version,
    })
  ).data.data.inventoryCount;
}
