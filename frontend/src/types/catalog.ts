export interface Unit {
  id: number;
  code: string;
  name: string;
  dimension: string;
  baseFactor: string;
  scale: number;
  isActive: boolean;
}

export interface LivestockSpecies {
  id: number;
  code: string;
  name: string;
  trackingMode: string;
  isActive: boolean;
}

export interface CropVariety {
  id: number;
  cropTypeId: number;
  code: string;
  name: string;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface CropType {
  id: number;
  code: string;
  name: string;
  isActive: boolean;
  varieties: CropVariety[];
}

export interface CatalogData {
  units: Unit[];
  livestockSpecies: LivestockSpecies[];
  cropTypes: CropType[];
}

export interface CreateCropVarietyInput {
  cropTypeId: number;
  code: string;
  name: string;
}

export interface UpdateCropVarietyInput {
  cropTypeId?: number;
  code?: string;
  name?: string;
  isActive?: boolean;
}
