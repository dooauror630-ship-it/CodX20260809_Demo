import { apiClient } from "./client";
import type { AuthResponse, LoginInput, RegisterInput } from "@/types/auth";


export async function restoreSession() {
  return (await apiClient.get<AuthResponse>("/auth/me")).data;
}

export async function login(input: LoginInput) {
  return (await apiClient.post<AuthResponse>("/auth/login", input)).data;
}

export async function register(input: RegisterInput) {
  return (await apiClient.post<AuthResponse>("/auth/register", input)).data;
}

export async function logout() {
  return (await apiClient.post<AuthResponse>("/auth/logout")).data;
}
