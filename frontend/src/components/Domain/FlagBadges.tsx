import { useQuery } from "@tanstack/react-query"
import { MessageSquare } from "lucide-react"

import { MeasurementsService } from "@/client"
import { orDash } from "@/components/Domain/ReferencePage"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { flagLabel, setFlags } from "@/lib/flags"

/** The quality flag bits of the server (they never change while running). */
export function useFlagInfos() {
  return useQuery({
    queryKey: ["measurements", "flags"],
    queryFn: async () => (await MeasurementsService.readFlags()).data,
    staleTime: Number.POSITIVE_INFINITY,
  })
}

interface FlagBadgesProps {
  flags: number
  comment?: string | null
  /** For a result: the flags of its whole measurement */
  runFlags?: number
  runComment?: string | null
}

/** The flags as badges (red: unusable), their meaning and comments on hover. */
export function FlagBadges({
  flags,
  comment,
  runFlags = 0,
  runComment,
}: FlagBadgesProps) {
  const { data: infos = [] } = useFlagInfos()
  const set = setFlags(flags | runFlags, infos)
  if (!set.length && !comment && !runComment) {
    return orDash(null)
  }
  const notes = [
    ...set.map((f) => `${flagLabel(f)}: ${f.description}`),
    ...(runComment ? [`Run: ${runComment}`] : []),
    ...(comment
      ? [runFlags || runComment ? `Compound: ${comment}` : comment]
      : []),
  ]
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex flex-wrap items-center gap-1">
          {set.map((f) => (
            <Badge
              key={f.name}
              variant={f.unusable ? "destructive" : "outline"}
            >
              {flagLabel(f)}
              {(runFlags & f.value) !== 0 &&
                (flags & f.value) === 0 &&
                " (run)"}
            </Badge>
          ))}
          {(comment || runComment) && (
            <MessageSquare
              className="size-3.5 text-muted-foreground"
              aria-label="Flag comment"
            />
          )}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm">
        {notes.map((note) => (
          <p key={note}>{note}</p>
        ))}
      </TooltipContent>
    </Tooltip>
  )
}
