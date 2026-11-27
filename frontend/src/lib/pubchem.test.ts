import { afterEach, describe, expect, it, vi } from "vitest"

import fixture from "./__fixtures__/pubchem-cfc11.json"
import {
  fetchPubChem,
  findCid,
  parseCelsius,
  pubchemFormValues,
} from "./pubchem"

describe("parseCelsius", () => {
  it.each([
    ["23.7 °C", 23.7],
    ["-161.5 °C", -161.5],
    ["23.7 °C @760 [mm Hg]", 23.7],
    ["74.7 °F at 760 mmHg (NTP, 1992)", 23.72],
    ["-40.9 °F at 760 mmHg (USCG, 1999)", -40.5],
    ["111.4 K", -161.75],
    ["75 °f", 23.89],
    // A range keeps its lower bound
    ["-162 to -160 °C", -162],
  ])("%s -> %s", (text, expected) => {
    expect(parseCelsius(text)).toBe(expected)
  })

  it.each(["", "decomposes", "760 mmHg", "about 24", "101.3 kPa", "24 KPa"])(
    "%s -> null",
    (text) => {
      expect(parseCelsius(text)).toBeNull()
    },
  )
})

/** Fake fetch answering from the recorded responses, by URL. */
function mockFetch(overrides: Record<string, unknown> = {}) {
  const routes: [RegExp, unknown][] = [
    [/\/compound\/name\/.+\/cids\//, { IdentifierList: { CID: [6389] } }],
    [/\/property\//, fixture.properties],
    [/\/synonyms\//, fixture.synonyms],
    [/pug_view\/.*Boiling/, fixture.boilingPoint],
    [/wikidata\.org/, fixture.wikidataSearch],
  ]
  const fetchMock = vi.fn(async (url: string) => {
    for (const [pattern, body] of Object.entries(overrides)) {
      if (url.includes(pattern)) {
        return body === 404
          ? new Response("", { status: 404 })
          : Response.json(body)
      }
    }
    const match = routes.find(([re]) => re.test(url))
    if (!match) return new Response("", { status: 404 })
    return Response.json(match[1])
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("findCid", () => {
  it("returns a given CID without any request", async () => {
    const fetchMock = mockFetch()
    expect(await findCid({ cid: 42, names: ["x"] })).toBe(42)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("tries the names in order, skipping empty ones", async () => {
    const fetchMock = mockFetch({ "/name/unknown/": 404 })
    const cid = await findCid({ names: ["", null, "unknown", "75-69-4"] })
    expect(cid).toBe(6389)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1][0]).toContain("/compound/name/75-69-4/")
  })

  it("returns null when nothing matches", async () => {
    mockFetch({ "/cids/": 404 })
    expect(await findCid({ names: ["nothing"] })).toBeNull()
  })
})

describe("fetchPubChem", () => {
  it("reads properties, CAS, industrial name, Wikidata and boiling points", async () => {
    mockFetch()
    const data = await fetchPubChem(6389)
    expect(data).toMatchObject({
      pubchem_cid: 6389,
      iupac_name: "trichloro(fluoro)methane",
      formula: "CCl3F",
      molar_mass: 137.36,
      inchikey: "CYRMSUTZVYGINF-UHFFFAOYSA-N",
      cas_number: "75-69-4",
      industrial_name: "CFC-11",
      wikidata_id: "Q423000",
    })
    expect(data.boiling_points.length).toBeGreaterThanOrEqual(4)
    const hsdb = data.boiling_points.find((p) => p.source.includes("HSDB"))
    expect(hsdb).toMatchObject({ temperature_c: 23.7, note: "23.7 °C" })
    expect(hsdb?.reference_url).toMatch(/^https:\/\//)
    const cameo = data.boiling_points.find((p) => p.source.includes("CAMEO"))
    expect(cameo?.temperature_c).toBe(23.72) // converted from °F
    for (const point of data.boiling_points) {
      expect(point.source.startsWith("PubChem: ")).toBe(true)
    }
  })

  it("works without boiling points and without Wikidata", async () => {
    mockFetch({ pug_view: 404, "wikidata.org": 404 })
    const data = await fetchPubChem(6389)
    expect(data.boiling_points).toEqual([])
    expect(data.wikidata_id).toBeNull()
  })

  it("survives a Wikidata network error", async () => {
    const fetchMock = mockFetch()
    const inner = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation(async (url: string) => {
      if (url.includes("wikidata.org")) throw new TypeError("Failed to fetch")
      return inner(url)
    })
    expect((await fetchPubChem(6389)).wikidata_id).toBeNull()
  })

  it("fails clearly for an unknown CID", async () => {
    mockFetch({ "/property/": 404 })
    await expect(fetchPubChem(1)).rejects.toThrow("no compound with CID 1")
  })

  it("reports PubChem errors", async () => {
    const fetchMock = mockFetch()
    fetchMock.mockResolvedValue(new Response("", { status: 503 }))
    await expect(fetchPubChem(6389)).rejects.toThrow("(503)")
  })
})

describe("pubchemFormValues", () => {
  it("turns the record into string form values, skipping missing ones", async () => {
    mockFetch({ "wikidata.org": 404 })
    const values = pubchemFormValues(await fetchPubChem(6389))
    expect(values).toMatchObject({
      pubchem_cid: "6389",
      molar_mass: "137.36",
      cas_number: "75-69-4",
    })
    expect(values).not.toHaveProperty("wikidata_id")
    expect(values).not.toHaveProperty("boiling_points")
  })
})
