/**
 * Lookups in PubChem (and Wikidata), straight from the browser: both APIs
 * allow cross-origin requests, so nothing goes through our backend.
 * Aliases are deliberately not imported: PubChem lists hundreds of trade
 * names per compound. Synonyms are only scanned for the CAS number and the
 * industrial designation (CFC-11, HFC-134a, ...).
 */
import { isValidCas } from "@/lib/compound"

const PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
const PUG_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
const PROPERTIES =
  "IUPACName,MolecularFormula,MolecularWeight,SMILES,InChI,InChIKey"

const INDUSTRIAL_RE = /^(CFC|HCFC|HFC|HFO|HCFO|PFC|Halon)-\d+[A-Za-z0-9]*$/

export type PubChemBoilingPoint = {
  temperature_c: number
  source: string
  reference_url: string | null
  note: string
}

export type PubChemData = {
  pubchem_cid: number
  iupac_name: string | null
  formula: string | null
  molar_mass: number | null
  smiles: string | null
  inchi: string | null
  inchikey: string | null
  cas_number: string | null
  industrial_name: string | null
  wikidata_id: string | null
  boiling_points: PubChemBoilingPoint[]
}

async function getJson<T>(url: string): Promise<T | null> {
  const response = await fetch(url)
  if (response.status === 404) return null
  if (!response.ok) {
    throw new Error(`PubChem request failed (${response.status})`)
  }
  return (await response.json()) as T
}

/** CID from a CID, a CAS number or any name PubChem knows. */
export async function findCid(query: {
  cid?: number | null
  names: (string | null | undefined)[]
}): Promise<number | null> {
  if (query.cid) return query.cid
  for (const name of query.names) {
    if (!name?.trim()) continue
    const data = await getJson<{ IdentifierList: { CID: number[] } }>(
      `${PUG}/compound/name/${encodeURIComponent(name.trim())}/cids/JSON`,
    )
    const cid = data?.IdentifierList?.CID?.[0]
    if (cid) return cid
  }
  return null
}

type PropertyTable = {
  PropertyTable: {
    Properties: {
      CID: number
      IUPACName?: string
      MolecularFormula?: string
      MolecularWeight?: string
      SMILES?: string
      InChI?: string
      InChIKey?: string
    }[]
  }
}

type Synonyms = {
  InformationList: { Information: { Synonym?: string[] }[] }
}

type ViewSection = {
  TOCHeading?: string
  Section?: ViewSection[]
  Information?: {
    ReferenceNumber?: number
    Value?: {
      StringWithMarkup?: { String: string }[]
      Number?: number[]
      Unit?: string
    }
  }[]
}

type ViewRecord = {
  Record: ViewSection & {
    Reference?: {
      ReferenceNumber: number
      SourceName?: string
      URL?: string
    }[]
  }
}

const round = (value: number) => Math.round(value * 100) / 100

/** "74.7 °F at 760 mmHg" -> 23.72; null when no temperature is found. */
export function parseCelsius(text: string): number | null {
  // "<value>[ to <value>] °C|°F" or "<value> K" (kelvin has no degree sign)
  const match =
    /(-?\d+(?:\.\d+)?)\s*(?:to\s*-?\d+(?:\.\d+)?\s*)?(?:°\s*([CcFf])|(K)(?![A-Za-z]))/.exec(
      text,
    )
  if (!match) return null
  const value = Number(match[1])
  if (match[3]) return round(value - 273.15)
  return match[2].toUpperCase() === "F" ? round(((value - 32) * 5) / 9) : value
}

function collectInformation(section: ViewSection): ViewSection["Information"] {
  const own = section.Information ?? []
  return [
    ...own,
    ...(section.Section ?? []).flatMap((s) => collectInformation(s) ?? []),
  ]
}

