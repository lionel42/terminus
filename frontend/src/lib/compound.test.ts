import { describe, expect, it } from "vitest"

import {
  compoundName,
  isValidCas,
  nistUrl,
  pubchemUrl,
  wikipediaUrl,
} from "./compound"

describe("isValidCas", () => {
  it.each(["75-69-4", "7732-18-5", "74-82-8", "2551-62-4"])(
    "accepts %s",
    (cas) => {
      expect(isValidCas(cas)).toBe(true)
    },
  )

  it.each([
    "75-69-5", // wrong check digit
    "7569-4",
    "75-69-44",
    "1-69-4", // first part needs 2 digits
    "75-69-4 ",
    "CFC-11",
    "",
  ])("rejects %j", (cas) => {
    expect(isValidCas(cas)).toBe(false)
  })
})

describe("compoundName", () => {
  it("prefers the industrial name, then the IUPAC name", () => {
    expect(
      compoundName({ id: "x", industrial_name: "CFC-11", iupac_name: "y" }),
    ).toBe("CFC-11")
    expect(compoundName({ id: "x", iupac_name: "methane" })).toBe("methane")
    expect(compoundName({ id: "x", industrial_name: "" })).toBeNull()
    expect(compoundName(undefined)).toBeNull()
  })
})

describe("links", () => {
  it("links PubChem by CID, else searches by CAS, name or id", () => {
    expect(pubchemUrl({ id: "cfc11", pubchem_cid: 6389 })).toBe(
      "https://pubchem.ncbi.nlm.nih.gov/compound/6389",
    )
    expect(pubchemUrl({ id: "cfc11", cas_number: "75-69-4" })).toBe(
      "https://pubchem.ncbi.nlm.nih.gov/#query=75-69-4",
    )
    expect(
      pubchemUrl({ id: "x", iupac_name: "trichloro(fluoro)methane" }),
    ).toBe("https://pubchem.ncbi.nlm.nih.gov/#query=trichloro(fluoro)methane")
    expect(pubchemUrl({ id: "sf6" })).toContain("#query=sf6")
  })

  it("links Wikipedia through Wikidata when known, else searches", () => {
    expect(wikipediaUrl({ id: "cfc11", wikidata_id: "Q423000" })).toBe(
      "https://www.wikidata.org/wiki/Special:GoToLinkedPage/enwiki/Q423000",
    )
    const search = new URL(
      wikipediaUrl({ id: "x", industrial_name: "HFC-134a" }),
    )
    expect(search.hostname).toBe("en.wikipedia.org")
    expect(search.searchParams.get("search")).toBe("HFC-134a")
    expect(search.searchParams.get("go")).toBe("Go")
  })

  it("encodes names in URLs", () => {
    const url = wikipediaUrl({ id: "x", iupac_name: "a&b c" })
    expect(url).toContain("search=a%26b%20c")
    expect(nistUrl("75-69-4")).toBe(
      "https://webbook.nist.gov/cgi/cbook.cgi?ID=75-69-4&Units=SI",
    )
  })
})
