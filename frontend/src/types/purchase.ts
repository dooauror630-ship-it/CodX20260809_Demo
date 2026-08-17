export interface Supplier {
  id: number;
  farmId: number;
  code: string;
  name: string;
  contact: string | null;
  phone: string | null;
  address: string | null;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export type PurchaseStatus = "DRAFT" | "POSTED" | "CANCELLED";

export interface PurchaseLine {
  id: number;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  quantity: string;
  unitPrice: string;
  amount: string;
  lotNo: string | null;
  expiresOn: string | null;
  returnedQuantity: string;
  returnableQuantity: string;
}

export interface PurchaseOrder {
  id: number;
  farmId: number;
  orderNo: string;
  supplierId: number;
  supplierName: string;
  warehouseId: number;
  warehouseName: string;
  orderDate: string;
  status: PurchaseStatus;
  totalAmount: string;
  notes: string | null;
  lineCount: number;
  version: number;
  postedAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  lines?: PurchaseLine[];
}

export interface PurchaseLineInput {
  itemId: number;
  quantity: number;
  unitPrice: number;
  lotNo?: string | null;
  expiresOn?: string | null;
}

export interface CreatePurchaseInput {
  farmId: number;
  orderNo: string;
  supplierId: number;
  warehouseId: number;
  orderDate: string;
  notes?: string | null;
  lines: PurchaseLineInput[];
}

export interface UpdatePurchaseInput extends CreatePurchaseInput {
  version: number;
}

export interface CreatePurchaseReturnInput {
  farmId: number;
  documentNo: string;
  purchaseId: number;
  purchaseLineId: number;
  returnDate: string;
  warehouseId: number;
  quantity: number;
}

export interface PurchaseReturn {
  id: number;
  farmId: number;
  documentNo: string;
  documentType: "PURCHASE_RETURN";
  purchaseId: number;
  purchaseOrderNo: string;
  purchaseLineId: number;
  supplierId: number;
  supplierName: string;
  returnDate: string;
  warehouseId: number;
  warehouseName: string;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  quantity: string;
  inventoryUnitCost: string;
  inventoryAmount: string;
  refundUnitPrice: string;
  refundAmount: string;
  lotNo: string | null;
  expiresOn: string | null;
  createdAt: string | null;
}

export interface PurchaseListQuery {
  farmId: number;
  page: number;
  pageSize: number;
  keyword?: string;
  status?: "all" | PurchaseStatus;
  dateFrom?: string;
  dateTo?: string;
}

export interface CreateSupplierInput {
  farmId: number;
  code: string;
  name: string;
  contact?: string | null;
  phone?: string | null;
  address?: string | null;
}

export interface UpdateSupplierInput {
  code?: string;
  name?: string;
  contact?: string | null;
  phone?: string | null;
  address?: string | null;
  isActive?: boolean;
}

export interface SupplierListQuery {
  farmId: number;
  page: number;
  pageSize: number;
  keyword?: string;
  status?: "all" | "active" | "disabled";
}

export interface StockBalance {
  id: number;
  farmId: number;
  warehouseId: number;
  warehouseName: string;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  quantity: string;
  averageCost: string;
  inventoryValue: string;
  safetyStock: string;
  lowStock: boolean;
  updatedAt: string | null;
}

export interface StockSummary {
  itemCount: number;
  totalValue: string;
  lowStockCount: number;
}

export interface StockLedgerEntry {
  id: number;
  documentNo: string;
  documentType: string;
  sourceType: string;
  sourceId: number | null;
  occurredAt: string | null;
  warehouseId: number;
  warehouseName: string;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  quantityDelta: string;
  unitCost: string;
  amount: string;
  lotNo: string | null;
  expiresOn: string | null;
  costObjectType: "FARM" | "BARN" | "PLOT" | null;
  costObjectId: number | null;
}

export interface CreateStockTransferInput {
  farmId: number;
  documentNo: string;
  fromWarehouseId: number;
  toWarehouseId: number;
  transferDate: string;
  itemId: number;
  quantity: number;
  lotNo?: string | null;
}

export interface StockTransfer {
  id: number;
  farmId: number;
  documentNo: string;
  documentType: "WAREHOUSE_TRANSFER";
  fromWarehouseId: number;
  fromWarehouseName: string;
  toWarehouseId: number;
  toWarehouseName: string;
  transferDate: string;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  quantity: string;
  unitCost: string;
  amount: string;
  lotNo: string | null;
  expiresOn: string | null;
  createdAt: string | null;
}

export type ProductionStockOperationType = "issue" | "return";
export type ProductionCostObjectType = "farm" | "barn" | "plot";

export interface CreateProductionStockOperationInput {
  farmId: number;
  documentNo: string;
  operationType: ProductionStockOperationType;
  operationDate: string;
  warehouseId: number;
  itemId: number;
  quantity: number;
  lotNo?: string | null;
  costObjectType: ProductionCostObjectType;
  costObjectId?: number | null;
}

export interface ProductionStockOperation {
  id: number;
  farmId: number;
  documentNo: string;
  documentType: "PRODUCTION_ISSUE" | "PRODUCTION_RETURN";
  operationType: ProductionStockOperationType;
  operationDate: string;
  warehouseId: number;
  warehouseName: string;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  quantity: string;
  unitCost: string;
  amount: string;
  lotNo: string | null;
  expiresOn: string | null;
  costObjectType: ProductionCostObjectType;
  costObjectId: number;
  createdAt: string | null;
}

export type InventoryCountStatus = "DRAFT" | "POSTED" | "CANCELLED";

export interface InventoryCountLine {
  id: number;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  lotNo: string | null;
  expiresOn: string | null;
  bookQuantity: string;
  actualQuantity: string;
  differenceQuantity: string;
  unitCost: string;
  differenceAmount: string;
  reason: string | null;
}

export interface InventoryCount {
  id: number;
  farmId: number;
  countNo: string;
  warehouseId: number;
  warehouseName: string;
  countDate: string;
  status: InventoryCountStatus;
  notes: string | null;
  version: number;
  lineCount: number;
  differenceLineCount: number;
  adjustmentDocumentNo: string | null;
  postedAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  lines?: InventoryCountLine[];
}

export interface InventoryCountListQuery {
  farmId: number;
  page: number;
  pageSize: number;
  keyword?: string;
  status?: "all" | InventoryCountStatus;
  dateFrom?: string;
  dateTo?: string;
}

export interface CreateInventoryCountInput {
  farmId: number;
  countNo: string;
  warehouseId: number;
  countDate: string;
  notes?: string | null;
}

export interface UpdateInventoryCountInput {
  version: number;
  notes?: string | null;
  lines: Array<{
    id: number;
    actualQuantity: number;
    reason?: string | null;
  }>;
}

export type InventoryExpiryStatus = "EXPIRED" | "EXPIRING";

export interface InventoryExpiryLot {
  warehouseId: number;
  warehouseName: string;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  lotNo: string | null;
  expiresOn: string;
  quantity: string;
  daysRemaining: number;
  status: InventoryExpiryStatus;
}

export interface InventoryTrendPoint {
  date: string;
  inboundAmount: string;
  outboundAmount: string;
}

export interface InventoryConsumedItem {
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  netQuantity: string;
  netAmount: string;
}

export interface InventoryAnalysis {
  summary: {
    warningLotCount: number;
    expiredLotCount: number;
    expiringLotCount: number;
    periodInboundAmount: string;
    periodOutboundAmount: string;
  };
  expiryLots: InventoryExpiryLot[];
  trend: InventoryTrendPoint[];
  topConsumedItems: InventoryConsumedItem[];
  period: {
    dateFrom: string;
    dateTo: string;
    trendDays: number;
    expiryDays: number;
  };
  generatedAt: string;
}

export interface InventoryAnalysisQuery {
  farmId: number;
  warehouseId?: number;
  expiryDays?: number;
  trendDays?: number;
}
