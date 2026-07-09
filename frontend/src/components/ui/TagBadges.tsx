import { cn } from "@/lib/cn";
import type { TagLite } from "@/features/tags/types";

/** Compact tag badges with overflow (+N). Neutral gray, subtle orange hover. */
export function TagBadges({ tags, max = 3, className }: { tags: TagLite[]; max?: number; className?: string }) {
  if (!tags?.length) return <span className="text-xs text-gray-300">—</span>;
  const shown = tags.slice(0, max);
  const extra = tags.length - shown.length;
  return (
    <div className={cn("flex flex-wrap items-center gap-1", className)}>
      {shown.map((t) => (
        <span
          key={t.id ?? t.slug}
          className="inline-flex items-center rounded-md border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[11px] font-medium text-gray-600 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700"
        >
          {t.name}
        </span>
      ))}
      {extra > 0 && (
        <span className="inline-flex items-center rounded-md bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-500" title={tags.slice(max).map((t) => t.name).join(", ")}>
          +{extra}
        </span>
      )}
    </div>
  );
}
