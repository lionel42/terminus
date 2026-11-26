import { createFileRoute, Link } from "@tanstack/react-router"

import {
  type ContainerCreate,
  type ContainerPublic,
  ContainersService,
  type ContainerUpdate,
} from "@/client"
import { orDash, ReferencePage } from "@/components/Domain/ReferencePage"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_layout/containers")({
  component: Containers,
  head: () => ({ meta: [{ title: "Containers - Terminus" }] }),
})

function Containers() {
  return (
    <ReferencePage<ContainerPublic>
      title="Containers"
      subtitle="Flasks, canisters, … that are filled with air samples"
      entityLabel="Container"
      queryKey="containers"
      fields={[
        { name: "kind", label: "Kind", placeholder: "flask" },
        { name: "description", label: "Description" },
      ]}
      columns={[
        { key: "kind", header: "Kind", cell: (c) => orDash(c.kind) },
        {
          key: "description",
          header: "Description",
          cell: (c) => orDash(c.description),
        },
      ]}
      rowExtras={(container) => (
        <Button variant="link" size="sm" asChild>
          <Link to="/samples" search={{ container_id: container.id }}>
            Filling history
          </Link>
        </Button>
      )}
      list={async (skip, limit) =>
        (await ContainersService.readContainers({ query: { skip, limit } }))
          .data
      }
      create={(body) =>
        ContainersService.createContainer({ body: body as ContainerCreate })
      }
      update={(id, body) =>
        ContainersService.updateContainer({
          path: { container_id: id },
          body: body as ContainerUpdate,
        })
      }
      remove={(id) =>
        ContainersService.deleteContainer({ path: { container_id: id } })
      }
    />
  )
}
