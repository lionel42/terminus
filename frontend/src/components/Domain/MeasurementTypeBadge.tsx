import type { MeasurementType } from "@/client"
import { Badge } from "@/components/ui/badge"

const VARIANTS: Record<MeasurementType, "default" | "secondary" | "outline"> = {
  air: "default",
  tank: "default",
  standard: "secondary",
  blank: "outline",
  labair: "outline",
  test: "outline",
}

export function MeasurementTypeBadge({ type }: { type: MeasurementType }) {
  return <Badge variant={VARIANTS[type] ?? "outline"}>{type}</Badge>
}
