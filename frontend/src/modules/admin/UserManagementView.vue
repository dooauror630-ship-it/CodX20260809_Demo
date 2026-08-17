<script setup lang="ts">
import { EditPen, Key, Refresh, Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { getUsers, resetUserPassword, updateUser } from "@/api/admin";
import { errorMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import type { User } from "@/types/auth";


const auth = useAuthStore();
const loading = ref(false);
const compactTable = ref(false);
const users = ref<User[]>([]);
const filters = reactive<{
  keyword: string;
  role: "" | "admin" | "operator";
  status: "all" | "active" | "disabled";
}>({
  keyword: "",
  role: "",
  status: "all",
});
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });

const editVisible = ref(false);
const editSaving = ref(false);
const editForm = reactive<{
  id: number;
  username: string;
  displayName: string;
  role: "admin" | "operator";
  isActive: boolean;
}>({
  id: 0,
  username: "",
  displayName: "",
  role: "operator",
  isActive: true,
});
const editingSelf = computed(() => editForm.id === auth.user?.id);

const passwordVisible = ref(false);
const passwordSaving = ref(false);
const passwordForm = reactive({ userId: 0, username: "", password: "", confirmation: "" });

function roleName(role: string) {
  return role === "admin" ? "系统管理员" : "普通用户";
}

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

