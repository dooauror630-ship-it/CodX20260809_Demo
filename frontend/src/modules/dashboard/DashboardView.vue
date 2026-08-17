<script setup lang="ts">
import { CircleCheck, Clock, Connection, Key, User } from "@element-plus/icons-vue";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { getSystemOverview } from "@/api/analytics";
import { errorMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import type { SystemOverview } from "@/types/analytics";
import RegistrationTrendChart from "./components/RegistrationTrendChart.vue";


const auth = useAuthStore();
const loading = ref(auth.isAdmin);
const loadError = ref("");
const overview = ref<SystemOverview>();
const descriptionColumns = ref(4);

const roleNames: Record<string, string> = {
  admin: "系统管理员",
  manager: "生产负责人",
  operator: "生产操作员",
  viewer: "查看人员",
};

const todayText = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "long",
  day: "numeric",
  weekday: "long",
}).format(new Date());

const summaryCards = computed(() => {
  if (!auth.isAdmin) {
    return [
      { label: "账户状态", value: auth.user?.isActive ? "正常" : "异常", unit: "", icon: CircleCheck, tone: "green" },
      { label: "用户身份", value: "普通用户", unit: "", icon: User, tone: "blue" },
      { label: "数据范围", value: "仅本人", unit: "", icon: Key, tone: "amber" },
      { label: "服务状态", value: "正常", unit: "", icon: Connection, tone: "green" },
    ];
  }
  const summary = overview.value?.summary;
  return [
    { label: "账户总数", value: summary?.registeredUsers ?? 0, unit: "个", icon: User, tone: "green" },
    { label: "有效账户", value: summary?.activeUsers ?? 0, unit: "个", icon: CircleCheck, tone: "blue" },
    { label: "近 7 日登录", value: summary?.recentLogins ?? 0, unit: "个", icon: Clock, tone: "amber" },
    {
      label: "服务状态",
      value: summary?.serviceHealthy ? "正常" : "异常",
      unit: "",
      icon: Connection,
      tone: summary?.serviceHealthy ? "green" : "red",
    },
  ];
});

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

async function loadOverview() {
  loading.value = true;
  loadError.value = "";
  try {
    overview.value = await getSystemOverview();
  } catch (error) {
    loadError.value = errorMessage(error);
  } finally {
    loading.value = false;
  }
}

function updateDescriptionColumns() {
  descriptionColumns.value = window.innerWidth < 700 ? 1 : window.innerWidth < 1180 ? 2 : 4;
}

onMounted(() => {
  updateDescriptionColumns();
  window.addEventListener("resize", updateDescriptionColumns);
  if (auth.isAdmin) void loadOverview();
});

onBeforeUnmount(() => window.removeEventListener("resize", updateDescriptionColumns));
</script>

<template>
  <section class="dashboard-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ todayText }}</p>
        <h1>{{ auth.user?.displayName }}，欢迎回来</h1>
        <p>{{ auth.isAdmin ? "用户与系统运行数据已更新。" : "生产经营工作台已就绪。" }}</p>
      </div>
      <el-tag type="success" effect="plain" round>MySQL 已连接</el-tag>
    </header>

    <el-alert v-if="auth.isAdmin && loadError" :title="loadError" type="error" show-icon :closable="false">
      <template #default>
        <el-button type="danger" link @click="loadOverview">重新加载</el-button>
      </template>
    </el-alert>

    <div class="summary-grid" :aria-label="auth.isAdmin ? '系统概览' : '账户概览'">
      <article v-for="item in summaryCards" :key="item.label" class="summary-card">
        <span class="summary-icon" :class="`tone-${item.tone}`">
          <el-icon><component :is="item.icon" /></el-icon>
        </span>
        <div>
          <p>{{ item.label }}</p>
          <strong>{{ item.value }}<small>{{ item.unit }}</small></strong>
        </div>
      </article>
    </div>

    <div v-if="auth.isAdmin" v-loading="loading" class="dashboard-grid">
      <section class="chart-panel" aria-labelledby="registrationTrendTitle">
        <header class="panel-header">
          <div>
            <p class="eyebrow">SYSTEM ACTIVITY</p>
            <h2 id="registrationTrendTitle">账户创建趋势</h2>
          </div>
          <span>最近 6 个月</span>
        </header>
        <registration-trend-chart :data="overview?.registrationTrend ?? []" />
      </section>

      <section class="role-panel" aria-labelledby="roleTitle">
        <header class="panel-header">
          <div>
            <p class="eyebrow">ACCESS</p>
            <h2 id="roleTitle">角色分布</h2>
          </div>
        </header>
        <div class="role-list">
          <div v-for="item in overview?.roleDistribution ?? []" :key="item.role" class="role-row">
            <span>{{ roleNames[item.role] ?? item.role }}</span>
            <strong>{{ item.count }}</strong>
          </div>
          <el-empty v-if="!loading && !overview?.roleDistribution.length" description="暂无账户数据" :image-size="72" />
        </div>
      </section>
    </div>

    <section class="account-panel" aria-labelledby="accountTitle">
      <header class="panel-header">
        <div>
          <p class="eyebrow">CURRENT ACCOUNT</p>
          <h2 id="accountTitle">当前账户</h2>
        </div>
        <el-tag type="success" effect="light">已登录</el-tag>
      </header>
      <el-descriptions :column="descriptionColumns" border class="account-descriptions">
        <el-descriptions-item label="姓名">{{ auth.user?.displayName }}</el-descriptions-item>
        <el-descriptions-item label="账号">{{ auth.user?.username }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ roleNames[auth.user?.role ?? ""] ?? auth.user?.role }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(auth.user?.createdAt) }}</el-descriptions-item>
      </el-descriptions>
    </section>
  </section>
</template>
