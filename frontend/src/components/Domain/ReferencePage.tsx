import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { type ReactNode, useState } from "react"

import { ActionsMenu } from "@/components/Common/ActionsMenu"
import { DeleteMenuItem } from "@/components/Common/DeleteMenuItem"
import {
  type Body,
  EntityFormDialog,
  type FieldConfig,
  type FillAction,
} from "@/components/Common/EntityFormDialog"
import { type Column, ServerTable } from "@/components/Common/ServerTable"
import useAuth from "@/hooks/useAuth"

export interface ReferencePageProps<T extends { id: string }> {
  title: string
  subtitle: string
  entityLabel: string
  queryKey: string
  /** Editable fields besides the id */
  fields: FieldConfig[]
  /** Displayed columns besides the id and the actions */
  columns: Column<T>[]
  list: (skip: number, limit: number) => Promise<{ data: T[]; count: number }>
  create: (body: Body) => Promise<unknown>
  update: (id: string, body: Body) => Promise<unknown>
  remove: (id: string) => Promise<unknown>
  /** Extra content per row, shown before the actions menu */
  rowExtras?: (row: T) => ReactNode
  /** Custom rendering of the id cell (e.g. a link to a detail page) */
  renderId?: (row: T) => ReactNode
  /** Optional "fill" button in the create/edit dialogs */
  fill?: FillAction
  /** Filter controls shown above the table */
  toolbar?: ReactNode
  /** Filter values used by `list`: part of the query key, resets the page */
  filters?: unknown
}

const PAGE_SIZE = 50

/** List + create/edit/delete page for compounds, instruments, containers. */
export function ReferencePage<T extends { id: string }>(
  props: ReferencePageProps<T>,
) {
  const { user } = useAuth()
  const canWrite = !!user?.is_superuser
  const [page, setPage] = useState(1)
  // Back to the first page whenever the filters change
  const filtersKey = JSON.stringify(props.filters ?? null)
  const [lastFiltersKey, setLastFiltersKey] = useState(filtersKey)
  if (filtersKey !== lastFiltersKey) {
    setLastFiltersKey(filtersKey)
    setPage(1)
  }

  const { data, isLoading } = useQuery({
    queryKey: [props.queryKey, page, filtersKey],
    queryFn: () => props.list((page - 1) * PAGE_SIZE, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  const idField: FieldConfig = {
    name: "id",
    label: "Id",
    type: "id",
    required: true,
    description: "Letters and digits only, stored in lower case",
  }

  const columns: Column<T>[] = [
    {
      key: "id",
      header: "Id",
      cell: (row) =>
        props.renderId ? (
          props.renderId(row)
        ) : (
          <span className="font-mono font-medium">{row.id}</span>
        ),
    },
    ...props.columns,
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      className: "text-right",
      cell: (row) => (
        <div className="flex items-center justify-end gap-2">
          {props.rowExtras?.(row)}
          {canWrite && (
            <ActionsMenu>
              {(close) => (
                <>
                  <EntityFormDialog
                    mode="edit"
                    entityLabel={props.entityLabel}
                    fields={props.fields}
                    initialValues={Object.fromEntries(
                      props.fields.map((f) => [
                        f.name,
                        String((row as Record<string, unknown>)[f.name] ?? ""),
                      ]),
                    )}
                    onSubmit={(body) => props.update(row.id, body)}
                    invalidate={[[props.queryKey]]}
                    onSuccess={close}
                    fill={props.fill}
                  />
                  <DeleteMenuItem
                    entityLabel={props.entityLabel}
                    name={row.id}
                    onDelete={() => props.remove(row.id)}
                    invalidate={[[props.queryKey]]}
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
          <h1 className="text-2xl font-bold tracking-tight">{props.title}</h1>
          <p className="text-muted-foreground">{props.subtitle}</p>
        </div>
        {canWrite && (
          <EntityFormDialog
            mode="create"
            entityLabel={props.entityLabel}
            fields={[idField, ...props.fields]}
            onSubmit={props.create}
            invalidate={[[props.queryKey]]}
            fill={props.fill}
          />
        )}
      </div>
      {props.toolbar}
      <ServerTable
        columns={columns}
        rows={data?.data}
        rowKey={(row) => row.id}
        isLoading={isLoading}
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.count ?? 0}
        onPageChange={setPage}
      />
    </div>
  )
}

/** Muted placeholder for empty optional values */
export const orDash = (value: string | null | undefined) =>
  value ? value : <span className="text-muted-foreground">—</span>
