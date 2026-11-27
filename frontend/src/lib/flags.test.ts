import { describe, expect, it } from "vitest"

import { flagLabel, setFlags, UNUSABLE_FLAGS } from "./flags"

const INFOS = [
  { name: "INVALID", value: 1, description: "Rejected", unusable: true },
  { name: "AUTO_REJECTED", value: 2, description: "Auto", unusable: true },
  { name: "SUSPECT", value: 4, description: "Questionable", unusable: false },
]

describe("flags", () => {
  it("lists the set bits in order", () => {
    expect(setFlags(5, INFOS).map((f) => f.name)).toEqual([
      "INVALID",
      "SUSPECT",
    ])
    expect(setFlags(0, INFOS)).toEqual([])
    expect(setFlags(64, INFOS)).toEqual([]) // unknown bit
  })

  it("labels flags in words", () => {
    expect(flagLabel(INFOS[1])).toBe("auto rejected")
  })

  it("matches the unusable flags of the server", () => {
    const unusable = INFOS.filter((f) => f.unusable).reduce(
      (m, f) => m | f.value,
      0,
    )
    expect(UNUSABLE_FLAGS).toBe(unusable)
  })
})
