import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getFarms } from "@/api/farms";
import { useAuthStore } from "@/stores/auth";
import { useFarmStore } from "@/stores/farm";
import type { Farm } from "@/types/farm";


vi.mock("@/api/farms", () => ({ getFarms: vi.fn() }));

const farms: Farm[] = [
  {
    id: 1,
    code: "FARM-001",
    name: "一号农场",
    ownerName: "负责人甲",
    address: null,
    timezone: "Asia/Shanghai",
    isActive: true,
    memberCount: 1,
    accessRole: "operator",
    createdAt: null,
    updatedAt: null,
  },
  {
    id: 2,
    code: "FARM-002",
    name: "二号农场",
    ownerName: "负责人乙",
    address: null,
    timezone: "Asia/Shanghai",
    isActive: true,
    memberCount: 1,
    accessRole: "viewer",
    createdAt: null,
    updatedAt: null,
  },
];

function setCurrentUser() {
  useAuthStore().user = {
    id: 9,
    username: "farm_user",
    displayName: "农场用户",
    role: "operator",
    isActive: true,
    createdAt: null,
    lastLoginAt: null,
  };
}

describe("farm store", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    vi.mocked(getFarms).mockResolvedValue({
      items: farms,
      pagination: { page: 1, pageSize: 100, total: 2, totalPages: 1 },
    });
    setActivePinia(createPinia());
    setCurrentUser();
  });

  it("restores a valid farm selection for the current user", async () => {
    const store = useFarmStore();
    await store.load();
    expect(store.currentFarm?.id).toBe(1);

    store.select(2);
    setActivePinia(createPinia());
    setCurrentUser();
    const restored = useFarmStore();
    await restored.load();

    expect(restored.currentFarm?.id).toBe(2);
    expect(getFarms).toHaveBeenCalledWith({ page: 1, pageSize: 100, status: "active" });
  });
});
