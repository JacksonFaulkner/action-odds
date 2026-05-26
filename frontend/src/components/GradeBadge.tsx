import { cn } from "@/lib/utils"
import type { Grade } from "@/types"

const styles: Record<Grade, string> = {
  A: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  B: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  C: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  D: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  F: "bg-red-500/15 text-red-400 border-red-500/30",
}

export function GradeBadge({ grade }: { grade: Grade }) {
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded border text-xs font-bold", styles[grade])}>
      {grade}
    </span>
  )
}
