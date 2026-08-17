import { apiClient } from "./client";
import type { User } from "@/types/auth";


interface DataResponse<T> {
  success: true;
  data: T;
  message?: string;
  requestId: string;
}

export interface UserListQuery {
  page: number;
  pageSize: number;
  keyword?: string;
  role?: "admin" | "operator";
  status?: "all" | "active" | "disabled";
}

export interface UserListData {
  items: User[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

export interface UpdateUserInput {
  displayName?: string;
  role?: "admin" | "operator";
  isActive?: boolean;
}

export async function getUsers(query: UserListQuery) {
  return (await apiClient.get<DataResponse<UserListData>>("/admin/users", { params: query })).data.data;
}

export async function updateUser(userId: number, input: UpdateUserInput) {
  return (await apiClient.patch<DataResponse<{ user: User }>>(`/admin/users/${userId}`, input)).data.data.user;
}

export async function resetUserPassword(userId: number, password: string) {
  return (await apiClient.post<DataResponse<{ user: User }>>(`/admin/users/${userId}/password`, { password })).data.data.user;
}
