import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil, Plus } from "lucide-react"
import { useState } from "react"
import { type Resolver, useForm } from "react-hook-form"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { fromDatetimeInput } from "@/lib/format"
import { handleError } from "@/utils"

export type FieldConfig = {
  name: string
  label: string
  /** "id": lower-case alphanumeric identifier; "datetime": entered in UTC */
  type?: "text" | "id" | "datetime" | "select"
  required?: boolean
  placeholder?: string
  description?: string
  options?: { value: string; label: string }[]
}

export type FormValues = Record<string, string>

const NONE = "__none__"

function buildSchema(fields: FieldConfig[]) {
  const shape: Record<string, z.ZodType<string>> = {}
  for (const field of fields) {
    let schema = z.string().trim()
    if (field.type === "id") {
      schema = schema.regex(/^[A-Za-z0-9]*$/, {
        message: "Only letters and digits",
      })
    }
    shape[field.name] = field.required
      ? schema.min(1, { message: `${field.label} is required` })
      : schema
  }
  return z.object(shape)
}

/** Form values -> API body: ids lower-cased, datetimes as UTC ISO, "" -> null. */
export function toBody(fields: FieldConfig[], values: FormValues) {
  const body: Record<string, string | null> = {}
  for (const field of fields) {
    const value = values[field.name]?.trim() ?? ""
    if (!value || value === NONE) {
      body[field.name] = null
    } else if (field.type === "id") {
      body[field.name] = value.toLowerCase()
    } else if (field.type === "datetime") {
      body[field.name] = fromDatetimeInput(value)
    } else {
      body[field.name] = value
    }
  }
  return body
}

interface EntityFormDialogProps {
  mode: "create" | "edit"
  entityLabel: string
  fields: FieldConfig[]
  initialValues?: FormValues
  /** Receives the API body built from the form. */
  onSubmit: (body: Record<string, string | null>) => Promise<unknown>
  /** Query keys to refresh after a successful save. */
  invalidate: unknown[][]
  /** Called after a successful save (e.g. to close a dropdown menu). */
  onSuccess?: () => void
}

export function EntityFormDialog({
  mode,
  entityLabel,
  fields,
  initialValues,
  onSubmit,
  invalidate,
  onSuccess,
}: EntityFormDialogProps) {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const defaultValues = Object.fromEntries(
    fields.map((f) => [f.name, initialValues?.[f.name] ?? ""]),
  )
  const form = useForm<FormValues>({
    // Schema built at runtime from `fields`: every value is a string
    resolver: zodResolver(
      buildSchema(fields),
    ) as unknown as Resolver<FormValues>,
    mode: "onBlur",
    defaultValues,
  })

  const mutation = useMutation({
    mutationFn: (values: FormValues) => onSubmit(toBody(fields, values)),
    onSuccess: () => {
      showSuccessToast(
        `${entityLabel} ${mode === "create" ? "created" : "updated"} successfully`,
      )
      if (mode === "create") form.reset()
      setIsOpen(false)
      onSuccess?.()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      for (const queryKey of invalidate) {
        queryClient.invalidateQueries({ queryKey })
      }
    },
  })

  const title = `${mode === "create" ? "Add" : "Edit"} ${entityLabel}`

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        if (open && mode === "edit") form.reset(defaultValues)
      }}
    >
      {mode === "create" ? (
        <DialogTrigger asChild>
          <Button>
            <Plus className="mr-2" />
            {title}
          </Button>
        </DialogTrigger>
      ) : (
        <DropdownMenuItem
          onSelect={(e) => e.preventDefault()}
          onClick={() => setIsOpen(true)}
        >
          <Pencil />
          Edit
        </DropdownMenuItem>
      )}
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Fields marked with <span className="text-destructive">*</span> are
            required. Times are in UTC.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((v) => mutation.mutate(v))}>
            <div className="grid gap-4 py-4">
              {fields.map((config) => (
                <FormField
                  key={config.name}
                  control={form.control}
                  name={config.name}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {config.label}
                        {config.required && (
                          <span className="text-destructive"> *</span>
                        )}
                      </FormLabel>
                      <FormControl>
                        {config.type === "select" ? (
                          <Select
                            value={field.value || NONE}
                            onValueChange={field.onChange}
                          >
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder={config.placeholder} />
                            </SelectTrigger>
                            <SelectContent>
                              {!config.required && (
                                <SelectItem value={NONE}>—</SelectItem>
                              )}
                              {config.options?.map((option) => (
                                <SelectItem
                                  key={option.value}
                                  value={option.value}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Input
                            {...field}
                            type={
                              config.type === "datetime"
                                ? "datetime-local"
                                : "text"
                            }
                            step={config.type === "datetime" ? 1 : undefined}
                            placeholder={config.placeholder}
                          />
                        )}
                      </FormControl>
                      {config.description && (
                        <FormDescription>{config.description}</FormDescription>
                      )}
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ))}
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
