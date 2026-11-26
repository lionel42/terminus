import { createFileRoute, Link } from "@tanstack/react-router"

import {
  type InstrumentCreate,
  type InstrumentPublic,
  InstrumentsService,
  type InstrumentUpdate,
} from "@/client"
import { orDash, ReferencePage } from "@/components/Domain/ReferencePage"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_layout/instruments")({
  component: Instruments,
  head: () => ({ meta: [{ title: "Instruments - Terminus" }] }),
})

function Instruments() {
  return (
    <ReferencePage<InstrumentPublic>
      title="Instruments"
      subtitle="Chromatographs the measurements are made on"
      entityLabel="Instrument"
      queryKey="instruments"
      fields={[
        { name: "name", label: "Name", placeholder: "Medusa GC-MS" },
        { name: "description", label: "Description" },
      ]}
      columns={[
        { key: "name", header: "Name", cell: (i) => orDash(i.name) },
        {
          key: "description",
          header: "Description",
          cell: (i) => orDash(i.description),
        },
      ]}
      rowExtras={(instrument) => (
        <Button variant="link" size="sm" asChild>
          <Link to="/measurements" search={{ instrument_id: instrument.id }}>
            Measurements
          </Link>
        </Button>
      )}
      list={async (skip, limit) =>
        (await InstrumentsService.readInstruments({ query: { skip, limit } }))
          .data
      }
      create={(body) =>
        InstrumentsService.createInstrument({ body: body as InstrumentCreate })
      }
      update={(id, body) =>
        InstrumentsService.updateInstrument({
          path: { instrument_id: id },
          body: body as InstrumentUpdate,
        })
      }
      remove={(id) =>
        InstrumentsService.deleteInstrument({ path: { instrument_id: id } })
      }
    />
  )
}