async function loadUsers() {
  loading.value = true;
  try {
    const data = await getUsers({
      page: pagination.page,
      pageSize: pagination.pageSize,
      keyword: filters.keyword || undefined,
      role: filters.role || undefined,
      status: filters.status,
    });
    users.value = data.items;
    pagination.total = data.pagination.total;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

function searchUsers() {
  pagination.page = 1;
  void loadUsers();
}

function resetFilters() {
  filters.keyword = "";
  filters.role = "";
  filters.status = "all";
  searchUsers();
}

function openEdit(user: User) {
  editForm.id = user.id;
  editForm.username = user.username;
  editForm.displayName = user.displayName;
  editForm.role = user.role === "admin" ? "admin" : "operator";
  editForm.isActive = user.isActive;
  editVisible.value = true;
}

async function saveUser() {
  const displayName = editForm.displayName.trim();
  if (displayName.length < 2 || displayName.length > 20) {
    ElMessage.error("姓名须为 2-20 个字符");
    return;
  }
  editSaving.value = true;
  try {
    const user = await updateUser(editForm.id, {
      displayName,
      role: editForm.role,
      isActive: editForm.isActive,
    });
    if (user.id === auth.user?.id) auth.user = user;
    ElMessage.success("用户信息已更新");
    editVisible.value = false;
    await loadUsers();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    editSaving.value = false;
  }
}

function openPasswordReset(user: User) {
  passwordForm.userId = user.id;
  passwordForm.username = user.username;
  passwordForm.password = "";
  passwordForm.confirmation = "";
  passwordVisible.value = true;
}

async function savePassword() {
  if (!/^(?=.*[A-Za-z])(?=.*\d).{8,64}$/.test(passwordForm.password)) {
    ElMessage.error("密码须为 8-64 位，且同时包含字母和数字");
    return;
  }
  if (passwordForm.password !== passwordForm.confirmation) {
    ElMessage.error("两次输入的密码不一致");
    return;
  }
  passwordSaving.value = true;
  try {
    await resetUserPassword(passwordForm.userId, passwordForm.password);
    ElMessage.success("密码已重置");
    passwordVisible.value = false;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    passwordSaving.value = false;
  }
}

function changePage(page: number) {
  pagination.page = page;
  void loadUsers();
}

function changePageSize(pageSize: number) {
  pagination.page = 1;
  pagination.pageSize = pageSize;
  void loadUsers();
}

function updateTableLayout() {
  compactTable.value = window.innerWidth < 700;
}

onMounted(() => {
  updateTableLayout();
  window.addEventListener("resize", updateTableLayout);
  void loadUsers();
});

onBeforeUnmount(() => window.removeEventListener("resize", updateTableLayout));
</script>

<template>
  <section class="admin-users-page">
    <header class="page-header admin-page-header">
      <div>
        <p class="eyebrow">ACCESS CONTROL</p>
        <h1>用户管理</h1>
        <p>当前共 {{ pagination.total }} 个账号</p>
      </div>
      <el-tag type="warning" effect="plain">管理员专属</el-tag>
    </header>

    <div class="admin-toolbar" role="search" aria-label="筛选用户">
      <el-input
        v-model="filters.keyword"
        clearable
        :prefix-icon="Search"
        placeholder="搜索账号或姓名"
        aria-label="搜索账号或姓名"
        @clear="searchUsers"
        @keyup.enter="searchUsers"
      />
      <el-select v-model="filters.role" aria-label="筛选用户身份" placeholder="全部身份">
        <el-option label="全部身份" value="" />
        <el-option label="系统管理员" value="admin" />
        <el-option label="普通用户" value="operator" />
      </el-select>
      <el-select v-model="filters.status" aria-label="筛选账号状态">
        <el-option label="全部状态" value="all" />
        <el-option label="正常" value="active" />
        <el-option label="已停用" value="disabled" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="searchUsers">查询</el-button>
      <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
    </div>

    <div class="admin-table-shell">
      <el-table v-loading="loading" :data="users" row-key="id" empty-text="暂无用户" class="admin-user-table">
        <el-table-column prop="displayName" label="姓名" min-width="110" />
        <el-table-column prop="username" label="账号" min-width="120" />
        <el-table-column v-if="!compactTable" label="用户身份" width="115">
          <template #default="scope">
            <el-tag :type="scope.row.role === 'admin' ? 'warning' : 'info'" effect="light">
              {{ roleName(scope.row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!compactTable" label="账号状态" width="95">
          <template #default="scope">
            <el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">
              {{ scope.row.isActive ? "正常" : "已停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!compactTable" label="创建时间" min-width="145">
          <template #default="scope">{{ formatDate(scope.row.createdAt) }}</template>
        </el-table-column>
        <el-table-column v-if="!compactTable" label="最近登录" min-width="145">
          <template #default="scope">{{ formatDate(scope.row.lastLoginAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" :width="compactTable ? 92 : 170" fixed="right">
          <template #default="scope">
            <template v-if="compactTable">
              <div class="compact-actions">
                <el-tooltip content="编辑用户">
                  <el-button circle :icon="EditPen" aria-label="编辑" @click="openEdit(scope.row)" />
                </el-tooltip>
                <el-tooltip content="重置密码">
                  <el-button circle :icon="Key" aria-label="重置密码" @click="openPasswordReset(scope.row)" />
                </el-tooltip>
              </div>
            </template>
            <template v-else>
              <el-button link type="primary" :icon="EditPen" @click="openEdit(scope.row)">编辑</el-button>
              <el-button link type="primary" :icon="Key" @click="openPasswordReset(scope.row)">重置密码</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <footer class="admin-pagination">
        <span>共 {{ pagination.total }} 个用户</span>
        <el-pagination
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="sizes, prev, pager, next"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </footer>
    </div>

    <el-dialog v-model="editVisible" title="编辑用户" width="min(92vw, 480px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveUser">
        <el-form-item label="账号">
          <el-input :model-value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="editForm.displayName" maxlength="20" show-word-limit placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="用户身份" required>
          <el-select v-model="editForm.role" :disabled="editingSelf">
            <el-option label="系统管理员" value="admin" />
            <el-option label="普通用户" value="operator" />
          </el-select>
          <p v-if="editingSelf" class="form-note">不能取消自己的管理员身份</p>
        </el-form-item>
        <el-form-item label="账号状态">
          <el-switch
            v-model="editForm.isActive"
            :disabled="editingSelf"
            active-text="正常"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveUser">保存修改</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordVisible" title="重置密码" width="min(92vw, 440px)" destroy-on-close>
      <p class="dialog-context">账号：{{ passwordForm.username }}</p>
      <el-form label-position="top" @submit.prevent="savePassword">
        <el-form-item label="新密码" required>
          <el-input
            v-model="passwordForm.password"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="至少 8 位，含字母和数字"
          />
        </el-form-item>
        <el-form-item label="确认密码" required>
          <el-input
            v-model="passwordForm.confirmation"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="请再次输入新密码"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSaving" @click="savePassword">确认重置</el-button>
      </template>
    </el-dialog>
  </section>
</template>
