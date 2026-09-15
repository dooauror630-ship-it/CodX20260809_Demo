<script setup lang="ts">
import { ChatDotRound, Close, Promotion } from "@element-plus/icons-vue";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { createAssistantToken, getGatewaySession, openGatewaySession, sendAssistantMessageStream } from "@/api/assistant";
import { errorMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { renderBusinessMessage } from "./messageFormat";

interface Message { id: number; role: "user" | "assistant"; content: string; createdAt: string }
const auth = useAuthStore();
const route = useRoute();
const hiddenOnAssistantPage = computed(() => route.path === "/assistant");
const open = ref(false); const loading = ref(false); const input = ref(""); const error = ref("");
const messages = ref<Message[]>([]); const sessionId = ref(""); const token = ref(""); let serial = 0;
const storageKey = `agri-assistant-messages-v1-${auth.user?.id ?? "current"}`;
const list = ref<HTMLElement>();

function save() { localStorage.setItem(storageKey, JSON.stringify({ savedAt: Date.now(), messages: messages.value.slice(-50) })); window.dispatchEvent(new Event("agri-assistant-sync")); }
function scroll() { void nextTick(() => list.value?.scrollTo({ top: list.value.scrollHeight, behavior: "smooth" })); }
async function ensureSession() {
  if (sessionId.value && token.value) return;
  const sessionKey = `agri-assistant-session-v1-${auth.user?.id ?? "current"}`;
  const saved = JSON.parse(sessionStorage.getItem(sessionKey) ?? "null") as { sessionId?: string; token?: string; expiresAt?: number } | null;
  if (saved?.sessionId && saved.token && saved.expiresAt && Date.now() < saved.expiresAt - 30_000) {
    try { await getGatewaySession(saved.sessionId, saved.token); sessionId.value = saved.sessionId; token.value = saved.token; return; } catch { sessionStorage.removeItem(sessionKey); }
  }
  const authToken = await createAssistantToken(); const session = await openGatewaySession(authToken.token); token.value = authToken.token; sessionId.value = session.sessionId;
  sessionStorage.setItem(sessionKey, JSON.stringify({ sessionId: session.sessionId, token: authToken.token, expiresAt: Date.now() + authToken.expiresIn * 1000 }));
}
async function send() {
  const text = input.value.trim(); if (!text || loading.value) return; input.value = ""; messages.value.push({ id: ++serial, role: "user", content: text, createdAt: new Date().toISOString() });
  const reply: Message = { id: ++serial, role: "assistant", content: "", createdAt: new Date().toISOString() }; messages.value.push(reply); loading.value = true; error.value = ""; save(); scroll();
  try { await ensureSession(); await sendAssistantMessageStream(sessionId.value, token.value, text, (event) => { if (event.event === "chunk") reply.content += event.data.text ?? ""; if (event.event === "done" && event.data.response) reply.content = event.data.response; if (event.event === "error") reply.content = event.data.message ?? "处理失败"; save(); scroll(); }); }
  catch (reason) { reply.content = "请求未完成：" + errorMessage(reason); error.value = errorMessage(reason); save(); }
  finally { loading.value = false; }
}
function restore() { try { const raw = JSON.parse(localStorage.getItem(storageKey) ?? "null") as { messages?: Message[] } | Message[] | null; const value = Array.isArray(raw) ? raw : raw?.messages ?? []; messages.value = value; serial = messages.value.reduce((max, item) => Math.max(max, item.id), 0); } catch { messages.value = []; } }
watch(hiddenOnAssistantPage, (hidden) => { if (hidden) open.value = false; });
onMounted(() => { restore(); window.addEventListener("agri-assistant-sync", restore); });
onBeforeUnmount(() => window.removeEventListener("agri-assistant-sync", restore));
</script>

<template>
  <div v-if="!hiddenOnAssistantPage" class="assistant-floating">
    <button v-if="!open" class="assistant-floating-trigger" type="button" aria-label="打开智能体助手" @click="open = true"><el-icon><ChatDotRound /></el-icon><span>智能体</span></button>
    <section v-else class="assistant-floating-panel" aria-label="智能体助手">
      <header><strong>智能体助手</strong><button type="button" aria-label="关闭智能体助手" @click="open = false"><el-icon><Close /></el-icon></button></header>
      <div ref="list" class="assistant-floating-messages">
        <p v-if="!messages.length" class="assistant-floating-empty">你好，我可以在当前页面帮你查询和处理业务。</p>
        <div v-for="message in messages" :key="message.id" :class="['assistant-floating-message', `is-${message.role}`]"><div v-if="message.role === 'assistant'" v-html="renderBusinessMessage(message.content)" /><span v-else>{{ message.content }}</span><time>{{ new Date(message.createdAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</time></div>
        <p v-if="loading" class="assistant-floating-loading">正在处理…</p>
      </div>
      <el-alert v-if="error" :title="error" type="warning" :closable="false" />
      <div class="assistant-floating-composer"><el-input v-model="input" :disabled="loading" placeholder="输入业务问题" @keydown.enter.prevent="send" /><el-button type="primary" :icon="Promotion" :loading="loading" :disabled="!input.trim()" aria-label="发送" @click="send" /></div>
    </section>
  </div>
</template>
