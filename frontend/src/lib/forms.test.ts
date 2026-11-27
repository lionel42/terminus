import { describe, expect, it } from "vitest"

import { buildSchema, type FieldConfig, NONE, toBody } from "./forms"

const fields: FieldConfig[] = [
  { name: "id", label: "Id", type: "id", required: true },
  { name: "name", label: "Name" },
  { name: "measured_at", label: "Measured at", type: "datetime" },
  { name: "mass", label: "Mass", type: "number" },
  { name: "status", label: "Status", type: "select" },
]

const empty = { id: "", name: "", measured_at: "", mass: "", status: "" }

describe("toBody", () => {
  it("lower-cases ids, converts datetimes to UTC and numbers", () => {
    expect(
      toBody(fields, {
        id: " CFC11 ",
        name: "  Freon ",
        measured_at: "2026-10-01T12:30",
        mass: "137.36",
        status: "measured",
      }),
    ).toEqual({
      id: "cfc11",
      name: "Freon",
      measured_at: "2026-10-01T12:30:00Z",
      mass: 137.36,
      status: "measured",
    })
  })

  it("sends null for empty values and the 'none' select option", () => {
    expect(toBody(fields, { ...empty, name: "   ", status: NONE })).toEqual({
      id: null,
      name: null,
      measured_at: null,
      mass: null,
      status: null,
    })
  })

  it("keeps seconds of datetimes and ignores unknown values", () => {
    const body = toBody(fields, {
      ...empty,
      measured_at: "2026-10-01T12:30:15",
      other: "x",
    })
    expect(body.measured_at).toBe("2026-10-01T12:30:15Z")
    expect(body).not.toHaveProperty("other")
  })
})

describe("buildSchema", () => {
  const schema = buildSchema(fields)
  const errors = (values: Record<string, string>) => {
    const result = schema.safeParse(values)
    return result.success
      ? {}
      : Object.fromEntries(
          result.error.issues.map((i) => [String(i.path[0]), i.message]),
        )
  }

  it("accepts valid values", () => {
    expect(errors({ ...empty, id: "Abc123", mass: "-1.5e3" })).toEqual({})
  })

  it("requires required fields", () => {
    expect(errors(empty)).toEqual({ id: "Id is required" })
    expect(errors({ ...empty, id: "   " })).toEqual({ id: "Id is required" })
  })

  it("restricts ids to letters and digits", () => {
    expect(errors({ ...empty, id: "cfc-11" })).toEqual({
      id: "Only letters and digits",
    })
  })

  it("checks numbers", () => {
    expect(errors({ ...empty, id: "a", mass: "12 g" })).toEqual({
      mass: "Must be a number",
    })
  })
})
