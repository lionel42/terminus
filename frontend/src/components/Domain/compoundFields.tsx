import { BookOpen, FlaskConical } from "lucide-react"

import type { CompoundPublicWithDetails, CompoundStatus } from "@/client"
import type {
  FieldConfig,
  FillAction,
} from "@/components/Common/EntityFormDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { COMPOUND_STATUSES, pubchemUrl, wikipediaUrl } from "@/lib/compound"
import { fetchPubChem, findCid, pubchemFormValues } from "@/lib/pubchem"

export const compoundFields: FieldConfig[] = [
  {
    name: "industrial_name",
    label: "Industrial name",
    placeholder: "CFC-11",
    description: "Official designation (CFC, HCFC, HFC, Halon, ...)",
  },
  {
    name: "iupac_name",
    label: "IUPAC name",
    placeholder: "trichloro(fluoro)methane",
  },
  { name: "formula", label: "Formula", placeholder: "CCl3F" },
  { name: "unit", label: "Unit", placeholder: "ppt" },
  {
    name: "status",
    label: "Status",
    type: "select",
    placeholder: "Not given",
    options: COMPOUND_STATUSES.map((s) => ({ value: s, label: s })),
  },
  { name: "description", label: "Description" },
  { name: "cas_number", label: "CAS number", placeholder: "75-69-4" },
  {
    name: "pubchem_cid",
    label: "PubChem CID",
    type: "number",
    placeholder: "6389",
  },
  {
    name: "molar_mass",
    label: "Molar mass (g/mol)",
    type: "number",
    placeholder: "137.36",
  },
  { name: "inchikey", label: "InChIKey" },
  { name: "inchi", label: "InChI" },
  { name: "smiles", label: "SMILES" },
  { name: "wikidata_id", label: "Wikidata id", placeholder: "Q423000" },
]

/** CID from the form (CID, CAS, names or id), then the PubChem record. */
export async function lookupPubChem(values: Record<string, string>) {
  const cid = await findCid({
    cid: values.pubchem_cid ? Number(values.pubchem_cid) : null,
    names: [
      values.cas_number,
      values.industrial_name,
      values.iupac_name,
      values.id,
    ],
  })
  if (!cid) {
    throw new Error(
      "Not found in PubChem: set a CID, a CAS number or a name first",
    )
  }
  return fetchPubChem(cid)
}

export const pubchemFill: FillAction = {
  label: "Fill from PubChem",
  run: async (values) => pubchemFormValues(await lookupPubChem(values)),
}

const STATUS_VARIANTS: Record<
  CompoundStatus,
  "default" | "secondary" | "outline"
> = {
  measured: "default",
  target: "secondary",
  suspect: "outline",
}

export function CompoundStatusBadge({
  status,
}: {
  status: CompoundStatus | null | undefined
}) {
  if (!status) return <span className="text-muted-foreground">—</span>
  return <Badge variant={STATUS_VARIANTS[status] ?? "outline"}>{status}</Badge>
}

/** Icon buttons to PubChem and Wikipedia. */
export function CompoundLinks({
  compound,
}: {
  compound: CompoundPublicWithDetails
}) {
  const links = [
    { label: "PubChem", href: pubchemUrl(compound), icon: FlaskConical },
    { label: "Wikipedia", href: wikipediaUrl(compound), icon: BookOpen },
  ]
  return (
    <div className="flex items-center">
      {links.map(({ label, href, icon: Icon }) => (
        <Tooltip key={label}>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" asChild>
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`${label} page`}
              >
                <Icon />
              </a>
            </Button>
          </TooltipTrigger>
          <TooltipContent>{label}</TooltipContent>
        </Tooltip>
      ))}
    </div>
  )
}
