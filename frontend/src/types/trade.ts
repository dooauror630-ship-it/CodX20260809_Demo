export interface Customer { id: number; farmId: number; code: string; name: string; contact: string | null; phone: string | null; address: string | null; isActive: boolean; }
export interface SalesOrder { id: number; orderNo: string; customerId: number; customerName: string; saleDate: string; status: "DRAFT" | "POSTED"; totalAmount: string; receivedAmount: string; warehouseId: number; }
export interface TradeSummary { postedSalesAmount: string; salesCost: string; grossProfit: string; receivedAmount: string; cashNetInflow: string; receivableAmount: string; }
