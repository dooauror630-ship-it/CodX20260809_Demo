<script setup lang="ts">
import {
  Box,
  Collection,
  DataAnalysis,
  Food,
  Goods,
  House,
  MapLocation,
  Menu,
  OfficeBuilding,
  ShoppingCart,
  SwitchButton,
  Tickets,
  UserFilled,
} from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { errorMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";


const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const farms = useFarmStore();
const mobileMenuOpen = ref(false);
const loggingOut = ref(false);
const currentPageTitle = computed(() => String(route.meta.title ?? "工作台"));
const identityRole = computed(() => auth.isAdmin ? "admin" : farms.currentFarm?.accessRole ?? "user");
const identityLabel = computed(() => ({
  admin: "管理员",
  manager: "负责人",
  operator: "操作员",
  viewer: "查看员",
  user: "普通用户",
})[identityRole.value]);

watch(
  () => route.fullPath,
  () => {
    mobileMenuOpen.value = false;
  },
);

async function handleLogout() {
  loggingOut.value = true;
  try {
    await auth.logout();
    farms.reset();
    await router.replace({ name: "login" });
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loggingOut.value = false;
  }
}

async function loadFarmContext() {
  try {
    await farms.load();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

onMounted(() => void loadFarmContext());
</script>

<template>
  <div class="app-shell" :class="{ 'mobile-menu-open': mobileMenuOpen }">
    <button
      v-if="mobileMenuOpen"
      class="mobile-backdrop"
      type="button"
      aria-label="关闭导航"
      @click="mobileMenuOpen = false"
    />
    <aside class="app-sidebar">
      <div class="sidebar-brand">
        <span class="brand-mark" aria-hidden="true">田</span>
        <span>
          <strong>综合农牧业</strong>
          <small>管理系统</small>
        </span>
      </div>
      <nav class="sidebar-nav" aria-label="主导航">
        <router-link to="/dashboard" class="sidebar-link">
          <el-icon><DataAnalysis /></el-icon>
          <span>工作台</span>
        </router-link>
        <router-link to="/base/farms" class="sidebar-link">
          <el-icon><OfficeBuilding /></el-icon>
          <span>农场档案</span>
        </router-link>
        <router-link to="/base/barns" class="sidebar-link">
          <el-icon><House /></el-icon>
          <span>圈舍管理</span>
        </router-link>
        <router-link to="/base/plots" class="sidebar-link">
          <el-icon><MapLocation /></el-icon>
          <span>地块管理</span>
        </router-link>
        <router-link to="/base/warehouses" class="sidebar-link">
          <el-icon><Box /></el-icon>
          <span>仓库管理</span>
        </router-link>
        <router-link to="/base/items" class="sidebar-link">
          <el-icon><Goods /></el-icon>
          <span>物料管理</span>
        </router-link>
        <router-link to="/base/catalogs" class="sidebar-link">
          <el-icon><Collection /></el-icon>
          <span>业务字典</span>
        </router-link>
        <router-link to="/inventory/purchases" class="sidebar-link">
          <el-icon><ShoppingCart /></el-icon>
          <span>采购入库</span>
        </router-link>
        <router-link to="/inventory/stocks" class="sidebar-link">
          <el-icon><Tickets /></el-icon>
          <span>库存管理</span>
        </router-link>
        <router-link to="/livestock/pigs" class="sidebar-link">
          <el-icon><Food /></el-icon>
          <span>生猪管理</span>
        </router-link>
        <router-link to="/crop/cycles" class="sidebar-link">
          <el-icon><MapLocation /></el-icon>
          <span>种植周期</span>
        </router-link>
        <router-link to="/crop/operations" class="sidebar-link">
          <el-icon><Tickets /></el-icon>
          <span>农事操作</span>
        </router-link>
        <router-link to="/crop/harvests" class="sidebar-link">
          <el-icon><Collection /></el-icon>
          <span>采收批次</span>
        </router-link>
        <router-link to="/crop/curing" class="sidebar-link">
          <el-icon><Tickets /></el-icon>
          <span>烟草烘烤</span>
        </router-link>
        <router-link v-if="auth.isAdmin" to="/admin/users" class="sidebar-link">
          <el-icon><UserFilled /></el-icon>
          <span>用户管理</span>
        </router-link>
      </nav>
      <div class="sidebar-status">
        <span class="status-dot" aria-hidden="true" />
        <span>系统服务正常</span>
      </div>
    </aside>

    <section class="app-main">
      <header class="app-topbar">
        <div class="topbar-leading">
          <el-button
            class="mobile-menu-button"
            text
            :icon="Menu"
            aria-label="打开导航"
            @click="mobileMenuOpen = true"
          />
          <div>
            <p>综合农牧业管理系统</p>
            <strong>{{ currentPageTitle }}</strong>
          </div>
        </div>

        <div class="topbar-actions">
          <div class="farm-context">
            <el-icon aria-hidden="true"><OfficeBuilding /></el-icon>
            <el-select
              :model-value="farms.currentFarmId"
              :loading="farms.loading"
              :disabled="farms.farms.length === 0"
              aria-label="当前农场"
              placeholder="暂无农场"
              @change="farms.select"
            >
              <el-option
                v-for="farm in farms.farms"
                :key="farm.id"
                :label="farm.name"
                :value="farm.id"
              />
            </el-select>
          </div>

          <el-dropdown trigger="click">
            <button
              class="user-control"
              type="button"
              :aria-label="`${auth.user?.displayName ?? '用户'}${identityLabel}账户菜单`"
            >
              <span class="user-avatar">{{ auth.user?.displayName?.slice(0, 1) }}</span>
              <span class="user-control-copy">
                <strong>{{ auth.user?.displayName }}</strong>
                <small>{{ auth.user?.username }}</small>
              </span>
              <span class="user-identity-badge" :class="`is-${identityRole}`">
                {{ identityLabel }}
              </span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="SwitchButton" :disabled="loggingOut" @click="handleLogout">
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="app-content">
        <router-view />
      </main>
    </section>
  </div>
</template>
