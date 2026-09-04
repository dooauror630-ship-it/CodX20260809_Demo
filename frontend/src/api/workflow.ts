import { apiClient } from "./client";

export interface FarmTask { id: number; farmId: number; taskNo: string; title: string; dueDate: string; status: "OPEN" | "DONE"; notes: string | null; createdAt: string | null; completedAt: string | null; }
export interface AuditLog { id: number; farmId: number | null; actorId: number; action: string; resourceType: string; resourceId: number | null; detail: string | null; createdAt: string | null; }
interface Response<T> { data: T; }
export async function getTasks(farmId: number, status = "all") { return (await apiClient.get<Response<{ items: FarmTask[] }>>("/tasks", { params: { farmId, status } })).data.data.items; }
export async function createTask(input: { farmId: number; taskNo: string; title: string; dueDate: string; notes?: string }) { return (await apiClient.post<Response<{ task: FarmTask }>>("/tasks", input)).data.data.task; }
export async function completeTask(taskId: number) { return (await apiClient.post<Response<{ task: FarmTask }>>(`/tasks/${taskId}/complete`)).data.data.task; }
export async function getAuditLogs(farmId: number) { return (await apiClient.get<Response<{ items: AuditLog[] }>>("/audit-logs", { params: { farmId } })).data.data.items; }
