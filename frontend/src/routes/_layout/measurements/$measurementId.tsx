import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"

import {
  MeasurementsService,
  type MeasurementUpdate,
  SamplesService,
} from "@/client"
import { ActionsMenu } from "@/components/Common/ActionsMenu"
import { DeleteMenuItem } from "@/components/Common/DeleteMenuItem"
import { EntityFormDialog } from "@/components/Common/EntityFormDialog"
import {
  useCompoundOptions,
  useInstrumentOptions,
} from "@/components/Domain/MeasurementFilters"
import { MeasurementTypeBadge } from "@/components/Domain/MeasurementTypeBadge"
import {
  measurementFields,
  measurementInitialValues,
} from "@/components/Domain/measurementFields"
import { orDash } from "@/components/Domain/ReferencePage"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { formatNumber, formatUtc } from "@/lib/format"

export const Route = createFileRoute("/_layout/measurements/$measurementId")({
  component: MeasurementDetail,
  head: () => ({ meta: [{ title: "Measurement - Terminus" }] }),
})

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span>{children}</span>
    </div>
  )
}

function MeasurementDetail() {
  const { measurementId } = Route.useParams()
  const id = Number(measurementId)
  const navigate = useNavigate()
  const { user } = useAuth()
  const canWrite = !!user?.is_superuser
  const instruments = useInstrumentOptions()
  const compounds = useCompoundOptions()

  const {
    data: m,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["measurements", "detail", id],
    queryFn: async () =>
      (
        await MeasurementsService.readMeasurement({
          path: { measurement_id: id },
        })
      ).data,
  })
  const { data: sample } = useQuery({
    queryKey: ["samples", "detail", m?.sample_id],
    queryFn: async () =>
      (await SamplesService.readSample({ path: { sample_id: m!.sample_id! } }))
        .data,
    enabled: !!m?.sample_id,
  })

  const compoundInfo = new Map(compounds.data?.map((c) => [c.id, c]) ?? [])

  if (isError) {
    return <p className="text-muted-foreground">Measurement not found.</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/measurements" aria-label="Back to measurements">
              <ArrowLeft />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Measurement #{measurementId}
            </h1>
            <p className="text-muted-foreground">
              {m ? `${formatUtc(m.measured_at)} UTC` : "…"}
            </p>
          </div>
        </div>
        {canWrite && m && (
          <ActionsMenu>
            {(close) => (
              <>
                <EntityFormDialog
                  mode="edit"
                  entityLabel="Measurement"
                  fields={measurementFields(instruments.data)}
                  initialValues={measurementInitialValues(m)}
                  onSubmit={(body) =>
                    MeasurementsService.updateMeasurement({
                      path: { measurement_id: id },
                      body: body as MeasurementUpdate,
                    })
                  }
                  invalidate={[["measurements"], ["results"]]}
                  onSuccess={close}
                />
                <DeleteMenuItem
                  entityLabel="Measurement"
                  name={`#${id}`}
                  warning="Its results are deleted too."
                  onDelete={() =>
                    MeasurementsService.deleteMeasurement({
                      path: { measurement_id: id },
                    })
                  }
                  invalidate={[["measurements"], ["results"]]}
                  onSuccess={() => navigate({ to: "/measurements" })}
                />
              </>
            )}
          </ActionsMenu>
        )}
      </div>

      <Card>
        <CardContent className="grid grid-cols-2 gap-6 md:grid-cols-5">
          {isLoading || !m ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))
          ) : (
            <>
              <Field label="Type">
                <MeasurementTypeBadge type={m.type} />
              </Field>
              <Field label="Instrument">
                <span className="font-mono">{m.instrument_id}</span>
              </Field>
              <Field label="Sample">
                {m.sample_id ? (
                  <span className="font-mono">{m.sample_id}</span>
                ) : (
                  orDash(null)
                )}
              </Field>
              <Field label="Container">
                {sample ? (
                  <Link
                    to="/samples"
                    search={{ container_id: sample.container_id }}
                    className="font-mono underline-offset-4 hover:underline"
                  >
                    {sample.container_id}
                  </Link>
                ) : (
                  orDash(null)
                )}
              </Field>
              <Field label="Description">{orDash(m.description)}</Field>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Compound</TableHead>
                <TableHead>Name</TableHead>
                <TableHead className="text-right">Area</TableHead>
                <TableHead className="text-right">Height</TableHead>
                <TableHead className="text-right">Retention time</TableHead>
                <TableHead className="text-right">Concentration</TableHead>
                <TableHead>Unit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {m?.results?.length ? (
                [...m.results]
                  .sort((a, b) => a.compound_id.localeCompare(b.compound_id))
                  .map((r) => {
                    const info = compoundInfo.get(r.compound_id)
                    return (
                      <TableRow key={r.compound_id}>
                        <TableCell className="font-mono font-medium">
                          {r.compound_id}
                        </TableCell>
                        <TableCell>{orDash(info?.name)}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatNumber(r.area)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatNumber(r.height)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatNumber(r.retention_time)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatNumber(r.concentration)}
                        </TableCell>
                        <TableCell>{orDash(info?.unit)}</TableCell>
                      </TableRow>
                    )
                  })
              ) : (
                <TableRow className="hover:bg-transparent">
                  <TableCell
                    colSpan={7}
                    className="h-24 text-center text-muted-foreground"
                  >
                    {isLoading
                      ? "Loading…"
                      : "No results for this measurement."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
