import { describe, expect, it } from "vitest";

import { buildRegistrationTrendOption } from "@/modules/dashboard/chartOptions";
import { buildInventoryTrendOption } from "@/modules/inventory/inventoryChartOptions";


describe("buildRegistrationTrendOption", () => {
  it("keeps month order and renders an empty message only for all-zero data", () => {
    const populated = buildRegistrationTrendOption([
      { month: "2026-07", count: 1 },
      { month: "2026-08", count: 2 },
    ]) as Record<string, unknown>;
    const xAxis = populated.xAxis as { data: string[] };
    const series = populated.series as Array<{ data: number[] }>;

    expect(xAxis.data).toEqual(["2026-07", "2026-08"]);
    expect(series[0].data).toEqual([1, 2]);
    expect(populated.graphic).toEqual([]);

    const empty = buildRegistrationTrendOption([{ month: "2026-08", count: 0 }]) as Record<string, unknown>;
    expect(empty.graphic).toHaveLength(1);
  });
});

describe("buildInventoryTrendOption", () => {
  it("keeps day order and converts API money strings into chart values", () => {
    const option = buildInventoryTrendOption([
      { date: "2026-08-15", inboundAmount: "12.50", outboundAmount: "0.00" },
      { date: "2026-08-16", inboundAmount: "0.00", outboundAmount: "3.25" },
    ]) as Record<string, unknown>;
    const xAxis = option.xAxis as { data: string[] };
    const series = option.series as Array<{ data: number[] }>;

    expect(xAxis.data).toEqual(["08-15", "08-16"]);
    expect(series[0].data).toEqual([12.5, 0]);
    expect(series[1].data).toEqual([0, 3.25]);
    expect(option.graphic).toEqual([]);

    const empty = buildInventoryTrendOption([
      { date: "2026-08-16", inboundAmount: "0.00", outboundAmount: "0.00" },
    ]) as Record<string, unknown>;
    expect(empty.graphic).toHaveLength(1);
  });
});
