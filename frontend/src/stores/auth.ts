import { defineStore } from "pinia";

import * as authApi from "@/api/auth";
import type { LoginInput, RegisterInput, User } from "@/types/auth";


export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null as User | null,
    initialized: false,
  }),
  getters: {
    isAdmin: (state) => state.user?.role === "admin",
    identityLabel: (state) => state.user?.role === "admin" ? "管理员" : "普通用户",
  },
  actions: {
    async restore() {
      if (this.initialized) return this.user;
      try {
        const response = await authApi.restoreSession();
        this.user = response.user ?? null;
      } catch {
        this.user = null;
      } finally {
        this.initialized = true;
      }
      return this.user;
    },
    async login(input: LoginInput) {
      const response = await authApi.login(input);
      this.user = response.user ?? null;
      this.initialized = true;
      return response;
    },
    async register(input: RegisterInput) {
      const response = await authApi.register(input);
      this.user = response.user ?? null;
      this.initialized = true;
      return response;
    },
    async logout() {
      await authApi.logout();
      this.user = null;
      this.initialized = true;
    },
  },
});
