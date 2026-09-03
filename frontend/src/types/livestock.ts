import type { ProductionStockOperation } from "@/types/purchase";

export type LivestockBatchStatus = "ACTIVE" | "CLOSED";
export type LivestockMovementType = "ENTRY" | "TRANSFER" | "DEATH" | "CULL" | "EXIT";
export type WritableLivestockMovementType = Exclude<LivestockMovementType, "ENTRY">;
export type LivestockHealthType = "VACCINATION" | "MEDICATION" | "DISEASE" | "OTHER";
export type LivestockCostType = "ENTRY" | "LABOR" | "OVERHEAD" | "OTHER";
export type LivestockCostStatus = "POSTED" | "CANCELLED";

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
  totalDirectCost: string;
  costPerHead: string | null;
  costPerHeadBasis: "EXITED" | "CURRENT_ESTIMATE" | null;
  totalAdditionalCost: string;
  totalProductionCost: string;
  productionCostPerHead: string | null;
  productionCostPerHeadBasis: "EXITED" | "CURRENT_ESTIMATE" | null;
  additionalCostBreakdown: LivestockAdditionalCostBreakdown[];
  costBreakdown: LivestockCostBreakdown[];
  totalFeedWeightKg: string;
  latestAverageWeight: string | null;
  latestWeightDate: string | null;
  adg: string | null;
  estimatedWeightGainKg: string | null;
  fcr: string | null;
  fcrEstimated: boolean;
  feedWeightComplete: boolean;
  healthRecordCount: number;
}

export interface LivestockAdditionalCostBreakdown {
  costType: LivestockCostType;
  amount: string;
  recordCount: number;
}

export interface LivestockCostEntry {
  id: number;
  farmId: number;
  batchId: number;
  entryNo: string;
  businessDate: string;
  costType: LivestockCostType;
  amount: string;
  description: string;
  notes: string | null;
  status: LivestockCostStatus;
  cancelledAt: string | null;
  cancelledById: number | null;
  createdById: number;
  createdAt: string | null;
}

export interface LivestockCostBreakdown {
  category: "feed" | "veterinary_drug" | "supply" | "other";
  amount: string;
  recordCount: number;
}

export interface LivestockProductionTrendPoint {
  date: string;
  headCount: number;
  averageWeight: string | null;
  sampleCount: number | null;
  dailyDirectCost: string;
  cumulativeDirectCost: string;
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
  materialRecords?: ProductionStockOperation[];
  costEntries?: LivestockCostEntry[];
  productionTrend?: LivestockProductionTrendPoint[];
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

export interface LivestockAnalysisSummary {
  activeBatchCount: number;
  currentHeadCount: number;
  entryCount: number;
  deathCount: number;
  mortalityRate: string;
}

export interface LivestockFarmTrendPoint {
  date: string;
  currentHeadCount: number;
  deathCount: number;
}

export interface LivestockBatchComparison {
  batchId: number;
  batchNo: string;
  name: string;
  status: LivestockBatchStatus;
  entryDate: string;
  initialCount: number;
  currentHeadCount: number;
  deathCount: number;
  mortalityRate: string;
  latestAverageWeight: string | null;
  adg: string | null;
  fcr: string | null;
  fcrEstimated: boolean;
  directCost: string;
  costPerHead: string | null;
  productionCost: string;
  productionCostPerHead: string | null;
}

export interface LivestockAnalysis {
  summary: LivestockAnalysisSummary;
  trend: LivestockFarmTrendPoint[];
  batchComparisons: LivestockBatchComparison[];
  period: {
    dateFrom: string;
    dateTo: string;
    trendDays: number;
  };
  generatedAt: string;
}

export interface LivestockAnalysisQuery {
  farmId: number;
  trendDays?: number;
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

export interface CreateLivestockCostEntryInput {
  farmId: number;
  batchId: number;
  entryNo: string;
  businessDate: string;
  costType: LivestockCostType;
  amount: number;
  description: string;
  notes?: string | null;
}
