import type { CompoundPublicWithDetails, CompoundStatus } from "@/client"

export const COMPOUND_STATUSES: CompoundStatus[] = [
  "measured",
  "target",
  "suspect",
]

type Named = Pick<CompoundPublicWithDetails, "id"> &
  Partial<Pick<CompoundPublicWithDetails, "industrial_name" | "iupac_name">>

/** Human-readable name: industrial designation, else IUPAC name. */
export function compoundName(c: Named | undefined): string | null {
  return c?.industrial_name || c?.iupac_name || null
}

const CAS_RE = /^(\d{2,7})-(\d{2})-(\d)$/

/** Format and check digit of a CAS registry number. */
export function isValidCas(cas: string): boolean {
  const match = CAS_RE.exec(cas)
  if (!match) return false
  const digits = (match[1] + match[2]).split("").reverse()
  const sum = digits.reduce((acc, d, i) => acc + Number(d) * (i + 1), 0)
  return sum % 10 === Number(match[3])
}

type Linkable = Named &
  Partial<
    Pick<
      CompoundPublicWithDetails,
      "pubchem_cid" | "cas_number" | "wikidata_id"
    >
  >

export function pubchemUrl(c: Linkable): string {
  if (c.pubchem_cid) {
    return `https://pubchem.ncbi.nlm.nih.gov/compound/${c.pubchem_cid}`
  }
  const query = c.cas_number || compoundName(c) || c.id
  return `https://pubchem.ncbi.nlm.nih.gov/#query=${encodeURIComponent(query)}`
}

/** Exact article through Wikidata when known, else a Wikipedia search. */
export function wikipediaUrl(c: Linkable): string {
  if (c.wikidata_id) {
    return `https://www.wikidata.org/wiki/Special:GoToLinkedPage/enwiki/${c.wikidata_id}`
  }
  const query = compoundName(c) || c.cas_number || c.id
  return `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(query)}&title=Special:Search&go=Go`
}

export function wikidataUrl(qid: string): string {
  return `https://www.wikidata.org/wiki/${qid}`
}

/** NIST Chemistry WebBook (thermochemistry, spectra), by CAS number. */
export function nistUrl(cas: string): string {
  return `https://webbook.nist.gov/cgi/cbook.cgi?ID=${encodeURIComponent(cas)}&Units=SI`
}
