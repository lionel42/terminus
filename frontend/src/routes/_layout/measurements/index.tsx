import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"

import {
  type MeasurementCreate,
  type MeasurementPublic,
  MeasurementsService,
  type MeasurementUpdate,
} from "@/client"
import { ActionsMenu } from "@/components/Common/ActionsMenu"
import { DeleteMenuItem } from "@/components/Common/DeleteMenuItem"
import { EntityFormDialog } from "@/components/Common/EntityFormDialog"
import { type Column, ServerTable } from "@/components/Common/ServerTable"
import {
  MeasurementFilterBar,
  measurementSearchSchema,
  toApiFilters,
  useInstrumentOptions,
} from "@/components/Domain/MeasurementFilters"
import { MeasurementTypeBadge } from "@/components/Domain/MeasurementTypeBadge"
import {
  measurementFields,
  measurementInitialValues,
} from "@/components/Domain/measurementFields"
import { orDash } from "@/components/Domain/ReferencePage"
import useAuth from "@/hooks/useAuth"
import { formatUtc } from "@/lib/format"

export const Route = createFileRoute("/_layout/measurements/")({
  component: Measurements,
  validateSearch: measurementSearchSchema,
  head: () => ({ meta: [{ title: "Measurements - Terminus" }] }),
})

const PAGE_SIZE = 50

function Measurements() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user } = useAuth()
  const canWrite = !!user?.is_superuser
  const instruments = useInstrumentOptions()
  const fields = measurementFields(instruments.data)
  const page = search.page ?? 1

  const { data, isLoading } = useQuery({
    queryKey: ["measurements", search],
    queryFn: async () => {
      const { compound_id: _ignored, ...filters } = toApiFilters(search)
      return (
        await MeasurementsService.readMeasurements({
          query: { ...filters, skip: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE },
        })
      ).data
    },
    placeholderData: keepPreviousData,
  })

  const columns: Column<MeasurementPublic>[] = [
    {
      key: "measured_at",
      header: "Measured at (UTC)",
      cell: (m) => (
        <Link
          to="/measurements/$measurementId"
          params={{ measurementId: String(m.id) }}
          className="font-medium underline-offset-4 hover:underline"
        >
          {formatUtc(m.measured_at)}
        </Link>
      ),
    },
    {
      key: "type",
      header: "Type",
      cell: (m) => <MeasurementTypeBadge type={m.type} />,
    },
    {
      key: "instrument",
      header: "Instrument",
      cell: (m) => <span className="font-mono">{m.instrument_id}</span>,
    },
    {
      key: "sample",
      header: "Sample",
      cell: (m) =>
        m.sample_id ? (
          <span className="font-mono">{m.sample_id}</span>
        ) : (
          orDash(null)
        ),
    },
    {
      key: "description",
      header: "Description",
      cell: (m) => orDash(m.description),
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      className: "text-right",
      cell: (m) =>
        canWrite && (
          <div className="flex justify-end">
            <ActionsMenu>
              {(close) => (
                <>
                  <EntityFormDialog
                    mode="edit"
                    entityLabel="Measurement"
                    fields={fields}
                    initialValues={measurementInitialValues(m)}
                    onSubmit={(body) =>
                      MeasurementsService.updateMeasurement({
                        path: { measurement_id: m.id },
                        body: body as MeasurementUpdate,
                      })
                    }
                    invalidate={[["measurements"], ["results"]]}
                    onSuccess={close}
                  />
                  <DeleteMenuItem
                    entityLabel="Measurement"
                    name={`#${m.id} (${formatUtc(m.measured_at)})`}
                    warning="Its results are deleted too."
                    onDelete={() =>
                      MeasurementsService.deleteMeasurement({
                        path: { measurement_id: m.id },
                      })
                    }
                    invalidate={[["measurements"], ["results"]]}
                    onSuccess={close}
                  />
                </>
              )}
            </ActionsMenu>
          </div>
        ),
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Measurements</h1>
          <p className="text-muted-foreground">
            Chromatography runs, newest first. Open one to see its results.
          </p>
        </div>
        {canWrite && (
          <EntityFormDialog
            mode="create"
            entityLabel="Measurement"
            fields={fields}
            initialValues={{ instrument_id: search.instrument_id ?? "" }}
            onSubmit={(body) =>
              MeasurementsService.createMeasurement({
                body: body as unknown as MeasurementCreate,
              })
            }
            invalidate={[["measurements"]]}
          />
        )}
      </div>
      <MeasurementFilterBar
        value={search}
        onApply={(value) => navigate({ search: value })}
      />
      <ServerTable
        columns={columns}
        rows={data?.data}
        rowKey={(m) => m.id}
        isLoading={isLoading}
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.count ?? 0}
        onPageChange={(p) => navigate({ search: { ...search, page: p } })}
      />
    </div>
  )
}