async function fetchBoilingPoints(cid: number): Promise<PubChemBoilingPoint[]> {
  const data = await getJson<ViewRecord>(
    `${PUG_VIEW}/data/compound/${cid}/JSON?heading=Boiling+Point`,
  )
  if (!data) return []
  const references = new Map(
    (data.Record.Reference ?? []).map((r) => [r.ReferenceNumber, r]),
  )
  const points: PubChemBoilingPoint[] = []
  for (const info of collectInformation(data.Record) ?? []) {
    const value = info.Value
    let note: string | null = null
    let celsius: number | null = null
    if (value?.StringWithMarkup?.length) {
      note = value.StringWithMarkup.map((s) => s.String).join(" ")
      celsius = parseCelsius(note)
    } else if (value?.Number?.length) {
      note = `${value.Number[0]} ${value.Unit ?? ""}`.trim()
      celsius = parseCelsius(note)
    }
    if (celsius === null || note === null) continue
    const reference = info.ReferenceNumber
      ? references.get(info.ReferenceNumber)
      : undefined
    points.push({
      temperature_c: celsius,
      source: `PubChem: ${reference?.SourceName ?? "unknown source"}`.slice(
        0,
        255,
      ),
      reference_url: reference?.URL ?? null,
      note: note.slice(0, 1024),
    })
  }
  return points
}

async function fetchWikidataId(
  inchikey: string | null,
  cid: number,
): Promise<string | null> {
  const statements = [
    inchikey ? `P235=${inchikey}` : null, // InChIKey
    `P662=${cid}`, // PubChem CID
  ]
  for (const statement of statements) {
    if (!statement) continue
    try {
      const response = await fetch(
        `https://www.wikidata.org/w/api.php?action=query&list=search&srsearch=haswbstatement:${statement}&format=json&origin=*`,
      )
      if (!response.ok) continue
      const data = (await response.json()) as {
        query?: { search?: { title: string }[] }
      }
      const title = data.query?.search?.[0]?.title
      if (title && /^Q\d+$/.test(title)) return title
    } catch {
      // Wikidata is a nice-to-have: ignore network errors
    }
  }
  return null
}

/** Everything we take from PubChem for one compound. */
export async function fetchPubChem(cid: number): Promise<PubChemData> {
  const [properties, synonyms, boilingPoints] = await Promise.all([
    getJson<PropertyTable>(
      `${PUG}/compound/cid/${cid}/property/${PROPERTIES}/JSON`,
    ),
    getJson<Synonyms>(`${PUG}/compound/cid/${cid}/synonyms/JSON`),
    fetchBoilingPoints(cid).catch(() => []),
  ])
  const p = properties?.PropertyTable?.Properties?.[0]
  if (!p) throw new Error(`PubChem has no compound with CID ${cid}`)
  const names = synonyms?.InformationList?.Information?.[0]?.Synonym ?? []
  const inchikey = p.InChIKey ?? null
  return {
    pubchem_cid: p.CID,
    iupac_name: p.IUPACName ?? null,
    formula: p.MolecularFormula ?? null,
    molar_mass: p.MolecularWeight ? Number(p.MolecularWeight) : null,
    smiles: p.SMILES ?? null,
    inchi: p.InChI ?? null,
    inchikey,
    cas_number: names.find(isValidCas) ?? null,
    industrial_name: names.find((n) => INDUSTRIAL_RE.test(n)) ?? null,
    wikidata_id: await fetchWikidataId(inchikey, p.CID),
    boiling_points: boilingPoints,
  }
}

/** Compound fields filled from PubChem, as form values (strings). */
export function pubchemFormValues(data: PubChemData): Record<string, string> {
  const values: Record<string, string> = {}
  for (const key of [
    "pubchem_cid",
    "iupac_name",
    "formula",
    "molar_mass",
    "smiles",
    "inchi",
    "inchikey",
    "cas_number",
    "industrial_name",
    "wikidata_id",
  ] as const) {
    const value = data[key]
    if (value !== null && value !== undefined) values[key] = String(value)
  }
  return values
}
