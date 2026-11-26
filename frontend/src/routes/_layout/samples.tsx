import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useState } from "react"
import { z } from "zod"

import {
  type SampleCreate,
  type SamplePublic,
  SamplesService,
  type SampleUpdate,
} from "@/client"
import { ActionsMenu } from "@/components/Common/ActionsMenu"
import { DeleteMenuItem } from "@/components/Common/DeleteMenuItem"
import {
  EntityFormDialog,
  type FieldConfig,
} from "@/components/Common/EntityFormDialog"
import { type Column, ServerTable } from "@/components/Common/ServerTable"
import { orDash } from "@/components/Domain/ReferencePage"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import useAuth from "@/hooks/useAuth"
import { formatUtc, toDatetimeInput } from "@/lib/format"

const searchSchema = z.object({
  container_id: z.string().optional(),
  page: z.number().int().min(1).optional(),
})

export const Route = createFileRoute("/_layout/samples")({
  component: Samples,
  validateSearch: searchSchema,
  head: () => ({ meta: [{ title: "Samples - Terminus" }] }),
})

const PAGE_SIZE = 50

const FIELDS: FieldConfig[] = [
  { name: "container_id", label: "Container", type: "id", required: true },
  {
    name: "filled_at",
    label: "Filled at (UTC)",
    type: "datetime",
    required: true,
  },
  { name: "description", label: "Description" },
]

function Samples() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { user } = useAuth()
  const canWrite = !!user?.is_superuser
  const page = search.page ?? 1
  const [containerDraft, setContainerDraft] = useState(
    search.container_id ?? "",
  )

  const { data, isLoading } = useQuery({
    queryKey: ["samples", search],
    queryFn: async () =>
      (
        await SamplesService.readSamples({
          query: {
            container_id: search.container_id || undefined,
            skip: (page - 1) * PAGE_SIZE,
            limit: PAGE_SIZE,
          },
        })
      ).data,
    placeholderData: keepPreviousData,
  })

  const columns: Column<SamplePublic>[] = [
    {
      key: "id",
      header: "Id",
      cell: (s) => <span className="font-mono font-medium">{s.id}</span>,
    },
    {
      key: "container",
      header: "Container",
      cell: (s) => (
        <Link
          to="/samples"
          search={{ container_id: s.container_id }}
          className="font-mono underline-offset-4 hover:underline"
          onClick={() => setContainerDraft(s.container_id)}
        >
          {s.container_id}
        </Link>
      ),
    },
    {
      key: "filled_at",
      header: "Filled at (UTC)",
      cell: (s) => formatUtc(s.filled_at),
    },
    {
      key: "description",
      header: "Description",
      cell: (s) => orDash(s.description),
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      className: "text-right",
      cell: (s) => (
        <div className="flex items-center justify-end gap-2">
          <Button variant="link" size="sm" asChild>
            <Link to="/measurements" search={{ sample_id: s.id }}>
              Measurements
            </Link>
          </Button>
          {canWrite && (
            <ActionsMenu>
              {(close) => (
                <>
                  <EntityFormDialog
                    mode="edit"
                    entityLabel="Sample"
                    fields={FIELDS}
                    initialValues={{
                      container_id: s.container_id,
                      filled_at: toDatetimeInput(s.filled_at),
                      description: s.description ?? "",
                    }}
                    onSubmit={(body) =>
                      SamplesService.updateSample({
                        path: { sample_id: s.id },
                        body: body as SampleUpdate,
                      })
                    }
                    invalidate={[["samples"]]}
                    onSuccess={close}
                  />
                  <DeleteMenuItem
                    entityLabel="Sample"
                    name={s.id}
                    onDelete={() =>
                      SamplesService.deleteSample({ path: { sample_id: s.id } })
                    }
                    invalidate={[["samples"]]}
                    onSuccess={close}
                  />
                </>
              )}
            </ActionsMenu>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Samples</h1>
          <p className="text-muted-foreground">
            Air filled into containers, newest first
          </p>
        </div>
        {canWrite && (
          <EntityFormDialog
            mode="create"
            entityLabel="Sample"
            fields={[
              {
                name: "id",
                label: "Id",
                type: "id",
                required: true,
                description: "Letters and digits only, stored in lower case",
              },
              ...FIELDS,
            ]}
            initialValues={{ container_id: search.container_id ?? "" }}
            onSubmit={(body) =>
              SamplesService.createSample({ body: body as SampleCreate })
            }
            invalidate={[["samples"]]}
          />
        )}
      </div>

      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          navigate({
            search: { container_id: containerDraft.toLowerCase() || undefined },
          })
        }}
      >
        <Input
          className="max-w-xs"
          placeholder="Filter by container id"
          value={containerDraft}
          onChange={(e) => setContainerDraft(e.target.value)}
        />
        <Button type="submit">Filter</Button>
        {search.container_id && (
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setContainerDraft("")
              navigate({ search: {} })
            }}
          >
            Clear
          </Button>
        )}
      </form>

      <ServerTable
        columns={columns}
        rows={data?.data}
        rowKey={(s) => s.id}
        isLoading={isLoading}
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.count ?? 0}
        onPageChange={(p) => navigate({ search: { ...search, page: p } })}
      />
    </div>
  )
}
