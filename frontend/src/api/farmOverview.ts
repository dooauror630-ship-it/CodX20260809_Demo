import { apiClient } from "./client";
export interface FarmOverview { farmId: number; inventory: { stockValue: string; activeItemCount: number }; livestock: { activeBatchCount: number }; crops: { openCycleCount: number }; trade: { postedSalesAmount: string; salesCost: string; grossProfit: string; receivedAmount: string; cashNetInflow: string; receivableAmount: string }; }
export async function getFarmOverview(farmId: number) { return (await apiClient.get<{ data: FarmOverview }>("/analytics/farm-overview", { params: { farmId } })).data.data; }
