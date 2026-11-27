import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil, Plus, Sparkles } from "lucide-react"
import { useState } from "react"
import { type Resolver, useForm } from "react-hook-form"

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
import {
  type Body,
  buildSchema,
  type FieldConfig,
  type FillAction,
  type FormValues,
  NONE,
  toBody,
} from "@/lib/forms"
import { handleError } from "@/utils"

export type {
  Body,
  FieldConfig,
  FillAction,
  FormValues,
} from "@/lib/forms"

interface EntityFormDialogProps {
  mode: "create" | "edit"
  entityLabel: string
  fields: FieldConfig[]
  initialValues?: FormValues
  /** Receives the API body built from the form. */
  onSubmit: (body: Body) => Promise<unknown>
  /** Query keys to refresh after a successful save. */
  invalidate: unknown[][]
  /** Called after a successful save (e.g. to close a dropdown menu). */
  onSuccess?: () => void
  /** Optional button that fills the empty fields from an external source. */
  fill?: FillAction
  /** Custom trigger for create mode (default: an "Add <entity>" button). */
  triggerLabel?: string
}

export function EntityFormDialog({
  mode,
  entityLabel,
  fields,
  initialValues,
  onSubmit,
  invalidate,
  onSuccess,
  fill,
  triggerLabel,
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

  const filler = useMutation({
    mutationFn: () => fill!.run(form.getValues()),
    onSuccess: (found) => {
      const filled: string[] = []
      for (const field of fields) {
        const value = found[field.name]
        if (value && !form.getValues(field.name)?.trim()) {
          form.setValue(field.name, value, { shouldDirty: true })
          filled.push(field.label)
        }
      }
      showSuccessToast(
        filled.length
          ? `Filled: ${filled.join(", ")}`
          : "Nothing new to fill (only empty fields are filled)",
      )
    },
    onError: handleError.bind(showErrorToast),
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
            {triggerLabel ?? title}
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
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
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
                            inputMode={
                              config.type === "number" ? "decimal" : undefined
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
              {fill && (
                <LoadingButton
                  type="button"
                  variant="secondary"
                  className="sm:mr-auto"
                  loading={filler.isPending}
                  onClick={() => filler.mutate()}
                >
                  <Sparkles className="mr-2" />
                  {fill.label}
                </LoadingButton>
              )}
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
