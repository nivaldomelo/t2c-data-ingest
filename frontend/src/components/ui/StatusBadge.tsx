import { cn } from "@/lib/cn";

type Tone = {
  dot: string;
  text: string;
  bg: string;
  border: string;
};

const TONES: Record<string, Tone> = {
  success: { dot: "bg-emerald-500", text: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200" },
  running: { dot: "bg-brand-500", text: "text-brand-700", bg: "bg-brand-50", border: "border-brand-200" },
  failed: { dot: "bg-red-500", text: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
  timeout: { dot: "bg-amber-500", text: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200" },
  queued: { dot: "bg-sky-500", text: "text-sky-700", bg: "bg-sky-50", border: "border-sky-200" },
  cancelled: { dot: "bg-gray-400", text: "text-gray-600", bg: "bg-gray-100", border: "border-gray-200" },
  skipped: { dot: "bg-gray-400", text: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200" },
  active: { dot: "bg-emerald-500", text: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200" },
  inactive: { dot: "bg-gray-400", text: "text-gray-600", bg: "bg-gray-100", border: "border-gray-200" },
  unreachable: { dot: "bg-red-500", text: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
};

const LABELS: Record<string, string> = {
  success: "Sucesso",
  running: "Executando",
  failed: "Falhou",
  timeout: "Timeout",
  queued: "Na fila",
  cancelled: "Cancelado",
  skipped: "Ignorado",
  active: "Ativo",
  inactive: "Inativo",
  unreachable: "Inacessível",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const tone = TONES[status] ?? TONES.cancelled;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tone.bg,
        tone.text,
        tone.border
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", tone.dot, status === "running" && "animate-pulse")} />
      {label ?? LABELS[status] ?? status}
    </span>
  );
}
