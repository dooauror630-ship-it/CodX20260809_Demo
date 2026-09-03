import { createRouter, createWebHistory } from "vue-router";

import { pinia } from "@/stores";
import { useAuthStore } from "@/stores/auth";


export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/modules/auth/LoginView.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      component: () => import("@/layouts/AppLayout.vue"),
      children: [
        {
          path: "",
          redirect: "/dashboard",
        },
        {
          path: "dashboard",
          name: "dashboard",
          component: () => import("@/modules/dashboard/DashboardView.vue"),
          meta: { title: "工作台" },
        },
        {
          path: "base/farms",
          name: "farms",
          component: () => import("@/modules/farm/FarmManagementView.vue"),
          meta: { title: "农场档案" },
        },
        {
          path: "base/barns",
          name: "barns",
          component: () => import("@/modules/farm/FarmResourceView.vue"),
          props: { resourceKind: "barn" },
          meta: { title: "圈舍管理" },
        },
        {
          path: "base/plots",
          name: "plots",
          component: () => import("@/modules/farm/FarmResourceView.vue"),
          props: { resourceKind: "plot" },
          meta: { title: "地块管理" },
        },
        {
          path: "base/warehouses",
          name: "warehouses",
          component: () => import("@/modules/farm/FarmResourceView.vue"),
          props: { resourceKind: "warehouse" },
          meta: { title: "仓库管理" },
        },
        {
          path: "base/items",
          name: "items",
          component: () => import("@/modules/inventory/ItemManagementView.vue"),
          meta: { title: "物料管理" },
        },
        {
          path: "base/catalogs",
          name: "catalogs",
          component: () => import("@/modules/catalog/CatalogManagementView.vue"),
          meta: { title: "业务字典" },
        },
        {
          path: "inventory/purchases",
          name: "purchases",
          component: () => import("@/modules/inventory/PurchaseManagementView.vue"),
          meta: { title: "采购入库" },
        },
        {
          path: "inventory/stocks",
          name: "stocks",
          component: () => import("@/modules/inventory/InventoryStockView.vue"),
          meta: { title: "库存管理" },
        },
        {
          path: "livestock/pigs",
          name: "pig-livestock",
          component: () => import("@/modules/livestock/PigManagementView.vue"),
          meta: { title: "生猪管理" },
        },
        {
          path: "livestock/chickens",
          name: "chicken-livestock",
          component: () => import("@/modules/livestock/PigManagementView.vue"),
          props: { speciesCode: "CHICKEN" },
          meta: { title: "肉鸡管理" },
        },
        {
          path: "crop/cycles",
          name: "crop-cycles",
          component: () => import("@/modules/crop/CropCycleView.vue"),
          meta: { title: "种植周期" },
        },
        {
          path: "crop/operations",
          name: "field-operations",
          component: () => import("@/modules/crop/FieldOperationView.vue"),
          meta: { title: "农事操作" },
        },
        {
          path: "crop/harvests",
          name: "harvest-batches",
          component: () => import("@/modules/crop/HarvestBatchView.vue"),
          meta: { title: "采收批次" },
        },
        {
          path: "crop/curing",
          name: "tobacco-curing",
          component: () => import("@/modules/crop/TobaccoCuringView.vue"),
          meta: { title: "烟草烘烤" },
        },
        {
          path: "crop/analysis",
          name: "crop-analysis",
          component: () => import("@/modules/crop/CropAnalysisView.vue"),
          meta: { title: "种植分析" },
        },
        {
          path: "admin/users",
          name: "admin-users",
          component: () => import("@/modules/admin/UserManagementView.vue"),
          meta: { title: "用户管理", requiresAdmin: true },
        },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/dashboard",
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia);
  await auth.restore();
  if (!to.meta.public && !auth.user) return { name: "login", query: { redirect: to.fullPath } };
  if (to.name === "login" && auth.user) return { name: "dashboard" };
  if (to.meta.requiresAdmin && !auth.isAdmin) return { name: "dashboard" };
  return true;
});
