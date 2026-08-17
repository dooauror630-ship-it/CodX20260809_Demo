<script setup lang="ts">
import { Check, EditPen, Plus, Refresh, Search, UserFilled } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { getUsers } from "@/api/admin";
import { errorMessage } from "@/api/client";
import {
  addFarmMember,
  createFarm,
  getFarmMembers,
  getFarms,
  updateFarm,
  updateFarmMember,
} from "@/api/farms";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { User } from "@/types/auth";
import type { Farm, FarmMember, FarmRole } from "@/types/farm";


const roleOptions: Array<{ value: FarmRole; label: string }> = [
  { value: "manager", label: "农场负责人" },
  { value: "operator", label: "生产操作员" },
  { value: "viewer", label: "只读人员" },
];

const auth = useAuthStore();
const farmContext = useFarmStore();
const loading = ref(false);
const compactTable = ref(false);
const farms = ref<Farm[]>([]);
const filters = reactive<{
  keyword: string;
  status: "all" | "active" | "disabled";
}>({ keyword: "", status: "all" });
const pagination = reactive({ page: 1, pageSize: 10, total: 0 });

const farmDialogVisible = ref(false);
const farmSaving = ref(false);
const editingFarmId = ref<number | null>(null);
const farmForm = reactive({
  code: "",
  name: "",
  ownerName: "",
  address: "",
  isActive: true,
});
const farmDialogTitle = computed(() => editingFarmId.value ? "编辑农场" : "新建农场");

const memberDialogVisible = ref(false);
const memberLoading = ref(false);
const memberSavingId = ref<number | null>(null);
const addingMember = ref(false);
const memberFarm = ref<Farm | null>(null);
const members = ref<FarmMember[]>([]);
const users = ref<User[]>([]);
const memberForm = reactive<{ userId: number | null; roleCode: FarmRole }>({
  userId: null,
  roleCode: "operator",
});
const availableUsers = computed(() => users.value.filter((user) => (
  !members.value.some((member) => member.user.id === user.id && member.isActive)
)));

function roleName(role: string) {
  if (role === "admin") return "系统管理员";
  return roleOptions.find((option) => option.value === role)?.label ?? role;
}

async function loadFarms() {
  loading.value = true;
  try {
    const data = await getFarms({
      page: pagination.page,
      pageSize: pagination.pageSize,
      keyword: filters.keyword || undefined,
      status: auth.isAdmin ? filters.status : "active",
    });
    farms.value = data.items;
    pagination.total = data.pagination.total;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loading.value = false;
  }
}

function searchFarms() {
  pagination.page = 1;
  void loadFarms();
}

function resetFilters() {
  filters.keyword = "";
  filters.status = "all";
  searchFarms();
}

function changePage(page: number) {
  pagination.page = page;
  void loadFarms();
}

function changePageSize(pageSize: number) {
  pagination.page = 1;
  pagination.pageSize = pageSize;
  void loadFarms();
}

function resetFarmForm() {
  editingFarmId.value = null;
  farmForm.code = "";
  farmForm.name = "";
  farmForm.ownerName = "";
  farmForm.address = "";
  farmForm.isActive = true;
}

function openCreateFarm() {
  resetFarmForm();
  farmDialogVisible.value = true;
}

function openEditFarm(farm: Farm) {
  editingFarmId.value = farm.id;
  farmForm.code = farm.code;
  farmForm.name = farm.name;
  farmForm.ownerName = farm.ownerName;
  farmForm.address = farm.address ?? "";
  farmForm.isActive = farm.isActive;
  farmDialogVisible.value = true;
}

function validateFarm() {
  const code = farmForm.code.trim();
  const name = farmForm.name.trim();
  const ownerName = farmForm.ownerName.trim();
  if (!/^[A-Za-z0-9_-]{2,20}$/.test(code)) return "农场编号须为 2-20 位字母、数字、下划线或短横线";
  if (name.length < 2 || name.length > 80) return "农场名称须为 2-80 个字符";
  if (ownerName.length < 2 || ownerName.length > 40) return "负责人须为 2-40 个字符";
  if (farmForm.address.trim().length > 255) return "地址不能超过 255 个字符";
  return "";
}

async function refreshFarmContext() {
  await loadFarms();
  try {
    await farmContext.load(true);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  }
}

async function saveFarm() {
  const validationError = validateFarm();
  if (validationError) {
    ElMessage.error(validationError);
    return;
  }

  farmSaving.value = true;
  const input = {
    code: farmForm.code.trim(),
    name: farmForm.name.trim(),
    ownerName: farmForm.ownerName.trim(),
    address: farmForm.address.trim() || null,
  };
  try {
    let createdFarm: Farm | null = null;
    if (editingFarmId.value) {
      await updateFarm(editingFarmId.value, { ...input, isActive: farmForm.isActive });
      ElMessage.success("农场信息已更新");
    } else {
      createdFarm = await createFarm(input);
      ElMessage.success("农场已创建");
    }
    farmDialogVisible.value = false;
    await refreshFarmContext();
    if (createdFarm) farmContext.select(createdFarm.id);
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    farmSaving.value = false;
  }
}

