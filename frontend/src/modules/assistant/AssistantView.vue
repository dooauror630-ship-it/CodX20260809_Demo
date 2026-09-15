<script setup lang="ts">
import { ChatDotRound, Connection, Delete, Promotion, Refresh } from "@element-plus/icons-vue";
import { onMounted, ref, nextTick, computed } from "vue";

import { createAssistantToken, getGatewaySession, openGatewaySession, sendAssistantMessageStream } from "@/api/assistant";
import { errorMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useAssistantTaskStore } from "@/stores/assistantTask";
import { buildBusinessReport, renderBusinessMessage } from "./messageFormat";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
}

const auth = useAuthStore();
const task = useAssistantTaskStore();
const messageStorageKey = `agri-assistant-messages-v1-${auth.user?.id ?? "current"}`;
const sessionStorageKey = `agri-assistant-session-v1-${auth.user?.id ?? "current"}`;
const retentionMs = 30 * 24 * 60 * 60 * 1000;
const behaviorStorageKey = `agri-assistant-behavior-v1-${auth.user?.id ?? "current"}`;

const messages = ref<ChatMessage[]>([]);
const input = ref("");
const loading = ref(false);
const starting = ref(true);
const statusText = ref("连接中");
const errorText = ref("");
const sessionId = ref("");
const sessionToken = ref("");
const tokenExpiresAt = ref(0);
const messageList = ref<HTMLElement>();
const behavior = ref<string[]>([]);
let messageSerial = 0;

function persistMessages() {
  localStorage.setItem(messageStorageKey, JSON.stringify({
    savedAt: Date.now(),
    messages: messages.value,
  }));
  window.dispatchEvent(new Event("agri-assistant-sync"));
}

function restoreMessages() {
  try {
    const saved = JSON.parse(localStorage.getItem(messageStorageKey) ?? "null") as { savedAt?: number; messages?: ChatMessage[] } | null;
    if (saved?.savedAt && Date.now() - saved.savedAt < retentionMs && Array.isArray(saved.messages)) {
      messages.value = saved.messages
        .filter((item) => item && (item.role === "user" || item.role === "assistant") && typeof item.content === "string")
        .map((item) => ({ ...item, createdAt: item.createdAt ?? new Date(saved.savedAt ?? Date.now()).toISOString() }));
      messageSerial = messages.value.reduce((max, item) => Math.max(max, item.id), 0);
    }
  } catch {
    localStorage.removeItem(messageStorageKey);
  }
}

function restoreBehavior() {
  try { behavior.value = JSON.parse(localStorage.getItem(behaviorStorageKey) ?? "[]") as string[]; } catch { behavior.value = []; }
}

const recommendations = computed(() => {
  if (behavior.value.includes("purchase")) return ["查询当前农场可用的采购基础选项", "查询最近采购记录", "查询当前农场库存概览"];
  if (behavior.value.includes("inventory")) return ["查询当前农场库存概览", "查询低库存物料", "创建一个采购草稿"];
  return ["查询当前农场库存概览", "查询当前农场养殖概览", "查询当前农场可用的采购基础选项"];
});


function actionInfo(content: string) {
  const token = content.match(/"?confirmationToken"?\s*[:：]\s*["“`]([^"”`]+)["”`]/)?.[1];
  if (!token) return null;
  const operation = content.includes("采购") ? "采购入库" : content.includes("盘点") ? "库存盘点" : "仓库调拨";
  return { token, operation };
}

