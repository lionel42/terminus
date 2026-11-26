import type { MeasurementType } from "@/client"

export const MEASUREMENT_TYPES: MeasurementType[] = [
  "air",
  "blank",
  "tank",
  "standard",
  "labair",
  "test",
]

/** "2026-01-05T10:00:00Z" -> "2026-01-05 10:00:00" (always shown in UTC). */
export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return ""
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toISOString().replace("T", " ").slice(0, 19)
}

/** Value for an <input type="datetime-local">, in UTC. */
export function toDatetimeInput(iso: string | null | undefined): string {
  return iso ? new Date(iso).toISOString().slice(0, 19) : ""
}

/** <input type="datetime-local"> value, interpreted as UTC -> ISO string. */
export function fromDatetimeInput(value: string): string {
  const withSeconds = value.length === 16 ? `${value}:00` : value
  return `${withSeconds}Z`
}

/** <input type="date"> value -> start / end of that day in UTC. */
export const dayStartUtc = (day: string) => `${day}T00:00:00Z`
export const dayEndUtc = (day: string) => `${day}T23:59:59Z`

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return ""
  // 6 significant digits, without padding zeros (4.77, not 4.77000)
  return String(Number(value.toPrecision(6)))
}

/** Keep only defined, non-empty values (for API query parameters). */
export function compact<T extends Record<string, unknown>>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(
      ([, v]) => v !== undefined && v !== null && v !== "",
    ),
  ) as Partial<T>
}
