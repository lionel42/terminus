import { describe, expect, it } from "vitest"

import { toApiFilters } from "@/components/Domain/MeasurementFilters"
import {
  compact,
  formatNumber,
  formatUtc,
  fromDatetimeInput,
  toDatetimeInput,
} from "./format"

describe("UTC date helpers", () => {
  it("formats any ISO time in UTC", () => {
    expect(formatUtc("2026-01-05T10:00:00Z")).toBe("2026-01-05 10:00:00")
    expect(formatUtc("2026-01-05T11:00:00+01:00")).toBe("2026-01-05 10:00:00")
    expect(formatUtc(null)).toBe("")
    expect(formatUtc("garbage")).toBe("garbage")
  })

  it("round-trips datetime-local inputs as UTC", () => {
    const input = toDatetimeInput("2026-01-05T11:00:00+01:00")
    expect(input).toBe("2026-01-05T10:00:00")
    expect(fromDatetimeInput(input)).toBe("2026-01-05T10:00:00Z")
    expect(fromDatetimeInput("2026-01-05T10:00")).toBe("2026-01-05T10:00:00Z")
    expect(toDatetimeInput(undefined)).toBe("")
  })
})

describe("formatNumber", () => {
  it.each([
    [4.77, "4.77"],
    [1950.123456, "1950.12"],
    [0.000123456789, "0.000123457"],
    [123456789, "123457000"],
    [0, "0"],
  ])("%s -> %s", (value, expected) => {
    expect(formatNumber(value)).toBe(expected)
  })

  it("shows nothing for missing values", () => {
    expect(formatNumber(null)).toBe("")
    expect(formatNumber(undefined)).toBe("")
  })
})

describe("compact", () => {
  it("drops undefined, null and empty strings but keeps 0 and false", () => {
    expect(
      compact({ a: undefined, b: null, c: "", d: 0, e: false, f: "x" }),
    ).toEqual({ d: 0, e: false, f: "x" })
  })
})

describe("toApiFilters", () => {
  it("maps URL search params to API query parameters (whole UTC days)", () => {
    expect(
      toApiFilters({
        instrument_id: "medusa",
        type: "air",
        from: "2026-10-10",
        to: "2026-10-12",
        page: 3,
      }),
    ).toEqual({
      instrument_id: "medusa",
      type: "air",
      measured_from: "2026-10-10T00:00:00Z",
      measured_to: "2026-10-12T23:59:59Z",
    })
    expect(toApiFilters({})).toEqual({})
  })
})
