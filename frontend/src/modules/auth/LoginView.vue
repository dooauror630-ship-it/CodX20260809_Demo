<script setup lang="ts">
import { Lock, Postcard, User } from "@element-plus/icons-vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { errorMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";


interface LoginForm {
  username: string;
  password: string;
  remember: boolean;
}

interface RegisterForm {
  displayName: string;
  username: string;
  password: string;
  confirmPassword: string;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const activeTab = ref("login");
const loginFormRef = ref<FormInstance>();
const registerFormRef = ref<FormInstance>();
const loginBusy = ref(false);
const registerBusy = ref(false);

const loginForm = reactive<LoginForm>({
  username: "",
  password: "",
  remember: false,
});

const registerForm = reactive<RegisterForm>({
  displayName: "",
  username: "",
  password: "",
  confirmPassword: "",
});

const loginRules: FormRules<LoginForm> = {
  username: [{ required: true, message: "请输入登录账号", trigger: "blur" }],
  password: [{ required: true, message: "请输入登录密码", trigger: "blur" }],
};

const registerRules: FormRules<RegisterForm> = {
  displayName: [
    { required: true, message: "请输入姓名", trigger: "blur" },
    { min: 2, max: 20, message: "姓名须为 2-20 个字符", trigger: "blur" },
  ],
  username: [
    { required: true, message: "请输入登录账号", trigger: "blur" },
    { pattern: /^[A-Za-z0-9_]{4,20}$/, message: "账号须为 4-20 位字母、数字或下划线", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请设置登录密码", trigger: "blur" },
    {
      pattern: /^(?=.*[A-Za-z])(?=.*\d).{8,64}$/,
      message: "密码须为 8-64 位，且同时包含字母和数字",
      trigger: "blur",
    },
  ],
  confirmPassword: [
    { required: true, message: "请再次输入密码", trigger: "blur" },
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        callback(value === registerForm.password ? undefined : new Error("两次输入的密码不一致"));
      },
      trigger: "blur",
    },
  ],
};

async function goToWorkspace() {
  const destination = typeof route.query.redirect === "string" ? route.query.redirect : "/dashboard";
  await router.replace(destination);
}

async function submitLogin() {
  const valid = await loginFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  loginBusy.value = true;
  try {
    await auth.login(loginForm);
    loginForm.password = "";
    await goToWorkspace();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    loginBusy.value = false;
  }
}

async function submitRegister() {
  const valid = await registerFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  registerBusy.value = true;
  try {
    await auth.register({
      displayName: registerForm.displayName,
      username: registerForm.username,
      password: registerForm.password,
    });
    await goToWorkspace();
  } catch (error) {
    ElMessage.error(errorMessage(error));
  } finally {
    registerBusy.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-visual" aria-label="现代农牧业生产场景">
      <div class="brand brand-on-image">
        <span class="brand-mark" aria-hidden="true">田</span>
        <span>
          <strong>综合农牧业管理系统</strong>
          <small>AGRICULTURE OPERATIONS</small>
        </span>
      </div>
      <div class="auth-visual-copy">
        <p class="eyebrow">生产 · 养殖 · 库存</p>
        <h1>每一批生产，都有清晰记录</h1>
        <p>统一管理生产过程与经营数据，及时掌握农场运行状态。</p>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-mobile-brand">
        <span class="brand-mark" aria-hidden="true">田</span>
        <strong>综合农牧业管理系统</strong>
      </div>

      <div class="auth-form-wrap">
        <header class="auth-heading">
          <p class="eyebrow">账户中心</p>
          <h2>{{ activeTab === "login" ? "欢迎回来" : "创建工作账户" }}</h2>
          <p>{{ activeTab === "login" ? "登录后进入生产经营工作台" : "注册完成后即可进入系统" }}</p>
        </header>

        <el-tabs v-model="activeTab" class="auth-tabs" stretch>
          <el-tab-pane label="登录" name="login">
            <el-form
              ref="loginFormRef"
              :model="loginForm"
              :rules="loginRules"
              label-position="top"
              size="large"
              @submit.prevent="submitLogin"
            >
              <el-form-item label="登录账号" prop="username">
                <el-input
                  v-model="loginForm.username"
                  :prefix-icon="User"
                  name="username"
                  autocomplete="username"
                  maxlength="20"
                  placeholder="请输入账号"
                />
              </el-form-item>
              <el-form-item label="登录密码" prop="password">
                <el-input
                  v-model="loginForm.password"
                  :prefix-icon="Lock"
                  name="password"
                  type="password"
                  autocomplete="current-password"
                  maxlength="64"
                  placeholder="请输入密码"
                  show-password
                  @keyup.enter="submitLogin"
                />
              </el-form-item>
              <el-checkbox v-model="loginForm.remember">7 天内保持登录</el-checkbox>
              <el-button class="auth-submit" type="primary" native-type="submit" :loading="loginBusy">
                登录系统
              </el-button>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="注册" name="register">
            <el-form
              ref="registerFormRef"
              :model="registerForm"
              :rules="registerRules"
              label-position="top"
              size="large"
              @submit.prevent="submitRegister"
            >
              <div class="auth-field-grid">
                <el-form-item label="姓名" prop="displayName">
                  <el-input
                    v-model="registerForm.displayName"
                    :prefix-icon="Postcard"
                    name="displayName"
                    autocomplete="name"
                    maxlength="20"
                    placeholder="请输入姓名"
                  />
                </el-form-item>
                <el-form-item label="登录账号" prop="username">
                  <el-input
                    v-model="registerForm.username"
                    :prefix-icon="User"
                    name="username"
                    autocomplete="username"
                    maxlength="20"
                    placeholder="4-20 位字符"
                  />
                </el-form-item>
              </div>
              <el-form-item label="设置密码" prop="password">
                <el-input
                  v-model="registerForm.password"
                  :prefix-icon="Lock"
                  name="newPassword"
                  type="password"
                  autocomplete="new-password"
                  maxlength="64"
                  placeholder="至少 8 位，含字母和数字"
                  show-password
                />
              </el-form-item>
              <el-form-item label="确认密码" prop="confirmPassword">
                <el-input
                  v-model="registerForm.confirmPassword"
                  :prefix-icon="Lock"
                  name="confirmPassword"
                  type="password"
                  autocomplete="new-password"
                  maxlength="64"
                  placeholder="请再次输入密码"
                  show-password
                  @keyup.enter="submitRegister"
                />
              </el-form-item>
              <el-button class="auth-submit" type="primary" native-type="submit" :loading="registerBusy">
                创建账户
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>

      <footer class="auth-footer">© 2026 综合农牧业管理系统</footer>
    </section>
  </main>
</template>
