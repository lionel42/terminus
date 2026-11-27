import type { FlagInfo } from "@/client"

/**
 * Bits that make a value unusable (INVALID | AUTO_REJECTED), for the
 * `exclude_flags` filter. A constant, so the filter needs no request first;
 * it mirrors UNUSABLE of backend/app/models/flags.py, which the backend test
 * `test_unusable_flags_of_the_frontend` pins: change both together.
 */
export const UNUSABLE_FLAGS = 0b11

/** The flags set in the bit mask `flags`, in bit order. */
export function setFlags(flags: number, infos: FlagInfo[]): FlagInfo[] {
  return infos.filter((info) => (flags & info.value) !== 0)
}

/** "AUTO_REJECTED" -> "auto rejected" */
export function flagLabel(info: FlagInfo): string {
  return info.name.toLowerCase().replace(/_/g, " ")
}
