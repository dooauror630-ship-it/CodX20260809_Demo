import { apiClient } from "./client";
import type { DataResponse, SystemOverview } from "@/types/analytics";


export async function getSystemOverview() {
  return (await apiClient.get<DataResponse<SystemOverview>>("/analytics/overview")).data.data;
}
