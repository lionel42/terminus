import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Download } from "lucide-react"

import { type ResultRow, ResultsService } from "@/client"
import { type Column, ServerTable } from "@/components/Common/ServerTable"
import { FlagBadges } from "@/components/Domain/FlagBadges"
import {
  MeasurementFilterBar,
  measurementSearchSchema,
  toApiFilters,
} from "@/components/Domain/MeasurementFilters"
import { MeasurementTypeBadge } from "@/components/Domain/MeasurementTypeBadge"
import { orDash } from "@/components/Domain/ReferencePage"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { formatNumber, formatUtc } from "@/lib/format"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/results")({
  component: Results,
  validateSearch: measurementSearchSchema,
  head: () => ({ meta: [{ title: "Results - Terminus" }] }),
})

const PAGE_SIZE = 100

const num = (key: keyof ResultRow, header: string): Column<ResultRow> => ({
  key,
  header,
  className: "text-right tabular-nums",
  cell: (r) => formatNumber(r[key] as number | null),
})

const columns: Column<ResultRow>[] = [
  {
    key: "measured_at",
    header: "Measured at (UTC)",
    cell: (r) => (
      <Link
        to="/measurements/$measurementId"
        params={{ measurementId: String(r.measurement_id) }}
        className="underline-offset-4 hover:underline"
      >
        {formatUtc(r.measured_at)}
      </Link>
    ),
  },
  {
    key: "type",
    header: "Type",
    cell: (r) => <MeasurementTypeBadge type={r.type} />,
  },
  {
    key: "instrument",
    header: "Instrument",
    cell: (r) => <span className="font-mono">{r.instrument_id}</span>,
  },
  {
    key: "container",
    header: "Container",
    cell: (r) =>
      r.container_id ? (
        <span className="font-mono">{r.container_id}</span>
      ) : (
        orDash(null)
      ),
  },
  {
    key: "compound",
    header: "Compound",
    cell: (r) => <span className="font-mono font-medium">{r.compound_id}</span>,
  },
  num("area", "Area"),
  num("height", "Height"),
  num("retention_time", "Ret. time"),
  num("concentration", "Concentration"),
  {
    key: "flags",
    header: "Flags",
    cell: (r) => (
      <FlagBadges
        flags={r.flags}
        comment={r.flag_comment}
        runFlags={r.measurement_flags}
        runComment={r.measurement_flag_comment}
      />
    ),
  },
]

function Results() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { showErrorToast } = useCustomToast()
  const page = search.page ?? 1
  const filters = toApiFilters(search)

  const { data, isLoading } = useQuery({
    queryKey: ["results", search],
    queryFn: async () =>
      (
        await ResultsService.readResults({
          query: { ...filters, skip: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE },
        })
      ).data,
    placeholderData: keepPreviousData,
  })

  const download = useMutation({
    mutationFn: async () => {
      const response = await ResultsService.readResultsCsv({ query: filters })
      const blob = new Blob([response.data as unknown as string], {
        type: "text/csv",
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = "results.csv"
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Results</h1>
          <p className="text-muted-foreground">
            One row per measurement and compound, oldest first
          </p>
        </div>
        <LoadingButton
          variant="outline"
          loading={download.isPending}
          onClick={() => download.mutate()}
          disabled={!data?.count}
        >
          <Download className="mr-2" />
          Download CSV
        </LoadingButton>
      </div>
      <MeasurementFilterBar
        value={search}
        onApply={(value) => navigate({ search: value })}
        showCompound
      />
      <ServerTable
        columns={columns}
        rows={data?.data}
        rowKey={(r) => `${r.measurement_id}-${r.compound_id}`}
        isLoading={isLoading}
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.count ?? 0}
        onPageChange={(p) => navigate({ search: { ...search, page: p } })}
      />
    </div>
  )
}
