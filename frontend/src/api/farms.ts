import { apiClient } from "./client";
import type {
  Barn,
  CreateBarnInput,
  CreateFarmInput,
  CreatePlotInput,
  Farm,
  FarmListData,
  FarmListQuery,
  FarmMember,
  FarmRole,
  FarmResourceListData,
  FarmResourceListQuery,
  Plot,
  UpdateBarnInput,
  UpdateFarmInput,
  UpdatePlotInput,
} from "@/types/farm";


interface DataResponse<T> {
  success: true;
  data: T;
  message?: string;
  requestId: string;
}

export async function getFarms(query: FarmListQuery) {
  return (await apiClient.get<DataResponse<FarmListData>>("/farms", { params: query })).data.data;
}

export async function createFarm(input: CreateFarmInput) {
  return (await apiClient.post<DataResponse<{ farm: Farm }>>("/farms", input)).data.data.farm;
}

export async function updateFarm(farmId: number, input: UpdateFarmInput) {
  return (await apiClient.patch<DataResponse<{ farm: Farm }>>(`/farms/${farmId}`, input)).data.data.farm;
}

export async function getFarmMembers(farmId: number) {
  return (await apiClient.get<DataResponse<{ items: FarmMember[] }>>(`/farms/${farmId}/members`)).data.data.items;
}

export async function addFarmMember(farmId: number, userId: number, roleCode: FarmRole) {
  const input = { userId, roleCode };
  return (await apiClient.post<DataResponse<{ member: FarmMember }>>(`/farms/${farmId}/members`, input)).data.data.member;
}

export async function updateFarmMember(
  farmId: number,
  userId: number,
  input: { roleCode?: FarmRole; isActive?: boolean },
) {
  return (
    await apiClient.patch<DataResponse<{ member: FarmMember }>>(`/farms/${farmId}/members/${userId}`, input)
  ).data.data.member;
}

export async function getBarns(query: FarmResourceListQuery) {
  return (await apiClient.get<DataResponse<FarmResourceListData<Barn>>>("/barns", { params: query })).data.data;
}

export async function createBarn(input: CreateBarnInput) {
  return (await apiClient.post<DataResponse<{ barn: Barn }>>("/barns", input)).data.data.barn;
}

export async function updateBarn(barnId: number, input: UpdateBarnInput) {
  return (await apiClient.patch<DataResponse<{ barn: Barn }>>(`/barns/${barnId}`, input)).data.data.barn;
}

export async function getPlots(query: FarmResourceListQuery) {
  return (await apiClient.get<DataResponse<FarmResourceListData<Plot>>>("/plots", { params: query })).data.data;
}

export async function createPlot(input: CreatePlotInput) {
  return (await apiClient.post<DataResponse<{ plot: Plot }>>("/plots", input)).data.data.plot;
}

export async function updatePlot(plotId: number, input: UpdatePlotInput) {
  return (await apiClient.patch<DataResponse<{ plot: Plot }>>(`/plots/${plotId}`, input)).data.data.plot;
}
