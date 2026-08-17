import { apiClient } from "./client";
import type {
  CatalogData,
  CreateCropVarietyInput,
  CropVariety,
  UpdateCropVarietyInput,
} from "@/types/catalog";


interface DataResponse<T> {
  success: true;
  data: T;
  message?: string;
  requestId: string;
}

export async function getCatalogs() {
  return (await apiClient.get<DataResponse<CatalogData>>("/catalogs")).data.data;
}

export async function createCropVariety(input: CreateCropVarietyInput) {
  return (
    await apiClient.post<DataResponse<{ variety: CropVariety }>>("/crop-varieties", input)
  ).data.data.variety;
}

export async function updateCropVariety(varietyId: number, input: UpdateCropVarietyInput) {
  return (
    await apiClient.patch<DataResponse<{ variety: CropVariety }>>(`/crop-varieties/${varietyId}`, input)
  ).data.data.variety;
}