function downloadReport(content: string, format: "doc" | "csv") {
  const title = `农牧业智能体业务报告-${new Date().toISOString().slice(0, 10)}`;
  const body = format === "doc" ? buildBusinessReport(content) : `内容\n"${content.replaceAll('"', '""')}"`;
  const blob = new Blob(["\ufeff", body], { type: format === "doc" ? "application/msword" : "text/csv;charset=utf-8" });
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${title}.${format}`; link.click(); URL.revokeObjectURL(link.href);
}

function printReport(content: string) {
  const popup = window.open("", "_blank", "width=900,height=700");
  if (!popup) return;
  popup.document.write(buildBusinessReport(content));
  popup.document.close(); popup.focus(); popup.print();
}

function addMessage(role: ChatMessage["role"], content: string) {
  messages.value.push({ id: ++messageSerial, role, content, createdAt: new Date().toISOString() });
  persistMessages();
  void nextTick(() => messageList.value?.scrollTo({ top: messageList.value.scrollHeight, behavior: "smooth" }));
}

function addWelcomeMessage(displayName = "用户") {
  if (messages.value.length) return;
  addMessage("assistant", `${displayName}你好，我是农牧业业务助手。当前智能体会话已建立，我可以帮你查询库存、养殖数据，并创建采购、盘点和仓库调拨草稿。涉及正式过账时，我会先展示草稿，等你明确确认。`);
}

async function startSession() {
  starting.value = true;
  errorText.value = "";
  const savedSession = JSON.parse(sessionStorage.getItem(sessionStorageKey) ?? "null") as { sessionId?: string; token?: string; expiresAt?: number } | null;
  if (savedSession?.sessionId && savedSession.token && savedSession.expiresAt && Date.now() < savedSession.expiresAt - 30_000) {
    try {
      const gateway = await getGatewaySession(savedSession.sessionId, savedSession.token);
      sessionToken.value = savedSession.token;
      sessionId.value = gateway.sessionId;
      tokenExpiresAt.value = savedSession.expiresAt;
      statusText.value = "已连接";
      addWelcomeMessage(String(gateway.context.user?.displayName ?? "用户"));
      starting.value = false;
      return;
    } catch { sessionStorage.removeItem(sessionStorageKey); }
  }
  sessionId.value = "";
  sessionToken.value = "";
  try {
    const token = await createAssistantToken();
    const gateway = await openGatewaySession(token.token);
    sessionToken.value = token.token;
    sessionId.value = gateway.sessionId;
    tokenExpiresAt.value = Date.now() + token.expiresIn * 1000;
    sessionStorage.setItem(sessionStorageKey, JSON.stringify({ sessionId: sessionId.value, token: sessionToken.value, expiresAt: tokenExpiresAt.value }));
    statusText.value = "已连接";
    addWelcomeMessage(String(gateway.context.user?.displayName ?? "用户"));
  } catch (error) {
    statusText.value = "未连接";
    errorText.value = errorMessage(error);
  } finally {
    starting.value = false;
  }
}

async function ensureSession() {
  if (!sessionId.value || Date.now() > tokenExpiresAt.value - 30_000) await startSession();
  if (!sessionId.value || !sessionToken.value) throw new Error(errorText.value || "智能体会话未建立");
}

async function send(retry = true) {
  const content = input.value.trim();
  if (!content || loading.value) return;
  input.value = "";
  addMessage("user", content);
  const category = content.includes("采购") ? "purchase" : content.includes("库存") ? "inventory" : "other";
  if (category !== "other") { behavior.value = [category, ...behavior.value.filter((item) => item !== category)].slice(0, 3); localStorage.setItem(behaviorStorageKey, JSON.stringify(behavior.value)); }
  loading.value = true;
  task.start(content);
  const assistantId = ++messageSerial;
  messages.value.push({ id: assistantId, role: "assistant", content: "", createdAt: new Date().toISOString() });
  persistMessages();
  try {
    await ensureSession();
    await sendAssistantMessageStream(sessionId.value, sessionToken.value, content, (event) => {
      const message = messages.value.find((item) => item.id === assistantId);
      if (!message) return;
      if (event.event === "chunk" && event.data.text) message.content += event.data.text;
      if (event.event === "progress") task.update(event.data.type === "tool/call" ? "正在调用业务工具" : "正在整理结果");
      if (event.event === "done" && event.data.response) message.content = event.data.response;
      if (event.event === "error") message.content = "请求未完成：" + (event.data.message ?? "智能体运行失败");
      persistMessages();
      void nextTick(() => messageList.value?.scrollTo({ top: messageList.value.scrollHeight, behavior: "smooth" }));
    });
    const message = messages.value.find((item) => item.id === assistantId);
    if (message && !message.content) message.content = "暂时没有可展示的结果。";
    persistMessages();
    task.finish();
  } catch (error) {
    const messageText = errorMessage(error);
    if (retry && /AGENT_SESSION_REVOKED|会话已失效|SESSION_NOT_FOUND/iu.test(messageText)) {
      messages.value = messages.value.filter((item) => item.id !== assistantId);
      sessionStorage.removeItem(sessionStorageKey);
      sessionId.value = "";
      sessionToken.value = "";
      loading.value = false;
      await startSession();
      input.value = content;
      void send(false);
      return;
    }
    const message = messages.value.find((item) => item.id === assistantId);
    if (message) message.content = "请求未完成：" + messageText;
    persistMessages();
    statusText.value = "需要重连";
    task.finish("任务失败");
  } finally {
    loading.value = false;
  }
}

async function resetConversation() {
  messages.value = [];
  localStorage.removeItem(messageStorageKey);
  await startSession();
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void send();
  }
}

function clearMessages() {
  messages.value = [];
  localStorage.removeItem(messageStorageKey);
}

function formatChatTime(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date).replace("/", "-");
}

onMounted(() => {
  restoreMessages();
  restoreBehavior();
  window.addEventListener("agri-assistant-sync", restoreMessages);
  void startSession();
});
</script>

<template>
  <section class="assistant-page">
    <header class="page-header assistant-page-header">
      <div>
        <p class="eyebrow">INTERNAL AGENT</p>
        <h1>智能体工作台</h1>
      </div>
      <div class="assistant-actions">
        <span class="assistant-status" :class="{ 'is-offline': statusText !== '已连接' }">
          <span class="status-dot" aria-hidden="true" />{{ statusText }}
        </span>
        <el-button :icon="Refresh" :loading="starting" :disabled="starting" @click="resetConversation">新会话</el-button>
      </div>
    </header>

    <section class="assistant-panel" aria-label="智能体对话">
      <div ref="messageList" class="assistant-messages">
        <div v-if="!messages.length && !starting" class="assistant-empty">
          <el-icon><ChatDotRound /></el-icon>
          <strong>管理员你好，我是农牧业业务助手</strong>
          <span>我可以帮你查询库存、养殖数据，或创建采购、盘点和仓库调拨草稿。</span>
          <div class="assistant-recommendations">
            <el-button v-for="item in recommendations" :key="item" size="small" @click="input = item">{{ item }}</el-button>
          </div>
        </div>
        <div v-if="messages.length && !loading" class="assistant-recommendations assistant-recommendations-fixed">
          <el-button v-for="item in recommendations" :key="item" size="small" @click="input = item">{{ item }}</el-button>
        </div>
        <div v-for="message in messages" :key="message.id" :class="['assistant-message', 'is-' + message.role]">
          <div class="assistant-avatar" aria-hidden="true">
            <el-icon><component :is="message.role === 'user' ? Connection : ChatDotRound" /></el-icon>
          </div>
          <div class="assistant-message-body">
            <div v-if="message.role === 'assistant'" class="assistant-message-content" v-html="renderBusinessMessage(message.content)" />
            <div v-else class="assistant-message-content assistant-user-text">{{ message.content }}</div>
            <time class="assistant-message-time" :datetime="message.createdAt">{{ formatChatTime(message.createdAt) }}</time>
            <div v-if="message.role === 'assistant' && message.content" class="assistant-message-tools">
              <template v-if="actionInfo(message.content)">
                <el-tag type="warning" size="small">{{ actionInfo(message.content)?.operation }}草稿待确认</el-tag>
                <el-button size="small" type="primary" @click="input = `确认${actionInfo(message.content)?.operation}，确认令牌：${actionInfo(message.content)?.token}`">确认过账</el-button>
              </template>
              <el-button size="small" text @click="downloadReport(message.content, 'doc')">下载 Word</el-button>
              <el-button size="small" text @click="printReport(message.content)">打印/PDF</el-button>
            </div>
          </div>
        </div>
      </div>

      <el-alert v-if="errorText" :title="errorText" type="warning" show-icon :closable="false" />
      <div class="assistant-composer">
        <el-input
          v-model="input"
          :disabled="starting || loading"
          :rows="3"
          type="textarea"
          maxlength="4000"
          show-word-limit
          placeholder="输入业务问题"
          @keydown="handleKeydown"
        />
        <div class="assistant-composer-footer">
          <el-button text :icon="Delete" :disabled="!messages.length" @click="clearMessages">清空记录</el-button>
          <el-button type="primary" :icon="Promotion" :loading="loading" :disabled="!input.trim()" @click="send">发送</el-button>
        </div>
      </div>
    </section>
  </section>
</template>
