import type { InstrumentPublic, MeasurementPublic } from "@/client"
import type {
  FieldConfig,
  FormValues,
} from "@/components/Common/EntityFormDialog"
import { MEASUREMENT_TYPES, toDatetimeInput } from "@/lib/format"

export function measurementFields(
  instruments: InstrumentPublic[] | undefined,
): FieldConfig[] {
  return [
    {
      name: "type",
      label: "Type",
      type: "select",
      required: true,
      options: MEASUREMENT_TYPES.map((t) => ({ value: t, label: t })),
    },
    {
      name: "instrument_id",
      label: "Instrument",
      type: "select",
      required: true,
      options: (instruments ?? []).map((i) => ({ value: i.id, label: i.id })),
    },
    {
      name: "measured_at",
      label: "Measured at (UTC)",
      type: "datetime",
      required: true,
    },
    {
      name: "sample_id",
      label: "Sample",
      type: "id",
      description: "Leave empty for direct air, blanks, …",
    },
    { name: "description", label: "Description" },
  ]
}

export function measurementInitialValues(m: MeasurementPublic): FormValues {
  return {
    type: m.type,
    instrument_id: m.instrument_id,
    measured_at: toDatetimeInput(m.measured_at),
    sample_id: m.sample_id ?? "",
    description: m.description ?? "",
  }
}
