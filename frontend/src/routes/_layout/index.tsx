import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"

import {
  CompoundsService,
  ContainersService,
  InstrumentsService,
  MeasurementsService,
  SamplesService,
} from "@/client"
import { MeasurementTypeBadge } from "@/components/Domain/MeasurementTypeBadge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"
import { formatUtc } from "@/lib/format"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({ meta: [{ title: "Dashboard - Terminus" }] }),
})

const ONE = { query: { limit: 1 } }

const COUNTS = [
  {
    label: "Measurements",
    to: "/measurements",
    key: "measurements",
    fetch: async () =>
      (await MeasurementsService.readMeasurements(ONE)).data.count,
  },
  {
    label: "Samples",
    to: "/samples",
    key: "samples",
    fetch: async () => (await SamplesService.readSamples(ONE)).data.count,
  },
  {
    label: "Containers",
    to: "/containers",
    key: "containers",
    fetch: async () => (await ContainersService.readContainers(ONE)).data.count,
  },
  {
    label: "Instruments",
    to: "/instruments",
    key: "instruments",
    fetch: async () =>
      (await InstrumentsService.readInstruments(ONE)).data.count,
  },
  {
    label: "Compounds",
    to: "/compounds",
    key: "compounds",
    fetch: async () => (await CompoundsService.readCompounds(ONE)).data.count,
  },
] as const

function CountCard({ item }: { item: (typeof COUNTS)[number] }) {
  const { data, isLoading } = useQuery({
    queryKey: [item.key, "count"],
    queryFn: item.fetch,
  })
  return (
    <Link to={item.to}>
      <Card className="transition-colors hover:bg-muted/50">
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {item.label}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-8 w-16" />
          ) : (
            <span className="text-3xl font-bold tabular-nums">{data}</span>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}

function LatestMeasurements() {
  const { data, isLoading } = useQuery({
    queryKey: ["measurements", "latest"],
    queryFn: async () =>
      (await MeasurementsService.readMeasurements({ query: { limit: 8 } })).data
        .data,
  })
  return (
    <Card>
      <CardHeader>
        <CardTitle>Latest measurements</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col divide-y">
        {isLoading &&
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="my-2 h-6 w-full" />
          ))}
        {data?.length === 0 && (
          <p className="text-muted-foreground">No measurements yet.</p>
        )}
        {data?.map((m) => (
          <Link
            key={m.id}
            to="/measurements/$measurementId"
            params={{ measurementId: String(m.id) }}
            className="flex items-center gap-4 py-2 hover:bg-muted/50"
          >
            <span className="w-44 tabular-nums">
              {formatUtc(m.measured_at)}
            </span>
            <MeasurementTypeBadge type={m.type} />
            <span className="font-mono text-muted-foreground">
              {m.instrument_id}
            </span>
            {m.sample_id && <span className="font-mono">{m.sample_id}</span>}
          </Link>
        ))}
      </CardContent>
    </Card>
  )
}

function Dashboard() {
  const { user: currentUser } = useAuth()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="max-w-sm truncate text-2xl">
          Hi, {currentUser?.full_name || currentUser?.email}
        </h1>
        <p className="text-muted-foreground">Overview of the database</p>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        {COUNTS.map((item) => (
          <CountCard key={item.key} item={item} />
        ))}
      </div>
      <LatestMeasurements />
    </div>
  )
}
