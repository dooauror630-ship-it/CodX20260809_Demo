import { apiClient } from "./client";
import type {
  AvailableFieldOperationInput,
  CropCycle,
  CropCycleAnalysis,
  CropCycleCostSummary,
  CropCycleListData,
  CropCycleListQuery,
  CreateCropCycleInput,
  CropCycleStatus,
  FieldOperation,
  FieldOperationInput,
  FieldOperationType,
  HarvestBatch,
  GradingRecord,
  GradingRecordData,
  TobaccoCuringBatch,
} from "@/types/crop";

interface DataResponse<T> {
  success: true;
  data: T;
  message?: string;
  requestId: string;
}

export async function getHarvestBatches(query: { farmId: number; cropCycleId: number }) {
  return (await apiClient.get<DataResponse<{ items: HarvestBatch[]; total: number }>>("/harvest-batches", { params: query })).data.data;
}

export async function createHarvestBatch(input: {
  farmId: number; cropCycleId: number; harvestNo: string; harvestDate: string;
  grossWeight: number; netWeight: number; unitId: number; warehouseId: number; notes?: string | null;
}) {
  return (await apiClient.post<DataResponse<{ batch: HarvestBatch }>>("/harvest-batches", input)).data.data.batch;
}

export async function getTobaccoCuringBatches(query: { farmId: number; cropCycleId: number }) {
  return (await apiClient.get<DataResponse<{ items: TobaccoCuringBatch[]; total: number }>>("/tobacco-curing-batches", { params: query })).data.data;
}

export async function createTobaccoCuringBatch(input: {
  farmId: number; cropCycleId: number; curingNo: string; startAt: string;
  inputWeight: number; unitId: number; notes?: string | null;
}) {
  return (await apiClient.post<DataResponse<{ batch: TobaccoCuringBatch }>>("/tobacco-curing-batches", input)).data.data.batch;
}

export async function completeTobaccoCuringBatch(batchId: number, input: {
  endAt: string; outputWeight: number; fuelCost: number; electricityCost: number;
}) {
  return (await apiClient.patch<DataResponse<{ batch: TobaccoCuringBatch }>>(`/tobacco-curing-batches/${batchId}/complete`, input)).data.data.batch;
}

export async function getGradingRecords(query: { farmId: number; harvestBatchId: number }) {
  return (await apiClient.get<DataResponse<GradingRecordData>>("/grading-records", { params: query })).data.data;
}

export async function createGradingRecord(input: {
  farmId: number; harvestBatchId: number; gradeCode: string; quantity: number;
  unitPriceReference: number; notes?: string | null;
}) {
  return (await apiClient.post<DataResponse<{ record: GradingRecord }>>("/grading-records", input)).data.data.record;
}

export async function getCropCycles(query: CropCycleListQuery) {
  return (
    await apiClient.get<DataResponse<CropCycleListData>>("/crop-cycles", {
      params: query,
    })
  ).data.data;
}

export async function createCropCycle(input: CreateCropCycleInput) {
  return (
    await apiClient.post<DataResponse<{ cycle: CropCycle }>>(
      "/crop-cycles",
      input,
    )
  ).data.data.cycle;
}

export async function updateCropCycleStatus(
  cycleId: number,
  status: CropCycleStatus,
) {
  return (
    await apiClient.patch<DataResponse<{ cycle: CropCycle }>>(
      `/crop-cycles/${cycleId}/status`,
      { status },
    )
  ).data.data.cycle;
}

export async function getCropCycleCostSummary(cycleId: number) {
  return (
    await apiClient.get<DataResponse<CropCycleCostSummary>>(
      `/crop-cycles/${cycleId}/cost-summary`,
    )
  ).data.data;
}

export async function getCropCycleAnalysis(cycleId: number) {
  return (
    await apiClient.get<DataResponse<CropCycleAnalysis>>(
      `/crop-cycles/${cycleId}/analysis`,
    )
  ).data.data;
}

export async function getFieldOperations(query: {
  farmId: number;
  cropCycleId: number;
  page: number;
  pageSize: number;
}) {
  return (
    await apiClient.get<
      DataResponse<{
        items: FieldOperation[];
        pagination: CropCycleListData["pagination"];
      }>
    >("/field-operations", { params: query })
  ).data.data;
}

export async function createFieldOperation(input: {
  farmId: number;
  cropCycleId: number;
  operationType: FieldOperationType;
  operationDate: string;
  areaMu: number;
  laborHours?: number;
  machineHours?: number;
  laborCost?: number;
  serviceCost?: number;
  notes?: string | null;
}) {
  return (
    await apiClient.post<DataResponse<{ operation: FieldOperation }>>(
      "/field-operations",
      input,
    )
  ).data.data.operation;
}

export async function getFieldOperationInputs(query: {
  farmId: number;
  fieldOperationId: number;
}) {
  return (
    await apiClient.get<
      DataResponse<{ items: FieldOperationInput[]; total: number }>
    >("/field-operation-inputs", { params: query })
  ).data.data;
}

export async function getAvailableFieldOperationInputs(query: {
  farmId: number;
  fieldOperationId: number;
}) {
  return (
    await apiClient.get<
      DataResponse<{ items: AvailableFieldOperationInput[]; total: number }>
    >("/field-operation-inputs/available", { params: query })
  ).data.data;
}

export async function createFieldOperationInput(input: {
  farmId: number;
  fieldOperationId: number;
  stockDocumentId: number;
}) {
  return (
    await apiClient.post<DataResponse<{ input: FieldOperationInput }>>(
      "/field-operation-inputs",
      input,
    )
  ).data.data.input;
}
