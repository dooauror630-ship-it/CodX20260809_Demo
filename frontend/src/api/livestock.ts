import { apiClient } from "./client";
import type {
  CreateLivestockBatchInput,
  CreateLivestockHealthRecordInput,
  CreateLivestockMovementInput,
  CreateLivestockWeightRecordInput,
  LivestockBatch,
  LivestockBatchListData,
  LivestockBatchListQuery,
  LivestockMovement,
  LivestockHealthRecord,
  LivestockWeightRecord,
} from "@/types/livestock";


interface DataResponse<T> {
  success: true;
  data: T;
  message?: string;
  requestId: string;
}

export async function getLivestockBatches(query: LivestockBatchListQuery) {
  return (
    await apiClient.get<DataResponse<LivestockBatchListData>>("/livestock-batches", { params: query })
  ).data.data;
}

export async function getLivestockBatch(batchId: number) {
  return (
    await apiClient.get<DataResponse<{ batch: LivestockBatch }>>(`/livestock-batches/${batchId}`)
  ).data.data.batch;
}

export async function createLivestockBatch(input: CreateLivestockBatchInput) {
  return (
    await apiClient.post<DataResponse<{ batch: LivestockBatch }>>("/livestock-batches", input)
  ).data.data.batch;
}

export async function createLivestockMovement(input: CreateLivestockMovementInput) {
  return (
    await apiClient.post<DataResponse<{ movement: LivestockMovement; batch: LivestockBatch }>>(
      "/livestock-movements",
      input,
    )
  ).data.data;
}

export async function createLivestockHealthRecord(input: CreateLivestockHealthRecordInput) {
  return (
    await apiClient.post<DataResponse<{ record: LivestockHealthRecord }>>("/livestock-health-records", input)
  ).data.data.record;
}

export async function createLivestockWeightRecord(input: CreateLivestockWeightRecordInput) {
  return (
    await apiClient.post<DataResponse<{ record: LivestockWeightRecord }>>("/livestock-weight-records", input)
  ).data.data.record;
}
