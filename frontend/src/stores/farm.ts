import { defineStore } from "pinia";

import { getFarms } from "@/api/farms";
import { useAuthStore } from "@/stores/auth";
import type { Farm } from "@/types/farm";


function storageKey(userId: number) {
  return `agri.currentFarm.${userId}`;
}

export const useFarmStore = defineStore("farm", {
  state: () => ({
    farms: [] as Farm[],
    currentFarmId: null as number | null,
    loading: false,
    loadedForUserId: null as number | null,
  }),
  getters: {
    currentFarm: (state) => state.farms.find((farm) => farm.id === state.currentFarmId) ?? null,
  },
  actions: {
    async load(force = false) {
      const userId = useAuthStore().user?.id;
      if (!userId) {
        this.reset();
        return;
      }
      if (!force && this.loadedForUserId === userId) return;

      this.loading = true;
      try {
        const data = await getFarms({ page: 1, pageSize: 100, status: "active" });
        this.farms = data.items;
        this.loadedForUserId = userId;
        const savedId = Number(localStorage.getItem(storageKey(userId)));
        const preferredId = this.currentFarmId ?? savedId;
        this.select(this.farms.some((farm) => farm.id === preferredId) ? preferredId : this.farms[0]?.id ?? null);
      } finally {
        this.loading = false;
      }
    },
    select(farmId: number | null) {
      this.currentFarmId = farmId;
      const userId = useAuthStore().user?.id;
      if (!userId) return;
      if (farmId === null) localStorage.removeItem(storageKey(userId));
      else localStorage.setItem(storageKey(userId), String(farmId));
    },
    reset() {
      this.farms = [];
      this.currentFarmId = null;
      this.loadedForUserId = null;
      this.loading = false;
    },
  },
});
