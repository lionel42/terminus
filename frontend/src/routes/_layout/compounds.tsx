import { createFileRoute } from "@tanstack/react-router"

import {
  type CompoundCreate,
  type CompoundPublic,
  CompoundsService,
  type CompoundUpdate,
} from "@/client"
import { orDash, ReferencePage } from "@/components/Domain/ReferencePage"

export const Route = createFileRoute("/_layout/compounds")({
  component: Compounds,
  head: () => ({ meta: [{ title: "Compounds - Terminus" }] }),
})

function Compounds() {
  return (
    <ReferencePage<CompoundPublic>
      title="Compounds"
      subtitle="Species quantified in the chromatograms"
      entityLabel="Compound"
      queryKey="compounds"
      fields={[
        { name: "name", label: "Name", placeholder: "Methane" },
        { name: "formula", label: "Formula", placeholder: "CH4" },
        { name: "unit", label: "Unit", placeholder: "ppb" },
        { name: "description", label: "Description" },
      ]}
      columns={[
        { key: "name", header: "Name", cell: (c) => orDash(c.name) },
        { key: "formula", header: "Formula", cell: (c) => orDash(c.formula) },
        { key: "unit", header: "Unit", cell: (c) => orDash(c.unit) },
        {
          key: "description",
          header: "Description",
          cell: (c) => orDash(c.description),
        },
      ]}
      list={async (skip, limit) =>
        (await CompoundsService.readCompounds({ query: { skip, limit } })).data
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
