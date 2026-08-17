import { apiClient } from "./client";
import type {
  CreateLivestockBatchInput,
  CreateLivestockMovementInput,
  LivestockBatch,
  LivestockBatchListData,
  LivestockBatchListQuery,
  LivestockMovement,
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
