/** Pure logic of the config-driven forms (see EntityFormDialog). */
import { z } from "zod"

import { fromDatetimeInput } from "@/lib/format"

export type FieldConfig = {
  name: string
  label: string
  /** "id": lower-case alphanumeric identifier; "datetime": entered in UTC */
  type?: "text" | "id" | "datetime" | "select" | "number"
  required?: boolean
  placeholder?: string
  description?: string
  options?: { value: string; label: string }[]
}

export type FormValues = Record<string, string>
export type Body = Record<string, string | number | null>

export type FillAction = {
  label: string
  /** Returns values for some fields; only empty fields are filled. */
  run: (values: FormValues) => Promise<Partial<FormValues>>
}

/** Select value meaning "no value" (sent as null) */
export const NONE = "__none__"

/** Zod schema validating the (string) form values. */
export function buildSchema(fields: FieldConfig[]) {
  const shape: Record<string, z.ZodType<string>> = {}
  for (const field of fields) {
    let schema = z.string().trim()
    if (field.type === "id") {
      schema = schema.regex(/^[A-Za-z0-9]*$/, {
        message: "Only letters and digits",
      })
    } else if (field.type === "number") {
      schema = schema.refine((v) => v === "" || Number.isFinite(Number(v)), {
        message: "Must be a number",
      })
    }
    shape[field.name] = field.required
      ? schema.min(1, { message: `${field.label} is required` })
      : schema
  }
  return z.object(shape)
}

/** Form values -> API body: ids lower-cased, datetimes as UTC ISO, "" -> null. */
export function toBody(fields: FieldConfig[], values: FormValues) {
  const body: Body = {}
  for (const field of fields) {
    const value = values[field.name]?.trim() ?? ""
    if (!value || value === NONE) {
      body[field.name] = null
    } else if (field.type === "id") {
      body[field.name] = value.toLowerCase()
    } else if (field.type === "datetime") {
      body[field.name] = fromDatetimeInput(value)
    } else if (field.type === "number") {
      body[field.name] = Number(value)
    } else {
      body[field.name] = value
    }
  }
  return body
}
