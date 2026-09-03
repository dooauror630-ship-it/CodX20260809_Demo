import { apiClient } from "./client";
import type { Customer, SalesOrder, TradeSummary } from "@/types/trade";
interface Response<T> { success: true; data: T; requestId: string; }
export async function getCustomers(farmId: number) { return (await apiClient.get<Response<{ items: Customer[] }>>("/customers", { params: { farmId, page: 1, pageSize: 100 } })).data.data.items; }
export async function createCustomer(input: { farmId: number; code: string; name: string; contact?: string; phone?: string }) { return (await apiClient.post<Response<{ customer: Customer }>>("/customers", input)).data.data.customer; }
export async function getSalesOrders(farmId: number) { return (await apiClient.get<Response<{ items: SalesOrder[] }>>("/sales-orders", { params: { farmId, page: 1, pageSize: 100, status: "all" } })).data.data.items; }
export async function getTradeSummary(farmId: number) { return (await apiClient.get<Response<TradeSummary>>("/trade-summary", { params: { farmId } })).data.data; }
