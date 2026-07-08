import { cn } from "@/lib/cn";
import { LIBRARY_STATUS_LABEL } from "@/features/libraries/types";

const TONE: Record<string, string> = {
  installed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  installing: "border-brand-200 bg-brand-50 text-brand-700",
  queued: "border-sky-200 bg-sky-50 text-sky-700",
  pending: "border-gray-200 bg-gray-50 text-gray-600",
  failed: "border-red-200 bg-red-50 text-red-700",
  removed: "border-gray-200 bg-gray-100 text-gray-600",
};

export function LibraryStatusBadge({ status }: { status: string }) {
  const tone = TONE[status] ?? TONE.pending;
  const active = status === "installing" || status === "queued";
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", tone)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", {
        installed: "bg-emerald-500", installing: "bg-brand-500", queued: "bg-sky-500",
        pending: "bg-gray-400", failed: "bg-red-500", removed: "bg-gray-400",
      }[status] ?? "bg-gray-400", active && "animate-pulse")} />
      {LIBRARY_STATUS_LABEL[status] ?? status}
    </span>
  );
}