async function loadMembers() {
  if (!memberFarm.value) return;
  memberLoading.value = true;
  try {
    const [farmMembers, userData] = await Promise.all([
      getFarmMembers(memberFarm.value.id),
      getUsers({ page: 1, pageSize: 100, role: "operator", status: "active" }),
    ]);
    members.value = farmMembers;
    users.value = userData.items;
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    memberLoading.value = false;
  }
}

function openMembers(farm: Farm) {
  memberFarm.value = farm;
  memberForm.userId = null;
  memberForm.roleCode = "operator";
  memberDialogVisible.value = true;
  void loadMembers();
}

async function saveMember() {
  if (!memberFarm.value || !memberForm.userId) {
    ElMessage.error("请选择需要加入农场的用户");
    return;
  }
  addingMember.value = true;
  try {
    await addFarmMember(memberFarm.value.id, memberForm.userId, memberForm.roleCode);
    memberForm.userId = null;
    memberForm.roleCode = "operator";
    ElMessage.success("农场成员已保存");
    await loadMembers();
    await refreshFarmContext();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    addingMember.value = false;
  }
}

async function saveMemberChange(member: FarmMember, input: { roleCode?: FarmRole; isActive?: boolean }) {
  if (!memberFarm.value) return;
  memberSavingId.value = member.user.id;
  try {
    const updated = await updateFarmMember(memberFarm.value.id, member.user.id, input);
    Object.assign(member, updated);
    ElMessage.success("成员权限已更新");
    await refreshFarmContext();
  } catch (error) {
    ElMessage.error(errorMessage(error));
    await loadMembers();
  } finally {
    memberSavingId.value = null;
  }
}

function changeMemberRole(member: FarmMember) {
  void saveMemberChange(member, { roleCode: member.roleCode });
}

function changeMemberStatus(member: FarmMember) {
  void saveMemberChange(member, { isActive: member.isActive });
}

function chooseFarm(farm: Farm) {
  farmContext.select(farm.id);
  ElMessage.success(`当前农场已切换为“${farm.name}”`);
}

function updateTableLayout() {
  compactTable.value = window.innerWidth < 760;
}

onMounted(() => {
  updateTableLayout();
  window.addEventListener("resize", updateTableLayout);
  void loadFarms();
});

onBeforeUnmount(() => window.removeEventListener("resize", updateTableLayout));
</script>

