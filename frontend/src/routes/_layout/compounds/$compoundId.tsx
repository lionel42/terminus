import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowLeft, ExternalLink, Plus, Trash2, X } from "lucide-react"
import { type ReactNode, useState } from "react"

import {
  type BoilingPointCreate,
  CompoundsService,
  type CompoundUpdate,
} from "@/client"
import { ActionsMenu } from "@/components/Common/ActionsMenu"
import { DeleteMenuItem } from "@/components/Common/DeleteMenuItem"
import {
  EntityFormDialog,
  type FieldConfig,
} from "@/components/Common/EntityFormDialog"
import {
  CompoundStatusBadge,
  compoundFields,
  pubchemFill,
} from "@/components/Domain/compoundFields"
import { PubChemDialog } from "@/components/Domain/PubChemDialog"
import { orDash } from "@/components/Domain/ReferencePage"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import {
  compoundName,
  nistUrl,
  pubchemUrl,
  wikidataUrl,
  wikipediaUrl,
} from "@/lib/compound"
import { formatNumber } from "@/lib/format"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/compounds/$compoundId")({
  component: CompoundDetail,
  head: () => ({ meta: [{ title: "Compound - Terminus" }] }),
})

const boilingPointFields: FieldConfig[] = [
  {
    name: "temperature_c",
    label: "Boiling point (°C)",
    type: "number",
    required: true,
    description: "At normal pressure, unless stated in the note",
  },
  {
    name: "source",
    label: "Source",
    required: true,
    placeholder: "CRC Handbook of Chemistry and Physics, 97th ed.",
  },
  { name: "reference_url", label: "Reference URL", placeholder: "https://…" },
  { name: "note", label: "Note" },
]

function Field({
  label,
  children,
  wide,
}: {
  label: string
  children: ReactNode
  wide?: boolean
}) {
  return (
    <div
      className={`flex min-w-0 flex-col gap-1 ${wide ? "md:col-span-2" : ""}`}
    >
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="break-all">{children}</span>
    </div>
  )
}

function ExternalLinkButton({ href, label }: { href: string; label: string }) {
  return (
    <Button variant="outline" size="sm" asChild>
      <a href={href} target="_blank" rel="noopener noreferrer">
        {label}
        <ExternalLink className="ml-1" />
      </a>
    </Button>
  )
}

