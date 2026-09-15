import { apiClient } from "./client";

export interface AssistantContext {
  user: { id: number; displayName: string; username: string; role: string };
  tools: Array<{ name: string; label: string; mode: string; minRole: string; status: string }>;
  farms: Array<{ id: number; name: string; code: string; accessRole: string }>;
  writePolicy: { enabled: boolean; reason: string };
}

interface AssistantSessionResponse {
  token: string;
  expiresIn: number;
  context: AssistantContext;
}

interface GatewaySessionResponse {
  sessionId: string;
  context: AssistantContext;
  createdAt: number;
}

interface GatewayMessageResponse {
  sessionId: string;
  response: string;
}

export interface AssistantStreamEvent {
  event: "chunk" | "progress" | "done" | "error";
  data: { text?: string; response?: string; type?: string; message?: string; code?: string; [key: string]: unknown };
}

const gatewayBaseUrl = String(import.meta.env.VITE_AGENT_GATEWAY_URL ?? "/agent-gateway").replace(/\/$/u, "");

export async function createAssistantToken() {
  return (await apiClient.post<{ data: AssistantSessionResponse }>("/assistant/session")).data.data;
}

async function gatewayRequest<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12_000);
  let response: Response;
  try {
    response = await fetch(gatewayBaseUrl + path, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
        ...(init.headers ?? {}),
      },
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) throw new Error("智能体连接超时，请检查网关是否启动", { cause: error });
    throw error;
  }
  let rawBody: string;
  try {
    rawBody = await response.text();
  } catch (error) {
    if (controller.signal.aborted) throw new Error("智能体连接超时，请检查网关是否启动", { cause: error });
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
  let body: { success?: boolean; data?: T; message?: string; code?: string } = {};
  if (rawBody.trim()) {
    try {
      body = JSON.parse(rawBody) as typeof body;
    } catch {
      throw new Error(`智能体网关返回了无效响应（HTTP ${response.status}）`);
    }
  }
  if (!response.ok || body.success !== true || body.data === undefined) {
    throw new Error(body.message ?? `智能体网关暂不可用（HTTP ${response.status}）`);
  }
  return body.data;
}

export function openGatewaySession(token: string) {
  return gatewayRequest<GatewaySessionResponse>("/v1/sessions", token, { method: "POST" });
}

export function getGatewaySession(sessionId: string, token: string) {
  return gatewayRequest<GatewaySessionResponse>("/v1/sessions/" + encodeURIComponent(sessionId), token);
}

export function sendAssistantMessage(sessionId: string, token: string, message: string) {
  return gatewayRequest<GatewayMessageResponse>("/v1/sessions/" + encodeURIComponent(sessionId) + "/messages", token, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function sendAssistantMessageStream(
  sessionId: string,
  token: string,
  message: string,
  onEvent: (event: AssistantStreamEvent) => void,
) {
  const response = await fetch(gatewayBaseUrl + "/v1/sessions/" + encodeURIComponent(sessionId) + "/messages/stream", {
    method: "POST",
    credentials: "include",
    headers: { Accept: "text/event-stream", "Content-Type": "application/json", Authorization: "Bearer " + token },
    body: JSON.stringify({ message }),
  });
  if (!response.ok || !response.body) {
    let messageText = `智能体网关暂不可用（HTTP ${response.status}）`;
    try { messageText = ((await response.json()) as { message?: string }).message ?? messageText; } catch { /* empty */ }
    throw new Error(messageText);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const chunk = await reader.read();
    buffer += decoder.decode(chunk.value ?? new Uint8Array(), { stream: !chunk.done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = frame.match(/^event:\s*(\S+)/m)?.[1] as AssistantStreamEvent["event"] | undefined;
      const dataLine = frame.split("\n").find((line) => line.startsWith("data:"));
      if (!event || !dataLine) continue;
      onEvent({ event, data: JSON.parse(dataLine.slice(5).trim()) });
    }
    if (chunk.done) break;
  }
}

export function closeGatewaySession(sessionId: string, token: string) {
  return gatewayRequest<{ sessionId: string; closed: boolean }>("/v1/sessions/" + encodeURIComponent(sessionId), token, {
    method: "DELETE",
  });
}
