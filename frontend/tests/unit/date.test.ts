import { describe, expect, it } from "vitest";

import { localDateInputValue } from "@/utils/date";


describe("localDateInputValue", () => {
  it("uses the local calendar date for business date fields", () => {
    expect(localDateInputValue(new Date(2026, 7, 16, 0, 30))).toBe("2026-08-16");
  });
});