function CompoundDetail() {
  const { compoundId } = Route.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canWrite = !!user?.is_superuser
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [newAlias, setNewAlias] = useState("")

  const {
    data: c,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["compounds", "detail", compoundId],
    queryFn: async () =>
      (
        await CompoundsService.readCompound({
          path: { compound_id: compoundId },
        })
      ).data,
  })

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["compounds"] })

  const addAlias = useMutation({
    mutationFn: (alias: string) =>
      CompoundsService.createAlias({
        path: { compound_id: compoundId },
        body: { alias },
      }),
    onSuccess: () => {
      setNewAlias("")
      showSuccessToast("Alias added")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })

  const removeAlias = useMutation({
    mutationFn: (aliasId: number) =>
      CompoundsService.deleteAlias({
        path: { compound_id: compoundId, alias_id: aliasId },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })

  const removeBoilingPoint = useMutation({
    mutationFn: (id: number) =>
      CompoundsService.deleteBoilingPoint({
        path: { compound_id: compoundId, boiling_point_id: id },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })

  if (isError) {
    return <p className="text-muted-foreground">Compound not found.</p>
  }

  const name = compoundName(c)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/compounds" aria-label="Back to compounds">
              <ArrowLeft />
            </Link>
          </Button>
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-bold tracking-tight">
              <span className="font-mono">{compoundId.toLowerCase()}</span>
              {c && <CompoundStatusBadge status={c.status} />}
            </h1>
            <p className="text-muted-foreground">
              {c ? [name, c.formula].filter(Boolean).join(" · ") || "—" : "…"}
            </p>
          </div>
        </div>
        {c && (
          <div className="flex items-center gap-2">
            <ExternalLinkButton href={pubchemUrl(c)} label="PubChem" />
            <ExternalLinkButton href={wikipediaUrl(c)} label="Wikipedia" />
            {c.cas_number && (
              <ExternalLinkButton href={nistUrl(c.cas_number)} label="NIST" />
            )}
            {canWrite && <PubChemDialog compound={c} />}
            {canWrite && (
              <ActionsMenu>
                {(close) => (
                  <>
                    <EntityFormDialog
                      mode="edit"
                      entityLabel="Compound"
                      fields={compoundFields}
                      fill={pubchemFill}
                      initialValues={Object.fromEntries(
                        compoundFields.map((f) => [
                          f.name,
                          String((c as Record<string, unknown>)[f.name] ?? ""),
                        ]),
                      )}
                      onSubmit={(body) =>
                        CompoundsService.updateCompound({
                          path: { compound_id: c.id },
                          body: body as CompoundUpdate,
                        })
                      }
                      invalidate={[["compounds"]]}
                      onSuccess={close}
                    />
                    <DeleteMenuItem
                      entityLabel="Compound"
                      name={c.id}
                      warning="Its aliases and boiling points are deleted too."
                      onDelete={() =>
                        CompoundsService.deleteCompound({
                          path: { compound_id: c.id },
                        })
                      }
                      invalidate={[["compounds"]]}
                      onSuccess={() => navigate({ to: "/compounds" })}
                    />
                  </>
                )}
              </ActionsMenu>
            )}
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Names and identifiers</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-4">
          {isLoading || !c ? (
            Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))
          ) : (
            <>
              <Field label="Industrial name">{orDash(c.industrial_name)}</Field>
              <Field label="IUPAC name" wide>
                {orDash(c.iupac_name)}
              </Field>
              <Field label="Formula">{orDash(c.formula)}</Field>
              <Field label="Unit">{orDash(c.unit)}</Field>
              <Field label="Molar mass">
                {c.molar_mass
                  ? `${formatNumber(c.molar_mass)} g/mol`
                  : orDash(null)}
              </Field>
              <Field label="CAS number">
                <span className="font-mono">{orDash(c.cas_number)}</span>
              </Field>
              <Field label="PubChem CID">
                {c.pubchem_cid ? (
                  <a
                    className="font-mono underline-offset-4 hover:underline"
                    href={pubchemUrl(c)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {c.pubchem_cid}
                  </a>
                ) : (
                  orDash(null)
                )}
              </Field>
              <Field label="Wikidata">
                {c.wikidata_id ? (
                  <a
                    className="font-mono underline-offset-4 hover:underline"
                    href={wikidataUrl(c.wikidata_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {c.wikidata_id}
                  </a>
                ) : (
                  orDash(null)
                )}
              </Field>
              <Field label="InChIKey" wide>
                <span className="font-mono text-sm">{orDash(c.inchikey)}</span>
              </Field>
              <Field label="SMILES" wide>
                <span className="font-mono text-sm">{orDash(c.smiles)}</span>
              </Field>
              <Field label="InChI" wide>
                <span className="font-mono text-sm">{orDash(c.inchi)}</span>
              </Field>
              <Field label="Description" wide>
                {orDash(c.description)}
              </Field>
            </>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Aliases</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-2">
              {c?.aliases?.length ? (
                c.aliases.map((a) => (
                  <Badge key={a.id} variant="secondary" className="gap-1">
                    {a.alias}
                    {canWrite && (
                      <button
                        type="button"
                        className="rounded-sm opacity-60 hover:opacity-100"
                        aria-label={`Remove alias ${a.alias}`}
                        onClick={() => removeAlias.mutate(a.id)}
                      >
                        <X className="size-3" />
                      </button>
                    )}
                  </Badge>
                ))
              ) : (
                <span className="text-sm text-muted-foreground">
                  No aliases.
                </span>
              )}
            </div>
            {canWrite && (
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (newAlias.trim()) addAlias.mutate(newAlias.trim())
                }}
              >
                <Input
                  placeholder="Trade name, synonym, in-house label…"
                  aria-label="New alias"
                  value={newAlias}
                  maxLength={255}
                  onChange={(e) => setNewAlias(e.target.value)}
                />
                <Button
                  type="submit"
                  variant="secondary"
                  disabled={!newAlias.trim() || addAlias.isPending}
                >
                  <Plus className="mr-1" />
                  Add
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Boiling points</CardTitle>
            {canWrite && (
              <EntityFormDialog
                mode="create"
                entityLabel="Boiling point"
                fields={boilingPointFields}
                onSubmit={(body) =>
                  CompoundsService.createBoilingPoint({
                    path: { compound_id: compoundId },
                    body: body as unknown as BoilingPointCreate,
                  })
                }
                invalidate={[["compounds"]]}
              />
            )}
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="text-right">°C</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Note</TableHead>
                  {canWrite && (
                    <TableHead>
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {c?.boiling_points?.length ? (
                  [...c.boiling_points]
                    .sort((a, b) => a.source.localeCompare(b.source))
                    .map((bp) => (
                      <TableRow key={bp.id}>
                        <TableCell className="text-right tabular-nums">
                          {formatNumber(bp.temperature_c)}
                        </TableCell>
                        <TableCell className="whitespace-normal">
                          {bp.reference_url ? (
                            <a
                              className="underline-offset-4 hover:underline"
                              href={bp.reference_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {bp.source}
                            </a>
                          ) : (
                            bp.source
                          )}
                        </TableCell>
                        <TableCell className="whitespace-normal text-muted-foreground">
                          {orDash(bp.note)}
                        </TableCell>
                        {canWrite && (
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label="Delete boiling point"
                              onClick={() => removeBoilingPoint.mutate(bp.id)}
                            >
                              <Trash2 />
                            </Button>
                          </TableCell>
                        )}
                      </TableRow>
                    ))
                ) : (
                  <TableRow className="hover:bg-transparent">
                    <TableCell
                      colSpan={4}
                      className="h-16 text-center text-muted-foreground"
                    >
                      {isLoading ? "Loading…" : "No boiling point stored."}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
