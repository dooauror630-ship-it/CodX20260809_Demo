import { apiClient } from "./client";
import type {
  CategoryListQuery,
  CreateCategoryInput,
  CreateItemInput,
  CreateWarehouseInput,
  Item,
  ItemCategory,
  ItemListQuery,
  ResourceListData,
  ResourceListQuery,
  UpdateCategoryInput,
  UpdateItemInput,
  UpdateWarehouseInput,
  Warehouse,
} from "@/types/inventory";


interface DataResponse<T> {
  success: true;
  data: T;
  message?: string;
  requestId: string;
}

export async function getWarehouses(query: ResourceListQuery) {
  return (
    await apiClient.get<DataResponse<ResourceListData<Warehouse>>>("/warehouses", { params: query })
  ).data.data;
}

export async function createWarehouse(input: CreateWarehouseInput) {
  return (
    await apiClient.post<DataResponse<{ warehouse: Warehouse }>>("/warehouses", input)
  ).data.data.warehouse;
}

export async function updateWarehouse(warehouseId: number, input: UpdateWarehouseInput) {
  return (
    await apiClient.patch<DataResponse<{ warehouse: Warehouse }>>(`/warehouses/${warehouseId}`, input)
  ).data.data.warehouse;
}

export async function getItemCategories(query: CategoryListQuery) {
  return (
    await apiClient.get<DataResponse<{ items: ItemCategory[] }>>("/item-categories", { params: query })
  ).data.data.items;
}

export async function createItemCategory(input: CreateCategoryInput) {
  return (
    await apiClient.post<DataResponse<{ category: ItemCategory }>>("/item-categories", input)
  ).data.data.category;
}

export async function updateItemCategory(categoryId: number, input: UpdateCategoryInput) {
  return (
    await apiClient.patch<DataResponse<{ category: ItemCategory }>>(`/item-categories/${categoryId}`, input)
  ).data.data.category;
}

export async function getItems(query: ItemListQuery) {
  return (
    await apiClient.get<DataResponse<ResourceListData<Item>>>("/items", { params: query })
  ).data.data;
}

export async function createItem(input: CreateItemInput) {
  return (await apiClient.post<DataResponse<{ item: Item }>>("/items", input)).data.data.item;
}

export async function updateItem(itemId: number, input: UpdateItemInput) {
  return (await apiClient.patch<DataResponse<{ item: Item }>>(`/items/${itemId}`, input)).data.data.item;
}
