export interface OverviewSummary {
  registeredUsers: number;
  activeUsers: number;
  recentLogins: number;
  serviceHealthy: boolean;
}

export interface RegistrationTrendPoint {
  month: string;
  count: number;
}

export interface RoleDistributionPoint {
  role: string;
  count: number;
}

export interface SystemOverview {
  summary: OverviewSummary;
  registrationTrend: RegistrationTrendPoint[];
  roleDistribution: RoleDistributionPoint[];
  generatedAt: string;
}

export interface DataResponse<T> {
  success: true;
  data: T;
  requestId: string;
}
