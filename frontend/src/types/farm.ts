import type { User } from "./auth";


export type FarmRole = "manager" | "operator" | "viewer";
export type FarmAccessRole = "admin" | FarmRole;

export interface Farm {
  id: number;
  code: string;
  name: string;
  ownerName: string;
  address: string | null;
  timezone: string;
  isActive: boolean;
  memberCount: number;
  accessRole: FarmAccessRole;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FarmMember {
  user: User;
  roleCode: FarmRole;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FarmListData {
  items: Farm[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

export interface FarmListQuery {
  page: number;
  pageSize: number;
  keyword?: string;
  status?: "all" | "active" | "disabled";
}

export interface CreateFarmInput {
  code: string;
  name: string;
  ownerName: string;
  address?: string | null;
}

export interface UpdateFarmInput {
  code?: string;
  name?: string;
  ownerName?: string;
  address?: string | null;
  isActive?: boolean;
}

export type BarnType = "pig" | "chicken" | "isolation" | "other";

export interface Barn {
  id: number;
  farmId: number;
  code: string;
  name: string;
  barnType: BarnType;
  capacity: number;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface Plot {
  id: number;
  farmId: number;
  code: string;
  name: string;
  areaMu: string;
  soilType: string | null;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FarmResourceListQuery {
  farmId: number;
  page: number;
  pageSize: number;
  keyword?: string;
  status?: "all" | "active" | "disabled";
}

export interface FarmResourceListData<T> {
  items: T[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

export interface CreateBarnInput {
  farmId: number;
  code: string;
  name: string;
  barnType: BarnType;
  capacity: number;
}

export interface UpdateBarnInput {
  code?: string;
  name?: string;
  barnType?: BarnType;
  capacity?: number;
  isActive?: boolean;
}

export interface CreatePlotInput {
  farmId: number;
  code: string;
  name: string;
  areaMu: number;
  soilType?: string | null;
}

export interface UpdatePlotInput {
  code?: string;
  name?: string;
  areaMu?: number;
  soilType?: string | null;
  isActive?: boolean;
}
