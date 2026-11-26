import { useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { z } from "zod"

import { CompoundsService, InstrumentsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  compact,
  dayEndUtc,
  dayStartUtc,
  MEASUREMENT_TYPES,
} from "@/lib/format"

/** URL search params shared by the measurements and results pages. */
export const measurementSearchSchema = z.object({
  instrument_id: z.string().optional(),
  type: z.enum(MEASUREMENT_TYPES).optional(),
  container_id: z.string().optional(),
  sample_id: z.string().optional(),
  compound_id: z.string().optional(),
  /** YYYY-MM-DD, UTC days, inclusive */
  from: z.string().optional(),
  to: z.string().optional(),
  page: z.number().int().min(1).optional(),
})

export type MeasurementSearch = z.infer<typeof measurementSearchSchema>

/** URL search params -> API query parameters. */
export function toApiFilters(search: MeasurementSearch) {
  return compact({
    instrument_id: search.instrument_id,
    type: search.type,
    container_id: search.container_id,
    sample_id: search.sample_id,
    compound_id: search.compound_id,
    measured_from: search.from ? dayStartUtc(search.from) : undefined,
    measured_to: search.to ? dayEndUtc(search.to) : undefined,
  })
}

const ALL = "__all__"

export function useInstrumentOptions() {
  return useQuery({
    queryKey: ["instruments", "options"],
    queryFn: async () =>
      (await InstrumentsService.readInstruments({ query: { limit: 1000 } }))
        .data.data,
    staleTime: 60_000,
  })
}

export function useCompoundOptions() {
  return useQuery({
    queryKey: ["compounds", "options"],
    queryFn: async () =>
      (await CompoundsService.readCompounds({ query: { limit: 1000 } })).data
        .data,
    staleTime: 60_000,
  })
}

interface MeasurementFilterBarProps {
  value: MeasurementSearch
  onApply: (value: MeasurementSearch) => void
  showCompound?: boolean
}

export function MeasurementFilterBar({
  value,
  onApply,
  showCompound,
}: MeasurementFilterBarProps) {
  const [draft, setDraft] = useState<MeasurementSearch>(value)
  useEffect(() => setDraft(value), [value])
  const instruments = useInstrumentOptions()
  const compounds = useCompoundOptions()

  const set = (key: keyof MeasurementSearch, v: string | undefined) =>
    setDraft((d) => ({ ...d, [key]: v === ALL || v === "" ? undefined : v }))

  return (
    <form
      className="grid grid-cols-2 gap-3 rounded-lg border p-4 md:grid-cols-4 xl:grid-cols-8"
      onSubmit={(e) => {
        e.preventDefault()
        onApply({ ...draft, page: undefined })
      }}
    >
      <div className="flex flex-col gap-1.5">
        <Label>Instrument</Label>
        <Select
          value={draft.instrument_id ?? ALL}
          onValueChange={(v) => set("instrument_id", v)}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All</SelectItem>
            {instruments.data?.map((i) => (
              <SelectItem key={i.id} value={i.id}>
                {i.id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Type</Label>
        <Select value={draft.type ?? ALL} onValueChange={(v) => set("type", v)}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All</SelectItem>
            {MEASUREMENT_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {showCompound && (
        <div className="flex flex-col gap-1.5">
          <Label>Compound</Label>
          <Select
            value={draft.compound_id ?? ALL}
            onValueChange={(v) => set("compound_id", v)}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All</SelectItem>
              {compounds.data?.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="filter-container">Container</Label>
        <Input
          id="filter-container"
          placeholder="any"
          value={draft.container_id ?? ""}
          onChange={(e) => set("container_id", e.target.value.toLowerCase())}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="filter-sample">Sample</Label>
        <Input
          id="filter-sample"
          placeholder="any"
          value={draft.sample_id ?? ""}
          onChange={(e) => set("sample_id", e.target.value.toLowerCase())}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="filter-from">From (UTC)</Label>
        <Input
          id="filter-from"
          type="date"
          value={draft.from ?? ""}
          onChange={(e) => set("from", e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="filter-to">To (UTC)</Label>
        <Input
          id="filter-to"
          type="date"
          value={draft.to ?? ""}
          onChange={(e) => set("to", e.target.value)}
        />
      </div>
      <div className="col-span-2 flex items-end gap-2 md:col-span-4 xl:col-span-1">
        <Button type="submit" className="flex-1">
          Apply
        </Button>
        <Button type="button" variant="outline" onClick={() => onApply({})}>
          Reset
        </Button>
      </div>
    </form>
  )
}
