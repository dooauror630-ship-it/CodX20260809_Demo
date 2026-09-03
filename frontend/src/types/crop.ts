export type CropCycleStatus =
  "PLANNED" | "ACTIVE" | "HARVESTING" | "CLOSED" | "CANCELLED";

export interface CropCycle {
  id: number;
  farmId: number;
  cycleCode: string;
  plotId: number;
  plotName: string | null;
  cropTypeId: number;
  cropTypeName: string | null;
  varietyId: number;
  varietyName: string | null;
  areaMu: string;
  plannedStartDate: string;
  plannedEndDate: string;
  actualStartDate: string | null;
  actualEndDate: string | null;
  status: CropCycleStatus;
  notes: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface CropCycleListData {
  items: CropCycle[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

export interface CropCycleCostSummary {
  cropCycleId: number;
  materialCost: string;
  laborCost: string;
  serviceCost: string;
  curingCost: string;
  totalCost: string;
  costPerMu: string;
  inputDocumentCount: number;
  operationCount: number;
}

export interface CropCycleListQuery {
  farmId: number;
  page: number;
  pageSize: number;
  keyword?: string;
  status?: CropCycleStatus | "all";
}

export interface CreateCropCycleInput {
  farmId: number;
  cycleCode: string;
  plotId: number;
  cropTypeId: number;
  varietyId: number;
  areaMu: number;
  plannedStartDate: string;
  plannedEndDate: string;
  notes?: string | null;
}

export type FieldOperationType =
  | "LAND_PREPARATION"
  | "SOWING"
  | "TRANSPLANTING"
  | "IRRIGATION"
  | "FERTILIZATION"
  | "PEST_CONTROL"
  | "WEEDING"
  | "OTHER";

export interface FieldOperation {
  id: number;
  farmId: number;
  cropCycleId: number;
  operationType: FieldOperationType;
  operationDate: string;
  areaMu: string;
  laborHours: string;
  machineHours: string;
  laborCost: string;
  serviceCost: string;
  notes: string | null;
  createdAt: string | null;
}

export interface AvailableFieldOperationInput {
  stockDocumentId: number;
  documentNo: string;
  itemId: number;
  itemCode: string;
  itemName: string;
  unitName: string;
  quantity: string;
  amount: string;
  operationDate: string;
}

export interface FieldOperationInput extends AvailableFieldOperationInput {
  id: number;
  farmId: number;
  fieldOperationId: number;
  unitCost: string;
  createdAt: string | null;
}

export interface HarvestBatch {
  id: number;
  farmId: number;
  cropCycleId: number;
  harvestNo: string;
  harvestDate: string;
  grossWeight: string;
  netWeight: string;
  unitId: number;
  unitName: string;
  warehouseId: number;
  warehouseName: string;
  notes: string | null;
  createdAt: string | null;
}

export type TobaccoCuringStatus = "IN_PROGRESS" | "COMPLETED";

export interface TobaccoCuringBatch {
  id: number;
  farmId: number;
  cropCycleId: number;
  curingNo: string;
  startAt: string | null;
  endAt: string | null;
  inputWeight: string;
  outputWeight: string | null;
  unitId: number;
  unitName: string;
  fuelCost: string;
  electricityCost: string;
  status: TobaccoCuringStatus;
  curingEfficiency: string | null;
  notes: string | null;
  createdAt: string | null;
}