<template>
  <section class="farm-page">
    <header class="page-header farm-page-header">
      <div>
        <p class="eyebrow">FARM PROFILE</p>
        <h1>农场档案</h1>
        <p>{{ auth.isAdmin ? `统一维护 ${pagination.total} 个农场及其成员权限` : "查看自己有权访问的农场资料" }}</p>
      </div>
      <el-button v-if="auth.isAdmin" type="primary" :icon="Plus" @click="openCreateFarm">新建农场</el-button>
    </header>

    <div class="farm-toolbar" :class="{ 'is-user-view': !auth.isAdmin }" role="search" aria-label="筛选农场">
      <el-input
        v-model="filters.keyword"
        clearable
        :prefix-icon="Search"
        placeholder="搜索农场编号、名称或负责人"
        aria-label="搜索农场"
        @clear="searchFarms"
        @keyup.enter="searchFarms"
      />
      <el-select v-if="auth.isAdmin" v-model="filters.status" aria-label="筛选农场状态">
        <el-option label="全部状态" value="all" />
        <el-option label="正常经营" value="active" />
        <el-option label="已停用" value="disabled" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="searchFarms">查询</el-button>
      <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
    </div>

    <div class="farm-table-shell">
      <el-table v-loading="loading" :data="farms" row-key="id" empty-text="暂无可访问的农场">
        <el-table-column label="农场名称" min-width="180">
          <template #default="scope">
            <div class="farm-name-cell">
              <strong>{{ scope.row.name }}</strong>
              <span>{{ scope.row.code }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="!compactTable" prop="ownerName" label="负责人" min-width="110" />
        <el-table-column v-if="!compactTable" label="地址" min-width="190" show-overflow-tooltip>
          <template #default="scope">{{ scope.row.address || "-" }}</template>
        </el-table-column>
        <el-table-column v-if="auth.isAdmin && !compactTable" prop="memberCount" label="有效成员" width="95" align="center" />
        <el-table-column v-if="!auth.isAdmin && !compactTable" label="我的权限" width="125">
          <template #default="scope">
            <el-tag type="info" effect="plain">{{ roleName(scope.row.accessRole) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="scope">
            <el-tag :type="scope.row.isActive ? 'success' : 'danger'" effect="plain">
              {{ scope.row.isActive ? "正常" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="compactTable ? 112 : auth.isAdmin ? 245 : 120" fixed="right">
          <template #default="scope">
            <div class="farm-actions">
              <el-tooltip v-if="farmContext.currentFarmId !== scope.row.id" content="设为当前农场">
                <el-button
                  circle
                  :icon="Check"
                  aria-label="设为当前农场"
                  @click="chooseFarm(scope.row)"
                />
              </el-tooltip>
              <el-tag v-else class="current-farm-tag" type="success" effect="light">当前</el-tag>
              <template v-if="auth.isAdmin">
                <el-tooltip v-if="compactTable" content="编辑农场">
                  <el-button circle :icon="EditPen" aria-label="编辑农场" @click="openEditFarm(scope.row)" />
                </el-tooltip>
                <el-tooltip v-if="compactTable" content="成员管理">
                  <el-button circle :icon="UserFilled" aria-label="成员管理" @click="openMembers(scope.row)" />
                </el-tooltip>
                <template v-else>
                  <el-button link type="primary" :icon="EditPen" @click="openEditFarm(scope.row)">编辑</el-button>
                  <el-button link type="primary" :icon="UserFilled" @click="openMembers(scope.row)">成员管理</el-button>
                </template>
              </template>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <footer class="admin-pagination">
        <span>共 {{ pagination.total }} 个农场</span>
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

    <el-dialog v-model="farmDialogVisible" :title="farmDialogTitle" width="min(92vw, 560px)" destroy-on-close>
      <el-form label-position="top" @submit.prevent="saveFarm">
        <div class="farm-form-grid">
          <el-form-item label="农场编号" required>
            <el-input v-model="farmForm.code" maxlength="20" placeholder="例如 FARM-001" aria-label="农场编号" />
          </el-form-item>
          <el-form-item label="农场名称" required>
            <el-input v-model="farmForm.name" maxlength="80" placeholder="请输入农场名称" aria-label="农场名称" />
          </el-form-item>
          <el-form-item label="负责人" required>
            <el-input v-model="farmForm.ownerName" maxlength="40" placeholder="请输入负责人姓名" aria-label="负责人" />
          </el-form-item>
          <el-form-item v-if="editingFarmId" label="经营状态">
            <el-switch v-model="farmForm.isActive" active-text="正常" inactive-text="停用" />
          </el-form-item>
        </div>
        <el-form-item label="农场地址">
          <el-input
            v-model="farmForm.address"
            type="textarea"
            :rows="2"
            maxlength="255"
            show-word-limit
            placeholder="请输入省、市、区县和详细地址"
            aria-label="农场地址"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="farmDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="farmSaving" @click="saveFarm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="memberDialogVisible"
      :title="`${memberFarm?.name ?? ''} · 成员管理`"
      width="min(94vw, 820px)"
      destroy-on-close
    >
      <div class="member-add-bar">
        <el-select
          v-model="memberForm.userId"
          filterable
          clearable
          aria-label="选择系统用户"
          placeholder="选择系统用户"
        >
          <el-option
            v-for="user in availableUsers"
            :key="user.id"
            :label="`${user.displayName}（${user.username}）`"
            :value="user.id"
          />
        </el-select>
        <el-select v-model="memberForm.roleCode" aria-label="选择农场角色">
          <el-option v-for="role in roleOptions" :key="role.value" :label="role.label" :value="role.value" />
        </el-select>
        <el-button type="primary" :icon="Plus" :loading="addingMember" @click="saveMember">添加成员</el-button>
      </div>

      <el-table v-loading="memberLoading" :data="members" row-key="user.id" empty-text="暂无成员" class="member-table">
        <el-table-column label="成员" min-width="180">
          <template #default="scope">
            <div class="farm-name-cell">
              <strong>{{ scope.row.user.displayName }}</strong>
              <span>{{ scope.row.user.username }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="农场角色" min-width="160">
          <template #default="scope">
            <el-select
              v-model="scope.row.roleCode"
              :disabled="memberSavingId !== null"
              :aria-label="`${scope.row.user.displayName}的农场角色`"
              @change="changeMemberRole(scope.row)"
            >
              <el-option v-for="role in roleOptions" :key="role.value" :label="role.label" :value="role.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="成员状态" width="145" align="center">
          <template #default="scope">
            <el-switch
              v-model="scope.row.isActive"
              :loading="memberSavingId === scope.row.user.id"
              :disabled="memberSavingId !== null"
              active-text="有效"
              inactive-text="停用"
              @change="changeMemberStatus(scope.row)"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </section>
</template>
