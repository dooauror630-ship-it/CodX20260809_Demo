import axios, { AxiosError } from "axios";


interface ApiErrorBody {
  message?: string;
  code?: string;
  field?: string;
  requestId?: string;
}

export const apiClient = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
  withCredentials: true,
  headers: {
    Accept: "application/json",
  },
});

let csrfToken: string | null = null;

export function updateCsrfToken(value?: string) {
  if (value) csrfToken = value;
}

apiClient.interceptors.request.use(async (config) => {
  const method = config.method?.toUpperCase() ?? "GET";
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    if (!csrfToken) {
      const response = await apiClient.get<{ csrfToken: string }>("/auth/csrf");
      csrfToken = response.data.csrfToken;
    }
    config.headers.set("X-CSRF-Token", csrfToken);
  }
  return config;
});

apiClient.interceptors.response.use((response) => {
  updateCsrfToken(response.data?.csrfToken);
  return response;
});

export function errorMessage(error: unknown) {
  if (error instanceof AxiosError) {
    const data = error.response?.data as ApiErrorBody | undefined;
    return data?.message ?? (error.code === "ECONNABORTED" ? "请求超时，请稍后重试" : "无法连接服务器");
  }
  return error instanceof Error ? error.message : "请求失败";
}
