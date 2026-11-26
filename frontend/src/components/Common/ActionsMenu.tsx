import { EllipsisVertical } from "lucide-react"
import { type ReactNode, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

/** "⋮" menu; `children` receives a callback that closes the menu. */
export function ActionsMenu({
  children,
}: {
  children: (close: () => void) => ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Actions">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {children(() => setOpen(false))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
