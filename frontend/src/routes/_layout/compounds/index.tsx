import { createFileRoute, Link } from "@tanstack/react-router"
import { useState } from "react"

import {
  type CompoundCreate,
  type CompoundPublicWithDetails,
  type CompoundStatus,
  CompoundsService,
  type CompoundUpdate,
} from "@/client"
import {
  CompoundLinks,
  CompoundStatusBadge,
  compoundFields,
  pubchemFill,
} from "@/components/Domain/compoundFields"
import { orDash, ReferencePage } from "@/components/Domain/ReferencePage"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { COMPOUND_STATUSES } from "@/lib/compound"

export const Route = createFileRoute("/_layout/compounds/")({
  component: Compounds,
  head: () => ({ meta: [{ title: "Compounds - Terminus" }] }),
})

const ALL = "__all__"

function Compounds() {
  const [draft, setDraft] = useState("")
  const [q, setQ] = useState("")
  const [status, setStatus] = useState<CompoundStatus | undefined>()

  const toolbar = (
    <form
      className="flex flex-wrap items-center gap-3"
      onSubmit={(e) => {
        e.preventDefault()
        setQ(draft.trim())
      }}
    >
      <Input
        className="w-72"
        placeholder="Search id, name, CAS, alias…"
        aria-label="Search compounds"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      <Select
        value={status ?? ALL}
        onValueChange={(v) =>
          setStatus(v === ALL ? undefined : (v as CompoundStatus))
        }
      >
        <SelectTrigger className="w-40" aria-label="Status">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Any status</SelectItem>
          {COMPOUND_STATUSES.map((s) => (
            <SelectItem key={s} value={s}>
              {s}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button type="submit" variant="secondary">
        Search
      </Button>
    </form>
  )

  return (
    <ReferencePage<CompoundPublicWithDetails>
      title="Compounds"
      subtitle="Species quantified in the chromatograms"
      entityLabel="Compound"
      queryKey="compounds"
      fields={compoundFields}
      fill={pubchemFill}
      toolbar={toolbar}
      filters={{ q, status }}
      renderId={(c) => (
        <Link
          to="/compounds/$compoundId"
          params={{ compoundId: c.id }}
          className="font-mono font-medium underline-offset-4 hover:underline"
        >
          {c.id}
        </Link>
      )}
      columns={[
        {
          key: "industrial_name",
          header: "Industrial name",
          cell: (c) => orDash(c.industrial_name),
        },
        {
          key: "iupac_name",
          header: "IUPAC name",
          cell: (c) => (
            <span
              className="block max-w-64 truncate"
              title={c.iupac_name ?? ""}
            >
              {orDash(c.iupac_name)}
            </span>
          ),
        },
        { key: "formula", header: "Formula", cell: (c) => orDash(c.formula) },
        {
          key: "status",
          header: "Status",
          cell: (c) => <CompoundStatusBadge status={c.status} />,
        },
        { key: "unit", header: "Unit", cell: (c) => orDash(c.unit) },
        {
          key: "cas_number",
          header: "CAS",
          cell: (c) => (
            <span className="font-mono">{orDash(c.cas_number)}</span>
          ),
        },
        {
          key: "aliases",
          header: "Aliases",
          cell: (c) => {
            const aliases = (c.aliases ?? []).map((a) => a.alias).join(", ")
            return (
              <span
                className="block max-w-56 truncate text-muted-foreground"
                title={aliases}
              >
                {aliases || "—"}
              </span>
            )
          },
        },
      ]}
      rowExtras={(c) => <CompoundLinks compound={c} />}
      list={async (skip, limit) =>
        (
          await CompoundsService.readCompounds({
            query: { skip, limit, q: q || undefined, status },
          })
        ).data
      }
      create={(body) =>
        CompoundsService.createCompound({ body: body as CompoundCreate })
      }
      update={(id, body) =>
        CompoundsService.updateCompound({
          path: { compound_id: id },
          body: body as CompoundUpdate,
        })
      }
      remove={(id) =>
        CompoundsService.deleteCompound({ path: { compound_id: id } })
      }
    />
  )
}
