import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Sparkles } from "lucide-react"
import { useState } from "react"

import {
  type CompoundPublicWithDetails,
  CompoundsService,
  type CompoundUpdate,
} from "@/client"
import {
  compoundFields,
  lookupPubChem,
} from "@/components/Domain/compoundFields"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import { type PubChemData, pubchemFormValues } from "@/lib/pubchem"
import { handleError } from "@/utils"

type FieldChange = {
  name: string
  label: string
  current: string
  found: string
}

/** Looks the compound up in PubChem, lets the user pick what to apply. */
export function PubChemDialog({
  compound,
}: {
  compound: CompoundPublicWithDetails
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [data, setData] = useState<PubChemData | null>(null)
  const [fieldPicks, setFieldPicks] = useState<Set<string>>(new Set())
  const [pointPicks, setPointPicks] = useState<Set<number>>(new Set())
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const current = (name: string) =>
    String((compound as Record<string, unknown>)[name] ?? "")

  const changes: FieldChange[] = data
    ? Object.entries(pubchemFormValues(data))
        .filter(([name, found]) => found !== current(name))
        .map(([name, found]) => ({
          name,
          label: compoundFields.find((f) => f.name === name)?.label ?? name,
          current: current(name),
          found,
        }))
    : []

  const isKnownPoint = (p: PubChemData["boiling_points"][number]) =>
    (compound.boiling_points ?? []).some(
      (bp) => bp.temperature_c === p.temperature_c && bp.source === p.source,
    )

  const lookup = useMutation({
    mutationFn: () =>
      lookupPubChem(
        Object.fromEntries(
          ["id", ...compoundFields.map((f) => f.name)].map((n) => [
            n,
            current(n),
          ]),
        ),
      ),
    onSuccess: (found) => {
      setData(found)
      // Pre-select: fields that are empty here, boiling points not stored yet
      setFieldPicks(
        new Set(
          Object.keys(pubchemFormValues(found)).filter((n) => !current(n)),
        ),
      )
      setPointPicks(
        new Set(
          found.boiling_points
            .map((p, i) => (isKnownPoint(p) ? -1 : i))
            .filter((i) => i >= 0),
        ),
      )
    },
    onError: (err: Error) => {
      setIsOpen(false)
      handleError.call(showErrorToast, err)
    },
  })

  const apply = useMutation({
    mutationFn: async () => {
      if (!data) return
      const values = pubchemFormValues(data)
      const body: Record<string, string | number> = {}
      for (const name of fieldPicks) {
        const type = compoundFields.find((f) => f.name === name)?.type
        body[name] = type === "number" ? Number(values[name]) : values[name]
      }
      if (Object.keys(body).length) {
        await CompoundsService.updateCompound({
          path: { compound_id: compound.id },
          body: body as CompoundUpdate,
        })
      }
      for (const index of pointPicks) {
        await CompoundsService.createBoilingPoint({
          path: { compound_id: compound.id },
          body: data.boiling_points[index],
        })
      }
    },
    onSuccess: () => {
      showSuccessToast("PubChem data applied")
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["compounds"] }),
  })

  const toggle = <T,>(set: Set<T>, value: T, on: boolean) => {
    const next = new Set(set)
    if (on) next.add(value)
    else next.delete(value)
    return next
  }

  const onOpenChange = (open: boolean) => {
    setIsOpen(open)
    if (open) {
      setData(null)
      lookup.mutate()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <Button variant="secondary" onClick={() => onOpenChange(true)}>
        <Sparkles className="mr-2" />
        Fill from PubChem
      </Button>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Fill from PubChem</DialogTitle>
          <DialogDescription>
            {data ? (
              <>
                Found{" "}
                <a
                  className="underline underline-offset-4"
                  href={`https://pubchem.ncbi.nlm.nih.gov/compound/${data.pubchem_cid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  CID {data.pubchem_cid}
                </a>
                . Pick what to apply. Aliases are not imported.
              </>
            ) : (
              "Searching PubChem by CID, CAS number, names and id…"
            )}
          </DialogDescription>
        </DialogHeader>

        {data && (
          <div className="flex flex-col gap-6">
            <section className="flex flex-col gap-2">
              <h3 className="font-medium">Properties</h3>
              {changes.length ? (
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="w-8" />
                      <TableHead>Field</TableHead>
                      <TableHead>Current</TableHead>
                      <TableHead>PubChem</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {changes.map((c) => (
                      <TableRow key={c.name}>
                        <TableCell>
                          <Checkbox
                            aria-label={`Apply ${c.label}`}
                            checked={fieldPicks.has(c.name)}
                            onCheckedChange={(on) =>
                              setFieldPicks((s) => toggle(s, c.name, !!on))
                            }
                          />
                        </TableCell>
                        <TableCell className="font-medium">{c.label}</TableCell>
                        <TableCell className="max-w-48 whitespace-normal break-all text-muted-foreground">
                          {c.current || "—"}
                        </TableCell>
                        <TableCell className="max-w-72 whitespace-normal break-all font-mono text-xs">
                          {c.found}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">
                  All properties already match PubChem.
                </p>
              )}
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="font-medium">Boiling points</h3>
              {data.boiling_points.length ? (
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="w-8" />
                      <TableHead className="text-right">°C</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>Original value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.boiling_points.map((p, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          <Checkbox
                            aria-label={`Add boiling point ${p.temperature_c} °C`}
                            checked={pointPicks.has(i)}
                            disabled={isKnownPoint(p)}
                            onCheckedChange={(on) =>
                              setPointPicks((s) => toggle(s, i, !!on))
                            }
                          />
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {p.temperature_c}
                        </TableCell>
                        <TableCell className="whitespace-normal">
                          {p.source}
                          {isKnownPoint(p) && (
                            <span className="text-muted-foreground">
                              {" "}
                              (stored)
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="whitespace-normal text-muted-foreground">
                          {p.note}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground">
                  PubChem lists no boiling point.
                </p>
              )}
            </section>
          </div>
        )}

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={apply.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            loading={apply.isPending || lookup.isPending}
            disabled={!data || (!fieldPicks.size && !pointPicks.size)}
            onClick={() => apply.mutate()}
          >
            Apply {fieldPicks.size + pointPicks.size || ""}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
