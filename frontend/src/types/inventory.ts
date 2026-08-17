export interface Warehouse {
  id: number;
  farmId: number;
  code: string;
  name: string;
  location: string | null;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface ItemCategory {
  id: number;
  farmId: number;
  parentId: number | null;
  parentName: string | null;
  code: string;
  name: string;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export type ItemType =
  | "feed"
  | "veterinary_drug"
  | "seed"
  | "fertilizer"
  | "pesticide"
  | "product"
  | "supply"
  | "other";

export interface Item {
  id: number;
  farmId: number;
  categoryId: number;
  categoryName: string;
  unitId: number;
  unitName: string;
  unitCode: string;
  code: string;
  name: string;
  itemType: ItemType;
  safetyStock: string;
  lotTracking: boolean;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface ResourceListQuery {
  farmId: number;
  page: number;
  pageSize: number;
  keyword?: string;
  status?: "all" | "active" | "disabled";
}

export interface ResourceListData<T> {
  items: T[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

export interface CreateWarehouseInput {
  farmId: number;
  code: string;
  name: string;
  location?: string | null;
}

export interface UpdateWarehouseInput {
  code?: string;
  name?: string;
  location?: string | null;
  isActive?: boolean;
}

export interface CategoryListQuery {
  farmId: number;
  keyword?: string;
  status?: "all" | "active" | "disabled";
}

export interface CreateCategoryInput {
  farmId: number;
  parentId?: number | null;
  code: string;
  name: string;
}

export interface UpdateCategoryInput {
  parentId?: number | null;
  code?: string;
  name?: string;
  isActive?: boolean;
}

export interface ItemListQuery extends ResourceListQuery {
  categoryId?: number;
}

export interface CreateItemInput {
  farmId: number;
  categoryId: number;
  unitId: number;
  code: string;
  name: string;
  itemType: ItemType;
  safetyStock: number;
  lotTracking: boolean;
}

export interface UpdateItemInput {
  categoryId?: number;
  unitId?: number;
  code?: string;
  name?: string;
  itemType?: ItemType;
  safetyStock?: number;
  lotTracking?: boolean;
  isActive?: boolean;
}
