import type { ProductionStockOperation } from "@/types/purchase";

export type LivestockBatchStatus = "ACTIVE" | "CLOSED";
export type LivestockMovementType = "ENTRY" | "TRANSFER" | "DEATH" | "CULL" | "EXIT";
export type WritableLivestockMovementType = Exclude<LivestockMovementType, "ENTRY">;
export type LivestockHealthType = "VACCINATION" | "MEDICATION" | "DISEASE" | "OTHER";

export interface LivestockHealthRecord {
  id: number;
  farmId: number;
  batchId: number;
  recordNo: string;
  recordType: LivestockHealthType;
  occurredOn: string;
  description: string;
  medicineName: string | null;
  dosage: string | null;
  notes: string | null;
  createdById: number;
  createdAt: string | null;
}

export interface LivestockWeightRecord {
  id: number;
  farmId: number;
  batchId: number;
  recordNo: string;
  occurredOn: string;
  sampleCount: number;
  averageWeight: string;
  notes: string | null;
  createdById: number;
  createdAt: string | null;
}

export interface LivestockProductionSummary {
  totalFeedCost: string;
  latestAverageWeight: string | null;
  latestWeightDate: string | null;
  adg: string | null;
  healthRecordCount: number;
}

export interface LivestockBarnBalance {
  barnId: number;
  barnCode: string;
  barnName: string;
  barnCapacity: number;
  headCount: number;
}

export interface LivestockMovement {
  id: number;
  farmId: number;
  batchId: number;
  movementNo: string;
  movementType: LivestockMovementType;
  fromBarnId: number | null;
  fromBarnCode: string | null;
  fromBarnName: string | null;
  toBarnId: number | null;
  toBarnCode: string | null;
  toBarnName: string | null;
  quantity: number;
  occurredOn: string;
  reason: string | null;
  notes: string | null;
  createdById: number;
  createdAt: string | null;
}

export interface LivestockBatch {
  id: number;
  farmId: number;
  speciesId: number;
  speciesCode: string;
  speciesName: string;
  batchNo: string;
  name: string;
  entryDate: string;
  source: string | null;
  status: LivestockBatchStatus;
  closedAt: string | null;
  notes: string | null;
  initialCount: number;
  currentHeadCount: number;
  deathCount: number;
  cullCount: number;
  exitCount: number;
  movementCount: number;
  barnBalances: LivestockBarnBalance[];
  movements?: LivestockMovement[];
  healthRecords?: LivestockHealthRecord[];
  weightRecords?: LivestockWeightRecord[];
  feedingRecords?: ProductionStockOperation[];
  productionSummary?: LivestockProductionSummary;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface LivestockSummary {
  activeBatchCount: number;
  currentHeadCount: number;
  deathCount: number;
  exitedCount: number;
}

export interface LivestockBatchListData {
  items: LivestockBatch[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
  summary: LivestockSummary;
}

export interface LivestockBatchListQuery {
  farmId: number;
  page: number;
  pageSize: number;
  keyword?: string;
  status?: "all" | LivestockBatchStatus;
}

export interface CreateLivestockBatchInput {
  farmId: number;
  speciesId: number;
  batchNo: string;
  name: string;
  entryNo: string;
  entryDate: string;
  barnId: number;
  initialCount: number;
  source?: string | null;
  notes?: string | null;
}

export interface CreateLivestockMovementInput {
  farmId: number;
  batchId: number;
  movementNo: string;
  movementType: WritableLivestockMovementType;
  occurredOn: string;
  fromBarnId: number;
  toBarnId?: number | null;
  quantity: number;
  reason?: string | null;
  notes?: string | null;
}

export interface CreateLivestockHealthRecordInput {
  farmId: number;
  batchId: number;
  recordNo: string;
  recordType: LivestockHealthType;
  occurredOn: string;
  description: string;
  medicineName?: string | null;
  dosage?: string | null;
  notes?: string | null;
}

export interface CreateLivestockWeightRecordInput {
  farmId: number;
  batchId: number;
  recordNo: string;
  occurredOn: string;
  sampleCount: number;
  averageWeight: number;
  notes?: string | null;
}
